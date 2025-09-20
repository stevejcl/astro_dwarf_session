import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
import json
import os
import datetime
import re
from fractions import Fraction
import csv
from stellarium_connection import StellariumConnection
from dwarf_python_api.lib.dwarf_utils import parse_ra_to_float
from dwarf_python_api.lib.dwarf_utils import parse_dec_to_float
from dwarf_python_api.lib.data_utils import allowed_exposures, allowed_gains, allowed_exposuresD3, allowed_gainsD3
from dwarf_python_api.lib.data_wide_utils import allowed_wide_exposuresD3, allowed_wide_gainsD3
import uuid
import threading
from astro_dwarf_scheduler import BASE_DIR
import configparser
import sys

def list_available_names(instance):
    return [entry["name"] for entry in instance.values]

# Define the available solar system objects
solar_system_objects = [
    "",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Sun"
]

def create_form_fields(scrollable_frame, settings_vars, config_vars):
    # Use grid layout for neat alignment and resizable behavior
    for i in range(0, 20):
        scrollable_frame.grid_rowconfigure(i, weight=0)
    scrollable_frame.grid_columnconfigure(1, weight=1)

    # Helper to add a label and widget to the grid
    def add_row(row, label_text, widget, label_width=20, sticky_label='e', sticky_widget='we', pady=2):
        label = tk.Label(scrollable_frame, text=label_text, width=label_width, anchor='w')
        label.grid(row=row, column=0, sticky=sticky_label, padx=(5,2), pady=pady)
        widget.grid(row=row, column=1, sticky=sticky_widget, padx=(2,10), pady=pady)
        return label, widget

    row = 0
    # Description field at the top
    description_var = tk.StringVar()
    if config_vars.get("description") is not None and config_vars["description"].get():
        description_var.set(config_vars["description"].get())
    settings_vars["description"] = description_var
    add_row(row, "Description", tk.Entry(scrollable_frame, textvariable=description_var))
    row += 1

    # Exposure
    exposure_var = tk.StringVar()
    exposure_dropdown = ttk.Combobox(scrollable_frame, textvariable=exposure_var)
    
    # Load config to get default values
    config = load_from_config()
    
    # Try to get exposure from config_vars first, then fall back to config file
    if config_vars.get("exposure") is not None and config_vars["exposure"].get():
        exposure_var.set(config_vars["exposure"].get())
    else:
        config_exposure = config.get("CONFIG", "exposure", fallback="30")
        exposure_var.set(config_exposure)

    settings_vars["exposure"] = exposure_var
    settings_vars["exposure_dropdown"] = exposure_dropdown  # Store dropdown reference
    add_row(row, "Exposure", exposure_dropdown)
    row += 1

    # Gain
    gain_var = tk.StringVar()
    gain_dropdown = ttk.Combobox(scrollable_frame, textvariable=gain_var)
    
    # Try to get gain from config_vars first, then fall back to config file
    if config_vars.get("gain") is not None and config_vars["gain"].get():
        gain_var.set(config_vars["gain"].get())
    else:
        config_gain = config.get("CONFIG", "gain", fallback="90")
        gain_var.set(config_gain)
        
    settings_vars["gain"] = gain_var
    settings_vars["gain_dropdown"] = gain_dropdown  # Store dropdown reference
    add_row(row, "Gain", gain_dropdown)
    row += 1

    # Get device type for dropdown population
    device_type = config.get("CONFIG", "device_type", fallback="Dwarf II")
    
    # Create dummy ircut dropdown since update_options expects it
    class DummyDropdown:
        def __setitem__(self, key, value):
            pass
    ircut_dummy = DummyDropdown()
    
    # Populate the exposure and gain dropdowns with appropriate values
    update_options(device_type, exposure_dropdown, gain_dropdown, ircut_dummy)

def create_mutually_exclusive_checkboxes(parent, var1, var2, var3, label1, label2, label3):
    """Create two mutually exclusive checkboxes using boolean variables."""
    def on_check1():
        if var1.get():
            var2.set(False)  # Uncheck the other checkbox
            var3.set(False)  # Uncheck the other checkbox
        elif var2.get():
            var1.set(False)  # Uncheck the other checkbox
            var3.set(False)  # Uncheck the other checkbox
        elif var3.get():
            var1.set(False)  # Uncheck the other checkbox
        else:
            var2.set(True)  # Uncheck the other checkbox

    def on_check2():
        if var2.get():
            var1.set(False)  # Uncheck the other checkbox
            var3.set(False)  # Uncheck the other checkbox
        elif var1.get():
            var2.set(False)  # Uncheck the other checkbox
        elif var3.get():
            var2.set(False)  # Uncheck the other checkbox
        else:
            var1.set(True)  # Uncheck the other checkbox

    def on_check3():
        if var3.get():
            var1.set(False)  # Uncheck the other checkbox
            var2.set(False)  # Uncheck the other checkbox
        elif var1.get():
            var3.set(False)  # Uncheck the other checkbox
        elif var2.get():
            var3.set(False)  # Uncheck the other checkbox
        else:
            var2.set(True)  # Uncheck the other checkbox

    # Create a frame to contain the checkboxes
    check1 = tk.Checkbutton(parent, text=label1, variable=var1, command=on_check1)
    check1.pack(side=tk.LEFT, padx=(0, 5))  # Pack side by side

    check2 = tk.Checkbutton(parent, text=label2, variable=var2, command=on_check2)
    check2.pack(side=tk.LEFT)  # Pack side by side

    check3 = tk.Checkbutton(parent, text=label3, variable=var3, command=on_check3)
    check3.pack(side=tk.LEFT)  # Pack side by side

