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
import logging
import os
import socket
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
#
# CAVEAT (Sep 2026, user-reported): this same noise can still show up
# around BLE pairing specifically - bleak's own WinRT backend
# (bleak.backends.winrt.util.allow_sta()'s own docs) genuinely wants a
# Windows event loop "properly integrated with asyncio" for its COM/
# WinRT calls, which in practice means Proactor-flavoured behaviour,
# in tension with the blanket Selector policy above. Rather than trying
# to thread a DIFFERENT policy through just the BLE pairing code path
# (fragile, and bleak may create its own loop machinery regardless of
# our process-wide policy), _suppress_benign_proactor_noise() below is
# a narrower, complementary safety net: it lets the exact known-benign
# "ConnectionResetError during _call_connection_lost cleanup" pattern
# through silently (logged at DEBUG, not printed as an unhandled
# exception), from WHICHEVER source it still slips through from,
# without touching anything else asyncio's default handler would
# normally report.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _suppress_benign_proactor_noise(loop: "asyncio.AbstractEventLoop", context: dict) -> None:
    exception = context.get("exception")
    # Checks BOTH context["message"] and the handle's own string repr -
    # asyncio's exact context dict shape for this callback-exception
    # path isn't pinned down by public docs, and the "_call_connection_
    # lost" marker reliably shows up in the handle's repr (matching the
    # user's own log: "handle: <Handle _ProactorBasePipeTransport.
    # _call_connection_lost(None)>") even if it's absent from message.
    marker_text = f"{context.get('message', '')} {context.get('handle', '')}"
    if isinstance(exception, ConnectionResetError) and "_call_connection_lost" in marker_text:
        # Known-harmless Windows/Proactor cleanup noise (WinError 10054
        # - the other side of a TCP connection was already reset by the
        # time cleanup runs) - never indicates the connection/pairing
        # itself failed, only that its OWN teardown logging is noisy.
        logging.getLogger("asyncio").debug("Suppressed benign Proactor cleanup noise: %r", exception)
        return
    loop.default_exception_handler(context)


from nicegui import native, app, ui

import platform

is_win32 = True if (
    platform.system() == "Windows"
    and platform.architecture()[0] == "32bit"
) else None

if is_win32:
    print("start win32")

    app.native.start_args["gui"] = "edgechromium"

    app.native.settings["WEBVIEW2_RUNTIME_PATH"] = (
        r"C:\Program Files\Microsoft\EdgeWebView\Application>"
    )

import dwarf_python_api.lib.my_logger as my_logger
from dwarf_python_api.lib.dwarf_session import get_manager

from device_registry import bootstrap_devices
from components.pwa import register_manifest_route
from components import rtsp_worker
from components import scheduler_runner
from components.api_routes import register_api_routes
from components.scheduler_loop import start_background_loop
from pages.dashboard import build_dashboard_page
from pages.explorer import build_explorer_page
from pages.session import build_session_page
from pages.programs import build_programs_page
from pages.settings import build_settings_page
from pages.pairing import build_pairing_page
from pages.logs import build_logs_page
from pages.manual_config import build_manual_config_page
from pages.sites import build_sites_page
from pages.watch_dashboard import build_watch_dashboard_page
from pages.watch_device import build_watch_device_page


