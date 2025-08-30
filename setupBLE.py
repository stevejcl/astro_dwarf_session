from cx_Freeze import setup, Executable
import sys

# Include additional files and folders
buildOptions = dict(
    include_files=[
        ('dwarf_ble_connect/','./dwarf_ble_connect'),
    ]
)

# Define the base for a GUI application
base = 'Win32GUI' if sys.platform=='win32' else None
# Setup function
setup(
    name="Dwarfium BLE CONNECT",
    version="1.0",
    description="Dwarfium BLE CONNECT",
    options = dict(build_exe = buildOptions),
    executables=[Executable("connect_bluetooth.py")]
)
