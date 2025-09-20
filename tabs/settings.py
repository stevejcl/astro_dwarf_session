import configparser
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser
import pytz

from geopy.geocoders import Nominatim
from geopy.geocoders import Photon
from timezonefinder import TimezoneFinder
from geopy.exc import GeocoderInsufficientPrivileges
from astro_dwarf_scheduler import BASE_DIR

# Import for exposure and gain dropdown values
from dwarf_python_api.lib.data_utils import allowed_exposures, allowed_gains, allowed_exposuresD3, allowed_gainsD3
from dwarf_python_api.lib.data_wide_utils import allowed_wide_exposuresD3, allowed_wide_gainsD3

import sys
import os

# Import DWARF_IP from config.py
DWARF_IP_CURRENT = ""
try:
    from config import DWARF_IP
    DWARF_IP_CURRENT = DWARF_IP
except ImportError:
    DWARF_IP = "192.168.88.1"  # Default fallback value

CONFIG_INI_FILE = 'config.ini'

def update_exposure_gain_options(device_type, exposure_dropdown, gain_dropdown):
    """Update the exposure and gain options based on the selected device type."""    
    # Helper function to get available names
    def get_available_names(instance):
        return [entry["name"] for entry in instance.values]
    
    if device_type == "Dwarf II":
        available_exposure_names = get_available_names(allowed_exposures)
        available_gain_names = get_available_names(allowed_gains)
        exposure_dropdown['values'] = list(reversed(available_exposure_names))
        gain_dropdown['values'] = available_gain_names
    elif device_type == "Dwarf 3 Tele Lens":
        available_exposure_namesD3 = get_available_names(allowed_exposuresD3)
        available_gain_namesD3 = get_available_names(allowed_gainsD3)
        exposure_dropdown['values'] = list(reversed(available_exposure_namesD3))
        gain_dropdown['values'] = available_gain_namesD3
    elif device_type == "Dwarf 3 Wide Lens":
        available_wide_exposure_namesD3 = get_available_names(allowed_wide_exposuresD3)
        available_wide_gains_namesD3 = get_available_names(allowed_wide_gainsD3)
        exposure_dropdown['values'] = list(reversed(available_wide_exposure_namesD3))
        gain_dropdown['values'] = available_wide_gains_namesD3
    else:
        exposure_dropdown['values'] = []
        gain_dropdown['values'] = []

def get_config_ini_file():
    """Get the appropriate INI file for the current configuration"""
    try:
        from astro_dwarf_scheduler import get_current_config_ini_file
        return get_current_config_ini_file()
    except ImportError:
        return CONFIG_INI_FILE

def get_lat_long_and_timezone(address, agent = 1):
    try:
        # Initialize the geolocator with Nominatim
        if agent == 1:
            geolocator = Nominatim(user_agent="geoapiAstroSession")
        else: 
            geolocator = Photon(user_agent="geoapiAstroSession")

        #Get location based on the address
        location = geolocator.geocode(address)
        if not location:
            return None, None, None
        latitude = getattr(location, 'latitude', None)
        longitude = getattr(location, 'longitude', None)
        if latitude is None or longitude is None:
            return None, None, None
        # Get the timezone using TimezoneFinder
        tf = TimezoneFinder()
        timezone_str = tf.timezone_at(lat=latitude, lng=longitude)
        return latitude, longitude, timezone_str

    except GeocoderInsufficientPrivileges as e:
        print(f"Error: {e} - You do not have permission to access this resource.")
        # Attempt to switch agent and retry
        if agent == 1:
            print("Switching to Photon geocoder for the next attempt.")
            return get_lat_long_and_timezone(address, agent=2)  # Retry with the second agent
        else:
            messagebox.showinfo("Error", "Can't found your location data!")
            return None, None, None
    except Exception as e:
        print(f"Error: {e}")
        # Attempt to switch agent and retry
        if agent == 1:
            print("Switching to Photon geocoder for the next attempt.")
            return get_lat_long_and_timezone(address, agent=2)  # Retry with the second agent
        else:
            messagebox.showinfo("Error", "Can't found your location data!")
            return None, None, None

def find_location(settings_vars):
    try:
        latitude, longitude, timezone_str = get_lat_long_and_timezone(settings_vars["address"].get())

        if latitude and longitude and timezone_str:
            settings_vars["latitude"].set(latitude)
            settings_vars["longitude"].set(longitude)
            settings_vars["timezone"].set(timezone_str)
        else:
            print("Location or timezone could not be determined.")
            messagebox.showinfo("Error", "Can't found your location data!")
    except Exception as e:
        print(f"Error: {e}")
        messagebox.showinfo("Error", "Can't found your location data!")

