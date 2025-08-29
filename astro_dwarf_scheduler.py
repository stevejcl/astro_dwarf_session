import os
import sys
import json
import shutil
import time
import subprocess

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
# The config value for dwarf_id is offset by -1 (stored as one less than the actual ID).
# the value return by get_config_data must be used with these functions
from dwarf_python_api.get_config_data import config_to_dwarf_id_str, config_to_dwarf_id_int

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

# Move the JSON file
def move_file(source, destination):
    try:
        shutil.move(source, destination)
    except Exception as e:
        log.error(f"error moving file: {source} to {destination} - {e}")
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

# Get the execution time for later processing
def get_time_to_execute(current_datetime, command):
    # Safely get 'date' and 'time' from the command, defaulting to now if missing
    command_date = command.get('date', current_datetime.strftime("%Y-%m-%d"))
    command_time = command.get('time', current_datetime.strftime("%H:%M:%S"))
            
    # Combine 'date' and 'time' into a single datetime object
    command_datetime = datetime.strptime(f"{command_date} {command_time}", "%Y-%m-%d %H:%M:%S")

    return command_datetime

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
        command['dwarf'] = "D" + config_to_dwarf_id_str(dwarf_id)
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status == "pending":
        command['starting_date'] = current_datetime
    command['processed_date'] = current_datetime
    return program  # Return the updated entire program object

def retry_procedure(program, max_retries =3):
    attempt = 0
    while attempt < max_retries:
        try:
            # Execute the session
            start_dwarf_session(program['command'])
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

# Main function to check and execute the commands
def check_and_execute_commands(askBluetooth = False):
    global LIST_ASTRO_DIR
    for filename in os.listdir(LIST_ASTRO_DIR["TODO_DIR"]):
        filepath = os.path.join(LIST_ASTRO_DIR["TODO_DIR"], filename)
        if filepath.endswith('.json'):
            program = load_json(filepath)
            if program is False:
                return

            # Extract command info
            command = program.get('command', {}).get('id_command')

            # ignore file if command or id_command doesn't exist
            if not command:
                log.error(f"Mandatory commands not found in file, the file {filename} is ignored")
                # Move file to "Error" folder
                current_filepath = os.path.join(LIST_ASTRO_DIR["TODO_DIR"], filename)
                move_file(current_filepath, os.path.join(LIST_ASTRO_DIR["ERROR_DIR"], filename))
                log.notice("----------------------")
                log.notice("----------------------")

            # Ignore file if process exists and is different from 'wait' 
            elif command.get('process') is not None and command.get('process') != 'wait':
                log.warning(f"Process value is not 'wait', the file {filename} is ignored")
                # Move file to "Error" folder
                current_filepath = os.path.join(LIST_ASTRO_DIR["TODO_DIR"], filename)
                move_file(current_filepath, os.path.join(LIST_ASTRO_DIR["ERROR_DIR"], filename))
                log.notice("----------------------")
                log.notice("----------------------")
            # Check if the execution time has been reached
            elif is_time_to_execute(command) and command.get('process', 'wait') == 'wait':
                log.notice("######################")
                log.notice(f"Find File  {filename}, that is ready to execute")
                log.debug(f"Executing command {command.get('uuid')}")

                # Move to "Current" folder and update status
                current_filepath = os.path.join(LIST_ASTRO_DIR["CURRENT_DIR"], filename)
                program = update_process_status(program, 'pending')
                save_json(filepath, program)
                move_file(filepath, current_filepath)

                # Remove from the logging dictionary as it's been executed
                if filename in last_logged:
                    del last_logged[filename]
                if filename in last_hourly_log:
                    del last_hourly_log[filename]

                try:
                    # Get The Dwarf Type
                    data_config = dwarf_python_api.get_config_data.get_config_data()
                    dwarf_id = "2"
                    if data_config["dwarf_id"]:
                        dwarf_id = data_config['dwarf_id']
                    # Execute the session
                    max_retries = int(program['command']['id_command'].get('max_retries', 3))
                    nb_try = retry_procedure(program)

                    # If successful, update process and result
                    program = update_process_status(program, 'ended', True, "Action completed successfully.", nb_try, dwarf_id)
                    save_json(current_filepath, program)

                    # Move file to "Done" folder
                    move_file(current_filepath, os.path.join(LIST_ASTRO_DIR["DONE_DIR"], filename))

                except Exception as e:
                    # Handle errors and update process and result
                    error_message = f"Error during execution: {e}"
                    log.error(error_message)

                    program = update_process_status(program, 'ended', False, error_message, max_retries, dwarf_id)
                    save_json(current_filepath, program)

                    # Move file to "Error" folder
                    move_file(current_filepath, os.path.join(LIST_ASTRO_DIR["ERROR_DIR"], filename))
                    log.notice("----------------------")
                    log.notice("----------------------")
                    if (askBluetooth and fn_wait_for_user_input(60, "An error occuring during last Action, do you want to reconnect to bluetooth or continue ?\nThe program will contine if you don't press CTRL-C within 60 seconds:" ))  == 1:
                        log.notice('continuing ....')
                    elif askBluetooth:
                        start_connection(True)
                    else:
                        log.notice('continuing ....')
                    pass

            # Log Ignore time
            elif command.get('process', 'wait') == 'wait':
                # Get current date and time
                current_datetime = datetime.now()
                command_datetime = get_time_to_execute(current_datetime, command)

                # If the file isn't ready, log it based on the time since the last log
                if filename not in last_logged:
                    # Log the first time
                    log_command_status(filename, command_datetime, first_time=True)
                    last_logged[filename] = current_datetime
                    last_hourly_log[filename] = current_datetime  # Initialize hourly log
                else:
                    # Check for hourly log
                    if current_datetime - last_hourly_log[filename] >= timedelta(hours=1):
                        log_command_status(filename, command_datetime, interval="Hourly")
                        last_hourly_log[filename] = current_datetime  # Update last hourly log

                    # Check for 30 minutes, 15 minutes, and 5 minutes before execution
                    time_intervals = {
                        '5 minutes': timedelta(minutes=5),
                        '15 minutes': timedelta(minutes=15),
                        '30 minutes': timedelta(minutes=30)
                    }
                    
                    for interval, delta in time_intervals.items():
                        # Check if the time until the command execution exceeds the interval
                        if command_datetime - current_datetime <= delta:
                            # Only log if we haven't logged this interval yet
                            if filename not in last_logged or last_logged[filename] != interval:
                                log_command_status(filename, command_datetime, interval)
                                last_logged[filename] = interval  # Update last logged interval
                            break  # Break to avoid logging multiple times for the same interval


