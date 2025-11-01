# reset_saxo.ps1 - Version simplifiée sans JavaScript embarqué

Write-Host "=== NETTOYAGE SAXO ===" -ForegroundColor Cyan
Write-Host ""

# Supprimer les caches JSON
$files = @(
    "data\wealth\saxo_snapshot.json",
    "data\users\jack\saxobank\snapshots\latest.json",
    "data\users\jack\config.json"
)

Write-Host "Suppression des caches..." -ForegroundColor Yellow
foreach ($file in $files) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        Write-Host "  [OK] $file" -ForegroundColor Green
    }
}

# Vider les dossiers Saxo
$folders = @(
    "data\users\jack\saxobank\uploads",
    "data\users\jack\saxobank\imports",
    "data\users\jack\saxobank\snapshots"
)

Write-Host ""
Write-Host "Vidage des dossiers..." -ForegroundColor Yellow
foreach ($folder in $folders) {
    if (Test-Path $folder) {
        Remove-Item "$folder\*" -Force -Recurse -ErrorAction SilentlyContinue
        Write-Host "  [OK] $folder" -ForegroundColor Green
    }
}

# Test API
Write-Host ""
Write-Host "Test API..." -ForegroundColor Yellow
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8080/api/saxo/portfolios" -Headers @{"X-User"="jack"} -UseBasicParsing
    Write-Host "  [OK] API accessible" -ForegroundColor Green
} catch {
    Write-Host "  [!!] API non accessible" -ForegroundColor Red
}

# Instructions
Write-Host ""
Write-Host "=== A FAIRE MAINTENANT ===" -ForegroundColor Magenta
Write-Host ""
Write-Host "1. Console navigateur (F12):" -ForegroundColor White
Write-Host ""
Write-Host "   localStorage.clear();" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Recharger: http://localhost:8080/static/saxo-dashboard.html" -ForegroundColor White
Write-Host ""
Write-Host "3. Uploader CSV: http://localhost:8080/static/settings.html#tab-sources" -ForegroundColor White
Write-Host ""
