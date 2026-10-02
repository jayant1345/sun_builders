@echo off
title Sun Builders - Install Tally 7.1 Setup
color 0B
cls
echo =========================================================================
echo       SUN BUILDERS - TALLY 7.1 GOLD SETUP LAUNCHER
echo =========================================================================
echo.
echo [*] Checking installer in downloads folder...

set INSTALLER=%~dp0downloads\setup_tally_7.1_gold.exe

if not exist "%INSTALLER%" (
    echo [ERROR] Installer not found at: %INSTALLER%
    pause
    exit /b 1
)

echo [*] Launching Tally 7.1 Setup Wizard...
echo [*] Follow the on-screen instructions to complete installation.
echo.
start "" "%INSTALLER%"

echo [OK] Installer launched! Once installed, Tally shortcut will appear on your desktop.
timeout /t 5
