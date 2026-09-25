import json
import time
from datetime import datetime, timedelta

from dwarf_python_api.lib.dwarf_utils import perform_GoLive
from dwarf_python_api.lib.dwarf_utils import perform_enter_astro_mode
from dwarf_python_api.lib.dwarf_utils import perform_enter_shooting_mode
from dwarf_python_api.lib.dwarf_utils import SHOOTING_MODE_SUN
from dwarf_python_api.lib.dwarf_utils import SHOOTING_MODE_MOON
from dwarf_python_api.lib.dwarf_utils import SHOOTING_MODE_PLANET
from dwarf_python_api.lib.dwarf_utils import SHOOTING_TECH_DEEP_SKY
from dwarf_python_api.lib.dwarf_utils import perform_calibration
from dwarf_python_api.lib.dwarf_utils import perform_goto
from dwarf_python_api.lib.dwarf_utils import perform_stop_goto
from dwarf_python_api.lib.dwarf_utils import perform_goto_stellar
from dwarf_python_api.lib.dwarf_utils import parse_ra_to_float
from dwarf_python_api.lib.dwarf_utils import parse_dec_to_float
from dwarf_python_api.lib.dwarf_utils import perform_takeAstroPhoto
from dwarf_python_api.lib.dwarf_utils import perform_continue_shooting
from dwarf_python_api.lib.dwarf_utils import perform_clear_needs_continue_shooting
from dwarf_python_api.lib.dwarf_session_socket import get_client_status
from dwarf_python_api.lib.dwarf_utils import perform_stopAstroPhoto, perform_stopAstroWidePhoto
from dwarf_python_api.lib.dwarf_utils import perform_read_astro_stacking_status_v3
from dwarf_python_api.lib.dwarf_utils import perform_set_astro_exposure_by_name_v3
from dwarf_python_api.lib.dwarf_utils import perform_set_astro_gain_v3
from dwarf_python_api.lib.dwarf_utils import perform_set_astro_ir_filter_v3
from dwarf_python_api.lib.dwarf_utils import perform_set_astro_stack_count_v3
from dwarf_python_api.lib.dwarf_utils import perform_set_astro_mosaic_count_v3
from dwarf_python_api.lib.dwarf_utils import perform_start_mosaic_v3
from dwarf_python_api.lib.dwarf_utils import perform_set_astro_stack_binning_v3
from dwarf_python_api.lib.dwarf_utils import perform_takeAstroWidePhoto
from dwarf_python_api.lib.dwarf_utils import perform_start_autofocus
from dwarf_python_api.lib.dwarf_utils import start_polar_align
from dwarf_python_api.lib.dwarf_utils import perform_time

# V3: the live HTTP API is the only confirmed-reliable way to read back the
# CURRENT exposure/gain/filter values in V3 - CMD_CAMERA_TELE_GET_ALL_PARAMS
# (used by perform_get_all_camera_setting) does not respond on V3 hardware.
from dwarf_python_api.lib.dwarf_utils import perform_read_camera_params_http_v3
from dwarf_python_api.lib.data_utils import get_exposure_name_by_index
from dwarf_python_api.lib.data_utils import get_gain_name_by_index
from dwarf_python_api.lib.data_wide_utils import get_wide_exposure_name_by_index
from dwarf_python_api.lib.data_wide_utils import get_wide_gain_name_by_index

# import data for config.py
import dwarf_python_api.get_config_data as config_py

# The config value for dwarf_id is offset by -1 (stored as one less than the actual ID).
# the value return by get_config_data must be used with these functions
from dwarf_python_api.get_config_data import config_to_dwarf_id_str, config_to_dwarf_id_int

import dwarf_python_api.lib.my_logger as log

def select_solar_target (target, session=None):
   
    target_id = None
    result = False
   
    if (target.lower() == "mercury"):
        target_id = 1

    if (target.lower() == "venus"):
        target_id = 2

    if (target.lower() == "mars"):
        target_id = 3

    if (target.lower() == "jupiter"):
        target_id = 4

    if (target.lower() == "saturn"):
        target_id = 5

    if (target.lower() == "uranus"):
        target_id = 6

    if (target.lower()== "neptune"):
        target_id = 7

    if (target.lower() == "moon"):
        target_id = 8

    if (target.lower() == "sun"):
        target_id = 9

    if target_id:
        target_name = target.capitalize()
        result = perform_goto_stellar(target_id, target_name, session=session)
    else:
        log.error(f"The solar system object ({target}) is unknown")
    return result

# Define step descriptions
STEP_DESCRIPTIONS = {
    "step_0": "initialization",
    "step_1a": "Send GO LIVE Command to close previous imaging session",
    "step_1b": "Do EQ Solving",
    "step_1c": "Do Automatic Autofocus",
    "step_1d": "Do Infinite Autofocus",
    "step_1e": "Entering Astro/DSO (or Solar) shooting mode",
    "step_2": "Set Exposure to 1s for Calibration",
    "step_3": "Set Gain to 80 for Calibration",
    "step_4": "Set IR Filter for Calibration",
    "step_5": "Set Binning to 4k for Calibration",
    "step_6": "Send Stop Goto to start Calibration command",
    "step_7": "Perform Calibration process",
    "step_8": "Perform Goto Solar System target",
    "step_9": "Perform Goto DSO target",
    "step_10": "Setup Astro Photo Parameters",
    "step_11": "Starting Astrophoto Session",
    "step_12": "Wait End of Astrophoto Session",
    "step_13": "Setup Astro Wide Photo Parameters",
    "step_14": "Starting Astro wide photo Session",
    "step_15": "Wait End of Astro wide photo Session",
    "step_16": "Stop Tele and Wide Astro photo Session",
}

