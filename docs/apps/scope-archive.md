---
tags:
  - Scope Archive
---

# Dwarfium Scope Archive

**Backs up, organises, explores and processes** your Dwarf sessions — and tells you what to shoot tonight. It works with the Dwarf's files (USB, FTP, MTP), not its live connection. Each page has its own **Help** button.

[Releases](https://github.com/stevejcl/dwarfium-scope-archive/releases){ .md-button .md-button--primary } [Source](https://github.com/stevejcl/dwarfium-scope-archive){ .md-button }

## Pages

| Page | What it does | How-to |
|---|---|---|
| Home | Slideshow of your favourite images | [Explore](../how-to/explore.md#explore) |
| What to shoot tonight | Targets well placed tonight, plan them on a Dwarf, tonight's plan | [Tonight](../how-to/plan.md#tonight) |
| Dwarf Configuration | Your Dwarfs (USB path, IP, model); analyze a Dwarf's drive; sessions with errors | [Back up](../how-to/archive.md#transfer) |
| Backup Drive | Your backup drives; analyze, check integrity, transfer history | [Back up](../how-to/archive.md#analyze-all) |
| Explore | Every session by object, filters, details, gallery, frames, notes, scores, Clean / Restore FITS, Prepare for Siril, SkyBot, Megastack | [Explore](../how-to/explore.md#explore) |
| Transfer | Archive (Dwarf → backup) or Restore, USB or FTP, in the background | [Back up](../how-to/archive.md#transfer) |
| Import a session | One session sent from Dwarfium Lite | [Archive one session](../how-to/archive.md#one-session) |
| Manual Sessions / Manual Explore | Your processed images, linked to their raw session | [Manual sessions](../how-to/process.md#manual-sessions) |
| Dark Library | Your dark frames and how they match the sessions | [Darks](../how-to/process.md#darks) |
| Mosaic | Stitch, Merge, Repair, **Milky Way** | [Mosaics](../how-to/mosaic.md#stitch) |
| Storage Report | Which sessions take the space | [Report](../how-to/archive.md#report) |
| Sky Map | All your sessions on the sky (Aladin Lite) | [Sky map](../how-to/explore.md#sky-map) |
| Catalog | DSO catalog; assign a target to a session | [Explore](../how-to/explore.md#explore) |
| MTP Device | DWARF II over MTP (Windows) | [Back up](../how-to/archive.md#transfer) |
| Analyze everything | Re-analyze every Dwarf copy and backup drive | [Re-sync](../how-to/archive.md#analyze-all) |
| Settings | Language, theme, database backup, astrometry (ASTAP, Nova), stitch parameters, PDF report, LAN | [DB backup](../how-to/archive.md#db-backup) |

## Command-line tools

Run from the installation folder: `tools/db_diagnostic.py`, `db_cleanup_dupes.py`, `db_report_pdf.py`, `quality_scan.py`, `skybot_scan.py`, `astrometry_scan.py`, `video_export.py`, `full_rescan.py`.

## Good to know

- Database: `dwarf_backup.db`, upgraded automatically with each version.
- DWARF II: no USB drive access — FTP, or MTP on Windows. DWARF 3 and mini can't be told apart over FTP: the configured model is trusted.
