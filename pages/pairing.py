"""BLE pairing screen.

Reuses connect_ble_direct_dwarf() (dwarf_ble_connect/lib/
connect_direct_bluetooth.py) rather than re-implementing the scan/WiFi
handoff by hand - this is the hardware-validated version (scan,
retries, config.py write via update_config_data()), just without the
Tkinter window from connect_ble_dwarf_win() (incompatible with a
headless/NiceGUI server).

TWO IMPORTANT FINDINGS from building this screen, worth confirming on
the astro_dwarf_session side:

1. update_config_data() requires the TARGET config.py to already exist
   (it does a line-by-line search/replace, it never creates anything) -
   so for a genuinely new device, a config.py/config.ini must first be
   materialized from a template (see _TEMPLATE_PY/_INI below, copied
   from Install/config.py and Install/config.ini).

2. The current Install/config.py has NO "DWARF_UID = ..." line -
   without that line, update_config_data('dwarf_uid', ...) finds
   nothing to replace and writes NOTHING, silently (it still returns
   True, "Value not found, file not changed"). The template below adds
   the missing line - but Install/config.py itself probably deserves
   the same fix so setupBLE.py etc. aren't hit by the same gap.

CONCURRENCY: set_config_data() redirects a GLOBAL state at the
get_config_data module level (not per-session) - two simultaneous
pairing operations would write into each other's target file.
_pairing_lock therefore serializes pairing: only one at a time, even
with several NiceGUI tabs/clients open."""
from __future__ import annotations

import re
import threading
from pathlib import Path

from nicegui import run, ui

import dwarf_python_api.get_config_data as get_config_data
from dwarf_python_api.lib.dwarf_config import DwarfConfig
from dwarf_python_api.lib.dwarf_session import get_manager

from components.ble_pairing import connect_ble, scan_dwarf_devices, write_ble_credentials
from components.i18n import t
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme
from device_registry import add_device_entry

# IMPORTANT (found while wiring this screen, needs an upstream fix):
# dwarf_ble_connect/lib/connect_direct_bluetooth.py unconditionally
# imports `from bleak.backends.winrt.util import allow_sta` (+ tkinter)
# at the top of the file, even though allow_sta is only used inside
# connect_ble_dwarf_win() (the Windows Tkinter flow). Result: importing
# this module at all crashes on Linux/macOS (bleak has no WinRT backend
# there), even for connect_ble_direct_dwarf() which doesn't need it.
# Deferred import + graceful degradation here in the meantime (proper
# fix upstream: move those imports inside connect_ble_dwarf_win(), or
# guard them behind `if sys.platform == "win32"`).

_TEMPLATE_PY = """DWARF_IP = ""
DWARF_ID = "2"
DWARF_UID = ""
DWARF_UI = ""
CLIENT_ID = "0000DAF2-0000-1000-8000-00805F9B34FB"
TIMEOUT_CMD = "0"
LOG_FILE = "astro_session.log"
DEBUG = True
TRACE = ""
"""

_TEMPLATE_INI = """[CONFIG]
longitude =
latitude =
timezone = Europe/Paris
ble_psd = DWARF_12345678
ble_sta_ssid =
ble_sta_pwd =
exposure = 15
gain = 100
ircut = 0
binning = 0
count = 20
address =
dwarf_ip =
stellarium_ip =
stellarium_port =
camera_type = Tele Camera
device_type = Dwarf II
"""

_pairing_lock = threading.Lock()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip().lower()).strip("_")
    return slug or "device"


def _ensure_config_files(slug: str) -> tuple[str, str]:
    """Creates config_<slug>.py / .ini from the template if they don't
    exist yet. Never touches a file that already exists (this could be
    a RE-pairing of an already-known device)."""
    config_py = f"config_{slug}.py"
    config_ini = f"config_{slug}.ini"

    if not Path(config_py).exists():
        Path(config_py).write_text(_TEMPLATE_PY, encoding="utf-8")
    if not Path(config_ini).exists():
        Path(config_ini).write_text(_TEMPLATE_INI, encoding="utf-8")

    return config_py, config_ini


def _do_pairing(
    device_name: str, ble_psd: str, wifi_ssid: str, wifi_pwd: str, auto_select: str = ""
) -> tuple[bool, str]:
    """All the blocking work (files + BLE scan + WiFi handoff), run
    outside the NiceGUI event loop via run.io_bound(). Returns
    (success, message).

    auto_select: pass a specific device's Bluetooth name (from
    scan_dwarf_devices()'s "multiple" result, after the user picked
    one in the UI) to connect to THAT device specifically - see
    components/ble_pairing.py's connect_ble() docstring."""
    try:
        from dwarf_ble_connect.lib import connect_direct_bluetooth  # noqa: F401 - import check only
    except Exception as e:
        # Deliberately broad: on Linux/macOS the import breaks with an
        # AttributeError (not an ImportError) partway through bleak's
        # winrt backend import chain - see the module docstring. Better
        # to degrade gracefully here than let any import exception
        # bubble up to the "Pair" button.
        return False, t(
            "pairing_ble_unavailable", error_type=type(e).__name__, error=str(e)
        )

    slug = _slugify(device_name)
    config_py, config_ini = _ensure_config_files(slug)

    # Redirects update_config_data()'s writes to THIS file pair - same
    # mechanism as connect_bluetooth_cmd.py --config-py.
    get_config_data.set_config_data(
        config_file=config_py,
        config_file_tmp=config_py + ".tmp",
        lock_file=config_py + ".lock",
    )

    connected = connect_ble(ble_psd, wifi_ssid, wifi_pwd, auto_select)
    if not connected:
        return False, t("pairing_connection_failed")

    cfg = DwarfConfig.from_files(config_py, config_ini)
    if not cfg.dwarf_uid:
        return False, t("pairing_uid_not_written", config_py=config_py)

    # Persisted for later reuse by settings.py's "Force Bluetooth"
    # (user-requested Sep 2026) - config.ini already had ble_psd/
    # ble_sta_ssid/ble_sta_pwd fields, just never actually written here.
    write_ble_credentials(config_ini, ble_psd, wifi_ssid, wifi_pwd)

    get_manager().add(cfg)
    add_device_entry(name=device_name, config_py=config_py, config_ini=config_ini)
    return True, t(
        "pairing_success", device_name=device_name, dwarf_uid=cfg.dwarf_uid, dwarf_ip=cfg.dwarf_ip
    )


