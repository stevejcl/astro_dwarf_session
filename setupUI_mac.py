"""
Setup script for building Astro Dwarf Scheduler GUI application on macOS using py2app
"""

from setuptools import setup
import sys
import os

# py2app setup options
OPTIONS = {
    'argv_emulation': True,
    'packages': ['bleak', 'tkinter'],
    'includes': [],
    'excludes': [],
    'resources': [],
    'plist': {
        'CFBundleName': 'AstroDwarfScheduler',
        'CFBundleDisplayName': 'Astro Dwarf Scheduler',
        'CFBundleVersion': '1.7.5',
        'CFBundleShortVersionString': '1.7.5',
        'CFBundleIdentifier': 'com.astrodwarf.scheduler',
        'LSMinimumSystemVersion': '10.9',
    }
}

# Include data files that exist
DATA_FILES = []
if os.path.exists('dwarf_ble_connect'):
    DATA_FILES.append('dwarf_ble_connect')
if os.path.exists('config.ini'):
    DATA_FILES.append('config.ini')
if os.path.exists('config.py'):
    DATA_FILES.append('config.py')
if os.path.exists('Astro_Sessions'):
    DATA_FILES.append('Astro_Sessions')

setup(
    name="AstroDwarfScheduler",
    version="1.7.5",
    description="Dwarf Astro Scheduler GUI Application",
    author="Astro Dwarf Team",
    app=['astro_dwarf_session_UI.py'],
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
