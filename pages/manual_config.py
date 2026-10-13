"""No-Bluetooth device config wizard.

For when a device's Wifi credentials were already handed over via the
official DwarfLab app (so the Dwarf reconnects to that network on its
own after a restart - no BLE pairing needed at all) - this page just
writes the config_py/config_ini/devices.json entry astro_dwarf_session
needs to talk to it, using device_provisioning.write_manual_config()
(which writes every field in one shot, unlike pairing.py's blank
template + BLE fill-in - see that function's docstring).

Built as a direct workaround for pages/pairing.py's Bluetooth scan
failing outright on some machines (bleak not detecting the adapter at
all) - this path never touches Bluetooth, so it works regardless.

Wifi credentials and location come ENTIRELY from the chosen Site (user-
requested Sep 2026: Sites are the single source of truth for these) -
this page no longer asks for them directly. The IP and UID fields are
the two values BLE would normally have discovered on its own - the
user reads them off the DwarfLab app's own "My Device" screen
instead - or the IP alone: the UID (the Dwarf's Bluetooth name) and the
model are then read from the Dwarf itself (POST :8082/deviceInfo).

Dwarfium-Hub opens this page filled in for a Dwarf Scope Archive already
knows (?name=&model=&ip=), with its Scope Archive id and URL
(?dwarfium_id=&dwarfium_base_url=): the new device is then saved already
linked to it."""
from __future__ import annotations

import configparser

from nicegui import run, ui

from dwarf_python_api.lib.dwarf_config import DwarfConfig
from dwarf_python_api.lib.dwarf_session import get_manager

from components.i18n import t
from components.pwa import add_pwa_head_tags
from components.site_picker import site_picker
from components.theme import apply_theme
from device_provisioning import (DEFAULT_BLE_PSD, DEVICE_MODELS, ManualDeviceInput, read_device_identity,
                                 write_manual_config)
from device_registry import add_device_entry


def build_manual_config_page() -> None:
    @ui.page("/manual-config", title="Astro Dwarf Session - Manual config")
    def manual_config_page(name: str = "", model: str = "", ip: str = "",
                           dwarfium_id: str = "", dwarfium_base_url: str = "") -> None:
        add_pwa_head_tags()
        apply_theme()

        with ui.column().classes("w-full max-w-md mx-auto gap-3 p-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round")
            ui.label(t("manual_config_title")).classes("text-xl")
            ui.label(t("manual_config_hint")).classes("text-sm text-grey-6")

            device_name = ui.input(
                t("device_name"), value=name, placeholder=t("device_name_placeholder")
            ).classes("w-full")
            model_select = ui.select(
                DEVICE_MODELS, value=model if model in DEVICE_MODELS else DEVICE_MODELS[0],
                label=t("manual_config_model"),
            ).classes("w-full")

            # The "+" next to the dropdown lets a first Site be created
            # right here, without leaving the page - a Site must exist
            # before a device can be configured, but that no longer
            # means a forced detour to /sites first.
            site_select, get_selected_site = site_picker()

            ui.label(t("manual_config_ip_hint")).classes("text-xs text-grey-6")
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                ip_input = ui.input(t("manual_config_ip"), value=ip).classes("flex-1")
                read_button = ui.button(t("manual_config_read"), icon="wifi_find").props("flat no-caps")
            uid_input = ui.input(t("manual_config_uid")).classes("w-full")

            async def read_from_dwarf(quiet: bool = False) -> bool:
                """UID + model from the Dwarf at the IP typed in."""
                address = ip_input.value.strip()
                if not address:
                    if not quiet:
                        ui.notify(t("manual_config_ip_first"), type="warning")
                    return False
                read_button.props("loading")
                try:
                    info = await run.io_bound(read_device_identity, address)
                finally:
                    read_button.props(remove="loading")
                if not info:
                    if not quiet:
                        ui.notify(t("manual_config_no_answer", ip=address), type="warning", multi_line=True)
                    return False
                uid_input.value = info["uid"]
                if info["model"]:
                    model_select.value = info["model"]
                if not device_name.value.strip():
                    device_name.value = info["uid"]
                ui.notify(t("manual_config_read_ok", uid=info["uid"]), type="positive")
                return True

            read_button.on_click(read_from_dwarf)
            if ip:      # opened with the IP (Dwarfium-Hub): the rest from the Dwarf, if it answers
                ui.timer(0.5, lambda: read_from_dwarf(quiet=True), once=True)
            ble_psd_input = ui.input(t("bluetooth_password"), value=DEFAULT_BLE_PSD).classes(
                "w-full"
            )

            status_label = ui.label("").classes("text-sm")

            async def handle_save() -> None:
                if not device_name.value.strip():
                    ui.notify(t("pairing_name_required"), type="negative")
                    return
                site = get_selected_site()
                if not site:
                    ui.notify(t("manual_config_site_required"), type="negative")
                    return
                if not ip_input.value.strip():
                    ui.notify(t("manual_config_ip_uid_required"), type="negative")
                    return
                if not uid_input.value.strip() and not await read_from_dwarf():
                    return      # neither typed nor read: said by read_from_dwarf()

                data = ManualDeviceInput(
                    device_name=device_name.value.strip(),
                    model=model_select.value,
                    dwarf_ip=ip_input.value.strip(),
                    dwarf_uid=uid_input.value.strip(),
                    site=site,
                    ble_psd=ble_psd_input.value.strip() or DEFAULT_BLE_PSD,
                )

                try:
                    config_py, config_ini = write_manual_config(data)
                except (FileExistsError, ValueError) as e:
                    status_label.set_text(str(e))
                    status_label.classes(replace="text-sm text-red-700")
                    return

                if dwarfium_id.isdigit():
                    # Opened from Dwarfium-Hub for a Dwarf of Scope Archive:
                    # saved linked to it (Settings > Scope Archive)
                    ini = configparser.ConfigParser()
                    ini.read(config_ini, encoding="utf-8")
                    if not ini.has_section("CONFIG"):
                        ini.add_section("CONFIG")
                    ini["CONFIG"]["dwarfium_id"] = dwarfium_id
                    if dwarfium_base_url.startswith(("http://", "https://")):
                        ini["CONFIG"]["dwarfium_base_url"] = dwarfium_base_url
                    with open(config_ini, "w", encoding="utf-8") as f:
                        ini.write(f)

                cfg = DwarfConfig.from_files(config_py, config_ini)
                get_manager().add(cfg)
                add_device_entry(name=data.device_name, config_py=config_py, config_ini=config_ini)

                ui.notify(t("manual_config_success", device_name=data.device_name), type="positive")
                ui.navigate.to("/")

            ui.button(t("settings_save"), icon="save", on_click=handle_save).props("color=primary")
