#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Update all Python files references from port 8000 to 8080

.DESCRIPTION
    This script updates all Python files to change port references from 8000 to 8080
    to reflect the current working port configuration.

.EXAMPLE
    .\update_python_port.ps1
#>

Write-Host "🔍 Searching for port 8000 references in Python files..." -ForegroundColor Cyan

# Find all Python files containing port 8000
$files = Get-ChildItem -Path . -Recurse -Include "*.py" | Select-String -Pattern "8000" -List | Select-Object -ExpandProperty Path

Write-Host "📄 Found $($files.Count) Python files to update" -ForegroundColor Yellow

$updatedCount = 0

foreach ($file in $files) {
    Write-Host "🔄 Updating $file..." -ForegroundColor Gray
    
    $content = Get-Content $file -Raw
    $originalContent = $content
    
    # Replace port 8000 with 8080 in URLs and configurations
    $content = $content -replace 'http://localhost:8000', 'http://localhost:8080'
    $content = $content -replace 'http://127.0.0.1:8000', 'http://127.0.0.1:8080'
    $content = $content -replace 'localhost:8000', 'localhost:8080'
    $content = $content -replace '127.0.0.1:8000', '127.0.0.1:8080'
    
    # Replace port in configuration examples and defaults
    $content = $content -replace '--port 8000', '--port 8080'
    $content = $content -replace 'port=8000', 'port=8080'
    $content = $content -replace 'port 8000', 'port 8080'
    $content = $content -replace 'port: int = Field\(default=8000', 'port: int = Field(default=8080'
    
    # Replace in BASE_URL constants
    $content = $content -replace 'BASE_URL = "http://localhost:8000"', 'BASE_URL = "http://localhost:8080"'
    $content = $content -replace 'BASE_URL = "http://127.0.0.1:8000"', 'BASE_URL = "http://127.0.0.1:8080"'
    
    # Replace in API_BASE constants
    $content = $content -replace 'API_BASE = "http://localhost:8000"', 'API_BASE = "http://localhost:8080"'
    $content = $content -replace 'API_BASE = "http://127.0.0.1:8000"', 'API_BASE = "http://127.0.0.1:8080"'
    
    # Replace in base_url parameters
    $content = $content -replace 'base_url: str = "http://localhost:8000"', 'base_url: str = "http://localhost:8080"'
    
    if ($content -ne $originalContent) {
        Set-Content -Path $file -Value $content
        $updatedCount++
        Write-Host "✅ Updated $file" -ForegroundColor Green
    }
    else {
        Write-Host "⚠️  No changes needed for $file" -ForegroundColor Yellow
    }
}

Write-Host "`n📊 Summary:" -ForegroundColor Cyan
Write-Host "   Python files processed: $($files.Count)" -ForegroundColor Gray
Write-Host "   Python files updated: $updatedCount" -ForegroundColor Green
Write-Host "`n🎯 Python files now reference port 8080" -ForegroundColor Cyan