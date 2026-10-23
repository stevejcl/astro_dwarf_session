---
tags:
  - Hub
---

# Dwarfium Hub

**One place to install, update and start the Dwarfium apps** — and to keep your Dwarfs and your installations consistent.

[Releases](https://github.com/stevejcl/dwarfium-hub/releases){ .md-button .md-button--primary } [Source](https://github.com/stevejcl/dwarfium-hub){ .md-button }

## Applications tab

| Feature | What it does | How-to |
|---|---|---|
| Latest versions | Compares each app's installed version with its latest release; **What's new** | [Update](../how-to/maintain.md#update) |
| Install / update | Downloads, checks (SHA-256), replaces program files only — your data is never touched | [Install](../start/install.md) |
| Rollback | **Back to x.y.z** restores what the last update replaced | [Update](../how-to/maintain.md#update) |
| Existing installation | **Use an existing installation** adopts a folder installed by hand | [Install](../start/install.md) |
| Start / stop | Each app on a fixed port (Scope Archive 8080, Lite 8090), alone or **Start both** | [Install](../start/install.md#3-start-them) |
| LAN access | Scope Archive reachable from other devices | [Phone](../how-to/remote.md#phone) |
| Launcher and watchdog | **Start with the hub**, **Restart automatically**, **Start the hub with Windows** | [Autostart](../how-to/maintain.md#autostart) |

## Dwarfs tab

The Dwarfs of Lite and Scope Archive side by side, matched by their **ID** (last 6 characters of the MAC address). Link them, copy name / IP / ID across, create a Dwarf missing on one side, flash a Dwarf's light to identify it. Can also work on another installation's Lite through its shared folder.
→ [Link a Dwarf](../how-to/connect.md#link), [Identify](../how-to/connect.md#identify)

## Installations tab

A map of your Dwarfium Lite installations — this PC, a source run, a laptop, a mini PC — on the home network or through Tailscale: running or not, their Dwarfs, whether they're in step with this PC, whether this PC reaches each Dwarf's FTP. A **Help** button walks through the Tailscale setup.
→ [Remote site](../how-to/remote.md#remote-site)

## Synchronize tab

Merges two Lite installations both ways (Dwarfs, programs, results, sites, preferences), after showing every change. Checked at startup.
→ [Laptop in the field](../how-to/remote.md#laptop)

## Good to know

- Apps are installed in `C:\Dwarfium` (Windows) or `~/Dwarfium`; **Change** picks another folder.
- Settings in `hub_config.json` next to the Hub; each installation's version in `.hub_version.json`, the previous version's files in `.hub_backup/`.
