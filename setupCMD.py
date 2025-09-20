from cx_Freeze import setup, Executable
import sys

# Dependencies are automatically detected, but it might need
# fine tuning.

buildOptions = dict(include_files = [('dwarf_ble_connect/','./dwarf_ble_connect'),('Install/','.')]) 
#folder,relative path. Use tuple like in the single file to set a absolute path.

 
base = 'Win32GUI' if sys.platform=='win32' else None
setup(
    name = "Atro_Dwarf_Session",
    version = "1.7.5",
    description = "automatic Astro Session for the Dwarf",
    options = dict(build_exe = buildOptions),
    executables = [Executable("astro_dwarf_scheduler.py",target_name="astro_dwarf_scheduler")]
)