param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Invoke-WealthRequest {
    param(
        [string]$Method = 'GET',
        [string]$Path,
        [hashtable]$Body = $null
    )

    $uri = "$BaseUrl$Path"
    if ($Method -eq 'GET') {
        return Invoke-RestMethod -Uri $uri -Method GET -TimeoutSec 15
    }

    $json = $null
    if ($Body) {
        $json = $Body | ConvertTo-Json -Depth 6
    }
    return Invoke-RestMethod -Uri $uri -Method $Method -Body $json -ContentType 'application/json' -TimeoutSec 15
}

$failures = @()
$warnings = @()

Write-Host "=== Wealth smoke test ===" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor DarkCyan

try {
    $modules = Invoke-WealthRequest -Path '/api/wealth/modules'
    if (-not ($modules -is [System.Collections.IEnumerable])) {
        throw "Réponse inattendue pour /api/wealth/modules"
    }
    Write-Host "Modules disponibles: $($modules -join ', ')"
    if (-not ($modules -contains 'crypto')) { $warnings += 'Module crypto absent de la liste.' }
    if (-not ($modules -contains 'saxo')) { $warnings += 'Module saxo absent de la liste.' }
} catch {
    $failures += "Impossible d'obtenir /api/wealth/modules : $_"
}

try {
    $cryptoPositions = Invoke-WealthRequest -Path '/api/wealth/crypto/positions'
    $count = ($cryptoPositions | Measure-Object).Count
    Write-Host "Positions crypto: $count"
    if ($count -eq 0) { $warnings += 'Aucune position crypto retournée.' }
} catch {
    $failures += "Erreur sur /api/wealth/crypto/positions : $_"
}

try {
    $saxoPositions = Invoke-WealthRequest -Path '/api/wealth/saxo/positions'
    $count = ($saxoPositions | Measure-Object).Count
    Write-Host "Positions saxo (wealth): $count"
} catch {
    $failures += "Erreur sur /api/wealth/saxo/positions : $_"
}

try {
    $legacyPositions = Invoke-WealthRequest -Path '/api/saxo/positions'
    $legacyCount = ($legacyPositions.positions | Measure-Object).Count
    Write-Host "Positions saxo (legacy): $legacyCount"
    $wealthCount = ($saxoPositions | Measure-Object).Count
    if ($wealthCount -ne $legacyCount) {
        $warnings += "Divergence saxo legacy vs wealth ($legacyCount vs $wealthCount)"
    }
} catch {
    $warnings += "Legacy /api/saxo/positions indisponible : $_"
}

try {
    $preview = Invoke-WealthRequest -Method 'POST' -Path '/api/wealth/saxo/rebalance/preview' -Body @{}
    $count = ($preview | Measure-Object).Count
    Write-Host "Preview rebalance saxo: $count propositions"
} catch {
    $warnings += "Prévisualisation rebalance saxo non disponible : $_"
}

try {
    $prices = Invoke-WealthRequest -Path '/api/wealth/crypto/prices?ids=BTC,ETH&granularity=daily'
    $priceCount = ($prices | Measure-Object).Count
    Write-Host "Points de prix (BTC/ETH): $priceCount"
    if ($priceCount -eq 0) { $warnings += 'Aucun prix renvoyé pour BTC/ETH.' }
} catch {
    $warnings += "Impossible d'obtenir les prix crypto : $_"
}

Write-Host "--- Résultat ---" -ForegroundColor Cyan
if ($failures.Count -gt 0) {
    Write-Host "ÉCHEC" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "[ERREUR] $_" -ForegroundColor Red }
    exit 1
}

Write-Host "OK" -ForegroundColor Green
if ($warnings.Count -gt 0) {
    $warnings | ForEach-Object { Write-Host "[AVERTISSEMENT] $_" -ForegroundColor Yellow }
}

exit 0
