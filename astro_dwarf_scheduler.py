import os
import json
import shutil
import time
from datetime import datetime

from dwarf_session import start_dwarf_session
from dwarf_ble_connect.connect_bluetooth import connect_bluetooth
from dwarf_ble_connect.connect_bluetooth import update_htmlfile

from dwarf_python_api.lib.dwarf_utils import perform_time
from dwarf_python_api.lib.dwarf_utils import perform_timezone
from dwarf_python_api.lib.dwarf_utils import perform_disconnect

from dwarf_python_api.lib.dwarf_utils import read_bluetooth_ble_psd
from dwarf_python_api.lib.dwarf_utils import read_bluetooth_ble_STA_ssid
from dwarf_python_api.lib.dwarf_utils import read_bluetooth_ble_STA_pwd

from dwarf_python_api.get_live_data_dwarf import fn_wait_for_user_input
import dwarf_python_api.lib.my_logger as log

# Directories
TODO_DIR = './Astro_Sessions/ToDo'
CURRENT_DIR = './Astro_Sessions/Current'
DONE_DIR = './Astro_Sessions/Done'
ERROR_DIR = './Astro_Sessions/Error'

# Load the JSON file
def load_json(filepath):
    with open(filepath, 'r') as file:
        return json.load(file)

# Save the JSON file
def save_json(filepath, data):
    with open(filepath, 'w') as file:
        json.dump(data, file, indent=4)

# Move the JSON file
def move_file(source, destination):
    shutil.move(source, destination)

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
def check_and_execute_commands():
    for filename in os.listdir(TODO_DIR):
        filepath = os.path.join(TODO_DIR, filename)
        if filepath.endswith('.json'):
            log.notice("######################")
            log.notice(f"Find File  {filepath}")
            program = load_json(filepath)

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
                    if (fn_wait_for_user_input(60, "An error occuring during last Action, do you want to reconnect to bluetooth or continue ?\nThe program will contine if you don't press CTRL-C within 60 seconds:" ))  == 1:
                        print('continuing ....')
                    else:
                        start_connection()

def start_connection():

    result = False

    ble_psd = read_bluetooth_ble_psd()

    ble_STA_ssid = read_bluetooth_ble_STA_ssid()

    ble_STA_pwd = read_bluetooth_ble_STA_pwd()

    if ble_psd is not False and  ble_psd is not False and  ble_psd is not False:
        result = update_htmlfile(ble_psd, ble_STA_ssid, ble_STA_pwd)
    
        if result:
            result = connect_bluetooth()

        if result is not False and result!= "":
        
            #init Frame : TIME and TIMEZONE
            result = perform_time()
       
            if result:
               perform_timezone()
    
    return result

# Main loop to check files in ToDo folder
def main():
    try:
        result = True
        choice = input("Do you want to Start bluetooth connection Y / N (default)? ")
        if (choice == "Y"):
            result = start_connection()
        if (result):
            log.notice ("##--------------------------------------##")
            log.notice ("## Astro_Dwarf_Scheduler is starting... ##")
            log.notice ("##--------------------------------------##")
            log.notice ("   Waiting for Action files...")
            while True:
                check_and_execute_commands()
                time.sleep(10)
        else:
             log.error("Can't connect to the Dwarf, process stop!")
    except KeyboardInterrupt:
        log.notice("Operation interrupted by the user (CTRL+C).")

    finally:
        perform_disconnect()

if __name__ == '__main__':
    main()
