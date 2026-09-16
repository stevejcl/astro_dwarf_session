"""Persistence of "Sites" - a Wifi network + location "profile" you
observe from (garden, an eclipse trip, a mountain chalet...) - decoupled
from any one physical Dwarf so the same Site can be reused across every
device that happens to be there, and picking a Site pre-fills the
Wifi/location fields instead of retyping them everywhere.

Same JSON-file approach as device_registry.py, for the same reason: a
short list to look up by name, nothing to query/join.

Format: sites.json next to the entry point:

    [
      {
        "name": "Jardin",
        "wifi_ssid": "MaBox-5G",
        "wifi_password": "...",
        "longitude": -1.723,
        "latitude": 47.311,
        "timezone": "Europe/Paris",
        "notes": ""
      }
    ]
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

SITES_FILE = Path("sites.json")


@dataclass
class SiteEntry:
    name: str
    wifi_ssid: str = ""
    wifi_password: str = ""
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    timezone: str = ""
    notes: str = ""


def _read_entries() -> list[SiteEntry]:
    if not SITES_FILE.exists():
        return []
    try:
        raw = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [SiteEntry(**item) for item in raw]


def _write_entries(entries: list[SiteEntry]) -> None:
    SITES_FILE.write_text(
        json.dumps([asdict(e) for e in entries], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_site_entries() -> list[SiteEntry]:
    return _read_entries()


def get_site_entry(name: str) -> Optional[SiteEntry]:
    return next((e for e in _read_entries() if e.name == name), None)


def add_site_entry(entry: SiteEntry) -> SiteEntry:
    entries = _read_entries()
    if any(e.name == entry.name for e in entries):
        raise ValueError(f"A site named '{entry.name}' already exists")
    entries.append(entry)
    _write_entries(entries)
    return entry


def update_site_entry(old_name: str, entry: SiteEntry) -> None:
    """Replaces the entry matching `old_name` with `entry` - separate
    from the entry's own (possibly new) name, in case the user is also
    renaming the Site."""
    entries = _read_entries()
    for i, e in enumerate(entries):
        if e.name == old_name:
            entries[i] = entry
            _write_entries(entries)
            return
    raise KeyError(f"No site named '{old_name}'")


def remove_site_entry(name: str) -> None:
    entries = [e for e in _read_entries() if e.name != name]
    _write_entries(entries)
