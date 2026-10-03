"""DSO catalog add-on - objects added on top of the shared Dwarfium
catalog (user-requested Oct 2026: "il manque peut-etre la possibilite
d'ajouter ses propres objets, par exemple ceux obtenus dans Astro Dwarf
Session par /catalog" - then "on pourrait creer un second fichier
catalog_add_on, qu'on importe apres").

A SECOND file, catalog_add_on.json, in the SAME folder as the
dso_catalog.json in use (see dso_catalog.add_on_path()): Dwarfium Scope
Archive's db/ when it is installed next to this app, else assets/.
dso_catalog.json itself is never written: it stays exactly as the
Dwarfium notebook (notebooks/5_create_catalogues.ipynb) produces it,
and Dwarfium Scope Archive can import catalog_add_on.json AFTER it with
the same importer.

Entries use the SAME schema as dso_catalog.json (designation,
displayName, alternateNames, ra "5h 35m 17s", dec "+05° 23' 28\"",
type, typeCategory, catalogue, objectNumber, constellation, magnitude,
size, notes, favorite) plus two extra keys: "source" (where the object
came from, e.g. "catalog.html") and "addedAt" (ISO timestamp).
dso_catalog.load_catalog() merges them after the shared catalog,
skipping any the shared catalog already has.

Today's only source: the /catalog page (JD's Deep Sky Catalog) - every
target it sends to /api/schedule carries a "catalogMeta" block (atlas
id, type code, magnitude, size, constellation, common name, Messier
cross-reference - see js/dwarf-scheduler.js), converted here. An object
already in the shared catalog or in this file (same designation, or
within DUPLICATE_RADIUS_ARCMIN) is not added again."""
from __future__ import annotations

import json
import math
import re
import threading
from datetime import datetime
from pathlib import Path

ADD_ON_FILE_NAME = "catalog_add_on.json"

DUPLICATE_RADIUS_ARCMIN = 2.0

_lock = threading.Lock()

# catalog.html's 6 atlas type codes -> (type, typeCategory) as the
# Dwarfium notebook writes them (OpenNGC type names).
_TYPE_MAP = {
    "GAL": ("Galaxy", "galaxies"),
    "NEB": ("Nebula", "nebulae"),
    "OC": ("Open Cluster", "clusters"),
    "GC": ("Globular Cluster", "clusters"),
    "PN": ("Planetary Nebula", "nebulae"),
    "SNR": ("Supernova remnant", "nebulae"),
}

# A "NEB" code is all catalog.html knows - the catalogue itself says more.
_NEBULA_TYPE_BY_CATALOGUE = {
    "B": "Dark Nebula",
    "LDN": "Dark Nebula",
    "Sh2": "HII Ionized region",
    "VdB": "Reflection Nebula",
}

# catalog.html ids whose prefix differs from the Dwarfium catalog's.
_CATALOGUE_ALIASES = {"Cl": "Cr"}

# IAU abbreviations -> constellation names as spelled in dso_catalog.json
# (Se1/Se2 are catalog.html's codes for the two halves of Serpens).
_CONSTELLATIONS = {
    "And": "Andromeda", "Ant": "Antlia", "Aps": "Apus", "Aql": "Aquila",
    "Aqr": "Aquarius", "Ara": "Ara", "Ari": "Aries", "Aur": "Auriga",
    "Boo": "Boötes", "CMa": "Canis Major", "CMi": "Canis Minor",
    "CVn": "Canes Venatici", "Cae": "Caelum", "Cam": "Camelopardalis",
    "Cap": "Capricornus", "Car": "Carina", "Cas": "Cassiopeia",
    "Cen": "Centaurus", "Cep": "Cepheus", "Cet": "Cetus", "Cha": "Chamaeleon",
    "Cir": "Circinus", "Cnc": "Cancer", "Col": "Columba",
    "Com": "Coma Berenices", "CrA": "Corona Australis",
    "CrB": "Corona Borealis", "Crt": "Crater", "Cru": "Crux", "Crv": "Corvus",
    "Cyg": "Cygnus", "Del": "Delphinus", "Dor": "Dorado", "Dra": "Draco",
    "Equ": "Equuleus", "Eri": "Eridanus", "For": "Fornax", "Gem": "Gemini",
    "Gru": "Grus", "Her": "Hercules", "Hor": "Horologium", "Hya": "Hydra",
    "Hyi": "Hydrus", "Ind": "Indus", "LMi": "Leo Minor", "Lac": "Lacerta",
    "Leo": "Leo", "Lep": "Lepus", "Lib": "Libra", "Lup": "Lupus", "Lyn": "Lynx",
    "Lyr": "Lyra", "Men": "Mensa", "Mic": "Microscopium", "Mon": "Monoceros",
    "Mus": "Musca", "Nor": "Norma", "Oct": "Octans", "Oph": "Ophiuchus",
    "Ori": "Orion", "Pav": "Pavo", "Peg": "Pegasus", "Per": "Perseus",
    "Phe": "Phoenix", "Pic": "Pictor", "PsA": "Piscis Austrinus",
    "Psc": "Pisces", "Pup": "Puppis", "Pyx": "Pyxis", "Ret": "Reticulum",
    "Scl": "Sculptor", "Sco": "Scorpius", "Sct": "Scutum",
    "Se1": "Serpens Caput", "Se2": "Serpens Cauda", "Ser": "Serpens",
    "Sex": "Sextans", "Sge": "Sagitta", "Sgr": "Sagittarius", "Tau": "Taurus",
    "Tel": "Telescopium", "TrA": "Triangulum Australe", "Tri": "Triangulum",
    "Tuc": "Tucana", "UMa": "Ursa Major", "UMi": "Ursa Minor", "Vel": "Vela",
    "Vir": "Virgo", "Vol": "Volans", "Vul": "Vulpecula",
}


