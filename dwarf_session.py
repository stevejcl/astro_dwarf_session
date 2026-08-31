import json
import time

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
from dwarf_python_api.lib.dwarf_utils import perform_waitEndAstroPhoto, perform_waitRetryEndAstroPhoto
from dwarf_python_api.lib.dwarf_utils import perform_set_astro_exposure_by_name_v3
from dwarf_python_api.lib.dwarf_utils import perform_set_astro_gain_v3
from dwarf_python_api.lib.dwarf_utils import perform_set_ir_filter_v3
from dwarf_python_api.lib.dwarf_utils import perform_set_astro_stack_count_v3
from dwarf_python_api.lib.dwarf_utils import perform_set_astro_stack_binning_v3
from dwarf_python_api.lib.dwarf_utils import perform_takeAstroWidePhoto
from dwarf_python_api.lib.dwarf_utils import perform_waitEndAstroWidePhoto, perform_waitRetryEndAstroWidePhoto
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

def select_solar_target (target):
   
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
        result = perform_goto_stellar(target_id, target_name)
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
    "step_2": "Set Exposure to 1s for Calibration",
    "step_3": "Set Gain to 80 for Calibration",
    "step_4": "Set IR PASS for Calibration",
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


def start_dwarf_session(program, stop_event=None):
    try:
        def interrupted():
            return stop_event is not None and stop_event.is_set()
        
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

            if exp_val or gain_val or binning_val or IR_val or count_val:
                log.notice(f" To do => Astro Photo with these parameters")
                log.notice(f"     exposure  => {exp_val}s")
                log.notice(f"     gain  => {gain_val}")
                log.notice(f"     binning => {'4k' if binning_val == '0' else '2k'}")
                log.notice(f"real binning => {binning_val}")
                if config_to_dwarf_id_str(dwarf_id) == "3":
                    log.notice(f"     IR => {'VIS_FILTER' if IR_val == '0' else 'ASTRO_FILTER' if IR_val == '1' else 'DUAL_BAND'}")
                elif config_to_dwarf_id_str(dwarf_id) == "5":
                    log.notice(f"     IR => {'DARK' if IR_val == '0' else 'ASTRO_FILTER' if IR_val == '1' else 'DUAL_BAND'}")
                else:
                    log.notice(f"     IR  => {'IR_CUT' if IR_val== '0' else 'IR_PASS'}")
                log.notice(f"     number of images  => {count_val}")
            else:
                log.warning(f" Error in Settings => PHOTO : none settings found, task ignored!")
                take_photo = False

        # Validate wide photo parameters
        if take_widephoto:
            wide_exp_val = str(program['setup_wide_camera'].get('exposure', "0"))
            wide_gain_val = str(program['setup_wide_camera'].get('gain', "0"))
            wide_count_val = str(program['setup_wide_camera'].get('count', "0"))  # Fix: use separate variable

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
        continue_action = try_attemps(perform_time, "Init succeeded.")
        verify_action(continue_action, "step_0")

        # V3: SET_LOCATION and CMD_GLOBAL_TASK_GET_DEVICE_STATE_INFO are
        # now both sent automatically - location at the connection layer
        # (astro_dwarf_scheduler.start_connection()/start_STA_connection(),
        # alongside SET_TIME/SET_TIME_ZONE), device-state-info at the WS
        # protocol layer (websockets_utils.send_message_init(), once per
        # connection) - matching the official app's own behavior. No
        # explicit calls needed here anymore.

        # Go Live
        continue_action = perform_GoLive()
        verify_action(continue_action, "step_1a")

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
            continue_action = perform_enter_shooting_mode(solar_mode, SHOOTING_TECH_DEEP_SKY)
        else:
            log.notice("Entering Astro/DSO shooting mode")
            continue_action = perform_enter_astro_mode()
        verify_action(continue_action, "step_1a")

        # Auto Focus
        if auto_focus:
            wait_before = program.get('auto_focus', {}).get('wait_before', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_before} seconds")
            time.sleep(wait_before)
            if interrupted(): return
            log.notice("Processing automatic autofocus")
            continue_action = perform_start_autofocus(False)
            if interrupted(): return
            verify_action(continue_action, "step_1c")
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
            continue_action = perform_start_autofocus(True)
            if interrupted(): return
            verify_action(continue_action, "step_1d")
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
                continue_action = perform_start_autofocus(True)
                if interrupted(): return
                verify_action(continue_action, "step_1d")
                time.sleep(5)

            continue_action = perform_stop_goto()
            if interrupted(): return
            verify_action(continue_action, "step_6")
            if interrupted(): return
            time.sleep(5)
            if interrupted(): return
            wait_before = program.get('eq_solving', {}).get('wait_before', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_before} seconds")
            time.sleep(wait_before)
            if interrupted(): return
            log.notice("Processing EQ Solving")
            continue_action = start_polar_align()
            if interrupted(): return
            verify_action(continue_action, "step_1b")
            wait_after = program.get('eq_solving', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return

        # Calibration
        if calibration:
            log.notice("Processing Calibration")
            log.notice("    Set Exposure to 1s")
            continue_action = perform_set_astro_exposure_by_name_v3("1", dwarf_id=str(config_to_dwarf_id_str(dwarf_id)))
            if interrupted(): return
            verify_action(continue_action, "step_2")
            
            log.notice("    Set Gain to 80")
            continue_action = perform_set_astro_gain_v3(80)
            if interrupted(): return
            verify_action(continue_action, "step_3")
            if config_to_dwarf_id_str(dwarf_id) >= "3":
                log.notice("    Set IR to Astro Filter")
            else:
                log.notice("    Set IR to IR_PASS")
            continue_action = perform_set_ir_filter_v3("1")
            if interrupted(): return
            verify_action(continue_action, "step_4")
            
            log.notice("    Set Binning to 4k")
            continue_action = perform_set_astro_stack_binning_v3(0)
            if interrupted(): return
            verify_action(continue_action, "step_5")
            
            time.sleep(5)
            if interrupted(): return
            print_camera_data()
            if interrupted(): return
            
            continue_action = perform_stop_goto()
            if interrupted(): return
            verify_action(continue_action, "step_6")
            time.sleep(5)
            if interrupted(): return
            
            log.notice("Starting Calibration")
            wait_before = program.get('calibration', {}).get('wait_before', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_before} seconds")
            time.sleep(wait_before)
            if interrupted(): return
            continue_action = perform_calibration()
            if interrupted(): return
            verify_action(continue_action, "step_7")
            wait_after = program.get('calibration', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return

        # Goto Solar System
        if goto_solar:
            target_name = program.get('goto_solar', {}).get('target')
            log.notice(f"Processing Goto Solar System : {target_name}")
            continue_action = select_solar_target(target_name)
            if interrupted(): return
            verify_action(continue_action, "step_8")
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

            continue_action = perform_goto(decimal_RA, decimal_Dec, target_name)
            if interrupted(): return
            verify_action(continue_action, "step_9")
            wait_after = program.get('goto_manual', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return

        # Astro Photo
        if take_photo:
            log.notice(f"Processing Astro Photo Session : {count_val} images")
            if exp_val:
                continue_action = perform_set_astro_exposure_by_name_v3(exp_val, dwarf_id=str(config_to_dwarf_id_str(dwarf_id)))
                if interrupted(): return
                verify_action(continue_action, "step_10")
            if gain_val:
                continue_action = perform_set_astro_gain_v3(int(gain_val))
                if interrupted(): return
                verify_action(continue_action, "step_10")
            if IR_val:
                continue_action = perform_set_ir_filter_v3(IR_val)
                if interrupted(): return
                verify_action(continue_action, "step_10")
            if binning_val:
                continue_action = perform_set_astro_stack_binning_v3(int(binning_val))
                if interrupted(): return
                verify_action(continue_action, "step_10")
            if count_val:
                continue_action = perform_set_astro_stack_count_v3(int(count_val))
                if interrupted(): return
                verify_action(continue_action, "step_10")

            time.sleep(5)
            if interrupted(): return
            print_camera_data()
            if interrupted(): return
            
            wait_after = program.get('setup_camera', {}).get('wait_after', 0)
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return
            
            time.sleep(2)
            if interrupted(): return
            continue_action = perform_takeAstroPhoto()
            if interrupted(): return
            verify_action(continue_action, "step_11")
            
            time.sleep(2)
            if interrupted(): return
            try:
                continue_action = perform_waitEndAstroPhoto()
                if interrupted(): return
                verify_action(continue_action, "step_12")
            except Exception as e:
                continue_action = try_attemps(perform_waitRetryEndAstroPhoto, "Astro photo session completed", 5, interrupted=interrupted)
                if interrupted(): return
                verify_action(continue_action, "step_12")

        # Wide Photo
        if take_widephoto:
            if take_photo:
                # need Go Live again in this case
                continue_action = perform_GoLive()
                verify_action(continue_action, "step_1a")

                # V3: GO LIVE alone does not keep the device in Astro/DSO
                # mode - field-confirmed (Aug 2026): after a tele session,
                # the wide session's exposure read back as a Normal/photo-
                # mode-style name (e.g. "1/30") instead of the configured
                # astro seconds value, meaning the device had silently
                # dropped out of astro mode. Re-enter it explicitly before
                # starting the wide phase, same as at the top of the
                # session for tele.
                log.notice("Entering Astro/DSO shooting mode (again, for wide)")
                continue_action = perform_enter_astro_mode()
                verify_action(continue_action, "step_1a")

            log.notice(f"Processing Astro Wide Photo Session : {wide_count_val} images")
            if wide_exp_val:
                continue_action = perform_set_astro_exposure_by_name_v3(wide_exp_val, dwarf_id=str(config_to_dwarf_id_str(dwarf_id)), camera="wide")
                if interrupted(): return
                verify_action(continue_action, "step_13")
            if wide_gain_val:
                continue_action = perform_set_astro_gain_v3(int(wide_gain_val), camera="wide")
                if interrupted(): return
                verify_action(continue_action, "step_13")
            if wide_count_val:
                continue_action = perform_set_astro_stack_count_v3(int(wide_count_val), camera="wide")
                if interrupted(): return
                verify_action(continue_action, "step_13")
            
            time.sleep(5)
            if interrupted(): return
            print_wide_camera_data()
            if interrupted(): return

            wait_after = int(program.get('setup_wide_camera', {}).get('wait_after', 0))
            if interrupted(): return
            log.warning(f"Waiting for {wait_after} seconds")
            time.sleep(wait_after)
            if interrupted(): return
            
            time.sleep(2)
            if interrupted(): return
            continue_action = perform_takeAstroWidePhoto()
            if interrupted(): return
            verify_action(continue_action, "step_14")
            
            time.sleep(2)
            if interrupted(): return
            try:
                continue_action = perform_waitEndAstroWidePhoto()
                if interrupted(): return
                verify_action(continue_action, "step_15")
            except Exception as e:
                continue_action = try_attemps(perform_waitRetryEndAstroWidePhoto, "Wide Astro photo session completed", 5, interrupted=interrupted)
                if interrupted(): return
                verify_action(continue_action, "step_15")

    except Exception as e:
        line_number = e.__traceback__.tb_lineno if e.__traceback__ else "unknown"
        log.error(f"Error during session : {e} Line: {line_number}")
        raise

    finally:
        log.success("######################")
        log.success(f"  End of Session")
        log.success("######################")

def verify_action(result, action_step):
    """Fixed verify_action function with consistent behavior"""
    log.notice(f"verify_action : {result}")
    if result is False:
        raise RuntimeError(f"Action failed at step: {STEP_DESCRIPTIONS.get(action_step, action_step)}")
    elif result or result == 0:
        log.success(f"Action successful for: {STEP_DESCRIPTIONS.get(action_step, action_step)}")
        log.notice("----------------------")
        return True
    else:
        raise RuntimeError(f"Action failed at step: {STEP_DESCRIPTIONS.get(action_step, action_step)}")

def print_camera_data():
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
    http_result = perform_read_camera_params_http_v3(mode_id=2)
    #result_feature = perform_get_all_feature_camera_setting()

    # get dwarf type id
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

def print_wide_camera_data():
    camera_wide_exposure = False
    camera_wide_gain = False
    camera_count = False

    # V3: CMD_CAMERA_WIDE_GET_ALL_PARAMS (perform_get_all_camera_wide_setting)
    # does not respond on V3 hardware - use the live HTTP API instead.
    http_result = perform_read_camera_params_http_v3(mode_id=2)

    # get dwarf type id
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