def update_exposure_gain_dropdowns_from_camera_type(camera_type_display, settings_vars):
    """Update exposure and gain dropdowns when camera type changes from settings tab"""
    try:
        if "exposure_dropdown" in settings_vars and "gain_dropdown" in settings_vars:
            exposure_dropdown = settings_vars["exposure_dropdown"]
            gain_dropdown = settings_vars["gain_dropdown"]
            
            # Create dummy ircut dropdown since update_options expects it
            class DummyDropdown:
                def __setitem__(self, key, value):
                    pass
            ircut_dummy = DummyDropdown()
            
            # Map display names to device types for update_options function
            device_type_map = {
                "Dwarf II": "Dwarf II",
                "Dwarf 3 Tele Lens": "Dwarf 3 Tele Lens", 
                "Dwarf 3 Wide Lens": "Dwarf 3 Wide Lens"
            }
            
            device_type = device_type_map.get(camera_type_display, "Dwarf II")
            
            # Update the dropdown options
            update_options(device_type, exposure_dropdown, gain_dropdown, ircut_dummy)
            
            # Load current settings from config.ini to use as defaults
            config = load_from_config()
            config_exposure = config.get("CONFIG", "exposure", fallback="30")
            config_gain = config.get("CONFIG", "gain", fallback="90")
            
            # Set the dropdown values to config settings if they exist in the available options
            if "exposure" in settings_vars:
                exposure_values = exposure_dropdown['values']
                if config_exposure in exposure_values:
                    settings_vars["exposure"].set(config_exposure)
                elif exposure_values:
                    # If config value not available, use the first option
                    settings_vars["exposure"].set(exposure_values[0])
                    
            if "gain" in settings_vars:
                gain_values = gain_dropdown['values']
                if config_gain in gain_values:
                    settings_vars["gain"].set(config_gain)
                elif gain_values:
                    # If config value not available, use the first option
                    settings_vars["gain"].set(gain_values[0])
                
    except Exception as e:
        print(f"[ERROR] Failed to update exposure/gain dropdowns: {e}")

# Function to generate increasing UUID
uuid_counter = 1

SAVE_FOLDER = os.path.join(BASE_DIR, 'Astro_Sessions')

def generate_uuid():
    file_uuid = uuid.uuid4()
    return str(file_uuid)

def check_integer(value):
    # Try to convert the value to an integer
    try:
        value = int(value)
    except (ValueError, TypeError):
        return 0  # Return 0 if conversion fails

    # Check if the value is negative
    if value < 0:
        return 0

    # Check if the value exceeds 999
    if value > 999:
        return 999

    return value  # Return the valid value

# Function to save data to JSON file
def save_to_json(settings_vars, config_vars):
    global uuid_counter

    # Load configuration variables from config.ini to overcome form initialization issues
    config_vars = load_from_config()

    description = settings_vars["description"].get()
    date = settings_vars["date"].get()
    time = settings_vars["time"].get()
    max_retries = settings_vars["max_retries"].get()
    wait_before = settings_vars["wait_before"].get()
    wait_after = settings_vars["wait_after"].get()
    eq_solving_action = settings_vars["eq_solving"].get()
    auto_focus_action = settings_vars["auto_focus"].get()
    infinite_focus_action = settings_vars["infinite_focus"].get()
    calibration_action = settings_vars["calibration"].get()
    no_goto = settings_vars["no_goto"].get()
    goto_solar = settings_vars["goto_solar"].get()
    target_solar = settings_vars["target_solar"].get()
    goto_manual = settings_vars["goto_manual"].get()
    target = settings_vars["target"].get()
    ra_coord = settings_vars["ra_coord"].get()
    dec_coord = settings_vars["dec_coord"].get()
    wait_after_target = settings_vars["wait_after_target"].get()
    wait_after_camera = settings_vars["wait_after_camera"].get()
    exposure = str(settings_vars["exposure"].get())
    gain = settings_vars["gain"].get()
    count = check_integer(settings_vars["count"].get())
    binning = config_vars.get("CONFIG", "binning")
    selected_camera = config_vars.get("CONFIG", "camera_type")
    ircut = config_vars.get("CONFIG", "ircut")

    # Ensure all required fields are non-empty (except booleans)
    required_fields = [
        ("Description", description),
        ("Date", date),
        ("Time", time),
        ("Max Retries", max_retries),
        ("Exposure", exposure),
        ("Gain", gain),
        ("Camera Type", selected_camera)
    ]
    missing = [name for name, val in required_fields if str(val).strip() == '']
    if missing:
        messagebox.showerror("Error", "Please fill all required fields:\n" + "\n".join(missing))
        return

    # Goto/Calibration logic: at least one of calibration, no_goto, goto_solar (with target_solar), or goto_manual (with target, ra_coord, dec_coord) must be valid
    goto_manual_valid = bool(goto_manual) and str(target).strip() != '' and str(ra_coord).strip() != '' and str(dec_coord).strip() != ''
    goto_solar_valid = bool(goto_solar) and str(target_solar).strip() != ''
    no_goto_valid = bool(no_goto)
    calibration_valid = bool(calibration_action)
    if not (calibration_valid or no_goto_valid or goto_solar_valid or goto_manual_valid):
        messagebox.showerror("Error", "Please select a valid target or calibration action.")
        return

    # Imaging logic: exposure, gain, count, and selected_camera must be set
    if str(exposure).strip() == '' or str(gain).strip() == '' or selected_camera == '':
        messagebox.showerror("Error", "Please fill all imaging fields.")
        return

    if count == 0:
        result = messagebox.askyesno("Confirmation", "count value is set to O, so no imaging will take place, Do you want to proceed?")
        if result:
            print("Count is 0, no imaging will take place.")
        else:
            return

    # Initialize the camera setup with default values for "Tele Camera"
    setup_camera = {
        "do_action": True and int(count) != 0,
        "exposure": exposure,
        "gain": gain,
        "binning": binning,
        "ircut": ircut,
        "count": count,
        "wait_after": int(wait_after_camera) if wait_after_camera and wait_after_camera.strip() else 30
    }

    setup_wide_camera = {
        "do_action": False,
        "exposure": "10",
        "gain": "90",
        "count": "10",
        "wait_after": int(wait_after_camera) if wait_after_camera and wait_after_camera.strip() else 30
    }

    # Modify the behavior for "Wide-Angle Camera"
    if selected_camera == "Wide-Angle Camera":
        setup_camera["do_action"] = False
        setup_wide_camera["do_action"] = True and int(count) != 0
        setup_wide_camera["exposure"] = exposure  # Use input fields for wide-angle as well
        setup_wide_camera["gain"] = gain
        setup_wide_camera["count"] = count

    # convert RA, DEC : Format HH:mm:ss.s and sign DD:mm:ss.s
    decimal_RA = ""
    if ra_coord not in (None, ""):
        try:
            decimal_RA = float(ra_coord)
        except ValueError:
            try:
                decimal_RA = parse_ra_to_float(ra_coord)
            except Exception:
                decimal_RA = ""

    decimal_Dec = ""
    if dec_coord not in (None, ""):
        try:
            decimal_Dec = float(dec_coord)
        except ValueError:
            try:
                decimal_Dec = parse_dec_to_float(dec_coord)
            except Exception:
                decimal_Dec = ""

    # Prepare the JSON data
    data = {
        "command": {
            "id_command": {
                "uuid": f"{generate_uuid()}-{uuid_counter:05d}",
                "description": description,
                "date": settings_vars["date"].get(),
                "time": settings_vars["time"].get(),
                "process": "wait",
                "max_retries": int(max_retries),
                "result": False,
                "message": "",
                "nb_try": 1
            },
            "eq_solving": {
                "do_action": eq_solving_action,
                "wait_before": int(wait_before),
                "wait_after": int(wait_after)
            },
            "auto_focus": {
                "do_action": auto_focus_action,
                "wait_before": int(wait_before),
                "wait_after": int(wait_after)
            },
            "infinite_focus": {
                "do_action": infinite_focus_action,
                "wait_before": int(wait_before),
                "wait_after": int(wait_after)
            },
            "calibration": {
                "do_action": calibration_action,
                "wait_before": int(wait_before),
                "wait_after": int(wait_after)
            },
            "goto_solar": {
                "do_action": goto_solar,
                "target": target_solar,
                "wait_after": int(wait_after_target) if wait_after_target and wait_after_target.strip() else 0
            },
            "goto_manual": {
                "do_action": goto_manual,
                "target": target,
                "ra_coord": float(decimal_RA) if ra_coord not in (None, "") and decimal_RA != "" else "",
                "dec_coord": float(decimal_Dec) if dec_coord not in (None, "") and decimal_Dec != "" else "",
                "wait_after": int(wait_after_target) if wait_after_target and wait_after_target.strip() else 0
            },
            "setup_camera": setup_camera,
            "setup_wide_camera": setup_wide_camera
        }
    }

    # Increment UUID for the next entry
    uuid_counter += 1

    # Define file name
    target_value = target if goto_manual else (target_solar if goto_solar else (target if target else description))
    filename = f"{date}-{time.replace(':', '-')}-{target_value}.json"
    filepath = os.path.join(SAVE_FOLDER, filename)

    # Save the data to a JSON file
    with open(filepath, 'w') as outfile:
        json.dump(data, outfile, indent=4)

    messagebox.showinfo("Success", "Data saved successfully!")