# -- file ------------------------------------------------------------------

def read_entries(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return raw if isinstance(raw, list) else []


def _write_entries(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# -- formatting (same strings as dso_catalog.json) ------------------------

def _trim(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_ra(ra_hours: float) -> str:
    """5.5881 -> '5h 35m 17.2s'."""
    total = round((ra_hours % 24) * 3600, 1)
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return f"{int(h) % 24}h {int(m)}m {_trim(s)}s"


def format_dec(dec_deg: float) -> str:
    """-5.3911 -> '-05° 23\\' 28"'."""
    sign = "-" if dec_deg < 0 else "+"
    total = round(abs(dec_deg) * 3600, 1)
    d, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    sec = f"{int(s):02d}" if s == int(s) else _trim(s).zfill(4)
    return f"{sign}{int(d):02d}° {int(m):02d}' {sec}\""


def _split_id(atlas_id: str) -> tuple[str, str, int | None]:
    """catalog.html atlas id -> (designation, catalogue, objectNumber):
    'NGC0224' -> ('NGC 224', 'NGC', 224), 'Sh2-101' -> ('Sh2 101', 'Sh2',
    101), 'Cl399' -> ('Cr 399', 'Cr', 399), 'ESO056-115' -> ('ESO
    056-115', 'ESO', None). Anything else is kept as-is."""
    atlas_id = atlas_id.strip()
    m = re.fullmatch(r"Sh2-0*(\d+)", atlas_id)
    if m:
        return f"Sh2 {int(m.group(1))}", "Sh2", int(m.group(1))
    m = re.fullmatch(r"([A-Za-z]+)0*(\d+)", atlas_id)
    if m:
        catalogue = _CATALOGUE_ALIASES.get(m.group(1), m.group(1))
        return f"{catalogue} {int(m.group(2))}", catalogue, int(m.group(2))
    m = re.fullmatch(r"([A-Za-z]+)(\d.*)", atlas_id)
    if m and m.group(1) != "M":  # 'M1-67' is Minkowski, not Messier
        return f"{m.group(1)} {m.group(2)}", m.group(1), None
    return atlas_id, "", None


def _notes_for_size(size_arcmin: float | None) -> str:
    """Same size classes as the Dwarfium notebook's large/small/tiny_dso."""
    if size_arcmin is None or size_arcmin >= 15:
        return "large_dso"
    return "small_dso" if size_arcmin > 1 else "tiny_dso"


def _number(value) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def entry_from_catalog_page(meta: dict, ra_hours, dec_deg) -> dict | None:
    """One /catalog task (its catalogMeta + ra in hours, dec in degrees)
    -> a dso_catalog.json-shaped entry. None when unusable."""
    ra, dec = _number(ra_hours), _number(dec_deg)
    atlas_id = str(meta.get("id") or "").strip()
    if ra is None or dec is None or not atlas_id:
        return None

    designation, catalogue, number = _split_id(atlas_id)
    names: list[str] = []
    messier = str(meta.get("messier") or "").strip()
    m = re.fullmatch(r"M\s*0*(\d+)", messier)
    if m:
        # Messier first, like the Dwarfium catalog ('M 42', NGC as alternate).
        names.append(designation)
        designation, catalogue, number = f"M {int(m.group(1))}", "M", int(m.group(1))
    common = [n.strip() for n in str(meta.get("commonName") or "").split("·") if n.strip()]
    names.extend(common)
    alternate = ", ".join(dict.fromkeys(names)) or None

    type_name, category = _TYPE_MAP.get(str(meta.get("type") or "").upper(), ("Other classification (see object notes)", "other"))
    if type_name == "Nebula":
        type_name = _NEBULA_TYPE_BY_CATALOGUE.get(catalogue, type_name)

    size = _number(meta.get("size"))
    con = str(meta.get("con") or "").strip()
    return {
        "dec": format_dec(dec),
        "designation": designation,
        "magnitude": _number(meta.get("mag")),
        "type": type_name,
        "typeCategory": category,
        "ra": format_ra(ra),
        "displayName": f"{designation} - {', '.join(common)}" if common else designation,
        "alternateNames": alternate,
        "catalogue": catalogue,
        "objectNumber": number,
        "constellation": _CONSTELLATIONS.get(con, con),
        "size": f"{_trim(size)}'" if size is not None else "",
        "notes": _notes_for_size(size),
        "favorite": False,
        "source": "catalog.html",
        "addedAt": datetime.now().isoformat(timespec="seconds"),
    }


# -- duplicates ------------------------------------------------------------

def _name_key(name: str) -> str:
    """'NGC 0224' / 'ngc224' -> 'ngc224'."""
    key = re.sub(r"\s+", "", str(name or "")).lower()
    return re.sub(r"(?<!\d)0+(?=\d)", "", key)


def name_keys(entry: dict) -> set[str]:
    names = [entry.get("designation") or ""]
    names += str(entry.get("alternateNames") or "").split(",")
    return {k for k in (_name_key(n) for n in names) if k}


def _separation_arcmin(ra1_h: float, dec1: float, ra2_h: float, dec2: float) -> float:
    r1, d1, r2, d2 = (math.radians(v) for v in (ra1_h * 15, dec1, ra2_h * 15, dec2))
    cos_sep = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_sep)))) * 60


