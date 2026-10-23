---
tags:
  - Scope Archive
  - Processing
---

# Process images

## Prepare a session for Siril { #siril }

**App:** Scope Archive → Explore → **Prepare for Siril**

Copies the session's lights — and the matching darks from the [Dark Library](#darks) when the 🎯 badge found some — to a processing folder, with a `siril_session.json`. Run it in Siril with the **Dwarfium Archive Selector** script (by Stephan Schmidt-Bilkenroth; a copy is in Scope Archive's `extern` folder) to calibrate, register and stack.

## Stack several nights of a target in Siril { #siril-megastack }

**App:** Scope Archive → Explore → select sessions of one object → **🧩 Prepare for Siril (Megastack)**

Choose the sessions; it writes a `siril_megastack.json`:

- **one filter** → a deeper stack;
- **several filters** (Duo-Band + L, Ha / OIII…) → each stacked, then combined (HaRGB / HOO / LRGB);
- **mosaics** → panels from raw files (default) or **already-stacked panels** (the Dwarf's own `stacked-16` FITS), assembled by astrometry (Siril 1.4.0+).

`RESTACKED_` sessions are already processed: they're used as already-stacked, and left out of a raw group rather than calibrated twice.

To stack **on the Dwarf** instead, see [Megastack on the Dwarf](capture.md#megastack).

## Manage my dark frames { #darks }

**App:** Scope Archive → **Dark Library**

A library is a `CALI_FRAME` folder on a backup drive, files named like `dark_exp_15.0_gain_80_bin_1_14C.fits`.

- **Scan Library** — inventory by camera, exposure, gain, binning, temperature.
- **Download Darks** — opens Transfer set to copy `CALI_FRAME` from the Dwarf.
- In Explore, the 🎯 badge says if a session has matching darks: green (temperature in range), orange (closest), red (none).

## Keep my processed images next to the raw session { #manual-sessions }

**App:** Scope Archive → **Manual Sessions**

Import a result from Siril, GraXpert, Stellar Studio (URL) or any tool: JPG, PNG, FITS. **Tags** (`Siril`, `GraXpert`, `v2`) keep several versions. They're listed in **Manual Explore** and linked to the original Dwarf session.

## Fix a smeared foreground on a wide session { #fix-foreground }

**App:** Scope Archive → Explore → **Fix the foreground** (backup drive, wide sessions)

For sessions shot before DWARF 3 V1.5.3.9 / DWARF mini V1.1.4.4: the Dwarf stacked on the stars and smeared the trees and roof. Scope Archive rebuilds the image from the raw frames: the foreground stacked on itself, the sky on the stars. The session is left untouched; the result goes into `FIXED_FOREGROUND` and shows in the session's **Image Fix** tab.
