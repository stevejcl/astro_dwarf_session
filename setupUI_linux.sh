#!/bin/bash
# setupUI_linux.py equivalent - Build GUI version for Linux using PyInstaller

echo "Building Astro Dwarf Scheduler GUI for Linux..."

# Install dependencies
pip install pyinstaller

# Build the GUI executable
pyinstaller --onedir --windowed \
    --add-data "dwarf_ble_connect:dwarf_ble_connect" \
    --add-data "config.ini:." \
    --add-data "config.py:." \
    --add-data "Astro_Sessions:Astro_Sessions" \
    --name "AstroDwarfScheduler" \
    astro_dwarf_session_UI.py

echo "✅ GUI build complete! Output in dist/AstroDwarfScheduler/"
