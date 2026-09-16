"""Sites management page: CRUD for the Wifi network + location
"profiles" a Dwarf gets provisioned with (see site_registry.py) - used
by pages/manual_config.py to pre-fill the no-BLE wizard. A natural
follow-up (not done here) would be having pages/pairing.py's own Wifi
fields pull from a Site too, instead of only find_shared_config_value()
against already-paired devices."""
from __future__ import annotations

from nicegui import ui

from components.i18n import t
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme
from site_registry import (
    SiteEntry,
    add_site_entry,
    list_site_entries,
    remove_site_entry,
    update_site_entry,
)


def build_sites_page() -> None:
    @ui.page("/sites", title="Astro Dwarf Session - Sites")
    def sites_page() -> None:
        add_pwa_head_tags()
        apply_theme()

        with ui.column().classes("w-full max-w-md mx-auto gap-3 p-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round")
            ui.label(t("sites_title")).classes("text-xl")
            ui.label(t("sites_hint")).classes("text-sm text-grey-6")

            list_container = ui.column().classes("w-full gap-2")
            form_container = ui.column().classes("w-full gap-2")

            def refresh_list() -> None:
                list_container.clear()
                with list_container:
                    for site in list_site_entries():
                        with ui.card().classes("w-full"):
                            with ui.row().classes("items-center justify-between w-full"):
                                with ui.column().classes("gap-0"):
                                    ui.label(site.name).classes("text-base")
                                    ui.label(site.wifi_ssid).classes("text-xs text-grey-6")
                                with ui.row().classes("gap-1"):
                                    ui.button(
                                        icon="edit", on_click=lambda s=site: open_form(s)
                                    ).props("flat round dense")
                                    ui.button(
                                        icon="delete", on_click=lambda s=site: handle_delete(s)
                                    ).props("flat round dense color=red")

            def handle_delete(site: SiteEntry) -> None:
                remove_site_entry(site.name)
                ui.notify(t("sites_deleted", name=site.name), type="positive")
                refresh_list()

            def open_form(site: SiteEntry | None) -> None:
                form_container.clear()
                editing_name = site.name if site else None

                with form_container:
                    ui.label(t("sites_edit_title") if site else t("sites_new_title")).classes(
                        "text-base mt-2"
                    )
                    name_input = ui.input(t("sites_name"), value=site.name if site else "").classes(
                        "w-full"
                    )
                    ssid_input = ui.input(
                        t("wifi_ssid"), value=site.wifi_ssid if site else ""
                    ).classes("w-full")
                    pwd_input = ui.input(
                        t("wifi_password"), password=True, value=site.wifi_password if site else ""
                    ).classes("w-full")
                    lon_input = ui.number(
                        t("settings_longitude"),
                        value=site.longitude if site else None,
                        format="%.6f",
                    ).classes("w-full")
                    lat_input = ui.number(
                        t("settings_latitude"),
                        value=site.latitude if site else None,
                        format="%.6f",
                    ).classes("w-full")
                    tz_input = ui.input(
                        t("settings_timezone"), value=site.timezone if site else "Europe/Paris"
                    ).classes("w-full")
                    notes_input = ui.textarea(
                        t("sites_notes"), value=site.notes if site else ""
                    ).classes("w-full")

                    form_status = ui.label("").classes("text-xs")

                    def handle_save() -> None:
                        if not name_input.value.strip():
                            form_status.set_text(t("sites_name_required"))
                            form_status.classes(replace="text-xs text-red-700")
                            return

                        entry = SiteEntry(
                            name=name_input.value.strip(),
                            wifi_ssid=ssid_input.value.strip(),
                            wifi_password=pwd_input.value,
                            longitude=float(lon_input.value) if lon_input.value is not None else None,
                            latitude=float(lat_input.value) if lat_input.value is not None else None,
                            timezone=tz_input.value.strip(),
                            notes=notes_input.value.strip(),
                        )
                        try:
                            if editing_name:
                                update_site_entry(editing_name, entry)
                            else:
                                add_site_entry(entry)
                        except (ValueError, KeyError) as e:
                            form_status.set_text(str(e))
                            form_status.classes(replace="text-xs text-red-700")
                            return

                        ui.notify(t("sites_saved", name=entry.name), type="positive")
                        form_container.clear()
                        refresh_list()

                    with ui.row().classes("gap-2"):
                        ui.button(t("settings_save"), icon="save", on_click=handle_save).props(
                            "color=primary"
                        )
                        ui.button(t("cancel"), on_click=form_container.clear).props("flat")

            ui.button(t("sites_add"), icon="add", on_click=lambda: open_form(None)).props(
                "color=primary"
            )

            refresh_list()
