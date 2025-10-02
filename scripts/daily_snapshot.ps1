# daily_snapshot.ps1
# Script pour créer un snapshot quotidien du portfolio
# Usage: .\scripts\daily_snapshot.ps1

param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$UserId = "jack",
    [string]$Source = "cointracking_api",
    [float]$MinUsd = 1.0
)

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "📸 Creating daily portfolio snapshot - $timestamp" -ForegroundColor Cyan

# Construire l'URL
$url = "$BaseUrl/portfolio/snapshot?source=$Source&user_id=$UserId&min_usd=$MinUsd"

try {
    # Appeler l'API
    $response = Invoke-RestMethod -Uri $url -Method POST -TimeoutSec 30

    if ($response.ok -eq $true) {
        Write-Host "✅ Snapshot created successfully" -ForegroundColor Green
        Write-Host "   User: $UserId" -ForegroundColor Gray
        Write-Host "   Source: $Source" -ForegroundColor Gray
        Write-Host "   Min USD: $MinUsd" -ForegroundColor Gray

        # Log dans un fichier
        $logFile = "data\logs\snapshots.log"
        $logEntry = "[$timestamp] Snapshot OK - user=$UserId source=$Source"
        Add-Content -Path $logFile -Value $logEntry -ErrorAction SilentlyContinue

        exit 0
    } else {
        Write-Host "❌ Snapshot creation failed: $($response.error)" -ForegroundColor Red
        exit 1
    }

} catch {
    Write-Host "❌ Error calling API: $_" -ForegroundColor Red

    # Log l'erreur
    $logFile = "data\logs\snapshots.log"
    $logEntry = "[$timestamp] ERROR - user=$UserId source=$Source - $_"
    Add-Content -Path $logFile -Value $logEntry -ErrorAction SilentlyContinue

    exit 1
}
