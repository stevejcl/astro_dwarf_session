import os
import shutil
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
from astro_dwarf_scheduler import check_and_execute_commands, start_connection, start_STA_connection, setup_new_config
from dwarf_python_api.lib.dwarf_utils import perform_disconnect, unset_HostMaster, set_HostMaster, start_polar_align, motor_action

# import data for config.py
import dwarf_python_api.get_config_data

import logging
import dwarf_python_api.lib.my_logger as log
from dwarf_python_api.lib.my_logger import NOTICE_LEVEL_NUM

from tabs import settings
from tabs import create_session
from tabs import overview_session
from tabs import result_session

# import directories
from astro_dwarf_scheduler import CONFIG_DEFAULT, BASE_DIR, DEVICES_DIR, LIST_ASTRO_DIR_DEFAULT

# Devices list file
DEVICES_FILE = os.path.join(DEVICES_DIR, 'list_devices.txt')

def load_configuration():
    # Ensure the devices directory exists
    os.makedirs(DEVICES_DIR, exist_ok=True)
    
    # Ensure the list_devices.txt file exists
    if not os.path.exists(DEVICES_FILE):
        with open(DEVICES_FILE, 'w') as file:
            pass  # Create an empty file

    # load configs in DEVICES_FILE
    devices = [CONFIG_DEFAULT]
    with open(DEVICES_FILE, 'r+') as file:
        devices = [line.strip() for line in file.readlines()]
    
    # Combine CONFIG_DEFAULT with the devices from the file, avoiding duplicates
    devices = list({CONFIG_DEFAULT, *devices})

    return devices

def check_new_configuration(config_name):
    """check a configuration exist and recreate the required directory structure if not present."""

    isPresent = False

    if config_name == CONFIG_DEFAULT: 
        return True

    # Check if the config already exists in the file
    with open(DEVICES_FILE, 'r+') as file:
        devices = [line.strip() for line in file.readlines()]
        if config_name in devices:
            isPresent = True

    if isPresent:
        # Create the main configuration directory if it doesn't exist
        config_dir = os.path.join(DEVICES_DIR, config_name)
        os.makedirs(config_dir, exist_ok=True)
    
        SESSIONS_DIR = os.path.join(config_dir, 'Astro_Sessions')
        # Ensure the devices directory exists
        os.makedirs(SESSIONS_DIR, exist_ok=True)
    
        # Create the subdirectories if they don't exist
        for dir_key, subdir in LIST_ASTRO_DIR_DEFAULT.items():
            if dir_key != "SESSIONS_DIR":
                full_path = os.path.join(SESSIONS_DIR, subdir)
                os.makedirs(full_path, exist_ok=True)

    return isPresent

def add_new_configuration(config_name):
    """Add a new configuration and create the required directory structure."""

    config_dir = os.path.join(DEVICES_DIR, config_name)
    
    # Ensure the devices directory exists
    os.makedirs(DEVICES_DIR, exist_ok=True)
    
    # Ensure the list_devices.txt file exists
    if not os.path.exists(DEVICES_FILE):
        with open(DEVICES_FILE, 'w') as file:
            pass  # Create an empty file

    # Check if the config already exists in the file
    with open(DEVICES_FILE, 'r+') as file:
        devices = [line.strip() for line in file.readlines()]
        if config_name not in devices:
            # Add the configuration name to the file if not present
            file.write(config_name + '\n')
    
    # Create the main configuration directory if it doesn't exist
    os.makedirs(config_dir, exist_ok=True)

    SESSIONS_DIR = os.path.join(config_dir, 'Astro_Sessions')
    # Ensure the devices directory exists
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    
    # Create the subdirectories if they don't exist
    for dir_key, subdir in LIST_ASTRO_DIR_DEFAULT.items():
        if dir_key != "SESSIONS_DIR":
            full_path = os.path.join(SESSIONS_DIR, subdir)
            os.makedirs(full_path, exist_ok=True)

    print(f"Configuration '{config_name}' added successfully with required directory structure.")

