# reset_saxo_completely.ps1
# Nettoyage COMPLET de toutes les données Saxo + localStorage

Write-Host "🧹 RESET COMPLET SAXO - Démarrage..." -ForegroundColor Cyan
Write-Host ""

# 1. Supprimer les fichiers JSON de cache
Write-Host "📦 1. Suppression des caches JSON..." -ForegroundColor Yellow

$files_to_remove = @(
    "data\wealth\saxo_snapshot.json",
    "data\users\jack\saxobank\snapshots\latest.json",
    "data\users\jack\config.json"
)

foreach ($file in $files_to_remove) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        Write-Host "  ✅ Supprimé: $file" -ForegroundColor Green
    } else {
        Write-Host "  ⏭️  Absent: $file" -ForegroundColor Gray
    }
}

# 2. Vider tous les dossiers uploads/imports/snapshots pour Saxo
Write-Host ""
Write-Host "📁 2. Vidage des dossiers Saxo..." -ForegroundColor Yellow

$folders_to_clean = @(
    "data\users\jack\saxobank\uploads",
    "data\users\jack\saxobank\imports",
    "data\users\jack\saxobank\snapshots"
)

foreach ($folder in $folders_to_clean) {
    if (Test-Path $folder) {
        $count = (Get-ChildItem $folder -File -ErrorAction SilentlyContinue).Count
        if ($count -gt 0) {
            Remove-Item "$folder\*" -Force -Recurse -ErrorAction SilentlyContinue
            Write-Host "  ✅ Vidé: $folder ($count fichiers)" -ForegroundColor Green
        } else {
            Write-Host "  ✓ Déjà vide: $folder" -ForegroundColor Gray
        }
    } else {
        # Créer le dossier s'il n'existe pas
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        Write-Host "  ✨ Créé: $folder" -ForegroundColor Cyan
    }
}

# 3. Instructions pour localStorage
Write-Host ""
Write-Host "🌐 3. ÉTAPE MANUELLE REQUISE:" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Ouvrez la console du navigateur (F12) et copiez/collez ce code:" -ForegroundColor White
Write-Host ""

$jsCode = @"
// Nettoyer localStorage
Object.keys(localStorage).forEach(key => {
  if (key.includes('saxo') || key.includes('wealth') || key.includes('csv_selected_file')) {
    localStorage.removeItem(key);
    console.log('Supprimé:', key);
  }
});
console.log('✅ localStorage nettoyé');
"@

Write-Host $jsCode -ForegroundColor Cyan
Write-Host ""

# 4. Vérification finale
Write-Host ""
Write-Host "🔍 4. État final des dossiers..." -ForegroundColor Yellow
Write-Host ""

foreach ($folder in $folders_to_clean) {
    $count = (Get-ChildItem $folder -File -ErrorAction SilentlyContinue).Count
    Write-Host "  $folder : $count fichiers" -ForegroundColor $(if ($count -eq 0) { "Green" } else { "Yellow" })
}

# 5. Instructions de test
Write-Host ""
Write-Host "✅ NETTOYAGE TERMINÉ !" -ForegroundColor Green
Write-Host ""
Write-Host "📝 PROCHAINES ÉTAPES:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. ⚠️  IMPORTANT: Exécutez le code localStorage ci-dessus dans la console du navigateur" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. Rafraîchissez le dashboard Saxo (F5):" -ForegroundColor White
Write-Host "     http://localhost:8080/static/saxo-dashboard.html" -ForegroundColor Gray
Write-Host "     → Devrait afficher 'Aucun portfolio trouvé'" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Allez sur Sources Manager:" -ForegroundColor White
Write-Host "     http://localhost:8080/static/settings.html#tab-sources" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. Uploadez votre CSV Saxo dans la section 'Saxobank'" -ForegroundColor White
Write-Host ""
Write-Host "  5. Retournez sur le dashboard Saxo" -ForegroundColor White
Write-Host "     → Devrait maintenant afficher Tesla Inc., NVIDIA Corp., etc." -ForegroundColor Gray
Write-Host ""

# 6. Test de connectivité API
Write-Host ""
Write-Host "🔌 5. Test de connectivité API..." -ForegroundColor Yellow

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8080/api/saxo/portfolios" -Method GET -Headers @{"X-User"="jack"} -UseBasicParsing -ErrorAction Stop
    Write-Host "  ✅ API Saxo accessible (HTTP $($response.StatusCode))" -ForegroundColor Green

    $json = $response.Content | ConvertFrom-Json
    $count = if ($json.portfolios) { $json.portfolios.Count } else { 0 }
    Write-Host "  📊 Portfolios trouvés: $count" -ForegroundColor $(if ($count -eq 0) { "Yellow" } else { "Green" })

} catch {
    Write-Host "  ⚠️  API non accessible - Le serveur tourne-t-il ?" -ForegroundColor Red
    Write-Host "     Lancez: python -m uvicorn api.main:app --reload --port 8000" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
