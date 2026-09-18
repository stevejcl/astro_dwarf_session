"""Shared "Use current location" helper - browser Geolocation API
(navigator.geolocation), not IP-based or address lookup (see
pages/settings.py's original docstring for why). Factored out here so
pages/sites.py can offer the same button instead of duplicating the JS
snippet - Sites are now the source of truth for location (user-
requested Sep 2026), so this belongs on the Sites page first and
foremost; pages/settings.py keeps its own copy of the fields for the
rare case of tweaking a single device away from its Site's value.
"""
from __future__ import annotations

import json
from typing import Optional

from nicegui import ui

from components.i18n import t

_GEOLOCATION_JS = """
return new Promise((resolve) => {
    if (!navigator.geolocation) {
        resolve(JSON.stringify({error: 'unsupported'}));
        return;
    }
    navigator.geolocation.getCurrentPosition(
        (pos) => resolve(JSON.stringify({lat: pos.coords.latitude, lon: pos.coords.longitude})),
        (err) => resolve(JSON.stringify({error: err.message})),
        {timeout: 15000, enableHighAccuracy: true}
    );
});
"""


async def fetch_current_location(status_label: ui.label) -> Optional[tuple[float, float]]:
    """Runs the browser geolocation prompt, updating `status_label` as
    it goes. Returns (latitude, longitude) on success, None on failure
    (status_label already carries the error message in that case - the
    caller doesn't need to show anything else)."""
    status_label.set_text(t("settings_location_fetching"))
    status_label.classes(replace="text-xs text-grey-6")
    try:
        raw = await ui.run_javascript(_GEOLOCATION_JS, timeout=20.0)
        result = json.loads(raw)
    except Exception as exc:
        status_label.set_text(t("settings_location_error", error=str(exc)))
        status_label.classes(replace="text-xs text-red-700")
        return None

    if "error" in result:
        status_label.set_text(t("settings_location_error", error=result["error"]))
        status_label.classes(replace="text-xs text-red-700")
        return None

    status_label.set_text(t("settings_location_fetched"))
    status_label.classes(replace="text-xs text-green-700")
    return result["lat"], result["lon"]
