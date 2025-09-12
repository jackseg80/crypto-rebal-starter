@echo off
echo ============================================
echo Phase 3 Complete E2E Test Suite
echo ============================================
echo.

:: Vérifier que le serveur fonctionne
echo 🚀 Checking test server...
curl -s http://localhost:8000/api/phase3/status >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Test server not running on localhost:8000
    echo Please start the server with: uvicorn api.main:app --port 8000
    pause
    exit /b 1
)
echo ✅ Test server is running

echo.
echo 📋 Running Complete E2E Test Suite...
echo ============================================

:: Test 1: Intégration de base
echo.
echo 🧪 1. Basic Integration Tests
echo ----------------------------------------
python tests\e2e\simple_phase3_test.py
echo.

:: Test 2: Résilience et récupération
echo 🛡️ 2. Resilience and Recovery Tests  
echo ----------------------------------------
python tests\e2e\test_resilience_simple.py
echo.

:: Test 3: Benchmarks de performance
echo 🏃 3. Performance Benchmarks
echo ----------------------------------------
python tests\e2e\test_performance_benchmark.py
echo.

:: Test 4: Compatibilité cross-browser
echo 🌐 4. Cross-Browser Compatibility
echo ----------------------------------------
python tests\e2e\test_compatibility_simple.py
echo.

echo ============================================
echo 📊 Test Results Summary
echo ============================================

:: Afficher les résultats s'ils existent
if exist phase3_test_results.json (
    echo ✅ Basic Integration: COMPLETED
    echo    Results: phase3_test_results.json
) else (
    echo ❌ Basic Integration: FAILED
)

if exist phase3_resilience_results.json (
    echo ✅ Resilience Tests: COMPLETED  
    echo    Results: phase3_resilience_results.json
) else (
    echo ❌ Resilience Tests: FAILED
)

if exist phase3_performance_benchmark.json (
    echo ✅ Performance Benchmarks: COMPLETED
    echo    Results: phase3_performance_benchmark.json
) else (
    echo ❌ Performance Benchmarks: FAILED
)

if exist phase3_compatibility_results.json (
    echo ✅ Compatibility Tests: COMPLETED
    echo    Results: phase3_compatibility_results.json
) else (
    echo ❌ Compatibility Tests: FAILED
)

echo.
echo ============================================
echo 🎉 E2E Test Suite Completed!
echo ============================================
echo.
echo 📁 All test results saved in current directory
echo 🔍 Review JSON files for detailed metrics
echo.

pause