"""Active connectivity verification, on top of DwarfSession.is_connected.

DwarfSession.is_connected only checks whether a client_instance/websocket
OBJECT REFERENCE exists - confirmed in dwarf_python_api's
send_socket_message() (dwarf_session_socket.py): the ERROR_TIMEOUT branch
just logs and returns False, it never calls stop_event_loop() or clears
client_instance/websocket the way the DISCONNECTED branch right above it
does. So a Wi-Fi glitch that causes a command timeout mid-session (rather
than a clean protocol-level disconnect) leaves is_connected stuck at True
forever - the UI would keep showing "Connected" even though every
subsequent command times out.

This module tracks, per dwarf_uid, whether the last ACTIVE check (a real
round-trip command, not just reading cached fields via get_client_status)
actually succeeded, and exposes is_actually_connected() for the UI to
combine with session.is_connected.

IMPORTANT LATENCY NOTE (found via real hardware testing): the check
itself (perform_get_device_state_info) can take anywhere from ~30s to
the full 150s (dwarf_python_api's gb_timeout) to come back False during
a real outage, DEPENDING on whether session.client_instance still looks
alive at the time - if it does (the common case, since nothing clears
it on a plain command timeout, see above), connect_socket() reuses it
via send_socket_message()'s 150s gb_timeout rather than the faster ~30s
init_socket() connection-establishment path. That's a much longer
"blind window" than the ~12s check cadence below suggests on its own -
see _PRESUMED_LOST_AFTER_S.

CONCURRENCY NOTE (found via a `cmd_send: None` anomaly in a real log):
session.client_instance.command is a SINGLE, UNLOCKED attribute in
dwarf_python_api (websockets_utils.py) - send_message() sets it, the
receive loop reads it to tag which outstanding request a reply belongs
to, and send_socket_message() resets it to None once done. There's no
locking around any of this. dwarf_python_api's own send_socket_message()
already defends against a MISMATCHED reply for the SAME request being
wrongly accepted (process_command() compares cmd_send/cmd_recv and
retries on a mismatch) - but nothing stops TWO DIFFERENT commands for
the SAME session from being sent concurrently in the first place, which
is exactly what could make that field race. This module's
try_acquire_command_slot()/release_command_slot() close that gap on our
side: every call site that sends a command for a given session - this
module's own active check AND every user-triggered action in
pages/session.py - claims the same per-uid slot first, so at most one
command is ever in flight for a given Dwarf regardless of which page or
tab triggered it.

AUTO-RECONNECT: mirrors a feature added to the Dwarfium project - when
the active check confirms a device has actually dropped, this module
automatically retries reconnecting up to _MAX_AUTO_RECONNECT_ATTEMPTS
times before giving up. Deliberately does NOT resend whatever command
was in flight when the drop happened - only the link is re-established,
never a replay of the interrupted action, to avoid risking a duplicate
(e.g. a capture command firing twice on the device).

The reconnect step itself is deliberately LIGHT: just
perform_get_device_state_info() (which transparently re-runs
init_socket() if needed), NOT a full perform_enter_astro_mode(). A
network drop doesn't necessarily mean the device itself left astro mode
or closed the camera - only that OUR socket died. Forcing a fresh
SWITCH_SHOOTING_MODE/ENTER_CAMERA on every auto-reconnect risked
disrupting a capture that might still be running fine on the device's
side, for no benefit - dwarf_python_api currently decodes but discards
shooting_mode from the state-info response (see perform_
get_device_state_info()'s docstring/log line), so there's no cheap way
to confirm "still in astro mode" before deciding whether re-entering it
is actually necessary. The manual Reconnect button in pages/session.py
still does the fuller connect_and_enter_astro_mode() - a human
explicitly asking to reconnect is a reasonable point to also force a
clean mode state, unlike an unattended background retry.

If all auto-reconnect attempts fail, the device is left in the existing
"connection lost" state for the user to retry manually via pages/
session.py's Reconnect button, which also clears the "exhausted" flag
so auto-reconnect gets another fresh shot next time.

EVENT LOOP CLEANUP: a device-initiated disconnect (CMD_NOTIFY_POWER_OFF)
calls WebSocketClient.disconnect() internally (websockets_utils.py) and
correctly clears self.websocket, so session.is_connected does flip to
False - but that low-level disconnect() has no reference to the owning
DwarfSession, so it can't call stop_event_loop() to actually join
session.event_loop_thread. Left alone, that thread just sits idle
forever (a real, if fairly harmless, leak - seen as noisy "Task was
destroyed" messages when the process eventually exits). Fixed here
instead, in maybe_check(): the first time a poll tick notices
is_connected went False while a thread is still around, it calls
stop_event_loop() to join it properly - this is the right layer for
that cleanup, since only the application (holding the DwarfSession)
can call it, not the protocol-level WebSocketClient itself."""
from __future__ import annotations

