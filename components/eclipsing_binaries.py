"""Eclipsing binaries: their next minima, to plan and capture them here and
measure them afterwards in Siril or AstroImageJ (user-requested Oct 2026:
"des Dwarf 2 et un Dwarf 3 qui s'ennuient, ils pourraient faire des mesures
des étoiles variables" - then "planifier et acquérir ici puis mesurer dans
Siril ou AstroImageJ, binaires à éclipses").

An eclipsing binary's minima come back every period: T = Epoch + n x P
(primary minima), T + P/2 for the secondary ones (a circular orbit). Epoch
is a heliocentric time (HJD): the light reaches the Sun up to 8.3 min before
or after it reaches us, so each predicted minimum is converted back to the
Earth's time (JD) before being shown - with the same low-precision Sun as
sky_altitude.py, well under 10 s here.

The stars and their elements (RA/Dec, epoch, period, magnitudes, variability
type, eclipse duration) are in eclipsing_binaries.json (working folder, as
end_of_night.json). SEED_STARS are the bright ones a Dwarf can measure;
their elements are fetched from the AAVSO's VSX (its JSON API, by name) the
first time, and can be refreshed, or typed in (e.g. the more up-to-date
elements of the Krakow "Up-to-date linear elements" list).

All datetimes are NAIVE wall-clock times in `tz` (the Dwarf's site
timezone), as in sky_altitude.py."""
from __future__ import annotations

import json
import math
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path

import requests

from components.sky_altitude import (
    DARKNESS_LEVELS,
    _altitude_deg,
    _julian_date,
    _local_sidereal_deg,
    sun_radec,
    to_utc,
)

STARS_FILE = Path("eclipsing_binaries.json")

VSX_URL = "https://www.aavso.org/vsx/index.php"
_VSX_TIMEOUT_S = 20

# Algol-type and other eclipsing binaries, bright enough for a Dwarf
# (maximum about mag 6 to 11) and deep enough to be measured with it (half a
# magnitude or more), north and south. Names as VSX knows them.
SEED_STARS = (
    "RZ Cas", "TV Cas", "AB Cas", "U Cep", "Y Cam", "XZ And", "RT And",
    "X Tri", "Z Per", "RW Tau", "TX UMa", "Z Dra", "TW Dra", "RZ Dra",
    "AI Dra", "U CrB", "SZ Her", "TX Her", "U Sge", "Z Vul", "WW Cyg",
    "AR Lac", "SW Lac", "Y Psc", "RY Aqr", "V505 Sgr", "RS Sgr", "R Ara",
)

# Light time for 1 AU, in days
_AU_LIGHT_DAYS = 0.0057755
_DEG = math.pi / 180.0
_SAMPLE_MIN = 5

# Observation window around a minimum when the eclipse duration is unknown:
# minimum +/- this many hours.
DEFAULT_HALF_WINDOW_H = 1.5
# Added on each side of a known eclipse: the light curve's flat parts
# before and after it, for the comparison.
WINDOW_MARGIN_H = 0.5

_lock = threading.Lock()


class _Feature:
    """On / off for this run of the app only (user-requested Oct 2026:
    optional, a button at the top right of the Programs page, the choice
    kept while the app runs): off, the editor shows no eclipsing binary
    button and nothing is read or fetched."""
    enabled = False


# The editor's button binds its visibility to feature.enabled
feature = _Feature()


# ── stars file ────────────────────────────────────────────────────────────
def _read_file() -> dict:
    if not STARS_FILE.exists():
        return {}
    try:
        data = json.loads(STARS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_file(data: dict) -> None:
    tmp = STARS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STARS_FILE)


def _key(name: str) -> str:
    return " ".join(str(name or "").split()).lower()


def load_stars() -> list[dict]:
    """Every star: the seed stars (minus the ones the user removed) then the
    user's own, each with its elements when known (see has_elements())."""
    data = _read_file()
    saved = {_key(s.get("name")): s for s in data.get("stars", []) if isinstance(s, dict) and s.get("name")}
    removed = {_key(n) for n in data.get("removed", [])}
    stars = []
    for name in SEED_STARS:
        if _key(name) not in removed:
            stars.append({**saved.pop(_key(name), {}), "name": name})
    stars.extend(s for k, s in saved.items() if k not in removed)
    return stars


