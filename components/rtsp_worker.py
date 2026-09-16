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
_running: set[str] = set()

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
        _running.add(rtsp_url)
    thread = threading.Thread(target=_worker_loop, args=(rtsp_url,), daemon=True)
    thread.start()


def stop_worker(rtsp_url: str) -> None:
    """Signals the worker for this URL to stop and releases its cached
    frame. The worker's own loop notices _running no longer contains
    its url within one read cycle and exits, killing its FFmpeg
    subprocess - see this module's own docstring for why this matters
    on reconnect."""
    with _lock:
        _running.discard(rtsp_url)
        _latest_frames.pop(rtsp_url, None)


def stop_all() -> None:
    """Call on app shutdown."""
    with _lock:
        _running.clear()
        _latest_frames.clear()


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

    -stimeout (microseconds): bounds how long FFmpeg's own
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
        "-stimeout", "5000000",
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

# UNCONDITIONAL periodic respawn, separate from the stall watchdog
# above. Forcing a fresh FFmpeg process (and therefore a fresh RTSP
# session) on a fixed cadence guarantees a clean keyframe periodically
# even if nothing LOOKS wrong - kept as a defensive measure carried
# over from the pre-rewrite diagnosis, though the subprocess rewrite
# (point 4 in the module docstring) may make this unnecessary in
# practice now that the root cause looks fixed; re-evaluate against
# real hardware over time.
_FORCED_RESPAWN_S = 25.0

_READ_CHUNK = 4096


def _worker_loop(rtsp_url: str) -> None:
    proc: subprocess.Popen | None = None
    buffer = bytearray()
    last_good = time.monotonic()
    spawned_at = time.monotonic()
    try:
        while True:
            with _lock:
                if rtsp_url not in _running:
                    return
            stalled = (time.monotonic() - last_good) > _MAX_STALL_S
            due_for_respawn = (time.monotonic() - spawned_at) > _FORCED_RESPAWN_S
            if proc is None or proc.poll() is not None or stalled or due_for_respawn:
                if proc is not None:
                    _terminate(proc)
                proc = _spawn(rtsp_url)
                buffer.clear()
                last_good = time.monotonic()
                spawned_at = time.monotonic()
                continue

            chunk = proc.stdout.read(_READ_CHUNK)
            if not chunk:
                time.sleep(0.05)
                continue
            buffer.extend(chunk)

            frame = _extract_latest_jpeg(buffer)
            if frame is None:
                continue

            last_good = time.monotonic()
            with _lock:
                _latest_frames[rtsp_url] = frame
    finally:
        if proc is not None:
            _terminate(proc)
        with _lock:
            _running.discard(rtsp_url)
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