def open_link(url):
    webbrowser.open_new(url)

# Load and save configuration settings from config.ini
def load_config():
    config = configparser.ConfigParser()
    config_ini_path = get_config_ini_file()
    
    config.read(config_ini_path)
    config_data = config['CONFIG'] if 'CONFIG' in config else {}
    # If DWARF_IP is not in config.ini, use the value from config.py
    if 'dwarf_ip' not in config_data:
        config_data['dwarf_ip'] = DWARF_IP
    return config_data

def save_config(config_data):
    # Read the existing config file to preserve all sections
    config = configparser.ConfigParser()
    config_ini_path = get_config_ini_file()
    config.read(config_ini_path)
    # Update only the CONFIG section with new values
    if 'CONFIG' not in config:
        config.add_section('CONFIG')
    for key, value in config_data.items():
        config.set('CONFIG', key, value)
    # Write back to file, preserving all sections
    with open(config_ini_path, 'w') as configfile:
        config.write(configfile)
        
    # Update config.py with the new DWARF_IP value if it changed and not set in config.py
    if 'dwarf_ip' in config_data:   
        update_config_py_dwarf_ip(config_data['dwarf_ip'])
    # Update DWARF_ID in config.py based on camera_type (was device_type) selection
    if 'camera_type' in config_data:
        update_config_py_dwarf_id(config_data['device_type'])

def update_config_py_dwarf_id(device_type):
    """Update the DWARF_ID value in config.py based on device_type"""
    try:
        import os
        config_py_path = 'config.py'
        # Determine DWARF_ID value (config.py values are offset by -1)
        if device_type == 'Dwarf II':
            dwarf_id_val = 1  # Config value for Dwarf II (actual device ID is 2)
        else:
            dwarf_id_val = 2  # Config value for Dwarf 3 (actual device ID is 3)
        if os.path.exists(config_py_path):
            # Read the current config.py content
            with open(config_py_path, 'r') as f:
                lines = f.readlines()
            # Find and update the DWARF_ID line
            updated = False
            for i, line in enumerate(lines):
                if line.strip().startswith('DWARF_ID'):
                    lines[i] = f'DWARF_ID = "{dwarf_id_val}"\n'
                    updated = True
                    break
            # If DWARF_ID line wasn't found, add it
            if not updated:
                lines.append(f'DWARF_ID = "{dwarf_id_val}"\n')
            # Write the updated content back to config.py
            with open(config_py_path, 'w') as f:
                f.writelines(lines)
        else:
            print("config.py not found, cannot update DWARF_ID")
    except Exception as e:
        print(f"Error updating DWARF_ID in config.py: {e}")

def update_config_py_dwarf_ip(new_ip):
    """Update the DWARF_IP value in config.py"""
    try:
        import os
        config_py_path = 'config.py'
        if os.path.exists(config_py_path):
            # Read the current config.py content
            with open(config_py_path, 'r') as f:
                lines = f.readlines()
            
            # Find and update the DWARF_IP line
            updated = False
            for i, line in enumerate(lines):
                if line.strip().startswith('DWARF_IP'):
                    lines[i] = f'DWARF_IP = "{new_ip}"\n'
                    updated = True
                    break
            
            # If DWARF_IP line wasn't found, add it
            if not updated:
                lines.append(f'DWARF_IP = "{new_ip}"\n')
            
            # Write the updated content back to config.py
            with open(config_py_path, 'w') as f:
                f.writelines(lines)
                
        else:
            print("config.py not found, cannot update DWARF_IP")
            
    except Exception as e:
        print(f"Error updating config.py: {e}")