# Tooltip class
class Tooltip:
    """Create a tooltip for a given widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None

        # Bind events to show/hide the tooltip
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window is not None:
            return  # Tooltip is already visible
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip_window, text=self.text, background="lightyellow", borderwidth=1, relief="solid")
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class TextHandler(logging.Handler):
    """
    This class allows logging to be directed to a Tkinter Text widget.
    """
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.config(state=tk.NORMAL)
    
    def emit(self, record):
        # Format the log message
        msg = self.format(record)
        # Append the message to the text widget
        self.text_widget.insert(tk.END, msg + '\n')
        # Auto scroll to the end
        self.text_widget.yview(tk.END)

# GUI Application class
class AstroDwarfSchedulerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Astro Dwarf Scheduler")
        self.geometry("800x800")
        
        # Create tabs
        self.tab_control = ttk.Notebook(self)
        self.tab_control.pack(expand=1, fill="both")
        
        self.tab_main = ttk.Frame(self.tab_control)
        self.tab_settings = ttk.Frame(self.tab_control)
        self.tab_overview_session = ttk.Frame(self.tab_control)
        self.tab_result_session = ttk.Frame(self.tab_control)
        self.tab_create_session = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.tab_main, text="Main")
        self.tab_control.add(self.tab_settings, text="Settings")
        self.tab_control.add(self.tab_overview_session, text="Session Overview")
        self.tab_control.add(self.tab_result_session, text="Results Session")
        self.tab_control.add(self.tab_create_session, text="Create Session")
        
        self.refresh_results = None
        self.create_main_tab()
        self.settings_vars = {}
        self.config_vars = {}
        settings.create_settings_tab(self.tab_settings, self.config_vars) 
        overview_session.overview_session_tab(self.tab_overview_session)
        # Add the tab's content and capture the refresh function
        self.refresh_results = result_session.result_session_tab(self.tab_result_session)
        create_session.create_session_tab(self.tab_create_session, self.settings_vars, self.config_vars)

        self.result = False
        self.bluetooth_connected = False
        self.stellarium_connection = None
        self.scheduler_running = False
        self.scheduler_stopped = True
        self.unset_lock_device_mode = True
        self.protocol("WM_DELETE_WINDOW", self.quit_method)

    def refresh_data(self):
        # Call the refresh function directly
        if self.refresh_results:
            self.refresh_results()

    def quit_method(self):
        '''
        User wants to quit
        '''
        print("Wait during closing...")
        self.log("Wait during closing...")

        # Schedule the close after a delay without blocking the GUI
        self.after(1000, self.finalize_close)  # 1000ms = 1 second delay

    def finalize_close(self):
        '''
        Perform the final close with a delay to give time for any cleanup
        '''
        self.force_stop_connect_bluetooth()

        if self.scheduler_running:
            self.log("Waiting Closing Scheduler...")
            self.stop_scheduler()
        
            self.countdown(20)

        else:
            self.after(5000, self.destroy)

    def force_stop_connect_bluetooth(self):
        # Read the config file and update the UI to Close
        dwarf_python_api.get_config_data.update_config_data( "ui", "Close", True)

    def countdown(self, wait):
        '''
        Countdown that checks scheduler status and waits for stop or timeout
        '''
        if self.scheduler_stopped:
            self.log("Scheduler stopped, closing now.")
            self.after(500, self.destroy)
        elif wait > 0:
            # Schedule the countdown to run again after 1 second
            self.after(1000, self.countdown, wait - 1)
        else:
            self.log("Time's up! Closing now...")
            self.after(500, self.destroy)
 
    def toggle_multiple(self):
        """Show or hide the Listbox and related widgets based on checkbox state."""
        if self.multiple_var.get():
            devices = load_configuration()  # Call the function to load devices
            self.config_combobox["values"] = devices
            self.config_combobox.set(CONFIG_DEFAULT)  # Always set CONFIG_DEFAULT as selected initially
            self.combobox_label.grid(row=0, column=1, sticky="w", padx=5)
            self.config_combobox.grid(row=0, column=2, sticky="w", padx=5)
            self.entry_label.grid(row=0, column=3, sticky="w", padx=5)
            self.config_entry.grid(row=0, column=4, sticky="w", padx=5)
            self.add_button.grid(row=0, column=5, sticky="w", padx=5)
            self.show_current_config(CONFIG_DEFAULT)
        else:
            self.config_combobox.set("")
            self.combobox_label.grid_remove()
            self.config_combobox.grid_remove()
            self.entry_label.grid_remove()
            self.config_entry.grid_remove()
            self.add_button.grid_remove()
            setup_new_config(CONFIG_DEFAULT)
            self.show_current_config(CONFIG_DEFAULT)

    def on_combobox_change(self, event):
        global LIST_ASTRO_DIR
        selected_value = self.config_combobox.get()
        print(f"Selected Configuration: {selected_value}")
        setup_new_config(selected_value)
        self.show_current_config(selected_value)

    def add_config(self):
        """Add a new configuration to the Listbox."""
        config_name = self.config_entry.get().strip().capitalize()
        if config_name:
            if check_new_configuration(config_name):
                self.config_combobox.set(config_name)
                self.config_entry.delete(0, tk.END)
                self.show_current_config(config_name)
            else:
                # Add to Combobox values
                current_values = list(self.config_combobox["values"])
                current_values.append(config_name)
                self.config_combobox["values"] = current_values
                self.config_combobox.set(config_name)  # Set the newly added config as the current selection
                self.config_entry.delete(0, tk.END)
                setup_new_config(config_name)
                add_new_configuration(config_name)
                self.show_current_config(config_name, True)
        else:
            messagebox.showwarning("Input Error", "Configuration name cannot be empty.")

    def show_current_config(self, config_name, created = False):
        from astro_dwarf_scheduler import LIST_ASTRO_DIR

        if (self.log_text):
            if config_name == CONFIG_DEFAULT:
                self.log("Default configuration selected.")
            elif created:
                self.log(f"New configuration '{config_name}' created.")
            else:
                self.log(f"Configuration '{config_name}' selected.")
            self.log(f"  Session directory is : '{LIST_ASTRO_DIR["SESSIONS_DIR"]}'.")

        self.refresh_data()

    def disable_controls(self):
        """Disable the checkbox and Add button."""
        self.multiple_checkbox.config(state=tk.DISABLED)
        self.config_combobox.config(state=tk.DISABLED)
        self.add_button.config(state=tk.DISABLED)

    def enable_controls(self):
        """Enable the checkbox and Add button."""
        self.multiple_checkbox.config(state=tk.NORMAL)
        self.config_combobox.config(state=tk.NORMAL)
        self.add_button.config(state=tk.NORMAL)

    def create_main_tab(self):
        self.log_text = None
        # Multipla configuration prompt label
        self.labelConfig = tk.Label(self.tab_main, text="Configuration", font=("Arial", 12))
        self.labelConfig.pack(anchor="w", padx=10, pady=10)

        # Checkbox for "Multiple"
        multiple_frame = tk.Frame(self.tab_main)
        multiple_frame.pack(anchor="w", padx=10, pady=5)

        self.multiple_var = tk.BooleanVar(value=False)
        self.multiple_checkbox = tk.Checkbutton(multiple_frame, text="Multiple", variable=self.multiple_var, command=self.toggle_multiple)
        self.multiple_checkbox.grid(row=0, column=0, sticky="w", padx=10)

        # Label and Combobox for configurations
        self.combobox_label = tk.Label(multiple_frame, text="Current Config:")
        self.config_combobox = ttk.Combobox(multiple_frame, state="readonly", width=27)
        self.config_combobox["values"] = (CONFIG_DEFAULT,)
        self.config_combobox.set(CONFIG_DEFAULT)  # Set the default value

        # Text entry and Add button
        self.entry_label = tk.Label(multiple_frame, text="New Config:")
        self.config_entry = tk.Entry(multiple_frame, width=20)
        self.add_button = tk.Button(multiple_frame, text="Add Config", command=self.add_config)

        # Initialize with widgets hidden (non-multiple mode)
        self.toggle_multiple()
        self.config_combobox.bind("<<ComboboxSelected>>", self.on_combobox_change)

        # Tooltip for Multiple Configuration connection prompt
        Tooltip(self.labelConfig, "Tick the multiple checkox if you have more than one Dwarf devices.")

        # Bluetooth connection prompt label
        self.label1 = tk.Label(self.tab_main, text="Dwarf connection", font=("Arial", 12))
        self.label1.pack(anchor="w", padx=10, pady=5)

        # Checkbox to toggle between Bluetooth commands
        self.use_web = tk.BooleanVar(value=False)
        self.checkbox_commandBluetooth = tk.Checkbutton(
            self.tab_main,
            text="Use Web Browser for Bluetooth",
            variable=self.use_web
        )
        self.checkbox_commandBluetooth.pack(anchor="w", padx=10, pady=5)

        # Add tooltip to the checkbox
        Tooltip(self.checkbox_commandBluetooth, "Use the direct Bluetooth function if unchecked.\nUse the web browser for Bluetooth if checked.")

        # Tooltip for Bluetooth connection prompt
        self.label2 = tk.Label(self.tab_main, text="Do you want to start the Bluetooth connection?", font=("Arial", 10))
        self.label2.pack(anchor="w", padx=10, pady=5)
        Tooltip(self.label2, "Select Yes to launch the command for Bluetooth connection or No to skip the connection.")

        # Frame for Bluetooth connection buttons
        bluetooth_frame = tk.Frame(self.tab_main)
        bluetooth_frame.pack(anchor="w", padx=10, pady=5)
        
        self.button_yes = tk.Button(bluetooth_frame, text="Yes", command=self.start_bluetooth, width=10)
        self.button_yes.grid(row=0, column=0, padx=5)
        
        self.button_no = tk.Button(bluetooth_frame, text="No", command=self.skip_bluetooth, width=10)
        self.button_no.grid(row=0, column=1, padx=5)
        
        # Frame for Start/Stop Scheduler buttons
        self.label3 = tk.Label(self.tab_main, text="Scheduler", font=("Arial", 12))
        self.label3.pack(anchor="w", padx=10, pady=10)

        scheduler_frame = tk.Frame(self.tab_main)
        scheduler_frame.pack(anchor="w", padx=10, pady=10)
        
        self.start_button = tk.Button(scheduler_frame, text="Start Scheduler", command=self.start_scheduler, state=tk.DISABLED, width=16)
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = tk.Button(scheduler_frame, text="Stop Scheduler", command=self.stop_scheduler, state=tk.DISABLED, width=16)
        self.stop_button.grid(row=0, column=1, padx=5)

        self.unlock_button = tk.Button(scheduler_frame, text="Unset Device as Host", command=self.unset_lock_device, state=tk.DISABLED, width=16)
        self.unlock_button.grid(row=0, column=2, padx=5)

        self.eq_button = tk.Button(scheduler_frame, text="EQ Solving", command=self.start_eq_solving, state=tk.DISABLED, width=16)
        self.eq_button.grid(row=0, column=3, padx=5)

        self.polar_button = tk.Button(scheduler_frame, text="Polar Position", command=self.start_polar_position, state=tk.DISABLED, width=16)
        self.polar_button.grid(row=0, column=4, padx=5)
        
        # Log text area
        self.log_text = tk.Text(self.tab_main, wrap=tk.WORD, height=15)
        self.log_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    def start_bluetooth(self):
        self.disable_controls()
        self.log("Starting Bluetooth connection in a separate thread...")
        threading.Thread(target=self.bluetooth_connect_thread).start()

    def bluetooth_connect_thread(self):
        try:
            self.bluetooth_connected = False
            self.result = start_connection(False, self.use_web.get())
            if self.result:
                self.log("Bluetooth connected successfully.")
                self.bluetooth_connected = True
                # Enable the start scheduler button
                self.start_button.config(state=tk.NORMAL)
            else:
                self.log("Bluetooth connection failed.")
        except Exception as e:
            self.log(f"Bluetooth connection failed: {e}")

      #  self.after(0, self.start_scheduler)

    def skip_bluetooth(self):
        self.log("Bluetooth connection skipped.")
        # Enable the start scheduler button
        self.bluetooth_connected = False
        self.start_button.config(state=tk.NORMAL)

    def start_scheduler(self):
        self.disable_controls()
        if not self.scheduler_running:
            self.scheduler_running = True
            self.start_logHandler()
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.unlock_button.config(state=tk.NORMAL)
            self.eq_button.config(state=tk.NORMAL)
            self.polar_button.config(state=tk.NORMAL)
            self.log("Astro_Dwarf_Scheduler is starting...")
            self.scheduler_thread = threading.Thread(target=self.run_scheduler)
            self.scheduler_thread.start()

    def stop_scheduler(self):
        self.stop_logHandler()
        if self.scheduler_running:
            self.scheduler_running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.unlock_button.config(state=tk.DISABLED)
            self.eq_button.config(state=tk.DISABLED)
            self.polar_button.config(state=tk.DISABLED)
            self.verifyCountdown(15)
            self.log("Scheduler is stopping...")
        else:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.unlock_button.config(state=tk.DISABLED)
            self.eq_button.config(state=tk.DISABLED)
            self.polar_button.config(state=tk.DISABLED)
            self.log("Scheduler is stopped")
            self.enable_controls()

    def unset_lock_device(self):
        self.scheduler_thread = threading.Thread(target=self.run_unset_lock_device)
        self.scheduler_thread.start()

    def start_eq_solving(self):
        self.scheduler_thread = threading.Thread(target=self.run_start_eq_solving)
        self.scheduler_thread.start()

    def start_polar_position(self):
        self.scheduler_thread = threading.Thread(target=self.run_start_polar_position)
        self.scheduler_thread.start()

    def verifyCountdown(self, wait):
        '''
        verifyCountdown that checks scheduler status and waits for stop or timeout
        '''
        if self.scheduler_stopped:
            self.log("Scheduler stopped.")
            self.enable_controls()
        elif wait > 0:
            # Schedule the verifyCountdown to run again after 1 second
            self.after(1000, self.verifyCountdown, wait - 1)
        else:
            self.log("Time's up! Closing now...")
            self.after(500, perform_disconnect())
            self.enable_controls()

    def run_scheduler(self):
        try:
            self.scheduler_stopped = False
            attempt = 0
            result = False
            while not result and attempt < 3 and self.scheduler_running:
                attempt += 1
                result = start_STA_connection(not self.bluetooth_connected)
            if result:
                self.log("Connected to the Dwarf")
            while result and self.scheduler_running:
                check_and_execute_commands()
                time.sleep(10)  # Sleep for 10 seconds between checks
        except KeyboardInterrupt:
            self.log("Operation interrupted by the user.")
        finally:
            perform_disconnect()
            self.log("Disconnected from the Dwarf.")
            self.scheduler_running = False
            self.scheduler_stopped = True

    def run_unset_lock_device(self):
        try:
            attempt = 0
            result = False
            while not result and attempt < 3:
                attempt += 1
                if self.unset_lock_device_mode:
                    result = unset_HostMaster()
                else:
                    result = set_HostMaster()
                if not result:
                    time.sleep(10)  # Sleep for 10 seconds between checks
            if result:
                if self.unset_lock_device_mode:
                    self.unlock_button.config(text="Set Device as Host")
                else:
                    self.unlock_button.config(text="Unset Device as Host")
                self.unset_lock_device_mode = not self.unset_lock_device_mode
                self.unlock_button.update()
        except KeyboardInterrupt:
            self.log("Operation interrupted by the user.")

    def run_start_eq_solving(self):
        try:
            attempt = 0
            result = False
            self.log("Starting EQ Solving process...")
            while not result and attempt < 3:
                attempt += 1
                result = start_polar_align()
                if not result:
                    time.sleep(10)  # Sleep for 10 seconds between checks
        except KeyboardInterrupt:
            self.log("Operation interrupted by the user.")

    def run_start_polar_position(self):
        try:
            dwarf_id = "2"
            data_config = dwarf_python_api.get_config_data.get_config_data()
            if data_config["dwarf_id"]:
                dwarf_id = data_config['dwarf_id']

            attempt = 0
            result = False
            self.log("Starting Polar Align positionning...")
            while not result and attempt < 1:
                attempt += 1
                # Rotation Motor Resetting
                result = motor_action(5)
                if result:
                     # Pitch Motor Resetting
                     result = motor_action(6)
                if result and dwarf_id == "3":
                     # Rotation Motor positioning D3
                     result = motor_action(9)
                elif result:
                     # Rotation Motor positioning
                     result = motor_action(2)
                if result and dwarf_id == "3":
                     # Pitch Motor positioning D3
                     result = motor_action(7)
                elif result:
                     # Pitch Motor positioning
                     result = motor_action(3)

                if result:
                     self.log("Success Polar Align positionning")
                if not result:
                    time.sleep(10)  # Sleep for 10 seconds between checks
        except KeyboardInterrupt:
            self.log("Operation interrupted by the user.")

    def start_logHandler(self):

        # Create an instance of the TextHandler and attach it to the logger
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)  # Ensure all messages are captured

        self.text_handler = TextHandler(self.log_text)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',  datefmt='%y-%m-%d %H:%M:%S')
        self.text_handler.setFormatter(formatter)
        self.text_handler.setLevel(NOTICE_LEVEL_NUM)
        self.logger.addHandler(self.text_handler)

    def stop_logHandler(self):

        self.logger.info("Removing L...")
        self.logger.removeHandler(self.text_handler)  # Remove the TextHandler

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

# Main application
if __name__ == "__main__":
    app = AstroDwarfSchedulerApp()
    app.mainloop()
