"""Build script for Astro Dwarf UI - adapted from Dwarfium Scope
Archive's own buildDwarfiumScopeArchive.py (same nicegui-pack/
PyInstaller foundation, same author). Trimmed to what THIS app
actually needs:
  - No db/ (DSO catalog), no astroquery, no CLI tools (quality_scan/
    skybot_scan/astrometry_scan) - all Dwarfium-specific features this
    app doesn't have.
  - Adds dwarf_ble_connect's own connect_dwarf.html (a genuine non-.py
    data file PyInstaller's import-tracing wouldn't pick up on its
    own) - Dwarfium doesn't need this since it never does live BLE
    pairing, only USB/FTP archive access.
  - Copies OUR OWN images/ (device-model icons, see components/
    device_card.py) instead of Dwarfium's image/+db/.

Run from the repo root (same level as astro_dwarf_ui.py):
    python buildAstroDwarfUI.py
"""
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

APP_NAME = "AstroDwarfUI"
ICON_NAME = "AstroDwarfUI.ico"
SOURCE_FILE = "astro_dwarf_ui.py"
DIST_DIR = Path("dist")
BUILD_DIR = Path("build")
IMAGES_DIR = Path("images")
DIST_IMAGES_DIR = DIST_DIR / "images"
DIST_LOCALES_DIR = DIST_DIR / "components" / "locales"

# dwarf_ble_connect's own connect_dwarf.html (used somewhere in its BLE
# pairing flow - see dwarf_python_api/lib/dwarf_utils.py's own
# html_file_path reference) - a genuine DATA file PyInstaller's default
# import-tracing doesn't pick up, unlike the .py modules around it.
_ble_connect_html = Path("dwarf_ble_connect") / "connect_dwarf.html"

# catalog.html - the external DSO target-catalog page (components/
# api_routes.py's /catalog route). MUST be bundled via --add-data, not
# just copied loose into dist/ (user-reported Sep 2026: copying it next
# to the built .exe did NOT work) - in a --onefile build, __file__ for
# a bundled module resolves inside the PyInstaller extraction temp dir
# (sys._MEIPASS), never the folder the .exe itself lives in, so a loose
# file next to the .exe was never where the lookup was actually
# checking. Destination "." bundles it at the ROOT of that extraction
# dir, matching _bundled_path()'s own sys._MEIPASS / "catalog.html".
_catalog_html = Path("catalog.html")

# program_fr.html / program_en.html - the combined "local programs +
# native on-device schedule" page, one file per language (components/
# api_routes.py's /Program-{lang} route, user-requested Sep 2026 - same
# fr/en-copies pattern as milky_way_mosaic_planner_{lang}.html, except
# these read through the SAME _bundled_path() as catalog.html above,
# so each needs the exact same --add-data treatment (destination "." =
# root of the PyInstaller extraction dir) - a loose copy next to the
# built .exe would NOT be found, for the same reason catalog.html's
# own note above explains.
_program_htmls = [Path("program_fr.html"), Path("program_en.html")]

sep = os.pathsep  # Cross-platform separator: ; on Windows, : on Unix/macOS

extra_data = []
if _ble_connect_html.exists():
    extra_data.append(f"{_ble_connect_html}{sep}dwarf_ble_connect")
else:
    print(f"Warning: {_ble_connect_html} not found - BLE pairing may break in the built exe.")

if _catalog_html.exists():
    extra_data.append(f"{_catalog_html}{sep}.")
else:
    print(f"Warning: {_catalog_html} not found - the target-catalog page will be unavailable in the built exe.")

for _program_html in _program_htmls:
    if _program_html.exists():
        extra_data.append(f"{_program_html}{sep}.")
    else:
        print(f"Warning: {_program_html} not found - /Program-{_program_html.stem.rsplit('_', 1)[-1]} will be unavailable in the built exe.")

print("Current working directory:", os.getcwd())

