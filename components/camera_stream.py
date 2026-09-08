"""Direct camera stream links (point D of the roadmap).

URL formats:
- HTTP astro STACKING streams: http://<ip>:8092/mainstream (tele) is
  confirmed via DWARFLAB's own published help documentation
  (help.dwarflab.com FAQ & Troubleshooting Guide, "How can I access the
  DWARF 3 & Mini live video stream (RTSP / HTTP)?"). http://<ip>:8092/
  secondstream (wide) is NOT in that doc - it's the user's own real-
  hardware finding, included on that basis rather than official
  confirmation.
- RTSP LIVE VIEW streams (tele + wide): rtsp://<ip>/ch0/stream0 and
  rtsp://<ip>/ch1/stream0 (from the same DWARFLAB doc) - STOP working
  once an astro session starts, and no browser can play RTSP natively
  at all (the doc itself says to use VLC/OBS/etc.) - offered as
  copyable URLs only, no embed attempted.

REAL-HARDWARE FINDING: the HTTP endpoints are NOT a continuous
multipart MJPEG stream - confirmed by the user seeing only a single,
fleeting frame even when hitting the raw URL directly outside this
app. They're closer to a snapshot-per-request endpoint, sometimes not
returning anything at all. This is exactly what the PSEUDO-LIVE section
below is for - without forcing a re-fetch, an <img> tag would just show
one frozen frame (or nothing) forever."""
from __future__ import annotations

import time
from dataclasses import dataclass

from nicegui import ui

from dwarf_python_api.lib.dwarf_session_socket import get_client_status

from components.i18n import t

# Values confirmed via websockets_utils.py's own CMD_NOTIFY_STREAM_TYPE
# handling: 1=RTSP, 2=JPEG, anything else/missing=not reported yet.
_STREAM_TYPE_LABELS = {1: "RTSP", 2: "JPEG"}

# How often to check for a new stacked frame (seconds). Cheap - reads
# get_client_status()'s own cache, no network call of its own.
_POLL_INTERVAL_S = 2.0

# cam_id 0 = tele, 1 = wide (matches ResNotifyStreamType_message.cam_id
# and get_client_status()'s takePhotoStacked/takeWidePhotoStacked pair).
_CAMERAS = (
    {"cam_id": 0, "url_key": "http_stacking_tele", "stack_field": "takePhotoStacked", "label_key": "camera_tele", "rtsp_key": "rtsp_tele"},
    {"cam_id": 1, "url_key": "http_stacking_wide", "stack_field": "takeWidePhotoStacked", "label_key": "camera_wide", "rtsp_key": "rtsp_wide"},
)


def _stream_urls(ip: str) -> dict[str, str]:
    return {
        "http_stacking_tele": f"http://{ip}:8092/mainstream",
        "http_stacking_wide": f"http://{ip}:8092/secondstream",
        "rtsp_tele": f"rtsp://{ip}/ch0/stream0",
        "rtsp_wide": f"rtsp://{ip}/ch1/stream0",
    }


def _stream_type_label(by_camera: dict, cam_id: int) -> str:
    return _STREAM_TYPE_LABELS.get(by_camera.get(cam_id), t("camera_stream_type_unknown"))


@dataclass
class _PreviewHandles:
    cam_id: int
    url: str
    stack_field: str
    image: ui.image
    container: ui.column
    not_available_label: ui.label


def _build_preview(cam_config: dict, url: str) -> _PreviewHandles:
    """One camera's HTTP preview block. Shown by default (see
    build_camera_stream_section()'s docstring for why hiding-by-default
    is the wrong failure mode here) - only hidden once the poll loop
    specifically confirms this camera is in RTSP mode."""
    not_available_label = ui.label(t("camera_stream_http_not_available")).classes(
        "text-xs text-grey-5 italic"
    )
    not_available_label.set_visibility(False)
    with ui.column().classes("w-full gap-1") as container:
        ui.label(t(cam_config["label_key"])).classes("text-xs text-grey-6")
        # Responsive height (user-reported Sep 2026: "le flux http en
        # mode Program à mettre en taille de la fenetre video (pas
        # assez haut)" - this was still a fixed 200px inline style,
        # same issue as the dashboard's own camera image had before
        # being made responsive - w-full already scaled with this
        # page's own now-responsive container (see pages/session.py),
        # but the height stayed capped small regardless, leaving it
        # looking undersized relative to the growing width). Tailwind
        # classes ONLY - no inline height style, which would win by CSS
        # specificity and defeat the responsiveness.
        image = (
            ui.image(url)
            .classes("w-full rounded bg-neutral-900 h-48 md:h-64 xl:h-80 2xl:h-96")
            .props("fit=contain")
        )
        with ui.row().classes("items-center gap-2 w-full"):
            ui.input(value=url).props("readonly dense").classes("flex-1")
            ui.button(
                icon="content_copy",
                on_click=lambda u=url: ui.run_javascript(f"navigator.clipboard.writeText('{u}')"),
            ).props("flat dense round")
            ui.button(
                icon="open_in_new",
                on_click=lambda u=url: ui.navigate.to(u, new_tab=True),
            ).props("flat dense round")

    return _PreviewHandles(
        cam_id=cam_config["cam_id"],
        url=url,
        stack_field=cam_config["stack_field"],
        image=image,
        container=container,
        not_available_label=not_available_label,
    )


