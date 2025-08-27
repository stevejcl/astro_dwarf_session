#!/bin/bash
# setupCMD_linux.py equivalent - Build Console version for Linux using PyInstaller

echo "Building Astro Dwarf Scheduler Console for Linux..."

# Install dependencies
pip install pyinstaller

# Build the Console executable
pyinstaller --onedir \
    --add-data "dwarf_ble_connect:dwarf_ble_connect" \
    --add-data "config.ini:." \
    --add-data "config.py:." \
    --add-data "Astro_Sessions:Astro_Sessions" \
    --name "AstroDwarfSchedulerConsole" \
    astro_dwarf_scheduler.py

echo "✅ Console build complete! Output in dist/AstroDwarfSchedulerConsole/"
