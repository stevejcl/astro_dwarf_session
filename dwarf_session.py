import json
import time

from dwarf_python_api.lib.dwarf_utils import perform_GoLive
from dwarf_python_api.lib.dwarf_utils import perform_calibration
from dwarf_python_api.lib.dwarf_utils import perform_goto
from dwarf_python_api.lib.dwarf_utils import perform_stop_goto
from dwarf_python_api.lib.dwarf_utils import perform_goto_stellar
from dwarf_python_api.lib.dwarf_utils import parse_ra_to_float
from dwarf_python_api.lib.dwarf_utils import parse_dec_to_float
from dwarf_python_api.lib.dwarf_utils import perform_takeAstroPhoto
from dwarf_python_api.lib.dwarf_utils import perform_waitEndAstroPhoto
from dwarf_python_api.lib.dwarf_utils import perform_update_camera_setting
from dwarf_python_api.lib.dwarf_utils import perform_takeAstroWidePhoto
from dwarf_python_api.lib.dwarf_utils import perform_waitEndAstroWidePhoto
from dwarf_python_api.lib.dwarf_utils import perform_start_autofocus
from dwarf_python_api.lib.dwarf_utils import start_polar_align
from dwarf_python_api.lib.dwarf_utils import perform_time

from dwarf_python_api.lib.dwarf_utils import perform_get_all_camera_setting
from dwarf_python_api.lib.dwarf_utils import perform_get_all_feature_camera_setting
from dwarf_python_api.lib.dwarf_utils import perform_get_all_camera_wide_setting
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
}