def refresh_stellarium_data(settings_vars, config_vars):
    """Refreshes Stellarium data and updates the form fields."""

    stellarium_ip_var = config_vars.get("stellarium_ip", "")
    stellarium_port_var = config_vars.get("stellarium_port", "")

    stellarium_ip = stellarium_ip_var.get() if hasattr(stellarium_ip_var, 'get') else stellarium_ip_var
    stellarium_port = stellarium_port_var.get() if hasattr(stellarium_port_var, 'get') else stellarium_port_var

    stellarium_ip = stellarium_ip or "127.0.0.1"
    stellarium_port = stellarium_port or 8090

    stellarium_connection = StellariumConnection(
        ip=stellarium_ip, 
        port=stellarium_port
    )

    try:
        # Get data from Stellarium
        data = stellarium_connection.get_data()
        
        # Handle target name - avoid duplication
        localized_name = data.get('localized-name', '').strip()
        name = data.get('name', '').strip()
        
        # Use the better name or combine if they're different
        if localized_name and name:
            if localized_name.lower() == name.lower():
                # They're the same (case-insensitive), use just one
                target_name = localized_name
            elif localized_name and name and localized_name != name:
                # They're different, combine them
                target_name = f"{localized_name} - {name}"
            else:
                # Use whichever one exists
                target_name = localized_name or name
        else:
            # Use whichever one exists
            target_name = localized_name or name or "Unknown Target"
        
        # Create appropriate description based on object type
        object_type = data.get('object-type', '').strip()
        vmag = data.get('vmag', '')
        constellation = data.get('constellation', '').strip()
        
        # Build description with available information
        description_parts = []
        
        # Start with observation of the target
        description_parts.append(f"Observation of {target_name}")
        
        # Add object type if available and meaningful
        if object_type and object_type not in ['', 'undefined', 'unknown']:
            # Clean up object type for better readability
            if object_type.lower() == 'nebula':
                description_parts.append("(Nebula)")
            elif object_type.lower() == 'galaxy':
                description_parts.append("(Galaxy)")
            elif object_type.lower() == 'star cluster':
                description_parts.append("(Star Cluster)")
            elif object_type.lower() == 'double star':
                description_parts.append("(Double Star)")
            elif object_type.lower() == 'variable star':
                description_parts.append("(Variable Star)")
            elif object_type.lower() == 'planet':
                description_parts.append("(Planet)")
            elif object_type.lower() == 'moon':
                description_parts.append("(Moon)")
            else:
                # Use the object type as-is for other types
                description_parts.append(f"({object_type.title()})")
        
        # Add constellation if available
        if constellation and constellation not in ['', 'undefined', 'unknown']:
            description_parts.append(f"in {constellation}")
        
        # Add magnitude if available and reasonable
        if vmag and vmag != '' and vmag != 'undefined':
            try:
                mag_value = float(vmag)
                if -5 <= mag_value <= 20:  # Reasonable magnitude range
                    description_parts.append(f"(Mag: {mag_value:.1f})")
            except (ValueError, TypeError):
                pass
        
        # Join all parts into final description
        description = " ".join(description_parts)
        
        # Populate form fields with Stellarium data
        settings_vars["description"].set(description)
        settings_vars["target"].set(target_name)
        
        # Use raJ2000 and decJ2000 directly (decimal hours and degrees)
        ra_decimal = ''
        if 'raJ2000' in data:
            try:
                ra_j2000 = float(data['raJ2000'])
                ra_decimal = (ra_j2000 + 360) / 15.0
            except Exception as e:
                print(f"[DEBUG] Exception in RA conversion from raJ2000: {e}")
                ra_decimal = ''
        if ra_decimal != '':
            settings_vars["ra_coord"].set(f"{ra_decimal:.6f}")
        else:
            settings_vars["ra_coord"].set("")
        if 'decJ2000' in data:
            settings_vars["dec_coord"].set(data['decJ2000'])
        else:
            settings_vars["dec_coord"].set("")
        # Update the date and time fields to the current date/time
        import datetime
        now = datetime.datetime.now()
        if "date" in settings_vars:
            settings_vars["date"].set(now.strftime('%Y-%m-%d'))
        if "time" in settings_vars:
            settings_vars["time"].set(now.strftime('%H:%M:%S'))
        # Update the Stellarium information labels (optional)
        print(f"RA: {data.get('raJ2000')}, Dec: {data.get('decJ2000')}, Target: {target_name}, Description: {description}")
    except Exception as e:
        error_message = str(e)
        if '404' in error_message:
            messagebox.showerror(
                "Error",
                f"Error retrieving data from Stellarium: {e}\n\nTip: Select a target in Stellarium first, then try again."
            )
        else:
            messagebox.showerror("Error", f"Error retrieving data from Stellarium: {e}")

