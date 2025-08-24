from fractions import Fraction
import os
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
from config import DWARF_IP
from astro_dwarf_scheduler import check_and_execute_commands, start_connection, start_STA_connection, setup_new_config
from dwarf_python_api.lib.dwarf_utils import perform_disconnect, perform_stopAstroPhoto, perform_update_camera_setting, perform_time, perform_GoLive, unset_HostMaster, set_HostMaster, perform_stop_goto, perform_calibration, start_polar_align, motor_action
import signal
from astro_dwarf_scheduler import LIST_ASTRO_DIR, get_json_files_sorted
import json
from datetime import datetime, timedelta
import traceback

# import data for config.py
import dwarf_python_api.get_config_data

import logging
from dwarf_python_api.lib.my_logger import NOTICE_LEVEL_NUM

from dwarf_session import verify_action
from tabs import settings
from tabs import create_session
from tabs import overview_session
from tabs import result_session

# import directories
from astro_dwarf_scheduler import CONFIG_DEFAULT, BASE_DIR, LIST_ASTRO_DIR_DEFAULT
import os

# Devices and sessions directories now use BASE_DIR from scheduler (AppData-aware)
DEVICES_DIR = os.path.join(BASE_DIR, "Devices_Sessions")
DEVICES_FILE = os.path.join(DEVICES_DIR, 'list_devices.txt')

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
    
def toggle_scheduler_buttons_state(self, state):
    # Toggle the state of the scheduler buttons only if running from UI
    self.after(0, lambda: self.start_button.config(state=state))
    self.after(0, lambda: self.eq_button.config(state=state))
    self.after(0, lambda: self.polar_button.config(state=state))
    self.after(0, lambda: self.calibrate_button.config(state=state))

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
        # Determine color and emoji based on log level
        if record.levelno >= logging.ERROR:
            color = 'red'
            emoji = '✗ '
        elif record.levelno == logging.WARNING:
            color = 'orange'
            emoji = '⚠ '
        elif record.levelno == logging.INFO:
            color = 'gray'
            emoji = 'ℹ '
        elif record.levelno == 25:
            color = 'green'
            emoji = '✓ '
        else:
            color = 'black'
            emoji = '⇒ '

        # Insert with tag for color
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, emoji + msg + '\n', color)
        self.text_widget.tag_config(color, foreground=color)
        self.text_widget.yview(tk.END)