def find_duplicate(entry: dict, ra_hours: float, dec_deg: float, existing: list[dict]) -> dict | None:
    """First entry of `existing` (each with ra_hours/dec_deg, as
    dso_catalog.load_catalog() returns them) that is the same object:
    same designation (only, not alternate names - two objects can share
    a nickname) or within DUPLICATE_RADIUS_ARCMIN."""
    designation = _name_key(entry.get("designation"))
    for other in existing:
        if designation and designation in name_keys(other):
            return other
        if "ra_hours" in other and "dec_deg" in other and _separation_arcmin(
            ra_hours, dec_deg, other["ra_hours"], other["dec_deg"]
        ) <= DUPLICATE_RADIUS_ARCMIN:
            return other
    return None


# -- adding ----------------------------------------------------------------

def add_from_schedule(schedule: dict) -> list[str]:
    """Removes every task's "catalogMeta" from a /api/schedule payload
    (the device never sees it - dwarf_utils builds the task params from
    named fields only, but there's no reason to store/send it either)
    and adds the objects not already known. Returns the designations
    added."""
    found = []
    for task in schedule.get("shooting_tasks") or []:
        if not isinstance(task, dict):
            continue
        meta = task.pop("catalogMeta", None)
        if isinstance(meta, dict):
            found.append((meta, task.get("ra"), task.get("dec")))
    return add_entries(found) if found else []


def add_entries(items: list[tuple[dict, object, object]]) -> list[str]:
    """items: (catalogMeta, ra_hours, dec_deg) triples."""
    from components import dso_catalog  # dso_catalog imports this module lazily too

    added: list[str] = []
    with _lock:
        known = list(dso_catalog.load_catalog(force_reload=True))
        path = dso_catalog.add_on_path()
        stored = read_entries(path)
        for meta, ra, dec in items:
            entry = entry_from_catalog_page(meta, ra, dec)
            if entry is None:
                continue
            ra_h, dec_d = float(ra) % 24, float(dec)
            if find_duplicate(entry, ra_h, dec_d, known):
                continue
            stored.append(entry)
            known.append({**entry, "ra_hours": ra_h, "dec_deg": dec_d})
            added.append(entry["designation"])
        if added:
            _write_entries(path, stored)
            dso_catalog.load_catalog(force_reload=True)
    return added
