"""Per-device settings page. Currently covers longitude/latitude/timezone
- the fields EQ Solving needs (see dwarf_python_api's start_polar_align(),
which now fails cleanly instead of crashing when these are missing, but
still can't actually run EQ Solving without them). Nothing in the
pairing flow (pages/pairing.py) ever asks for these, and they're a
property of where you're observing FROM, not of the device itself - you
might reasonably want to change them between sessions without
re-pairing over BLE - so this lives as its own lightweight page rather
than being folded into pairing.

DwarfConfig is a plain (non-frozen) dataclass (dwarf_config.py) - saving
here mutates session.config directly, so the change is live immediately
for the current session, in addition to being persisted to config.ini
for next time.

LOCATION AUTO-FILL: uses the BROWSER's own Geolocation API
(navigator.geolocation) rather than requiring an address lookup - no
typing needed, just a one-time permission prompt, and it's already
running on the same machine/network as the telescope in the normal
case. Deliberately NOT IP-based geolocation (too coarse - city-level at
best) and NOT an address-to-coordinates lookup (would need typing an
address AND a third-party geocoding service for no real benefit over
just asking the browser directly).

CAVEAT: in native mode (ui.run(native=True), pywebview), geolocation
support depends on the underlying embedded engine (WebView2 on Windows,
WebKit elsewhere) and may not prompt/work as reliably as in a real
browser tab - if "Use current location" fails there, the same NiceGUI
server is also reachable over LAN in a normal browser (already
confirmed working simultaneously with native mode elsewhere in this
app), or coordinates can simply be typed in by hand."""
from __future__ import annotations

import configparser
import json

from nicegui import run, ui

from dwarf_python_api.get_config_data import set_config_data
from dwarf_python_api.lib.dwarf_config import DwarfConfig
from dwarf_python_api.lib.dwarf_session import get_manager
from dwarf_python_api.lib.dwarf_utils import perform_disconnect

from components import connection_health
from components.ble_pairing import connect_ble, scan_dwarf_devices, write_ble_credentials
from components.i18n import t
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme

_GEOLOCATION_JS = """
return new Promise((resolve) => {
    if (!navigator.geolocation) {
        resolve(JSON.stringify({error: 'unsupported'}));
        return;
    }
    navigator.geolocation.getCurrentPosition(
        (pos) => resolve(JSON.stringify({lat: pos.coords.latitude, lon: pos.coords.longitude})),
        (err) => resolve(JSON.stringify({error: err.message})),
        {timeout: 15000, enableHighAccuracy: true}
    );
});
"""


def _read_ini(path: str) -> configparser.ConfigParser:
    ini = configparser.ConfigParser()
    ini.read(path)
    if not ini.has_section("CONFIG"):
        ini.add_section("CONFIG")
    return ini


def _do_force_bluetooth(
    session, ble_psd: str, wifi_ssid: str, wifi_pwd: str, auto_select: str = ""
) -> tuple[bool, str]:
    """Re-does the BLE scan+connect+WiFi-handoff for this ALREADY-paired
    device, reusing its EXISTING config_py/config_ini (never creates new
    ones, unlike pairing a brand-new device in pages/pairing.py) - a
    recovery option (user-requested Sep 2026) for when the device's
    Wi-Fi IP changed (e.g. a DHCP lease renewal) and the normal
    WebSocket Connect/Reconnect stopped working, but it's still
    Bluetooth-discoverable.

    Disconnects FIRST if currently connected, before touching
    session.config underneath a live connection - leaving a
    client_instance/event_loop_thread running while its own session's
    dwarf_ip is about to change would risk exactly the kind of orphaned-
    thread situation connection_health.py's own cleanup exists to catch
    elsewhere; better to never create it here at all.

    Updates session.config IN PLACE afterward rather than calling
    DwarfManager.add() again - that method does a plain dict assignment
    (self._sessions[uid] = session), which would silently replace this
    session object with a brand new one, orphaning whatever thread the
    OLD object might still reference."""
    if session.is_connected:
        perform_disconnect(session=session)

    config_py = session.config.config_py_path
    config_ini = session.config.config_ini_path

    set_config_data(
        config_file=config_py,
        config_file_tmp=config_py + ".tmp",
        lock_file=config_py + ".lock",
    )

    connected = connect_ble(ble_psd, wifi_ssid, wifi_pwd, auto_select)
    if not connected:
        return False, t("settings_force_ble_failed")

    fresh = DwarfConfig.from_files(config_py, config_ini)
    if not fresh.dwarf_uid:
        return False, t("settings_force_ble_no_uid")
    if fresh.dwarf_uid != session.dwarf_uid:
        # Shouldn't normally happen for the SAME physical device, but if
        # BLE somehow matched a DIFFERENT Dwarf, don't silently merge
        # its identity into this session.
        return False, t(
            "settings_force_ble_uid_mismatch", expected=session.dwarf_uid, got=fresh.dwarf_uid
        )

    session.config.dwarf_ip = fresh.dwarf_ip
    session.config.dwarf_model_id = fresh.dwarf_model_id
    write_ble_credentials(config_ini, ble_psd, wifi_ssid, wifi_pwd)

    return True, t("settings_force_ble_success", ip=fresh.dwarf_ip)


