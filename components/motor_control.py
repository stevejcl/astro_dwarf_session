"""Manual directional pad to orient/position the Dwarf's mount BEFORE
starting a session (native schedule or program) - user-requested (Sep
2026), mirroring the joystick control already used in the dwarfium
React project (components/imaging/CameraJoystick.tsx there), but built
around dwarf_python_api's EXISTING perform_motor_joystick_v3()/
perform_motor_joystick_stop_v3() (CMD_STEP_MOTOR_SERVICE_JOYSTICK,
14006/14008) - nothing new needed on the protocol side.

MOVEMENT SEMANTICS (user-corrected Sep 2026, live testing): a SINGLE
perform_motor_joystick_v3() call starts a CONTINUOUS movement in that
direction - the mount keeps slewing until perform_motor_joystick_stop_v3()
is called, not just for an instant. No repeated re-sending needed while
held (an earlier version of this file re-sent every 0.4s, which was
unnecessary and risked queuing redundant commands) - one call on press,
one call on release, matching how the button is actually held.

Placed next to the live camera preview (see pages/session.py, right
after build_camera_stream_section()) - user-requested (Sep 2026): "à
côté de la vue vidéo pour avoir un retour image" - nudging blind, with
no visual feedback of where the mount is pointing, isn't useful.
"""
from __future__ import annotations

import asyncio

from nicegui import run, ui

from components import connection_health
from components.i18n import t
from dwarf_python_api.lib.dwarf_utils import perform_motor_joystick_v3, perform_motor_joystick_stop_v3
from dwarf_python_api.lib.dwarf_utils import perform_get_motor_position_full, perform_motor_run_to_v3, motor_action

# Angles to SEND to perform_motor_joystick_v3 for each displayed
# direction - user-confirmed (Sep 2026, live device test) that the
# naive "0=N, clockwise" convention was wrong: pressing the button
# shown as Up actually moved the mount Right, Right actually moved Up,
# Down actually moved Left, Left actually moved Down. That's a
# reflection (not a simple rotation) - solved from the observed pairs
# as actual_angle = (90 - sent_angle) mod 360, then inverted to get the
# sent_angle that produces the INTENDED actual_angle for each button:
#     sent_angle = (90 - intended_angle) mod 360
# NE/SW sit exactly on the mirror axis and were already correct by
# coincidence; N/E/S/W and NW/SE all needed correcting.
_DIRECTIONS = {
    "N":  90,
    "NE": 45,
    "E":  0,
    "SE": 315,
    "S":  270,
    "SW": 225,
    "W":  180,
    "NW": 135,
}
_DIRECTION_ICONS = {
    "N": "keyboard_arrow_up", "NE": "north_east", "E": "keyboard_arrow_right",
    "SE": "south_east", "S": "keyboard_arrow_down", "SW": "south_west",
    "W": "keyboard_arrow_left", "NW": "north_west",
}
_GRID_ORDER = ["NW", "N", "NE", "W", None, "E", "SW", "S", "SE"]


def build_motor_pad(session) -> None:
    """Call once, inline in a page (same pattern as build_camera_settings()
    and the other build_*() components)."""
    dwarf_uid = session.dwarf_uid
    speed_input = ui.slider(min=0.05, max=1.0, step=0.05, value=0.3).props("label-always")
    ui.label(t("motor_pad_speed_hint")).classes("text-xs text-grey-6 -mt-2")

    moving = {"active": False}  # guards against a stray extra start/stop pair

    async def _stop() -> None:
        if not moving["active"]:
            return  # already stopped - e.g. mouseup firing right after mouseleave already handled it
        # SAFETY-CRITICAL (user-reported Sep 2026: "le dwarf bouge mais
        # ne s'arrête pas" - field-confirmed via the log: every single
        # stop attempt was silently denied because the slot was still
        # held by the start command's own in-flight round-trip, and this
        # function just gave up instead of retrying - the mount kept
        # moving because the stop request never once reached the
        # device). Unlike start, a stop must NOT give up on the first
        # busy slot - retry for a few seconds rather than silently
        # leaving the mount slewing.
        for _ in range(50):  # up to ~5s
            if connection_health.try_acquire_command_slot(dwarf_uid, caller="motor_pad.stop"):
                break
            await asyncio.sleep(0.1)
        else:
            status_label.set_text(t("motor_pad_stop_failed"))
            status_label.classes(replace="text-xs text-red-700")
            return  # moving["active"] stays True - a follow-up press/release can retry
        try:
            await run.io_bound(perform_motor_joystick_stop_v3, session=session)
        finally:
            connection_health.release_command_slot(dwarf_uid)
        moving["active"] = False
        status_label.set_text("")

    async def _start(angle: int) -> None:
        if moving["active"]:
            await _stop()  # switching direction mid-press - stop the previous one first
        moving["active"] = True
        if not connection_health.try_acquire_command_slot(dwarf_uid, caller="motor_pad.start"):
            moving["active"] = False
            status_label.set_text(t("device_busy"))
            status_label.classes(replace="text-xs text-red-700")
            return
        try:
            ok = await run.io_bound(perform_motor_joystick_v3, angle, speed_input.value, session=session)
        finally:
            connection_health.release_command_slot(dwarf_uid)
        if ok is False:
            moving["active"] = False
            status_label.set_text(t("motor_pad_error"))
            status_label.classes(replace="text-xs text-red-700")
        else:
            status_label.set_text(t("motor_pad_moving"))
            status_label.classes(replace="text-xs text-grey-6")

    with ui.grid(columns=3).classes("w-48 gap-1 mx-auto"):
        for cell in _GRID_ORDER:
            if cell is None:
                ui.button(icon="stop", on_click=_stop).props("round color=negative").classes("w-12 h-12")
                continue
            angle = _DIRECTIONS[cell]
            btn = ui.button(icon=_DIRECTION_ICONS[cell]).props("round outline").classes("w-12 h-12")
            # press-and-hold: start on press, stop on release OR if the
            # pointer/finger leaves the button without a clean "up"
            # (mouseleave/touchcancel) - otherwise a drag-off would leave
            # the mount slewing with no way to stop it from the pad.
            btn.on("mousedown", lambda _, a=angle: _start(a))
            btn.on("touchstart", lambda _, a=angle: _start(a))
            btn.on("mouseup", lambda _: _stop())
            btn.on("mouseleave", lambda _: _stop())
            btn.on("touchend", lambda _: _stop())
            btn.on("touchcancel", lambda _: _stop())

    ui.label(t("motor_pad_hint")).classes("text-xs text-grey-6 text-center")
    # Fixed height reserved (user-reported Sep 2026: "l'info motor_pad_
    # moving doit être en dessous pour éviter de bouger le pad" - text
    # appearing/disappearing here was reflowing the pad above it,
    # shifting the buttons out from under a finger/cursor mid-press).
    # Below the grid AND the hint text now, with min-height so its own
    # appearance/disappearance never moves anything else either.
    status_label = ui.label("").classes("text-xs text-center w-full").style("min-height: 1.2em")


