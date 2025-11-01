#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test P&L separation by (user_id, source)

.DESCRIPTION
    Validates that P&L tracking is properly isolated per user and source combination
#>

$ErrorActionPreference = "Stop"

Write-Host "`n=== P&L Separation Test ===" -ForegroundColor Cyan
Write-Host "Testing that each (user_id, source) has independent P&L tracking`n" -ForegroundColor White

# Test 1: Check demo/cointracking
Write-Host "[Test 1] demo / cointracking (CSV)" -ForegroundColor Yellow
$response1 = Invoke-RestMethod "http://localhost:8080/portfolio/metrics?source=cointracking&user_id=demo"

if ($response1.ok) {
    Write-Host "  ✓ Total Value: $([math]::Round($response1.metrics.total_value_usd, 2)) USD" -ForegroundColor Green
    Write-Host "  ✓ Asset Count: $($response1.metrics.asset_count)" -ForegroundColor Green
    Write-Host "  ✓ Historical Entries: $($response1.performance.historical_entries_count)" -ForegroundColor Green
    Write-Host "  ✓ P&L Today: $([math]::Round($response1.performance.absolute_change_usd, 2)) USD" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to fetch metrics" -ForegroundColor Red
}

Write-Host ""

# Test 2: Check jack/cointracking_api
Write-Host "[Test 2] jack / cointracking_api (API)" -ForegroundColor Yellow
$response2 = Invoke-RestMethod "http://localhost:8080/portfolio/metrics?source=cointracking_api&user_id=jack"

if ($response2.ok) {
    Write-Host "  ✓ Total Value: $([math]::Round($response2.metrics.total_value_usd, 2)) USD" -ForegroundColor Green
    Write-Host "  ✓ Asset Count: $($response2.metrics.asset_count)" -ForegroundColor Green
    Write-Host "  ✓ Historical Entries: $($response2.performance.historical_entries_count)" -ForegroundColor Green
    Write-Host "  ✓ P&L Today: $([math]::Round($response2.performance.absolute_change_usd, 2)) USD" -ForegroundColor Green

    if ($response2.metrics.asset_count -eq 0) {
        Write-Host "  ⚠ Warning: API returned 0 assets (rate limit or auth issue?)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ✗ Failed to fetch metrics" -ForegroundColor Red
}

Write-Host ""

# Test 3: Check isolation
Write-Host "[Test 3] Isolation Verification" -ForegroundColor Yellow
$historyCount1 = $response1.performance.historical_entries_count
$historyCount2 = $response2.performance.historical_entries_count

if ($historyCount1 -ne $historyCount2) {
    Write-Host "  ✓ History counts are different ($historyCount1 vs $historyCount2)" -ForegroundColor Green
    Write-Host "  ✓ P&L tracking is properly isolated per (user_id, source)" -ForegroundColor Green
} else {
    Write-Host "  ⚠ History counts are the same - might indicate isolation issue" -ForegroundColor Yellow
}

Write-Host ""

# Test 4: Verify portfolio_history.json structure
Write-Host "[Test 4] History File Structure" -ForegroundColor Yellow
$historyFile = "data\portfolio_history.json"

if (Test-Path $historyFile) {
    $history = Get-Content $historyFile -Raw | ConvertFrom-Json

    $demoEntries = @($history | Where-Object { $_.user_id -eq "demo" -and $_.source -eq "cointracking" })
    $jackEntries = @($history | Where-Object { $_.user_id -eq "jack" -and $_.source -eq "cointracking_api" })

    Write-Host "  ✓ Total entries: $($history.Count)" -ForegroundColor Green
    Write-Host "  ✓ demo/cointracking: $($demoEntries.Count)" -ForegroundColor Green
    Write-Host "  ✓ jack/cointracking_api: $($jackEntries.Count)" -ForegroundColor Green

    # Check all entries have required fields
    $allHaveUserIdAndSource = $true
    foreach ($entry in $history) {
        if (-not $entry.user_id -or -not $entry.source) {
            $allHaveUserIdAndSource = $false
            break
        }
    }

    if ($allHaveUserIdAndSource) {
        Write-Host "  ✓ All entries have user_id and source fields" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Some entries missing user_id or source fields" -ForegroundColor Red
    }
} else {
    Write-Host "  ✗ History file not found" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Test Complete ===" -ForegroundColor Cyan
Write-Host ""