# Function to get the exposure time from settings_vars
def get_exposure_time(settings_vars):
    exposure_string = str(settings_vars["exposure"].get())  # Get the exposure string from settings_vars
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

def calculate_end_time(settings_vars):
    try:
        # Get the starting date, time, exposure, and count
        start_date_str = settings_vars["date"].get()
        start_time_str = settings_vars["time"].get()
        exposure_seconds = get_exposure_time(settings_vars)

        if not settings_vars["count"].get():
           print ("count imaging is not defined")
           return None, None

        count = int(settings_vars["count"].get())

        # add wait time init to 
        wait_time = 0  
        if settings_vars["eq_solving"].get():
          # wait time actions
          wait_time += 60
          wait_time += int(settings_vars.get("wait_before", 0).get())
          wait_time += int(settings_vars.get("wait_after", 0).get())
        if settings_vars["auto_focus"].get():
          # wait time actions
          wait_time += 10
          wait_time += int(settings_vars.get("wait_before", 0).get())
          wait_time += int(settings_vars.get("wait_after", 0).get())
        if settings_vars["infinite_focus"].get():
          # wait time actions
          wait_time += 5
          wait_time += int(settings_vars.get("wait_before", 0).get())
          wait_time += int(settings_vars.get("wait_after", 0).get())
        if settings_vars["calibration"].get():
          # wait between actions and time actions
          wait_time += 10 + 60
          wait_time += int(settings_vars.get("wait_before", 0).get())
          wait_time += int(settings_vars.get("wait_after", 0).get())
        if settings_vars["goto_solar"].get() or settings_vars["goto_manual"].get():
          wait_time += 30
          wait_time += int(settings_vars.get("wait_after_target", 0).get())

        # wait time setup camera
        wait_time += 15
        wait_time += int(settings_vars.get("wait_after_camera", 0).get())

        # Combine date and time into a single datetime object
        start_datetime_str = f"{start_date_str} {start_time_str}"
        start_datetime = datetime.datetime.strptime(start_datetime_str, '%Y-%m-%d %H:%M:%S')

        # Calculate the total exposure time
        total_exposure_time = wait_time + (exposure_seconds + 1) * count 

        # Calculate end time
        end_datetime = start_datetime + datetime.timedelta(seconds=total_exposure_time)

        end_date = end_datetime.strftime('%Y-%m-%d')
        end_time = end_datetime.strftime('%H:%M:%S')

        return end_date, end_time
    except ValueError as e:
        messagebox.showerror("Error", f"Invalid input: {e}")
        return None, None

