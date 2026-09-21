"""
components/api_routes.py

Adds REST + page routes to the FastAPI server that NiceGUI is already
running (`from nicegui import app` — `app` IS the FastAPI instance; see
`astro_dwarf_ui.py`, which already uses it for `app.add_static_files`).

No second server, no second port, and no re-reading of `devices.json` on
every request: read the state IN MEMORY from `get_manager()`, the same state
that the UI itself displays.

```
GET  /api/dwarfs
    -> {"devices": [{"name", "dwarfUid", "model", "ip", "connected", "busy", "hasPending"}, ...]}
    Name comes from `device_registry` (`devices.json`), while "ip" comes
    from that device's own config.ini (dwarf_ip) and "connected" from
    the actual DwarfSession in memory. Also includes a synthetic
    "auto:<model>" entry per model with 2+ known devices (see
    _devices_snapshot()'s own docstring) - these have no single "ip",
    since they don't resolve to one real device until send time.

POST /api/schedule
    body: {"dwarfUid": "...", "schedule": {...}}
    - If the device is connected: send it immediately via
      `perform_sync_shooting_schedule()` (run on a separate thread; see
      `components/connection_health.py::connect_and_enter_astro_mode`
      for the same `run.io_bound` pattern).
    - Otherwise: store it via `pending_schedules.set_pending()`; it will
      be offered for synchronization the next time THAT device connects
      (see the hook in `pages/session.py::_handle_connect`).

    -> {"ok": true, "mode": "sent"|"pending", ...}

POST /api/program
    body: {"dwarfUid": "...", "target": {"name", "ra", "dec"}, "camera":
           "wide"|"tele", "exposure", "gain", "count", "binning"?,
           "ircut"?, "date"?, "time"?, "endTime"?, "autofocus"?,
           "startNow"?}
    For the MILKY WAY MOSAIC use case (user-requested Sep 2026): the
    Wide camera - the whole point of using astro_dwarf_session over the
    official app for this - has NO equivalent in the on-device native
    schedule at all (ShootingTaskMsg's business fields, confirmed in
    dwarf_python_api's _build_shooting_task_msg(), carry no camera
    selector - it's implicitly Tele-only). So a Wide-camera plan can't
    go through /api/schedule above; this builds and saves an
    astro_dwarf_session PROGRAM instead (goto_manual + setup_camera/
    setup_wide_camera, matching components/program_editor.py's own
    _blank_program() shape), which DOES support Wide.

    Always writes the program as a ToDo file (components/session_dirs.py),
    same as saving from the editor - so components/scheduler_loop.py's
    existing background loop picks it up and runs it automatically at
    its own date/time, PROVIDED the device has been armed for that
    (pages/programs.py's toggle - this endpoint never arms a device on
    its own, matching that toggle's own "off by default" safety
    reasoning) AND, for a Milky Way mosaic, already in EQ mode - both
    are manual, physical/UI steps this API can't do for the caller.
    date/time default to now/now+5min if omitted.

    startNow=true additionally tries to start it RIGHT AWAY instead of
    only relying on the schedule - only if the device is connected and
    not already running something; otherwise it's silently left as a
    saved, scheduled file (not an error - the ToDo file is exactly as
    useful either way).

    -> {"ok": true, "mode": "started"|"scheduled"|"saved_not_connected"|
        "saved_busy", "filepath": "..."}
```

CORS: the catalogue page has a different origin (a local file or another
port), so `CORSMiddleware` is added here to allow `fetch()` requests from
that page. It is intentionally open (`allow_origins=["*"]`) because this is
a local, LAN-only use case, like the rest of this application — tighten it
if needed.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from nicegui import app, run

from dwarf_python_api.lib.dwarf_config import DwarfConfig
from dwarf_python_api.lib.dwarf_session import get_manager
from dwarf_python_api.lib.dwarf_utils import perform_sync_shooting_schedule
from dwarf_python_api.lib.dwarf_utils import perform_get_last_sync_error
from dwarf_python_api.get_config_data import config_to_dwarf_id_str

from device_registry import list_device_entries
from components import connection_health, scheduler_runner
from components.device_card import _DEVICE_TYPE_ICONS
from components.program_editor import _blank_program, _filename_for
from components.session_dirs import ensure_dirs
import pending_schedules
import dwarf_python_api.lib.my_logger as log


def _bundled_path(relative: str) -> Path:
    """Resolves a data file bundled alongside the app - catalog.html,
    specifically (user-reported Sep 2026: copying it next to the built
    .exe did NOT work). In a normal source checkout, __file__ sits under
    the project root as usual. In a PyInstaller --onefile build, though,
    __file__ for a bundled module resolves inside the temporary
    extraction directory (sys._MEIPASS), NOT the folder the .exe
    actually lives in - so "next to the .exe" was never where this
    lookup was checking. Matches astro_dwarf_ui.py's own frozen-check
    for images_dir, and requires catalog.html to be bundled via
    buildAstroDwarfUI.py's --add-data (not just copied into dist/)."""
    if getattr(sys, "frozen", False):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).resolve().parent.parent
    return base_dir / relative


