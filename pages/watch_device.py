"""Read-only single-device 'watch' page: /watch/{dwarf_uid}

Companion to pages/session.py, but strictly for spectators on the local
network. Deliberately NOT a variant of session_page() with buttons hidden -
this file imports zero action/control components (no components/
actions_section.py, no perform_set_*/perform_disconnect calls) so there is
no code path here that could ever send a command to the device, regardless
of future edits.

Reused as-is from the control app, both already read-only by construction:
- components.camera_stream.build_camera_stream_section(session): pseudo-live
  HTTP preview + embedded RTSP worker, no capture controls.
- dwarf_python_api.lib.dwarf_session_socket.get_client_status(session): the
  same status cache pages/session.py reads for battery/temperature/storage,
  here also read for the capture counters - takePhotoCount/takeWidePhotoCount
  are "captured so far" under a misleading cache key, NOT the requested
  total (user-reported Sep 2026 - see components/scheduler_runner.py's
  RunState.requested_count_tele/requested_count_wide, read here too, purely
  a local state lookup with no command sent, so it doesn't break this
  page's read-only guarantee).

NOW SHOWN: IR filter, exposure and gain, via perform_read_camera_params_http_v3()
(port 8082, live HTTP - NOT the WebSocket cache) - the same call
dwarf_session.py and components/scheduler_runner.py already use to verify
camera settings after setup (user-reported Sep 2026: this HTTP read
already exists in the codebase for that purpose - the earlier claim here
that IR filter had no read path at all was wrong). Requires the device to
be in astro/DSO mode (mode_id=2) to return camera params at all - falls
back to "—" otherwise, same as when nothing has been captured yet. A GET-
like query (no state-changing side effect), so this doesn't break this
page's read-only guarantee despite being a real HTTP request rather than
a passive cache read.

Each ui.page() call below builds its OWN @ui.refreshable-free view function
instead of a module-level one - see pages/session.py's own docstring for
why a shared refreshable across two open tabs/devices would leak one
device's data into another's page.
"""
from __future__ import annotations

from nicegui import ui

from dwarf_python_api.lib.dwarf_session import get_manager
from dwarf_python_api.lib.dwarf_session_socket import get_client_status
from dwarf_python_api.lib.dwarf_utils import perform_read_camera_params_http_v3

from components.camera_stream import build_camera_stream_section
from components.camera_settings import ir_filter_display_label
from components import scheduler_runner
from components.i18n import t
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme, theme_toggle_button
from dwarf_session import _ir_filter_display_name

_POLL_INTERVAL_S = 2.0


def _metric(
    label: str, value, unit: str = "", *,
    stacked_icon: str | None = None, stacked_value=None,
    value_classes: str | None = None,
) -> None:
    # When a stacked count is shown too (Tele/Wide cards), it's the
    # more important number to glance at - flip the emphasis: shrink
    # the current/total value, enlarge the icon+stacked pair (user-
    # requested Sep 2026). Cards without a stacked_icon (battery,
    # temperature, exposure, gain, filter) keep the original single big
    # value - except filter, which passes its own smaller value_classes
    # (user-reported Sep 2026, mobile screenshot: "Filtre Astro" at the
    # same text-3xl size as a two-digit number wrapped onto two lines
    # and overflowed the card).
    # h-full: stretches every card in a row to match its tallest sibling
    # (user-reported Sep 2026, mode watch screenshot: the Filter card -
    # shorter content, no stacked-icon row - looked visually shorter
    # than Exposure/Gain next to it) - the row's default flex cross-
    # axis alignment (stretch) already sizes each flex-1 COLUMN to the
    # tallest, but the card inside only filled its own content height
    # unless told to fill that column too.
    with ui.card().classes("flex-1 items-center justify-center p-4 w-full h-full"):
        ui.label(label).classes("text-sm text-grey-6")
        if value_classes is None:
            value_classes = "text-lg font-medium" if stacked_icon else "text-3xl font-semibold"
        ui.label(f"{value if value is not None else '\u2014'}{unit}").classes(
            f"{value_classes} text-center"
        )
        if stacked_icon and stacked_value is not None:
            with ui.row().classes("items-center gap-2 mt-1"):
                ui.icon(stacked_icon).classes("text-3xl text-primary")
                ui.label(str(stacked_value)).classes("text-3xl font-semibold")


