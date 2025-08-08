import os
import json
import shutil
import tkinter as tk
from tkinter import messagebox
import re

from astro_dwarf_scheduler import LIST_ASTRO_DIR_DEFAULT

def overview_session_tab(parent_frame, refresh_setter=None):
    """Initializes the session overview tab. Optionally registers a refresh function for external use."""
    # Use grid layout for resizable content and sticky buttons
    parent_frame.grid_rowconfigure(1, weight=0)  # label
    parent_frame.grid_rowconfigure(2, weight=0)  # listbox
    parent_frame.grid_rowconfigure(3, weight=1)  # text area (expandable)
    parent_frame.grid_rowconfigure(4, weight=0)  # buttons
    parent_frame.grid_columnconfigure(0, weight=1)

    # JSON session management section
    json_label = tk.Label(parent_frame, text="Available Sessions:", font=("Arial", 12))
    json_label.grid(row=1, column=0, sticky="ew", pady=(5,0))
    # Listbox to show available JSON files
    json_listbox = tk.Listbox(parent_frame, height=13, selectmode=tk.EXTENDED)
    json_listbox.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
    # Text area to display JSON file content (resizable)
    json_text = tk.Text(parent_frame, state=tk.DISABLED)
    json_text.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
    json_listbox.bind('<<ListboxSelect>>', lambda event: on_json_select(event, json_listbox, json_text))
    # Bind double-click to select_session
    json_listbox.bind('<Double-Button-1>', lambda event: select_session(json_listbox, json_text, select_button))
    # --- Place Select Session and Refresh JSON List buttons on the same line, always at the bottom ---
    button_frame = tk.Frame(parent_frame)
    button_frame.grid(row=4, column=0, sticky="ew", pady=10)
    # Center the buttons using an internal frame with pack and expand
    inner_button_frame = tk.Frame(button_frame)
    inner_button_frame.pack(expand=True)
    select_button = tk.Button(inner_button_frame, text="Select Session", command=lambda: select_session(json_listbox, json_text, select_button), state=tk.NORMAL)
    select_button.pack(side="left", padx=(0, 10))
    def refresh_json_list():
        populate_json_list(json_listbox)
    refresh_button = tk.Button(inner_button_frame, text="Refresh JSON List", command=refresh_json_list)
    refresh_button.pack(side="left")
    # Populate JSON list
    refresh_json_list()
    # Register the refresh function for external use
    if refresh_setter is not None:
        refresh_setter(refresh_json_list)
    return refresh_json_list

def populate_json_list(json_listbox):
    """Populates the listbox with JSON files from the Astro_Sessions folder."""
    json_listbox.delete(0, tk.END)
    
    def natural_sort_key(text):
        """Convert a string into a list of mixed strings and integers for natural sorting."""
        return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]
    
    # Helper to get sorted files by uuid
    def get_json_files_sorted_by_uuid(directory):
        files_with_uuid = []
        if os.path.exists(directory):
            for fname in os.listdir(directory):
                if fname.endswith('.json'):
                    fpath = os.path.join(directory, fname)
                    try:
                        with open(fpath, 'r') as f:
                            data = json.load(f)
                        uuid = data.get('command', {}).get('id_command', {}).get('uuid', '')
                    except Exception:
                        uuid = ''
                    files_with_uuid.append((uuid, fname))
            files_with_uuid.sort(key=lambda x: (x[0] == '', natural_sort_key(x[0])))
        return [fname for uuid, fname in files_with_uuid]

    # Get files from all session subdirectories
    from astro_dwarf_scheduler import LIST_ASTRO_DIR
    sessions_dir = LIST_ASTRO_DIR_DEFAULT["SESSIONS_DIR"]
    subdirs = {
        'main': {'path': sessions_dir, 'label': '', 'color': 'black', 'font': None},
        'ToDo': {'path': LIST_ASTRO_DIR["TODO_DIR"], 'label': ' [ToDo]', 'color': 'blue', 'font': None},
        'Current': {'path': os.path.join(sessions_dir, 'Current'), 'label': ' [Current]', 'color': 'purple', 'font': None},
        'Done': {'path': os.path.join(sessions_dir, 'Done'), 'label': ' [Done]', 'color': 'green', 'font': None},
        'Error': {'path': os.path.join(sessions_dir, 'Error'), 'label': ' [Error]', 'color': 'red', 'font': None},
        'Results': {'path': os.path.join(sessions_dir, 'Results'), 'label': ' [Results]', 'color': 'gray', 'font': None},
    }
    files_with_origin = []
    for key, info in subdirs.items():
        dirpath = info['path']
        label = info['label']
        if os.path.exists(dirpath):
            for fname in os.listdir(dirpath):
                if fname.endswith('.json'):
                    fpath = os.path.join(dirpath, fname)
                    try:
                        with open(fpath, 'r') as f:
                            data = json.load(f)
                        uuid = data.get('command', {}).get('id_command', {}).get('uuid', '')
                    except Exception:
                        uuid = ''
                    files_with_origin.append((uuid, fname, dirpath, label, info['color'], info['font']))
    # Sort all by uuid (empty uuid last) with natural sorting
    files_with_origin.sort(key=lambda x: (x[0] == '', natural_sort_key(x[0])))
    # Insert into listbox and build mapping
    json_listbox.file_origin_map = {}
    for uuid, fname, dirpath, label, color, font in files_with_origin:
        display_name = fname + label
        json_listbox.insert(tk.END, display_name)
        if font:
            json_listbox.itemconfig(tk.END, foreground=color, font=font)
        else:
            json_listbox.itemconfig(tk.END, foreground=color)
        json_listbox.file_origin_map[display_name] = (dirpath, fname)

