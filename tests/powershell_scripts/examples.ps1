$base = "http://127.0.0.1:8000"

# 1) portfolio groups
Invoke-RestMethod "$base/portfolio/groups?source=cointracking&min_usd=1" -Method GET | ConvertTo-Json -Depth 6

# 2) plan
$body = @{
  group_targets_pct = @{
    BTC = 35; ETH = 25; "Stablecoins" = 10; SOL = 10; "L1/L0 majors"=10; Others=10
  }
  min_trade_usd = 25
  sub_allocation = "proportional"
  primary_symbols = @{
    BTC = @("BTC","TBTC","WBTC")
    ETH = @("ETH","WSTETH","RETH","STETH","WETH")
    SOL = @("SOL","JUPSOL","JITOSOL")
  }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod "$base/rebalance/plan?source=cointracking&min_usd=1" -Method POST -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 6
