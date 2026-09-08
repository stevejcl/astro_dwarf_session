"""Quick actions section for the session page - collapsed by default,
built ONCE per page load (same reasoning as camera_settings.py and
program_section.py) rather than inside session_view's auto-refreshing
body: an ui.expansion's open/closed state would otherwise get reset
every ~2s poll tick, along with any button mid-interaction.

Toggle Lights / Focus Infinite / Calibrate / Polar Position / EQ Solving
/ Reboot are ported from astro_dwarf_session_UI.py's own buttons -
verified against that source, not guessed:
- Toggle Lights: perform_powerOpenRGB()/perform_powerCloseRGB() - there's
  no status field to read the light's current state back from the
  device, so this module tracks it itself (in-memory, per dwarf_uid,
  reset on app restart).
- Focus Infinite: perform_start_autofocus(infinite=True, ...).
- Calibrate: perform_calibration().
- Polar Position: NOT a single perform_* call - astro_dwarf_session_UI.
  py's run_start_polar_position() runs a specific motor_action()
  sequence (reset rotation/pitch motors, then position them, with
  different motor codes for D3 vs older models) - motor_action()
  doesn't follow the perform_* naming convention (a known trap for
  grep-based searches, see project notes), ported here as
  _polar_position_sequence().
- EQ Solving: start_polar_align() (dwarf_python_api).
- Reboot: perform_reboot() - destructive, gated behind a confirmation
  dialog before actually sending it."""
from __future__ import annotations

import asyncio
from typing import Callable

from nicegui import run, ui

from dwarf_python_api.get_config_data import config_to_dwarf_id_int
from dwarf_python_api.lib.dwarf_session_socket import get_client_status
from dwarf_python_api.lib.dwarf_utils import (
    motor_action,
    perform_calibration,
    perform_powerCloseRGB,
    perform_powerOpenRGB,
    perform_reboot,
    perform_start_autofocus,
    perform_stop_goto,
    perform_stopAstroPhoto,
    perform_takeAstroPhoto,
    start_polar_align,
)

from components import connection_health
from components.i18n import t

# In-memory only - no field in get_client_status()'s fullStatus reports
# the RGB light's current on/off state, so there's nothing to read back
# from the device to stay in sync with. Resets to "assumed off" on app
# restart.
_lights_on: dict[str, bool] = {}


def _build_eq_result_panel(session) -> Callable[[], None]:
    """Persistent EQ Solving result panel (user-requested Sep 2026,
    ported from Dwarfium's own EQ-result UI - not a transient toast,
    since the user needs to glance back at this repeatedly while
    physically turning azimuth/altitude knobs, matching Dwarfium's own
    choice of a persistent panel over a notification).

    Icon direction and colour scheme is a faithful port of Dwarfium's
    own JSX (bi-arrow-clockwise/counterclockwise for azimuth mapped to
    Material's rotate_right/rotate_left, bi-arrow-up/down mapped to
    arrow_upward/arrow_downward) - confirmed against the official
    protocol docs' own field comments (azi_err: positive=clockwise,
    negative=counter-clockwise; alt_err: positive=up, negative=down),
    not guessed. Absolute value shown (sign is conveyed by the icon/
    colour, not by a +/- prefix), matching Dwarfium's own
    Math.abs(...).toFixed(2).

    Hidden until the first EQ Solving result is available, then stays
    visible with the LAST known reading (does not clear itself, so the
    user can keep referring back to it between successive adjustment/
    re-check cycles).

    Returns an `update()` callback the caller runs after each EQ
    Solving attempt completes."""
    with ui.row().classes("items-center gap-4 flex-wrap") as panel:
        with ui.row().classes("items-center gap-2") as azi_row:
            azi_icon = ui.icon("rotate_right").classes("text-lg")
            azi_label = ui.label("")
        with ui.row().classes("items-center gap-2") as alt_row:
            alt_icon = ui.icon("arrow_upward").classes("text-lg")
            alt_label = ui.label("")
    panel.set_visibility(False)

    def update() -> None:
        full_status = get_client_status(session).get("fullStatus", {})
        azi_err = full_status.get("eqAziErr")
        alt_err = full_status.get("eqAltErr")
        if azi_err is None or alt_err is None:
            return
        panel.set_visibility(True)

        if azi_err > 0:
            azi_icon.name = "rotate_right"
            azi_icon.classes(replace="text-lg text-positive")
        else:
            azi_icon.name = "rotate_left"
            azi_icon.classes(replace="text-lg text-negative")
        azi_label.set_text(f"{abs(azi_err):.2f}\u00b0 {t('action_eq_solving_azimuth')}")

        if alt_err > 0:
            alt_icon.name = "arrow_upward"
            alt_icon.classes(replace="text-lg text-positive")
        else:
            alt_icon.name = "arrow_downward"
            alt_icon.classes(replace="text-lg text-negative")
        alt_label.set_text(f"{abs(alt_err):.2f}\u00b0 {t('action_eq_solving_altitude')}")

    return update


