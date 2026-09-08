"""Dark/Light mode toggle - ported from dwarfium-scope-archive's own
components/menu.py pattern (same app.storage.user-persisted preference,
same ui.navigate.reload() to apply it everywhere after toggling), but
without that project's full menu() (transfer badges, help drawer, etc.
that don't apply here) - just the theme piece.

app.storage.user requires storage_secret to be set on ui.run() -
already configured in astro_dwarf_ui.py."""
from __future__ import annotations

from nicegui import app, ui


def apply_theme() -> None:
    """Call once per page, near the top - applies the user's stored
    preference (defaults to light) to THIS page's dark_mode element."""
    dark = ui.dark_mode()
    if app.storage.user.get("ui_mode") == "dark":
        dark.enable()
    else:
        dark.disable()


def theme_toggle_button() -> None:
    """A single icon button that flips the stored preference and
    reloads (matching dwarfium-scope-archive's own dark_mode()/
    light_mode() functions - a full page reload is the simplest way to
    guarantee every element on the page picks up the new theme)."""
    is_dark = app.storage.user.get("ui_mode") == "dark"

    def _toggle() -> None:
        app.storage.user["ui_mode"] = "light" if is_dark else "dark"
        ui.navigate.reload()

    ui.button(icon="dark_mode" if not is_dark else "light_mode", on_click=_toggle).props(
        "flat round dense"
    )
