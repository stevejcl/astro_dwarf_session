@echo off
echo Building Astro Dwarf Scheduler Installer...
echo.

echo Step 1: Building GUI executable...
python setupUI.py build
if errorlevel 1 (
    echo Error building GUI executable
    exit /b 1
)

echo Step 2: Building BLE executable...
python setupBLE.py build
if errorlevel 1 (
    echo Error building BLE executable
    exit /b 1
)

echo Step 3: Organizing files...
if exist "build\exe.win-amd64-3.12\extern" rmdir /s /q "build\exe.win-amd64-3.12\extern"
move "build\exe.win-amd64-3.11" "build\exe.win-amd64-3.12\extern"
if errorlevel 1 (
    echo Error moving BLE executable
    exit /b 1
)

echo Step 4: Creating symbolic links...
mklink "build\exe.win-amd64-3.12\extern\config.py" "..\config.py"
mklink "build\exe.win-amd64-3.12\extern\config.ini" "..\config.ini"

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