async def _run_and_notify(
    session,
    dwarf_uid,
    fn,
    *,
    success_message: str,
    success_message_fn: Callable[[], str] | None = None,
    refresh_view=None,
    display_duration: float = 2.0,
    **kwargs,
) -> None:
    if not connection_health.try_acquire_command_slot(dwarf_uid):
        ui.notify(t("device_busy"), type="warning")
        return

    notification = ui.notification(
        t("command_in_progress"), type="ongoing", spinner=True, timeout=None
    )
    try:
        result = await run.io_bound(fn, session=session, **kwargs)
    finally:
        connection_health.release_command_slot(dwarf_uid)

    notification.spinner = False
    # is not False, NOT a plain truthy check: some of the perform_*
    # functions called through here (start_polar_align in particular)
    # return the protocol response code directly on success, and 0
    # (OK) is a valid success value that happens to be Python-falsy -
    # `if result:` would misreport a genuine success as a failure.
    # Others already normalize to True/False internally, for which
    # `is not False` behaves identically - safe either way.
    success = result is not False
    if success:
        notification.message = success_message_fn() if success_message_fn else success_message
        notification.type = "positive"
    else:
        notification.message = t("command_failed")
        notification.type = "negative"
    if refresh_view:
        refresh_view()
    await asyncio.sleep(display_duration)
    notification.dismiss()


def _polar_position_sequence(session) -> bool:
    """Runs entirely on the run.io_bound() worker thread - a faithful
    port of astro_dwarf_session_UI.py's run_start_polar_position(),
    single attempt (the original retries once with a 10s sleep between
    attempts; left as a single try here since a UI button can just be
    pressed again if it fails, rather than silently blocking for 10s+
    inside one click)."""
    dwarf_id_int = config_to_dwarf_id_int(session.config.dwarf_model_id) or 2

    if not motor_action(5, session=session):  # Rotation motor reset
        return False
    if not motor_action(6, session=session):  # Pitch motor reset
        return False

    if dwarf_id_int >= 3:
        if not motor_action(9, session=session):  # Rotation positioning (D3)
            return False
        return bool(motor_action(7, session=session))  # Pitch positioning (D3)
    else:
        if not motor_action(2, session=session):  # Rotation positioning
            return False
        return bool(motor_action(3, session=session))  # Pitch positioning


async def _handle_toggle_lights(session, dwarf_uid) -> None:
    is_on = _lights_on.get(dwarf_uid, False)
    fn = perform_powerCloseRGB if is_on else perform_powerOpenRGB

    if not connection_health.try_acquire_command_slot(dwarf_uid):
        ui.notify(t("device_busy"), type="warning")
        return
    try:
        result = await run.io_bound(fn, session=session)
    finally:
        connection_health.release_command_slot(dwarf_uid)

    # is not False, not a plain truthy check - perform_powerOpenRGB/
    # perform_powerCloseRGB return the raw response value (>= 0) on
    # success via get_result_value(), and 0 is a valid success value
    # that's Python-falsy. See _run_and_notify() above for the same fix.
    if result is not False:
        _lights_on[dwarf_uid] = not is_on
        ui.notify(t("lights_off_done") if is_on else t("lights_on_done"), type="positive")
    else:
        ui.notify(t("command_failed"), type="negative")