def import_csv_and_generate_json(settings_vars, config_vars):
    # Open file dialog to select CSV file
    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if not file_path:
        return  # User cancelled file selection

    json_preview = []
    current_datetime = datetime.datetime.now()
    settings_vars["uuid"].set(generate_uuid())

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            # Strip whitespace from the column names
            if csv_reader.fieldnames is None:
                messagebox.showerror("Error", "CSV file is empty or malformed (no header row found).")
                return
            csv_reader.fieldnames = [field.strip() for field in csv_reader.fieldnames]
            rows = list(csv_reader)
            if not rows:
                messagebox.showerror("Error", "No data rows found in the CSV file.")
                return

            # Detect format by header
            is_telescopius_list = (
                'Catalogue Entry' in csv_reader.fieldnames and
                'Right Ascension (j2000)' in csv_reader.fieldnames and
                'Declination (j2000)' in csv_reader.fieldnames
            )
            is_mosaic_plan = (
                'Pane' in csv_reader.fieldnames and
                'RA' in csv_reader.fieldnames and
                'DEC' in csv_reader.fieldnames
            )

            for row in rows:
                if is_mosaic_plan:
                    pane = row['Pane']
                    ra = row['RA']
                    dec = row['DEC']
                    description = f"Observation of Mosaic {pane}"
                    target = f"Mosaic {pane}"
                elif is_telescopius_list:
                    catalogue_entry = row['Catalogue Entry']
                    ra = row['Right Ascension (j2000)']
                    dec = row['Declination (j2000)']
                    description = f"Observation of {catalogue_entry}"
                    target = catalogue_entry
                else:
                    # Skip rows that do not match known formats
                    continue

                # Convert RA to Hour Decimal and Dec to decimal degrees
                ra_deg = convert_ra_to_hourdecimal(ra)
                dec_deg = convert_dec_to_degrees(dec)

                # Set the values in settings_vars
                settings_vars["description"].set(description)
                settings_vars["target"].set(target)
                settings_vars["ra_coord"].set(ra_deg)
                settings_vars["dec_coord"].set(dec_deg)
                settings_vars["date"].set(current_datetime.strftime('%Y-%m-%d'))
                settings_vars["time"].set(current_datetime.strftime('%H:%M:%S'))

                # Set default values if not already set
                if not settings_vars["max_retries"].get():
                    pass
                if not settings_vars["count"].get():
                    pass
                if not settings_vars["wait_before"].get():
                    pass
                if not settings_vars["wait_after"].get():
                    pass
                if not settings_vars["wait_after_target"].get():
                    pass
                if not settings_vars["wait_after_camera"].get():
                    pass

                # Ensure goto_manual is set to True
                settings_vars["goto_manual"].set(True)
                settings_vars["goto_solar"].set(False)
                settings_vars["no_goto"].set(False)

                # Generate JSON preview for this row
                json_data = generate_json_preview(settings_vars, config_vars)
                json_preview.append(json_data)

                # Calculate end time for this entry
                end_date, end_time = calculate_end_time(settings_vars)
                if end_date and end_time:
                    # Set the end time as the start time for the next entry
                    current_datetime = datetime.datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S')

        # Show preview dialog
        if show_preview_dialog(json_preview):
            # User confirmed, generate actual JSON files
            for json_data in json_preview:
                save_json_to_file(json_data)
            messagebox.showinfo("Success", f"CSV imported and {len(json_preview)} record(s) generated successfully!")
        else:
            messagebox.showinfo("Cancelled", "JSON generation cancelled.")

    except KeyError as e:
        # Display a "bad format" error message if a key is missing
        missing_field = str(e)
        messagebox.showerror("Bad Format", f"Missing required field: {missing_field}")
        return None

def convert_ra_to_hourdecimal(ra_str):
    # If it's already a float, just return it
    if isinstance(ra_str, float):
        return ra_str
    # Clean up the RA string to handle the format in the CSV
    ra_str = str(ra_str).replace('h', '').replace("r", '').replace("'", '').replace('"', '').strip()
    # If it's already a decimal, just return it
    try:
        return float(ra_str)
    except ValueError:
        pass

    # Try to split by colon or space
    if ':' in ra_str:
        parts = ra_str.split(':')
    else:
        parts = ra_str.split()
    # Pad with zeros if not enough parts
    while len(parts) < 3:
        parts.append('0')
    try:
        h, m, s = map(float, parts[:3])
    except Exception:
        # If still can't parse, return 0.0 as fallback
        return 0.0
    return h + m/60 + s/3600

def convert_dec_to_degrees(dec_str):
    # Remove any non-numeric and non-decimal characters except minus and space/colon
    dec_str = re.sub(r'[^\d\.\s:-]', '', dec_str).strip()
    # If it's already a decimal, just return it
    try:
        return float(dec_str)
    except ValueError:
        pass

    # Try to split by colon or space
    if ':' in dec_str:
        parts = dec_str.split(':')
    else:
        parts = dec_str.split()
    # Pad with zeros if not enough parts
    while len(parts) < 3:
        parts.append('0')
    try:
        d, m, s = map(float, parts[:3])
    except Exception:
        # If still can't parse, return 0.0 as fallback
        return 0.0
    # If the degrees are negative, treat the minutes and seconds as positive
    if d < 0:
        return d - (m / 60) - (s / 3600)
    else:
        return d + (m / 60) + (s / 3600)

