---
tags:
  - Hub
  - Lite
  - Scope Archive
  - Maintenance
---

# Install, update, maintain

## Update an app, or go back { #update }

**App:** Dwarfium Hub → **Applications**

- **Update to x.y.z** appears when a new release exists; **What's new** shows its notes. Stop the app first.
- Only program files are replaced: **your data is never touched** (Dwarfs, configs, sessions, database, settings).
- **Back to x.y.z** restores the files the last update replaced.

## Start the apps automatically and restart them if they crash { #autostart }

**App:** Dwarfium Hub

- Per app: **Start with the hub**, **Restart automatically** (after a crash, at most 3 times in 10 min — not after you close its window).
- Windows: **Start the hub with Windows** — after a reboot, the Hub starts minimized and starts the apps ticked.

The Hub is the watchdog: if the Hub is closed, nothing is watched.

## Read the logs { #logs }

**App:** Dwarfium Lite → `/logs`

The log file, live, with a text filter. A running program also has its step-by-step trace on the Dwarf's page. Include a log excerpt when you [report a problem](https://github.com/stevejcl/astro_dwarf_session/issues).

## Translate the apps into my language { #language }

**Dwarfium Lite:** the texts are in `components/locales/<code>.py` (`en.py` is the reference).

1. `python tools/check_i18n.py --new de "Deutsch"` creates `de.py`, every value marked `# TODO`.
2. Translate (keep `{placeholders}` as they are), set `ENABLED = True`, restart: the language button becomes a menu.
3. `python tools/check_i18n.py --lang de` lists what's missing.

With the packaged app, copy `en.py` to `components/locales/de.py` next to the executable, set `LANGUAGE_NAME` and `ENABLED = True`, translate and restart. Send the file to have it included.

**Scope Archive:** same idea in its `components/locales/` (and `components/help_locales/` for the in-app help); `tools/check_i18n.py` and `tools/check_help.py` audit them.
