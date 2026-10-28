"""Target picking + night planning for the program editor (user-requested
Oct 2026):
  - open_catalog_dialog(): pick a target from the DSO catalog shared
    with Dwarfium Scope Archive (components/dso_catalog.py) - a second
    source next to "Get from Stellarium", with no external app needed.
  - build_altitude_panel(): the selected target's altitude over the
    night (plus Sun darkness and Moon), the best slot highlighted, and
    one click to use it as the program's start/end time."""
from __future__ import annotations

from datetime import datetime, timedelta, tzinfo
from typing import Callable, Optional

from nicegui import ui

from components import catalog_add_on, my_targets
from components.dso_catalog import add_on_path, catalog_source, load_catalog, max_dark_altitudes, user_entry_count
from components.i18n import t
import json

from components.sky_altitude import compass_index, compute_night_plan

_TYPE_CATEGORIES = ("galaxies", "nebulae", "clusters", "stars")


def site_location(session) -> tuple[float, float] | None:
    """(latitude, longitude) of this device's configured site, falling
    back to another registered Dwarf's (same rule as pages/settings.py's
    pre-fill - every Dwarf a person owns is usually at the same place)."""
    lat, lon = session.config.latitude, session.config.longitude
    if lat is None or lon is None:
        try:
            from device_registry import find_shared_config_value
            from dwarf_python_api.lib.dwarf_session import get_manager

            uid = session.config.dwarf_uid
            lat = lat if lat is not None else find_shared_config_value(get_manager(), lambda c: c.latitude, exclude_uid=uid)
            lon = lon if lon is not None else find_shared_config_value(get_manager(), lambda c: c.longitude, exclude_uid=uid)
        except Exception:
            return None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def night_of(date_str: str, time_str: str) -> datetime:
    """The evening a program's date/time belongs to: a start before noon
    is the second half of the PREVIOUS evening's night."""
    try:
        day = datetime.strptime((date_str or "").strip(), "%Y-%m-%d")
    except ValueError:
        day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        hour = int((time_str or "").strip().split(":")[0])
    except (ValueError, IndexError):
        hour = 12
    return day - timedelta(days=1) if hour < 12 else day


# A slot whose start has already passed starts this many minutes from now
START_LEAD_MINUTES = 5


def earliest_start(start: datetime, now: datetime) -> datetime:
    """start, or now + START_LEAD_MINUTES (to the next whole minute) when
    start is already past (user-requested Oct 2026: "Use best slot" kept a
    start time already gone). Both naive wall-clock times of the same
    timezone."""
    if start >= now:
        return start
    lead = now + timedelta(minutes=START_LEAD_MINUTES)
    rounded = lead.replace(second=0, microsecond=0)
    return rounded if rounded == lead else rounded + timedelta(minutes=1)


_VIEWS = ("all", "fav", "recent", "mine")


def search_key(text) -> str:
    """A name as the search compares it (user-requested Oct 2026, issue
    #162: "m42" = "M 42" = "Messier 42", "Andromède" = "andromede"): no
    case, accents, spaces or punctuation, "Messier" as "M", no leading
    zeros ("NGC 0224" = "NGC 224")."""
    import re
    import unicodedata
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\bmessier\b", "m", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return re.sub(r"(?<![0-9])0+(?=[0-9])", "", text)


def _entry_search_keys(entry: dict) -> list[str]:
    import re
    names = [entry.get("designation"), entry.get("_userDesignation")]
    names += re.split(r",| - ", str(entry.get("displayName") or ""))
    names += str(entry.get("alternateNames") or "").split(",")
    return [k for k in dict.fromkeys(search_key(n) for n in names if n) if k]


def match_score(query: str, keys: list[str]) -> int | None:
    """0 exact, 1 starts with, 2 contains, 3 every word found - None when
    the query doesn't match."""
    q = search_key(query)
    if not q:
        return 0
    if q in keys:
        return 0
    if any(k.startswith(q) for k in keys):
        return 1
    if any(q in k for k in keys):
        return 2
    # several words ("orion nebula", "great orion"): each found - short
    # ones left out ("messier 42": "m" and "42" are in many names)
    words = [w for w in (search_key(w) for w in str(query).split()) if len(w) >= 3]
    joined = " ".join(keys)
    if len(words) > 1 and all(w in joined for w in words):
        return 3
    return None
