# Astro Dwarf Session

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


Astro Dwarf Session automates and monitors imaging sessions for Dwarf II, Dwarf 3, and Dwarf Mini telescopes. It runs as a lightweight local web app (built with [NiceGUI](https://nicegui.io)) that you open in a browser or as a native desktop window — and, since it's a web app, from your phone or tablet too, on the same network.

> **Note:** this project used to ship a Tkinter desktop GUI (`astro_dwarf_session_UI.py`). That interface is retired — a full rewrite on NiceGUI now covers everything it did and more, including proper multi-device support. The old Tkinter code is preserved on the `V3-multi` branch for reference.

<img width="1008" height="791" alt="Screen_Dwarf_Session_Home" src="https://github.com/user-attachments/assets/cd685d0f-505a-4468-9543-40224d2020b6" />

<img width="1011" height="905" alt="Screen_Dwarf_Session_Home_Session" src="https://github.com/user-attachments/assets/1120c509-5a21-4ce6-b0fa-cddb6a9b012c" />

<img width="1007" height="1049" alt="Screen_Dwarf_Session_Detail" src="https://github.com/user-attachments/assets/98211df4-4266-41f5-8ff0-516ef13b59c3" />

<img width="1004" height="1002" alt="Screen_Dwarf_Session_Program_1" src="https://github.com/user-attachments/assets/e5a28f22-86f8-455c-93a0-c3d21811cc96" />
<img width="1004" height="595" alt="Screen_Dwarf_Session_Program_2" src="https://github.com/user-attachments/assets/f054525e-f82a-4bba-b5f5-4c536639d961" />

<img width="1003" height="771" alt="Screen_Dwarf_Session_Program_Scripts" src="https://github.com/user-attachments/assets/b5b03398-e0ff-4406-b01f-3bdf050fd501" />
<img width="1005" height="896" alt="Screen_Dwarf_Session_Program_Result" src="https://github.com/user-attachments/assets/74aecb3d-e8bf-4611-ba34-425c645efde2" />


<img width="1010" height="794" alt="Screen_Dwarf_Session_Explorer" src="https://github.com/user-attachments/assets/13fa5367-5671-43e5-ae4b-88154625fcf3" />
<img width="1009" height="793" alt="Screen_Dwarf_Session_Explorer_full" src="https://github.com/user-attachments/assets/78209d87-05c4-4ef6-81f2-ee9a8cb356cd" />

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