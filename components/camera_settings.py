"""Astro camera settings (exposure + gain, tele + wide) for the session
page. Split out from session.py: this section has its own non-trivial
data (per-model exposure tables) and deliberately does NOT live inside
session_view's auto-refreshing body (see session.py) - it's built ONCE
per page load instead, with an explicit reload button. If it were part
of the view that re-renders every ~2s on every poll tick, an open
dropdown or a gain field mid-edit would get torn down and rebuilt out
from under the user's cursor.

V3 has NO "GET" command for these params (see dwarf_utils.py's docstring
above perform_read_exposure_v3) - the firmware only BROADCASTS the
current value via notifications, cached in
session.client_instance.cameraParamsDwarf. perform_read_exposure_v3()/
perform_read_gain_v3() read this cache directly (no network call), so
reading here is cheap - it's only the WRITE side (perform_set_astro_*)
that needs run.io_bound() and the shared command-slot lock, same as
every other command in this app (see components/connection_health.py's
CONCURRENCY NOTE for why that lock exists)."""
from __future__ import annotations

from nicegui import run, ui

from dwarf_python_api.get_config_data import config_to_dwarf_id_str
from dwarf_python_api.lib.data_utils import (
    allowed_exposures,
    allowed_exposuresD3,
    allowed_exposuresMini,
    allowed_ir_filter,
    allowed_ir_filterD2,
    allowed_ir_filterMini,
)
from dwarf_python_api.lib.data_wide_utils import (
    allowed_wide_exposures,
    allowed_wide_exposuresD3,
    allowed_wide_exposuresMini,
)
from dwarf_python_api.lib.dwarf_utils import (
    PARAM_ID_ASTRO_EXPOSURE,
    PARAM_ID_ASTRO_GAIN,
    PARAM_ID_ASTRO_WIDE_EXPOSURE,
    PARAM_ID_ASTRO_WIDE_GAIN,
    perform_read_exposure_v3,
    perform_read_gain_v3,
    perform_set_astro_exposure_by_name_v3,
    perform_set_astro_gain_v3,
    perform_set_ir_filter_v3,
)

from components import connection_health
from components.i18n import t

# IR/Astro filter - TELE ONLY: the underlying command is
# CMD_CAMERA_TELE_SET_IRCUT (dwarf_utils.py), there is no wide-camera
# equivalent at all, confirmed by there being no CAMERA_WIDE-module
# counterpart anywhere in websockets_utils.py.
#
# NOT the same across models (user-confirmed Sep 2026, corrected from
# an earlier "single shared table" assumption): the numeric index
# (0/1/2) is shared, but the NAMES differ by model, and D2 only has 2
# valid positions (IR_PASS/IR_CUT), not 3 like D3 (VIS/Astro/Duo-Band)
# or Mini (DARK/Astro/Duo-Band) - see data_utils.py's AllowedIRFilter/
# AllowedIRFilterD2/AllowedIRFilterMini. _ir_filter_table() below
# dispatches by dwarf_type, same pattern as _exposure_table().
#
# perform_set_ir_filter_v3() is called with the raw INTEGER index here,
# never the name string - it also accepts a name via a single SHARED
# global table (get_ir_filter_index_by_name(), matching D3's table
# only), which would silently resolve a D2/Mini name to the wrong
# index (or fall back to index 0) since that lookup has no model
# awareness at all. Passing the index directly, already resolved from
# the correct PER-MODEL table here, sidesteps that entirely.
#
# WRITE-ONLY: there is no perform_read_ir_filter_v3()-style function at
# all - websockets_utils.py decodes CMD_CAMERA_TELE_GET_IRCUT responses
# but never caches the resulting value anywhere retrievable, unlike
# exposure/gain's own cameraParamsDwarf cache. The dropdown below
# therefore never shows a pre-selected current value (always starts at
# None) - same limitation as actions_section.py's own Toggle Lights.


