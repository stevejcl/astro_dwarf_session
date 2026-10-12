"""Presence of Dwarfium Scope Archive (user-requested Oct 2026).

Every 30 s (and at startup; every 10 s while it doesn't answer, e.g.
both apps just started) this app says hello to the Scope Archive URL(s)
of the Settings page:

POST {scope_archive}/api/peer/hello  {"app": "astro_dwarf_session", "version": ..., "port": ...}

Scope Archive thus learns this app's address and that it is running (to
offer actions done here), and this app learns whether Scope Archive
answers: its "Open in" / "Archive" buttons are greyed when it doesn't,
instead of waiting for a request timeout. Older Scope Archive versions
have no /api/peer/hello: any HTTP answer still means it is running.

Requests in a worker thread, 2 s timeout: never blocks the interface.
Logged only when a state changes.
"""
from __future__ import annotations

import time

import requests
from nicegui import app, run

import dwarf_python_api.lib.my_logger as log
from components.app_version import get_app_version

HELLO_INTERVAL_S = 30
RETRY_INTERVAL_S = 10
_TIMEOUT_S = 2

_port: int | None = None
# base URL -> {"up": bool, "version": str, "checked": time.monotonic()}
_state: dict[str, dict] = {}


def _bases() -> list[str]:
    """Scope Archive URLs set on this app's Dwarfs (usually one)."""
    from dwarf_python_api.lib.dwarf_config import DwarfConfig
    from device_registry import list_device_entries
    from components.scope_archive import scope_settings
    bases = []
    for entry in list_device_entries():
        try:
            base, _dwarf_id = scope_settings(DwarfConfig.from_files(entry.config_py, entry.config_ini))
        except Exception:
            continue
        base = base.strip().rstrip("/")
        if base and base not in bases:
            bases.append(base)
    return bases


def _hello(base: str) -> dict:
    """Blocking: one hello to that Scope Archive."""
    try:
        response = requests.post(
            f"{base}/api/peer/hello",
            json={"app": "astro_dwarf_session", "version": get_app_version(), "port": _port},
            timeout=_TIMEOUT_S,
        )
    except requests.RequestException:
        return {"up": False, "version": ""}
    try:
        version = str(response.json().get("version", "")) if response.ok else ""
    except ValueError:
        version = ""
    return {"up": True, "version": version}


def _set(base: str, result: dict | None) -> None:
    if result is None:   # run.io_bound() while the app is stopping: nothing was asked
        return
    previous = _state.get(base)
    _state[base] = {**result, "checked": time.monotonic()}
    if previous is None or previous["up"] != result["up"]:
        if result["up"]:
            log.info(f"Dwarfium Scope Archive {result['version']} reachable at {base}".replace("  ", " "))
        elif previous is not None:
            log.warning(f"Dwarfium Scope Archive not reachable at {base}")
        else:
            log.info(f"Dwarfium Scope Archive not running at {base}")


async def hello_all() -> None:
    try:
        bases = await run.io_bound(_bases)
    except Exception as e:
        log.error(f"Scope Archive hello: {e}")
        return
    if not bases:   # none set, or the app is stopping (run.io_bound() -> None)
        return
    now = time.monotonic()
    for base in bases:
        state = _state.get(base)
        due = HELLO_INTERVAL_S if state and state["up"] else RETRY_INTERVAL_S
        if state is None or now - state["checked"] >= due - 1:
            _set(base, await run.io_bound(_hello, base))


def is_up(url: str | None) -> bool | None:
    """Whether the Scope Archive of that URL (a page of it, or its base)
    answered the last hello; None when not checked yet."""
    if not url:
        return None
    for base, state in _state.items():
        if url == base or url.startswith(base + "/"):
            return state["up"]
    return None


async def check_now(url: str) -> bool | None:
    """Hello right now to the Scope Archive of that URL (before giving up on
    a click: it may have been started since the last hello)."""
    for base in list(_state):
        if url == base or url.startswith(base + "/"):
            _set(base, await run.io_bound(_hello, base))
            return _state.get(base, {}).get("up")
    return None


def start(port: int) -> None:
    """Called once at startup (astro_dwarf_ui.py)."""
    global _port
    _port = port
    app.timer(RETRY_INTERVAL_S, hello_all)
