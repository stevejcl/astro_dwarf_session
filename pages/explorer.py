"""Session explorer - user-requested Sep 2026: "affichage des vignettes
des sessions astro reelles sur le Dwarf sur une page dediee affichage
classe par date les plus recentes en premier et on affiche la liste et
click sur une vignette affiche en grand dans un dialog... c'est tout".

Deliberately minimal, per that same request - a list of thumbnails,
sorted newest-first, click for a large dialog view. No download, no
Stellar Studio integration (that's cloud-based and still blocked on TLS
decryption - see project notes), no editing.

Data comes from perform_list_astro_sessions_http() (dwarf_python_api) -
POST /album/list/mediaInfos {"mediaType": 6, ...} on port 8082,
confirmed by real network capture (Sep 2026) against a Dwarf Mini.
Thumbnail/full-size images are served by the SAME device on PORT 80 (a
different port from the listing call) - referenced directly as <img
src="http://<ip>/<path>"> URLs so the user's own BROWSER fetches them
straight from the device; this backend never proxies the image bytes
themselves, only the JSON listing call."""
from __future__ import annotations

import asyncio
from datetime import datetime

import requests
from nicegui import run, ui

from dwarf_python_api.lib.dwarf_session import get_manager
from dwarf_python_api.lib.dwarf_utils import perform_list_astro_sessions_http

from components.i18n import t
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme


def _thumbnail_url(dwarf_ip: str, path: str) -> str:
    # thumbnailPath/filePath already start with "/" in the real
    # responses (e.g. "/DWARF_mini/Astronomy/.../stacked_thumbnail.jpg") -
    # confirmed by capture, not assumed.
    return f"http://{dwarf_ip}{path}"


def _shots_info_url(dwarf_ip: str, thumbnail_path: str) -> str:
    # shotsInfo.json sits next to stacked.jpg/stacked_thumbnail.jpg in
    # the SAME session folder (user-confirmed Sep 2026, real FTP
    # listing) - since that folder is already served over plain HTTP
    # (see module docstring), the JSON should be fetchable the exact
    # same way, just swapping the filename for the directory's own.
    session_dir = thumbnail_path.rsplit("/", 1)[0]
    return f"http://{dwarf_ip}{session_dir}/shotsInfo.json"


