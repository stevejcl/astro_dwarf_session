"""This app's version (user-requested Oct 2026: shown on the home page, as
Dwarfium Scope Archive does on its Settings page).

version.py in the executable (buildAstroDwarfUI.py writes it from
CHANGELOG.md), else the first [X.Y.Z] of CHANGELOG.md (source run - the
build also leaves a version.py in the source folder, ignored there). Read
once."""
from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_app_version() -> str:
    # version.py only in the executable: the build also leaves it in the
    # source folder, where it would show the last built version
    if getattr(sys, "frozen", False):
        try:
            from version import APP_VERSION
            return APP_VERSION
        except ImportError:
            pass
    try:
        changelog = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
        with open(changelog, encoding="utf-8") as f:
            for line in f:
                m = re.search(r"\[V?([\d.]+[a-z]?)\]", line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return ""
