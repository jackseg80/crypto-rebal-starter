# Test du système de classification automatique
# Usage: .\test-auto-classification.ps1

$base = "http://127.0.0.1:8000"

Write-Host "🧪 Tests du système de classification automatique" -ForegroundColor Cyan
Write-Host "=" * 60

# Test 1: Vérifier l'API de base
Write-Host "`n1️⃣  Test de connexion API..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$base/healthz"
    Write-Host "✅ API disponible: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "❌ API non disponible: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Taxonomy de base
Write-Host "`n2️⃣  Test taxonomy de base..." -ForegroundColor Yellow
try {
    $taxonomy = Invoke-RestMethod -Uri "$base/taxonomy"
    $groupsCount = $taxonomy.groups.Count
    $aliasesCount = $taxonomy.aliases.Count
    Write-Host "✅ Groupes: $groupsCount | Aliases: $aliasesCount" -ForegroundColor Green
    Write-Host "   Groupes: $($taxonomy.groups -join ', ')" -ForegroundColor Gray
} catch {
    Write-Host "❌ Erreur taxonomy: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 3: Suggestions avec symboles de test
Write-Host "`n3️⃣  Test suggestions avec échantillons..." -ForegroundColor Yellow
$testSymbols = "DOGE,SHIB,PEPE,BONK,ARBUSDT,USDX,GAMEFI,RENDER,AITOKEN,NFTCOIN"
try {
    $suggestions = Invoke-RestMethod -Uri "$base/taxonomy/suggestions?sample_symbols=$testSymbols"
    Write-Host "✅ Suggestions générées:" -ForegroundColor Green
    Write-Host "   Source: $($suggestions.source)" -ForegroundColor Gray
    Write-Host "   Unknown count: $($suggestions.unknown_count)" -ForegroundColor Gray
    Write-Host "   Auto-classified: $($suggestions.auto_classified_count)" -ForegroundColor Gray
    Write-Host "   Coverage: $([math]::Round($suggestions.coverage * 100, 1))%" -ForegroundColor Gray
    
    if ($suggestions.suggestions.Count -gt 0) {
        Write-Host "   Suggestions:" -ForegroundColor Gray
        foreach ($suggestion in $suggestions.suggestions.GetEnumerator()) {
            Write-Host "     $($suggestion.Key) → $($suggestion.Value)" -ForegroundColor Cyan
        }
    } else {
        Write-Host "   ⚠️  Aucune suggestion trouvée" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Erreur suggestions: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 4: Auto-classification avec échantillons
Write-Host "`n4️⃣  Test auto-classification avec échantillons..." -ForegroundColor Yellow
try {
    $body = @{
        sample_symbols = $testSymbols
    } | ConvertTo-Json
    
    $result = Invoke-RestMethod -Uri "$base/taxonomy/auto-classify" -Method POST -Body $body -ContentType "application/json"
    
    if ($result.ok) {
        Write-Host "✅ Auto-classification réussie:" -ForegroundColor Green
        Write-Host "   Message: $($result.message)" -ForegroundColor Gray
        Write-Host "   Classifiés: $($result.classified)" -ForegroundColor Gray
        Write-Host "   Source: $($result.source)" -ForegroundColor Gray
        
        if ($result.suggestions_applied.Count -gt 0) {
            Write-Host "   Classifications appliquées:" -ForegroundColor Gray
            foreach ($applied in $result.suggestions_applied.GetEnumerator()) {
                Write-Host "     $($applied.Key) → $($applied.Value)" -ForegroundColor Cyan
            }
        }
    } else {
        Write-Host "⚠️  Auto-classification échouée: $($result.message)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Erreur auto-classification: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Détails: $($_.ErrorDetails.Message)" -ForegroundColor Red
}

# Test 5: Vérification des nouveaux aliases ajoutés
Write-Host "`n5️⃣  Vérification des aliases après classification..." -ForegroundColor Yellow
try {
    $taxonomyAfter = Invoke-RestMethod -Uri "$base/taxonomy"
    $newAliasesCount = $taxonomyAfter.aliases.Count
    Write-Host "✅ Aliases après classification: $newAliasesCount" -ForegroundColor Green
    
    # Montrer quelques nouveaux aliases
    $testSymbolsArray = $testSymbols -split ","
    $foundAliases = @()
    foreach ($symbol in $testSymbolsArray) {
        $symbol = $symbol.Trim().ToUpper()
        if ($taxonomyAfter.aliases.$symbol) {
            $foundAliases += "$symbol → $($taxonomyAfter.aliases.$symbol)"
        }
    }
    
    if ($foundAliases.Count -gt 0) {
        Write-Host "   Nouveaux aliases trouvés:" -ForegroundColor Gray
        foreach ($alias in $foundAliases) {
            Write-Host "     $alias" -ForegroundColor Cyan
        }
    }
} catch {
    Write-Host "❌ Erreur vérification: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 6: Cache des unknown aliases (après génération d'un plan)
Write-Host "`n6️⃣  Test cache unknown aliases..." -ForegroundColor Yellow
try {
    $cacheTest = Invoke-RestMethod -Uri "$base/taxonomy/suggestions"
    Write-Host "✅ Cache unknown aliases:" -ForegroundColor Green
    Write-Host "   Source: $($cacheTest.source)" -ForegroundColor Gray
    Write-Host "   Unknown count: $($cacheTest.unknown_count)" -ForegroundColor Gray
    
    if ($cacheTest.cached_unknowns.Count -gt 0) {
        Write-Host "   Cached unknowns: $($cacheTest.cached_unknowns -join ', ')" -ForegroundColor Cyan
    } else {
        Write-Host "   ⚠️  Cache vide - générez un plan de rebalancement d'abord" -ForegroundColor Yellow
    }
    
    if ($cacheTest.note) {
        Write-Host "   Note: $($cacheTest.note)" -ForegroundColor Gray
    }
} catch {
    Write-Host "❌ Erreur cache: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n" + "=" * 60
Write-Host "✅ Tests terminés !" -ForegroundColor Green
Write-Host "💡 Pour tester avec de vrais unknown aliases:" -ForegroundColor Yellow
Write-Host "   1. Générez un plan de rebalancement via l'interface" -ForegroundColor Gray
Write-Host "   2. Relancez: .\test-auto-classification.ps1" -ForegroundColor Gray