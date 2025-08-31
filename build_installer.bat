@echo off
echo Building Astro Dwarf Scheduler Installer...
echo.

echo Step 1: Building GUI executable...
python setupUI.py build_exe --build-exe "build\setupUI"
if errorlevel 1 (
    echo Error building GUI executable
    exit /b 1
)

echo Step 2: Building BLE executable...
python setupBLE.py build_exe --build-exe "build\setupBLE"
if errorlevel 1 (
    echo Error building BLE executable
    exit /b 1
)

echo Step 3: Organizing files...
if exist "build\setupBLE\extern" rmdir /s /q "build\setupBLE\extern"
move "build\setupBLE" "build\setupUI\extern"
if errorlevel 1 (
    echo Error moving BLE executable
    exit /b 1
)

echo Step 4: Creating symbolic links...
mklink "build\setupUI\extern\config.py" "..\config.py"
mklink "build\setupUI\extern\config.ini" "..\config.ini"

echo Step 5: Building installer with Inno Setup...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" AstroDwarfScheduler.iss
if errorlevel 1 (
    echo Error: Inno Setup not found or build failed
    echo Please install Inno Setup from: https://jrsoftware.org/isinfo.php
    exit /b 1
)

echo.
echo ✅ Installer built successfully!
echo Output: installer\AstroDwarfScheduler-Setup.exe
echo.
pause