def generate_json_preview(settings_vars, config_vars):
    global uuid_counter

    config_vars = load_from_config()

    count = check_integer(settings_vars["count"].get())
    gain = settings_vars["gain"].get()
    selected_camera = config_vars.get("CONFIG", "camera_type")
    exposure = check_integer(settings_vars["exposure"].get())
    binning_value = config_vars.get("CONFIG", "binning")
    ircut_value = config_vars.get("CONFIG", "ircut")

    # Initialize the camera setup with default values for "Tele Camera"
    setup_camera = {
        "do_action": True and int(count) != 0,
        "exposure": exposure,
        "gain": gain,
        "binning": binning_value,
        "ircut": ircut_value,
        "count": count,
        "wait_after": int(settings_vars["wait_after_camera"].get()) if settings_vars["wait_after_camera"].get() and settings_vars["wait_after_camera"].get().strip() else 0
    }

    setup_wide_camera = {
        "do_action": False,
        "exposure": "10",
        "gain": "90",
        "count": "10",
        "wait_after": "30"
    }

    # Modify the behavior for "Wide-Angle Camera"
    if selected_camera == "Wide-Angle Camera":
        setup_camera["do_action"] = False
        setup_wide_camera["do_action"] = True and int(count) != 0
        setup_wide_camera["exposure"] = exposure  # Use input fields for wide-angle as well
        setup_wide_camera["gain"] = gain
        setup_wide_camera["count"] = count
        setup_wide_camera["wait_after"] = int(settings_vars["wait_after_camera"].get()) if settings_vars["wait_after_camera"].get() and settings_vars["wait_after_camera"].get().strip() else 0


    data = {
        "command": {
            "id_command": {
                "uuid": f"{settings_vars['uuid'].get()}-{uuid_counter:05d}",
                "description": settings_vars["description"].get(),
                "date": settings_vars["date"].get(),
                "time": settings_vars["time"].get(),
                "process": "wait",
                "max_retries": int(settings_vars["max_retries"].get()),
                "result": False,
                "message": "",
                "nb_try": 1
            },
            "eq_solving": {
                "do_action": settings_vars["eq_solving"].get(),
                "wait_before": int(settings_vars["wait_before"].get()),
                "wait_after": int(settings_vars["wait_after"].get()),
            },
            "auto_focus": {
                "do_action": settings_vars["auto_focus"].get(),
                "wait_before": int(settings_vars["wait_before"].get()),
                "wait_after": int(settings_vars["wait_after"].get()),
            },
            "infinite_focus": {
                "do_action": settings_vars["infinite_focus"].get(),
                "wait_before": int(settings_vars["wait_before"].get()),
                "wait_after": int(settings_vars["wait_after"].get()),
            },
            "calibration": {
                "do_action": settings_vars["calibration"].get(),
                "wait_before": int(settings_vars["wait_before"].get()),
                "wait_after": int(settings_vars["wait_after"].get()),
            },
            "goto_solar": {
                "do_action": False,
                "target": "",
                "wait_after": int(settings_vars["wait_after_target"].get()) if settings_vars["wait_after_target"].get() and settings_vars["wait_after_target"].get().strip() else 0
            },
            "goto_manual": {
                "do_action": True,
                "target": settings_vars["target"].get(),
                "ra_coord": float(settings_vars["ra_coord"].get()),
                "dec_coord": float(settings_vars["dec_coord"].get()),
                "wait_after": int(settings_vars["wait_after_target"].get()) if settings_vars["wait_after_target"].get() and settings_vars["wait_after_target"].get().strip() else 0
            },
            "setup_camera": setup_camera,
            "setup_wide_camera": setup_wide_camera
        }
    }

    uuid_counter += 1
    return data


def show_preview_dialog(json_preview):
    # Create a new window for the preview
    preview_window = tk.Toplevel()
    preview_window.title("Preview JSON Data")
    
    # Default value for confirmed attribute
    setattr(preview_window, "confirmed", False)
    
    # Create a text widget to display the preview
    text_widget = tk.Text(preview_window, wrap='word', height=20, width=50)
    text_widget.pack(expand=True, fill='both')
    
    # Insert the JSON preview data into the text widget
    for json_data in json_preview:
        text_widget.insert(tk.END, f"{json_data}\n\n")
    
    # Make the text widget read-only
    text_widget.config(state=tk.DISABLED)
    
    # Create a frame for the buttons
    button_frame = tk.Frame(preview_window)
    button_frame.pack(pady=10)

    # Add "Confirm" and "Cancel" buttons
    confirm_button = tk.Button(button_frame, text="Confirm", command=lambda: on_confirm(preview_window))
    confirm_button.pack(side=tk.LEFT, padx=5)
    
    cancel_button = tk.Button(button_frame, text="Cancel", command=lambda: on_cancel(preview_window))
    cancel_button.pack(side=tk.LEFT, padx=5)

    # Run the window and wait for user action
    preview_window.wait_window()

    # If the window was confirmed, return True, otherwise return False
    return getattr(preview_window, "confirmed", False)


def on_confirm(window):
    # Set an attribute in the window to indicate confirmation
    setattr(window, "confirmed", True)
    window.destroy()  # Close the window

def on_cancel(window):
    # Set an attribute in the window to indicate cancellation
    setattr(window, "confirmed", False)
    window.destroy()  # Close the window

def save_json_to_file(json_data):
    date = json_data["command"]["id_command"]["date"]
    time = json_data["command"]["id_command"]["time"]
    target = json_data["command"]["goto_manual"]["target"]
    
    filename = f"{date}-{time.replace(':', '-')}-{target}.json"
    filepath = os.path.join(SAVE_FOLDER, filename)

    with open(filepath, 'w') as outfile:
        json.dump(json_data, outfile, indent=4)

