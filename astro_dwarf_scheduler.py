import os
import sys
import json
import shutil
import time
import subprocess
import re

from datetime import datetime, timedelta

from dwarf_session import start_dwarf_session

from dwarf_python_api.lib.dwarf_utils import perform_time
from dwarf_python_api.lib.dwarf_utils import perform_timezone
from dwarf_python_api.lib.dwarf_utils import perform_disconnect

from dwarf_python_api.lib.dwarf_utils import save_bluetooth_config_from_ini_file
from dwarf_python_api.get_live_data_dwarf import fn_wait_for_user_input

from dwarf_ble_connect.connect_bluetooth import connect_bluetooth
from dwarf_ble_connect.lib.connect_direct_bluetooth import connect_ble_dwarf_win
from dwarf_python_api.lib.dwarf_utils import read_bluetooth_ble_psd
from dwarf_python_api.lib.dwarf_utils import read_bluetooth_ble_STA_ssid
from dwarf_python_api.lib.dwarf_utils import read_bluetooth_ble_STA_pwd

# import data for config.py
import dwarf_python_api.get_config_data

import dwarf_python_api.lib.my_logger as log

# Directories
CONFIG_DEFAULT = "Default"
BASE_DIR = os.path.abspath(".")
DEVICES_DIR = os.path.join(BASE_DIR, "Devices_Sessions")
SESSIONS_DIR =  os.path.join(BASE_DIR, 'Astro_Sessions')

LIST_ASTRO_DIR_DEFAULT = {
    "SESSIONS_DIR": SESSIONS_DIR,
    "RESULTS_DIR": os.path.join('.', 'Results'),
    "TODO_DIR": os.path.join(".", "ToDo"),
    "CURRENT_DIR": os.path.join(".", "Current"),
    "DONE_DIR": os.path.join(".", "Done"),
    "ERROR_DIR": os.path.join(".", "Error")
}

LIST_ASTRO_DIR = {
    "SESSIONS_DIR": SESSIONS_DIR,
    "RESULTS_DIR": os.path.join(SESSIONS_DIR, 'Results'),
    "TODO_DIR": os.path.join(SESSIONS_DIR, 'ToDo'),
    "CURRENT_DIR": os.path.join(SESSIONS_DIR, 'Current'),
    "DONE_DIR": os.path.join(SESSIONS_DIR, 'Done'),
    "ERROR_DIR": os.path.join(SESSIONS_DIR, 'Error'),
}

import requests

def setup_new_config(config_name):
    global LIST_ASTRO_DIR

    if config_name == CONFIG_DEFAULT:
        dwarf_python_api.get_config_data.set_config_data(
            config_file='config.py',
            config_file_tmp='config.tmp',
            lock_file='config.lock',
            print_log=True
        )

        SESSIONS_DIR =  os.path.join(BASE_DIR, 'Astro_Sessions')
        LIST_ASTRO_DIR = {
            "SESSIONS_DIR": SESSIONS_DIR,
            "RESULTS_DIR": os.path.join(SESSIONS_DIR, 'Results'),
            "TODO_DIR": os.path.join(SESSIONS_DIR, 'ToDo'),
            "CURRENT_DIR": os.path.join(SESSIONS_DIR, 'Current'),
            "DONE_DIR": os.path.join(SESSIONS_DIR, 'Done'),
            "ERROR_DIR": os.path.join(SESSIONS_DIR, 'Error'),
        }

    else:
        new_config_file = f"config_{config_name}.py"
        new_config_file_tmp = f"config_{config_name}.tmp"
        new_lock_file = f"config_{config_name}.lock"

        # Update CONFIG variables using the set_config_data function
        dwarf_python_api.get_config_data.set_config_data(
            config_file=new_config_file,
            config_file_tmp=new_config_file_tmp,
            lock_file=new_lock_file,
            print_log=True
        )

        config_filemname = os.path.join(BASE_DIR, new_config_file)
        if not os.path.exists(config_filemname):

            try:
                # Copy the original config file if not exist
                shutil.copy('config.py', new_config_file)
                print(f"'{'config.py'}' successfully copied to '{new_config_file}'.")
            except FileNotFoundError:
                print(f"Error: '{'config.py'}' not found.")
            except Exception as e:
                print(f"An error occurred: {e}")

            # get Original log_file
            data_config = dwarf_python_api.get_config_data.get_config_data("config.py")
            if data_config['log_file'] == "False":
                log_file = None
            else: 
                log_file = "app.log" if data_config['log_file'] == "" else data_config['log_file']

            if log_file is not None:
                name, ext = log_file.rsplit(".", 1)
                new_log_file = f"{name}_{config_name}.{ext}"
                dwarf_python_api.get_config_data.update_config_data( "log_file", new_log_file, True)

        config_dir = os.path.join(DEVICES_DIR, config_name)
        SESSIONS_DIR = os.path.join(config_dir, 'Astro_Sessions')
        # Define the list of directories
        LIST_ASTRO_DIR = {
            "SESSIONS_DIR": SESSIONS_DIR,
            "RESULTS_DIR": os.path.join(SESSIONS_DIR, 'Results'),
            "TODO_DIR": os.path.join(SESSIONS_DIR, 'ToDo'),
            "CURRENT_DIR": os.path.join(SESSIONS_DIR, 'Current'),
            "DONE_DIR": os.path.join(SESSIONS_DIR, 'Done'),
            "ERROR_DIR": os.path.join(SESSIONS_DIR, 'Error'),
        }

    # update log
    log.update_log_file()

