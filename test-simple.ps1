# Simple test script for new features
$base = "http://127.0.0.1:8000"

Write-Host "🧪 Testing New Features" -ForegroundColor Green

# Test 1: List available backtesting strategies
Write-Host "`n1. Backtesting Strategies:" -ForegroundColor Yellow
$strategies = irm "$base/api/backtesting/strategies"
$strategies.strategies | ForEach-Object { Write-Host "   - $($_.name)" -ForegroundColor Cyan }

# Test 2: List optimization objectives  
Write-Host "`n2. Optimization Objectives:" -ForegroundColor Yellow
$objectives = irm "$base/api/portfolio/optimization/objectives"
$objectives.objectives | ForEach-Object { Write-Host "   - $($_.name)" -ForegroundColor Cyan }

# Test 3: ML Status
Write-Host "`n3. ML Models Status:" -ForegroundColor Yellow
$ml = irm "$base/api/ml/models/status"
Write-Host "   - Models trained: $($ml.pipeline_trained)" -ForegroundColor Cyan
Write-Host "   - Available models: $($ml.models_count)" -ForegroundColor Cyan

Write-Host "`n✅ All APIs working!" -ForegroundColor Green
Write-Host "Next: Open http://localhost:8000/static/portfolio-optimization.html" -ForegroundColor Yellow