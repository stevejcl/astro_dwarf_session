"""Runs an astro_dwarf_session "program" (dwarf_session.start_dwarf_session())
for a given DwarfSession, exposing live, thread-safe progress state for a
NiceGUI page to poll and display.

Deliberately does NOT pre-compute an expected step list: start_dwarf_
session()'s internal branching (auto_focus vs infinite_focus, calibration's
five sub-steps, goto_solar vs goto_manual, wait-for-completion steps...) is
non-trivial, and some step keys (e.g. "step_1a") are reused for more than
one distinct action within a single run. Mirroring that branching here to
predict the steps ahead of time would be a second copy of that logic,
liable to silently drift out of sync with the real one whenever dwarf_
session.py changes. Instead, this appends each step to a live log AS it
actually happens, in real execution order - a strictly more honest source
of truth, and this module never needs updating when the step sequence in
dwarf_session.py changes.

Threading note: start_dwarf_session() is synchronous and can run for
HOURS (a real astro capture session). It runs via run.io_bound() wrapped
in a detached background task (nicegui.background_tasks.create) rather
than awaited directly - the caller must not block waiting for it. The
progress_callback it invokes therefore runs on a WORKER THREAD, not the
UI's event loop: it only mutates this module's plain, thread-safe state
objects, never touches a NiceGUI element directly. The UI polls that
state via its own ui.timer instead (same pattern as connection_health.py
and every other background operation in this app).

NAMING NOTE: `dwarf_session.py` here is astro_dwarf_session's own
top-level scheduler/session-orchestration module (start_dwarf_session(),
STEP_DESCRIPTIONS) - NOT dwarf_python_api.lib.dwarf_session (the
DwarfSession/DwarfManager registry classes used everywhere else in this
UI). Same base name, two unrelated modules in two different packages -
easy to mix up when skimming imports.

COMMAND SLOT: start_dwarf_session() sends MANY individual commands
internally over the course of a run (goto, calibration, camera setup,
capture, wait-for-completion...), all on the same session.client_
instance - but none of that internal traffic goes through connection_
health.py's try_acquire_command_slot(). Without holding that slot for
the WHOLE run, connection_health's periodic active check (or its own
auto-reconnect, or a user clicking a manual action on the session page)
could send a GET_DEVICE_STATE_INFO - or worse - concurrently with a
step the program is mid-way through, hitting the exact
client_instance.command race documented in connection_health.py's
CONCURRENCY NOTE. start_run() therefore claims the slot up front and
holds it for the run's entire duration (released in _run_blocking()'s
finally, whether the run succeeds, fails, or is stopped) - this also
means connection_health's health check and any manual action correctly
back off / report "device busy" while a program is running, which is
the right behaviour anyway, not just a side effect.

FILE LIFECYCLE (ToDo/Current/Done/Error): astro_dwarf_scheduler.py's own
check_and_execute_commands() is what normally moves a session's JSON
file between these folders and updates its id_command bookkeeping
(process/result/message/starting_date/processed_date/dwarf/
exposure_actual/gain_actual/ir_actual) as it runs it - but THAT function
is never called here; this module calls start_dwarf_session() directly
instead. Without replicating that bookkeeping, a program run from this
UI would execute correctly but its file would just sit in ToDo forever,
and pages/programs.py's Results tab (which only scans Done/Error) would
never see it. _update_process_status()/_move_to_current()/
_finalize_to_done()/_finalize_to_error() below port that exact logic
field-for-field from astro_dwarf_scheduler.py, rather than inventing a
new bookkeeping scheme - a file produced by either path looks the same.

MAX_RETRIES (user-found bug, Sep 2026): the program's own
id_command.max_retries field was silently unused everywhere - astro_
dwarf_scheduler.py HAS a retry_procedure() that reads it and re-runs a
failed session up to that many times, but that function is never
actually called anywhere in that file either (start_dwarf_session() is
called directly, bypassing it) - confirmed dead code in the upstream
project, not something broken by this port. Implemented properly here
instead: _run_blocking() below wraps start_dwarf_session() in its own
retry loop reading max_retries directly, since this module never went
through astro_dwarf_scheduler.py's orchestration anyway."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from nicegui import background_tasks, run

import dwarf_session as astro_dwarf_session
from dwarf_session import STEP_DESCRIPTIONS

from dwarf_python_api.get_config_data import config_to_dwarf_id_str
from dwarf_python_api.lib.dwarf_session_socket import get_client_status
from dwarf_python_api.lib.dwarf_utils import perform_read_camera_params_http_v3

from components import connection_health
from components.session_dirs import session_dirs_for


@dataclass
class StepEvent:
    key: str
    label: str
    status: str  # "success" | "failed"
    seq: int


@dataclass
class RunState:
    running: bool = True
    stop_event: threading.Event = field(default_factory=threading.Event)
    steps: list[StepEvent] = field(default_factory=list)
    error: str | None = None
    finished_ok: bool | None = None  # None while running, True/False once done
    program_name: str = ""  # user-requested (Sep 2026): shown by program_section.py's
    # simplified "running" view regardless of HOW the run was started (a
    # direct upload here, or a relaunch from pages/programs.py's Scripts/
    # Results tabs) - populated once in start_run() from the program's
    # own id_command.description, not tracked separately by each caller.


# One RunState per dwarf_uid - a given device can only run one program at
# a time (mirrors astro_dwarf_scheduler.py's own one-session-at-a-time
# model). Kept even after completion so the final step log/result stays
# visible until the user starts a new run or navigates away.
_runs: dict[str, RunState] = {}


def _update_process_status(program: dict, status: str, *, result: bool | None = None, message: str | None = None) -> None:
    """Field-for-field port of astro_dwarf_scheduler.py's own
    update_process_status() - same semantics, including the fact that
    passing status="done" always sets id_command['process']="done"
    regardless of whether the run actually succeeded (the real outcome
    lives in 'result'/'message', not 'process') - that's the existing
    convention, not something introduced here."""
    command = program["command"]["id_command"]
    command["process"] = status
    if result is not None:
        command["result"] = result
    if message:
        command["message"] = message
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status == "pending":
        command["starting_date"] = now
    if status == "done":
        command["processed_date"] = now


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _capture_actual_camera_settings(id_command: dict, session) -> None:
    """Best-effort, mirrors astro_dwarf_scheduler.py's own try/except
    around this HTTP read - it may simply be unavailable, not worth
    failing an otherwise-successful run over."""
    try:
        camera_settings = perform_read_camera_params_http_v3(mode_id=2, session=session)
        tele_cam = (
            camera_settings.get("cameras", {}).get(0)
            if isinstance(camera_settings, dict)
            else None
        )
        if tele_cam:
            ir_cut_value = tele_cam.get("filterType")
            if ir_cut_value is not None:
                ir_mapping = {0: "Vis", 1: "Astro Filter", 2: "DUAL Band"}
                id_command["ir_actual"] = ir_mapping.get(ir_cut_value, f"Unknown({ir_cut_value})")
            exposure_info = tele_cam.get("exposure") or {}
            gain_info = tele_cam.get("gain") or {}
            id_command["exposure_actual"] = exposure_info.get("name")
            id_command["gain_actual"] = gain_info.get("value")
    except Exception:
        pass


def _capture_eq_solving_result(id_command: dict, session) -> None:
    """User-requested Sep 2026: "ajouter une trace visible si l'eq est
    demande" in the final program JSON, alongside ir_actual/exposure_
    actual/gain_actual - azi_err/alt_err are cached on the client
    (websockets_utils.py) after start_polar_align()'s own response,
    read here the same "best-effort, after a successful run" way as
    _capture_actual_camera_settings() above. Only written when EQ
    Solving actually ran during this session - the cache being
    populated at all (None otherwise) already implies that, without
    needing a separate "was eq_solving requested" check here."""
    try:
        full_status = get_client_status(session).get("fullStatus", {})
        azi_err = full_status.get("eqAziErr")
        alt_err = full_status.get("eqAltErr")
        if azi_err is not None and alt_err is not None:
            id_command["eq_azimut_error"] = f"{azi_err:.4f}"
            id_command["eq_altitude_error"] = f"{alt_err:.4f}"
    except Exception:
        pass


def _set_dwarf_field(id_command: dict, session) -> None:
    dwarf_model_id = getattr(session.config, "dwarf_model_id", None)
    if dwarf_model_id:
        id_command["dwarf"] = f"D{config_to_dwarf_id_str(dwarf_model_id)}"
    else:
        id_command["dwarf"] = "Unknown"


def get_run_state(dwarf_uid: str) -> RunState | None:
    return _runs.get(dwarf_uid)


def is_running(dwarf_uid: str) -> bool:
    state = _runs.get(dwarf_uid)
    return bool(state and state.running)


def _run_blocking(
    program: dict, session, state: RunState, source_filepath: str | None
) -> None:
    """Executed on a run.io_bound() worker thread - see module docstring
    for why this must not touch any NiceGUI element directly. Holds the
    command slot for the whole run - see the COMMAND SLOT note above.

    source_filepath: the ToDo file this program came from, if any (None
    for a run started without a backing file, e.g. a quick upload-and-
    run with no intent to track it in Scripts/Results). When given, this
    reproduces astro_dwarf_scheduler.py's own ToDo -> Current -> Done/
    Error file lifecycle - see the module docstring's FILE LIFECYCLE
    note for why that can't just be skipped."""
    full_program = {"command": program}
    id_command = program.setdefault("id_command", {})
    current_path = None

    if source_filepath is not None:
        dirs = session_dirs_for(session)
        filename = os.path.basename(source_filepath)
        current_path = os.path.join(dirs["CURRENT_DIR"], filename)
        os.makedirs(dirs["CURRENT_DIR"], exist_ok=True)
        try:
            os.replace(source_filepath, current_path)
        except OSError:
            # Already moved (e.g. a previous crash left it in Current) -
            # proceed treating current_path as the working copy either way.
            pass

        id_command["process"] = "running"
        id_command["result"] = False
        id_command["message"] = "Session started"
        _update_process_status(full_program, "pending")
        id_command["time"] = datetime.now().strftime("%H:%M:%S")
        _write_json(current_path, full_program)

    seq = 0

    def on_progress(step_key: str, status: str) -> None:
        nonlocal seq
        seq += 1
        label = STEP_DESCRIPTIONS.get(step_key, step_key)
        state.steps.append(StepEvent(key=step_key, label=label, status=status, seq=seq))

    # MAX_RETRIES: see module docstring - astro_dwarf_scheduler.py's own
    # retry_procedure() would do this, but it's never actually called
    # there either (confirmed dead code upstream). Clamped to [1, 10] -
    # matches the editor's own spinbox range, defends against an
    # absurd hand-edited value hammering the device.
    try:
        max_retries = int(id_command.get("max_retries", 3) or 3)
    except (TypeError, ValueError):
        max_retries = 3
    max_retries = max(1, min(10, max_retries))

    succeeded = False
    last_exception: Exception | None = None
    attempt = 0

    while attempt < max_retries:
        if state.stop_event.is_set():
            last_exception = RuntimeError("Session interrupted by user.")
            break
        attempt += 1
        try:
            astro_dwarf_session.start_dwarf_session(
                program, stop_event=state.stop_event, session=session, progress_callback=on_progress
            )
            succeeded = True
            break
        except Exception as e:  # noqa: BLE001 - matches retry_procedure()'s own broad catch
            last_exception = e
            seq += 1
            will_retry = attempt < max_retries and not state.stop_event.is_set()
            state.steps.append(
                StepEvent(
                    key="retry",
                    label=(
                        f"Attempt {attempt}/{max_retries} failed: {e} - retrying..."
                        if will_retry
                        else f"Attempt {attempt}/{max_retries} failed: {e} - giving up."
                    ),
                    status="failed",
                    seq=seq,
                )
            )
            if not will_retry:
                break
            # Not in the original retry_procedure() (which loops with no
            # delay at all) - added here as basic defensive spacing so a
            # real hardware fault isn't hammered instantly, since this
            # loop runs up to 10x now instead of never running at all.
            time.sleep(3)

    try:
        if succeeded:
            state.finished_ok = True

            id_command["process"] = "done"
            id_command["result"] = True
            id_command["message"] = "Session completed successfully"
            _set_dwarf_field(id_command, session)
            _capture_actual_camera_settings(id_command, session)
            _capture_eq_solving_result(id_command, session)

            if current_path is not None:
                dirs = session_dirs_for(session)
                starting_date = id_command.get(
                    "starting_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                dt_str = starting_date.replace(":", "-").replace(" ", "-")
                new_filename_base = re.sub(
                    r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}_", "", os.path.basename(current_path)
                )
                new_filename = f"{dt_str}_{new_filename_base}"
                done_path = os.path.join(dirs["DONE_DIR"], new_filename)
                os.makedirs(dirs["DONE_DIR"], exist_ok=True)

                _update_process_status(full_program, "done")
                _write_json(done_path, full_program)
                if os.path.exists(current_path):
                    os.remove(current_path)

        else:
            e = last_exception
            state.error = str(e)
            state.finished_ok = False
            id_command["process"] = "error"
            id_command["result"] = False
            id_command["message"] = (
                f"Session failed after {attempt} attempt(s): {e}" if attempt > 1 else f"Session failed: {e}"
            )
            _set_dwarf_field(id_command, session)

            if current_path is not None:
                dirs = session_dirs_for(session)
                error_path = os.path.join(dirs["ERROR_DIR"], os.path.basename(current_path))
                os.makedirs(dirs["ERROR_DIR"], exist_ok=True)
                _update_process_status(full_program, "done")
                _write_json(error_path, full_program)
                if os.path.exists(current_path):
                    os.remove(current_path)

    finally:
        state.running = False
        connection_health.release_command_slot(session.dwarf_uid)


