"""Per-device display preferences (user-requested Oct 2026: a Dwarf not
used for now - e.g. a D2 - took the first place on the dashboard).

A hidden Dwarf keeps only its card's header (name, IP, status), is listed
after the others, and isn't auto-connected; it is shown again with the
same button. The dashboard order can be changed too (user-requested Oct
2026): each Dwarf's "position"; hidden ones always stay after the others.
JSON file, same pattern as pending_schedules.py (one small
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


def _ordered(sessions: list, data: dict) -> list:
    """Shown Dwarfs then hidden ones, each group by saved position (a Dwarf
    without one keeps its registry order, after the positioned ones)."""
    def key(item):
        index, session = item
        entry = data.get(session.dwarf_uid, {})
        position = entry.get("position")
        return (
            bool(entry.get("hidden")),
            position if isinstance(position, int) else len(sessions) + index,
        )
    return [s for _i, s in sorted(enumerate(sessions), key=key)]


def display_order(sessions: list) -> list:
    """Sessions in dashboard order: shown ones first, then hidden ones,
    each group in the order chosen with move()."""
    return _ordered(sessions, _read_all())


def move(dwarf_uid: str, sessions: list, where: str) -> None:
    """Moves a Dwarf within its group (shown or hidden): where is "first",
    "up", "down" or "last". Saves every Dwarf's position, so the order
    stays as displayed."""
    data = _read_all()
    ordered = [s.dwarf_uid for s in _ordered(sessions, data)]
    if dwarf_uid not in ordered:
        return
    hidden = bool(data.get(dwarf_uid, {}).get("hidden"))
    group = [uid for uid in ordered if bool(data.get(uid, {}).get("hidden")) == hidden]
    index = group.index(dwarf_uid)
    group.pop(index)
    target = {"first": 0, "up": max(0, index - 1), "down": index + 1, "last": len(group)}.get(where, index)
    group.insert(min(target, len(group)), dwarf_uid)
    others = [uid for uid in ordered if uid not in group]
    final = group + others if not hidden else others + group
    for position, uid in enumerate(final):
        data.setdefault(uid, {})["position"] = position
    _write_all(data)
