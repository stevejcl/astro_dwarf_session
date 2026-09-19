"""Read-only multi-device 'watch' dashboard: /watch

Same layout/polling pattern as pages/dashboard.py's build_dashboard_page(),
reusing DeviceCardView as-is - it was already pure display (name, IP,
battery/temperature/disk, live thumbnail when a session is active) with a
single on_open callback for its one interactive affordance: clicking a
card navigates. The only change from the control dashboard is where that
click goes - /watch/{dwarf_uid} instead of /session/{dwarf_uid} - so a
spectator can never land on a page with capture/connect/disconnect
buttons by clicking through from here.
"""
from __future__ import annotations

from nicegui import ui

from dwarf_python_api.lib.dwarf_session import get_manager

from components import connection_health
from components.device_card import DeviceCardView
from components.i18n import t
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme, theme_toggle_button


def _open_device(dwarf_uid: str) -> None:
    ui.navigate.to(f"/watch/{dwarf_uid}")


def build_watch_dashboard_page() -> None:
    @ui.page("/watch", title="Astro Dwarf Session — Watch")
    def watch_dashboard_page() -> None:
        add_pwa_head_tags()
        apply_theme()
        manager = get_manager()

        initial_count = len(manager.all())
        columns = 2 if initial_count >= 2 else 1
        container_width = (
            "max-w-2xl md:max-w-3xl lg:max-w-4xl xl:max-w-5xl 2xl:max-w-[1600px]"
            if columns == 2
            else "max-w-md md:max-w-lg lg:max-w-xl xl:max-w-2xl 2xl:max-w-[900px]"
        )

        with ui.column().classes(f"w-full {container_width} mx-auto gap-3 p-4"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label(t("my_dwarfs")).classes("text-xl")
                theme_toggle_button()

            empty_label = ui.label(t("no_devices_configured")).classes(
                "text-grey-6 text-sm"
            )
            cards_container = ui.grid(columns=columns).classes("w-full gap-3")
            cards: dict[str, DeviceCardView] = {}

            async def poll() -> None:
                sessions = manager.all()
                current_uids = {s.dwarf_uid for s in sessions}

                if current_uids != set(cards):
                    cards_container.clear()
                    cards.clear()
                    with cards_container:
                        for session in sessions:
                            cards[session.dwarf_uid] = DeviceCardView(
                                session, on_open=_open_device
                            )
                    empty_label.set_visibility(not sessions)
                    return

                for session in sessions:
                    await connection_health.maybe_check(session)
                    cards[session.dwarf_uid].update(session)

            ui.timer(2.0, poll)
