"""
Setup script for building Dwarfium BLE Connect application on macOS using py2app
"""

from setuptools import setup
import sys
import os

# py2app setup options
OPTIONS = {
    'argv_emulation': True,
    'packages': ['bleak'],
    'includes': [],
    'excludes': [],
    'resources': [],
    'plist': {
        'CFBundleName': 'DwarfiumBLEConnect',
        'CFBundleDisplayName': 'Dwarfium BLE Connect',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleIdentifier': 'com.dwarfium.ble.connect',
        'LSMinimumSystemVersion': '10.9',
        'NSBluetoothAlwaysUsageDescription': 'This app needs Bluetooth access to connect to Dwarf devices.',
        'NSBluetoothPeripheralUsageDescription': 'This app needs Bluetooth access to connect to Dwarf devices.',
    }
}

# Include data files that exist
DATA_FILES = []
if os.path.exists('dwarf_ble_connect'):
    DATA_FILES.append('dwarf_ble_connect')

setup(
    name="DwarfiumBLEConnect",
    version="1.0.0",
    description="Dwarfium BLE Connect Application",
    author="Dwarfium Team",
    app=['connect_bluetooth.py'],
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
