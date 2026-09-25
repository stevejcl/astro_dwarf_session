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

import dwarf_python_api.lib.my_logger as log
import dwarf_session as astro_dwarf_session
from dwarf_session import STEP_DESCRIPTIONS
from dwarf_python_api.lib.dwarf_session import get_manager

from dwarf_python_api.get_config_data import config_to_dwarf_id_str
from dwarf_python_api.lib.dwarf_session_socket import get_client_status
from dwarf_python_api.lib.dwarf_utils import perform_read_camera_params_http_v3
from dwarf_python_api.lib.dwarf_utils import perform_is_camera_actually_busy

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
    stop_requested: bool = False  # user-requested Sep 2026
    steps: list[StepEvent] = field(default_factory=list)
    error: str | None = None
    finished_ok: bool | None = None  # None while running, True/False once done
    program_name: str = ""  # user-requested (Sep 2026): shown by program_section.py's
    # simplified "running" view regardless of HOW the run was started (a
    # direct upload here, or a relaunch from pages/programs.py's Scripts/
    # Results tabs) - populated once in start_run() from the program's
    # own id_command.description, not tracked separately by each caller.
    shots_taken: int | None = None  # user-requested Sep 2026: same numbers
    shots_stacked: int | None = None  # _capture_shots_result() writes into
    # id_command (for the Results tab's card - see pages/programs.py),
    # mirrored here too so program_section.py's LIVE view can show them
    # right after a run finishes without re-reading the just-written
    # Done/Error JSON file back off disk.
    # Same mirroring, for exposure/gain (user-reported Sep 2026: these
    # were missing from program_section.py's own live/just-finished
    # view - "expo, gain et count total se sont pas affiches dans les
    # infos en cours" - _capture_actual_camera_settings() already wrote
    # them onto id_command, just never got mirrored here like shots_
    # taken/stacked were). "Count total" itself doesn't need a new
    # field - requested_count_tele/requested_count_wide below already
    # cover that.
    exposure_actual: str = ""
    gain_actual: str = ""
    # Filled LIVE from on_progress()'s own "Exposure:"/"Gain:"/"IR
    # Filter:" parsing below (user-requested Sep 2026: "les parametres
    # affiches ne sont pas bon, il se rafraichissent juste a la fin" -
    # program_section.py's own display, and watch_device.py's Dwarf-II-
    # during-capture fallback, both want a value available THROUGH the
    # run, not just once _capture_actual_camera_settings() runs at the
    # very end) - a plain live echo of what dwarf_session.py itself
    # just configured, not a fresh device read like the end-of-run
    # mirroring above.
    ir_filter_actual: str = ""
    end_time_display: str = ""  # "" when no scheduled end time was set for this run
    # user-reported Sep 2026: the device's own progress notification
    # carries a total_count field, but dwarf_python_api only logs it
    # (websockets_utils.py) and never stores it - current_count
    # (confusingly cached as "takePhotoCount"/"takeWidePhotoCount") is
    # the only number that survives into get_client_status(), and it's
    # "captured so far", not the target. The target IS available here
    # though - it's simply what the program itself asked for
    # (setup_camera/setup_wide_camera's own "count" field) - so
    # device_card.py's capturing banner and pages/watch_device.py read
    # it from here instead of needing a dwarf_python_api change.
    #
    # Kept as TWO separate fields, one per camera (user-reported Sep
    # 2026, second report: a single shared field applied to whichever
    # camera actually ran, wrongly showed "0/20" on the OTHER camera
    # too - e.g. Wide showing a target of 20 it was never actually
    # asked to shoot, just because Tele's setup_camera.count was 20 and
    # this field didn't distinguish which section was do_action=True) -
    # each defaults to "" when that camera's do_action is False, so a
    # camera that was never part of this run shows no total at all.
    requested_count_tele: str = ""
    requested_count_wide: str = ""
    force_stopped: bool = False  # set by check_stuck_runs()._force_stop() - lets a
        # stuck _run_blocking() call that eventually unblocks anyway (late, after the
        # stale event loop was torn down) recognize its result is stale: it must not
        # overwrite the forced-failure outcome with a late "success", nor release a
        # slot a LATER operation (auto_reconnect, a new run...) may have since
        # legitimately acquired.

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


