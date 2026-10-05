"""Link to archive a session with Dwarfium Scope Archive (user-requested
Oct 2026).

Scope Archive's ImportSession page does the import: with its DwarfId
and a session folder name, it syncs that session only from the Dwarf
(USB or FTP) and scans it into its database - the session is then
registered - and opens its Transfer page with it preselected (Archive
mode), where the user picks the backup drive and starts the copy. So
this app only builds the address, from the Settings page's Dwarfium
Scope Archive URL and DwarfId (the same as the "Open in" links).

Opened in Scope Archive's own window when it runs as an app (user-
requested Oct 2026: in a web browser, its Transfer page's system folder
dialogs aren't available): its /api/open-in-app loads the page there and
brings it to front. Without an app window, or Scope Archive not
answering, the page opens in a browser as before.
"""
from __future__ import annotations

import posixpath
from urllib.parse import urlencode, urlsplit

import requests
from nicegui import run, ui

from components.i18n import t

_OPEN_TIMEOUT_S = 5


def session_folder(media_path: str) -> str:
    """Session folder name of one of its files (the album's filePath or
    thumbnailPath: .../Astronomy/<session>/stacked.jpg)."""
    return posixpath.basename(posixpath.dirname(media_path or ""))


def transfer_url(config, media_path: str) -> str | None:
    """Scope Archive's import page for this session (then its Transfer
    page), or None when the URL / DwarfId isn't set for this Dwarf."""
    base = (getattr(config, "dwarfium_base_url", "") or "").rstrip("/")
    dwarf_id = getattr(config, "dwarfium_id", "") or ""
    folder = session_folder(media_path)
    if not base or not str(dwarf_id).strip() or not folder:
        return None
    query = urlencode({"DwarfId": dwarf_id, "session": folder})
    return f"{base}/ImportSession?{query}"


def open_in_app(url: str) -> bool:
    """Asks Scope Archive to show this page of its own in its window
    (blocking). True when it did; False without an app window, or when it
    doesn't answer (not running, older version without the route)."""
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    try:
        response = requests.get(f"{base}/api/open-in-app", params={"path": path}, timeout=_OPEN_TIMEOUT_S)
        return response.ok and response.json().get("opened") is True
    except (requests.RequestException, ValueError):
        return False


async def archive_session(config, media_path: str) -> None:
    """The "Archive in Dwarfium Scope Archive" action: Scope Archive's
    window when it has one, else a browser tab."""
    url = transfer_url(config, media_path)
    if not url:
        return
    if await run.io_bound(open_in_app, url):
        ui.notify(t("archive_opened_in_app"), type="positive")
    else:
        ui.navigate.to(url, new_tab=True)
