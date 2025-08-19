# tests/api_tests.ps1
# Tests robustes de l’API Crypto Rebal Starter
# Lancer l'API ainsi : uvicorn api.main:app --reload --port 8000

$ErrorActionPreference = "Stop"

# --- Paramètres ---
$base = ${env:API_BASE}
if ([string]::IsNullOrWhiteSpace($base)) { $base = "http://127.0.0.1:8000" }
$qs   = "source=cointracking_api&min_usd=1&pricing=local"

# Payload commun
$body = @{
  group_targets_pct = @{
    BTC = 35; ETH = 25; Stablecoins = 10; SOL = 10; "L1/L0 majors" = 10; Others = 10
  }
  primary_symbols   = @{
    BTC = @("BTC","TBTC","WBTC")
    ETH = @("ETH","WSTETH","STETH","RETH","WETH")
    SOL = @("SOL","JUPSOL","JITOSOL")
  }
  sub_allocation    = "proportional"
  min_trade_usd     = 25
} | ConvertTo-Json -Depth 6

function Try-InvokeJson {
  param([string]$Url,[string]$Method="GET",[string]$ContentType="application/json",[string]$BodyJson=$null)
  try {
    if ($Method -eq "GET") {
      return Invoke-RestMethod -Uri $Url -Method GET
    } else {
      return Invoke-RestMethod -Uri $Url -Method $Method -ContentType $ContentType -Body $BodyJson
    }
  } catch {
    # On remonte l'objet d'erreur pour tests conditionnels (ex: 404)
    return $_
  }
}

Write-Host "== /healthz ==" -ForegroundColor Cyan
$health = Try-InvokeJson "$base/healthz"
$health | ConvertTo-Json -Depth 4

# --- /portfolio/groups (fallback sur /balances/current si 404) ---
Write-Host "`n== /portfolio/groups (fallback si 404) ==" -ForegroundColor Cyan
$groupsRes = Try-InvokeJson "$base/portfolio/groups?$qs"
$useBalancesFallback = $false
if ($groupsRes -is [System.Management.Automation.ErrorRecord]) {
  $status = $groupsRes.Exception.Response.StatusCode.Value__
  if ($status -eq 404) {
    Write-Host "Route /portfolio/groups introuvable → fallback /balances/current" -ForegroundColor Yellow
    $useBalancesFallback = $true
  } else {
    throw $groupsRes
  }
}
if ($useBalancesFallback) {
  $cur = Try-InvokeJson "$base/balances/current?$qs"
  if ($cur -is [System.Management.Automation.ErrorRecord]) { throw $cur }
  "{0}  {1}  {2}" -f ($cur.source_used),
                    ($cur.items.Count),
                    ("{0:N2}" -f ( ($cur.items | Measure-Object value_usd -Sum).Sum ))
} else {
  "{0}  total=${1:N2}" -f ($groupsRes.source_used),
                         ($groupsRes.total_usd)
  # Affiche top 5 alias
  ($groupsRes.alias_summary | Sort-Object -Property total_usd -Descending | Select-Object -First 5) |
    ForEach-Object { "{0}  {1:N2}$" -f $_.alias, $_.total_usd }
}

# --- /rebalance/plan ---
Write-Host "`n== /rebalance/plan ==" -ForegroundColor Cyan
$plan = Try-InvokeJson "$base/rebalance/plan?$qs" -Method POST -BodyJson $body
if ($plan -is [System.Management.Automation.ErrorRecord]) { throw $plan }

"Total USD : {0:N2}" -f $plan.total_usd
$sumTargets = ($plan.target_weights_pct.PSObject.Properties | Measure-Object -Property Value -Sum).Sum
"Somme des poids : {0} (attendu 100)" -f [int][math]::Round($sumTargets)
$net = ($plan.actions | Measure-Object -Property usd -Sum).Sum
"Net (achats + ventes) : {0:N2} (≈ 0 attendu)" -f $net

$unknown = $plan.unknown_aliases
"Unknown aliases : {0}" -f ($(if ($unknown) { ($unknown -join ", ") } else { "" }))

# Affiche un extrait des 10 premières actions
$plan.actions | Select-Object -First 10 group,alias,symbol,action,usd,est_quantity,price_used |
  Format-Table -AutoSize

# --- /rebalance/plan.csv ---
Write-Host "`n== /rebalance/plan.csv ==" -ForegroundColor Cyan
$tmpCsv = Join-Path $env:TEMP "rebalance-actions.csv"
Invoke-RestMethod -Method POST -ContentType 'application/json' -Uri "$base/rebalance/plan.csv?$qs" -Body $body -OutFile $tmpCsv
"CSV créé ? {0}" -f (Test-Path $tmpCsv)
"Premières lignes CSV :"
Get-Content $tmpCsv | Select-Object -First 10

# --- /taxonomy/aliases : mise à jour au bon format ---
Write-Host "`n== /taxonomy/aliases (mise à jour d'exemple) ==" -ForegroundColor Cyan
$aliasesPayload = @{
  aliases = @{
    WSTETH = "ETH"
    STETH  = "ETH"
    RETH   = "ETH"
    TBTC   = "BTC"
    USD    = "Stablecoins"
    USDT   = "Stablecoins"
    USDC   = "Stablecoins"
  }
} | ConvertTo-Json -Depth 4

$tcx = Try-InvokeJson "$base/taxonomy/aliases" -Method POST -BodyJson $aliasesPayload
if ($tcx -is [System.Management.Automation.ErrorRecord]) { throw $tcx }
$tcx | ConvertTo-Json -Depth 4
