from cx_Freeze import setup, Executable
import sys

# Include additional files and folders
buildOptions = dict(
    include_files=[
        ('dwarf_ble_connect/','./dwarf_ble_connect'),
        ('Install/','.')
    ]
)

# Define the base for a GUI application
base = 'Win32GUI' if sys.platform=='win32' else None
# Setup function
setup(
    name="Astro Dwarf Scheduler",
    version="1.0",
    description="Dwarf Astro Scheduler",
    options = dict(build_exe = buildOptions),
    executables=[Executable("astro_dwarf_session_UI.py")]
)
