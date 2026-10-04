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

from components import catalog_add_on
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


def open_catalog_dialog(
    session,
    on_pick: Callable[[dict], None],
    get_night: Callable[[], datetime],
    *,
    tz: tzinfo | None = None,
) -> None:
    """on_pick(entry): called with the chosen catalog entry (its
    ra_hours/dec_deg already parsed - see dso_catalog.load_catalog()).
    tz: timezone of get_night()'s date (None = this PC's)."""
    entries = load_catalog()
    if not entries:
        ui.notify(t("catalog_not_found"), type="warning")
        return

    location = site_location(session)
    night = get_night()
    altitudes = (
        max_dark_altitudes(entries, location[0], location[1], night, tz=tz) if location else [None] * len(entries)
    )

    rows = []
    for i, (entry, alt) in enumerate(zip(entries, altitudes)):
        rows.append({
            "id": i,
            "designation": entry.get("designation", ""),
            "name": entry.get("alternateNames") or "",
            "type": entry.get("type") or "",
            "category": entry.get("typeCategory") or "",
            "constellation": entry.get("constellation") or "",
            "mag": entry.get("magnitude"),
            "size": entry.get("size") or "",
            "alt": round(alt) if alt is not None else None,
            "addOn": bool(entry.get("_addOn")),
        })

    columns = [
        {"name": "designation", "label": t("catalog_col_designation"), "field": "designation", "sortable": True, "align": "left"},
        {"name": "name", "label": t("catalog_col_name"), "field": "name", "sortable": True, "align": "left"},
        {"name": "type", "label": t("catalog_col_type"), "field": "type", "sortable": True, "align": "left"},
        {"name": "constellation", "label": t("catalog_col_constellation"), "field": "constellation", "sortable": True, "align": "left"},
        {"name": "mag", "label": t("catalog_col_mag"), "field": "mag", "sortable": True},
        {"name": "size", "label": t("catalog_col_size"), "field": "size"},
    ]
    if location:
        columns.append({"name": "alt", "label": t("catalog_col_max_alt"), "field": "alt", "sortable": True})
    has_add_on = any(r["addOn"] for r in rows)
    if has_add_on:
        columns.append({"name": "actions", "label": "", "field": "addOn"})

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-5xl"):
        ui.label(t("catalog_title")).classes("text-lg")
        source = catalog_source()
        user_count = user_entry_count()
        if source:
            ui.label(t("catalog_source", path=str(source), count=len(entries) - user_count)).classes("text-xs text-grey-6")
        if user_count:
            ui.label(t("catalog_add_on_source", path=str(add_on_path()), count=user_count)).classes("text-xs text-grey-6")
        if location:
            ui.label(t("catalog_alt_hint", date=night.strftime("%Y-%m-%d"))).classes("text-xs text-grey-6")
        else:
            ui.label(t("planner_no_location")).classes("text-xs text-amber-700")

        with ui.row().classes("w-full gap-2 items-end"):
            search = ui.input(t("catalog_search")).props("clearable autofocus").classes("flex-1 min-w-[200px]")
            category = ui.select(
                {"": t("catalog_all_types"), **{c: t(f"catalog_cat_{c}") for c in _TYPE_CATEGORIES}},
                value="",
                label=t("catalog_col_type"),
            ).classes("w-40")
            min_alt = ui.number(t("catalog_min_alt"), value=0, min=0, max=90, step=5).classes("w-36")
            min_alt.set_visibility(bool(location))

        table = ui.table(
            columns=columns,
            rows=rows,
            row_key="id",
            pagination={"rowsPerPage": 10, "sortBy": "alt" if location else "designation", "descending": bool(location)},
        ).classes("w-full").props("dense flat")
        search.bind_value_to(table, "filter")

        # Objects from catalog_add_on.json can be removed again (user-
        # requested Oct 2026: the user chooses whether to keep them).
        if has_add_on:
            table.add_slot(
                "body-cell-actions",
                '<q-td :props="props">'
                '<q-btn v-if="props.row.addOn" flat dense round size="sm" icon="delete_outline" color="negative"'
                ' @click.stop="() => $parent.$emit(\'remove_add_on\', props.row)">'
                f'<q-tooltip>{t("catalog_add_on_remove")}</q-tooltip></q-btn>'
                '</q-td>',
            )

            def _on_remove(e) -> None:
                row = e.args if isinstance(e.args, dict) else None
                if not row:
                    return
                designation = entries[row["id"]].get("designation", "")
                if catalog_add_on.remove_entry(designation):
                    rows[:] = [r for r in rows if r["id"] != row["id"]]
                    _apply_filters()
                    ui.notify(t("catalog_add_on_removed", name=designation), type="positive")

            table.on("remove_add_on", _on_remove)

        def _apply_filters() -> None:
            wanted = category.value or ""
            floor = float(min_alt.value or 0) if location else 0
            table.rows = [
                r for r in rows
                if (not wanted or r["category"] == wanted)
                and (not floor or (r["alt"] is not None and r["alt"] >= floor))
            ]
            table.update()

        category.on_value_change(lambda _: _apply_filters())
        min_alt.on_value_change(lambda _: _apply_filters())

        def _on_row_click(e) -> None:
            row = e.args[1] if isinstance(e.args, list) and len(e.args) > 1 else None
            if not row:
                return
            dialog.close()
            on_pick(entries[row["id"]])

        table.on("rowClick", _on_row_click)
        ui.label(t("catalog_click_hint")).classes("text-xs text-grey-6")
        with ui.row().classes("w-full justify-end"):
            ui.button(t("close"), on_click=dialog.close).props("flat")
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
