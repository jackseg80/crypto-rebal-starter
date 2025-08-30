# Script de test pour le Dashboard Portfolio Analytics
# Utilise des données de test (source=stub) pour démontrer les fonctionnalités

$BASE_URL = "http://localhost:8001"

Write-Host "=== Test Portfolio Analytics Dashboard ===" -ForegroundColor Green

# 1. Test de base - métriques avec données stub
Write-Host "`n1. Test métriques avec données de démo..." -ForegroundColor Yellow
$response = Invoke-RestMethod -Uri "$BASE_URL/portfolio/metrics?source=stub" -Method Get
Write-Host "Status: OK = $($response.ok)" -ForegroundColor Cyan
if ($response.ok) {
    $metrics = $response.metrics
    Write-Host "   - Valeur totale: `$$('{0:F2}' -f $metrics.total_value_usd)" -ForegroundColor White
    Write-Host "   - Nombre d'assets: $($metrics.asset_count)" -ForegroundColor White
    Write-Host "   - Score de diversité: $($metrics.diversity_score)/10" -ForegroundColor White
    Write-Host "   - Top holding: $($metrics.top_holding.symbol) ($('{0:P1}' -f $metrics.top_holding.percentage))" -ForegroundColor White
    Write-Host "   - Risque de concentration: $($metrics.concentration_risk)" -ForegroundColor White
    Write-Host "   - Groupes: $($metrics.group_count) différents" -ForegroundColor White
    
    if ($metrics.rebalance_recommendations.Count -gt 0) {
        Write-Host "   - Recommandations:" -ForegroundColor Magenta
        foreach ($rec in $metrics.rebalance_recommendations) {
            Write-Host "     * $rec" -ForegroundColor Gray
        }
    }
}

# 2. Test sauvegarde snapshot
Write-Host "`n2. Test sauvegarde snapshot..." -ForegroundColor Yellow
$response = Invoke-RestMethod -Uri "$BASE_URL/portfolio/snapshot?source=stub" -Method Post
Write-Host "Status: OK = $($response.ok)" -ForegroundColor Cyan
Write-Host "Message: $($response.message)" -ForegroundColor White

# 3. Attendre un moment puis sauver un autre snapshot pour tester la performance
Write-Host "`n3. Attente 2 secondes puis nouveau snapshot..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
$response = Invoke-RestMethod -Uri "$BASE_URL/portfolio/snapshot?source=stub" -Method Post

# 4. Test des métriques de performance
Write-Host "`n4. Test métriques après snapshot..." -ForegroundColor Yellow
$response = Invoke-RestMethod -Uri "$BASE_URL/portfolio/metrics?source=stub" -Method Get
if ($response.ok -and $response.performance.performance_available) {
    $perf = $response.performance
    Write-Host "   - Performance disponible: $($perf.performance_available)" -ForegroundColor Green
    Write-Host "   - Changement absolu: `$$('{0:F2}' -f $perf.absolute_change_usd)" -ForegroundColor White
    Write-Host "   - Changement %: $('{0:F2}' -f $perf.percentage_change)%" -ForegroundColor White
    Write-Host "   - Jours de suivi: $($perf.days_tracked)" -ForegroundColor White
    Write-Host "   - Status: $($perf.performance_status)" -ForegroundColor White
} else {
    Write-Host "   - Performance: $($response.performance.message)" -ForegroundColor Gray
}

# 5. Test données de tendance
Write-Host "`n5. Test données de tendance (30 jours)..." -ForegroundColor Yellow
$response = Invoke-RestMethod -Uri "$BASE_URL/portfolio/trend?days=30" -Method Get
Write-Host "Status: OK = $($response.ok)" -ForegroundColor Cyan
if ($response.ok) {
    $trend = $response.trend
    Write-Host "   - Jours disponibles: $($trend.days_available)" -ForegroundColor White
    Write-Host "   - Date la plus ancienne: $($trend.oldest_date)" -ForegroundColor White
    Write-Host "   - Date la plus récente: $($trend.newest_date)" -ForegroundColor White
}

# 6. Instructions pour tester le dashboard web
Write-Host "`n=== Instructions Dashboard Web ===" -ForegroundColor Green
Write-Host "Pour tester l'interface web:" -ForegroundColor Yellow
Write-Host "1. Assure-toi que le serveur tourne sur http://localhost:8001" -ForegroundColor White
Write-Host "2. Ouvre le fichier: static\dashboard.html dans ton navigateur" -ForegroundColor White
Write-Host "3. Le dashboard chargera automatiquement les données" -ForegroundColor White
Write-Host "4. Clique sur 'Actualiser' pour recharger les métriques" -ForegroundColor White
Write-Host ""
Write-Host "Fichier dashboard: file:///$(Get-Location)\static\dashboard.html" -ForegroundColor Cyan

Write-Host "`n=== Test terminé ===" -ForegroundColor Green