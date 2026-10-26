"""Settings card "HTTPS for phones" (user-requested Oct 2026): turns the
HTTPS relay on (components/https_server.py), Dwarfium's CA folder, and
walks the phone through trusting the CA and installing the app."""
from __future__ import annotations

from nicegui import ui

from components import https_server
from components.i18n import t
from components.network_info import get_lan_port, qr_svg


def render_https_card() -> None:
    settings = https_server.load_settings()
    with ui.card().classes("w-full p-0 mt-2"), ui.expansion(
        t("https_title"), icon="lock", value=False
    ).classes("w-full"):
        ui.label(t("https_hint")).classes("text-xs text-grey-6")
        enabled = ui.switch(t("https_enable"), value=bool(settings.get("enabled")))
        dwarfium_dir = ui.input(
            t("https_dwarfium_dir"), value=settings.get("dwarfium_dir", ""),
            placeholder=r"C:\Dwarfium",
        ).classes("w-full")
        ui.label(t("https_dwarfium_hint")).classes("text-xs text-grey-6")

        async def apply() -> None:
            folder = (dwarfium_dir.value or "").strip()
            if folder and not https_server.find_dwarfium_ca(folder):
                ui.notify(t("https_dwarfium_missing"), type="warning")
                return
            https_server.save_settings(enabled=bool(enabled.value), dwarfium_dir=folder)
            await https_server.restart_relay()
            details.refresh()
            if enabled.value and not https_server.is_running():
                ui.notify(t("https_not_running", error=https_server.last_error()), type="negative")

        ui.button(t("https_apply"), icon="save", on_click=apply).props("color=primary")

        @ui.refreshable
        def details() -> None:
            if not https_server.is_enabled():
                return
            if not https_server.is_running():
                ui.label(t("https_not_running", error=https_server.last_error())).classes(
                    "text-negative text-sm")
                return
            ip = (https_server.local_ips() or ["localhost"])[0]
            ca_url = f"http://{ip}:{get_lan_port()}/https/ca.crt"
            app_urls = https_server.https_urls()
            ui.label(t("https_ca_dwarfium") if https_server.uses_dwarfium_ca()
                     else t("https_ca_own")).classes("text-sm text-positive")
            ui.label(t("https_step_ca")).classes("text-base mt-2")
            ui.html(qr_svg(ca_url)).classes("w-40 h-40 bg-white p-1")
            ui.link(ca_url, ca_url, new_tab=True).classes("text-xs break-all")
            ui.markdown(t("https_step_ca_how")).classes("text-xs")
            ui.label(t("https_step_app")).classes("text-base mt-2")
            ui.html(qr_svg(app_urls[0])).classes("w-40 h-40 bg-white p-1")
            ui.link(app_urls[0], app_urls[0], new_tab=True).classes("text-xs break-all")
            ui.label(t("https_step_app_how")).classes("text-xs")
            if app_urls[1:]:
                ui.label(t("https_other_urls", urls=", ".join(app_urls[1:]))).classes(
                    "text-xs text-grey-6 break-all")
            ui.label(t("https_firewall", port=https_server.HTTPS_PORT,
                       folder=str(https_server.CERT_DIR))).classes("text-xs text-grey-6")

        details()
