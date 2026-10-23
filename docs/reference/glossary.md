# Glossary

Site
:   A place you observe from: a Wi-Fi network, a location and a timezone. Created once in Dwarfium Lite (`/sites`), picked everywhere. Every time shown for a Dwarf is in its Site's timezone.

Program
:   A list of steps (goto, calibration, focus, capture…) that **Dwarfium Lite** runs on a Dwarf at a given time. Stored as a JSON file that moves through `ToDo` → `Current` → `Done` / `Error`. Lite must be running. → [Programs](../how-to/capture.md#program)

Native schedule (shooting schedule on device)
:   A list of targets stored **in the Dwarf** and run by its firmware, like the DwarfLab app's scheduling. Works with the PC off. → [Native schedule](../how-to/capture.md#native)

Scheduler
:   Dwarfium Lite's background loop that starts due programs. Can be switched on / off per Dwarf (**Scheduler active**).

Best slot
:   The part of the night when a target is above your minimum altitude in a dark enough sky, highlighted on the altitude chart.

Tonight's plan
:   A list of targets (5 by default) built in Scope Archive's *What to shoot tonight*, chained over the night by Lite's *Plan a target* page.

Dwarf mosaic / tiles
:   *Dwarf mosaic*: the Dwarf's own multi-panel capture (framing 1.0–1.8×). *Tiles*: separate programs, one per pointing (catalog planner, Milky Way planner), assembled afterwards.

Megastack / RESTACKED
:   Stacking several sessions of a target (or restacking one). On the Dwarf, the result goes to `Astronomy/RESTACKED/`. In Siril, through Scope Archive's *Prepare for Siril (Megastack)*.

View / Check
:   Buttons that read what the Dwarf really saved for a program or schedule task (stacked / taken, integration). *View* on success, *Check* on failure.

Initial position
:   The Dwarf's axes position saved after a calibration (or by hand), that a program can go back to before starting.

Backup drive
:   A disk or folder where Scope Archive keeps copies of your sessions. Linked to one Dwarf.

Clean FITS / Restore FITS
:   Remove a session's raw frames to free space (stacked files kept) / copy them back from the backup.

Dark Library
:   A `CALI_FRAME` folder of dark frames, matched to sessions by exposure, gain, binning and temperature (🎯 badge).

ID (of a Dwarf)
:   The last 6 characters of the MAC address printed on the Dwarf. Ends its Bluetooth name (`DWARF3_A1B2C3`). Proves two entries are the same physical Dwarf.

UID
:   Dwarfium Lite's name for a Dwarf's Bluetooth name (e.g. `DWARF3_A1B2C3`).

Dwarf Id
:   The id of a Dwarf **in Scope Archive's database**, set in Lite's Dwarf Settings to link it.

Instance
:   In the Hub, any Dwarfium Lite installation other than the Hub's own (a laptop, a mini PC, a source run), shown and synchronized but not started by the Hub.

Watch mode
:   Lite's read-only pages (`/watch`): nothing there can send a command to a Dwarf.

STA mode
:   The Dwarf connected to your Wi-Fi network (as opposed to its own hotspot).