def _parse_end_time(value):
    """'HH:MM' (24h, program_editor.py's prog_end_time field) -> a
    datetime for the NEXT occurrence of that clock time, or None if
    blank/unset/unparseable.

    MIDNIGHT ROLLOVER (fixed - was a known limitation): a session
    started at 22:00 with end_time="01:30" means "1:30 AM tomorrow",
    not "01:30 earlier today" - if the naive "today at HH:MM" has
    already passed relative to right now, this rolls it to tomorrow
    instead. Without this, the very first check in
    _wait_for_astro_end() below would see an already-past deadline and
    stop the capture almost immediately, instead of after actually
    crossing midnight."""
    if not value:
        return None
    try:
        hour, minute = str(value).strip().split(":")
        candidate = datetime.now().replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        if candidate <= datetime.now():
            candidate += timedelta(days=1)
        return candidate
    except (ValueError, AttributeError):
        log.warning(f"Invalid end_time value ignored: {value!r}")
        return None

def _wait_for_astro_end(stop_fn, end_time, interrupted, session, camera_type="Tele", progress_callback=None):
    """User-requested Sep 2026: \"Finish at specified time (optional, if
    number of images not yet finished))\". SECOND DESIGN (the first,
    thread-based one - see git history - had a confirmed bug, also
    user-reported Sep 2026): running perform_waitEndAstroPhoto() on a
    background thread WHILE calling stop_fn() (perform_stopAstroPhoto /
    perform_stopAstroWidePhoto) concurrently raced two consumers against
    the SAME session.client_instance.result_queue - that queue has no
    notion of "this message belongs to that specific caller", so two
    simultaneous reads of it can steal each other's response. In a real
    test this left an orphaned wait running for several more minutes
    after the capture had already stopped cleanly, eventually timing
    out and firing a spurious retry.

    This version never has more than ONE consumer of that queue at a
    time. Instead of blocking on perform_waitEndAstroPhoto()
    continuously, it polls perform_read_astro_stacking_status_v3() -
    confirmed (see that function's own docstring) to read a passively-
    updated LOCAL cache and send NO network request at all, so it never
    touches the shared queue - to detect natural completion. Once the
    cache says the device is no longer capturing, that IS the
    confirmation (the same device notification perform_waitEndAstroPhoto()
    would otherwise have consumed fed this cache too) - no separate
    "confirm" call is made or needed.

    If `end_time` is reached first, stop_fn() is called - and awaited -
    on THIS thread, with nothing else reading the queue concurrently.

    `end_time` may be None (user-requested Sep 2026: "j'ai essaye
    d'arreter la capture... mais cela n'a pas marche" - a real overnight
    test confirmed the OLD design, calling perform_waitEndAstroPhoto()
    directly whenever no end time was set, never checked interrupted()
    at all once inside that single blocking call - clicking Stop just
    set the flag with nothing left to notice it until the capture
    finished naturally on its own, which for a long/cloudy session
    could be many more minutes). With end_time=None this function skips
    only the "reached scheduled end time" branch below and otherwise
    behaves identically - still polling the local cache every 2s and
    checking interrupted() each time, so Stop now takes effect within a
    couple of seconds regardless of whether an end time was set. Now
    called unconditionally from both call sites below - no more direct
    perform_waitEndAstroPhoto()/perform_waitEndAstroWidePhoto() calls
    outside of this function."""
    while True:
        if interrupted():
            log.notice("Stop requested - sending stop capture command to device")
            stop_fn(session=session)
            return False

        status = perform_read_astro_stacking_status_v3(session=session, type=camera_type)
        if status and not status.get("capturing"):
            return True

        if end_time is not None and datetime.now() >= end_time:
            log.notice(
                f"Reached scheduled end time ({end_time:%H:%M}) - image count not finished, stopping capture now"
            )
            if progress_callback:
                progress_callback("step_16", "success")
            stop_fn(session=session)
            return True

        time.sleep(2)

def try_attemps (function, function_succeed_message, max_attempts = 3, interrupted=lambda: False):
    # Try to perform the action up to 3 times by default
    attempts = 0
    continue_action = False

    # Try to perform the action up to 3 times
    while attempts < max_attempts:
        if interrupted():  # Check before attempting
            return False

        continue_action = function()  # action to test

        if continue_action:
            if function_succeed_message:
                log.notice(function_succeed_message)
            break  # Exit the loop if the action succeeds
 
        attempts += 1
        log.notice(f"Attempt {attempts} failed. Retrying...")

    # If the maximum number of attempts is reached and continue_action is False
    if not continue_action:
        log.notice(f"Action failed after {max_attempts} attempts.")

    return continue_action


def _ir_filter_display_name(dwarf_id, IR_val: str) -> str:
    """User-requested Sep 2026: "In the filter display during a
    session, you can enter the actual value, not the number" - factored
    out of the model-dependent naming ternary already used a few lines
    below for the "To do => Astro Photo" log block, so both that block
    and the step-trace notice added for verification (see the
    perform_set_astro_ir_filter_v3() call sites) show the SAME real
    name rather than duplicating (and risking drifting) this per-model
    mapping in two places."""
    dwarf_type = config_to_dwarf_id_str(dwarf_id)
    if dwarf_type == "3":
        return {"0": "VIS_FILTER", "1": "ASTRO_FILTER"}.get(IR_val, "DUAL_BAND")
    if dwarf_type == "5":
        return {"0": "DARK", "1": "ASTRO_FILTER"}.get(IR_val, "DUAL_BAND")
    return "IR_CUT" if IR_val == "0" else "IR_PASS"


