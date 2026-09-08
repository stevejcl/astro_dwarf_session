"""
Persistance de la liste des Dwarf connus (couples config.py/config.ini
par appareil physique) - remplace la liste KNOWN_DEVICE_CONFIGS codee en
dur du premier scaffold.

Format: un simple fichier JSON, devices.json, a cote du point d'entree:

    [
      {"name": "Dwarf 3", "config_py": "config_d3.py", "config_ini": "config_d3.ini"},
      {"name": "Dwarf Mini", "config_py": "config_mini.py", "config_ini": "config_mini.ini"}
    ]

Un simple JSON suffit ici (contrairement a dwarf_backup.db dans
dwarfium-scope-archive) car cette liste ne contient que des chemins de
fichiers a associer a un nom affiche - rien a interroger/filtrer/joindre.

Ce fichier est le SEUL endroit qui connait la correspondance
nom-affiche <-> couple-de-fichiers-config. DwarfConfig.from_files() et
DwarfManager (indexe par dwarf_uid) restent inchanges - ce module ne
fait qu'appeler l'un pour peupler l'autre.

Si devices.json n'existe pas encore, la liste est simplement vide -
c'est a pages/pairing.py d'appeler add_device_entry() une fois un
nouvel appareil apparie avec succes (dwarf_uid confirme).
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
    """Utilise par la future page Settings pour afficher/editer la liste
    (renommer, retirer un appareil, corriger un chemin de fichier)."""
    return _read_entries()


def add_device_entry(name: str, config_py: str, config_ini: str) -> DeviceEntry:
    """Enregistre un nouveau couple de fichiers config. A appeler depuis
    pages/pairing.py une fois l'appairage BLE reussi et le dwarf_uid
    confirme (evite d'enregistrer une entree pour un appareil dont on ne
    sait pas encore s'il repond vraiment)."""
    entries = _read_entries()
    entry = DeviceEntry(name=name, config_py=config_py, config_ini=config_ini)
    entries.append(entry)
    _write_entries(entries)
    return entry


def remove_device_entry(config_py: str) -> None:
    """Retire une entree par son chemin config.py (cle naturelle: un
    couple de fichiers correspond a un seul appareil physique)."""
    entries = [e for e in _read_entries() if e.config_py != config_py]
    _write_entries(entries)


def bootstrap_devices(manager: DwarfManager) -> None:
    """Enregistre un DwarfSession par entree connue dans devices.json.
    Une entree dont les fichiers sont introuvables ou sans dwarf_uid
    exploitable est ignoree silencieusement plutot que de faire planter
    le demarrage - l'appareil pourra toujours etre reappaire plus tard
    via pages/pairing.py."""
    for entry in _read_entries():
        try:
            cfg = DwarfConfig.from_files(entry.config_py, entry.config_ini)
        except FileNotFoundError:
            continue

        if not cfg.dwarf_uid:
            continue

        manager.add(cfg)
