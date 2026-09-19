"""Reusable date/time inputs backed by real pickers (ui.date/ui.time
popups) instead of free-typed text (user-reported Sep 2026: plain text
fields for dates/times were error-prone - wrong format, typos). Used by
components/schedule_editor.py (per-target date + start time) and
components/program_editor.py (the optional scheduled end_time and the
program's own scheduled date/time).

ui.date's own value format ('YYYY-MM-DD') and ui.time's ('HH:mm') match
what callers already parse elsewhere in this app (schedule_editor.py's
_build_wire_tasks(), dwarf_session.py's _parse_end_time()), so swapping
a plain ui.input for one of these changes nothing downstream - only the
widget construction differs, every .value read stays a plain string in
the same format as before.

IMPORTANT: the ui.menu() holding the picker is created INSIDE the
`with field:` block, not as a sibling after it (user-reported Sep 2026:
a sibling menu, sitting outside the input's own element tree, could
end up anchored to/opening the WRONG field's picker when a date field
and a time field sit right next to each other, as they do in
schedule_editor.py's row - Quasar's default anchor for q-menu is its
nearest actual PARENT element, not whichever icon called .open()).
Nesting the menu inside `with field:` makes it unambiguously that
field's own popup - this matches NiceGUI's own documented date-picker
recipe exactly, rather than the sibling variant used here originally."""
from __future__ import annotations

from nicegui import ui


def date_picker_input(label: str, value: str) -> ui.input:
    """A ui.input with a calendar-popup 'append' icon, bound to a
    ui.date - typing the field by hand still works too, this only adds
    the picker as a faster alternative."""
    with ui.input(label, value=value) as field:
        with field.add_slot("append"):
            icon = ui.icon("edit_calendar").classes("cursor-pointer")
        with ui.menu() as menu:
            ui.date().bind_value(field)
        icon.on("click", menu.open)
    return field


def time_picker_input(label: str, value: str, *, with_seconds: bool = False) -> ui.input:
    """Same idea as date_picker_input(), for ui.time.

    with_seconds: most callers (schedule_editor.py's per-target start
    time, program_editor.py's optional camera end_time) use plain
    'HH:mm', matching what dwarf_session.py/schedule_editor.py already
    parse. program_editor.py's id_command['time'] (the program's OWN
    scheduled start, checked by scheduler_loop.py) is the one exception
    - it's stored as 'HH:mm:ss' (see pages/programs.py's
    now.strftime('%H:%M:%S')).

    Deliberately does NOT pass with_seconds through to ui.time() itself
    (user-reported Sep 2026: TypeError - the installed NiceGUI/Quasar
    version's ui.time() doesn't accept that kwarg at all). ui.time()
    always works in plain 'HH:mm' here; when with_seconds=True this
    appends ':00' itself on every pick instead, which works the same on
    any NiceGUI version."""
    with ui.input(label, value=value) as field:
        with field.add_slot("append"):
            icon = ui.icon("access_time").classes("cursor-pointer")
        with ui.menu() as menu:
            if with_seconds:
                picker = ui.time(value=value[:5] if value else None)
                picker.on_value_change(lambda e: field.set_value(f"{e.value}:00" if e.value else e.value))
            else:
                ui.time().bind_value(field)
        icon.on("click", menu.open)
    return field