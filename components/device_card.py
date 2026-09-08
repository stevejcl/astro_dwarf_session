"""Card summarizing one DwarfSession's status, used on the dashboard.
Matches the 'dwarf_multi_dashboard_mobile' mockup already validated.

DeviceCardView builds its DOM ONCE. update() only rebuilds the banner
area when its STRUCTURAL kind changes (error / capturing /
connection_lost / disconnected / connected) - values that legitimately
change on their own WITHIN the same kind (battery percentage while
connected, stacked/count while capturing) are pushed via
label.set_text() on an existing element instead.

An earlier version put those changing values directly in the change-
detection key, which caused a full clear()+rebuild of the banner every
time the battery percentage ticked (i.e. most polls) - that's what was
actually causing the reported "cards oscillating" symptom to persist
even after the bigger per-card/per-list rebuilds were eliminated."""
from __future__ import annotations

from typing import Callable

from nicegui import ui

from dwarf_python_api.get_config_data import config_to_dwarf_id_str
from dwarf_python_api.lib.dwarf_session import DwarfSession
from dwarf_python_api.lib.dwarf_session_socket import get_client_status

from components import connection_health, scheduler_loop, scheduler_runner
from components.camera_stream import (
    build_dashboard_thumbnail,
    dashboard_thumbnail_refresh_source,
    dashboard_thumbnail_should_show,
)
from components.i18n import t
from components.status_banner import status_banner


_DEVICE_TYPE_ICONS = {
    # dwarf_type -> (short_label, full_label, image filename in
    # /images). Two label lengths (clarified Sep 2026): the
    # disconnected view has room for the FULL name since it's the only
    # thing shown; the connected/session views pair the name with
    # Battery/Temp/Disk (and, in-session, a small icon too), so a SHORT
    # label keeps that row compact. Derived from dwarf_model_id
    # (config.py's own DWARF_ID, kept fresh by BLE pairing/Force
    # Bluetooth) rather than config.ini's own "device_type" field,
    # which is a static template default ("Dwarf II") never actually
    # updated after pairing - user-identified as unused/stale (Sep
    # 2026). Images are AI-generated icons (Gemini, user-provided Sep
    # 2026), not manufacturer product photos - no copyright concern,
    # served locally from astro_dwarf_ui/images/ via
    # app.add_static_files("/images", ...) in astro_dwarf_ui.py.
    "2": ("D II", "Dwarf II", "dwarf2.png"),
    "3": ("D 3", "Dwarf 3", "dwarf3.png"),
    "5": ("Mini", "Dwarf Mini", "dwarf_mini.png"),
}


def _device_type_info(session: DwarfSession) -> tuple[str, str, str]:
    """Returns (short_label, full_label, image filename in /images) for
    this session's device model - see _DEVICE_TYPE_ICONS's own
    docstring for how it's derived and why there are two label
    lengths."""
    dwarf_type = config_to_dwarf_id_str(session.config.dwarf_model_id) or "2"
    return _DEVICE_TYPE_ICONS.get(dwarf_type, _DEVICE_TYPE_ICONS["2"])


def _device_type_badge(session: DwarfSession) -> None:
    """Small icon + SHORT name - used in the in-session view, where the
    live camera image already takes the large left-hand spot."""
    short_label, _full_label, filename = _device_type_info(session)
    with ui.row().classes("items-center gap-1"):
        ui.image(f"/images/{filename}").style("width: 24px; height: 24px;").classes("rounded")
        ui.label(short_label).classes("text-xs font-medium text-grey-8")


def _connection_color(connected: bool) -> str:
    return "positive" if connected else "negative"


# Responsive size for the large device-type icon (disconnected/
# connected-idle views only - the in-session camera image now has its
# own full-width sizing in camera_stream.py's build_dashboard_
# thumbnail(), since the two no longer share a visual slot after that
# layout was revised). 128px by default, growing at Tailwind's md
# (768px+)/xl (1280px+)/2xl (1536px+) breakpoints up to 224px on very
# large screens (user follow-up, Sep 2026: "un reglage plus grand sur
# grand ecran" - the earlier xl-only cap topped out at 192px). Tailwind
# classes ONLY - no inline width/height style, which would win over
# these by CSS specificity and defeat the whole point.
_LARGE_VISUAL_CLASSES = "rounded w-32 h-32 md:w-40 md:h-40 xl:w-48 xl:h-48 2xl:w-56 2xl:h-56"

# Responsive text/icon size for the Battery/Temperature/Disk readouts
# (user-requested Sep 2026: bigger font on wide screens, while staying
# well within the growing icon's own height above - see
# _LARGE_VISUAL_CLASSES). At 2xl the icon is 224px tall for up to 4
# stacked lines (name + 3 readouts) - even text-lg/text-xl (these
# classes' largest step) comfortably fits multiple times over in that
# space, so there's no risk of the text outgrowing the icon it sits
# beside.
_INFO_TEXT_CLASSES = "text-xs md:text-sm xl:text-base 2xl:text-lg"
_INFO_ICON_CLASSES = "text-sm md:text-base xl:text-lg 2xl:text-xl"


