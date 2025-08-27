#!/bin/bash
# setupBLE_linux.py equivalent - Build BLE Connect for Linux using PyInstaller

echo "Building Dwarfium BLE Connect for Linux..."

# Install dependencies
pip install pyinstaller

# Build the BLE Connect executable
pyinstaller --onedir \
    --add-data "dwarf_ble_connect:dwarf_ble_connect" \
    --name "DwarfiumBLEConnect" \
    connect_bluetooth.py

echo "✅ BLE Connect build complete! Output in dist/DwarfiumBLEConnect/"
