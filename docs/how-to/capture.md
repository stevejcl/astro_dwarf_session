---
tags:
  - Lite
  - Capture
  - Programs
---

# Capture and schedule

## Take pictures now, by hand { #live }

**App:** Dwarfium Lite → a Dwarf's page

- **Camera settings** — exposure, gain, binning, filter (per model), **Frames** (the number of images, for both cameras: sent on Enter or when leaving the field).
- **Actions** — calibration, **EQ Solving** (with the live azimuth / altitude correction: which way to turn the knobs), goto, capture, reboot, close the lenses, positions…
- **Live view** — Tele and Wide panels, each foldable; a **Stacked / Last frame** switch.
- The lights and power-indicator buttons work during a capture too. **Shut down** (far right of *Disconnect*) powers the Dwarf off after a confirmation.

!!! note "Live view needs FFmpeg"
    The RTSP live view uses FFmpeg. Without it, the Dwarf's page and the log file say so.

## Create a program and run it later { #program }

**App:** Dwarfium Lite → a Dwarf's **Programs** page

A **program** is a list of steps run in order: start position, goto (solar system / manual RA-Dec / none), calibration, EQ Solving, auto focus or infinite focus, camera settings, capture (optionally a Dwarf mosaic), what to do after the session.

1. **Add** a program, set the date and time (calendar / clock, *now + 5 min*).
2. Fill the target: [catalog, Stellarium](plan.md#catalog) or RA/Dec — decimal or `18h 13m 40.3s`, `18:13:40.3`, `-17° 36' 06"`.
3. **Save**. The program waits in **ToDo**.
4. Leave **Scheduler active** on for that Dwarf. The scheduler runs due programs in the background, whatever page is open, and retries a failed step (*Max retries*).

The program then moves through **ToDo → Current → Done / Error**. The Programs page lists the newest first, 20 at a time (**Show more**).

!!! tip "Same program, another Dwarf"
    **Import a program from another device/model** reuses a program; values the other model doesn't accept (gain, exposure) are adjusted and said.

## Stop a capture at a given time { #end-time }

**App:** Dwarfium Lite → program editor → **End time**

If the requested count isn't reached by then, the capture stops cleanly instead of running into the dawn. Crossing midnight is handled. The *Use best slot* button fills it from the altitude chart.

## Use the Dwarf's own schedule { #native }

**App:** Dwarfium Lite → a Dwarf's page → *Shooting schedule (on device)*

| | Lite **program** | Dwarf **native schedule** |
|---|---|---|
| Who runs it | Dwarfium Lite (must stay running) | The Dwarf itself (PC can be off) |
| Steps | Everything (EQ Solving, start position, end of night…) | What the Dwarf's firmware offers |
| Same as | — | The DwarfLab app's own scheduling |

- **Add a target** (catalog and altitude chart available, *Next free slot*), then **Sync to device**.
- The list shows every schedule on the Dwarf with its state (Planned, In progress, Completed, Expired) and each target's progress; delete one, **View** a completed task, **Check** a failed one.
- Dwarf offline or busy? The schedule is kept as **Pending** — a banner offers **Sync now**, or it is sent automatically at the next connection.

!!! warning
    While a native schedule is planned, Lite's end of the night never powers the Dwarf off: it must stay on, it sleeps and wakes up on its own.

## Send targets to "any free Dwarf" { #any-dwarf }

**App:** Dwarfium Lite, from the `/catalog` page

With two or more Dwarfs of the same model, choose **Any Dwarf 3 (auto)** (or the model you have) when sending: Lite picks whichever Dwarf is actually free at send time.

## Resume a program that failed while the Dwarf kept capturing { #force-resume }

**App:** Dwarfium Lite → Programs → **Results** tab → **Force resume**

After a network drop, a run can be marked as failed while the Dwarf is still capturing its target. *Force resume* follows it again to its end.

## Megastack / restack on the Dwarf { #megastack }

**App:** Dwarfium Lite → the Dwarf's **Astro Sessions** explorer → **Megastack** (top right)

The Dwarf stacks several of its sessions of one target together — or restacks a single one — into `Astronomy/RESTACKED/`, like the official app. The raw FITS must still be on the Dwarf.

1. Only stackable sessions are shown, grouped by target. Tick one or more of the same target (single captures or mosaics, not mixed; filters can be mixed).
2. **Megastack**. The Dwarf checks first (binning, dark frames) and says why if it refuses.
3. Progress shows everywhere: *Megastack in progress · 436/598 · 399 stacked*.

Scope Archive can ask for it too, from its Explore page. Meanwhile the Dwarf does nothing else: a due program waits.
