"""
Persistence of the list of known Dwarfs (config.py/config.ini pairs per
physical device) - replaces the KNOWN_DEVICE_CONFIGS list hardcoded in
the first scaffold.

Format: a simple JSON file, devices.json, next to the entry point:

    [
      {"name": "Dwarf 3", "config_py": "config_d3.py", "config_ini": "config_d3.ini"},
      {"name": "Dwarf Mini", "config_py": "config_mini.py", "config_ini": "config_mini.ini"}
    ]

A plain JSON file is enough here (unlike dwarf_backup.db in
dwarfium-scope-archive), since this list only maps file paths to a
display name - nothing to query/filter/join.

This file is the ONLY place that knows the display-name <-> config-file-
pair mapping. DwarfConfig.from_files() and DwarfManager (keyed by
dwarf_uid) are untouched - this module only calls one to populate the
other.

If devices.json doesn't exist yet, the list is simply empty - it's up
to pages/pairing.py to call add_device_entry() once a new device has
been successfully paired (dwarf_uid confirmed).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from dwarf_python_api.lib.dwarf_config import DwarfConfig
from dwarf_python_api.lib.dwarf_session import DwarfManager

DEVICES_FILE = Path("devices.json")


@dataclass
class DeviceEntry:
    name: str
    config_py: str
    config_ini: str


def _read_entries() -> list[DeviceEntry]:
    if not DEVICES_FILE.exists():
        return []
    try:
        raw = json.loads(DEVICES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [DeviceEntry(**item) for item in raw]


def _write_entries(entries: list[DeviceEntry]) -> None:
    DEVICES_FILE.write_text(
        json.dumps([asdict(e) for e in entries], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_device_entries() -> list[DeviceEntry]:
    """Used by the future Settings page to display/edit the list
    (rename, remove a device, fix a file path)."""
    return _read_entries()


def add_device_entry(name: str, config_py: str, config_ini: str) -> DeviceEntry:
    """Registers a new config file pair. Call this from pages/pairing.py
    once BLE pairing succeeded and dwarf_uid was confirmed (avoids
    registering a device we don't actually know responds correctly)."""
    entries = _read_entries()
    entry = DeviceEntry(name=name, config_py=config_py, config_ini=config_ini)
    entries.append(entry)
    _write_entries(entries)
    return entry


def remove_device_entry(config_py: str) -> None:
    """Removes an entry by its config.py path (natural key: one file
    pair corresponds to exactly one physical device)."""
    entries = [e for e in _read_entries() if e.config_py != config_py]
    _write_entries(entries)


def bootstrap_devices(manager: DwarfManager) -> None:
    """Registers one DwarfSession per known entry in devices.json. An
    entry whose files are missing, or without a usable dwarf_uid, is
    silently skipped rather than crashing startup - the device can
    always be re-paired later via pages/pairing.py."""
    for entry in _read_entries():
        try:
            cfg = DwarfConfig.from_files(entry.config_py, entry.config_ini)
        except FileNotFoundError:
            continue

        if not cfg.dwarf_uid:
            continue

        manager.add(cfg)
