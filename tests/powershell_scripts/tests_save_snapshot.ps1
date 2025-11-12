#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Sauvegarde un snapshot du portfolio pour le calcul du P&L

.DESCRIPTION
    Appelle l'endpoint /portfolio/snapshot pour creer un snapshot du portfolio actuel.
    Ce snapshot sera utilise pour calculer le P&L Today en comparant avec les donnees futures.

.PARAMETER BaseUrl
    URL de base de l'API (defaut: http://127.0.0.1:8080)

.PARAMETER Source
    Source de donnees a utiliser (defaut: cointracking)

.PARAMETER UserId
    User ID pour les donnees utilisateur (defaut: demo)

.EXAMPLE
    .\tests_save_snapshot.ps1
    .\tests_save_snapshot.ps1 -BaseUrl http://localhost:8080 -Source cointracking_api
#>

param(
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [string]$Source = "cointracking",
    [string]$UserId = "demo"
)

$ErrorActionPreference = "Stop"

Write-Host "Portfolio Snapshot Creator" -ForegroundColor Cyan
Write-Host "---------------------------------------------" -ForegroundColor DarkGray
Write-Host "Base URL:  $BaseUrl"
Write-Host "Source:    $Source"
Write-Host "User ID:   $UserId"
Write-Host ""

# 1. Check current portfolio state
Write-Host "Fetching current portfolio state..." -ForegroundColor Yellow