# Types offered for "my objects" (dso_catalog.json's names)
_MY_TYPES = ("", "Galaxy", "Emission Nebula", "Reflection Nebula", "Planetary Nebula", "Dark Nebula",
             "Open Cluster", "Globular Cluster", "Variable Star", "Star")


def open_catalog_dialog(
    session,
    on_pick: Callable[[dict], None],
    get_night: Callable[[], datetime],
    *,
    tz: tzinfo | None = None,
    view: str = "all",
) -> None:
    """on_pick(entry): called with the chosen catalog entry (its
    ra_hours/dec_deg already parsed - see dso_catalog.load_catalog()).
    tz: timezone of get_night()'s date (None = this PC's).

    Favourites (a star to tick), recent targets (the programs already run)
    and "my objects" (catalog_add_on.json) first, then the catalog; a
    filter shows one of them only (user-requested Oct 2026, issue #162 -
    components/my_targets.py). "My objects" are added, edited and removed
    here."""
    from dwarf_python_api.lib.dwarf_session import get_manager

    entries = list(load_catalog())
    location = site_location(session)
    night = get_night()

    # Recent targets: their catalog object when it has one, else their own row
    recent_by_index: dict[int, dict] = {}
    try:
        recent = my_targets.recent_targets(get_manager().all())
    except Exception:
        recent = []
    for item in recent:
        same = catalog_add_on.find_duplicate({"designation": item["name"]}, item["ra_hours"], item["dec_deg"], entries)
        if same is not None:
            index = next(i for i, e in enumerate(entries) if e is same)
            recent_by_index.setdefault(index, item)
        else:
            entries.append({"designation": item["name"], "displayName": item["name"], "ra_hours": item["ra_hours"],
                            "dec_deg": item["dec_deg"], "type": "", "_recentOnly": True,
                            "_description": item["description"]})
            recent_by_index[len(entries) - 1] = item
    if not entries:
        ui.notify(t("catalog_not_found"), type="warning")
        return

    altitudes = (
        max_dark_altitudes(entries, location[0], location[1], night, tz=tz) if location else [None] * len(entries)
    )

    def _rank(row) -> tuple:
        group = 0 if row["fav"] else 1 if row["recent"] else 2 if row["addOn"] else 3
        return (group, row["lastSort"], -(row["alt"] if row["alt"] is not None else -99))

    rows = []
    for i, (entry, alt) in enumerate(zip(entries, altitudes)):
        rec = recent_by_index.get(i)
        rows.append({
            "id": i,
            "designation": entry.get("designation", ""),
            "name": entry.get("alternateNames") or (entry.get("_userDesignation") or ""),
            "type": "" if str(entry.get("type") or "").startswith("Other classification") else entry.get("type") or "",
            "category": entry.get("typeCategory") or "",
            "constellation": entry.get("constellation") or "",
            "mag": entry.get("magnitude"),
            "size": entry.get("size") or "",
            "alt": round(alt) if alt is not None else None,
            "addOn": bool(entry.get("_addOn")),
            "recentOnly": bool(entry.get("_recentOnly")),
            "fav": my_targets.is_favorite(entry),
            "recent": rec is not None,
            "last": t("catalog_recent_last", date=rec["last"].strftime("%Y-%m-%d"), count=rec["count"]) if rec else "",
            "lastSort": 0 if rec is None else -rec["last"].timestamp(),   # the last used first
        })
    rows.sort(key=_rank)
    search_keys = {i: _entry_search_keys(entry) for i, entry in enumerate(entries)}

    columns = [
        {"name": "fav", "label": "", "field": "fav", "align": "center"},
        {"name": "designation", "label": t("catalog_col_designation"), "field": "designation", "sortable": True, "align": "left"},
        # wrapped: the long alternate names pushed Max alt. out of sight
        {"name": "name", "label": t("catalog_col_name"), "field": "name", "sortable": True, "align": "left",
         "style": "max-width: 260px; white-space: normal", "headerStyle": "max-width: 260px",
         "classes": "gt-xs", "headerClasses": "gt-xs"},
        # On a phone (user-requested Oct 2026): the name and type under the
        # designation, the other columns hidden
        {"name": "type", "label": t("catalog_col_type"), "field": "type", "sortable": True, "align": "left",
         "classes": "gt-xs", "headerClasses": "gt-xs"},
        {"name": "constellation", "label": t("catalog_col_constellation"), "field": "constellation", "sortable": True,
         "align": "left", "classes": "gt-sm", "headerClasses": "gt-sm"},
        {"name": "mag", "label": t("catalog_col_mag"), "field": "mag", "sortable": True,
         "classes": "gt-xs", "headerClasses": "gt-xs"},
        {"name": "size", "label": t("catalog_col_size"), "field": "size", "classes": "gt-sm", "headerClasses": "gt-sm"},
    ]
    if location:
        columns.append({"name": "alt", "label": t("catalog_col_max_alt"), "field": "alt", "sortable": True})
    columns.append({"name": "actions", "label": "", "field": "addOn"})

    def _reopen(new_view: str) -> None:
        dialog.close()
        open_catalog_dialog(session, on_pick, get_night, tz=tz, view=new_view)

    # On a phone: almost the whole screen (narrow margins)
    ui.add_css("@media (max-width: 599px) { .catalog-dialog.q-dialog__inner--minimized { padding: 4px; }"
               " .catalog-dialog .q-card { max-height: calc(100vh - 8px) !important; padding: 8px; } }")
    with ui.dialog().props('content-class="catalog-dialog"') as dialog, ui.card().classes("w-full max-w-5xl"):
        # The help and the files behind an info button (user-asked Oct 2026:
        # four lines of help took the room of the list)
        with ui.row().classes("w-full items-center no-wrap gap-1"):
            ui.label(t("catalog_title")).classes("text-lg")
            info_button = ui.button(icon="info_outline").props("flat dense round size=sm color=grey-7") \
                .tooltip(t("catalog_help"))
        with ui.column().classes("w-full gap-0") as help_box:
            ui.label(t("catalog_click_hint")).classes("text-xs text-grey-6")
            if location:
                ui.label(t("catalog_alt_hint", date=night.strftime("%Y-%m-%d"))).classes("text-xs text-grey-6")
            source = catalog_source()
            user_count = user_entry_count()
            if source:
                ui.label(t("catalog_source", path=str(source), count=len(load_catalog()) - user_count)) \
                    .classes("text-xs text-grey-6 break-all")
            if user_count:
                ui.label(t("catalog_add_on_source", path=str(add_on_path()), count=user_count)) \
                    .classes("text-xs text-grey-6 break-all")
        help_box.set_visibility(False)
        info_button.on("click", lambda: help_box.set_visibility(not help_box.visible))
        if not location:   # a warning, kept in sight
            ui.label(t("planner_no_location")).classes("text-xs text-amber-700")

        with ui.row().classes("w-full gap-2 items-center"):
            view_toggle = ui.toggle(
                {v: t(f"catalog_view_{v}") for v in _VIEWS},
                value=view if view in _VIEWS else "all",
            ).props("dense no-caps").style("flex-wrap: wrap")
            ui.space()
            ui.button(t("catalog_my_add"), icon="add_location_alt",
                      on_click=lambda: _edit_my_object(None, lambda: _reopen("mine"))).props("flat dense no-caps")

        with ui.row().classes("w-full gap-2 items-end"):
            search = ui.input(t("catalog_search")).props("clearable autofocus debounce=250") \
                .classes("flex-1 min-w-[200px]").tooltip(t("catalog_search_hint"))
            with ui.row().classes("gap-2 no-wrap items-end"):   # side by side on a phone too
                category = ui.select(
                    {"": t("catalog_all_types"), **{c: t(f"catalog_cat_{c}") for c in _TYPE_CATEGORIES}},
                    value="",
                    label=t("catalog_col_type"),
                ).classes("w-40")
                min_alt = ui.number(t("catalog_min_alt"), value=0, min=0, max=90, step=5).classes("w-32")
                min_alt.set_visibility(bool(location))

        table = ui.table(
            columns=columns,
            rows=rows,
            row_key="id",
            pagination={"rowsPerPage": 10},
        ).classes("w-full").props("dense flat")
        empty_label = ui.label("").classes("text-sm text-grey-6")

        table.add_slot(
            "body-cell-fav",
            '<q-td :props="props">'
            '<q-btn flat dense round size="sm" :icon="props.row.fav ? \'star\' : \'star_border\'"'
            ' :color="props.row.fav ? \'amber-8\' : \'grey-6\'"'
            ' @click.stop="() => $parent.$emit(\'toggle_fav\', props.row)">'
            f'<q-tooltip>{t("catalog_fav_toggle")}</q-tooltip></q-btn>'
            '</q-td>',
        )
        table.add_slot(
            "body-cell-designation",
            '<q-td :props="props" style="white-space: normal">{{ props.value }}'
            '<q-icon v-if="props.row.recent" name="history" size="xs" color="primary" class="q-ml-xs">'
            '<q-tooltip>{{ props.row.last }}</q-tooltip></q-icon>'
            '<q-icon v-if="props.row.addOn" name="push_pin" size="xs" color="teal" class="q-ml-xs">'
            f'<q-tooltip>{t("catalog_view_mine")}</q-tooltip></q-icon>'
            '<div class="lt-sm text-xs text-grey-7">{{ [props.row.name, props.row.type].filter(Boolean).join(" · ") }}</div>'
            '</q-td>',
        )
        # "My objects" can be edited and removed again (user-requested Oct
        # 2026: the user chooses whether to keep them); a recent target
        # that isn't in the catalog can be kept
        table.add_slot(
            "body-cell-actions",
            '<q-td :props="props">'
            '<q-btn v-if="props.row.addOn" flat dense round size="sm" icon="edit"'
            ' @click.stop="() => $parent.$emit(\'edit_add_on\', props.row)">'
            f'<q-tooltip>{t("catalog_my_edit")}</q-tooltip></q-btn>'
            '<q-btn v-if="props.row.addOn" flat dense round size="sm" icon="delete_outline" color="negative"'
            ' @click.stop="() => $parent.$emit(\'remove_add_on\', props.row)">'
            f'<q-tooltip>{t("catalog_add_on_remove")}</q-tooltip></q-btn>'
            '<q-btn v-if="props.row.recentOnly"'
            ' flat dense round size="sm" icon="push_pin" color="teal"'
            ' @click.stop="() => $parent.$emit(\'keep_recent\', props.row)">'
            f'<q-tooltip>{t("catalog_keep_recent")}</q-tooltip></q-btn>'
            '</q-td>',
        )

        def _row_of(e) -> dict | None:
            return e.args if isinstance(e.args, dict) else None

        def _on_toggle_fav(e) -> None:
            row = _row_of(e)
            if not row:
                return
            value = not row["fav"]
            my_targets.set_favorite(entries[row["id"]], value)
            for r in rows:
                if r["id"] == row["id"]:
                    r["fav"] = value
            _apply_filters()

        def _on_remove(e) -> None:
            row = _row_of(e)
            if not row:
                return
            designation = entries[row["id"]].get("designation", "")
            if catalog_add_on.remove_entry(designation):
                rows[:] = [r for r in rows if r["id"] != row["id"]]
                _apply_filters()
                ui.notify(t("catalog_add_on_removed", name=designation), type="positive")

        def _on_edit(e) -> None:
            row = _row_of(e)
            if row:
                _edit_my_object(entries[row["id"]], lambda: _reopen(view_toggle.value))

        def _on_keep_recent(e) -> None:
            row = _row_of(e)
            if not row:
                return
            entry = entries[row["id"]]
            added, name = catalog_add_on.add_target(entry["designation"], entry["ra_hours"], entry["dec_deg"], "recent")
            ui.notify(t("my_objects_added" if added else "my_objects_known", name=name),
                      type="positive" if added else "info")
            _reopen("mine")

        table.on("toggle_fav", _on_toggle_fav)
        table.on("remove_add_on", _on_remove)
        table.on("edit_add_on", _on_edit)
        table.on("keep_recent", _on_keep_recent)

        def _apply_filters() -> None:
            wanted = category.value or ""
            floor = float(min_alt.value or 0) if location else 0
            shown = view_toggle.value
            query = search.value or ""
            kept = []
            for r in rows:
                if wanted and r["category"] != wanted:
                    continue
                if floor and (r["alt"] is None or r["alt"] < floor):
                    continue
                if not (shown == "all" or (shown == "fav" and r["fav"]) or (shown == "recent" and r["recent"])
                        or (shown == "mine" and r["addOn"])):
                    continue
                score = match_score(query, search_keys[r["id"]]) if query.strip() else 0
                if score is not None:
                    kept.append((score, r))
            # Best match first (the order above among equals: favourites,
            # recent, mine), the last used first in Recent
            kept.sort(key=lambda p: (p[0], p[1]["lastSort"]) if shown == "recent" else p[0])
            table.rows = [r for _, r in kept]
            table.update()
            if query.strip() and not table.rows:
                empty_label.set_text(t("catalog_search_none", query=query.strip()))
            else:
                empty_label.set_text(t(f"catalog_view_{shown}_empty") if shown != "all" and not table.rows else "")

        category.on_value_change(lambda _: _apply_filters())
        min_alt.on_value_change(lambda _: _apply_filters())
        view_toggle.on_value_change(lambda _: _apply_filters())
        search.on_value_change(lambda _: _apply_filters())

        def _pick_first() -> None:   # Enter: the best match
            if table.rows:
                dialog.close()
                on_pick(entries[table.rows[0]["id"]])

        search.on("keydown.enter", _pick_first)

        def _on_row_click(e) -> None:
            row = e.args[1] if isinstance(e.args, list) and len(e.args) > 1 else None
            if not row:
                return
            dialog.close()
            on_pick(entries[row["id"]])

        table.on("rowClick", _on_row_click)
        with ui.row().classes("w-full justify-end"):
            ui.button(t("close"), on_click=dialog.close).props("flat")
    _apply_filters()
    dialog.open()


