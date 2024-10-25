import os
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
from tabs import overview_session
from tabs import result_session

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
        self.geometry("600x800")
        
        # Create tabs
        self.tab_control = ttk.Notebook(self)
        self.tab_control.pack(expand=1, fill="both")
        
        self.tab_main = ttk.Frame(self.tab_control)
        self.tab_settings = ttk.Frame(self.tab_control)
        self.tab_overview_session = ttk.Frame(self.tab_control)
        self.tab_result_session = ttk.Frame(self.tab_control)
        self.tab_create_session = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.tab_main, text="Main")
        self.tab_control.add(self.tab_settings, text="Settings")
        self.tab_control.add(self.tab_overview_session, text="Session Overview")
        self.tab_control.add(self.tab_result_session, text="Results Session")
        self.tab_control.add(self.tab_create_session, text="Create Session")
        
        self.create_main_tab()
        self.settings_vars = {}
        self.config_vars = {}
        settings.create_settings_tab(self.tab_settings, self.config_vars) 
        overview_session.overview_session_tab(self.tab_overview_session)
        result_session.result_session_tab(self.tab_result_session)
        create_session.create_session_tab(self.tab_create_session, self.settings_vars, self.config_vars)

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
