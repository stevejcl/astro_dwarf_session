"""
Astro Dwarf UI - entry point.

Reuses dwarfium-scope-archive's ui.run() pattern exactly (native=True +
explicit host/port => the desktop window AND network clients (phone on
the same LAN) talk to the same NiceGUI server), but controls hardware
LIVE (WebSocket/BLE via dwarf_python_api) rather than an archive of
finished sessions.

Key difference from dwarfium-scope-archive: state (WS connections,
DwarfManager, notification cache) is GLOBAL to the process, not per
NiceGUI client. There is exactly one set of DwarfSession, no matter how
many windows/browsers are open on it (native window + phone on the same
network must see the same hardware state in real time).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from multiprocessing import freeze_support

# Windows only: forces the WHOLE PROCESS (not just dwarf_python_api's
# own device-connection loops, which already use SelectorEventLoop -
# see websockets_utils.py/dwarf_session_socket.py's own init_socket())
# to use SelectorEventLoop instead of the platform default
# ProactorEventLoop - user-reported Sep 2026: the SAME
# "_ProactorBasePipeTransport._call_connection_lost" / WinError 10054
# noise was STILL happening even after that earlier fix, but this time
# from a DIFFERENT source - ui.run() runs its own uvicorn ASGI server
# (handling the browser/phone's own HTTP/WebSocket connections to the
# NiceGUI UI itself, entirely separate from the Dwarf-device
# connections dwarf_python_api manages), and uvicorn creates ITS OWN
# event loop via plain asyncio.new_event_loop() - which still defaults
# to ProactorEventLoop on Windows unless the process-wide policy itself
# is changed, which is what this does. Must run before ui.run() (or
# anything else) creates any event loop - set at import time, as early
# as possible in this file, rather than inside main().
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from nicegui import native, app, ui

from dwarf_python_api.lib.dwarf_session import get_manager

from device_registry import bootstrap_devices
from components.pwa import register_manifest_route
from components.scheduler_loop import start_background_loop
from pages.dashboard import build_dashboard_page
from pages.explorer import build_explorer_page
from pages.session import build_session_page
from pages.programs import build_programs_page
from pages.settings import build_settings_page
from pages.pairing import build_pairing_page
from pages.logs import build_logs_page


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Astro Dwarf UI")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="IP address the NiceGUI server listens on. 0.0.0.0 = reachable "
        "from the whole LAN (phone, tablet...), not just locally.",
    )
    parser.add_argument("--port", type=int)
    parser.add_argument(
        "--no-native",
        action="store_true",
        help="Don't open a native desktop window (server-only mode, "
        "useful headless / on a box with no screen).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    PORT = args.port if args.port else native.find_open_port()

    # Device-type icons (dashboard's model badge, see device_card.py) -
    # served from /images/<name>.png. Resolved relative to THIS file
    # (not the current working directory), so it works regardless of
    # where the app is launched from.
    images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
    app.add_static_files("/images", images_dir)

    # PWA support (user-requested Sep 2026: "plein ecran sur Mobile,
    # enlever la barre d'adresse") - see components/pwa.py's own
    # docstring for what this does/doesn't cover.
    register_manifest_route()

    # A single DwarfManager for the whole process. Populated at startup
    # from the known config.py/config.ini pairs (see device_registry.py)
    # - NOT recreated per NiceGUI client.
    bootstrap_devices(get_manager())

    build_dashboard_page()
    build_explorer_page()
    build_session_page()
    build_programs_page()
    build_settings_page()
    build_pairing_page()
    build_logs_page()

    # Global, client-independent (see components/scheduler_loop.py's
    # module docstring for why app.timer, not ui.timer) - a scheduled
    # program must fire at its due time regardless of whether anyone
    # currently has a browser tab open.
    start_background_loop(get_manager())

    ui.run(
        title="Astro Dwarf Session",
        storage_secret="astro_dwarf_session_key_change_me",  # TODO: move to a .env
        native=not args.no_native,
        window_size=(1024, 800),
        host=args.host,
        port=PORT,
        reconnect_timeout=20,
        reload=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    # Required for a FROZEN app (PyInstaller/py2app) that uses
    # multiprocessing (user-requested Sep 2026, for macOS) - since
    # Python 3.8, macOS's default multiprocessing start method is
    # "spawn" (matching Windows), not the older "fork", which means a
    # frozen executable re-launching itself to spawn a child process
    # needs this guard to avoid re-running the whole app recursively in
    # that child. NiceGUI's native mode (pywebview) can spawn its own
    # subprocess depending on platform/backend, so this matters even
    # though this app doesn't use multiprocessing directly itself. A
    # no-op when NOT frozen (plain `python astro_dwarf_ui.py`), safe to
    # always call.
    freeze_support()
    main()
