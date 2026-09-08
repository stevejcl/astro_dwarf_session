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

import json
import os
import uuid
from datetime import datetime

from nicegui import ui

from dwarf_python_api.lib.dwarf_session import get_manager

from components import scheduler_loop, scheduler_runner
from components.i18n import t
from components.program_editor import build_program_editor
from components.session_dirs import session_dirs_for
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme


def _list_json_files(directory: str) -> list[str]:
    if not os.path.isdir(directory):
        return []
    return [f for f in os.listdir(directory) if f.endswith(".json")]


def _read_json(filepath: str) -> dict | None:
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


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
            ui.button(
                icon="arrow_back",
                on_click=lambda: ui.navigate.to(f"/session/{dwarf_uid}"),
            ).props("flat round")
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
                            ui.notify(t("program_invalid_json", error=""), type="negative")
                            return
                        tabs.set_value(editor_tab)
                        render_editor(initial=data)

                    def relaunch(filepath: str) -> None:
                        data = _read_json(filepath)
                        if data is None:
                            ui.notify(t("program_invalid_json", error=""), type="negative")
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
                            ui.notify(t("program_invalid_json", error=""), type="negative")
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
                            ui.notify(t("program_invalid_json", error=""), type="negative")
                            return

                        cmd = data.get("command", {})
                        id_command = cmd.setdefault("id_command", {})
                        now = datetime.now()
                        id_command["uuid"] = f"{uuid.uuid4()}-00001"
                        id_command["date"] = now.strftime("%Y-%m-%d")
                        id_command["time"] = now.strftime("%H:%M:%S")

                        dirs = session_dirs_for(session)
                        os.makedirs(dirs["TODO_DIR"], exist_ok=True)
                        new_filename = f"{id_command['date']}-{id_command['time'].replace(':', '-')}-relaunch.json"
                        new_filepath = os.path.join(dirs["TODO_DIR"], new_filename)
                        with open(new_filepath, "w", encoding="utf-8") as f:
                            json.dump({"command": cmd}, f, indent=4)

                        try:
                            scheduler_runner.start_run(
                                dwarf_uid, cmd, session, source_filepath=new_filepath
                            )
                        except RuntimeError as exc:
                            ui.notify(str(exc), type="warning")
                            return
                        ui.notify(t("program_running"), type="positive")
                        ui.navigate.to(f"/session/{dwarf_uid}")

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
                                id_command = data.get("command", {}).get("id_command", {})
                                when = _parse_full_datetime(
                                    id_command.get("processed_date")
                                ) or _parse_datetime(
                                    id_command.get("date"), id_command.get("time")
                                )
                                entries.append((when, kind, filepath, id_command, filename))

                        # Most recent first - undated entries sort last.
                        entries.sort(key=lambda e: e[0] or datetime.min, reverse=True)

                        with results_container:
                            if not entries:
                                ui.label(t("no_results")).classes("text-grey-6 text-sm")
                            for when, kind, filepath, id_command, filename in entries:
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
                                    if id_command.get("exposure_actual"):
                                        detail = (
                                            f"{t('prog_exposure')}: {id_command.get('exposure_actual')}"
                                            f" \u00b7 {t('prog_gain')}: {id_command.get('gain_actual', '')}"
                                        )
                                        if id_command.get("ir_actual"):
                                            detail += f" \u00b7 IR: {id_command['ir_actual']}"
                                        ui.label(detail).classes("text-xs")
                                    if id_command.get("starting_date") or id_command.get("processed_date"):
                                        ui.label(
                                            f"{t('results_started')}: {id_command.get('starting_date', '\u2013')}"
                                            f"  \u2192  {t('results_finished')}: {id_command.get('processed_date', '\u2013')}"
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

                    render_results()

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