def on_json_select(event, json_listbox, json_text):
    """Triggered when a JSON file is selected, and displays its content."""
    selection = json_listbox.curselection()
    if selection:
        # Get the last selected item
        last_selected_index = selection[-1]
        selected_file = json_listbox.get(last_selected_index)
        # Determine origin
        file_origin_map = getattr(json_listbox, 'file_origin_map', {})
        if selected_file in file_origin_map:
            dirpath, fname = file_origin_map[selected_file]
            filepath = os.path.join(dirpath, fname)
            display_json_content(filepath, json_text)

def display_json_content(filepath, json_text):
    """Displays the content of the selected JSON file in the text area."""
    with open(filepath, 'r') as file:
        data = json.load(file)

    json_text.config(state=tk.NORMAL)
    json_text.delete(1.0, tk.END)
    # Extract 'id_command' details
    id_command = data['command']['id_command']
    description = id_command.get('description', 'N/A')
    date = id_command.get('date', 'N/A')
    time_ = id_command.get('time', 'N/A')
    status_ = id_command.get('process', 'N/A')
    # Insert description, date, and time
    json_text.insert(tk.END, f"Description: {description}\n")
    json_text.insert(tk.END, f"Date: {date}\n")
    json_text.insert(tk.END, f"Time: {time_}\n")
    json_text.insert(tk.END, f"Process: {status_}\n")
    # Now check each action and display details if 'do_action' is True
    command = data['command']
    # EQ Solving
    if command.get('eq_solving', {}).get('do_action', False):
        json_text.insert(tk.END, "\nEQ Solving:\n")
        json_text.insert(tk.END, f"  Wait Before: {command['eq_solving'].get('wait_before', 'N/A')}\n")
        json_text.insert(tk.END, f"  Wait After: {command['eq_solving'].get('wait_after', 'N/A')}\n")
    # Autofocus
    if command.get('auto_focus', {}).get('do_action', False):
        json_text.insert(tk.END, "\nAuto focus:\n")
        json_text.insert(tk.END, f"  Wait Before: {command['auto_focus'].get('wait_before', 'N/A')}\n")
        json_text.insert(tk.END, f"  Wait After: {command['auto_focus'].get('wait_after', 'N/A')}\n")
    # infinite_focus
    if command.get('infinite_focus', {}).get('do_action', False):
        json_text.insert(tk.END, "\nInfinite focus:\n")
        json_text.insert(tk.END, f"  Wait Before: {command['infinite_focus'].get('wait_before', 'N/A')}\n")
        json_text.insert(tk.END, f"  Wait After: {command['infinite_focus'].get('wait_after', 'N/A')}\n")
    # Calibration
    if command.get('calibration', {}).get('do_action', False):
        json_text.insert(tk.END, "\nCalibration:\n")
        json_text.insert(tk.END, f"  Wait Before: {command['calibration'].get('wait_before', 'N/A')}\n")
        json_text.insert(tk.END, f"  Wait After: {command['calibration'].get('wait_after', 'N/A')}\n")
    # Goto Solar
    if command.get('goto_solar', {}).get('do_action', False):
        json_text.insert(tk.END, "\nGoto Solar:\n")
        json_text.insert(tk.END, f"  Target: {command['goto_solar'].get('target', 'N/A')}\n")
        json_text.insert(tk.END, f"  Wait After: {command['goto_solar'].get('wait_after', 'N/A')}\n")
    # Goto Manual
    if command.get('goto_manual', {}).get('do_action', False):
        json_text.insert(tk.END, "\nGoto Manual:\n")
        json_text.insert(tk.END, f"  Target: {command['goto_manual'].get('target', 'N/A')}\n")
        json_text.insert(tk.END, f"  RA Coord: {command['goto_manual'].get('ra_coord', 'N/A')}\n")
        json_text.insert(tk.END, f"  Dec Coord: {command['goto_manual'].get('dec_coord', 'N/A')}\n")
        json_text.insert(tk.END, f"  Wait After: {command['goto_manual'].get('wait_after', 'N/A')}\n")
    # Setup Camera
    if command.get('setup_camera', {}).get('do_action', False):
        json_text.insert(tk.END, "\nSetup Camera:\n")
        setup_camera = command['setup_camera']
        json_text.insert(tk.END, f"  Exposure: {setup_camera.get('exposure', 'N/A')}\n")
        json_text.insert(tk.END, f"  Gain: {setup_camera.get('gain', 'N/A')}\n")
        json_text.insert(tk.END, f"  Binning: {setup_camera.get('binning', 'N/A')}\n")
        json_text.insert(tk.END, f"  IRCut: {setup_camera.get('ircut', 'N/A')}\n")
        json_text.insert(tk.END, f"  Count: {setup_camera.get('count', 'N/A')}\n")
        json_text.insert(tk.END, f"  Wait After: {setup_camera.get('wait_after', 'N/A')}\n")
    
    if command.get('setup_wide_camera', {}).get('do_action', False):
        json_text.insert(tk.END, "\nSetup Wide-Angle Camera:\n")
        setup_wide_camera = command['setup_wide_camera']
        json_text.insert(tk.END, f"  Exposure: {setup_wide_camera.get('exposure', 'N/A')}\n")
        json_text.insert(tk.END, f"  Gain: {setup_wide_camera.get('gain', 'N/A')}\n")
        json_text.insert(tk.END, f"  Count: {setup_wide_camera.get('count', 'N/A')}\n")
        json_text.insert(tk.END, f"  Wait After: {setup_wide_camera.get('wait_after', 'N/A')}\n")
    json_text.config(state=tk.DISABLED)