def _fetch_shots_info(url: str) -> dict | None:
    """Best-effort - shotsInfo.json may not exist for every entry
    (Mosaic/RESTACKED sessions store their own metadata differently -
    see _get_details()'s own comment - and very old sessions might
    predate this file). None on ANY failure (404, timeout, malformed
    JSON) - the caller just omits the stacked-count/duration bit for
    that entry rather than showing an error in a photo gallery."""
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def _format_duration(total_seconds: float) -> str:
    total_seconds = int(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    bits = []
    if hours:
        bits.append(f"{hours}h")
    if hours or minutes:
        bits.append(f"{minutes}min")
    bits.append(f"{seconds}s")
    return " ".join(bits)


def _shots_info_caption(info: dict) -> str:
    stacked = info.get("shotsStacked")
    taken = info.get("shotsTaken")
    try:
        exposure_seconds = float(info.get("exp"))
    except (TypeError, ValueError):
        exposure_seconds = None

    bits = []
    if stacked is not None and taken is not None:
        bits.append(f"{stacked}/{taken} {t('prog_shots_stacked')}")
    if taken is not None and exposure_seconds is not None:
        bits.append(_format_duration(taken * exposure_seconds))
    return " \u00b7 ".join(bits)


def _get_details(entry: dict) -> dict | None:
    for key in ("astroImageDetails", "astroMosaicImageDetails", "astroMultiImageDetails"):
        details = entry.get(key)
        if details:
            return details
    return None


def _target_name(entry: dict) -> str:
    details = _get_details(entry)
    if details and details.get("target"):
        return details["target"]
    return entry.get("fileName", "")


def _format_datetime(unix_ts) -> str:
    if not unix_ts:
        return ""
    try:
        return datetime.fromtimestamp(int(unix_ts)).strftime("%d/%m/%Y %H:%M")
    except (ValueError, OSError, OverflowError):
        return ""


def build_explorer_page() -> None:
    @ui.page("/session/{dwarf_uid}/explorer")
    def explorer_page(dwarf_uid: str) -> None:
        add_pwa_head_tags()
        apply_theme()
        ui.page_title(f"Astro Dwarf Session - {dwarf_uid} - {t('explorer_title')}")

        # get_manager().get() raises KeyError for an unregistered
        # dwarf_uid despite its dict-like name (confirmed by testing a
        # bogus URL directly) - guarded here so a stale/bad link shows
        # the same "not paired" fallback below instead of a 500 error.
        try:
            session = get_manager().get(dwarf_uid)
        except KeyError:
            session = None

        with ui.column().classes(
            "w-full max-w-md md:max-w-lg lg:max-w-xl xl:max-w-2xl 2xl:max-w-[900px] mx-auto gap-3 p-4"
        ):
            with ui.row().classes("items-center justify-between w-full"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to(f"/session/{dwarf_uid}")).props(
                    "flat round"
                )
                ui.label(t("explorer_title")).classes("text-xl")
                ui.element("div").classes("w-8")  # keeps the title centered

            if session is None or not session.config.dwarf_ip:
                ui.label(t("explorer_no_ip")).classes("text-grey-6")
                return

            grid = ui.grid().classes("grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 w-full")
            spinner = ui.spinner(size="lg").classes("mx-auto")
            empty_label = ui.label(t("explorer_empty")).classes("text-grey-6 mx-auto")
            empty_label.set_visibility(False)

            # Large-view dialog - built once, content swapped on each
            # click rather than recreated, matching the rest of the
            # project's own "persistent element, update in place" habit.
            # w-[80vw] (user-requested Sep 2026: "au moins 80% de la
            # fenetre en largeur" - the default dialog card was much
            # narrower). max-w-none overrides Quasar's own default
            # dialog max-width, which otherwise caps this well below
            # 80vw regardless of the card's own explicit width class.
            with ui.dialog() as dialog, ui.card().classes("p-0 w-[80vw] max-w-none"):
                full_image = ui.image("").classes("w-full")
                with ui.column().classes("w-full gap-1 p-3"):
                    with ui.row().classes("w-full justify-between items-center"):
                        dialog_target_label = ui.label("").classes("text-base font-medium")
                        ui.button(icon="close", on_click=dialog.close).props("flat round dense")
                    # Date/Exposure/Gain (user-requested Sep 2026: "Date,
                    # Cible et details de prise de vue") - all read
                    # directly from the SAME listing entry already in
                    # memory (astroImageDetails' own "target"/"params"/
                    # modificationTime) - no extra HTTP call or filename
                    # parsing needed, unlike the user's own initial
                    # guess that this might require reading a separate
                    # JSON file or decoding the folder name.
                    dialog_info_label = ui.label("").classes("text-sm text-grey-6")
                    # Stacked count / total exposure duration (user-
                    # requested Sep 2026: from shotsInfo.json - see
                    # _shots_info_cache below) - its own line, since it
                    # may take a moment to arrive after the dialog
                    # itself opens (network fetch, not already in the
                    # listing entry like everything above).
                    dialog_shots_label = ui.label("").classes("text-sm text-grey-6")

            _shots_info_cache: dict[str, dict | None] = {}

            async def _ensure_shots_info(thumb_path: str) -> dict | None:
                """Fetches shotsInfo.json once per session and caches
                it - shared between the grid captions (fetched eagerly
                in load() below) and the dialog (which reuses that same
                cache, or fetches on demand if the dialog is opened
                before the background fetch for THIS entry finished)."""
                if thumb_path not in _shots_info_cache:
                    url = _shots_info_url(session.config.dwarf_ip, thumb_path)
                    _shots_info_cache[thumb_path] = await run.io_bound(_fetch_shots_info, url)
                return _shots_info_cache[thumb_path]

            async def open_dialog(entry: dict) -> None:
                url = _thumbnail_url(session.config.dwarf_ip, entry["filePath"])
                full_image.set_source(url)
                dialog_target_label.set_text(_target_name(entry))

                details = _get_details(entry) or {}
                params = details.get("params") or {}
                parts = []
                date_str = _format_datetime(entry.get("modificationTime"))
                if date_str:
                    parts.append(date_str)
                if params.get("exp"):
                    parts.append(f"{t('explorer_exposure')}: {params['exp']}s")
                if params.get("gain"):
                    parts.append(f"{t('explorer_gain')}: {params['gain']}")
                if params.get("filter"):
                    parts.append(f"{t('explorer_ir_filter')}: {params['filter']}")
                dialog_info_label.set_text(" \u00b7 ".join(parts))

                dialog_shots_label.set_text("")
                dialog.open()

                thumb_path = entry.get("thumbnailPath")
                if thumb_path:
                    info = await _ensure_shots_info(thumb_path)
                    if info:
                        dialog_shots_label.set_text(_shots_info_caption(info))

            async def load() -> None:
                sessions = await run.io_bound(perform_list_astro_sessions_http, session=session)
                spinner.set_visibility(False)
                if sessions is False or not sessions:
                    empty_label.set_visibility(True)
                    return
                # Newest first (user-requested) - modificationTime is a
                # unix timestamp, confirmed present on every entry in
                # the real capture.
                sessions = sorted(
                    sessions, key=lambda e: e.get("modificationTime", 0), reverse=True
                )
                thumb_paths_to_prefetch: set[str] = set()
                with grid:
                    for entry in sessions:
                        thumb_path = entry.get("thumbnailPath")
                        if not thumb_path:
                            continue
                        with ui.column().classes(
                            "gap-1 cursor-pointer"
                        ).on("click", lambda e=entry: open_dialog(e)):
                            ui.image(_thumbnail_url(session.config.dwarf_ip, thumb_path)).classes(
                                "w-full aspect-square rounded"
                            ).props("fit=cover")
                            # Grid caption kept to ONE line (user-
                            # requested Sep 2026: "pour la grille une
                            # ligne juste la date") - the fuller detail
                            # (target/exposure/gain/filter/stacked
                            # count/duration) lives in the fullscreen
                            # dialog only, opened by clicking the tile -
                            # thumb_paths_to_prefetch just tracks which
                            # sessions to warm _shots_info_cache for
                            # below (so the dialog opens with the data
                            # already there, no extra wait on click).
                            ui.label(_format_datetime(entry.get("modificationTime"))).classes(
                                "text-xs text-center text-grey-6 truncate w-full"
                            )
                            thumb_paths_to_prefetch.add(thumb_path)

                # Fetches shotsInfo.json for every thumbnail above,
                # bounded concurrency - a real capture can list 175+
                # sessions (see perform_list_astro_sessions_http()'s
                # own docstring), so firing that many HTTP requests at
                # the Dwarf's small embedded server all at once risked
                # overwhelming it. Just warms _shots_info_cache here
                # (grid tiles show only the date now - see above), so
                # opening the dialog for any of these sessions finds
                # its shotsInfo.json already fetched instead of waiting
                # on it at that point.
                semaphore = asyncio.Semaphore(6)

                async def _load_one(thumb_path: str) -> None:
                    async with semaphore:
                        await _ensure_shots_info(thumb_path)

                await asyncio.gather(*(_load_one(p) for p in thumb_paths_to_prefetch))

            ui.timer(0.1, load, once=True)