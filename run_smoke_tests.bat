@echo off
echo Starting smoke tests for refactored endpoints...

REM Démarrer uvicorn en arrière-plan
echo Starting server...
start /B uvicorn api.main:app --host localhost --port 8000

REM Attendre que le serveur démarre
echo Waiting for server to start...
timeout /t 15 /nobreak >nul

REM Exécuter les tests
echo Running smoke tests...
python tests\smoke_test_refactored_endpoints.py

REM Arrêter uvicorn
echo Stopping server...
taskkill /f /im uvicorn.exe >nul 2>&1

pause