def _edit_my_object(entry: dict | None, on_done: Callable[[], None]) -> None:
    """Adds (entry None) or edits one of "my objects": name, RA, Dec
    (decimal or sexagesimal), type, magnitude, notes."""
    from components.coords import parse_dec_degrees, parse_ra_hours

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-md"):
        ui.label(t("catalog_my_edit" if entry else "catalog_my_add")).classes("text-lg")
        name = ui.input(t("prog_target_name"), value=(entry or {}).get("designation", "")).classes("w-full")
        with ui.row().classes("w-full gap-2 no-wrap"):
            ra = ui.input(t("prog_ra"), value=f"{entry['ra_hours']:.6f}" if entry else "",
                          validation={t("prog_ra_invalid"): lambda v: not v or parse_ra_hours(v) is not None}) \
                .classes("flex-1").tooltip(t("prog_ra_hint"))
            dec = ui.input(t("prog_dec"), value=f"{entry['dec_deg']:.6f}" if entry else "",
                           validation={t("prog_dec_invalid"): lambda v: not v or parse_dec_degrees(v) is not None}) \
                .classes("flex-1").tooltip(t("prog_dec_hint"))
        current = (entry or {}).get("type") or ""
        types = {k: k or "—" for k in _MY_TYPES}
        if current and current not in types:
            types[current] = current
        type_select = ui.select(types, value=current if current in types else "", label=t("catalog_col_type")).classes("w-full")
        mag = ui.number(t("catalog_col_mag"), value=(entry or {}).get("magnitude"), step=0.1).classes("w-32")
        notes = ui.input(t("catalog_my_notes"), value=(entry or {}).get("notes") or "").classes("w-full")
        status = ui.label("").classes("text-sm text-red-700")

        def save() -> None:
            ra_h, dec_d = parse_ra_hours(ra.value or ""), parse_dec_degrees(dec.value or "")
            if not (name.value or "").strip() or ra_h is None or dec_d is None:
                status.set_text(t("catalog_my_missing"))
                return
            if entry is None:
                added, known = catalog_add_on.add_target(name.value, ra_h, dec_d, "catalog-dialog",
                                                         type_name=type_select.value or "", magnitude=mag.value,
                                                         notes=notes.value or "")
                if not added:
                    status.set_text(t("my_objects_known", name=known))
                    return
                ui.notify(t("my_objects_added", name=name.value.strip()), type="positive")
            else:
                catalog_add_on.update_entry(entry["designation"], name.value, ra_h, dec_d,
                                            type_name=type_select.value or "", magnitude=mag.value,
                                            notes=notes.value or "")
            dialog.close()
            on_done()

        with ui.row().classes("w-full justify-end"):
            ui.button(t("close"), on_click=dialog.close).props("flat")
            ui.button(t("prog_save"), icon="save", on_click=save).props("color=primary")
    dialog.open()


