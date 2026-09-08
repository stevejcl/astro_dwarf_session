#!/usr/bin/env python3
"""
tools/check_i18n.py - Audit tool for the i18n locale files.
Adapted from dwarfium-scope-archive's tools/check_i18n.py (same approach,
paths updated to astro_dwarf_ui's layout). Run from the project root:

    python tools/check_i18n.py                 # checks all locales vs English
    python tools/check_i18n.py --lang fr        # checks only French

Reports per locale:
  - Missing keys (need translation)
  - Orphan keys  (no longer exist in English - safe to remove)
  - Untranslated entries (value still equals English)

Global report:
  - Keys used in source code (t("...") calls) but absent from English
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path

# -- Paths ----------------------------------------------------------------
ROOT       = Path(__file__).parent.parent
LOCALE_DIR = ROOT / "components" / "locales"
SCAN_DIRS  = [ROOT / "pages", ROOT / "components"]

# Keys intentionally identical across languages (short technical labels,
# example placeholders / proper nouns) - keeps the audit signal useful
# instead of drowning it in expected non-translations.
WHITELIST_SAME: set[str] = {
    "actions", "device_name_placeholder", "stop_capture", "stop_goto", "gain",
    "prog_actions", "prog_calibration", "prog_date", "prog_description", "prog_gain",
    "tab_scripts", "settings_longitude", "settings_latitude", "action_eq_solving",
    "prog_mosaic", "dashboard_temperature", "dashboard_disk_space", "explorer_gain",
}

SEP = "-" * 70


def load_locale(path: Path) -> dict[str, str]:
    """Load a locale file and return its TRANSLATIONS dict."""
    spec = importlib.util.spec_from_file_location("_locale_tmp", path)
    mod = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
    spec.loader.exec_module(mod)                  # type: ignore[union-attr]
    return mod.TRANSLATIONS


def section(title: str, items: list, note: str = "") -> None:
    status = "OK" if not items else "WARN"
    suffix = f"  -- {note}" if note else ""
    print(f"\n{SEP}")
    print(f"[{status}]  {title}  ({len(items)}){suffix}")
    print(SEP)
    for item in items:
        if isinstance(item, tuple):
            k, v = item
            print(f"  {k:<35s}  {v[:70]!r}")
        else:
            print(f"  {item}")


def scan_source_usage() -> set[str]:
    """Scan all source .py files for literal t("key") calls."""
    pattern = re.compile(r'\bt\(\s*["\']([^"\']+)["\']\s*[),]')
    used: set[str] = set()
    for d in SCAN_DIRS:
        if d.exists():
            for f in d.rglob("*.py"):
                try:
                    text = f.read_text(errors="replace")
                    used.update(m.group(1) for m in pattern.finditer(text))
                except Exception:
                    pass
    return used


def audit_locale(ref: dict[str, str], loc: dict[str, str], lang: str) -> int:
    """Audit one locale against the English reference. Returns issue count."""
    ref_keys = set(ref)
    loc_keys = set(loc)

    missing = sorted(ref_keys - loc_keys)
    orphans = sorted(loc_keys - ref_keys)
    untrans = sorted(
        (k, loc[k]) for k in (ref_keys & loc_keys)
        if loc[k] == ref[k] and k not in WHITELIST_SAME
    )

    section(f"[{lang}] Missing keys (need translation)", missing)
    section(f"[{lang}] Orphan keys (no longer in English reference)", orphans, note="safe to remove")
    section(f"[{lang}] Untranslated (still equals English)", untrans)

    return len(missing) + len(untrans)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit i18n locale files.")
    parser.add_argument("--lang", help="Only audit this language code, e.g. fr")
    args = parser.parse_args()

    ref_path = LOCALE_DIR / "en.py"
    if not ref_path.exists():
        print(f"Reference locale not found: {ref_path}", file=sys.stderr)
        sys.exit(1)

    ref = load_locale(ref_path)
    print(f"\nReference locale: {ref_path} ({len(ref)} keys)")

    used_in_code = scan_source_usage()
    missing_from_ref = sorted(used_in_code - set(ref))
    section("Keys used in source code but MISSING from en.py -- fix first!", missing_from_ref)
    total_issues = len(missing_from_ref)

    if args.lang:
        locale_files = [LOCALE_DIR / f"{args.lang}.py"]
    else:
        locale_files = sorted(
            p for p in LOCALE_DIR.glob("*.py")
            if p.stem != "en" and not p.name.startswith("_")
        )

    if not locale_files:
        print("\nNo locale files found to audit (other than English).")
    else:
        for lf in locale_files:
            if not lf.exists():
                print(f"\nLocale file not found: {lf}")
                continue
            lang = lf.stem
            loc = load_locale(lf)
            print(f"\n{'=' * 70}")
            print(f"  Auditing: {lf.name} ({len(loc)} keys)")
            print(f"{'=' * 70}")
            total_issues += audit_locale(ref, loc, lang)

    print(f"\n{SEP}")
    if total_issues == 0:
        print("All locales are clean.")
    else:
        print(f"{total_issues} issue(s) to fix across all audited locales.")
    print(SEP)
    print()


if __name__ == "__main__":
    main()