def _capture_actual_camera_settings(id_command: dict, session, is_wide: bool = False) -> None:
    """Best-effort, mirrors astro_dwarf_scheduler.py's own try/except
    around this HTTP read - it may simply be unavailable, not worth
    failing an otherwise-successful run over.

    is_wide (user-reported Sep 2026: "je n'ai rien pour wide" - this
    used to always read cameras[0], which is the TELE camera's own
    params (see components/camera_stream.py's own cam_id mapping:
    0=Tele, 1=Wide) - so a Wide-only program's actual exposure/gain
    never showed up anywhere, on the dashboard OR the Programs page,
    silently reading the WRONG camera's settings instead of failing
    loudly)."""
    try:
        camera_settings = perform_read_camera_params_http_v3(mode_id=2, session=session)
        cam_index = 1 if is_wide else 0
        active_cam = (
            camera_settings.get("cameras", {}).get(cam_index)
            if isinstance(camera_settings, dict)
            else None
        )
        if active_cam:
            ir_cut_value = active_cam.get("filterType")
            if ir_cut_value is not None:
                ir_mapping = {0: "Vis", 1: "Astro Filter", 2: "DUAL Band"}
                id_command["ir_actual"] = ir_mapping.get(ir_cut_value, f"Unknown({ir_cut_value})")
            exposure_info = active_cam.get("exposure") or {}
            gain_info = active_cam.get("gain") or {}
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


def _capture_shots_result(id_command: dict, session) -> None:
    """User-requested Sep 2026: "est ce que le nombre images et
    stackees sont presentes dans le Jason final" - shotsTaken/
    shotsStacked, alongside eq_azimut_error/eq_altitude_error above,
    same best-effort read from the client's own live-tracked counters
    (websockets_utils.py), updated throughout the run from
    CMD_NOTIFY_PROGRESS_CAPTURE_RAW_LIVE_STACKING notifications - not
    re-fetched from the device's own album listing after the fact.

    Tries the tele/mosaic/wide counter pairs in turn and uses whichever
    is non-zero - a session only ever populates ONE of these three
    (matching perform_waitEndAstroPhoto()'s own routing by
    takePhotoStarted/takeWidePhotoStarted), so this reads correctly
    regardless of which kind of capture the program actually ran,
    without needing the caller to already know which one to check."""
    try:
        full_status = get_client_status(session).get("fullStatus", {})
        for count_key, stacked_key in (
            ("takeMosaicCount", "takeMosaicStacked"),
            ("takeWidePhotoCount", "takeWidePhotoStacked"),
            ("takePhotoCount", "takePhotoStacked"),
        ):
            count = full_status.get(count_key)
            stacked = full_status.get(stacked_key)
            if count:
                id_command["shots_taken"] = count
                id_command["shots_stacked"] = stacked
                return
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


def resolve_active_camera_is_tele(dwarf_uid: str, full_status: dict) -> bool:
    """Which camera (Tele vs Wide) is behind the current capture - for
    displays that need to pick between the two cameras' stats/streams
    (components/device_card.py's capturing banner, components/
    camera_stream.py's dashboard thumbnail; user-requested Sep 2026 to
    share this one spot rather than duplicate it a third time).

    Prefers RunState (set by start_run() from the program's own
    setup_camera/setup_wide_camera do_action - known instantly,
    independent of anything the device itself reports, so it can't
    inherit any device-side staleness). Falls back to the device's own
    takePhotoStarted/takeWidePhotoStarted flags only when no RunState
    exists (e.g. a capture started outside this app's own
    scheduler_runner) - safe to trust for that fallback since
    dwarf_python_api v3.0.8 fixed the device-side bug that could
    otherwise leave takePhotoStarted reading True during a Wide-only
    capture, stale from an earlier Tele one that session. Defaults to
    Tele when nothing usable is available at all."""
    run_state = get_run_state(dwarf_uid)
    if run_state and run_state.requested_count_wide and not run_state.requested_count_tele:
        return False
    if run_state and run_state.requested_count_tele:
        return True
    if full_status.get("takeWidePhotoStarted") and not full_status.get("takePhotoStarted"):
        return False
    return True


