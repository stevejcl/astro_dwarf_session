"""Megastack: the Dwarf stacks several of its own sessions together (same
target, FITS still on its disk) into Astronomy/RESTACKED/ - the official
app's feature, its commands found by a capture of its traffic (Oct 2026,
dwarf_python_api: perform_check_restackable / perform_start_restack /
get_task_state).

Run as a program (a "megastack" section, start_dwarf_session()): the
check, the start, then the follow-up until the Dwarf's task ends - shown
and recorded like any program (steps, Results tab). The Dwarf is busy all
along: nothing else can run on it meanwhile.

Asked by Scope Archive's Explore (POST /api/megastack, api_routes.py)."""
from __future__ import annotations

import time

from dwarf_python_api.lib.dwarf_utils import (
    get_task_state,
    perform_check_restackable,
    perform_get_device_state_info,
    perform_list_astro_sessions_http,
    perform_start_restack,
)

import dwarf_python_api.lib.my_logger as log

STEP_CHECK = "step_m1"
STEP_START = "step_m2"
STEP_STACKING = "step_m3"
STEP_DESCRIPTIONS = {
    STEP_CHECK: "Megastack: check the sessions",
    STEP_START: "Megastack: start",
    STEP_STACKING: "Megastack: stacking on the Dwarf",
}

# The Dwarf only reports its task state with its device state, asked
# every _POLL_S (the official app's own pace, about 15 s)
_POLL_S = 15
# A megastack never takes this long: given up (the Dwarf may go on)
_MAX_S = 8 * 3600
# The result appears in the album shortly after the end
_ALBUM_TRIES = 6
_ALBUM_WAIT_S = 10

_DONE_STATES = ("OPERATION_STATE_STOPPED", "OPERATION_STATE_IDLE")


def megastack_section(program: dict) -> dict | None:
    """The program's megastack section when it asks for one."""
    section = program.get("megastack") or {}
    return section if section.get("do_action") else None


def _session_folder(entry: dict) -> str | None:
    """The session's folder on the Dwarf (with a trailing "/") from an album
    entry: its thumbnail sits in it."""
    path = entry.get("thumbnailPath") or entry.get("filePath") or ""
    return path.rsplit("/", 1)[0] + "/" if "/" in path else None


def resolve_folders(session, names: list[str]) -> tuple[list[str], list[str]]:
    """(full folders on the Dwarf, names not found) for session folder
    names (e.g. "DWARF_RAW_TELE_LDN 1235_EXP_120_GAIN_80_2026-10-17-22-05-06-912"),
    found in the Dwarf's album - the root (/DWARF_mini/Astronomy/,
    /DWARF3/...) differs per model. A full path is kept as given."""
    wanted = [str(n).strip().rstrip("/") for n in names if str(n).strip()]
    if all(n.startswith("/") for n in wanted):
        return [n + "/" for n in wanted], []
    entries = perform_list_astro_sessions_http(session=session)
    if entries is False:
        raise RuntimeError("Megastack: the Dwarf's album could not be read")
    by_name = {}
    for entry in entries or []:
        folder = _session_folder(entry)
        if folder:
            by_name[folder.rstrip("/").rsplit("/", 1)[-1]] = folder
    folders, missing = [], []
    for name in wanted:
        if name.startswith("/"):
            folders.append(name + "/")
        elif name in by_name:
            folders.append(by_name[name])
        else:
            missing.append(name)
    return folders, missing


def _progress(session, result_dir: str) -> tuple[int, int, int] | None:
    """(stacked, processed, to stack) from the result's shotsInfo.json,
    which the Dwarf updates while it stacks (user-checked Oct 2026:
    "shotsStacked": 399, "shotsDiscard": 37, "shotsToStack": 598 - 436
    processed) - None while not readable yet."""
    from pages.explorer import _fetch_shots_info, _shots_info_url

    info = _fetch_shots_info(_shots_info_url(session.config.dwarf_ip, result_dir + "stacked_thumbnail.jpg"))
    try:
        stacked = int(info["shotsStacked"])
        return stacked, stacked + int(info.get("shotsDiscard") or 0), int(info["shotsToStack"])
    except (TypeError, KeyError, ValueError):
        return None


def _show_progress(session, program: dict, counts: tuple[int, int, int]) -> None:
    """Shown like a capture's counts - stacked / processed so far, the total
    as its count: "399/436 stacked, count 598" on the running program's
    view and, kept in id_command, on the Results tab's card."""
    from components import scheduler_runner

    stacked, processed, total = counts
    id_command = program.setdefault("id_command", {})
    id_command["shots_stacked"], id_command["shots_taken"] = stacked, processed
    state = scheduler_runner.get_run_state(session.dwarf_uid)
    if state is not None and state.running:
        state.shots_stacked, state.shots_taken = stacked, processed
        state.requested_count_tele = str(total)
        # The stack's thumbnail is rewritten as it goes (user-seen)
        state.preview_url = preview_url(session, _result_dir_of(program))
        state.preview_version = processed


