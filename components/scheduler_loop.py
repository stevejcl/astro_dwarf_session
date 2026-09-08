"""Background scheduler loop - the piece that was missing for "programmer
un programme (lancer a l'heure indiquee), valable pour plusieurs
programmes qui s'enchainent": until now, scheduler_runner.start_run()
only ever fired immediately on a user click. This module periodically
checks each ARMED device's ToDo queue for a program whose id_command
date/time has arrived, and starts the earliest-due one via
scheduler_runner.start_run() - mirrors astro_dwarf_scheduler.py's own
check_and_execute_commands() (process one session at a time, oldest due
first; chaining happens naturally because scheduler_runner.is_running()
is True for the device until that run finishes, so the NEXT tick simply
picks up whichever file is next due).

Uses nicegui.app.timer (not ui.timer): app.timer's base Timer class has
no client/page dependency at all (_can_start()/_get_context()/
_should_stop() only check app-level stopping state, never a specific
browser client) - unlike ui.timer, which is a per-client Element that
stops the moment its owning page's client disconnects. A scheduled
astro session firing only while someone happens to have a browser tab
open would defeat the entire point of "programmer a l'avance".

ARMED BY DEFAULT: OFF. A program sitting in ToDo with a future date/
time should not silently start firing on real hardware just because a
file exists - the user explicitly arms the scheduler per device (see
pages/programs.py's toggle) when they're ready for it to run
unattended."""
from __future__ import annotations

import json
import os
from datetime import datetime

from components import scheduler_runner
from components.session_dirs import session_dirs_for

_CHECK_INTERVAL_S = 15.0

_armed: set[str] = set()


def is_armed(dwarf_uid: str) -> bool:
    return dwarf_uid in _armed


def arm(dwarf_uid: str) -> None:
    _armed.add(dwarf_uid)


def disarm(dwarf_uid: str) -> None:
    _armed.discard(dwarf_uid)


def _read_schedule(filepath: str) -> tuple[datetime, dict] | None:
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        id_command = data.get("command", {}).get("id_command", {})
        date_str = id_command.get("date")
        time_str = id_command.get("time")
        if not date_str or not time_str:
            return None
        scheduled = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
    return scheduled, data


def _next_due_file(todo_dir: str) -> str | None:
    """Returns the path of the earliest-scheduled ToDo file whose time
    has already arrived, or None if none are due yet. Files with a
    missing/unparseable date-time are silently skipped (never
    auto-started - matches astro_dwarf_scheduler.py's own
    "Missing date/time" skip-and-continue behaviour) rather than
    treated as an error."""
    if not os.path.isdir(todo_dir):
        return None

    now = datetime.now()
    due: list[tuple[datetime, str]] = []
    for filename in os.listdir(todo_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(todo_dir, filename)
        parsed = _read_schedule(filepath)
        if parsed is None:
            continue
        scheduled, _data = parsed
        if scheduled <= now:
            due.append((scheduled, filepath))

    if not due:
        return None
    due.sort(key=lambda pair: pair[0])
    return due[0][1]


def check_all(manager) -> None:
    """Call this once per tick (see start_background_loop()) for every
    known session. Starts at most ONE new run per device per tick, and
    only for armed devices that aren't already busy - see the module
    docstring for why that's enough to chain multiple due programs
    without any extra logic here."""
    for session in manager.all():
        uid = session.dwarf_uid
        if uid not in _armed:
            continue
        if scheduler_runner.is_running(uid):
            continue

        dirs = session_dirs_for(session)
        filepath = _next_due_file(dirs["TODO_DIR"])
        if filepath is None:
            continue

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        try:
            scheduler_runner.start_run(
                uid, data.get("command", {}), session, source_filepath=filepath
            )
        except RuntimeError:
            # Command slot busy for some unrelated reason (a manual
            # action, a health check) - try again next tick rather than
            # forcing it.
            pass


def start_background_loop(manager) -> None:
    """Call once at app startup (astro_dwarf_ui.py). Uses app.timer, not
    ui.timer - see the module docstring."""
    from nicegui import app

    app.timer(_CHECK_INTERVAL_S, lambda: check_all(manager))
