"""RTSP-to-MJPEG bridge for embedding the Dwarf's live-view RTSP stream
in-browser (browsers can't play RTSP natively - see camera_stream.py's
own module docstring). Decodes with OpenCV/FFmpeg in a background
thread per camera and re-serves the latest frame as a continuous
multipart/x-mixed-replace HTTP stream, which any <img> tag can embed
directly.

Kept SEPARATE from camera_stream.py (which only builds UI) - this
module owns the worker threads and the FastAPI route, camera_stream.py
just starts/stops workers and points an <img> at the route.

DESIGN NOTES (user-reported Sep 2026, from a working proof-of-concept
that had blocking/latency issues once merged in):

1. NO per-frame stderr redirection. An earlier version wrapped every
   cap.read() in os.dup2() calls to silence FFmpeg's native (C-level)
   decode warnings - but os.dup2() rewrites the PROCESS-WIDE stderr
   file descriptor, not something thread-local. With more than one
   camera/device streaming at once, concurrent workers' redirect/
   restore cycles raced on the SAME file descriptor - a real source of
   the reported blocking, and it also silenced this app's OWN logging
   (via my_logger.py) for the duration, losing trace of everything
   else. FFmpeg's own verbosity is controlled at the source instead,
   via OPENCV_FFMPEG_CAPTURE_OPTIONS' "loglevel;quiet" (already set
   below) - no process-wide file descriptor surgery needed.

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
"""
from __future__ import annotations

import asyncio
import base64
import os
import threading
import time

import cv2
from fastapi import Response
from fastapi.responses import StreamingResponse
from nicegui import app

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    # stimeout (microseconds): bounds how long FFmpeg's own native
    # connection/read attempt can block before giving up with an error,
    # rather than potentially hanging far longer against an address
    # that never responds at all (confirmed by testing: an unreachable
    # address left the native thread blocked long enough that a
    # process exit while it was still in progress triggered a native
    # abort - stop_worker()'s own _running flag can only be noticed
    # BETWEEN native calls, not during one already in progress). 5s.
    #
    # max_delay lowered from 0, "nobuffer" flag REMOVED (user-reported
    # Sep 2026, real hardware over Wi-Fi: stream was visibly choppy -
    # "bouge mais peu" - with repeated HEVC decode errors: "Could not
    # find ref with POC", "cu_qp_delta outside valid range", and RTP
    # "bad cseq" sequence mismatches). Both settings existed purely to
    # minimize latency, but left FFmpeg with ZERO tolerance for the
    # normal jitter of a Wi-Fi link - a packet arriving even slightly
    # late got dropped outright rather than buffered, corrupting the
    # HEVC reference-frame chain and producing exactly these errors.
    # 300ms of buffering is a deliberate trade: a bit more latency for
    # a materially smoother, artifact-free picture - which matters more
    # for framing/focus checks than shaving off a few hundred ms.
    "rtsp_transport;tcp|max_delay;300000|stimeout;5000000|loglevel;quiet",
)
os.environ.setdefault("OPENCV_LOG_LEVEL", "OFF")

_BLACK_1PX = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXNSR0IArs4c6QAAAA1JREFUGFdjYGBg"
    "+A8AAQQBAHAgZQsAAAAASUVORK5CYII="
)
_PLACEHOLDER_JPEG = base64.b64decode(_BLACK_1PX)

_lock = threading.Lock()
_latest_frames: dict[str, bytes] = {}
_running: set[str] = set()


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
    its url within one read cycle and exits, releasing the
    VideoCapture - see this module's own docstring for why this
    matters on reconnect."""
    with _lock:
        _running.discard(rtsp_url)
        _latest_frames.pop(rtsp_url, None)


def stop_all() -> None:
    """Call on app shutdown."""
    with _lock:
        _running.clear()
        _latest_frames.clear()


def _worker_loop(rtsp_url: str) -> None:
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    try:
        while True:
            with _lock:
                if rtsp_url not in _running:
                    return
            if not cap.isOpened():
                time.sleep(0.5)
                cap.release()
                cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                continue

            success, frame = cap.read()
            if not success or frame is None:
                time.sleep(0.05)
                continue

            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if not ok:
                continue
            with _lock:
                _latest_frames[rtsp_url] = encoded.tobytes()
    finally:
        cap.release()
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