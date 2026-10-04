"""What a device is working on right now, for the dashboard card and the
watch page (user-requested Oct 2026: the current target was only shown in
the program's details, and a native shooting schedule running on the
Dwarf wasn't shown at all).

Two sources:
  - a program run by this app (scheduler_runner's RunState): its target
    comes from the program's goto (manual or solar system);
  - a native shooting schedule run by the Dwarf itself: the task comes
    from the last schedule list read from the device (native_schedule's
    cache) - the task flagged "shooting", else the task whose time window
    contains now.

Read-only: nothing here sends a command (used by the watch page). The
schedule list is read from the device by scheduler_loop.
refresh_schedule_on_capture(), once when a capture starts that no program
of this app explains - never polled, a capture may be running."""
from __future__ import annotations

import time
from datetime import datetime

from components import native_schedule, scheduler_runner
from components.native_schedule import schedule_tz

# Schedule states that can no longer run (completed, expired)
_SCHEDULE_DONE_STATES = {3, 4}
# Task states already over (success, failed, interrupted)
_TASK_DONE_STATES = {2, 3, 4}
_TASK_SHOOTING = 1

def _epoch_s(value) -> int | None:
    """Epoch seconds from seconds or milliseconds."""
    if not value:
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value // 1000 if value > 10_000_000_000 else value


def program_target(program: dict | None) -> str:
    """Target of an app program: the goto target, else its description."""
    if not program:
        return ""
    cmd = program.get("command", {})
    goto_manual = cmd.get("goto_manual", {})
    goto_solar = cmd.get("goto_solar", {})
    if goto_manual.get("do_action") and goto_manual.get("target"):
        return str(goto_manual["target"])
    if goto_solar.get("do_action") and goto_solar.get("target"):
        return str(goto_solar["target"])
    return str(cmd.get("id_command", {}).get("description") or "")


def current_schedule_task(dwarf_uid: str, now: float | None = None) -> dict | None:
    """The native schedule task running now according to the cache, or
    None: {"schedule", "task", "index", "total", "start", "end"} (start/end
    in epoch seconds, None when unknown)."""
    now = now if now is not None else time.time()
    best = None
    for sched in native_schedule.get_cached(dwarf_uid) or []:
        if sched.get("state_code") in _SCHEDULE_DONE_STATES:
            continue
        tasks = sched.get("tasks") or []
        for index, task in enumerate(tasks):
            start, end = _epoch_s(task.get("startTime")), _epoch_s(task.get("endTime"))
            shooting = task.get("state_code") == _TASK_SHOOTING
            in_window = (
                start is not None and end is not None and start <= now < end
                and task.get("state_code") not in _TASK_DONE_STATES
            )
            if not (shooting or in_window):
                continue
            found = {
                "schedule": sched.get("name") or "",
                "task": task.get("name") or "",
                "index": index + 1,
                "total": len(tasks),
                "start": start,
                "end": end,
            }
            # The device's own "shooting" flag wins over a time match
            if shooting:
                return found
            best = best or found
    return best


def current_activity(session) -> dict | None:
    """{"source": "program"|"schedule", "title", "target", "start", "end"}
    for what the device is doing now, or None. title is the program or
    schedule name; target the program's target or the schedule task."""
    uid = session.dwarf_uid
    if scheduler_runner.is_running(uid):
        run_state = scheduler_runner.get_run_state(uid)
        return {
            "source": "program",
            "title": run_state.program_name if run_state else "",
            "target": program_target(run_state.program if run_state else None),
            "start": None,
            "end": None,
        }
    task = current_schedule_task(uid)
    if task:
        return {
            "source": "schedule",
            "title": task["schedule"],
            "target": task["task"],
            "index": task["index"],
            "total": task["total"],
            "start": task["start"],
            "end": task["end"],
        }
    return None


def format_window(session, start: int | None, end: int | None) -> str:
    """"21:05-22:30" in the device's timezone (the one schedules use)."""
    if not start or not end:
        return ""
    tz = schedule_tz(session.config)
    fmt = lambda ts: datetime.fromtimestamp(ts, tz).strftime("%H:%M")
    return f"{fmt(start)}–{fmt(end)}"
