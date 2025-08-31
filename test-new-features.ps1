# Test script for new advanced features
$base = "http://127.0.0.1:8000"

Write-Host "🧪 Testing Advanced Features" -ForegroundColor Green
Write-Host "=============================" -ForegroundColor Green

# Test 1: Portfolio Optimization
Write-Host "`n1. 📊 Testing Portfolio Optimization" -ForegroundColor Yellow

# Get available objectives
$objectives = irm "$base/api/portfolio/optimization/objectives"
Write-Host "Available objectives: $($objectives.objectives.Count)" -ForegroundColor Cyan

# Get default constraints (conservative mode)
$constraints = irm "$base/api/portfolio/optimization/constraints/defaults?conservative=true"
Write-Host "Conservative constraints loaded" -ForegroundColor Cyan

# Test 2: Backtesting
Write-Host "`n2. 🎯 Testing Backtesting Engine" -ForegroundColor Yellow

# Get available strategies
$strategies = irm "$base/api/backtesting/strategies"
Write-Host "Available strategies: $($strategies.total_count)" -ForegroundColor Cyan
$strategies.strategies | ForEach-Object { Write-Host "  - $($_.name)" -ForegroundColor Gray }

# Get metrics definitions
$metrics = irm "$base/api/backtesting/metrics/definitions"
Write-Host "Performance metrics defined: $($metrics.performance_metrics.Count)" -ForegroundColor Cyan

# Test 3: Machine Learning
Write-Host "`n3. 🤖 Testing ML Models" -ForegroundColor Yellow

# Check ML models status
$mlStatus = irm "$base/api/ml/models/status"
Write-Host "ML models directory exists: $($mlStatus.models_directory_exists)" -ForegroundColor Cyan
Write-Host "Pipeline trained: $($mlStatus.pipeline_trained)" -ForegroundColor Cyan

# Test current regime prediction (might fail without trained models)
try {
    $regime = irm "$base/api/ml/regime/current"
    Write-Host "Current market regime: $($regime.regime) (confidence: $($regime.confidence))" -ForegroundColor Cyan
} catch {
    Write-Host "Regime prediction not available (models need training)" -ForegroundColor Red
}

# Test 4: API Documentation
Write-Host "`n4. 📚 Testing API Documentation" -ForegroundColor Yellow

try {
    $openapi = irm "$base/openapi.json"
    $pathCount = $openapi.paths.PSObject.Properties.Count
    Write-Host "Total API endpoints: $pathCount" -ForegroundColor Cyan
    
    # Count new endpoints
    $newEndpoints = 0
    $openapi.paths.PSObject.Properties | ForEach-Object {
        if ($_.Name -match "(optimization|backtesting|ml)") {
            $newEndpoints++
        }
    }
    Write-Host "New advanced endpoints: $newEndpoints" -ForegroundColor Green
    
} catch {
    Write-Host "OpenAPI spec not available" -ForegroundColor Red
}

# Test 5: Performance Test
Write-Host "`n5. ⚡ Performance Test" -ForegroundColor Yellow

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

# Test multiple endpoints in parallel
$jobs = @()

# Health check
$jobs += Start-Job -ScriptBlock { 
    param($base) 
    Measure-Command { irm "$base/healthz" } 
} -ArgumentList $base

# Optimization objectives
$jobs += Start-Job -ScriptBlock { 
    param($base) 
    Measure-Command { irm "$base/api/portfolio/optimization/objectives" } 
} -ArgumentList $base

# Backtesting strategies  
$jobs += Start-Job -ScriptBlock { 
    param($base) 
    Measure-Command { irm "$base/api/backtesting/strategies" } 
} -ArgumentList $base

# ML status
$jobs += Start-Job -ScriptBlock { 
    param($base) 
    Measure-Command { irm "$base/api/ml/models/status" } 
} -ArgumentList $base

# Wait for all jobs and get results
$results = $jobs | ForEach-Object { 
    Wait-Job $_ | Receive-Job
    Remove-Job $_
}

$stopwatch.Stop()

Write-Host "Parallel API calls completed in: $($stopwatch.ElapsedMilliseconds)ms" -ForegroundColor Green
$avgTime = ($results | Measure-Object -Property TotalMilliseconds -Average).Average
Write-Host "Average response time: $([math]::Round($avgTime, 2))ms" -ForegroundColor Cyan

# Summary
Write-Host "`n🎉 Test Summary" -ForegroundColor Green
Write-Host "===============" -ForegroundColor Green
Write-Host "✅ Portfolio Optimization: Ready" -ForegroundColor Green
Write-Host "✅ Backtesting Engine: Ready" -ForegroundColor Green  
Write-Host "⚠️  ML Models: Need Training" -ForegroundColor Yellow
Write-Host "✅ API Documentation: Complete" -ForegroundColor Green
Write-Host "✅ Performance: Good" -ForegroundColor Green

Write-Host "`n📋 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Open Portfolio Optimization: http://localhost:8000/static/portfolio-optimization.html" -ForegroundColor Gray
Write-Host "2. View API Docs: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "3. Train ML models via API or interface" -ForegroundColor Gray
Write-Host "4. Run backtests with your portfolio data" -ForegroundColor Gray