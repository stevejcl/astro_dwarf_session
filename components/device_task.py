"""A task the Dwarf runs on its own - a megastack, whoever started it (the
official app too, closed since): the Dwarf can do nothing else meanwhile
(user-seen Oct 2026: no session could start).

Known from the Dwarf's CMD_NOTIFY_EXCLUSIVE_SYSTEM_IO_TASK_STATE, sent with
each device state answer (connection_health's check, every ~15 s):
dwarf_python_api keeps the task last seen running (active_task_id) until
the Dwarf reports it over. Programs don't start meanwhile (scheduler_runner,
scheduler_loop), the end of the night does nothing (end_of_night), and the
device card shows it with its progress (device_card)."""
from __future__ import annotations

import time

from nicegui import background_tasks, run

# Its state is refreshed every ~15 s: older means not heard of since (the
# connection's check paused) - not trusted
_FRESH_S = 5 * 60
# The progress (the result's shotsInfo.json) read at most this often
_PROGRESS_EVERY_S = 30

_progress: dict[str, dict] = {}  # uid -> {"at", "counts": (stacked, processed, total) | None}


def running_task(session) -> dict | None:
    """{"name": TASK_ID_..., "megastack": bool, "result_dir": str | None} of
    the task the Dwarf runs now, else None."""
    client = getattr(session, "client_instance", None)
    task_id = getattr(client, "active_task_id", None) if client else None
    if task_id is None:
        return None
    entry = (getattr(client, "task_states", None) or {}).get(task_id)
    if not entry or time.time() - entry.get("updated", 0) > _FRESH_S:
        return None
    import dwarf_python_api.proto.task_center_pb2 as task_center

    return {
        "name": task_center.TaskId.Name(task_id),
        "megastack": task_id == task_center.TASK_ID_ASTRO_MULTI_STACK,
        "result_dir": entry.get("result_dir"),
    }


def busy_reason(session) -> str:
    """Why nothing can start on the Dwarf now ("" when nothing runs)."""
    task = running_task(session)
    if task is None:
        return ""
    return "the Dwarf is busy: a megastack is running" if task["megastack"] else f"the Dwarf is busy: {task['name']}"


def progress(session) -> tuple[int, int, int] | None:
    """(stacked, processed, to stack) of the running megastack, read from
    its result's shotsInfo.json - in the background, at most every 30 s
    (the last value meanwhile)."""
    task = running_task(session)
    if task is None or not task["result_dir"]:
        return None
    uid = session.dwarf_uid
    cached = _progress.get(uid) or {}
    if time.time() - cached.get("at", 0) >= _PROGRESS_EVERY_S:
        _progress[uid] = {**cached, "at": time.time()}
        background_tasks.create(_read_progress(session, task["result_dir"]), name=f"device-task-progress-{uid}")
    return cached.get("counts")


async def _read_progress(session, result_dir: str) -> None:
    from components import megastack

    counts = await run.io_bound(megastack._progress, session, result_dir)
    if counts is not None:
        _progress[session.dwarf_uid] = {"at": time.time(), "counts": counts}
    # Its stack's last complete image too (megastack.refresh_preview)
    await run.io_bound(megastack.refresh_preview, session, result_dir, counts[1] if counts else None)


def _own_megastack(session):
    """This app's running megastack program (its RunState), else None."""
    from components import megastack, scheduler_runner

    state = scheduler_runner.get_run_state(session.dwarf_uid)
    if state is None or not state.running or not state.program:
        return None
    # RunState.program: the command part, or a whole program file's dict
    return state if megastack.megastack_section(state.program.get("command", state.program)) else None


def megastack_running(session) -> bool:
    """A megastack runs on the Dwarf: this app's, or one for another app."""
    task = running_task(session)
    return _own_megastack(session) is not None or bool(task and task["megastack"])


def megastack_counts(session) -> tuple[int, int, int] | None:
    """(stacked, processed, to stack) of the megastack the Dwarf runs now:
    this app's run (its RunState, components/megastack.py), else one it
    runs for another app (progress()). None when none runs or nothing read
    yet."""
    state = _own_megastack(session)
    if state is not None:
        if not state.shots_taken:
            return None
        try:
            total = int(state.requested_count_tele or 0)
        except ValueError:
            total = 0
        return state.shots_stacked or 0, state.shots_taken, total
    task = running_task(session)
    return progress(session) if task and task["megastack"] else None


def megastack_progress_text(counts: tuple[int, int, int]) -> str:
    """"Megastack in progress · 12/409 · 12 stacked" - a capture's own
    progress line (capture_progress_with_total), for every screen: the
    home screen card, the device page's program, the watch page."""
    from components.i18n import t

    stacked, processed, total = counts
    return t("megastack_progress", processed=processed, total=total, stacked=stacked)


def megastack_preview_url(session) -> str:
    """The running megastack's stack thumbnail on the Dwarf, its progress as
    the cache key ("" when none runs): this app's run (RunState, components/
    megastack.py), else one the Dwarf runs for another app. Shown instead of
    the Tele preview (nothing to see there meanwhile): the home screen card,
    the Tele frame of the device and watch pages."""
    from components import megastack, scheduler_runner

    state = scheduler_runner.get_run_state(session.dwarf_uid)
    if state is not None and state.running and state.preview_url:
        return f"{state.preview_url}?v={state.preview_version}"
    task = running_task(session)
    if task and task["megastack"] and task["result_dir"]:
        progress(session)  # reads the progress and the image, every 30 s
        url = megastack.preview_url(session)
        return f"{url}?v={megastack.preview_version(session.dwarf_uid)}" if url else ""
    return ""