def _result_dir_of(program: dict) -> str:
    return (program.get("megastack") or {}).get("result_dir") or ""


def preview_url(session, result_dir: str) -> str:
    """The stack's thumbnail on the Dwarf (its HTTP server, port 80)."""
    from urllib.parse import quote

    return f"http://{session.config.dwarf_ip}{quote(result_dir + 'stacked_thumbnail.jpg')}" if result_dir else ""


def _in_album(session, result_dir: str) -> bool:
    entries = perform_list_astro_sessions_http(session=session) or []
    return any((_session_folder(e) or "") == result_dir for e in entries)


def run(program: dict, session, interrupted, progress_callback=None) -> None:
    """The megastack of the program's sessions, followed to its end. Raises
    RuntimeError on a failure (the run then ends in Error with its
    message); returns when done or when the run is stopped (the Dwarf goes
    on stacking - it has no known stop command for this)."""
    section = megastack_section(program) or {}

    def step(key: str, ok: bool, detail: str = "") -> None:
        if progress_callback:
            progress_callback(f"{STEP_DESCRIPTIONS[key]}{(': ' + detail) if detail else ''}", "success" if ok else "failed")

    folders, missing = resolve_folders(session, section.get("sessions") or [])
    if missing:
        step(STEP_CHECK, False, f"{len(missing)} not on the Dwarf")
        raise RuntimeError(f"Megastack: sessions not found on the Dwarf: {', '.join(missing)}")
    if len(folders) < 2:
        step(STEP_CHECK, False, "at least 2 sessions")
        raise RuntimeError("Megastack: at least 2 sessions are needed")

    log.notice(f"Megastack of {len(folders)} sessions: {folders}")
    check = perform_check_restackable(folders, session=session)
    if check is None:
        step(STEP_CHECK, False, "no answer")
        raise RuntimeError("Megastack: the Dwarf didn't answer the check")
    if not check["ok"]:
        darks = check.get("need_dark_frames") or []
        detail = check["code_name"] + (f", {len(darks)} dark frame(s) missing" if darks else "")
        step(STEP_CHECK, False, detail)
        raise RuntimeError(f"Megastack refused by the Dwarf: {detail}")
    step(STEP_CHECK, True, f"{len(folders)} sessions")
    if interrupted():
        return

    started_at = time.time()
    start = perform_start_restack(folders, session=session)
    if start is None or not start["ok"]:
        detail = "no answer" if start is None else start["code_name"]
        step(STEP_START, False, detail)
        raise RuntimeError(f"Megastack not started: {detail}")
    # Its folder (the answer names its stacked.jpg)
    result_dir = start["result_dir"]
    if not result_dir.endswith("/"):
        result_dir = result_dir.rsplit("/", 1)[0] + "/"
    section["result_dir"] = result_dir
    step(STEP_START, True, result_dir.rstrip("/").rsplit("/", 1)[-1])

    # Followed until the Dwarf's multi-stack task ends: its state STOPPED
    # or IDLE, or the Dwarf back to no task at all (TASK_ID_IDLE reported
    # after it)
    deadline = time.monotonic() + _MAX_S
    seen_running = False
    while True:
        if interrupted():
            log.notice("Megastack: no longer followed (stop requested) - the Dwarf goes on stacking")
            return
        if time.monotonic() > deadline:
            step(STEP_STACKING, False, "too long")
            raise RuntimeError("Megastack: still running after 8 h - no longer followed")
        perform_get_device_state_info(session=session)
        counts = _progress(session, result_dir)
        if counts is not None:
            _show_progress(session, program, counts)
        task = get_task_state(session=session)
        idle = get_task_state("TASK_ID_IDLE", session=session)
        if task is not None and task["updated"] >= started_at:
            if task["state"] == "OPERATION_STATE_RUNNING":
                seen_running = True
            elif task["state"] in _DONE_STATES:
                break
        if seen_running and idle is not None and task is not None and idle["updated"] > task["updated"]:
            break
        time.sleep(_POLL_S)

    for _ in range(_ALBUM_TRIES):
        if _in_album(session, result_dir):
            counts = _progress(session, result_dir)
            if counts is not None:
                _show_progress(session, program, counts)
            step(STEP_STACKING, True, "done")
            log.success(f"Megastack done: {result_dir}")
            return
        time.sleep(_ALBUM_WAIT_S)
    step(STEP_STACKING, False, "result not in the album")
    raise RuntimeError(f"Megastack ended but its result isn't in the Dwarf's album: {result_dir}")