# Load the JSON file
def load_json(filepath):
    try:
        with open(filepath, 'r') as file:
            return json.load(file)
    except Exception as e:
        log.error(f"error loading file: {filepath} - {e}")
        return False

# Save the JSON file
def save_json(filepath, data):
    try:
        with open(filepath, 'w') as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        log.error(f"error saving file: {filepath} - {e}")
        return False

# Check if the execution time of the command has been reached
def is_time_to_execute(command):
    # Get current date and time
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")

    date_action = command.get('date',current_date)
    time_action = command.get('time',current_time)
    command_datetime = datetime.strptime(f"{date_action} {time_action}", "%Y-%m-%d %H:%M:%S")
    return datetime.now() >= command_datetime

# Update the process status in the JSON file
def update_process_status(program, status, result=None, message=None, nb_try=None, dwarf_id=None):
    command = program['command']['id_command']
    command['process'] = status
    if result is not None:
        command['result'] = result
    if message:
        command['message'] = message
    if nb_try is not None:
        command['nb_try'] = nb_try
    if dwarf_id is not None:
        command['dwarf'] = "D" + str(dwarf_id)
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status == "pending":
        command['starting_date'] = current_datetime
    if status == "done":
        command['processed_date'] = current_datetime
    return program  # Return the updated entire program object

def retry_procedure(program, max_retries=3, stop_event=None):
    attempt = 0
    while attempt < max_retries:
        if stop_event is not None and stop_event.is_set():
            raise Exception("Session interrupted by user.")
        try:
            # Execute the session
            start_dwarf_session(program['command'], stop_event=stop_event)
            return attempt + 1
        except Exception as e:
            attempt += 1
            log.notice("----------------------")
            log.error(f"Session Attempt {attempt} failed with error: {e}")
            if attempt == max_retries:
                log.error("Max retries reached. Raising the exception.")
                raise  # Re-raise the exception after max attempts
            else:
                log.notice("Retrying...")
                log.notice("----------------------")

last_logged = {}  # Dictionary to track when each file was last logged
last_hourly_log = {}  # Dictionary to track the last hourly log time for each filename


# Helper to get JSON files sorted by date and time
def get_json_files_sorted(directory):
    files_with_datetime = []
    for fname in os.listdir(directory):
        if fname.endswith('.json'):
            fpath = os.path.join(directory, fname)
            try:
                with open(fpath, 'r') as f:
                    data = json.load(f)
                id_command = data.get('command', {}).get('id_command', {})
                date_str = id_command.get('date', '')
                time_str = id_command.get('time', '')
                # Combine date and time for sorting
                datetime_str = f"{date_str} {time_str}"
            except Exception:
                datetime_str = ''
            files_with_datetime.append((datetime_str, fname))
    files_with_datetime.sort(key=lambda x: (x[0] == '', x[0]))
    return [fname for datetime_str, fname in files_with_datetime]