def build_watch_device_page() -> None:
    @ui.page("/watch/{dwarf_uid}", title="Astro Dwarf Session — Watch")
    def watch_device_page(dwarf_uid: str) -> None:
        add_pwa_head_tags()
        apply_theme()
        manager = get_manager()
        session = manager.get(dwarf_uid)

        with ui.column().classes(
            "w-full max-w-2xl md:max-w-3xl lg:max-w-4xl mx-auto gap-3 p-4"
        ):
            with ui.row().classes("items-center justify-between w-full"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/watch")).props(
                    "flat round"
                )
                theme_toggle_button()

            if session is None:
                ui.label(t("device_not_found")).classes("text-negative")
                return

            ui.label(dwarf_uid).classes("text-xl font-medium")
            ui.label(session.config.dwarf_ip or t("unknown_ip")).classes(
                "text-xs text-grey-6"
            )

            status_row = ui.row().classes("items-center gap-2")
            with status_row:
                connected_icon = ui.icon("circle").classes("text-xs")
                connected_label = ui.label("")

            if session.is_connected:
                # Camera preview + RTSP embed: reused verbatim, no
                # capture controls of any kind inside it. show_links=
                # False (user-requested Sep 2026) - the RTSP-URL-to-copy
                # block below the preview is for opening the stream in
                # an external player from the control app, not useful
                # to a read-only spectator here.
                build_camera_stream_section(session, show_links=False)

            with ui.row().classes("w-full gap-3"):
                battery_metric = ui.column().classes("flex-1")
                temperature_metric = ui.column().classes("flex-1")
            with ui.row().classes("w-full gap-3"):
                tele_count_metric = ui.column().classes("flex-1")
                wide_count_metric = ui.column().classes("flex-1")

            ui.label(t("watch_exposure_gain")).classes("text-sm text-grey-6 mt-2")
            with ui.row().classes("w-full gap-3"):
                exposure_metric = ui.column().classes("flex-1")
                gain_metric = ui.column().classes("flex-1")
                filter_metric = ui.column().classes("flex-1")

            def _refresh() -> None:
                connected_icon.classes(
                    replace="text-xs " + ("text-positive" if session.is_connected else "text-grey-5")
                )
                connected_label.text = t("connected") if session.is_connected else t("disconnected")

                if not session.is_connected:
                    for col in (
                        battery_metric, temperature_metric,
                        tele_count_metric, wide_count_metric,
                        exposure_metric, gain_metric, filter_metric,
                    ):
                        col.clear()
                    return

                status = get_client_status(session)
                full_status = status.get("fullStatus", {})

                for col, label, key, unit in (
                    (battery_metric, t("battery"), "BatteryLevelDwarf", "%"),
                    (temperature_metric, t("temperature"), "TemperatureLevelDwarf", "°C"),
                ):
                    col.clear()
                    with col:
                        _metric(label, full_status.get(key), unit)

                # NOT the requested total - see RunState's own per-camera
                # requested_count_tele/wide docstring (components/
                # scheduler_runner.py): these cache keys are current_count
                # under a misleading name, i.e. "captured so far", not the
                # target - same mix-up fixed on the dashboard card
                # (components/device_card.py).
                tele_current = full_status.get("takePhotoCount")
                tele_stacked = full_status.get("takePhotoStacked")
                wide_current = full_status.get("takeWidePhotoCount")
                wide_stacked = full_status.get("takeWidePhotoStacked")

                run_state = scheduler_runner.get_run_state(dwarf_uid)
                # Two SEPARATE totals now (user-reported Sep 2026: a
                # single shared total wrongly showed "0/20" on Wide when
                # only Tele actually had count=20 configured) - each is
                # "" when that camera wasn't part of the run at all, so
                # the fallback (no "/total") applies independently per
                # card.
                tele_total = (run_state.requested_count_tele if run_state else "") or ""
                wide_total = (run_state.requested_count_wide if run_state else "") or ""

                tele_count_metric.clear()
                with tele_count_metric:
                    _metric(
                        t("camera_tele"),
                        f"{tele_current}/{tele_total}" if tele_total else tele_current,
                        stacked_icon="layers",
                        stacked_value=tele_stacked,
                    )
                wide_count_metric.clear()
                with wide_count_metric:
                    _metric(
                        t("camera_wide"),
                        f"{wide_current}/{wide_total}" if wide_total else wide_current,
                        stacked_icon="layers",
                        stacked_value=wide_stacked,
                    )

                # Live HTTP read (port 8082, NOT the WebSocket cache -
                # user-reported Sep 2026: "elle existe puisque l'on
                # utilise lors d'une capture pour verifier, c'est une
                # requete http") - same call dwarf_session.py and
                # scheduler_runner.py already use to verify exposure/
                # gain/filter after setup. Best-effort: returns False or
                # an unexpected shape if the device isn't currently in
                # astro/DSO mode (mode_id=2) - see that function's own
                # docstring - so every read below falls back to the
                # existing "—" placeholder rather than raising.
                http_params = perform_read_camera_params_http_v3(mode_id=2, session=session)
                tele_cam = (
                    http_params.get("cameras", {}).get(0)
                    if isinstance(http_params, dict)
                    else None
                )

                exposure_name = None
                gain_value = None
                filter_name = None
                if tele_cam:
                    exposure_info = tele_cam.get("exposure")
                    if exposure_info:
                        exposure_name = exposure_info.get("name")
                    gain_info = tele_cam.get("gain")
                    if gain_info:
                        gain_value = gain_info.get("value")
                    if "filterType" in tele_cam:
                        filter_name = ir_filter_display_label(
                            _ir_filter_display_name(
                                session.config.dwarf_model_id, str(tele_cam["filterType"])
                            )
                        )

                exposure_metric.clear()
                with exposure_metric:
                    _metric(t("exposure"), exposure_name)
                gain_metric.clear()
                with gain_metric:
                    _metric(t("gain"), gain_value)
                filter_metric.clear()
                with filter_metric:
                    _metric(t("watch_filter"), filter_name, value_classes="text-lg font-medium")

            _refresh()
            ui.timer(_POLL_INTERVAL_S, _refresh)