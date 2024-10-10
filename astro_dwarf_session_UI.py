import os
import json
import shutil
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
from astro_dwarf_scheduler import check_and_execute_commands, start_connection, start_STA_connection
from dwarf_ble_connect.connect_bluetooth import connect_bluetooth
from dwarf_python_api.lib.dwarf_utils import perform_disconnect
import logging
import dwarf_python_api.lib.my_logger as log
from dwarf_python_api.lib.my_logger import NOTICE_LEVEL_NUM

from tabs import settings
from tabs import create_session

# Directories
TODO_DIR = './Astro_Sessions/ToDo'
CURRENT_DIR = './Astro_Sessions/Current'
DONE_DIR = './Astro_Sessions/Done'
ERROR_DIR = './Astro_Sessions/Error'
CONFIG_FILE = 'config.ini'

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
        self.geometry("600x600")
        
        # Create tabs
        self.tab_control = ttk.Notebook(self)
        self.tab_control.pack(expand=1, fill="both")
        
        self.tab_main = ttk.Frame(self.tab_control)
        self.tab_settings = ttk.Frame(self.tab_control)
        self.tab_session = ttk.Frame(self.tab_control)
        self.tab_create_session = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.tab_main, text="Main")
        self.tab_control.add(self.tab_settings, text="Settings")
        self.tab_control.add(self.tab_session, text="Session Overview")
        self.tab_control.add(self.tab_create_session, text="Create Session")
        
        self.create_main_tab()
        self.settings_vars = {}
        settings.create_settings_tab(self.tab_settings, self.settings_vars) 
        self.overview_session_tab()
        create_session.create_session_tab(self.tab_create_session, self.settings_vars)

        self.result = False
        self.stellarium_connection = None
        self.scheduler_running = False
        self.scheduler_stopped = True
        self.protocol("WM_DELETE_WINDOW", self.quit_method)

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
        if self.scheduler_running:
            self.log("Waiting Closing Scheduler...")
            self.stop_scheduler()
        
            self.countdown(20)

        else:
            self.after(3000, self.destroy)

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
 
    def create_main_tab(self):
        # Bluetooth connection prompt label
        self.label1 = tk.Label(self.tab_main, text="Dwarf connection", font=("Arial", 12))
        self.label1.pack(anchor="w", padx=10, pady=10)
        self.label2 = tk.Label(self.tab_main, text="Do you want to start the Bluetooth connection?", font=("Arial", 10))
        self.label2.pack(anchor="w", padx=10, pady=10)

        # Tooltip for Bluetooth connection prompt
        Tooltip(self.label2, "Select Yes to open the Webbrowser for Bluetooth connection or No to skip the connection.")

        # Frame for Bluetooth connection buttons
        bluetooth_frame = tk.Frame(self.tab_main)
        bluetooth_frame.pack(anchor="w", padx=10, pady=5)
        
        self.button_yes = tk.Button(bluetooth_frame, text="Yes", command=self.start_bluetooth, width=10)
        self.button_yes.grid(row=0, column=0, padx=5)
        
        self.button_no = tk.Button(bluetooth_frame, text="No", command=self.skip_bluetooth, width=10)
        self.button_no.grid(row=0, column=1, padx=5)
        
        # Frame for Start/Stop Scheduler buttons
        self.label3 = tk.Label(self.tab_main, text="Scheduler", font=("Arial", 10))
        self.label3.pack(anchor="w", padx=10, pady=10)

        scheduler_frame = tk.Frame(self.tab_main)
        scheduler_frame.pack(anchor="w", padx=10, pady=10)
        
        self.start_button = tk.Button(scheduler_frame, text="Start Scheduler", command=self.start_scheduler, state=tk.DISABLED, width=15)
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = tk.Button(scheduler_frame, text="Stop Scheduler", command=self.stop_scheduler, state=tk.DISABLED, width=15)
        self.stop_button.grid(row=0, column=1, padx=5)
        
        # Log text area
        self.log_text = tk.Text(self.tab_main, wrap=tk.WORD, height=15)
        self.log_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    def overview_session_tab(self):  
        # JSON session management section
        self.json_label = tk.Label(self.tab_session, text="Available Sessions:", font=("Arial", 12))
        self.json_label.pack(pady=5)
    
        # Listbox to show available JSON files
        self.json_listbox = tk.Listbox(self.tab_session, height=6)
        self.json_listbox.pack(fill=tk.BOTH, padx=10, pady=5)
        self.json_listbox.bind('<<ListboxSelect>>', self.on_json_select)
    
        # Text area to display JSON file content
        self.json_text = tk.Text(self.tab_session, height=10, state=tk.DISABLED)
        self.json_text.pack(fill=tk.BOTH, padx=10, pady=5)
    
        # Button to select the session
        self.select_button = tk.Button(self.tab_session, text="Select Session", command=self.select_session, state=tk.DISABLED)
        self.select_button.pack(pady=20)
    
        # Button to refresh the JSON list
        self.refresh_button = tk.Button(self.tab_session, text="Refresh JSON List", command=self.populate_json_list)
        self.refresh_button.pack(pady=5)

        # Populate JSON list
        self.populate_json_list()  
    
    def populate_json_list(self):
        """Populates the listbox with JSON files from the Astro_Sessions folder."""
        self.json_listbox.delete(0, tk.END)
        try:
            for filename in os.listdir('./Astro_Sessions'):
                if filename.endswith('.json'):
                   self.json_listbox.insert(tk.END, filename)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load JSON files: {e}")
    
    def on_json_select(self, event):
        """Triggered when a JSON file is selected, and displays its content."""
        selection = self.json_listbox.curselection()
        if selection:
            selected_file = self.json_listbox.get(selection[0])
            filepath = os.path.join('./Astro_Sessions', selected_file)
            
            # Load and display the selected JSON file content
            self.display_json_content(filepath)
    
            # Enable the Select Session button
            self.select_button.config(state=tk.NORMAL)
    
    def display_json_content(self, filepath):
        """Displays the content of the selected JSON file in the text area."""
        with open(filepath, 'r') as file:
            data = json.load(file)

        self.json_text.config(state=tk.NORMAL)
        self.json_text.delete(1.0, tk.END)

        # Extract 'id_command' details
        id_command = data['command']['id_command']
        description = id_command.get('description', 'N/A')
        date = id_command.get('date', 'N/A')
        time_ = id_command.get('time', 'N/A')

        # Insert description, date, and time
        self.json_text.insert(tk.END, f"Description: {description}\n")
        self.json_text.insert(tk.END, f"Date: {date}\n")
        self.json_text.insert(tk.END, f"Time: {time_}\n")

        # Now check each action and display details if 'do_action' is True
        command = data['command']

        # Calibration
        if command.get('calibration', {}).get('do_action', False):
            self.json_text.insert(tk.END, "\nCalibration:\n")
            self.json_text.insert(tk.END, f"  Wait Before: {command['calibration'].get('wait_before', 'N/A')}\n")
            self.json_text.insert(tk.END, f"  Wait After: {command['calibration'].get('wait_after', 'N/A')}\n")

        # Goto Solar
        if command.get('goto_solar', {}).get('do_action', False):
            self.json_text.insert(tk.END, "\nGoto Solar:\n")
            self.json_text.insert(tk.END, f"  Target: {command['goto_solar'].get('target', 'N/A')}\n")
            self.json_text.insert(tk.END, f"  Wait After: {command['goto_solar'].get('wait_after', 'N/A')}\n")

        # Goto Manual
        if command.get('goto_manual', {}).get('do_action', False):
            self.json_text.insert(tk.END, "\nGoto Manual:\n")
            self.json_text.insert(tk.END, f"  Target: {command['goto_manual'].get('target', 'N/A')}\n")
            self.json_text.insert(tk.END, f"  RA Coord: {command['goto_manual'].get('ra_coord', 'N/A')}\n")
            self.json_text.insert(tk.END, f"  Dec Coord: {command['goto_manual'].get('dec_coord', 'N/A')}\n")
            self.json_text.insert(tk.END, f"  Wait After: {command['goto_manual'].get('wait_after', 'N/A')}\n")

        # Setup Camera
        if command.get('setup_camera', {}).get('do_action', False):
            self.json_text.insert(tk.END, "\nSetup Camera:\n")
            setup_camera = command['setup_camera']
            self.json_text.insert(tk.END, f"  Exposure: {setup_camera.get('exposure', 'N/A')}\n")
            self.json_text.insert(tk.END, f"  Gain: {setup_camera.get('gain', 'N/A')}\n")
            self.json_text.insert(tk.END, f"  Binning: {setup_camera.get('binning', 'N/A')}\n")
            self.json_text.insert(tk.END, f"  IRCut: {setup_camera.get('IRCut', 'N/A')}\n")
            self.json_text.insert(tk.END, f"  Count: {setup_camera.get('count', 'N/A')}\n")
            self.json_text.insert(tk.END, f"  Wait After: {setup_camera.get('wait_after', 'N/A')}\n")

        self.json_text.config(state=tk.DISABLED)
    
    def select_session(self):
        """Moves the selected JSON file to the ToDo folder."""
        selection = self.json_listbox.curselection()
        if selection:
            selected_file = self.json_listbox.get(selection[0])
            source_path = os.path.join('./Astro_Sessions', selected_file)
            destination_path = os.path.join(TODO_DIR, selected_file)
            
            try:
                # Move the file to the ToDo directory
                shutil.move(source_path, destination_path)
                self.log(f"Moved {selected_file} to ToDo folder.")
    
                # Refresh the listbox
                self.populate_json_list()
                
                # Clear the text area and disable the select button
                self.json_text.config(state=tk.NORMAL)
                self.json_text.delete(1.0, tk.END)
                self.json_text.config(state=tk.DISABLED)
                self.select_button.config(state=tk.DISABLED)
    
            except Exception as e:
                self.log(f"Error moving file: {e}")



    def start_bluetooth(self):
        self.log("Starting Bluetooth connection in a separate thread...")
        threading.Thread(target=self.bluetooth_connect_thread).start()

    def bluetooth_connect_thread(self):
        try:
            self.result = start_connection()
            if self.result:
                self.log("Bluetooth connected successfully.")
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
        self.start_button.config(state=tk.NORMAL)

    def start_scheduler(self):
        if not self.scheduler_running:
            self.scheduler_running = True
            self.start_logHandler()
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.log("Astro_Dwarf_Scheduler is starting...")
            self.scheduler_thread = threading.Thread(target=self.run_scheduler)
            self.scheduler_thread.start()

    def stop_scheduler(self):
        self.stop_logHandler()
        if self.scheduler_running:
            self.scheduler_running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.verifyCountdown(15)
            self.log("Scheduler is stopping...")
        else:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.log("Scheduler is stopped")

    def verifyCountdown(self, wait):
        '''
        verifyCountdown that checks scheduler status and waits for stop or timeout
        '''
        if self.scheduler_stopped:
            self.log("Scheduler stopped.")
        elif wait > 0:
            # Schedule the verifyCountdown to run again after 1 second
            self.after(1000, self.verifyCountdown, wait - 1)
        else:
            self.log("Time's up! Closing now...")
            self.after(500, perform_disconnect())
 

    def run_scheduler(self):
        try:
            self.scheduler_stopped = False
            attempt = 0
            result = False
            while not result and attempt < 3 and self.scheduler_running:
                attempt += 1
                result = start_STA_connection()
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
