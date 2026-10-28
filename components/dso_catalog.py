"""DSO catalog shared with Dwarfium Scope Archive (user-requested Oct
2026: "faire le lien entre Dwarf Scope Archive et Astro Session, par
exemple en partageant le catalog de Dwarfium Archive, pour selectionner
une cible sous Astro Session en plus de Stellarium").

Same file, same schema as dwarfium-scope-archive's db/dso_catalog.json
(designation, displayName, alternateNames, ra "5h 35m 17s", dec
"-05deg 23' 28\"", type, typeCategory, constellation, magnitude, size...)
- read as-is, never converted to a format of our own, so an updated
catalog from that project can simply be dropped in.

Lookup order (first file found wins):
  1. $DWARFIUM_ARCHIVE_DIR/db/dso_catalog.json - an explicit pointer to
     a Dwarfium Scope Archive install.
  2. A Dwarfium Scope Archive install sitting NEXT TO this app (source
     checkout "dwarfium-scope-archive/" or packaged
     "DwarfiumScopeArchive/", both ship db/dso_catalog.json) - so the
     two apps automatically share the same, most up to date, catalog.
  3. assets/dso_catalog.json - the copy shipped with this app (a loose,
     replaceable file next to the .exe, same as catalog.html - see
     api_routes.py's _external_path()).

Then catalog_add_on.json (see components/catalog_add_on.py) is appended
after it - a second file, so dso_catalog.json is never modified. It sits
next to Dwarfium Scope Archive's catalog (that app reads it too), else in
the user's folder (~/.astro_dwarf_session, components/my_targets.py), not
in assets/ that an update may replace (issue #162; moved from there once).
A user object that the shared catalog has too is not listed twice: the
shared entry is kept, the user's name for it carried onto it
(_userDesignation) so its favourite stays."""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from components.sky_altitude import (
    DARKNESS_LEVELS,
    _altitude_deg,
    _julian_date,
    _local_sidereal_deg,
    sun_radec,
    to_utc,
)

_ARCHIVE_DIR_NAMES = ("dwarfium-scope-archive", "DwarfiumScopeArchive", "Dwarfium Scope Archive")

_cache: list[dict] | None = None
_cache_source: Path | None = None
_user_count = 0


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    env_dir = os.environ.get("DWARFIUM_ARCHIVE_DIR", "").strip()
    if env_dir:
        paths.append(Path(env_dir) / "db" / "dso_catalog.json")
    parent = _app_dir().parent
    for name in _ARCHIVE_DIR_NAMES:
        paths.append(parent / name / "db" / "dso_catalog.json")
        paths.append(parent / name / "dist" / "db" / "dso_catalog.json")
    paths.append(_app_dir() / "assets" / "dso_catalog.json")
    return paths


def parse_ra_hours(value: str) -> float | None:
    """'5h 35m 17s' (or '5 35 17') -> 5.588 decimal hours."""
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", str(value or ""))
    if not nums:
        return None
    h, m, s = (float(n) for n in (nums + ["0", "0"])[:3])
    return (h + m / 60 + s / 3600) % 24


def parse_dec_degrees(value: str) -> float | None:
    """'-05deg 23' 28"' (any of the usual separators) -> -5.391 degrees."""
    text = str(value or "").strip()
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if not nums:
        return None
    d, m, s = (float(n) for n in (nums + ["0", "0"])[:3])
    sign = -1 if text.startswith("-") or text.startswith("−") else 1
    return sign * (d + m / 60 + s / 3600)


def load_catalog(force_reload: bool = False) -> list[dict]:
    """Catalog entries, each with ra_hours/dec_deg added (entries whose
    coordinates don't parse are skipped), followed by the user's own
    objects (catalog_add_on.json) not already in the shared catalog.
    Cached after the first call."""
    global _cache, _cache_source, _user_count
    if _cache is not None and not force_reload:
        return _cache

    from components import catalog_add_on

    entries, source = [], None
    for path in _candidate_paths():
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        entries, source = _with_coordinates(raw), path
        break

    # A user object later added to the shared catalog itself: the shared
    # entry, with the user's name for it (its favourite kept)
    shared_count = len(entries)
    for item in _with_coordinates(catalog_add_on.read_entries(_add_on_path_for(source))):
        same = catalog_add_on.find_duplicate(item, item["ra_hours"], item["dec_deg"], entries[:shared_count])
        if same is None:
            entries.append({**item, "_addOn": True})
            continue
        index = next(i for i, e in enumerate(entries) if e is same)
        if item.get("designation") and item["designation"] != same.get("designation"):
            entries[index] = {**same, "_userDesignation": item["designation"]}

    _cache, _cache_source, _user_count = entries, source, len(entries) - shared_count
    return _cache


