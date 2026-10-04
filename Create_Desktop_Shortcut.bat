@echo off
title Create Sun Builders Sync Shortcut on Desktop
echo Creating 1-Click Sync Shortcut on your Desktop...

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Sync Sun Tally to Cloud.lnk'); $s.TargetPath = '%~dp0Sun_Tally_Sync.bat'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = 'shell32.dll,238'; $s.Save()"

echo.
echo [SUCCESS] Shortcut 'Sync Sun Tally to Cloud' has been placed on your Desktop!
echo Whenever you want to sync new vouchers from Tally to Railway Cloud, just double-click that icon.
echo.
pause
