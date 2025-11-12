@echo off
echo ========================================
echo Phase 3 E2E Integration Test Suite
echo ========================================
echo.

echo 🚀 Starting test server check...
curl -s http://localhost:8000/api/phase3/status >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Test server not running on localhost:8000
    echo Please start the server with: uvicorn api.main:app --port 8000
    pause
    exit /b 1
)
echo ✅ Test server is running

echo.
echo 🧪 Running Quick API Tests...
echo ----------------------------------------
python tests\e2e\quick_phase3_test.py

echo.
echo 📊 Test Results saved to: phase3_test_results.json
echo.

echo ========================================
echo Would you like to run full E2E tests with UI?
echo (Requires Chrome WebDriver)
echo ========================================
set /p choice="Run full tests? (y/n): "

if /i "%choice%"=="y" (
    echo.
    echo 🌐 Running Full E2E Tests with UI...
    echo ----------------------------------------
    python -m pytest tests\e2e\test_phase3_integration.py -v
) else (
    echo Skipping full E2E tests
)

echo.
echo 🎉 Test Suite Completed!
echo Check the results above for any issues.
pause