# Function to create the session tab
def create_session_tab(tab_create_session, settings_vars, config_vars):
    # --- Modern scrollable frame setup ---
    container = ttk.Frame(tab_create_session)
    container.grid(row=0, column=0, sticky='nsew')
    tab_create_session.grid_rowconfigure(0, weight=1)
    tab_create_session.grid_columnconfigure(0, weight=1)

    canvas = tk.Canvas(container, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    def _on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas_width = event.width
        canvas.itemconfig("frame", width=canvas_width)

    scrollable_frame.bind(
        "<Configure>", _on_frame_configure
    )
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", tags="frame")
    canvas.configure(yscrollcommand=scrollbar.set)

    def _on_canvas_configure(event):
        canvas.itemconfig("frame", width=event.width)

    canvas.bind('<Configure>', _on_canvas_configure)

    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)
    # Make the scrollable_frame expand vertically
    scrollable_frame.grid_rowconfigure(999, weight=1)

    # Create form fields in the scrollable frame using grid
    fields = [
        ("Description", "description"),
        ("Max Retries", "max_retries"),
        ("Wait Before Action in s.", "wait_before"),
        ("Wait After Action in s.", "wait_after"),
        ("Target Type", "target_type"),
        ("Solar System Object", "target_solar"),
        ("Manual Target", "target"),
        ("RA (dec or HH:mm:ss.s)", "ra_coord"),
        ("Dec (dec or ±DD:mm:ss.s)", "dec_coord"),
        ("Wait After Goto in s.", "wait_after_target"),
        ("Imaging count (0 Not Do)", "count"),
        ("Wait After Session in s.", "wait_after_camera"),
        ("Date (YYYY-MM-DD)", "date")
    ]

    current_datetime = datetime.datetime.now()
    var_goto_solar = tk.BooleanVar(value=False)
    var_goto_manual = tk.BooleanVar(value=True)
    var_no_goto = tk.BooleanVar(value=False)

    entry = tk.Entry()
    var = tk.StringVar()

    grid_row = 0
    for field, key in fields:
        label = tk.Label(scrollable_frame, width=20, text=field, anchor='w')
        if key == "date":
            var = tk.StringVar()
            entry = DateEntry(scrollable_frame, textvariable=var, date_pattern="yyyy-mm-dd")
        elif key == "target_type":
            entry = tk.Frame(scrollable_frame)
            create_mutually_exclusive_checkboxes(entry, var_goto_solar, var_goto_manual, var_no_goto, "Solar System", "Manual", "None")
            settings_vars["goto_solar"] = var_goto_solar
            settings_vars["goto_manual"] = var_goto_manual
            settings_vars["no_goto"] = var_no_goto
        elif key != "target_solar":
            var = tk.StringVar()
            entry = tk.Entry(scrollable_frame, textvariable=var)

        if key != "date" and key != "target_type" and key != "target_solar":
            if config_vars.get(key) is not None and config_vars[key].get():
                var.set(config_vars[key].get())
        if key == "max_retries":
            var.set("2")
        if key == "wait_before":
            var.set("10")
        if key == "wait_after":
            var.set("10")
        if key == "wait_after_target":
            var.set("30")
        if key == "wait_after_camera":
            var.set("20")
        if key != "target_type" and key != "target_solar":
            settings_vars[key] = var

        label.grid(row=grid_row, column=0, sticky='e', padx=(5,2), pady=6)
        if key == "target":
            # Ensure the entry is a child of the frame and the StringVar is stored
            var = tk.StringVar()
            if config_vars.get(key) is not None and config_vars[key].get():
                var.set(config_vars[key].get())
            settings_vars[key] = var
            entry = tk.Entry(target_frame := tk.Frame(scrollable_frame), textvariable=var)
            target_frame.grid(row=grid_row, column=1, sticky='we', padx=(2,10), pady=6)
            target_frame.grid_columnconfigure(0, weight=1)
            entry.grid(row=0, column=0, sticky='we')
            refresh_button = tk.Button(
                target_frame,
                text="Refresh from Stellarium",
                width=20,  # Set a fixed width to accommodate the longest text
                command=lambda: refresh_stellarium_data_in_background(settings_vars, config_vars, button=refresh_button)
            )
            refresh_button.grid(row=0, column=1, sticky='e', padx=(6, 0))
        elif key == "target_type":
            entry.grid(row=grid_row, column=1, sticky='w', padx=(2,10), pady=6)
        elif key == "target_solar":
            var = tk.StringVar()
            entry = ttk.Combobox(scrollable_frame, textvariable=var, values=solar_system_objects)
            entry.grid(row=grid_row, column=1, sticky='we', padx=(2,10), pady=6)
            settings_vars[key] = var
        else:
            entry.grid(row=grid_row, column=1, sticky='we', padx=(2,10), pady=6)
        if key == "max_retries":
            # ACTIONS checkboxes row
            actions_label = tk.Label(scrollable_frame, width=20, text="ACTIONS", anchor='w')
            actions_label.grid(row=grid_row+1, column=0, sticky='e', padx=(5,2), pady=6)
            actions_frame = tk.Frame(scrollable_frame)
            actions_frame.grid(row=grid_row+1, column=1, sticky='w', padx=(2,10), pady=6)
            auto_focus_var = tk.BooleanVar()
            auto_focus_checkbox = tk.Checkbutton(actions_frame, text="Auto Focus", variable=auto_focus_var)
            auto_focus_checkbox.pack(side=tk.LEFT, padx=5)
            settings_vars["auto_focus"] = auto_focus_var
            infinite_focus_var = tk.BooleanVar()
            infinite_focus_checkbox = tk.Checkbutton(actions_frame, text="Infinite Focus", variable=infinite_focus_var)
            infinite_focus_checkbox.pack(side=tk.LEFT, padx=5)
            settings_vars["infinite_focus"] = infinite_focus_var
            eq_solving_var = tk.BooleanVar()
            eq_solving_checkbox = tk.Checkbutton(actions_frame, text="EQ Solving", variable=eq_solving_var)
            eq_solving_checkbox.pack(side=tk.LEFT, padx=5)
            settings_vars["eq_solving"] = eq_solving_var
            calibration_var = tk.BooleanVar()
            calibration_checkbox = tk.Checkbutton(actions_frame, text="Calibration", variable=calibration_var)
            calibration_checkbox.pack(side=tk.LEFT, padx=5)
            settings_vars["calibration"] = calibration_var
            grid_row += 1
        grid_row += 1

    # Time field
    time_label = tk.Label(scrollable_frame, width=20, text="Time (HH:MM:SS)", anchor='w')
    time_var = tk.StringVar()
    time_entry = tk.Entry(scrollable_frame, textvariable=time_var)
    settings_vars["time"] = time_var
    time_label.grid(row=grid_row, column=0, sticky='e', padx=(5,2), pady=6)
    time_entry.grid(row=grid_row, column=1, sticky='we', padx=(2,10), pady=6)
    time_var.set(current_datetime.strftime('%H:%M:%S'))
    grid_row += 1

    # Create form fields for device type, exposure, gain, and filter
    create_form_fields(scrollable_frame, settings_vars, config_vars)

    # Add a spacer row to push Save and Import CSV to the bottom if possible
    scrollable_frame.grid_rowconfigure(grid_row, weight=1)
    grid_row += 1

    # Save button
    save_button = tk.Button(scrollable_frame, text="Save", command=lambda: save_to_json(settings_vars, config_vars))
    save_button.grid(row=grid_row, column=0, columnspan=3, pady=10, sticky='s')
    grid_row += 1

    # Import CSV section
    import_frame = tk.Frame(scrollable_frame, borderwidth=2, relief="groove")
    import_frame.grid(row=grid_row, column=0, columnspan=3, sticky='we', pady=10, padx=5)
    import_label = tk.Label(import_frame, text="Import Telescopius Mosaic or List CSV, it will take the values from your settings", fg="#555555")
    import_label.pack(pady=(10, 5), padx=10)
    import_csv_button = ttk.Button(import_frame, text="Import CSV", command=lambda: import_csv_and_generate_json(settings_vars, config_vars))
    import_csv_button.pack(pady=(0, 10), padx=10)

    # Initialize the "uuid" key in settings_vars
    settings_vars["uuid"] = tk.StringVar()
    
    # Initial update of exposure and gain dropdowns based on current config
    config = load_from_config()
    device_type = config.get("CONFIG", "device_type", fallback="Dwarf II")
    update_exposure_gain_dropdowns_from_camera_type(device_type, settings_vars)

