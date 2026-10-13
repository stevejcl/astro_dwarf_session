"""Identify a Dwarf: its ring light flashes, to tell which one it is on the
table when several are on (user-requested Oct 2026).

Used by the device card, the manual configuration (a Dwarf typed by IP,
before it is saved), and GET /api/identify?ip= (Scope Archive's Dwarf page,
Dwarfium-Hub's Dwarfs tab).

Never during a capture - the light would spoil the frames: refused when a
program of this app runs on that Dwarf, when the Dwarf reports a photo
being taken, or when its state on connection shows a camera / motor /
focus operation in progress (connection_health._device_busy, which also
covers a native schedule running on the Dwarf itself).

- A Dwarf of this app already connected: its own session, with the command
  slot (like the Lights button); the light is put back as it was.
- Otherwise (not connected, or not registered at all): a throwaway session
  built from /deviceInfo (name, model) at that IP, disconnected afterwards.
  If another client holds the Dwarf (the DwarfLab app...), the Dwarf
  refuses the connection: said so, nothing forced.
"""
from __future__ import annotations

import logging
import time

from nicegui import run

from dwarf_python_api.lib.dwarf_config import DwarfConfig
from dwarf_python_api.lib.dwarf_session import DwarfSession, get_manager
from dwarf_python_api.lib.dwarf_session_socket import disconnect_socket, get_client_status
from dwarf_python_api.lib.dwarf_utils import (
    perform_get_device_state_info,
    perform_powerCloseRGB,
    perform_powerOpenRGB,
)

from components import connection_health, scheduler_runner
from device_provisioning import DEVICE_ID_BY_MODEL, read_device_identity

log = logging.getLogger(__name__)

OK, BUSY, NO_ANSWER, OCCUPIED, FAILED = "ok", "busy", "no_answer", "occupied", "failed"
FLASHES = 3
_ON_S, _OFF_S = 0.7, 0.5
_CLIENT_ID = "0000DAF2-0000-1000-8000-00805F9B34FB"     # the app's usual one (device_provisioning)


def _registered_session(ip: str) -> DwarfSession | None:
    for session in get_manager().all():
        if ip and ip in (session.config.dwarf_ip, getattr(session.config, "alternate_dwarf_ip", None)):
            return session
    return None


def _capturing(session: DwarfSession) -> bool:
    full_status = get_client_status(session).get("fullStatus") or {}
    return bool(full_status.get("takePhotoStarted") or full_status.get("takeWidePhotoStarted"))


def _reported_state(session: DwarfSession, notified_attr: str, state_field: str) -> bool | None:
    """A light as the Dwarf reports it: its last notification (the
    WebSocketClient's notified_attr), else the device state received on
    connection (device_state_info.<state_field>); None when neither says."""
    client = getattr(session, "client_instance", None)
    notified = getattr(client, notified_attr, None)
    if notified is not None:
        return bool(notified)
    info = getattr(client, "last_device_state_info", None)
    try:
        if info is not None and info.HasField("device_state_info"):
            return bool(getattr(info.device_state_info, state_field).state)
    except (AttributeError, ValueError):
        pass
    return None


def _light_is_on(session: DwarfSession) -> bool | None:
    """The ring light (a Dwarf's ring light is usually on - assuming it off
    left it off after identifying, user-reported Oct 2026)."""
    return _reported_state(session, "RgbIndStateDwarf", "rgb_state")


def power_light_is_on(session: DwarfSession) -> bool | None:
    """The power (battery) indicator."""
    return _reported_state(session, "PowerIndStateDwarf", "power_ind_state")


def _flash(session: DwarfSession, light_was_on: bool) -> bool:
    """Blocking. FLASHES times the opposite of the light's state and back,
    so it ends as it was (on stays on, off stays off)."""
    first, back = ((perform_powerCloseRGB, perform_powerOpenRGB) if light_was_on
                   else (perform_powerOpenRGB, perform_powerCloseRGB))
    for _ in range(FLASHES):
        # is False, not falsy: 0 is a success code (see actions_section)
        if first(session=session) is False:
            return False
        time.sleep(_ON_S)
        if back(session=session) is False:
            return False
        time.sleep(_OFF_S)
    return True


def _identify_throwaway(ip: str) -> str:
    """Blocking. A Dwarf this app isn't connected to."""
    info = read_device_identity(ip)
    if not info:
        return NO_ANSWER
    session = DwarfSession(DwarfConfig(
        dwarf_uid=info["uid"], dwarf_ip=ip,
        dwarf_model_id=DEVICE_ID_BY_MODEL.get(info["model"], ""), client_id=_CLIENT_ID))
    try:
        # Opens the connection, whose first message is the device state
        if perform_get_device_state_info(session=session) is False:
            error = str(getattr(session, "last_connection_error", "") or "")
            return OCCUPIED if "OCCUPIED" in error.upper() else NO_ANSWER
        if connection_health._device_busy(session):
            return BUSY
        light = _light_is_on(session)
        return OK if _flash(session, light_was_on=True if light is None else light) else FAILED
    finally:
        try:
            disconnect_socket(session)
        except Exception as e:   # never leave the caller on a cleanup error
            log.warning(f"[identify {ip}] disconnect: {e}")


async def identify(ip: str) -> str:
    """OK, BUSY, NO_ANSWER, OCCUPIED or FAILED."""
    ip = (ip or "").strip()
    if not ip:
        return NO_ANSWER
    session = _registered_session(ip)
    if session is None or not session.is_connected:
        if session is not None and scheduler_runner.is_running(session.dwarf_uid):
            return BUSY
        return await run.io_bound(_identify_throwaway, ip)

    uid = session.dwarf_uid
    if scheduler_runner.is_running(uid) or _capturing(session):
        return BUSY
    if not connection_health.acquire_with_priority(uid, caller="identify"):
        return BUSY
    try:
        from components.actions_section import _lights_on
        light = _light_is_on(session)
        if light is None:
            light = _lights_on.get(uid, True)
        ok = await run.io_bound(_flash, session, light)
        if ok:
            _lights_on[uid] = light       # the Lights button knows it too
        return OK if ok else FAILED
    finally:
        connection_health.release_command_slot(uid)


async def identify_and_notify(ip: str) -> str:
    """identify() from a button: says it started, then how it went."""
    from nicegui import ui
    from components.i18n import t

    ui.notify(t("identify_running"), type="info")
    result = await identify(ip)
    ui.notify(t(f"identify_{result}", ip=ip), type="positive" if result == OK else "warning", multi_line=True)
    return result
