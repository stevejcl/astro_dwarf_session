"""Telescopius CSV import (point C, second half): generates a CHAIN of
programs from a Telescopius target-list or Mosaic-plan CSV export, each
one starting right after the previous one's estimated finish time.

Ported verbatim from astro_dwarf_session's own tabs/create_session.py:
- Format detection (by header names) and RA/Dec string parsing:
  convert_ra_to_hourdecimal()/convert_dec_to_degrees().
- The chaining logic itself: calculate_end_time()'s wait_time formula
  (a fixed per-action overhead PLUS that action's own wait_before/
  wait_after, summed across whichever actions are enabled) plus the
  capture time itself. Adapted here to read our own JSON schema's dict
  shape (do_action/wait_before/wait_after under eq_solving/auto_focus/
  etc.) instead of Tkinter's settings_vars, but the arithmetic and the
  magic per-action overhead constants (60s for eq_solving, 10s for
  auto_focus, 5s for infinite_focus, 70s for calibration, 30s for a
  goto, 15s for camera setup, +1s per exposure) are unchanged - these
  aren't guessed, they're the existing tool's own timing model."""
from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import datetime, timedelta
from fractions import Fraction


def detect_csv_format(fieldnames: list[str]) -> str | None:
    """Returns "mosaic", "telescopius_list", or None (unrecognized)."""
    fields = {f.strip() for f in fieldnames}
    if {"Pane", "RA", "DEC"} <= fields:
        return "mosaic"
    if {"Catalogue Entry", "Right Ascension (j2000)", "Declination (j2000)"} <= fields:
        return "telescopius_list"
    return None


def convert_ra_to_hourdecimal(ra_str) -> float:
    """Same intent as the original convert_ra_to_hourdecimal(), but
    STRENGTHENED after finding a real Telescopius Mosaic CSV export
    (via Telescopius's own support forum) using typographic/smart
    quotes for arcmin/arcsec - e.g. "05hr 05' 30"" with U+2019/U+201D
    characters, not the straight ASCII "'"/'"' the original's explicit
    .replace("'", '')/.replace('"', '') calls only ever stripped. That
    silently produced 0.0 (wrong coordinates, not an error) instead of
    the real RA for any such export - confirmed by testing this exact
    real-world example. Ported convert_dec_to_degrees() below already
    used a permissive regex (strip anything that isn't digit/dot/space/
    colon/minus) rather than an explicit small blacklist, which is why
    it was already robust to this - this function now does the same,
    rather than staying selectively fragile."""
    if isinstance(ra_str, float):
        return ra_str
    cleaned = re.sub(r"[^\d\.\s:-]", " ", str(ra_str)).strip()
    try:
        return float(cleaned)
    except ValueError:
        pass

    parts = cleaned.split(":") if ":" in cleaned else cleaned.split()
    while len(parts) < 3:
        parts.append("0")
    try:
        h, m, s = map(float, parts[:3])
    except Exception:
        return 0.0
    return h + m / 60 + s / 3600


def convert_dec_to_degrees(dec_str) -> float:
    """Verbatim port - same tolerant parsing as convert_ra_to_hourdecimal,
    with correct sign handling: for a negative declination, minutes/
    seconds subtract further from zero rather than toward it."""
    cleaned = re.sub(r"[^\d\.\s:-]", "", str(dec_str)).strip()
    try:
        return float(cleaned)
    except ValueError:
        pass

    parts = cleaned.split(":") if ":" in cleaned else cleaned.split()
    while len(parts) < 3:
        parts.append("0")
    try:
        d, m, s = map(float, parts[:3])
    except Exception:
        return 0.0
    if d < 0:
        return d - (m / 60) - (s / 3600)
    return d + (m / 60) + (s / 3600)


def parse_csv_rows(csv_text: str) -> tuple[str | None, list[dict]]:
    """Returns (format, rows) where each row is
    {"target": str, "description": str, "ra_hours": float, "dec_degrees": float}.
    format is None (and rows empty) if the header doesn't match either
    known layout."""
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        return None, []
    fieldnames = [f.strip() for f in reader.fieldnames]
    reader.fieldnames = fieldnames

    fmt = detect_csv_format(fieldnames)
    if fmt is None:
        return None, []

    rows: list[dict] = []
    for raw_row in reader:
        if fmt == "mosaic":
            pane = raw_row.get("Pane", "")
            ra = raw_row.get("RA", "")
            dec = raw_row.get("DEC", "")
            target = f"Mosaic {pane}"
            description = f"Observation of Mosaic {pane}"
        else:  # telescopius_list
            catalogue_entry = raw_row.get("Catalogue Entry", "")
            ra = raw_row.get("Right Ascension (j2000)", "")
            dec = raw_row.get("Declination (j2000)", "")
            target = catalogue_entry
            description = f"Observation of {catalogue_entry}"

        rows.append(
            {
                "target": target,
                "description": description,
                "ra_hours": convert_ra_to_hourdecimal(ra),
                "dec_degrees": convert_dec_to_degrees(dec),
            }
        )
    return fmt, rows