def load_from_config():
    """Load the camera type from config.ini file"""
    try:
        from astro_dwarf_scheduler import get_current_config_ini_file
        config_file = get_current_config_ini_file()
    except ImportError:
        config_file = 'config.ini'
    
    config = configparser.ConfigParser()
    if os.path.exists(config_file):
        config.read(config_file)
    else:
        # Set default values if config file does not exist
        config.add_section("CONFIG")
        config.set("CONFIG", "device_type", "Dwarf II")
        config.set("CONFIG", "camera_type", "Tele Camera")
        config.set("CONFIG", "binning", "1")
        config.set("CONFIG", "ircut", "0")
        config.set("CONFIG", "exposure", "30")
        config.set("CONFIG", "gain", "90")
        config.set("CONFIG", "count", "1")
    return config

# Utility to update Exposure and Gain fields from config.ini
def update_exposure_gain_fields(settings_vars):
    """Update Exposure and Gain fields from config.ini when Create Session tab is selected."""
    try:
        # Load configuration from config.ini
        config = load_from_config()
        
        # Get device type from config
        device_type = config.get("CONFIG", "device_type", fallback="Dwarf II")
        
        # Use the camera type change function to update dropdowns
        update_exposure_gain_dropdowns_from_camera_type(device_type, settings_vars)
        
        # Update exposure from config.ini only if it's different
        if "exposure" in settings_vars:
            config_exposure = config.get("CONFIG", "exposure", fallback="30")
            current_exposure = settings_vars["exposure"].get()
            if current_exposure != config_exposure:
                settings_vars["exposure"].set(config_exposure)
        
        # Update gain from config.ini only if it's different
        if "gain" in settings_vars:
            config_gain = config.get("CONFIG", "gain", fallback="90")
            current_gain = settings_vars["gain"].get()
            if current_gain != config_gain:
                settings_vars["gain"].set(config_gain)

        # Update count from config.ini only if it's different
        if "count" in settings_vars:
            config_count = config.get("CONFIG", "count", fallback="1")
            current_count = settings_vars["count"].get()
            if current_count != config_count:
                settings_vars["count"].set(config_count)

    except Exception as e:
        print(f"[ERROR] Failed to update exposure/gain from config.ini: {e}")
        # Fallback to default values if config loading fails
        if "exposure" in settings_vars:
            settings_vars["exposure"].set("30")
        if "gain" in settings_vars:
            settings_vars["gain"].set("90")
        if "count" in settings_vars:
            settings_vars["count"].set("1")

def update_options(device_type, exposure_dropdown, gain_dropdown, ircut_dropdown):
    """Update the exposure, gain, and filter options based on the selected device type."""    
    # Helper function to get available names
    def get_available_names(instance):
        return [entry["name"] for entry in instance.values]
    
    if device_type == "Dwarf II":
        available_exposure_names = get_available_names(allowed_exposures)
        available_gain_names = get_available_names(allowed_gains)
        exposure_dropdown['values'] = list(reversed(available_exposure_names))
        gain_dropdown['values'] = available_gain_names
        ircut_dropdown['values'] = ["D2: IRCut", "D2: IRPass"]
    elif device_type == "Dwarf 3 Tele Lens":
        available_exposure_namesD3 = get_available_names(allowed_exposuresD3)
        available_gain_namesD3 = get_available_names(allowed_gainsD3)
        exposure_dropdown['values'] = list(reversed(available_exposure_namesD3))
        gain_dropdown['values'] = available_gain_namesD3
        ircut_dropdown['values'] = ["D3: VIS Filter", "D3: Astro Filter", "D3: DUAL Band"]
    elif device_type == "Dwarf 3 Wide Lens":
        available_wide_exposure_namesD3 = get_available_names(allowed_wide_exposuresD3)
        available_wide_gains_namesD3 = get_available_names(allowed_wide_gainsD3)
        exposure_dropdown['values'] = list(reversed(available_wide_exposure_namesD3))
        gain_dropdown['values'] = available_wide_gains_namesD3
        ircut_dropdown['values'] = []
    else:
        exposure_dropdown['values'] = []
        gain_dropdown['values'] = []
        ircut_dropdown['values'] = []

def refresh_stellarium_data_in_background(settings_vars, config_vars, button=None):
    """Run refresh_stellarium_data in a background thread and update the button state and text during execution."""
    def task():
        original_text = button.cget("text") if button else None  # Store the original button text
        try:
            if button:
                button.config(state=tk.DISABLED, text="Stand by..")  # Disable the button and change text
                
            refresh_stellarium_data(settings_vars, config_vars)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
        finally:
            if button:
                button.config(state=tk.NORMAL, text=original_text)  # Re-enable the button and restore text

    # Start the background thread
    threading.Thread(target=task, daemon=True).start()