# components/i18n.py
"""
Astro Dwarf UI - Internationalization (i18n) engine.

Same conventions as dwarfium-scope-archive's components/i18n.py (locale
file format, t()/set_language()/get_language() API, ENABLED flag) - no
need to relearn a second system if you already maintain translations for
one.

Locale files live in components/locales/<lang>.py, each exporting:
    LANGUAGE_NAME = "Deutsch"        # label shown in the language menu
    ENABLED       = True             # False while the translation is not ready
    TRANSLATIONS  = {...}            # dict[str, str]

Languages are discovered at startup from the locale files (user-requested
Oct 2026, as in Dwarfium Scope Archive), so adding a language only
requires dropping a new file there with ENABLED = True - no code change.
`python tools/check_i18n.py --new de "Deutsch"` writes a template. The
locale files are also shipped next to the executable
(dist/components/locales/), and that folder is read first, so a
translator can work with the packaged app: edit <lang>.py there, set
ENABLED = True and restart.

Usage:
    from components.i18n import t, set_language, get_language

    ui.label(t("connect"))
    ui.button(t("disconnect"))
    ui.label(t("battery_detail", battery=80))
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from nicegui import app

DEFAULT_LANGUAGE: str = "en"


# -- Locale file lookup ---------------------------------------------------

def locale_dirs() -> list[Path]:
    """Candidate components/locales folders, in priority order: next to
    the executable first (files edited in the distribution override the
    copy bundled in the exe), then the bundle, then the source tree."""
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).parent / "components" / "locales")
        if hasattr(sys, "_MEIPASS"):
            dirs.append(Path(sys._MEIPASS) / "components" / "locales")
    dirs += [
        Path(__file__).parent / "locales",
        Path("components") / "locales",
        Path("locales"),
    ]
    return dirs


def _load_module(lang: str) -> ModuleType | None:
    """Execute the first existing locales/<lang>.py, or None."""
    for d in locale_dirs():
        path = d / f"{lang}.py"
        if not path.exists():
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"locales.{lang}", path)
            module = importlib.util.module_from_spec(spec)       # type: ignore[arg-type]
            spec.loader.exec_module(module)                      # type: ignore[union-attr]
            return module
        except Exception as e:
            print(f"[i18n] Failed to load locale '{lang}' from {path}: {e}")
            return None
    print(f"[i18n] WARNING: locale '{lang}' not found. Tried:")
    for d in locale_dirs():
        print(f"  MISSING  {(d / f'{lang}.py').resolve()}")
    return None


# -- Locale cache ---------------------------------------------------------
_modules: dict[str, ModuleType | None] = {}


def _locale_module(lang: str) -> ModuleType | None:
    if lang not in _modules:
        _modules[lang] = _load_module(lang)
    return _modules[lang]


def _load_locale(lang: str) -> dict[str, str]:
    """The TRANSLATIONS dict for *lang* (empty if unavailable)."""
    module = _locale_module(lang)
    return getattr(module, "TRANSLATIONS", {}) if module else {}


def _discover_languages() -> dict[str, str]:
    """{code: display name} of every enabled language found in the locale
    folders. English is always available (the fallback language)."""
    codes = set()
    for d in locale_dirs():
        if d.is_dir():
            codes.update(p.stem for p in d.glob("*.py") if not p.stem.startswith("_"))
    languages: dict[str, str] = {}
    for code in sorted(codes | {DEFAULT_LANGUAGE}):
        module = _locale_module(code)
        if module is None:
            continue
        if code != DEFAULT_LANGUAGE and not getattr(module, "ENABLED", False):
            continue
        languages[code] = getattr(module, "LANGUAGE_NAME", code)
    return languages


# {code: display name} of the enabled languages, e.g. {"en": "English", "fr": "Français"}
AVAILABLE_LANGUAGES: dict[str, str] = _discover_languages()
SUPPORTED_LANGUAGES: list[str] = list(AVAILABLE_LANGUAGES)


# -- Public API -------------------------------------------------------------

def get_language() -> str:
    """Return the active language code (e.g. 'en', 'fr').

    Uses app.storage.general (server-wide, not per-browser-session):
    this app controls a single piece of physical hardware, so the
    language is a property of the installation, not of any one client -
    every window/tab/phone connected should show the same language."""
    try:
        lang = app.storage.general.get("language", DEFAULT_LANGUAGE)
        return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    except Exception:
        return DEFAULT_LANGUAGE


def set_language(lang: str) -> None:
    """Persist the language choice. Locales are already cached at first use."""
    if lang in SUPPORTED_LANGUAGES:
        app.storage.general["language"] = lang


def t(key: str, **kwargs) -> str:
    """
    Translate *key* to the active language.

    Falls back to English, then returns the raw key if still not found.
    Supports str.format()-style placeholders: t("connect") or
    t("battery_detail", battery=80).
    """
    lang = get_language()
    locale = _load_locale(lang)
    text = locale.get(key)
    if text is None:
        # Fall back to English
        en_locale = _load_locale(DEFAULT_LANGUAGE)
        text = en_locale.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def t_list(keys: list[str]) -> list[str]:
    """Translate a list of keys."""
    return [t(k) for k in keys]