# Main function to check and execute the commands
def check_and_execute_commands(self, stop_event=None, skip_time_checks=False):
    """
    Check for JSON command files and execute them based on their scheduled time.
    
    Args:
        stop_event: Optional event to signal stopping
        skip_time_checks: If True, ignore scheduled time and execute immediately
    
    Returns:
        bool: True if any sessions were processed, False otherwise
    """
    sessions_processed = False
    
    try:
        # Get all JSON files from ToDo directory
        todo_files = []
        if os.path.exists(LIST_ASTRO_DIR["TODO_DIR"]):
            for filename in os.listdir(LIST_ASTRO_DIR["TODO_DIR"]):
                if filename.endswith('.json'):
                    todo_files.append(filename)
        
        if not todo_files:
            return sessions_processed
        
        # Sort files naturally
        def natural_sort_key(text):
            return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]
        
        todo_files.sort(key=lambda x: natural_sort_key(x))
        
        current_time = datetime.now()
        
        for filename in todo_files:
            if stop_event and stop_event.is_set():
                break
                
            filepath = os.path.join(LIST_ASTRO_DIR["TODO_DIR"], filename)
            
            try:
                with open(filepath, 'r') as f:
                    command_data = json.load(f)
                
                # Extract scheduled time
                id_command = command_data.get('command', {}).get('id_command', {})
                scheduled_date = id_command.get('date', '')
                scheduled_time = id_command.get('time', '')

                # Get target name or use filename
                target = command_data.get('goto_manual', {}).get('target', filename)

                # Check if we should skip time checks
                if skip_time_checks:
                    log.notice(f"Skipping time check for {target} - executing immediately")
                    time_ready = True
                else:
                    # Check if it's time to execute
                    time_ready = False
                    if scheduled_date and scheduled_time:
                        try:
                            scheduled_datetime = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M:%S")
                            time_ready = current_time >= scheduled_datetime
                            
                            if not time_ready:
                                time_diff = scheduled_datetime - current_time
                                log.debug(f"Session {target} scheduled for {scheduled_datetime}, waiting {time_diff}")
                        except ValueError as e:
                            log.warning(f"Invalid date/time format in {target}: {e}")
                            continue
                    else:
                        log.warning(f"Missing date/time in {target}")
                        continue
                
                if time_ready:
                    #if __name__ != "__main__":
                        #self.toggle_scheduler_buttons_state(state="disabled")
    
                    log.notice(f"Executing session: {target}")
                    
                    # Move to Current directory
                    current_path = os.path.join(LIST_ASTRO_DIR_DEFAULT["SESSIONS_DIR"], "Current", filename)
                    os.makedirs(os.path.dirname(current_path), exist_ok=True)
                    shutil.move(filepath, current_path)

                    # Execute the session
                    try:
                        # Update session status
                        id_command['process'] = 'running'
                        id_command['result'] = False
                        id_command['message'] = 'Session started'

                        update_process_status(command_data, 'pending')

                        # Save updated status
                        with open(current_path, 'w') as f:
                            json.dump(command_data, f, indent=4)
                        
                        # Start the session
                        id_command['time'] = datetime.now().strftime("%H:%M:%S")

                        start_dwarf_session(command_data['command'], stop_event=stop_event)

                        # Session completed successfully
                        id_command['process'] = 'done'
                        id_command['result'] = True
                        id_command['message'] = 'Session completed successfully'
                        
                        # Capture Dwarf device ID from config
                        data_config = dwarf_python_api.get_config_data.get_config_data()
                        dwarf_id = data_config.get("dwarf_id")
                        if dwarf_id:
                            id_command['dwarf'] = f"D{dwarf_id}"
                        else:
                            id_command['dwarf'] = "Unknown"

                        # Capture actual camera settings used during the session
                        try:
                            from dwarf_python_api.lib.dwarf_utils import perform_get_all_camera_setting
                            camera_settings = perform_get_all_camera_setting()
                            if camera_settings:
                                # Get the actual IR setting used
                                if isinstance(camera_settings, dict):
                                    ir_cut_value = camera_settings.get('ircut')
                                else:
                                    ir_cut_value = None
                                if ir_cut_value is not None:
                                    # Convert numeric IR value to readable format
                                    ir_mapping = {0: 'Vis', 1: 'Astro Filter', 2: 'DUAL Band'}
                                    id_command['ir_actual'] = ir_mapping.get(ir_cut_value, f'Unknown({ir_cut_value})')
                                
                                # Store other actual settings used
                                if isinstance(camera_settings, dict):
                                    id_command['exposure_actual'] = camera_settings.get('exposure')
                                    id_command['gain_actual'] = camera_settings.get('gain')
                                else:
                                    id_command['exposure_actual'] = camera_settings if isinstance(camera_settings, (int, float, str)) else None
                                    id_command['gain_actual'] = camera_settings if isinstance(camera_settings, (int, float, str)) else None
                        except Exception as e:
                            log.warning(f"Could not capture actual camera settings: {e}")
                            # Fallback to planned settings from session data
                            setup_camera = command_data.get('command', {}).get('setup_camera', {})
                            if setup_camera.get('do_action', False):
                                id_command['ir_actual'] = setup_camera.get('ircut', 'Unknown')
                        
                        # Move to Done directory
                        done_path = os.path.join(LIST_ASTRO_DIR_DEFAULT["SESSIONS_DIR"], "Done", filename)
                        os.makedirs(os.path.dirname(done_path), exist_ok=True)

                        update_process_status(command_data, 'done')

                        with open(done_path, 'w') as f:
                            json.dump(command_data, f, indent=4)
                        
                        os.remove(current_path)
                        
                        sessions_processed = True

                        log.success(f"Session {filename} completed successfully")

                        from tabs.result_session import analyze_files
                        analyze_files()

                        
                    except Exception as e:
                        # Session failed
                        log.error(f"Session {target} failed: {e}")
                        
                        id_command['process'] = 'error'
                        id_command['result'] = False
                        id_command['message'] = f'Session failed: {str(e)}'
                        
                        # ADD: Still capture Dwarf device ID even on failure
                        data_config = dwarf_python_api.get_config_data.get_config_data()
                        dwarf_id = data_config.get("dwarf_id")
                        if dwarf_id:
                            id_command['dwarf'] = f"D{dwarf_id}"
                        else:
                            id_command['dwarf'] = "Unknown"
                        
                        # Move to Error directory
                        error_path = os.path.join(LIST_ASTRO_DIR_DEFAULT["SESSIONS_DIR"], "Error", filename)
                        os.makedirs(os.path.dirname(error_path), exist_ok=True)

                        update_process_status(command_data, 'done')

                        with open(error_path, 'w') as f:
                            json.dump(command_data, f, indent=4)
                        
                        if os.path.exists(current_path):
                            os.remove(current_path)
                        
                        sessions_processed = True
    
                        #if __name__ != "__main__":
                            #self.toggle_scheduler_buttons_state(state="normal")

                    # Only process one session at a time                    
                    break
                        
            except Exception as e:
                log.error(f"Error processing {filename}: {e}")
                continue
    
    except Exception as e:
        log.error(f"Error in check_and_execute_commands: {e}")
    
    return sessions_processed