def log_command_status(filename, command_datetime, interval=None, first_time=False):
    if first_time:
        log.notice("######################")
        log.notice(f"Find File  {filename}, not yet ready, will execute not earlier than {command_datetime}")
    else:
        log.notice("######################")
        log.notice(f"{interval} log:  {filename}, not yet ready, will execute not earlier than {command_datetime}")

def start_connection(startSTA = False, use_web_page = False):

    result = False
    if not save_bluetooth_config_from_ini_file():
        log.error("No Wifi Data have been found, can't connect to wifi")
        log.error("Need to update the config file with Wifi Informations.") 
        return result

    if not os.path.exists("extern"):
        # python script running
        log.info("local bluetooth connection")
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
        log.notice(f'Connecting to the dwarf {config_to_dwarf_id_int(dwarf_id)} on {dwarf_ip}')
        result = perform_time()
       
        if result:
            perform_timezone()

        if result and CheckDwarfId:
            update_dwarf_data = update_get_config_data(dwarf_ip)

            if update_dwarf_data['id'] != dwarf_id:
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
                new_id = data.get('id') 
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
                # ask for dwarf_id = 2 or 3, need to substract 1 to get the real dwarf_id use in config file
                if sys.argv[i] == "--id":
                    if i + 1 < len(sys.argv):
                        dwarf_id = int(sys.argv[i + 1]) - 1
                        log.notice(f"Read: --id parameter => {config_to_dwarf_id_str(dwarf_id)}")
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
            log.notice(f'Try to connect to the dwarf {config_to_dwarf_id_int(dwarf_id)} on {dwarf_ip}')
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
