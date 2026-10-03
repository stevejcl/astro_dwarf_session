"""Site time - the wall clock of the place a Dwarf observes from
(user-requested Oct 2026: "il faut utiliser la time zone definie pour le
site lie au dwarf" - remote setups, e.g. a mini PC on site reached over
Tailscale, or this app running at home for a Dwarf far away, mean this
PC's own clock isn't necessarily the site's).

A Dwarf's `timezone` setting is written from its Site
(device_provisioning.apply_site_to_ini()) and is the same one
perform_timezone() pushes to the device, so every date/time typed,
shown or compared for that Dwarf - native schedule AND this app's own
program scheduler - is wall-clock time in that zone. Falls back to this
PC's local timezone when the setting is empty or unknown, i.e. exactly
the previous behaviour.

Kept free of any dwarf_python_api import so low-level modules
(dwarf_session.py, the scheduler) can use it without import cycles."""
from __future__ import annotations

import logging
import zoneinfo
from datetime import datetime, tzinfo

_warned: set[str] = set()


def site_tz(config) -> tzinfo:
    """ZoneInfo of the Dwarf's configured timezone, else this PC's.
    ZoneInfo("") raises ValueError (not ZoneInfoNotFoundError) - both
    are caught, so a bad setting can never break a caller."""
    name = (getattr(config, "timezone", "") or "").strip() if config is not None else ""
    if name:
        try:
            return zoneinfo.ZoneInfo(name)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError) as e:
            if name not in _warned:
                _warned.add(name)
                logging.getLogger(__name__).warning(
                    f"Unknown timezone {name!r} ({e}) - using this PC's local timezone."
                )
    return datetime.now().astimezone().tzinfo


def site_now(config) -> datetime:
    """Current NAIVE wall-clock time at the Dwarf's site - drop-in for
    datetime.now() wherever a program's date/time is created or compared."""
    return datetime.now(site_tz(config)).replace(tzinfo=None)


def session_now(session) -> datetime:
    """site_now() for a session that may be None (legacy callers)."""
    return site_now(getattr(session, "config", None))


def site_from_timestamp(ts: float, config) -> datetime:
    """POSIX timestamp (e.g. a file's mtime) -> naive site wall-clock time."""
    return datetime.fromtimestamp(ts, site_tz(config)).replace(tzinfo=None)