def _exposure_seconds(exposure_str) -> float:
    """Mirrors get_exposure_time() - exposure fields can be a fraction
    like "1/500" (used for photo mode; harmless for astro mode's plain
    integers too)."""
    if not exposure_str:
        return 0.0
    try:
        if "/" in str(exposure_str):
            return float(Fraction(str(exposure_str)))
        return float(exposure_str)
    except (ValueError, ZeroDivisionError):
        return 0.0


def estimate_session_duration_seconds(cmd: dict) -> float:
    """Port of calculate_end_time()'s wait_time + capture-time formula,
    reading our own JSON schema (cmd = program["command"]) instead of
    Tkinter's settings_vars. The per-action overhead constants (60/10/
    5/70/30/15s) are the original tool's own timing model, not
    estimated here."""
    wait_time = 0.0

    eq = cmd.get("eq_solving", {})
    if eq.get("do_action"):
        wait_time += 60 + eq.get("wait_before", 0) + eq.get("wait_after", 0)

    af = cmd.get("auto_focus", {})
    if af.get("do_action"):
        wait_time += 10 + af.get("wait_before", 0) + af.get("wait_after", 0)

    inf_focus = cmd.get("infinite_focus", {})
    if inf_focus.get("do_action"):
        wait_time += 5 + inf_focus.get("wait_before", 0) + inf_focus.get("wait_after", 0)

    calib = cmd.get("calibration", {})
    if calib.get("do_action"):
        wait_time += 70 + calib.get("wait_before", 0) + calib.get("wait_after", 0)

    goto_solar = cmd.get("goto_solar", {})
    goto_manual = cmd.get("goto_manual", {})
    if goto_solar.get("do_action") or goto_manual.get("do_action"):
        wait_time += 30 + goto_solar.get("wait_after", 0)

    setup_camera = cmd.get("setup_camera", {})
    setup_wide = cmd.get("setup_wide_camera", {})
    active_camera = setup_wide if setup_wide.get("do_action") else setup_camera

    wait_time += 15 + active_camera.get("wait_after", 0)

    exposure = _exposure_seconds(active_camera.get("exposure", "0"))
    try:
        count = int(active_camera.get("count", 0) or 0)
    except (TypeError, ValueError):
        count = 0

    return wait_time + (exposure + 1) * count


def _json_deepcopy(d: dict) -> dict:
    return json.loads(json.dumps(d))


def generate_chained_programs(
    base_cmd: dict, rows: list[dict], start_datetime: datetime
) -> list[dict]:
    """base_cmd: the CURRENT program editor's settings (calibration,
    camera exposure/gain/count, wait times...) - used as a shared
    template for every generated row, only description/target/date/
    time/goto_manual differ per row. Each row's start time is the
    previous row's estimated finish time (see estimate_session_duration_
    seconds) - a faithful port of import_csv_and_generate_json()'s own
    chaining loop.

    Returns a list of full {"command": {...}} dicts, ready to be
    written out as individual ToDo files."""
    programs: list[dict] = []
    current_dt = start_datetime

    for row in rows:
        cmd = _json_deepcopy(base_cmd)
        id_command = cmd.setdefault("id_command", {})
        id_command["uuid"] = f"{uuid.uuid4()}-00001"
        id_command["description"] = row["description"]
        id_command["date"] = current_dt.strftime("%Y-%m-%d")
        id_command["time"] = current_dt.strftime("%H:%M:%S")
        id_command["process"] = "wait"
        id_command["result"] = False
        id_command["message"] = ""
        id_command["nb_try"] = 1

        cmd["goto_manual"] = {
            **cmd.get("goto_manual", {}),
            "do_action": True,
            "target": row["target"],
            "ra_coord": row["ra_hours"],
            "dec_coord": row["dec_degrees"],
        }
        cmd["goto_solar"] = {**cmd.get("goto_solar", {}), "do_action": False, "target": ""}

        programs.append({"command": cmd})

        duration_s = estimate_session_duration_seconds(cmd)
        current_dt = current_dt + timedelta(seconds=duration_s)

    return programs