async def _handle_pair(
    device_name: str,
    ble_psd: str,
    wifi_ssid: str,
    wifi_pwd: str,
    status_label: ui.label,
    pair_button: ui.button,
    choice_container: ui.column,
) -> None:
    if not device_name.strip():
        ui.notify(t("pairing_name_required"), type="negative")
        return
    if not wifi_ssid.strip() or not wifi_pwd.strip():
        ui.notify(t("pairing_wifi_required"), type="negative")
        return

    if not _pairing_lock.acquire(blocking=False):
        ui.notify(t("pairing_already_in_progress"), type="warning")
        return

    pair_button.disable()
    choice_container.clear()
    status_label.set_text(t("pairing_searching"))
    try:
        outcome, names = await run.io_bound(scan_dwarf_devices)
    except Exception as e:
        _pairing_lock.release()
        pair_button.enable()
        status_label.set_text(t("pairing_ble_unavailable", error_type=type(e).__name__, error=str(e)))
        return

    if outcome == "none":
        _pairing_lock.release()
        pair_button.enable()
        status_label.set_text(t("pairing_connection_failed"))
        return

    if outcome == "single":
        await _finish_pairing(
            device_name, ble_psd, wifi_ssid, wifi_pwd, "", status_label, pair_button
        )
        return

    # outcome == "multiple": show a real choice instead of connect_ble_
    # dwarf()'s own blind "10s then pick #1" fallback (see module
    # docstring) - the lock/button stay held/disabled until the user
    # actually picks one and the second (name-matching) scan completes.
    status_label.set_text(t("pairing_multiple_found", count=len(names)))
    with choice_container:
        choice = ui.radio(names, value=names[0]).classes("w-full")
        ui.label(t("pairing_rescan_note")).classes("text-xs text-grey-5")

        async def _connect_chosen() -> None:
            choice_container.clear()
            await _finish_pairing(
                device_name, ble_psd, wifi_ssid, wifi_pwd, choice.value, status_label, pair_button
            )

        ui.button(t("pairing_connect_to_selected"), on_click=_connect_chosen).props(
            "color=primary"
        )
    pair_button.enable()  # re-enable "Pair" itself in case the user wants to restart the scan instead
    _pairing_lock.release()


async def _finish_pairing(
    device_name: str,
    ble_psd: str,
    wifi_ssid: str,
    wifi_pwd: str,
    auto_select: str,
    status_label: ui.label,
    pair_button: ui.button,
) -> None:
    """Runs the actual connect+WiFi-handoff+config-write flow (via
    _do_pairing()) - shared by the "single device found" path (called
    directly, auto_select="") and the "user picked one from multiple"
    path (auto_select=<chosen name>, re-scans and matches by name)."""
    if not _pairing_lock.acquire(blocking=False):
        ui.notify(t("pairing_already_in_progress"), type="warning")
        return

    pair_button.disable()
    status_label.set_text(
        t("pairing_connecting_to", name=auto_select) if auto_select else t("pairing_searching")
    )
    try:
        success, message = await run.io_bound(
            _do_pairing, device_name, ble_psd or "DWARF_12345678", wifi_ssid, wifi_pwd, auto_select
        )
    finally:
        _pairing_lock.release()
        pair_button.enable()

    status_label.set_text(message)
    if success:
        ui.notify(message, type="positive")
        ui.navigate.to("/")
    else:
        ui.notify(message, type="negative")


def build_pairing_page() -> None:
    @ui.page("/pairing", title="Astro Dwarf Session - Pairing")
    def pairing_page() -> None:
        add_pwa_head_tags()
        apply_theme()
        with ui.column().classes("w-full max-w-md mx-auto gap-3 p-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props(
                "flat round"
            )
            ui.label(t("add_dwarf")).classes("text-xl")
            ui.label(t("pairing_instructions")).classes("text-sm text-grey-6")

            device_name = ui.input(
                t("device_name"), placeholder=t("device_name_placeholder")
            ).classes("w-full")
            ble_psd = ui.input(
                t("bluetooth_password"), value="DWARF_12345678"
            ).classes("w-full")
            wifi_ssid = ui.input(t("wifi_ssid")).classes("w-full")
            wifi_pwd = ui.input(t("wifi_password"), password=True).classes("w-full")

            status_label = ui.label("").classes("text-sm text-grey-6")
            choice_container = ui.column().classes("w-full gap-1")

            pair_button = ui.button(t("pair"), icon="bluetooth_searching")
            pair_button.on(
                "click",
                lambda: _handle_pair(
                    device_name.value,
                    ble_psd.value,
                    wifi_ssid.value,
                    wifi_pwd.value,
                    status_label,
                    pair_button,
                    choice_container,
                ),
            )

            ui.label(t("pairing_known_limitation")).classes("text-xs text-grey-5 mt-2")