def is_running(dwarf_uid: str) -> bool:
    state = _runs.get(dwarf_uid)
    return bool(state and state.running)


# Generous safety ceiling (user-agreed Sep 2026, after a confirmed real
# incident) - deliberately loose: a single program's capture step is
# allowed to run essentially all night, since a long winter night in a
# temperate/high latitude can mean 14-16+ hours of real darkness, and
# someone may well want one very long single-target integration in one
# program, not just short mosaic tiles. This only needs to be shorter
# than "an entire day", to still catch a genuinely stuck/leaked thread
# (see check_stuck_runs()'s own docstring) rather than cap any
# realistic legitimate capture.
_MAX_RUN_SECONDS = 20 * 3600


def check_stuck_runs() -> None:
    """Background watchdog (app.timer, astro_dwarf_ui.py) - user-agreed
    Sep 2026, after a confirmed real-world incident: a disconnect
    during an active capture (the ORIGINAL trigger for that specific
    case is now fixed - see dwarf_python_api's result_notification_
    messages() and its own reset_timeout comment) left scheduler_
    runner.start_run() holding the command slot forever, because the
    thread blocked inside it never returned - dwarf_python_api's
    send_socket_message() busy-waits on future_cnx.done(), which can
    spin forever if session.event_loop was torn down while that future
    was still pending. That stuck thread ALSO permanently blocked every
    other operation on the device (health_check, any later start_run
    attempt, everything) until the whole app was restarted - "un
    blocage complet n'est pas permis".

    This does NOT fix the leaked thread itself (it's still running,
    accomplishing nothing) - it only stops that leak from ALSO
    starving every future operation forever, by forcing the SLOT and
    this run's own state back to a normal "not running" shape once
    it's been held unreasonably long. A real, still-healthy multi-hour
    capture never approaches _MAX_RUN_SECONDS, so this should never
    fire during normal use.

    FASTER TRIGGER (user-confirmed Sep 2026, a second real incident -
    this time a genuine WiFi drop, not the reset_timeout bug, which
    left the SAME kind of stuck thread behind): waiting the full 20h
    ceiling is far too slow when the session has ALREADY visibly
    disconnected (session.is_connected is False) - that's a much
    stronger, more immediate signal that the run backing this slot is
    never coming back, vs. still being a legitimate long capture.
    ORIGINALLY only acted once the slot had ALSO been held a couple of
    minutes past that disconnect, meant to give the app's own
    auto-reconnect (connection_health.py's _auto_reconnect()) a chance
    to recover first - but that reasoning was circular (Sep 2026,
    confirmed via real log): _auto_reconnect() itself needs this exact
    same command slot, so it was denied on every attempt for the whole
    grace period, unable to do anything until THIS watchdog released
    it. Shortened to _DISCONNECTED_GRACE_SECONDS instead - long enough
    to not mistake a momentary is_connected flicker for a genuine
    drop, short enough that auto_reconnect gets the slot back quickly
    once a real disconnect is confirmed."""
    
    # Was 120 - see Sep 2026 finding: this grace period was meant to "give
    # auto_reconnect a chance to recover on its own first" (see this
    # function's own docstring), but auto_reconnect can NEVER get that
    # chance during this window - it needs the SAME command slot this run
    # is holding, so it's denied on every attempt until THIS watchdog
    # releases the slot. The two mechanisms were deadlocked against each
    # other: waiting longer here only delayed recovery, it never let
    # anything recover in the meantime. Shortened so a real disconnect
    # hands the slot to auto_reconnect quickly, while still being long
    # enough that a session.is_connected blip lasting a couple of seconds
    # (not a genuine drop) doesn't force-stop a run that was about to
    # recover on its own via the normal WebSocket layer.
    _DISCONNECTED_GRACE_SECONDS = 15

    def _force_stop(dwarf_uid: str, state: RunState, reason: str) -> None:
        log.warning(f"[{dwarf_uid}] Run force-stopped: {reason}")
        state.running = False
        state.finished_ok = False
        state.error = f"Run force-stopped: {reason}"
        state.force_stopped = True
        connection_health.release_command_slot(dwarf_uid)

    manager = get_manager()
    for dwarf_uid, state in list(_runs.items()):
        if not state.running:
            continue
        duration = connection_health.command_in_flight_duration(dwarf_uid)
        if duration is None:
            continue

        try:
            session = manager.get(dwarf_uid)
        except KeyError:
            session = None

        if (
            session is not None
            and not session.is_connected
            and duration > _DISCONNECTED_GRACE_SECONDS
        ):
            _force_stop(
                dwarf_uid,
                state,
                f"session disconnected and slot still held {duration:.0f}s later "
                "(likely a leaked thread after a network drop).",
            )
            continue

        if duration > _MAX_RUN_SECONDS:
            _force_stop(
                dwarf_uid,
                state,
                f"slot held {duration:.0f}s > {_MAX_RUN_SECONDS}s - far longer than "
                "any real capture should take (likely a leaked thread).",
            )


