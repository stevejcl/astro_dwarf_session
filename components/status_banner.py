"""Reusable status/error banner shared across pages (dashboard, session,
multi-session...). Covers the 4 states sketched in the mockups: info
(action in progress), success, warning, danger (blocking error).

The message/detail strings passed in are already translated by the
caller via components.i18n.t() - this component only picks icon/color
per `kind`, it has no user-facing strings of its own."""
from __future__ import annotations

from nicegui import ui

_ICONS = {
    "info": "play_arrow",
    "success": "check_circle",
    "warning": "warning",
    "danger": "error",
}

_CLASSES = {
    "info": "bg-blue-50 text-blue-800",
    "success": "bg-green-50 text-green-800",
    "warning": "bg-amber-50 text-amber-800",
    "danger": "bg-red-50 text-red-800",
}


def status_banner(message: str, kind: str = "info", *, detail: str | None = None) -> ui.row:
    """kind: 'info' | 'success' | 'warning' | 'danger'.
    `detail` is an optional second, smaller line (e.g. a sub-step or
    error code). Both `message` and `detail` are expected to already be
    translated strings."""
    icon = _ICONS.get(kind, _ICONS["info"])
    classes = _CLASSES.get(kind, _CLASSES["info"])

    with ui.row().classes(f"items-center gap-2 rounded-lg px-3 py-2 w-full {classes}") as row:
        ui.icon(icon).classes("text-lg")
        with ui.column().classes("gap-0"):
            ui.label(message).classes("text-sm font-medium")
            if detail:
                ui.label(detail).classes("text-xs opacity-80")
    return row