# Create the settings tab
def create_settings_tab(tab_settings, settings_vars, camera_type_change_callback=None, update_create_session_callback=None):

    config = load_config()
    # --- Modern scrollable frame setup ---
    container = ttk.Frame(tab_settings)
    container.grid(row=0, column=0, sticky='nsew')
    tab_settings.grid_rowconfigure(0, weight=1)
    tab_settings.grid_columnconfigure(0, weight=1)

    canvas = tk.Canvas(container, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    def _on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
        # Make the scrollable_frame width always match the canvas width
        canvas_width = event.width
        canvas.itemconfig("frame", width=canvas_width)

    scrollable_frame.bind(
        "<Configure>", _on_frame_configure
    )
    # Add a window with a tag so we can resize it
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", tags="frame")
    canvas.configure(yscrollcommand=scrollbar.set)

    def _on_canvas_configure(event):
        # Set the inner frame's width to the canvas width
        canvas.itemconfig("frame", width=event.width)

    canvas.bind('<Configure>', _on_canvas_configure)

    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)

    settings_fields = [
        ("Your Address", "address"),
        ("Help", "Find longitude and lattitude in Google Map by CTRL + Right Click"),
        ("Longitude", "longitude"),
        ("Latitude", "latitude"),
        ("Timezone", "timezone"),
        ("DWARF IP", "dwarf_ip"),
        ("BLE PSD", "ble_psd"),
        ("BLE STA SSID", "ble_sta_ssid"),
        ("BLE STA Password", "ble_sta_pwd"),
        ("Help", "Use to Connect to Stellarium, let them blank if you are using default config"),
        ("Stellarium IP", "stellarium_ip"),
        ("Stellarium Port", "stellarium_port"),
        ("Help", "The following values are the default values use in the Create Session Tabs"),
        ("IR Cut", "ircut"),
        ("Binning", "binning"),
        ("Exposure", "exposure"),
        ("Gain", "gain"),
        ("Count", "count")
    ]

    camera_type_options = [
        ("Dwarf II", "Tele Camera"),
        ("Dwarf 3 Tele Lens", "Tele Camera"),
        ("Dwarf 3 Wide Lens", "Wide-Angle Camera")
    ]
    camera_type_display = [opt[0] for opt in camera_type_options]
    camera_type_value_map = {opt[0]: opt[1] for opt in camera_type_options}
    camera_type_reverse_map = {opt[1]: opt[0] for opt in camera_type_options}
    # Find the index of IR Cut row to insert Camera Type before it, ensuring Camera Type appears first to control IR Cut options
    ircut_row_index = next((i for i, (field, key) in enumerate(settings_fields) if key == "ircut"), None)
    # Insert Camera Type row before IR Cut for proper ordering of dependent dropdowns
    if ircut_row_index is not None:
        settings_fields.insert(ircut_row_index, ("Camera Type", "camera_type"))

    # Add location button at the top, running in background
    def find_location_in_background():
        def task():
            original_text = location_button.cget("text")
            try:
                location_button.config(state=tk.DISABLED, text="Finding...")
                find_location(settings_vars)
            finally:
                location_button.config(state=tk.NORMAL, text=original_text)
        import threading
        threading.Thread(target=task, daemon=True).start()

    location_button = tk.Button(scrollable_frame, text="Find your location data from your address or Enter them manually", command=find_location_in_background)
    location_button.grid(row=0, column=0, columnspan=2, pady=(15, 15), padx=10, sticky='ew')

    grid_row = 1
    # --- Dynamic IR Cut logic ---
    ircut_combo = None
    ircut_var = None
    
    def update_ircut_options(selected_camera_type):
        nonlocal ircut_combo, ircut_var
        update_ircut_dropdown(selected_camera_type, ircut_combo, ircut_var, settings_vars)
        
        # Also update exposure and gain dropdowns when device type changes
        if 'exposure_dropdown' in settings_vars and 'gain_dropdown' in settings_vars:
            update_exposure_gain_options(selected_camera_type, settings_vars['exposure_dropdown'], settings_vars['gain_dropdown'])

    for field, key in settings_fields:
        index = key.find("http")
        if not "Help" in field:
            label = tk.Label(scrollable_frame, width=15, text=field, anchor='e')
            extra_pady = 4
            if key == "gain":
                label.grid(row=grid_row, column=0, sticky='e', padx=(10,6), pady=(4, 9))
            else:
                label.grid(row=grid_row, column=0, sticky='e', padx=(10,6), pady=4)
            if key == "timezone":
                tz_list = pytz.all_timezones
                var = tk.StringVar(value=config.get(key, ''))
                combo = ttk.Combobox(scrollable_frame, textvariable=var, values=tz_list, state="readonly")
                settings_vars[key] = var
                combo.grid(row=grid_row, column=1, sticky='ew', padx=(0,14), pady=4)
                scrollable_frame.grid_columnconfigure(1, weight=1)
            elif key == "ircut":
                # IR Cut dropdown with dynamic options
                # Determine the correct device type from config
                device_type_val = config.get('device_type', '')
                if device_type_val in camera_type_display:
                    camera_type_display_val = device_type_val
                else:
                    # Fallback to camera_type mapping if device_type is not valid
                    camera_type_val = config.get('camera_type', 'Tele Camera')
                    camera_type_display_val = camera_type_reverse_map.get(camera_type_val, camera_type_display[0])
                
                # Set up IR Cut options based on device type
                display_options = ["D2: IRCut", "D2: IRPass"] if camera_type_display_val == "Dwarf II" else ["D3: VIS Filter", "D3: Astro Filter", "D3: DUAL Band"]
                value_map = {"D2: IRCut": 0, "D2: IRPass": 1, "D3: VIS Filter": 0, "D3: Astro Filter": 1, "D3: DUAL Band": 2}
                current_val = str(config.get(key, ''))
                initial_display = display_options[0]
                for disp in display_options:
                    if str(value_map[disp]) == current_val:
                        initial_display = disp
                        break
                ircut_var = tk.StringVar(value=initial_display)
                ircut_combo = ttk.Combobox(scrollable_frame, textvariable=ircut_var, values=display_options, state="readonly")
                settings_vars[key] = ircut_var
                settings_vars['ircut_dropdown'] = ircut_combo  # Store dropdown reference for enable/disable
                ircut_combo.grid(row=grid_row, column=1, sticky='ew', padx=(0,14), pady=4)
                scrollable_frame.grid_columnconfigure(1, weight=1)
                settings_vars['_ircut_value_map'] = {disp: value_map[disp] for disp in display_options}
            elif key == "binning":
                # Binning dropdown with example names and integer values
                binning_options = [
                    ("4k", 0),
                    ("2k", 1)
                ]
                binning_display_options = [opt for opt, val in binning_options]
                binning_value_map = {opt: val for opt, val in binning_options}
                current_val = str(config.get(key, ''))
                initial_display = binning_display_options[0]
                for disp, val in binning_value_map.items():
                    if str(val) == current_val:
                        initial_display = disp
                        break
                var = tk.StringVar(value=initial_display)
                combo = ttk.Combobox(scrollable_frame, textvariable=var, values=binning_display_options, state="readonly")
                settings_vars[key] = var
                settings_vars['binning_dropdown'] = combo  # Store dropdown reference for enable/disable
                combo.grid(row=grid_row, column=1, sticky='ew', padx=(0,14), pady=4)
                scrollable_frame.grid_columnconfigure(1, weight=1)
                if '_binning_value_map' not in settings_vars:
                    settings_vars['_binning_value_map'] = binning_value_map
            elif key == "camera_type":
                # Camera Type dropdown with name-value mapping
                # Prefer device_type from config.ini if present, else fallback to camera_type
                device_type_val = config.get('device_type', '')
                if device_type_val in camera_type_display:
                    initial_display = device_type_val
                else:
                    current_val = config.get(key, '')
                    initial_display = camera_type_reverse_map.get(current_val, camera_type_display[0])
                var = tk.StringVar(value=initial_display)
                combo = ttk.Combobox(scrollable_frame, textvariable=var, values=camera_type_display, state="readonly")
                settings_vars[key] = var
                combo.grid(row=grid_row, column=1, sticky='ew', padx=(0,14), pady=4)
                scrollable_frame.grid_columnconfigure(1, weight=1)
                if '_camera_type_value_map' not in settings_vars:
                    settings_vars['_camera_type_value_map'] = camera_type_value_map
                # Bind to update IR Cut options dynamically, using a closure to capture the correct var
                def make_camera_type_handler(bound_var):
                    def handler(event):
                        selected_device_type = bound_var.get()
                        update_ircut_options(selected_device_type)
                        
                        # Handle Dwarf 3 Wide Lens special case - disable ircut and binning
                        if selected_device_type == "Dwarf 3 Wide Lens":
                            # Disable ircut and binning dropdowns
                            if 'ircut_dropdown' in settings_vars:
                                settings_vars['ircut_dropdown'].config(state="disabled")
                                # Set ircut to first option
                                if 'ircut' in settings_vars and '_ircut_value_map' in settings_vars:
                                    # Get the first option from the current value map
                                    first_option = list(settings_vars['_ircut_value_map'].keys())[0]
                                    settings_vars['ircut'].set(first_option)
                            if 'binning_dropdown' in settings_vars:
                                settings_vars['binning_dropdown'].config(state="disabled")
                        else:
                            # Enable ircut and binning dropdowns for other device types
                            if 'ircut_dropdown' in settings_vars:
                                settings_vars['ircut_dropdown'].config(state="readonly")
                            if 'binning_dropdown' in settings_vars:
                                settings_vars['binning_dropdown'].config(state="readonly")
                        
                        # Reset exposure and gain to valid dropdown values for the selected device type
                        if 'exposure' in settings_vars and 'gain' in settings_vars:
                            # Helper function to get available names
                            def get_available_names(instance):
                                return [entry["name"] for entry in instance.values]
                                
                            # Get valid dropdown values for each device type
                            if selected_device_type == "Dwarf II":
                                available_exposure_names = get_available_names(allowed_exposures)
                                available_gain_names = get_available_names(allowed_gains)
                                # Set to a reasonable default that exists in the dropdown
                                default_exposure = "15" if "15" in available_exposure_names else available_exposure_names[0] if available_exposure_names else "15"
                                default_gain = "100" if "100" in available_gain_names else available_gain_names[0] if available_gain_names else "100"
                            elif selected_device_type == "Dwarf 3 Tele Lens":
                                available_exposure_namesD3 = get_available_names(allowed_exposuresD3)
                                available_gain_namesD3 = get_available_names(allowed_gainsD3)
                                # Set to a reasonable default that exists in the dropdown
                                default_exposure = "30" if "30" in available_exposure_namesD3 else available_exposure_namesD3[0] if available_exposure_namesD3 else "30"
                                default_gain = "60" if "60" in available_gain_namesD3 else available_gain_namesD3[0] if available_gain_namesD3 else "60"
                            elif selected_device_type == "Dwarf 3 Wide Lens":
                                available_wide_exposure_namesD3 = get_available_names(allowed_wide_exposuresD3)
                                available_wide_gains_namesD3 = get_available_names(allowed_wide_gainsD3)
                                # Set to a reasonable default that exists in the dropdown
                                default_exposure = "0.4" if "0.4" in available_wide_exposure_namesD3 else available_wide_exposure_namesD3[0] if available_wide_exposure_namesD3 else "0.4"
                                default_gain = "100" if "100" in available_wide_gains_namesD3 else available_wide_gains_namesD3[0] if available_wide_gains_namesD3 else "100"
                            else:
                                # Fallback to Dwarf II values
                                available_exposure_names = get_available_names(allowed_exposures)
                                available_gain_names = get_available_names(allowed_gains)
                                default_exposure = "15" if "15" in available_exposure_names else available_exposure_names[0] if available_exposure_names else "15"
                                default_gain = "100" if "100" in available_gain_names else available_gain_names[0] if available_gain_names else "100"

                            # Update the exposure and gain fields
                            settings_vars['exposure'].set(default_exposure)
                            settings_vars['gain'].set(default_gain)
                            
                            # Also update the dropdown values for the exposure and gain fields
                            if 'exposure_dropdown' in settings_vars and 'gain_dropdown' in settings_vars:
                                update_exposure_gain_options(selected_device_type, settings_vars['exposure_dropdown'], settings_vars['gain_dropdown'])
                        
                        # Call the callback if provided to update create session tab
                        if camera_type_change_callback:
                            camera_type_change_callback(selected_device_type)
                    return handler
                combo.bind('<<ComboboxSelected>>', make_camera_type_handler(var))
            elif key == "exposure":
                # Exposure dropdown with device-specific options
                # Determine the device type from config
                device_type_val = config.get('device_type', '')
                if device_type_val not in camera_type_display:
                    # Fallback to camera_type mapping if device_type is not valid
                    camera_type_val = config.get('camera_type', 'Tele Camera')
                    device_type_val = camera_type_reverse_map.get(camera_type_val, camera_type_display[0])
                
                # Create exposure dropdown
                current_val = config.get(key, '30')  # Default to "30"
                var = tk.StringVar(value=current_val)
                combo = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly")
                settings_vars[key] = var
                settings_vars['exposure_dropdown'] = combo  # Store dropdown reference
                combo.grid(row=grid_row, column=1, sticky='ew', padx=(0,14), pady=4)
                scrollable_frame.grid_columnconfigure(1, weight=1)
            elif key == "gain":
                # Gain dropdown with device-specific options  
                # Determine the device type from config
                device_type_val = config.get('device_type', '')
                if device_type_val not in camera_type_display:
                    # Fallback to camera_type mapping if device_type is not valid
                    camera_type_val = config.get('camera_type', 'Tele Camera')
                    device_type_val = camera_type_reverse_map.get(camera_type_val, camera_type_display[0])
                
                # Create gain dropdown
                current_val = config.get(key, '22')  # Default to "22"
                var = tk.StringVar(value=current_val)
                combo = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly")
                settings_vars[key] = var
                settings_vars['gain_dropdown'] = combo  # Store dropdown reference
                combo.grid(row=grid_row, column=1, sticky='ew', padx=(0,14), pady=4)
                scrollable_frame.grid_columnconfigure(1, weight=1)
            else:
                var = tk.StringVar(value=config.get(key, ''))
                entry = tk.Entry(scrollable_frame, textvariable=var)
                settings_vars[key] = var
                entry.grid(row=grid_row, column=1, sticky='ew', padx=(0,14), pady=4)
                scrollable_frame.grid_columnconfigure(1, weight=1)
        elif index != -1:
            url = key[index:].strip()
            link_label = tk.Label(scrollable_frame, text=key[:index], fg="blue", cursor="hand2", anchor='w')
            # Align the link label to the data entry column
            link_label.grid(row=grid_row, column=1, sticky='w', padx=(0,14), pady=4)
            link_label.config(font=("Arial", 12, "underline"))
            link_label.bind("<Button-1>", lambda e, url=url: open_link(url))
        else:
            help_Label = tk.Label(scrollable_frame, width=60, text=key, anchor='w', fg="#555")
            # Align the help label to the data entry column
            help_Label.grid(row=grid_row, column=1, sticky='w', padx=(0,14), pady=4)
        grid_row += 1

    # Populate exposure and gain dropdowns with device-specific values
    if 'exposure_dropdown' in settings_vars and 'gain_dropdown' in settings_vars:
        # Get current device type
        device_type_val = config.get('device_type', '')
        if device_type_val not in camera_type_display:
            # Fallback to camera_type mapping if device_type is not valid
            camera_type_val = config.get('camera_type', 'Tele Camera')
            device_type_val = camera_type_reverse_map.get(camera_type_val, camera_type_display[0])
        
        # Update dropdown values
        update_exposure_gain_options(device_type_val, settings_vars['exposure_dropdown'], settings_vars['gain_dropdown'])

    # Handle initial state for Dwarf 3 Wide Lens - disable ircut and binning if selected
    initial_device_type = config.get('device_type', '')
    if initial_device_type not in camera_type_display:
        # Fallback to camera_type mapping if device_type is not valid
        camera_type_val = config.get('camera_type', 'Tele Camera')
        initial_device_type = camera_type_reverse_map.get(camera_type_val, camera_type_display[0])
    
    if initial_device_type == "Dwarf 3 Wide Lens":
        # Disable ircut and binning dropdowns and set ircut to first option
        if 'ircut_dropdown' in settings_vars:
            settings_vars['ircut_dropdown'].config(state="disabled")
            if 'ircut' in settings_vars and '_ircut_value_map' in settings_vars:
                first_option = list(settings_vars['_ircut_value_map'].keys())[0]
                settings_vars['ircut'].set(first_option)
        if 'binning_dropdown' in settings_vars:
            settings_vars['binning_dropdown'].config(state="disabled")

    # Auto-save info label at the bottom (light grey)
    autosave_label = tk.Label(scrollable_frame, text="Updates are saved automatically.", fg="#555555", font=("Arial", 11, "italic"))
    autosave_label.grid(row=grid_row, column=0, columnspan=2, pady=20, padx=10, sticky='ew')

    def on_tab_focus_out(event):
        save_settings(settings_vars, show_message=False, update_create_session_callback=update_create_session_callback)

    def on_app_close():
        save_settings(settings_vars, show_message=False, update_create_session_callback=update_create_session_callback)
        if hasattr(tab_settings, 'winfo_toplevel'):
            tab_settings.winfo_toplevel().destroy()

    # Bind tab focus out to auto-save
    tab_settings.bind('<FocusOut>', on_tab_focus_out)

    # Bind app close (window close) to auto-save
    root = tab_settings.winfo_toplevel()
    if hasattr(root, 'protocol'):
        try:
            root.protocol("WM_DELETE_WINDOW", on_app_close)
        except Exception:
            pass

