"""A capture whose count no longer moves (user-reported Oct 2026: a DWARF 3
hung at 00:20, its card read "Capture in progress 141/500" until the
morning - the same notification over and over, the user thought it ran).

stalled_minutes() is called with the counts shown (taken, stacked), on each refresh: the
minutes since it last changed once that is longer than an image should take
(STALL_MIN_S, or 4 x the exposure), else None. Logged once per stall."""
from __future__ import annotations

import time

import dwarf_python_api.lib.my_logger as log

STALL_MIN_S = 10 * 60
_EXPOSURE_FACTOR = 4

_last: dict[tuple[str, str], tuple[object, float, bool]] = {}


def _exposure_s(run_state, is_tele: bool) -> float:
    """The running program's exposure for that camera, 0 when unknown."""
    try:
        cmd = (run_state.program or {}).get("command", run_state.program or {})
        setup = cmd.get("setup_camera" if is_tele else "setup_wide_camera") or {}
        return float(setup.get("exposure") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0.0


def stalled_minutes(uid: str, is_tele: bool, count, run_state=None) -> int | None:
    key = (uid, "tele" if is_tele else "wide")
    now = time.monotonic()
    previous = _last.get(key)
    if previous is None or previous[0] != count:
        _last[key] = (count, now, False)
        return None
    _, since, logged = previous
    threshold = max(STALL_MIN_S, _EXPOSURE_FACTOR * _exposure_s(run_state, is_tele))
    if now - since < threshold:
        return None
    minutes = int((now - since) // 60)
    if not logged:
        _last[key] = (count, since, True)
        shown = "/".join(str(c) for c in count) if isinstance(count, tuple) else count
        log.warning(f"[{uid}] Capture: still {shown} (taken/stacked) after {minutes} min - the Dwarf may be stuck.")
    return minutes


def forget(uid: str) -> None:
    for key in [k for k in _last if k[0] == uid]:
        _last.pop(key, None)
