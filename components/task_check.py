"""Checks a failed native schedule task against what the Dwarf actually
saved (user-requested Oct 2026: tasks end with "error -1" while the
stack is saved - DwarfLab's analysis - so the error alone doesn't say
whether the night is lost).

Finds the task's session in the Dwarf's album (same listing as the
Explorer page: target name + the task's time window), then reads its
shotsInfo.json (images taken / stacked, exposure). Only on a click: one
album listing and one small JSON over HTTP, never polled.

Also for this app's own programs (user-requested Oct 2026): the target
is the program's goto, the window its real start / end (program_task()).
Used by the device page, the Programs page's Results tab (NiceGUI
dialog) and the Program HTML page (/api/task-check, api_routes.py)."""
from __future__ import annotations

import re
from datetime import datetime

from nicegui import run, ui

from dwarf_python_api.lib.dwarf_utils import perform_list_astro_sessions_http

from components.current_activity import program_target
from components.i18n import t
from components.site_time import site_tz
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


# A program whose end wasn't recorded: its session can't be later than this
_PROGRAM_DEFAULT_SPAN_S = 15 * 3600


def _site_epoch(value: str | None, config) -> int | None:
    """Epoch seconds of a "YYYY-MM-DD HH:MM:SS" site time (a program's
    starting_date / processed_date)."""
    if not value:
        return None
    try:
        naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return int(naive.replace(tzinfo=site_tz(config)).timestamp())


def program_task(program: dict, config) -> dict | None:
    """{"name", "startTime", "endTime"} for a program that ran (its file's
    dict or "command" part), like a native task; None when it never
    started. name: the goto target, else the description."""
    cmd = program.get("command", program)
    id_command = cmd.get("id_command", {})
    start = _site_epoch(id_command.get("starting_date"), config)
    if start is None:
        return None
    end = _site_epoch(id_command.get("processed_date"), config)
    return {
        "name": program_target(cmd),
        "startTime": start,
        "endTime": end if end and end >= start else start + _PROGRAM_DEFAULT_SPAN_S,
    }


def summarize(session, task: dict) -> dict:
    """What the Dwarf saved for a task (blocking, HTTP): {"status":
    "album_error" | "not_found" | "ok" | "empty" | "unknown", and when
    found "target", "date", "nameMatched", "stacked", "taken",
    "integration", "thumbnailPath"}."""
    entries = perform_list_astro_sessions_http(session=session)
    if entries is False:
        return {"status": "album_error"}
    entry, named = find_album_session(entries or [], task)
    if entry is None:
        return {"status": "not_found"}
    info = None
    if entry.get("thumbnailPath"):
        info = _fetch_shots_info(_shots_info_url(session.config.dwarf_ip, entry["thumbnailPath"]))
    out = {
        "status": verdict(info),
        "target": _target_name(entry),
        "date": _format_datetime(entry.get("modificationTime")),
        "nameMatched": named,
        "stacked": None,
        "taken": None,
        "integration": None,
        "thumbnailPath": entry.get("thumbnailPath"),
    }
    if info:
        out["stacked"], out["taken"] = info.get("shotsStacked"), info.get("shotsTaken")
        try:
            out["integration"] = _format_duration(float(info["shotsStacked"]) * float(info["exp"]))
        except (KeyError, TypeError, ValueError):
            pass
    return out


async def open_task_check(session, task: dict, make_dialog=ui.dialog) -> None:
    """Dialog with what the Dwarf saved for this task. make_dialog: the
    caller's dialog factory (the device page attaches its dialogs to the
    page, see pages/session.py's _page_dialog())."""
    with make_dialog() as dialog, ui.card().classes("w-[min(90vw,480px)]"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(t("task_check_title", name=task.get("name") or "?")).classes("text-base font-medium")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")
        body = ui.column().classes("w-full gap-1")
        with body:
            ui.spinner(size="lg").classes("mx-auto")
    dialog.open()

    result = await run.io_bound(summarize, session, task)
    body.clear()
    with body:
        status = result["status"]
        if status in ("album_error", "not_found"):
            key = "task_check_album_error" if status == "album_error" else "task_check_not_found"
            ui.label(t(key)).classes("text-negative text-sm")
            return
        color = {"ok": "text-positive", "empty": "text-negative"}.get(status, "text-grey-7")
        ui.label(t(f"task_check_{status}")).classes(f"text-sm font-medium {color}")
        ui.label(f"{result['target']} \u00b7 {result['date']}").classes("text-sm")
        if not result["nameMatched"]:
            ui.label(t("task_check_name_differs")).classes("text-xs text-warning")
        bits = []
        if result["stacked"] is not None and result["taken"] is not None:
            bits.append(t("task_check_shots", stacked=result["stacked"], taken=result["taken"]))
        if result["integration"]:
            bits.append(t("task_check_integration", duration=result["integration"]))
        if bits:
            ui.label(" \u00b7 ".join(bits)).classes("text-sm text-grey-7")
        if result["thumbnailPath"]:
            ui.image(_thumbnail_url(session.config.dwarf_ip, result["thumbnailPath"])).classes(
                "w-full rounded"
            )
