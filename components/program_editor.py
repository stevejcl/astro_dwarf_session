"""Program editor - builds/edits the exact JSON schema produced by
astro_dwarf_session's own tabs/create_session.py (save_to_json()),
verified against that source rather than guessed. Saving writes into
the SAME per-device ToDo directory astro_dwarf_scheduler.py's
check_and_execute_commands() actually scans (see
components/session_dirs.py) - a program saved here is picked up and run
exactly like one created from the legacy Tkinter "Create Session" tab.

SCOPE: covers create-from-blank and edit-existing (load an uploaded/
selected JSON file, prefill every field, save back either as a new
file or overwriting the original) - not a from-scratch reinvention of
the schema, a faithful port of the existing one to NiceGUI widgets."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta

from nicegui import run, ui

from components.camera_settings import (
    _exposure_names,
    _gain_range,
    _GAIN_STEP,
    _ir_filter_index_by_name,
    _ir_filter_names,
    _ir_filter_table,
)
from components.i18n import t
from components.session_dirs import ensure_dirs
from components.stellarium import get_target_from_stellarium
from dwarf_python_api.get_config_data import config_to_dwarf_id_str

_SOLAR_TARGETS = ["", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Sun"]
BINNING_MAP_D3 = {0: "4k", 1: "2k"}
BINNING_NAME_TO_VAL_D3 = {"4k": 0, "2k": 1}

def _blank_program() -> dict:
    """Mirrors save_to_json()'s own "data" dict shape exactly, with
    generic wait_before/wait_after (0) and empty/default values -
    astro_dwarf_session's own form reuses ONE wait_before/wait_after
    pair across eq_solving/auto_focus/infinite_focus/calibration, so
    this editor does too."""
    now = datetime.now()
    return {
        "command": {
            "id_command": {
                "uuid": f"{uuid.uuid4()}-00001",
                "description": "",
                "date": now.strftime("%Y-%m-%d"),
                "time": (now + timedelta(minutes=5)).strftime("%H:%M:%S"),
                "process": "wait",
                "max_retries": 3,
                "result": False,
                "message": "",
                "nb_try": 1,
            },
            "eq_solving": {"do_action": False, "wait_before": 0, "wait_after": 0},
            "auto_focus": {"do_action": False, "wait_before": 0, "wait_after": 0},
            "infinite_focus": {"do_action": False, "wait_before": 0, "wait_after": 0},
            "calibration": {"do_action": False, "wait_before": 0, "wait_after": 0},
            "goto_solar": {"do_action": False, "target": "", "wait_after": 0},
            "goto_manual": {
                "do_action": False,
                "target": "",
                "ra_coord": "",
                "dec_coord": "",
                "wait_after": 10,
            },
            "setup_camera": {
                "do_action": True,
                "exposure": "15",
                "gain": "80",
                "binning": "0",
                "ircut": "1",
                "count": "20",
                "wait_after": 30,
            },
            "setup_wide_camera": {
                "do_action": False,
                "exposure": "10",
                "gain": "90",
                "count": "10",
                "wait_after": 30,
            },
        }
    }


def _filename_for(program: dict) -> str:
    id_command = program["command"]["id_command"]
    date = id_command.get("date", "")
    time_str = id_command.get("time", "").replace(":", "-")
    goto_manual = program["command"]["goto_manual"]
    goto_solar = program["command"]["goto_solar"]
    if goto_manual.get("do_action") and goto_manual.get("target"):
        target = goto_manual["target"]
    elif goto_solar.get("do_action") and goto_solar.get("target"):
        target = goto_solar["target"]
    else:
        target = id_command.get("description") or "session"
    safe_target = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(target))
    return f"{date}-{time_str}-{safe_target}.json"


def build_program_editor(session, *, initial_program: dict | None = None, on_saved=None) -> None:
    """initial_program: load an existing script's dict for editing (None
    = blank template). on_saved(filepath): called after a successful
    save, e.g. to refresh a scripts list."""
    program = json.loads(json.dumps(initial_program)) if initial_program else _blank_program()
    cmd = program["command"]

    with ui.column().classes("w-full gap-3"):
        description = ui.input(t("prog_description"), value=cmd["id_command"]["description"]).classes("w-full")

        with ui.row().classes("w-full gap-2"):
            date_input = ui.input(t("prog_date"), value=cmd["id_command"]["date"]).classes("flex-1")
            time_input = ui.input(t("prog_time"), value=cmd["id_command"]["time"]).classes("flex-1")
            retries_input = ui.number(
                t("prog_max_retries"), value=cmd["id_command"]["max_retries"], min=1, max=10
            ).classes("w-32")

        with ui.row().classes("w-full gap-2"):
            wait_before_input = ui.number(t("prog_wait_before"), value=cmd["auto_focus"]["wait_before"], min=0).classes("flex-1")
            wait_after_input = ui.number(t("prog_wait_after"), value=cmd["auto_focus"]["wait_after"], min=0).classes("flex-1")

        ui.label(t("prog_actions")).classes("text-sm text-grey-6 mt-2")
        with ui.row().classes("w-full gap-4"):
            auto_focus_cb = ui.checkbox(t("prog_auto_focus"), value=cmd["auto_focus"]["do_action"])
            infinite_focus_cb = ui.checkbox(t("prog_infinite_focus"), value=cmd["infinite_focus"]["do_action"])
            eq_solving_cb = ui.checkbox(t("prog_eq_solving"), value=cmd["eq_solving"]["do_action"])
            calibration_cb = ui.checkbox(t("prog_calibration"), value=cmd["calibration"]["do_action"])

        # auto_focus / infinite_focus are mutually exclusive in the
        # original form (one autofocus method OR the other) - enforced
        # here the same way.
        def _on_auto_focus_change(e) -> None:
            if e.value:
                infinite_focus_cb.set_value(False)

        def _on_infinite_focus_change(e) -> None:
            if e.value:
                auto_focus_cb.set_value(False)

        auto_focus_cb.on_value_change(_on_auto_focus_change)
        infinite_focus_cb.on_value_change(_on_infinite_focus_change)

        ui.label(t("prog_goto")).classes("text-sm text-grey-6 mt-2")
        goto_mode = ui.radio(
            {"none": t("prog_goto_none"), "solar": t("prog_goto_solar"), "manual": t("prog_goto_manual")},
            value=(
                "solar" if cmd["goto_solar"]["do_action"]
                else "manual" if cmd["goto_manual"]["do_action"]
                else "none"
            ),
        ).props("inline")

        with ui.column().classes("w-full gap-2") as solar_section:
            solar_target = ui.select(_SOLAR_TARGETS, value=cmd["goto_solar"]["target"], label=t("prog_solar_target")).classes("w-full")

        with ui.column().classes("w-full gap-2") as manual_section:
            with ui.row().classes("w-full gap-2"):
                manual_target = ui.input(t("prog_target_name"), value=cmd["goto_manual"]["target"]).classes("flex-1")
                ra_input = ui.input(t("prog_ra"), value=str(cmd["goto_manual"]["ra_coord"] or "")).classes("w-32")
                dec_input = ui.input(t("prog_dec"), value=str(cmd["goto_manual"]["dec_coord"] or "")).classes("w-32")

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
                manual_target.value = target.target_name
                ra_input.value = target.ra_hours
                dec_input.value = str(target.dec_degrees)
                description.value = target.description
                goto_mode.value = "manual"
                _update_goto_visibility()
                stellarium_status.set_text(t("prog_stellarium_fetched", name=target.target_name))
                stellarium_status.classes(replace="text-xs text-green-700")

            ui.button(
                t("prog_get_from_stellarium"), icon="explore", on_click=_fetch_from_stellarium
            ).props("flat dense")

        wait_after_target_input = ui.number(
            t("prog_wait_after_target"), value=cmd["goto_solar"]["wait_after"], min=0
        ).classes("w-full")

        def _update_goto_visibility() -> None:
            solar_section.set_visibility(goto_mode.value == "solar")
            manual_section.set_visibility(goto_mode.value == "manual")

        goto_mode.on_value_change(lambda _: _update_goto_visibility())
        _update_goto_visibility()

        ui.label(t("prog_camera")).classes("text-sm text-grey-6 mt-2")
        _initial_camera = (
            "wide" if cmd["setup_wide_camera"]["do_action"]
            else "tele" if cmd["setup_camera"]["do_action"]
            else "none"
        )
        camera_choice = ui.radio(
            {"none": t("prog_camera_none"), "tele": t("camera_tele"), "wide": t("camera_wide")},
            value=_initial_camera,
        ).props("inline")

        # Cross-device import validation (point B): a program authored
        # for a different Dwarf model can carry an exposure/gain value
        # that doesn't exist / isn't in range on THIS device - e.g. the
        # wide table's 180s step only exists on some models (see
        # camera_settings.py's data_wide_utils dispatch). Rather than
        # silently accepting an invalid value (which would just fail
        # when the program actually runs), the exposure field is a
        # dropdown of THIS device's own valid options - an out-of-range
        # imported value simply won't be pre-selected, and gain is
        # clamped into range with a visible warning either way.
        dwarf_type = config_to_dwarf_id_str(session.config.dwarf_model_id) or "2"
        import_warning_label = ui.label("").classes("text-xs text-amber-700")

        def _exposure_options(camera: str) -> list[str]:
            return _exposure_names(camera, dwarf_type)

        _camera_for_options = _initial_camera if _initial_camera != "none" else "tele"
        _initial_exposure_value = (
            cmd["setup_wide_camera"]["exposure"]
            if _initial_camera == "wide"
            else cmd["setup_camera"]["exposure"]
        )
        _initial_gain_raw = (
            cmd["setup_wide_camera"]["gain"]
            if _initial_camera == "wide"
            else cmd["setup_camera"]["gain"]
        )
        try:
            _initial_gain = int(float(_initial_gain_raw))
        except (TypeError, ValueError):
            _initial_gain = 40

        # IR filter (tele-only, user-requested Sep 2026): the schema's
        # own setup_camera.ircut field already existed and was already
        # read by dwarf_session.py at run time, but this editor never
        # exposed a way to actually CHOOSE it - it just silently carried
        # over whatever was already in a loaded file, defaulting to "0"
        # for a blank template. Stored as the per-model INDEX (string),
        # same convention dwarf_session.py's own IR_val already expects
        # - resolved to/from a NAME here purely for display, using the
        # SAME per-model table as the live camera_settings.py control
        # (not the single global D3-only table perform_set_ir_filter_v3()
        # would otherwise fall back to by name).
        try:
            _initial_ircut_index = int(cmd["setup_camera"].get("ircut", "0") or "0")
        except (TypeError, ValueError):
            _initial_ircut_index = 0
        _initial_ircut_name = next(
            (v["name"] for v in _ir_filter_table(dwarf_type).values if v["index"] == _initial_ircut_index),
            None,
        )
        try:
            _initial_binning_index = int(cmd["setup_camera"].get("binning", "0") or "0")
        except (TypeError, ValueError):
            _initial_binning_index = 0
        _initial_binning_name = "4k" if _initial_binning_index == 0 else "2k"


        with ui.row().classes("w-full gap-2") as camera_settings_section:
            exposure_input = ui.select(
                _exposure_options(_camera_for_options),
                value=_initial_exposure_value,
                label=t("prog_exposure"),
            ).classes("flex-1")
            gain_input = ui.number(
                t("prog_gain"),
                value=_initial_gain,
                step=_GAIN_STEP,
            ).classes("flex-1")
            count_input = ui.number(
                t("prog_count"),
                value=int(cmd["setup_wide_camera"]["count"] if cmd["setup_wide_camera"]["do_action"] else cmd["setup_camera"]["count"]),
                min=0,
            ).classes("w-24")
            wait_after_camera_input = ui.number(
                t("prog_wait_after_camera"), value=cmd["setup_camera"]["wait_after"], min=0
            ).classes("w-32")

        def _ir_filter_names(dwarf_type: str) -> list[str]:
            return [v["name"] for v in _ir_filter_table(dwarf_type).values]


        with ui.row().classes("w-full gap-2") as ir_filter_section:
            ir_filter_input = ui.select(
                _ir_filter_names(dwarf_type),
                value=_initial_ircut_name,
                label=t("ir_filter"),
            ).classes("flex-1")

            # Binning only on D3
            binning_input = None

            if dwarf_type == "3":
                initial_val = BINNING_NAME_TO_VAL_D3.get(_initial_binning_name, 0)

                binning_input = ui.select(
                    options=BINNING_MAP_D3,
                    value=initial_val,
                    label=t("binning"),
                ).classes("flex-1")

                binning_val = binning_input.value
    
        # Mosaic (tele-only, user-requested Sep 2026): a sub-section of
        # the tele capture settings - doMosaic off by default (a normal
        # single-target session). framingX/framingY are shown as the
        # REAL scale factor (1.00-1.80, step 0.1) for readability - the
        # API itself takes 100-180 in steps of 10 (multiply by 100),
        # confirmed via dwarf_python_api's own main_v3.py reference
        # tool. Both at 1.00x means nothing to mosaic - same rule as
        # that tool's own option_A17(), enforced again at save time
        # below (_collect_cmd()).
        _mosaic_cmd = cmd["setup_camera"]
        with ui.column().classes("w-full gap-2") as mosaic_section:
            mosaic_cb = ui.checkbox(
                t("prog_mosaic"), value=bool(_mosaic_cmd.get("doMosaic", False))
            )
            with ui.row().classes("w-full gap-2") as mosaic_fields:
                framing_x_input = ui.number(
                    t("prog_framing_x"),
                    value=int(_mosaic_cmd.get("framingX", 100)) / 100,
                    min=1.0,
                    max=1.8,
                    step=0.1,
                    format="%.1f",
                ).classes("flex-1")
                framing_y_input = ui.number(
                    t("prog_framing_y"),
                    value=int(_mosaic_cmd.get("framingY", 100)) / 100,
                    min=1.0,
                    max=1.8,
                    step=0.1,
                    format="%.1f",
                ).classes("flex-1")
                mosaic_count_input = ui.number(
                    t("prog_mosaic_count"),
                    # Falls back to matching count_input's own current
                    # value (not a hardcoded default) when mosaic_count
                    # was never set - user-requested consistency: a
                    # freshly-checked Mosaic at 1.0x/1.0x framing (1
                    # panel) should start showing the SAME total as the
                    # plain session it's replacing, not an arbitrary 45.
                    value=int(_mosaic_cmd.get("mosaic_count") or count_input.value or 1),
                    min=1,
                    max=249,
                ).classes("flex-1")

        def _panel_count(framing_x_pct: int, framing_y_pct: int) -> int:
            """Matches the official DWARFLAB app's own (undisplayed)
            behaviour, per the user's direct inspection of that app:
            2 panels if exactly one axis is extended past 1.0x, 4 if
            both are, 1 if neither (no extra framing at all - a
            "1-panel mosaic" is just a normal single capture, not a
            special case)."""
            x_extended = framing_x_pct != 100
            y_extended = framing_y_pct != 100
            if x_extended and y_extended:
                return 4
            if x_extended or y_extended:
                return 2
            return 1

        def _sync_mosaic_stack_count() -> None:
            """User-requested (Sep 2026): in the official app, the total
            "subframes to stack" count for a Mosaic session isn't
            separately entered at all - it's silently computed from
            panel_count * count_per_view (mosaic_count) and shown in the
            regular camera stack-count field, without ever explaining
            the multiplication in that app's own interface either. This
            mirrors that.

            The formula is applied UNCONDITIONALLY whenever Mosaic is
            checked (panels=1 for framing 1.0/1.0 is just the formula's
            natural result, not a special case to skip) - so count_input
            stays consistent with mosaic_count even when framing is
            brought back down to 1.0/1.0 rather than being left at a
            stale value from when it was a real multi-panel mosaic.
            Only the EDITABLE/LOCKED state differs: a genuine mosaic
            (panels > 1) locks count_input via .disable() (a real
            NiceGUI element method - a raw "readonly" Quasar prop alone
            did not reliably block the number spinner's +/- arrows in
            testing); at panels == 1 it's not really a mosaic (see
            _collect_cmd()'s own fallback), so it's re-enabled for free
            editing, same as outside Mosaic mode entirely."""
            in_mosaic = camera_choice.value == "tele" and mosaic_cb.value
            if not in_mosaic:
                count_input.enable()
                return
            try:
                fx_pct = int(round(float(framing_x_input.value or 1.0) * 100))
                fy_pct = int(round(float(framing_y_input.value or 1.0) * 100))
            except (TypeError, ValueError):
                fx_pct = fy_pct = 100
            panels = _panel_count(fx_pct, fy_pct)
            per_view = int(mosaic_count_input.value or 0)
            count_input.value = panels * per_view
            if panels == 1:
                count_input.enable()
            else:
                count_input.disable()

        def _update_mosaic_visibility() -> None:
            is_tele = camera_choice.value == "tele"
            mosaic_section.set_visibility(is_tele)
            mosaic_fields.set_visibility(is_tele and mosaic_cb.value)
            _sync_mosaic_stack_count()

        camera_choice.on_value_change(lambda _: _update_mosaic_visibility())
        mosaic_cb.on_value_change(lambda _: _update_mosaic_visibility())
        framing_x_input.on_value_change(lambda _: _sync_mosaic_stack_count())
        framing_y_input.on_value_change(lambda _: _sync_mosaic_stack_count())
        mosaic_count_input.on_value_change(lambda _: _sync_mosaic_stack_count())
        _update_mosaic_visibility()

        def _refresh_camera_validation() -> None:
            """Re-runs whenever the camera radio changes: repopulates the
            exposure dropdown for tele vs wide (their valid values
            differ), re-clamps gain into this device's range, and shows
            a warning if the value carried over from a different device/
            camera no longer fits."""
            camera = camera_choice.value if camera_choice.value != "none" else "tele"
            options = _exposure_options(camera)
            warnings = []

            current_exposure = exposure_input.value
            exposure_input.options = options
            if current_exposure in options:
                exposure_input.value = current_exposure
            else:
                exposure_input.value = None
                if current_exposure:
                    warnings.append(
                        t("prog_exposure_not_available", value=current_exposure)
                    )
            exposure_input.update()

            gain_min, gain_max = _gain_range(camera)
            gain_input.props(f"min={gain_min} max={gain_max} step={_GAIN_STEP}")
            try:
                current_gain = int(gain_input.value)
            except (TypeError, ValueError):
                current_gain = gain_min
            clamped_gain = max(gain_min, min(gain_max, current_gain))
            # Also snap to the nearest valid step (40, 50, 60...) - a
            # value imported from elsewhere (or hand-edited) might land
            # off-step even after clamping into range.
            snapped_gain = gain_min + round((clamped_gain - gain_min) / _GAIN_STEP) * _GAIN_STEP
            snapped_gain = max(gain_min, min(gain_max, snapped_gain))
            if snapped_gain != current_gain:
                warnings.append(
                    t("prog_gain_clamped", value=current_gain, clamped=snapped_gain)
                )
            gain_input.value = snapped_gain

            import_warning_label.set_text(" \u00b7 ".join(warnings))

        def _update_camera_visibility() -> None:
            camera_settings_section.set_visibility(camera_choice.value != "none")
            # IR filter is TELE ONLY - no wide-camera equivalent command
            # exists at all (see camera_settings.py's own note on this).
            ir_filter_section.set_visibility(camera_choice.value == "tele")

        camera_choice.on_value_change(
            lambda _: (_update_camera_visibility(), _refresh_camera_validation())
        )
        _update_camera_visibility()
        _refresh_camera_validation()

        status_label = ui.label("").classes("text-sm")

        def _collect_cmd(require_description: bool = True) -> dict | None:
            """Builds the "command" dict from the CURRENT widget values -
            shared by handle_save() (single program) and the Telescopius
            import button below (used as the TEMPLATE for a whole
            chained sequence). Returns None if required fields are
            missing (status_label is updated with the specifics either
            way).

            require_description=False (Telescopius import only, user-
            reported bug fix Sep 2026): each Telescopius/Mosaic CSV row
            gets its OWN generated description (generate_chained_
            programs() overwrites it per row), so the top-level
            Description field here is only a throwaway TEMPLATE value -
            requiring it to be filled in blocked every CSV import with
            "Please fill in: Description" whenever that field was
            reasonably left blank (there's nothing meaningful to put
            there when every row gets a different one anyway).

            Forces one final _sync_mosaic_stack_count() pass first
            (user-reported Sep 2026): count_input's on_value_change-
            driven sync could lag behind mosaic_count_input/framing
            changes made via the number spinner's +/- arrows rather
            than typed input, and _collect_cmd() reading a stale
            count_input.value would have SAVED the wrong number to the
            file, not just displayed it wrong - a correctness issue, not
            only a cosmetic one. Cheap and idempotent, safe to call
            unconditionally right before reading the fields it touches."""
            _sync_mosaic_stack_count()

            missing = []
            if require_description and not description.value.strip():
                missing.append(t("prog_description"))
            if not date_input.value.strip():
                missing.append(t("prog_date"))
            if not time_input.value.strip():
                missing.append(t("prog_time"))
            if camera_choice.value != "none":
                if not exposure_input.value:
                    missing.append(t("prog_exposure"))
                if gain_input.value is None:
                    missing.append(t("prog_gain"))
            if goto_mode.value == "solar" and not solar_target.value:
                missing.append(t("prog_solar_target"))
            if goto_mode.value == "manual" and not (manual_target.value and ra_input.value and dec_input.value):
                missing.append(t("prog_goto_manual"))
            # Mosaic requires a prior goto - confirmed by real testing
            # (Sep 2026): without one, the device rejects the mosaic
            # start with CODE_ASTRO_NEED_GOTO_DSO (-11518). Unlike a
            # plain single-target capture (which the device accepts
            # wherever the telescope happens to be pointed), Mosaic
            # apparently needs a confirmed DSO goto to compute its panel
            # grid around - this isn't optional the way it is for a
            # normal session, so it's a hard validation error here
            # rather than a soft warning.
            # Mosaic requires a prior MANUAL (DSO) goto specifically -
            # confirmed by real testing (Sep 2026): without one, the
            # device rejects the mosaic start with CODE_ASTRO_NEED_GOTO_
            # DSO (-11518) - "DSO" as in Deep Sky Object, i.e. a Solar
            # system target (goto_solar) does NOT satisfy this, only
            # goto_manual does. Mosaic is an Astro-only feature, not
            # applicable to Solar system targets at all.
            if camera_choice.value == "tele" and mosaic_cb.value and goto_mode.value != "manual":
                missing.append(t("prog_mosaic_needs_goto"))
            if missing:
                status_label.set_text(t("prog_missing_fields", fields=", ".join(missing)))
                status_label.classes(replace="text-sm text-red-700")
                return None

            is_wide = camera_choice.value == "wide"
            is_no_camera = camera_choice.value == "none"
            is_tele = camera_choice.value == "tele"
            wait_after_cam = int(wait_after_camera_input.value or 30)

            # Mosaic (tele-only): both framings at 1.00x means nothing
            # to mosaic - same rule dwarf_session.py enforces again at
            # run time (defense in depth, not relied on solely here) -
            # computed here too so a SAVED file already reflects the
            # effective state rather than a stale "requested but
            # ineffective" doMosaic=True.
            framing_x_pct = int(round(float(framing_x_input.value or 1.0) * 100))
            framing_y_pct = int(round(float(framing_y_input.value or 1.0) * 100))
            do_mosaic_effective = (
                is_tele and mosaic_cb.value and not (framing_x_pct == 100 and framing_y_pct == 100)
            )

            def _coord(value: str):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return ""

            if dwarf_type == "3" and binning_input is not None:
                current_binning_val = binning_input.value
            elif dwarf_type == "5":
                current_binning_val = 1
            else:
                current_binning_val = 0

            return {
                "id_command": {
                    **cmd["id_command"],
                    "description": description.value.strip(),
                    "date": date_input.value.strip(),
                    "time": time_input.value.strip(),
                    "max_retries": int(retries_input.value or 3),
                },
                "eq_solving": {
                    "do_action": eq_solving_cb.value,
                    "wait_before": int(wait_before_input.value or 0),
                    "wait_after": int(wait_after_input.value or 0),
                },
                "auto_focus": {
                    "do_action": auto_focus_cb.value,
                    "wait_before": int(wait_before_input.value or 0),
                    "wait_after": int(wait_after_input.value or 0),
                },
                "infinite_focus": {
                    "do_action": infinite_focus_cb.value,
                    "wait_before": int(wait_before_input.value or 0),
                    "wait_after": int(wait_after_input.value or 0),
                },
                "calibration": {
                    "do_action": calibration_cb.value,
                    "wait_before": int(wait_before_input.value or 0),
                    "wait_after": int(wait_after_input.value or 0),
                },
                "goto_solar": {
                    "do_action": goto_mode.value == "solar",
                    "target": solar_target.value if goto_mode.value == "solar" else "",
                    "wait_after": int(wait_after_target_input.value or 0),
                },
                "goto_manual": {
                    "do_action": goto_mode.value == "manual",
                    "target": manual_target.value if goto_mode.value == "manual" else "",
                    "ra_coord": _coord(ra_input.value) if goto_mode.value == "manual" else "",
                    "dec_coord": _coord(dec_input.value) if goto_mode.value == "manual" else "",
                    "wait_after": int(wait_after_target_input.value or 0),
                },
                "setup_camera": {
                    "do_action": (not is_wide and not is_no_camera) and int(count_input.value or 0) != 0,
                    "exposure": exposure_input.value or "",
                    "gain": str(int(gain_input.value)),
                    "binning": str(current_binning_val), 
                    "ircut": str(_ir_filter_index_by_name(dwarf_type, ir_filter_input.value))
                    if ir_filter_input.value
                    else cmd["setup_camera"].get("ircut", "0"),
                    "count": str(int(count_input.value or 0)),
                    "wait_after": wait_after_cam,
                    "doMosaic": do_mosaic_effective,
                    "framingX": framing_x_pct,
                    "framingY": framing_y_pct,
                    "mosaic_count": int(mosaic_count_input.value or 45),
                },
                "setup_wide_camera": {
                    "do_action": is_wide and int(count_input.value or 0) != 0,
                    "exposure": (exposure_input.value or "") if is_wide else cmd["setup_wide_camera"]["exposure"],
                    "gain": str(int(gain_input.value)) if is_wide else cmd["setup_wide_camera"]["gain"],
                    "count": str(int(count_input.value or 0)) if is_wide else cmd["setup_wide_camera"]["count"],
                    "wait_after": wait_after_cam,
                },
            }

        def handle_save() -> None:
            new_cmd = _collect_cmd()
            if new_cmd is None:
                return
            new_program = {"command": new_cmd}

            dirs = ensure_dirs(session)
            filename = _filename_for(new_program)
            filepath = os.path.join(dirs["TODO_DIR"], filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(new_program, f, indent=4)

            message = t("prog_saved", filename=filename)
            # Soft, non-blocking heads-up: mosaic was checked but both
            # framings are 1.00x, so _collect_cmd() already saved it as
            # a normal (non-mosaic) session - matching what dwarf_
            # session.py itself would fall back to at run time anyway,
            # but worth surfacing here rather than silently differing
            # from what the checkbox showed.
            if camera_choice.value == "tele" and mosaic_cb.value and not new_cmd["setup_camera"]["doMosaic"]:
                message += " " + t("prog_mosaic_ineffective")
            status_label.set_text(message)
            status_label.classes(replace="text-sm text-green-700")
            if on_saved:
                on_saved(filepath)

        ui.button(t("prog_save"), icon="save", on_click=handle_save).props("color=primary")

        # --- Telescopius / Mosaic CSV import (point C) --------------------
        # Uses the CURRENT form's settings (calibration, camera exposure/
        # gain/count, wait times...) as a shared template, generating one
        # program per CSV row with only description/target/date/time/
        # goto_manual overridden - each row's start time is the previous
        # row's own estimated finish time (see components/
        # telescopius_import.py's generate_chained_programs()).
        ui.label(t("prog_telescopius_hint")).classes("text-xs text-grey-6 mt-3")
        telescopius_status = ui.label("").classes("text-xs")

        async def handle_telescopius_upload(e) -> None:
            from components.telescopius_import import generate_chained_programs, parse_csv_rows

            # require_description=False: each CSV row gets its own
            # generated description (see _collect_cmd()'s own docstring
            # for the bug this fixes) - the top-level field is just a
            # throwaway template value here, not meaningful to require.
            template_cmd = _collect_cmd(require_description=False)
            if template_cmd is None:
                return

            # Encoding fallback (user-reported Sep 2026): real Telescopius
            # CSV exports aren't guaranteed to be UTF-8 - try that first
            # (utf-8-sig also strips a BOM if present), and fall back to
            # Latin-1 (ISO-8859-1) if decoding fails, since Latin-1 can
            # decode ANY byte sequence without raising (unlike guessing
            # wrong the other way around, which would corrupt accented
            # characters silently rather than erroring loudly).
            try:
                csv_text = await e.file.text("utf-8-sig")
            except UnicodeDecodeError:
                csv_text = await e.file.text("latin-1")

            fmt, rows = parse_csv_rows(csv_text)
            if fmt is None:
                telescopius_status.set_text(t("prog_telescopius_bad_format"))
                telescopius_status.classes(replace="text-xs text-red-700")
                return
            if not rows:
                telescopius_status.set_text(t("prog_telescopius_empty"))
                telescopius_status.classes(replace="text-xs text-red-700")
                return

            start_dt = datetime.strptime(
                f"{template_cmd['id_command']['date']} {template_cmd['id_command']['time']}",
                "%Y-%m-%d %H:%M:%S",
            )
            programs = generate_chained_programs(template_cmd, rows, start_dt)

            dirs = ensure_dirs(session)
            for program in programs:
                filename = _filename_for(program)
                filepath = os.path.join(dirs["TODO_DIR"], filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(program, f, indent=4)

            telescopius_status.set_text(
                t("prog_telescopius_generated", count=len(programs), format=fmt)
            )
            telescopius_status.classes(replace="text-xs text-green-700")
            if on_saved:
                on_saved(None)

        ui.upload(
            label=t("prog_telescopius_upload"),
            auto_upload=True,
            on_upload=handle_telescopius_upload,
        ).props("accept=.csv").classes("w-full")