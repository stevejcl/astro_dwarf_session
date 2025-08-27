"""
Setup script for building Astro Dwarf Scheduler Console application on macOS using py2app
"""

from setuptools import setup
import sys

# py2app setup options
OPTIONS = {
    'argv_emulation': True,
    'packages': [],
    'includes': [],
    'excludes': [],
    'resources': [],
    'plist': {
        'CFBundleName': 'AstroDwarfSchedulerConsole',
        'CFBundleDisplayName': 'Astro Dwarf Scheduler Console',
        'CFBundleVersion': '1.7.0',
        'CFBundleShortVersionString': '1.7.0',
        'CFBundleIdentifier': 'com.astrodwarf.scheduler.console',
        'LSMinimumSystemVersion': '10.9',
    }
}

DATA_FILES = [
    ('dwarf_ble_connect', ['dwarf_ble_connect']),
    ('', ['config.ini', 'config.py']),
    ('Astro_Sessions', ['Astro_Sessions']),
]

setup(
    name="AstroDwarfSchedulerConsole",
    version="1.7.0",
    description="Automatic Astro Session for the Dwarf - Console Version",
    author="Astro Dwarf Team",
    app=['astro_dwarf_scheduler.py'],
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    install_requires=[],
)
