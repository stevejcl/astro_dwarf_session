"""Shared helpers for this app's own LAN reachability - used by
pages/logs.py's "LAN access" readout and pages/dashboard.py's watch-
mode QR code (both need the same local IP + published port, and a QR
code is just that same URL rendered differently)."""
from __future__ import annotations

import io
import socket

from nicegui import app


def get_local_ip() -> str:
    """Best-effort LAN-facing IP (user-requested Sep 2026: a quick "what
    do I type on my phone" readout, since the app's own host binding
    doesn't tell you which actual address that resolves to on the
    network). Opens a UDP socket toward a public address without ever
    sending a packet - purely so the OS picks the right outbound
    interface for routing - then reads that interface's own address
    back. Falls back to "127.0.0.1" if nothing is reachable at all (no
    network), which at least fails obviously rather than raising."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def get_lan_port() -> int:
    """LAN_PORT is published once at startup (astro_dwarf_ui.py) via
    app.storage.general - server-wide, so this works from any page
    without threading PORT through every build_*_page() call."""
    return app.storage.general.get("LAN_PORT", 8080)


def watch_url() -> str:
    return f"http://{get_local_ip()}:{get_lan_port()}/watch"


def watch_qr_svg() -> str:
    """Renders watch_url() as an inline SVG string (user-requested Sep
    2026: a QR code on the dashboard, to open Watch mode on a phone
    without typing the LAN URL by hand). Generated locally via the
    `qrcode` package's SVG image factory - no Pillow dependency, and no
    external QR-generation API/service, which matters here: the whole
    point of Watch mode is working on a local network at an observing
    site that may well have no internet access at all."""
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(watch_url(), image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()
