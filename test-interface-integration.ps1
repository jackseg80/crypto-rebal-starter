# Test de l'intégration avec l'interface (simulation des appels de l'Alias Manager)
# Usage: .\test-interface-integration.ps1

$base = "http://127.0.0.1:8000"

try { chcp 65001 | Out-Null } catch {}

Write-Host "🛠️  Test intégration interface Alias Manager" -ForegroundColor Cyan
Write-Host "=" * 55

# Test 1: Simulation bouton "🤖 Suggestions auto"
Write-Host "`n1️⃣  Simulation bouton 'Suggestions auto'..." -ForegroundColor Yellow
try {
    # Simule l'appel exact de l'interface (POST vide)
    $result = Invoke-RestMethod -Uri "$base/taxonomy/suggestions" -Method POST -Body "{}" -ContentType "application/json"
    
    Write-Host "✅ Réponse suggestions:" -ForegroundColor Green
    Write-Host "  Source: $($result.source)" -ForegroundColor Gray
    Write-Host "  Unknown count: $($result.unknown_count)" -ForegroundColor Gray
    Write-Host "  Auto-classified: $($result.auto_classified_count)" -ForegroundColor Gray
    Write-Host "  Coverage: $([math]::Round($result.coverage * 100, 1))%" -ForegroundColor Gray
    
    if ($result.note) {
        Write-Host "  📝 Note: $($result.note)" -ForegroundColor Yellow
    }
    
    if ($result.suggestions -and $result.suggestions.Count -gt 0) {
        Write-Host "  🎯 Suggestions:" -ForegroundColor Cyan
        foreach ($suggestion in $result.suggestions.GetEnumerator()) {
            Write-Host "    $($suggestion.Key) → $($suggestion.Value)" -ForegroundColor White
        }
    }
    
} catch {
    Write-Host "❌ Erreur suggestions: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "   Détails: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

# Test 2: Simulation bouton "🚀 Auto-classifier" 
Write-Host "`n2️⃣  Simulation bouton 'Auto-classifier'..." -ForegroundColor Yellow
try {
    $result = Invoke-RestMethod -Uri "$base/taxonomy/auto-classify" -Method POST -Body "{}" -ContentType "application/json"
    
    if ($result.ok) {
        Write-Host "✅ Auto-classification réussie:" -ForegroundColor Green
        Write-Host "  Message: $($result.message)" -ForegroundColor Gray
        Write-Host "  Classifiés: $($result.classified)" -ForegroundColor Gray
        Write-Host "  Source: $($result.source)" -ForegroundColor Gray
        
        if ($result.suggestions_applied -and $result.suggestions_applied.Count -gt 0) {
            Write-Host "  🎯 Classifications appliquées:" -ForegroundColor Cyan
            foreach ($applied in $result.suggestions_applied.GetEnumerator()) {
                Write-Host "    $($applied.Key) → $($applied.Value)" -ForegroundColor White
            }
        }
    } else {
        Write-Host "⚠️  Auto-classification refusée:" -ForegroundColor Yellow
        Write-Host "  Message: $($result.message)" -ForegroundColor Gray
    }
    
} catch {
    Write-Host "❌ Erreur auto-classification: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "   Détails: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

# Test 3: Données simulées
Write-Host "`n3️⃣  Test avec données simulées..." -ForegroundColor Yellow
try {
    $testData = @{
        sample_symbols = "DOGE,SHIB,USDT,USDC,ARB,RENDER,SAND,GAMETOKEN"
    } | ConvertTo-Json

    Write-Host "  📤 Envoi données test: DOGE,SHIB,USDT,USDC,ARB,RENDER,SAND,GAMETOKEN" -ForegroundColor Gray

    $suggestions = Invoke-RestMethod -Uri "$base/taxonomy/suggestions" -Method POST -Body $testData -ContentType "application/json"
    Write-Host "  ✅ Suggestions avec test data:" -ForegroundColor Green
    Write-Host "    Auto-classified: $($suggestions.auto_classified_count)/$($suggestions.unknown_count)" -ForegroundColor Cyan
    
    if ($suggestions.suggestions.Count -gt 0) {
        foreach ($suggestion in $suggestions.suggestions.GetEnumerator()) {
            Write-Host "    $($suggestion.Key) → $($suggestion.Value)" -ForegroundColor White
        }
    }
    
    $classify = Invoke-RestMethod -Uri "$base/taxonomy/auto-classify" -Method POST -Body $testData -ContentType "application/json"
    if ($classify.ok) {
        Write-Host "  ✅ Auto-classify avec test data: $($classify.classified) classifiés" -ForegroundColor Green
    }
    
} catch {
    Write-Host "❌ Erreur test données: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 4: État final de la taxonomy
Write-Host "`n4️⃣  État final de la taxonomy..." -ForegroundColor Yellow
try {
    $finalTaxonomy = Invoke-RestMethod -Uri "$base/taxonomy"
    Write-Host "✅ Taxonomy finale:" -ForegroundColor Green
    Write-Host "  Groupes: $($finalTaxonomy.groups.Count)" -ForegroundColor Gray
    Write-Host "  Aliases: $($finalTaxonomy.aliases.Count)" -ForegroundColor Gray
    Write-Host "  En mémoire: $($finalTaxonomy.storage.in_memory_count)" -ForegroundColor Gray
    
    $newGroups = $finalTaxonomy.groups | Where-Object { $_ -notin @("BTC", "ETH", "SOL", "Stablecoins", "Others") }
    if ($newGroups.Count -gt 0) {
        Write-Host "  🆕 Nouveaux groupes: $($newGroups -join ', ')" -ForegroundColor Cyan
    }
    
} catch {
    Write-Host "❌ Erreur taxonomy finale: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n" + "=" * 55
Write-Host "💡 Instructions pour debug interface:" -ForegroundColor Yellow
Write-Host "1. Ouvrez les DevTools du navigateur (F12)" -ForegroundColor Gray
Write-Host "2. Allez dans l'onglet Network/Réseau" -ForegroundColor Gray  
Write-Host "3. Cliquez sur les boutons dans l'Alias Manager" -ForegroundColor Gray
Write-Host "4. Vérifiez les requêtes HTTP et leurs réponses" -ForegroundColor Gray
Write-Host "5. Comparez avec les résultats de ces tests PowerShell" -ForegroundColor Gray
Write-Host "`n✅ Tests terminés !" -ForegroundColor Green
