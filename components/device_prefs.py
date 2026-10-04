"""Per-device display preferences (user-requested Oct 2026: a Dwarf not
used for now - e.g. a D2 - took the first place on the dashboard).

A hidden Dwarf keeps only its card's header (name, IP, status), is listed
after the others, and isn't auto-connected; it is shown again with the
same button. JSON file, same pattern as pending_schedules.py (one small
file in the working folder, nothing to query)."""
from __future__ import annotations

import json
from pathlib import Path

PREFS_FILE = Path("device_prefs.json")


def _read_all() -> dict:
    if not PREFS_FILE.exists():
        return {}
    try:
        data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_all(data: dict) -> None:
    PREFS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def is_hidden(dwarf_uid: str) -> bool:
    return bool(_read_all().get(dwarf_uid, {}).get("hidden"))


def set_hidden(dwarf_uid: str, hidden: bool) -> None:
    data = _read_all()
    entry = data.setdefault(dwarf_uid, {})
    if hidden:
        entry["hidden"] = True
    else:
        entry.pop("hidden", None)
        if not entry:
            data.pop(dwarf_uid, None)
    _write_all(data)


def display_order(sessions: list) -> list:
    """Sessions in dashboard order: shown ones first (their own order),
    then hidden ones."""
    hidden = {uid for uid, entry in _read_all().items() if entry.get("hidden")}
    return [s for s in sessions if s.dwarf_uid not in hidden] + [
        s for s in sessions if s.dwarf_uid in hidden
    ]