def _ir_filter_table(dwarf_type: str):
    if dwarf_type == "5":
        return allowed_ir_filterMini
    if dwarf_type == "2":
        return allowed_ir_filterD2
    return allowed_ir_filter  # D3 - also the fallback for an unrecognized dwarf_type


def _ir_filter_names(dwarf_type: str) -> list[str]:
    return [v["name"] for v in _ir_filter_table(dwarf_type).values]


def _ir_filter_index_by_name(dwarf_type: str, name: str) -> int:
    table = _ir_filter_table(dwarf_type)
    found = next((v for v in table.values if v["name"] == name), None)
    return found["index"] if found else table.default_value_index

# Astro TELE gain range confirmed via the live HTTP API (Aug 2026): 40 is
# the minimum in astro mode specifically (different from 0 in normal
# photo mode). WIDE's range is NOT independently confirmed yet - reusing
# tele's as a cautious placeholder, per dwarf_utils.py's
# perform_set_astro_gain_v3() docstring ("use with the same caution as
# tele until cross-checked").
_TELE_GAIN_RANGE = (40, 240)
_WIDE_GAIN_RANGE = (40, 240)  # unconfirmed for wide

# User-confirmed (Sep 2026): astro gain only steps in increments of 10
# (40, 50, 60, ... 240), not every integer - both the live camera_
# settings field and the program editor's gain field need to snap to
# this, otherwise a value like 45 could be typed/scrolled to but never
# actually corresponds to a real gain setting on the device.
_GAIN_STEP = 10


def _exposure_table(camera: str, dwarf_type: str):
    if camera == "wide":
        if dwarf_type == "5":
            return allowed_wide_exposuresMini
        if dwarf_type == "3":
            return allowed_wide_exposuresD3
        return allowed_wide_exposures
    if dwarf_type == "5":
        return allowed_exposuresMini
    if dwarf_type == "3":
        return allowed_exposuresD3
    return allowed_exposures


def _exposure_names(camera: str, dwarf_type: str) -> list[str]:
    return [v["name"] for v in _exposure_table(camera, dwarf_type).values]


def _param_ids(camera: str) -> tuple[int, int]:
    if camera == "wide":
        return PARAM_ID_ASTRO_WIDE_EXPOSURE, PARAM_ID_ASTRO_WIDE_GAIN
    return PARAM_ID_ASTRO_EXPOSURE, PARAM_ID_ASTRO_GAIN


def _gain_range(camera: str) -> tuple[int, int]:
    return _WIDE_GAIN_RANGE if camera == "wide" else _TELE_GAIN_RANGE


def build_camera_settings(session) -> None:
    """Call once, inline in the page - not inside a periodically
    refreshed container. Renders two rows (tele, wide), each with an
    exposure dropdown and a gain number field, plus a manual reload
    button (since values are a firmware-pushed cache, not something we
    poll automatically here)."""
    dwarf_type = config_to_dwarf_id_str(session.config.dwarf_model_id) or "2"

    with ui.column().classes("w-full gap-2 mt-2") as container:
        with ui.row().classes("items-center justify-between w-full"):
            ui.label(t("camera_settings")).classes("text-sm text-grey-6")
            ui.button(
                icon="refresh",
                on_click=lambda: _reload(session, dwarf_type, container),
            ).props("flat round dense")

        _render_rows(session, dwarf_type, container)


def _render_rows(session, dwarf_type: str, container: ui.column) -> None:
    with container:
        _camera_row(session, "tele", dwarf_type)
        _camera_row(session, "wide", dwarf_type)


def _reload(session, dwarf_type: str, container: ui.column) -> None:
    """Manual re-sync from the cache - the only way values here change
    without the user's own edit, since this section isn't on the
    auto-refresh loop (see module docstring for why)."""
    container.clear()
    _render_rows(session, dwarf_type, container)