def start_connection(startSTA = False, use_web_page = False):

    result = False
    if not save_bluetooth_config_from_ini_file():
        log.error("No Wifi Data have been found, can't connect to wifi")
        log.error("Need to update the config file with Wifi Informations.") 
        return result

    if not os.path.exists("extern"):
        # python script running
        log.notice("local bluetooth connection")
        if use_web_page:
            result = connect_bluetooth() 

        else:
            ble_psd = read_bluetooth_ble_psd() or "DWARF_12345678"
            ble_STA_ssid = read_bluetooth_ble_STA_ssid() or ""
            ble_STA_pwd = read_bluetooth_ble_STA_pwd() or ""
            result = connect_ble_dwarf_win(ble_psd, ble_STA_ssid, ble_STA_pwd)

    else:
        # use external exe for bluetooth direct connection
        # code is no working in python 3.12 with CX_Freeze
        # need to use python 3.11 to build this as subprocess
        if use_web_page:
            subprocess.run(["extern\\connect_bluetooth.exe", "--web"])
        else:
            dwarf_python_api.get_config_data.update_config_data( "ip", "", True)
            subprocess.run(["extern\\connect_bluetooth.exe"])
      
        # Parse the returned value
        data_config = dwarf_python_api.get_config_data.get_config_data()
        dwarf_ip = data_config["ip"]
        result = True if dwarf_ip else False

    if startSTA and result is not False and result!= "":
        
        #init Frame : TIME and TIMEZONE
        result = perform_time()
       
        if result:
           perform_timezone()
    
    return result

def start_STA_connection(CheckDwarfId = False):

    result = False
    data_config = dwarf_python_api.get_config_data.get_config_data()
    dwarf_ip = data_config["ip"]
    dwarf_id = data_config["dwarf_id"]

    if not dwarf_ip:
        log.error("The dwarf Ip has not been set , need Bluetooth First, can't connect to wifi")
    else:
        #init Frame : TIME and TIMEZONE
        log.notice(f'Connecting to the dwarf {dwarf_id} on {dwarf_ip}')
        result = perform_time()
       
        if result:
            perform_timezone()

        if result and CheckDwarfId:
            update_dwarf_data = update_get_config_data(dwarf_ip)

            if update_dwarf_data is not None and update_dwarf_data.get('id') != dwarf_id:
                log.success(f'Updated Dwarf Type to dwarf {update_dwarf_data["id"]}')
    return result