# GUI Application class
class AstroDwarfSchedulerApp(tk.Tk):
    def start_video_preview(self):
        import io
        import threading
        import time
        try:
            from PIL import Image, ImageTk
            import requests
        except ImportError:
            self.video_canvas.config(text="Install Pillow and requests for video preview.")
            return

        def video_stream_worker():
            last_frame_time = 0
            while not getattr(self, '_stop_video_stream', False):
                try:
                    stream = requests.get(self.video_stream_url, stream=True, timeout=60)
                    bytes_data = b""
                    last_update = 0
                    for chunk in stream.iter_content(chunk_size=1024):
                        bytes_data += chunk
                        a = bytes_data.find(b'\xff\xd8')
                        b = bytes_data.find(b'\xff\xd9')
                        if a != -1 and b != -1:
                            jpg = bytes_data[a:b+2]
                            bytes_data = bytes_data[b+2:]
                            try:
                                image = Image.open(io.BytesIO(jpg)).resize((220, 140))
                                photo = ImageTk.PhotoImage(image)
                                now = time.time()
                                if now - last_update > 0.3:
                                    self.after(0, self.update_video_canvas, photo)
                                    last_update = now
                            except Exception:
                                pass
                        if getattr(self, '_stop_video_stream', False):
                            break
                    # If we got here, stream ended or stopped, retry after short delay
                except Exception:
                    self.after(0, lambda: self.video_canvas.config(image='', text="No video stream."))
                time.sleep(3)  # Wait 3 seconds before retrying

        threading.Thread(target=video_stream_worker, daemon=True).start()

    def update_video_canvas(self, photo):
        self.video_canvas.config(image=photo)
        self._video_photo = photo  # Keep a reference to avoid garbage collection
        
    def __init__(self):
        super().__init__()
        self.title("Astro Dwarf Scheduler")
        self.geometry("810x800")

        # --- Initialize all attributes used by methods before any method that uses them ---
        self.scheduler_running = False
        self.scheduler_stopped = True
        self.scheduler_stop_event = threading.Event()
        self.unset_lock_device_mode = True
        self.bluetooth_connected = False
        self.result = False
        self.stellarium_connection = None
        self.skip_time_checks = False

        # Create tabs
        self.tab_control = ttk.Notebook(self)
        self.tab_control.pack(expand=1, fill="both", pady=(5, 0))

        self.tab_main = ttk.Frame(self.tab_control)
        self.tab_settings = ttk.Frame(self.tab_control)
        self.tab_overview_session = ttk.Frame(self.tab_control)
        self.tab_result_session = ttk.Frame(self.tab_control)
        self.tab_create_session = ttk.Frame(self.tab_control)
        self.tab_edit_sessions = ttk.Frame(self.tab_control)

        self.tab_control.add(self.tab_main, text="Main")
        self.tab_control.add(self.tab_settings, text="Settings")
        self.tab_control.add(self.tab_overview_session, text="Session Overview")
        self.tab_control.add(self.tab_result_session, text="Results Session")
        self.tab_control.add(self.tab_create_session, text="Create Session")
        self.tab_control.add(self.tab_edit_sessions, text="Edit Sessions")

        self.refresh_results = None
        self.create_main_tab()
        # Ensure file counts are updated on startup
        self.update_session_counts()
        self.settings_vars = {}
        self.config_vars = {}
        settings.create_settings_tab(self.tab_settings, self.config_vars)
        # Store refresh functions for tabs
        self.overview_refresh = None
        self.edit_sessions_refresh = None
        # Setup overview tab and capture refresh
        def set_overview_refresh(refresh_func):
            self.overview_refresh = refresh_func
        overview_session.overview_session_tab(self.tab_overview_session, set_overview_refresh)
        # Add the tab's content and capture the refresh function
        self.refresh_results = result_session.result_session_tab(self.tab_result_session)
        create_session.create_session_tab(self.tab_create_session, self.settings_vars, self.config_vars)
        # Patch create_load_session_tab to capture refresh

        from tabs import edit_sessions
        def edit_sessions_tab_wrapper():
            from astro_dwarf_scheduler import LIST_ASTRO_DIR
            session_dir = LIST_ASTRO_DIR["SESSIONS_DIR"]
            result = edit_sessions.edit_sessions_tab(self.tab_edit_sessions, session_dir)
            # result is a tuple: (refresh_list, cleanup)
            if isinstance(result, tuple) and callable(result[0]):
                self.edit_sessions_refresh = result[0]

        edit_sessions_tab_wrapper()

        # Bind tab change event to refresh file lists
        def on_tab_changed(event):
            tab = event.widget.tab(event.widget.index('current'))['text']
            #if tab == 'Edit Sessions':
            #    if self.edit_sessions_refresh:
            #        self.edit_sessions_refresh()
            if tab == 'Session Overview':
                if self.overview_refresh:
                    self.overview_refresh()
            # Update Exposure and Gain fields when Create Session tab is selected
            elif tab == 'Create Session':
                create_session.update_exposure_gain_fields(self.settings_vars)

        self.tab_control.bind('<<NotebookTabChanged>>', on_tab_changed)

    def reset_total_runtime(self):
        self.total_session_runtime = 0
        self.session_runtime = 0
        self.session_start_time = 0

    def add_to_total_runtime(self, session_seconds):
        if not hasattr(self, 'total_session_runtime'):
            self.total_session_runtime = 0
        self.total_session_runtime += session_seconds

    def set_scheduler_buttons_state(self, state):
        """Enable or disable the unlock, polar, and eq buttons on the Scheduler tab."""
        self.unlock_button.config(state=state)
        self.polar_button.config(state=state)
        self.calibrate_button.config(state=state)
        self.eq_button.config(state=state)

    # Function to get the exposure time from settings_vars
    def get_exposure_time(self, settings_vars):
        exposure_string = str(settings_vars["id_command"]["exposure"])  # Get the exposure string from settings_vars
        try:
            if not exposure_string:
                print("exposure not defined")
                return 0
            # Check for fractional input
            if '/' in exposure_string:
                exposure_seconds = float(Fraction(exposure_string))  # Convert fraction to float
            else:
                exposure_seconds = float(exposure_string)  # Convert to float to handle fractions

            return exposure_seconds  # Return the float value directly
        except (ValueError, ZeroDivisionError):
            print(f"Invalid exposure time: {exposure_string}. Defaulting to 0.")
            return 0.0  # Return a default value if conversion fails

    def calculate_end_time(self, settings_vars):
        try:
            # Get exposure and gain from settings_vars  
            settings_vars["id_command"]["exposure"] = 1
            settings_vars["id_command"]["gain"] = 1
            settings_vars["id_command"]["count"] = 1

            camera_sections = ['setup_camera', 'setup_wide_camera']
            for section in camera_sections:
                settings = settings_vars.get(section, {})
                if settings.get('do_action'):
                    settings_vars["id_command"]["exposure"] = settings['exposure']
                    settings_vars["id_command"]["gain"] = settings['gain']
                    settings_vars["id_command"]["count"] = settings['count']
                    break

            # Get the starting date, time, exposure, and count
            exposure_seconds = self.get_exposure_time(settings_vars)

            count = int(settings_vars["id_command"]["count"])

            # Initialise wait time - manual adjustment
            wait_time = 0

            if settings_vars["eq_solving"]:
                # wait time actions
                wait_time += 60
                wait_time += int(settings_vars.get("wait_before", 0))
                wait_time += int(settings_vars.get("wait_after", 0))
            if settings_vars["auto_focus"]:
                # wait time actions
                wait_time += 10
                wait_time += int(settings_vars.get("wait_before", 0))
                wait_time += int(settings_vars.get("wait_after", 0))
            if settings_vars["infinite_focus"]:
                # wait time actions
                wait_time += 5
                wait_time += int(settings_vars.get("wait_before", 0))
                wait_time += int(settings_vars.get("wait_after", 0))
            if settings_vars["calibration"]:
                dwarf_id = 2  # Ensure dwarf_id is always defined
                data_config = dwarf_python_api.get_config_data.get_config_data()
                if data_config.get("dwarf_id"):
                    dwarf_id = data_config['dwarf_id']
                # wait between actions and time actions
                wait_time += 10 + 60
                wait_time += 90 if dwarf_id == "3" else 0
                wait_time += int(settings_vars.get("wait_before", 0))
                wait_time += int(settings_vars.get("wait_after", 0))
            if settings_vars["goto_solar"] or settings_vars["goto_manual"]:
                wait_time += 30
                wait_time += int(settings_vars.get("wait_after_target", 0))

            # wait time setup camera
            wait_time += int(settings_vars.get("wait_after_camera", 0))

            if not isinstance(self.session_start_time, datetime):
                self.session_start_time = datetime.now()

            # Combine date and time into a single datetime object
            start_datetime = self.session_start_time

            # Calculate the total exposure time
            total_exposure_time = wait_time + (exposure_seconds + 1) * count 

            # Calculate end time
            end_datetime = start_datetime + timedelta(seconds=total_exposure_time)

            # Calculate duration in H:M:S
            duration = end_datetime - start_datetime
            duration_str = str(duration).split(", ")[-1]  # Get the last part (H:M:S)

            return duration_str
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
            return 0


    def quit_method(self):
        '''
        User wants to quit
        '''
        print("Wait during closing...")
        self.log("Wait during closing...")

        # Force stop the scheduler immediately
        if self.scheduler_running:
            self.scheduler_running = False
            self.scheduler_stop_event.set()
            self.log("Forcing scheduler to stop...")

        # Schedule the close with a shorter delay
        self.after(2000, self.finalize_close)  # Reduced to 2 seconds

    def finalize_close(self):
        '''
        Perform the final close with force termination if needed
        '''
        try:
            # Force disconnect
            perform_disconnect()
        except:
            pass  # Ignore errors during forced disconnect
    
        if self.scheduler_running:
            self.log("Force closing scheduler...")
            self.scheduler_running = False
            self.scheduler_stop_event.set()
            
            # Wait briefly for thread to finish, then force close
            self.countdown(5)  # Reduced timeout
        else:
            self.after(1000, self.destroy)  # Reduced delay

    def countdown(self, wait):
        '''
        Countdown that checks scheduler status and waits for stop or timeout
        '''
        if self.scheduler_stopped or not self.scheduler_running:
            self.log("Scheduler stopped, closing now.")
            self.after(500, self.destroy)
        elif wait > 0:
            # Schedule the countdown to run again after 1 second
            self.after(1000, self.countdown, wait - 1)
        else:
            self.log("Timeout reached, force closing...")
            # Cannot forcibly terminate threads safely in Python; log and proceed to close
            if hasattr(self, 'scheduler_thread') and self.scheduler_thread.is_alive():
                self.log("Scheduler thread is still running and cannot be forcibly stopped safely.", level="warning")
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


    def refresh_data(self):
        # Call the refresh function directly
        if self.refresh_results:
            self.refresh_results()
        # Always update file counts after refresh
        if hasattr(self, 'update_session_counts'):
            self.update_session_counts()

    def show_current_config(self, config_name, created = False):
        from astro_dwarf_scheduler import LIST_ASTRO_DIR

        if (self.log_text):
            if config_name == CONFIG_DEFAULT:
                self.log("Default configuration selected.")
            elif created:
                self.log(f"New configuration '{config_name}' created.")
            else:
                self.log(f"Configuration '{config_name}' selected.")
            self.log(f"  Session directory is : '{LIST_ASTRO_DIR['SESSIONS_DIR']}'.")

        self.refresh_data()
        # Always update file counts after config change
        if hasattr(self, 'update_session_counts'):
            self.update_session_counts()

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

        # --- Video Preview Frame (top right) ---
        preview_frame = tk.Frame(self.tab_main, bd=1, relief="solid")
        preview_frame.place(relx=1.0, x=-20, y=80, anchor="ne", width=220, height=123, bordermode="outside")  # Top right, moved down by 50px
        preview_frame.pack_propagate(False)
        self.video_canvas = tk.Label(preview_frame, text="No video stream.")
        self.video_canvas.pack(fill="both", expand=True)
        self.video_stream_url = f"http://{DWARF_IP}:8092/mainstream"
        self._stop_video_stream = False
        self.start_video_preview()

        # Checkbox for "Multiple" and related widgets in a grid for alignment
        multiple_frame = tk.Frame(self.tab_main)
        multiple_frame.pack(anchor="w", padx=10, pady=5, fill="x")

        self.multiple_var = tk.BooleanVar(value=False)
        self.multiple_checkbox = tk.Checkbutton(multiple_frame, text="Multiple", variable=self.multiple_var, command=self.toggle_multiple)
        self.multiple_checkbox.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=2)

        self.combobox_label = tk.Label(multiple_frame, text="Current Config:")
        self.combobox_label.grid(row=0, column=1, sticky="e", padx=(0, 4), pady=2)
        self.config_combobox = ttk.Combobox(multiple_frame, state="readonly", width=27)
        self.config_combobox["values"] = (CONFIG_DEFAULT)
        self.config_combobox.set(CONFIG_DEFAULT)
        self.config_combobox.grid(row=0, column=2, sticky="w", padx=(0, 8), pady=2)

        self.entry_label = tk.Label(multiple_frame, text="New Config:")
        self.entry_label.grid(row=0, column=3, sticky="e", padx=(0, 4), pady=2)
        self.config_entry = tk.Entry(multiple_frame, width=20)
        self.config_entry.grid(row=0, column=4, sticky="w", padx=(0, 8), pady=2)
        self.add_button = tk.Button(multiple_frame, text="Add Config", command=self.add_config)
        self.add_button.grid(row=0, column=5, sticky="w", padx=(0, 0), pady=2)

        # Make columns expand as needed
        for col in range(6):
            multiple_frame.grid_columnconfigure(col, weight=0)
        multiple_frame.grid_columnconfigure(2, weight=1)  # Make combobox column expand if needed

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
        scheduler_header_frame = tk.Frame(self.tab_main)
        scheduler_header_frame.pack(anchor="w", padx=10, pady=(5, 2), fill="x")

        self.label3 = tk.Label(scheduler_header_frame, text="Scheduler", font=("Arial", 12))
        self.label3.pack(side="left", anchor="w")

        # Add session information label to the right of the Scheduler heading
        self.session_info_label = tk.Label(scheduler_header_frame, text="", font=("Arial", 10), fg="blue")
        self.session_info_label.pack(side="left", anchor="w", padx=(20, 0))  # 20px left padding for spacing
        self.session_info_label.pack_forget()  # Hide it initially

        scheduler_frame = tk.Frame(self.tab_main)
        scheduler_frame.pack(anchor="w", padx=10, pady=(10, 2), fill="x")

        # Configure columns to expand equally
        for i in range(5):
            scheduler_frame.grid_columnconfigure(i, weight=1)

        self.start_button = tk.Button(scheduler_frame, text="Start Scheduler", command=self.start_scheduler, state=tk.DISABLED, width=16)
        self.start_button.grid(row=0, column=0, padx=2, sticky="sew")
        
        self.stop_button = tk.Button(scheduler_frame, text="Stop Scheduler", command=self.stop_scheduler, state=tk.DISABLED, width=16)
        self.stop_button.grid(row=0, column=1, padx=2, sticky="sew")

        self.unlock_button = tk.Button(scheduler_frame, text="Unset Host", command=self.unset_lock_device, state=tk.DISABLED, width=16)
        self.unlock_button.grid(row=0, column=2, padx=2, sticky="sew")

        self.calibrate_button = tk.Button(scheduler_frame, text="Calibrate", command=self.start_calibration, state=tk.DISABLED, width=16)
        self.calibrate_button.grid(row=0, column=3, padx=2, sticky="sew")

        self.polar_button = tk.Button(scheduler_frame, text="Polar Position", command=self.start_polar_position, state=tk.DISABLED, width=16)
        self.polar_button.grid(row=0, column=4, padx=2, sticky="sew")

        self.eq_button = tk.Button(scheduler_frame, text="EQ Solving", command=self.start_eq_solving, state=tk.DISABLED, width=16)
        self.eq_button.grid(row=0, column=5, padx=2, sticky="sew")

        # Log text area with vertical scrollbar
        emoji_font = ("Segoe UI Emoji", 10)
        log_frame = tk.Frame(self.tab_main)
        log_frame.pack(padx=10, pady=(10, 10), fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=15, font=emoji_font)
        log_scrollbar = tk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Astro Sessions file counts summary (one line, colored, correct count) ---
        # Use colors from overview_session.py
        folder_colors = {
            'ToDo': 'blue',
            'Current': 'purple',
            'Done': 'green',
            'Error': 'red',
            'Results': 'gray',
        }
        from astro_dwarf_scheduler import LIST_ASTRO_DIR
        sessions_dir = LIST_ASTRO_DIR['SESSIONS_DIR']
        # Place file counts and clear log button in a horizontal frame just below the output window
        bottom_frame = tk.Frame(self.tab_main)
        bottom_frame.pack(fill="x", padx=10, pady=(0,10))
        # File counts (left)
        summary_frame = tk.Frame(bottom_frame)
        summary_frame.pack(side="left", anchor="w")
        tk.Label(summary_frame, text="Astro Sessions", font=("Arial", 10)).pack(side="left")
        self.session_count_labels = {}
        for folder, color in folder_colors.items():
            folder_path = os.path.join(sessions_dir, folder)
            try:
                count = len([
                    f for f in os.listdir(folder_path)
                    if os.path.isfile(os.path.join(folder_path, f)) and not f.startswith('.')
                ])
            except Exception:
                count = 0
            lbl = tk.Label(summary_frame, text=f" {folder}: {count}", fg=color, font=("Arial", 10))
            lbl.pack(side="left")
            self.session_count_labels[folder] = lbl

        # Clear Log button (right)
        clear_log_btn = tk.Button(bottom_frame, text="Clear Log", command=self.clear_log_output)
        clear_log_btn.pack(side="right", padx=0)

        # Skip Time Checks checkbox (right, next to clear log)
        self.skip_time_checks_var = tk.BooleanVar(value=self.skip_time_checks)
        def on_skip_time_checks_changed():
            self.skip_time_checks = self.skip_time_checks_var.get()
        skip_time_checks_cb = tk.Checkbutton(bottom_frame, text="Skip Time Checks", variable=self.skip_time_checks_var, command=on_skip_time_checks_changed)
        skip_time_checks_cb.pack(side="right", padx=10)

        # Add a method to update the counts (can be called after file changes)
        def update_session_counts():
            for folder, color in folder_colors.items():
                folder_path = os.path.join(sessions_dir, folder)
                try:
                    count = len([
                        f for f in os.listdir(folder_path)
                        if os.path.isfile(os.path.join(folder_path, f)) and not f.startswith('.')
                    ])
                except Exception:
                    count = 0
                self.session_count_labels[folder].config(text=f" {folder}: {count}")
        self.update_session_counts = update_session_counts

        # --- Periodically update session counts every 10 seconds ---
        def periodic_update_counts():
            self.update_session_counts()
            self.after(10000, periodic_update_counts)
        periodic_update_counts()

        # Periodically update session information
        self.update_session_info()

    def clear_log_output(self):
        if self.log_text is not None:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state=tk.NORMAL)
        # Update file counts in case log clearing is related to session changes
        if hasattr(self, 'update_session_counts'):
            self.update_session_counts()

    def start_bluetooth(self):
        self.disable_controls()
        self.log("Starting Bluetooth connection in a separate thread...")
        # Only start if not already running
        if not hasattr(self, 'bluetooth_thread') or not self.bluetooth_thread.is_alive():
            self.bluetooth_thread = threading.Thread(target=self.bluetooth_connect_thread, daemon=True)
            self.bluetooth_thread.start()

    def bluetooth_connect_thread(self):
        try:
            self.bluetooth_connected = False
            self.result = start_connection(False, self.use_web.get())
            if self.result:
                self.after(0, lambda: self.log("Bluetooth connected successfully."))
                self.bluetooth_connected = True
                # Enable the start scheduler button
                self.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            else:
                self.after(0, lambda: self.log("Bluetooth connection failed."))
        except Exception as e:
            self.after(0, lambda: self.log(f"Bluetooth connection failed: {e}"))

      #  self.after(0, self.start_scheduler)

    def skip_bluetooth(self):
        self.log("Bluetooth connection skipped.")
        # Enable the start scheduler button
        self.bluetooth_connected = False
        self.start_button.config(state=tk.NORMAL)

    def start_scheduler(self):
        self.disable_controls()
        if not self.scheduler_running:
            self.log("Astro_Dwarf_Scheduler is starting...")
            self.scheduler_running = True
            self.scheduler_stop_event.clear()
            self.start_logHandler()
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.unlock_button.config(state=tk.NORMAL)
            self.eq_button.config(state=tk.NORMAL)
            self.polar_button.config(state=tk.NORMAL)
            self.calibrate_button.config(state=tk.NORMAL)
            self.scheduler_start_time = datetime.now()  # Track when the scheduler starts
            # Only start if not already running
            if not hasattr(self, 'scheduler_thread') or not self.scheduler_thread.is_alive():
                self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
                self.scheduler_thread.start()
            self.update_session_info()  # Start updating session info
        # Update file counts when scheduler starts
        if hasattr(self, 'update_session_counts'):
            self.update_session_counts()

    def stop_scheduler(self):
        self.stop_logHandler()  # Stop the logging handler
        if self.scheduler_running:
            self.scheduler_running = False
            self.scheduler_stop_event.set()
            self.log("Scheduler is waiting for the process to stop.")

            # Update UI immediately
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.DISABLED)
            self.unlock_button.config(state=tk.DISABLED)
            self.eq_button.config(state=tk.DISABLED)
            self.polar_button.config(state=tk.DISABLED)
            self.calibrate_button.config(state=tk.DISABLED)

            # Wait for thread to finish with timeout
            self.verifyCountdown(10)  # Reduced timeout
        else:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.unlock_button.config(state=tk.DISABLED)
            self.eq_button.config(state=tk.DISABLED)
            self.polar_button.config(state=tk.DISABLED)
            self.calibrate_button.config(state=tk.DISABLED) 
            self.log("Scheduler is stopping...")
            self.enable_controls()

        # Hide session info when scheduler stops
        self.session_info_label.pack_forget()

        # Update file counts when scheduler stops
        if hasattr(self, 'update_session_counts'):
            self.update_session_counts()

    def unset_lock_device(self):
        # Only start if not already running
        if not hasattr(self, 'unset_thread') or not self.unset_thread.is_alive():
            self.unset_thread = threading.Thread(target=self.run_unset_lock_device, daemon=True)
            self.unset_thread.start()

    def start_eq_solving(self):
        # Only start if not already running
        if not hasattr(self, 'eq_thread') or not self.eq_thread.is_alive():
            self.eq_thread = threading.Thread(target=self.run_start_eq_solving, daemon=True)
            self.eq_thread.start()

    def start_polar_position(self):
        # Only start if not already running
        if not hasattr(self, 'polar_thread') or not self.polar_thread.is_alive():
            self.polar_thread = threading.Thread(target=self.run_start_polar_position, daemon=True)
            self.polar_thread.start()

    def start_calibration(self):
        # Only start if not already running
        if not hasattr(self, 'cal_thread') or not self.cal_thread.is_alive():
            self.cal_thread = threading.Thread(target=self.run_start_calibration, daemon=True)
            self.cal_thread.start()

    def verifyCountdown(self, wait):
        '''
        verifyCountdown that checks scheduler status and waits for stop or timeout
        '''
        if self.scheduler_stopped or not self.scheduler_running:
            self.log("Scheduler is stopping...")
            self.enable_controls()
        elif wait > 0:
            # Schedule the verifyCountdown to run again after 1 second
            self.after(1000, self.verifyCountdown, wait - 1)
        else:
            self.log("Timeout reached, forcing disconnect...")
            try:
                perform_disconnect()
            except:
                pass
            self.scheduler_stopped = True
            self.enable_controls()

    def run_scheduler(self):
        try:
            self.scheduler_stopped = False
            self.session_running = False  # Track if a session is running
            attempt = 0
            result = False
            while not result and attempt < 3 and self.scheduler_running and not self.scheduler_stop_event.is_set():
                attempt += 1
                result = start_STA_connection(not self.bluetooth_connected)

            if result:
                self.log("Connected to the Dwarf")

            while result and self.scheduler_running and not self.scheduler_stop_event.is_set():
                try:

                    # Execute commands and check if any sessions were processed
                    self.session_running = True  # Mark session as running

                    session_start = datetime.now()
                    sessions_processed = check_and_execute_commands(self, stop_event=self.scheduler_stop_event, skip_time_checks=self.skip_time_checks)
                    session_end = datetime.now()

                    if sessions_processed:
                        # Add this session's runtime to the total
                        session_runtime = (session_end - session_start).total_seconds()
                        self.add_to_total_runtime(session_runtime)
                        self.log("Session completed, checking for more sessions...")
                        # Brief pause between sessions
                        time.sleep(1)
                        continue

                    self.reset_total_runtime()

                    # If no sessions were processed and scheduler is still running, continue checking
                    if not sessions_processed and self.scheduler_running and not self.scheduler_stop_event.is_set():
                        self.session_running = False  # No session is running
                        # Instead of sleeping for 10 seconds, check every 0.1s if stopped
                        total_sleep = 0
                        while total_sleep < 10 and self.scheduler_running and not self.scheduler_stop_event.is_set():
                            time.sleep(0.1)
                            total_sleep += 0.1

                except Exception as e:
                    self.after(0, lambda e=e: self.log(f"Error in scheduler loop: {e}", level="error"))
                    break

        except KeyboardInterrupt:
            self.log("Operation interrupted by the user.")
        except Exception as e:
            self.after(0, lambda e=e: self.log(f"Scheduler error: {e}", level="error"))
        finally:
            self.session_running = False  # Ensure session state is reset
            # Ensure proper cleanup
            try:
                perform_disconnect()
                self.after(0, lambda: self.log("Disconnected from the Dwarf."))
            except Exception as e:
                self.after(0, lambda: self.log(f"Error during disconnect: {e}", level="error"))

            # Update UI state on main thread
            def update_ui_after_scheduler():
                self.scheduler_running = False
                self.scheduler_stopped = True
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                self.unlock_button.config(state=tk.DISABLED)
                self.eq_button.config(state=tk.DISABLED)
                self.polar_button.config(state=tk.DISABLED)
                self.calibrate_button.config(state=tk.DISABLED)
                self.enable_controls()
                if hasattr(self, 'update_session_counts'):
                    self.update_session_counts()
                self.log("Scheduler stopped - no more sessions to process.", level="success")
                self.stop_logHandler()  # Stop the logging handler here as well

            self.after(0, update_ui_after_scheduler)

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
                def update_unlock_button():
                    if self.unset_lock_device_mode:
                        self.unlock_button.config(text="Set Device as Host")
                    else:
                        self.unlock_button.config(text="Unset Device as Host")
                    self.unset_lock_device_mode = not self.unset_lock_device_mode
                    self.unlock_button.update()
                self.after(0, update_unlock_button)
        except Exception as e:
            self.after(0, lambda e=e: self.log(f"Error in unset_lock_device: {e}", level="error"))

    def run_start_eq_solving(self):
        try:
            attempt = 0
            result = False
            self.after(0, lambda: self.log("Starting EQ Solving process..."))
            while not result and attempt < 3:
                attempt += 1
                result = start_polar_align()
                if not result:
                    time.sleep(10)  # Sleep for 10 seconds between checks
        except Exception as e:
            self.after(0, lambda e=e: self.log(f"Error in EQ Solving: {e}", level="error"))

    def run_start_polar_position(self):
        try:
            dwarf_id = "2"
            data_config = dwarf_python_api.get_config_data.get_config_data()
            if data_config["dwarf_id"]:
                dwarf_id = data_config['dwarf_id']
            dwarf_id_int = int(dwarf_id) + 1 if dwarf_id is not None else 0

            attempt = 0
            result = False
            self.after(0, lambda: self.log("Starting Polar Align positionning..."))
            while not result and attempt < 1:
                attempt += 1
                # Rotation Motor Resetting
                result = motor_action(5)
                if result:
                     # Pitch Motor Resetting
                     result = motor_action(6)
                if result and dwarf_id_int == 3:
                     # Rotation Motor positioning D3
                     result = motor_action(9)
                elif result:
                     # Rotation Motor positioning
                     result = motor_action(2)
                if result and dwarf_id_int == 3:
                     # Pitch Motor positioning D3
                     result = motor_action(7)
                elif result:
                     # Pitch Motor positioning
                     result = motor_action(3)

                if result:
                     self.after(0, lambda: self.log("Success Polar Align positionning"))
                if not result:
                    time.sleep(10)  # Sleep for 10 seconds between checks
        except Exception as e:
            self.after(0, lambda e=e: self.log(f"Error in Polar Align positionning: {e}", level="error"))

    def run_start_calibration(self):
        try:

            # Session initialization
            self.after(0, lambda: self.log("Starting Calibration process..."))
            continue_action = perform_time()
            verify_action(continue_action, "step_0")

            # Go Live
            continue_action = perform_GoLive()
            verify_action(continue_action, "step_1a")

            wait_after = 5
            wait_before = 5

            continue_action = perform_stop_goto()
            verify_action(continue_action, "step_6")
            self.after(0, lambda: self.log(f"Waiting for {wait_before} seconds"))
            time.sleep(wait_before)

            self.after(0, lambda: self.log("Starting Calibration"))
            self.after(0, lambda: self.log(f"Waiting for {wait_before} seconds"))
            time.sleep(wait_before)
            continue_action = perform_calibration()
            verify_action(continue_action, "step_7")
            self.after(0, lambda: self.log(f"Waiting for {wait_after} seconds"))
            time.sleep(wait_after)
            continue_action = perform_stop_goto()
            self.after(0, lambda: self.log(f"Waiting for {wait_after} seconds"))
            time.sleep(wait_after)
            continue_action = perform_calibration()

        except Exception as e:
            self.after(0, lambda e=e: self.log(f"Error in Calibration: {e}", level="error"))

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
        if hasattr(self, 'text_handler') and self.text_handler in self.logger.handlers:
            self.logger.removeHandler(self.text_handler)  # Remove the TextHandler
            self.text_handler = None  # Clear the reference to avoid reuse

    def log(self, message, level="info"):
        # Add color and emoji for direct log calls
        if level == "error":
            color = 'red'
            emoji = '✗ '
        elif level == "warning":
            color = 'orange'
            emoji = '⚠ '
        elif level == "info":
            color = 'blue'
            emoji = '◉ '
        elif level == "success":
            color = 'green'
            emoji = '✓ '
        else:
            color = 'black'
            emoji = '⇒ '
            
        if self.log_text is not None:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, emoji + message + "\n", color)
            self.log_text.tag_config(color, foreground=color)
            self.log_text.see(tk.END)

    def update_session_info(self):
        """
        Update the session information label with the next session's start time,
        the runtime of the current session, or a countdown to the next session.
        """
        if self.scheduler_running:
            # Show the session info label
            self.session_info_label.pack(side="left", anchor="w", padx=(20, 0))

            # Check for the next session in the ToDo directory
            todo_dir_var = "CURRENT_DIR" if getattr(self, 'session_running', False) else "TODO_DIR"
            todo_dir = LIST_ASTRO_DIR[todo_dir_var]

            if os.path.exists(todo_dir):
                todo_files = get_json_files_sorted(todo_dir)
                if todo_files:
                    next_session_file = todo_files[0]
                    next_session_path = os.path.join(todo_dir, next_session_file)
                    try:
                        with open(next_session_path, 'r') as f:
                            session_data = json.loads(f.read())

                        # Always check for up next countdown if scheduler is running
                        # Track the last session file to reset timer if a new file loads
                        if not hasattr(self, 'last_session_path') or self.last_session_path != next_session_path:
                            self.session_start_time = datetime.now()
                            self.last_session_path = next_session_path

                        if not hasattr(self, 'session_start_time'):
                            self.session_start_time = datetime.now()

                        # Get scheduled date/time from session file
                        id_command = session_data.get('command', {}).get('id_command', {})
                        goto_manual = session_data.get('command', {}).get('goto_manual', {})
                        scheduled_date = id_command.get('date', None)
                        scheduled_time = id_command.get('time', None)
                        scheduled_target = goto_manual.get('target', 'Unknown')
                        show_countdown = False
                        countdown_str = ''

                        if scheduled_date and scheduled_time:
                            try:
                                scheduled_dt = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M:%S")
                                now = datetime.now()
                                if scheduled_dt > now:
                                    show_countdown = True
                                    countdown = scheduled_dt - now
                                    countdown_str = str(countdown).split('.')[0]
                            except Exception:
                                pass

                        if show_countdown:
                            self.session_info_label.config(
                                text=f"Up next: {scheduled_target} at {scheduled_date} {scheduled_time} (starts in {countdown_str})",
                                fg="#0078d7"
                            )
                        else:
                            estimated_runtime = self.calculate_end_time(session_data.get('command', {}))
                            # Ensure self.session_start_time is a datetime object
                            if not isinstance(self.session_start_time, datetime):
                                self.session_start_time = datetime.now()
                            this_session_runtime = datetime.now() - self.session_start_time
                            this_session_runtime_str = str(this_session_runtime).split('.')[0]  # Format as HH:MM:SS
                            # Format total runtime (add current session's runtime live)
                            if not hasattr(self, 'total_session_runtime'):
                                self.total_session_runtime = 0
                            live_total_seconds = int(self.total_session_runtime + this_session_runtime.total_seconds())
                            total_runtime_td = timedelta(seconds=live_total_seconds)
                            total_runtime_str = str(total_runtime_td).split('.')[0]
                            self.session_info_label.config(text=f"Session runtime: {this_session_runtime_str} / {estimated_runtime} - Total runtime: {total_runtime_str}", fg="#26447A")

                    except Exception as e:
                       self.session_info_label.config(text=f"Error reading next session. {e}\n{traceback.format_exc()}")
                else:
                    self.session_info_label.config(text="No sessions scheduled - Create sessions in 'Create Session' tab", fg="purple")
            else:
                self.session_info_label.config(text="No session directory found - Check configuration",fg="red")
        else:
            # Show a helpful placeholder when scheduler is not running
            self.session_info_label.pack(side="left", anchor="w", padx=(20, 0))
            
            # Check if there are any sessions in ToDo to provide useful information
            todo_dir = LIST_ASTRO_DIR["TODO_DIR"]
            if os.path.exists(todo_dir):
                todo_files = get_json_files_sorted(todo_dir)
                if todo_files:
                    self.session_info_label.config(
                        text=f"Ready to start - {len(todo_files)} session(s) waiting. Click 'Start Scheduler' to begin.",
                        fg="green"
                    )
                else:
                    self.session_info_label.config(
                        text="No sessions scheduled - Create sessions in 'Create Session' tab to get started.",
                        fg="purple"
                    )
            else:
                self.session_info_label.config(
                    text="Session directory not found - Check your configuration settings.",
                    fg="red"
                )

        # Schedule the next update
        self.after(1000, self.update_session_info)

# Main application
if __name__ == "__main__":
    app = AstroDwarfSchedulerApp()

    def handler(sig, frame):
        print("\nExiting Astro Dwarf Scheduler.")
        app.quit()

    signal.signal(signal.SIGINT, handler)
    try:
        app.mainloop()
    except KeyboardInterrupt:
        # This is a fallback, but the handler should catch Ctrl+C
        print("\nExiting Astro Dwarf Scheduler.")
