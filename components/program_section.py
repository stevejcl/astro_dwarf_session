"""Program ("scheduler") UI section for the session page: upload a JSON
program file, run it via components/scheduler_runner.py, and follow
live step-by-step progress.

SIMPLIFIED VIEW WHILE RUNNING (user-requested, Sep 2026): while a
program is actively executing, the upload widget and "Start" button
aren't relevant (you can't start a second one on this device, and
there's nothing to upload towards) - they're hidden in favour of just
the program's name and the live step trace, restored once the run
finishes. program_name comes from RunState (scheduler_runner.py) rather
than this component's own `loaded_program`, since a run can also be
STARTED elsewhere (pages/programs.py's Scripts/Results relaunch) and
this section still needs to show whose steps it's displaying.

SCOPE NOTE: this does NOT reimplement a program editor - the legacy
astro_dwarf_session_UI.py (Tkinter) already has a "Create Session" tab
for that, producing exactly the JSON shape start_dwarf_session() expects
(session_data["command"], per astro_dwarf_scheduler.py's own call site).
This section is upload-and-run plus live progress tracking - the part
that didn't exist yet."""
from __future__ import annotations

from nicegui import events, ui

from components import scheduler_runner
from components.i18n import t

_STATUS_ICON = {"success": "check_circle", "failed": "cancel"}
_STATUS_COLOR = {"success": "text-green-600", "failed": "text-red-600"}


def build_program_section(session) -> None:
    """Call once per page load, like camera_settings.build_camera_settings -
    NOT inside session_view's auto-refreshing body (same reasoning: an
    upload widget or a mid-scroll progress log shouldn't be torn down
    every ~2s). Manages its own faster-cadence timer internally instead,
    active only while a run is actually in progress."""
    dwarf_uid = session.dwarf_uid
    loaded_program: dict = {}

    with ui.column().classes("w-full gap-2 mt-2"):
        ui.label(t("program_section")).classes("text-sm text-grey-6")

        # --- Idle state: upload + Start (hidden while a run is active) ---
        with ui.column().classes("w-full gap-2") as idle_section:
            program_name_label = ui.label(t("no_program_loaded")).classes(
                "text-xs text-grey-6"
            )

            async def handle_upload(e: events.UploadEventArguments) -> None:
                nonlocal loaded_program
                try:
                    data = await e.file.json()
                except Exception as exc:
                    ui.notify(t("program_invalid_json", error=str(exc)), type="negative")
                    return
                # astro_dwarf_scheduler.py calls start_dwarf_session(program["command"], ...)
                # - session files store the actual program under a "command"
                # key. Also accept a bare program dict directly (no wrapper),
                # for a hand-authored file.
                loaded_program = data.get("command", data)
                program_name_label.set_text(t("program_loaded", name=e.file.name))

            ui.upload(
                label=t("program_upload"),
                auto_upload=True,
                on_upload=handle_upload,
            ).props("accept=.json").classes("w-full")

        # --- Running state: program name (visible only while relevant) ---
        running_name_label = ui.label("").classes("text-sm font-medium")
        running_name_label.set_visibility(False)

        progress_container = ui.column().classes("w-full gap-1 mt-2")

        def render_progress() -> None:
            progress_container.clear()
            state = scheduler_runner.get_run_state(dwarf_uid)

            if state is not None and state.program_name:
                running_name_label.set_text(t("program_name_label", name=state.program_name))
                running_name_label.set_visibility(True)
            else:
                running_name_label.set_visibility(False)

            with progress_container:
                if state is None:
                    return
                for step in state.steps:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon(_STATUS_ICON.get(step.status, "circle")).classes(
                            f"text-base {_STATUS_COLOR.get(step.status, '')}"
                        )
                        ui.label(step.label).classes("text-xs")
                if state.running:
                    with ui.row().classes("items-center gap-2"):
                        ui.spinner(size="1em")
                        ui.label(t("program_running")).classes("text-xs text-grey-6")
                elif state.finished_ok is True:
                    ui.label(t("program_finished_ok")).classes(
                        "text-xs text-green-700 font-medium mt-1"
                    )
                elif state.finished_ok is False:
                    ui.label(t("program_finished_failed", error=state.error or "")).classes(
                        "text-xs text-red-700 font-medium mt-1"
                    )

            # Hide the upload/Start controls while a run is actively
            # executing (user-requested) - nothing to upload towards and
            # you can't start a second one on this device anyway.
            idle_section.set_visibility(not (state is not None and state.running))

            # Restore the idle button layout once nothing is running -
            # but the timer itself is NEVER deactivated (see poll_timer's
            # own comment below for the bug this fixes).
            if state is None or not state.running:
                start_button.set_visibility(True)
                stop_button.set_visibility(False)
                stop_button.enable()

        # ALWAYS active - never gated behind "only while I started a run
        # from THIS widget" (user-reported bug, Sep 2026): a program can
        # also be started EXTERNALLY (pages/programs.py's Scripts/
        # Results relaunch, or scheduler_loop.py's own armed auto-start
        # firing while this page just happens to be open) - if the timer
        # only ever got activated via this widget's own handle_start()
        # and deactivated the moment a run finished, it would never
        # notice a LATER externally-started run at all: the page would
        # keep showing a stale "no program loaded" idle state until the
        # user navigated away and back, forcing a full rebuild (which
        # DOES correctly re-check get_run_state() once, at the bottom of
        # this function - the previous bug was that nothing repeated
        # that check afterward). get_run_state() is a cheap in-memory
        # dict lookup, not a network call - there's no real cost to
        # simply always checking, and render_progress() itself already
        # does nothing when state is None/idle.
        poll_timer = ui.timer(1.0, render_progress)

        with ui.row().classes("w-full gap-2 mt-2"):
            start_button = ui.button(t("program_start"), icon="play_arrow")
            stop_button = ui.button(t("program_stop"), icon="stop").props(
                "flat color=negative"
            )
            stop_button.set_visibility(False)

            def handle_start() -> None:
                if not loaded_program:
                    ui.notify(t("program_none_loaded"), type="warning")
                    return
                try:
                    scheduler_runner.start_run(dwarf_uid, loaded_program, session)
                except RuntimeError as exc:
                    ui.notify(str(exc), type="warning")
                    return
                start_button.set_visibility(False)
                stop_button.set_visibility(True)
                render_progress()

            def handle_stop() -> None:
                scheduler_runner.request_stop(dwarf_uid)
                stop_button.disable()

            start_button.on_click(handle_start)
            stop_button.on_click(handle_stop)

        # If a run from before this page load is still active (or just
        # finished) for this device, reflect that immediately instead of
        # showing a blank "not started" state - the always-on poll_timer
        # above takes over from here regardless.
        existing = scheduler_runner.get_run_state(dwarf_uid)
        if existing is not None:
            start_button.set_visibility(not existing.running)
            stop_button.set_visibility(existing.running)
            idle_section.set_visibility(not existing.running)
            render_progress()