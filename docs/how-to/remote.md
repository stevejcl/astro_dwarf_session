---
tags:
  - Lite
  - Hub
  - Remote
---

# Watch, share and work remotely

## Use the apps from my phone { #phone }

The apps are local web apps: any device on the same network opens them in a browser.

- **Dwarfium Lite:** `http://<PC IP>:8090` (port set by the Hub; started by hand, the port is printed at startup, or fix it with `--port`). Then *Add to Home Screen* (iOS) / *Install app* (Android) for an app icon.
- **Scope Archive:** start it with **LAN access** (Hub option, or `--lan`), then `http://<PC IP>:8080`.

## Let someone watch without touching anything { #watch }

**App:** Dwarfium Lite → `/watch`

A read-only dashboard and per-Dwarf view: live camera, battery, temperature, capture progress, exposure / gain / filter. No button in this mode can send a command to a Dwarf — safe to give the link or show the QR code (*Scan to open Watch mode*) to anyone on the network.

## Drive Dwarfs at a remote site { #remote-site }

**Apps:** Dwarfium Lite on a mini PC or laptop next to the Dwarfs, Dwarfium Hub at home, [Tailscale](https://tailscale.com) between them

1. Install Dwarfium Lite on the remote computer, Tailscale on both.
2. Hub → **Installations** → **Add an instance**: type *Mini PC*, access *Tailscale* (or *Both*), its Tailscale name or `100.x` IP, port 8090, and its shared folder for the synchronization.
3. The card shows the remote Lite and its Dwarfs (connected, busy, waiting). **Open** it in the browser.

All times follow the **Site's timezone**, whatever the PC's or the browser's.

!!! tip "Backups from a remote Dwarf"
    The **FTP** badge on each Dwarf says whether this PC reaches the Dwarf's FTP (what Scope Archive downloads from). For a Dwarf on the remote network, set a Tailscale **subnet router** on the remote computer (`tailscale set --advertise-routes=192.168.88.0/24`, approved in the admin console). The tab's **Help** has every step, Windows firewall included.

!!! warning "One Lite per Dwarf"
    A Dwarf connected to two installations is shown in red: a Dwarf is driven by one Dwarfium Lite at a time.

## Take a laptop to the field and merge back at home { #laptop }

**App:** Dwarfium Hub → **Synchronize**

Merges two Dwarfium Lite installations both ways:

- **Dwarfs** missing on one side are copied (recognised by their ID, even under another config name);
- **Programs** by their id — the most advanced state wins (Done / Error over Current over ToDo);
- **Results, sites, preferences** missing on one side are copied; differences are only shown.

**Compare** lists every change (untick any), nothing is written before **Synchronize**. Lite must be stopped on both sides; a zip of both is made first in `sync_backups`. At startup the Hub tells you if an installation differs.
