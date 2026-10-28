"""The user's own targets around the shared catalog (user-requested Oct
2026, issue #162): favourites, recent targets, and where the user's files
live.

- Favourites: chosen by the user, a star in "Pick from catalog". No app
  had any yet (the "favorite" field of dso_catalog.json is unused; the
  user's favourites were in another smartphone app), so they start here:
  USER_DIR/favorites.json, by designation - the shared catalog is never
  written. Using a target does NOT make it a favourite (user-agreed).
- Recent targets: automatic - the targets of the programs already run
  (Done / Error of every Dwarf), with their RA/Dec, how many times and
  when last, so a session can be redone without having kept anything.
- USER_DIR (~/.astro_dwarf_session, ASTRO_DWARF_USER_DIR): the user's
  files, out of the app's folder that an update may replace -
  catalog_add_on.json lives there too when Dwarfium Scope Archive isn't
  installed next to this app (see dso_catalog.add_on_path())."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

USER_DIR = Path(os.environ.get("ASTRO_DWARF_USER_DIR", Path.home() / ".astro_dwarf_session"))
_FAVORITES_FILE = "favorites.json"

_lock = threading.Lock()
_favorites: set[str] | None = None


def _key(name) -> str:
    from components.catalog_add_on import _name_key
    return _name_key(name)


# ---------------------------------------------------------------- favourites

def _favorites_path() -> Path:
    return USER_DIR / _FAVORITES_FILE


def favorites() -> set[str]:
    """The favourite designations, as name keys (catalog_add_on._name_key)."""
    global _favorites
    if _favorites is None:
        try:
            data = json.loads(_favorites_path().read_text(encoding="utf-8"))
            names = data.get("designations", []) if isinstance(data, dict) else []
        except (OSError, ValueError):
            names = []
        _favorites = {_key(n) for n in names if n}
    return _favorites


def is_favorite(entry: dict) -> bool:
    keys = favorites()
    return any(_key(n) in keys for n in _entry_names(entry))


def _entry_names(entry: dict) -> list[str]:
    """The designation, and the user's own name for it when their object
    was later found in the shared catalog (dso_catalog.load_catalog())."""
    return [n for n in (entry.get("designation"), entry.get("_userDesignation")) if n]


def set_favorite(entry: dict, value: bool) -> None:
    from components.json_files import write_json_atomic

    with _lock:
        keys = favorites()
        names = _entry_names(entry)
        if value:
            keys.add(_key(names[0]))
        else:
            keys.difference_update(_key(n) for n in names)
        try:
            data = json.loads(_favorites_path().read_text(encoding="utf-8"))
            stored = data.get("designations", []) if isinstance(data, dict) else []
        except (OSError, ValueError):
            stored = []
        stored = [n for n in stored if _key(n) in keys]
        if value and _key(names[0]) not in {_key(n) for n in stored}:
            stored.append(names[0])
        USER_DIR.mkdir(parents=True, exist_ok=True)
        write_json_atomic(str(_favorites_path()), {"designations": stored})


# ---------------------------------------------------------------- recent targets

def _program_files(sessions) -> list[str]:
    from components.session_dirs import session_dirs_for

    files = []
    for session in sessions:
        try:
            dirs = session_dirs_for(session)
        except Exception:
            continue
        for key in ("DONE_DIR", "ERROR_DIR"):
            folder = dirs.get(key)
            if folder and os.path.isdir(folder):
                files += [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".json")]
    return files


def recent_targets(sessions, limit: int = 50) -> list[dict]:
    """The targets of the programs run on these Dwarfs (manual goto with
    RA/Dec), most recent first: [{"name", "ra_hours", "dec_deg", "last",
    "count", "description"}] - one per name."""
    found: dict[str, dict] = {}
    for path in _program_files(sessions):
        try:
            with open(path, encoding="utf-8") as f:
                program = json.load(f)
            cmd = program.get("command", program)
            goto = cmd.get("goto_manual") or {}
            if not goto.get("do_action") or not goto.get("target"):
                continue
            ra, dec = float(goto["ra_coord"]), float(goto["dec_coord"])
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
        ident = cmd.get("id_command") or {}
        try:
            when = datetime.strptime(f"{ident.get('date', '')} {ident.get('time', '')}".strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            when = datetime.fromtimestamp(os.path.getmtime(path))
        name = str(goto["target"]).strip()
        key = _key(name)
        item = found.get(key)
        if item is None:
            found[key] = {"name": name, "ra_hours": ra % 24, "dec_deg": dec, "last": when, "count": 1,
                          "description": str(ident.get("description") or "")}
        else:
            item["count"] += 1
            if when > item["last"]:
                item.update(name=name, ra_hours=ra % 24, dec_deg=dec, last=when,
                            description=str(ident.get("description") or ""))
    return sorted(found.values(), key=lambda r: r["last"], reverse=True)[:limit]