def save_settings(settings_vars, show_message=True, update_create_session_callback=None):
    config_data = {}
    device_type_display_name = None
    settings_changed = False
    
    # Load current config to compare with new values
    try:
        current_config = load_config()
    except:
        current_config = {}
    
    # Track if any Create Session relevant settings changed
    create_session_relevant_keys = ['exposure', 'gain', 'count', 'device_type', 'camera_type']
    
    for key, var in settings_vars.items():
        if key == "ircut" and '_ircut_value_map' in settings_vars:
            display_val = var.get()
            value_map = settings_vars['_ircut_value_map']
            new_value = str(value_map.get(display_val, 0))
            config_data[key] = new_value
            # Check if this value actually changed
            if key in create_session_relevant_keys:
                old_value = current_config.get(key, "")
                if str(old_value) != new_value:
                    settings_changed = True
        elif key == "binning" and '_binning_value_map' in settings_vars:
            display_val = var.get()
            value_map = settings_vars['_binning_value_map']
            new_value = str(value_map.get(display_val, 0))
            config_data[key] = new_value
            # Check if this value actually changed
            if key in create_session_relevant_keys:
                old_value = current_config.get(key, "")
                if str(old_value) != new_value:
                    settings_changed = True
        elif key == "camera_type" and '_camera_type_value_map' in settings_vars:
            display_val = var.get()
            value_map = settings_vars['_camera_type_value_map']
            new_value = str(value_map.get(display_val, 'Tele Camera'))
            config_data[key] = new_value
            device_type_display_name = display_val  # Save the display name for config.ini
            # Check if camera_type actually changed
            old_value = current_config.get(key, "")
            if str(old_value) != new_value:
                settings_changed = True
        elif key.startswith('_') or key.endswith('_dropdown'):
            continue
        else:
            new_value = var.get()
            config_data[key] = new_value
            # Check if this value actually changed
            if key in create_session_relevant_keys:
                old_value = current_config.get(key, "")
                if str(old_value) != new_value:
                    settings_changed = True
            
    # Save the display name of camera_type as device_type in config.ini
    if device_type_display_name is not None:
        new_device_type = device_type_display_name
        config_data['device_type'] = new_device_type
        # Check if device_type actually changed
        old_device_type = current_config.get('device_type', "")
        if str(old_device_type) != new_device_type:
            settings_changed = True
        
    save_config(config_data)
    
    # Trigger Create Session update if relevant settings changed
    if settings_changed and update_create_session_callback:
        update_create_session_callback()
        
    if show_message:
        messagebox.showinfo("Settings", "Configuration saved successfully!")

