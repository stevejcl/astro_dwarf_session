"""
Setup script for building Astro Dwarf Scheduler GUI application on macOS using py2app
"""

from setuptools import setup
import sys

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
        'CFBundleVersion': '1.7.0',
        'CFBundleShortVersionString': '1.7.0',
        'CFBundleIdentifier': 'com.astrodwarf.scheduler',
        'LSMinimumSystemVersion': '10.9',
    }
}

DATA_FILES = [
    'dwarf_ble_connect/',
    'config.ini',
    'config.py',
    'Astro_Sessions/',
]

setup(
    name="AstroDwarfScheduler",
    version="1.7.0",
    description="Dwarf Astro Scheduler GUI Application",
    author="Astro Dwarf Team",
    app=['astro_dwarf_session_UI.py'],
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    install_requires=[
        'bleak',
        'tkinter',
    ],
)
