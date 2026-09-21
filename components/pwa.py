"""PWA ("Add to Home Screen") support - user-requested Sep 2026: "lancer
la fenetre en plein ecran sur Mobile (enlever la barre d'adresse)".

NiceGUI has no built-in manifest/PWA generation (confirmed via its own
GitHub discussions - #3810 documents this exact manual pattern: serve a
manifest.json + link to it from <head>). Deliberately NO service worker
here, unlike a typical PWA setup - service workers are for OFFLINE
caching, and this app inherently needs a live connection to the
backend/hardware at all times, so there's nothing meaningful to serve
offline; skipping it keeps this simple and avoids any risk of a stale
cached page being served instead of the live app.

The address-bar-hiding effect ONLY applies once the page has been added
to the phone's home screen (iOS: Share -> Add to Home Screen; Android:
browser menu -> Add to Home Screen/Install app) and is then opened via
THAT icon - a regular browser tab visit, even with this manifest
present, still shows the normal address bar. This is standard PWA
behaviour, not something any manifest setting can override for a
plain browser tab.

ANDROID + HTTPS (user-reported Sep 2026: "pwa ne marche pas sur mon
android"): Chrome's PWA installability check - the "any icon must be
square" requirement fixed below, PLUS a secure context - requires
either HTTPS or a hostname of exactly "localhost"/"127.0.0.1". This app
is reached over plain HTTP at a LAN IP (see components/network_info.py's
own watch_url()), which Chrome does NOT treat as secure - so on Android,
"Add to Home Screen" is likely to only create a plain bookmark shortcut
(still shows the address bar) rather than a true standalone-mode PWA,
NO MATTER what this manifest says. iOS Safari has historically been more
lenient about this for its own apple-mobile-web-app-capable meta tag,
which is why the effect may still work there over plain HTTP. Fixing
this properly on Android would mean serving the app over HTTPS (a
self-signed cert the phone has to be told to trust, or a real cert via
a domain name / local CA) - a deployment change, not something fixable
from this file alone.
"""
from __future__ import annotations

from fastapi.responses import JSONResponse
from nicegui import app, ui

# Dedicated square PWA icon (user-reported Sep 2026: "pwa ne marche pas
# sur mon android" - dwarf3.png itself is 270x280, NOT square, which
# fails Chrome's installability check on Android; PWA manifest icons
# must be square). Generated once from dwarf3.png (512x512, centered,
# padded) - see the git history for how, no need to regenerate unless
# swapping the source image.
_ICON_PATH = "/images/pwa_icon.png"

_MANIFEST = {
    "name": "Astro Dwarf Session",
    "short_name": "Astro Dwarf",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": "#1976d2",
    "icons": [
        {"src": _ICON_PATH, "sizes": "512x512", "type": "image/png"},
        {"src": _ICON_PATH, "sizes": "192x192", "type": "image/png"},
    ],
}


def register_manifest_route() -> None:
    """Call once at startup (astro_dwarf_ui.py's main()), alongside the
    other app.add_static_files()/route registration - serves the
    manifest JSON itself at /manifest.json."""

    @app.get("/manifest.json")
    def _manifest():
        return JSONResponse(_MANIFEST)


def add_pwa_head_tags() -> None:
    """Call once per page body (same pattern as apply_theme() - see
    components/theme.py), near the top, before other content.

    The <link rel="manifest"> covers Android/Chrome. iOS Safari
    ignores the manifest entirely for "standalone" behaviour and needs
    its OWN separate meta tags instead (apple-mobile-web-app-*) - both
    are included so the effect works on either platform once added to
    the home screen."""
    ui.add_head_html('<link rel="manifest" href="/manifest.json">')
    ui.add_head_html('<meta name="apple-mobile-web-app-capable" content="yes">')
    ui.add_head_html('<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">')
    ui.add_head_html('<meta name="apple-mobile-web-app-title" content="Astro Dwarf">')
    ui.add_head_html(f'<link rel="apple-touch-icon" href="{_ICON_PATH}">')
