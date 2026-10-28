"""Full-screen live stacking view (user-requested Oct 2026, issue #164):
the Dwarf's last stacked image, refreshed when the next one lands, with
the session's progress and settings over it - instead of the Dwarf's raw
HTTP image alone in a browser tab.

- /live/{dwarf_uid}: from the control app (the card's and the device
  page's open button). Display adjustments: brightness, contrast,
  saturation, black point, gamma - they belong to the Dwarf (kept by the
  app, app.storage.general), never sent to it nor written in a file.
- /watch/{dwarf_uid}/live: the same view for a spectator - the image as
  adjusted from the control app, no adjustment of its own; the info can
  only be hidden. Imports nothing that sends a command.

Zoom and pan are each viewer's own (browser side, not kept). Hiding the
info or the other camera's inset is remembered by the browser.

The image goes through this app (/live/frame/<uid>/<cam>), not straight
from the Dwarf (http://<ip>:8092/mainstream): one request to the Dwarf per
new stacked image whatever the number of viewers, a phone over HTTPS
(no mixed content) or Tailscale (the Dwarf's address unreachable) sees it
too. The Dwarf's endpoint gives a snapshot per request, not a stream (see
camera_stream.py): a new one is asked when its counters change.

Only a DWARF mini stacks with both cameras at once: there the other one
is shown as a small inset, swapped with a click, hidden by a button."""
from __future__ import annotations

import json
import threading
import time

import requests
from nicegui import app, run, ui

import dwarf_python_api.lib.my_logger as log
from dwarf_python_api.get_config_data import config_to_dwarf_id_str
from dwarf_python_api.lib.dwarf_session import get_manager

from components import current_activity, device_task, scheduler_runner
from components.i18n import t
from components.pwa import add_pwa_head_tags

_POLL_S = 2.0
_TIMEOUT_S = 5
_REFETCH_S = 30     # same counters: asked again at most this often (another display source...)
_RETRY_S = 5        # after a failed fetch
_SETTINGS_S = 30    # exposure / gain / filter read from the Dwarf's HTTP API at most this often

_STORE_KEY = "live_view_adjust"
DEFAULTS = {"brightness": 1.0, "contrast": 1.0, "saturation": 1.0, "black": 0.0, "gamma": 1.0}
# (key, min, max, step) - the order of the panel
_SLIDERS = (
    ("brightness", 0.3, 3.0, 0.05),
    ("contrast", 0.5, 3.0, 0.05),
    ("saturation", 0.0, 3.0, 0.05),
    ("black", 0.0, 0.6, 0.01),
    ("gamma", 0.3, 3.0, 0.05),
)

_MINI = "5"


# ---------------------------------------------------------------- adjustments

def adjustments(dwarf_uid: str) -> dict:
    stored = (app.storage.general.get(_STORE_KEY) or {}).get(dwarf_uid) or {}
    return {k: float(stored.get(k, v)) for k, v in DEFAULTS.items()}


def adjust_version(dwarf_uid: str) -> str:
    """Changes when the Dwarf's adjustments change."""
    return json.dumps(adjustments(dwarf_uid), sort_keys=True)


def save_adjustments(dwarf_uid: str, values: dict) -> None:
    store = dict(app.storage.general.get(_STORE_KEY) or {})
    clean = {k: float(values.get(k, v)) for k, v in DEFAULTS.items()}
    if clean == DEFAULTS:
        store.pop(dwarf_uid, None)
    else:
        store[dwarf_uid] = clean
    app.storage.general[_STORE_KEY] = store     # reassigned: saved


def _filter_id(dwarf_uid: str) -> str:
    return "lv-curve-" + "".join(c if c.isalnum() else "-" for c in dwarf_uid)


