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
from datetime import datetime, timedelta

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


_LOCAL_PROGRAM_DIRS = (("todo", "TODO_DIR"), ("done", "DONE_DIR"), ("error", "ERROR_DIR"))


def _extract_capture_summary(cmd: dict, id_command: dict) -> dict:
    """Camera/exposure/gain/filter/shot-count summary for the combined
    /Program page's Detail column (user-requested Sep 2026: "capteur
    Tele/Wide, Expo/Gain/Filtre et nb de stacked, nb shots sur nombre
    total demandé"). Prefers the ACTUAL values a finished run recorded
    (id_command's own exposure_actual/gain_actual/ir_actual/shots_taken/
    shots_stacked - see scheduler_runner.py's _capture_actual_camera_
    settings()/_capture_shots_result(), already human-readable strings,
    no index-to-name lookup needed) over the originally PLANNED setup_
    camera/setup_wide_camera values, for a ToDo/ program that hasn't
    run yet. cameraType/requestedCount always come from whichever setup
    dict has do_action=True - that never changes once the program was
    saved, run or not. filterName is only ever the ACTUAL one (Tele
    only, Wide has no filter) - the planned one is stored as a numeric
    ircut index needing a dwarf-type-specific name lookup this function
    deliberately doesn't do, matching the request's own "si présent"."""
    camera_type = None
    requested_count = None
    for cam_key, label in (("setup_camera", "Tele"), ("setup_wide_camera", "Wide")):
        setup = cmd.get(cam_key) or {}
        if setup.get("do_action"):
            camera_type = label
            requested_count = setup.get("count")
            break
    return {
        "cameraType": camera_type,
        "requestedCount": requested_count,
        "exposure": id_command.get("exposure_actual"),
        "gain": id_command.get("gain_actual"),
        "filterName": id_command.get("ir_actual"),
        "shotsTaken": id_command.get("shots_taken"),
        "shotsStacked": id_command.get("shots_stacked"),
    }


def _extract_end_time(cmd: dict, scheduled: datetime) -> str | None:
    """Combines a program's own "end_time" field (program_editor.py's
    optional "HH:MM", 24h, under whichever of setup_camera/setup_wide_
    camera is do_action=True) with its scheduled START date/time, to get
    a full end date/time for display (user-requested Sep 2026: "on n'a
    pas l'heure de fin sur nos programmes ?" - the combined /Program
    page was only ever showing "-" for a local program's end column).

    Rolls to the NEXT day if the naive "same calendar day as start"
    combination would fall at or before the start time - mirrors
    dwarf_session.py's own _parse_end_time() midnight-rollover handling
    (a session started at 22:00 with end_time="01:30" means 01:30 the
    FOLLOWING day) - just anchored to the program's own scheduled start
    rather than "right now", since this runs long before the program
    ever starts (unlike _parse_end_time(), only ever called once a
    session is already live)."""
    for key in ("setup_camera", "setup_wide_camera"):
        setup = cmd.get(key) or {}
        if not setup.get("do_action"):
            continue
        raw = setup.get("end_time")
        if not raw:
            return None
        try:
            hour, minute = str(raw).strip().split(":")
            candidate = scheduled.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        except (ValueError, AttributeError):
            return None
        if candidate <= scheduled:
            candidate += timedelta(days=1)
        return candidate.strftime("%Y-%m-%d %H:%M:%S")
    return None


def list_upcoming_programs(dwarf_uid: str, session) -> list[dict]:
    """Every local program for this device - ToDo/ (due or not yet),
    PLUS already-finished ones from Done/ and Error/ - for the combined
    "everything scheduled" view (api_routes.py's /api/programs, user-
    requested Sep 2026). Originally ToDo/-only; extended (still Sep
    2026) after the user noticed past programs (done or failed) were
    missing entirely from the combined page - the page's own Tous/
    Futur filter already handles hiding these by default, so this
    function's job is simply to expose the full local history, not to
    decide what's shown. Sorted earliest first; each entry carries its
    own "status" (todo/done/error) so the page can tag it."""
    dirs = session_dirs_for(session)
    out = []
    for status, dir_key in _LOCAL_PROGRAM_DIRS:
        folder = dirs[dir_key]
        if not os.path.isdir(folder):
            continue
        for filename in os.listdir(folder):
            if not filename.endswith(".json"):
                continue
            parsed = _read_schedule(os.path.join(folder, filename))
            if parsed is None:
                continue
            scheduled, data = parsed
            cmd = data.get("command", {})
            id_command = cmd.get("id_command", {})
            entry = {
                "filename": filename,
                "description": id_command.get("description") or "",
                "scheduledAt": scheduled.strftime("%Y-%m-%d %H:%M:%S"),
                "endAt": _extract_end_time(cmd, scheduled),
                "due": status == "todo" and scheduled <= datetime.now(),
                "status": status,
                # ACTUAL run timing (user-requested Sep 2026), distinct
                # from the scheduled date/time and the optional end_time
                # above - set by scheduler_runner.py's own
                # _update_process_status(): "realStart" is stamped the
                # moment execution actually begins (process -> pending),
                # "realEnd" the moment it finishes either way, success or
                # failure (process -> done; the real outcome is in
                # "status"/result, not this timestamp). Both are None for
                # a ToDo/ program that hasn't run yet.
                "realStart": id_command.get("starting_date"),
                "realEnd": id_command.get("processed_date"),
            }
            entry.update(_extract_capture_summary(cmd, id_command))
            out.append(entry)
    out.sort(key=lambda p: p["scheduledAt"])
    return out


def start_background_loop(manager) -> None:
    """Call once at app startup (astro_dwarf_ui.py). Uses app.timer, not
    ui.timer - see the module docstring."""
    from nicegui import app

    app.timer(_CHECK_INTERVAL_S, lambda: check_all(manager))
