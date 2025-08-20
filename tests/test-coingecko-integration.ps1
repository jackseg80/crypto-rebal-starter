# Test de l'intégration CoinGecko pour l'enrichissement des classifications
# Usage: .\test-coingecko-integration.ps1

$base = "http://127.0.0.1:8000"

try { chcp 65001 | Out-Null } catch {}

Write-Host "🥷 Test de l'intégration CoinGecko" -ForegroundColor Cyan
Write-Host "=" * 55

# Test 1: Vérifier les statistiques CoinGecko
Write-Host "`n1️⃣  Vérification des statistiques CoinGecko..." -ForegroundColor Yellow
try {
    $stats = Invoke-RestMethod -Uri "$base/taxonomy/coingecko-stats"
    
    if ($stats.ok) {
        Write-Host "✅ Service CoinGecko actif:" -ForegroundColor Green
        Write-Host "  Cache symbols: $($stats.stats.cache_stats.symbols_cached)" -ForegroundColor Gray
        Write-Host "  Cache categories: $($stats.stats.cache_stats.categories_cached)" -ForegroundColor Gray
        Write-Host "  Cache metadata: $($stats.stats.cache_stats.metadata_cached)" -ForegroundColor Gray
        Write-Host "  Appels dernière minute: $($stats.stats.api_stats.calls_last_minute)" -ForegroundColor Gray
        Write-Host "  Rate limit: $($stats.stats.api_stats.rate_limit)" -ForegroundColor Gray
        Write-Host "  API Key configurée: $($stats.stats.api_stats.has_api_key)" -ForegroundColor Gray
        Write-Host "  Catégories supportées: $($stats.stats.mapping_stats.supported_categories)" -ForegroundColor Gray
    } else {
        Write-Host "❌ Erreur service CoinGecko: $($stats.error)" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Erreur stats CoinGecko: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Test d'enrichissement direct (sans patterns regex)
Write-Host "`n2️⃣  Test enrichissement direct CoinGecko..." -ForegroundColor Yellow
try {
    $testData = @{
        sample_symbols = "LINK,AAVE,UNI,COMP,CRV,SUSHI,1INCH,THETA,FLOW,CHZ"
    } | ConvertTo-Json
    
    Write-Host "  📤 Test symboles: LINK,AAVE,UNI,COMP,CRV,SUSHI,1INCH,THETA,FLOW,CHZ" -ForegroundColor Gray
    
    $enrichment = Invoke-RestMethod -Uri "$base/taxonomy/enrich-from-coingecko" -Method POST -Body $testData -ContentType "application/json"
    
    if ($enrichment.ok) {
        Write-Host "  ✅ Enrichissement CoinGecko réussi:" -ForegroundColor Green
        Write-Host "    Total demandé: $($enrichment.total_requested)" -ForegroundColor Cyan
        Write-Host "    CoinGecko classifié: $($enrichment.coingecko_classified)" -ForegroundColor Cyan
        Write-Host "    Coverage: $([math]::Round($enrichment.coverage * 100, 1))%" -ForegroundColor Cyan
        
        if ($enrichment.classifications.Count -gt 0) {
            Write-Host "  🎯 Classifications CoinGecko:" -ForegroundColor Cyan
            foreach ($classification in $enrichment.classifications.GetEnumerator()) {
                Write-Host "    $($classification.Key) → $($classification.Value)" -ForegroundColor White
            }
        }
        
        if ($enrichment.unclassified.Count -gt 0) {
            Write-Host "  ❓ Non classifiés: $($enrichment.unclassified -join ', ')" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ❌ Enrichissement échoué: $($enrichment.message)" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Erreur enrichissement: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 3: Comparaison suggestions regex vs enrichies
Write-Host "`n3️⃣  Comparaison regex vs CoinGecko..." -ForegroundColor Yellow
try {
    $testSymbols = "MATIC,POLYGON,ARBITRUM,OPTIMISM,STARGATE,CURVE,CHAINLINK"
    $testData = @{
        sample_symbols = $testSymbols
    } | ConvertTo-Json
    
    # Suggestions regex (anciennes)
    Write-Host "  📊 Suggestions regex seules:" -ForegroundColor Gray
    $regexSuggestions = Invoke-RestMethod -Uri "$base/taxonomy/suggestions" -Method POST -Body $testData -ContentType "application/json"
    Write-Host "    Coverage regex: $([math]::Round($regexSuggestions.coverage * 100, 1))% ($($regexSuggestions.auto_classified_count)/$($regexSuggestions.unknown_count))" -ForegroundColor Gray
    
    # Suggestions enrichies (nouvelles)
    Write-Host "  🚀 Suggestions enrichies (regex + CoinGecko):" -ForegroundColor Gray
    $enhancedSuggestions = Invoke-RestMethod -Uri "$base/taxonomy/suggestions-enhanced" -Method POST -Body $testData -ContentType "application/json"
    Write-Host "    Coverage enrichie: $([math]::Round($enhancedSuggestions.coverage * 100, 1))% ($($enhancedSuggestions.auto_classified_count)/$($enhancedSuggestions.unknown_count))" -ForegroundColor Gray
    
    # Comparaison
    if ($enhancedSuggestions.coverage -gt $regexSuggestions.coverage) {
        $improvement = ($enhancedSuggestions.coverage - $regexSuggestions.coverage) * 100
        Write-Host "  📈 Amélioration: +$([math]::Round($improvement, 1))% de précision avec CoinGecko!" -ForegroundColor Green
    } else {
        Write-Host "  📊 Même performance que regex seul" -ForegroundColor Yellow
    }
    
    # Détails des classifications
    Write-Host "  🔍 Classifications enrichies:" -ForegroundColor Cyan
    foreach ($suggestion in $enhancedSuggestions.suggestions.GetEnumerator()) {
        $inRegex = $regexSuggestions.suggestions.ContainsKey($suggestion.Key)
        $marker = if ($inRegex) { "📝" } else { "🆕" }
        Write-Host "    $marker $($suggestion.Key) → $($suggestion.Value)" -ForegroundColor White
    }
    
} catch {
    Write-Host "❌ Erreur comparaison: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 4: Auto-classification enrichie
Write-Host "`n4️⃣  Test auto-classification enrichie..." -ForegroundColor Yellow
try {
    $testData = @{
        sample_symbols = "MKR,COMP,YFI,SUSHI,CRV,BAL,SNX"
    } | ConvertTo-Json
    
    $autoClassify = Invoke-RestMethod -Uri "$base/taxonomy/auto-classify-enhanced" -Method POST -Body $testData -ContentType "application/json"
    
    if ($autoClassify.ok) {
        Write-Host "  ✅ Auto-classification enrichie réussie:" -ForegroundColor Green
        Write-Host "    Message: $($autoClassify.message)" -ForegroundColor Gray
        Write-Host "    Classifiés: $($autoClassify.classified)" -ForegroundColor Gray
        Write-Host "    Enhanced: $($autoClassify.enhanced)" -ForegroundColor Gray
        Write-Host "    CoinGecko enabled: $($autoClassify.coingecko_enabled)" -ForegroundColor Gray
        
        if ($autoClassify.suggestions_applied.Count -gt 0) {
            Write-Host "  🎯 Classifications appliquées:" -ForegroundColor Cyan
            foreach ($applied in $autoClassify.suggestions_applied.GetEnumerator()) {
                Write-Host "    $($applied.Key) → $($applied.Value)" -ForegroundColor White
            }
        }
    } else {
        Write-Host "  ⚠️ Auto-classification refusée: $($autoClassify.message)" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ Erreur auto-classification: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 5: État final de la taxonomy
Write-Host "`n5️⃣  État final après enrichissement..." -ForegroundColor Yellow
try {
    $finalTaxonomy = Invoke-RestMethod -Uri "$base/taxonomy"
    Write-Host "✅ Taxonomy finale:" -ForegroundColor Green
    Write-Host "  Groupes: $($finalTaxonomy.groups.Count)" -ForegroundColor Gray
    Write-Host "  Aliases: $($finalTaxonomy.aliases.Count)" -ForegroundColor Gray
    Write-Host "  En mémoire: $($finalTaxonomy.storage.in_memory_count)" -ForegroundColor Gray
    
    # Compter les aliases DeFi ajoutés
    $defiAliases = 0
    foreach ($alias in $finalTaxonomy.aliases.GetEnumerator()) {
        if ($alias.Value -eq "DeFi") { $defiAliases++ }
    }
    
    if ($defiAliases -gt 0) {
        Write-Host "  🏦 Aliases DeFi détectés: $defiAliases" -ForegroundColor Cyan
    }
    
} catch {
    Write-Host "❌ Erreur taxonomy finale: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n" + "=" * 55
Write-Host "💡 Notes importantes:" -ForegroundColor Yellow
Write-Host "- CoinGecko Demo API: 30 appels/minute, 10k/mois" -ForegroundColor Gray
Write-Host "- Pour production: ajouter COINGECKO_API_KEY dans .env" -ForegroundColor Gray
Write-Host "- Le service cache les données 5 minutes (TTL)" -ForegroundColor Gray
Write-Host "- Rate limiting automatique implémenté" -ForegroundColor Gray
Write-Host "`n✅ Tests CoinGecko terminés !" -ForegroundColor Green