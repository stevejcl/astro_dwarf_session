"""Shared logic for creating a NEW device's config_py/config_ini pair
and registering it with the app - used by both the BLE pairing flow
(pages/pairing.py) and the no-BLE manual config wizard
(pages/manual_config.py).

MODEL -> DWARF_ID mapping (hardware-confirmed, Sep 2026): the raw value
stored in config.py's DWARF_ID is NOT the same as the "+1" number shown
in the DwarfLab app's own device list - that "+1" naming is display-
only and doesn't even hold for the Mini (4 + 1 = 5 maps to nothing
real). Only this table is authoritative for what actually goes into
config.py. The BLE pairing flow never needs this table itself - the
device tells it its own model over Bluetooth - but the no-BLE wizard
has no such handshake, so it must set DWARF_ID correctly up front from
whatever model the user picked.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEVICE_MODELS = ["Dwarf II", "Dwarf 3", "Dwarf Mini"]

DEVICE_ID_BY_MODEL = {
    "Dwarf II": "1",
    "Dwarf 3": "2",
    "Dwarf Mini": "4",
}

# TODO confirm the Mini's actual default with Steve - copied from the
# Tele/Wide split visible in the existing config.ini samples, not yet
# hardware-verified for the Mini specifically.
DEFAULT_CAMERA_TYPE_BY_MODEL = {
    "Dwarf II": "Tele Camera",
    "Dwarf 3": "Tele Camera",
    "Dwarf Mini": "Wide Camera",
}

DEFAULT_BLE_PSD = "DWARF_12345678"

# Same blank template pairing.py has always used - BLE fills in the
# real values afterward via update_config_data(). Kept here so both
# call sites share one source of truth for what a "blank" device looks
# like.
_TEMPLATE_PY = """DWARF_IP = ""
DWARF_ID = "2"
DWARF_UID = ""
DWARF_UI = ""
CLIENT_ID = "0000DAF2-0000-1000-8000-00805F9B34FB"
TIMEOUT_CMD = "0"
LOG_FILE = "astro_session.log"
DEBUG = True
TRACE = ""
"""

_TEMPLATE_INI = """[CONFIG]
longitude =
latitude =
timezone = Europe/Paris
ble_psd = DWARF_12345678
ble_sta_ssid =
ble_sta_pwd =
exposure = 15
gain = 100
ircut = 0
binning = 0
count = 20
address =
dwarf_ip =
stellarium_ip =
stellarium_port =
camera_type = Tele Camera
device_type = Dwarf II
"""


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip().lower()).strip("_")
    return slug or "device"


def config_filenames(device_name: str) -> tuple[str, str]:
    """(config_py, config_ini) filenames a given device NAME would use -
    exposed so callers can check for a naming collision BEFORE writing
    anything."""
    slug = slugify(device_name)
    return f"config_{slug}.py", f"config_{slug}.ini"


def ensure_config_files(slug: str) -> tuple[str, str]:
    """Used by the BLE pairing flow (pages/pairing.py): creates
    config_<slug>.py/.ini from the blank template if they don't exist
    yet, then leaves the actual field values to be filled in by BLE.
    Never touches a file that already exists (this could be a
    RE-pairing of an already-known device)."""
    config_py = f"config_{slug}.py"
    config_ini = f"config_{slug}.ini"

    if not Path(config_py).exists():
        Path(config_py).write_text(_TEMPLATE_PY, encoding="utf-8")
    if not Path(config_ini).exists():
        Path(config_ini).write_text(_TEMPLATE_INI, encoding="utf-8")

    return config_py, config_ini


@dataclass
class ManualDeviceInput:
    """Everything the no-BLE wizard collects from the user/Site to
    build a complete config_py/config_ini pair in one shot (unlike
    ensure_config_files(), which only ever writes the blank template -
    there's no BLE handshake here afterward to fill the real values
    in, so write_manual_config() below must write them all itself)."""

    device_name: str
    model: str  # one of DEVICE_MODELS
    dwarf_ip: str
    dwarf_uid: str
    wifi_ssid: str
    wifi_password: str
    longitude: Optional[float]
    latitude: Optional[float]
    timezone: str
    ble_psd: str = DEFAULT_BLE_PSD
    stellarium_ip: str = ""
    stellarium_port: str = ""


def write_manual_config(data: ManualDeviceInput) -> tuple[str, str]:
    """Writes a COMPLETE config_py/config_ini pair directly (not the
    blank template) - the manual wizard's entire point is to supply
    every value BLE would normally have filled in, so the device can
    connect straight over Wi-Fi on first launch (it already knows the
    target network - its credentials were handed to it separately via
    the official DwarfLab app).

    Refuses to overwrite an existing file pair (same natural-key
    reasoning as ensure_config_files(), but as a hard error here
    rather than a silent skip - a name collision in THIS flow means
    the user is about to overwrite a real, already-working config, not
    innocently re-pairing the same device)."""
    config_py, config_ini = config_filenames(data.device_name)

    if Path(config_py).exists() or Path(config_ini).exists():
        raise FileExistsError(
            f"{config_py} / {config_ini} already exist - choose a different device name"
        )

    if data.model not in DEVICE_ID_BY_MODEL:
        raise ValueError(f"Unknown model: {data.model}")

    py_content = (
        f'DWARF_IP = "{data.dwarf_ip}"\n'
        f'DWARF_ID = "{DEVICE_ID_BY_MODEL[data.model]}"\n'
        f'DWARF_UID = "{data.dwarf_uid}"\n'
        f'DWARF_UI = ""\n'
        f'CLIENT_ID = "0000DAF2-0000-1000-8000-00805F9B34FB"\n'
        f'TIMEOUT_CMD = "0"\n'
        f'LOG_FILE = "astro_session.log"\n'
        f'DEBUG = True\n'
        f'TRACE = ""\n'
    )
    Path(config_py).write_text(py_content, encoding="utf-8")

    ini_content = (
        "[CONFIG]\n"
        f"longitude = {data.longitude if data.longitude is not None else ''}\n"
        f"latitude = {data.latitude if data.latitude is not None else ''}\n"
        f"timezone = {data.timezone}\n"
        f"ble_psd = {data.ble_psd or DEFAULT_BLE_PSD}\n"
        f"ble_sta_ssid = {data.wifi_ssid}\n"
        f"ble_sta_pwd = {data.wifi_password}\n"
        "exposure = 15\n"
        "gain = 100\n"
        "ircut = 0\n"
        "binning = 0\n"
        "count = 20\n"
        "address = \n"
        "dwarf_ip = \n"
        f"stellarium_ip = {data.stellarium_ip}\n"
        f"stellarium_port = {data.stellarium_port}\n"
        f"camera_type = {DEFAULT_CAMERA_TYPE_BY_MODEL[data.model]}\n"
        f"device_type = {data.model}\n"
    )
    Path(config_ini).write_text(ini_content, encoding="utf-8")

    return config_py, config_ini
