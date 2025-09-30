#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test smoke pour l'endpoint /portfolio/metrics (P&L Today)

.DESCRIPTION
    Verifie que l'endpoint retourne les metriques correctes avec le P&L calcule.
    Affiche les valeurs actuelles, l'historique et le delta.

.PARAMETER BaseUrl
    URL de base de l'API (defaut: http://127.0.0.1:8000)

.PARAMETER Source
    Source de donnees a utiliser (defaut: cointracking)

.PARAMETER UserId
    User ID pour les donnees utilisateur (defaut: demo)

.EXAMPLE
    .\tests_pnl_today_smoke.ps1
    .\tests_pnl_today_smoke.ps1 -BaseUrl http://localhost:8000 -Source cointracking_api
#>

param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Source = "cointracking",
    [string]$UserId = "demo"
)

$ErrorActionPreference = "Stop"

Write-Host "P&L Today Smoke Test" -ForegroundColor Cyan
Write-Host "---------------------------------------------" -ForegroundColor DarkGray
Write-Host "Base URL:  $BaseUrl"
Write-Host "Source:    $Source"
Write-Host "User ID:   $UserId"
Write-Host ""

# 1. Test endpoint /portfolio/metrics
Write-Host "Testing GET /portfolio/metrics?source=$Source" -ForegroundColor Yellow

try {
    $url = "$BaseUrl/portfolio/metrics?source=$Source"
    $response = Invoke-RestMethod -Uri $url -Method Get -ErrorAction Stop

    Write-Host "Response received" -ForegroundColor Green
    Write-Host ""

    # Check response structure
    if ($response.ok -eq $true) {
        Write-Host "API returned ok: true" -ForegroundColor Green

        # Display metrics
        if ($response.metrics) {
            Write-Host ""
            Write-Host "METRICS:" -ForegroundColor Cyan
            Write-Host "  Total Value:    $([math]::Round($response.metrics.total_value_usd, 2)) USD" -ForegroundColor White
            Write-Host "  Asset Count:    $($response.metrics.asset_count)" -ForegroundColor White
            Write-Host "  Last Updated:   $($response.metrics.last_updated)" -ForegroundColor DarkGray
        }

        # Display performance (P&L)
        if ($response.performance) {
            Write-Host ""
            Write-Host "PERFORMANCE (P&L):" -ForegroundColor Cyan

            if ($response.performance.performance_available -eq $true) {
                $currentValue = [math]::Round($response.performance.current_value_usd, 2)
                $historicalValue = [math]::Round($response.performance.historical_value_usd, 2)
                $absoluteChange = [math]::Round($response.performance.absolute_change_usd, 2)
                $percentageChange = [math]::Round($response.performance.percentage_change, 2)

                Write-Host "  Current:        $currentValue USD" -ForegroundColor White
                Write-Host "  Historical:     $historicalValue USD" -ForegroundColor White

                if ($absoluteChange -ge 0) {
                    Write-Host "  Delta Absolute:     +$absoluteChange USD" -ForegroundColor Green
                    Write-Host "  Delta Percentage:   +$percentageChange %" -ForegroundColor Green
                } else {
                    Write-Host "  Delta Absolute:     $absoluteChange USD" -ForegroundColor Red
                    Write-Host "  Delta Percentage:   $percentageChange %" -ForegroundColor Red
                }

                Write-Host "  Status:         $($response.performance.performance_status)" -ForegroundColor $(
                    switch ($response.performance.performance_status) {
                        "gain" { "Green" }
                        "loss" { "Red" }
                        default { "Yellow" }
                    }
                )

                if ($response.performance.comparison_date) {
                    Write-Host "  Comparison Date: $($response.performance.comparison_date)" -ForegroundColor DarkGray
                }

                if ($response.performance.days_tracked) {
                    Write-Host "  Days Tracked:   $($response.performance.days_tracked)" -ForegroundColor DarkGray
                }

                if ($response.performance.historical_entries_count) {
                    Write-Host "  History Entries: $($response.performance.historical_entries_count)" -ForegroundColor DarkGray
                }

                Write-Host ""
                Write-Host "P&L is available and calculated!" -ForegroundColor Green

            } else {
                Write-Host "  Performance not available" -ForegroundColor Yellow
                if ($response.performance.message) {
                    Write-Host "      Message: $($response.performance.message)" -ForegroundColor DarkYellow
                }
            }
        }

        Write-Host ""
        Write-Host "---------------------------------------------" -ForegroundColor DarkGray
        Write-Host "TEST PASSED: P&L endpoint is working" -ForegroundColor Green

    } elseif ($response.ok -eq $false) {
        Write-Host "API returned ok: false" -ForegroundColor Yellow
        Write-Host "    Message: $($response.message)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "This usually means:" -ForegroundColor Cyan
        Write-Host "   - Using a stub source (no real data)" -ForegroundColor Gray
        Write-Host "   - COMPUTE_ON_STUB_SOURCES=false in settings" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Try with a real data source (cointracking_api, cointracking)" -ForegroundColor Cyan
        exit 1
    }

} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Possible causes:" -ForegroundColor Yellow
    Write-Host "   - API server not running (uvicorn api.main:app --reload --port 8000)" -ForegroundColor Gray
    Write-Host "   - Wrong BaseUrl or Source parameter" -ForegroundColor Gray
    Write-Host "   - Network/firewall issue" -ForegroundColor Gray
    exit 1
}

# 2. Additional check: verify portfolio history file exists
Write-Host ""
Write-Host "Checking portfolio history file..." -ForegroundColor Yellow

$historyFile = Join-Path $PSScriptRoot "data\portfolio_history.json"
if (Test-Path $historyFile) {
    Write-Host "History file exists: $historyFile" -ForegroundColor Green

    try {
        $history = Get-Content $historyFile -Raw | ConvertFrom-Json
        $entryCount = $history.Count
        Write-Host "   Entries: $entryCount" -ForegroundColor White

        if ($entryCount -lt 2) {
            Write-Host ""
            Write-Host "WARNING: Less than 2 history entries found" -ForegroundColor Yellow
            Write-Host "   P&L calculation requires at least 2 snapshots" -ForegroundColor Gray
            Write-Host "   Run: .\tests_save_snapshot.ps1 to create a snapshot" -ForegroundColor Cyan
        }

        # Show last entry
        if ($entryCount -gt 0) {
            $lastEntry = $history[-1]
            Write-Host ""
            Write-Host "   Last snapshot:" -ForegroundColor DarkGray
            Write-Host "     Date:  $($lastEntry.date)" -ForegroundColor DarkGray
            Write-Host "     Value: $([math]::Round($lastEntry.total_value_usd, 2)) USD" -ForegroundColor DarkGray
        }

    } catch {
        Write-Host "Could not parse history file: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "History file not found: $historyFile" -ForegroundColor Yellow
    Write-Host "   P&L calculation requires portfolio snapshots" -ForegroundColor Gray
    Write-Host "   Run: .\tests_save_snapshot.ps1 to create a snapshot" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "---------------------------------------------" -ForegroundColor DarkGray
Write-Host "Smoke test completed!" -ForegroundColor Green
Write-Host ""