class DeviceCardView:
    """One card per DwarfSession, built once. Call update(session) on
    every poll instead of recreating the card."""

    def __init__(self, session: DwarfSession, on_open: Callable[[str], None]) -> None:
        self.dwarf_uid = session.dwarf_uid
        self._banner_kind: str | None = None
        self._dynamic_label: ui.label | None = None
        self._dynamic_detail: ui.label | None = None
        self._thumbnail: ui.image | None = None

        with ui.card().classes("w-full cursor-pointer").on(
            "click", lambda: on_open(self.dwarf_uid)
        ) as self.card:
            with ui.row().classes("items-center justify-between w-full"):
                with ui.row().classes("items-center gap-2 min-w-0"):
                    ui.icon("satellite_alt").classes("text-2xl text-grey-6 shrink-0")
                    with ui.column().classes("gap-0 min-w-0"):
                        # truncate (user-reported Sep 2026: a long device
                        # name/UID could disrupt the card's layout) -
                        # ellipsis instead of wrapping/overflowing; the
                        # full name is still available in the title
                        # attribute and via the session page this card
                        # opens.
                        ui.label(session.dwarf_uid).classes("font-medium truncate").props(
                            f"title='{session.dwarf_uid}'"
                        )
                        ui.label(session.config.dwarf_ip or t("unknown_ip")).classes(
                            "text-xs text-grey-6 truncate"
                        )
                with ui.row().classes("items-center gap-1"):
                    # Always present (not conditionally created) so
                    # toggling the scheduler for this device never
                    # reflows the card - just a colour/visibility swap
                    # via classes(replace=...), same pattern as
                    # _status_dot below. The tooltip TEXT is set in
                    # update() below too, not here - a static title set
                    # once at creation would always read "Scheduler
                    # actif" regardless of the real state (this is
                    # exactly the bug reported: the icon's colour was
                    # correctly toggling, but its tooltip text was
                    # frozen on the "on" wording forever).
                    self._scheduler_icon = ui.icon("schedule")
                    self._status_dot = ui.icon("circle")
            # "Mission control" row (user-requested Sep 2026: monitor
            # running sessions across devices with a way to jump to the
            # live stacking view) - a PERSISTENT row, ALWAYS visible,
            # showing one of THREE alternate contents (clarified Sep
            # 2026 - two earlier attempts each collapsed some of these
            # together, which turned out confusing). Only visibility
            # toggles here, no sub-row is ever recreated:
            # - Disconnected: LARGE device-type icon (left) + FULL model
            #   name (right), nothing else - no Battery/Temp/Disk, no
            #   value to show without a connection.
            # - Connected, idle (no active session): LARGE device-type
            #   icon (left, same slot/size as disconnected) + SHORT
            #   model name + Battery/Temperature/Disk (right, each with
            #   its own icon).
            # - Connected, session active (capturing/program_running):
            #   the LIVE CAMERA image (left, same slot/size the device
            #   icon otherwise occupies - see build_dashboard_
            #   thumbnail()'s own note on staying in sync) + a SMALL
            #   device-type icon+short name badge, still followed by
            #   Battery/Temperature/Disk (right) - "idem" to the idle
            #   view's right-hand column, just with the icon shrunk down
            #   since the camera has taken over the large left-hand
            #   spot.
            with ui.row().classes("items-center gap-3 w-full") as self._info_row:
                with ui.row().classes(
                    "flex-wrap justify-center sm:justify-start items-center text-center sm:text-left gap-3 w-full"
                ) as self._disconnected_content:
                    self._disconnected_icon = ui.image("").classes(_LARGE_VISUAL_CLASSES).props(
                        "fit=contain"
                    )
                    self._disconnected_name_label = ui.label("").classes(
                        "text-sm font-medium text-grey-7 truncate"
                    )
                with ui.row().classes(
                    "flex-wrap justify-center sm:justify-between items-center gap-3 w-full"
                ) as self._idle_content:
                    self._idle_icon = ui.image("").classes(_LARGE_VISUAL_CLASSES).props(
                        "fit=contain"
                    )
                    # centered when wrapped below the icon on a narrow/
                    # portrait phone (user-requested Sep 2026), right-
                    # aligned next to the icon once there's room for a
                    # single row (sm: 640px+) - justify-between on the
                    # parent row above already pushes this column to the
                    # far right in that wider case, so no ml-auto needed
                    # here anymore.
                    with ui.column().classes(
                        "gap-2 items-center sm:items-end"
                    ) as self._idle_info_column:
                        self._idle_name_label = ui.label("").classes(
                            f"font-medium text-grey-8 {_INFO_TEXT_CLASSES}"
                        )
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("battery_full").classes(f"text-grey-6 {_INFO_ICON_CLASSES}")
                            self._idle_battery_label = ui.label("").classes(
                                f"text-grey-7 {_INFO_TEXT_CLASSES}"
                            )
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("thermostat").classes(f"text-grey-6 {_INFO_ICON_CLASSES}")
                            self._idle_temperature_label = ui.label("").classes(
                                f"text-grey-7 {_INFO_TEXT_CLASSES}"
                            )
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("sd_card").classes(f"text-grey-6 {_INFO_ICON_CLASSES}")
                            self._idle_disk_label = ui.label("").classes(
                                f"text-grey-7 {_INFO_TEXT_CLASSES}"
                            )
                with ui.column().classes("gap-2 w-full") as self._active_content:
                    self._thumbnail, self._thumbnail_open_button = build_dashboard_thumbnail(session)
                    # Small icon + Battery/Temperature/Disk, all in a
                    # single horizontal LINE below the full-width image
                    # (revised Sep 2026 - the user settled on this
                    # instead of a right-hand column squeezed beside a
                    # smaller image) - flex-wrap as a safety net on very
                    # narrow cards, though the full-width image above
                    # already gives this line the whole card width to
                    # work with.
                    with ui.row().classes("items-center gap-3 flex-wrap") as self._info_column:
                        _device_type_badge(session)
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("battery_full").classes(f"text-grey-6 {_INFO_ICON_CLASSES}")
                            self._battery_label = ui.label("").classes(
                                f"text-grey-7 {_INFO_TEXT_CLASSES}"
                            )
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("thermostat").classes(f"text-grey-6 {_INFO_ICON_CLASSES}")
                            self._temperature_label = ui.label("").classes(
                                f"text-grey-7 {_INFO_TEXT_CLASSES}"
                            )
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("sd_card").classes(f"text-grey-6 {_INFO_ICON_CLASSES}")
                            self._disk_label = ui.label("").classes(
                                f"text-grey-7 {_INFO_TEXT_CLASSES}"
                            )
            # Only this small container is ever cleared/rebuilt, and
            # only when the banner's structural kind changes.
            self._banner_slot = ui.column().classes("w-full gap-0")

        self.update(session)

    def update(self, session: DwarfSession) -> None:
        full_status: dict = {}
        new_values: dict = {}
        if session.is_connected:
            result = get_client_status(session)
            full_status = result.get("fullStatus", {})
            new_values = result.get("newValues", {})

        error = full_status.get("ErrorConnection")
        capturing = full_status.get("takePhotoStarted") or full_status.get(
            "takeWidePhotoStarted"
        )
        connected = connection_health.is_actually_connected(session)
        connection_lost = session.is_connected and not connected
        program_running = scheduler_runner.is_running(session.dwarf_uid)

        if error:
            kind = "error"
        elif capturing:
            kind = "capturing"
        elif program_running:
            # Covers goto/calibration/camera-setup, BEFORE actual
            # capturing starts - user-reported: those phases had no
            # visible indicator at all before this, only showing up on
            # the Programs page's own step log at the bottom.
            kind = "program_running"
        elif connection_lost:
            kind = "connection_lost"
        elif not session.is_connected:
            kind = "disconnected"
        else:
            kind = "connected"

        # In-place class swap - no element recreation.
        self._status_dot.classes(replace=f"text-xs text-{_connection_color(connected)}")
        armed = scheduler_loop.is_armed(self.dwarf_uid)
        self._scheduler_icon.classes(
            replace=("text-sm text-primary" if armed else "text-sm text-grey-4")
        )
        self._scheduler_icon.props(
            f"title='{t('scheduler_on_tooltip') if armed else t('scheduler_off_tooltip')}'"
        )

        # "Mission control" row: ALWAYS visible - one of THREE alternate
        # contents (see constructor's own note for the full reasoning).
        # No sub-row is ever recreated, only toggled/updated in place.
        active_session = kind in ("capturing", "program_running")
        self._disconnected_content.set_visibility(not session.is_connected)
        self._idle_content.set_visibility(session.is_connected and not active_session)
        self._active_content.set_visibility(session.is_connected and active_session)

        if not session.is_connected:
            _short_label, full_label, filename = _device_type_info(session)
            self._disconnected_icon.set_source(f"/images/{filename}")
            self._disconnected_name_label.set_text(full_label)
        elif not active_session:
            _short_label, full_label, filename = _device_type_info(session)
            self._idle_icon.set_source(f"/images/{filename}")
            self._idle_name_label.set_text(full_label)
            battery = full_status.get("BatteryLevelDwarf")
            self._idle_battery_label.set_text(f"{battery}%" if battery is not None else "")
            temperature = full_status.get("TemperatureLevelDwarf")
            self._idle_temperature_label.set_text(
                f"{temperature}\u00b0C" if temperature is not None else ""
            )
            available = full_status.get("availableSizeDwarf")
            total = full_status.get("totalSizeDwarf")
            self._idle_disk_label.set_text(
                t("dashboard_disk_space", available=available, total=total)
                if available is not None and total is not None
                else ""
            )
        else:
            battery = full_status.get("BatteryLevelDwarf")
            self._battery_label.set_text(f"{battery}%" if battery is not None else "")
            temperature = full_status.get("TemperatureLevelDwarf")
            self._temperature_label.set_text(
                f"{temperature}\u00b0C" if temperature is not None else ""
            )
            available = full_status.get("availableSizeDwarf")
            total = full_status.get("totalSizeDwarf")
            self._disk_label.set_text(
                t("dashboard_disk_space", available=available, total=total)
                if available is not None and total is not None
                else ""
            )

            # active_session is already True here (this branch is only
            # reached in that case) - only camera availability itself
            # gates the thumbnail now.
            show_thumbnail = dashboard_thumbnail_should_show(session)
            if self._thumbnail is not None:
                self._thumbnail.set_visibility(show_thumbnail)
                if show_thumbnail:
                    dashboard_thumbnail_refresh_source(session, self._thumbnail, new_values)
            if self._thumbnail_open_button is not None:
                self._thumbnail_open_button.set_visibility(show_thumbnail)

        if kind != self._banner_kind:
            self._banner_kind = kind
            self._dynamic_label = None
            self._dynamic_detail = None
            self._banner_slot.clear()
            with self._banner_slot:
                if kind == "error":
                    status_banner(t("error_with_detail", error=error), kind="danger")
                elif kind == "capturing":
                    self._dynamic_label = self._build_dynamic_banner(
                        icon="play_arrow", css="bg-blue-50 text-blue-800"
                    )
                elif kind == "program_running":
                    # Dynamic (not a static status_banner()) so the
                    # program name/current step can update in place as
                    # the run progresses, without a full rebuild each
                    # tick - see below.
                    self._dynamic_label, self._dynamic_detail = self._build_dynamic_banner(
                        icon="schedule", css="bg-blue-50 text-blue-800", two_lines=True
                    )
                elif kind == "connection_lost":
                    status_banner(t("connection_lost"), kind="danger")
                elif kind == "disconnected":
                    status_banner(t("disconnected"), kind="warning")
                else:  # connected
                    # Battery/Temp/Disk now live in the persistent info
                    # row above (shown whenever connected, not just
                    # here) - a plain static banner avoids duplicating
                    # battery in two places.
                    status_banner(t("connected"), kind="success")

        # Same kind as last tick: only refresh the bit of text that can
        # legitimately change on its own - no DOM rebuild.
        if kind == "capturing" and self._dynamic_label is not None:
            stacked = full_status.get("takePhotoStacked") or full_status.get(
                "takeWidePhotoStacked", 0
            )
            count = full_status.get("takePhotoCount") or full_status.get(
                "takeWidePhotoCount", 0
            )
            self._dynamic_label.set_text(t("capture_in_progress", stacked=stacked, count=count))
        elif kind == "program_running" and self._dynamic_label is not None:
            run_state = scheduler_runner.get_run_state(self.dwarf_uid)
            name = (run_state.program_name if run_state else "") or t("program_untitled")
            self._dynamic_label.set_text(name)
            if self._dynamic_detail is not None:
                last_step = run_state.steps[-1].label if run_state and run_state.steps else ""
                self._dynamic_detail.set_text(last_step)

    @staticmethod
    def _build_dynamic_banner(
        *, icon: str, css: str, static_message: str | None = None, two_lines: bool = False
    ):
        """Builds a banner whose message (or detail line, if
        static_message is given) is meant to be mutated afterwards via
        the returned label rather than rebuilt. Mirrors status_banner()'s
        markup so both look identical.

        two_lines=True (program_running only): returns a (title_label,
        detail_label) tuple instead of a single label - title is the
        program name, detail is the current step, both independently
        mutable without a rebuild."""
        with ui.row().classes(f"items-center gap-2 rounded-lg px-3 py-2 w-full {css}"):
            ui.icon(icon).classes("text-lg")
            with ui.column().classes("gap-0"):
                if static_message is not None:
                    ui.label(static_message).classes("text-sm font-medium")
                    return ui.label("").classes("text-xs opacity-80")
                if two_lines:
                    title = ui.label("").classes("text-sm font-medium")
                    detail = ui.label("").classes("text-xs opacity-80")
                    return title, detail
                return ui.label("").classes("text-sm font-medium")