def save_star(star: dict) -> None:
    """Adds or replaces a star (same name), and brings it back if it had
    been removed."""
    with _lock:
        data = _read_file()
        key = _key(star.get("name"))
        stars = [s for s in data.get("stars", []) if _key(s.get("name")) != key]
        stars.append(star)
        data["stars"] = stars
        data["removed"] = [n for n in data.get("removed", []) if _key(n) != key]
        _write_file(data)


def remove_star(name: str) -> None:
    with _lock:
        data = _read_file()
        key = _key(name)
        data["stars"] = [s for s in data.get("stars", []) if _key(s.get("name")) != key]
        removed = [n for n in data.get("removed", []) if _key(n) != key]
        if any(_key(n) == key for n in SEED_STARS):
            removed.append(name)
        data["removed"] = removed
        _write_file(data)


def has_elements(star: dict) -> bool:
    try:
        return (float(star["period_d"]) > 0 and float(star["epoch_hjd"]) > 2400000
                and star.get("ra_hours") is not None and star.get("dec_deg") is not None)
    except (KeyError, TypeError, ValueError):
        return False


# ── VSX ───────────────────────────────────────────────────────────────────
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _first_number(value) -> float | None:
    match = _NUMBER.search(str(value if value is not None else ""))
    return float(match.group()) if match else None


def parse_vsx_object(name: str, obj: dict) -> dict:
    """A star's entry from VSX's api.object answer ("VSXObject": RA2000 /
    Declination2000 in decimal degrees, Period in days, Epoch in HJD,
    MaxMag "6.18 V", MinMag "7.72 V" or an amplitude "(0.52) V"...).
    Raises ValueError when VSX doesn't know the star."""
    if not isinstance(obj, dict) or not obj:
        raise ValueError(f"{name}: not found in VSX")
    ra_deg = _first_number(obj.get("RA2000"))
    dec_deg = _first_number(obj.get("Declination2000"))
    if ra_deg is None or dec_deg is None:
        raise ValueError(f"{name}: no coordinates in VSX")
    max_mag = _first_number(obj.get("MaxMag"))
    min_text = str(obj.get("MinMag") or "")
    min_mag = _first_number(min_text)
    if min_mag is not None and min_text.lstrip().startswith("(") and max_mag is not None:
        min_mag = max_mag + min_mag  # an amplitude
    # Eclipse duration, in % of the period ("D" in the GCVS)
    duration_pct = next(
        (_first_number(v) for k, v in obj.items() if "duration" in k.lower() and _first_number(v)), None
    )
    band = (re.sub(r"[\d.()\s<>:-]+", " ", str(obj.get("MaxMag") or "")).split() or [""])[0]
    return {
        "name": obj.get("Name") or name,
        "ra_hours": (ra_deg / 15.0) % 24,
        "dec_deg": dec_deg,
        "vartype": obj.get("VariabilityType") or "",
        "period_d": _first_number(obj.get("Period")),
        "epoch_hjd": _first_number(obj.get("Epoch")),
        "max_mag": max_mag,
        "min_mag": min_mag,
        "band": band,
        "duration_pct": duration_pct,
        "constellation": obj.get("Constellation") or "",
        "auid": obj.get("AUID") or "",
        "source": "VSX",
        "updated": datetime.now().strftime("%Y-%m-%d"),
    }