def start_run(
    dwarf_uid: str, program: dict, session, source_filepath: str | None = None
) -> RunState:
    """Starts a new run for this device (raises if one is already
    running, or if a command is otherwise in flight for it right now)
    and returns its RunState immediately - the caller polls it (e.g. via
    a ui.timer) rather than awaiting completion, since a real astro
    session can run for hours. Uses background_tasks.create()
    (fire-and-forget, exception-safe, GC-safe) rather than a bare
    asyncio.create_task(), matching how NiceGUI itself schedules this
    kind of detached work internally (e.g. AwaitableResponse).

    source_filepath: pass the ToDo file's path (see pages/programs.py's
    relaunch()) so this run's progress/outcome gets tracked into Current
    then Done/Error, same as astro_dwarf_scheduler.py would - omit only
    for a throwaway run with nothing to track."""
    if is_running(dwarf_uid):
        raise RuntimeError("A program is already running for this device.")
    if not connection_health.try_acquire_command_slot(dwarf_uid):
        raise RuntimeError("A command is already in progress for this device.")

    state = RunState()
    state.program_name = program.get("id_command", {}).get("description") or ""
    _runs[dwarf_uid] = state
    background_tasks.create(
        run.io_bound(_run_blocking, program, session, state, source_filepath),
        name=f"scheduler-{dwarf_uid}",
    )
    return state


def request_stop(dwarf_uid: str) -> None:
    """Signals stop_event - dwarf_session.py's own interrupted() checks
    this between steps and short-circuits try_attemps()'s retry loop.
    Does not forcibly kill the worker thread (not possible/safe to do
    from here); the run stops at its next checkpoint, not necessarily
    instantly."""
    state = _runs.get(dwarf_uid)
    if state:
        state.stop_event.set()


def clear_run(dwarf_uid: str) -> None:
    """Drops the finished run's state so the UI can start fresh (e.g.
    after reviewing a completed/failed run's step log)."""
    if not is_running(dwarf_uid):
        _runs.pop(dwarf_uid, None)