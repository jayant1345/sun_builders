@echo off
title Sun Builders - 1-Click Tally to Railway Cloud Sync Connector
color 0A
cls
echo ==========================================================================
echo       SUN BUILDERS PROJECTS LLP - 1-CLICK TALLY SYNC CONNECTOR
echo       Syncs Local TallyPrime / Tally.ERP 9 (Port 9000) -^> Railway Cloud
echo ==========================================================================
echo.

set CLOUD_URL=https://sunbuilders-production.up.railway.app
if not "%~1"=="" set CLOUD_URL=%~1

echo [*] Target Cloud URL: %CLOUD_URL%
echo [*] Checking local Tally connection on Port 9000...
echo.

REM 1. Check Python installation
set PYEXE=
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 set PYEXE=python
if not defined PYEXE py --version >nul 2>&1 && set PYEXE=py

if defined PYEXE (
    echo [*] Executing Tally Live Extraction Engine via %PYEXE%...
    %PYEXE% -u "%~dp0tally_sync_agent.py" "%CLOUD_URL%"
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo [*] Opening live dashboard in your default browser...
        start %CLOUD_URL%
        goto :DONE
    )
)

echo.
echo [!] If Tally was not open, please open TallyPrime with Company 010010 and re-run.
echo.

:DONE
echo.
echo ==========================================================================
echo Sync process completed.
echo ==========================================================================
echo.
pause
