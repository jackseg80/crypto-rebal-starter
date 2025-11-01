# Test des patterns de classification automatique
# Usage: .\test-patterns.ps1

$base = "http://127.0.0.1:8080"

# (Optionnel) Forcer l'affichage correct en console
try { chcp 65001 | Out-Null } catch {}

Write-Host "Test des patterns de classification" -ForegroundColor Cyan
Write-Host ("=" * 50)

# Définir les échantillons par catégorie
$patterns = @{
    "Stablecoins" = @("USDT", "USDC", "DAI", "BUSD", "TUSD", "USDX", "FRAX");
    "L2/Scaling"  = @("ARB", "ARBITRUM", "OP", "MATIC", "POL3", "STRK2", "POLYGON");
    "Memecoins"   = @("DOGE", "DOGECOIN", "SHIB", "PEPE", "BONK", "WIF", "FLOKI", "MEMECOIN", "SAFEMOON");
    "AI/Data"     = @("AI", "GPT", "RENDER", "FET", "OCEAN", "GRT", "AITOKEN", "GPTCOIN");
    "Gaming/NFT"  = @("GAME", "NFT", "SAND", "MANA", "AXS", "ENJ", "GALA", "GAMEFI", "NFTCOIN");
}

foreach ($category in $patterns.Keys) {
    Write-Host ""
    Write-Host ("Test catégorie: {0}" -f $category) -ForegroundColor Yellow

    $symbols = $patterns[$category] -join ","
    # URL-encode robuste sans System.Web
    $symbolsEnc = [uri]::EscapeDataString($symbols)
    $url = "$base/taxonomy/suggestions?sample_symbols=$symbolsEnc"

    try {
        $result = Invoke-RestMethod -Uri $url -Method GET -ErrorAction Stop

        if (-not $result.PSObject.Properties.Name.Contains('suggestions') -or $null -eq $result.suggestions) {
            $result | Add-Member -NotePropertyName suggestions -NotePropertyValue @{}
        }

        Write-Host "  Resultats:" -ForegroundColor White
        Write-Host ("    Total symboles: {0}" -f $result.unknown_count) -ForegroundColor Gray
        Write-Host ("    Auto-classifies: {0}" -f $result.auto_classified_count) -ForegroundColor Gray
        $covPct = [math]::Round(([double]$result.coverage * 100), 1)
        Write-Host ("    Coverage: {0}%" -f $covPct) -ForegroundColor Gray

        if ($result.suggestions.Count -gt 0) {
            Write-Host "  Classifications detectees:" -ForegroundColor Green

            foreach ($suggestion in $result.suggestions.GetEnumerator()) {
                $color = if ($suggestion.Value -eq $category) { "Green" } else { "Yellow" }
                Write-Host ("    {0} -> {1}" -f $suggestion.Key, $suggestion.Value) -ForegroundColor $color
            }

            # Vérifier la précision
            $correct = 0
            foreach ($suggestion in $result.suggestions.GetEnumerator()) {
                if ($suggestion.Value -eq $category) { $correct++ }
            }
            $totalSug = [int]$result.suggestions.Count
            $precision = if ($totalSug -gt 0) { [math]::Round(($correct / $totalSug) * 100, 1) } else { 0 }
            $precColor = if ($precision -ge 80) { "Green" } elseif ($precision -ge 50) { "Yellow" } else { "Red" }
            Write-Host ("  Precision: {0}%" -f $precision) -ForegroundColor $precColor
        } else {
            Write-Host "  Aucune classification detectee" -ForegroundColor Red
        }

    } catch {
        Write-Host ("  Erreur: {0}" -f $_.Exception.Message) -ForegroundColor Red
        Write-Host ("  URL: {0}" -f $url) -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host ("=" * 50)
Write-Host "Test des patterns termine." -ForegroundColor Green
