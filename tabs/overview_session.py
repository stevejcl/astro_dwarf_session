import os
import json
import shutil
import tkinter as tk
from tkinter import messagebox

from astro_dwarf_scheduler import LIST_ASTRO_DIR_DEFAULT

def overview_session_tab(parent_frame):
    """Initializes the session overview tab."""
    # JSON session management section
    json_label = tk.Label(parent_frame, text="Available Sessions:", font=("Arial", 12))
    json_label.pack(pady=5)
    
    # Listbox to show available JSON files
    json_listbox = tk.Listbox(parent_frame, height=13, selectmode=tk.EXTENDED)
    json_listbox.pack(fill=tk.BOTH, padx=10, pady=5)
    json_listbox.bind('<<ListboxSelect>>', lambda event: on_json_select(event, json_listbox, json_text))
    
    # Text area to display JSON file content
    json_text = tk.Text(parent_frame, height=24, state=tk.DISABLED)
    json_text.pack(fill=tk.BOTH, padx=10, pady=5)
    
    # Button to select the session
    select_button = tk.Button(parent_frame, text="Select Session", command=lambda: select_session(json_listbox, json_text, select_button), state=tk.NORMAL)
    select_button.pack(pady=20)
    
    # Button to refresh the JSON list
    refresh_button = tk.Button(parent_frame, text="Refresh JSON List", command=lambda: populate_json_list(json_listbox))
    refresh_button.pack(pady=5)

    # Populate JSON list
    populate_json_list(json_listbox)

def populate_json_list(json_listbox):
    """Populates the listbox with JSON files from the Astro_Sessions folder."""
    json_listbox.delete(0, tk.END)
    try:
        for filename in os.listdir(LIST_ASTRO_DIR_DEFAULT["SESSIONS_DIR"]):
            if filename.endswith('.json'):
               json_listbox.insert(tk.END, filename)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load JSON files: {e}")

def on_json_select(event, json_listbox, json_text):
    """Triggered when a JSON file is selected, and displays its content."""
    selection = json_listbox.curselection()
    if selection:
        # Get the last selected item
        last_selected_index = selection[-1]
        selected_file = json_listbox.get(last_selected_index)
        filepath = os.path.join(LIST_ASTRO_DIR_DEFAULT["SESSIONS_DIR"], selected_file)
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
        json_text.insert(tk.END, f"  IRCut: {setup_camera.get('IRCut', 'N/A')}\n")
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
        for index in selection:
            selected_file = json_listbox.get(index)
            source_path = os.path.join(LIST_ASTRO_DIR_DEFAULT["SESSIONS_DIR"], selected_file)
            destination_path = os.path.join(LIST_ASTRO_DIR["TODO_DIR"], selected_file)
            
            try:
                # Move the file to the ToDo directory
                shutil.move(source_path, destination_path)
                print(f"Moved {selected_file} to ToDo folder.")

            except Exception as e:
                print(f"Error moving file {selected_file}: {e}")

        # Refresh the listbox after moving all files
        populate_json_list(json_listbox)

        # Clear the text area and disable the select button
        json_text.config(state=tk.NORMAL)
        json_text.delete(1.0, tk.END)
        json_text.config(state=tk.DISABLED)
        select_button.config(state=tk.NORMAL)