async def _handle_reboot(session, dwarf_uid) -> None:
    with ui.dialog() as dialog, ui.card():
        ui.label(t("reboot_confirm"))
        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button(t("cancel"), on_click=dialog.close).props("flat")

            async def _confirmed() -> None:
                dialog.close()
                await _run_and_notify(
                    session, dwarf_uid, perform_reboot, success_message=t("reboot_sent")
                )

            ui.button(t("reboot_confirm_button"), on_click=_confirmed).props(
                "color=negative"
            )
    dialog.open()


def build_actions_section(session, refresh_view) -> None:
    """Call once per page load. refresh_view: the session page's own
    session_view.refresh (see pages/session.py) - called after an action
    so capture/status changes show up immediately rather than waiting
    for the next ~2s poll tick."""
    dwarf_uid = session.dwarf_uid
    # Placeholder reassigned below, after the button row, to the real
    # panel-update callback from _build_eq_result_panel() - the EQ
    # Solving button's on_click (built first) looks this name up in the
    # enclosing scope only when actually CLICKED, by which point the
    # reassignment below has already run, so this ordering is safe
    # despite the button being defined before the panel it triggers.
    eq_result_update: Callable[[], None] = lambda: None

    with ui.expansion(t("actions"), icon="tune", value=False).classes("w-full"):
        with ui.row().classes("w-full gap-2 flex-wrap"):
            ui.button(
                t("start_astro_capture"),
                icon="play_arrow",
                on_click=lambda: _run_and_notify(
                    session,
                    dwarf_uid,
                    perform_takeAstroPhoto,
                    success_message=t("astro_capture_started"),
                    refresh_view=refresh_view,
                ),
            ).props("flat")
            ui.button(
                t("stop_capture"),
                icon="stop",
                on_click=lambda: _run_and_notify(
                    session,
                    dwarf_uid,
                    perform_stopAstroPhoto,
                    success_message=t("astro_capture_stopped"),
                    refresh_view=refresh_view,
                ),
            ).props("flat")
            ui.button(
                t("stop_goto"),
                icon="gps_off",
                on_click=lambda: _run_and_notify(
                    session,
                    dwarf_uid,
                    perform_stop_goto,
                    success_message=t("goto_stopped"),
                    refresh_view=refresh_view,
                ),
            ).props("flat")
            ui.button(
                t("action_toggle_lights"),
                icon="lightbulb",
                on_click=lambda: _handle_toggle_lights(session, dwarf_uid),
            ).props("flat")
            ui.button(
                t("action_focus_infinite"),
                icon="all_out",
                on_click=lambda: _run_and_notify(
                    session,
                    dwarf_uid,
                    perform_start_autofocus,
                    infinite=True,
                    success_message=t("action_focus_infinite_done"),
                ),
            ).props("flat")
            ui.button(
                t("action_calibrate"),
                icon="tune",
                on_click=lambda: _run_and_notify(
                    session,
                    dwarf_uid,
                    perform_calibration,
                    success_message=t("action_calibrate_done"),
                ),
            ).props("flat")
            ui.button(
                t("action_polar_position"),
                icon="explore",
                on_click=lambda: _run_and_notify(
                    session,
                    dwarf_uid,
                    _polar_position_sequence,
                    success_message=t("action_polar_position_done"),
                ),
            ).props("flat")
            ui.button(
                t("action_eq_solving"),
                icon="my_location",
                on_click=lambda: _run_and_notify(
                    session,
                    dwarf_uid,
                    start_polar_align,
                    success_message=t("action_eq_solving_done"),
                    refresh_view=eq_result_update,
                ),
            ).props("flat")
            ui.button(
                t("action_reboot"),
                icon="restart_alt",
                on_click=lambda: _handle_reboot(session, dwarf_uid),
            ).props("flat color=negative")

        eq_result_update = _build_eq_result_panel(session)
