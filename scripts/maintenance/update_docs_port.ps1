#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Update all documentation references from port 8000 to 8080

.DESCRIPTION
    This script updates all markdown files to change port references from 8000 to 8080
    to reflect the current working port configuration.

.EXAMPLE
    .\update_docs_port.ps1
#>

Write-Host "🔍 Searching for port 8000 references in documentation..." -ForegroundColor Cyan

# Find all markdown files containing port 8000
$files = Get-ChildItem -Path . -Recurse -Include "*.md" | Select-String -Pattern "8000" -List | Select-Object -ExpandProperty Path

Write-Host "📄 Found $($files.Count) files to update" -ForegroundColor Yellow

$updatedCount = 0

foreach ($file in $files) {
    Write-Host "🔄 Updating $file..." -ForegroundColor Gray
    
    $content = Get-Content $file -Raw
    $originalContent = $content
    
    # Replace port 8000 with 8080 in URLs
    $content = $content -replace 'http://localhost:8000', 'http://localhost:8080'
    $content = $content -replace 'http://127.0.0.1:8000', 'http://127.0.0.1:8080'
    $content = $content -replace 'localhost:8000', 'localhost:8080'
    $content = $content -replace '127.0.0.1:8000', '127.0.0.1:8080'
    
    # Replace port in configuration examples
    $content = $content -replace '--port 8000', '--port 8080'
    $content = $content -replace '-Port 8000', '-Port 8080'
    $content = $content -replace 'port 8000', 'port 8080'
    
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
Write-Host "   Files processed: $($files.Count)" -ForegroundColor Gray
Write-Host "   Files updated: $updatedCount" -ForegroundColor Green
Write-Host "`n🎯 Documentation now references port 8080" -ForegroundColor Cyan