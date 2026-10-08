"""Home page: list of known Dwarfs. Matches the 'dwarf_multi_dashboard_mobile'
mockup validated with Steve, wired here to the real DwarfManager instead
of sample data.

Cards are built once per dwarf_uid (DeviceCardView) and updated in
place on every poll - NOT recreated from scratch, and DeviceCardView
itself skips touching the DOM when nothing actually changed (see
components/device_card.py's _banner_key). poll() is async so it can run
components.connection_health's active liveness check before refreshing
each card - see that module for why session.is_connected alone isn't
enough to detect a connection that died mid-session (e.g. a Wi-Fi
glitch causing a command timeout, rather than a clean disconnect)."""
from __future__ import annotations

from nicegui import ui,run,app

from dwarf_python_api.lib.dwarf_session import get_manager

from components import connection_health, device_lock, device_prefs
from components.device_card import DeviceCardView
from components.network_info import watch_qr_svg, watch_url
from components.app_version import get_app_version
from components.i18n import AVAILABLE_LANGUAGES, SUPPORTED_LANGUAGES, get_language, set_language, t
from components.pwa import add_pwa_head_tags
from components.theme import apply_theme, theme_toggle_button


def _open_device(dwarf_uid: str) -> None:
    ui.navigate.to(f"/session/{dwarf_uid}")


async def _handle_connect_all(button: ui.button | None = None) -> None:
    """Connects every currently-disconnected device, one at a time -
    sequential rather than concurrent so several Dwarfs don't compete
    for network/BLE resources at the exact same moment (matches
    clicking each card's own \"Connect\" button one after another, just
    without the clicking). A device already connected, or already mid-
    command from something else, is skipped rather than treated as a
    failure - this is a convenience for the common \"just powered on
    several Dwarfs together\" case, not a strict all-or-nothing action.
    Card states pick up the result on their own via dashboard_page()'s
    existing 2s poll() - no manual refresh needed here.

    `button`: disabled for the duration so a second click can't start
    an overlapping run while this one is still going through devices."""
    manager = get_manager()
    targets = [s for s in manager.all() if not s.is_connected]
    if not targets:
        ui.notify(t("connect_all_none"), type="info")
        return

    if button:
        button.disable()
    try:
        connected = 0
        skipped = 0
        failed = 0
        for session in targets:
            if device_lock.held_elsewhere(session.dwarf_uid) or device_prefs.is_hidden(session.dwarf_uid):
                skipped += 1
                continue
            connection_health.clear_taken_over(session.dwarf_uid)
            if not connection_health.try_acquire_command_slot(session.dwarf_uid, caller="dashboard.connect_all"):
                skipped += 1
                continue
            try:
                success = await connection_health.connect_and_enter_astro_mode(session)
            finally:
                connection_health.release_command_slot(session.dwarf_uid)
            if success:
                connected += 1
                connection_health.mark_just_connected(session.dwarf_uid)
                from components import scheduler_runner  # local import - avoids circular import
                await run.io_bound(scheduler_runner.reconcile_orphaned_current_files, uid, session)
            else:
                failed += 1
    finally:
        if button:
            button.enable()

    ui.notify(
        t("connect_all_result", connected=connected, failed=failed, skipped=skipped),
        type="positive" if failed == 0 else "warning",
    )


