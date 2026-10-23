---
tags:
  - Hub
  - Beginner
---

# Install everything with the Hub

The **Dwarfium Hub** downloads the latest version of each app for your system, installs it and starts it. You never unzip anything by hand again: updates are one click, and your data is never touched by them.

## 1. Get the Hub

1. Download `DwarfiumHub-Windows.zip` (or `-Linux` / `-macOS`) from the [Hub releases](https://github.com/stevejcl/dwarfium-hub/releases).
2. Unzip it anywhere and run **DwarfiumHub**.

The apps will be installed in `C:\Dwarfium` on Windows, `~/Dwarfium` elsewhere. **Change** at the top of the Hub picks another folder.

## 2. Install the apps

On the Hub's home tab, each app shows its installed version and the latest one.

1. Click **Install** on **Dwarfium Lite** and on **Dwarfium Scope Archive** (you can install only one).
2. The Hub downloads the build for your system, checks it (SHA-256) and installs it. **What's new** shows the release notes.

!!! info "Already installed by hand?"
    **Use an existing installation** adopts a folder you installed yourself, instead of reinstalling it. Its data stays where it is.

## 3. Start them

- **Start** one app, or both together. Each runs on its own fixed port: **Scope Archive 8080**, **Dwarfium Lite 8090** (editable).
- Closing the Hub leaves them running.
- Tick **Start with the hub** and **Restart automatically** to have them started with the Hub and restarted if they crash. On Windows, **Start the hub with Windows** completes the chain after a reboot.

## 4. Open them

- Dwarfium Lite opens in its own window. From a phone or a tablet on the same network: `http://<PC IP>:8090`.
- Scope Archive opens at `http://localhost:8080`. To reach it from another device, start it with **LAN access** (option in the Hub).

!!! tip "On a phone"
    Open Dwarfium Lite's address in the browser, then *Add to Home Screen* (iOS Safari) or *Install app* (Android Chrome): it becomes an app with its own icon, without the address bar.

## Without the Hub

Each app also has its own releases ([Dwarfium Lite](https://github.com/stevejcl/astro_dwarf_session/releases), [Scope Archive](https://github.com/stevejcl/dwarfium-scope-archive/releases)) and runs from source with Python 3.10+ — see each repository's README.

**Next:** [Add your first Dwarf](first-dwarf.md)
