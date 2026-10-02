@echo off
title Sun Builders - 1-Click Tally 7.1 to Cloud Sync Connector
color 0A
cls
echo =========================================================================
echo       SUN BUILDERS PROJECTS LLP - 1-CLICK TALLY SYNC CONNECTOR
echo       Syncs Local Tally 7.1 / TallyPrime (Port 9000) -^> Railway Cloud
echo =========================================================================
echo.

set CLOUD_URL=https://sunbuilders-production.up.railway.app
if not "%~1"=="" set CLOUD_URL=%~1

echo [*] Target Cloud URL: %CLOUD_URL%
echo [*] Checking local Tally 7.1 connection on Port 9000...
echo.

REM 1. Prefer Python script if Python is available and tally_sync_agent.py exists
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    if exist "%~dp0tally_sync_agent.py" (
        echo [*] Running via Python Tally Sync Engine...
        python "%~dp0tally_sync_agent.py" "%CLOUD_URL%"
        if %ERRORLEVEL% EQU 0 goto :DONE
    )
)

REM 2. Standalone Windows PowerShell Engine (Runs on ANY Windows PC without Python)
echo [*] Executing Native Windows PowerShell Connector (No Python needed)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference = 'Stop'; ^
  try { ^
    $tallyUrl = 'http://localhost:9000'; ^
    $cloudUrl = '%CLOUD_URL%/api/vouchers/sync'; ^
    Write-Host '[1/4] Connecting to Tally 7.1 on Port 9000...' -ForegroundColor Cyan; ^
    $pingXml = '<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>List of Companies</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>'; ^
    $compResp = Invoke-RestMethod -Uri $tallyUrl -Method Post -Body $pingXml -ContentType 'text/xml' -TimeoutSec 4; ^
    [xml]$cxml = $compResp; ^
    $companies = @($cxml.SelectNodes('//COMPANYNAME') | ForEach-Object { $_.InnerText }); ^
    if (-not $companies -or $companies.Count -eq 0) { ^
      Write-Host '[!] Tally is online on Port 9000, but no company is currently open.' -ForegroundColor Yellow; ^
      Write-Host 'Please open your Sun Builders company (e.g. 010000 or 010010) in Tally and press any key to re-try.' -ForegroundColor Yellow; ^
      exit 1 ^
    }; ^
    $activeComp = $companies[0]; ^
    Write-Host ('[2/4] Connected to Tally! Loaded Company: ' + $activeComp) -ForegroundColor Green; ^
    Write-Host '[3/4] Querying live Tally Daybook via XML API...' -ForegroundColor Cyan; ^
    $vchReqXml = '<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>Voucher Register</ID></HEADER><BODY><DESC><STATICVARIABLES><SVCURRENTCOMPANY>' + $activeComp + '</SVCURRENTCOMPANY><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>'; ^
    $vchResp = Invoke-RestMethod -Uri $tallyUrl -Method Post -Body $vchReqXml -ContentType 'text/xml' -TimeoutSec 30; ^
    [xml]$vxml = $vchResp; ^
    $vchs = @($vxml.SelectNodes('//VOUCHER')); ^
    Write-Host ('[OK] Extracted ' + $vchs.Count + ' vouchers from Tally.') -ForegroundColor Green; ^
    Write-Host '[4/4] Transmitting vouchers to Cloud Dashboard...' -ForegroundColor Cyan; ^
    $payloadList = @(); ^
    $idx = 1; ^
    foreach ($v in $vchs) { ^
      $vNum = $v.SelectSingleNode('VOUCHERNUMBER').InnerText; ^
      $vDate = $v.SelectSingleNode('DATE').InnerText; ^
      $crAmt = 0; $ded = 0; $party = 'Member'; ^
      foreach ($entry in $v.SelectNodes('.//ALLLEDGERENTRIES.LIST')) { ^
        $lName = $entry.SelectSingleNode('LEDGERNAME').InnerText; ^
        $amt = [double]($entry.SelectSingleNode('AMOUNT').InnerText); ^
        if ($amt -lt 0) { $crAmt = [Math]::Abs($amt); $party = $lName } ^
        elseif ($lName -like '*Stamp*' -or $lName -like '*Reg*') { $ded += [Math]::Abs($amt) } ^
      }; ^
      $taxable = [Math]::Max(0, ($crAmt - $ded)); ^
      $payloadList += @{ ^
        vch_no = ($vNum ? $vNum : ('VCH-' + $idx)); ^
        date = $vDate; ^
        name = $party; ^
        raw_name = $party; ^
        unit = 'Unit N/A'; ^
        cr_amount = $crAmt; ^
        deductions = $ded; ^
        taxable_amount = $taxable; ^
        classification = 'Taxable'; ^
        badge_type = 'taxable-1'; ^
        project = $activeComp ^
      }; ^
      $idx++ ^
    }; ^
    $syncPayload = @{ ^
      project = $activeComp; ^
      synced_at = (Get-Date -Format s); ^
      source = '1-Click Windows Connector (PowerShell)'; ^
      count = $payloadList.Count; ^
      vouchers = $payloadList ^
    } | ConvertTo-Json -Depth 5; ^
    $cloudResp = Invoke-RestMethod -Uri $cloudUrl -Method Post -Body $syncPayload -ContentType 'application/json' -TimeoutSec 30; ^
    Write-Host '=========================================================================' -ForegroundColor Green; ^
    Write-Host (' [SUCCESS] ' + $cloudResp.message) -ForegroundColor Green; ^
    Write-Host ' Cloud Dashboard updated live! You can now view returns in your browser.' -ForegroundColor Green; ^
    Write-Host '=========================================================================' -ForegroundColor Green ^
  } catch { ^
    Write-Host ('[!] Local Tally Notice: ' + $_.Exception.Message) -ForegroundColor Yellow; ^
    Write-Host 'Please ensure Tally 7.1 is running and listening on Port 9000.' -ForegroundColor Red ^
  }"

:DONE
echo.
echo Press any key to exit...
pause >nul
