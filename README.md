# Astro Dwarf Session

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


Astro Dwarf Session automates and monitors imaging sessions for Dwarf II, Dwarf 3, and Dwarf Mini telescopes. It runs as a lightweight local web app (built with [NiceGUI](https://nicegui.io)) that you open in a browser or as a native desktop window — and, since it's a web app, from your phone or tablet too, on the same network.

> **Note:** this project used to ship a Tkinter desktop GUI (`astro_dwarf_session_UI.py`). That interface is retired — a full rewrite on NiceGUI now covers everything it did and more, including proper multi-device support. The old Tkinter code is preserved on the `V3-multi` branch for reference.

<img width="1010" height="808" alt="AstroDwarfUI_Home Screen" src="https://github.com/user-attachments/assets/7e9a2e86-b1a8-4cee-b14f-4255d819f636" />

<img width="1010" height="808" alt="AstroDwarfUI_Home Screen_Black" src="https://github.com/user-attachments/assets/6c8fc9d0-b594-43a0-9450-b391c03bfb44" />

<img width="1011" height="905" alt="AstroDwarfUI_Home Screen_Live Capture" src="https://github.com/user-attachments/assets/facd3ffc-03c1-4f30-9660-607ffd01b9f8" />

<img width="1010" height="1031" alt="AstroDwarfUI_Add_New_Site" src="https://github.com/user-attachments/assets/d48b3d92-6d3d-4d5e-9f52-d98629ddc38f" />

<img width="1011" height="530" alt="AstroDwarfUI_Add_Device" src="https://github.com/user-attachments/assets/d4a4dd81-bc96-423f-824c-df239a7e581f" />

<img width="1010" height="1080" alt="AstroDwarfUI_Device_Settings" src="https://github.com/user-attachments/assets/12f20406-96ad-4999-a52f-726cbd0acb90" />

<img width="1010" height="808" alt="AstroDwarfUI_Manual_Config" src="https://github.com/user-attachments/assets/44c287e9-8188-40dd-a16f-09186ab70c70" />

<img width="869" height="1080" alt="AstroDwarfUI_Device_Card" src="https://github.com/user-attachments/assets/dfb651e3-46fe-4b2a-b9ae-a344e4bdfb03" />

<img width="868" height="1690" alt="AstroDwarfUI_Program_Editor" src="https://github.com/user-attachments/assets/92c88521-93c8-4871-ad7e-67c7e7867754" />

<img width="869" height="564" alt="AstroDwarfUI_Program_Scripts" src="https://github.com/user-attachments/assets/b960476f-de27-427a-84d5-6afaefc99b05" />

<img width="1010" height="983" alt="AstroDwarfUI_Program_Results" src="https://github.com/user-attachments/assets/0f46a713-c902-432d-9904-80469cac14f7" />

<img width="1010" height="983" alt="AstroDwarfUI_Program_Native_Schedule" src="https://github.com/user-attachments/assets/26e520ba-9fc1-411c-98d2-1119f2abaeb2" />

<img width="970" height="837" alt="AstroDwarfUI_Watch_Screen" src="https://github.com/user-attachments/assets/cb7f3050-0f52-410d-9cb3-8b1cca5880a3" />

<img width="1554" height="2357" alt="AstroDwarfUI_Milky_Way_Planner" src="https://github.com/user-attachments/assets/b978e0f9-eddf-4db5-80da-8fa7a4bb151b" />

## What it does

- **Connects to your Dwarf(s)** over Wi-Fi (BLE pairing built in, plus a no-Bluetooth manual config path for when a BLE adapter isn't cooperating — see below) and talks to them live over the same WebSocket/protobuf protocol the official app uses.
- **Controls several telescopes from one app**, side by side — a "mission control" dashboard shows every paired Dwarf at a glance: connected/disconnected, battery, sensor temperature, free storage, live capture progress (captured/requested count, stacked count, scheduled stop time if set), a live camera thumbnail while a capture is running, and the result of the last finished program. A **Connect all** button brings every disconnected Dwarf online in one click instead of opening each one's own page.
- **Sites** bundle a Wi-Fi network and a location (lat/long, timezone) under one name, reusable across every Dwarf that observes from there — pick one instead of retyping the same Wi-Fi password and coordinates for every device, every time you change location.
- **Runs and schedules imaging programs**: build a program once (goto, calibration, EQ Solving, camera settings, capture — including Mosaic panels) and either run it live or schedule it for later. A background scheduler picks up due programs even with no browser tab open. A capture step can optionally be given a scheduled end time — if the requested image count isn't reached by then, the session is stopped cleanly instead of running indefinitely.
- **Syncs and monitors the Dwarf's own on-device shooting schedule** (the native, firmware-side scheduling feature, separate from this app's own program scheduler) — view every schedule currently stored on the device with live status (planned/in progress/completed/expired) and per-target progress, delete one, or queue one for the next connection while offline.
- **Spreads a batch of targets across identical Dwarfs**: when two or more paired devices share the same model, sending a session from the target-catalog page can target "any available" one of that model instead of a specific device, and the app picks whichever is actually free at send time.
- **Plans a Milky Way mosaic** from a standalone planning tool (no login, works from a phone) — pick a Site or use your own location, see a twilight-aware sky chart with the galactic plane and a Moon position/phase check per tile, generate a grid of tiles sized to your Dwarf's own Wide field of view, and send the whole schedule straight into this app's scheduler.
- **Lets you browse the sessions already on the device** — a dedicated explorer lists real astro sessions straight from the Dwarf's own storage, sorted newest first, with thumbnails and a one-click enlarged view showing target, date, exposure, gain, and IR filter.
- **Keeps a live step-by-step trace** of what a running program is doing, and a full log viewer for anything that needs a closer look.
- **Watch mode** (`/watch`) — a read-only dashboard and per-device view for spectators on the same network: live camera preview, battery/temperature, capture progress, exposure/gain/filter. No path in this mode can ever send a command to a device, by construction, so it's safe to hand someone the link without handing over control.
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
python astro_dwarf_ui.py --no_native
```
Then open `http://<this-computer's-IP>:<port>` from any device on the same network — the port is chosen automatically and printed on startup, or pass `--port` to fix it.

On a phone, open that same address in the browser, then use "Add to Home Screen" (iOS Safari) or "Install app" (Android Chrome) to get an app-like icon with no address bar.

## Usage

### Sites
Before pairing or configuring a device, it helps to have at least one Site set up: `/sites` lets you name a Wi-Fi network + location (with a "use current location" button, browser-based) once and reuse it everywhere. Every place that needs a Wi-Fi/location pair — pairing a new device, the no-Bluetooth manual config wizard, a device's own settings page — has a Site picker with an inline "+" to create one on the spot, so you're never forced to leave the page you're on just to set up the first Site.

### Pairing a device
From the dashboard, tap **+** to pair a new Dwarf over Bluetooth — pick a Site (for its Wi-Fi credentials and location) and it walks you through selecting the device and joining that network. Once paired, the device shows up on the dashboard permanently (until you remove it).

If a device's Wi-Fi was already configured through the official DwarfLab app (so it reconnects to that network on its own at startup) — or if Bluetooth pairing isn't an option on this machine (a common issue: `bleak` failing to detect the BLE adapter at all) — the dashboard's Wi-Fi icon opens a manual config wizard instead: pick a Site, the model, and enter the IP/UID shown in the DwarfLab app's own "My Device" screen. No Bluetooth involved.

### Live control
Open a paired device from the dashboard to reach its control page: camera settings (exposure, gain, binning, IR filter — per-model, since Dwarf II/3/Mini each have their own filter set), one-off actions (calibration, EQ Solving with a live Azimuth/Altitude correction readout, goto, reboot), the live camera stream (Tele and Wide each in their own collapsible panel — show both, one, or neither), and a "Force Bluetooth reconnect" recovery option for when the device's IP changed and the normal reconnect stopped working.

### Programs
The program editor builds a JSON session file — the same format the scheduler consumes — covering goto (solar/manual/none), calibration, EQ Solving, camera setup, capture duration, an optional scheduled end time (stop the capture at a given time if the requested count isn't reached yet — handles crossing midnight correctly), and Mosaic (framing scale on each axis, shots per panel). Save a program to run it immediately, or schedule it for a specific date/time (with a calendar/clock picker, and a "now + 5 min" shortcut on schedule editing); the scheduler runs in the background regardless of which page you're looking at, and retries a failed step a configurable number of times before giving up.

### On-device shooting schedule
Separate from this app's own program scheduler above, a Dwarf can also hold its own native shooting schedule (the same mechanism the official DwarfLab app's own scheduling feature uses). A device's control page shows every schedule currently stored on it — status (planned, with its date/time range; in progress; completed; expired), and per-target progress — with a delete action per schedule. A schedule built elsewhere and waiting to be sent (e.g. while the device was offline or busy) shows as a banner you can sync immediately or discard once the device is reachable.

### Session explorer
Each device's control page links to an **Astro Sessions** explorer: a grid of thumbnails pulled directly from the Dwarf's own on-device album (no separate app or cloud account needed), sorted most-recent-first. Click a thumbnail for a large view with the session's target, capture date, exposure, gain, and IR filter.

### Milky Way mosaic planner
A standalone planning page, separate from the main app's own pages — open `/mosaic-planner-en` or `/mosaic-planner-fr` (served straight from the app, no separate install) from a phone or a desktop browser. Pick a Site from the dropdown or use the browser's own geolocation, and it draws a twilight-aware sky chart with the galactic plane, lets you center a mosaic grid sized to a chosen Dwarf's own Wide field of view (EQ or Alt-Az framing), and schedules each tile's exposure/count/duration across the night. Each tile also has a one-tap Moon check — position, altitude, and phase (illumination %) at that tile's own scheduled time — so you can see how much moonlight a given frame will pick up before committing a whole night to it. Once you're happy with the plan, sending it queues every tile straight into this app's own scheduler, one program per tile, with no need to build each one by hand in the program editor.

### Watch mode
`/watch` is a separate, read-only dashboard meant for someone to look at your session without being able to touch it — no capture, connect, disconnect, or settings controls exist anywhere in this mode's code, so there's no path by which opening it could ever send a command to a device. Useful for sharing progress with someone else on the same network (or just for a second screen) without worrying about a stray tap changing a setting mid-capture.

### Logs
A dedicated `/logs` page tails the shared log file live, with a text filter — useful for anything the on-screen step trace doesn't cover in enough detail.

## Architecture

```
astro_dwarf_session/          (this repo)
├── astro_dwarf_ui.py         # entry point (NiceGUI + native window)
├── dwarf_session.py          # session-execution logic (goto/calibration/EQ/capture/Mosaic, scheduled end time)
├── device_registry.py        # loads known devices' config.py/config.ini pairs at startup
├── device_provisioning.py    # creates a new device's config.py/config.ini (BLE pairing template, or the no-BLE wizard's full write)
├── site_registry.py          # Wi-Fi + location "Sites", reusable across devices
├── pending_schedules.py      # on-device shooting schedules queued while offline/busy
├── components/                # UI building blocks + the scheduler
│   ├── scheduler_runner.py    #   runs one program, step by step
│   ├── scheduler_loop.py      #   background timer that picks up due programs
│   ├── program_editor.py      #   the program-builder form
│   ├── schedule_editor.py     #   builds a shooting-schedule task list to sync to the device
│   ├── camera_stream.py       #   live HTTP/RTSP camera preview, one collapsible panel per camera
│   ├── device_card.py         #   the dashboard's per-device "mission control" card
│   ├── site_picker.py         #   Site dropdown + inline "create a Site" dialog, shared by pairing/manual config/settings
│   ├── datetime_picker.py     #   calendar/clock popup inputs, shared across the program and schedule editors
│   ├── geolocation.py         #   browser-based "use current location" button
│   ├── api_routes.py          #   /api/dwarfs + /api/schedule + /api/program + /api/sites, for the external target-catalog page and the Milky Way mosaic planner (incl. auto load-balancing across same-model devices)
│   └── ...
├── pages/                     # one file per route (dashboard, session, programs, explorer, settings, pairing, manual_config, sites, watch_dashboard, watch_device, logs)
├── images/                    # device-model icons shown on the dashboard
├── milky_way_mosaic_planner_en.html / _fr.html   # standalone Milky Way mosaic planner, served at /mosaic-planner-{lang}
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

## License

MIT -- see [LICENSE](LICENSE).
