import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import datetime
from stellarium_connection import StellariumConnection

# Function to generate increasing UUID
uuid_counter = 1

SAVE_FOLDER = 'Astro_Sessions'

# Function to save data to JSON file
def save_to_json(settings_vars):
    global uuid_counter

    description = settings_vars["description"].get()
    date = settings_vars["date"].get()
    time = settings_vars["time"].get()
    max_retries = settings_vars["max_retries"].get()
    calibration_action = settings_vars["calibration"].get()
    target = settings_vars["target"].get()
    ra_coord = settings_vars["ra_coord"].get()
    dec_coord = settings_vars["dec_coord"].get()
    exposure = settings_vars["exposure"].get()
    gain = settings_vars["gain"].get()
    count = settings_vars["count"].get()
    
    # Get the selected value for IR Cut from settings_vars
    ircut_selected = settings_vars["IRCut"].get()
    
    # Update the IR Cut value based on selection
    ircut_options = {
        "D2 - IRCut": "0",
        "D2 - IRPass": "1",
        "D3 - VIS Filter": "0",
        "D3 - Astro Filter": "1",
        "D3 - DUAL Band": "2"
    }
    ircut_value = ircut_options.get(ircut_selected, "")  # Get the numerical value from the description

    # Get the selected camera type
    selected_camera = settings_vars["camera_type"].get()

    # Initialize the camera setup with default values for "Tele Camera"
    setup_camera = {
        "do_action": True,
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
        setup_wide_camera["do_action"] = True
        setup_wide_camera["exposure"] = exposure  # Use input fields for wide-angle as well
        setup_wide_camera["gain"] = gain
        setup_wide_camera["count"] = count

    # Validate required fields
    if not description or not date or not time or not max_retries:
        messagebox.showerror("Error", "Please fill all required fields")
        return

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
                "do_action": False,
                "target": "planet_name",
                "wait_after": 10
            },
            "goto_manual": {
                "do_action": True,
                "target": target,
                "ra_coord": float(ra_coord),
                "dec_coord": float(dec_coord),
                "wait_after": 20
            },
            "setup_camera": setup_camera,
            "setup_wide_camera": setup_wide_camera
        }
    }

    # Increment UUID for the next entry
    uuid_counter += 1

    # Define file name
    filename = f"{date}-{time.replace(':', '-')}-{target}.json"
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
        if key not in ["date", "time", "calibration"]:  # Don't clear date, time, or calibration checkbox
            settings_vars[key].set("")

    messagebox.showinfo("Success", "Data saved successfully!")

def refresh_stellarium_data(settings_vars):
    """Refreshes Stellarium data and updates the form fields."""
    stellarium_connection = StellariumConnection()

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

def calculate_end_time(settings_vars):
    try:
        # Get the starting date, time, exposure, and count
        start_date_str = settings_vars["date"].get()
        start_time_str = settings_vars["time"].get()
        exposure_seconds = int(settings_vars["exposure"].get())
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
def create_session_tab(tab_create_session, settings_vars):
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
        ("Date (YYYY-MM-DD)", "date"),
        ("Time (HH:MM:SS)", "time"),
        ("Max Retries", "max_retries"),
        ("Target", "target"),
        ("RA Coord", "ra_coord"),
        ("Dec Coord", "dec_coord"),
        ("Exposure", "exposure"),
        ("Gain", "gain"),
        ("Count", "count")
    ]

    for field, key in fields:
        row = tk.Frame(scrollable_frame)
        label = tk.Label(row, width=15, text=field, anchor='w')
        var = tk.StringVar()  # Create a StringVar for each entry field
        entry = tk.Entry(row, textvariable=var)
        settings_vars[key] = var  # Store variable for later use
        row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        label.pack(side=tk.LEFT)
        entry.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)

    # Calibration Checkbox
    var_calibration = tk.BooleanVar()
    check_calibration = tk.Checkbutton(scrollable_frame, text="Calibration", variable=var_calibration)
    check_calibration.pack(pady=10)
    settings_vars["calibration"] = var_calibration

    # Camera Type Dropdown Menu
    camera_label = tk.Label(scrollable_frame, text="Camera Type")
    camera_label.pack(pady=5)
    camera_var = tk.StringVar()
    camera_dropdown = ttk.Combobox(scrollable_frame, textvariable=camera_var)
    camera_dropdown['values'] = ["Tele Camera", "Wide-Angle Camera"]
    camera_dropdown.pack(pady=5)
    settings_vars["camera_type"] = camera_var  # Store selected camera type

    # IR Cut Dropdown Menu
    ircut_options = {
        "D2 - IRCut": "0",
        "D2 - IRPass": "1",
        "D3 - VIS Filter": "0",
        "D3 - Astro Filter": "1",
        "D3 - DUAL Band": "2"
    }
    
    ircut_label = tk.Label(scrollable_frame, text="Filter")
    ircut_label.pack(pady=5)
    ircut_var = tk.StringVar()
    ircut_dropdown = ttk.Combobox(scrollable_frame, textvariable=ircut_var)
    ircut_dropdown['values'] = list(ircut_options.keys())
    ircut_dropdown.pack(pady=5)
    settings_vars["IRCut"] = ircut_var

    # Add button to fetch Stellarium data
    fetch_stellarium_button = tk.Button(scrollable_frame, text="Fetch Stellarium Data", command=lambda: refresh_stellarium_data(settings_vars))
    fetch_stellarium_button.pack(pady=10)

    # Button to calculate session end time
    calculate_end_button = tk.Button(scrollable_frame, text="Calculate End Time", command=lambda: calculate_end_time(settings_vars))
    calculate_end_button.pack(pady=10)

    # Save button to save the session data
    save_button = tk.Button(scrollable_frame, text="Save", command=lambda: save_to_json(settings_vars))
    save_button.pack(pady=20)