def _external_path(relative: str) -> Path:
    """Resolves a data file meant to be REPLACEABLE without rebuilding
    the .exe (user-requested Sep 2026, for the Milky Way mosaic planner
    specifically - still under active iteration, unlike catalog.html's
    stable third-party content, so requiring a full rebuild for every
    tweak would be painful). Unlike _bundled_path() above, this reads
    next to the ACTUAL RUNNING .exe (sys.executable's own folder) in a
    packaged build - not sys._MEIPASS, which is a fresh temp extraction
    dir every launch and can never be edited persistently. Matches how
    images/ and components/locales/ are already handled: copied as
    LOOSE files into dist/ by buildAstroDwarfUI.py, not baked in via
    --add-data, so replacing the file next to the .exe takes effect on
    the next launch with no rebuild at all."""
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent
    return base_dir / relative


def _model_display_name(cfg: DwarfConfig) -> str:
    """Full model name ('Dwarf II' / 'Dwarf 3' / 'Dwarf Mini') for a
    device's config - reuses components/device_card.py's own icon table
    (already keyed by the SAME config_to_dwarf_id_str() runtime id) so
    this doesn't duplicate that mapping a third time. Used to group
    devices by model for the AUTO virtual entries below - see
    _devices_snapshot()'s own docstring."""
    dwarf_type = config_to_dwarf_id_str(cfg.dwarf_model_id) or "2"
    return _DEVICE_TYPE_ICONS.get(dwarf_type, _DEVICE_TYPE_ICONS["2"])[1]


def _devices_snapshot() -> list[dict]:
    """Real devices (from devices.json), each tagged with its `model` -
    plus one SYNTHETIC \"auto:<model>\" entry per model that has 2+ real
    devices known (user-requested Sep 2026: \"si on en avait deux même
    type, on pourrait se répartir la charge\"). catalog.html is fully
    generic about what a dwarfUid IS - it just lists whatever this
    returns and POSTs back whichever `dwarfUid` was picked (verified by
    reading its own fetch('/api/dwarfs') / fetch('/api/schedule') code)
    - so a virtual entry works there with ZERO changes to that
    third-party file: catalog.html shows \"Any Dwarf 3 (auto)\" as just
    another option, the user picks it like any other device, and
    api_schedule() below (_resolve_auto_dwarf_uid()) is what actually
    turns \"auto:Dwarf 3\" into a REAL dwarfUid at send time - resolved
    THEN, not when this snapshot was fetched, so it reflects whichever
    device is actually free at the moment of sending, not whenever the
    catalog page happened to load."""
    manager = get_manager()
    sessions_by_uid = {s.dwarf_uid: s for s in manager.all()}
    out = []
    for entry in list_device_entries():
        try:
            cfg = DwarfConfig.from_files(entry.config_py, entry.config_ini)
        except FileNotFoundError:
            continue
        session = sessions_by_uid.get(cfg.dwarf_uid)
        out.append({
            "name": entry.name,
            "dwarfUid": cfg.dwarf_uid,
            "model": _model_display_name(cfg),
            "ip": cfg.dwarf_ip,
            "connected": bool(session and session.is_connected),
            "busy": bool(session and connection_health.is_busy(cfg.dwarf_uid)),
            "hasPending": pending_schedules.get_pending(cfg.dwarf_uid) is not None,
        })

    models_count: dict[str, int] = {}
    for d in out:
        models_count[d["model"]] = models_count.get(d["model"], 0) + 1
    for model, count in models_count.items():
        if count < 2:
            continue
        same_model = [d for d in out if d["model"] == model]
        out.append({
            "name": f"Any {model} (auto)",
            "dwarfUid": f"auto:{model}",
            "model": model,
            "connected": any(d["connected"] for d in same_model),
            "busy": False,  # a virtual entry is never itself "busy" - see resolution logic
            "hasPending": False,
            "virtual": True,
        })
    return out