import asyncio
import time

from nicegui import background_tasks, run

from dwarf_python_api.lib.dwarf_session import DwarfSession
from dwarf_python_api.lib.dwarf_session_socket import stop_event_loop
from dwarf_python_api.lib.dwarf_utils import (
    perform_disconnect,
    perform_enter_astro_mode,
    perform_get_device_state_info,
)

# How often to actively probe a session that LOOKS connected (seconds).
# Deliberately much longer than the UI's ~2s display refresh - this
# sends a real command to the device, unlike the cheap in-memory status
# reads (get_client_status) used for the rest of the polling.
_CHECK_INTERVAL_S = 12.0

# If a check has been running (unresolved) for longer than this, treat
# the session as disconnected FOR DISPLAY PURPOSES already, rather than
# silently keep showing "Connected" for up to gb_timeout=150s while the
# underlying blocking call is still stuck waiting for a reply that will
# never come. The slow call keeps running in its own thread regardless
# (it can't be cancelled mid-flight - dwarf_python_api has no support
# for that) and _last_check_ok / the command slot are updated normally
# once it eventually does return, this just stops the UI from lying in
# the meantime.
_PRESUMED_LOST_AFTER_S = 15.0

# Auto-reconnect only actually STARTS once the active check's own
# up-to-150s round trip finally comes back False (see the LATENCY NOTE
# above) - it does not fire the moment _PRESUMED_LOST_AFTER_S flips the
# UI to "connection lost". A known, accepted limitation for v1: the
# display goes stale-looking (~15s) well before the automatic recovery
# attempt actually begins (up to 150s later). Tightening that gap would
# mean racing to reconnect while the original stuck call might still be
# running in its own thread - left as a possible future improvement.
_MAX_AUTO_RECONNECT_ATTEMPTS = 3
_AUTO_RECONNECT_DELAY_S = 3.0

_last_check_at: dict[str, float] = {}
_last_check_ok: dict[str, bool] = {}
_check_started_at: dict[str, float] = {}

# Shared across ALL command-sending call sites for a session (this
# module's own active check AND every user action in pages/session.py) -
# see the CONCURRENCY NOTE above for why this needs to be a single
# shared registry rather than each call site guarding only itself.
_command_in_flight: set[str] = set()

# uids where _MAX_AUTO_RECONNECT_ATTEMPTS auto-reconnect attempts just
# failed in a row - stop auto-retrying until the user manually
# reconnects (which clears this, see mark_just_connected()).
_auto_reconnect_exhausted: set[str] = set()
_auto_reconnect_in_progress: set[str] = set()


def try_acquire_command_slot(dwarf_uid: str) -> bool:
    """Claims the exclusive right to send ONE command to this device.
    Returns False if another command - ours or a user action from
    pages/session.py - is already in flight for it; the caller should
    back off (skip this tick, or tell the user to wait) rather than
    risk racing dwarf_python_api's unlocked client_instance.command."""
    if dwarf_uid in _command_in_flight:
        return False
    _command_in_flight.add(dwarf_uid)
    return True


def release_command_slot(dwarf_uid: str) -> None:
    _command_in_flight.discard(dwarf_uid)


def is_actually_connected(session: DwarfSession) -> bool:
    """session.is_connected AND no active check has failed since AND no
    command has been stuck unresolved for longer than _PRESUMED_LOST_AFTER_S."""
    if not session.is_connected:
        return False

    uid = session.dwarf_uid
    if uid in _command_in_flight:
        started = _check_started_at.get(uid)
        if started is not None and time.monotonic() - started > _PRESUMED_LOST_AFTER_S:
            return False

    return _last_check_ok.get(uid, True)


async def connect_and_enter_astro_mode(session) -> bool:
    """Shared by the manual Reconnect button (pages/session.py) and this
    module's own auto-reconnect below. perform_enter_astro_mode() alone
    is enough to both establish the connection AND enter astro mode -
    connect_socket() (dwarf_session_socket.py) already runs init_socket()
    whenever session.client_instance is None/not started, and init_
    socket()'s own send_message_init() sends an initial
    CMD_GLOBAL_TASK_GET_DEVICE_STATE_INFO before whatever command was
    actually asked for - so a separate perform_get_device_state_info()
    call first would just send that same command twice on every fresh
    connect."""
    result = await run.io_bound(perform_enter_astro_mode, session=session)
    return result is not False


