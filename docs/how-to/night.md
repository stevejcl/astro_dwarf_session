---
tags:
  - Lite
  - Unattended
---

# Leave a Dwarf unattended

All of this is set per Dwarf in **Dwarfium Lite → Programs page → Scripts tab → *After the session and end of the night***. Lite must be running and connected: a delay in progress is lost if it restarts.

## Get the Dwarf off its end-of-session screen { #leave-screen }

After a capture the Dwarf stays on its end-of-session screen, **still tracking** (battery).

**Leave the end-of-session screen after N min** (5 by default) — after a program, a capture started from the Actions, or the Dwarf's own schedule while connected: Lite goes back to live view, and **stops the tracking** if ticked.

A program can override it in its editor (**After the session**: *As set for this Dwarf* / *Leave* / *Stay*). Nothing is done after a program you stopped yourself.

## Close the lenses or power off at the end of the night { #end-of-night }

**End of the night**, X min after the last capture (off by default):

- **Close the lenses** — when the next planned activity is more than 15 min away (the next program reopens them).
- **Power off the Dwarf** — only when **nothing at all** is planned any more (programs in ToDo, tasks of the Dwarf's schedule, a schedule waiting to be sent): a remote Dwarf can't be switched back on.

The lenses are always closed before powering off (a Dwarf powered off while tracking keeps them open). The card shows the estimated time.

!!! warning "Native schedule"
    Neither happens while a schedule of the Dwarf itself is planned or waiting to be sent: the Dwarf must stay on and as set up — it sleeps and wakes up before its tasks.

## Start each program from a known position { #initial-position }

The **initial position** is saved after each successful calibration of a program, or with **Save position** in the Actions (point the Dwarf first, by hand or with the joystick — its axes are reset first, that's how the Dwarf learns its position).

In a program, **Start position**:

- **Saved initial position** — axes reset if needed, then back to the saved position. Ideal for a Dwarf powered off in the morning and put back without touching it.
- **Polar position**, or **None**.

When Lite closed the lenses, the next program goes back to the initial position anyway. On DWARF II / 3 the Rotation axis is restored too; on the mini only the Pitch.

## Use a cap or a thick filter holder safely { #accessory }

Tick **Bulky accessory mounted** when something on the lens could touch while the Pitch folds (a cap, a thick filter holder on a DWARF 3 — a filter on the DWARF II's magnetic holder doesn't touch).

Then nothing folds the Pitch automatically: no closing or power-off at the end of the night, no start position in programs, and a confirmation for *Polar position*, *Close the lenses*, *Go to / Save the initial position*.

**Order:** calibrate (or save the initial position) first, then mount the accessory and tick the box.