def try_attemps (function, function_succeed_message, max_attempts = 3):
    # Try to perform the action up to 3 times by default
    attempts = 0
    continue_action = False

    # Try to perform the action up to 3 times
    while attempts < max_attempts:
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
                if config_to_dwarf_id_str(dwarf_id) == "3":
                    log.notice(f"     IR => {'VIS_FILTER' if IR_val == '0' else 'ASTRO_FILTER' if IR_val == '1' else 'DUAL_BAND'}")
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

        # Go Live
        continue_action = perform_GoLive()
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
            continue_action = perform_update_camera_setting("exposure", "1", str(config_to_dwarf_id_str(dwarf_id)))
            if interrupted(): return
            verify_action(continue_action, "step_2")
            
            log.notice("    Set Gain to 80")
            continue_action = perform_update_camera_setting("gain", "80", str(config_to_dwarf_id_str(dwarf_id)))
            if interrupted(): return
            verify_action(continue_action, "step_3")
            if config_to_dwarf_id_str(dwarf_id) == "3":
                log.notice("    Set IR to Astro Filter")
            else:
                log.notice("    Set IR to IR_PASS")
            continue_action = perform_update_camera_setting("IR", "1")
            if interrupted(): return
            verify_action(continue_action, "step_4")
            
            log.notice("    Set Binning to 4k")
            continue_action = perform_update_camera_setting("binning", "0")
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
                continue_action = perform_update_camera_setting("exposure", exp_val, str(config_to_dwarf_id_str(dwarf_id)))
                if interrupted(): return
                verify_action(continue_action, "step_10")
            if gain_val:
                continue_action = perform_update_camera_setting("gain", gain_val, str(config_to_dwarf_id_str(dwarf_id)))
                if interrupted(): return
                verify_action(continue_action, "step_10")
            if IR_val:
                continue_action = perform_update_camera_setting("IR", IR_val)
                if interrupted(): return
                verify_action(continue_action, "step_10")
            if binning_val:
                continue_action = perform_update_camera_setting("binning", binning_val)
                if interrupted(): return
                verify_action(continue_action, "step_10")
            if count_val:
                continue_action = perform_update_camera_setting("count", count_val)
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
            continue_action = try_attemps(perform_waitEndAstroPhoto, "Astro photo session completed", 5)
            if interrupted(): return
            verify_action(continue_action, "step_12")

        # Wide Photo
        if take_widephoto:
            log.notice(f"Processing Astro Wide Photo Session : {wide_count_val} images")
            if wide_exp_val:
                continue_action = perform_update_camera_setting("wide_exposure", wide_exp_val, str(config_to_dwarf_id_str(dwarf_id)))
                if interrupted(): return
                verify_action(continue_action, "step_13")
            if wide_gain_val:
                continue_action = perform_update_camera_setting("wide_gain", wide_gain_val, str(config_to_dwarf_id_str(dwarf_id)))
                if interrupted(): return
                verify_action(continue_action, "step_13")
            if wide_count_val:
                continue_action = perform_update_camera_setting("count", wide_count_val)
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
            continue_action = try_attemps(perform_waitEndAstroWidePhoto, "Wide photo session completed", 5)
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

    result = perform_get_all_camera_setting()
    result_feature = perform_get_all_feature_camera_setting()

    # get dwarf type id
    data_config = config_py.get_config_data()
    dwarf_id = data_config['dwarf_id']
    log.notice("----------------------")
    log.notice(f"Connected to Dwarf {config_to_dwarf_id_int(dwarf_id)}")

    # ALL PARAMS
    if isinstance(result, dict) and "all_params" in result:
        # get Camera
        target_id = 0

        # Find the entry with the matching id
        matching_entry = next((entry for entry in result["all_params"] if entry["id"] == target_id), None)

        if matching_entry:
            # Extract specific fields for the matching entry
           index_value = matching_entry["index"]

           camera_exposure = str(get_exposure_name_by_index(index_value, str(config_to_dwarf_id_str(dwarf_id))))
           log.notice(f"the exposure is: {camera_exposure}")
        else:
           log.notice("the exposure has not been found")

        # get Gain
        target_id = 1

        # Find the entry with the matching id
        matching_entry = next((entry for entry in result["all_params"] if entry["id"] == target_id), None)

        if matching_entry:
            # Extract specific fields for the matching entry
           index_value = matching_entry["index"]


           camera_gain = str(get_gain_name_by_index(index_value, str(config_to_dwarf_id_str(dwarf_id))))
           log.notice(f"the gain is: {camera_gain}")
        else:
           log.notice("the gain has not been found")

        # get IR
        target_id = 8

        # Find the entry with the matching id
        matching_entry = next((entry for entry in result["all_params"] if entry["id"] == target_id), None)

        if matching_entry:
            # Extract specific fields for the matching entry
            camera_IR = str(matching_entry["index"])

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
        else:
           log.notice("the IRfilter has not been found")
    else:
       log.notice("the exposure has not been found")
       log.notice("the gain has not been found")
       log.notice("the IRfilter has not been found")

    # ALL FEATURE PARAMS
    if isinstance(result_feature, dict) and "all_feature_params" in result_feature:
        # get binning
        target_id = 0

        # Find the entry with the matching id
        matching_entry = next((entry for entry in result_feature["all_feature_params"] if entry["id"] == target_id), None)

        if matching_entry:
            # Extract specific fields for the matching entry
            camera_binning = str(matching_entry["index"])
            if (camera_binning == "0"):
                log.notice("the Binning value is 4k")
            else:
                log.notice("the Binning value is 2k")
        else:
           log.notice("the Binning value has not been found")

        # get camera_format
        target_id = 2

        # Find the entry with the matching id
        matching_entry = next((entry for entry in result_feature["all_feature_params"] if entry["id"] == target_id), None)

        if matching_entry:
            # Extract specific fields for the matching entry
            camera_format = str(matching_entry["index"])
            if (camera_format == "0"):
                log.notice("the image format value is: FITS")
            else:
                log.notice("the image format value is: TIFF")
        else:
           log.notice("the image format value has not been found")

        # get camera_count
        target_id = 1

        # Find the entry with the matching id
        matching_entry = next((entry for entry in result_feature["all_feature_params"] if entry["id"] == target_id), None)

        if matching_entry:
            # Extract specific fields for the matching entry
            camera_count = str(round(matching_entry["continue_value"]))

            log.notice(f"the number of images for the session is: {camera_count}")
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

    result = perform_get_all_camera_wide_setting()
    result_feature = perform_get_all_feature_camera_setting()

    # get dwarf type id
    data_config = config_py.get_config_data()
    dwarf_id = data_config['dwarf_id']
    log.notice("----------------------")
    log.notice(f"Connected to Dwarf {config_to_dwarf_id_int(dwarf_id)}")

    # ALL PARAMS
    if isinstance(result, dict) and "all_params" in result:
        # get Camera
        target_id = 0

        # Find the entry with the matching id
        matching_entry = next((entry for entry in result["all_params"] if entry["id"] == target_id), None)

        if matching_entry:
            # Extract specific fields for the matching entry
           index_value = matching_entry["index"]

           camera_wide_exposure = str(get_wide_exposure_name_by_index(index_value, str(config_to_dwarf_id_str(dwarf_id))))
           log.notice(f"the exposure is: {camera_wide_exposure}")
        else:
           log.notice("the exposure has not been found")

        # get Gain
        target_id = 1

        # Find the entry with the matching id
        matching_entry = next((entry for entry in result["all_params"] if entry["id"] == target_id), None)

        if matching_entry:
            # Extract specific fields for the matching entry
           index_value = matching_entry["index"]


           camera_wide_gain = str(get_wide_gain_name_by_index(index_value, str(config_to_dwarf_id_str(dwarf_id))))
           log.notice(f"the gain is: {camera_wide_gain}")
        else:
           log.notice("the gain has not been found")

    else:
       log.notice("the exposure has not been found")
       log.notice("the gain has not been found")

    # ALL FEATURE PARAMS
    if isinstance(result_feature, dict) and "all_feature_params" in result_feature:
        # get camera_count
        target_id = 1

        # Find the entry with the matching id
        matching_entry = next((entry for entry in result_feature["all_feature_params"] if entry["id"] == target_id), None)

        if matching_entry:
            # Extract specific fields for the matching entry
            camera_count = str(round(matching_entry["continue_value"]))

            log.notice(f"the number of images for the session is: {camera_count}")
        else:
           log.notice("the number of images for the session has not been found")
    else:
       log.notice("the number of images for the session has not been found")

    log.notice("----------------------")
