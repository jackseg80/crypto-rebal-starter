# Vérif balances côté API CT
irm "http://127.0.0.1:8000/balances/current?source=cointracking_api&min_usd=1" |
  Select-Object source_used, @{n="count";e={$_.items.Count}},
                         @{n="sum";e={("{0:N2}" -f (($_.items | Measure-Object value_usd -Sum).Sum))}}

# Plan + CSV
$base = "http://127.0.0.1:8000"
$qs = "source=cointracking_api&min_usd=1"
$body = @{
  group_targets_pct = @{
    BTC = 35; ETH = 25; Stablecoins = 10; SOL = 10; "L1/L0 majors" = 10; Others = 10
  }
  primary_symbols = @{
    BTC = @("BTC","TBTC","WBTC")
    ETH = @("ETH","WSTETH","STETH","RETH","WETH")
    SOL = @("SOL","JUPSOL","JITOSOL")
  }
  sub_allocation = "proportional"
  min_trade_usd  = 25
} | ConvertTo-Json -Depth 6

$plan = irm -Method POST -ContentType 'application/json' -Uri "$base/rebalance/plan?$qs" -Body $body
$plan.meta
$plan.total_usd
$plan.actions | Select-Object group,alias,symbol,action,usd,est_quantity,price_used | ft -Auto

$csvPath = "$env:USERPROFILE\Desktop\rebalance-actions-api.csv"
irm -Method POST -ContentType 'application/json' -Uri "$base/rebalance/plan.csv?$qs" -Body $body -OutFile $csvPath
Get-Content $csvPath -TotalCount 5