# Utility function to update IR Cut dropdown and value map on the page
def update_ircut_dropdown(camera_type_display_val, ircut_combo, ircut_var, settings_vars):
    d2_options = [
        ("D2: IR Cut", 0),
        ("D2: IR Pass", 1)
    ]
    d3_options = [
        ("D3: VIS", 0),
        ("D3: ASTRO", 1),
        ("D3: DUAL BAND", 2)
    ]
    if camera_type_display_val == "Dwarf II":
        options = d2_options
    else:
        options = d3_options
    display_options = [opt for opt, val in options]
    value_map = {opt: val for opt, val in options}
    
    # Update the value map in settings_vars
    settings_vars['_ircut_value_map'] = value_map
    
    if ircut_combo is not None and ircut_var is not None:
        ircut_combo['values'] = display_options
        current_val = ircut_var.get()
        if current_val not in display_options:
            ircut_var.set(display_options[0])
    
    # Handle special case for Dwarf 3 Wide Lens
    if camera_type_display_val == "Dwarf 3 Wide Lens":
        # Set to first option and disable
        if 'ircut_dropdown' in settings_vars:
            settings_vars['ircut_dropdown'].config(state="disabled")
        if ircut_var is not None:
            ircut_var.set(display_options[0])
    else:
        # Enable for other device types
        if 'ircut_dropdown' in settings_vars:
            settings_vars['ircut_dropdown'].config(state="readonly")

def refresh_settings_tab(tab_settings, config_vars, camera_type_change_callback=None, update_create_session_callback=None):
    """Refresh the settings tab with new configuration data"""
    # Clear the existing tab
    for widget in tab_settings.winfo_children():
        widget.destroy()
    
    # Recreate the settings tab with fresh data and callback
    create_settings_tab(tab_settings, config_vars, camera_type_change_callback, update_create_session_callback)