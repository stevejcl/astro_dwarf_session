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

from dwarf_python_api.lib.data_utils import allowed_exposures, allowed_gains
from dwarf_python_api.lib.data_wide_utils import allowed_wide_exposures, allowed_wide_gains
from dwarf_python_api.lib.data_utils import allowed_exposuresD3, allowed_gainsD3
from dwarf_python_api.lib.data_wide_utils import allowed_wide_exposuresD3, allowed_wide_gainsD3
from dwarf_python_api.lib.dwarf_utils import parse_ra_to_float
from dwarf_python_api.lib.dwarf_utils import parse_dec_to_float

def list_available_names(instance):
    return [entry["name"] for entry in instance.values]

# Retrieve available exposure and gain names
available_exposure_names = list_available_names(allowed_exposures)
available_gain_names = list_available_names(allowed_gains)
available_wide_exposure_names = list_available_names(allowed_wide_exposures)
available_wide_gains_names = list_available_names(allowed_wide_gains)

available_exposure_namesD3 = list_available_names(allowed_exposuresD3)
available_gain_namesD3 = list_available_names(allowed_gainsD3)
available_wide_exposure_namesD3 = list_available_names(allowed_wide_exposuresD3)
available_wide_gains_namesD3 = list_available_names(allowed_wide_gainsD3)

# Filter options for different devices
ircut_options = {
    "D2 - IRCut": "0",
    "D2 - IRPass": "1",
    "D3 - VIS Filter": "0",
    "D3 - Astro Filter": "1",
    "D3 - DUAL Band": "2"
}

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

def update_options(device_type, exposure_dropdown, gain_dropdown, ircut_dropdown):
    """Update the exposure, gain, and filter options based on the selected device type."""
    if device_type == "Dwarf II":
        exposure_dropdown['values'] = list(reversed(available_exposure_names))
        gain_dropdown['values'] = available_gain_names
        ircut_dropdown['values'] = ["D2 - IRCut", "D2 - IRPass"]
    elif device_type == "Dwarf 3 Tele Lens":
        exposure_dropdown['values'] = list(reversed(available_exposure_namesD3))
        gain_dropdown['values'] = available_gain_namesD3
        ircut_dropdown['values'] = ["D3 - VIS Filter", "D3 - Astro Filter", "D3 - DUAL Band"]
    elif device_type == "Dwarf 3 Wide Lens":
        exposure_dropdown['values'] = list(reversed(available_wide_exposure_namesD3))
        gain_dropdown['values'] = available_wide_gains_namesD3
        ircut_dropdown['values'] = []
    else:
        exposure_dropdown['values'] = []
        gain_dropdown['values'] = []
        ircut_dropdown['values'] = []

