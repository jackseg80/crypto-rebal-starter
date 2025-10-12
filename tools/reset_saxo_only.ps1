# reset_saxo_only.ps1 - Nettoie UNIQUEMENT les données Saxo (préserve le reste)

Write-Host "=== NETTOYAGE SAXO UNIQUEMENT ===" -ForegroundColor Cyan
Write-Host ""

# 1. Nettoyer le fichier config.json de Jack (seulement csv_selected_file si c'est Saxo)
$configPath = "data\users\jack\config.json"
if (Test-Path $configPath) {
    Write-Host "Nettoyage config utilisateur..." -ForegroundColor Yellow

    $config = Get-Content $configPath -Raw | ConvertFrom-Json

    # Si csv_selected_file contient "Positions" ou "saxo", le supprimer
    if ($config.csv_selected_file -and ($config.csv_selected_file -like "*Position*" -or $config.csv_selected_file -like "*saxo*")) {
        Write-Host "  [CLEAN] csv_selected_file: $($config.csv_selected_file)" -ForegroundColor Yellow
        $config.PSObject.Properties.Remove('csv_selected_file')

        # Sauvegarder la config modifiée
        $config | ConvertTo-Json -Depth 10 | Set-Content $configPath
        Write-Host "  [OK] Config mise à jour (Saxo CSV supprimé)" -ForegroundColor Green
    } else {
        Write-Host "  [SKIP] Pas de référence Saxo dans config" -ForegroundColor Gray
    }
}

# 2. Supprimer les caches JSON Saxo
$saxoFiles = @(
    "data\wealth\saxo_snapshot.json",
    "data\users\jack\saxobank\snapshots\latest.json"
)

Write-Host ""
Write-Host "Suppression caches Saxo..." -ForegroundColor Yellow
foreach ($file in $saxoFiles) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        Write-Host "  [OK] $file" -ForegroundColor Green
    } else {
        Write-Host "  [SKIP] $file (absent)" -ForegroundColor Gray
    }
}

# 3. Vider les dossiers Saxo uniquement
$saxoFolders = @(
    "data\users\jack\saxobank\uploads",
    "data\users\jack\saxobank\imports",
    "data\users\jack\saxobank\snapshots"
)

Write-Host ""
Write-Host "Vidage dossiers Saxo..." -ForegroundColor Yellow
foreach ($folder in $saxoFolders) {
    if (Test-Path $folder) {
        $count = (Get-ChildItem $folder -File -ErrorAction SilentlyContinue).Count
        if ($count -gt 0) {
            Remove-Item "$folder\*" -Force -Recurse -ErrorAction SilentlyContinue
            Write-Host "  [OK] $folder ($count fichiers)" -ForegroundColor Green
        } else {
            Write-Host "  [SKIP] $folder (déjà vide)" -ForegroundColor Gray
        }
    }
}

# 4. Vérification que les données crypto sont intactes
Write-Host ""
Write-Host "Vérification données crypto..." -ForegroundColor Yellow

$cryptoFolders = @(
    "data\users\jack\cointracking\uploads",
    "data\users\jack\cointracking\imports",
    "data\users\jack\cointracking\snapshots"
)

foreach ($folder in $cryptoFolders) {
    if (Test-Path $folder) {
        $count = (Get-ChildItem $folder -File -ErrorAction SilentlyContinue).Count
        Write-Host "  [OK] $folder : $count fichiers (préservés)" -ForegroundColor Cyan
    }
}

# 5. Test API
Write-Host ""
Write-Host "Test API..." -ForegroundColor Yellow
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/saxo/portfolios" -Headers @{"X-User"="jack"} -UseBasicParsing
    Write-Host "  [OK] API accessible" -ForegroundColor Green
} catch {
    Write-Host "  [!!] API non accessible" -ForegroundColor Red
}

# 6. Résumé
Write-Host ""
Write-Host "=== RÉSUMÉ ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Nettoyé :" -ForegroundColor Green
Write-Host "  [OK] Fichiers Saxo (uploads/imports/snapshots)"
Write-Host "  [OK] Caches JSON Saxo"
Write-Host "  [OK] Référence CSV Saxo dans config"
Write-Host ""
Write-Host "Préservé :" -ForegroundColor Cyan
Write-Host "  [OK] Clés API (CoinGecko, CoinTracking, FRED)"
Write-Host "  [OK] Préférences utilisateur (thème, devise)"
Write-Host "  [OK] Données crypto (cointracking/*)"
Write-Host "  [OK] Toutes autres configs"
Write-Host ""
Write-Host "=== PROCHAINES ÉTAPES ===" -ForegroundColor Magenta
Write-Host ""
Write-Host "1. Console navigateur (F12):" -ForegroundColor White
Write-Host ""
Write-Host "   // Nettoyer uniquement localStorage Saxo" -ForegroundColor Cyan
Write-Host "   Object.keys(localStorage).forEach(k => {" -ForegroundColor Cyan
Write-Host "     if (k.includes('saxo') || k.includes('wealth')) {" -ForegroundColor Cyan
Write-Host "       localStorage.removeItem(k);" -ForegroundColor Cyan
Write-Host "       console.log('Supprimé:', k);" -ForegroundColor Cyan
Write-Host "     }" -ForegroundColor Cyan
Write-Host "   });" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Recharger: http://localhost:8000/static/settings.html#tab-sources" -ForegroundColor White
Write-Host ""
Write-Host "3. Uploader votre CSV Saxo (section Saxobank)" -ForegroundColor White
Write-Host ""