def _resolve_auto_dwarf_uid(dwarf_uid: str) -> tuple[str | None, str | None]:
    """Turns a virtual 'auto:<model>' dwarfUid (see _devices_snapshot()'s
    synthetic entries) into a REAL device's dwarfUid, picking the best
    candidate of that model RIGHT NOW - not whichever was least busy
    when the catalog page loaded its dropdown, which could easily be
    stale by the time \"Send\" is actually clicked.

    Preference order: connected AND idle > connected but busy (queued
    as busy_pending, same as picking that device manually) > known but
    offline (queued as pending, offered on its next connect) - i.e. the
    exact same three outcomes api_schedule() already has for a manually-
    picked device, just with the device itself chosen automatically.
    Returns (resolved_uid, error_message) - error_message is set only
    when no device of that model is known at all."""
    if not dwarf_uid.startswith("auto:"):
        return dwarf_uid, None
    model = dwarf_uid[len("auto:"):]
    candidates = [d for d in _devices_snapshot() if d.get("model") == model and not d.get("virtual")]
    if not candidates:
        return None, f"No known device of model {model!r}"
    candidates.sort(key=lambda d: (not d["connected"], d["busy"], d["hasPending"]))
    return candidates[0]["dwarfUid"], None


def register_api_routes() -> None:
    """Appelez ceci une fois depuis astro_dwarf_ui.py::main(), après
    bootstrap_devices() (comme les autres build_*_page() calls)."""

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/catalog")
    def catalog_page():
        """Serves the DSO catalog page over THIS server's own http://,
        instead of file:// / content:// on the phone. User-reported (Sep
        2026): the catalog's own location step hung silently on mobile -
        the Geolocation API requires a SECURE CONTEXT (https, or
        localhost) and file:///content:// don't qualify, so the browser
        just never resolves the permission prompt. Visiting this route
        from the phone (http://<this PC's LAN IP>:<port>/catalog) makes
        the catalog and the /api/* routes same-origin too, which also
        sidesteps the earlier 127.0.0.1-means-the-phone-itself confusion
        in the "Program to Dwarf" panel's bridge URL field.

        Looks for catalog.html next to astro_dwarf_ui.py in a source
        checkout, or bundled into the .exe in a packaged build (see
        _bundled_path() above) - drop the downloaded catalog file at
        the project root under that exact name for this route to find
        it in dev mode; a packaged build needs it present at build time
        instead (buildAstroDwarfUI.py bundles it via --add-data).
        """
        catalog_path = _bundled_path("catalog.html")
        if not catalog_path.exists():
            return JSONResponse(
                {"error": f"catalog.html not found at {catalog_path} - place the DSO catalog HTML file there."},
                status_code=404,
            )
        return FileResponse(catalog_path, media_type="text/html")

    @app.get("/mosaic-planner-{lang}")
    def mosaic_planner_page(lang: str):
        """Serves the Milky Way mosaic planner the same way /catalog
        serves catalog.html above - same-origin with /api/*, secure-
        context geolocation on mobile, etc. Uses _external_path()
        rather than _bundled_path() (see that function's own docstring)
        specifically because this file is still under active iteration
        - drop an updated milky_way_mosaic_planner_<lang>.html next to
        the project root (dev) or the built .exe (packaged) and it
        takes effect on the very next request, no rebuild needed
        either way.

        {lang} is "fr" or "en" (user-requested Sep 2026: no real i18n
        system in this standalone file yet - just two full copies, one
        per language, picked by whichever link the caller used - see
        pages/programs.py's own link, which picks the URL from
        components.i18n.get_language()). Any other value falls back to
        "fr" rather than 404ing, so a stray/old link still resolves to
        SOMETHING rather than a dead page.
        """
        if lang not in ("fr", "en"):
            lang = "fr"
        planner_path = _external_path(f"milky_way_mosaic_planner_{lang}.html")
        if not planner_path.exists():
            return JSONResponse(
                {"error": f"milky_way_mosaic_planner_{lang}.html not found at {planner_path} - place the mosaic planner HTML file there."},
                status_code=404,
            )
        return FileResponse(planner_path, media_type="text/html")

    @app.get("/api/dwarfs")
    def api_dwarfs():
        return JSONResponse({"devices": _devices_snapshot()})

    @app.post("/api/schedule")
    async def api_schedule(request: Request):
        try:
            body = await request.json()
        except json.JSONDecodeError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        dwarf_uid = body.get("dwarfUid")
        schedule = body.get("schedule", body)

        if not dwarf_uid:
            return JSONResponse({"error": "dwarfUid is required"}, status_code=400)

        if dwarf_uid.startswith("auto:"):
            resolved, err = _resolve_auto_dwarf_uid(dwarf_uid)
            if err:
                return JSONResponse({"error": err}, status_code=404)
            log.info(f"[{dwarf_uid}] Resolved to {resolved!r} (least busy of that model).")
            dwarf_uid = resolved

        try:
            session = get_manager().get(dwarf_uid)
        except KeyError:
            return JSONResponse({"error": f"unknown dwarfUid {dwarf_uid!r}"}, status_code=404)

        if session.is_connected:
            # CONCURRENCY: don't fire CMD_SYNC_SHOOTING_SCHEDULE while
            # another command is in flight for this session - a manual
            # action from pages/session.py OR a scheduler_runner "program"
            # (astro_dwarf_session's own manual/scheduled session, which
            # holds this exact slot for its ENTIRE run - see scheduler_
            # runner.py's COMMAND SLOT note) both claim it via
            # connection_health.try_acquire_command_slot(). Racing that
            # unlocked client_instance.command field is the exact hazard
            # connection_health.py's CONCURRENCY NOTE warns about.
            if not connection_health.try_acquire_command_slot(dwarf_uid, caller="api_routes.sync"):
                log.info(f"[{dwarf_uid}] Busy (manual session or other command in flight) — queuing as pending instead of racing it.")
                pending_schedules.set_pending(dwarf_uid, schedule)
                return JSONResponse({"ok": True, "mode": "busy_pending"})

            log.info(f"[{dwarf_uid}] Sending shooting schedule now (device connected).")
            try:
                ok = await run.io_bound(perform_sync_shooting_schedule, schedule, session=session)
            finally:
                connection_health.release_command_slot(dwarf_uid)
            if ok:
                pending_schedules.clear_pending(dwarf_uid)  # un envoi réussi rend l'attente obsolète
                return JSONResponse({"ok": True, "mode": "sent"})
            # User-requested (Sep 2026): "ce message m'intéresse plus
            # que... check the log" - the real DwarfErrorCode name
            # (e.g. "CODE_SHOOTING_SCHEDULE_TIME_CONFLICT") is now
            # available via perform_get_last_sync_error() right after a
            # failed sync - included here so the catalog page's own
            # toast can show it directly instead of sending the person
            # to the log file.
            reason = perform_get_last_sync_error(session=session)
            return JSONResponse(
                {"ok": False, "mode": "sent", "error": "perform_sync_shooting_schedule failed", "reason": reason},
                status_code=502,
            )

        log.info(f"[{dwarf_uid}] Device offline — storing schedule as pending.")
        pending_schedules.set_pending(dwarf_uid, schedule)
        return JSONResponse({"ok": True, "mode": "pending"})

    @app.post("/api/program")
    async def api_program(request: Request):
        try:
            body = await request.json()
        except json.JSONDecodeError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        dwarf_uid = body.get("dwarfUid")
        if not dwarf_uid:
            return JSONResponse({"error": "dwarfUid is required"}, status_code=400)

        if dwarf_uid.startswith("auto:"):
            resolved, err = _resolve_auto_dwarf_uid(dwarf_uid)
            if err:
                return JSONResponse({"error": err}, status_code=404)
            log.info(f"[{dwarf_uid}] Resolved to {resolved!r} (least busy of that model).")
            dwarf_uid = resolved

        try:
            session = get_manager().get(dwarf_uid)
        except KeyError:
            return JSONResponse({"error": f"unknown dwarfUid {dwarf_uid!r}"}, status_code=404)

        target = body.get("target") or {}
        name = target.get("name") or "target"
        ra = target.get("ra")
        dec = target.get("dec")
        if ra is None or dec is None:
            return JSONResponse({"error": "target.ra and target.dec are required"}, status_code=400)

        camera = str(body.get("camera", "wide")).lower()
        if camera not in ("wide", "tele"):
            return JSONResponse({"error": "camera must be 'wide' or 'tele'"}, status_code=400)

        program = _blank_program()
        cmd = program["command"]
        cmd["id_command"]["description"] = name
        cmd["id_command"]["date"] = body.get("date") or datetime.now().strftime("%Y-%m-%d")
        cmd["id_command"]["time"] = (
            body.get("time") or (datetime.now() + timedelta(minutes=5)).strftime("%H:%M:%S")
        )

        # Manual RA/Dec goto - a Milky Way mosaic tile (the driving use
        # case, user-requested Sep 2026) isn't a named catalog object, so
        # goto_solar (Sun/Moon/planets) doesn't apply here.
        cmd["goto_manual"] = {
            "do_action": True,
            "target": name,
            "ra_coord": str(ra),
            "dec_coord": str(dec),
            "wait_after": 10,
        }

        # Per-tile autofocus (user-requested Sep 2026, Milky Way mosaic
        # use case: focus can drift with temperature over a long night,
        # but re-focusing on EVERY tile wastes real integration time on
        # overhead). Deliberately just a plain per-request bool, no
        # "every N tiles" counter here - each /api/program call is
        # independent and stateless, so tracking "tiles since last
        # focus" across many separate saved files would need new shared
        # state for little benefit; the caller (the mosaic planner)
        # already knows its own tile order and can decide which ones
        # set autofocus=true (e.g. the first tile of each hour) when it
        # builds each request.
        cmd["infinite_focus"]["do_action"] = bool(body.get("autofocus", False))

        # Only ONE of setup_camera/setup_wide_camera is ever do_action=True
        # for a program built this way - matches how the editor itself
        # only lets you pick Tele XOR Wide, never both, for one program.
        active_key = "setup_wide_camera" if camera == "wide" else "setup_camera"
        inactive_key = "setup_camera" if camera == "wide" else "setup_wide_camera"
        active = cmd[active_key]
        active["do_action"] = True
        active["exposure"] = str(body.get("exposure", active["exposure"]))
        active["gain"] = str(body.get("gain", active["gain"]))
        active["count"] = str(body.get("count", active["count"]))
        active["end_time"] = body.get("endTime", "")
        if camera == "tele":
            active["binning"] = str(body.get("binning", active.get("binning", "0")))
            active["ircut"] = str(body.get("ircut", active.get("ircut", "1")))
        cmd[inactive_key]["do_action"] = False

        # Always saved as a ToDo file first, START-NOW-or-not - see this
        # route's own docstring above for why (scheduler_loop.py picks it
        # up on its own once the device is armed, same as any program
        # saved from the editor).
        dirs = ensure_dirs(session)
        filename = _filename_for(program)
        filepath = os.path.join(dirs["TODO_DIR"], filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(program, f, indent=4)
        log.info(f"[{dwarf_uid}] Program saved: {filepath}")

        if not body.get("startNow"):
            return JSONResponse({"ok": True, "mode": "scheduled", "filepath": filepath})

        if not session.is_connected:
            log.info(f"[{dwarf_uid}] startNow requested but device is offline - left as scheduled.")
            return JSONResponse({"ok": True, "mode": "saved_not_connected", "filepath": filepath})

        if scheduler_runner.is_running(dwarf_uid):
            log.info(f"[{dwarf_uid}] startNow requested but a program is already running - left as scheduled.")
            return JSONResponse({"ok": True, "mode": "saved_busy", "filepath": filepath})

        try:
            scheduler_runner.start_run(dwarf_uid, cmd, session, source_filepath=filepath)
        except RuntimeError as e:
            # Same race is possible as scheduler_loop.py's own start_run()
            # call (is_running() checked above, but something else could
            # have claimed it between that check and this call) -
            # RuntimeError here means it's STILL saved as a ToDo file, not
            # lost, so this is a soft "try again" rather than a hard error.
            log.info(f"[{dwarf_uid}] start_run() race: {e} - left as scheduled.")
            return JSONResponse({"ok": True, "mode": "saved_busy", "filepath": filepath})

        return JSONResponse({"ok": True, "mode": "started", "filepath": filepath})
