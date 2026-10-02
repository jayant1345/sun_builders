param(
    [string]$CloudUrl = $env:CLOUD_URL
)

if (-not $CloudUrl) { $CloudUrl = 'https://sunbuilders-production.up.railway.app' }

$ErrorActionPreference = 'Stop'
$tallyUrl = 'http://localhost:9000'
$syncUrl = $CloudUrl.TrimEnd('/') + '/api/vouchers/sync'

try {
    Write-Host '[1/4] Connecting to Tally 7.1 on Port 9000...' -ForegroundColor Cyan

    $companies = @()
    foreach ($reqType in @('Collection', 'Data')) {
        $pingXml = '<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>' + $reqType + '</TYPE><ID>List of Companies</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>'
        try {
            $compResp = Invoke-RestMethod -Uri $tallyUrl -Method Post -Body $pingXml -ContentType 'text/xml' -TimeoutSec 4
            [xml]$cxml = $compResp
            $cList = @($cxml.SelectNodes('//COMPANYNAME') | ForEach-Object { $_.InnerText })
            if (-not $cList -or $cList.Count -eq 0) {
                $cList = @($cxml.SelectNodes('//NAME') | ForEach-Object { $_.InnerText } | Where-Object { -not $_.StartsWith('$$') })
            }
            if ($cList -and $cList.Count -gt 0) { $companies = $cList; break }
        } catch {}
    }

    if (-not $companies -or $companies.Count -eq 0) {
        Write-Host '[!] Tally is online on Port 9000, but no company is currently open.' -ForegroundColor Yellow
        Write-Host 'Please open your Sun Builders company (e.g. 010002 or 010010) in Tally and re-run this connector.' -ForegroundColor Yellow
        exit 1
    }

    $activeComp = $companies[0]
    Write-Host ('[2/4] Connected to Tally! Loaded Company: ' + $activeComp) -ForegroundColor Green
    Write-Host '[3/4] Querying live Tally Daybook via XML API...' -ForegroundColor Cyan

    $vchReqXml = '<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>Voucher Register</ID></HEADER><BODY><DESC><STATICVARIABLES><SVCURRENTCOMPANY>' + $activeComp + '</SVCURRENTCOMPANY><SVFROMDATE>20000101</SVFROMDATE><SVTODATE>20991231</SVTODATE><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>'
    $vchResp = Invoke-RestMethod -Uri $tallyUrl -Method Post -Body $vchReqXml -ContentType 'text/xml' -TimeoutSec 30
    [xml]$vxml = $vchResp
    $vchs = @($vxml.SelectNodes('//VOUCHER'))
    Write-Host ('[OK] Extracted ' + $vchs.Count + ' vouchers from Tally.') -ForegroundColor Green
    Write-Host '[4/4] Transmitting vouchers to Cloud Dashboard...' -ForegroundColor Cyan

    $payloadList = @()
    $idx = 1
    foreach ($v in $vchs) {
        $vNum = $v.SelectSingleNode('VOUCHERNUMBER').InnerText
        $vDate = $v.SelectSingleNode('DATE').InnerText
        $crAmt = 0; $ded = 0; $party = 'Member'
        foreach ($entry in $v.SelectNodes('.//ALLLEDGERENTRIES.LIST')) {
            $lName = $entry.SelectSingleNode('LEDGERNAME').InnerText
            $amt = [double]($entry.SelectSingleNode('AMOUNT').InnerText)
            if ($amt -lt 0) { $crAmt = [Math]::Abs($amt); $party = $lName }
            elseif ($lName -like '*Stamp*' -or $lName -like '*Reg*') { $ded += [Math]::Abs($amt) }
        }
        $taxable = [Math]::Max(0, ($crAmt - $ded))
        $vchNo = if ($vNum) { $vNum } else { 'VCH-' + $idx }
        $payloadList += @{
            vch_no = $vchNo
            date = $vDate
            name = $party
            raw_name = $party
            unit = 'Unit N/A'
            cr_amount = $crAmt
            deductions = $ded
            taxable_amount = $taxable
            classification = 'Taxable'
            badge_type = 'taxable-1'
            project = $activeComp
        }
        $idx++
    }

    $syncPayload = @{
        project = $activeComp
        synced_at = (Get-Date -Format s)
        source = '1-Click Windows Connector (PowerShell)'
        count = $payloadList.Count
        vouchers = $payloadList
    } | ConvertTo-Json -Depth 5

    $cloudResp = Invoke-RestMethod -Uri $syncUrl -Method Post -Body $syncPayload -ContentType 'application/json' -TimeoutSec 30
    Write-Host '=========================================================================' -ForegroundColor Green
    Write-Host (' [SUCCESS] ' + $cloudResp.message) -ForegroundColor Green
    Write-Host ' Cloud Dashboard updated live! You can now view returns in your browser.' -ForegroundColor Green
    Write-Host '=========================================================================' -ForegroundColor Green
} catch {
    Write-Host ('[!] Local Tally Notice: ' + $_.Exception.Message) -ForegroundColor Yellow
    Write-Host 'Please ensure Tally 7.1 is running, listening on Port 9000, with a company open.' -ForegroundColor Red
}
