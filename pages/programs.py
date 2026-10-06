"""Programs page per device: create/edit a program (Editor tab), browse
the ToDo queue sorted by scheduled time with edit/relaunch/delete
(Scripts tab), and review completed/failed runs with edit/relaunch too
(Results tab). Reads/writes the exact directories astro_dwarf_
scheduler.py's check_and_execute_commands() itself scans (see
components/session_dirs.py) - a script created or edited here is picked
up exactly like one from the legacy Tkinter "Create Session" tab.

The Scripts tab also carries the per-device scheduler arm/disarm switch
(components/scheduler_loop.py) - this is the natural place for it, since
it's exactly the queue that switch controls."""
from __future__ import annotations

import os
import uuid
from datetime import datetime

from nicegui import run, ui

from dwarf_python_api.lib.dwarf_session import get_manager

from components import scheduler_loop, scheduler_runner, task_check_cache
from components.i18n import get_language, t
from components.json_files import read_json, write_json_atomic
from components.program_editor import build_program_editor
from components.site_time import site_now
from components.schedule_editor import build_schedule_editor
from components.session_dirs import session_dirs_for
from components.task_check import open_task_check, program_task
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme


def _list_json_files(directory: str) -> list[str]:
    if not os.path.isdir(directory):
        return []
    return [f for f in os.listdir(directory) if f.endswith(".json")]


def _read_json(filepath: str) -> dict | None:
    data, _reason = read_json(filepath)
    return data


def _notify_unreadable(filepath: str) -> None:
    """Why a program file couldn't be read (user-reported Oct 2026: a
    plain "Invalid JSON file" with no detail, also when the file had just
    left ToDo)."""
    _data, reason = read_json(filepath)
    if reason == "missing":
        ui.notify(t("program_file_missing", name=os.path.basename(filepath)), type="warning")
    else:
        ui.notify(t("program_invalid_json", error=f"{os.path.basename(filepath)}: {reason}"), type="negative")