def _with_coordinates(raw: list) -> list[dict]:
    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ra_hours = parse_ra_hours(item.get("ra"))
        dec_deg = parse_dec_degrees(item.get("dec"))
        if ra_hours is None or dec_deg is None:
            continue
        entries.append({**item, "ra_hours": ra_hours, "dec_deg": dec_deg})
    return entries


def _add_on_path_for(source: Path | None) -> Path:
    """Next to Dwarfium Scope Archive's catalog (it reads the file too),
    else in the user's folder - moved there once from assets/."""
    from components.my_targets import USER_DIR

    assets = _app_dir() / "assets"
    if source and source.parent.resolve() != assets.resolve():
        return source.parent / "catalog_add_on.json"
    path = USER_DIR / "catalog_add_on.json"
    old = assets / "catalog_add_on.json"
    if not path.exists() and old.is_file():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(old.read_bytes())
            old.rename(old.with_name("catalog_add_on.json.moved"))
        except OSError:
            return old if not path.exists() else path
    return path


def add_on_path() -> Path:
    """catalog_add_on.json in use (_add_on_path_for()) - where new objects
    are written and read."""
    return _add_on_path_for(catalog_source())


def user_entry_count() -> int:
    """How many of load_catalog()'s entries come from catalog_add_on.json."""
    load_catalog()
    return _user_count


def catalog_source() -> Path | None:
    load_catalog()
    return _cache_source


def short_name(entry: dict) -> str:
    """Target name as Dwarfium Scope Archive shows it (its Astro Object
    description): displayName up to the first comma, e.g. "M 42 - Great
    Nebula in Orion, Great Orion Nebula,Orion Nebula" -> "M 42 - Great
    Nebula in Orion"."""
    name = (entry.get("displayName") or "").split(",")[0].strip()
    return name or entry.get("designation") or ""


def describe(entry: dict) -> str:
    """Same "Observation of X (Type) in Constellation (Mag: Y)" shape
    stellarium.py builds, so a program description reads the same
    whichever way its target was picked."""
    if entry.get("_description"):   # a recent target: its program's own description
        return entry["_description"]
    parts = [f"Observation of {short_name(entry)}"]
    if entry.get("type") and not str(entry["type"]).startswith("Other classification"):
        parts.append(f"({entry['type']})")
    if entry.get("constellation"):
        parts.append(f"in {entry['constellation']}")
    if entry.get("magnitude") is not None:
        try:
            parts.append(f"(Mag: {float(entry['magnitude']):.1f})")
        except (TypeError, ValueError):
            pass
    return " ".join(parts)


def max_dark_altitudes(
    entries: list[dict],
    latitude: float,
    longitude: float,
    night_of: datetime,
    darkness: str = "astronomical",
    step_minutes: int = 15,
    tz=None,
) -> list[float | None]:
    """Highest altitude each entry reaches while the sky is dark on the
    night of `night_of` (naive local date) - a cheap per-row "is it worth
    it tonight" column for the catalog picker. None when there's no dark
    period at all that night (e.g. summer at high latitude). tz: as in
    sky_altitude.compute_night_plan()."""
    sun_limit = DARKNESS_LEVELS.get(darkness, DARKNESS_LEVELS["astronomical"])
    start = night_of.replace(hour=12, minute=0, second=0, microsecond=0)
    dark_lsts: list[float] = []
    for i in range((24 * 60) // step_minutes + 1):
        jd = _julian_date(to_utc(start + timedelta(minutes=i * step_minutes), tz))
        lst = _local_sidereal_deg(jd, longitude)
        sra, sdec, _ = sun_radec(jd)
        if _altitude_deg(sra, sdec, lst, latitude) <= sun_limit:
            dark_lsts.append(lst)
    if not dark_lsts:
        return [None] * len(entries)

    lat = math.radians(latitude)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    result: list[float | None] = []
    for entry in entries:
        ra_deg = entry["ra_hours"] * 15.0
        dec = math.radians(entry["dec_deg"])
        a, b = sin_lat * math.sin(dec), cos_lat * math.cos(dec)
        best_cos_ha = max(math.cos(math.radians(lst - ra_deg)) for lst in dark_lsts)
        result.append(math.degrees(math.asin(max(-1.0, min(1.0, a + b * best_cos_ha)))))
    return result
