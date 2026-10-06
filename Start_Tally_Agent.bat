@echo off
setlocal
title Sun Builders - Tally Cloud Bridge Agent
color 0A
cd /d "%~dp0"

REM -------------------------------------------------------------
REM 1. Priority 1: Check if Standalone .EXE exists in this folder
REM -------------------------------------------------------------
if exist "%~dp0SunBuilders_Tally_Agent.exe" (
    echo [*] Starting Standalone Tally Bridge Agent...
    start "" "%~dp0SunBuilders_Tally_Agent.exe"
    exit /b 0
)

REM -------------------------------------------------------------
REM 2. Priority 2: Check for working Python command
REM -------------------------------------------------------------
set "PYCMD="
if exist "%~dp0.python_cmd" (
    set /p PYCMD=<"%~dp0.python_cmd"
)

if not "%PYCMD%"=="" (
    %PYCMD% -c "print(1)" >nul 2>&1
    if errorlevel 1 set "PYCMD="
)

if "%PYCMD%"=="" (
    python -c "print(1)" >nul 2>&1
    if not errorlevel 1 (
        set "PYCMD=python"
    ) else (
        py -c "print(1)" >nul 2>&1
        if not errorlevel 1 set "PYCMD=py"
    )
)

REM Check well-known local installation directories if PATH is not updated yet
if "%PYCMD%"=="" (
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "C:\Program Files\Python312\python.exe"
        "C:\Program Files\Python313\python.exe"
        "C:\Program Files\Python311\python.exe"
    ) do (
        if "%PYCMD%"=="" (
            if exist "%%~fP" (
                "%%~fP" -c "print(1)" >nul 2>&1
                if not errorlevel 1 set "PYCMD=%%~fP"
            )
        )
    )
)

if "%PYCMD%"=="" goto :NoPythonFound

echo %PYCMD%> "%~dp0.python_cmd"

REM -------------------------------------------------------------
REM 3. Run the Bridge Agent
REM -------------------------------------------------------------
color 0A
echo [*] Starting Tally Cloud Bridge Agent using: %PYCMD%
%PYCMD% "%~dp0tally_bridge_agent.py"
echo.
echo The agent has stopped. Close this window or press any key to exit.
pause
exit /b 0

:NoPythonFound
color 0C
echo =========================================================================
echo   [X] Python is not installed on this PC yet ^(or isn't in PATH^).
echo =========================================================================
echo.
echo   Tally Cloud Bridge requires Python runtime to connect to Tally (Port 9000)
echo   and sync live vouchers with: https://sunbuilders-production.up.railway.app
echo.
echo   Choose an option:
echo     [1] Automatically Download and Install Python now (Recommended)
echo     [2] Exit
echo.
set /p CHOICE="Enter 1 or 2 [Default: 1]: "
if "%CHOICE%"=="" set CHOICE=1
if "%CHOICE%"=="1" (
    cls
    if exist "%~dp0Install_Python_And_Setup.bat" (
        call "%~dp0Install_Python_And_Setup.bat"
        exit /b 0
    ) else (
        echo Error: Install_Python_And_Setup.bat not found in current directory.
        pause
        exit /b 1
    )
)
exit /b 1