def _find_open_port(host: str, start_port: int = 8000, end_port: int = 8999) -> int:
    """Own replacement for nicegui.native.find_open_port() (user-
    reported Sep 2026: the default launch picked a port that was
    already in use by something else). That function only test-binds
    on 'localhost' (127.0.0.1) regardless of what host the app will
    actually listen on - with --host defaulting to 0.0.0.0 (see
    parse_args() below), a port already held by another process
    specifically on 0.0.0.0 or on a particular LAN adapter's address
    can slip through as "free" when only tested against localhost.
    This probes the SAME host the server will actually bind to."""
    for port in range(start_port, end_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return port
        except OSError:
            continue
    raise OSError("No open port found")


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
        "--no_native",
        action="store_true",
        help="Don't open a native desktop window (server-only mode, "
        "useful headless / on a box with no screen).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # dwarf_python_api's own my_logger.py auto-configures itself at
    # IMPORT time (setup_logger() runs unconditionally at module load,
    # before this function ever gets a chance to run) - using a neutral
    # "app.log" default, since it's a GENERIC library shared by several
    # standalone tools (main_v3.py, get_live_data_dwarf.py, ...), not
    # just this app (user-corrected Sep 2026: an earlier attempt at this
    # fix hardcoded "astro_session.log" directly inside the library
    # itself, which wrongly baked in astro_dwarf_ui's own naming
    # preference at the generic-library level). THIS is where that
    # application-level choice actually belongs - re-triggers the same
    # update_log_file() the library already ran automatically, just
    # with OUR preferred name instead of its own neutral default.
    #
    # Guarded to __name__ == "__main__" specifically (user-reported Sep
    # 2026: real log showed this whole sequence twice) - native mode's
    # pywebview window runs in a genuinely SEPARATE child process
    # (spawned, not forked - see freeze_support()'s own comment below),
    # which re-imports and re-runs this ENTIRE script from scratch,
    # with __name__ == "__mp_main__" instead. Without this guard, that
    # child process's own call renamed the real astro_session.log (the
    # one THIS/parent process had just created moments before) to
    # astro_session.log.old, destroying the true PREVIOUS session's
    # backup that file was meant to hold - not just cosmetic log
    # duplication, an actual loss of the intended history.
    if __name__ == "__main__":
        my_logger.update_log_file(default_name="astro_session.log")

    PORT = args.port if args.port else _find_open_port(args.host)

    # Read back by pages/settings.py's LAN-access label (user-requested
    # Sep 2026) - app.storage.general is server-wide (see components/
    # i18n.py's own use of it), so any page can read this without
    # threading PORT through every build_*_page() call. Set via
    # on_startup rather than a bare assignment here, same reasoning as
    # the win32 exception-handler install a few lines below: NiceGUI's
    # storage backend is only guaranteed ready once ui.run()'s own
    # server has actually started.
    def _publish_lan_port() -> None:
        app.storage.general["LAN_PORT"] = PORT

    app.on_startup(_publish_lan_port)

    # Device-type icons (dashboard's model badge, see device_card.py) -
    # served from /images/<name>.png. Resolved relative to THIS file
    # (not the current working directory), so it works regardless of
    # where the app is launched from.
    from pathlib import Path

    # Detect PyInstaller running
    if getattr(sys, 'frozen', False):
        BASE_DIR = Path(sys._MEIPASS)
    else:
        BASE_DIR = Path(__file__).parent

    # Chemin complet vers le dossier images
    images_dir = BASE_DIR / "images"
    
    # Creadte directory to avoid RuntimeError
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # Declare ats Static Dir for NiceGUI 
    app.add_static_files('/images', str(images_dir))

    # PWA support (user-requested Sep 2026: "plein ecran sur Mobile,
    # enlever la barre d'adresse") - see components/pwa.py's own
    # docstring for what this does/doesn't cover.
    register_manifest_route()

    # Embedded live RTSP preview (user-requested Sep 2026) - registers
    # the /video/rtsp_stream/ and /video/rtsp_snapshot/ routes
    # components/camera_stream.py's own <img> tags point at. stop_all()
    # on shutdown releases every camera's OpenCV/FFmpeg worker thread
    # cleanly rather than leaving them running past the app's own exit.
    rtsp_worker.register_routes()
    app.on_shutdown(rtsp_worker.stop_all)

    if sys.platform == "win32":
        # Installed via on_startup, not right after set_event_loop_policy
        # above - a handler can only be attached to an ACTUAL running
        # loop instance, which doesn't exist yet until ui.run()'s own
        # uvicorn server is up. See _suppress_benign_proactor_noise()'s
        # own docstring/comment for why this exists alongside (not
        # instead of) the process-wide policy set earlier.
        def _install_proactor_noise_filter() -> None:
            asyncio.get_running_loop().set_exception_handler(_suppress_benign_proactor_noise)

        app.on_startup(_install_proactor_noise_filter)

    # A single DwarfManager for the whole process. Populated at startup
    # from the known config.py/config.ini pairs (see device_registry.py)
    # - NOT recreated per NiceGUI client.
    bootstrap_devices(get_manager())

    # REST API for external tools (e.g. the DSO catalog page's "Program
    # session to the Dwarf" button) - GET /api/dwarfs, POST /api/schedule.
    # See components/api_routes.py's module docstring.
    register_api_routes()

    build_dashboard_page()
    build_explorer_page()
    build_session_page()
    build_programs_page()
    build_settings_page()
    build_pairing_page()
    build_sites_page()
    build_manual_config_page()
    build_logs_page()
    # Read-only spectator mode (user-requested Sep 2026) - separate
    # dashboard/device pages, no capture/connect/settings controls
    # anywhere in their code - see their own module docstrings.
    build_watch_dashboard_page()
    build_watch_device_page()

    # Global, client-independent (see components/scheduler_loop.py's
    # module docstring for why app.timer, not ui.timer) - a scheduled
    # program must fire at its due time regardless of whether anyone
    # currently has a browser tab open.
    start_background_loop(get_manager())

    # Same reasoning, own app.timer - a stuck/leaked run must eventually
    # get cleaned up (see check_stuck_runs()'s own docstring) whether or
    # not anyone has a browser tab open to notice it. Every 5 minutes is
    # plenty frequent against a 6-hour ceiling.
    app.timer(30.0, scheduler_runner.check_stuck_runs)

    if not args.no_native:
        ui.run(
            title="Astro Dwarf Session",
            storage_secret="astro_dwarf_session_key_change_me",  # TODO: move to a .env
            native=not args.no_native,
            window_size=(1024, 815),
            host=args.host,
            port=PORT,
            reconnect_timeout=20,
            reload=False,
        )
    else:
        ui.run(
            title="Astro Dwarf Session",
            storage_secret="astro_dwarf_session_key_change_me",  # TODO: move to a .env
            native=not args.no_native,
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
    try:

        main()

    except (KeyboardInterrupt):
        print("Application closed by user.")
        
    except SystemExit:
        print("Application closed.")

    except Exception as e:
        print(f"Application closed error detected {e}.")
