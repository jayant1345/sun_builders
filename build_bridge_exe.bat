@echo off
title Sun Builders - Build Bridge Standalone Executable
color 0B

echo =========================================================================
echo       SUN BUILDERS - BUILD STANDALONE TALLY BRIDGE EXECUTABLE
echo       Packages tally_bridge_agent.py into standalone .EXE for CA Office
echo =========================================================================
echo.

python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install/verify pyinstaller.
    pause
    exit /b 1
)

echo.
echo [*] Building standalone executable into dist_bridge\SunBuilders_Tally_Agent...
python -m PyInstaller --noconfirm --onedir --console ^
  --name "SunBuilders_Tally_Agent" ^
  --distpath "%~dp0dist_bridge" ^
  --workpath "%~dp0build_bridge" ^
  --add-data "%~dp0core;core" ^
  --add-data "%~dp0config;config" ^
  --hidden-import "xml.etree.ElementTree" ^
  --hidden-import "sqlite3" ^
  "%~dp0tally_bridge_agent.py"

if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo =========================================================================
echo [OK] Standalone Executable Build Successful!
echo Location: %~dp0dist_bridge\SunBuilders_Tally_Agent\
echo.
echo You can zip the "SunBuilders_Tally_Agent" folder and send it to the CA office.
echo They can run "SunBuilders_Tally_Agent.exe" directly WITHOUT installing Python!
echo =========================================================================
pause
