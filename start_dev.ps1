#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start crypto-rebal development server with optional features

.DESCRIPTION
    Starts Uvicorn server with configurable options:
    - Crypto-Toolbox: 0=Flask proxy (legacy), 1=FastAPI native (Playwright)
    - Scheduler: Enable/disable periodic tasks (P&L snapshots, OHLCV updates)
    - Reload: Enable/disable hot reload (auto-disabled with Scheduler or Playwright)

.PARAMETER CryptoToolboxMode
    Crypto-Toolbox mode: 0=Flask proxy (legacy), 1=FastAPI native (new)

.PARAMETER EnableScheduler
    Enable task scheduler (P&L snapshots, OHLCV updates, warmers)
    Note: Disables hot reload to prevent double execution

.PARAMETER Reload
    Enable hot reload (--reload flag). Auto-disabled if Scheduler or Playwright enabled.

.PARAMETER Port
    Server port (default: 8000)

.PARAMETER Workers
    Uvicorn workers (default: 1, REQUIRED for Playwright mode)

.EXAMPLE
    .\start_dev.ps1
    # Start with FastAPI native, no scheduler, hot reload enabled

.EXAMPLE
    .\start_dev.ps1 -EnableScheduler
    # Start with scheduler enabled (no hot reload)

.EXAMPLE
    .\start_dev.ps1 -CryptoToolboxMode 0 -Reload
    # Start with Flask proxy and hot reload

.EXAMPLE
    .\start_dev.ps1 -EnableScheduler -Port 8001
    # Start with scheduler on custom port
#>

param(
    [int]$CryptoToolboxMode = $(if ($env:CRYPTO_TOOLBOX_NEW) { [int]$env:CRYPTO_TOOLBOX_NEW } else { 1 }),
    [switch]$EnableScheduler = $false,
    [switch]$Reload = $false,
    [int]$Port = 8000,
    [int]$Workers = 1
)

# Validate Playwright installation if using new mode
if ($CryptoToolboxMode -eq 1) {
    Write-Host "🎭 Checking Playwright installation..." -ForegroundColor Cyan

    $playwrightCheck = & .venv\Scripts\python.exe -c "try:
    from playwright.async_api import async_playwright
    print('OK')
except ImportError:
    print('MISSING')" 2>$null

    if ($playwrightCheck -ne "OK") {
        Write-Host "❌ Playwright not installed!" -ForegroundColor Red
        Write-Host "   Install with: pip install playwright && playwright install chromium" -ForegroundColor Yellow
        exit 1
    }

    Write-Host "✅ Playwright ready" -ForegroundColor Green
}

# Determine reload mode
$UseReload = $Reload -and -not $EnableScheduler -and ($CryptoToolboxMode -ne 1)

# Display configuration
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "🚀 Starting Crypto Rebal Development Server" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue

# Crypto-Toolbox mode
if ($CryptoToolboxMode -eq 1) {
    Write-Host "📦 Crypto-Toolbox: FastAPI native (Playwright)" -ForegroundColor Green
} else {
    Write-Host "📦 Crypto-Toolbox: Flask proxy (legacy)" -ForegroundColor Yellow
    Write-Host "   ⚠️  Make sure Flask server is running on port 8001" -ForegroundColor Yellow
}

# Scheduler mode
if ($EnableScheduler) {
    Write-Host "⏰ Task Scheduler: ENABLED" -ForegroundColor Green
    Write-Host "   • P&L snapshots (intraday 15min, EOD 23:59)" -ForegroundColor Gray
    Write-Host "   • OHLCV updates (daily 03:10, hourly :05)" -ForegroundColor Gray
    Write-Host "   • Staleness monitor (hourly :15)" -ForegroundColor Gray
    Write-Host "   • API warmers (every 10min)" -ForegroundColor Gray
} else {
    Write-Host "⏰ Task Scheduler: DISABLED" -ForegroundColor Yellow
    Write-Host "   Run manual scripts for P&L/OHLCV updates" -ForegroundColor Gray
}

# Reload mode
if ($UseReload) {
    Write-Host "🔄 Hot Reload: ENABLED" -ForegroundColor Green
} else {
    Write-Host "🔄 Hot Reload: DISABLED" -ForegroundColor Yellow
    if ($EnableScheduler) {
        Write-Host "   (auto-disabled: prevents double execution with scheduler)" -ForegroundColor Gray
    } elseif ($CryptoToolboxMode -eq 1) {
        Write-Host "   (auto-disabled: required for Playwright on Windows)" -ForegroundColor Gray
    }
}

Write-Host "`n🌐 Server: http://localhost:$Port" -ForegroundColor Cyan
Write-Host "📚 API Docs: http://localhost:$Port/docs" -ForegroundColor Cyan
Write-Host "🩺 Scheduler Health: http://localhost:$Port/api/scheduler/health" -ForegroundColor Cyan
Write-Host "👷 Workers: $Workers $(if ($Workers -eq 1) { '(required for Playwright)' })" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Blue

# Set environment variables
$env:CRYPTO_TOOLBOX_NEW = $CryptoToolboxMode

if ($EnableScheduler) {
    $env:RUN_SCHEDULER = "1"
    Write-Host "✅ Environment: RUN_SCHEDULER=1" -ForegroundColor Green
} else {
    $env:RUN_SCHEDULER = "0"
}

# Start server
Write-Host "🚀 Starting Uvicorn...`n" -ForegroundColor Cyan

if ($UseReload) {
    & .venv\Scripts\python.exe -m uvicorn api.main:app --reload --port $Port --workers $Workers
} else {
    & .venv\Scripts\python.exe -m uvicorn api.main:app --port $Port --workers $Workers
}