def _compass_names() -> list[str]:
    """Localized 8-point compass (N, NE, E, SE, S, SW/SO, W/O, NW/NO), in
    sky_altitude.COMPASS_POINTS order."""
    names = [n.strip() for n in t("planner_compass").split(",")]
    return names if len(names) == 8 else ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _fmt(dt: Optional[datetime]) -> str:
    return dt.strftime("%H:%M") if dt else "-"


def build_altitude_panel(
    session,
    *,
    get_target: Callable[[], tuple[float, float] | None],
    get_night: Callable[[], datetime],
    apply_slot: Callable[[datetime, Optional[datetime]], None],
    tz: tzinfo | None = None,
    get_busy: Callable[[], list[tuple[datetime, datetime, str]]] | None = None,
):
    """Altitude chart for the target returned by get_target() ((ra_hours,
    dec_deg) or None). apply_slot(start, end) is called when the user
    picks a slot (end=None for a single click on the curve). Returns
    (panel, refresh) - refresh() is what the editor calls whenever the
    target or date changes. tz: timezone every time on the chart is in
    (None = this PC's). get_busy(): (start, end, name) windows already
    planned that night (the native schedule's other targets) - drawn on
    the chart so the next target can be fitted around them."""
    state: dict = {"plan": None}

    with ui.expansion(t("planner_title"), icon="show_chart").classes("w-full") as panel:
        with ui.row().classes("w-full gap-2 items-end"):
            min_alt_input = ui.number(t("planner_min_alt"), value=30, min=0, max=85, step=5).classes("w-40")
            darkness = ui.select(
                {
                    "astronomical": t("planner_dark_astro"),
                    "nautical": t("planner_dark_nautical"),
                    "civil": t("planner_dark_civil"),
                },
                value="astronomical",
                label=t("planner_darkness"),
            ).classes("w-56")
        message = ui.label("").classes("text-xs text-grey-6")
        chart = ui.echart({
            "animation": False,
            "tooltip": {"trigger": "axis"},
            "legend": {"top": 0},
            "grid": {"left": 40, "right": 32, "top": 30, "bottom": 30},
            "xAxis": {"type": "category", "data": []},
            "yAxis": {"type": "value", "min": -10, "max": 90, "name": "°"},
            "series": [],
        }).classes("w-full h-64")
        summary = ui.label("").classes("text-sm")
        with ui.row().classes("w-full gap-2 items-center"):
            use_best = ui.button(t("planner_use_best"), icon="schedule").props("flat dense")
            ui.label(t("planner_click_hint")).classes("text-xs text-grey-6")

    def _set_empty(text: str) -> None:
        state["plan"] = None
        message.set_text(text)
        chart.set_visibility(False)
        summary.set_text("")
        use_best.disable()

    def refresh() -> None:
        target = get_target()
        location = site_location(session)
        if target is None:
            _set_empty(t("planner_no_target"))
            return
        if location is None:
            _set_empty(t("planner_no_location"))
            return
        night = get_night()
        plan = compute_night_plan(
            target[0],
            target[1],
            location[0],
            location[1],
            night,
            min_altitude=float(min_alt_input.value or 0),
            darkness=darkness.value,
            tz=tz,
        )
        state["plan"] = plan
        if tz is None:
            message.set_text(t("planner_night_of", date=night.strftime("%Y-%m-%d")))
        else:
            message.set_text(t("planner_night_of_tz", date=night.strftime("%Y-%m-%d"), tz=str(tz)))
        chart.set_visibility(True)

        labels = [ts.strftime("%H:%M") for ts in plan.times]
        mark_areas = []
        if plan.dark_start and plan.dark_end:
            mark_areas.append([
                {"name": t("planner_night"), "xAxis": _fmt(plan.dark_start), "itemStyle": {"color": "rgba(60,80,140,0.18)"}},
                {"xAxis": _fmt(plan.dark_end)},
            ])
        if plan.best_slot:
            mark_areas.append([
                {"name": t("planner_best"), "xAxis": _fmt(plan.best_slot[0]), "itemStyle": {"color": "rgba(56,200,112,0.22)"}},
                {"xAxis": _fmt(plan.best_slot[1])},
            ])
        if get_busy is not None:
            first, last = plan.times[0], plan.times[-1]
            for start, end, name in get_busy():
                if end < first or start > last:
                    continue
                # Snap to the chart's own 5-min category labels.
                start_i = min(range(len(plan.times)), key=lambda i: abs(plan.times[i] - max(start, first)))
                end_i = min(range(len(plan.times)), key=lambda i: abs(plan.times[i] - min(end, last)))
                mark_areas.append([
                    {"name": name, "xAxis": labels[start_i], "itemStyle": {"color": "rgba(224,64,64,0.22)"}},
                    {"xAxis": labels[end_i]},
                ])
        # Compass direction of the target (user-requested Oct 2026: "les
        # indicateurs cardinaux N E S O sur la courbe"): labelled on the
        # curve wherever it changes while above the horizon, and in the
        # tooltip for every point - to see at a glance when the target is
        # behind the trees to the East, or over the house to the South.
        compass = _compass_names()
        directions = [compass[compass_index(az)] for az in plan.target_az]
        target_points: list = []
        previous = None
        for alt, direction in zip(plan.target_alt, directions):
            value = round(alt, 1)
            if alt > 0 and direction != previous:
                target_points.append({
                    "value": value,
                    "symbolSize": 8,
                    "label": {"show": True, "formatter": direction, "position": "top",
                              "fontWeight": "bold", "fontSize": 11},
                })
            else:
                target_points.append(value)
            previous = direction if alt > 0 else None
        target_name = t("planner_target")
        tooltip_dirs = json.dumps([f"{d} ({round(az)}\u00b0)" for d, az in zip(directions, plan.target_az)])
        chart.options["tooltip"] = {
            "trigger": "axis",
            ":formatter": (
                "params => { const dirs = " + tooltip_dirs + "; "
                "let html = params.length ? params[0].axisValueLabel : ''; "
                "for (const p of params) { "
                "html += '<br/>' + p.marker + p.seriesName + ' : <b>' + p.value + '\u00b0</b>'; "
                "if (p.seriesName === " + json.dumps(target_name) + ") html += ' \u00b7 ' + dirs[p.dataIndex]; } "
                "return html; }"
            ),
        }

        floor = float(min_alt_input.value or 0)
        chart.options["xAxis"]["data"] = labels
        chart.options["series"] = [
            {
                "name": target_name,
                "type": "line",
                # Small but real symbols: ECharts only fires a point click
                # on a symbol, and the curve is the "click to set the
                # start time" target.
                "symbol": "circle",
                "symbolSize": 5,
                # Every point drawn: with "auto" ECharts skips symbols when
                # they're dense - and the compass labels with them.
                "showAllSymbol": True,
                "data": target_points,
                "lineStyle": {"width": 3},
                "markArea": {"silent": True, "data": mark_areas, "label": {"show": False}},
                "markLine": {
                    "silent": True,
                    "symbol": "none",
                    "lineStyle": {"type": "dashed", "color": "#f0a030"},
                    "data": [{"yAxis": floor}],
                },
            },
            {
                "name": t("planner_moon", pct=round(plan.moon_illumination * 100)),
                "type": "line",
                "showSymbol": False,
                "data": [round(a, 1) for a in plan.moon_alt],
                "lineStyle": {"type": "dotted", "color": "#9e9e9e"},
                "itemStyle": {"color": "#9e9e9e"},
            },
            {
                "name": t("planner_sun"),
                "type": "line",
                "showSymbol": False,
                "data": [round(a, 1) for a in plan.sun_alt],
                "lineStyle": {"width": 1, "color": "#f0b840"},
                "itemStyle": {"color": "#f0b840"},
            },
        ]
        chart.update()

        transit_i = plan.times.index(plan.transit_time)
        bits = [t(
            "planner_culmination",
            time=_fmt(plan.transit_time),
            alt=round(plan.max_altitude or 0),
            direction=directions[transit_i],
        )]
        if plan.dark_start:
            bits.append(t("planner_dark_window", start=_fmt(plan.dark_start), end=_fmt(plan.dark_end)))
        else:
            bits.append(t("planner_never_dark"))
        if plan.best_slot:
            bits.append(t("planner_best_slot", start=_fmt(plan.best_slot[0]), end=_fmt(plan.best_slot[1])))
            use_best.enable()
        else:
            bits.append(t("planner_no_slot", alt=round(floor)))
            use_best.disable()
        bits.append(t(
            "planner_moon_info",
            pct=round(plan.moon_illumination * 100),
            sep=round(plan.moon_separation or 0),
        ))
        summary.set_text(" · ".join(bits))

    def _on_use_best() -> None:
        plan = state["plan"]
        if plan and plan.best_slot:
            apply_slot(plan.best_slot[0], plan.best_slot[1])

    def _on_point_click(e) -> None:
        plan = state["plan"]
        index = getattr(e, "data_index", None)
        if plan is None or index is None or not 0 <= index < len(plan.times):
            return
        apply_slot(plan.times[index], None)

    use_best.on_click(_on_use_best)
    chart.on_point_click(_on_point_click)
    min_alt_input.on_value_change(lambda _: refresh())
    darkness.on_value_change(lambda _: refresh())
    return panel, refresh
