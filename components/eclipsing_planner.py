"""Program editor: pick an eclipsing binary's next minimum as the target
(user-requested Oct 2026, see components/eclipsing_binaries.py) - the star,
its coordinates, a description and the window around the minimum as start /
end time, in one click. The measurement is done afterwards in Siril or
AstroImageJ, on the session's raw FITS."""
from __future__ import annotations

from datetime import datetime, tzinfo
from typing import Callable

import requests
from nicegui import run, ui

from components import eclipsing_binaries as eb
from components.coords import parse_dec_degrees, parse_ra_hours
from components.datetime_picker import date_picker_input
from components.i18n import t
from components.site_time import site_now
from components.target_planner import night_of, site_location


def _mag_range(star: dict) -> str:
    try:
        return f"{float(star['max_mag']):.1f}–{float(star['min_mag']):.1f}"
    except (KeyError, TypeError, ValueError):
        return ""


def _why_missing(star: dict) -> str:
    """Why a star has no elements: its last VSX fetch's error, or what VSX
    has no value for."""
    error = eb.progress.errors.get(star["name"], "")
    if error == "not found":
        return t("eb_status_not_found")
    if error.startswith("network"):
        return t("eb_status_network", detail=error.partition(":")[2].strip()[:80])
    missing = star.get("vsx_error") or ""
    if missing:
        names = ", ".join(t(f"eb_el_{field}") for field in missing.split(","))
        return t("eb_status_missing", what=names)
    return t("eb_status_not_fetched")


