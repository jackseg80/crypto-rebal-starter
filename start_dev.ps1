#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start crypto-rebal development server with optional Crypto-Toolbox mode

.DESCRIPTION
    Starts Uvicorn server with configurable CRYPTO_TOOLBOX_NEW flag:
    - 0: Legacy Flask proxy (requires separate Flask server on port 8001)
    - 1 (default): FastAPI native Playwright scraper (requires playwright install)

.PARAMETER CryptoToolboxMode
    Crypto-Toolbox mode: 0=Flask proxy (legacy), 1=FastAPI native (new)

.PARAMETER Port
    Server port (default: 8000)

.PARAMETER Workers
    Uvicorn workers (default: 1, REQUIRED for Playwright mode)

.EXAMPLE
    .\start_dev.ps1
    # Start with FastAPI native (default)

.EXAMPLE
    .\start_dev.ps1 -CryptoToolboxMode 0
    # Start with Flask proxy (legacy fallback)

.EXAMPLE
    $env:CRYPTO_TOOLBOX_NEW=1; .\start_dev.ps1
    # Use environment variable
#>

param(
    [int]$CryptoToolboxMode = $(if ($env:CRYPTO_TOOLBOX_NEW) { [int]$env:CRYPTO_TOOLBOX_NEW } else { 1 }),
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

# Display configuration
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "🚀 Starting Crypto Rebal Development Server" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue

if ($CryptoToolboxMode -eq 1) {
    Write-Host "📦 Crypto-Toolbox: FastAPI native (Playwright)" -ForegroundColor Green
} else {
    Write-Host "📦 Crypto-Toolbox: Flask proxy (legacy)" -ForegroundColor Yellow
    Write-Host "   ⚠️  Make sure Flask server is running on port 8001" -ForegroundColor Yellow
}

Write-Host "🌐 Server: http://localhost:$Port" -ForegroundColor Cyan
Write-Host "📚 API Docs: http://localhost:$Port/docs" -ForegroundColor Cyan
Write-Host "👷 Workers: $Workers $(if ($Workers -eq 1) { '(required for Playwright)' })" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Blue

# Set environment variable
$env:CRYPTO_TOOLBOX_NEW = $CryptoToolboxMode

# Start server
# Note: --reload disabled for Playwright mode on Windows (asyncio subprocess incompatibility)
if ($CryptoToolboxMode -eq 1) {
    Write-Host "⚠️  Hot reload disabled (required for Playwright on Windows)" -ForegroundColor Yellow
    & .venv\Scripts\python.exe -m uvicorn api.main:app --port $Port --workers $Workers
} else {
    & .venv\Scripts\python.exe -m uvicorn api.main:app --reload --port $Port --workers $Workers
}
