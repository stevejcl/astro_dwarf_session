import os
import sys
import json
import shutil
import time
from datetime import datetime

from dwarf_session import start_dwarf_session
from dwarf_ble_connect.connect_bluetooth import connect_bluetooth

from dwarf_python_api.lib.dwarf_utils import perform_time
from dwarf_python_api.lib.dwarf_utils import perform_timezone
from dwarf_python_api.lib.dwarf_utils import perform_disconnect

from dwarf_python_api.lib.dwarf_utils import save_bluetooth_config_from_ini_file
from dwarf_python_api.get_config_data import get_config_data, update_config_data

from dwarf_python_api.get_live_data_dwarf import fn_wait_for_user_input
import dwarf_python_api.lib.my_logger as log

# Directories
TODO_DIR = './Astro_Sessions/ToDo'
CURRENT_DIR = './Astro_Sessions/Current'
DONE_DIR = './Astro_Sessions/Done'
ERROR_DIR = './Astro_Sessions/Error'

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
    command_datetime = datetime.strptime(f"{command['date']} {command['time']}", "%Y-%m-%d %H:%M:%S")
    return datetime.now() >= command_datetime

# Update the process status in the JSON file
def update_process_status(program, status, result=None, message=None, nb_try=None):
    command = program['command']['id_command']
    command['process'] = status
    if result is not None:
        command['result'] = result
    if message:
        command['message'] = message
    if nb_try is not None:
        command['nb_try'] = nb_try
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

# Main function to check and execute the commands
def check_and_execute_commands(askBluetooth = False):
    for filename in os.listdir(TODO_DIR):
        filepath = os.path.join(TODO_DIR, filename)
        if filepath.endswith('.json'):
            log.notice("######################")
            log.notice(f"Find File  {filepath}")
            program = load_json(filepath)
            if program is False:
                return

            # Extract command info
            command = program['command']['id_command']

            # Check if the execution time has been reached
            if is_time_to_execute(command) and command['process'] == 'wait':
                log.debug(f"Executing command {command['uuid']}")

                # Move to "Current" folder and update status
                current_filepath = os.path.join(CURRENT_DIR, filename)
                program = update_process_status(program, 'pending')
                save_json(filepath, program)
                move_file(filepath, current_filepath)

                try:
                    # Execute the session
                    max_retries = int(program['command']['id_command'].get('max_retries', 3))
                    nb_try = retry_procedure(program)

                    # If successful, update process and result
                    program = update_process_status(program, 'ended', True, "Action completed successfully.", nb_try)
                    save_json(current_filepath, program)

                    # Move file to "Done" folder
                    move_file(current_filepath, os.path.join(DONE_DIR, filename))

                except Exception as e:
                    # Handle errors and update process and result
                    error_message = f"Error during execution: {e}"
                    log.error(error_message)

                    program = update_process_status(program, 'ended', False, error_message, max_retries)
                    save_json(current_filepath, program)

                    # Move file to "Error" folder
                    move_file(current_filepath, os.path.join(ERROR_DIR, filename))
                    log.notice("----------------------")
                    log.notice("----------------------")
                    if (askBluetooth and fn_wait_for_user_input(60, "An error occuring during last Action, do you want to reconnect to bluetooth or continue ?\nThe program will contine if you don't press CTRL-C within 60 seconds:" ))  == 1:
                        log.notice('continuing ....')
                    elif askBluetooth:
                        start_connection(True)
                    else:
                        log.notice('continuing ....')
                    pass

def start_connection(startSTA = False):

    if not save_bluetooth_config_from_ini_file():
        log.error("No Wifi Data have been found, can't connect to wifi")
        log.error("Need to update the config file with Wifi Informations.") 
        result = False

    else:
        result = connect_bluetooth()

        if startSTA and result is not False and result!= "":
        
            #init Frame : TIME and TIMEZONE
            result = perform_time()
       
            if result:
               perform_timezone()
    
    return result

def start_STA_connection():

    #init Frame : TIME and TIMEZONE
    result = perform_time()
       
    if result:
       perform_timezone()
    
    return result

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
                update_config_data( 'dwarf_id', dwarf_id)
            if dwarf_ip:
                update_config_data( 'ip', dwarf_ip)

        # test if Ip and Id is set
        data_config = get_config_data()
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