try {
    $metricsUrl = "$BaseUrl/portfolio/metrics?source=$Source&user_id=$UserId"
    $currentMetrics = Invoke-RestMethod -Uri $metricsUrl -Method Get -ErrorAction Stop

    if ($currentMetrics.ok -eq $false) {
        Write-Host "Cannot fetch current portfolio metrics" -ForegroundColor Red
        Write-Host "   Message: $($currentMetrics.message)" -ForegroundColor Red
        Write-Host ""
        Write-Host "This usually means:" -ForegroundColor Yellow
        Write-Host "   - Using a stub source (no real data)" -ForegroundColor Gray
        Write-Host "   - COMPUTE_ON_STUB_SOURCES=false in settings" -ForegroundColor Gray
        exit 1
    }

    Write-Host "Current portfolio loaded" -ForegroundColor Green
    Write-Host "   Total Value:  $([math]::Round($currentMetrics.metrics.total_value_usd, 2)) USD" -ForegroundColor White
    Write-Host "   Asset Count:  $($currentMetrics.metrics.asset_count)" -ForegroundColor White
    Write-Host ""

} catch {
    Write-Host "ERROR fetching current metrics: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 2. Check existing history
$historyFile = Join-Path $PSScriptRoot "data\portfolio_history.json"
$existingEntries = 0

if (Test-Path $historyFile) {
    try {
        $history = Get-Content $historyFile -Raw | ConvertFrom-Json
        $existingEntries = $history.Count
        Write-Host "Existing history file found" -ForegroundColor Yellow
        Write-Host "   Current entries: $existingEntries" -ForegroundColor White

        if ($existingEntries -gt 0) {
            $lastEntry = $history[-1]
            $lastDate = [DateTime]::Parse($lastEntry.date)
            $hoursSinceLastSnapshot = ([DateTime]::Now - $lastDate).TotalHours

            Write-Host "   Last snapshot:  $($lastEntry.date)" -ForegroundColor DarkGray
            Write-Host "   Last value:     $([math]::Round($lastEntry.total_value_usd, 2)) USD" -ForegroundColor DarkGray
            Write-Host "   Time since:     $([math]::Round($hoursSinceLastSnapshot, 1)) hours ago" -ForegroundColor DarkGray

            if ($hoursSinceLastSnapshot -lt 1) {
                Write-Host ""
                Write-Host "WARNING: Last snapshot was less than 1 hour ago" -ForegroundColor Yellow
                Write-Host "   P&L Today is most meaningful with daily snapshots" -ForegroundColor Gray
                Write-Host ""
                $continue = Read-Host "Continue anyway? (y/n)"
                if ($continue -ne "y") {
                    Write-Host "Cancelled by user" -ForegroundColor Gray
                    exit 0
                }
            }
        }
        Write-Host ""
    } catch {
        Write-Host "Could not parse existing history: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host ""
    }
} else {
    Write-Host "No existing history file (will create new one)" -ForegroundColor Yellow
    Write-Host ""
}

# 3. Save snapshot
Write-Host "Saving portfolio snapshot..." -ForegroundColor Yellow

try {
    $snapshotUrl = "$BaseUrl/portfolio/snapshot?source=$Source&user_id=$UserId"
    $response = Invoke-RestMethod -Uri $snapshotUrl -Method Post -ErrorAction Stop

    if ($response.success -eq $true) {
        Write-Host "Snapshot saved successfully!" -ForegroundColor Green
        Write-Host ""

        if ($response.snapshot) {
            Write-Host "Snapshot details:" -ForegroundColor Cyan
            Write-Host "   Date:           $($response.snapshot.date)" -ForegroundColor White
            Write-Host "   Total Value:    $([math]::Round($response.snapshot.total_value_usd, 2)) USD" -ForegroundColor White
            Write-Host "   Asset Count:    $($response.snapshot.asset_count)" -ForegroundColor White
            Write-Host "   Group Count:    $($response.snapshot.group_count)" -ForegroundColor White
            Write-Host "   Diversity Score: $([math]::Round($response.snapshot.diversity_score, 1))" -ForegroundColor White
        }

        if ($response.total_snapshots) {
            Write-Host ""
            Write-Host "History status:" -ForegroundColor Cyan
            Write-Host "   Total snapshots: $($response.total_snapshots)" -ForegroundColor White

            if ($response.total_snapshots -lt 2) {
                Write-Host ""
                Write-Host "Note: P&L calculation requires at least 2 snapshots" -ForegroundColor Yellow
                Write-Host "   Current count: $($response.total_snapshots)" -ForegroundColor Gray
                Write-Host "   Create another snapshot tomorrow for P&L tracking" -ForegroundColor Cyan
            } else {
                Write-Host ""
                Write-Host "P&L tracking is now active!" -ForegroundColor Green
                Write-Host "   You can view P&L in the dashboard" -ForegroundColor Gray
            }
        }

    } else {
        Write-Host "Snapshot save failed" -ForegroundColor Red
        if ($response.error) {
            Write-Host "   Error: $($response.error)" -ForegroundColor Red
        }
        exit 1
    }

} catch {
    Write-Host "ERROR saving snapshot: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Possible causes:" -ForegroundColor Yellow
    Write-Host "   - API server not running" -ForegroundColor Gray
    Write-Host "   - Permissions issue with data/portfolio_history.json" -ForegroundColor Gray
    Write-Host "   - Invalid portfolio data" -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "---------------------------------------------" -ForegroundColor DarkGray
Write-Host "Snapshot saved successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "   1. Wait until tomorrow (or change portfolio value)" -ForegroundColor White
Write-Host "   2. Run this script again to create a new snapshot" -ForegroundColor White
Write-Host "   3. Run: .\tests_pnl_today_smoke.ps1 to verify P&L calculation" -ForegroundColor White
Write-Host "   4. Open dashboard to see P&L Today displayed" -ForegroundColor White
Write-Host ""

# 4. Verify file was written
if (Test-Path $historyFile) {
    try {
        $history = Get-Content $historyFile -Raw | ConvertFrom-Json
        $newEntryCount = $history.Count

        Write-Host "Verification: History file updated" -ForegroundColor Green
        Write-Host "   Entries before: $existingEntries" -ForegroundColor DarkGray
        Write-Host "   Entries after:  $newEntryCount" -ForegroundColor White
        Write-Host "   File path:      $historyFile" -ForegroundColor DarkGray
    } catch {
        Write-Host "Could not verify file: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "History file not found after save" -ForegroundColor Yellow
}

Write-Host ""
