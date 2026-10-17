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


def _info(key: str) -> None:
    """The help of a line: an (i) icon, its text in a tooltip (hidden by
    default - user-requested Oct 2026: the card hid the scripts below)."""
    with ui.icon("info_outline", size="xs").classes("text-grey-6 cursor-help"):
        ui.tooltip(t(key)).style("white-space: pre-line; max-width: 420px").classes("text-sm")


def _summary(uid: str) -> str:
    current = E.get_settings(uid)
    ex, night = current["exit"], current["night"]
    parts = [t("eon_sum_exit", minutes=ex["after_min"]) if ex["enabled"] else t("eon_sum_exit_off")]
    if night["action"] == E.NIGHT_NONE:
        parts.append(t("eon_sum_night_off"))
    else:
        key = "eon_sum_night_close" if night["action"] == E.NIGHT_CLOSE else "eon_sum_night_power_off"
        parts.append(t(key, minutes=night["after_min"]))
    return " \u00b7 ".join(parts)


def build_end_of_night_card(session) -> None:
    uid = session.dwarf_uid
    settings = E.get_settings(uid)

    def refresh_all() -> None:
        expansion._props["caption"] = _summary(uid)
        expansion.update()
        estimate.refresh()

    def save_exit(**values) -> None:
        E.set_settings(uid, exit_=values)
        refresh_all()

    def save_night(**values) -> None:
        E.set_settings(uid, night=values)
        refresh_all()

    with ui.card().classes("w-full gap-1 p-2"):
        # Folded by default: the scripts below matter most
        with ui.expansion(t("eon_title"), caption=_summary(uid), icon="bedtime") \
                .classes("w-full").props("dense") as expansion:
            # After each session
            ex = settings["exit"]
            with ui.row().classes("items-center gap-x-4 gap-y-1 flex-wrap"):
                ui.switch(t("eon_exit_label"), value=ex["enabled"],
                          on_change=lambda e: save_exit(enabled=bool(e.value)))
                ui.number(t("eon_after_min"), value=ex["after_min"], min=0, max=240, step=1, format="%d",
                          on_change=lambda e: save_exit(after_min=int(e.value or 0))).classes("w-28")
                ui.checkbox(t("eon_stop_tracking"), value=ex["stop_tracking"],
                            on_change=lambda e: save_exit(stop_tracking=bool(e.value)))
                _info("eon_exit_hint")

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
                _info("eon_night_hint")

            def toggle_accessory(e) -> None:
                E.set_accessory(uid, bool(e.value))
                refresh_all()

            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.checkbox(t("eon_accessory"), value=E.has_accessory(uid), on_change=toggle_accessory) \
                    .classes("min-w-0")
                _info("eon_accessory_hint")

            ui.separator()

            # Initial position
            @ui.refreshable
            def position() -> None:
                pos = E.open_position(uid)
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.icon("bookmark", size="sm").classes("text-grey-7 shrink-0")
                    if pos is None:
                        ui.label(t("eon_position_none")).classes("text-sm flex-1 min-w-0")
                    else:
                        ui.label(t("eon_position", position=E.describe_position(pos), saved_at=pos.get("saved_at", ""),
                                   source=t("eon_source_" + str(pos.get("source", "auto"))))) \
                            .classes("text-sm flex-1 min-w-0")
                        ui.button(icon="delete_outline",
                                  on_click=lambda: (E.clear_open_position(uid), position.refresh())) \
                            .props("flat dense round size=sm").classes("shrink-0").tooltip(t("eon_position_clear"))
                    _info("eon_position_hint")

            position()

        # What is coming and what needs attention: shown folded too
        @ui.refreshable
        def estimate() -> None:
            current = E.get_settings(uid)
            state = E.status(uid)
            lines = []
            if state["exit_due"]:
                lines.append(t("eon_exit_due", time=_hhmm(state["exit_due"])))
            action = current["night"]["action"]
            if action != E.NIGHT_NONE and not E.has_accessory(uid):
                delay = int(current["night"]["after_min"]) * 60
                try:
                    end = E.last_planned_end(session)
                except Exception:
                    end = None
                if end is not None:
                    lines.append(t("eon_night_estimate", time=_hhmm(end + delay), last=_hhmm(end)))
                elif state["idle_since"]:
                    lines.append(t("eon_night_estimate_idle", time=_hhmm(state["idle_since"] + delay)))
            if E.has_accessory(uid):
                ui.label(t("eon_accessory_on")).classes("text-xs text-orange-700 px-2")
                if E.is_closed_by_app(uid):
                    with ui.row().classes("items-center gap-2 px-2"):
                        ui.label(t("eon_accessory_closed")).classes("text-xs text-red-700")
                        ui.button(t("eon_opened_by_hand"),
                                  on_click=lambda: (E.set_closed_by_app(uid, False), estimate.refresh())) \
                            .props("flat dense no-caps size=sm")
            elif E.is_closed_by_app(uid):
                lines.append(t("eon_closed_by_app"))
            for line in lines:
                ui.label(line).classes("text-xs text-primary px-2")

        estimate()

    # The estimate and the saved position follow what happens meanwhile
    ui.timer(30, lambda: (estimate.refresh(), position.refresh()))