def fetch_vsx(name: str) -> dict:
    """The star's elements from VSX (network). Raises ValueError (unknown
    star) or requests.RequestException."""
    response = requests.get(
        VSX_URL,
        params={"view": "api.object", "ident": name, "format": "json"},
        timeout=_VSX_TIMEOUT_S,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError:
        raise ValueError(f"{name}: not found in VSX")
    obj = payload.get("VSXObject") if isinstance(payload, dict) else None
    return parse_vsx_object(name, obj or {})


def update_from_vsx(star: dict) -> dict:
    """Fetched elements merged over the saved ones - and saved. Elements the
    user typed in themselves (source "manual") keep their epoch and period:
    only the rest is completed from VSX."""
    fetched = fetch_vsx(star["name"])
    merged = {**star, **{k: v for k, v in fetched.items() if v not in (None, "")}}
    if star.get("source") == "manual" and has_elements(star):
        merged.update(epoch_hjd=star["epoch_hjd"], period_d=star["period_d"], source="manual")
    merged["name"] = star["name"]
    save_star(merged)
    return merged


class _FetchProgress:
    """The VSX update running, if any - shown by the editor's dialog."""
    running = False
    done = 0
    total = 0
    failed: list[str] = []


progress = _FetchProgress()
_fetch_lock = threading.Lock()
_progress_lock = threading.Lock()
# Stars fetched at the same time (user-reported Oct 2026: one after the
# other, the 28 seed stars took long, the dialog's button greyed meanwhile)
_FETCH_WORKERS = 4


def fetch_elements(only_missing: bool = True) -> list[str]:
    """The stars' elements from VSX (network) - only those that have none
    yet, or all of them. Returns the names that could not be fetched. One
    update at a time: called while one runs (the Programs page's button,
    then the dialog), it waits for it and returns its result. A network
    failure skips the stars not tried yet (VSX not reachable)."""
    if not _fetch_lock.acquire(blocking=False):
        with _fetch_lock:
            return list(progress.failed)
    try:
        todo = [s for s in load_stars() if not (only_missing and has_elements(s))]
        progress.done, progress.total, progress.failed, progress.running = 0, len(todo), [], True
        unreachable = threading.Event()

        def _one(star: dict) -> None:
            failed = unreachable.is_set()
            if not failed:
                try:
                    update_from_vsx(star)
                except requests.RequestException:
                    unreachable.set()
                    failed = True
                except ValueError:
                    failed = True
            with _progress_lock:
                progress.done += 1
                if failed:
                    progress.failed.append(star["name"])

        with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
            list(pool.map(_one, todo))
        return list(progress.failed)
    finally:
        progress.running = False
        _fetch_lock.release()


# ── predictions ───────────────────────────────────────────────────────────
def heliocentric_correction_days(jd: float, ra_deg: float, dec_deg: float) -> float:
    """HJD - JD for a star at ra/dec (J2000) seen at jd: positive when the
    Earth is between the Sun and the star (its light reaches us first)."""
    eps = 23.439 * _DEG
    ra, dec = ra_deg * _DEG, dec_deg * _DEG
    beta = math.asin(math.sin(dec) * math.cos(eps) - math.cos(dec) * math.sin(eps) * math.sin(ra))
    lam = math.atan2(math.sin(ra) * math.cos(eps) + math.tan(dec) * math.sin(eps), math.cos(ra))
    d = jd - 2451545.0
    g = (357.529 + 0.98560028 * d) * _DEG
    distance_au = 1.00014 - 0.01671 * math.cos(g) - 0.00014 * math.cos(2 * g)
    _, _, sun_lon = sun_radec(jd)
    return -_AU_LIGHT_DAYS * distance_au * math.cos(beta) * math.cos(lam - sun_lon * _DEG)


def _local_from_jd(jd: float, tz: tzinfo | None) -> datetime:
    aware = datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jd - 2451545.0)
    return (aware.astimezone(tz) if tz is not None else aware.astimezone()).replace(tzinfo=None)


def half_window_hours(star: dict) -> float:
    """Half of the window to capture around a minimum: half the eclipse plus
    WINDOW_MARGIN_H when its duration is known, else DEFAULT_HALF_WINDOW_H."""
    try:
        duration_h = float(star["duration_pct"]) / 100.0 * float(star["period_d"]) * 24.0
    except (KeyError, TypeError, ValueError):
        return DEFAULT_HALF_WINDOW_H
    if duration_h <= 0:
        return DEFAULT_HALF_WINDOW_H
    return duration_h / 2 + WINDOW_MARGIN_H


