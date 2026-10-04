@echo off
title Install Automatic Daily Tally Sync (Task Scheduler)
echo ==========================================================================
echo    INSTALL AUTOMATIC DAILY TALLY SYNC - WINDOWS TASK SCHEDULER
echo ==========================================================================
echo.
echo This will schedule a task in Windows to automatically extract new vouchers
echo from Tally and sync to Railway Cloud every day at 6:00 PM (18:00).
echo.

schtasks /create /tn "SunBuilders_Daily_Tally_Sync" /tr "\"%~dp0Sun_Tally_Sync.bat\"" /sc daily /st 18:00 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==========================================================================
    echo [SUCCESS] Daily automatic sync scheduled for 6:00 PM every day!
    echo To run sync anytime manually, double-click 'Sync Sun Tally to Cloud' on Desktop.
    echo ==========================================================================
) else (
    echo [!] Could not create scheduled task. Please run this batch file as Administrator.
)

echo.
pause