def build_dashboard_thumbnail(session) -> tuple[ui.image, ui.button] | tuple[None, None]:
    """Compact-ish, read-only preview for the dashboard's "mission
    control" card (user-requested Sep 2026: monitor running sessions
    across devices with a way to jump to the live stacking view) - the
    tele camera's HTTP image, plus an "open in new tab" button matching
    build_camera_stream_section()'s own one (user-requested follow-up).
    Tele only (not wide) to keep each dashboard card reasonably sized;
    the full session page's camera_stream section already covers wide.

    fit=contain with a RESPONSIVE size (not w-full/fit=cover, which
    stretched/cropped the image to fill the box, and not a single fixed
    pixel size either - user-requested Sep 2026: "responsive, plus
    grand si ecran plus grand", matching the same treatment already
    applied to the idle-state device icon). FULL WIDTH (further
    revised, Sep 2026: the user settled on this taking the whole card
    width, with the small icon/Battery/Temp/Disk info moving to a
    horizontal line BELOW it instead of squeezed beside it - see
    device_card.py's own _active_content) with a responsive HEIGHT cap
    (128px default, up to 224px at xl:) rather than matching the
    idle-icon's square box, which this layout no longer shares. Tailwind
    classes ONLY (no inline width/height style, which would win by CSS
    specificity and defeat the responsiveness).

    Returns (image, open_button) so the caller can wire up its own
    pseudo-live refresh polling (matching build_camera_stream_section()'s
    own mechanism) alongside whatever ELSE that caller's poll loop
    already does each tick - a second independent ui.timer per card
    would be wasteful when the dashboard already polls every device.
    Returns (None, None) if this session has no dwarf_ip yet (not
    paired)."""
    ip = session.config.dwarf_ip
    if not ip:
        return None, None
    url = _stream_urls(ip)["http_stacking_tele"]
    # Full width + responsive height only (revised Sep 2026 - no longer
    # shares device_card.py's square icon size, since this now sits
    # ABOVE a horizontal info line rather than beside a right-hand
    # column - see that file's own _active_content).
    #
    # Height steps significantly increased (user-reported Sep 2026:
    # visible black bars left/right on a wide screen) - the box's width
    # grows a LOT on large screens (up to 1600px, see dashboard.py's own
    # container_width), but a camera image's real aspect ratio is
    # roughly 4:3-16:9 (~1.3-1.8:1), nowhere near as wide as that box
    # was becoming relative to its old, much smaller height cap -
    # fit=contain then centers the actual image with large empty
    # letterboxing on the sides. Taller steps here keep the box closer
    # to the image's own proportions at each breakpoint's typical card
    # width, though the exact fit still depends on the real image's
    # aspect ratio, which isn't known ahead of time.
    _size_classes = "w-full h-48 md:h-64 xl:h-80 2xl:h-96"
    with ui.element("div").classes(f"relative {_size_classes}"):
        image = (
            ui.image(url)
            .classes(f"rounded bg-neutral-900 {_size_classes}")
            .props("fit=contain")
        )
        # click.stop: this sits inside the dashboard card's own
        # click-to-open-session-page handler (device_card.py) - without
        # stopping propagation, opening the external tab would ALSO
        # navigate the card underneath it at the same time.
        open_button = ui.button(icon="open_in_new").props("flat dense round size=sm color=white").classes(
            "absolute top-0.5 right-0.5 bg-black/40 min-w-0 p-1"
        )
        open_button.on("click.stop", lambda: ui.navigate.to(url, new_tab=True))
    return image, open_button


def dashboard_thumbnail_should_show(session) -> bool:
    """Mirrors _update_http_availability()'s own "show unless we KNOW
    it's RTSP" default (see build_camera_stream_section()'s docstring
    for the reasoning - a push-only notification with no "current
    state" GET means an unknown state should default to visible, not
    hidden)."""
    if not session.is_connected:
        return False
    full_status = get_client_status(session).get("fullStatus", {})
    return full_status.get("StreamTypeByCamera", {}).get(0) != 1


def dashboard_thumbnail_refresh_source(session, image: ui.image, new_values: dict) -> None:
    """Call once per dashboard poll tick, per card that has a thumbnail
    (image from build_dashboard_thumbnail()) - forces a re-fetch only
    when a genuinely new stacked frame landed (see module docstring:
    the HTTP endpoint isn't a continuous stream), using the SAME
    cache-busting technique as build_camera_stream_section()."""
    ip = session.config.dwarf_ip
    if not ip or "takePhotoStacked" not in new_values:
        return
    url = _stream_urls(ip)["http_stacking_tele"]
    image.set_source(f"{url}?t={time.monotonic()}")


