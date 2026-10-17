"""The Scripts tab's card: what happens after a session and at the end of
the night, for this Dwarf (components/end_of_night.py)."""
from __future__ import annotations

import time
from datetime import datetime

from nicegui import ui

from components import end_of_night as E
from components.i18n import t


def _hhmm(epoch: float | None) -> str:
    return datetime.fromtimestamp(epoch).strftime("%H:%M") if epoch else ""


def build_end_of_night_card(session) -> None:
    uid = session.dwarf_uid
    settings = E.get_settings(uid)

    def save_exit(**values) -> None:
        E.set_settings(uid, exit_=values)
        estimate.refresh()

    def save_night(**values) -> None:
        E.set_settings(uid, night=values)
        estimate.refresh()

    with ui.card().classes("w-full gap-2"):
        ui.label(t("eon_title")).classes("text-base font-medium")

        # After each session
        ex = settings["exit"]
        with ui.row().classes("items-center gap-x-4 gap-y-1 flex-wrap"):
            ui.switch(t("eon_exit_label"), value=ex["enabled"],
                      on_change=lambda e: save_exit(enabled=bool(e.value)))
            ui.number(t("eon_after_min"), value=ex["after_min"], min=0, max=240, step=1, format="%d",
                      on_change=lambda e: save_exit(after_min=int(e.value or 0))).classes("w-28")
            ui.checkbox(t("eon_stop_tracking"), value=ex["stop_tracking"],
                        on_change=lambda e: save_exit(stop_tracking=bool(e.value)))
        ui.label(t("eon_exit_hint")).classes("text-xs text-grey-6 -mt-1")

        ui.separator()

        # End of the night
        night = settings["night"]
        with ui.row().classes("items-center gap-x-4 gap-y-1 flex-wrap"):
            ui.select({E.NIGHT_NONE: t("eon_night_none"), E.NIGHT_CLOSE: t("eon_night_close"),
                       E.NIGHT_POWER_OFF: t("eon_night_power_off")},
                      value=night["action"], label=t("eon_night_label"),
                      on_change=lambda e: save_night(action=e.value)).classes("min-w-56")
            ui.number(t("eon_after_min"), value=night["after_min"], min=0, max=600, step=5, format="%d",
                      on_change=lambda e: save_night(after_min=int(e.value or 0))).classes("w-28")
        ui.label(t("eon_night_hint")).classes("text-xs text-grey-6 -mt-1")

        @ui.refreshable
        def estimate() -> None:
            current = E.get_settings(uid)
            state = E.status(uid)
            lines = []
            if state["exit_due"]:
                lines.append(t("eon_exit_due", time=_hhmm(state["exit_due"])))
            action = current["night"]["action"]
            if action != E.NIGHT_NONE:
                delay = int(current["night"]["after_min"]) * 60
                try:
                    end = E.last_planned_end(session)
                except Exception:
                    end = None
                if end is not None:
                    lines.append(t("eon_night_estimate", time=_hhmm(end + delay), last=_hhmm(end)))
                elif state["idle_since"]:
                    lines.append(t("eon_night_estimate_idle", time=_hhmm(state["idle_since"] + delay)))
                else:
                    lines.append(t("eon_night_estimate_none", minutes=current["night"]["after_min"]))
            if E.is_closed_by_app(uid):
                lines.append(t("eon_closed_by_app"))
            for line in lines:
                ui.label(line).classes("text-sm text-primary")

        estimate()

        ui.separator()

        # Opening position
        @ui.refreshable
        def position() -> None:
            pos = E.open_position(uid)
            with ui.row().classes("items-center gap-2 flex-wrap"):
                ui.icon("bookmark", size="sm").classes("text-grey-7")
                if pos is None:
                    ui.label(t("eon_position_none")).classes("text-sm")
                else:
                    ui.label(t("eon_position", pitch=f"{pos['pitch']:.1f}", saved_at=pos.get("saved_at", ""),
                               source=t("eon_source_" + str(pos.get("source", "auto"))))).classes("text-sm")
                    ui.button(icon="delete_outline", on_click=lambda: (E.clear_open_position(uid), position.refresh())) \
                        .props("flat dense round size=sm").tooltip(t("eon_position_clear"))
            ui.label(t("eon_position_hint")).classes("text-xs text-grey-6")

        position()

    # The estimate and the saved position follow what happens meanwhile
    ui.timer(30, lambda: (estimate.refresh(), position.refresh()))
