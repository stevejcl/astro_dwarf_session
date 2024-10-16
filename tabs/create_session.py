import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry  # Import DateEntry from tkcalendar
import json
import os
import datetime
from fractions import Fraction
from stellarium_connection import StellariumConnection

from dwarf_python_api.lib.data_utils import allowed_exposures, allowed_gains
from dwarf_python_api.lib.data_wide_utils import allowed_wide_exposures, allowed_wide_gains
from dwarf_python_api.lib.data_utils import allowed_exposuresD3, allowed_gainsD3
from dwarf_python_api.lib.data_wide_utils import allowed_wide_exposuresD3, allowed_wide_gainsD3

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
    calibration_action = settings_vars["calibration"].get()
    no_goto = settings_vars["no_goto"].get()
    goto_solar = settings_vars["goto_solar"].get()
    target_solar = settings_vars["target_solar"].get()
    goto_manual = settings_vars["goto_manual"].get()
    target = settings_vars["target"].get()
    ra_coord = settings_vars["ra_coord"].get()
    dec_coord = settings_vars["dec_coord"].get()
    exposure = str(settings_vars["exposure"].get())
    gain = settings_vars["gain"].get()
    count = check_integer(settings_vars["count"].get())
    settings_vars["count"].set(count)
    # Get the selected camera type
    selected_camera = settings_vars["camera_type"].get()

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
            "calibration": {
                "do_action": calibration_action,
                "wait_before": 10,
                "wait_after": 10
            },
            "goto_solar": {
                "do_action": goto_solar,
                "target": target_solar,
                "wait_after": 10
            },
            "goto_manual": {
                "do_action": goto_manual,
                "target": target,
                "ra_coord": float(ra_coord) if ra_coord not in (None, "")  else "",
                "dec_coord": float(dec_coord) if dec_coord not in (None, "")  else "",
                "wait_after": 20
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
        if key not in ["date", "time", "calibration", "target_type", "goto_solar", "goto_manual", "no_goto"]:  # Don't clear date, time, or calibration checkbox
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
        settings_vars["target"].set(data['name'])
        settings_vars["ra_coord"].set(data['ra'])
        settings_vars["dec_coord"].set(data['dec'])
        
        # Update the Stellarium information labels (optional)
        print(f"RA: {data['ra']}, Dec: {data['dec']}, Target: {data['name']}")
        
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
           print ("count imainging is not defined")
           return None, None
        count = int(settings_vars["count"].get())

        # Combine date and time into a single datetime object
        start_datetime_str = f"{start_date_str} {start_time_str}"
        start_datetime = datetime.datetime.strptime(start_datetime_str, '%Y-%m-%d %H:%M:%S')

        # Calculate the total exposure time
        total_exposure_time = exposure_seconds * count

        # Calculate end time
        end_datetime = start_datetime + datetime.timedelta(seconds=total_exposure_time)

        end_date = end_datetime.strftime('%Y-%m-%d')
        end_time = end_datetime.strftime('%H:%M:%S')

        # Show a message box with the calculated end time
        messagebox.showinfo("Calculated End Time", f"End Date: {end_date}\nEnd Time: {end_time}")

        return end_date, end_time
    except ValueError as e:
        messagebox.showerror("Error", f"Invalid input: {e}")
        return None, None

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
        ("Target Type", "target_type"),
        ("Solar System Object", "target_solar"),
        ("Manual Target", "target"),
        ("RA Coord", "ra_coord"),
        ("Dec Coord", "dec_coord"),
        ("Imaging count", "count"),
        ("Date (YYYY-MM-DD)", "date")
    ]

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
            entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
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

        if key != "target_type" and key != "target_solar":
            settings_vars[key] = var  # Store variable for later use

        row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        if key == "target":
            label.pack(side=tk.LEFT)
            entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
            # Add button to fetch Stellarium data
            fetch_stellarium_button = tk.Button(row, text="Fetch Stellarium Data", command=lambda: refresh_stellarium_data(settings_vars, config_vars))
            fetch_stellarium_button.pack(side=tk.LEFT, padx=(5, 0))  # Place the button to the right of the Target field
        elif key == "target_solar":
            label.pack(side=tk.LEFT)
            entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
            solar_target_var = tk.StringVar()
            target_name_dropdown = ttk.Combobox(row, textvariable=solar_target_var)
            target_name_dropdown['values'] = solar_system_objects
            target_name_dropdown.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)
            settings_vars["target_solar"] = solar_target_var
        else:
            label.pack(side=tk.LEFT)
            entry.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)
  
   # Add Time selection using Comboboxes for HH:MM:SS
    time_row = tk.Frame(scrollable_frame)
    time_label = tk.Label(time_row, width=20, text="Time (HH:MM:SS)", anchor='w')
    time_label.pack(side=tk.LEFT)
    
    hours_var = tk.StringVar()
    hours_combobox = ttk.Combobox(time_row, textvariable=hours_var, width=3, values=[f"{i:02d}" for i in range(24)])
    hours_combobox.pack(side=tk.LEFT, padx=5)
    hours_combobox.set("00")  # Set default value
    
    minutes_var = tk.StringVar()
    minutes_combobox = ttk.Combobox(time_row, textvariable=minutes_var, width=3, values=[f"{i:02d}" for i in range(60)])
    minutes_combobox.pack(side=tk.LEFT, padx=5)
    minutes_combobox.set("00")  # Set default value
    
    seconds_var = tk.StringVar()
    seconds_combobox = ttk.Combobox(time_row, textvariable=seconds_var, width=3, values=[f"{i:02d}" for i in range(60)])
    seconds_combobox.pack(side=tk.LEFT, padx=5)
    seconds_combobox.set("00")  # Set default value
    
    # Combine the time variables into a single StringVar for settings_vars
    combined_time_var = tk.StringVar(value="00:00:00")
    settings_vars["time"] = combined_time_var

    # Function to update combined_time_var when any of the time comboboxes change
    def update_combined_time(*args):
        combined_time_var.set(f"{hours_var.get()}:{minutes_var.get()}:{seconds_var.get()}")
    
    hours_var.trace_add("write", update_combined_time)
    minutes_var.trace_add("write", update_combined_time)
    seconds_var.trace_add("write", update_combined_time)

    time_row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

    create_form_fields(scrollable_frame, settings_vars, config_vars)

    # Calibration Checkbox
    var_calibration = tk.BooleanVar()
    check_calibration = tk.Checkbutton(scrollable_frame, text="Calibration", variable=var_calibration)
    check_calibration.pack(pady=10)
    settings_vars["calibration"] = var_calibration

    # Button to calculate session end time
    calculate_end_button = tk.Button(scrollable_frame, text="Calculate End Time", command=lambda: calculate_end_time(settings_vars))
    calculate_end_button.pack(pady=10)

    # Save button to save the session data
    save_button = tk.Button(scrollable_frame, text="Save", command=lambda: save_to_json(settings_vars, config_vars))
    save_button.pack(pady=20)
