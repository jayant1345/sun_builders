@echo off
setlocal enabledelayedexpansion
title Sun Builders - Automated Python Installer & Setup
color 0B

echo =========================================================================
echo       SUN BUILDERS - AUTOMATED PYTHON SETUP FOR CA OFFICE
echo       Configures Python runtime and PATH for Tally Cloud Bridge
echo =========================================================================
echo.

REM 1. Test if Python is already installed and working
echo [*] Checking existing Python installation...
set "FOUND_PY="

for %%P in (
    "python"
    "py"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files\Python313\python.exe"
    "C:\Program Files\Python311\python.exe"
) do (
    if not defined FOUND_PY (
        %%~P -c "print(1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "FOUND_PY=%%~P"
        )
    )
)

if defined FOUND_PY (
    color 0A
    echo [OK] Working Python detected: %FOUND_PY%
    %FOUND_PY% --version
    echo %FOUND_PY%> "%~dp0.python_cmd"
    echo.
    echo Everything is already configured!
    echo Starting Tally Cloud Bridge Agent in 3 seconds...
    timeout /t 3 >nul
    call "%~dp0Start_Tally_Agent.bat"
    exit /b 0
)

echo [-] Python runtime is not detected or not configured.
echo [*] Disabling Windows Store App Execution Aliases to prevent Store popups...
REM Disable Windows Store python.exe alias redirect trap
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\AppModel\SystemAppData\Microsoft.DesktopAppInstaller_8wekyb3d8bbwe\State" /v "PythonAvailable" /t REG_DWORD /d 0 /f >nul 2>&1

set "PY_VERSION=3.12.8"
set "PY_URL=https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
set "INSTALLER_PATH=%TEMP%\python-%PY_VERSION%-amd64.exe"

echo.
echo [*] Step 1 of 3: Downloading official Python %PY_VERSION% (64-bit)...
echo     Source: %PY_URL%
echo     This may take 1-2 minutes depending on internet speed. Please wait...
echo.

if exist "%SystemRoot%\System32\curl.exe" (
    "%SystemRoot%\System32\curl.exe" --ssl-no-revoke -fLo "%INSTALLER_PATH%" "%PY_URL%"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13; (New-Object System.Net.WebClient).DownloadFile('%PY_URL%', '%INSTALLER_PATH%')"
)

if not exist "%INSTALLER_PATH%" (
    color 0C
    echo [ERROR] Failed to download Python installer.
    echo Please ensure the internet connection is active or download manually from:
    echo %PY_URL%
    echo.
    pause
    exit /b 1
)

echo [*] Download complete! File saved to: %INSTALLER_PATH%
echo.
echo [*] Step 2 of 3: Installing Python %PY_VERSION% silently...
echo     - Setting user PATH variable automatically
echo     - Enabling pip and standard modules
echo     - No admin password required
echo     Please wait for installation to finish...

REM Silent user install with PATH prepended
"%INSTALLER_PATH%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Shortcuts=0
set "INSTALL_STATUS=%errorlevel%"

REM Clean up installer file
del /f /q "%INSTALLER_PATH%" >nul 2>&1

if %INSTALL_STATUS% neq 0 (
    echo [!] Standard user install returned status %INSTALL_STATUS%, checking if Python directory exists...
)

REM 3. Configure and ensure PATH variable is set permanently in user environment
echo.
echo [*] Step 3 of 3: Verifying and locking PATH variables...

set "TARGET_PY_DIR=%LOCALAPPDATA%\Programs\Python\Python312"
set "TARGET_SCRIPTS_DIR=%LOCALAPPDATA%\Programs\Python\Python312\Scripts"

if exist "%TARGET_PY_DIR%\python.exe" (
    REM Add to user environment PATH permanently via PowerShell if not already present
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$userPath = [Environment]::GetEnvironmentVariable('Path', [EnvironmentVariableTarget]::User); " ^
        "$newEntries = @('%TARGET_PY_DIR%', '%TARGET_SCRIPTS_DIR%'); " ^
        "foreach ($entry in $newEntries) { " ^
        "  if ($userPath -notlike '*' + $entry + '*') { " ^
        "    $userPath = $entry + ';' + $userPath; " ^
        "  } " ^
        "}; " ^
        "[Environment]::SetEnvironmentVariable('Path', $userPath, [EnvironmentVariableTarget]::User);"

    REM Update current cmd session PATH
    set "PATH=%TARGET_PY_DIR%;%TARGET_SCRIPTS_DIR%;%PATH%"
    set "PYCMD=%TARGET_PY_DIR%\python.exe"
) else (
    set "PYCMD=python"
)

REM Test the new install
%PYCMD% -c "import sys; print('Python installed successfully: ' + sys.version)" >nul 2>&1
if errorlevel 1 (
    color 0C
    echo.
    echo [ERROR] Python installation did not finish cleanly.
    echo Please reboot this PC once and run this script again, or contact developer.
    echo.
    pause
    exit /b 1
)

color 0A
echo.
echo =========================================================================
echo  SUCCESS! Python has been installed and PATH variables are configured!
echo =========================================================================
echo.
%PYCMD% --version
echo "%PYCMD%"> "%~dp0.python_cmd"
echo.
echo Ready to start Sun Builders Tally Cloud Bridge Agent!
echo.
pause
call "%~dp0Start_Tally_Agent.bat"