def build_dashboard_page() -> None:
    @ui.page("/", title="Astro Dwarf Session")
    def dashboard_page() -> None:
        add_pwa_head_tags()
        apply_theme()
        manager = get_manager()

        # Grid layout: side-by-side cards once there are 2+ devices (2
        # columns - naturally becomes a 2x2 grid for 4 devices), a
        # single column for 0-1. Decided once at page load from the
        # current device count; if a device is later paired/removed
        # while this page stays open, the column count doesn't
        # re-adjust live (pairing.py already does a full page reload on
        # success, so that path is covered - only removing a device
        # mid-view is a minor, rare cosmetic miss).
        #
        # Container width is RESPONSIVE (user-requested Sep 2026: "le
        # cadre plus grand si grand ecran") - the original fixed max-w-
        # 2xl/max-w-md capped the whole page at 672px/448px regardless
        # of actual screen size, so device_card.py's own model icon/
        # camera image never had more room to grow into on a genuinely
        # large monitor. Follow-up (Sep 2026, user-reported): an earlier
        # version only widened the cap at xl (1280px+), leaving a big
        # "dead zone" from ~640px to 1280px where the container stayed
        # frozen at its smallest size - filled in with md/lg steps too,
        # so it grows gradually across every Tailwind breakpoint. Second
        # follow-up (Sep 2026, user-reported at a real 1920px Full HD
        # screen): even the max-w-6xl (1152px) 2xl step left a lot of
        # visibly unused width - Tailwind's NAMED scale tops out at
        # max-w-7xl (1280px), still short of that, so 2xl now uses an
        # arbitrary-value class instead to actually make use of a wide
        # monitor rather than stopping at Tailwind's largest preset.
        initial_count = len(manager.all())
        columns = 2 if initial_count >= 2 else 1
        container_width = (
            "max-w-2xl md:max-w-3xl lg:max-w-4xl xl:max-w-5xl 2xl:max-w-[1600px]"
            if columns == 2
            else "max-w-md md:max-w-lg lg:max-w-xl xl:max-w-2xl 2xl:max-w-[900px]"
        )

        with ui.column().classes(f"w-full {container_width} mx-auto gap-3 p-4"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label(t("my_dwarfs")).classes("text-xl")
                with ui.row().classes("items-center gap-1"):
                    # TODO: move this into a proper Settings page once one
                    # exists (see dwarfium-scope-archive's pattern in
                    # pages/astro_settings.py) - a bare toggle in the
                    # dashboard header is a stopgap, not the final UX.
                    #
                    # A plain button toggling between the two supported
                    # languages (user-reported Sep 2026, mobile
                    # screenshot: the dropdown's own chevron + padding
                    # took noticeably more width than any of the icon
                    # buttons next to it, at "fr"'s expense on a narrow
                    # screen) - only 2 languages exist right now, so a
                    # toggle is both narrower AND matches the row's
                    # existing icon-button sizing exactly.
                    # With a 3rd language (a locale file with ENABLED = True,
                    # see components/i18n.py) the button opens a menu of the
                    # enabled languages instead (user-requested Oct 2026).
                    def _switch_language(lang: str) -> None:
                        set_language(lang)
                        ui.navigate.reload()

                    def _toggle_language() -> None:
                        current = get_language()
                        other = next(lang for lang in SUPPORTED_LANGUAGES if lang != current)
                        _switch_language(other)

                    if len(SUPPORTED_LANGUAGES) > 2:
                        with ui.button(get_language().upper()).props("flat round dense").classes("text-xs"):
                            with ui.menu():
                                for code, name in AVAILABLE_LANGUAGES.items():
                                    ui.menu_item(
                                        f"{name} ({code})", on_click=lambda _, c=code: _switch_language(c)
                                    ).classes("font-bold" if code == get_language() else "")
                    elif len(SUPPORTED_LANGUAGES) == 2:
                        ui.button(get_language().upper(), on_click=_toggle_language).props(
                            "flat round dense"
                        ).classes("text-xs")
                    ui.button(
                        icon="add", on_click=lambda: ui.navigate.to("/pairing")
                    ).props("flat round")
                    # No-Bluetooth manual config wizard (user-requested
                    # Sep 2026: Bleak sometimes fails to detect the BLE
                    # adapter outright) - a separate entry point from
                    # "add" (BLE pairing) since it collects different
                    # inputs (IP/UID read off the DwarfLab app instead
                    # of a BLE scan) - see pages/manual_config.py.
                    ui.button(
                        icon="wifi", on_click=lambda: ui.navigate.to("/manual-config")
                    ).props("flat round")
                    # Sites management (user-requested Sep 2026): Wifi +
                    # location profiles reusable across devices - see
                    # site_registry.py / pages/sites.py.
                    ui.button(
                        icon="location_on", on_click=lambda: ui.navigate.to("/sites")
                    ).props("flat round")
                    # Connect All (user-requested Sep 2026): a single
                    # click to connect every currently-disconnected
                    # device instead of opening each one's own page -
                    # useful right after several Dwarfs are powered on
                    # together at the start of a session. Reuses the
                    # exact same connect_and_enter_astro_mode() +
                    # command-slot guard pages/session.py's own per-
                    # device "Connect" button already goes through -
                    # see _handle_connect_all() below.
                    connect_all_button = ui.button(icon="power", on_click=lambda: _handle_connect_all(connect_all_button))
                    connect_all_button.props("flat round")
                    connect_all_button.tooltip(t("connect_all"))
                    ui.button(
                        icon="article", on_click=lambda: ui.navigate.to("/logs")
                    ).props("flat round")
                    theme_toggle_button()

            empty_label = ui.label(t("no_devices_configured")).classes("text-grey-6 text-sm")
            cards_container = ui.grid(columns=columns).classes("w-full gap-3")

            # dwarf_uid -> DeviceCardView, kept for the lifetime of this
            # page so poll() below can update() them in place instead of
            # rebuilding the whole list.
            cards: dict[str, DeviceCardView] = {}
            # Order and hidden flags the cards were built with
            built_layout: list = []

            async def _toggle_hidden(uid: str) -> None:
                device_prefs.set_hidden(uid, not device_prefs.is_hidden(uid))
                built_layout.clear()
                await poll()  # rebuilt now, in the new order

            async def _move(uid: str, where: str) -> None:
                device_prefs.move(uid, manager.all(), where)
                built_layout.clear()
                await poll()

            async def poll() -> None:
                sessions = device_prefs.display_order(manager.all())
                layout = [(s.dwarf_uid, device_prefs.is_hidden(s.dwarf_uid)) for s in sessions]

                # Rare path: the device list itself changed (a device
                # was paired/removed while this page stayed open), or a
                # Dwarf was hidden/shown (moves to / from the end) - full
                # rebuild is fine here since it happens once, not every
                # tick.
                if layout != built_layout:
                    cards_container.clear()
                    cards.clear()
                    with cards_container:
                        for session, (_uid, hidden) in zip(sessions, layout):
                            cards[session.dwarf_uid] = DeviceCardView(
                                session, on_open=_open_device,
                                on_toggle_hidden=_toggle_hidden, hidden=hidden, on_move=_move,
                            )
                    built_layout[:] = layout
                    empty_label.set_visibility(not sessions)
                    return

                # Common path: same devices as last tick - active
                # liveness check (rate-limited internally, see
                # connection_health.maybe_check) then update in place,
                # no DOM teardown for anything that hasn't changed.
                for session in sessions:
                    await connection_health.maybe_check(session)
                    cards[session.dwarf_uid].update(session)

            # Watch-mode QR code (user-requested Sep 2026): opens a
            # dialog with a QR code + the plain URL for /watch, so a
            # phone on the same network can join as a read-only
            # spectator without typing an IP address by hand. Placed at
            # the bottom of the page, away from the denser icon row at
            # the top - this is a one-off "share" action, not something
            # reached for on every visit.
            is_dark = app.storage.user.get("ui_mode") == "dark"
            logo_color = "#f5f5f5" if is_dark else "#1a1a1a"

            with ui.row().classes("w-full items-center justify-center mt-2 relative"):
                def _open_watch_qr() -> None:
                    with ui.dialog() as dialog, ui.card().classes("items-center"):
                        ui.label(t("watch_qr_title")).classes("text-base")
                        ui.html(watch_qr_svg()).classes("w-48 h-48")
                        ui.label(watch_url()).classes("text-xs text-grey-6")
                        ui.button(t("close"), on_click=dialog.close).props("flat")
                    dialog.open()

                # Version, small, at the left of the logo's line
                # (user-requested Oct 2026)
                version = get_app_version()
                if version:
                    ui.label(f"v{version}").classes("text-xs text-grey-6 absolute left-0")

                ui.button(icon="qr_code_2", on_click=_open_watch_qr).props("flat round")

                ui.html(
                    'Dwarf<span style="color:#00c896">ium</span> Lite'
                ).classes(
                    "text-lg sm:text-2xl font-bold absolute right-0"
                ).style(f"color:{logo_color}; font-variant-ligatures: none;")

            ui.timer(2.0, poll)