def add_adjust_support(dwarf_uid: str) -> None:
    """The page's SVG curve filter for this Dwarf and the view's JS
    (lvAdjust, lvSwap...) - added once per page and Dwarf."""
    client = ui.context.client
    added = getattr(client, "_live_view_added", None)
    if added is None:
        added = client._live_view_added = set()
    if not added:
        ui.add_head_html(_JS)
    fid = _filter_id(dwarf_uid)
    if fid in added:
        return
    added.add(fid)
    ui.add_body_html(
        f'<svg width="0" height="0" style="position:absolute"><filter id="{fid}" '
        'color-interpolation-filters="sRGB"><feComponentTransfer>'
        + "".join(f'<feFunc{c} class="lv-lin" type="linear" slope="1" intercept="0"/>' for c in "RGB")
        + '</feComponentTransfer><feComponentTransfer>'
        + "".join(f'<feFunc{c} class="lv-gam" type="gamma" amplitude="1" exponent="1" offset="0"/>' for c in "RGB")
        + "</feComponentTransfer></filter></svg>"
    )


def apply_adjustments(dwarf_uid: str, values: dict | None = None) -> None:
    """The Dwarf's adjustments on this page's images of it (class
    lv-adj-<filter id>)."""
    values = values or adjustments(dwarf_uid)
    ui.run_javascript(f"window.lvAdjust && lvAdjust({json.dumps(_filter_id(dwarf_uid))}, {json.dumps(values)})")


def adjust_class(dwarf_uid: str) -> str:
    return "lv-adj-" + _filter_id(dwarf_uid)


# ---------------------------------------------------------------- frames

_frames: dict[tuple[str, int], dict] = {}
_frames_lock = threading.Lock()


def _client(session):
    return getattr(session, "client_instance", None) if session is not None and session.is_connected else None


def _status(session) -> dict:
    """The cached status fields this view reads - straight from the
    client, not get_client_status(): that one records "what changed
    since the last call", which the device page and the card rely on."""
    client = _client(session)
    if client is None:
        return {}
    keys = ("takePhotoStarted", "takeWidePhotoStarted", "AstroCapture", "takePhotoCount",
            "takePhotoStacked", "takeMosaicCount", "takeMosaicStacked", "takeWidePhotoCount",
            "takeWidePhotoStacked", "BatteryLevelDwarf", "TemperatureLevelDwarf")
    status = {k: getattr(client, k, None) for k in keys}
    status["CurrentTargetName"] = getattr(client, "currentTargetName", "")
    return status


def frame_key(session, cam: int) -> tuple:
    """Changes when the camera has a new image: its counters."""
    s = _status(session)
    if cam == 0:
        return (s.get("takePhotoCount"), s.get("takePhotoStacked"), s.get("takeMosaicStacked"))
    return (s.get("takeWidePhotoCount"), s.get("takeWidePhotoStacked"))


def _complete_jpeg(data: bytes | None) -> bool:
    return bool(data) and data[:2] == b"\xff\xd8" and data.rstrip(b"\0")[-2:] == b"\xff\xd9"


def frame_bytes(dwarf_uid: str, cam: int) -> bytes | None:
    """The camera's last image, asked from the Dwarf only when its counters
    changed (or _REFETCH_S later) - blocking, a few seconds at most. The
    previous image while a new one fails or is incomplete."""
    session = get_manager().get(dwarf_uid)
    ip = session.config.dwarf_ip if session is not None else None
    if not ip or _client(session) is None:
        return None
    key = frame_key(session, cam)
    with _frames_lock:
        entry = _frames.setdefault((dwarf_uid, cam), {"key": None, "data": None, "at": 0.0,
                                                      "lock": threading.Lock()})
    with entry["lock"]:        # one request to the Dwarf for every viewer
        now = time.monotonic()
        fresh = entry["key"] == key and now - entry["at"] < (_REFETCH_S if entry["data"] else _RETRY_S)
        if not fresh:
            url = f"http://{ip}:8092/{'mainstream' if cam == 0 else 'secondstream'}"
            try:
                response = requests.get(url, timeout=_TIMEOUT_S)
                data = response.content if response.ok else None
            except requests.RequestException as e:
                log.debug(f"[{dwarf_uid}] live view: {url}: {e}")
                data = None
            entry["at"] = now
            if _complete_jpeg(data):
                entry["key"], entry["data"] = key, data
            elif entry["data"] is None:
                entry["key"] = key
        return entry["data"]


