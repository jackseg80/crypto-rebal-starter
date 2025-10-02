# setup_daily_snapshot_task.ps1
# Configure une tâche planifiée Windows pour créer un snapshot quotidien
# Doit être exécuté en tant qu'Administrateur

param(
    [string]$Time = "00:00",  # Heure d'exécution (format 24h)
    [string]$UserId = "jack",
    [string]$Source = "cointracking_api"
)

Write-Host "🔧 Configuration de la tâche planifiée..." -ForegroundColor Cyan

# Vérifier les privilèges admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ Ce script doit être exécuté en tant qu'Administrateur" -ForegroundColor Red
    Write-Host "   Faites un clic droit > 'Exécuter en tant qu'administrateur'" -ForegroundColor Yellow
    exit 1
}

# Chemins
$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $projectRoot "scripts\daily_snapshot.ps1"
$logPath = Join-Path $projectRoot "data\logs\snapshots.log"

# Vérifier que le script existe
if (-not (Test-Path $scriptPath)) {
    Write-Host "❌ Script non trouvé: $scriptPath" -ForegroundColor Red
    exit 1
}

# Créer le dossier de logs si nécessaire
$logDir = Split-Path -Parent $logPath
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# Définir l'action (PowerShell + script)
$action = New-ScheduledTaskAction `
    -Execute "PowerShell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -UserId $UserId -Source $Source"

# Définir le déclencheur (quotidien à l'heure spécifiée)
$trigger = New-ScheduledTaskTrigger -Daily -At $Time

# Définir les paramètres (exécuter même si l'utilisateur n'est pas connecté)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Créer ou mettre à jour la tâche
$taskName = "Crypto Portfolio Daily Snapshot"
$taskPath = "\CryptoRebal\"

try {
    # Supprimer la tâche existante si présente
    $existingTask = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false
        Write-Host "⚠️  Tâche existante supprimée" -ForegroundColor Yellow
    }

    # Créer la nouvelle tâche
    Register-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $taskPath `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Crée automatiquement un snapshot quotidien du portfolio crypto pour le P&L tracking" `
        -RunLevel Highest | Out-Null

    Write-Host "✅ Tâche planifiée créée avec succès!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 Détails:" -ForegroundColor Cyan
    Write-Host "   Nom: $taskName" -ForegroundColor Gray
    Write-Host "   Heure: $Time (tous les jours)" -ForegroundColor Gray
    Write-Host "   User: $UserId" -ForegroundColor Gray
    Write-Host "   Source: $Source" -ForegroundColor Gray
    Write-Host "   Script: $scriptPath" -ForegroundColor Gray
    Write-Host "   Logs: $logPath" -ForegroundColor Gray
    Write-Host ""
    Write-Host "🔍 Pour vérifier:" -ForegroundColor Yellow
    Write-Host "   Ouvrir 'Planificateur de tâches' > CryptoRebal > $taskName" -ForegroundColor Gray
    Write-Host ""
    Write-Host "🧪 Pour tester maintenant:" -ForegroundColor Yellow
    Write-Host "   Start-ScheduledTask -TaskPath '$taskPath' -TaskName '$taskName'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "❌ Pour supprimer:" -ForegroundColor Yellow
    Write-Host "   Unregister-ScheduledTask -TaskName '$taskName' -TaskPath '$taskPath' -Confirm:`$false" -ForegroundColor Gray

} catch {
    Write-Host "❌ Erreur lors de la création de la tâche: $_" -ForegroundColor Red
    exit 1
}
