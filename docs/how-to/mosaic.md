---
tags:
  - Lite
  - Scope Archive
  - Mosaic
---

# Mosaics and the Milky Way

## Shoot a mosaic of a big target { #dwarf-mosaic }

**App:** Dwarfium Lite

Two ways, which can be combined:

- **The Dwarf's own mosaic** — in the program editor, **Mosaic**: framing 1.0–1.8× on each axis, subframes per panel. The Dwarf shoots and stacks the panels itself.
- **A grid of tiles** — the `/catalog` page's mosaic planner: at its top choose **Planner → Dwarf**, then the Dwarf, Wide or Tele field, a grid sized to the target and/or the Dwarf's mosaic, exposure / gain / images per panel. The night's schedule comes from the site. **Send to Dwarf** creates one program per tile in Lite.

The catalog's **Mosaic Inspector** then shows the tiles' footprints and composite from your FITS. DWARF FITS have no plate-solve: select each frame's `.wcs` file with it (same name, as written by ASTAP, astrometry.net or Scope Archive's Milky Way tab).

## Plan a Milky Way mosaic { #milky-way-planner }

**App:** Dwarfium Lite → `/mosaic-planner-en` (or `-fr`), works from a phone

1. Pick a **Site** or use the browser's location.
2. The sky chart shows the twilight, the galactic plane and the Moon.
3. Center a grid of tiles sized to your Dwarf's **Wide** field (EQ or Alt-Az framing); set each tile's exposure and count.
4. Check the **Moon** per tile (position, altitude, phase at that tile's time).
5. **Send**: one program per tile, named `MW Tile R1C1`, `MW Tile R1C2`… in Lite's scheduler.

## Keep the trees / roof sharp in front of the Milky Way { #foreground }

**Apps:** Dwarfium Lite (planner) + Scope Archive (assembly)

The sky turns 15° an hour, the foreground doesn't: over a 2-hour mosaic each tile sees the trees elsewhere against the stars.

- In the Milky Way planner, tick **Foreground pass** (at the start or at the end, 5 images per tile by default): the same tiles again, one right after the other, named `MW Tile R1C1 Decor`. The foreground is frozen at almost the same time on every tile.
- Scope Archive's Milky Way tab puts that foreground back in front of the mosaic.

For a single wide session whose foreground came out smeared, see [Fix the foreground](process.md#fix-foreground).

## Assemble the Milky Way tiles { #milky-way-assembly }

**App:** Scope Archive → **Mosaic** → **Milky Way** tab

1. The tab lists the mosaics found on the backup drive — sessions named `R<row>C<col>`, grouped by name and night — or takes the FITS of a folder you choose.
2. Tick the tiles → **Assemble**. Each tile is placed where its sky is (plate solved if needed), corrected for lens distortion, its foreground left out, its brightness and colour levelled with its neighbours.
3. Output in `MOSAIC_WCS` next to the sessions: a linear 32-bit FITS with its WCS (for Siril) and a stretched preview. About 2 min and 1 GB for 5 tiles.

The assembly keeps running if you go to another page: come back to the tab to see its progress. From Explore, **Mosaic (astrometry)** on a tile's session opens the tab on its mosaic.

## Stitch, merge or repair a Dwarf mosaic { #stitch }

**App:** Scope Archive → **Mosaic**

| Mode | Use it to |
|---|---|
| **Stitch** | Assemble selected panels into a wide image from their WCS |
| **Merge** | Add panels from a second session to a first one |
| **Repair** | Fix a mosaic whose transfer was interrupted (a small correct session as reference) |

Mosaics without a final stacked file are listed in **Dwarf Configuration → Sessions with Errors**.