def register_live_routes() -> None:
    from fastapi.responses import JSONResponse, Response

    @app.get("/live/frame/{dwarf_uid}/{cam}")
    def live_frame(dwarf_uid: str, cam: int):
        data = frame_bytes(dwarf_uid, 1 if cam == 1 else 0)
        if not data:
            return JSONResponse({"error": "no image"}, status_code=404)
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


def frame_url(session, cam: int) -> str:
    """The camera's image for an <img>: a megastack's stack on the Tele
    (nothing to see there meanwhile), else the proxied stacked image -
    the counters in the query, a new URL for a new image."""
    if cam == 0:
        megastack = device_task.megastack_preview_url(session)
        if megastack:
            return megastack
    key = "-".join(str(x) for x in frame_key(session, cam))
    return f"/live/frame/{session.dwarf_uid}/{cam}?k={key}"


def is_mini(session) -> bool:
    return config_to_dwarf_id_str(session.config.dwarf_model_id) == _MINI


def _swap_js(img, url: str) -> None:
    """The <img> to the new image once it's loaded (no blank meanwhile)."""
    ui.run_javascript(f"lvSwap('{img.html_id}', {json.dumps(url)}, {time.time():.0f})")


# ---------------------------------------------------------------- small preview

def build_stacked_preview(session, live_url: str) -> None:
    """The stacked image, small, as adjusted - a click opens the full
    view (live_url). For the watch page: the stacked image, not the live
    stream (user-asked)."""
    uid = session.dwarf_uid
    add_adjust_support(uid)
    shown = {"url": None, "version": None, "at": 0.0}
    with ui.element("div").classes("relative w-full rounded bg-neutral-900 overflow-hidden lv-frame lv-empty cursor-pointer") \
            .style("min-height: 8rem").on("click", lambda: ui.navigate.to(live_url)) as box:
        img = ui.element("img").classes(f"w-full h-auto block {adjust_class(uid)}").props('draggable="false"')
        ui.label(t("live_no_image")).classes("lv-empty-text absolute inset-0 items-center justify-center "
                                             "text-grey-5 text-sm italic")
        ui.icon("fullscreen").classes("absolute top-1 right-1 text-white text-2xl bg-black/40 rounded")

    def refresh() -> None:
        is_tele = scheduler_runner.resolve_active_camera_is_tele(uid, _status(session))
        url = frame_url(session, 0 if is_tele else 1)
        if url != shown["url"] or time.monotonic() - shown["at"] > _REFETCH_S:
            shown["url"], shown["at"] = url, time.monotonic()
            _swap_js(img, url)
        version = adjust_version(uid)
        if version != shown["version"]:
            shown["version"] = version
            apply_adjustments(uid)

    ui.timer(0.3, refresh, once=True)
    ui.timer(_POLL_S, refresh)


# ---------------------------------------------------------------- full view

