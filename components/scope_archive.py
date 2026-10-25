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

Clicked from another device - a phone on the LAN (user-requested Oct
2026: the capture launched from the phone, its archive opened on the PC)
- the page opens on that device when Scope Archive answers on the LAN
(started with --lan); its address the PC's as the phone reaches this app
(LAN, Tailscale) when the Settings URL is one of this PC's (localhost, its
LAN IP...: both apps on the PC), another machine's kept. Else on the PC,
said so.
"""
from __future__ import annotations

import configparser
import posixpath
import socket
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from nicegui import run, ui

from components import peer_link
from components.i18n import t

# Scope Archive waits up to 4 s for its window's page to be ready
_OPEN_TIMEOUT_S = 8
# Scope Archive answering on the LAN address (for a phone)
_LAN_TIMEOUT_S = 2
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def remote_host(request) -> str | None:
    """The host name another device (a phone) used to reach this app, or
    None when the request comes from this PC: from the loopback, or from
    the address it asked for (a browser of the PC on its LAN IP)."""
    if request is None or request.client is None:
        return None
    client = request.client.host
    asked = request.url.hostname or ""
    if client in _LOOPBACK or client == asked:
        return None
    return asked or None


def _own_address(host: str) -> bool:
    """host is one of this PC's addresses - loopback, its LAN or Tailscale
    IP, its name: a socket can be bound to it only here."""
    if host in _LOOPBACK:
        return True
    try:
        for family, _, _, _, address in socket.getaddrinfo(host, None):
            with socket.socket(family, socket.SOCK_DGRAM) as probe:
                probe.bind((address[0], 0))
            return True
    except OSError:
        return False
    return False


def lan_url(url: str, host: str) -> str:
    """url for a device that reaches this PC as `host`: a URL of this PC
    (Scope Archive here: localhost, or its LAN IP while the phone comes
    through Tailscale - user-asked Oct 2026) gets that host, its port kept;
    another machine's is left as set in the Settings."""
    parts = urlsplit(url)
    if not parts.hostname or parts.hostname == host or not _own_address(parts.hostname):
        return url
    netloc = f"[{host}]" if ":" in host else host
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def answers(url: str) -> bool:
    """Scope Archive answers at this address (blocking) - on a LAN address,
    only when started with --lan (else bound to 127.0.0.1)."""
    parts = urlsplit(url)
    try:
        return requests.get(f"{parts.scheme}://{parts.netloc}/", timeout=_LAN_TIMEOUT_S).ok
    except requests.RequestException:
        return False


def open_for(url: str, request) -> dict:
    """Where the page opens for the device of `request` (blocking):
    {"url": ...} for that device to open (a phone, Scope Archive on the
    LAN), else Scope Archive's window on the PC: {"opened": True, "on_pc":
    <clicked from another device>}, {"busy": True}, or {"url": url} when it
    has no window (a browser tab, as before)."""
    host = remote_host(request)
    if host:
        phone_url = lan_url(url, host)
        if answers(phone_url):
            return {"url": phone_url}
    result = open_in_app(url)
    if result == "opened":
        return {"opened": True, "on_pc": bool(host)}
    if result == "busy":
        return {"busy": True}
    return {"url": url}


def scope_settings(config) -> tuple[str, str]:
    """(URL, Dwarf Id) of Dwarfium Scope Archive for this Dwarf. From the
    config when the library reads them (dwarf_python_api >= 3.1.5), else
    straight from the device's config.ini, where the Settings page saves
    them (user-reported Oct 2026: with an older library they were lost at
    each start)."""
    base = (getattr(config, "dwarfium_base_url", "") or "").strip()
    dwarf_id = str(getattr(config, "dwarfium_id", "") or "").strip()
    ini_path = getattr(config, "config_ini_path", "") or ""
    if (not base or not dwarf_id) and ini_path:
        ini = configparser.ConfigParser()
        try:
            ini.read(ini_path, encoding="utf-8")
        except (configparser.Error, OSError, UnicodeDecodeError):
            return base, dwarf_id
        if ini.has_section("CONFIG"):
            base = base or ini["CONFIG"].get("dwarfium_base_url", "").strip()
            dwarf_id = dwarf_id or ini["CONFIG"].get("dwarfium_id", "").strip()
    return base, dwarf_id


def session_folder(media_path: str) -> str:
    """Session folder name of one of its files (the album's filePath or
    thumbnailPath: .../Astronomy/<session>/stacked.jpg)."""
    return posixpath.basename(posixpath.dirname(media_path or ""))


