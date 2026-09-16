"""Native Dwarf shooting-schedule editor (module 13,
CMD_SYNC_SHOOTING_SCHEDULE) - builds a schedule and syncs it DIRECTLY to
the device, unlike program_editor.py's step-by-step "programs" (replayed
live by scheduler_runner.py from this PC, one command at a time). This
one lives ON the device once synced - it keeps running even if this app,
or the PC, disconnects or shuts down.

Reuses program_editor.py's target-input approach (Stellarium fetch +
manual RA/Dec) and camera_settings.py's exposure/gain/IR-filter tables -
not reinvented.

CONFIRMED PROTOCOL LIMITS (dwarf_python_api/proto/shooting_schedule.proto
+ live device testing, Sep 2026) - each one is why a field from program_
editor.py is deliberately ABSENT here, not an oversight:
  - TELE CAMERA ONLY. ShootingScheduleMode has exactly one value
    (SHOOTING_SCHEDULE_MODE_ASTRO_DEEP_SKY = 0) - no wide-camera
    equivalent exists in the protocol at all. No camera choice offered.
  - No calibration/eq_solving/auto_focus/infinite_focus fields exist in
    the protocol either - live testing showed the device runs its own
    calibration + plate-solving automatically before a task's exposures
    start, with no way to configure or skip that step from here.
  - No solar-system target support (program_editor.py's goto_solar) -
    every task needs explicit ra/dec (via Stellarium or typed by hand);
    there's no "Moon"/"Jupiter" name field in the native protocol.
  - Mosaic (horizontalScale/verticalScale/isMosaicMode, 100-180%, same
    convention as program_editor.py's framingX/framingY) IS included -
    present in real official-app schedule dumps (Sep 2026, a live
    CMD_GET_ALL_SHOOTING_SCHEDULE read-back) even though the DwarfLab
    PDF spec's own field table omits it entirely - confirmed from actual
    device data, not the documentation. `rotation` is also present in
    those dumps but user-confirmed (Sep 2026) as reserved for a future
    model, not currently functional on this one - always sent as -1
    (the value every observed real dump used), never exposed as an
    editable field here.
  - shutterIndex/gainIndex/filterModeIndex are intentionally left for
    dwarf_python_api's perform_sync_shooting_schedule() to resolve
    server-side from the Name fields (see its own docstring) - this
    editor only ever sends names, matching the catalog page's approach
    and avoiding a second, possibly-drifting copy of the index tables.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta

from nicegui import run, ui

from components import connection_health
from components.camera_settings import _exposure_names, _gain_range, _GAIN_STEP, _ir_filter_names
from components.i18n import t
from components.stellarium import get_target_from_stellarium
from dwarf_python_api.get_config_data import config_to_dwarf_id_str
from dwarf_python_api.lib.dwarf_utils import perform_sync_shooting_schedule


def _exposure_seconds(name: str) -> float | None:
    """Parses an exposure name from _exposure_names() (e.g. "1/50",
    "0.4", "60") into a plain float number of seconds. Returns None for
    anything unparseable rather than raising, so a caller can fall back
    to a safe default instead of crashing the UI on an unexpected name.
    """
    if not name:
        return None
    try:
        if "/" in name:
            numerator, denominator = name.split("/", 1)
            return float(numerator) / float(denominator)
        return float(name)
    except (ValueError, ZeroDivisionError):
        return None


def _new_task_defaults(dwarf_type: str) -> dict:
    exposures = _exposure_names("tele", dwarf_type)
    filters = _ir_filter_names(dwarf_type)
    gain_min, _gain_max = _gain_range("tele")
    return {
        "name": "",
        "ra": "",
        "dec": "",
        "shutterName": exposures[-3] if exposures else "",
        "gainName": str(gain_min),
        "filterModeName": filters[0] if filters else "",
        "count": 20,
        "mosaic": False,
        "horizontalScale": 1.0,
        "verticalScale": 1.0,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "startTime": (datetime.now() + timedelta(minutes=5)).strftime("%H:%M"),
        "durationMin": 60,
    }


def build_schedule_editor(session) -> None:
    """Call once, inline in a tab panel (same pattern as
    build_program_editor()). Keeps its own in-memory task list across
    Add/Remove clicks within this render, synced to the device only on
    an explicit button press."""
    dwarf_type = config_to_dwarf_id_str(session.config.dwarf_model_id) or "2"
    dwarf_uid = session.dwarf_uid
    tasks: list[dict] = []

    schedule_name_input = ui.input(
        t("sched_name"), value=f"Session {datetime.now().strftime('%Y-%m-%d')}"
    ).classes("w-full")

    ui.label(t("sched_add_target")).classes("text-sm text-grey-6 mt-2")

    draft = _new_task_defaults(dwarf_type)

    with ui.row().classes("w-full gap-2"):
        target_name_input = ui.input(t("prog_target_name"), value=draft["name"]).classes("flex-1")
        ra_input = ui.input(t("prog_ra"), value=draft["ra"]).classes("w-32")
        dec_input = ui.input(t("prog_dec"), value=draft["dec"]).classes("w-32")

    stellarium_status = ui.label("").classes("text-xs")

    async def _fetch_from_stellarium() -> None:
        stellarium_status.set_text(t("prog_stellarium_fetching"))
        stellarium_status.classes(replace="text-xs text-grey-6")
        try:
            target = await run.io_bound(
                get_target_from_stellarium,
                session.config.stellarium_ip,
                session.config.stellarium_port,
            )
        except Exception as exc:
            stellarium_status.set_text(str(exc))
            stellarium_status.classes(replace="text-xs text-red-700")
            return
        target_name_input.value = target.target_name
        ra_input.value = target.ra_hours
        dec_input.value = str(target.dec_degrees)
        stellarium_status.set_text(t("prog_stellarium_fetched", name=target.target_name))
        stellarium_status.classes(replace="text-xs text-green-700")

    ui.button(t("prog_get_from_stellarium"), icon="explore", on_click=_fetch_from_stellarium).props("flat dense")

    with ui.row().classes("w-full gap-2"):
        exposure_input = ui.select(_exposure_names("tele", dwarf_type), value=draft["shutterName"], label=t("prog_exposure")).classes("flex-1")
        gain_min, gain_max = _gain_range("tele")
        gain_input = ui.number(t("prog_gain"), value=int(draft["gainName"]), min=gain_min, max=gain_max, step=_GAIN_STEP).classes("flex-1")
        filter_input = ui.select(_ir_filter_names(dwarf_type), value=draft["filterModeName"], label=t("ir_filter")).classes("flex-1")
        count_input = ui.number(t("prog_count"), value=draft["count"], min=1).classes("w-24")

    mosaic_cb = ui.checkbox(t("prog_mosaic"), value=False)
    with ui.row().classes("w-full gap-2") as mosaic_fields:
        h_scale_input = ui.number(t("prog_framing_x"), value=1.0, min=1.0, max=1.8, step=0.1, format="%.1f").classes("flex-1")
        v_scale_input = ui.number(t("prog_framing_y"), value=1.0, min=1.0, max=1.8, step=0.1, format="%.1f").classes("flex-1")
    mosaic_fields.set_visibility(False)
    mosaic_cb.on_value_change(lambda e: mosaic_fields.set_visibility(e.value))

    with ui.row().classes("w-full gap-2"):
        date_input = ui.input(t("prog_date"), value=draft["date"]).classes("flex-1")
        start_time_input = ui.input(t("sched_start_time"), value=draft["startTime"]).classes("flex-1")
        # Computed, not manually entered (user-reported Sep 2026: the
        # schedule's end_time - which the device uses to know when to
        # STOP - was a separate, independently-typed field, so it could
        # silently disagree with what "count" images at "shutterName"
        # exposure would actually take, ending the session early (cut
        # off mid-sequence) or leaving it running well past the last
        # planned exposure. Tying duration directly to count x exposure
        # removes that gap - editing this number no longer does
        # anything (see the on_value_change handlers on count_input/
        # exposure_input below, which are the actual source of truth
        # now), it only ever reflects them.
        duration_input = ui.number(t("sched_duration_min"), value=draft["durationMin"], min=1).classes("w-32").props("readonly")

    def _recompute_duration() -> None:
        exposure_s = _exposure_seconds(exposure_input.value or "")
        count = int(count_input.value or 0)
        if exposure_s is None or count <= 0:
            return
        # Ceil, not floor/round: a device stopped by end_time mid-way
        # through what would have been the last exposure of the
        # sequence is worse than a session that runs a few seconds past
        # its last completed exposure - rounding DOWN here would
        # silently truncate the count the user actually asked for.
        duration_input.value = math.ceil(1 + (count * exposure_s) / 60) or 1

    count_input.on_value_change(lambda _e: _recompute_duration())
    exposure_input.on_value_change(lambda _e: _recompute_duration())
    _recompute_duration()

    task_list_container = ui.column().classes("w-full gap-1")
    add_status_label = ui.label("").classes("text-xs text-red-700")

    def _render_task_list() -> None:
        task_list_container.clear()
        with task_list_container:
            if not tasks:
                ui.label(t("sched_no_targets")).classes("text-xs text-grey-6")
                return
            for i, tk in enumerate(tasks):
                with ui.row().classes("w-full items-center gap-2 q-pa-xs").style("border-bottom: 1px solid #4442"):
                    label = f"{i + 1}. {tk['name']} — {tk['date']} {tk['startTime']} ({tk['durationMin']}min) — {tk['shutterName']}s @ {tk['gainName']}, {tk['filterModeName']}"
                    if tk["mosaic"]:
                        label += f" [mosaic {tk['horizontalScale']:.1f}x{tk['verticalScale']:.1f}]"
                    ui.label(label).classes("text-xs flex-1")
                    ui.button(icon="delete", on_click=lambda _, idx=i: _remove_task(idx)).props("flat dense round size=sm color=negative")

    def _remove_task(idx: int) -> None:
        tasks.pop(idx)
        _render_task_list()

    def _add_task() -> None:
        missing = []
        if not target_name_input.value.strip():
            missing.append(t("prog_target_name"))
        if not ra_input.value or not dec_input.value:
            missing.append(t("sched_ra_dec"))
        if not date_input.value.strip() or not start_time_input.value.strip():
            missing.append(t("sched_start_time"))
        if missing:
            add_status_label.set_text(t("prog_missing_fields", fields=", ".join(missing)))
            return
        try:
            ra_val = float(ra_input.value)
            dec_val = float(dec_input.value)
        except (TypeError, ValueError):
            add_status_label.set_text(t("sched_invalid_coords"))
            return

        tasks.append({
            "name": target_name_input.value.strip(),
            "ra": ra_val,
            "dec": dec_val,
            "shutterName": exposure_input.value or "",
            "gainName": str(int(gain_input.value)),
            "filterModeName": filter_input.value or "",
            "count": 0, #int(count_input.value or 0),
            "mosaic": bool(mosaic_cb.value),
            "horizontalScale": float(h_scale_input.value or 1.0),
            "verticalScale": float(v_scale_input.value or 1.0),
            "date": date_input.value.strip(),
            "startTime": start_time_input.value.strip(),
            "durationMin": int(duration_input.value or 30),
        })
        add_status_label.set_text("")
        target_name_input.value = ""
        ra_input.value = ""
        dec_input.value = ""
        stellarium_status.set_text("")
        _render_task_list()

    ui.button(t("sched_add_to_schedule"), icon="add", on_click=_add_task).props("flat")

    ui.label(t("sched_targets_label")).classes("text-sm text-grey-6 mt-2")
    _render_task_list()

    sync_status_label = ui.label("").classes("text-sm")

    def _build_wire_tasks() -> list[dict]:
        wire_tasks = []
        for tk in tasks:
            start_dt = datetime.strptime(f"{tk['date']} {tk['startTime']}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=tk["durationMin"])
            start_ms = int(start_dt.timestamp() * 1000)
            end_ms = int(end_dt.timestamp() * 1000)
            is_mosaic = tk["mosaic"] and not (tk["horizontalScale"] == 1.0 and tk["verticalScale"] == 1.0)
            wire_tasks.append({
                "name": tk["name"],
                "ra": tk["ra"],
                "dec": tk["dec"],
                "startTime": start_ms,
                "endTime": end_ms,
                "shutterName": tk["shutterName"],
                "gainName": tk["gainName"],
                "filterModeName": tk["filterModeName"],
                "count": tk["count"],
                # stacked: 0, not None - matches count above and the
                # official app's own convention (a real device dump
                # always sends 0, never null) - same reasoning as the
                # catalog page's fix for CODE_SHOOTING_SCHEDULE_INVALID_
                # SHOOTING_DURATION (-16301).
                "stacked": None,
                # isMosaicMode/horizontalScale/verticalScale: field names
                # match the real official-app dump exactly (see this
                # module's own docstring) - percentages (100-180), same
                # convention program_editor.py already uses for framingX/Y.
                "isMosaicMode": is_mosaic,
                "horizontalScale": int(round(tk["horizontalScale"] * 100)) if is_mosaic else 100,
                "verticalScale": int(round(tk["verticalScale"] * 100)) if is_mosaic else 100,
                "schedule_task_id": str(uuid.uuid4()),
                "createFrom": 0,
            })
        return wire_tasks

    async def _handle_sync() -> None:
        if not tasks:
            sync_status_label.set_text(t("sched_no_targets"))
            sync_status_label.classes(replace="text-sm text-red-700")
            return

        wire_tasks = _build_wire_tasks()
        starts = [tk["startTime"] for tk in wire_tasks]
        ends = [tk["endTime"] for tk in wire_tasks]

        # STALENESS CHECK (user-reported Sep 2026: got -16308 CODE_
        # SHOOTING_SCHEDULE_START_TIME_TOO_FAR on a manual entry test) -
        # mirrors the same check already added to the DSO catalog page
        # for the exact same field-confirmed device limit: a task whose
        # window is more than 12h from "now" (in either direction) gets
        # rejected outright. Checked here BEFORE sending, with a clear
        # message, instead of surfacing the device's bare error code -
        # a manually-typed date/time is an easy way to hit this by
        # mistake (unlike the catalog page's auto-computed "tonight").
        now_ms = datetime.now().timestamp() * 1000
        twelve_h_ms = 12 * 60 * 60 * 1000
        if min(starts) - twelve_h_ms > now_ms or max(ends) + twelve_h_ms < now_ms:
            sync_status_label.set_text(t("sched_stale"))
            sync_status_label.classes(replace="text-sm text-red-700")
            return

        schedule = {
            "scheduleId": str(uuid.uuid4()),
            "scheduleName": schedule_name_input.value.strip() or "Schedule",
            "startTime": min(starts),
            "endTime": max(ends),
            "lock": 0,
            "password": "",
            "paramsMode": 0,
            "params": {
                "longitude": session.config.longitude,
                "latitude": session.config.latitude,
                # No city-name field existed at all on DwarfConfig until
                # user-requested (Sep 2026) - now set in Settings, read
                "cityName": "", #session.config.city_name or "",
                "focusMode": 0,
            },
            "shooting_tasks": wire_tasks,
        }

        if not connection_health.try_acquire_command_slot(dwarf_uid, caller="schedule_editor.sync"):
            sync_status_label.set_text(t("device_busy"))
            sync_status_label.classes(replace="text-sm text-red-700")
            return
        sync_status_label.set_text(t("sched_syncing"))
        sync_status_label.classes(replace="text-sm text-grey-6")
        try:
            ok = await run.io_bound(perform_sync_shooting_schedule, schedule, session=session)
        finally:
            connection_health.release_command_slot(dwarf_uid)

        if ok:
            sync_status_label.set_text(t("sched_synced"))
            sync_status_label.classes(replace="text-sm text-green-700")
            tasks.clear()
            _render_task_list()
        else:
            sync_status_label.set_text(t("sched_sync_failed"))
            sync_status_label.classes(replace="text-sm text-red-700")

    ui.button(t("sched_sync"), icon="cloud_upload", on_click=_handle_sync).props("color=primary")
