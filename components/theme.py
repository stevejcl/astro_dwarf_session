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
    is_dark = app.storage.user.get("ui_mode") == "dark"
    if is_dark:
        dark.enable()
    else:
        dark.disable()
    ui.query(".nicegui-content").style("padding-top: 0.25rem")
    # Three-tier contrast (user-requested Sep 2026: "differencier le
    # fond d'ecran entre les bords externe et l'appli en elle meme") -
    # body (the outer edge, outside the app's own working area) now
    # gets its OWN distinct shade, separate from .nicegui-content (the
    # app's actual content wrapper), which keeps the lighter/tinted
    # background from the previous pass. Cards on top of that stay
    # plain white/Quasar-dark, untouched here. Edge -> app -> card,
    # three visibly different levels instead of the single flat tint
    # applied uniformly to body before this.
    if is_dark:
        edge_bg, app_bg = "#000000", "#121212"
    else:
        edge_bg, app_bg = "#d7dce3", "#eef1f5"
    ui.query("body").style(f"background-color: {edge_bg}")
    ui.query(".nicegui-content").style(f"background-color: {app_bg}")


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