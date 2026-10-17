"""After a session, and at the end of the night (user-requested Oct 2026).

After a capture the Dwarf stays on its end-of-session screen, still
tracking - handy to shoot the same target again, but it drains the
battery; and powered off while tracking, the D3 / Mini don't close their
lenses (from rest they do - user-tested). Per Dwarf:

- Exit the end-of-session screen N minutes after a capture ended (Go
  Live, and optionally Stop goto - the tracking). A program can override
  it (its id_command["end_session"]).
- End of the night, X minutes after the last capture: close the lenses
  (Pitch motor: motor_action(1) on D3 / Mini, 12 on D2) when the next
  planned activity is far enough, or power the Dwarf off - only when
  nothing at all is planned any more (programs in ToDo, tasks of the
  Dwarf's own schedule, a schedule waiting to be sent): a remote Dwarf
  powered off can't be switched back on.
- The opening position: the Pitch position saved after a successful
  calibration of a program (or by the user). When this app closed the
  lenses, the next program goes back to it first (Pitch reset, then run
  to it); a program can also ask for it (or the polar position) at start.

A capture's end is seen here as the falling edge of "running a program
or capturing" (a program of this app, a capture started from the
Actions, a schedule run by the Dwarf itself while connected), polled by a
client-independent timer (start_background_loop). Delays in progress are
in memory: lost when the app restarts.

Settings in end_of_night.json (working folder, same pattern as
device_prefs.py), one entry per Dwarf UID."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

import dwarf_python_api.lib.my_logger as log
from dwarf_python_api.get_config_data import config_to_dwarf_id_int

SETTINGS_FILE = Path("end_of_night.json")

NIGHT_NONE, NIGHT_CLOSE, NIGHT_POWER_OFF = "none", "close", "power_off"
START_NONE, START_SAVED, START_POLAR = "none", "saved", "polar"
OVERRIDE_DEFAULT, OVERRIDE_ON, OVERRIDE_OFF = "default", "on", "off"

DEFAULTS = {
    "exit": {"enabled": True, "after_min": 5, "stop_tracking": False},
    "night": {"action": NIGHT_NONE, "after_min": 30},
}
# Lenses not closed when the next planned activity starts sooner than this
CLOSE_MARGIN_S = 15 * 60
_TICK_S = 30.0


# ── settings ──────────────────────────────────────────────────────────────
def _read_all() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_all(data: dict) -> None:
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, SETTINGS_FILE)


def _entry(dwarf_uid: str) -> dict:
    return _read_all().get(dwarf_uid, {})


def _update(dwarf_uid: str, **values) -> None:
    data = _read_all()
    entry = data.setdefault(dwarf_uid, {})
    for key, value in values.items():
        if value is None:
            entry.pop(key, None)
        else:
            entry[key] = value
    _write_all(data)


def get_settings(dwarf_uid: str) -> dict:
    """{"exit": {...}, "night": {...}} with the defaults filled in."""
    entry = _entry(dwarf_uid)
    return {key: {**default, **(entry.get(key) or {})} for key, default in DEFAULTS.items()}


def set_settings(dwarf_uid: str, exit_: dict | None = None, night: dict | None = None) -> None:
    current = get_settings(dwarf_uid)
    _update(dwarf_uid,
            exit={**current["exit"], **(exit_ or {})},
            night={**current["night"], **(night or {})})


def exit_settings_for(dwarf_uid: str, override: dict | None) -> dict:
    """The Dwarf's exit settings, with a program's id_command["end_session"]
    ({"mode": default/on/off, "after_min", "stop_tracking"}) over them."""
    base = dict(get_settings(dwarf_uid)["exit"])
    if not isinstance(override, dict):
        return base
    mode = override.get("mode") or OVERRIDE_DEFAULT
    if mode == OVERRIDE_OFF:
        base["enabled"] = False
    elif mode == OVERRIDE_ON:
        base["enabled"] = True
        for key in ("after_min", "stop_tracking"):
            if override.get(key) is not None:
                base[key] = override[key]
    return base


# ── opening position ──────────────────────────────────────────────────────
def open_position(dwarf_uid: str) -> dict | None:
    """{"pitch", "saved_at", "source": "auto"/"manual"} or None."""
    pos = _entry(dwarf_uid).get("open_position")
    return pos if isinstance(pos, dict) and isinstance(pos.get("pitch"), (int, float)) else None


def save_open_position(dwarf_uid: str, pitch: float, source: str, saved_at: str | None = None) -> None:
    _update(dwarf_uid, open_position={
        "pitch": round(float(pitch), 2),
        "saved_at": saved_at or datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": source,
    })
    log.notice(f"[{dwarf_uid}] Opening position saved ({source}): Pitch {pitch:.2f}°")


def clear_open_position(dwarf_uid: str) -> None:
    _update(dwarf_uid, open_position=None)


def is_closed_by_app(dwarf_uid: str) -> bool:
    return bool(_entry(dwarf_uid).get("closed_by_app"))


def set_closed_by_app(dwarf_uid: str, closed: bool) -> None:
    _update(dwarf_uid, closed_by_app=True if closed else None)


# ── Dwarf commands (blocking, the caller holds the command slot) ──────────
def _model(session) -> int:
    return config_to_dwarf_id_int(session.config.dwarf_model_id) or 2


def exit_session_screen(session, stop_tracking: bool) -> bool:
    """Go Live (leaves the end-of-session screen), then Stop goto (the
    tracking) when asked."""
    from dwarf_python_api.lib.dwarf_utils import perform_GoLive, perform_stop_goto

    ok = bool(perform_GoLive(session=session))
    if stop_tracking:
        time.sleep(2)
        ok = bool(perform_stop_goto(session=session)) and ok
    return ok


def close_lenses(session) -> bool:
    """Pitch to the closed position of the model (motor_action 12 on a D2,
    1 on a D3 / Mini - dwarf_python_api 3.1.6)."""
    from dwarf_python_api.lib.dwarf_utils import motor_action

    return bool(motor_action(12 if _model(session) == 2 else 1, session=session))


def read_pitch(session) -> float | None:
    from dwarf_python_api.lib.dwarf_utils import perform_get_motor_position_full

    try:
        return perform_get_motor_position_full(2, session=session)
    except Exception as e:  # never fails a program for this
        log.warning(f"Pitch position not read: {e}")
        return None


def go_to_open_position(session) -> bool:
    """Pitch reset, then to the saved opening position. False when none is
    saved or a command failed."""
    from dwarf_python_api.lib.dwarf_utils import motor_action, perform_motor_run_to_v3

    pos = open_position(session.dwarf_uid)
    if pos is None:
        return False
    if not motor_action(6, session=session):  # Pitch reset
        return False
    return bool(perform_motor_run_to_v3(2, float(pos["pitch"]), speed=10, session=session))


def go_to_start_position(session, mode: str) -> bool:
    """A program's start position: the saved one (the polar position when
    none is saved) or the polar position. Clears closed_by_app on success."""
    from components.actions_section import _polar_position_sequence

    if mode == START_SAVED and open_position(session.dwarf_uid) is not None:
        ok = go_to_open_position(session)
    else:
        ok = bool(_polar_position_sequence(session))
    if ok:
        set_closed_by_app(session.dwarf_uid, False)
    return ok


def start_position_mode(session, program_mode: str | None) -> str:
    """What a program does at start: its own choice, or the saved position
    when this app closed the lenses (a remote Dwarf must not stay closed)."""
    mode = program_mode or START_NONE
    if mode == START_NONE and is_closed_by_app(session.dwarf_uid):
        return START_SAVED
    return mode


# Actions buttons (session as keyword, as actions_section._run_and_notify)
def action_close_lenses(session) -> bool:
    exit_session_screen(session, stop_tracking=True)
    time.sleep(2)
    ok = close_lenses(session)
    if ok:
        set_closed_by_app(session.dwarf_uid, True)
    return ok


def action_go_to_open_position(session) -> bool:
    return go_to_start_position(session, START_SAVED)


def action_save_open_position(session) -> bool:
    pitch = read_pitch(session)
    if pitch is None:
        return False
    save_open_position(session.dwarf_uid, pitch, "manual")
    return True


# ── planned activity ──────────────────────────────────────────────────────
def next_activity(session, now: float | None = None) -> float | None:
    """Epoch start of the next planned activity of this Dwarf: a program in
    ToDo (its date/time), a task of the Dwarf's own schedule (cached), a
    schedule waiting to be sent. None when nothing is planned."""
    import pending_schedules
    from components import native_schedule
    from components.scheduler_loop import _read_schedule, is_armed
    from components.session_dirs import session_dirs_for
    from components.site_time import site_now

    now = now if now is not None else time.time()
    starts: list[float] = []
    todo = session_dirs_for(session)["TODO_DIR"]
    if os.path.isdir(todo):
        site_offset = now - site_now(session.config).timestamp()
        for filename in os.listdir(todo):
            if filename.endswith(".json"):
                parsed = _read_schedule(os.path.join(todo, filename))
                if parsed is None:
                    continue
                # Site wall-clock time -> epoch: the same offset as now
                start = parsed[0].timestamp() + site_offset
                # One already due starts at the next scheduler tick - if
                # the scheduler is on; else it is left over, not planned
                if start > now or is_armed(session.dwarf_uid):
                    starts.append(max(now, start))
    starts += [max(now, task["start"]) for task in native_schedule.upcoming_tasks(session.dwarf_uid, now)]
    pending = pending_schedules.get_pending(session.dwarf_uid)
    if pending and not pending_schedules.is_expired(pending, now):
        start = pending_schedules._epoch_s(pending.get("startTime"))
        if start:
            starts.append(max(now, start))
    return min(starts) if starts else None


def last_planned_end(session, now: float | None = None) -> float | None:
    """Epoch end of the last planned activity (a program's end_time, else
    its start; a native task's end) - for the estimated end of the night."""
    from components import native_schedule
    from components.scheduler_loop import list_upcoming_programs
    from components.site_time import site_now

    now = now if now is not None else time.time()
    ends: list[float] = []
    site_offset = now - site_now(session.config).timestamp()
    for program in list_upcoming_programs(session.dwarf_uid, session):
        if program.get("status") != "todo":
            continue
        value = program.get("endAt") or program.get("scheduledAt")
        try:
            ends.append(datetime.strptime(value, "%Y-%m-%d %H:%M:%S").timestamp() + site_offset)
        except (TypeError, ValueError):
            continue
    ends += [task["end"] for task in native_schedule.upcoming_tasks(session.dwarf_uid, now)]
    future = [e for e in ends if e > now]
    return max(future) if future else None


# ── the loop ──────────────────────────────────────────────────────────────
_was_busy: dict[str, bool] = {}
_idle_since: dict[str, float] = {}
_exit_due: dict[str, tuple[float, bool]] = {}
_night_done: dict[str, float] = {}
_program_end: dict[str, dict] = {}


def program_ended(dwarf_uid: str, id_command: dict, user_stopped: bool) -> None:
    """Called by scheduler_runner at the end of a program run: its override
    of the exit settings for the end edge that follows; nothing done after
    a program the user stopped."""
    _program_end[dwarf_uid] = {"override": id_command.get("end_session"), "user_stopped": user_stopped}


def activity_started(dwarf_uid: str) -> None:
    """Something new runs: the delays in progress are dropped."""
    _exit_due.pop(dwarf_uid, None)
    _idle_since.pop(dwarf_uid, None)


def status(dwarf_uid: str) -> dict:
    """For the Scripts card: {"exit_due", "idle_since"} (epoch or None)."""
    due = _exit_due.get(dwarf_uid)
    return {"exit_due": due[0] if due else None, "idle_since": _idle_since.get(dwarf_uid)}


def _is_busy(session) -> bool:
    from components import scheduler_runner
    from components.scheduler_loop import _is_capturing

    return scheduler_runner.is_running(session.dwarf_uid) or _is_capturing(session)


def _on_end(session, now: float) -> None:
    uid = session.dwarf_uid
    ended = _program_end.pop(uid, None) or {}
    if ended.get("user_stopped"):
        log.info(f"[{uid}] Program stopped by the user: no end-of-session action.")
        return
    _idle_since[uid] = now
    settings = exit_settings_for(uid, ended.get("override"))
    if settings["enabled"]:
        _exit_due[uid] = (now + max(0, int(settings["after_min"])) * 60, bool(settings["stop_tracking"]))
        log.info(f"[{uid}] Capture ended: leaving the end-of-session screen in {settings['after_min']} min.")


async def _with_slot(session, caller: str, fn, *args):
    from nicegui import run
    from components import connection_health

    uid = session.dwarf_uid
    if not connection_health.try_acquire_command_slot(uid, caller=caller):
        return None
    try:
        return await run.io_bound(fn, *args)
    finally:
        connection_health.release_command_slot(uid)


def _night_sequence(session, power_off: bool) -> bool:
    """Blocking: Go Live, Stop goto, lenses closed - then power off."""
    from dwarf_python_api.lib.dwarf_utils import perform_powerdown

    exit_session_screen(session, stop_tracking=True)
    time.sleep(2)
    closed = close_lenses(session)
    if closed:
        set_closed_by_app(session.dwarf_uid, True)
    if not power_off:
        return closed
    if not closed:
        log.warning(f"[{session.dwarf_uid}] Lenses not closed - not powering off.")
        return False
    time.sleep(15)  # the lenses closing
    return perform_powerdown(session=session) is True


async def power_off_cleanup(session) -> None:
    """After a power off sent: the connection closed, no auto-reconnect
    (same as pages/session.py's Power off)."""
    from nicegui import run
    from dwarf_python_api.lib.dwarf_utils import perform_disconnect
    from dwarf_python_api.lib.my_logger import unregister_thread_device_label
    from components import connection_health, device_lock

    uid = session.dwarf_uid
    thread = getattr(session, "event_loop_thread", None)
    try:
        await run.io_bound(perform_disconnect, session=session)
    except Exception:
        pass
    if thread is not None:
        unregister_thread_device_label(thread.ident)
    connection_health.forget(uid)
    device_lock.release(uid)
    connection_health.mark_manual_disconnect(uid)


async def tick(manager) -> None:
    now = time.time()
    for session in manager.all():
        uid = session.dwarf_uid
        if not session.is_connected:
            _was_busy.pop(uid, None)
            continue
        busy = _is_busy(session)
        if busy:
            if not _was_busy.get(uid):
                activity_started(uid)
            _was_busy[uid] = True
            continue
        if _was_busy.get(uid):
            _on_end(session, now)
        _was_busy[uid] = False

        from components import connection_health
        if connection_health.is_busy(uid):
            continue

        due = _exit_due.get(uid)
        if due is not None and now >= due[0]:
            ok = await _with_slot(session, "end_of_night.exit", exit_session_screen, session, due[1])
            if ok is not None:
                _exit_due.pop(uid, None)
                log.notice(f"[{uid}] End-of-session screen left{' and tracking stopped' if due[1] else ''}: {ok}")
            continue

        idle_since = _idle_since.get(uid)
        night = get_settings(uid)["night"]
        if (idle_since is None or night["action"] == NIGHT_NONE or _night_done.get(uid) == idle_since
                or now < idle_since + max(0, int(night["after_min"])) * 60):
            continue
        upcoming = next_activity(session, now)
        if night["action"] == NIGHT_POWER_OFF and upcoming is None:
            power_off = True
        elif upcoming is None or upcoming - now > CLOSE_MARGIN_S:
            power_off = False  # something planned later: lenses closed only
        else:
            continue  # the next activity is near: left as it is
        if is_closed_by_app(uid) and not power_off:
            _night_done[uid] = idle_since
            continue
        log.notice(f"[{uid}] End of the night: {'power off' if power_off else 'closing the lenses'}.")
        ok = await _with_slot(session, "end_of_night.night", _night_sequence, session, power_off)
        if ok is None:
            continue  # slot busy: next tick
        _night_done[uid] = idle_since
        _exit_due.pop(uid, None)
        if ok and power_off:
            await power_off_cleanup(session)
        log.notice(f"[{uid}] End of the night done: {ok}")


def start_background_loop(manager) -> None:
    """Call once at app startup (astro_dwarf_ui.py) - app.timer, alive
    without any page open."""
    from nicegui import app

    app.timer(_TICK_S, lambda: tick(manager))