class _Settings:
    """Exposure / gain / filter: the program's (RunState, echoed live),
    else read from the Dwarf's HTTP API every _SETTINGS_S - not on a
    DWARF II while a program runs (those polls crashed it, see
    pages/watch_device.py)."""

    def __init__(self, session):
        self.session = session
        self.values: tuple = (None, None, None)
        self.read_at = 0.0
        self.reading = False

    async def update(self, is_tele: bool) -> None:
        uid = self.session.dwarf_uid
        state = scheduler_runner.get_run_state(uid)
        if state is not None and state.running and (state.exposure_actual or state.gain_actual):
            self.values = (state.exposure_actual, state.gain_actual, state.ir_filter_actual if is_tele else None)
            return
        if config_to_dwarf_id_str(self.session.config.dwarf_model_id) == "2" and scheduler_runner.is_running(uid):
            return
        if self.reading or time.monotonic() - self.read_at < _SETTINGS_S or _client(self.session) is None:
            return
        from dwarf_python_api.lib.dwarf_utils import perform_read_camera_params_http_v3
        from components.camera_settings import ir_filter_display_label
        from dwarf_session import _ir_filter_display_name

        self.reading = True
        try:
            params = await run.io_bound(perform_read_camera_params_http_v3, mode_id=2, session=self.session)
        finally:
            self.reading = False
            self.read_at = time.monotonic()
        cam = params.get("cameras", {}).get(0 if is_tele else 1) if isinstance(params, dict) else None
        if not cam:
            return
        exposure = (cam.get("exposure") or {}).get("name")
        gain = (cam.get("gain") or {}).get("value")
        flt = None
        if is_tele and "filterType" in cam:
            flt = ir_filter_display_label(_ir_filter_display_name(self.session.config.dwarf_model_id,
                                                                  str(cam["filterType"])))
        self.values = (exposure, gain, flt)


def _progress_line(session, status: dict, is_tele: bool) -> str:
    uid = session.dwarf_uid
    counts = device_task.megastack_counts(session) if device_task.megastack_running(session) else None
    if counts:
        return device_task.megastack_progress_text(counts)
    run_state = scheduler_runner.get_run_state(uid)
    if is_tele:
        current = status.get("takePhotoCount") or status.get("takeMosaicCount") or 0
        stacked = status.get("takePhotoStacked") or status.get("takeMosaicStacked") or 0
        total = run_state.requested_count_tele if run_state else ""
    else:
        current = status.get("takeWidePhotoCount") or 0
        stacked = status.get("takeWidePhotoStacked") or 0
        total = run_state.requested_count_wide if run_state else ""
    if total:
        text = t("live_progress_total", stacked=stacked, current=current, total=total)
    else:
        text = t("live_progress", stacked=stacked, current=current)
    activity = current_activity.current_activity(session, status)
    if run_state and run_state.end_time_display and scheduler_runner.is_running(uid):
        text += " · " + t("card_end_time", time=run_state.end_time_display)
    elif activity and activity["source"] == "schedule" and activity["end"]:
        text += " · " + t("card_end_time", time=current_activity.format_time(session, activity["end"]))
    return text


def _title_line(session, status: dict) -> str:
    from device_registry import device_name

    activity = current_activity.current_activity(session, status)
    bits = [device_name(session)]
    if activity:
        if activity["title"]:
            bits.append(activity["title"])
        if activity["target"] and activity["target"] not in bits:
            bits.append(activity["target"])
    return " · ".join(bits)


