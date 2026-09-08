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
#_ble_connect_html = Path("dwarf_ble_connect") / "connect_dwarf.html"
#sep = os.pathsep  # Cross-platform separator: ; on Windows, : on Unix/macOS

extra_data = []
#if _ble_connect_html.exists():
#    extra_data.append(f"{_ble_connect_html}{sep}dwarf_ble_connect")
#else:
#    print(f"Warning: {_ble_connect_html} not found - BLE pairing may break in the built exe.")

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

# Step 4 - Zip everything in dist
suffix = os.environ.get("RUNNER_OS", "unknown")  # Windows, Linux, macOS
zip_path = Path(f"{APP_NAME}-{suffix}.zip")
print(f"Creating archive {zip_path}...")

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for path in DIST_DIR.rglob("*"):
        arcname = path.relative_to(DIST_DIR)
        zipf.write(path, arcname)

print("Build and packaging complete.")
