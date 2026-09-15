"""
components/api_routes.py

Greffe deux routes REST sur le serveur FastAPI que NiceGUI fait déjà tourner
(`from nicegui import app` — app EST l'instance FastAPI, voir
astro_dwarf_ui.py qui l'utilise déjà pour app.add_static_files). Pas de
second serveur, pas de second port, pas de re-lecture de devices.json à
chaque appel : on lit l'état EN MÉMOIRE de get_manager(), le même que celui
que la UI elle-même affiche.

    GET  /api/dwarfs
        -> {"devices": [{"name", "dwarfUid", "connected"}, ...]}
        Nom depuis device_registry (devices.json), état "connected" depuis
        la vraie DwarfSession en mémoire.

    POST /api/schedule
        body: {"dwarfUid": "...", "schedule": {...}}
        - Si l'appareil est connecté : envoie tout de suite via
          perform_sync_shooting_schedule() (déplacé sur un thread, voir
          components/connection_health.py::connect_and_enter_astro_mode
          pour le même pattern run.io_bound).
        - Sinon : stocke via pending_schedules.set_pending() ; sera proposé
          à la synchronisation la prochaine fois que CET appareil se
          connectera (voir le hook dans pages/session.py::_handle_connect).
        -> {"ok": true, "mode": "sent"|"pending", ...}

CORS : la page catalogue est une origine différente (fichier local ou autre
port), donc CORSMiddleware est ajouté ici pour que fetch() depuis cette page
fonctionne. Ouvert (allow_origins=["*"]) parce que c'est un usage local,
LAN-only, comme le reste de cette app — resserrez si besoin.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from nicegui import app, run

from dwarf_python_api.lib.dwarf_config import DwarfConfig
from dwarf_python_api.lib.dwarf_session import get_manager
from dwarf_python_api.lib.dwarf_utils import perform_sync_shooting_schedule

from device_registry import list_device_entries
from components import connection_health
import pending_schedules
import dwarf_python_api.lib.my_logger as log


def _devices_snapshot() -> list[dict]:
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
            "connected": bool(session and session.is_connected),
            "busy": bool(session and connection_health.is_busy(cfg.dwarf_uid)),
            "hasPending": pending_schedules.get_pending(cfg.dwarf_uid) is not None,
        })
    return out


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

        Looks for catalog.html next to astro_dwarf_ui.py (the project
        root) - drop the downloaded catalog file there under that exact
        name for this route to find it.
        """
        catalog_path = Path(__file__).resolve().parent.parent / "catalog.html"
        if not catalog_path.exists():
            return JSONResponse(
                {"error": f"catalog.html not found at {catalog_path} - place the DSO catalog HTML file there."},
                status_code=404,
            )
        return FileResponse(catalog_path, media_type="text/html")

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
            return JSONResponse({"ok": False, "mode": "sent", "error": "perform_sync_shooting_schedule failed"}, status_code=502)

        log.info(f"[{dwarf_uid}] Device offline — storing schedule as pending.")
        pending_schedules.set_pending(dwarf_uid, schedule)
        return JSONResponse({"ok": True, "mode": "pending"})