def build_live_view(dwarf_uid: str, editable: bool, back_url: str) -> None:
    add_pwa_head_tags()
    ui.query("body").classes("bg-black")
    ui.add_head_html(_CSS)
    session = get_manager().get(dwarf_uid)
    if session is None:
        ui.label(t("device_not_found")).classes("text-negative p-4")
        return
    add_adjust_support(dwarf_uid)
    adj_class = adjust_class(dwarf_uid)
    mini = is_mini(session)
    settings = _Settings(session)
    state = {"main": None, "urls": {}, "at": {}, "version": None, "swapped": False}

    images = {}
    with ui.element("div").classes("lv-root") as root:
        with ui.element("div").classes("lv-stage lv-frame lv-empty") as stage:
            images["main"] = ui.element("img").classes(f"lv-main {adj_class}").props('draggable="false"')
            ui.label(t("live_no_image")).classes("lv-empty-text")
        if mini:
            with ui.element("div").classes("lv-inset lv-frame lv-empty lv-hideable-inset").on("click", lambda: _swap()):
                images["inset"] = ui.element("img").classes(adj_class).props('draggable="false"')

        with ui.element("div").classes("lv-info lv-top lv-hideable"):
            title = ui.label("").classes("lv-title")
            progress = ui.label("").classes("lv-progress")
        with ui.element("div").classes("lv-info lv-bottom lv-hideable"):
            settings_label = ui.label("").classes("lv-settings")

        with ui.element("div").classes("lv-buttons"):
            def _button(icon: str, tip: str, js: str | None = None, handler=None):
                b = ui.button(icon=icon).props("flat round color=white").classes("lv-btn").tooltip(tip)
                if js:
                    b.on("click", js_handler=js)
                if handler:
                    b.on("click", handler)
                return b

            _button("info", t("live_toggle_info"), js=f"() => lvToggle('{root.html_id}', 'info')")
            if mini:
                _button("swap_horiz", t("live_swap"), handler=lambda: _swap())
                _button("picture_in_picture_alt", t("live_toggle_inset"), js=f"() => lvToggle('{root.html_id}', 'inset')")
            if editable:
                _button("tune", t("live_adjust"), handler=lambda: panel.set_visibility(not panel.visible))
            _button("fullscreen", t("live_fullscreen"), js="() => lvFullscreen()")
            _button("close", t("live_close"),
                    js=f"() => {{ if (history.length > 1) history.back(); else location.href = {json.dumps(back_url)}; }}")

        if editable:
            panel = _build_panel(dwarf_uid)
            panel.set_visibility(False)

    ui.run_javascript(f"lvZoomInit('{stage.html_id}'); lvRestore('{root.html_id}');")

    def _swap() -> None:
        state["swapped"] = not state["swapped"]
        state["urls"] = {}
        _refresh_images()

    def _refresh_images() -> None:
        status = _status(session)
        main_tele = scheduler_runner.resolve_active_camera_is_tele(dwarf_uid, status)
        if state["swapped"]:
            main_tele = not main_tele
        state["main"] = main_tele
        targets = {"main": 0 if main_tele else 1}
        if mini:
            targets["inset"] = 1 if main_tele else 0
        now = time.monotonic()
        for which, cam in targets.items():
            url = frame_url(session, cam)
            # The same URL again after _REFETCH_S: an image the Dwarf
            # hadn't ready at the counters' change
            if state["urls"].get(which) != url or now - state["at"].get(which, 0) > _REFETCH_S:
                state["urls"][which], state["at"][which] = url, now
                _swap_js(images[which], url)

    async def _refresh() -> None:
        _refresh_images()
        status = _status(session)
        if _client(session) is None:
            title.set_text(_title_line(session, status))
            progress.set_text(t("disconnected"))
            settings_label.set_text("")
            return
        is_tele = bool(state["main"])
        title.set_text(_title_line(session, status))
        progress.set_text(_progress_line(session, status, is_tele))
        await settings.update(is_tele)
        exposure, gain, flt = settings.values
        bits = [t("camera_tele" if is_tele else "camera_wide")]
        bits += [f"{t(key)} {value}" for key, value in
                 (("exposure", exposure), ("gain", gain), ("watch_filter", flt if is_tele else None))
                 if value not in (None, "")]
        settings_label.set_text(" · ".join(bits))
        version = adjust_version(dwarf_uid)
        if version != state["version"]:     # changed from the control app: the watchers follow
            state["version"] = version
            apply_adjustments(dwarf_uid)

    ui.timer(0.3, _refresh, once=True)
    ui.timer(_POLL_S, _refresh)


