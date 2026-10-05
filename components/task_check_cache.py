"""Remembers what a View / Check found (task_check.py) so the images
stacked / taken show directly in the lists afterwards, without opening
it again (user-requested Oct 2026).

Per Dwarf, per task: its name and time window, the same for a native
schedule task and for a run of this app's own programs. Only final
results are kept: the task is over and its session was found with a
readable shotsInfo.json - a later check could still find a session not
saved yet, or read a shotsInfo.json that failed this time. JSON file in
the working folder, same pattern as native_schedule.py's cache."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import dwarf_python_api.lib.my_logger as log

CACHE_FILE = Path("task_check_cache.json")

# Entries not checked again for this long are dropped on write
_KEEP_S = 120 * 86400
_FINAL_STATUSES = {"ok", "empty"}
# What the lists show; the rest (thumbnail...) needs the Dwarf anyway
_KEPT_FIELDS = ("status", "stacked", "taken", "integration", "target", "date")


def _read() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


_store: dict = _read()
# Bumped on each kept result: lists built once (the device page's native
# schedules) refresh when it changes, whichever page ran the check
_version = 0


def version() -> int:
    return _version


def _epoch_s(value) -> int | None:
    """Epoch seconds from seconds or milliseconds."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value // 1000 if value > 10_000_000_000 else value


def _key(task: dict) -> str | None:
    start, end = _epoch_s(task.get("startTime")), _epoch_s(task.get("endTime"))
    if start is None or end is None:
        return None
    name = re.sub(r"[^a-z0-9]", "", (task.get("name") or "").lower())
    return f"{name}|{start}|{end}"


def get(dwarf_uid: str, task: dict) -> dict | None:
    """The kept result for this task, or None."""
    key = _key(task)
    found = _store.get(dwarf_uid, {}).get(key) if key else None
    if found is None and _store.get(dwarf_uid):
        log.debug(f"[{dwarf_uid}] no kept task check for {key}")
    return found


def remember(dwarf_uid: str, task: dict, result: dict, now: float | None = None) -> None:
    """Keeps a final result (see the module docstring); ignores others."""
    now = now if now is not None else time.time()
    key = _key(task)
    end = _epoch_s(task.get("endTime"))
    if key is None or end is None or end > now or result.get("status") not in _FINAL_STATUSES:
        log.debug(f"[{dwarf_uid}] task check not kept ({key}, end {end}, status {result.get('status')})")
        return
    entry = {field: result.get(field) for field in _KEPT_FIELDS}
    entry["checkedAt"] = int(now)
    device = _store.setdefault(dwarf_uid, {})
    device[key] = entry
    global _version
    _version += 1
    for old_key in [k for k, v in device.items() if now - (v.get("checkedAt") or 0) > _KEEP_S]:
        device.pop(old_key, None)
    log.debug(f"[{dwarf_uid}] task check kept: {key} -> {entry}")
    try:
        CACHE_FILE.write_text(json.dumps(_store, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        log.warning(f"Couldn't write {CACHE_FILE.resolve()}: {e}")


def shots_text(cached: dict | None, stacked_word: str) -> str:
    """"75/78 <stacked_word>" for a list line, "" when unknown."""
    if not cached or cached.get("stacked") is None or cached.get("taken") is None:
        return ""
    return f"{cached['stacked']}/{cached['taken']} {stacked_word}"
