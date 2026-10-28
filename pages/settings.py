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

SITE AS SOURCE OF TRUTH (user-requested Sep 2026): the fields below can
still be edited by hand for a one-off tweak, but the normal path is
now picking a Site (components/site_picker.py) and clicking "Apply" -
that copies the Site's Wifi/location straight into the form fields
below (longitude/latitude/timezone/city_name AND the Force Bluetooth
section's SSID/password), which are then saved/applied exactly as
before by this page's own Save / Force Bluetooth buttons. This page
intentionally does NOT try to auto-detect which Site is "currently
applied" - there's no stored link between a device and a Site (config.
ini has no such field), so re-selecting one each time is a deliberate,
explicit action rather than a guess based on matching ble_sta_ssid.

LOCATION AUTO-FILL: uses the BROWSER's own Geolocation API
(navigator.geolocation) via components/geolocation.py, shared with
pages/sites.py (Sites are the natural place to set this now, but a
device's fields can still be nudged individually here without going
through its Site) - no typing needed, just a one-time permission
prompt, and it's already running on the same machine/network as the
telescope in the normal case. Deliberately NOT IP-based geolocation
(too coarse - city-level at best) and NOT an address-to-coordinates
lookup (would need typing an address AND a third-party geocoding
service for no real benefit over just asking the browser directly).