def select_session(json_listbox, json_text, select_button):
    # import directories
    from astro_dwarf_scheduler import LIST_ASTRO_DIR

    """Moves the selected JSON files to the ToDo folder."""

    selection = json_listbox.curselection()
    if selection:
        file_origin_map = getattr(json_listbox, 'file_origin_map', {})
        for index in selection:
            selected_file = json_listbox.get(index)
            if selected_file in file_origin_map:
                dirpath, fname = file_origin_map[selected_file]
                dir_base = os.path.basename(dirpath)
                # If file is in ToDo, Done, or Error, move it back to parent dir and reset values
                if dir_base in ("ToDo", "Done", "Error"):
                    parent_dir = os.path.dirname(dirpath)
                    dest_path = os.path.join(parent_dir, fname)
                    source_path = os.path.join(dirpath, fname)
                    try:
                        # Load the JSON data before moving
                        with open(source_path, 'r') as f:
                            data = json.load(f)
                        
                        # Reset the session values (same as "Reset Session State" button)
                        id_cmd = data['command']['id_command']
                        id_cmd['process'] = 'wait'
                        id_cmd['result'] = False
                        id_cmd['message'] = ''
                        id_cmd['nb_try'] = 1
                        
                        # Save the modified data to the destination
                        with open(dest_path, 'w') as f:
                            json.dump(data, f, indent=4)
                        
                        # Remove the original file
                        os.remove(source_path)
                        
                        print(f"Moved {fname} back to {parent_dir} and reset session state.")
                    except Exception as e:
                        print(f"Error moving and resetting file {fname}: {e}")
                        # Try to move without reset if JSON modification fails
                        try:
                            shutil.move(source_path, dest_path)
                            print(f"Moved {fname} back to {parent_dir} (without reset).")
                        except Exception as move_error:
                            print(f"Error moving file {fname}: {move_error}")
                else:
                    # Move file to ToDo as before
                    from astro_dwarf_scheduler import LIST_ASTRO_DIR
                    source_path = os.path.join(dirpath, fname)
                    destination_path = os.path.join(LIST_ASTRO_DIR["TODO_DIR"], fname)
                    try:
                        shutil.move(source_path, destination_path)
                        print(f"Moved {fname} to ToDo folder.")
                    except Exception as e:
                        print(f"Error moving file {fname}: {e}")
        # Refresh the listbox after moving all files
        populate_json_list(json_listbox)
        # Clear the text area and disable the select button
        json_text.config(state=tk.NORMAL)
        json_text.delete(1.0, tk.END)
        json_text.config(state=tk.DISABLED)
        select_button.config(state=tk.NORMAL)

