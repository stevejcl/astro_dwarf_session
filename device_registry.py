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
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

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


def _same_file(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a or "")) == os.path.normcase(os.path.abspath(b or ""))


def entry_for(config) -> DeviceEntry | None:
    """The devices.json entry of a loaded Dwarf (its DwarfConfig), by its
    config.py - the natural key, see remove_device_entry()."""
    path = getattr(config, "config_py_path", "") or ""
    return next((e for e in _read_entries() if _same_file(e.config_py, path)), None)


def device_name(session) -> str:
    """The name given to the Dwarf when it was added (user-reported Oct
    2026: typed at pairing / manual configuration, then shown nowhere -
    every page showed its dwarf_uid), else its dwarf_uid."""
    entry = entry_for(session.config)
    return (entry.name.strip() if entry and entry.name else "") or session.dwarf_uid


def name_and_uid(session) -> str:
    """"Name (dwarf_uid)", or the dwarf_uid alone when it has no name."""
    name = device_name(session)
    return name if name == session.dwarf_uid else f"{name} ({session.dwarf_uid})"


def rename_device(session, name: str) -> bool:
    """Its display name only: the dwarf_uid and the config files stay, so
    programs, the Scope Archive link and the Hub are untouched. False when
    the Dwarf has no devices.json entry."""
    entries = _read_entries()
    path = getattr(session.config, "config_py_path", "") or ""
    for e in entries:
        if _same_file(e.config_py, path):
            e.name = name.strip()
            _write_entries(entries)
            return True
    return False


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


def find_shared_config_value(manager: DwarfManager, getter, exclude_uid: str = ""):
    """User-requested Sep 2026: "pre enregistrer si existant pour un
    autre Dwarf" - Wi-Fi name/password, Stellarium IP/port, and
    location are almost always the SAME across every Dwarf a person
    owns (same home network, same house), so re-typing them for every
    newly paired device is pure friction. Scans every OTHER already-
    registered device's own config for the first value `getter` returns
    that isn't None/empty, e.g.:
        find_shared_config_value(manager, lambda c: c.ble_sta_ssid)
        find_shared_config_value(manager, lambda c: c.longitude)
    Generic over the getter's own return type (str, float, int, ...) -
    truthiness is enough to detect "genuinely unset" (None, "", 0.0 for
    a coordinate would all be equally meaningless as a pre-fill anyway).
    Returns None if no other device has a value (nothing to pre-fill
    with, not an error) - callers should still let the user type their
    own value in that case, same as today."""
    for session in manager.all():
        if session.config.dwarf_uid == exclude_uid:
            continue
        value = getter(session.config)
        if value:
            return value
    return None