async def _auto_reconnect(session: DwarfSession) -> None:
    """Runs as a detached background task (see maybe_check()) - never
    awaited by the poll loop, since a reconnect sequence can itself
    take a while per attempt.

    Deliberately light: perform_get_device_state_info() only, NOT
    connect_and_enter_astro_mode() - see the module docstring's AUTO-
    RECONNECT section for why forcing a fresh mode switch on every
    unattended retry is the wrong default."""
    uid = session.dwarf_uid
    if uid in _auto_reconnect_in_progress:
        return
    _auto_reconnect_in_progress.add(uid)
    try:
        for attempt in range(1, _MAX_AUTO_RECONNECT_ATTEMPTS + 1):
            if not try_acquire_command_slot(uid):
                # A manual action (or another auto-reconnect pass)
                # already has the slot - back off rather than fight over
                # it; the next failed check will try again later.
                return
            try:
                await run.io_bound(perform_disconnect, session=session)
                result = await run.io_bound(perform_get_device_state_info, session=session)
                success = result is not False
            finally:
                release_command_slot(uid)

            if success:
                mark_just_connected(uid)
                _auto_reconnect_exhausted.discard(uid)
                return

            if attempt < _MAX_AUTO_RECONNECT_ATTEMPTS:
                await asyncio.sleep(_AUTO_RECONNECT_DELAY_S)

        # All attempts failed - stop auto-retrying for this uid until a
        # manual reconnect (mark_just_connected()) clears this.
        _auto_reconnect_exhausted.add(uid)
    finally:
        _auto_reconnect_in_progress.discard(uid)


async def _cleanup_stale_event_loop(session: DwarfSession) -> None:
    """See the module docstring's EVENT LOOP CLEANUP section.

    Two things fixed here after a real crash caught this in testing:
    1) stop_event_loop() is BLOCKING (thread.join() etc.) - it must go
       through run.io_bound() like every other dwarf_python_api call in
       this app, never called directly from an async function (that
       would freeze NiceGUI's single event loop, and every client with
       it, for however long the join takes).
    2) It must go through the SAME command slot as every other operation
       on this session. Without that guard, this cleanup - running on
       every poll tick for a disconnected session - could close
       session.event_loop out from under a concurrent user action (e.g.
       clicking Connect right as a poll tick ran), which is exactly what
       produced a real "Event loop is closed" crash inside
       perform_enter_astro_mode(). If the slot is already held, some
       real operation (or another cleanup pass) owns this session right
       now - skip and let a later poll tick retry instead of racing it.
    """
    thread = getattr(session, "event_loop_thread", None)
    if thread is None or not thread.is_alive():
        return

    uid = session.dwarf_uid
    if not try_acquire_command_slot(uid):
        return
    try:
        await run.io_bound(stop_event_loop, session=session)
    except Exception as e:  # noqa: BLE001 - best-effort cleanup, never worth crashing a poll tick over
        import dwarf_python_api.lib.my_logger as log

        log.warning(f"[{uid}] Error cleaning up stale event loop: {e}")
    finally:
        release_command_slot(uid)


async def maybe_check(session: DwarfSession) -> None:
    """Call this on every poll tick for a session that looks connected.
    Only actually probes the device every _CHECK_INTERVAL_S, and backs
    off entirely if a command (ours or a user action) is already in
    flight for this device - see try_acquire_command_slot(). If the
    check confirms the device has dropped, kicks off _auto_reconnect()
    as a detached background task (unless already exhausted or already
    running for this uid)."""
    if not session.is_connected:
        await _cleanup_stale_event_loop(session)
        forget(session.dwarf_uid)
        return

    uid = session.dwarf_uid
    now = time.monotonic()
    if now - _last_check_at.get(uid, 0.0) < _CHECK_INTERVAL_S:
        return
    if not try_acquire_command_slot(uid):
        return

    _check_started_at[uid] = time.monotonic()
    try:
        result = await run.io_bound(perform_get_device_state_info, session=session)
        ok = result is not False
        _last_check_ok[uid] = ok
        _last_check_at[uid] = time.monotonic()
    finally:
        release_command_slot(uid)
        _check_started_at.pop(uid, None)

    if not ok and uid not in _auto_reconnect_exhausted and uid not in _auto_reconnect_in_progress:
        background_tasks.create(_auto_reconnect(session), name=f"auto-reconnect-{uid}")


def forget(dwarf_uid: str) -> None:
    """Call after a manual disconnect so a stale failed check doesn't
    linger and immediately re-flag a fresh connection as dead."""
    _last_check_ok.pop(dwarf_uid, None)
    _last_check_at.pop(dwarf_uid, None)


def mark_just_connected(dwarf_uid: str) -> None:
    """Call right after a successful connect/reconnect (manual or
    automatic). Without this, a freshly-connected device has no
    _last_check_at entry yet, so the very NEXT poll tick (up to ~2s
    later, not the intended _CHECK_INTERVAL_S) would immediately fire an
    active check - this sets "now" as the baseline instead. Also clears
    _auto_reconnect_exhausted, so a device the user just fixed manually
    (or that recovered on its own) is eligible for auto-reconnect again
    next time it drops."""
    _last_check_ok.pop(dwarf_uid, None)
    _last_check_at[dwarf_uid] = time.monotonic()
    _auto_reconnect_exhausted.discard(dwarf_uid)