def build_motor_position_tool(session) -> None:
    """Diagnostic tool - user-requested (Sep 2026): motor_action() has
    hardware-confirmed "positioning" end_position angles for D2 and D3
    (Rotation motor id=1: 158.6°/158°; Pitch motor id=2: 150.5°/169°)
    but NONE for the Dwarf Mini. This lets the user find Mini's own
    values by trial and error: pick an axis, send it to a hand-typed
    angle, read the real position back, repeat while watching the
    physical mount - not something that can be guessed without the
    hardware in hand. Not meant for routine use like build_motor_pad()
    - keep this collapsed/out of the way unless actively hunting for a
    reference angle.
    """
    dwarf_uid = session.dwarf_uid
    status_label = ui.label("").classes("text-xs").style("min-height: 1.2em")

    with ui.row().classes("w-full justify-between gap-2 items-end"):
        motor_select = ui.select({1: "Rotation (id=1)", 2: "Pitch (id=2)"}, value=1, label="Axis").classes("flex-1")
        angle_input = ui.number("Target angle (°)", value=0.0, step=0.1, format="%.1f").classes("flex-1")
        speed_input = ui.number("Speed (°/s)", value=5.0, min=0.1, max=30.0, step=0.5).classes("w-28")

    async def _run_to() -> None:
        if not connection_health.try_acquire_command_slot(dwarf_uid, caller="motor_position_tool.run_to"):
            status_label.set_text(t("device_busy"))
            status_label.classes(replace="text-xs text-red-700")
            return
        try:
            ok = await run.io_bound(
                perform_motor_run_to_v3, motor_select.value, float(angle_input.value), float(speed_input.value),
                session=session,
            )
        finally:
            connection_health.release_command_slot(dwarf_uid)
        status_label.set_text("Move sent." if ok else "Move failed - see app log.")
        status_label.classes(replace="text-xs text-grey-6" if ok else "text-xs text-red-700")

    async def _get_position() -> None:
        if not connection_health.try_acquire_command_slot(dwarf_uid, caller="motor_position_tool.get_position"):
            status_label.set_text(t("device_busy"))
            status_label.classes(replace="text-xs text-red-700")
            return
        try:
            position = await run.io_bound(perform_get_motor_position_full, motor_select.value, session=session)
        finally:
            connection_health.release_command_slot(dwarf_uid)
        if position is None:
            status_label.set_text("Could not read position - see app log.")
            status_label.classes(replace="text-xs text-red-700")
        else:
            status_label.set_text(f"Current position: {position:.2f}\u00b0")
            status_label.classes(replace="text-xs text-green-700")

    async def _reset() -> None:
        # motor_action()'s own action==5 (Rotation reset, id=1) / 6
        # (Pitch reset, id=2) - reused directly rather than re-deriving,
        # since a reset needs a specific direction value per axis that's
        # already correctly encoded there (see its own if action==5/6).
        if not connection_health.try_acquire_command_slot(dwarf_uid, caller="motor_position_tool.reset"):
            status_label.set_text(t("device_busy"))
            status_label.classes(replace="text-xs text-red-700")
            return
        action = 5 if motor_select.value == 1 else 6
        try:
            ok = await run.io_bound(motor_action, action, 0, session)
        finally:
            connection_health.release_command_slot(dwarf_uid)
        status_label.set_text("Reset sent." if ok else "Reset failed - see app log.")
        status_label.classes(replace="text-xs text-grey-6" if ok else "text-xs text-red-700")

    with ui.row().classes("w-full justify-between gap-2"):
        ui.button("Run to", icon="place", on_click=_run_to).props("color=primary")
        ui.button("Get position", icon="my_location", on_click=_get_position).props("flat")
        ui.button("Reset axis", icon="restart_alt", on_click=_reset).props("flat color=negative")

    ui.label(
        "Diagnostic tool - not for routine use. D2/D3 reference angles: "
        "Rotation 158.6°/158°, Pitch 150.5°/169° - none confirmed yet for Mini."
    ).classes("text-xs text-grey-6")

