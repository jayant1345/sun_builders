# Script to build clean, rock-solid zip distribution packages for CA Office

$baseDir = "c:\Project_AI\sun_builders"
$packageDir = Join-Path $baseDir "release_packages"
$opt1Dir = Join-Path $packageDir "Option_1_Standalone_EXE"
$opt2Dir = Join-Path $packageDir "Option_2_Python_Script"

Write-Host "Creating clean release directories..." -ForegroundColor Cyan
if (Test-Path $packageDir) {
    Remove-Item $packageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $opt1Dir -Force | Out-Null
New-Item -ItemType Directory -Path $opt2Dir -Force | Out-Null

# -------------------------------------------------------------
# 1. OPTION 1: STANDALONE EXE (ZERO PYTHON NEEDED)
# -------------------------------------------------------------
Write-Host "Packaging Option 1: Standalone EXE (Zero Python)..." -ForegroundColor Green
Copy-Item (Join-Path $baseDir "dist_bridge\SunBuilders_Tally_Agent\SunBuilders_Tally_Agent.exe") -Destination $opt1Dir
Copy-Item (Join-Path $baseDir "dist_bridge\SunBuilders_Tally_Agent\_internal") -Destination $opt1Dir -Recurse
New-Item -ItemType Directory -Path (Join-Path $opt1Dir "data") -Force | Out-Null
if (Test-Path (Join-Path $baseDir "data")) {
    Get-ChildItem (Join-Path $baseDir "data") -Filter *.json | Copy-Item -Destination (Join-Path $opt1Dir "data")
}

# Launcher for Option 1
$opt1Bat = @"
@echo off
title Sun Builders - Tally Cloud Bridge Agent (Standalone)
color 0A
cd /d "%~dp0"

echo =========================================================================
echo       SUN BUILDERS - TALLY CLOUD BRIDGE AGENT (STANDALONE)
echo       Connecting Tally (Port 9000) to Railway Cloud Dashboard
echo       NO PYTHON INSTALLATION REQUIRED
echo =========================================================================
echo.
echo [*] Checking Tally connection on http://localhost:9000...
echo [*] Watching Railway Cloud: https://sunbuilders-production.up.railway.app
echo [*] Keep this window open. You can minimize it.
echo.

SunBuilders_Tally_Agent.exe

echo.
echo The agent has stopped. Close this window or press any key to exit.
pause >nul
"@
Set-Content -Path (Join-Path $opt1Dir "Start_Tally_Bridge.bat") -Value $opt1Bat -Encoding Ascii

# Readme for Option 1
$opt1Readme = @"
SUN BUILDERS - TALLY CLOUD BRIDGE (OPTION 1: STANDALONE)
=========================================================
NO PYTHON INSTALLATION REQUIRED!

HOW TO USE IN CA OFFICE:
1. Make sure TallyPrime or Tally.ERP 9 is running with your company open (Port 9000).
2. Double-click "Start_Tally_Bridge.bat" (or "SunBuilders_Tally_Agent.exe").
3. A black/green window will appear saying "Watching: https://sunbuilders-production.up.railway.app".
4. Keep this window OPEN (you can minimize it).
5. Open your browser and go to your dashboard:
   https://sunbuilders-production.up.railway.app/
6. Click "Sync Tally" or view live vouchers on the Railway dashboard!

All vouchers will sync automatically.
"@
Set-Content -Path (Join-Path $opt1Dir "HOW_TO_USE_CA_OFFICE.txt") -Value $opt1Readme -Encoding Ascii


# -------------------------------------------------------------
# 2. OPTION 2: PYTHON SCRIPT WITH 1-CLICK AUTO-INSTALLER
# -------------------------------------------------------------
Write-Host "Packaging Option 2: Python Script with Auto-Installer..." -ForegroundColor Green
Copy-Item (Join-Path $baseDir "Install_Python_And_Setup.bat") -Destination $opt2Dir
Copy-Item (Join-Path $baseDir "Start_Tally_Agent.bat") -Destination $opt2Dir
Copy-Item (Join-Path $baseDir "1_Install_Python_Once.bat") -Destination $opt2Dir
Copy-Item (Join-Path $baseDir "2_Start_Tally_Agent.bat") -Destination $opt2Dir
Copy-Item (Join-Path $baseDir "tally_bridge_agent.py") -Destination $opt2Dir
Copy-Item (Join-Path $baseDir "tally_sync_agent.py") -Destination $opt2Dir
Copy-Item (Join-Path $baseDir "core") -Destination $opt2Dir -Recurse
Copy-Item (Join-Path $baseDir "config") -Destination $opt2Dir -Recurse
New-Item -ItemType Directory -Path (Join-Path $opt2Dir "data") -Force | Out-Null
if (Test-Path (Join-Path $baseDir "data")) {
    Get-ChildItem (Join-Path $baseDir "data") -Filter *.json | Copy-Item -Destination (Join-Path $opt2Dir "data")
}

# Readme for Option 2
$opt2Readme = @"
SUN BUILDERS - TALLY CLOUD BRIDGE (OPTION 2: PYTHON SETUP)
==========================================================
AUTOMATIC PYTHON INSTALLER & SYNC AGENT

HOW TO USE IN CA OFFICE:
STEP 1 (First Time Only):
- Double-click "Install_Python_And_Setup.bat".
- It will automatically download official Python, install it silently,
  and configure your Windows PATH variable (no admin password needed).

STEP 2:
- Make sure TallyPrime or Tally.ERP 9 is running with your company open (Port 9000).
- Double-click "Start_Tally_Agent.bat".
- Keep the window open while working with Railway Cloud!

STEP 3:
- Open your Railway cloud dashboard in your browser:
  https://sunbuilders-production.up.railway.app/
"@
Set-Content -Path (Join-Path $opt2Dir "HOW_TO_USE_CA_OFFICE.txt") -Value $opt2Readme -Encoding Ascii


# -------------------------------------------------------------
# 3. CREATE ZIP ARCHIVES
# -------------------------------------------------------------
Write-Host "Compressing ZIP archives..." -ForegroundColor Yellow

$zip1 = Join-Path $baseDir "Option_1_Standalone_EXE_No_Python_Needed.zip"
$zip2 = Join-Path $baseDir "Option_2_Python_Script_With_AutoInstaller.zip"
$zipMaster = Join-Path $baseDir "CA_Office_Tally_Bridge_Complete_Package.zip"

if (Test-Path $zip1) { Remove-Item $zip1 -Force }
if (Test-Path $zip2) { Remove-Item $zip2 -Force }
if (Test-Path $zipMaster) { Remove-Item $zipMaster -Force }

# Create Option 1 Zip
Compress-Archive -Path "$opt1Dir\*" -DestinationPath $zip1 -CompressionLevel Optimal
Write-Host "Created: $zip1" -ForegroundColor Green

# Create Option 2 Zip
Compress-Archive -Path "$opt2Dir\*" -DestinationPath $zip2 -CompressionLevel Optimal
Write-Host "Created: $zip2" -ForegroundColor Green

# Master Readme
$masterReadme = @"
================================================================================
  SUN BUILDERS PROJECTS LLP - TALLY TO RAILWAY CLOUD BRIDGE PACKAGES
================================================================================

Cloud App URL: https://sunbuilders-production.up.railway.app/
Local Tally Port: 9000

We have provided TWO separate options for the CA Office:

--------------------------------------------------------------------------------
OPTION 1: Standalone EXE (RECOMMENDED - 100% ZERO PYTHON REQUIRED)
Folder: Option_1_Standalone_EXE
Zip:    Option_1_Standalone_EXE_No_Python_Needed.zip
--------------------------------------------------------------------------------
- Requires NO Python installation at all!
- Requires NO administrator password or PATH settings.
- Simply extract the folder, make sure Tally is open, and double-click:
  Start_Tally_Bridge.bat (or SunBuilders_Tally_Agent.exe)

--------------------------------------------------------------------------------
OPTION 2: Python Script with 1-Click Auto-Installer
Folder: Option_2_Python_Script
Zip:    Option_2_Python_Script_With_AutoInstaller.zip
--------------------------------------------------------------------------------
- If you prefer running Python directly:
  1. Double-click "Install_Python_And_Setup.bat" once.
     (It silently downloads Python 3.12, sets PATH, and bypasses Windows Store prompts).
  2. Open Tally, then double-click "Start_Tally_Agent.bat".

================================================================================
"@
Set-Content -Path (Join-Path $packageDir "README_FIRST.txt") -Value $masterReadme -Encoding Ascii

# Create Master Zip containing both
Compress-Archive -Path "$packageDir\*" -DestinationPath $zipMaster -CompressionLevel Optimal
Write-Host "Created Master Package: $zipMaster" -ForegroundColor Green
Write-Host "All ZIP files ready!" -ForegroundColor Cyan
