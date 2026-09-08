"""Stellarium integration - target retrieval only (point C of the
roadmap). Ported from astro_dwarf_session's own stellarium_connection.py
(the HTTP client, verbatim) and tabs/create_session.py's
refresh_stellarium_data() (the field-extraction/target-name/description
logic, verbatim) - not reinvented.

Stellarium's Remote Control plugin must be enabled and running for
get_target_from_stellarium() to work - it queries
/api/objects/info?format=json, which reports whatever object is
CURRENTLY SELECTED in Stellarium at the time of the call."""
from __future__ import annotations

import json
from urllib import request


class StellariumConnection:
    """Verbatim port of astro_dwarf_session/stellarium_connection.py."""

    def __init__(self, ip: str = "127.0.0.1", port: int = 8090):
        self.ip = ip
        self.port = port

    def get_data(self) -> dict:
        url = f"http://{self.ip}:{self.port}/api/objects/info?format=json"
        try:
            with request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return json.loads(response.read().decode())
                else:
                    raise Exception(f"Failed to retrieve data: {response.status}")
        except Exception as e:
            raise Exception(f"Error connecting to Stellarium: {e}")


class StellariumTarget:
    """What get_target_from_stellarium() hands back to the program
    editor - already converted/formatted, ready to drop into the
    goto_manual fields."""

    def __init__(self, description: str, target_name: str, ra_hours: str, dec_degrees):
        self.description = description
        self.target_name = target_name
        self.ra_hours = ra_hours
        self.dec_degrees = dec_degrees


def get_target_from_stellarium(ip: str, port: int) -> StellariumTarget:
    """Raises on failure - the caller is expected to catch and display
    the message (including the 404 case's specific hint, same as the
    legacy Tkinter form: 'select a target in Stellarium first')."""
    connection = StellariumConnection(ip=ip or "127.0.0.1", port=port or 8090)
    try:
        data = connection.get_data()
    except Exception as e:
        message = str(e)
        if "404" in message:
            raise Exception(
                f"{message} - select a target in Stellarium first, then try again."
            )
        raise

    # --- Target name: avoid duplicating localized-name vs name -------
    localized_name = (data.get("localized-name") or "").strip()
    name = (data.get("name") or "").strip()
    if localized_name and name:
        if localized_name.lower() == name.lower():
            target_name = localized_name
        else:
            target_name = f"{localized_name} - {name}"
    else:
        target_name = localized_name or name or "Unknown Target"

    # --- Description: "Observation of X (Type) in Constellation (Mag: Y)" ---
    object_type = (data.get("object-type") or "").strip()
    constellation = (data.get("constellation") or "").strip()
    vmag = data.get("vmag", "")

    parts = [f"Observation of {target_name}"]
    type_labels = {
        "nebula": "Nebula", "galaxy": "Galaxy", "star cluster": "Star Cluster",
        "double star": "Double Star", "variable star": "Variable Star",
        "planet": "Planet", "moon": "Moon",
    }
    if object_type and object_type.lower() not in ("", "undefined", "unknown"):
        parts.append(f"({type_labels.get(object_type.lower(), object_type.title())})")
    if constellation and constellation.lower() not in ("", "undefined", "unknown"):
        parts.append(f"in {constellation}")
    if vmag not in ("", "undefined", None):
        try:
            mag_value = float(vmag)
            if -5 <= mag_value <= 20:
                parts.append(f"(Mag: {mag_value:.1f})")
        except (ValueError, TypeError):
            pass
    description = " ".join(parts)

    # --- RA/Dec: raJ2000 (degrees) -> decimal hours, decJ2000 as-is ---
    # Base conversion (degrees / 15 = hours) is verbatim from tabs/
    # create_session.py's refresh_stellarium_data() - but that original
    # formula, (ra_j2000 + 360) / 15, produces values ABOVE the normal
    # 0-24h range for any already-positive raJ2000 (the common case):
    # e.g. Orion Nebula's raJ2000=83.82 gives 29.588h there, not the
    # correct 5.588h (real RA of M42 is 5h35m). The +360 only makes
    # sense as a normalization for a NEGATIVE raJ2000 (which some
    # Stellarium versions can return crossing the meridian) - it needs
    # a trailing "% 24" to wrap back into range either way, which the
    # original was missing. Added here after finding this via a real
    # test case (Orion Nebula) rather than left silently wrong - a
    # goto_manual sent with RA=29.588 instead of 5.588 could point the
    # mount at entirely the wrong part of the sky if the Dwarf's own
    # goto command doesn't itself wrap out-of-range RA values.
    ra_hours = ""
    if "raJ2000" in data:
        try:
            ra_j2000 = float(data["raJ2000"])
            ra_hours = f"{((ra_j2000 + 360) / 15.0) % 24:.6f}"
        except (TypeError, ValueError):
            ra_hours = ""

    dec_degrees = data.get("decJ2000", "")

    return StellariumTarget(
        description=description,
        target_name=target_name,
        ra_hours=ra_hours,
        dec_degrees=dec_degrees,
    )
