"""Shared BLE scan/connect helpers - used by both pages/pairing.py
(pairing a brand NEW device) and settings.py's "Force Bluetooth"
section (re-doing the BLE handshake for an ALREADY-paired device, e.g.
after its Wi-Fi IP changed and normal WebSocket reconnect stopped
working, but it's still Bluetooth-discoverable).

Extracted here rather than duplicated, since both screens need the
exact same scan-then-choose-if-multiple state machine (see
scan_dwarf_devices()'s own docstring for why connect_ble_dwarf()'s
built-in auto_select="0" path can't be reused directly for this - its
device list never actually reaches calling code, only a log line)."""
from __future__ import annotations

import asyncio
import configparser


def scan_dwarf_devices() -> tuple[str, list[str]]:
    """Pre-scan (discover_dwarf_devices() + select_dwarf_device()) to
    see how many DWARF devices are currently discoverable, WITHOUT
    connecting to any of them - so the UI can present a real choice
    when there's more than one.

    NOT the same as connect_ble_dwarf()'s own auto_select="0" path:
    that one internally reaches this exact "multiple found" state too,
    but only ever LOGS the device list (log.notice) - its actual return
    value is just a plain bool either way (status_bluetooth), so the
    list was never actually reachable from calling code. This function
    exists specifically to get that list back, by calling the same
    underlying primitives (dwarf_lib_ble.py) directly rather than going
    through connect_ble_dwarf()'s all-in-one orchestration.

    Returns ("none", []), ("single", [name]), or ("multiple", [names]).
    The "single" case still needs a full connect_ble()/
    connect_ble_direct_dwarf() call afterward (this function only
    scans, never connects) - it's returned mainly so the caller can
    skip showing a pointless one-item choice screen."""
    from dwarf_ble_connect.lib.dwarf_lib_ble import discover_dwarf_devices, select_dwarf_device

    async def _scan():
        state = await discover_dwarf_devices()
        dwarf_devices = state.get("dwarf_devices")
        if not dwarf_devices:
            return "none", []
        select_state = await select_dwarf_device(dwarf_devices)
        if select_state.get("step") == "2":
            return "single", [select_state["dwarf_device"].name]
        return "multiple", [d.name for d in dwarf_devices]

    return asyncio.run(_scan())


def connect_ble(ble_psd: str, wifi_ssid: str, wifi_pwd: str, auto_select: str = "") -> bool:
    """Thin re-export of connect_ble_direct_dwarf() - the CALLER must
    already have pointed get_config_data.set_config_data() at the
    target config_py/config_ini pair before calling this (matches the
    existing convention throughout this app). Only reports whether the
    BLE connect + WiFi handoff succeeded - does not touch DwarfManager
    or re-read the resulting config; callers handle that differently
    for a brand-new device (create + register) vs refreshing an
    existing one (update in place, see settings.py).

    auto_select: pass a specific device's Bluetooth name (from
    scan_dwarf_devices()'s "multiple" result, after the user picked one
    in the UI) - connect_ble_direct_dwarf() re-scans internally and
    matches by name, it doesn't take an already-discovered device
    object directly. Leave "" for the "none"/"single" cases."""
    from dwarf_ble_connect.lib.connect_direct_bluetooth import connect_ble_direct_dwarf

    return connect_ble_direct_dwarf(ble_psd, wifi_ssid, wifi_pwd, auto_select)


def write_ble_credentials(config_ini_path: str, ble_psd: str, wifi_ssid: str, wifi_pwd: str) -> None:
    """Persists the BLE password + Wi-Fi SSID/PWD used for a successful
    pairing/reconnect into config.ini's own ble_psd/ble_sta_ssid/
    ble_sta_pwd fields (already present in the pairing template, just
    never actually written to before) - so a later "Force Bluetooth"
    can pre-fill them instead of asking the user to retype the Wi-Fi
    password from scratch every time."""
    ini = configparser.ConfigParser()
    ini.read(config_ini_path)
    if not ini.has_section("CONFIG"):
        ini.add_section("CONFIG")
    ini["CONFIG"]["ble_psd"] = ble_psd
    ini["CONFIG"]["ble_sta_ssid"] = wifi_ssid
    ini["CONFIG"]["ble_sta_pwd"] = wifi_pwd
    with open(config_ini_path, "w", encoding="utf-8") as f:
        ini.write(f)
