"""Checks a failed native schedule task against what the Dwarf actually
saved (user-requested Oct 2026: tasks end with "error -1" while the
stack is saved - DwarfLab's analysis - so the error alone doesn't say
whether the night is lost).

Finds the task's session in the Dwarf's album (same listing as the
Explorer page: target name + the task's time window), then reads its
shotsInfo.json (images taken / stacked, exposure). Only on a click: one
album listing and one small JSON over HTTP, never polled."""
from __future__ import annotations

import re

from nicegui import run, ui

from dwarf_python_api.lib.dwarf_utils import perform_list_astro_sessions_http

from components.i18n import t
from pages.explorer import (
    _fetch_shots_info,
    _format_datetime,
    _format_duration,
    _shots_info_url,
    _target_name,
    _thumbnail_url,
)

# The album entry's modificationTime is when the session was last saved:
# within the task's window, or a little after its end (final stack)
_BEFORE_START_S = 10 * 60
_AFTER_END_S = 60 * 60


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _names_match(task_name: str, target: str) -> bool:
    a, b = _norm(task_name), _norm(target)
    return bool(a and b) and (a == b or a in b or b in a)


def find_album_session(entries: list[dict], task: dict) -> tuple[dict | None, bool]:
    """(album entry, name matched) for the task: an entry saved within
    the task's window (with margins), the target name's match first,
    else the closest one in time. (None, False) when none."""
    start, end = task.get("startTime"), task.get("endTime")
    if not start or not end:
        return None, False
    lo, hi = start - _BEFORE_START_S, end + _AFTER_END_S
    in_window = [e for e in entries if lo <= (e.get("modificationTime") or 0) <= hi]
    if not in_window:
        return None, False

    def distance(entry: dict) -> float:
        saved = entry.get("modificationTime") or 0
        return 0 if start <= saved <= end + _AFTER_END_S else abs(saved - start)

    named = [e for e in in_window if _names_match(task.get("name", ""), _target_name(e))]
    if named:
        return min(named, key=distance), True
    return min(in_window, key=distance), False


def verdict(info: dict | None) -> str:
    """"ok" (images stacked), "empty" (none stacked) or "unknown" (no
    shotsInfo.json)."""
    if not info:
        return "unknown"
    try:
        stacked = int(info.get("shotsStacked") or 0)
    except (TypeError, ValueError):
        return "unknown"
    return "ok" if stacked > 0 else "empty"


def _check(session, task: dict) -> dict:
    """Blocking part (HTTP): {"entry", "named", "info"} or {"error"}."""
    entries = perform_list_astro_sessions_http(session=session)
    if entries is False:
        return {"error": True}
    entry, named = find_album_session(entries or [], task)
    info = None
    if entry and entry.get("thumbnailPath"):
        info = _fetch_shots_info(_shots_info_url(session.config.dwarf_ip, entry["thumbnailPath"]))
    return {"entry": entry, "named": named, "info": info}


async def open_task_check(session, task: dict, make_dialog=ui.dialog) -> None:
    """Dialog with what the Dwarf saved for this task. make_dialog: the
    caller's dialog factory (the device page attaches its dialogs to the
    page, see pages/session.py's _page_dialog())."""
    with make_dialog() as dialog, ui.card().classes("w-[min(90vw,480px)]"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(t("task_check_title", name=task.get("name", "?"))).classes("text-base font-medium")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")
        body = ui.column().classes("w-full gap-1")
        with body:
            ui.spinner(size="lg").classes("mx-auto")
    dialog.open()

    result = await run.io_bound(_check, session, task)
    body.clear()
    with body:
        if result.get("error"):
            ui.label(t("task_check_album_error")).classes("text-negative text-sm")
            return
        entry = result["entry"]
        if entry is None:
            ui.label(t("task_check_not_found")).classes("text-negative text-sm")
            return
        info = result["info"]
        state = verdict(info)
        color = {"ok": "text-positive", "empty": "text-negative"}.get(state, "text-grey-7")
        ui.label(t(f"task_check_{state}")).classes(f"text-sm font-medium {color}")
        ui.label(
            f"{_target_name(entry)} · {_format_datetime(entry.get('modificationTime'))}"
        ).classes("text-sm")
        if not result["named"]:
            ui.label(t("task_check_name_differs")).classes("text-xs text-warning")
        if info:
            bits = []
            if info.get("shotsStacked") is not None and info.get("shotsTaken") is not None:
                bits.append(t("task_check_shots", stacked=info["shotsStacked"], taken=info["shotsTaken"]))
            try:
                bits.append(t("task_check_integration",
                              duration=_format_duration(float(info["shotsStacked"]) * float(info["exp"]))))
            except (KeyError, TypeError, ValueError):
                pass
            if bits:
                ui.label(" · ".join(bits)).classes("text-sm text-grey-7")
        if entry.get("thumbnailPath"):
            ui.image(_thumbnail_url(session.config.dwarf_ip, entry["thumbnailPath"])).classes(
                "w-full rounded"
            )
