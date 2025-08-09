import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
import json
import os
import csv
from datetime import datetime, timedelta

# Directories
TIME_CHANGE_DAY = 18

# Define columns to display in Treeviews
columns_OK = ["Description", "Dwarf", "Starting", "Ending", 
           "Calibration", "Goto", "Target", 
           "RA", "Dec", "Lens", 
           "exposure", "gain", "IR", "count"]
columns_KO = ["Description", "Dwarf", "Starting", "Ending", 
           "Message", "Calibration", "Goto", "Target", 
           "RA", "Dec", "Lens", 
           "exposure", "gain", "IR", "count"]

def autosize_columns(treeview, padding, max_width_col = 0):
    for col in treeview["columns"]:
        max_width = tk.font.Font().measure(col)  # Start with the width of the header

        # Check each row to find the maximum width in the column
        for item in treeview.get_children():
            cell_value = treeview.set(item, col)
            cell_width = tkFont.Font().measure(cell_value)
            max_width = max(max_width, cell_width)

        if max_width_col !=0:
            max_width = min(max_width, max_width_col)
 
        # Set the column width based on the maximum width found
        treeview.column(col, width=max_width + padding)  # Add padding

def result_session_tab(parent_frame):

    # Top frame for combobox and refresh button
    top_frame = ttk.Frame(parent_frame)
    top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(20, 10))

    combobox_label = ttk.Label(top_frame, text="Select Observation File:")
    combobox_label.pack(side=tk.LEFT, padx=(0, 5))

    combobox = ttk.Combobox(top_frame, state="readonly")
    combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # Table frame for displaying OK and Error sessions
    table_frame = ttk.Frame(parent_frame)
    table_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=0)

    # OK Treeview
    ok_frame = ttk.Frame(table_frame)
    ok_frame.pack(fill=tk.BOTH, expand=True)

    ok_label = ttk.Label(ok_frame, text="Sessions OK")
    ok_label.pack()

    ok_treeview = ttk.Treeview(ok_frame, columns=columns_OK, show='headings', height=10)
    default_width = 100
    for col in columns_OK:
        ok_treeview.heading(col, text=col)
        ok_treeview.column(col, anchor="center", width=default_width)
    ok_treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Error Treeview
    error_frame = ttk.Frame(table_frame)
    error_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    error_label = ttk.Label(error_frame, text="Error Sessions")
    error_label.pack()

    error_treeview = ttk.Treeview(error_frame, columns=columns_KO, show='headings', height=10)
    for col in columns_KO:
        error_treeview.heading(col, text=col)
        error_treeview.column(col, anchor="center")
    error_treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # init results
    refresh_observation_list(combobox, ok_treeview, error_treeview)

    # Closure function for refreshing
    def refresh():
        refresh_observation_list(combobox, ok_treeview, error_treeview)


    def delete_selected_file():
        selected_file = combobox.get()
        if not selected_file:
            return
        from astro_dwarf_scheduler import LIST_ASTRO_DIR
        RESULTS_DIR = LIST_ASTRO_DIR["SESSIONS_DIR"] + '/Results'
        file_path = os.path.join(RESULTS_DIR, selected_file)
        if os.path.exists(file_path):
            import tkinter.messagebox as messagebox
            if messagebox.askyesno("Delete File", f"Are you sure you want to delete '{selected_file}'?"):
                try:
                    os.remove(file_path)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not delete file: {e}")
        refresh()

    update_button = ttk.Button(top_frame, text="Update Results", command=lambda: refresh())
    update_button.pack(side=tk.LEFT, padx=(10, 5))
    delete_button = ttk.Button(top_frame, text="Delete File", command=delete_selected_file)
    delete_button.pack(side=tk.LEFT, padx=5)

    # Autosize the columns based on the content
    padding = 1
    max_width_col = 40
    autosize_columns(ok_treeview, padding, max_width_col)
    padding = 1
    max_width_col = 40
    autosize_columns(error_treeview, padding, max_width_col)

    combobox.bind("<<ComboboxSelected>>", lambda event: on_file_select(event, combobox, ok_treeview, error_treeview))

    return refresh

