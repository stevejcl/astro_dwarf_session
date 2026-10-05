"""RA / Dec as people write them (user-reported Oct 2026: a program with
RA "18h 13m 40.3s" / Dec "-17° 36' 06\"" saved empty coordinates - the
editor only read decimal numbers - and the runner's fallback parsers only
knew "HH:MM:SS", with the Dec sign applied to the degrees alone).

parse_ra_hours():  decimal hours, "18h 13m 40.3s", "18:13:40.3",
                   "18 13 40.3", "18h13.5m"; a decimal above 24 is taken
                   as degrees (/15), and so is a value written with ° or d.
parse_dec_degrees(): decimal degrees, "-17° 36' 06\"", "-17:36:06",
                   "-17 36 06", "-17d36m06s", "−0 30" (the sign applies to
                   the whole value, minutes and seconds included).
Both return None when the text can't be read or is out of range."""
from __future__ import annotations

import re

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_MINUS = ("-", "−", "–", "—")


def _clean(value) -> str:
    text = str(value if value is not None else "").strip().replace(",", ".")
    for minus in _MINUS[1:]:
        text = text.replace(minus, "-")
    return text


def _sexagesimal(text: str) -> float | None:
    """|d| + m/60 + s/3600 of the numbers in text (1 to 3 of them)."""
    numbers = _NUMBER.findall(text)
    if not 1 <= len(numbers) <= 3:
        return None
    parts = [float(n) for n in numbers] + [0.0, 0.0]
    whole, minutes, seconds = parts[:3]
    if len(numbers) > 1 and (minutes >= 60 or seconds >= 60):
        return None
    return whole + minutes / 60 + seconds / 3600


def _plain_number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def parse_ra_hours(value) -> float | None:
    """RA in decimal hours [0, 24), or None."""
    text = _clean(value)
    if not text or text.startswith("-"):
        return None
    number = _plain_number(text)
    if number is not None:
        hours = number / 15 if number >= 24 else number
    else:
        in_degrees = "°" in text or re.search(r"\d\s*d", text, re.IGNORECASE) is not None
        sexa = _sexagesimal(text)
        if sexa is None:
            return None
        hours = sexa / 15 if in_degrees else sexa
    if not 0 <= hours < 24:
        return None
    return hours


def parse_dec_degrees(value) -> float | None:
    """Dec in decimal degrees [-90, 90], or None."""
    text = _clean(value)
    if not text:
        return None
    negative = text.startswith("-")
    number = _plain_number(text)
    if number is not None:
        degrees = number
    else:
        magnitude = _sexagesimal(text.lstrip("+-").strip())
        if magnitude is None:
            return None
        degrees = -magnitude if negative else magnitude
    if not -90 <= degrees <= 90:
        return None
    return degrees