def build_settings_page() -> None:
    @ui.page("/session/{dwarf_uid}/settings")
    def settings_page(dwarf_uid: str) -> None:
        add_pwa_head_tags()
        apply_theme()
        ui.page_title(f"Settings - {dwarf_uid}")
        try:
            session = get_manager().get(dwarf_uid)
        except KeyError:
            ui.label(t("unknown_dwarf", dwarf_uid=dwarf_uid)).classes("text-red-800 p-4")
            return

        with ui.column().classes("w-full max-w-md mx-auto gap-3 p-4"):
            ui.button(
                icon="arrow_back",
                on_click=lambda: ui.navigate.to(f"/session/{dwarf_uid}"),
            ).props("flat round")
            # See pages/programs.py for why this is shown explicitly: no
            # address bar in native mode means the URL's dwarf_uid -
            # which device these settings actually apply to - would
            # otherwise be invisible.
            ui.label(t("settings_title")).classes("text-xl")
            ui.label(session.dwarf_uid).classes("text-sm text-grey-6 -mt-2")
            ui.label(t("settings_location_hint")).classes("text-sm text-grey-6")

            geolocation_status = ui.label("").classes("text-xs")

            longitude_input = ui.number(
                t("settings_longitude"),
                value=session.config.longitude,
                format="%.6f",
            ).classes("w-full")
            latitude_input = ui.number(
                t("settings_latitude"),
                value=session.config.latitude,
                format="%.6f",
            ).classes("w-full")

            async def handle_use_current_location() -> None:
                geolocation_status.set_text(t("settings_location_fetching"))
                geolocation_status.classes(replace="text-xs text-grey-6")
                try:
                    raw = await ui.run_javascript(_GEOLOCATION_JS, timeout=20.0)
                    result = json.loads(raw)
                except Exception as exc:
                    geolocation_status.set_text(t("settings_location_error", error=str(exc)))
                    geolocation_status.classes(replace="text-xs text-red-700")
                    return

                if "error" in result:
                    geolocation_status.set_text(t("settings_location_error", error=result["error"]))
                    geolocation_status.classes(replace="text-xs text-red-700")
                    return

                longitude_input.value = result["lon"]
                latitude_input.value = result["lat"]
                geolocation_status.set_text(t("settings_location_fetched"))
                geolocation_status.classes(replace="text-xs text-green-700")

            ui.button(
                t("settings_use_current_location"),
                icon="my_location",
                on_click=handle_use_current_location,
            ).props("flat")

            timezone_input = ui.input(
                t("settings_timezone"), value=session.config.timezone
            ).classes("w-full")

            ui.label(t("settings_stellarium_hint")).classes("text-sm text-grey-6 mt-2")
            with ui.row().classes("w-full gap-2"):
                stellarium_ip_input = ui.input(
                    t("settings_stellarium_ip"),
                    value=session.config.stellarium_ip or "127.0.0.1",
                ).classes("flex-1")
                stellarium_port_input = ui.number(
                    t("settings_stellarium_port"),
                    value=session.config.stellarium_port or 8090,
                    format="%.0f",
                ).classes("w-32")

            status_label = ui.label("").classes("text-sm")

            def handle_save() -> None:
                if longitude_input.value is None or latitude_input.value is None:
                    status_label.set_text(t("settings_missing_coords"))
                    status_label.classes(replace="text-sm text-red-700")
                    return

                lon = float(longitude_input.value)
                lat = float(latitude_input.value)
                tz = timezone_input.value.strip()
                stellarium_ip = stellarium_ip_input.value.strip() or "127.0.0.1"
                stellarium_port = int(stellarium_port_input.value or 8090)

                ini = _read_ini(session.config.config_ini_path)
                ini["CONFIG"]["longitude"] = str(lon)
                ini["CONFIG"]["latitude"] = str(lat)
                ini["CONFIG"]["timezone"] = tz
                ini["CONFIG"]["stellarium_ip"] = stellarium_ip
                ini["CONFIG"]["stellarium_port"] = str(stellarium_port)
                with open(session.config.config_ini_path, "w", encoding="utf-8") as f:
                    ini.write(f)

                # Live for the current session immediately - DwarfConfig
                # is a plain mutable dataclass, no reconnect needed for
                # this to take effect (read_longitude()/read_latitude()
                # read session.config.* directly).
                session.config.longitude = lon
                session.config.latitude = lat
                session.config.timezone = tz
                session.config.stellarium_ip = stellarium_ip
                session.config.stellarium_port = stellarium_port

                status_label.set_text(t("settings_saved"))
                status_label.classes(replace="text-sm text-green-700")

            ui.button(t("settings_save"), icon="save", on_click=handle_save).props(
                "color=primary"
            )

            # --- Force Bluetooth (user-requested Sep 2026) --------------
            # Recovery option for an already-paired device: re-does the
            # BLE handshake to refresh dwarf_ip (e.g. after a DHCP lease
            # renewal) when normal WebSocket Connect/Reconnect stopped
            # working. Pre-fills from whatever was persisted at the last
            # successful pairing/force-reconnect (see components/
            # ble_pairing.py's write_ble_credentials()) - blank the
            # first time this device was paired before that existed.
            with ui.expansion(t("settings_force_ble_title"), icon="bluetooth_searching", value=False).classes("w-full mt-2"):
                ui.label(t("settings_force_ble_hint")).classes("text-xs text-grey-6")

                ble_psd_input = ui.input(
                    t("bluetooth_password"), value=session.config.ble_psd or "DWARF_12345678"
                ).classes("w-full")
                ble_ssid_input = ui.input(
                    t("wifi_ssid"), value=session.config.ble_sta_ssid
                ).classes("w-full")
                ble_pwd_input = ui.input(
                    t("wifi_password"), password=True, value=session.config.ble_sta_pwd
                ).classes("w-full")

                ble_status_label = ui.label("").classes("text-xs")
                ble_choice_container = ui.column().classes("w-full gap-1")
                force_ble_button = ui.button(t("settings_force_ble_button"), icon="bluetooth_searching")

                async def _finish_force_ble(auto_select: str) -> None:
                    if not connection_health.try_acquire_command_slot(dwarf_uid):
                        ui.notify(t("device_busy"), type="warning")
                        return
                    force_ble_button.disable()
                    ble_status_label.set_text(
                        t("pairing_connecting_to", name=auto_select)
                        if auto_select
                        else t("pairing_searching")
                    )
                    try:
                        success, message = await run.io_bound(
                            _do_force_bluetooth,
                            session,
                            ble_psd_input.value or "DWARF_12345678",
                            ble_ssid_input.value,
                            ble_pwd_input.value,
                            auto_select,
                        )
                    finally:
                        connection_health.release_command_slot(dwarf_uid)
                        force_ble_button.enable()

                    ble_status_label.set_text(message)
                    ble_status_label.classes(
                        replace=f"text-xs {'text-green-700' if success else 'text-red-700'}"
                    )
                    if success:
                        connection_health.mark_just_connected(dwarf_uid)

                async def _handle_force_ble() -> None:
                    if not ble_ssid_input.value.strip() or not ble_pwd_input.value.strip():
                        ui.notify(t("pairing_wifi_required"), type="negative")
                        return

                    # No command slot held here - the BLE scan is a
                    # separate subsystem entirely (Bluetooth, not the
                    # WebSocket session.client_instance the slot
                    # protects) - only _finish_force_ble() below, which
                    # actually touches the session, needs it.
                    force_ble_button.disable()
                    ble_choice_container.clear()
                    ble_status_label.set_text(t("pairing_searching"))
                    try:
                        outcome, names = await run.io_bound(scan_dwarf_devices)
                    except Exception as e:
                        force_ble_button.enable()
                        ble_status_label.set_text(
                            t("pairing_ble_unavailable", error_type=type(e).__name__, error=str(e))
                        )
                        return

                    if outcome == "none":
                        force_ble_button.enable()
                        ble_status_label.set_text(t("pairing_connection_failed"))
                        return

                    if outcome == "single":
                        await _finish_force_ble("")
                        return

                    ble_status_label.set_text(t("pairing_multiple_found", count=len(names)))
                    with ble_choice_container:
                        ble_choice = ui.radio(names, value=names[0]).classes("w-full")
                        ui.label(t("pairing_rescan_note")).classes("text-xs text-grey-5")

                        async def _connect_chosen() -> None:
                            ble_choice_container.clear()
                            await _finish_force_ble(ble_choice.value)

                        ui.button(t("pairing_connect_to_selected"), on_click=_connect_chosen).props(
                            "color=primary"
                        )
                    force_ble_button.enable()

                force_ble_button.on("click", _handle_force_ble)
