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
from components import rtsp_worker

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


@dataclass
class _PreviewHandles:
    cam_id: int
    url: str
    rtsp_url: str
    stack_field: str
    image: ui.image
    container: ui.column
    not_available_label: ui.label
    rtsp_image: ui.image
    rtsp_container: ui.column
    expansion: ui.expansion
    rtsp_started: bool = False


def _build_preview(cam_config: dict, url: str, rtsp_url: str, show_links: bool) -> _PreviewHandles:
    """One camera's OWN expansion (user-requested Sep 2026: "peut t'on
    mettre chaque flux dans un expansion... voir les deux ou un seul ou
    rien" - each camera used to share a single combined expansion, so
    Tele and Wide could only be shown or hidden together) - collapsed
    by default, its title IS the camera name (no separate "Astro
    stacking stream" sub-header needed anymore).

    Inside: an HTTP snapshot preview (shown by default - see
    build_camera_stream_section()'s docstring for why hiding-by-default
    is the wrong failure mode here) and an embedded live RTSP preview
    (shown only once the poll loop specifically confirms THIS camera IS
    in RTSP mode - see rtsp_worker.py's own module docstring for why
    eagerly starting this is wasteful/risky). Only one of the two is
    ever visible at a time.

    show_links: adds a small RTSP-URL-to-copy row below the preview -
    for opening the raw stream in an external player (VLC/OBS) from the
    control app, not useful to a read-only spectator (pages/
    watch_device.py passes False)."""
    with ui.card().classes("w-full p-0"):
        expansion = ui.expansion(t(cam_config["label_key"]), icon="videocam", value=False).classes("w-full")

        with expansion:
            not_available_label = ui.label(t("camera_stream_http_not_available")).classes(
                "text-xs text-grey-5 italic"
            )
            not_available_label.set_visibility(False)

            # Auto height instead of fixed breakpoint steps (user-reported
            # Sep 2026: "le flux video a la bonne taille en hauteur" - a
            # fixed h-48/h-64/... doesn't match the STREAM's actual aspect
            # ratio, so it either letterboxes or crops depending on screen
            # width, unlike a plain ui.image() of a known picture - e.g.
            # Dwarfium Scope Archive's own library view - where the browser
            # sizes the <img> to its real intrinsic dimensions automatically
            # once w-full h-auto is the only sizing rule). min-h keeps a
            # placeholder box (not zero height) before the first frame has
            # actually loaded, so the panel doesn't collapse to nothing the
            # instant it's expanded.
            _size_classes = "w-full h-auto min-h-32 rounded bg-neutral-900"

            with ui.column().classes("w-full gap-1") as container:
                image = ui.image(url).classes(_size_classes)

            # Embedded live RTSP preview (user-requested Sep 2026) - hidden
            # until confirmed RTSP; its own <img src> points at OUR OWN
            # /video/rtsp_stream/ route (rtsp_worker.py), not the raw rtsp://
            # URL directly, since browsers can't play RTSP natively at all.
            with ui.column().classes("w-full gap-1") as rtsp_container:
                rtsp_image = ui.image("").classes(_size_classes)
            rtsp_container.set_visibility(False)

            if show_links:
                with ui.row().classes("items-center gap-2 w-full mt-1"):
                    ui.input(value=url).props("readonly dense").classes("flex-1")
                    ui.button(
                        icon="content_copy",
                        on_click=lambda u=url: ui.run_javascript(f"navigator.clipboard.writeText('{u}')"),
                    ).props("flat dense round")
                    ui.button(
                        icon="open_in_new",
                        on_click=lambda u=url: ui.navigate.to(u, new_tab=True),
                    ).props("flat dense round")
                with ui.row().classes("items-center gap-2 w-full"):
                    ui.input(value=rtsp_url).props("readonly dense").classes("flex-1")
                    ui.button(
                        icon="content_copy",
                        on_click=lambda u=rtsp_url: ui.run_javascript(f"navigator.clipboard.writeText('{u}')"),
                    ).props("flat dense round")

    return _PreviewHandles(
        cam_id=cam_config["cam_id"],
        url=url,
        rtsp_url=rtsp_url,
        stack_field=cam_config["stack_field"],
        image=image,
        container=container,
        not_available_label=not_available_label,
        rtsp_image=rtsp_image,
        rtsp_container=rtsp_container,
        expansion=expansion,
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
    # Auto height instead of fixed breakpoint steps (user-reported Sep
    # 2026: this thumbnail's own fixed-step sizing had the same problem
    # already fixed on the full camera-stream panel in this same file -
    # a box height decoupled from the stream's real aspect ratio either
    # letterboxes or leaves the box the wrong shape for the image inside
    # it). w-full h-auto lets the browser size the box to the actual
    # image once loaded, exactly like a plain picture would (e.g.
    # Dwarfium Scope Archive's own library view) - min-h is just a
    # placeholder so the card doesn't collapse to nothing before the
    # first frame arrives.
    _size_classes = "w-full h-auto min-h-32"
    with ui.element("div").classes(f"relative {_size_classes}"):
        image = ui.image(url).classes(f"rounded bg-neutral-900 {_size_classes}")
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
    if not ip or "takePhotoStacked"  or "takeWidePhotoStacked" not in new_values:
        return
    if takeWidePhotoStacked:
        url = _stream_urls(ip)["http_stacking_wide"]
    else:
        url = _stream_urls(ip)["http_stacking_tele"]
    image.set_source(f"{url}?t={time.monotonic()}")


def build_camera_stream_section(session, show_links: bool = True) -> None:
    """Call once per page load. Tele and Wide each get their OWN
    ui.expansion (user-requested Sep 2026 - see _build_preview()'s own
    docstring) - collapsed by default, so a viewer can show both, just
    one, or neither.

    show_links=False (pages/watch_device.py): omits the RTSP/HTTP-URL-
    to-copy row below each preview - for opening the raw stream in an
    external player from the control app, not useful to a read-only
    spectator.

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
    only hides once a camera is specifically confirmed to be RTSP. This
    SAME unknown-defaults-to-HTTP rule is what keeps a fresh reconnect
    safe: get_client_status()'s own StreamTypeByCamera cache is reset
    to empty on every new connection (websockets_utils.py), so right
    after reconnecting we genuinely don't know the current mode - and
    defaulting to the cheap, harmless HTTP preview (rather than eagerly
    starting an RTSP worker thread against a guess) is the safe choice.

    EMBEDDED LIVE RTSP (user-requested Sep 2026, via rtsp_worker.py):
    shown instead of the HTTP preview once a camera is specifically
    CONFIRMED RTSP (StreamTypeByCamera == 1). The worker (OpenCV/FFmpeg
    background thread decoding to a re-servable MJPEG stream) only
    starts once BOTH this section is expanded AND that camera is
    confirmed RTSP - not eagerly for a collapsed/never-opened section -
    and stops the moment either condition stops holding (mode flips
    back to JPEG, the section collapses, or the connection drops/resets
    or this page is torn down), so a stale worker never keeps holding
    open a connection to the Dwarf's own RTSP server, which most
    embedded devices only serve to a single client at a time."""
    ip = session.config.dwarf_ip
    if not ip:
        return
    urls = _stream_urls(ip)

    # Each camera gets its OWN expansion now (user-requested Sep 2026:
    # "peut t'on mettre chaque flux dans un expansion... voir les deux
    # ou un seul ou rien" - previously a single combined expansion held
    # both, so Tele and Wide could only be shown/hidden together) - see
    # _build_preview()'s own docstring. preview.expansion.value is the
    # ground truth for whether THAT camera's panel is open (checked per
    # preview in _poll() below, not a single shared flag) - see
    # rtsp_worker.py's own docstring for why an idle, collapsed section
    # shouldn't eagerly hold an RTSP connection open.
    previews = [
        _build_preview(cfg, urls[cfg["url_key"]], urls[cfg["rtsp_key"]], show_links)
        for cfg in _CAMERAS
    ]

    for preview in previews:
        def _on_expansion_change(e, preview=preview) -> None:
            if not e.value and preview.rtsp_started:
                print(f"Stop RTSP: {preview.rtsp_url}")
                rtsp_worker.stop_worker(preview.rtsp_url)
                preview.rtsp_started = False

        preview.expansion.on_value_change(_on_expansion_change)

    # Guards against a race with NiceGUI's own disconnect grace period
    # (user-reported Sep 2026, via added debug prints: navigating to
    # another page correctly fired on_disconnect below - "Stop RTSP"
    # logged for both cameras - but was immediately followed by "Start
    # RTSP" for both again). NiceGUI doesn't destroy a disconnected
    # client (and cancel its ui.timer) the INSTANT on_disconnect fires -
    # there's a grace window first, in case it's a brief reconnect
    # rather than a real navigation-away. _poll() below can still tick
    # once during that window, see the (unchanged) cached RTSP status
    # and preview.rtsp_started now False (just reset by on_disconnect),
    # and restart the very workers on_disconnect just stopped - which
    # then have nothing left to stop them, since on_disconnect only
    # fires once. This flag makes that restart impossible regardless of
    # ordering.
    _torn_down = False

    def _stop_all_rtsp_workers() -> None:
        # Explicit cleanup on client disconnect (user-reported Sep
        # 2026: an RTSP worker kept running server-side, still holding
        # the Dwarf's RTSP connection open, after navigating away from
        # this page - NiceGUI does NOT automatically call stop_worker()
        # on disconnect, only _on_expansion_change/_poll do that, and
        # both require the browser client to still be alive to ever
        # fire at all).
        nonlocal _torn_down
        _torn_down = True
        for preview in previews:
            if preview.rtsp_started:
                print(f"Stop RTSP: {preview.rtsp_url}")
                rtsp_worker.stop_worker(preview.rtsp_url)
                preview.rtsp_started = False

    ui.context.client.on_disconnect(_stop_all_rtsp_workers)

    def _poll() -> None:
        if _torn_down:
            return
        if not session.is_connected:
            # Disconnected: release any RTSP worker still running
            # rather than leaving it spinning against a source that's
            # now unreachable anyway - and so it isn't still holding
            # the Dwarf's own (usually single-client) RTSP server busy
            # once a reconnect attempt starts.
            for preview in previews:
                if preview.rtsp_started:
                    print(f"Stop RTSP: {preview.rtsp_url}")
                    rtsp_worker.stop_worker(preview.rtsp_url)
                    preview.rtsp_started = False
                    preview.rtsp_container.set_visibility(False)
                    preview.container.set_visibility(True)
            return
        result = get_client_status(session)
        full_status = result.get("fullStatus", {})
        new_values = result.get("newValues", {})
        by_camera = full_status.get("StreamTypeByCamera", {})

        for preview in previews:
            if not preview.expansion.value:
                # This camera's panel is collapsed - release its own
                # RTSP worker if it's still holding one, skip the rest
                # (no point refreshing a preview nobody can see).
                if preview.rtsp_started:
                    print(f"Stop RTSP: {preview.rtsp_url}")
                    rtsp_worker.stop_worker(preview.rtsp_url)
                    preview.rtsp_started = False
                continue

            # Confirmed RTSP (1) -> embedded live preview.
            # Confirmed JPEG (2) or genuinely unknown (unset, including
            # right after a reconnect - see the module docstring above)
            # -> HTTP snapshot preview, the safe default that never
            # needs starting a worker thread.
            is_rtsp = by_camera.get(preview.cam_id) == 1
            preview.container.set_visibility(not is_rtsp)
            preview.not_available_label.set_visibility(False)
            preview.rtsp_container.set_visibility(is_rtsp)

            if is_rtsp and not preview.rtsp_started:
                print(f"Start RTSP : {preview.rtsp_url}")
                rtsp_worker.start_worker(preview.rtsp_url)
                # Set once - this is a continuous multipart stream, not
                # a snapshot, so it never needs cache-busting re-fetches
                # like the HTTP preview below does (see rtsp_worker.py's
                # own docstring point 2 for why an earlier version's
                # repeated re-pointing caused visible stuttering).
                preview.rtsp_image.set_source(f"/video/rtsp_stream/{ip}/{preview.cam_id}")
                preview.rtsp_started = True
            elif not is_rtsp and preview.rtsp_started:
                print(f"Stop RTSP: {preview.rtsp_url}")
                rtsp_worker.stop_worker(preview.rtsp_url)
                preview.rtsp_started = False

            if not is_rtsp and preview.stack_field in new_values:
                preview.image.set_source(f"{preview.url}?t={time.monotonic()}")

    ui.timer(_POLL_INTERVAL_S, _poll)