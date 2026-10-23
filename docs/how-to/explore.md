---
tags:
  - Lite
  - Scope Archive
  - Results
---

# Check and explore results

## See what the Dwarf really saved { #view-check }

**App:** Dwarfium Lite → Programs → **Results**, or the native schedule list

**View** (success) or **Check** (failure) finds the session in the Dwarf's album and shows images **stacked / taken**, integration time and the stacked thumbnail. The counts are then kept and shown directly in the lists. From there: **Archive in Dwarfium Scope Archive**.

## Browse and download sessions still on the Dwarf { #on-the-dwarf }

**App:** Dwarfium Lite → a Dwarf's page → **Astro Sessions**

A grid of the Dwarf's own sessions, newest first, the target on each tile. A click opens the large view (target, date, exposure, gain, filter) with **Download** (the stacked JPG, or the Dwarf's 16-bit PNG) and **Archive in Dwarfium Scope Archive**. No cloud account needed.

## Find a session in my archive { #explore }

**App:** Scope Archive → **Explore**

Sessions grouped by object. Filter by backup drive, Dwarf, name, quality score, and *Only on Dwarf* / *Only on backup* / *Not yet backed up* / *Already backed up* / *Duplicates*.

A session shows its target, coordinates, date, exposure, gain, filter, temperature, stacked count, total exposure, quality score and dark match badge 🎯. **Show Gallery** goes through all the sessions of an object (mouse wheel to scroll quickly). **View** jumps to the same session on the Dwarf or on a backup.

Also on a session: **Session Notes** (moon, seeing, location, notes), favourites (shown on the Home slideshow), **Identify target** (catalog match, Aladin).

## Score sessions / keep only the good frames { #quality }

**App:** Scope Archive → Explore

- **Image Quality Score** (0–100, ⭐ to ⭐⭐⭐⭐⭐): stack rate, total exposure, darks, then image analysis (dynamic range, contrast, entropy). Filter Explore by score.
- **Frames:** each frame's JPG in a gallery (previous / next, space to mark). Marked frames go to the session's trash — so a megastack or restack only takes the good ones. **Delete the rejected frames** takes the ones the Dwarf rejected (`failed_`) at once. The trash can be restored or emptied.

## See all my sessions on a sky map { #sky-map }

**App:** Scope Archive → **Sky Map** (Aladin Lite)

Each solved session drawn with its real footprint, mosaic panels one by one, overlaps highlighted. **Best session per object** keeps the best-scored one; **Hide from the Sky Map** on a session.

Sessions are solved with **ASTAP** (local; path and D50 / G05 databases in Settings) or **astrometry.net** (API key in Settings).

## Find comets or asteroids in a session { #skybot }

**App:** Scope Archive → Explore → SkyBot

Asks IMCCE's SkyBot service which comets and asteroids were in the field at the time of the session. In bulk: `tools/skybot_scan.py`.

## Make a video of my best images { #video }

**App:** Scope Archive — `tools/video_export.py`

A slideshow video of your favourite or filtered sessions, with captions and transitions. A **PDF report** of the archive is in Settings.
