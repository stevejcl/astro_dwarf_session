---
tags:
  - Scope Archive
  - Lite
  - Backup
---

# Back up and tidy sessions

## Archive one session right after the night { #one-session }

**Apps:** Dwarfium Lite → Scope Archive (V3.4.0+)

Set once, in Lite's Dwarf **Settings**: *Dwarfium Scope Archive URL* and *Dwarf Id* (or link the Dwarf from the [Hub's Dwarfs tab](connect.md#link)).

Then **Archive in Dwarfium Scope Archive** — in the explorer's large view, the View / Check dialog, or the Programs page:

1. Scope Archive says first if the session is **already backed up** (with *See it in the backups* or *Import and transfer anyway*).
2. It reads and registers **only that session** from the Dwarf (USB if reachable, else FTP).
3. Its **Transfer** page opens with the session selected: pick the backup drive, start the copy.

The buttons are greyed while Scope Archive isn't running. When it runs as an app, its pages open in its own window.

## Back up all new sessions from the Dwarf { #transfer }

**App:** Scope Archive

1. **Dwarf Configuration** → **Analyze Dwarf Drive**: indexes every session on the Dwarf (USB path or FTP). It first checks that the configured model matches the sessions found.
2. **Transfer** → mode **Archive** (Dwarf → backup drive), USB (fast) or FTP (Wi-Fi, slower).
3. Explore's filter **Not yet backed up** shows what is left.

The transfer goes on in the background: browse other pages meanwhile (a badge in the menu shows progress). Closing the app stops it. **Restore** copies the other way, backup → Dwarf.

!!! note "DWARF II"
    No USB drive access on the DWARF II: use FTP, or MTP on Windows (**MTP Device** page).

## Free space on the Dwarf or the backup drive { #free-space }

**App:** Scope Archive → Explore

- **Clean FITS** removes a session's raw FITS (the stacked files stay). **Restore FITS** copies them back from the backup drive.
- Delete bad frames only: see [keep only the good frames](explore.md#quality).
- Delete a whole session from Explore.

## See which sessions take the most space { #report }

**App:** Scope Archive → **Storage Report**

Per backup drive or Dwarf: sessions sorted by size or date, the size on the backup, on the Dwarf, and on the Dwarf without FITS (what *Clean FITS* would free). **Calculate sizes** measures the sessions not measured yet.

## Re-sync the database after files moved { #analyze-all }

**App:** Scope Archive → **Analyze everything** (menu)

Analyses the local copy of every Dwarf and every backup drive, one after the other — the database matches the files again after another installation changed them or a folder was moved by hand. Log in `logs/analyze_all_<date>.log`.

For one drive only: **Backup Drive** → **Analyze Current Drive**, **Check Session Integrity** (FITS count on disk vs. database).

## Back up the archive database { #db-backup }

**App:** Scope Archive → **Settings** → *Database Backup*

Automatic copies: `.bak` at startup, `.last` at shutdown. **Backup now** saves a dated copy to any folder.
