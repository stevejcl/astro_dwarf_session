"""Link to archive a session with Dwarfium Scope Archive (user-requested
Oct 2026).

Scope Archive's own Transfer page does the import: in Archive mode, with
its DwarfId and a session folder name, it preselects that folder on the
Dwarf (FTP, RESTACKED / STARTRAILS handled by the folder's name) and
copies it to the Backup with its own checks, once the user confirms. So
this app only builds the address, from the Settings page's Dwarfium URL
and DwarfId (the same as the "Open in Dwarfium" links)."""
from __future__ import annotations

import posixpath
from urllib.parse import urlencode


def session_folder(media_path: str) -> str:
    """Session folder name of one of its files (the album's filePath or
    thumbnailPath: .../Astronomy/<session>/stacked.jpg)."""
    return posixpath.basename(posixpath.dirname(media_path or ""))


def transfer_url(config, media_path: str) -> str | None:
    """Scope Archive's Transfer page for this session, or None when the
    Dwarfium URL / DwarfId isn't set for this Dwarf."""
    base = (getattr(config, "dwarfium_base_url", "") or "").rstrip("/")
    dwarf_id = getattr(config, "dwarfium_id", "") or ""
    folder = session_folder(media_path)
    if not base or not str(dwarf_id).strip() or not folder:
        return None
    query = urlencode({"DwarfId": dwarf_id, "session": folder, "mode": "Archive"})
    return f"{base}/Transfer?{query}"