def _build_panel(dwarf_uid: str):
    """The adjustments, saved for the Dwarf as they change (its watch
    views follow)."""
    values = adjustments(dwarf_uid)
    sliders = {}

    def changed(key: str, value) -> None:
        values[key] = float(value)
        save_adjustments(dwarf_uid, values)
        apply_adjustments(dwarf_uid, values)

    def reset() -> None:
        values.update(DEFAULTS)
        for key, slider in sliders.items():
            slider.set_value(DEFAULTS[key])
        save_adjustments(dwarf_uid, values)
        apply_adjustments(dwarf_uid, values)

    with ui.card().classes("lv-panel") as panel:
        ui.label(t("live_adjust")).classes("text-sm font-medium")
        for key, low, high, step in _SLIDERS:
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                ui.label(t(f"live_{key}")).classes("text-xs w-24 shrink-0")
                sliders[key] = ui.slider(min=low, max=high, step=step, value=values[key]) \
                    .props("dense label color=red-4").classes("flex-1") \
                    .on("update:model-value", lambda e, k=key: changed(k, e.args), throttle=0.15)
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(t("live_adjust_hint")).classes("text-xs opacity-70 flex-1")
            ui.button(t("live_reset"), icon="restart_alt", on_click=reset).props("flat dense no-caps color=white")
    return panel


def build_live_pages() -> None:
    @ui.page("/live/{dwarf_uid}", title="Astro Dwarf Session — Live")
    def live_page(dwarf_uid: str) -> None:
        build_live_view(dwarf_uid, editable=True, back_url=f"/session/{dwarf_uid}")

    @ui.page("/watch/{dwarf_uid}/live", title="Astro Dwarf Session — Watch")
    def watch_live_page(dwarf_uid: str) -> None:
        build_live_view(dwarf_uid, editable=False, back_url=f"/watch/{dwarf_uid}")


_CSS = """<style>
.lv-root{position:fixed;inset:0;background:#000;overflow:hidden;color:#fff;user-select:none}
.lv-stage{position:absolute;inset:0;overflow:hidden;touch-action:none;cursor:grab}
.lv-main{width:100%;height:100%;object-fit:contain;transform-origin:center center;will-change:transform}
.lv-inset{position:absolute;right:12px;bottom:56px;width:min(28vw,320px);border:1px solid rgba(255,255,255,.4);
  border-radius:6px;overflow:hidden;background:#111;cursor:pointer;z-index:2}
.lv-inset img{width:100%;height:auto;display:block}
.lv-stage .lv-empty-text{position:absolute;inset:0;align-items:center;justify-content:center;color:#888;font-style:italic}
.lv-info{position:absolute;left:0;right:0;padding:10px 16px;pointer-events:none;z-index:1;
  text-shadow:0 1px 3px #000}
.lv-top{top:0;padding-right:300px;background:linear-gradient(rgba(0,0,0,.65),rgba(0,0,0,0))}
.lv-bottom{bottom:0;background:linear-gradient(rgba(0,0,0,0),rgba(0,0,0,.65))}
.lv-title{font-size:clamp(1rem,2.2vw,2rem);font-weight:600}
.lv-progress{font-size:clamp(.95rem,1.8vw,1.6rem)}
.lv-settings{font-size:clamp(.85rem,1.4vw,1.3rem);opacity:.9}
.lv-buttons{position:absolute;top:6px;right:6px;display:flex;gap:2px;z-index:3}
.lv-btn{background:rgba(0,0,0,.35)!important}
.lv-panel{position:absolute;top:56px;right:8px;width:min(92vw,360px);z-index:4;
  background:rgba(20,20,20,.88)!important;color:#fff!important}
.lv-root.lv-no-info .lv-hideable{display:none}
.lv-root.lv-no-inset .lv-hideable-inset{display:none}
@media (max-width:640px){.lv-top{padding-right:16px;padding-top:52px}}
</style>"""

