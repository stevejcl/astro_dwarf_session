"""Reusable Site picker: a dropdown of known Sites (site_registry.py)
plus an inline "+" button to create a new one without leaving the
current page - a Site must exist before a Dwarf can be paired/
configured, so forcing a detour to /sites first every time would be
pure friction (user-requested Sep 2026). Used by pages/manual_config.py,
pages/pairing.py and pages/settings.py.
"""
from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

from components.geolocation import fetch_current_location
from components.i18n import t
from site_registry import SiteEntry, add_site_entry, list_site_entries


def site_picker(initial_value: Optional[str] = None) -> tuple[ui.select, Callable[[], Optional[SiteEntry]]]:
    """Renders `Site [dropdown] [+]` inline. Returns (select,
    get_selected_site) - get_selected_site() re-reads site_registry
    every call (not just the label the dropdown shows), so it always
    reflects the latest saved values, including a Site just created via
    the "+" dialog (which auto-selects itself on save)."""
    sites = list_site_entries()
    names = [s.name for s in sites]

    with ui.row().classes("w-full gap-2 items-end"):
        select = ui.select(
            names,
            value=initial_value if initial_value in names else (names[0] if names else None),
            label=t("site_picker_label"),
        ).classes("flex-1")

        def open_create_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                ui.label(t("sites_new_title")).classes("text-base")
                name_input = ui.input(t("sites_name")).classes("w-full")
                ssid_input = ui.input(t("wifi_ssid")).classes("w-full")
                pwd_input = ui.input(t("wifi_password"), password=True).classes("w-full")
                lon_input = ui.number(t("settings_longitude"), format="%.6f").classes("w-full")
                lat_input = ui.number(t("settings_latitude"), format="%.6f").classes("w-full")

                geolocation_status = ui.label("").classes("text-xs")

                async def handle_use_current_location() -> None:
                    result = await fetch_current_location(geolocation_status)
                    if result is None:
                        return
                    lat, lon = result
                    lon_input.value = lon
                    lat_input.value = lat

                ui.button(
                    t("settings_use_current_location"),
                    icon="my_location",
                    on_click=handle_use_current_location,
                ).props("flat")

                tz_input = ui.input(t("settings_timezone"), value="Europe/Paris").classes("w-full")
                dialog_status = ui.label("").classes("text-xs")

                def handle_create() -> None:
                    if not name_input.value.strip():
                        dialog_status.set_text(t("sites_name_required"))
                        dialog_status.classes(replace="text-xs text-red-700")
                        return

                    entry = SiteEntry(
                        name=name_input.value.strip(),
                        wifi_ssid=ssid_input.value.strip(),
                        wifi_password=pwd_input.value,
                        longitude=float(lon_input.value) if lon_input.value is not None else None,
                        latitude=float(lat_input.value) if lat_input.value is not None else None,
                        timezone=tz_input.value.strip(),
                    )
                    try:
                        add_site_entry(entry)
                    except ValueError as e:
                        dialog_status.set_text(str(e))
                        dialog_status.classes(replace="text-xs text-red-700")
                        return

                    select.set_options([s.name for s in list_site_entries()], value=entry.name)
                    dialog.close()

                with ui.row().classes("gap-2 mt-2"):
                    ui.button(t("sites_add"), icon="save", on_click=handle_create).props(
                        "color=primary"
                    )
                    ui.button(t("cancel"), on_click=dialog.close).props("flat")
            dialog.open()

        ui.button(icon="add", on_click=open_create_dialog).props("flat round dense")

    def get_selected_site() -> Optional[SiteEntry]:
        if not select.value:
            return None
        return next((s for s in list_site_entries() if s.name == select.value), None)

    return select, get_selected_site