def get_default_params_config(IP):
    return f"http://{IP}:8082/getDefaultParamsConfig"

def update_get_config_data(IPDwarf=None):
    try:
        # Determine the request address
        request_addr = get_default_params_config(IPDwarf) if IPDwarf else None
        
        if request_addr:
            # Make the HTTP GET request to the specified URL
            response = requests.get(request_addr)
            
            # Check if the response has data
            if response.status_code == 200 and 'data' in response.json():
                data = response.json().get('data')
                new_id = data.get('id') + 1 
                name = data.get('name')
                
                print(f"ID: {new_id}")
                print(f"Name: {name}")

                dwarf_python_api.get_config_data.update_config_data( 'dwarf_id', new_id)

                return {'id': new_id, 'name': name}
            else:
                print("update_get_config_data : No data found in the response.")
                return None
        else:
            print("Invalid request for update_get_config_data.")
            return None
    except requests.RequestException as error:
        print("Error fetching config data:", error)
        return None

# Main loop to check files in ToDo folder
def main():
    try:
        start_bluetooth = False
        dwarf_ip = None
        dwarf_id = None

        if len(sys.argv) > 1:
            # If command-line parameters are provided
            i = 1
            while i < len(sys.argv):
                if sys.argv[i] == "--ble":
                    start_bluetooth = True
                    log.notice("Read: --ble parameter")
                if sys.argv[i] == "--id":
                    if i + 1 < len(sys.argv):
                        dwarf_id = sys.argv[i + 1]
                        log.notice(f"Read: --id parameter => {dwarf_id}")
                        i += 1
                    else:
                        log.error("Error: --id parameter requires an argument.")
                        sys.exit(1)
                elif sys.argv[i] == "--ip":
                    if i + 1 < len(sys.argv):
                        dwarf_ip = sys.argv[i + 1]
                        log.notice(f"Read: --ip parameter => {dwarf_ip}")
                        i += 1
                    else:
                        log.error("Error: --ip parameter requires an argument.")
                        sys.exit(1)
                i += 1
            if dwarf_id:
                dwarf_python_api.get_config_data.update_config_data( 'dwarf_id', dwarf_id)
            if dwarf_ip:
                dwarf_python_api.get_config_data.update_config_data( 'ip', dwarf_ip)

        # test if Ip and Id is set
        data_config = dwarf_python_api.get_config_data.get_config_data()
        if data_config["dwarf_id"]:
            dwarf_id = data_config['dwarf_id']
        if data_config["ip"]:
            dwarf_ip = data_config['ip']

        # can't start
        if not start_bluetooth and  not (dwarf_ip and dwarf_id):
            log.notice("Some parameters are missing to connect automatically to the Dwarf, need to connect with bluetooth first.")
            start_bluetooth = True

        result = start_bluetooth
        max_retries = 3
        attempt = 0
        while not result and attempt < max_retries:
            log.notice ("##--------------------------------------##")
            log.notice(f'Try to connect to the dwarf {dwarf_id} on {dwarf_ip}')
            result = start_STA_connection()
            attempt += 1

        if start_bluetooth or not result:
            if start_bluetooth:
                log.notice('starting bluetooth....')
                result = start_connection(True)
            elif (fn_wait_for_user_input(30, "Can't connect to the dwarf, do you want to reconnect to bluetooth or continue ?\nThe program will continue if you don't press CTRL-C within 30 seconds:" ))  == 1:
                log.notice('continue ....')
                result = True
            else:
                log.notice('starting bluetooth....')
                result = start_connection(True)

        if (result):
            log.notice ("##--------------------------------------##")
            log.notice ("## Astro_Dwarf_Scheduler is starting... ##")
            log.notice ("##--------------------------------------##")
            log.notice ("   Waiting for Action files...")
            while True:
                check_and_execute_commands(True)
                time.sleep(10)
        else:
             log.error("Can't connect to the Dwarf, process stop!")
    except KeyboardInterrupt:
        log.notice("Operation interrupted by the user (CTRL+C).")
        pass
    finally:
        perform_disconnect()

if __name__ == '__main__':
    main()