_JS = """<style>
.lv-frame.lv-empty img{visibility:hidden}
.lv-inset.lv-empty{display:none}
.lv-empty-text{display:none}
.lv-frame.lv-empty .lv-empty-text{display:flex}
</style>
<script>
window.lvSwap = function (id, url, stamp) {
  const el = document.getElementById(id);
  if (!el) return;
  const frame = el.closest('.lv-frame');
  const src = url + (url.includes('?') ? '&' : '?') + 'r=' + stamp;
  const im = new Image();
  im.onload = () => { el.src = src; el.dataset.ok = '1'; if (frame) frame.classList.remove('lv-empty'); };
  im.onerror = () => { if (!el.dataset.ok && frame) frame.classList.add('lv-empty'); };
  im.src = src;
};
window.lvAdjust = function (fid, a) {
  const f = document.getElementById(fid);
  if (f) {
    const b = Math.min(a.black, 0.95), slope = 1 / (1 - b);
    f.querySelectorAll('.lv-lin').forEach(n => { n.setAttribute('slope', slope); n.setAttribute('intercept', -b * slope); });
    f.querySelectorAll('.lv-gam').forEach(n => n.setAttribute('exponent', 1 / a.gamma));
  }
  const css = `url(#${fid}) brightness(${a.brightness}) contrast(${a.contrast}) saturate(${a.saturation})`;
  document.querySelectorAll('.lv-adj-' + fid).forEach(n => n.style.filter = css);
};
window.lvToggle = function (rootId, what) {
  const root = document.getElementById(rootId);
  if (!root) return;
  const on = root.classList.toggle('lv-no-' + what);
  try { localStorage.setItem('lv-no-' + what, on ? '1' : ''); } catch (e) {}
};
window.lvRestore = function (rootId) {
  const root = document.getElementById(rootId);
  if (!root) return;
  ['info', 'inset'].forEach(w => {
    try { if (localStorage.getItem('lv-no-' + w)) root.classList.add('lv-no-' + w); } catch (e) {}
  });
};
window.lvFullscreen = function () {
  if (document.fullscreenElement) document.exitFullscreen();
  else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen().catch(() => {});
};
window.lvZoomInit = function (id) {
  const box = document.getElementById(id);
  if (!box || box.dataset.zoom) return;
  box.dataset.zoom = '1';
  const img = box.querySelector('.lv-main');
  let s = 1, x = 0, y = 0, lastTap = 0;
  const ptrs = new Map();
  let pinch = null;
  const apply = () => { img.style.transform = `translate(${x}px, ${y}px) scale(${s})`; };
  const zoomAt = (f, cx, cy) => {
    const r = box.getBoundingClientRect();
    const px = cx - r.left - r.width / 2, py = cy - r.top - r.height / 2;
    const ns = Math.min(20, Math.max(1, s * f));
    const k = ns / s;
    x = px - (px - x) * k; y = py - (py - y) * k; s = ns;
    if (s === 1) { x = 0; y = 0; }
    apply();
  };
  const reset = () => { s = 1; x = 0; y = 0; apply(); };
  box.addEventListener('wheel', e => { e.preventDefault(); zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX, e.clientY); }, { passive: false });
  box.addEventListener('dblclick', reset);
  box.addEventListener('pointerdown', e => {
    box.setPointerCapture(e.pointerId);
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (e.pointerType === 'touch' && ptrs.size === 1) {
      const now = Date.now();
      if (now - lastTap < 300) reset();
      lastTap = now;
    }
    if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      pinch = Math.hypot(a.x - b.x, a.y - b.y);
    }
  });
  box.addEventListener('pointermove', e => {
    const prev = ptrs.get(e.pointerId);
    if (!prev) return;
    const cur = { x: e.clientX, y: e.clientY };
    ptrs.set(e.pointerId, cur);
    if (ptrs.size === 1 && s > 1) { x += cur.x - prev.x; y += cur.y - prev.y; apply(); }
    else if (ptrs.size === 2 && pinch) {
      const [a, b] = [...ptrs.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      zoomAt(d / pinch, (a.x + b.x) / 2, (a.y + b.y) / 2);
      pinch = d;
    }
  });
  const up = e => { ptrs.delete(e.pointerId); if (ptrs.size < 2) pinch = null; };
  box.addEventListener('pointerup', up);
  box.addEventListener('pointercancel', up);
};
</script>"""
