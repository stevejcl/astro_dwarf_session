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

The IP and UID fields are the two values BLE would normally have
discovered on its own - the user reads them off the DwarfLab app's own
"My Device" screen instead."""
from __future__ import annotations

from nicegui import ui

from dwarf_python_api.lib.dwarf_config import DwarfConfig
from dwarf_python_api.lib.dwarf_session import get_manager

from components.i18n import t
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme
from device_provisioning import (
    DEFAULT_BLE_PSD,
    DEVICE_MODELS,
    ManualDeviceInput,
    write_manual_config,
)
from device_registry import add_device_entry
from site_registry import list_site_entries


def build_manual_config_page() -> None:
    @ui.page("/manual-config", title="Astro Dwarf Session - Manual config")
    def manual_config_page() -> None:
        add_pwa_head_tags()
        apply_theme()

        sites = list_site_entries()
        site_names = [s.name for s in sites]

        with ui.column().classes("w-full max-w-md mx-auto gap-3 p-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round")
            ui.label(t("manual_config_title")).classes("text-xl")
            ui.label(t("manual_config_hint")).classes("text-sm text-grey-6")

            if not sites:
                ui.label(t("manual_config_no_sites")).classes("text-sm text-orange-700")
                ui.button(
                    t("sites_add"), icon="add", on_click=lambda: ui.navigate.to("/sites")
                ).props("flat")
                return

            device_name = ui.input(
                t("device_name"), placeholder=t("device_name_placeholder")
            ).classes("w-full")
            model_select = ui.select(
                DEVICE_MODELS, value=DEVICE_MODELS[0], label=t("manual_config_model")
            ).classes("w-full")
            site_select = ui.select(
                site_names, value=site_names[0], label=t("manual_config_site")
            ).classes("w-full")

            ui.label(t("manual_config_ip_hint")).classes("text-xs text-grey-6")
            ip_input = ui.input(t("manual_config_ip")).classes("w-full")
            uid_input = ui.input(t("manual_config_uid")).classes("w-full")
            ble_psd_input = ui.input(t("bluetooth_password"), value=DEFAULT_BLE_PSD).classes(
                "w-full"
            )

            status_label = ui.label("").classes("text-sm")

            def handle_save() -> None:
                if not device_name.value.strip():
                    ui.notify(t("pairing_name_required"), type="negative")
                    return
                if not site_select.value:
                    ui.notify(t("manual_config_site_required"), type="negative")
                    return
                if not ip_input.value.strip() or not uid_input.value.strip():
                    ui.notify(t("manual_config_ip_uid_required"), type="negative")
                    return

                site = next(s for s in sites if s.name == site_select.value)

                data = ManualDeviceInput(
                    device_name=device_name.value.strip(),
                    model=model_select.value,
                    dwarf_ip=ip_input.value.strip(),
                    dwarf_uid=uid_input.value.strip(),
                    wifi_ssid=site.wifi_ssid,
                    wifi_password=site.wifi_password,
                    longitude=site.longitude,
                    latitude=site.latitude,
                    timezone=site.timezone,
                    ble_psd=ble_psd_input.value.strip() or DEFAULT_BLE_PSD,
                )

                try:
                    config_py, config_ini = write_manual_config(data)
                except (FileExistsError, ValueError) as e:
                    status_label.set_text(str(e))
                    status_label.classes(replace="text-sm text-red-700")
                    return

                cfg = DwarfConfig.from_files(config_py, config_ini)
                get_manager().add(cfg)
                add_device_entry(name=data.device_name, config_py=config_py, config_ini=config_ini)

                ui.notify(t("manual_config_success", device_name=data.device_name), type="positive")
                ui.navigate.to("/")

            ui.button(t("settings_save"), icon="save", on_click=handle_save).props("color=primary")
