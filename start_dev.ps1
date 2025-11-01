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

# Check virtual environment exists
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "`n❌ Virtual environment not found!" -ForegroundColor Red
    Write-Host "   Please create it first:" -ForegroundColor Yellow
    Write-Host "   1. python -m venv .venv" -ForegroundColor Gray
    Write-Host "   2. .venv\Scripts\Activate.ps1" -ForegroundColor Gray
    Write-Host "   3. pip install -r requirements.txt`n" -ForegroundColor Gray
    exit 1
}

# Check and start Redis
Write-Host "🔍 Checking Redis..." -ForegroundColor Cyan

# Try localhost first
$redisRunning = Test-NetConnection -ComputerName localhost -Port 6379 -InformationLevel Quiet -WarningAction SilentlyContinue
$redisHost = "localhost"

if ($redisRunning) {
    Write-Host "✅ Redis is running on localhost" -ForegroundColor Green
}
else {
    # Try WSL2 Redis
    try {
        wsl --status 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   Starting Redis via WSL2..." -ForegroundColor Gray

            # Auto-provide sudo password for WSL2
            $wslPassword = "Hgbdhgbd1"
            Write-Output $wslPassword | wsl -d Ubuntu bash -c "sudo -S service redis-server start" 2>$null

            # Get WSL2 IP address
            $wslIP = wsl -d Ubuntu hostname -I 2>$null | ForEach-Object { $_.Trim().Split()[0] }

            if ($wslIP) {
                Write-Host "   WSL2 IP: $wslIP" -ForegroundColor Gray

                # Wait for Redis to start and test WSL2 IP
                Start-Sleep -Milliseconds 500
                $redisRunning = Test-NetConnection -ComputerName $wslIP -Port 6379 -InformationLevel Quiet -WarningAction SilentlyContinue

                if ($redisRunning) {
                    Write-Host "✅ Redis started on WSL2" -ForegroundColor Green
                    $redisHost = $wslIP
                    # Override REDIS_URL to use WSL2 IP
                    $env:REDIS_URL = "redis://${wslIP}:6379/0"
                    Write-Host "   Using REDIS_URL=$env:REDIS_URL" -ForegroundColor Gray
                }
                else {
                    Write-Host "⚠️  Redis not accessible - server will run in degraded mode" -ForegroundColor Yellow
                }
            }
        }
        else {
            Write-Host "⚠️  WSL2 not available - Redis not started" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "⚠️  Could not start Redis - continuing without it" -ForegroundColor Yellow
    }
}

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
}
else {
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
    Write-Host "   • Crypto-Toolbox indicators (2x daily: 08:00, 20:00)" -ForegroundColor Gray
}
else {
    Write-Host "⏰ Task Scheduler: DISABLED" -ForegroundColor Yellow
    Write-Host "   Run manual scripts for P&L/OHLCV updates" -ForegroundColor Gray
}

# Reload mode
if ($UseReload) {
    Write-Host "🔄 Hot Reload: ENABLED" -ForegroundColor Green
}
else {
    Write-Host "🔄 Hot Reload: DISABLED" -ForegroundColor Yellow
    if ($EnableScheduler) {
        Write-Host "   (auto-disabled: prevents double execution with scheduler)" -ForegroundColor Gray
    }
    elseif ($CryptoToolboxMode -eq 1) {
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
}
else {
    $env:RUN_SCHEDULER = "0"
}

# Start server
Write-Host "�� Checking if port $Port is available..." -ForegroundColor Cyan
Start-Sleep -Milliseconds 200 # Brief pause to allow ports to be released

$portInUse = $null
try {
    $portInUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
}
catch {
    # Ignore errors, assume port is free
}

if ($portInUse) {
    Write-Host "`n❌ Port $Port is already in use by another process!" -ForegroundColor Red
    Write-Host "   Please stop the existing process or use a different port." -ForegroundColor Yellow
    Write-Host "   To find the process, run: Get-Process -Id (Get-NetTCPConnection -LocalPort $Port).OwningProcess" -ForegroundColor Gray
    Write-Host "   Example: .\\start_dev.ps1 -Port 8001`n" -ForegroundColor Gray
    exit 1
}

Write-Host "� Starting Uvicorn...`n" -ForegroundColor Cyan

if ($UseReload) {
    # For --reload, uvicorn handles the process lifetime, so '&' is fine.
    & .venv\Scripts\python.exe -m uvicorn api.main:app --reload --port $Port --workers $Workers 
}
else {
    # Without --reload, we must wait for the process to exit cleanly.
    # Start-Process -Wait ensures the PowerShell script doesn't exit prematurely.
    Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m uvicorn api.main:app --port $Port --workers $Workers" -NoNewWindow -Wait
}
