"""RTSP-to-MJPEG bridge for embedding the Dwarf's live-view RTSP stream
in-browser (browsers can't play RTSP natively - see camera_stream.py's
own module docstring). Spawns FFmpeg as a subprocess per camera
(REWRITTEN Sep 2026 - see point 4 below) and re-serves its MJPEG output
as a continuous multipart/x-mixed-replace HTTP stream, which any <img>
tag can embed directly.

Kept SEPARATE from camera_stream.py (which only builds UI) - this
module owns the worker threads and the FastAPI route, camera_stream.py
just starts/stops workers and points an <img> at the route.

DESIGN NOTES:

1. NO per-frame stderr redirection. An earlier version wrapped every
   frame read in os.dup2() calls to silence FFmpeg's native (C-level)
   decode warnings - but os.dup2() rewrites the PROCESS-WIDE stderr
   file descriptor, not something thread-local. With more than one
   camera/device streaming at once, concurrent workers' redirect/
   restore cycles raced on the SAME file descriptor - a real source of
   blocking, and it also silenced this app's OWN logging (via
   my_logger.py) for the duration. FFmpeg's own verbosity is
   controlled via its -loglevel flag instead (see _ffmpeg_cmd()) - no
   process-wide file descriptor surgery needed.

2. ONE delivery mechanism only (continuous multipart stream), not a
   continuous stream AND a separately-polled single-snapshot endpoint
   pointed at the same <img> in alternation - the earlier version did
   both, so the image kept getting torn down and re-fetched from
   scratch every couple of seconds even while the continuous stream
   was working fine, which read as stuttering/blocking.

3. Explicit stop_worker() rather than only relying on threads dying
   naturally - camera_stream.py calls this when a camera stops being
   confirmed-RTSP (mode flip to JPEG, or an unknown state after a
   reconnect - see that module's own corrected default). Most RTSP
   servers on embedded devices only accept one client at a time, so a
   stale worker still holding the connection open would block a fresh
   one from connecting after a reconnect.

4. FFmpeg driven directly via subprocess, NOT cv2.VideoCapture
   (user-reported Sep 2026: persistent HEVC "Could not find ref with
   POC 0" / "Duplicate POC" errors and grey/corrupted frames on the
   Dwarf Mini's stream, reproduced even on a fast PC - ruling out both
   Wi-Fi packet loss and CPU/decode speed as the cause. A whole series
   of OPENCV_FFMPEG_CAPTURE_OPTIONS tuning attempts (max_delay,
   fflags;discardcorrupt, thread_type;slice, reorder_queue_size,
   rtsp_transport udp vs tcp, buffer_size) never fully resolved it.
   Decisive test: running plain `ffmpeg -rtsp_transport tcp -i
   <same rtsp url> -f null -` from the command line on the SAME
   machine/network/stream produced ZERO POC errors - only 3 unrelated,
   benign "invalid increasing DTS to muxer" warnings - while VLC (which
   also doesn't go through OpenCV) played the same stream cleanly the
   whole time. This isolated the bug to OpenCV's cv2.CAP_FFMPEG wrapper
   itself, not FFmpeg, not the network, not decode speed. Spawning
   FFmpeg exactly as the working CLI test did, and reading its MJPEG
   output directly, sidesteps that wrapper entirely.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import shutil
import subprocess
import threading
import time

from fastapi import Response
from fastapi.responses import StreamingResponse
from nicegui import app

from components.i18n import t

_BLACK_1PX = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXNSR0IArs4c6QAAAA1JREFUGFdjYGBg"
    "+A8AAQQBAHAgZQsAAAAASUVORK5CYII="
)
_PLACEHOLDER_JPEG = base64.b64decode(_BLACK_1PX)

_JPEG_SOI = b"\xff\xd8"
_JPEG_EOI = b"\xff\xd9"

_lock = threading.Lock()
_latest_frames: dict[str, bytes] = {}
# url -> generation token of the worker that currently owns it. A token
# rather than a plain set so a stop_worker() immediately followed by a
# start_worker() (camera_stream.py does exactly this on reconnect) can't
# be undone by the OLD worker's own cleanup removing the NEW one's entry.
_running: dict[str, object] = {}

_FFMPEG_INSTALL_URL = "https://www.gyan.dev/ffmpeg/builds/"


def check_ffmpeg_available() -> bool:
    """Call once at app startup (astro_dwarf_ui.py's own main()) - since
    the rewrite from cv2.VideoCapture to a direct FFmpeg subprocess (see
    module docstring point 4), the RTSP preview silently does nothing
    useful if FFmpeg isn't on PATH: _spawn() would raise FileNotFoundError
    only the FIRST time a camera preview is opened, buried inside a
    background worker thread where the person would never see it. This
    surfaces the problem immediately and clearly instead, with a direct
    link to a working Windows build (the one confirmed during diagnosis
    to decode this app's RTSP stream cleanly - see module docstring),
    rather than leaving someone to guess why the live preview never
    shows anything.

    Deliberately NOT auto-downloading/installing FFmpeg (considered and
    reverted, Sep 2026) - a manual install keeps the app's own package
    small, needs no network access or extra write location at startup,
    and avoids a packaged .exe silently downloading and running another
    .exe on its own, which some antivirus/SmartScreen setups flag. The
    app works fully otherwise; only the RTSP live preview is affected.

    Uses t("ffmpeg_missing") (components/locales/) so the message
    follows the app's configured language (get_language(), stored in
    app.storage.general) rather than being hardcoded to one language -
    this runs before ui.run() starts serving, but get_language() already
    falls back safely to the default language if storage isn't ready
    yet at that point.
    """
    if shutil.which("ffmpeg") is not None:
        return True
    logging.getLogger(__name__).error(t("ffmpeg_missing", url=_FFMPEG_INSTALL_URL))
    return False


def start_worker(rtsp_url: str) -> None:
    """Idempotent - safe to call every time a preview becomes visible,
    even if a worker for this exact URL is already running."""
    with _lock:
        if rtsp_url in _running:
            return
        token = object()
        _running[rtsp_url] = token
    thread = threading.Thread(target=_worker_loop, args=(rtsp_url, token), daemon=True)
    thread.start()


def stop_worker(rtsp_url: str) -> None:
    """Signals the worker for this URL to stop and releases its cached
    frame. The worker's own loop notices _running no longer contains
    its url within one read cycle and exits, killing its FFmpeg
    subprocess - see this module's own docstring for why this matters
    on reconnect."""
    with _lock:
        _running.pop(rtsp_url, None)
        _latest_frames.pop(rtsp_url, None)


def stop_all() -> None:
    """Call on app shutdown."""
    with _lock:
        _running.clear()
        _latest_frames.clear()


_timeout_option_cache: str | None = None


def _timeout_option() -> str:
    """Name of the RTSP socket I/O timeout option for the installed
    FFmpeg (user-reported Oct 2026: the stream never started with a
    recent FFmpeg until -stimeout was replaced by -timeout).
    FFmpeg <= 4.x: -stimeout (microseconds); there -timeout means
    something else entirely (seconds to wait for an INCOMING connection,
    implying listen mode), so it can't simply be used everywhere.
    FFmpeg >= 5.0: -stimeout removed, -timeout is the socket I/O
    timeout in microseconds. Probed once from the RTSP demuxer's own
    help and cached; falls back to -timeout (current FFmpeg) if the
    probe fails."""
    global _timeout_option_cache
    if _timeout_option_cache is None:
        option = "-timeout"
        try:
            kwargs = {}
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            out = subprocess.run(
                ["ffmpeg", "-hide_banner", "-h", "demuxer=rtsp"],
                capture_output=True, text=True, timeout=10, **kwargs,
            )
            if "-stimeout" in out.stdout + out.stderr:
                option = "-stimeout"
        except (OSError, subprocess.SubprocessError):
            pass
        _timeout_option_cache = option
    return _timeout_option_cache


def _ffmpeg_cmd(rtsp_url: str) -> list[str]:
    """Mirrors the exact CLI invocation confirmed clean of HEVC POC
    errors during diagnosis (see module docstring point 4), with only
    an output format change: MJPEG frames on stdout instead of -f null,
    since those frames ARE the deliverable here. Deliberately minimal -
    none of the OPENCV_FFMPEG_CAPTURE_OPTIONS tuning tried earlier
    (max_delay, discardcorrupt, thread_type, reorder_queue_size,
    buffer_size) proved necessary once the OpenCV wrapper itself was
    removed from the picture; re-add here individually, only if a
    specific symptom reappears against real hardware.

    -stimeout / -timeout (microseconds, name depends on the FFmpeg
    version - see _timeout_option()): bounds how long FFmpeg's own
    connection/read attempt can block before giving up with an error,
    rather than hanging indefinitely against an address that never
    responds. Matches the value used throughout earlier diagnosis.

    -q:v 5: MJPEG quality (FFmpeg scale: 1=best/largest,
    31=worst/smallest) - moderate compression, roughly comparable to
    the JPEG quality=70 used by the previous cv2.imencode() step.
    """
    return [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        _timeout_option(), "5000000",
        "-i", rtsp_url,
        "-an",
        "-f", "mjpeg",
        "-q:v", "5",
        "-loglevel", "quiet",
        "pipe:1",
    ]


def _spawn(rtsp_url: str) -> subprocess.Popen:
    kwargs = {}
    if os.name == "nt":
        # Suppress the console window FFmpeg would otherwise flash open
        # on Windows (this app is Windows-deployed - see the VLC
        # screenshot used during diagnosis).
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(
        _ffmpeg_cmd(rtsp_url),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        bufsize=0,
        **kwargs,
    )


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            pass


def _extract_latest_jpeg(buffer: bytearray) -> bytes | None:
    """Scans buffer for complete JPEG frames (SOI...EOI) and returns
    only the LAST one found, discarding any earlier complete frames
    and consuming everything up to the end of the one returned. This
    is the direct replacement for the old cv2-based drain loop
    (_DRAIN_MAX repeated cap.grab() calls) - same goal (never display
    a stale, backlogged frame - see the Dwarf 3 growing-latency
    diagnosis earlier in this project), simpler here since we're
    parsing FFmpeg's own MJPEG byte stream directly rather than going
    through a capture API. Incomplete trailing data is left in buffer
    for the next read to complete."""
    last_frame = None
    while True:
        start = buffer.find(_JPEG_SOI)
        if start == -1:
            buffer.clear()
            break
        end = buffer.find(_JPEG_EOI, start + 2)
        if end == -1:
            if start > 0:
                del buffer[:start]
            break
        end += 2
        last_frame = bytes(buffer[start:end])
        del buffer[:end]
    return last_frame


# If no complete JPEG frame has been extracted for this long, force an
# FFmpeg respawn rather than let the worker keep reading indefinitely
# against a stalled process or connection.
_MAX_STALL_S = 8.0

# Periodic respawn while frames ARE arriving, separate from the stall
# watchdog above: a fresh FFmpeg process (fresh RTSP session, fresh
# keyframe) on a fixed cadence. Carried over from the cv2.VideoCapture
# era (module docstring point 4), when a broken HEVC decode never
# healed by itself. DISABLED by default since Oct 2026: with FFmpeg
# driven directly the decode no longer degrades, and each respawn cost
# a visible freeze (reconnect + wait for a keyframe) plus a new RTSP
# session every 25 s - one that could take the stream back from the
# phone app, or lose it to it. The stall watchdog still covers a stream
# that really stops. Re-enable for comparison by setting the
# environment variable ASTRO_DWARF_RTSP_RESPAWN_S to the period in
# seconds (25 = previous behaviour); 0 or unset = disabled.
def _forced_respawn_s() -> float:
    try:
        return max(0.0, float(os.environ.get("ASTRO_DWARF_RTSP_RESPAWN_S", "0")))
    except ValueError:
        return 0.0


_FORCED_RESPAWN_S = _forced_respawn_s()

_READ_CHUNK = 4096

# How often the worker checks its timers / stop flag while the reader
# thread blocks on FFmpeg's stdout.
_POLL_S = 0.25

# Retry delay when an FFmpeg run ends without delivering a single frame
# (Dwarf refusing the session while another client - typically the
# phone app - holds the stream, or the Dwarf unreachable): doubles on
# each such failure up to the max, back to the min after a good frame.
_RETRY_MIN_S = 1.0
_RETRY_MAX_S = 10.0


def _owns(rtsp_url: str, token: object) -> bool:
    with _lock:
        return _running.get(rtsp_url) is token


def _pump(proc: subprocess.Popen, rtsp_url: str, token: object, state: dict) -> None:
    """Reader thread for ONE FFmpeg process: blocks on its stdout and
    publishes complete frames. Kept off the worker's own thread
    (user-reported Oct 2026: the preview didn't always come back after
    another client took over the stream) - a blocking read() there meant
    the stall / forced-respawn timers were only checked BETWEEN reads,
    so an FFmpeg still alive but receiving nothing (the Dwarf keeping
    the old session open without sending data) blocked the worker
    forever. Here the worker keeps its timers and simply terminates the
    process, which ends this read with EOF."""
    buffer = bytearray()
    try:
        while True:
            chunk = proc.stdout.read(_READ_CHUNK)
            if not chunk:
                return
            buffer.extend(chunk)
            frame = _extract_latest_jpeg(buffer)
            if frame is None:
                continue
            state["last_good"] = time.monotonic()
            state["got_frame"] = True
            with _lock:
                if _running.get(rtsp_url) is not token:
                    return
                _latest_frames[rtsp_url] = frame
    except (OSError, ValueError):
        # stdout closed under us by _terminate() - normal on respawn.
        return


def _worker_loop(rtsp_url: str, token: object) -> None:
    retry_delay = _RETRY_MIN_S
    try:
        while _owns(rtsp_url, token):
            proc = _spawn(rtsp_url)
            spawned_at = time.monotonic()
            state = {"last_good": spawned_at, "got_frame": False}
            reader = threading.Thread(
                target=_pump, args=(proc, rtsp_url, token, state), daemon=True
            )
            reader.start()
            try:
                while _owns(rtsp_url, token):
                    if proc.poll() is not None or not reader.is_alive():
                        break
                    now = time.monotonic()
                    if now - state["last_good"] > _MAX_STALL_S:
                        break
                    if (
                        _FORCED_RESPAWN_S > 0
                        and now - spawned_at > _FORCED_RESPAWN_S
                        and state["got_frame"]
                    ):
                        break
                    time.sleep(_POLL_S)
            finally:
                _terminate(proc)
                reader.join(timeout=2.0)

            if state["got_frame"]:
                retry_delay = _RETRY_MIN_S
                continue
            # No frame at all from this run: don't hammer the Dwarf with
            # back-to-back reconnects while another client holds the
            # stream - wait (still reacting to stop_worker()) and retry.
            # The last good frame is dropped so the preview doesn't sit
            # on a frozen image meanwhile.
            with _lock:
                if _running.get(rtsp_url) is token:
                    _latest_frames.pop(rtsp_url, None)
            deadline = time.monotonic() + retry_delay
            while time.monotonic() < deadline and _owns(rtsp_url, token):
                time.sleep(_POLL_S)
            retry_delay = min(retry_delay * 2, _RETRY_MAX_S)
    finally:
        with _lock:
            if _running.get(rtsp_url) is token:
                del _running[rtsp_url]
                _latest_frames.pop(rtsp_url, None)


def register_routes() -> None:
    """Call once at app startup (astro_dwarf_ui.py's own main(), same
    pattern as register_manifest_route())."""

    @app.get("/video/rtsp_stream/{ip}/{channel}")
    async def rtsp_stream(ip: str, channel: int):
        rtsp_url = f"rtsp://{ip}/ch{channel}/stream0"
        start_worker(rtsp_url)

        async def frame_generator():
            try:
                while True:
                    with _lock:
                        still_running = rtsp_url in _running
                        frame_bytes = _latest_frames.get(rtsp_url)
                    if not still_running:
                        return
                    if frame_bytes:
                        yield (
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                            + frame_bytes
                            + b"\r\n"
                        )
                    await asyncio.sleep(0.03)
            except asyncio.CancelledError:
                # Browser navigated away / tab closed - not an error,
                # just the client disconnecting from the stream.
                return

        return StreamingResponse(
            frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame"
        )

    @app.get("/video/rtsp_snapshot/{ip}/{channel}")
    async def rtsp_snapshot(ip: str, channel: int) -> Response:
        """Single-frame fallback (e.g. for a context where an <img> tag
        can't stay open, unlike the main embedded preview above, which
        should always prefer the continuous stream route instead)."""
        rtsp_url = f"rtsp://{ip}/ch{channel}/stream0"
        with _lock:
            frame_bytes = _latest_frames.get(rtsp_url)
        if frame_bytes is None:
            return Response(content=_PLACEHOLDER_JPEG, media_type="image/png")
        return Response(content=frame_bytes, media_type="image/jpeg")
