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
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

PENDING_FILE = Path("pending_schedules.json")


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