def _dwarf_ip_param(config) -> dict:
    """{"DwarfIp": <the Dwarf's IP as this app reaches it>}, or {} (user-
    requested Oct 2026). Scope Archive tries it first for FTP, before its
    own configured IP - the local site's when this app runs on a remote
    site, the Dwarf reached through Tailscale - and its Dwarf Configuration
    page offers to save it, as FTP or session IP. Older Scope Archive
    versions ignore it."""
    dwarf_ip = (getattr(config, "dwarf_ip", "") or "").strip()
    return {"DwarfIp": dwarf_ip} if dwarf_ip else {}


def transfer_url(config, media_path: str) -> str | None:
    """Scope Archive's import page for this session (then its Transfer
    page), or None when the URL / DwarfId isn't set for this Dwarf. With
    the Dwarf's IP (_dwarf_ip_param)."""
    base, dwarf_id = scope_settings(config)
    base = base.rstrip("/")
    folder = session_folder(media_path)
    if not base or not dwarf_id or not folder:
        return None
    query = urlencode({"DwarfId": dwarf_id, "session": folder, **_dwarf_ip_param(config)})
    return f"{base}/ImportSession?{query}"


def open_in_app(url: str) -> str:
    """Asks Scope Archive to show this page of its own in its window
    (blocking). "opened" when it did; "busy" when its window is still
    starting (user-requested Oct 2026: navigating it then froze it - try
    again in a moment, no browser tab); "" without an app window, or when
    it doesn't answer (not running, older version without the route)."""
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    try:
        response = requests.get(f"{base}/api/open-in-app", params={"path": path}, timeout=_OPEN_TIMEOUT_S)
        data = response.json() if response.ok else {}
    except (requests.RequestException, ValueError):
        return ""
    if data.get("opened") is True:
        return "opened"
    return "busy" if data.get("busy") is True else ""


# Scope Archive pages for one Dwarf: (path, extra query)
_PAGES = {
    "config": ("/Dwarf", {}),                        # Dwarf Configuration
    "explore_dwarf": ("/Explore/", {"mode": "dwarf"}),  # sessions on the Dwarf
    "explore_backup": ("/Explore/", {}),             # backed-up sessions (its default mode)
}


def page_url(config, page: str) -> str | None:
    """One of Scope Archive's own pages for this Dwarf (see _PAGES), or
    None when the URL / DwarfId isn't set. With the Dwarf's IP
    (_dwarf_ip_param), for the Dwarf Configuration page."""
    base, dwarf_id = scope_settings(config)
    base = base.rstrip("/")
    if not base or not dwarf_id:
        return None
    path, extra = _PAGES[page]
    return f"{base}{path}?{urlencode({'DwarfId': dwarf_id, **extra, **_dwarf_ip_param(config)})}"


async def open_page(url: str | None) -> None:
    """Shows a Scope Archive page: on the phone when clicked there and
    Scope Archive is on the LAN (open_for), else in its window when it
    runs as an app (notified), else in a browser tab. When it didn't answer the last
    hello (peer_link.py), asked again first: said so if still not
    running, without waiting for a timeout or opening a dead tab."""
    if not url:
        return
    if peer_link.is_up(url) is False and await peer_link.check_now(url) is False:
        ui.notify(t("scope_archive_not_running"), type="warning")
        return
    try:
        request = ui.context.client.request
    except (AttributeError, RuntimeError):
        request = None
    result = await run.io_bound(open_for, url, request)
    if result.get("url") and remote_host(request):
        # On the phone: a link to tap - a tab opened after this round trip is
        # blocked by its browser (no longer the click's)
        with ui.dialog() as dialog, ui.card():
            ui.label(t("archive_open_on_device"))
            ui.link(t("archive_in_scope_archive"), result["url"], new_tab=True) \
                .on("click", dialog.close)
            ui.button(t("close"), on_click=dialog.close).props("flat")
        dialog.open()
    elif result.get("opened"):
        ui.notify(t("archive_opened_on_pc" if result.get("on_pc") else "archive_opened_in_app"), type="positive")
    elif result.get("busy"):
        ui.notify(t("archive_app_busy"), type="warning")
    else:
        ui.navigate.to(result["url"], new_tab=True)


async def archive_session(config, media_path: str) -> None:
    """The "Archive in Dwarfium Scope Archive" action (import then
    Transfer page)."""
    await open_page(transfer_url(config, media_path))


def watch_presence(element, url_fn) -> None:
    """Greys a Scope Archive button while Scope Archive doesn't answer its
    hellos (peer_link.py). Still clickable: a click asks again."""
    def update() -> None:
        try:
            url = url_fn()
        except NameError:   # url_fn's variables not built yet
            return
        if peer_link.is_up(url) is False:
            element.classes(add="opacity-40")
        else:
            element.classes(remove="opacity-40")
    update()
    ui.timer(5, update)
