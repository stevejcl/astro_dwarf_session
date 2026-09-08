"""Log viewer - a "log window" for keeping an eye on what's happening
during a long/unattended run (useful especially in native mode, where
there's no visible terminal to watch).

There is ONE shared log file for the whole process (dwarf_python_api's
my_logger.py - log_file is a module-level global, not per-device), but
every line is already tagged with a "[dwarf_uid]" prefix via
register_thread_device_label()/the "%(device)s" format field - so a
single tail view, with a text filter, covers all devices without
needing a real per-device file split (a separate, still-PENDING
feature - see my_logger.py's own exclude_thread_from_shared_log(),
whose per-device FileHandler counterpart was never actually wired up).

Reads the TAIL of the file efficiently (seek from the end, not load the
whole file) - a long overnight test can produce a genuinely large log,
and this page polls every few seconds for the duration of a session."""
from __future__ import annotations

import os

from nicegui import ui

import dwarf_python_api.lib.my_logger as my_logger

from components.i18n import t
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme

_POLL_INTERVAL_S = 3.0
_TAIL_BYTES = 200_000  # ~last few thousand lines, generous but bounded
_MAX_DISPLAYED_LINES = 1000


def _read_tail(path: str, max_bytes: int) -> list[str]:
    try:
        size = os.path.getsize(path)
    except OSError:
        return []
    with open(path, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
            f.readline()  # discard the first (likely partial) line
        else:
            f.seek(0)
        data = f.read()
    text = data.decode("utf-8", errors="replace")
    return text.splitlines()


def build_logs_page() -> None:
    @ui.page("/logs", title="Astro Dwarf Session - Logs")
    def logs_page() -> None:
        add_pwa_head_tags()
        apply_theme()
        with ui.column().classes("w-full max-w-4xl mx-auto gap-3 p-4"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props(
                    "flat round"
                )
                ui.label(t("logs_title")).classes("text-xl")
                ui.button(icon="refresh", on_click=lambda: _refresh()).props(
                    "flat round dense"
                )

            log_path = my_logger.log_file
            if not log_path:
                ui.label(t("logs_disabled")).classes("text-grey-6")
                return
            ui.label(t("logs_path", path=os.path.abspath(log_path))).classes(
                "text-xs text-grey-5"
            )

            with ui.row().classes("items-center gap-2 w-full"):
                filter_input = ui.input(t("logs_filter_placeholder")).classes("flex-1").props("dense clearable")
                autoscroll_cb = ui.checkbox(t("logs_autoscroll"), value=True)

            log_area = ui.column().classes(
                "w-full gap-0 bg-grey-9 text-grey-2 rounded p-2 overflow-auto"
            ).style("height: 60vh; font-family: monospace; font-size: 12px;")

            def _line_color(line: str) -> str:
                if " ERROR " in line or " - ERROR" in line:
                    return "text-red-400"
                if " WARNING " in line:
                    return "text-amber-400"
                if " SUCCESS " in line:
                    return "text-green-400"
                return "text-grey-2"

            def _refresh() -> None:
                lines = _read_tail(log_path, _TAIL_BYTES)
                needle = filter_input.value.strip().lower()
                if needle:
                    lines = [line for line in lines if needle in line.lower()]
                lines = lines[-_MAX_DISPLAYED_LINES:]

                log_area.clear()
                with log_area:
                    if not lines:
                        ui.label(t("logs_empty")).classes("text-grey-5")
                    for line in lines:
                        ui.label(line).classes(f"whitespace-pre-wrap {_line_color(line)}")

                if autoscroll_cb.value:
                    ui.run_javascript(
                        f"getElement({log_area.id}).scrollTop = "
                        f"getElement({log_area.id}).scrollHeight"
                    )

            filter_input.on_value_change(lambda _: _refresh())
            ui.timer(_POLL_INTERVAL_S, _refresh)
            _refresh()
