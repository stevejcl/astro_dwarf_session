# Astro Dwarf Session

Astro Dwarf Session automates and monitors imaging sessions for Dwarf II, Dwarf 3, and Dwarf Mini telescopes. It runs as a lightweight local web app (built with [NiceGUI](https://nicegui.io)) that you open in a browser or as a native desktop window — and, since it's a web app, from your phone or tablet too, on the same network.

> **Note:** this project used to ship a Tkinter desktop GUI (`astro_dwarf_session_UI.py`). That interface is retired — a full rewrite on NiceGUI now covers everything it did and more, including proper multi-device support. The old Tkinter code is preserved on the `V3-multi` branch for reference.

![image](p:\JiCi_IMG\Screenshots\Screen_Dwarf_Session_Home.png)
![image](p:\JiCi_IMG\Screenshots\Screen_Dwarf_Session_Home_Session.png)

![image](p:\JiCi_IMG\Screenshots\Screen_Dwarf_Session_Detail.png)

![image](p:\JiCi_IMG\Screenshots\Screen_Dwarf_Session_Program_1.png)

![image](p:\JiCi_IMG\Screenshots\Screen_Dwarf_Session_Program_2.png)

![image](p:\JiCi_IMG\Screenshots\Screen_Dwarf_Session_Program_Scripts.png)
![image](p:\JiCi_IMG\Screenshots\Screen_Dwarf_Session_Program_Result.png)

![image](p:\JiCi_IMG\Screenshots\Screen_Dwarf_Session_Explorer.png)
![image](p:\JiCi_IMG\Screenshots\Screen_Dwarf_Session_Explorer_full.png)

## What it does

- **Connects to your Dwarf(s)** over Wi-Fi (BLE pairing built in) and talks to them live over the same WebSocket/protobuf protocol the official app uses.
- **Controls several telescopes from one app**, side by side — a "mission control" dashboard shows every paired Dwarf at a glance: connected/disconnected, battery, sensor temperature, free storage, and a live camera thumbnail while a capture is running.
- **Runs and schedules imaging programs**: build a program once (goto, calibration, EQ Solving, camera settings, capture — including Mosaic panels) and either run it live or schedule it for later. A background scheduler picks up due programs even with no browser tab open.
- **Lets you browse the sessions already on the device** — a dedicated explorer lists real astro sessions straight from the Dwarf's own storage, sorted newest first, with thumbnails and a one-click enlarged view showing target, date, exposure, gain, and IR filter.
- **Keeps a live step-by-step trace** of what a running program is doing, and a full log viewer for anything that needs a closer look.
- **Installs to your phone's home screen** as a standalone app (no browser address bar) via built-in PWA support.

## Installation

### Prerequisites
- Python 3.10+
- Windows, macOS, or Linux

### Setup
```sh
git clone <this repo>
cd astro_dwarf_session

Install a virtual env
python -m venv myenv
Add Rights on Windows
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
Activate the virtual env
myenv\Scripts\activate

Install the dependency
python -m pip install -r requirements.txt
python -m pip install -r requirements-local.txt --target .
```

Note: The dwarf_python_api library must be installed locally in the root path of this project using the --target . parameter.


### Running
```sh
python astro_dwarf_ui.py
```
This opens a native desktop window by default, backed by a local web server. To run it server-only (no desktop window, useful headless or to just use it from a browser/phone):
```sh
python astro_dwarf_ui.py --no-native
```
Then open `http://<this-computer's-IP>:<port>` from any device on the same network — the port is chosen automatically and printed on startup, or pass `--port` to fix it.

On a phone, open that same address in the browser, then use "Add to Home Screen" (iOS Safari) or "Install app" (Android Chrome) to get an app-like icon with no address bar.

## Usage

### Pairing a device
From the dashboard, tap **+** to pair a new Dwarf over Bluetooth — it walks you through selecting the device and joining your Wi-Fi network. Once paired, the device shows up on the dashboard permanently (until you remove it).

### Live control
Open a paired device from the dashboard to reach its control page: camera settings (exposure, gain, binning, IR filter — per-model, since Dwarf II/3/Mini each have their own filter set), one-off actions (calibration, EQ Solving with a live Azimuth/Altitude correction readout, goto, reboot), and the live camera stream.

### Programs
The program editor builds a JSON session file — the same format the scheduler consumes — covering goto (solar/manual/none), calibration, EQ Solving, camera setup, capture duration, and Mosaic (framing scale on each axis, shots per panel). Save a program to run it immediately, or schedule it for a specific date/time; the scheduler runs in the background regardless of which page you're looking at, and retries a failed step a configurable number of times before giving up.

### Session explorer
Each device's control page links to an **Astro Sessions** explorer: a grid of thumbnails pulled directly from the Dwarf's own on-device album (no separate app or cloud account needed), sorted most-recent-first. Click a thumbnail for a large view with the session's target, capture date, exposure, gain, and IR filter.

### Logs
A dedicated `/logs` page tails the shared log file live, with a text filter — useful for anything the on-screen step trace doesn't cover in enough detail.

## Architecture

```
astro_dwarf_session/          (this repo)
├── astro_dwarf_ui.py         # entry point (NiceGUI + native window)
├── dwarf_session.py          # session-execution logic (goto/calibration/EQ/capture/Mosaic)
├── device_registry.py        # loads known devices' config.py/config.ini pairs at startup
├── components/                # UI building blocks + the scheduler
│   ├── scheduler_runner.py    #   runs one program, step by step
│   ├── scheduler_loop.py      #   background timer that picks up due programs
│   ├── program_editor.py      #   the program-builder form
│   ├── camera_stream.py       #   live HTTP camera preview
│   ├── device_card.py         #   the dashboard's per-device "mission control" card
│   └── ...
├── pages/                     # one file per route (dashboard, session, programs, explorer, settings, pairing, logs)
├── images/                    # device-model icons shown on the dashboard
└── dwarf_python_api/          # device-control library (WebSocket/protobuf + HTTP), a separate project
```

Session JSON files move through `Devices_Sessions/<device>/Astro_Sessions/{ToDo,Current,Done,Error}/` exactly as before — but for each device

### Multi-device model
Every paired Dwarf gets its own `DwarfSession` (own connection, own event loop, own cached state) inside a single process-wide `DwarfManager` — so the dashboard, a program running on one device, and live camera control on another can all happen at once without cross-talk between devices.

## Troubleshooting

- **A device shows "Disconnected" but the Dwarf's own status light is solid**: give it a few seconds — the app validates the connection with a real round-trip to the device rather than trusting the raw socket state, since a socket can look open while the device stopped actually responding.
- **Video preview issues**: the live camera preview needs the Dwarf's own HTTP stacking endpoint (`http://<dwarf-ip>:8092/mainstream` for tele, `/secondstream` for wide) — confirm the device is reachable at that address.
- **Windows async warnings** (`ConnectionResetError [WinError 10054]`, `_ProactorBasePipeTransport`): harmless asyncio/Windows noise, already suppressed at both the device-connection layer and the app's own web server.

## See also

**[Dwarfium Scope Archive](https://github.com/stevejcl/dwarfium-scope-archive)** — a companion tool for archiving and browsing completed Dwarf sessions via USB/FTP, without going through the device's live network API at all. Built on the same NiceGUI foundation as this app, which makes cross-launching between the two (jump straight from a just-finished session here into archiving it there, and back) a realistic near-term goal rather than a stretch.

## Contributing

Issues and pull requests welcome — this project leans heavily on real-hardware testing (network captures, direct device testing across Dwarf II/3/Mini) rather than guesswork, so bug reports with a log excerpt are especially useful.

## Notes

Clear skies and good luck — the Dwarf will work for you.
