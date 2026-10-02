"""
pending_schedules.py

Stocke, par dwarf_uid, le dernier planning "shooting schedule" reçu pour un
appareil actuellement DÉCONNECTÉ (voir components/api_routes.py). Format
JSON, même esprit que device_registry.py : un seul petit fichier, rien à
interroger/joindre.

    pending_schedules.json:
    {
      "<dwarf_uid>": { ...schedule dict tel que produit par
                        buildDwarfShootingSchedule() côté page catalogue... }
    }

Un appareil n'a qu'UN planning en attente à la fois : en recevoir un nouveau
remplace l'ancien (comportement volontaire - c'est la même sémantique que
"REPLACE" côté firmware pour CMD_SYNC_SHOOTING_SCHEDULE).

FENÊTRE DE SYNCHRO (confirmé sur l'appareil, oct. 2026) : le Dwarf refuse
un planning synchronisé plus de 12 h avant son début
(CODE_SHOOTING_SCHEDULE_START_TIME_TOO_FAR, -16308). Un planning peut donc
être créé à l'avance, mais il reste ici en attente (avec "autoSync": True)
jusqu'à ce que scheduler_loop.check_pending_schedules() l'envoie, une fois
dans la fenêtre des 12 h.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

PENDING_FILE = Path("pending_schedules.json")

# Device limit is 12 h; keep a small margin so a sync sent right at the
# boundary (clock drift, network latency) isn't refused.
MAX_SYNC_LEAD_S = 12 * 3600 - 5 * 60


def _epoch_s(value) -> Optional[int]:
    """Epoch seconds from seconds or milliseconds (catalog page sends ms)."""
    if not value:
        return None
    value = int(value)
    return value // 1000 if value > 10000000000 else value


def sync_opens_at(schedule: dict) -> Optional[int]:
    """Earliest epoch second at which `schedule` can be synced, or None if
    it has no start time."""
    start = _epoch_s(schedule.get("startTime"))
    return start - MAX_SYNC_LEAD_S if start else None


def is_too_early(schedule: dict, now: Optional[float] = None) -> bool:
    """True while the schedule starts more than ~12 h from now."""
    opens = sync_opens_at(schedule)
    return opens is not None and (now if now is not None else time.time()) < opens


def is_expired(schedule: dict, now: Optional[float] = None) -> bool:
    """True once the schedule's whole window has ended - syncing it is
    pointless (and the device would refuse it)."""
    end = _epoch_s(schedule.get("endTime"))
    return end is not None and end <= (now if now is not None else time.time())


def _read_all() -> dict:
    if not PENDING_FILE.exists():
        return {}
    try:
        return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_all(data: dict) -> None:
    PENDING_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def set_pending(dwarf_uid: str, schedule: dict) -> None:
    data = _read_all()
    data[dwarf_uid] = schedule
    _write_all(data)


def get_pending(dwarf_uid: str) -> Optional[dict]:
    return _read_all().get(dwarf_uid)


def clear_pending(dwarf_uid: str) -> None:
    data = _read_all()
    if dwarf_uid in data:
        del data[dwarf_uid]
        _write_all(data)


def list_pending_uids() -> list[str]:
    return list(_read_all().keys())