def get_observation_files():
    from astro_dwarf_scheduler import LIST_ASTRO_DIR

    # Directories
    RESULTS_DIR = LIST_ASTRO_DIR["SESSIONS_DIR"] + '/Results'

    files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.csv')]
    files.sort(reverse=True)
    return files

def load_csv_data(filename):
    from astro_dwarf_scheduler import LIST_ASTRO_DIR

    # Directories
    RESULTS_DIR = LIST_ASTRO_DIR["SESSIONS_DIR"] + '/Results'

    ok_data = []
    error_data = []
    with open(os.path.join(RESULTS_DIR, filename), newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            row["Description"] = row.get("description")
            row["Dwarf"] = row.get("dwarf")
            row["Starting"] = row.get("starting_date")[11:]
            row["Ending"] = row.get("processed_date")[11:]
            row["Calibration"] = "Done" if row.get("calibration") == "True" else ""
            if row.get("goto_solar") == "True" :
                row["Goto"] = "Solar"
            elif row.get("goto_manual") == "True" :
                row["Goto"] = "Manual"
            else:
                row["Goto"] = ""
            row["Target"] = row.get("target")
            row["RA"] = row.get("ra_coord")
            row["Dec"] = row.get("dec_coord")
            if row.get("Tele Astro") == "True" :
                row["Lens"] = "Tele"
            elif row.get("Wide Angle") == "True" :
                row["Lens"] = "Wide"
            else:
                row["Lens"] = ""
            if row.get("dwarf") == "D2" :
                row["IR"] = "Cut" if row.get("IR") == "0" else "Pass"
            else:
                if row.get("IR") == "0":
                    row["IR"] = "VIS"
                elif row.get("IR") == "1":
                    row["IR"] = "ASTRO"
                else:
                    row["IR"] = "DUO B."
            if row.get("count") == "0":
                row["Lens"] = ""
                row["count"] = ""
                row["exposure"] = ""
                row["gain"] = ""
                row["IR"] = ""
            if row["result"] == "True":
                ok_data.append(row)
            else:
                row["Message"] = row["message"].replace("Error during execution: ", "").replace("Action failed at step: ", "Error: ")
                error_data.append(row)
    ok_data.sort(key=lambda x: x["starting_date"])
    error_data.sort(key=lambda x: x["starting_date"])
    return ok_data, error_data

def update_treeview(treeview, data, columns):
    treeview.delete(*treeview.get_children())
    for row in data:
        treeview.insert('', tk.END, values=[row[col] for col in columns])

def on_file_select(event, combobox, ok_treeview, error_treeview):
    selected_file = combobox.get()
    if selected_file:
        ok_data, error_data = load_csv_data(selected_file)
        update_treeview(ok_treeview, ok_data, columns_OK)
        update_treeview(error_treeview, error_data, columns_KO)

def refresh_observation_list(combobox, ok_treeview, error_treeview):
    analyze_files()

    # Load initial data
    files = get_observation_files()
    combobox['values'] = files
    if files:
        combobox.set(files[0])
        ok_data, error_data = load_csv_data(files[0])
        update_treeview(ok_treeview, ok_data, columns_OK)
        update_treeview(error_treeview, error_data, columns_KO)
    else:
        combobox.set("")  # Clear the combobox
        # Clear the treeviews and display only column headers
        update_treeview(ok_treeview, [], columns_OK)
        update_treeview(error_treeview, [], columns_KO)

# Function to load already processed filenames
def load_processed_files():
    from astro_dwarf_scheduler import LIST_ASTRO_DIR

    RESULTS_LIST_PATH = os.path.join(LIST_ASTRO_DIR["SESSIONS_DIR"], 'results_list.txt')

    if os.path.exists(RESULTS_LIST_PATH):
        with open(RESULTS_LIST_PATH, 'r') as file:
            return set(line.strip() for line in file.readlines())
    return set()

# Function to save processed filename
def save_processed_file(filename):
    from astro_dwarf_scheduler import LIST_ASTRO_DIR

    RESULTS_LIST_PATH = os.path.join(LIST_ASTRO_DIR["SESSIONS_DIR"], 'results_list.txt')

    with open(RESULTS_LIST_PATH, 'a') as file:
        file.write(filename + '\n')

def get_observation_night(starting_date):
    """Determine the observation night for a given date and time."""
    observation_datetime = datetime.strptime(starting_date, '%Y-%m-%d %H:%M:%S')
    if observation_datetime.hour < TIME_CHANGE_DAY:
        observation_datetime -= timedelta(days=1)  # Shift to the previous night
    observation_night = observation_datetime.strftime('%Y-%m-%d')
    return observation_night

# Function to analyze JSON files and generate CSV
def analyze_files():
    from astro_dwarf_scheduler import LIST_ASTRO_DIR

    # Directories
    RESULTS_DIR = LIST_ASTRO_DIR["SESSIONS_DIR"] + '/Results'

    processed_files = load_processed_files()

    # Paths to Done and Error directories
    for status_dir in ['Done', 'Error']:
        dir_path = os.path.join(LIST_ASTRO_DIR["SESSIONS_DIR"], status_dir)
        if not os.path.exists(dir_path):
            continue

        for filename in os.listdir(dir_path):
            if filename in processed_files:
                continue  # Skip if already processed
            if not filename.endswith('.json'):
                continue  # Skip if not a JSON file
            if filename.startswith('.keep'):
                continue  # Skip if not a JSON file

            file_path = os.path.join(dir_path, filename)
            with open(file_path, 'r') as file:
                data = json.load(file)

            # Attempt to get starting_date from the JSON data
            starting_date = data["command"]["id_command"].get("starting_date")

            # If starting_date is not found, extract it from the filename
            if not starting_date:
                # Extract date and time from filename, e.g., "2024-10-20-17-29-45-Mosaic Pane 4.json"
                date_parts = filename.split('-')[:3]  # Get the first three parts for year, month, day
                time_parts = filename.split('-')[3:6]  # Get the next three parts for hours, minutes, seconds
                starting_date = '-'.join(date_parts) + ' ' + ':'.join(time_parts)  # Combine with time part
                # Strip any whitespace from starting_date
                starting_date = starting_date.strip()

                try:
                    # Convert to a datetime object to ensure the format is correct
                    datetime.strptime(starting_date, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    print(f"Invalid date format in filename: {filename}")
                    continue  # Skip this file if the date format is invalid

            typeDwarf = data["command"]["id_command"].get("dwarf")
            if not typeDwarf:
                typeDwarf = "-"

            observation_night = get_observation_night(starting_date)
    
            # Prepare the CSV data based on JSON content
            csv_data = {
                'id': data["command"]["id_command"]["uuid"],
                'description': data["command"]["id_command"]["description"],
                'dwarf': typeDwarf,
                'starting_date': starting_date,
                'processed_date': data["command"]["id_command"].get("processed_date", ""),
                'result': data["command"]["id_command"]["result"],
                'message': data["command"]["id_command"]["message"],
                'calibration': data["command"].get("calibration", {}).get("do_action", False),
                'goto_solar': data["command"].get("goto_solar", {}).get("do_action", False),
                'goto_manual': data["command"].get("goto_manual", {}).get("do_action", False),
                'target': data["command"].get("goto_manual", {}).get("target", ""),
                'ra_coord': data["command"].get("goto_manual", {}).get("ra_coord", ""),
                'dec_coord': data["command"].get("goto_manual", {}).get("dec_coord", ""),
                'Tele Astro': data["command"].get("setup_camera", {}).get("do_action", False),
                'Wide Angle': data["command"].get("setup_wide_camera", {}).get("do_action", False),
                'exposure': data["command"].get("setup_camera", {}).get("exposure", ""),
                'gain': data["command"].get("setup_camera", {}).get("gain", ""),
                'IR': data["command"].get("setup_camera", {}).get("IRCut", ""),
                'count': data["command"].get("setup_camera", {}).get("count", ""),
            }

            # Write to CSV file
            csv_filename = f'results_session_night_{observation_night}.csv'
            csv_filepath = os.path.join(RESULTS_DIR, csv_filename)
            write_to_csv(csv_filepath, csv_data)

            save_processed_file(filename)

# Helper function to write data to CSV
def write_to_csv(csv_path, csv_data):
    headers = csv_data.keys()
    file_exists = os.path.exists(csv_path)

    with open(csv_path, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow(csv_data)
