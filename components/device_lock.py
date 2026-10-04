"""One Astro Dwarf Session instance per Dwarf on this PC (user-reported Oct
2026: with the .exe and a source run open together, both connected to the
same Dwarf with the same client_id, the Dwarf dropped one each time the
other connected and both auto-reconnected in turn).

An OS file lock per Dwarf (dwarf_uid), in the temp folder so the .exe and
a source checkout (different folders) see the same lock. The instance
that connects first claims it and keeps it until a manual Disconnect or
its exit (the OS releases it even after a crash). The other instance
doesn't connect: its card shows the Dwarf as used elsewhere, with a link
to the owner's watch page (the owner writes its port next to the lock),
and it connects on its own once the lock is free."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from filelock import FileLock, Timeout

_LOCK_DIR = Path(tempfile.gettempdir()) / "astro_dwarf_session"
_locks: dict[str, FileLock] = {}
_port: int | None = None


def set_port(port: int) -> None:
    """Port of this instance's server, written next to each claimed lock."""
    global _port
    _port = port


def _base(uid: str) -> Path:
    return _LOCK_DIR / re.sub(r"[^A-Za-z0-9_.-]", "_", uid)


def _lock_for(uid: str) -> FileLock:
    lock = _locks.get(uid)
    if lock is None:
        _LOCK_DIR.mkdir(parents=True, exist_ok=True)
        # thread_local=False: claimed from the event loop and io threads
        lock = FileLock(str(_base(uid)) + ".lock", thread_local=False)
        _locks[uid] = lock
    return lock


def claim(uid: str) -> bool:
    """True when this instance holds (or just took) the Dwarf's lock."""
    lock = _lock_for(uid)
    if lock.is_locked:
        return True
    try:
        lock.acquire(timeout=0)
    except Timeout:
        return False
    try:
        Path(str(_base(uid)) + ".owner.json").write_text(
            json.dumps({"pid": os.getpid(), "port": _port}), encoding="utf-8"
        )
    except OSError:
        pass
    return True


def release(uid: str) -> None:
    """After a manual Disconnect: lets another instance take the Dwarf."""
    lock = _locks.get(uid)
    if lock is not None and lock.is_locked:
        lock.release(force=True)


def held_elsewhere(uid: str) -> bool:
    """True when another instance holds the Dwarf (checked without keeping
    the lock)."""
    lock = _lock_for(uid)
    if lock.is_locked:
        return False
    try:
        lock.acquire(timeout=0)
    except Timeout:
        return True
    lock.release(force=True)
    return False


def owner_port(uid: str) -> int | None:
    """Port of the instance holding the Dwarf, if it wrote one."""
    try:
        data = json.loads(Path(str(_base(uid)) + ".owner.json").read_text(encoding="utf-8"))
        return int(data["port"]) if data.get("port") else None
    except (OSError, ValueError, KeyError, TypeError):
        return None
