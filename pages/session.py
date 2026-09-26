"""Single-session page. Matches the already-validated
'dwarf_control_single_session' mockup, this time wired to the real
perform_* functions from dwarf_python_api instead of sample data.

All perform_* functions are SYNCHRONOUS and BLOCKING (they wait for a
WebSocket reply, sometimes several seconds) - they are always passed
through run.io_bound() so the NiceGUI event loop (which serves ALL
clients, native window included) never freezes.

IMPORTANT (found via real multi-device testing): the @ui.refreshable
view used to be a plain MODULE-LEVEL function decorated once, called as
_session_view(dwarf_uid) and refreshed via _session_view.refresh(dwarf_uid).
NiceGUI's `refreshable` wraps ONE single object per decorated function,
shared across every call site regardless of which client/page/device
called it - `refresh()` loops over EVERY target ever created by that
function and overwrites each one's arguments with whatever was just
passed in (see nicegui/functions/refreshable.py: `target.args = args or
target.args` inside `_execute_refresh`, with no per-client isolation for
a plain function since `target.instance` is always None). With two
devices open in two tabs, refreshing device B's view would silently
repaint device A's already-open page with device B's data, and vice
versa - this is exactly the "shows the wrong device's data" bug seen in
testing. Fix: the refreshable view is now built INSIDE session_page(),
so every page load gets its OWN independent refreshable object with its
own target list - nothing shared across pages/devices anymore."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Callable

from nicegui import run, ui

from dwarf_python_api.lib.dwarf_session import get_manager
from dwarf_python_api.lib.dwarf_session_socket import get_client_status
from dwarf_python_api.lib.dwarf_utils import perform_disconnect
from dwarf_python_api.lib.dwarf_utils import perform_sync_shooting_schedule
from dwarf_python_api.lib.dwarf_utils import perform_get_all_shooting_schedule_full
from dwarf_python_api.lib.dwarf_utils import perform_get_last_connection_error
from dwarf_python_api.lib.dwarf_utils import perform_delete_shooting_schedule
import pending_schedules
from dwarf_python_api.lib.my_logger import (
    register_thread_device_label,
    unregister_thread_device_label,
)

from components import connection_health, scheduler_runner, native_schedule
from components.native_schedule import parse_native_schedule_info
from components.actions_section import build_actions_section
from components.camera_stream import build_camera_stream_section
from components.motor_control import build_motor_pad, build_motor_position_tool
from components.camera_settings import build_camera_settings
from components.i18n import t
from components.program_section import build_program_section
from components.status_banner import status_banner
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme

# Dwarf uids with a user action currently in flight (connect/disconnect/
# capture...). Keyed by dwarf_uid, shared across pages - that's fine,
# unlike the refreshable bug above: this is a plain set used only to
# skip a poll tick, not something that overwrites another page's UI
# content. The periodic ui.timer skips its refresh for these uids -
# without this, a concurrent refresh during an `await run.io_bound(...)`
# could delete the button/slot the in-flight handler depends on, and a
# subsequent ui.notify() would crash with "The parent element this slot
# belongs to has been deleted." (seen in real testing: the connection
# itself succeeded fine on hardware, only the confirmation popup crashed).
_busy_uids: set[str] = set()


def _safe_notify(message: str, type: str = "info") -> None:  # noqa: A002 (keeps NiceGUI's name)
    """Safety net: if the slot was deleted anyway in the meantime
    (navigation, tab closed...), we just lose the popup instead of
    crashing the handler."""
    try:
        ui.notify(message, type=type)
    except RuntimeError:
        pass


def _connection_color(connected: bool) -> str:
    return "positive" if connected else "negative"


def _label_thread_for_device(session) -> None:
    """Tags session.event_loop_thread's log records with this device's
    uid (see my_logger.register_thread_device_label) - that thread is
    where most low-level protocol log lines actually get emitted (ping/
    pong, frame decoding...), deep inside WebSocketClient's async
    methods that don't have a dwarf_uid string handy to embed by hand.
    No-op if the thread isn't up yet for some reason - best-effort, this
    is a debugging aid, not something worth failing a connect over."""
    thread = getattr(session, "event_loop_thread", None)
    if thread is not None:
        register_thread_device_label(thread.ident, session.dwarf_uid)


def _metric_card(label: str, value, unit: str, *, is_low: bool = False) -> None:
    """is_low (user-requested Sep 2026, same threshold as components/
    device_card.py's dashboard card - see its own _LOW_BATTERY_PCT/
    _LOW_DISK_GB): red + a soft pulse instead of the normal grey, for
    battery/free-storage specifically - "je n'ai pas vu qu'il ne
    restait que 1 Go" was reported from the dashboard card, but this
    page had the exact same gap, its own separate implementation."""
    with ui.card().classes("flex-1 items-center"):
        ui.label(label).classes(
            "text-xs text-red-6 font-medium" if is_low else "text-xs text-grey-6"
        )
        ui.label(f"{value if value is not None else '\u2013'}{unit}").classes(
            "text-lg font-medium text-red-6 animate-pulse" if is_low else "text-lg font-medium"
        )


class _NullNotification:
    """No-op stand-in for ui.notification() when its own creation fails
    (user-reported Sep 2026, real hardware log: BLE pairing succeeded
    fully, but the app crashed right after because the user had already
    navigated away by the time this ran - ui.notification()'s creation
    specifically needs an active page slot via context.client.layout,
    unlike its later .spinner/.message/.type updates or .dismiss(),
    which use the notification's own bound client reference and stay
    safe regardless - see the comment on the real dismiss() call below).
    Lets the rest of _handle_connect() set .spinner/.message/.type and
    call .dismiss() unconditionally, without scattering `if notification`
    checks through code that already reads cleanly linearly."""
    spinner = False
    message = ""
    type = "info"  # noqa: A003

    def dismiss(self) -> None:
        pass


def _safe_ongoing_notification(message: str):
    """ui.notification(..., timeout=None) for a persistent, updatable
    popup - but its CREATION can hit the exact same "parent slot
    deleted" RuntimeError _safe_notify() guards against for plain
    ui.notify(), if the user has already navigated away by the time a
    background task (like _handle_connect(), which awaits a multi-
    second BLE operation) gets around to creating it. Falls back to
    _NullNotification so the caller's later attribute updates/dismiss()
    are always safe to call unconditionally."""
    try:
        return ui.notification(message, type="ongoing", spinner=True, timeout=None)
    except RuntimeError:
        return _NullNotification()


def _finish_ongoing_notification(notification, message: str, type: str) -> None:  # noqa: A002
    """Closes the ongoing/spinner popup IMMEDIATELY, then fires a fresh,
    ordinary toast with the final result.

    BUG FIX (Sep 2026, user-reported: "toujours pareil pour la notif du
    delete" - persisted even after removing the delete handler's unrelated
    sync-wrapper indirection): updating message/type on the SAME long-
    lived "ongoing" notification and scheduling a LATER dismiss via
    ui.timer(N, notification.dismiss) turned out unreliable for that
    handler specifically - the delayed timer apparently doesn't always
    fire/reach the notification correctly. Simplified to dismiss right
    away and use _safe_notify() (the same already-proven-reliable
    mechanism every other simple result toast in this file already
    uses) for the final message, instead of trying to keep reusing and
    later closing the original popup.
     """
    try:
        notification.dismiss()
    except RuntimeError:
        pass
    _safe_notify(message, type=type)


async def _offer_pending_schedule_sync(session, dwarf_uid: str, pending: dict) -> None:
    """Called right after a successful (re)connect when
    pending_schedules.get_pending(dwarf_uid) returned something (i.e. a
    "Program session to the Dwarf" POST arrived from the catalog page while
    this device was offline - see components/api_routes.py). Asks before
    syncing rather than doing it silently: the plan may be stale by the
    time the person actually opens the app and connects."""
    name = pending.get("scheduleName", t("sched_unnamed"))
    n_tasks = len(pending.get("shooting_tasks", []))

    async def _sync_now() -> None:
        dialog.close()
        notif = _safe_ongoing_notification(t("sched_syncing"))
        ok = await run.io_bound(perform_sync_shooting_schedule, pending, session=session)
        notif.spinner = False
        if ok:
            pending_schedules.clear_pending(dwarf_uid)
            notif.message = t("sched_synced")
            notif.type = "positive"
        else:
            notif.message = t("sched_sync_failed_retry")
            notif.type = "negative"
        await asyncio.sleep(2.0)
        notif.dismiss()

    def _dismiss_only() -> None:
        dialog.close()

    with ui.dialog() as dialog, ui.card():
        ui.label(t("sched_pending_offer", name=name, count=n_tasks))
        with ui.row():
            ui.button(t("sched_sync_now"), on_click=_sync_now)
            ui.button(t("later"), on_click=_dismiss_only)
            ui.button(t("discard"), on_click=lambda: (pending_schedules.clear_pending(dwarf_uid), dialog.close()))
    dialog.open()


_SCHEDULE_STATE_KEYS = {
    0: "sched_state_initialized",
    1: "sched_state_pending",
    2: "sched_state_shooting",
    3: "sched_state_completed",
    4: "sched_state_expired",
}
_TASK_STATE_KEYS = {
    0: "sched_task_state_idle",
    1: "sched_task_state_shooting",
    2: "sched_task_state_success",
    3: "sched_task_state_failed",
    4: "sched_task_state_interrupted",
}


def _schedule_state_label(state: int) -> str:
    """Looked up through t() at CALL time, never cached in a module-
    level dict (user-reported Sep 2026: translations missing here) -
    the app's language can change at runtime (dashboard.py's language
    selector), so a dict built once at import time would freeze
    whichever language was active on first import instead of following
    later switches, the same reasoning components/i18n.py's own t()
    calls elsewhere already follow."""
    key = _SCHEDULE_STATE_KEYS.get(state)
    return t(key) if key else str(state)


def _task_state_label(state: int) -> str:
    key = _TASK_STATE_KEYS.get(state)
    return t(key) if key else str(state)


def _schedule_status_text(sc: dict) -> str:
    """User-requested (Sep 2026): \"un texte dépendant de l'état : prévu
    date debut - fin, en cours, terminé et échec\". The device's own
    ShootingScheduleMsg carries this schedule's own start_time/end_time
    (separate from each task's own startTime/endTime - see the parsing
    in _handle_refresh_schedules()) - shown only for the PENDING state
    (1, \"not started yet\"), since that's the one case where knowing
    WHEN it's due to run is actually useful; once it's shooting/
    completed/expired the plain state label already says what happened,
    the dates would be redundant with the per-task lines shown below."""
    if sc.get("state_code") == 1 and sc.get("startTime") and sc.get("endTime"):
        start_dt = datetime.fromtimestamp(sc["startTime"])
        end_dt = datetime.fromtimestamp(sc["endTime"])
        end_fmt = f"{end_dt:%H:%M}" if start_dt.date() == end_dt.date() else f"{end_dt:%Y-%m-%d %H:%M}"
        return t("sched_planned_range", start=f"{start_dt:%Y-%m-%d %H:%M}", end=end_fmt)
    return _schedule_state_label(sc["state_code"])

# Per-dwarf_uid cache of the last CMD_GET_ALL_SHOOTING_SCHEDULE read - see
# _handle_refresh_schedules(). Module-level (like connection_health's own
# state), not per-NiceGUI-client: the device's actual stored schedules
# are shared truth regardless of which browser tab asked.
# Which "conn_error_<code>" keys actually have a translation - a
# code from dwarf_python_api with no mapped key here falls back to
# the generic t("connection_failed") rather than showing a raw,
# untranslated key string to the user.
_known_conn_error_keys = {"conn_error_device_occupied"}

_schedules_fetch_error: dict[str, str] = {}
_schedules_last_fetch: dict[str, float] = {}
# Persistent cache moved to components/native_schedule.py (user-requested
# Sep 2026: shared with components/api_routes.py's /api/programs, and
# now JSON-file-backed so it survives an app restart too) - this module
# no longer keeps its own in-memory copy, see native_schedule.get_cached()/
# set_cached() used below.
# How many of native_schedule.get_cached(uid) (already sorted newest-first) to
# render before the "Show more" button - user-requested (Sep 2026):
# newest first, 3 at a time, "more" to reveal the rest.
_schedules_shown_count: dict[str, int] = {}


class _BoolBox:
    """Tiny mutable wrapper so ui.expansion's open/closed state can be
    bound (via .bind_value()) to a specific dwarf_uid's slot in a plain
    dict - bind_value needs a settable OBJECT ATTRIBUTE, not a dict key.
    """
    def __init__(self, value: bool = False) -> None:
        self.value = value


# User-reported (Sep 2026): "la fenêtre se replie toute seule" - the
# WHOLE render function (including this ui.expansion) re-runs on every
# 2s poll tick (see build_session_page()'s ui.timer), so a freshly
# recreated ui.expansion() with no persisted state defaults back to
# closed every single tick, undoing any manual open within ~2s. One
# _BoolBox per dwarf_uid, read for the initial `value=` and bound so
# NiceGUI writes user toggles back into it, keeps the open/closed choice
# alive across those re-renders instead of resetting it.
_schedule_section_open: dict[str, _BoolBox] = {}


def _get_schedule_section_box(dwarf_uid: str) -> _BoolBox:
    box = _schedule_section_open.get(dwarf_uid)
    if box is None:
        box = _BoolBox(False)
        _schedule_section_open[dwarf_uid] = box
    return box


async def _handle_delete_schedule(
    session, dwarf_uid: str, schedule_id: str, schedule_name: str, refresh_view: Callable[[], None]
) -> None:
    """CMD_DELETE_SHOOTING_SCHEDULE (16108) - user-requested (Sep 2026):
    a button to remove a not-yet-executed schedule from the device's own
    list, distinct from the local "Discard" button on the Pending-
    schedule banner (that one clears something never even sent yet; this
    one removes something already sitting ON the device). perform_
    delete_shooting_schedule() itself has existed since the very first
    native-schedule integration but was never wired to any button until
    now.

    BUG FIX (Sep 2026, user-reported: notification never closes, list
    doesn't refresh after delete): _do_delete() used to be a SYNC on_
    click handler that deferred the real async work via ui.timer(0.01,
    _run, once=True) - unlike every other handler here (Connect,
    Reconnect, Sync pending), which are plain async functions given
    directly to on_click (NiceGUI runs an async on_click natively, no
    deferral needed). That extra indirection was losing the proper
    client context by the time the LATER dismiss timer inside _finish_
    ongoing_notification() fired, and apparently refresh_view() too.
    Simplified to match the other three handlers' working pattern.
    """
    with ui.dialog() as dialog, ui.card():
        ui.label(t("sched_delete_confirm", name=schedule_name)).classes("text-sm")

        async def _do_delete() -> None:
            dialog.close()
            if not connection_health.try_acquire_command_slot(dwarf_uid, caller="session.delete_schedule"):
                _safe_notify(t("device_busy"), type="warning")
                return
            notification = _safe_ongoing_notification(t("sched_deleting", name=schedule_name))
            try:
                ok = await run.io_bound(perform_delete_shooting_schedule, schedule_id, session=session)
            finally:
                connection_health.release_command_slot(dwarf_uid)
            if ok:
                _finish_ongoing_notification(notification, t("sched_deleted"), "positive")
                # Drop it from the cached list immediately rather than
                # waiting for the next manual Refresh - the device won't
                # offer it back on a re-fetch anyway once deleted.
                native_schedule.remove_from_cache(dwarf_uid, schedule_id)
            else:
                _finish_ongoing_notification(notification, t("sched_delete_failed"), "negative")
            refresh_view()

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button(t("cancel"), on_click=dialog.close).props("flat")
            ui.button(t("delete"), on_click=_do_delete).props("color=negative")
    dialog.open()


async def _handle_refresh_schedules(session, dwarf_uid: str, refresh_view: Callable[[], None]) -> None:
    """User-reported (Sep 2026): after a schedule sync succeeds, there was
    no way to see what's actually stored on the device from within
    astro_dwarf_session's own UI at all - not just "was the last sync
    successful", but "what schedules/tasks does the device currently
    think it has, and what state is each one in" (idle/shooting/success/
    failed/...). This reads that directly from the device (CMD_GET_ALL_
    SHOOTING_SCHEDULE) rather than trusting our own bookkeeping, since a
    schedule could have been synced by something else entirely (the
    official app, or a previous astro_dwarf_session run)."""
    if not connection_health.try_acquire_command_slot(dwarf_uid, caller="session.refresh_schedules"):
        _safe_notify(t("device_busy"), type="warning")
        return
    try:
        info = await run.io_bound(perform_get_all_shooting_schedule_full, session=session)
    finally:
        connection_health.release_command_slot(dwarf_uid)

    if info is None:
        _schedules_fetch_error[dwarf_uid] = t("sched_read_error")
        # Deliberately NOT clearing the cache on a failed refresh (user-
        # requested Sep 2026, same reasoning as api_routes.py's own
        # fallback-to-cache behaviour): a transient read failure shouldn't
        # blank out a perfectly good last-known list.
        _safe_notify(t("sched_read_error"), type="negative")
    else:
        _schedules_fetch_error.pop(dwarf_uid, None)
        # Shared parsing (components/native_schedule.py) - state_code is
        # the raw int from the device. BUG FIX (Sep 2026, user-reported
        # KeyError 'state' crash): this used to also stamp a translated
        # "state" label onto each dict before caching - but the SAME
        # cache is also written by api_routes.py's /api/programs (via
        # native_schedule.set_cached()), which never adds that label -
        # whichever caller wrote last decided the cached shape, so this
        # UI could easily render a cache entry with no "state" key at
        # all. The cache now always stays in the canonical (label-free)
        # shape; labels are derived at RENDER time instead (see
        # _schedule_status_text() and the task-line rendering below),
        # from state_code, which is always present.
        parsed = parse_native_schedule_info(info)
        native_schedule.set_cached(dwarf_uid, parsed)
        _schedules_shown_count[dwarf_uid] = 3  # reset paging on every fresh fetch
        # Explicit confirmation (user-reported Sep 2026: "je ne sais pas
        # si la commande a été envoyée (pas de notif)") - this function
        # previously only updated the cache and refreshed the view
        # silently, with no feedback distinguishable from "nothing
        # happened" if the person wasn't staring at the section already.
        _safe_notify(t("sched_refreshed_notify", count=len(parsed)), type="positive")
    _schedules_last_fetch[dwarf_uid] = time.time()
    refresh_view()


async def _handle_sync_pending(session, dwarf_uid: str, refresh_view: Callable[[], None]) -> None:
    """Triggered by the persistent "Pending schedule" banner (shown
    whenever connected + not busy + something is queued) - covers the case
    the connect-time dialog (_offer_pending_schedule_sync) doesn't: a
    schedule arriving while the device was BUSY (a manual/scheduled
    program running - see scheduler_runner's COMMAND SLOT note) rather
    than offline. No reconnect event fires when a run simply finishes, so
    this is checked declaratively on every poll tick instead.

    BUG FIX (Sep 2026, user-reported: "je ne vois pas... envoi en cours,
    erreur ou succès"): this had success/failure _safe_notify() calls
    already, but nothing at all for "in progress" - unlike _handle_
    connect()'s _safe_ongoing_notification (a single persistent, in-place-
    updatable popup with its own spinner). Rebuilt on that same, already-
    proven pattern instead of separate fire-and-forget toasts, which are
    easy to miss individually if the person isn't looking at that exact
    moment.
    """
    if not connection_health.try_acquire_command_slot(dwarf_uid, caller="session.sync_pending"):
        _safe_notify(t("device_busy"), type="warning")
        return
    notification = _safe_ongoing_notification(t("sched_syncing"))
    pending = pending_schedules.get_pending(dwarf_uid)
    try:
        ok = await run.io_bound(perform_sync_shooting_schedule, pending, session=session) if pending else False
    finally:
        connection_health.release_command_slot(dwarf_uid)

    if ok:
        pending_schedules.clear_pending(dwarf_uid)
        _finish_ongoing_notification(notification, t("sched_synced"), "positive")
    else:
        _finish_ongoing_notification(notification, t("sched_sync_failed_retry"), "negative")
    refresh_view()


async def _handle_connect(session, dwarf_uid: str, refresh_view: Callable[[], None]) -> None:
    if not connection_health.try_acquire_command_slot(dwarf_uid, caller="session.connect"):
        _safe_notify(t("device_busy"), type="warning")
        return
    _busy_uids.add(dwarf_uid)
    # ui.notification (not ui.notify): a persistent element we can
    # update in place and dismiss explicitly. type="ongoing" in Quasar
    # has timeout=0 by design (never auto-dismisses) - it's meant to be
    # updated/closed programmatically, which plain ui.notify() calls
    # can't do (each call opens a separate, independent toast).
    notification = _safe_ongoing_notification(t("connecting_in_progress"))
    try:
        success = await connection_health.connect_and_enter_astro_mode(session)
    finally:
        _busy_uids.discard(dwarf_uid)
        connection_health.release_command_slot(dwarf_uid)

    if not success:
        # User-requested (Sep 2026): surface the REAL reason when one is
        # known (currently: DEVICE_OCCUPIED, close code 4409 - another
        # client, likely the official app, already connected) instead of
        # always showing the generic "Connection failed". dwarf_python_
        # api returns a stable CODE (not a hardcoded English sentence -
        # it's a generic library, this app owns translation), mapped via
        # a "conn_error_<code>" key so both languages work. Falls back
        # to the generic message for any code without a mapped key.
        error_code = perform_get_last_connection_error(session=session)
        translation_key = f"conn_error_{error_code.lower()}" if error_code else None
        specific_reason = t(translation_key) if translation_key and translation_key in _known_conn_error_keys else None
        _finish_ongoing_notification(notification, specific_reason or t("connection_failed"), "negative")
    else:
        _finish_ongoing_notification(notification, t("connected"), "positive")
        connection_health.mark_just_connected(dwarf_uid)
        _label_thread_for_device(session)

        pending = pending_schedules.get_pending(dwarf_uid)
        if pending is not None:
            await _offer_pending_schedule_sync(session, dwarf_uid, pending)
    refresh_view()


async def _handle_disconnect(session, dwarf_uid: str, refresh_view: Callable[[], None]) -> None:
    if not connection_health.try_acquire_command_slot(dwarf_uid, caller="session.disconnect"):
        _safe_notify(t("device_busy"), type="warning")
        return
    _busy_uids.add(dwarf_uid)
    thread = getattr(session, "event_loop_thread", None)
    try:
        await run.io_bound(perform_disconnect, session=session)
    finally:
        _busy_uids.discard(dwarf_uid)
        connection_health.release_command_slot(dwarf_uid)
    if thread is not None:
        unregister_thread_device_label(thread.ident)
    connection_health.forget(dwarf_uid)
    connection_health.mark_manual_disconnect(dwarf_uid)  # <-- ADD: suppresses
        # auto_reconnect() until the user reconnects again themselves -
        # otherwise maybe_check() sees is_connected=False right after this
        # and immediately undoes the user's own Disconnect click.
    _safe_notify(t("disconnected"), type="warning")
    refresh_view()


def build_session_page() -> None:
    @ui.page("/session/{dwarf_uid}")
    def session_page(dwarf_uid: str) -> None:
        add_pwa_head_tags()
        apply_theme()
        ui.page_title(f"Astro Dwarf Session - {dwarf_uid}")
        # Responsive width (user-requested Sep 2026: "une seconde taille
        # un peu plus large pour les ecrans larges" - same reasoning as
        # dashboard.py's own container_width, this control page was
        # ALSO stuck at a fixed 448px regardless of screen size before
        # this).
        with ui.column().classes(
            "w-full max-w-md md:max-w-lg lg:max-w-xl xl:max-w-2xl 2xl:max-w-[900px] mx-auto gap-3 p-4"
        ):
            with ui.row().classes("items-center justify-between w-full"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props(
                    "flat round"
                )
                ui.button(
                    t("open_programs"),
                    icon="list_alt",
                    on_click=lambda: ui.navigate.to(f"/session/{dwarf_uid}/programs"),
                ).props("flat")
                ui.button(
                    icon="photo_library",
                    on_click=lambda: ui.navigate.to(f"/session/{dwarf_uid}/explorer"),
                ).props("flat round")
                ui.button(
                    icon="settings",
                    on_click=lambda: ui.navigate.to(f"/session/{dwarf_uid}/settings"),
                ).props("flat round")

            # "Open in Dwarfium" (user-requested Sep 2026: cross-launch
            # links to the companion Dwarfium Scope Archive app) - only
            # shown once configured (settings page), since there's
            # nothing meaningful to link to otherwise. Plain external
            # links (ui.link, new tab) rather than any native-window
            # control - the user explicitly settled on this simpler
            # scope for v1, deferring same-window native navigation.
            #
            # session resolved HERE, independently of session_view()'s
            # own internal `session` below (user-reported Sep 2026:
            # "NameError: name 'session' is not defined" - that name is
            # local to the @ui.refreshable session_view() function
            # further down, not visible at this outer scope where this
            # block was originally placed; a real scoping bug on my
            # part, not a version-mismatch issue like the getattr()
            # guard below addresses). try/except KeyError matches
            # pages/explorer.py's own guard for the same "stale/bad
            # dwarf_uid in the URL" case.
            try:
                _header_session = get_manager().get(dwarf_uid)
            except KeyError:
                _header_session = None

            # getattr(..., "") rather than direct attribute access
            # (user-reported Sep 2026: "AttributeError: 'DwarfConfig'
            # object has no attribute 'dwarfium_base_url'") - these two
            # fields were added to dwarf_python_api's own DwarfConfig
            # alongside this feature, and astro_dwarf_ui can end up
            # slightly ahead of whichever dwarf_python_api version is
            # actually installed, being separate repos - same defensive
            # pattern already used for dwarf_model_id in scheduler_
            # runner.py. Degrades to simply not showing these links
            # rather than crashing the whole session page.
            dwarfium_base_url = getattr(_header_session.config, "dwarfium_base_url", "") if _header_session else ""
            dwarfium_id = getattr(_header_session.config, "dwarfium_id", "") if _header_session else ""
            if dwarfium_base_url and dwarfium_id:
                base = dwarfium_base_url.rstrip("/")
                did = dwarfium_id
                with ui.row().classes("items-center gap-3 -mt-1"):
                    ui.link(t("open_in_dwarfium_config"), f"{base}/Dwarf?DwarfId={did}", new_tab=True).classes(
                        "text-xs"
                    )
                    ui.link(
                        t("open_in_dwarfium_explore"), f"{base}/Explore/?DwarfId={did}", new_tab=True
                    ).classes("text-xs")

            # Defined HERE, inside the page function, not at module
            # level - see the module docstring for why: this gives THIS
            # page load its own private refreshable object, so its
            # refresh() can never repaint another device's page.
            @ui.refreshable
            def session_view() -> None:
                try:
                    manager = get_manager()
                    try:
                        session = manager.get(dwarf_uid)
                    except KeyError:
                        ui.label(t("unknown_dwarf", dwarf_uid=dwarf_uid)).classes(
                            "text-red-800"
                        )
                        return

                    full_status: dict = {}
                    if session.is_connected:
                        full_status = get_client_status(session).get("fullStatus", {})

                    error = full_status.get("ErrorConnection")
                    capturing = (
                        full_status.get("AstroCapture")
                        or full_status.get("takePhotoStarted")
                        or full_status.get("takeWidePhotoStarted")
                    )

                    # session.is_connected only reflects whether a
                    # client_instance/websocket OBJECT still exists - it
                    # does NOT get cleared when a single command times out
                    # mid-session (confirmed in dwarf_python_api's
                    # send_socket_message(): the ERROR_TIMEOUT branch never
                    # calls stop_event_loop(), unlike the DISCONNECTED
                    # branch right above it). connection_health actively
                    # re-verifies this with a real round-trip command every
                    # ~12s - see components/connection_health.py.
                    connected = connection_health.is_actually_connected(session)
                    connection_lost = session.is_connected and not connected

                    # --- Header: identity + connection state --------------
                    with ui.row().classes("items-center gap-2 w-full"):
                        ui.icon("satellite_alt").classes("text-2xl text-grey-6")
                        with ui.column().classes("gap-0 flex-1"):
                            ui.label(session.dwarf_uid).classes("font-medium")
                            ui.label(session.config.dwarf_ip or t("unknown_ip")).classes(
                                "text-xs text-grey-6"
                            )
                        ui.icon("circle").classes(
                            f"text-xs text-{_connection_color(connected)}"
                        )

                    # --- Status banner --------------------------------------
                    program_running = scheduler_runner.is_running(dwarf_uid)
                    if error:
                        status_banner(t("error_with_detail", error=error), kind="danger")
                    elif capturing:
                        stacked = (
                            full_status.get("takePhotoStacked", 0)
                            or full_status.get("takeWidePhotoStacked", 0)
                            or full_status.get("takeMosaicStacked", 0)
                        )

                        count = (
                            full_status.get("takePhotoCount", 0)
                            or full_status.get("takeWidePhotoCount", 0)
                            or full_status.get("takeMosaicCount", 0)
                        )
                        status_banner(
                            t("astro_capture_in_progress", stacked=stacked, count=count),
                            kind="info",
                        )
                    elif program_running:
                        # Covers the goto/calibration/camera-setup phases
                        # of a scheduled program, BEFORE actual capturing
                        # starts (user-reported: those phases had no
                        # visible indicator at all before this, only
                        # showing up on the Programs page's own step log
                        # at the bottom) - scheduler_runner.is_running()
                        # is a cheap in-memory flag, safe on every poll tick.
                        status_banner(t("program_running_banner"), kind="info")
                    elif connection_lost:
                        status_banner(t("connection_lost"), kind="danger")
                    elif session.is_connected:
                        status_banner(t("connected"), kind="success")
                    else:
                        status_banner(t("disconnected"), kind="warning")

                    # --- Pending schedule (declarative, checked every poll
                    # tick — covers BOTH "was offline, just connected" and
                    # "was busy running a manual/scheduled program, just
                    # freed up" cases; the latter has no reconnect event to
                    # hook, hence checking state here rather than only at
                    # connect time in _handle_connect/_handle_reconnect. ---
                    pending_sched = pending_schedules.get_pending(dwarf_uid)
                    if pending_sched:
                        # BUG FIX (Sep 2026, user-reported: "il va falloir
                        # un bouton pour supprimer les programmes en
                        # attente"): Discard already existed but was
                        # gated behind the SAME connected+idle condition
                        # as Sync now - so a stale/wrong pending schedule
                        # couldn't be cleared at all while offline or
                        # busy, even though discarding is purely local
                        # (pending_schedules.py) and needs no live
                        # connection whatsoever. The banner (and Discard)
                        # now always shows when something is pending;
                        # only "Sync now" itself still needs the device
                        # connected and idle.
                        can_sync_now = connected and not program_running and not capturing
                        with ui.row().classes("items-center gap-2 w-full"):
                            ui.icon("schedule").classes("text-amber-6")
                            ui.label(
                                t(
                                    "sched_pending_banner",
                                    name=pending_sched.get("scheduleName", t("sched_unnamed")),
                                    count=len(pending_sched.get("shooting_tasks", [])),
                                )
                            ).classes("text-sm flex-1")
                            if can_sync_now:
                                ui.button(
                                    t("sched_sync_now"),
                                    on_click=lambda: _handle_sync_pending(
                                        session, dwarf_uid, refresh_view_and_camera_settings
                                    ),
                                ).props("dense flat color=primary")
                            ui.button(
                                t("discard"),
                                on_click=lambda: (
                                    pending_schedules.clear_pending(dwarf_uid),
                                    refresh_view_and_camera_settings(),
                                ),
                            ).props("dense flat color=negative")

                    # --- Connection ------------------------------------------
                    with ui.row().classes("w-full gap-2"):
                        if connection_lost:
                            ui.button(
                                t("reconnect"),
                                icon="refresh",
                                on_click=lambda: _handle_reconnect(
                                    session, dwarf_uid, refresh_view_and_camera_settings
                                ),
                            ).props("color=negative")
                        elif session.is_connected:
                            ui.button(
                                t("disconnect"),
                                icon="link_off",
                                on_click=lambda: _handle_disconnect(
                                    session, dwarf_uid, refresh_view_and_camera_settings
                                ),
                            ).props("flat color=negative")
                        else:
                            ui.button(
                                t("connect"),
                                icon="link",
                                on_click=lambda: _handle_connect(
                                    session, dwarf_uid, refresh_view_and_camera_settings
                                ),
                            ).props("color=primary")

                    # --- Hardware status --------------------------------------
                    if session.is_connected:
                        with ui.row().classes("w-full gap-2"):
                            battery = full_status.get("BatteryLevelDwarf")
                            _metric_card(
                                t("battery"), battery, "%",
                                is_low=battery is not None and battery < 15,
                            )
                            _metric_card(
                                t("temperature"),
                                full_status.get("TemperatureLevelDwarf"),
                                "\u00b0C",
                            )
                        with ui.row().classes("w-full gap-2"):
                            available = full_status.get("availableSizeDwarf")
                            total = full_status.get("totalSizeDwarf")
                            _metric_card(
                                t("free_storage"), available, "GB" if available else "",
                                is_low=available is not None and available < 15,
                            )
                            _metric_card(
                                t("total_storage"), total, "GB" if total else ""
                            )

                    # Actions (capture, lights, focus, calibration, EQ
                    # solving, reboot...) live in their own separate,
                    # collapsible, NOT-auto-refreshing section built by
                    # session_page() below (see components/
                    # actions_section.py's module docstring for why: an
                    # expansion's open/closed state and any button mid-
                    # click would otherwise be reset every ~2s by this
                    # view's own refresh cycle).

                    # Camera settings (exposure/gain, tele/wide) live in
                    # their own separate, NOT-auto-refreshing container
                    # built by session_page() below (see
                    # components/camera_settings.py's module docstring
                    # for why: an interactive control torn down every
                    # ~2s by this view's own refresh cycle would lose
                    # focus / close mid-edit).
                except Exception as e:
                    # Defensive: a refreshable's body runs as a
                    # NiceGUI "fire and forget" background task when
                    # called from refresh() - an unhandled exception in
                    # here would otherwise fail SILENTLY, leaving the
                    # previous (stale) content on screen with no clue
                    # why it never updated. Log loudly and show
                    # something rather than nothing.
                    import traceback

                    print(f"[session_view] error rendering {dwarf_uid}: {e}")
                    traceback.print_exc()
                    status_banner(f"UI error: {e}", kind="danger")

            session_view()

            # Camera settings: a SEPARATE, non-auto-refreshing container
            # (see components/camera_settings.py's module docstring) -
            # rebuilt only right after a successful connect/reconnect,
            # via refresh_camera_settings() below, not on every 2s poll
            # tick like session_view.
            camera_settings_container = ui.column().classes("w-full")

            def refresh_camera_settings() -> None:
                camera_settings_container.clear()
                try:
                    current_session = get_manager().get(dwarf_uid)
                except KeyError:
                    return
                if current_session.is_connected:
                    with camera_settings_container:
                        build_camera_settings(current_session)

            refresh_camera_settings()

            # Actions (capture, lights, focus, calibration, EQ solving,
            # reboot...): also built once, not on the 2s poll - see
            # components/actions_section.py's module docstring for why
            # (an expansion's collapsed/expanded state would otherwise
            # reset every tick). Shown regardless of live connection
            # state, same reasoning as the Program section below: a
            # command just fails gracefully (device_busy/command_failed
            # notification) if attempted while not actually connected.
            #
            # `session` is only in scope INSIDE session_view() above (a
            # nested function) - not here, in session_page()'s own body -
            # so it must be re-fetched locally, same pattern as
            # refresh_camera_settings()/program_session below.
            try:
                actions_session = get_manager().get(dwarf_uid)
            except KeyError:
                actions_session = None
            if actions_session is not None:
                build_actions_section(actions_session, session_view.refresh)
                build_camera_stream_section(actions_session)
                with ui.card().classes("w-full p-0"), ui.expansion(t("motor_pad_title"), icon="control_camera").classes("w-full"):
                    build_motor_pad(actions_session)

                    with ui.card().classes("w-full p-0 mt-2"), ui.expansion("Motor axis positioning (advanced)", icon="tune").classes("w-full"):
                        build_motor_position_tool(actions_session)

            # --- Shooting schedule (on device) — user-reported
            # (Sep 2026): no visibility anywhere in the UI into
            # what's actually stored on the device after a sync,
            # or whether it's idle/running/succeeded/failed. Reads
            # straight from the device (not our own bookkeeping) -
            # manual refresh only, not polled every tick, since
            # it's a real device round-trip.
            #
            # BUG FIX (Sep 2026, user-reported: "je ne vois rien... il
            # faut changer de page"): this used to be plain inline code
            # in session_page()'s own "built once" section - clicking
            # Refresh correctly updated _schedules_cache server-side,
            # but refresh_view_and_camera_settings() only ever calls
            # session_view.refresh()/refresh_camera_settings(), NEITHER
            # of which touches this block, so the new data never
            # actually got drawn (matching "toggling the expansion does
            # nothing either" - its children were built once, at page-
            # load time, and never told to rebuild). Needs its OWN
            # @ui.refreshable - and per the module docstring above, that
            # MUST be defined HERE, inside session_page(), not at module
            # level, for the exact same cross-device-bleeding reason
            # session_view already had to be fixed for.
            @ui.refreshable
            def shooting_schedule_view() -> None:
                with ui.card().classes("w-full p-0"), ui.expansion(
                    t("sched_section_title"), icon="event_note",
                ).classes("w-full").bind_value(_get_schedule_section_box(dwarf_uid), "value"):
                    last_fetch = _schedules_last_fetch.get(dwarf_uid)
                    if last_fetch:
                        ui.label(
                            t("sched_last_checked", time=datetime.fromtimestamp(last_fetch).strftime("%H:%M:%S"))
                        ).classes("text-xs text-grey-6")
                    fetch_err = _schedules_fetch_error.get(dwarf_uid)
                    cached_scheds = native_schedule.get_cached(dwarf_uid)
                    if fetch_err:
                        ui.label(fetch_err).classes("text-negative text-sm")
                    elif cached_scheds is None:
                        ui.label(t("sched_not_checked_yet")).classes("text-sm text-grey-6")
                    elif not cached_scheds:
                        ui.label(t("sched_none_stored")).classes("text-sm text-grey-6")
                    else:
                        shown = _schedules_shown_count.get(dwarf_uid, 3)
                        for sc in cached_scheds[:shown]:
                            with ui.card().classes("w-full q-pa-sm q-mb-xs"):
                                with ui.row().classes("w-full items-center gap-2"):
                                    ui.label(f"{sc['name']} — {_schedule_status_text(sc)}").classes("font-medium text-sm flex-1")
                                    ui.button(
                                        icon="delete",
                                        on_click=lambda _, sid=sc["scheduleId"], sname=sc["name"]: _handle_delete_schedule(
                                            actions_session, dwarf_uid, sid, sname, shooting_schedule_view.refresh
                                        ),
                                    ).props("flat dense round size=sm color=negative")
                                for tsk in sc["tasks"]:
                                    detail_bits = []
                                    if tsk.get("startTime"):
                                        dt = datetime.fromtimestamp(tsk["startTime"])
                                        detail_bits.append(f"[{dt:%Y-%m-%d %H:%M}")
                                    if tsk.get("endTime"):
                                        dt = datetime.fromtimestamp(tsk["endTime"])
                                        detail_bits.append(f" - {dt:%H:%M}]")
                                    if tsk.get("shutterName"):
                                        detail_bits.append(f"{tsk['shutterName']}s")
                                    if tsk.get("gainName"):
                                        detail_bits.append(f"gain {tsk['gainName']}")
                                    if tsk.get("filterModeName"):
                                        detail_bits.append(tsk["filterModeName"])
                                    # count/stacked deliberately NOT shown
                                    # (user-reported Sep 2026, confirmed by
                                    # a real screenshot: always "0 imgs /
                                    # 0 stacked" - these come from the
                                    # task's stored params JSON, which
                                    # reflects what was last SYNCED, not
                                    # live capture progress - same finding
                                    # as the combined /Program page's own
                                    # native task rendering).
                                    detail = " · ".join(str(b) for b in detail_bits if b)
                                    line = f"• {tsk['name']}: {_task_state_label(tsk['state_code'])}"
                                    if detail:
                                        line += f" ({detail})"
                                    ui.label(line).classes("text-xs text-grey-7")
                        if len(cached_scheds) > shown:
                            ui.button(
                                t("sched_show_more", count=len(cached_scheds) - shown),
                                on_click=lambda: (
                                    _schedules_shown_count.__setitem__(dwarf_uid, shown + 3),
                                    shooting_schedule_view.refresh(),
                                ),
                            ).props("dense flat size=sm")
                    ui.button(
                        t("sched_refresh"),
                        on_click=lambda: _handle_refresh_schedules(
                            actions_session, dwarf_uid, shooting_schedule_view.refresh
                        ),
                    ).props("dense flat")

            shooting_schedule_view()

            # Program (scheduler): also built once, not on the 2s poll -
            # it holds its own upload widget + a running program's live
            # step log, neither of which should be torn down every tick.
            # Unlike camera settings, it's shown regardless of live
            # connection state (a program can be uploaded ahead of time;
            # start_run() itself will simply fail fast if the device
            # isn't actually connected when Start is pressed).
            try:
                program_session = get_manager().get(dwarf_uid)
            except KeyError:
                program_session = None
            if program_session is not None:
                build_program_section(program_session)

            def refresh_view_and_camera_settings() -> None:
                session_view.refresh()
                refresh_camera_settings()

            async def poll() -> None:
                if dwarf_uid in _busy_uids:
                    return
                try:
                    session = get_manager().get(dwarf_uid)
                except KeyError:
                    return
                await connection_health.maybe_check(session)
                session_view.refresh()

                # Hide Camera Settings while a program is actively
                # running (user-requested, Sep 2026): it's not relevant
                # during execution, and de-clutters the page down to
                # just the running program's name + trace (see
                # components/program_section.py's own simplified view
                # for the same reasoning).
                camera_settings_container.set_visibility(
                    not scheduler_runner.is_running(dwarf_uid)
                )

            ui.timer(2.0, poll)