@dataclass
class Minimum:
    star: dict
    primary: bool
    time: datetime              # the predicted minimum, site time
    hjd: float
    window_start: datetime
    window_end: datetime
    altitude: float             # at the minimum
    full: bool                  # the whole window dark and high enough

    @property
    def name(self) -> str:
        return self.star.get("name", "")


def predict_minima(
    star: dict,
    latitude: float,
    longitude: float,
    night_of: datetime,
    *,
    nights: int = 1,
    min_altitude: float = 30.0,
    darkness: str = "astronomical",
    secondary: bool = False,
    half_window_h: float | None = None,
    tz: tzinfo | None = None,
) -> list[Minimum]:
    """The star's minima from noon of night_of's date over `nights` nights
    that can be observed: the minimum itself in the dark and at least
    min_altitude high. full tells whether the whole window around it is
    too. half_window_h: None = half_window_hours(star)."""
    if not has_elements(star):
        return []
    period = float(star["period_d"])
    epoch = float(star["epoch_hjd"])
    ra_deg = float(star["ra_hours"]) * 15.0
    dec_deg = float(star["dec_deg"])
    sun_limit = DARKNESS_LEVELS.get(darkness, DARKNESS_LEVELS["astronomical"])
    half = timedelta(hours=half_window_h if half_window_h is not None else half_window_hours(star))

    def observable(local: datetime) -> tuple[bool, float]:
        jd = _julian_date(to_utc(local, tz))
        lst = _local_sidereal_deg(jd, longitude)
        sra, sdec, _ = sun_radec(jd)
        alt = _altitude_deg(ra_deg, dec_deg, lst, latitude)
        return alt >= min_altitude and _altitude_deg(sra, sdec, lst, latitude) <= sun_limit, alt

    start = night_of.replace(hour=12, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=max(1, nights))
    jd_start = _julian_date(to_utc(start, tz))
    jd_end = _julian_date(to_utc(end, tz))
    phases = (0.0, 0.5) if secondary else (0.0,)
    result: list[Minimum] = []
    steps = int(half.total_seconds() // 60 // _SAMPLE_MIN)
    # From one cycle before the first night (the light-time shift) to past the last
    n = math.floor((jd_start - epoch) / period) - 1
    while epoch + n * period <= jd_end + 0.01:
        for phase in phases:
            hjd = epoch + (n + phase) * period
            jd = hjd - heliocentric_correction_days(hjd, ra_deg, dec_deg)
            if not jd_start <= jd < jd_end:
                continue
            local = _local_from_jd(jd, tz)
            ok, alt = observable(local)
            if not ok:
                continue
            full = all(observable(local + timedelta(minutes=i * _SAMPLE_MIN))[0] for i in range(-steps, steps + 1))
            full = full and observable(local - half)[0] and observable(local + half)[0]
            # Whole minutes, the window widened to them (the editor's times)
            window_start = (local - half).replace(second=0, microsecond=0)
            window_end = (local + half).replace(second=0, microsecond=0) + timedelta(minutes=1)
            result.append(Minimum(star, phase == 0.0, local, hjd, window_start, window_end, alt, full))
        n += 1
    return result


def predict_all(stars: list[dict], latitude: float, longitude: float, night_of: datetime, **kwargs) -> list[Minimum]:
    """Every star's minima (see predict_minima()), in time order."""
    minima = []
    for star in stars:
        minima.extend(predict_minima(star, latitude, longitude, night_of, **kwargs))
    return sorted(minima, key=lambda m: m.time)


def describe(minimum: Minimum) -> str:
    """Program description: what is captured and why, kept with the session
    for the measurement afterwards."""
    star = minimum.star
    kind = "primary" if minimum.primary else "secondary"
    parts = [f"Eclipsing binary {minimum.name}"]
    if star.get("vartype"):
        parts.append(f"({star['vartype']})")
    parts.append(f"- {kind} minimum predicted {minimum.time:%Y-%m-%d %H:%M} (HJD {minimum.hjd:.4f})")
    if star.get("max_mag") is not None and star.get("min_mag") is not None:
        parts.append(f"- mag {float(star['max_mag']):.1f}-{float(star['min_mag']):.1f}")
    parts.append("- photometry: Siril / AstroImageJ")
    return " ".join(parts)