def _camera_row(session, camera: str, dwarf_type: str) -> None:
    exposure_param_id, gain_param_id = _param_ids(camera)
    exposure_info = perform_read_exposure_v3(
        param_id=exposure_param_id, dwarf_id=dwarf_type, session=session
    )
    gain_info = perform_read_gain_v3(param_id=gain_param_id, session=session)
    gain_min, gain_max = _gain_range(camera)

    label = t("camera_tele") if camera == "tele" else t("camera_wide")

    with ui.row().classes("w-full items-center gap-2"):
        ui.label(label).classes("text-xs text-grey-6 w-12 shrink-0")

        ui.select(
            _exposure_names(camera, dwarf_type),
            value=exposure_info["name"] if exposure_info else None,
            label=t("exposure"),
            on_change=lambda e, cam=camera: _handle_set_exposure(
                session, cam, dwarf_type, e.value
            ),
        ).classes("flex-1").props("dense")

        ui.number(
            label=t("gain"),
            value=int(gain_info["value"]) if gain_info else None,
            min=gain_min,
            max=gain_max,
            step=_GAIN_STEP,
            on_change=lambda e, cam=camera: _handle_set_gain(session, cam, e.value),
        ).classes("w-24").props("dense")

        if camera == "tele":
            ui.select(
                _ir_filter_names(dwarf_type),
                value=None,
                label=t("ir_filter"),
                on_change=lambda e: _handle_set_ir_filter(session, dwarf_type, e.value),
            ).classes("w-32").props("dense")


async def _handle_set_exposure(session, camera: str, dwarf_type: str, name) -> None:
    if name is None:
        return
    dwarf_uid = session.dwarf_uid
    if not connection_health.try_acquire_command_slot(dwarf_uid):
        ui.notify(t("device_busy"), type="warning")
        return
    try:
        result = await run.io_bound(
            perform_set_astro_exposure_by_name_v3,
            name,
            dwarf_id=dwarf_type,
            camera=camera,
            session=session,
        )
    finally:
        connection_health.release_command_slot(dwarf_uid)
    # is not False, NOT a plain truthy check: these perform_* functions
    # return the protocol response code directly on success, and 0
    # (OK) is a valid success value that happens to be Python-falsy -
    # `if result:` would misreport a genuine success as a failure
    # (confirmed via a real log: SET EXPOSURE (V3) -> 0 / SUCCESS, but
    # the UI showed "command failed" because of exactly this).
    success = result is not False
    ui.notify(
        t("exposure_set", value=name) if success else t("command_failed"),
        type="positive" if success else "negative",
    )


async def _handle_set_gain(session, camera: str, value) -> None:
    if value is None:
        return
    dwarf_uid = session.dwarf_uid
    if not connection_health.try_acquire_command_slot(dwarf_uid):
        ui.notify(t("device_busy"), type="warning")
        return
    try:
        result = await run.io_bound(
            perform_set_astro_gain_v3, int(value), camera=camera, session=session
        )
    finally:
        connection_health.release_command_slot(dwarf_uid)
    success = result is not False  # see _handle_set_exposure() for why
    ui.notify(
        t("gain_set", value=int(value)) if success else t("command_failed"),
        type="positive" if success else "negative",
    )


async def _handle_set_ir_filter(session, dwarf_type: str, name) -> None:
    if name is None:
        return
    dwarf_uid = session.dwarf_uid
    if not connection_health.try_acquire_command_slot(dwarf_uid):
        ui.notify(t("device_busy"), type="warning")
        return
    index = _ir_filter_index_by_name(dwarf_type, name)
    try:
        result = await run.io_bound(perform_set_ir_filter_v3, index, session=session)
    finally:
        connection_health.release_command_slot(dwarf_uid)
    success = result is not False  # see _handle_set_exposure() for why
    ui.notify(
        t("ir_filter_set", value=name) if success else t("command_failed"),
        type="positive" if success else "negative",
    )