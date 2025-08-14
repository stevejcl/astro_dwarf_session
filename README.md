# Astro Dwarf Scheduler

Astro Dwarf Scheduler is a tool designed to automate imaging sessions for Dwarf II and Dwarf III devices. It processes session files and executes them based on their scheduled time.

<img width="640" height="676" alt="image" src="https://github.com/user-attachments/assets/244615ba-f901-4fab-8f4a-157cc71c05d4" />

## Features
- Automates imaging sessions using JSON configuration files.
- Supports Bluetooth and Wi-Fi connections to Dwarf devices.
- Provides a GUI and console interface for managing sessions.

## Installation
1. Clone this repository:
   ```sh
   git clone <repository-url>
   cd astro_dwarf_session
   ```

2. Install the required Python libraries:
   ```sh
   python -m pip install -r requirements.txt
   python -m pip install -r requirements-local.txt --target .
   ```
   > **Note**: The `dwarf_python_api` library must be installed locally in the root path of this project using the `--target .` parameter. Ensure the dot at the end of the line is not missed.

3. Configure the `config.ini` file with your Wi-Fi SSID and password to use your Dwarf on your local Wi-Fi network.

4. Start the application:
   - For the console version, run: `python astro_dwarf_scheduler.py`
   - For the GUI version, run: `python astro_dwarf_session_UI.py`

5. If using the console, you can set parameters for IP and ID: `--ip ip_value --id (2 or 3)`. These values are necessary if the device hasn't been connected via Bluetooth previously.

6. If parameters are not set, the application will attempt to connect to the Dwarf via Bluetooth at startup. A web page will open, and the process will stop if there's a Bluetooth error.

7. If the connection to the Dwarf fails at startup, the application will prompt whether to connect via Bluetooth for 30 seconds and then continue.

8. After an error at the end of a processing action, the application will ask again about connecting to the Dwarf via Bluetooth, waiting 60 seconds in this case before continuing.

   - If the parameters are correct, the console will proceed without asking for Bluetooth connection.
   - The console can be operated in a headless environment until a connection is established.
   - If you have Dwarfium, start the connection there so processing can continue without manual intervention on the console.

## Usage
- Session files should be placed in the `./Astro_Sessions/ToDo/` subdirectory. They will be processed automatically.
- To stop the processing at any time, use `CTRL+C`.

## Notes
- Clear skies and good luck! The Dwarf will work for you.
