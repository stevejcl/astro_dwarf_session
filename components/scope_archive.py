"""Link to archive a session with Dwarfium Scope Archive (user-requested
Oct 2026).

Scope Archive's ImportSession page does the import: with its DwarfId
and a session folder name, it syncs that session only from the Dwarf
(USB or FTP) and scans it into its database - the session is then
registered - and opens its Transfer page with it preselected (Archive
mode), where the user picks the backup drive and starts the copy. So
this app only builds the address, from the Settings page's Dwarfium
Scope Archive URL and DwarfId (the same as the "Open in" links).
"""
from __future__ import annotations

import posixpath
from urllib.parse import urlencode


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
