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
from typing import Callable

from nicegui import run, ui

from dwarf_python_api.lib.dwarf_session import get_manager
from dwarf_python_api.lib.dwarf_session_socket import get_client_status
from dwarf_python_api.lib.dwarf_utils import perform_disconnect
from dwarf_python_api.lib.my_logger import (
    register_thread_device_label,
    unregister_thread_device_label,
)

from components import connection_health, scheduler_runner
from components.actions_section import build_actions_section
from components.camera_stream import build_camera_stream_section
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


def _metric_card(label: str, value, unit: str) -> None:
    with ui.card().classes("flex-1 items-center"):
        ui.label(label).classes("text-xs text-grey-6")
        ui.label(f"{value if value is not None else '\u2013'}{unit}").classes(
            "text-lg font-medium"
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


async def _handle_connect(session, dwarf_uid: str, refresh_view: Callable[[], None]) -> None:
    if not connection_health.try_acquire_command_slot(dwarf_uid):
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

    notification.spinner = False
    if not success:
        notification.message = t("connection_failed")
        notification.type = "negative"
    else:
        notification.message = t("connected")
        notification.type = "positive"
        connection_health.mark_just_connected(dwarf_uid)
        _label_thread_for_device(session)
    refresh_view()

    # A direct asyncio.sleep + dismiss() call, NOT a ui.timer: dismiss()
    # only needs the notification's own bound client (see Element.
    # run_method, which reads self.client, never context.client), so
    # it works fine here with no active UI slot at all. A ui.timer
    # would instead be a NEW element created in whatever slot happens
    # to be current at this point - if the periodic page refresh
    # deletes that slot before the timer's first tick, dismiss() is
    # simply never called and the popup is stuck forever (this is what
    # was actually happening).
    await asyncio.sleep(2.0)
    notification.dismiss()


async def _handle_disconnect(session, dwarf_uid: str, refresh_view: Callable[[], None]) -> None:
    if not connection_health.try_acquire_command_slot(dwarf_uid):
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
    _safe_notify(t("disconnected"), type="warning")
    refresh_view()


async def _handle_reconnect(session, dwarf_uid: str, refresh_view: Callable[[], None]) -> None:
    """For the connection_lost case: session.client_instance is still
    set to a dead connection, so a plain 'connect' call would just
    reuse it and time out again (connect_socket() only goes through
    init_socket() when client_instance is None/start_client is False).
    A real reconnect needs a clean disconnect first."""
    if not connection_health.try_acquire_command_slot(dwarf_uid):
        _safe_notify(t("device_busy"), type="warning")
        return
    _busy_uids.add(dwarf_uid)
    old_thread = getattr(session, "event_loop_thread", None)
    notification = _safe_ongoing_notification(t("reconnecting_in_progress"))
    try:
        await run.io_bound(perform_disconnect, session=session)
        if old_thread is not None:
            unregister_thread_device_label(old_thread.ident)
        success = await connection_health.connect_and_enter_astro_mode(session)
    finally:
        _busy_uids.discard(dwarf_uid)
        connection_health.release_command_slot(dwarf_uid)

    notification.spinner = False
    if not success:
        notification.message = t("connection_failed")
        notification.type = "negative"
    else:
        notification.message = t("connected")
        notification.type = "positive"
        connection_health.mark_just_connected(dwarf_uid)
        _label_thread_for_device(session)
    refresh_view()
    await asyncio.sleep(2.0)
    notification.dismiss()


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
                            _metric_card(
                                t("battery"), full_status.get("BatteryLevelDwarf"), "%"
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
                                t("free_storage"), available, "GB" if available else ""
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