CAVEAT: in native mode (ui.run(native=True), pywebview), geolocation
support depends on the underlying embedded engine (WebView2 on Windows,
WebKit elsewhere) and may not prompt/work as reliably as in a real
browser tab - if "Use current location" fails there, the same NiceGUI
server is also reachable over LAN in a normal browser (already
confirmed working simultaneously with native mode elsewhere in this
app), or coordinates can simply be typed in by hand."""
from __future__ import annotations

import configparser

from nicegui import run, ui

from dwarf_python_api.get_config_data import set_config_data
from dwarf_python_api.lib.dwarf_config import DwarfConfig
from dwarf_python_api.lib.dwarf_session import get_manager

from device_registry import find_shared_config_value, name_and_uid, rename_device, device_name
from device_provisioning import update_dwarf_ip
from dwarf_python_api.lib.dwarf_utils import perform_disconnect

from components import scope_archive
from components import connection_health
from components.ble_pairing import connect_ble, scan_dwarf_devices, write_ble_credentials
from components.geolocation import fetch_current_location
from components.https_card import render_https_card
from components.i18n import t
from components.network_info import qr_svg, wake_url
from components.pwa import add_pwa_head_tags
from components.site_picker import site_picker
from components.theme import apply_theme


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

    # connect_ble() writes what it found (uid, IP, model) into config_py
    # as it goes: kept as it was unless it is this Dwarf (user-reported Oct
    # 2026: another Dwarf answered, "not applied" was said, but its uid was
    # in the file already - after a restart this Dwarf had the other one's
    # identity, and one of the two vanished from the list)
    try:
        with open(config_py, "rb") as f:
            saved = f.read()
    except OSError:
        saved = None

    def _restore() -> None:
        if saved is not None:
            try:
                with open(config_py, "wb") as f:
                    f.write(saved)
            except OSError:
                pass

    connected = connect_ble(ble_psd, wifi_ssid, wifi_pwd, auto_select)
    if not connected:
        _restore()
        return False, t("settings_force_ble_failed")

    fresh = DwarfConfig.from_files(config_py, config_ini)
    if not fresh.dwarf_uid:
        _restore()
        return False, t("settings_force_ble_no_uid")
    if fresh.dwarf_uid != session.dwarf_uid:
        # BLE matched a DIFFERENT Dwarf (several in range): its identity
        # neither in this session nor in this Dwarf's file
        _restore()
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
            name_label = ui.label(name_and_uid(session)).classes("text-sm text-grey-6 -mt-2")

            # The Dwarf's name (user-reported Oct 2026: typed when it was
            # added, then neither shown nor editable) - its display name
            # only, the dwarf_uid and the config files stay
            def _handle_rename() -> None:
                new_name = (name_input.value or "").strip()
                if not new_name:
                    ui.notify(t("settings_device_name_required"), type="negative")
                    return
                if not rename_device(session, new_name):
                    ui.notify(t("settings_device_name_failed"), type="negative")
                    return
                name_label.set_text(name_and_uid(session))
                ui.notify(t("settings_device_name_saved", name=new_name), type="positive")

            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                name_input = ui.input(
                    t("settings_device_name"),
                    value="" if device_name(session) == session.dwarf_uid else device_name(session),
                ).classes("flex-1").on("keydown.enter", _handle_rename)
                ui.button(icon="save", on_click=_handle_rename).props("flat round") \
                    .tooltip(t("settings_device_name_save"))
            ui.label(t("settings_location_hint")).classes("text-sm text-grey-6")

            geolocation_status = ui.label("").classes("text-xs")

            # Pre-filled from another already-configured device, if this
            # device's own value isn't set yet (user-requested Sep
            # 2026) - location/Stellarium/timezone are almost always the
            # SAME across every Dwarf someone owns (same house, same PC
            # running Stellarium), so re-entering them for every newly
            # paired device is pure friction. Never overrides a value
            # THIS device already has - only fills in genuine gaps.
            shared_longitude = session.config.longitude
            if shared_longitude is None:
                shared_longitude = find_shared_config_value(get_manager(), lambda c: c.longitude, exclude_uid=dwarf_uid)
            shared_latitude = session.config.latitude
            if shared_latitude is None:
                shared_latitude = find_shared_config_value(get_manager(), lambda c: c.latitude, exclude_uid=dwarf_uid)
            shared_city_name = session.config.city_name or find_shared_config_value(
                get_manager(), lambda c: c.city_name, exclude_uid=dwarf_uid
            ) or ""
            shared_timezone = session.config.timezone or find_shared_config_value(
                get_manager(), lambda c: c.timezone, exclude_uid=dwarf_uid
            ) or ""
            shared_stellarium_ip = session.config.stellarium_ip or find_shared_config_value(
                get_manager(), lambda c: c.stellarium_ip, exclude_uid=dwarf_uid
            ) or "127.0.0.1"
            shared_stellarium_port = session.config.stellarium_port or find_shared_config_value(
                get_manager(), lambda c: c.stellarium_port, exclude_uid=dwarf_uid
            ) or 8090

            longitude_input = ui.number(
                t("settings_longitude"),
                value=shared_longitude,
                format="%.6f",
            ).classes("w-full")
            latitude_input = ui.number(
                t("settings_latitude"),
                value=shared_latitude,
                format="%.6f",
            ).classes("w-full")
            city_name_input = ui.input(
                t("settings_city_name"),
                value=session.config.city_name or "",
            ).classes("w-full")

            async def handle_use_current_location() -> None:
                result = await fetch_current_location(geolocation_status)
                if result is None:
                    return
                lat, lon = result
                longitude_input.value = lon
                latitude_input.value = lat

            ui.button(
                t("settings_use_current_location"),
                icon="my_location",
                on_click=handle_use_current_location,
            ).props("flat")

            timezone_input = ui.input(
                t("settings_timezone"), value=shared_timezone
            ).classes("w-full")

            # --- Apply from a Site (user-requested Sep 2026) ------------
            # Sites (pages/sites.py) are now the source of truth for
            # Wifi/location - this fills the fields above (and the Force
            # Bluetooth section's SSID/password further below) from the
            # chosen Site's saved values. Deliberately a separate
            # "Apply" click rather than auto-applying on selection - the
            # fields above may already hold a device-specific tweak the
            # user doesn't want silently overwritten just by opening the
            # dropdown.
            ui.label(t("settings_apply_site_hint")).classes("text-sm text-grey-6 mt-2")
            site_select, get_selected_site = site_picker()

            def handle_apply_site() -> None:
                site = get_selected_site()
                if site is None:
                    return
                if site.longitude is not None:
                    longitude_input.value = site.longitude
                if site.latitude is not None:
                    latitude_input.value = site.latitude
                city_name_input.value = site.name
                if site.timezone:
                    timezone_input.value = site.timezone
                ble_ssid_input.value = site.wifi_ssid
                ble_pwd_input.value = site.wifi_password
                ui.notify(t("settings_site_applied", name=site.name), type="positive")

            ui.button(
                t("settings_apply_site"), icon="content_copy", on_click=handle_apply_site
            ).props("flat")

            ui.label(t("settings_stellarium_hint")).classes("text-sm text-grey-6 mt-2")
            with ui.row().classes("w-full gap-2"):
                stellarium_ip_input = ui.input(
                    t("settings_stellarium_ip"),
                    value=shared_stellarium_ip,
                ).classes("flex-1")
                stellarium_port_input = ui.number(
                    t("settings_stellarium_port"),
                    value=shared_stellarium_port,
                    format="%.0f",
                ).classes("w-32")

            # Dwarfium Scope Archive (user-requested Sep 2026: cross-
            # launch links between the two apps) - dwarfium_id is
            # looked up manually by the user once, in Dwarfium's own
            # Dwarf Configuration page (its SQLite "id" column) - no
            # automatic detection in this first version.
            # getattr(..., "") on read (user-reported Sep 2026:
            # AttributeError on an older dwarf_python_api not yet
            # carrying these two new DwarfConfig fields) - see
            # pages/session.py's own matching comment. Writing these
            # back further down (session.config.dwarfium_base_url = ...)
            # doesn't need the same guard - plain attribute assignment
            # works even on an object whose class didn't originally
            # declare the field.
            ui.label(t("settings_dwarfium_hint")).classes("text-sm text-grey-6 mt-2")
            with ui.row().classes("w-full gap-2"):
                _scope_url, _dwarfium_id_current = scope_archive.scope_settings(session.config)
                dwarfium_url_input = ui.input(
                    t("settings_dwarfium_url"),
                    value=_scope_url or "http://localhost:8080",
                ).classes("flex-1")
                dwarfium_id_input = ui.number(
                    t("settings_dwarfium_id"),
                    value=int(_dwarfium_id_current) if _dwarfium_id_current else None,
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
                city_name = city_name_input.value.strip()
                tz = timezone_input.value.strip()
                stellarium_ip = stellarium_ip_input.value.strip() or "127.0.0.1"
                stellarium_port = int(stellarium_port_input.value or 8090)
                dwarfium_url = dwarfium_url_input.value.strip()
                dwarfium_id = (
                    str(int(dwarfium_id_input.value)) if dwarfium_id_input.value else ""
                )

                ini = _read_ini(session.config.config_ini_path)
                ini["CONFIG"]["longitude"] = str(lon)
                ini["CONFIG"]["latitude"] = str(lat)
                ini["CONFIG"]["city_name"] = city_name
                ini["CONFIG"]["timezone"] = tz
                ini["CONFIG"]["stellarium_ip"] = stellarium_ip
                ini["CONFIG"]["stellarium_port"] = str(stellarium_port)
                ini["CONFIG"]["dwarfium_base_url"] = dwarfium_url
                ini["CONFIG"]["dwarfium_id"] = dwarfium_id
                with open(session.config.config_ini_path, "w", encoding="utf-8") as f:
                    ini.write(f)

                # Live for the current session immediately - DwarfConfig
                # is a plain mutable dataclass, no reconnect needed for
                # this to take effect (read_longitude()/read_latitude()
                # read session.config.* directly).
                session.config.longitude = lon
                session.config.latitude = lat
                session.config.city_name = city_name
                session.config.timezone = tz
                session.config.stellarium_ip = stellarium_ip
                session.config.stellarium_port = stellarium_port
                session.config.dwarfium_base_url = dwarfium_url
                session.config.dwarfium_id = dwarfium_id

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
            # first time this device was paired before that existed, or
            # filled from the Site above via "Apply".
            with ui.card().classes("w-full p-0 mt-2"), ui.expansion(t("settings_force_ble_title"), icon="bluetooth_searching", value=False).classes("w-full"):
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

                    # This Dwarf by its Bluetooth name, which is its dwarf_uid
                    # (user-reported Oct 2026: Force Bluetooth done with the
                    # other DWARF 3, which then got this one's place) - straight
                    # to it when found, never another one on its own
                    if dwarf_uid in names:
                        await _finish_force_ble(dwarf_uid)
                        return
                    if outcome == "single":
                        ble_status_label.set_text(t("settings_force_ble_other_found", name=dwarf_uid, found=names[0]))
                    else:
                        ble_status_label.set_text(t("pairing_multiple_found", count=len(names)) + " "
                                                  + t("settings_force_ble_not_listed", name=dwarf_uid))
                    ble_status_label.classes(replace="text-xs text-orange-800")
                    with ble_choice_container:
                        ble_choice = ui.radio(names, value=None).classes("w-full")
                        ui.label(t("pairing_rescan_note")).classes("text-xs text-grey-5")

                        async def _connect_chosen() -> None:
                            if not ble_choice.value:
                                return
                            ble_choice_container.clear()
                            await _finish_force_ble(ble_choice.value)

                        ui.button(t("pairing_connect_to_selected"), on_click=_connect_chosen).props(
                            "color=primary"
                        )
                    force_ble_button.enable()

                force_ble_button.on("click", _handle_force_ble)

            # Wake up from the phone (user-requested Oct 2026): a Dwarf
            # that no longer answers on the home Wi-Fi wakes up once
            # switched to its hotspot over Bluetooth - from the phone's
            # browser (/wake-dwarf, wake_dwarf.html) when this PC is too
            # far from the Dwarf for Force Bluetooth above.
            with ui.card().classes("w-full p-0 mt-2"), ui.expansion(t("settings_wake_title"), icon="wifi_tethering", value=False).classes("w-full"):
                ui.label(t("settings_wake_hint")).classes("text-xs text-grey-6")
                url = wake_url(dwarf_uid)
                ui.html(qr_svg(url)).classes("w-48 h-48")
                ui.link(url, url, new_tab=True).classes("text-xs break-all")
                ui.label(t("settings_wake_chrome")).classes("text-xs text-grey-6")

            # Manual IP update (user-requested Sep 2026) - for someone
            # who configured this device manually in the first place
            # (pages/manual_config.py, no Bluetooth working on their
            # machine at all) and later needs to fix a changed IP (e.g.
            # a DHCP lease renewal) - the "Force Bluetooth reconnect"
            # section above already covers this same scenario, but
            # needs Bluetooth to work, which is exactly what got them
            # onto the manual-config path to begin with. No slot
            # needed - like _do_force_bluetooth, this disconnects first
            # if currently connected, before touching session.config
            # underneath a live connection.
            with ui.card().classes("w-full p-0 mt-2"), ui.expansion(t("settings_manual_ip_title"), icon="edit_location_alt", value=False).classes("w-full"):
                ui.label(t("settings_manual_ip_hint")).classes("text-xs text-grey-6")
                manual_ip_input = ui.input(t("settings_manual_ip_label"), value=session.config.dwarf_ip or "").classes("w-full")
                manual_ip_status = ui.label("").classes("text-xs")

                def _handle_manual_ip_update() -> None:
                    new_ip = manual_ip_input.value.strip()
                    if not new_ip:
                        ui.notify(t("settings_manual_ip_required"), type="negative")
                        return
                    if session.is_connected:
                        perform_disconnect(session=session)
                    try:
                        update_dwarf_ip(session.config.config_py_path, new_ip)
                    except (OSError, ValueError) as e:
                        manual_ip_status.set_text(str(e))
                        manual_ip_status.classes(replace="text-xs text-red-700")
                        return
                    session.config.dwarf_ip = new_ip
                    manual_ip_status.set_text(t("settings_manual_ip_success", ip=new_ip))
                    manual_ip_status.classes(replace="text-xs text-green-700")

                ui.button(t("settings_manual_ip_button"), icon="save", on_click=_handle_manual_ip_update)

            # HTTPS for phones (user-requested Oct 2026), the last card:
            # Android installs the app full screen only over HTTPS - see
            # components/https_server.py
            render_https_card()
