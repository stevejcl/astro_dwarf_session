import configparser
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from geopy.geocoders import Nominatim
from geopy.geocoders import Photon
from timezonefinder import TimezoneFinder
from geopy.exc import GeocoderInsufficientPrivileges

CONFIG_FILE = 'config.ini'

def get_lat_long_and_timezone(address, agent = 1):
    try:
        # Initialize the geolocator with Nominatim
        if agent == 1:
            geolocator = Nominatim(user_agent="geoapiAstroSession")
        else: 
            geolocator = Photon(user_agent="geoapiAstroSession")

        #Get location based on the address
        location = geolocator.geocode(address)

        if not location:
            return None, None, None

        latitude = location.latitude
        longitude = location.longitude

        #Get the timezone using TimezoneFinder
        tf = TimezoneFinder()
        timezone_str = tf.timezone_at(lat=latitude, lng=longitude)

        return latitude, longitude, timezone_str

    except GeocoderInsufficientPrivileges as e:
        print(f"Error: {e} - You do not have permission to access this resource.")

        # Attempt to switch agent and retry
        if agent == 1:
            print("Switching to Photon geocoder for the next attempt.")
            return get_location_data(address, agent=2)  # Retry with the second agent
        else:
            messagebox.showinfo("Error", "Can't found your location data!")
            return None, None, None

    except Exception as e:
        print(f"Error: {e}")

        # Attempt to switch agent and retry
        if agent == 1:
            print("Switching to Photon geocoder for the next attempt.")
            return get_location_data(address, agent=2)  # Retry with the second agent
        else:
            messagebox.showinfo("Error", "Can't found your location data!")
            return None, None, None

def find_location(settings_vars):
    try:
        latitude, longitude, timezone_str = get_lat_long_and_timezone(settings_vars["address"].get())

        if latitude and longitude and timezone_str:
            settings_vars["latitude"].set(latitude)
            settings_vars["longitude"].set(longitude)
            settings_vars["timezone"].set(timezone_str)
        else:
            print("Location or timezone could not be determined.")
            messagebox.showinfo("Error", "Can't found your location data!")
    except Exception as e:
        print(f"Error: {e}")
        messagebox.showinfo("Error", "Can't found your location data!")

def open_link(url):
    webbrowser.open_new(url)

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
        ("Your Address", "address"),
        ("Help", "Find longitude and lattitude in Google Map by CTRL + Right Click"),
        ("Longitude", "longitude"),
        ("Latitude", "latitude"),
        ("Help", "The timezone value can be found here https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"),
        ("Timezone", "timezone"),
        ("BLE PSD", "ble_psd"),
        ("BLE STA SSID", "ble_sta_ssid"),
        ("BLE STA Password", "ble_sta_pwd"),
        ("Help", "Use to Connect to Stellarium, let them blank if you are using default config"),
        ("Stellarium IP", "stellarium_ip"),  # New field for Stellarium IP
        ("Stellarium Port", "stellarium_port"),  # New field for Stellarium Port
        ("Help", "The following values are the default values use in the Create Session Tabs"),
        ("Exposure", "exposure"),
        ("Gain", "gain"),
        ("Help IR Cut", "For D2 0: IR Cut 1: IR Pass  -  For D3 0: VIS  1: ASTRO 2: DUAL BAND."),
        ("IR Cut", "ircut"),
        ("Help Binning", "0: 4k 1: 2k"),
        ("Binning", "binning"),
        ("Count", "count")
    ]

    location_button = tk.Button(scrollable_frame, text="Find your location data from your address or Enter them manually", command=lambda: find_location(settings_vars))
    location_button.pack(pady=20)

    for field, key in settings_fields:
        row = tk.Frame(scrollable_frame)
        label = tk.Label(row, width=15, text=field, anchor='w')
        row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        label.pack(side=tk.LEFT)
        index = key.find("http")

        if not "Help" in field:
            var = tk.StringVar(value=config.get(key, ''))  # Load the value from config.ini
            entry = tk.Entry(row, textvariable=var)
            settings_vars[key] = var  # Store variable for later use
            entry.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)
        elif index != -1: # Create a label that looks like a hyperlink
            url = key[index:].strip()
            print (url)
            link_label = tk.Label(row, text=key[:index], fg="blue", cursor="hand2", anchor='w')
            link_label.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)

            # Make the text underlined
            link_label.config(font=("Arial", 12, "underline"))

            # Bind the click event to the open_link function
            link_label.bind("<Button-1>", lambda e: open_link(url))
        else:
            help_Label = tk.Label(row, width=60, text=key, anchor='w')
            help_Label.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)

    save_button = tk.Button(scrollable_frame, text="Save", command=lambda: save_settings(settings_vars))
    save_button.pack(pady=20)

def save_settings(settings_vars):
    config_data = {key: var.get() for key, var in settings_vars.items()}
    save_config(config_data)
    messagebox.showinfo("Settings", "Configuration saved successfully!")