def create_form_fields(scrollable_frame, settings_vars, config_vars):
    # Device Type Dropdown Menu
    device_frame = tk.Frame(scrollable_frame)
    device_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

    device_label = tk.Label(device_frame, text="Device Type", width=20, anchor='w')
    device_label.pack(side='left')
    device_var = tk.StringVar()
    device_dropdown = ttk.Combobox(device_frame, textvariable=device_var)
    device_dropdown['values'] = ["Dwarf II", "Dwarf 3 Tele Lens", "Dwarf 3 Wide Lens"]
    device_dropdown.pack(side='left', padx=5)
    settings_vars["device_type"] = device_var

    # Camera Type Variable (will be updated automatically)
    camera_var = tk.StringVar()
    settings_vars["camera_type"] = camera_var

    # Exposure Dropdown Menu
    exposure_frame = tk.Frame(scrollable_frame)
    exposure_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

    exposure_label = tk.Label(exposure_frame, text="Exposure", width=20, anchor='w')
    exposure_label.pack(side='left')
    exposure_var = tk.StringVar()
    exposure_dropdown = ttk.Combobox(exposure_frame, textvariable=exposure_var)
    exposure_dropdown.pack(side='left', padx=5)
    # Set default value from config settings if exist
    if config_vars.get("exposure") is not None and config_vars["exposure"].get():
        exposure_var.set(config_vars["exposure"].get())
    settings_vars["exposure"] = exposure_var

    # Gain Dropdown Menu
    gain_frame = tk.Frame(scrollable_frame)
    gain_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

    gain_label = tk.Label(gain_frame, text="Gain", width=20, anchor='w')
    gain_label.pack(side='left')
    gain_var = tk.StringVar()
    gain_dropdown = ttk.Combobox(gain_frame, textvariable=gain_var)
    gain_dropdown.pack(side='left', padx=5)
    # Set default value from config settings if exist
    if config_vars.get("gain") is not None and config_vars["gain"].get():
        gain_var.set(config_vars["gain"].get())
    settings_vars["gain"] = gain_var

    # Filter Dropdown Menu
    ircut_frame = tk.Frame(scrollable_frame)
    ircut_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

    ircut_label = tk.Label(ircut_frame, text="Filter", width=20, anchor='w')
    ircut_label.pack(side='left')
    ircut_var = tk.StringVar()
    ircut_dropdown = ttk.Combobox(ircut_frame, textvariable=ircut_var)
    ircut_dropdown.pack(side='left', padx=5)
    settings_vars["IRCut"] = ircut_var

    # Update the exposure and gain options when the device type changes
    def on_device_change(event):
        selected_device = device_var.get()
        update_options(selected_device, exposure_dropdown, gain_dropdown, ircut_dropdown)

        # Set camera type based on device type
        if selected_device == "Dwarf II":
            camera_var.set("Tele Camera")
        elif selected_device == "Dwarf 3 Tele Lens":
            camera_var.set("Tele Camera")
        elif selected_device == "Dwarf 3 Wide Lens":
            camera_var.set("Wide-Angle Camera")

        # Reset exposure and gain if they are not valid for the new device type
        if exposure_var.get() not in exposure_dropdown['values']:
            exposure_var.set('')  # Reset to empty if invalid
        if gain_var.get() not in gain_dropdown['values']:
            gain_var.set('')  # Reset to empty if invalid
        if ircut_var.get() not in ircut_dropdown['values']:
            ircut_var.set('')  # Reset to empty if invalid

            # Set default value from config settings if it exists and is valid
            if config_vars.get("ircut") is not None:
                default_ircut_value = config_vars["ircut"].get()
                for label, value in ircut_options.items():
                    if value == default_ircut_value and label in ircut_dropdown['values']:
                        ircut_var.set(label)  # Set the dropdown to the corresponding label
                        break
                else:
                    ircut_var.set('')  # Clear if the default value doesn't match any label

        # Update camera type in settings
        settings_vars["camera_type"] = camera_var

    device_dropdown.bind("<<ComboboxSelected>>", on_device_change)

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

# Function to generate increasing UUID
uuid_counter = 1

