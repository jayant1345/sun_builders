@echo off
title Sun Builders Real Estate GST Automation
color 0B
echo =========================================================================
echo       SUN BUILDERS PROJECTS LLP - REAL ESTATE GST AUTOMATION
echo                Powered by Flask ^& Google Stitch Modern UI
echo =========================================================================
echo.
echo [1/3] Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH. Please install Python 3.10+
    pause
    exit /b 1
)

echo [2/3] Starting Flask Application Server on http://localhost:5050...
start "" http://localhost:5050
python server.py

pause
