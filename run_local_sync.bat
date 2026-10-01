@echo off
title Sun Builders - Local Tally to Railway Cloud Sync Agent
color 0A
echo =========================================================================
echo       SUN BUILDERS - LOCAL TALLY TO RAILWAY CLOUD SYNC AGENT
echo       Syncs Local Tally (Port 9000) -^> Railway Cloud Dashboard
echo =========================================================================
echo.
set /p RAILWAY_URL="Enter Railway App URL [Press ENTER for http://localhost:5050]: "
if "%RAILWAY_URL%"=="" set RAILWAY_URL=http://localhost:5050
echo.
echo [*] Target Cloud URL: %RAILWAY_URL%
echo [*] Connecting to local Tally on Port 9000...
echo.
python tally_sync_agent.py "%RAILWAY_URL%"
echo.
pause