def build_camera_stream_section(session) -> None:
    """Call once per page load (static links/URLs, nothing here needs
    the ~2s auto-refresh loop) - but the stream-type badges are a
    firmware-pushed cache like camera_settings.py's exposure/gain, so a
    manual reload button re-reads them without rebuilding the whole
    page.

    PSEUDO-LIVE PREVIEW: see module docstring - the HTTP endpoints
    aren't a continuous stream, so without help an <img> tag would just
    show one frozen (or blank) frame forever. Rather than polling on a
    blind fixed timer regardless of whether anything changed, this
    polls get_client_status()'s own change-detection (hasNewValues/
    newValues, dwarf_session_socket.py) every _POLL_INTERVAL_S and only
    forces each camera's <img> to re-fetch (via a cache-busting query
    string) when ITS OWN takePhotoStacked/takeWidePhotoStacked actually
    appears in newValues - a genuinely new stacked frame for THAT
    camera, not the other one. Each IMAGE ELEMENT is created once and
    never destroyed by the manual reload button (which only rebuilds
    the RTSP URL list / stream-type badges) - otherwise every reload
    click would leave behind another orphaned timer.

    USE STATUS TO SHOW/HIDE: each camera's own StreamTypeByCamera
    notification (websockets_utils.py's CMD_NOTIFY_STREAM_TYPE) flips
    between RTSP and JPEG depending on whether it's in plain live view
    or astro/stacking mode - DWARFLAB's own docs confirm RTSP live view
    stops the moment an astro session starts, replaced by the HTTP
    stacking stream (user-confirmed: exposures under ~1s stay RTSP,
    at/above that threshold switches to JPEG).

    IMPORTANT LIMITATION (found via real testing): this is a push-only
    notification - the firmware only sends it when the state actually
    CHANGES, there's no "GET current stream type" command (same
    limitation as temperature/battery/etc. throughout this protocol).
    If the app is restarted WITHOUT the Dwarf itself transitioning
    modes in the meantime, no notification ever arrives and
    StreamTypeByCamera stays empty for that camera - not because
    nothing is available, but because nothing NEW happened to report.
    Defaulting an unknown state to HIDDEN would then hide a perfectly
    working stream indefinitely, so each preview defaults to SHOWN and
    only hides once a camera is specifically confirmed to be RTSP."""
    ip = session.config.dwarf_ip
    if not ip:
        return
    urls = _stream_urls(ip)

    with ui.expansion(t("camera_stream_title"), icon="videocam", value=False).classes("w-full"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label(t("camera_stream_http_label")).classes("text-xs text-grey-6")
            ui.button(
                icon="refresh", on_click=lambda: _reload(session, ip, links_container)
            ).props("flat round dense")
        ui.label(t("camera_stream_http_hint")).classes("text-xs text-grey-5")

        previews = [_build_preview(cfg, urls[cfg["url_key"]]) for cfg in _CAMERAS]

        def _poll() -> None:
            if not session.is_connected:
                return
            result = get_client_status(session)
            full_status = result.get("fullStatus", {})
            new_values = result.get("newValues", {})
            by_camera = full_status.get("StreamTypeByCamera", {})

            for preview in previews:
                # Hide only when we KNOW this camera is RTSP (1) - see
                # the docstring's LIMITATION note for why unknown stays
                # visible rather than hidden.
                available = by_camera.get(preview.cam_id) != 1
                preview.container.set_visibility(available)
                preview.not_available_label.set_visibility(not available)

                if preview.stack_field in new_values:
                    preview.image.set_source(f"{preview.url}?t={time.monotonic()}")

        ui.timer(_POLL_INTERVAL_S, _poll)

        links_container = ui.column().classes("w-full gap-1")
        _render_links(session, ip, links_container)


def _reload(session, ip: str, container: ui.column) -> None:
    container.clear()
    _render_links(session, ip, container)


def _render_links(session, ip: str, container: ui.column) -> None:
    urls = _stream_urls(ip)
    full_status = get_client_status(session).get("fullStatus", {}) if session.is_connected else {}
    by_camera = full_status.get("StreamTypeByCamera", {})

    with container:
        ui.label(t("camera_stream_rtsp_label")).classes("text-xs text-grey-6")
        ui.label(t("camera_stream_rtsp_hint")).classes("text-xs text-grey-5")

        for cfg in _CAMERAS:
            stream_type = _stream_type_label(by_camera, cfg["cam_id"])
            with ui.row().classes("items-center gap-2 w-full"):
                ui.label(t(cfg["label_key"])).classes("text-xs text-grey-6 w-12 shrink-0")
                ui.badge(stream_type).props(
                    "color=positive" if stream_type == "RTSP" else "color=grey"
                )
                url = urls[cfg["rtsp_key"]]
                ui.input(value=url).props("readonly dense").classes("flex-1")
                ui.button(
                    icon="content_copy",
                    on_click=lambda u=url: ui.run_javascript(
                        f"navigator.clipboard.writeText('{u}')"
                    ),
                ).props("flat dense round")