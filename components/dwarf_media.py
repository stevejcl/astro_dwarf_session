"""Files of a session's folder on the Dwarf, for the explorer's download
(user-requested Oct 2026: the stacked PNG too, not only the JPG).

The album listing gives one file per session (stacked.jpg) and its
thumbnail; the folder holds more, among them the PNG the Dwarf writes
with its own long name ("stacked-16_M 42 ..._60s40_Duo-Band_...png").
The listing comes from the Dwarf's anonymous FTP (the only way to list a
folder - HTTP serves a known file, it doesn't list); the bytes are read
over HTTP, as the explorer's thumbnails, and over FTP if that fails.

The FTP root isn't the HTTP one: a file served as
  http://<ip>/DWARF_mini/Astronomy/<session>/stacked.jpg
sits on FTP at /Astronomy/<session> (D3, Mini) or /DWARF_II/Astronomy/
<session> (D2) - see dwarf_python_api's get_live_data_dwarf.py. Both are
tried rather than guessed from the model."""
from __future__ import annotations

import posixpath
from ftplib import FTP, all_errors

import requests

import dwarf_python_api.lib.my_logger as log

# The Dwarf's own anonymous FTP (dwarf_ip carries no port)
FTP_PORT = 21
_FTP_TIMEOUT_S = 10
_HTTP_TIMEOUT_S = 60


def _ftp_dir_candidates(http_dir: str) -> list[str]:
    """FTP paths to try for an HTTP folder, most likely first."""
    parts = [p for p in http_dir.strip("/").split("/") if p]
    candidates = ["/" + "/".join(parts[1:])] if len(parts) > 1 else []
    candidates.append("/" + "/".join(parts))
    return [c for c in candidates if c != "/"]


def list_session_files(dwarf_ip: str, http_dir: str) -> list[str]:
    """File names of a session's folder, [] when it can't be listed."""
    host = dwarf_ip.split(":")[0]
    try:
        ftp = FTP()
        ftp.connect(host, FTP_PORT, timeout=_FTP_TIMEOUT_S)
        ftp.login("Anonymous", "")
        ftp.set_pasv(True)
    except all_errors as e:
        log.debug(f"Dwarf FTP: no connection to {host} ({e})")
        return []
    try:
        for candidate in _ftp_dir_candidates(http_dir):
            try:
                ftp.cwd(candidate)
            except all_errors:
                continue
            names = [posixpath.basename(name) for name in ftp.nlst()]
            log.debug(f"Dwarf FTP: {candidate} -> {names}")
            return [name for name in names if name not in (".", "..")]
        log.debug(f"Dwarf FTP: no folder found for {http_dir}")
        return []
    except all_errors as e:
        log.debug(f"Dwarf FTP: listing failed for {http_dir} ({e})")
        return []
    finally:
        try:
            ftp.quit()
        except all_errors:
            pass


def png_path(dwarf_ip: str, file_path: str) -> str | None:
    """HTTP path of the session's PNG (the Dwarf's own stacked PNG), or
    None. file_path: the album entry's own filePath (.../stacked.jpg)."""
    http_dir = posixpath.dirname(file_path)
    names = [n for n in list_session_files(dwarf_ip, http_dir) if n.lower().endswith(".png")]
    if not names:
        return None
    # "stacked-16_..." (16-bit) first, else the longest name: the Dwarf's
    # own export rather than a preview it may also have written
    names.sort(key=lambda n: (not n.lower().startswith("stacked"), -len(n)))
    return posixpath.join(http_dir, names[0])


def _fetch_http(dwarf_ip: str, path: str) -> bytes | None:
    try:
        response = requests.get(f"http://{dwarf_ip}{path}", timeout=_HTTP_TIMEOUT_S)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        log.debug(f"Dwarf HTTP: {path} unreadable ({e})")
        return None


def _fetch_ftp(dwarf_ip: str, path: str) -> bytes | None:
    host = dwarf_ip.split(":")[0]
    chunks: list[bytes] = []
    try:
        ftp = FTP()
        ftp.connect(host, FTP_PORT, timeout=_FTP_TIMEOUT_S)
        ftp.login("Anonymous", "")
        ftp.set_pasv(True)
    except all_errors as e:
        log.debug(f"Dwarf FTP: no connection to {host} ({e})")
        return None
    try:
        for candidate in _ftp_dir_candidates(posixpath.dirname(path)):
            try:
                ftp.retrbinary(f"RETR {posixpath.join(candidate, posixpath.basename(path))}", chunks.append)
            except all_errors:
                chunks.clear()
                continue
            return b"".join(chunks)
        return None
    finally:
        try:
            ftp.quit()
        except all_errors:
            pass


def fetch(dwarf_ip: str, path: str) -> bytes | None:
    """The file's bytes, over HTTP then FTP, or None."""
    return _fetch_http(dwarf_ip, path) or _fetch_ftp(dwarf_ip, path)
