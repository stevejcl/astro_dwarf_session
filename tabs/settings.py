import configparser
import tkinter as tk
from tkinter import messagebox, ttk

CONFIG_FILE = 'config.ini'

# Load and save configuration settings from config.ini
def load_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return config['CONFIG']

def save_config(config_data):
    config = configparser.ConfigParser()
    config['CONFIG'] = config_data
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)

# Create the settings tab
def create_settings_tab(tab_settings, settings_vars):
    config = load_config()

    # Create a Canvas and a Scrollbar for the settings
    canvas = tk.Canvas(tab_settings)
    scrollbar = ttk.Scrollbar(tab_settings, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    settings_fields = [
        ("Longitude", "longitude"),
        ("Latitude", "latitude"),
        ("Timezone", "timezone"),
        ("Exposure", "exposure"),
        ("Gain", "gain"),
        ("IR Cut", "ircut"),
        ("Binning", "binning"),
        ("Format", "format"),
        ("Count", "count"),
        ("BLE WiFi Type", "ble_wifi_type"),
        ("BLE Auto AP", "ble_auto_ap"),
        ("BLE Country List", "ble_country_list"),
        ("BLE PSD", "ble_psd"),
        ("BLE Auto STA", "ble_auto_sta"),
        ("BLE STA SSID", "ble_sta_ssid"),
        ("BLE STA Password", "ble_sta_pwd"),
        ("BLE Country", "ble_country"),
        ("Stellarium IP", "stellarium_ip"),  # New field for Stellarium IP
        ("Stellarium Port", "stellarium_port")  # New field for Stellarium Port
    ]

    for field, key in settings_fields:
        row = tk.Frame(scrollable_frame)
        label = tk.Label(row, width=15, text=field, anchor='w')
        var = tk.StringVar(value=config.get(key, ''))  # Load the value from config.ini
        entry = tk.Entry(row, textvariable=var)
        settings_vars[key] = var  # Store variable for later use
        row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        label.pack(side=tk.LEFT)
        entry.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)

    save_button = tk.Button(scrollable_frame, text="Save", command=lambda: save_settings(settings_vars))
    save_button.pack(pady=20)

def save_settings(settings_vars):
    config_data = {key: var.get() for key, var in settings_vars.items()}
    save_config(config_data)
    messagebox.showinfo("Settings", "Configuration saved successfully!")