def _parse_datetime(date_str: str | None, time_str: str | None) -> datetime | None:
    if not date_str or not time_str:
        return None
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _parse_full_datetime(value: str | None) -> datetime | None:
    """Same as _parse_datetime() but for a single "YYYY-MM-DD HH:MM:SS"
    string, e.g. id_command's own starting_date/processed_date fields."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def build_programs_page() -> None:
    @ui.page("/session/{dwarf_uid}/programs")
    def programs_page(dwarf_uid: str) -> None:
        add_pwa_head_tags()
        apply_theme()
        ui.page_title(f"Programs - {dwarf_uid}")
        try:
            session = get_manager().get(dwarf_uid)
        except KeyError:
            ui.label(t("unknown_dwarf", dwarf_uid=dwarf_uid)).classes("text-red-800 p-4")
            return

        # Responsive width (user-requested Sep 2026: "une seconde taille
        # un peu plus large pour les ecrans larges" - same reasoning as
        # dashboard.py's own container_width, this control page was
        # ALSO stuck at a fixed 448px regardless of screen size before
        # this).
        with ui.column().classes(
            "w-full max-w-md md:max-w-lg lg:max-w-xl xl:max-w-2xl 2xl:max-w-[900px] mx-auto gap-3 p-4"
        ):
            with ui.row().classes("items-center gap-2"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to(f"/session/{dwarf_uid}"),
                ).props("flat round")
                # Milky Way mosaic planner (user-requested Sep 2026) -
                # a standalone page (components/api_routes.py's
                # /mosaic-planner-{lang}), not tied to this dwarf_uid at
                # all - it has its own device picker - so this is just a
                # convenience jump-off point from wherever a program
                # would be sent to, not a per-device link. No real i18n
                # system in that standalone file yet (user-requested
                # Sep 2026: "deux version _fr _en... suivant la langue
                # on ouvre le bon lien") - two full HTML copies, picked
                # here from the app's OWN current language setting.
                ui.button(
                    icon="grid_view",
                    on_click=lambda: ui.navigate.to(f"/mosaic-planner-{get_language()}", new_tab=True),
                ).props("flat round").tooltip(t("mosaic_planner_link"))
                # Combined "local programs + native on-device schedule"
                # page (components/api_routes.py's /Program-{lang} route,
                # user-requested Sep 2026: "un petit icon de lancement sur
                # la page programme comme le planning Voie Lactée" -
                # same jump-off pattern as the button above, but THIS one
                # DOES carry the current dwarf_uid, since this page (unlike
                # the mosaic planner) already has one device firmly in
                # context - opens straight to it preselected instead of
                # making the person pick it again on the new page.
                ui.button(
                    icon="event_note",
                    on_click=lambda: ui.navigate.to(f"/Program-{get_language()}/{dwarf_uid}", new_tab=True),
                ).props("flat round").tooltip(t("program_page_link"))
            # In native mode (ui.run(native=True)) there is no address
            # bar at all - the URL's dwarf_uid, which is the ONLY thing
            # that determines which device Scripts/Results/relaunch
            # apply to, would otherwise be completely invisible to the
            # user. Shown explicitly here so it's never a guess.
            ui.label(t("programs_title")).classes("text-xl")
            ui.label(session.dwarf_uid).classes("text-sm text-grey-6 -mt-2")

            with ui.tabs().classes("w-full") as tabs:
                editor_tab = ui.tab(t("tab_editor"))
                scripts_tab = ui.tab(t("tab_scripts"))
                results_tab = ui.tab(t("tab_results"))
                schedule_tab = ui.tab(t("tab_schedule"))

            with ui.tab_panels(tabs, value=editor_tab).classes("w-full"):

                # --- Editor -----------------------------------------------
                with ui.tab_panel(editor_tab):
                    # Import (point B): load a program JSON regardless of
                    # which device it was originally created for/by -
                    # unlike Scripts' load_for_edit(), which only ever
                    # lists files already in THIS device's own ToDo
                    # folder. build_program_editor()'s exposure/gain
                    # fields validate the loaded values against the
                    # CURRENT session's device automatically (see
                    # components/program_editor.py) - an exposure that
                    # doesn't exist here, or a gain outside this model's
                    # range, surfaces as a visible warning rather than
                    # silently saving something that would fail at
                    # runtime.
                    async def handle_import(e) -> None:
                        try:
                            data = await e.file.json()
                        except Exception as exc:
                            ui.notify(t("program_invalid_json", error=str(exc)), type="negative")
                            return
                        render_editor(initial=data)
                        ui.notify(t("prog_imported"), type="positive")

                    ui.upload(
                        label=t("prog_import_label"),
                        auto_upload=True,
                        on_upload=handle_import,
                    ).props("accept=.json").classes("w-full")

                    editor_container = ui.column().classes("w-full")

                    def render_editor(initial: dict | None = None) -> None:
                        editor_container.clear()
                        with editor_container:
                            build_program_editor(
                                session,
                                initial_program=initial,
                                on_saved=lambda _path: (
                                    ui.notify(t("prog_saved_notify"), type="positive"),
                                    render_scripts(),
                                ),
                            )

                    render_editor()

                # --- Scripts (ToDo queue) ----------------------------------
                with ui.tab_panel(scripts_tab):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label(t("scheduler_armed_label")).classes("text-sm")
                        ui.switch(
                            value=scheduler_loop.is_armed(dwarf_uid),
                            on_change=lambda e: (
                                scheduler_loop.arm(dwarf_uid)
                                if e.value
                                else scheduler_loop.disarm(dwarf_uid)
                            ),
                        )
                    ui.label(t("scheduler_armed_hint")).classes("text-xs text-grey-6")

                    scripts_container = ui.column().classes("w-full gap-2 mt-2")

                    def load_for_edit(filepath: str) -> None:
                        data = _read_json(filepath)
                        if data is None:
                            _notify_unreadable(filepath)
                            return
                        tabs.set_value(editor_tab)
                        render_editor(initial=data)

                    def relaunch(filepath: str) -> None:
                        data = _read_json(filepath)
                        if data is None:
                            _notify_unreadable(filepath)
                            return
                        try:
                            scheduler_runner.start_run(
                                dwarf_uid, data.get("command", {}), session, source_filepath=filepath
                            )
                        except RuntimeError as exc:
                            ui.notify(str(exc), type="warning")
                            return
                        ui.notify(t("program_running"), type="positive")
                        ui.navigate.to(f"/session/{dwarf_uid}")

                    def delete_script(filepath: str) -> None:
                        try:
                            os.remove(filepath)
                        except OSError:
                            pass
                        render_scripts()

                    def render_scripts() -> None:
                        scripts_container.clear()
                        dirs = session_dirs_for(session)
                        entries = []
                        for filename in _list_json_files(dirs["TODO_DIR"]):
                            filepath = os.path.join(dirs["TODO_DIR"], filename)
                            data = _read_json(filepath) or {}
                            id_command = data.get("command", {}).get("id_command", {})
                            when = _parse_datetime(id_command.get("date"), id_command.get("time"))
                            entries.append((when, filepath, id_command, filename))

                        # Soonest first - undated/unparseable entries
                        # (when is None) sort last via the datetime.max
                        # fallback, rather than crashing on a None compare.
                        entries.sort(key=lambda e: e[0] or datetime.max)

                        with scripts_container:
                            if not entries:
                                ui.label(t("no_scripts")).classes("text-grey-6 text-sm")
                            for when, filepath, id_command, filename in entries:
                                with ui.card().classes("w-full"):
                                    ui.label(
                                        id_command.get("description") or filename
                                    ).classes("text-sm font-medium")
                                    ui.label(
                                        f"{id_command.get('date', '')} {id_command.get('time', '')}"
                                    ).classes("text-xs text-grey-6")
                                    with ui.row().classes("gap-1 mt-1"):
                                        ui.button(
                                            icon="edit",
                                            on_click=lambda p=filepath: load_for_edit(p),
                                        ).props("flat dense round")
                                        ui.button(
                                            icon="play_arrow",
                                            on_click=lambda p=filepath: relaunch(p),
                                        ).props("flat dense round color=primary")
                                        ui.button(
                                            icon="delete",
                                            on_click=lambda p=filepath: delete_script(p),
                                        ).props("flat dense round color=negative")

                    render_scripts()

                # --- Results (Done/Error) ----------------------------------
                with ui.tab_panel(results_tab):
                    results_container = ui.column().classes("w-full gap-2")

                    def load_result_for_edit(filepath: str) -> None:
                        """Loads a finished run's data into the editor for
                        modification - saving produces a NEW ToDo entry
                        (see program_editor.py), the original Done/Error
                        entry is left untouched as history."""
                        data = _read_json(filepath)
                        if data is None:
                            _notify_unreadable(filepath)
                            return
                        tabs.set_value(editor_tab)
                        render_editor(initial=data)

                    def relaunch_result(filepath: str) -> None:
                        """Re-runs a finished (Done or Error) program -
                        the ORIGINAL file stays in Done/Error as history.

                        Writes a FRESH ToDo entry and passes ITS path as
                        source_filepath (user-reported bug fix, Sep
                        2026): omitting source_filepath entirely, as an
                        earlier version of this function did, skips
                        _run_blocking()'s WHOLE file-lifecycle block (see
                        scheduler_runner.py's own "if source_filepath is
                        not None" gate) - so the run actually succeeded
                        on the device but never got written to Done/
                        Error at all (never appeared in Results
                        afterward), AND the previous run's stale
                        id_command fields (process/result/message/
                        starting_date/processed_date) were carried over
                        untouched, since the reset that normally happens
                        at the start of a tracked run lives inside that
                        same gate. A fresh uuid/date/time avoids any
                        confusion with the original file's own identity."""
                        data = _read_json(filepath)
                        if data is None:
                            _notify_unreadable(filepath)
                            return

                        cmd = data.get("command", {})
                        id_command = cmd.setdefault("id_command", {})
                        now = site_now(session.config)
                        id_command["uuid"] = f"{uuid.uuid4()}-00001"
                        id_command["date"] = now.strftime("%Y-%m-%d")
                        id_command["time"] = now.strftime("%H:%M:%S")

                        dirs = session_dirs_for(session)
                        os.makedirs(dirs["TODO_DIR"], exist_ok=True)
                        new_filename = f"{id_command['date']}-{id_command['time'].replace(':', '-')}-relaunch.json"
                        new_filepath = os.path.join(dirs["TODO_DIR"], new_filename)
                        write_json_atomic(new_filepath, {"command": cmd})

                        try:
                            scheduler_runner.start_run(
                                dwarf_uid, cmd, session, source_filepath=new_filepath
                            )
                        except RuntimeError as exc:
                            ui.notify(str(exc), type="warning")
                            return
                        ui.notify(t("program_running"), type="positive")
                        ui.navigate.to(f"/session/{dwarf_uid}")

                    async def force_resume(filepath: str) -> None:
                        """Error/ program whose capture the Dwarf is still
                        running: back to Current/ and resumed (see
                        scheduler_runner.force_resume_from_error())."""
                        ok = await run.io_bound(
                            scheduler_runner.force_resume_from_error, dwarf_uid, session, filepath
                        )
                        ui.notify(
                            t("results_force_resume_done") if ok else t("results_force_resume_failed"),
                            type="positive" if ok else "warning",
                        )
                        render_results()

                    def render_results() -> None:
                        results_container.clear()
                        dirs = session_dirs_for(session)
                        entries = []
                        for kind, dirpath in (
                            ("done", dirs["DONE_DIR"]),
                            ("error", dirs["ERROR_DIR"]),
                        ):
                            for filename in _list_json_files(dirpath):
                                filepath = os.path.join(dirpath, filename)
                                data = _read_json(filepath) or {}
                                program = data.get("command", {})
                                id_command = program.get("id_command", {})
                                when = _parse_full_datetime(
                                    id_command.get("processed_date")
                                ) or _parse_datetime(
                                    id_command.get("date"), id_command.get("time")
                                )
                                entries.append((when, kind, filepath, id_command, program, filename))

                        # Most recent first - undated entries sort last.
                        entries.sort(key=lambda e: e[0] or datetime.min, reverse=True)

                        with results_container:
                            if not entries:
                                ui.label(t("no_results")).classes("text-grey-6 text-sm")
                            for when, kind, filepath, id_command, program, filename in entries:
                                with ui.card().classes("w-full"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon(
                                            "check_circle" if kind == "done" else "cancel"
                                        ).classes(
                                            "text-green-600" if kind == "done" else "text-red-600"
                                        )
                                        ui.label(
                                            id_command.get("description") or filename
                                        ).classes("text-sm font-medium")
                                    if id_command.get("message"):
                                        ui.label(id_command["message"]).classes(
                                            "text-xs text-grey-6"
                                        )
                                    if program.get("setup_camera", {}).get("do_action"):
                                        ui.label(f"{t('prog_camera')}: {t('camera_tele')}").classes(
                                            "text-xs text-grey-6"
                                        )
                                    if program.get("setup_wide_camera", {}).get("do_action"):
                                        ui.label(f"{t('prog_camera')}: {t('camera_wide')}").classes(
                                            "text-xs text-grey-6"
                                        )
                                    if id_command.get("exposure_actual"):
                                        detail = (
                                            f"{t('prog_exposure')}: {id_command.get('exposure_actual')}"
                                            f" \u00b7 {t('prog_gain')}: {id_command.get('gain_actual', '')}"
                                        )
                                        if id_command.get("ir_actual"):
                                            detail += f" \u00b7 IR: {id_command['ir_actual']}"
                                        # user-requested Sep 2026: "nombre
                                        # images et stackees... pour
                                        # affichages card program"
                                        if id_command.get("shots_taken"):
                                            detail += (
                                                f" \u00b7 {id_command.get('shots_stacked', 0)}/"
                                                f"{id_command['shots_taken']} {t('prog_shots_stacked')}"
                                            )
                                        if id_command.get("count_info"):
                                            detail += (
                                                f" \u00b7 {t('prog_count')}: {id_command.get('count_info', 0)}"
                                            )
                                        if id_command.get("mosaic_info"):
                                            detail += (
                                                f" \u00b7 {t('prog_mosaic')}"
                                            )
                                        ui.label(detail).classes("text-xs")
                                    check_task = program_task(program, session.config)
                                    if not id_command.get("shots_taken") and check_task is not None:
                                        # Counts found by an earlier View / Check
                                        shots = task_check_cache.shots_text(
                                            task_check_cache.get(dwarf_uid, check_task), t("prog_shots_stacked")
                                        )
                                        if shots:
                                            ui.label(shots).classes("text-xs")
                                    if id_command.get("starting_date") or id_command.get("processed_date"):
                                        # "Error" date for a failed run
                                        end_label = t("results_failed_at") if kind == "error" else t("results_finished")
                                        ui.label(
                                            f"{t('results_started')}: {id_command.get('starting_date', '\u2013')}"
                                            f"  \u2192  {end_label}: {id_command.get('processed_date', '\u2013')}"
                                        ).classes("text-xs text-grey-5")
                                    with ui.row().classes("gap-1 mt-1"):
                                        ui.button(
                                            icon="edit",
                                            on_click=lambda p=filepath: load_result_for_edit(p),
                                        ).props("flat dense round")
                                        ui.button(
                                            icon="replay",
                                            on_click=lambda p=filepath: relaunch_result(p),
                                        ).props("flat dense round color=primary")
                                        # What the Dwarf saved for this run: "View" (done,
                                        # blue) / "Check" (error, red), see task_check.py
                                        if check_task is not None:
                                            ui.button(
                                                t("task_view") if kind == "done" else t("task_check"),
                                                icon="image" if kind == "done" else "fact_check",
                                                on_click=lambda _, task=check_task: open_task_check(
                                                    session, task, on_result=render_results
                                                ),
                                            ).props(
                                                f"flat dense no-caps size=sm color={'primary' if kind == 'done' else 'negative'}"
                                            )
                                        # The Dwarf is still capturing this
                                        # program's target (error < 15 h)
                                        if kind == "error" and scheduler_runner.can_force_resume(
                                            dwarf_uid, session, program
                                        ):
                                            ui.button(
                                                t("results_force_resume"),
                                                icon="play_circle",
                                                on_click=lambda p=filepath: force_resume(p),
                                            ).props("flat dense no-caps color=positive").tooltip(
                                                t("results_force_resume_hint")
                                            )

                    render_results()

                # --- Native Schedule (on-device, module 13) ----------------
                with ui.tab_panel(schedule_tab):
                    build_schedule_editor(session)

            # Refresh Scripts/Results when switching to them, in case a
            # program finished (or was saved) while the user was looking
            # at another tab. Reads tabs.value directly (bindable
            # property) rather than the change-event's own payload shape,
            # to avoid depending on exactly how NiceGUI shapes that event.
            def _on_tab_change() -> None:
                if tabs.value == scripts_tab:
                    render_scripts()
                elif tabs.value == results_tab:
                    render_results()

            tabs.on_value_change(_on_tab_change)