SAVE_FOLDER = 'Astro_Sessions'

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
    exposure = str(settings_vars["exposure"].get())
    gain = settings_vars["gain"].get()
    count = check_integer(settings_vars["count"].get())
    settings_vars["count"].set(count)
    # Get the selected camera type
    selected_camera = settings_vars["camera_type"].get()
    wait_after_camera = settings_vars["wait_after_camera"].get()

    check_values = description and date and time and max_retries
    check_values_goto = no_goto or (goto_solar and target_solar !="") or (goto_manual and target!="" and ra_coord and dec_coord)
    check_values_imaging = (exposure and gain and (count or count == 0) and selected_camera)

    # Validate required fields
    if not (check_values and (calibration_action or check_values_goto) and check_values_imaging):
        messagebox.showerror("Error", "Please fill all required fields")
        return

    if count == 0:
        result = messagebox.askyesno("Confirmation", "count value is set to O, so no imaging will take place, Do you want to proceed?")
        if result:
            print("Count is 0, no imaging will take place.")
        else:
            return

    # Get the selected value for IR Cut from settings_vars
    ircut_selected = settings_vars["IRCut"].get()
    
    ircut_value = ircut_options.get(ircut_selected, "")  # Get the numerical value from the description

    # Initialize the camera setup with default values for "Tele Camera"
    setup_camera = {
        "do_action": True and int(count) != 0,
        "exposure": exposure,
        "gain": gain,
        "binning": "0",
        "IRCut": ircut_value,
        "count": count,
        "wait_after": 30
    }

    setup_wide_camera = {
        "do_action": False,
        "exposure": "10",
        "gain": "90",
        "count": "10",
        "wait_after": 30
    }

    # Modify the behavior for "Wide-Angle Camera"
    if selected_camera == "Wide-Angle Camera":
        setup_camera["do_action"] = False
        setup_wide_camera["do_action"] = True and int(count) != 0
        setup_wide_camera["exposure"] = exposure  # Use input fields for wide-angle as well
        setup_wide_camera["gain"] = gain
        setup_wide_camera["count"] = count

    # convert RA, DEC : Format HH:mm:ss.s and sign DD:mm:ss.s
    if ra_coord not in (None, ""):
        try:
            decimal_RA = float(ra_coord)
        except ValueError:
            decimal_RA = parse_ra_to_float(ra_coord)

    if dec_coord not in (None, ""):
        try:
            decimal_Dec = float(dec_coord)
        except ValueError:
            decimal_Dec = parse_dec_to_float(dec_coord)

    # Prepare the JSON data
    data = {
        "command": {
            "id_command": {
                "uuid": f"{uuid_counter:05d}",
                "description": description,
                "date": date,
                "time": time,
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
                "wait_after": int(wait_after_target)
            },
            "goto_manual": {
                "do_action": goto_manual,
                "target": target,
                "ra_coord": float(decimal_RA) if ra_coord not in (None, "")  else "",
                "dec_coord": float(decimal_Dec) if dec_coord not in (None, "")  else "",
                "wait_after": int(wait_after_target)
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

    # Calculate the end time and update the date and time fields
    end_date, end_time = calculate_end_time(settings_vars)
    if end_date and end_time:  # Ensure valid end time returned
        settings_vars["date"].set(end_date)
        settings_vars["time"].set(end_time)

    # Clear other fields
    for key in settings_vars.keys():
        if key not in ["date", "time", "max_retries", "eq_solving", "auto_focus", "infinite_focus", "calibration", "target_type", "goto_solar", "goto_manual", "no_goto", "wait_before", "wait_after", "wait_after_target", "wait_after_camera"]:  # Don't clear date, time, or calibration checkbox
            if config_vars.get(key) is not None and config_vars[key].get():
                settings_vars[key].set(config_vars[key].get())
            else:
                settings_vars[key].set("")

    messagebox.showinfo("Success", "Data saved successfully!")

def refresh_stellarium_data(settings_vars, config_vars):
    """Refreshes Stellarium data and updates the form fields."""

    stellarium_ip_var = config_vars.get("stellarium_ip", "")
    stellarium_port_var = config_vars.get("stellarium_port", "")

    stellarium_ip = stellarium_ip_var.get() if hasattr(stellarium_ip_var, 'get') else stellarium_ip_var
    stellarium_port = stellarium_port_var.get() if hasattr(stellarium_port_var, 'get') else stellarium_port_var

    stellarium_ip = stellarium_ip or "127.0.0.1"
    stellarium_port = stellarium_port or 8095

    stellarium_connection = StellariumConnection(
        ip=stellarium_ip, 
        port=stellarium_port
    )

    try:
        # Get data from Stellarium
        data = stellarium_connection.get_data()
        # Populate form fields with Stellarium data
        settings_vars["target"].set(data['localized-name'] + " - " + data['name'])
        settings_vars["ra_coord"].set(convert_radeg_to_hourdecimal(data['raJ2000']))
        settings_vars["dec_coord"].set(data['decJ2000'])
        
        # Update the Stellarium information labels (optional)
        print(f"RA: {data['raJ2000']}, Dec: {data['decJ2000']}, Target: {data['name']}")
        
    except Exception as e:
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

    try:

        with open(file_path, 'r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            bFindType = False

            # Strip whitespace from the column names
            csv_reader.fieldnames = [field.strip() for field in csv_reader.fieldnames]

            # Sort the rows by the first column (csv_reader.fieldnames[0])
            sorted_rows = sorted(csv_reader, key=lambda row: row[csv_reader.fieldnames[0]])

            # Process each sorted row
            for row in sorted_rows:
               # Determine which format is being used by checking the presence of certain keys
                if 'Pane' in row and 'RA' in row and 'DEC' in row:
                    if not bFindType:
                        print ("Simple Mosaic Telescopius File detected")
                        bFindType = True
                    # First format: Pane, RA, DEC, etc.
                    pane = row['Pane']
                    ra = row['RA']
                    dec = row['DEC']

                    # Description and target based on Pane
                    description = f"Observation of Mosaic {pane}"
                    target = f"Mosaic {pane}"
                
                elif 'Catalogue Entry' in row and 'Right Ascension' in row and 'Declination' in row:
                    if bFindType is False:
                        print ("Observation Mosaic Telescopius List File detected")
                        bFindType = True
                    # Second format: Catalogue Entry, Familiar Name, etc.
                    catalogue_entry = row['Catalogue Entry']
                    ra = row['Right Ascension']
                    dec = row['Declination']

                    # Description and target based on Catalogue Entry
                    description = f"Mosaic of {catalogue_entry}"
                    target = catalogue_entry
                
                else:
                    # Neither format matched, show a "bad format" message
                    raise KeyError("Unrecognized CSV format")

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
                    settings_vars["max_retries"].set("3")
                if not settings_vars["count"].get():
                    settings_vars["count"].set("10")
                if not settings_vars["wait_before"].get():
                    settings_vars["wait_before"].set("10")
                if not settings_vars["wait_after"].get():
                    settings_vars["wait_after"].set("10")
                if not settings_vars["wait_after_target"].get():
                    settings_vars["wait_after_target"].set("10")
                if not settings_vars["wait_after_camera"].get():
                    settings_vars["wait_after_camera"].set("10")

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
            messagebox.showinfo("Success", "CSV imported and JSON files generated successfully!")
        else:
            messagebox.showinfo("Cancelled", "JSON generation cancelled.")

    except KeyError as e:
        # Display a "bad format" error message if a key is missing
        missing_field = str(e)
        messagebox.showerror("Bad Format", f"Missing required field: {missing_field}")
        return None

def convert_radeg_to_hourdecimal(ra_deg):
    # Transform Ra degrees value in Hour
    if ra_deg < 0: 
        ra_deg = 360 + ra_deg
    # convert to hours
    return (ra_deg/15)

def convert_ra_to_hourdecimal(ra_str):
    # Clean up the RA string to handle the format in the CSV
    ra_str = ra_str.replace('h', '').replace("r", '').replace("'", '').replace('"', '').strip()
    h, m, s = map(float, ra_str.split())

    return (h + m/60 + s/3600)

def convert_dec_to_degrees(dec_str):
    # Remove any non-numeric and non-decimal characters
    dec_str = re.sub(r'[^\d\.\s-]', '', dec_str)
    d, m, s = map(float, dec_str.split())

    # If the degrees are negative, treat the minutes and seconds as positive
    if d < 0:
        return d - (m / 60) - (s / 3600)
    else:
        return d + (m / 60) + (s / 3600)

def generate_json_preview(settings_vars, config_vars):
    global uuid_counter
    ircut_selected = settings_vars["IRCut"].get()
    ircut_value = ircut_options.get(ircut_selected, config_vars["ircut"].get())  # Get the numerical value from the description

    data = {
        "command": {
            "id_command": {
                "uuid": f"{uuid_counter:05d}",
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
                "wait_after": int(settings_vars["wait_after_target"].get())
            },
            "goto_manual": {
                "do_action": True,
                "target": settings_vars["target"].get(),
                "ra_coord": float(settings_vars["ra_coord"].get()),
                "dec_coord": float(settings_vars["dec_coord"].get()),
                "wait_after": int(settings_vars["wait_after_target"].get())
            },
            "setup_camera": {
                "do_action": True,
                "exposure": str(settings_vars["exposure"].get()),
                "gain": settings_vars["gain"].get(),
                "binning": "0",
                "IRCut": ircut_options.get(settings_vars["IRCut"].get(), config_vars["ircut"].get()),
                "count": check_integer(settings_vars["count"].get()),
                "wait_after": int(settings_vars["wait_after_camera"].get())
            },
            "setup_wide_camera": {
                "do_action": False,
                "exposure": "10",
                "gain": "90",
                "count": "10",
                "wait_after": int(settings_vars["wait_after_camera"].get())
            }
        }
    }

    uuid_counter += 1
    return data


def show_preview_dialog(json_preview):
    # Create a new window for the preview
    preview_window = tk.Toplevel()
    preview_window.title("Preview JSON Data")
    
    # Default value for confirmed attribute
    preview_window.confirmed = False
    
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
    return preview_window.confirmed


def on_confirm(window):
    # Set an attribute in the window to indicate confirmation
    window.confirmed = True
    window.destroy()  # Close the window

def on_cancel(window):
    # Set an attribute in the window to indicate cancellation
    window.confirmed = False
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
    # Create a Canvas and a Scrollbar for the session
    canvas = tk.Canvas(tab_create_session)
    scrollbar = ttk.Scrollbar(tab_create_session, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    # Create form fields in the scrollable frame
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

    for field, key in fields:
        row = tk.Frame(scrollable_frame)
        label = tk.Label(row, width=20, text=field, anchor='w')

        # Use DateEntry for date selection
        if key == "date":
            var = tk.StringVar()
            entry = DateEntry(row, textvariable=var, date_pattern="yyyy-mm-dd")  # Date pattern set to "YYYY-MM-DD"
        elif key == "target_type":
            # Create mutually exclusive checkboxes
            label.pack(side=tk.LEFT)
            create_mutually_exclusive_checkboxes(row, var_goto_solar, var_goto_manual, var_no_goto, "Solar System", "Manual", "None")
            settings_vars["goto_solar"] = var_goto_solar
            settings_vars["goto_manual"] = var_goto_manual
            settings_vars["no_goto"] = var_no_goto
        elif key != "target_solar":
            var = tk.StringVar()  # Create a StringVar for each entry field
            entry = tk.Entry(row, textvariable=var)

        if key != "date" and key != "target_type" and key != "target_solar":
            # set default value from settings
            if config_vars.get(key) is not None and config_vars[key].get():
                var.set(config_vars[key].get())

        if key == "max_retries":
           var.set(2)

        if key == "wait_before":
           var.set(10)
        if key == "wait_after":
           var.set(10)
        if key == "wait_after_target":
           var.set(30)
        if key == "wait_after_camera":
           var.set(20)

        if key != "target_type" and key != "target_solar":
            settings_vars[key] = var  # Store variable for later use

        row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        if key == "target":
            label.pack(side=tk.LEFT)
            entry.pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
            refresh_button = tk.Button(row, text="Refresh", command=lambda: refresh_stellarium_data(settings_vars, config_vars))
            refresh_button.pack(side=tk.RIGHT)
        elif key != "target_type" and key != "target_solar":
            label.pack(side=tk.LEFT)
            entry.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)

            if key == "max_retries":
                # Create a frame for the "ACTIONS" text and checkboxes
                actions_frame = tk.Frame(scrollable_frame)
                actions_label = tk.Label(actions_frame, width=20, text="ACTIONS", anchor='w')
                actions_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
                actions_label.pack(side=tk.LEFT)

                # EQ Solving checkbox
                #eq_solving_frame = tk.Frame(scrollable_frame)
                eq_solving_var = tk.BooleanVar()
                eq_solving_checkbox = tk.Checkbutton(actions_frame, text="EQ Solving", variable=eq_solving_var)
                settings_vars["eq_solving"] = eq_solving_var
                #eq_solving_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
                eq_solving_checkbox.pack(side=tk.LEFT, padx=5)

                # Auto Focus checkbox
                #auto_focus_frame = tk.Frame(scrollable_frame)
                auto_focus_var = tk.BooleanVar()
                auto_focus_checkbox = tk.Checkbutton(actions_frame, text="Auto Focus", variable=auto_focus_var)
                settings_vars["auto_focus"] = auto_focus_var
                #auto_focus_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
                auto_focus_checkbox.pack(side=tk.LEFT, padx=5)

                # Infinite Focus checkbox
                #infinite_focus_frame = tk.Frame(scrollable_frame)
                infinite_focus_var = tk.BooleanVar()
                infinite_focus_checkbox = tk.Checkbutton(actions_frame, text="Infinite Focus", variable=infinite_focus_var)
                settings_vars["infinite_focus"] = infinite_focus_var
                #infinite_focus_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
                infinite_focus_checkbox.pack(side=tk.LEFT, padx=5)

                # Calibration checkbox
                #calibration_frame = tk.Frame(scrollable_frame)
                calibration_var = tk.BooleanVar()
                calibration_checkbox = tk.Checkbutton(actions_frame, text="Calibration", variable=calibration_var)
                settings_vars["calibration"] = calibration_var
                #calibration_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
                calibration_checkbox.pack(side=tk.LEFT, padx=5)

        if key == "target_solar":
            label.pack(side=tk.LEFT)
            var = tk.StringVar()
            entry = ttk.Combobox(row, textvariable=var, values=solar_system_objects)
            entry.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)
            settings_vars[key] = var

    # Time field
    time_frame = tk.Frame(scrollable_frame)
    time_label = tk.Label(time_frame, width=20, text="Time (HH:MM:SS)", anchor='w')
    time_var = tk.StringVar()
    time_entry = tk.Entry(time_frame, textvariable=time_var)
    settings_vars["time"] = time_var
    time_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
    time_label.pack(side=tk.LEFT)
    time_entry.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)
    time_var.set(current_datetime.strftime('%H:%M:%S'))

    # Create form fields for device type, exposure, gain, and filter
    create_form_fields(scrollable_frame, settings_vars, config_vars)

    # Save button
    save_button = tk.Button(scrollable_frame, text="Save", command=lambda: save_to_json(settings_vars, config_vars))
    save_button.pack(pady=10)

    # Create a frame to hold the Import CSV label and button
    import_frame = tk.Frame(scrollable_frame, borderwidth=2, relief="groove")
    import_frame.pack(pady=10, padx=5, fill=tk.X)

    # Label for Import CSV button
    import_label = tk.Label(import_frame, text="Import Telescopius Mosaic CSV, it will take the values from your settings")
    import_label.pack(pady=(10, 0), padx=10)  # Add padding around the label

    # Import CSV button
    import_csv_button = ttk.Button(import_frame, text="Import CSV", 
                                   command=lambda: import_csv_and_generate_json(settings_vars, config_vars))
    import_csv_button.pack(pady=(0, 10), padx=10)  # Add padding around the button

    import_frame.pack(pady=10)  # Additional padding around the frame