def open_minima_dialog(
    session,
    on_pick: Callable[[eb.Minimum], None],
    get_night: Callable[[], datetime],
    *,
    tz: tzinfo | None = None,
) -> None:
    """on_pick(minimum): called with the chosen eb.Minimum. tz: the
    timezone of every time shown (None = this PC's). The minima from
    tonight (site time) by default - not get_night(), the program's own
    date, which may already be the next day (user-reported Oct 2026: a
    minimum picked at 19:30 dated the next day); its "Night of" field picks
    another night."""
    location = site_location(session)
    state: dict = {"stars": eb.load_stars(), "minima": []}
    now = site_now(getattr(session, "config", None))
    tonight = night_of(f"{now:%Y-%m-%d}", f"{now:%H:%M:%S}")

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-5xl"):
        ui.label(t("eb_title")).classes("text-lg")
        ui.label(t("eb_intro")).classes("text-xs text-grey-6")
        if location is None:
            ui.label(t("planner_no_location")).classes("text-xs text-amber-700")

        with ui.row().classes("w-full gap-2 items-end"):
            night_input = date_picker_input(t("eb_night_of"), f"{tonight:%Y-%m-%d}").classes("w-40")
            nights_input = ui.number(t("eb_nights"), value=3, min=1, max=30, step=1, format="%d").classes("w-28")
            min_alt_input = ui.number(t("planner_min_alt"), value=30, min=0, max=85, step=5).classes("w-36")
            darkness = ui.select(
                {"astronomical": t("planner_dark_astro"), "nautical": t("planner_dark_nautical"),
                 "civil": t("planner_dark_civil")},
                value="nautical",
                label=t("planner_darkness"),
            ).classes("w-56")
            secondary_cb = ui.checkbox(t("eb_secondary"), value=False)
            full_only_cb = ui.checkbox(t("eb_full_only"), value=False)

        message = ui.label("").classes("text-xs text-grey-6")
        columns = [
            {"name": "date", "label": t("eb_col_date"), "field": "date", "sortable": True, "align": "left"},
            {"name": "time", "label": t("eb_col_minimum"), "field": "time", "align": "left"},
            {"name": "kind", "label": "", "field": "kind"},
            {"name": "star", "label": t("eb_col_star"), "field": "star", "sortable": True, "align": "left"},
            {"name": "vartype", "label": t("catalog_col_type"), "field": "vartype", "align": "left"},
            {"name": "mag", "label": t("catalog_col_mag"), "field": "mag"},
            {"name": "alt", "label": t("eb_col_alt"), "field": "alt", "sortable": True},
            {"name": "window", "label": t("eb_col_window"), "field": "window", "align": "left"},
            {"name": "full", "label": t("eb_col_full"), "field": "full"},
        ]
        table = ui.table(columns=columns, rows=[], row_key="id",
                         pagination={"rowsPerPage": 10}).classes("w-full").props("dense flat")
        ui.label(t("eb_click_hint")).classes("text-xs text-grey-6")

        with ui.expansion(t("eb_stars_title"), icon="star").classes("w-full"):
            stars_label = ui.label("").classes("text-xs text-grey-6")
            with ui.row().classes("w-full gap-2 items-end"):
                name_input = ui.input(t("eb_star_name")).classes("w-40")
                ra_input = ui.input(t("prog_ra")).classes("w-32").tooltip(t("prog_ra_hint"))
                dec_input = ui.input(t("prog_dec")).classes("w-32").tooltip(t("prog_dec_hint"))
                epoch_input = ui.input(t("eb_epoch")).classes("w-36")
                period_input = ui.input(t("eb_period")).classes("w-32")
                add_button = ui.button(t("eb_add"), icon="add").props("flat dense")
            ui.label(t("eb_add_hint")).classes("text-xs text-grey-6")
            star_table = ui.table(
                columns=[
                    {"name": "name", "label": t("eb_col_star"), "field": "name", "sortable": True, "align": "left"},
                    {"name": "vartype", "label": t("catalog_col_type"), "field": "vartype", "align": "left"},
                    {"name": "mag", "label": t("catalog_col_mag"), "field": "mag"},
                    {"name": "period", "label": t("eb_period"), "field": "period"},
                    {"name": "epoch", "label": t("eb_epoch"), "field": "epoch"},
                    {"name": "source", "label": t("eb_col_source"), "field": "source", "align": "left"},
                    {"name": "actions", "label": "", "field": "name"},
                ],
                rows=[], row_key="name", pagination={"rowsPerPage": 8},
            ).classes("w-full").props("dense flat")
            star_table.add_slot(
                "body-cell-actions",
                '<q-td :props="props">'
                '<q-btn flat dense round size="sm" icon="delete_outline" color="negative"'
                ' @click.stop="() => $parent.$emit(\'remove_star\', props.row)">'
                f'<q-tooltip>{t("eb_remove")}</q-tooltip></q-btn>'
                '</q-td>',
            )

        with ui.row().classes("w-full justify-between items-center"):
            update_button = ui.button(t("eb_update_vsx"), icon="cloud_download").props("flat dense")
            ui.button(t("close"), on_click=dialog.close).props("flat")

    def _refresh_stars() -> None:
        stars = state["stars"]
        missing = sum(1 for s in stars if not eb.has_elements(s))
        stars_label.set_text(t("eb_stars_count", count=len(stars), missing=missing, path=str(eb.STARS_FILE.resolve())))
        star_table.rows = [{
            "name": s["name"],
            "vartype": s.get("vartype") or "",
            "mag": _mag_range(s),
            "period": f"{float(s['period_d']):.7f}" if eb.has_elements(s) else "",
            "epoch": f"{float(s['epoch_hjd']):.4f}" if eb.has_elements(s) else "",
            "source": s.get("source") or "" if eb.has_elements(s) else _why_missing(s),
        } for s in stars]
        star_table.update()

    def _refresh_minima() -> None:
        _refresh_stars()
        if location is None:
            table.rows = []
            table.update()
            return
        try:
            night = datetime.strptime((night_input.value or "").strip(), "%Y-%m-%d")
        except ValueError:
            night = tonight
        minima = eb.predict_all(
            state["stars"], location[0], location[1], night,
            nights=int(nights_input.value or 1),
            min_altitude=float(min_alt_input.value or 0),
            darkness=darkness.value,
            secondary=bool(secondary_cb.value),
            tz=tz,
        )
        if full_only_cb.value:
            minima = [m for m in minima if m.full]
        state["minima"] = minima
        table.rows = [{
            "id": i,
            "date": f"{m.time:%Y-%m-%d}",
            "time": f"{m.time:%H:%M}",
            "kind": "I" if m.primary else "II",
            "star": m.name,
            "vartype": m.star.get("vartype") or "",
            "mag": _mag_range(m.star),
            "alt": round(m.altitude),
            "window": f"{m.window_start:%H:%M} → {m.window_end:%H:%M}",
            "full": "✓" if m.full else t("eb_partial"),
        } for i, m in enumerate(minima)]
        table.update()
        with_elements = sum(1 for s in state["stars"] if eb.has_elements(s))
        tz_text = str(tz) if tz is not None else t("eb_pc_time")
        message.set_text(t("eb_found", count=len(minima), stars=with_elements, date=f"{night:%Y-%m-%d}", tz=tz_text))

    async def _update(only_missing: bool) -> None:
        """A VSX update - or waits for the one already running (started by
        the Programs page's button). _show_progress() follows it."""
        if not only_missing or any(not eb.has_elements(s) for s in state["stars"]) or eb.progress.running:
            _show_progress()
            failed = await run.io_bound(eb.fetch_elements, only_missing)
            _show_progress()
            if failed:
                ui.notify(t("eb_fetch_failed", names=", ".join(failed)), type="warning", multi_line=True)

    def _show_progress() -> None:
        """The update's progress on its button (greyed meanwhile), and the
        minima of the stars fetched so far."""
        running = eb.progress.running
        if running:
            update_button.disable()
            update_button.set_text(t("eb_updating", done=eb.progress.done, total=eb.progress.total))
        else:
            update_button.enable()
            update_button.set_text(t("eb_update_vsx"))
        if eb.progress.done != state.get("shown_done") or running != state.get("shown_running"):
            state["shown_done"], state["shown_running"] = eb.progress.done, running
            state["stars"] = eb.load_stars()
            _refresh_minima()

    def _number(text) -> float | None:
        try:
            return float(str(text or "").strip().replace(",", "."))
        except ValueError:
            return None

    async def _add() -> None:
        name = " ".join(str(name_input.value or "").split())
        if not name:
            return
        star: dict = {"name": name}
        epoch, period = _number(epoch_input.value), _number(period_input.value)
        if epoch is not None and period is not None:
            star.update(epoch_hjd=epoch, period_d=period, source="manual")
        ra, dec = parse_ra_hours(ra_input.value), parse_dec_degrees(dec_input.value)
        if ra is not None and dec is not None:
            star.update(ra_hours=ra, dec_deg=dec)
        try:
            await run.io_bound(eb.update_from_vsx, star)
        except (requests.RequestException, ValueError) as exc:
            if not eb.has_elements(star):
                ui.notify(t("eb_add_failed", name=name, error=str(exc)), type="warning", multi_line=True)
                return
            eb.save_star(star)   # typed in completely: VSX not needed
        for field in (name_input, ra_input, dec_input, epoch_input, period_input):
            field.value = ""
        state["stars"] = eb.load_stars()
        _refresh_minima()
        ui.notify(t("eb_added", name=name), type="positive")

    def _on_remove(e) -> None:
        row = e.args if isinstance(e.args, dict) else None
        if not row:
            return
        eb.remove_star(row["name"])
        state["stars"] = eb.load_stars()
        _refresh_minima()

    def _on_row_click(e) -> None:
        row = e.args[1] if isinstance(e.args, list) and len(e.args) > 1 else None
        if not row:
            return
        dialog.close()
        on_pick(state["minima"][row["id"]])

    table.on("rowClick", _on_row_click)
    star_table.on("remove_star", _on_remove)
    update_button.on_click(lambda: _update(only_missing=False))
    add_button.on_click(_add)
    for element in (night_input, nights_input, min_alt_input, darkness, secondary_cb, full_only_cb):
        element.on_value_change(lambda _: _refresh_minima())

    _refresh_minima()
    dialog.open()
    with dialog:
        # The seed stars' elements, fetched from VSX the first time
        ui.timer(0.1, lambda: _update(only_missing=True), once=True)
        progress_timer = ui.timer(1.0, _show_progress)
    dialog.on_value_change(lambda e: None if e.value else progress_timer.cancel())