def start_dwarf_session(program, stop_event=None, session=None, progress_callback=None):
    try:
        def interrupted():
            return stop_event is not None and stop_event.is_set()

        if session is not None:
            dwarf_id = session.config.dwarf_model_id or "2"
            dwarf_ip = session.config.dwarf_ip or ""
        else:
            data_config = config_py.get_config_data()
            dwarf_id = "2"  # Default Dwarf ID
            if data_config["dwarf_id"]:
                dwarf_id = data_config['dwarf_id']

            dwarf_ip = ""
            if data_config["ip"]:
                dwarf_ip = data_config['ip']

        dump_json = json.dumps(program, indent=4)

        log.notice("######################")
        log.notice(f"Starting new Session for Dwarf {config_to_dwarf_id_int(dwarf_id)} on {dwarf_ip}")
        log.notice("######################")
        log.debug(f"program: {dump_json}")
        log.debug("######################")

        # Extracting program parameters
        auto_focus = program.get('auto_focus', {}).get('do_action')
        infinite_focus = program.get('infinite_focus', {}).get('do_action')
        calibration = program.get('calibration', {}).get('do_action')
        eq_solving = program.get('eq_solving', {}).get('do_action')
        goto_solar = program.get('goto_solar', {}).get('do_action')
        goto_manual = program.get('goto_manual', {}).get('do_action')
        take_photo = program.get('setup_camera', {}).get('do_action')
        take_widephoto = program.get('setup_wide_camera', {}).get('do_action')

        # Initialize camera parameter variables to avoid unbound errors
        exp_val = None
        gain_val = None
        binning_val = None
        IR_val = None
        count_val = None
        wide_exp_val = None
        wide_gain_val = None
        wide_count_val = None

        # Log what will be done
        if auto_focus:
            log.notice(f" To do => Automatic Autofocus")
        if infinite_focus:
            log.notice(f" To do => Infinite Autofocus")
        if calibration:
            log.notice(f" To do => Calibration")
        if eq_solving:
            log.notice(f" To do => Automatic EQ Solving")

        # Validate goto_solar parameters
        if goto_solar:
            target_name = program.get('goto_solar', {}).get('target')
            if target_name:
                log.notice(f" To do => GOTO SOLAR SYSTEM : {target_name}")
            else:
                log.error(f" Error in Settings => GOTO SOLAR SYSTEM : 'target' is not valid, task ignored!")
                goto_solar = False

        # Validate goto_manual parameters
        manual_RA = program.get('goto_manual', {}).get('ra_coord')
        manual_declination = program.get('goto_manual', {}).get('dec_coord')
        target_name = program.get('goto_manual', {}).get('target')
        if goto_manual:
            if target_name and manual_RA and manual_declination:
                log.notice(f" To do => GOTO : {target_name}")
            else:
                log.error(f" Error in Settings => GOTO : parameters are not valid, task ignored!")
                goto_manual = False

        # Validate photo parameters
        if take_photo:
            exp_val = str(program['setup_camera'].get('exposure', "0"))
            gain_val = str(program['setup_camera'].get('gain', "0"))
            binning_val = str(program['setup_camera'].get('binning', "0"))
            IR_val = str(program['setup_camera'].get('ircut', "0"))
            count_val = str(program['setup_camera'].get('count', "0"))
            end_time_val = _parse_end_time(program['setup_camera'].get('end_time', ''))

            # Mosaic (tele-only, user-requested Sep 2026): a sub-section
            # of the tele capture settings, backward-compatible -
            # missing keys (an older program file saved before this was
            # added) default to doMosaic=False, exactly like a normal
            # single-target session.
            do_mosaic = bool(program['setup_camera'].get('doMosaic', False))
            framing_x = int(program['setup_camera'].get('framingX', 100))
            framing_y = int(program['setup_camera'].get('framingY', 100))
            mosaic_count_val = str(program['setup_camera'].get('mosaic_count', "45"))
            # Both at 100 (1.00x, i.e. no extra framing in either axis)
            # means there is nothing to mosaic - same rule as main_v3.py's
            # own option_A17() (dwarf_python_api's reference CLI tool).
            if do_mosaic and framing_x == 100 and framing_y == 100:
                log.warning(" Mosaic requested but framingX/framingY are both 1.00x - nothing to mosaic, falling back to a normal session.")
                do_mosaic = False
            # Mosaic requires a prior MANUAL (DSO) goto specifically -
            # confirmed by real hardware testing (Sep 2026): without
            # one, the device rejects the mosaic start with CODE_ASTRO_
            # NEED_GOTO_DSO (-11518) - "DSO" as in Deep Sky Object. A
            # Solar system goto (goto_solar) does NOT satisfy this -
            # Mosaic is an Astro-only feature, not applicable to Solar
            # system targets at all (corrected Sep 2026: an earlier
            # version of this check wrongly accepted goto_solar too).
            # The program editor (astro_dwarf_ui) validates this at save
            # time too - this is a second guard for a hand-edited or
            # imported program file that bypassed that.
            if do_mosaic and not goto_manual:
                log.warning(" Mosaic requested but no Manual (DSO) goto is configured - the device would reject this with CODE_ASTRO_NEED_GOTO_DSO (Solar system targets don't count), falling back to a normal session.")
                do_mosaic = False

            if exp_val or gain_val or binning_val or IR_val or count_val:
                log.notice(f" To do => Astro Photo with these parameters")
                log.notice(f"     exposure  => {exp_val}s")
                log.notice(f"     gain  => {gain_val}")
                log.notice(f"     binning => {'4k' if binning_val == '0' else '2k'}")
                log.notice(f"real binning => {binning_val}")
                log.notice(f"     IR => {_ir_filter_display_name(dwarf_id, IR_val)}")
                log.notice(f"     number of images  => {count_val}")
            else:
                log.warning(f" Error in Settings => PHOTO : none settings found, task ignored!")
                take_photo = False

        # Validate wide photo parameters
        if take_widephoto:
            wide_exp_val = str(program['setup_wide_camera'].get('exposure', "0"))
            wide_gain_val = str(program['setup_wide_camera'].get('gain', "0"))
            wide_count_val = str(program['setup_wide_camera'].get('count', "0"))  # Fix: use separate variable
            wide_end_time_val = _parse_end_time(program['setup_wide_camera'].get('end_time', ''))

            if wide_exp_val or wide_gain_val or wide_count_val:
                log.notice(f" To do => Astro Wide Photo with these parameters")
                log.notice(f"     exposure  => {wide_exp_val}s")
                log.notice(f"     gain  => {wide_gain_val}")
                log.notice(f"     number of images  => {wide_count_val}")
            else:
                log.warning(f" Error in Settings => WIDE PHOTO : none settings found, task ignored!")
                take_widephoto = False

        # Session initialization
        log.notice("######################")
        continue_action = try_attemps(lambda: perform_time(session=session), "Init succeeded.")
        verify_action(continue_action, "step_0", progress_callback=progress_callback)

        # V3: SET_LOCATION and CMD_GLOBAL_TASK_GET_DEVICE_STATE_INFO are
        # now both sent automatically - location at the connection layer
        # (astro_dwarf_scheduler.start_connection()/start_STA_connection(),
        # alongside SET_TIME/SET_TIME_ZONE), device-state-info at the WS
        # protocol layer (websockets_utils.send_message_init(), once per
        # connection) - matching the official app's own behavior. No
        # explicit calls needed here anymore.

        # Go Live
        continue_action = perform_GoLive(session=session)
        verify_action(continue_action, "step_1a", progress_callback=progress_callback)

        # V3: switch the device into the right shooting mode + technique
        # (SWITCH_SHOOTING_MODE/ENTER_CAMERA/SWITCH_SHOOTING_TECH,
        # confirmed on real hardware) - without this, CMD_ASTRO_START_GOTO_DSO
        # and other astro commands fail (CODE_ASTRO_GOTO_FAILED / -11505)
        # because the device is still in whatever mode it was last in.
        #
        # Field-confirmed (Aug 2026): a solar-system target (Sun/Moon/
        # planet) needs its own specific mode (8/9/10), NOT the DSO mode
        # (2) used for everything else in this session (manual GOTO,
        # calibration, EQ Solving) - entering DSO mode before a solar
        # system GOTO would fail the same way DSO GOTO failed before this
        # was fixed for DSO.
        if goto_solar:
            solar_target = (program.get('goto_solar', {}).get('target') or "").lower()
            if solar_target == "sun":
                solar_mode = SHOOTING_MODE_SUN
            elif solar_target == "moon":
                solar_mode = SHOOTING_MODE_MOON
            else:
                solar_mode = SHOOTING_MODE_PLANET
            log.notice(f"Entering Solar shooting mode (mode={solar_mode}) for target: {solar_target}")
            continue_action = perform_enter_shooting_mode(solar_mode, SHOOTING_TECH_DEEP_SKY, session=session)
        else:
            log.notice("Entering Astro/DSO shooting mode")
            continue_action = perform_enter_astro_mode(session=session)
        # user-reported Sep 2026: "on utilise plusieurs fois [step_1a]
        # alors qu'on fait autre chose" - this is entering a shooting
        # mode, not the Go Live call step_1a's own label actually
        # describes.
        verify_action(continue_action, "step_1e", progress_callback=progress_callback)

        # Auto Focus
        if auto_focus:
            wait_before = program.get('auto_focus', {}).get('wait_before', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_before} seconds")
            time.sleep(wait_before)
            if interrupted(): return
            log.notice("Processing automatic autofocus")
            continue_action = perform_start_autofocus(False, session=session)
            if interrupted(): return
            verify_action(continue_action, "step_1c", progress_callback=progress_callback)
            wait_after = program.get('auto_focus', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return

        # Infinite Focus
        if infinite_focus:
            wait_before = program.get('infinite_focus', {}).get('wait_before', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_before} seconds")
            time.sleep(wait_before)
            if interrupted(): return
            log.notice("Processing infinite autofocus")
            continue_action = perform_start_autofocus(True, session=session)
            if interrupted(): return
            verify_action(continue_action, "step_1d", progress_callback=progress_callback)
            wait_after = program.get('infinite_focus', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return

        # EQ Solving - Fix: Execute when eq_solving is True
        if eq_solving:
            # Field-confirmed (Aug 2026): EQ Solving needs an infinite
            # autofocus done immediately before it, regardless of whether
            # the "infinite_focus" step above already ran (it might be
            # disabled independently in the program config, or have run
            # too long before this point) - without it, EQ Solving fails.
            if not infinite_focus:
                log.notice("Processing infinite autofocus (forced before EQ Solving)")
                continue_action = perform_start_autofocus(True, session=session)
                if interrupted(): return
                verify_action(continue_action, "step_1d", progress_callback=progress_callback)
                time.sleep(5)

            continue_action = perform_stop_goto(session=session)
            if interrupted(): return
            verify_action(continue_action, "step_6", progress_callback=progress_callback)
            if interrupted(): return
            time.sleep(5)
            if interrupted(): return
            wait_before = program.get('eq_solving', {}).get('wait_before', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_before} seconds")
            time.sleep(wait_before)
            if interrupted(): return
            log.notice("Processing EQ Solving")
            continue_action = start_polar_align(session=session)
            if interrupted(): return
            verify_action(continue_action, "step_1b", progress_callback=progress_callback)
            # Visible step-log trace of the EQ result (user-requested Sep
            # 2026: "tracer a l'ecran apres l'etape EQ... dans les
            # programmes automatiques") - azi_err/alt_err are already
            # cached on the client after start_polar_align()'s own
            # response (see websockets_utils.py) but were only ever
            # surfaced through the manual session-page button before
            # this; reading them here makes them show up in the same
            # step trace the scheduled program's other steps already use
            # (progress_callback), without needing to open logs.
            eq_status = get_client_status(session).get("fullStatus", {})
            eq_azi = eq_status.get("eqAziErr")
            eq_alt = eq_status.get("eqAltErr")
            if eq_azi is not None and eq_alt is not None:
                log.notice(f"EQ Solving result: azimuth {eq_azi:+.2f}\u00b0, altitude {eq_alt:+.2f}\u00b0")
                if progress_callback:
                    # step_key doubles as the displayed label here (via
                    # STEP_DESCRIPTIONS.get(step_key, step_key)'s own
                    # fallback-to-raw-key behaviour in scheduler_runner.py)
                    # since this is dynamic per-run text, not a fixed,
                    # reusable step description - status="success" gives
                    # it a proper checkmark icon in the step trace rather
                    # than an unstyled generic circle.
                    progress_callback(
                        f"EQ Solving: azimuth {eq_azi:+.2f}\u00b0, altitude {eq_alt:+.2f}\u00b0",
                        "success",
                    )
            wait_after = program.get('eq_solving', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return

        # Calibration
        if calibration:
            log.notice("Processing Calibration")
            log.notice("    Set Exposure to 1s")
            continue_action = perform_set_astro_exposure_by_name_v3("1", dwarf_id=str(config_to_dwarf_id_str(dwarf_id)), session=session)
            if interrupted(): return
            verify_action(continue_action, "step_2", progress_callback=progress_callback)
            
            log.notice("    Set Gain to 80")
            continue_action = perform_set_astro_gain_v3(80, session=session)
            if interrupted(): return
            verify_action(continue_action, "step_3", progress_callback=progress_callback)
            if config_to_dwarf_id_str(dwarf_id) >= "3":
                log.notice("    Set IR to Astro Filter")
            else:
                log.notice("    Set IR to IR_PASS")
            # All three models confirmed on the modern path (user-
            # updated Sep 2026, THREE independent network captures -
            # D3, Mini, and now D2 too): same param_id, values sent
            # and matching each model's own name set (D2: IR_CUT/
            # IR_PASS at 0/1; D3/Mini: Astro/Duo-Band at 1/2, VIS or
            # DARK at 0) - only the NAMES differ per model, the actual
            # mechanism is universal. No legacy fallback needed
            # anymore for this call.
            continue_action = perform_set_astro_ir_filter_v3(1, session=session)
            if interrupted(): return
            verify_action(continue_action, "step_4", progress_callback=progress_callback)
            
            log.notice("    Set Binning to 4k")
            # D3-ONLY (corrected, user-confirmed Sep 2026): the official
            # DWARFLAB app itself only exposes binning control for the
            # Dwarf 3 - not D2, not Mini. An earlier version of this
            # gate used ">= 3" (D3 or Mini), based only on D2's own
            # observed 150s silent timeout with no confirmation of
            # Mini's own behavior - too permissive now that the
            # official app's own actual restriction is confirmed.
            if config_to_dwarf_id_str(dwarf_id) == "3":
                continue_action = perform_set_astro_stack_binning_v3(0, session=session)
                if interrupted(): return
                verify_action(continue_action, "step_5", progress_callback=progress_callback)
            
            time.sleep(5)
            if interrupted(): return
            print_camera_data(session=session)
            if interrupted(): return
            
            continue_action = perform_stop_goto(session=session)
            if interrupted(): return
            verify_action(continue_action, "step_6", progress_callback=progress_callback)
            time.sleep(5)
            if interrupted(): return
            
            log.notice("Starting Calibration")
            wait_before = program.get('calibration', {}).get('wait_before', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_before} seconds")
            time.sleep(wait_before)
            if interrupted(): return
            continue_action = perform_calibration(session=session)
            if interrupted(): return
            verify_action(continue_action, "step_7", progress_callback=progress_callback)
            wait_after = program.get('calibration', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return

        # Goto Solar System
        if goto_solar:
            target_name = program.get('goto_solar', {}).get('target')
            log.notice(f"Processing Goto Solar System : {target_name}")
            continue_action = select_solar_target(target_name, session=session)
            if interrupted(): return
            verify_action(continue_action, "step_8", progress_callback=progress_callback)
            wait_after = program.get('goto_solar', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return

        # Goto Manual
        if goto_manual:
            target_name = program.get('goto_manual', {}).get('target')
            log.notice(f"Processing Goto : {target_name}")
            try:
                decimal_RA = float(manual_RA)
            except ValueError:
                decimal_RA = parse_ra_to_float(manual_RA)

            try:
                decimal_Dec = float(manual_declination)
            except ValueError:
                decimal_Dec = parse_dec_to_float(manual_declination)

            continue_action = perform_goto(decimal_RA, decimal_Dec, target_name, session=session)
            if interrupted(): return
            verify_action(continue_action, "step_9", progress_callback=progress_callback)
            wait_after = program.get('goto_manual', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return

        # Astro Photo
        if take_photo:
            log.notice(f"Processing Astro Photo Session : {count_val} images")
            if exp_val:
                continue_action = perform_set_astro_exposure_by_name_v3(exp_val, dwarf_id=str(config_to_dwarf_id_str(dwarf_id)), session=session)
                if interrupted(): return
                verify_action(continue_action, "step_10", progress_callback=progress_callback)
                # Actual-value traces (user-requested Sep 2026: "affichage
                # des parametrage images dans les traces des etapes...
                # pour verification") - same step_key-doubles-as-label
                # trick used for the EQ Solving result trace above,
                # since this is per-run dynamic text, not a fixed,
                # reusable STEP_DESCRIPTIONS entry.
                if progress_callback:
                    progress_callback(f"Exposure: {exp_val}", "success")
            if gain_val:
                continue_action = perform_set_astro_gain_v3(int(gain_val), session=session)
                if interrupted(): return
                verify_action(continue_action, "step_10", progress_callback=progress_callback)
                if progress_callback:
                    progress_callback(f"Gain: {gain_val}", "success")
            if IR_val:
                # All three models confirmed on the modern path - see
                # this file's other call site (a few hundred lines up)
                # for the full reasoning (three independent network
                # captures, D2/D3/Mini).
                continue_action = perform_set_astro_ir_filter_v3(int(IR_val), session=session)
                if interrupted(): return
                verify_action(continue_action, "step_10", progress_callback=progress_callback)
                if progress_callback:
                    progress_callback(f"IR Filter: {_ir_filter_display_name(dwarf_id, IR_val)}", "success")
            # Same D2 stack_binning gate as the manual/live flow above
            # (see that call site's own comment) - a scheduled program
            # with setup_camera.binning set would otherwise hit the
            # same 150s silent timeout on this model.
            # D3-ONLY (corrected, user-confirmed Sep 2026): see the
            # manual/live flow's own comment above - the official app
            # itself only exposes binning control for D3, not D2/Mini.
            if binning_val and config_to_dwarf_id_str(dwarf_id) == "3":
                continue_action = perform_set_astro_stack_binning_v3(int(binning_val), session=session)
                if interrupted(): return
                verify_action(continue_action, "step_10", progress_callback=progress_callback)
                if progress_callback:
                    progress_callback(
                        f"Binning: {'2K' if str(binning_val) == '1' else '4K'}", "success"
                    )
            # Regular (non-mosaic) stack count is skipped entirely when
            # Mosaic is active (user-reported Sep 2026: real hardware
            # test with count=40/mosaic_count=20 - the correct, already-
            # saved values per the program JSON - produced
            # subviewShotsToTake=100 on the device, not the expected 20).
            # Sending BOTH the regular stackCount (40, meant for a
            # single-panel session) AND the mosaic-specific mosaicCount
            # (20) back-to-back doesn't make conceptual sense for a
            # session that's actually going to run in Mosaic mode - this
            # skips the regular one so only the mosaic-specific count
            # ever reaches the device for a Mosaic session, removing
            # that cross-talk as a possible cause. NOT independently
            # confirmed by network capture to be the exact mechanism
            # behind the observed 100 - re-test on real hardware to
            # verify subviewShotsToTake matches mosaic_count afterward.
            if count_val and not do_mosaic:
                continue_action = perform_set_astro_stack_count_v3(int(count_val), session=session)
                if interrupted(): return
                verify_action(continue_action, "step_10", progress_callback=progress_callback)
                if progress_callback:
                    progress_callback(
                        f"Total Count: {int(count_val)}", "success"
                    )
            if do_mosaic:
                continue_action = perform_set_astro_mosaic_count_v3(int(mosaic_count_val), session=session)
                if interrupted(): return
                verify_action(continue_action, "step_10", progress_callback=progress_callback)
                if progress_callback:
                    progress_callback(
                        f"Mosaic on", "success"
                    )

            time.sleep(5)
            if interrupted(): return
            print_camera_data(session=session)
            if interrupted(): return
            
            wait_after = program.get('setup_camera', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return
            
            time.sleep(2)
            if interrupted(): return
            if do_mosaic:
                log.notice(f"Starting Mosaic Session : framingX={framing_x/100:.2f}x framingY={framing_y/100:.2f}x")
                continue_action = perform_start_mosaic_v3(framing_x, framing_y, session=session)
            else:
                # User-found root cause (Sep 2026) of the whole IR
                # filter mystery from earlier tonight: this call has
                # its OWN ir_index parameter (ReqCaptureRawLiveStacking,
                # V3-only field, per perform_takeAstroPhoto()'s own
                # docstring) - it was left at the function's default
                # (1 = Astro Filter) every single time, silently
                # re-applying/overriding Astro Filter at the exact
                # moment capture actually starts, no matter what
                # perform_set_astro_ir_filter_v3()/perform_set_ir_
                # filter_v3() had set moments earlier. Not a device-
                # side "mode drop" or a wrong param_id after all -
                # this one line was the entire explanation.
                continue_action = perform_takeAstroPhoto(
                    ir_index=int(IR_val) if IR_val else 1, session=session
                )
            if interrupted(): return
            verify_action(continue_action, "step_11", progress_callback=progress_callback)

            # CMD_ASTRO_CONTINUE_SHOOTING follow-up (user-identified, Sep
            # 2026): CODE_ASTRO_DARK_TEMP_MISMATCH is a genuinely BLOCKING
            # state on the device side (the official app shows a
            # confirmation dialog for it) - websockets_utils.py's own
            # handling of that response code unblocks OUR waiting caller
            # locally (result_receive_messages() with a faked OK), but
            # that alone does NOT tell the DEVICE itself to actually
            # proceed. needsContinueShooting is set there specifically to
            # flag this - checked here, right after the step it applies
            # to, so the explicit CMD_ASTRO_CONTINUE_SHOOTING (11050) can
            # be sent, matching what the user taps in the official app's
            # own dialog for this exact scenario. Cleared immediately
            # after, so a LATER unrelated check of this flag doesn't
            # re-trigger a stale follow-up.
            status = get_client_status(session) if session is not None else {}
            if status.get("fullStatus", {}).get("needsContinueShooting"):
                log.notice("Dark frame temperature mismatch was ignored - sending Continue Shooting confirmation")
                continue_action = perform_continue_shooting(session=session)
                perform_clear_needs_continue_shooting(session=session)
                if interrupted(): return
                verify_action(continue_action, "step_11", progress_callback=progress_callback)
            
            time.sleep(2)
            if interrupted(): return
            try:
                continue_action = _wait_for_astro_end(
                    perform_stopAstroPhoto, end_time_val, interrupted, session, "Tele", progress_callback,
                )
                if interrupted(): return
                verify_action(continue_action, "step_12", progress_callback=progress_callback)
            #except Exception as e:
            #    continue_action = try_attemps(lambda: perform_waitRetryEndAstroPhoto(session=session), "Astro photo session completed", 5, interrupted=interrupted)
            #    if interrupted(): return
            #    verify_action(continue_action, "step_12", progress_callback=progress_callback)
            except Exception as e:
                if interrupted():
                    log.notice("Stop requested - sending stop capture command to device")
                    perform_stopAstroPhoto(session=session)
                    return
                continue_action = try_attemps(
                    lambda: _wait_for_astro_end(
                        perform_stopAstroPhoto, end_time_val, interrupted, session, "Tele", progress_callback,
                    ),
                    "Astro photo session completed", 5, interrupted=interrupted,
                )
                if interrupted():
                    log.notice("Stop requested during retry - sending stop capture command to device")
                    perform_stopAstroPhoto(session=session)
                    return
                verify_action(continue_action, "step_12", progress_callback=progress_callback)

        # Wide Photo
        if take_widephoto:
            if take_photo:
                # need Go Live again in this case
                continue_action = perform_GoLive(session=session)
                verify_action(continue_action, "step_1a", progress_callback=progress_callback)

                # V3: GO LIVE alone does not keep the device in Astro/DSO
                # mode - field-confirmed (Aug 2026): after a tele session,
                # the wide session's exposure read back as a Normal/photo-
                # mode-style name (e.g. "1/30") instead of the configured
                # astro seconds value, meaning the device had silently
                # dropped out of astro mode. Re-enter it explicitly before
                # starting the wide phase, same as at the top of the
                # session for tele.
                log.notice("Entering Astro/DSO shooting mode (again, for wide)")
                continue_action = perform_enter_astro_mode(session=session)
                verify_action(continue_action, "step_1e", progress_callback=progress_callback)

            log.notice(f"Processing Astro Wide Photo Session : {wide_count_val} images")
            if wide_exp_val:
                continue_action = perform_set_astro_exposure_by_name_v3(wide_exp_val, dwarf_id=str(config_to_dwarf_id_str(dwarf_id)), camera="wide", session=session)
                if interrupted(): return
                verify_action(continue_action, "step_13", progress_callback=progress_callback)
                if progress_callback:
                    progress_callback(f"Exposure: {wide_exp_val}", "success")
            if wide_gain_val:
                continue_action = perform_set_astro_gain_v3(int(wide_gain_val), camera="wide", session=session)
                if interrupted(): return
                verify_action(continue_action, "step_13", progress_callback=progress_callback)
                if progress_callback:
                    progress_callback(f"Gain: {wide_gain_val}", "success")
            if wide_count_val:
                continue_action = perform_set_astro_stack_count_v3(int(wide_count_val), camera="wide", session=session)
                if interrupted(): return
                verify_action(continue_action, "step_13", progress_callback=progress_callback)
                if progress_callback:
                    progress_callback(f"Total Count: {int(wide_count_val)}", "success")
            
            time.sleep(5)
            if interrupted(): return
            print_wide_camera_data(session=session)
            if interrupted(): return

            wait_after = int(program.get('setup_wide_camera', {}).get('wait_after', 0))
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return
            
            time.sleep(2)
            if interrupted(): return
            continue_action = perform_takeAstroWidePhoto(session=session)
            if interrupted(): return
            verify_action(continue_action, "step_14", progress_callback=progress_callback)

            # CMD_ASTRO_CONTINUE_SHOOTING follow-up - see the tele/mosaic
            # branch's own note above for why this is needed.
            status = get_client_status(session) if session is not None else {}
            if status.get("fullStatus", {}).get("needsContinueShooting"):
                log.notice("Dark frame temperature mismatch was ignored - sending Continue Shooting confirmation")
                continue_action = perform_continue_shooting(session=session)
                perform_clear_needs_continue_shooting(session=session)
                if interrupted(): return
                verify_action(continue_action, "step_14", progress_callback=progress_callback)
            
            time.sleep(2)
            if interrupted(): return
            try:
                continue_action = _wait_for_astro_end(
                    perform_stopAstroWidePhoto, wide_end_time_val, interrupted, session, "Wide", progress_callback,
                )
                if interrupted(): return
                verify_action(continue_action, "step_15", progress_callback=progress_callback)
            #except Exception as e:
            #    continue_action = try_attemps(lambda: perform_waitRetryEndAstroWidePhoto(session=session), "Wide Astro photo session completed", 5, interrupted=interrupted)
            #    if interrupted(): return
            #    verify_action(continue_action, "step_15", progress_callback=progress_callback)
            except Exception as e:
                if interrupted():
                    log.notice("Stop requested - sending stop capture command to device")
                    perform_stopAstroWidePhoto(session=session)
                    return
                continue_action = try_attemps(
                    lambda: _wait_for_astro_end(
                        perform_stopAstroWidePhoto, wide_end_time_val, interrupted, session, "Tele", progress_callback,
                    ),
                    "Astro photo session completed", 5, interrupted=interrupted,
                )
                if interrupted():
                    log.notice("Stop requested during retry - sending stop capture command to device")
                    perform_stopAstroWidePhoto(session=session)
                    return
                verify_action(continue_action, "step_12", progress_callback=progress_callback)

    except Exception as e:
        line_number = e.__traceback__.tb_lineno if e.__traceback__ else "unknown"
        log.error(f"Error during session : {e} Line: {line_number}")
        raise

    finally:
        log.success("######################")
        log.success(f"  End of Session")
        log.success("######################")

def verify_action(result, action_step, progress_callback=None):
    """Fixed verify_action function with consistent behavior.

    progress_callback(action_step, status), status in {"success", "failed"} -
    optional, additive (see start_dwarf_session()'s own progress_callback
    param). Called from whatever thread runs start_dwarf_session (usually
    a worker thread, not the UI's event loop) - a caller wiring this up to
    a live UI should have the callback only write to a plain, thread-safe
    shared state and let the UI's own timer poll it, rather than touching
    UI elements directly from here."""
    log.notice(f"verify_action : {result}")
    if result is False:
        if progress_callback:
            progress_callback(action_step, "failed")
        raise RuntimeError(f"Action failed at step: {STEP_DESCRIPTIONS.get(action_step, action_step)}")
    elif result or result == 0:
        log.success(f"Action successful for: {STEP_DESCRIPTIONS.get(action_step, action_step)}")
        log.notice("----------------------")
        if progress_callback:
            progress_callback(action_step, "success")
        return True
    else:
        if progress_callback:
            progress_callback(action_step, "failed")
        raise RuntimeError(f"Action failed at step: {STEP_DESCRIPTIONS.get(action_step, action_step)}")

def print_camera_data(session=None):
    camera_exposure = False
    camera_gain = False
    camera_binning = False
    camera_IR = False
    camera_format = False
    camera_count = False

    # V3: CMD_CAMERA_TELE_GET_ALL_PARAMS (perform_get_all_camera_setting) does
    # not respond on V3 hardware - use the live HTTP API instead, confirmed
    # reliable for exposure/gain/filter (see MIGRATION_V3.md).
    # modeId=2 (HTTP API numbering) = DSO/astro - not to be confused with
    # mode=8 used by SWITCH_SHOOTING_MODE over the WebSocket connection.
    http_result = perform_read_camera_params_http_v3(mode_id=2, session=session)
    #result_feature = perform_get_all_feature_camera_setting()

    # get dwarf type id
    if session is not None:
        dwarf_id = session.config.dwarf_model_id
    else:
        data_config = config_py.get_config_data()
        dwarf_id = data_config['dwarf_id']
    log.notice("----------------------")
    log.notice(f"Connected to Dwarf {config_to_dwarf_id_int(dwarf_id)}")

    # ALL PARAMS (exposure/gain/IR filter) - via live HTTP API (V3)
    if isinstance(http_result, dict) and http_result.get("cameras", {}).get(0):
        tele_cam = http_result["cameras"][0]

        # get exposure
        exposure_info = tele_cam.get("exposure")
        if exposure_info:
            auto_mode = exposure_info.get("mode")
            log.notice(f"The exposition mode is: {'Manual' if auto_mode else 'Auto'}")
            camera_exposure = exposure_info.get("name")
            if camera_exposure is None:
                # fallback: resolve name from the raw index ourselves
                camera_exposure = str(get_exposure_name_by_index(exposure_info.get("value"), str(config_to_dwarf_id_str(dwarf_id))))
            log.notice(f"the exposure is: {camera_exposure}")
        else:
            log.notice("the exposure has not been found")

        # get Gain (V3: gain is now a direct value, no index/table lookup needed)
        gain_info = tele_cam.get("gain")
        if gain_info:
            camera_gain = str(gain_info.get("value"))
            log.notice(f"the gain is: {camera_gain}")
        else:
            log.notice("the gain has not been found")

        # get IR
        if "filterType" in tele_cam:
            camera_IR = str(tele_cam["filterType"])

            if camera_IR == "0" and config_to_dwarf_id_str(dwarf_id) == "2":
                log.notice("the IR value is: IRCut")
            if camera_IR == "1" and config_to_dwarf_id_str(dwarf_id) == "2":
                log.notice("the IR value is: IRPass")
            if camera_IR == "0" and config_to_dwarf_id_str(dwarf_id) == "3":
                log.notice("the IR value is: VIS FILTER")
            if camera_IR == "1" and config_to_dwarf_id_str(dwarf_id) == "3":
                log.notice("the IR value is: ASTRO FILTER")
            if camera_IR == "2" and config_to_dwarf_id_str(dwarf_id) == "3":
                log.notice("the IR value is: DUAL BAND")
            if camera_IR == "0" and config_to_dwarf_id_str(dwarf_id) == "5":
                log.notice("the IR value is: DARK FILTER")
            if camera_IR == "1" and config_to_dwarf_id_str(dwarf_id) == "5":
                log.notice("the IR value is: ASTRO FILTER")
            if camera_IR == "2" and config_to_dwarf_id_str(dwarf_id) == "5":
                log.notice("the IR value is: DUAL BAND")
        else:
           log.notice("the IRfilter has not been found")
    else:
       log.notice("the exposure has not been found")
       log.notice("the gain has not been found")
       log.notice("the IRfilter has not been found")

    if isinstance(http_result, dict):
        stack_settings = http_result.get("tech_settings", {}).get(15)
        if stack_settings:
            if "stackFormat" in stack_settings:
                format_map = {2: "FITS", 3: "TIFF"}
                value = stack_settings["stackFormat"]
                log.notice(f"the image format value is: {format_map.get(value, value)}")
            else:
               log.notice("the image format value has not been found")

            if "stackBinning" in stack_settings:
                # NOTE (Aug 2026): this HTTP read can lag behind the real
                # applied value right after a write (field-confirmed: the
                # actual capture correctly used the configured binning -
                # verified via the captured file's own JSON metadata and
                # resolution - even when this diagnostic print still
                # showed the old value). Purely a display quirk, not a
                # functional issue - see MIGRATION_V3.md.
                binning_map = {0: "4k", 1:"2k"}
                value = stack_settings["stackBinning"]
                log.notice(f"the Binning value is {binning_map.get(value, value)}")
            else:
                log.notice("the Binning value has not been found")
        else:
            log.notice("the image format value has not been found")
            log.notice("the Binning value has not been found")

        count_tele_settings = http_result.get("tech_settings", {}).get(0)
        if count_tele_settings:
            if "stackCount" in count_tele_settings:
                value = count_tele_settings["stackCount"]
                log.notice(f"the number of images for the session is: {value}")
        else:
           log.notice("the number of images for the session has not been found")

    else:
       log.notice("the Binning value has not been found")
       log.notice("the image format value has not been found")
       log.notice("the number of images for the session has not been found")

    log.notice("----------------------")

def print_wide_camera_data(session=None):
    camera_wide_exposure = False
    camera_wide_gain = False
    camera_count = False

    # V3: CMD_CAMERA_WIDE_GET_ALL_PARAMS (perform_get_all_camera_wide_setting)
    # does not respond on V3 hardware - use the live HTTP API instead.
    http_result = perform_read_camera_params_http_v3(mode_id=2, session=session)

    # get dwarf type id
    if session is not None:
        dwarf_id = session.config.dwarf_model_id
    else:
        data_config = config_py.get_config_data()
        dwarf_id = data_config['dwarf_id']
    log.notice("----------------------")
    log.notice(f"Connected to Dwarf {config_to_dwarf_id_int(dwarf_id)}")

    # ALL PARAMS (exposure/gain) - via live HTTP API (V3), cameraId=1 (wide)
    if isinstance(http_result, dict) and http_result.get("cameras", {}).get(1):
        wide_cam = http_result["cameras"][1]

        exposure_info = wide_cam.get("exposure")
        if exposure_info:
            camera_wide_exposure = exposure_info.get("name")
            if camera_wide_exposure is None:
                camera_wide_exposure = str(get_wide_exposure_name_by_index(exposure_info.get("value"), str(config_to_dwarf_id_str(dwarf_id))))
            log.notice(f"the exposure is: {camera_wide_exposure}")
        else:
           log.notice("the exposure has not been found")

        # V3: gain is now a direct value, no index/table lookup needed
        gain_info = wide_cam.get("gain")
        if gain_info:
            camera_wide_gain = str(gain_info.get("value"))
            log.notice(f"the gain is: {camera_wide_gain}")
        else:
           log.notice("the gain has not been found")

    else:
       log.notice("the exposure has not been found")
       log.notice("the gain has not been found")

    if isinstance(http_result, dict):
        count_wide_settings = http_result.get("tech_settings", {}).get(1)
        if count_wide_settings:
            if "stackCount" in count_wide_settings:
                value = count_wide_settings["stackCount"]
                log.notice(f"the number of images for the session is: {value}")
        else:
           log.notice("the number of images for the session has not been found")
    else:
       log.notice("the number of images for the session has not been found")

    log.notice("----------------------")