def device_is_actively_capturing(session) -> bool:
    """Checks the DEVICE's real, live state via a FRESH
    CMD_GLOBAL_TASK_GET_DEVICE_STATE_INFO query - NOT get_client_status()'s
    AstroCapture/takePhotoStarted/takeWidePhotoStarted flags.

    CORRECTION (this function previously used those three flags - traced
    through dwarf_python_api/lib/websockets_utils.py and confirmed they
    are UNRELIABLE for this purpose): each only flips True on a
    notification whose state matches `self.command == the exact command
    THIS process itself last sent` (e.g. the CMD_ASTRO_START_CAPTURE_RAW_
    LIVE_STACKING block). A session started by the OFFICIAL Dwarf app, or
    an on-device native shooting-schedule task, never sets self.command to
    any of those values here - so those flags silently stay False for it
    even while the device is genuinely capturing, which is exactly the
    scenario this check exists to catch. perform_is_camera_actually_busy()
    instead sends a fresh request and reads the device's real answer,
    regardless of who started the activity.

    Fails OPEN (returns False) if the query itself fails/times out, same
    as perform_is_camera_actually_busy() - see its own docstring.
    """
    if not session.is_connected:
        return False
    return perform_is_camera_actually_busy(session=session)

def _run_starting_blocking(
    dwarf_uid,
    program,
    session,
    state,
    source_filepath,
):
    # This is now running in the io_bound worker thread.
    try:
        if device_is_actively_capturing(session):
            state.running = False
            state.error = (
                "The Dwarf is already capturing - "
                "refusing to start a new session."
            )
            return

        acquired = connection_health.try_acquire_command_slot(
            dwarf_uid,
            caller="scheduler_runner.start_run",
        )
        if not acquired:
            state.running = False
            state.error = "A command is already in progress for this device."
            return
    finally:
        # try/finally (not a plain call after the acquire, as in an
        # earlier version) so mark_priority_pending() from start_run()
        # below always gets cleared here even if something above raises
        # - a leaked pending flag would otherwise starve health_check
        # for this device FOREVER, the same failure mode this exists to
        # fix, just permanent instead of an 18-minute window.
        connection_health.clear_priority_pending(dwarf_uid)

    _run_blocking(
        program,
        session,
        state,
        source_filepath,
    )

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
        # Live echo (user-requested Sep 2026) - dwarf_session.py already
        # sends these exact "Exposure: X"/"Gain: X"/"IR Filter: X"
        # messages right when it configures them, well before capture
        # actually starts (Setup Astro Photo Parameters, both Tele and
        # Wide) - parsing them here as they arrive gives program_
        # section.py's live view and watch_device.py's Dwarf-II fallback
        # a value for the WHOLE run, not just once it finishes.
        if status == "success" and ":" in step_key:
            prefix, _, value = step_key.partition(":")
            value = value.strip()
            if prefix == "Exposure":
                state.exposure_actual = value
            elif prefix == "Gain":
                state.gain_actual = value
            elif prefix == "IR Filter":
                state.ir_filter_actual = value

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

    if state.force_stopped:
        log.warning(f"[{session.dwarf_uid}] Stuck call finally returned after force-stop - discarding its stale result.")
        return

    try:
        if succeeded:
            state.finished_ok = True

            id_command["process"] = "done"
            id_command["result"] = True
            id_command["message"] = "Session completed successfully"
            _set_dwarf_field(id_command, session)
            _capture_actual_camera_settings(
                id_command, session,
                is_wide=bool(program.get("setup_wide_camera", {}).get("do_action")),
            )
            _capture_eq_solving_result(id_command, session)
            _capture_shots_result(id_command, session)
            id_command["count_info"] = state.requested_count_tele if state.requested_count_tele else state.requested_count_wide
            id_command["mosaic_info"] =  program.get("setup_camera", {}).get("doMosaic") and program.get("setup_camera", {}).get("do_action")
            state.shots_taken = id_command.get("shots_taken")
            state.shots_stacked = id_command.get("shots_stacked")
            state.exposure_actual = id_command.get("exposure_actual") or ""
            state.gain_actual = id_command.get("gain_actual") or ""

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
        #clear_run(session.dwarf_uid)
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
    print("start_run")

    if is_running(dwarf_uid):
        raise RuntimeError("A program is already running for this device.")

    # Marked here, BEFORE the background thread even starts (user-
    # reported Sep 2026: a real overnight log showed a scheduled
    # program's start starved for 18 minutes straight - health_check's
    # own poll cadence happened to phase-lock against scheduler_loop's
    # retry cadence, so it kept winning the slot-acquire race every
    # single time). Cleared in _run_starting_blocking() below the
    # moment its own acquire attempt actually resolves - see
    # connection_health.clear_priority_pending()'s own docstring for why
    # this shouldn't linger any longer than that.
    connection_health.mark_priority_pending(dwarf_uid)

    # Neither check above knows about activity astro_dwarf_session didn't
    # itself start (a manual session from the official Dwarf app, or an
    # on-device native shooting-schedule task currently running) - without
    # this, start_run() would happily fire goto/calibration/capture-start
    # commands on top of whatever's already happening, interrupting it.
    # The Dwarf's OWN scheduling logic already queues a shooting-schedule
    # task behind a running capture gracefully (field-confirmed) - but
    # that graceful handling is on the RECEIVING end for a schedule sync,
    # not for a full manual start_dwarf_session() run, which actively
    # drives goto/calibration/capture from the first step.

    state = RunState()
    state.program_name = program.get("id_command", {}).get("description") or ""
    # Surfaced by device_card.py's "capturing"/"program_running" banner
    # (user-requested Sep 2026: "peut etre l'heure final si presente") -
    # whichever camera section is actually active carries the optional
    # end_time (see program_editor.py's prog_end_time field); "" if
    # neither is set, in which case the banner just omits it.
    state.end_time_display = (
        program.get("setup_camera", {}).get("end_time")
        or program.get("setup_wide_camera", {}).get("end_time")
        or ""
    )
    state.requested_count_tele = (
        program.get("setup_camera", {}).get("count")
        if program.get("setup_camera", {}).get("do_action")
        else ""
    ) or ""
    state.requested_count_wide = (
        program.get("setup_wide_camera", {}).get("count")
        if program.get("setup_wide_camera", {}).get("do_action")
        else ""
    ) or ""
    _runs[dwarf_uid] = state
    
    background_tasks.create(
        run.io_bound(
            _run_starting_blocking,
            dwarf_uid,
            program,
            session,
            state,
            source_filepath,
        ),
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
        state.stop_requested = True
        state.stop_event.set()


def clear_run(dwarf_uid: str) -> None:
    """Drops the finished run's state so the UI can start fresh (e.g.
    after reviewing a completed/failed run's step log)."""
    if not is_running(dwarf_uid):
        _runs.pop(dwarf_uid, None)