# Step 1 - Clean old build folders
for folder in [DIST_DIR, BUILD_DIR]:
    if folder.exists():
        print(f"Removing {folder}...")
        shutil.rmtree(folder)

# Step 1b - Extract version from CHANGELOG.md and write version.py
# (same [X.Y.Z] format Dwarfium's own CHANGELOG.md uses, confirmed
# compatible with this same regex).
version_str = "Unknown"
try:
    with open("CHANGELOG.md", "r", encoding="utf-8") as f:
        for line in f:
            m = re.search(r"\[V?([\d.]+[a-z]?)\]", line)
            if m:
                version_str = m.group(1)
                break
except Exception:
    pass

with open("version.py", "w", encoding="utf-8") as f:
    f.write(f'APP_VERSION = "{version_str}"\n')
print(f"Version extracted: {version_str}")

# Step 2 - Run nicegui-pack
print("Building executable...")

if not Path(ICON_NAME).exists():
    print(f"Warning: {ICON_NAME} not found - building without a custom icon.")

icon_args = ["--icon", ICON_NAME] if Path(ICON_NAME).exists() else []
pack_cmd = [
    "nicegui-pack",
    "--onefile",
    "--windowed",
    *icon_args,
    "--name", APP_NAME,
    "--add-data", f"{IMAGES_DIR}{sep}images",
    *[arg for data in extra_data for arg in ["--add-data", data]],
    SOURCE_FILE,
]

subprocess.run(pack_cmd, check=True)

# Step 3 - Copy additional files into dist
print("Copying extra files into dist...")

DIST_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
for png_file in IMAGES_DIR.glob("*.png"):
    dest = DIST_IMAGES_DIR / png_file.name
    print(f"Copying {png_file} to {dest}")
    shutil.copy2(png_file, dest)

# Locale files into dist/components/locales/ (required for i18n - see
# components/i18n.py, same pattern as Dwarfium's own).
DIST_LOCALES_DIR.mkdir(parents=True, exist_ok=True)
for locale_file in Path("components/locales").glob("*.py"):
    dest = DIST_LOCALES_DIR / locale_file.name
    print(f"Copying {locale_file} to {dest}")
    shutil.copy2(locale_file, dest)

# Milky Way mosaic planner, next to the exe in dist/ (user-requested
# Sep 2026) - a LOOSE companion file, like catalog.html USED to be
# before it needed --add-data (see that decision's own note above):
# this page is still under active iteration, so requiring a full
# rebuild for every tweak would be painful. components/api_routes.py's
# _external_path() (not _bundled_path()) reads it from next to the
# ACTUAL running .exe, so replacing this file after the fact takes
# effect on the next launch, no rebuild at all. Warn rather than fail
# if it's missing from the repo checkout - same reasoning as
# catalog.html's own warning below.
# Two full copies, one per language (user-requested Sep 2026: "on peut
# faire deux version pour l'instant _fr _en" - no real i18n system in
# this standalone file yet). /mosaic-planner-{lang} (components/
# api_routes.py) looks for both by this exact naming.
for _lang in ("fr", "en"):
    _lang_html = Path(f"milky_way_mosaic_planner_{_lang}.html")
    if _lang_html.exists():
        dest = DIST_DIR / _lang_html.name
        print(f"Copying {_lang_html} to {dest}")
        shutil.copy2(_lang_html, dest)
    else:
        print(f"Warning: {_lang_html} not found - /mosaic-planner-{_lang} will be unavailable until one is placed next to the built exe.")

# Step 4 - Zip everything in dist
suffix = os.environ.get("RUNNER_OS", "unknown")  # Windows, Linux, macOS
zip_path = Path(f"{APP_NAME}-{suffix}.zip")
print(f"Creating archive {zip_path}...")

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for path in DIST_DIR.rglob("*"):
        arcname = path.relative_to(DIST_DIR)
        zipf.write(path, arcname)

print("Build and packaging complete.")
