"""Shared parsing of the DEVICE's own native shooting-schedule read-back
(CMD_GET_ALL_SHOOTING_SCHEDULE / perform_get_all_shooting_schedule_full())
into plain dicts - factored out of pages/session.py's own "Shooting
Schedule" section (_handle_refresh_schedules()) so components/api_routes.py
can return the exact same shape over JSON (for the combined /Program page,
user-requested Sep 2026) without duplicating this parsing a second time.

Also holds a small persistent CACHE of the last successfully-read schedule
per device (user-requested Sep 2026: "meme si non connecte on a une liste
des qu'on l'a interrogee") - JSON file, same pattern as pending_schedules.py
(one small file, nothing to join/query), so /api/programs still has
something to show for a device that's offline right now, and the cache
survives an app restart too."""
from __future__ import annotations

import json
import time
from pathlib import Path

CACHE_FILE = Path("native_schedule_cache.json")

SCHEDULE_STATE_LABELS = {
    0: "initialized", 1: "pending", 2: "shooting", 3: "completed", 4: "expired",
}
TASK_STATE_LABELS = {
    0: "idle", 1: "shooting", 2: "success", 3: "failed", 4: "interrupted",
}


def parse_native_schedule_info(info) -> list[dict]:
    """Turns a ResGetAllShootingSchedule protobuf message into a list of
    plain dicts - one per on-device schedule, each with its tasks. Used
    both by pages/session.py's own UI (which further applies its local
    _schedule_state_label()/_task_state_label() for display) and by
    api_routes.py's /api/programs (returned as-is, state_code left as
    a raw int so the HTML page can map it to its own tags/labels)."""
    parsed = []
    for sched in info.shooting_schedule:
        tasks = []
        for task in sched.shooting_tasks:
            try:
                p = json.loads(task.params)
            except Exception:
                p = {}
            tasks.append({
                "name": p.get("name", "?"),
                "state_code": task.state,
                "startTime": p.get("startTime"),
                "endTime": p.get("endTime"),
                "shutterName": p.get("shutterName"),
                "gainName": p.get("gainName"),
                "filterModeName": p.get("filterModeName"),
                "count": p.get("count"),
                "stacked": p.get("stacked"),
            })
        recency = sched.updated_time or sched.created_time or sched.schedule_time or 0
        parsed.append({
            "scheduleId": sched.schedule_id,
            "name": sched.schedule_name or sched.schedule_id,
            "state_code": sched.state,
            "startTime": sched.start_time or None,
            "endTime": sched.end_time or None,
            "tasks": tasks,
            "recency": recency,
        })
    parsed.sort(key=lambda s: s["recency"], reverse=True)
    return parsed


def _read_cache_file() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_cache_file(data: dict) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


_store: dict = _read_cache_file()


def get_cached(dwarf_uid: str) -> list[dict] | None:
    entry = _store.get(dwarf_uid)
    return entry["schedule"] if entry else None


def get_cached_fetched_at(dwarf_uid: str) -> float | None:
    entry = _store.get(dwarf_uid)
    return entry["fetchedAt"] if entry else None


def set_cached(dwarf_uid: str, parsed: list[dict]) -> None:
    _store[dwarf_uid] = {"schedule": parsed, "fetchedAt": time.time()}
    _write_cache_file(_store)


def remove_from_cache(dwarf_uid: str, schedule_id: str) -> None:
    entry = _store.get(dwarf_uid)
    if not entry:
        return
    entry["schedule"] = [s for s in entry["schedule"] if s.get("scheduleId") != schedule_id]
    _write_cache_file(_store)
