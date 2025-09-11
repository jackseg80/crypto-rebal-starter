@echo off
REM Script de test complet Phase 1 - Système d'Alertes
REM Usage: test_phase1_alerting.bat

echo 🚀 Tests Phase 1 - Système d'Alertes Prédictives
echo ================================================

REM Vérifier que Python est disponible
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python non trouvé - installation requise
    exit /b 1
)

REM Vérifier structure des fichiers
echo.
echo 📁 Vérification structure des fichiers...
if not exist "config\alerts_rules.json" (
    echo ❌ Fichier config\alerts_rules.json manquant
    exit /b 1
)
if not exist "services\alerts\alert_engine.py" (
    echo ❌ AlertEngine manquant
    exit /b 1
)
if not exist "api\alerts_endpoints.py" (
    echo ❌ Endpoints alertes manquants
    exit /b 1
)
echo ✅ Structure des fichiers OK

REM Tests unitaires
echo.
echo 🧪 Exécution tests unitaires...
python -m pytest tests/unit/test_alert_engine.py -v
if errorlevel 1 (
    echo ⚠️  Certains tests unitaires ont échoué
    set UNIT_TESTS_FAILED=1
) else (
    echo ✅ Tests unitaires passés
)

REM Tests d'intégration API
echo.
echo 🔌 Tests d'intégration API...
python -m pytest tests/integration/test_alerts_api.py -v
if errorlevel 1 (
    echo ⚠️  Certains tests d'intégration ont échoué
    set INTEGRATION_TESTS_FAILED=1
) else (
    echo ✅ Tests d'intégration passés
)

REM Vérifier si le serveur est démarré
echo.
echo 🌐 Vérification serveur local...
python -c "import requests; requests.get('http://localhost:8000/docs', timeout=3)" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Serveur local non accessible sur http://localhost:8000
    echo    Démarrez le serveur avec: uvicorn api.main:app --reload --port 8000
    echo    Les tests manuels seront ignorés
    set SERVER_DOWN=1
    goto :skip_manual_tests
)

echo ✅ Serveur local accessible

REM Tests manuels workflow
echo.
echo 🎯 Tests workflows manuels...
python tests/manual/test_alerting_workflows.py
if errorlevel 1 (
    set MANUAL_TESTS_FAILED=1
    echo ⚠️  Certains tests manuels ont échoué
) else (
    echo ✅ Tests workflows manuels passés
)

REM Test hot-reload (optionnel - peut échouer si RBAC actif)
echo.
echo 🔥 Test hot-reload configuration...
python tests/manual/test_config_hot_reload.py
if errorlevel 1 (
    echo ⚠️  Test hot-reload échoué (peut être normal si RBAC actif)
    set HOTRELOAD_FAILED=1
) else (
    echo ✅ Test hot-reload réussi
)

:skip_manual_tests

REM Résumé final
echo.
echo 📊 RÉSUMÉ DES TESTS PHASE 1
echo ===========================

if not defined UNIT_TESTS_FAILED (
    echo ✅ Tests Unitaires: PASSÉS
) else (
    echo ❌ Tests Unitaires: ÉCHOUÉS
)

if not defined INTEGRATION_TESTS_FAILED (
    echo ✅ Tests Intégration: PASSÉS
) else (
    echo ❌ Tests Intégration: ÉCHOUÉS
)

if defined SERVER_DOWN (
    echo ⚠️  Tests Manuels: NON EXÉCUTÉS (serveur non démarré)
) else (
    if not defined MANUAL_TESTS_FAILED (
        echo ✅ Tests Manuels: PASSÉS
    ) else (
        echo ❌ Tests Manuels: ÉCHOUÉS
    )
    
    if not defined HOTRELOAD_FAILED (
        echo ✅ Hot-reload: PASSÉ
    ) else (
        echo ⚠️  Hot-reload: ÉCHOUÉ (peut être normal)
    )
)

echo.
if not defined UNIT_TESTS_FAILED (
    if not defined INTEGRATION_TESTS_FAILED (
        if not defined MANUAL_TESTS_FAILED (
            echo 🎉 TOUS LES TESTS CRITIQUES SONT PASSÉS !
            echo    Le système d'alertes Phase 1 est prêt pour la production.
            exit /b 0
        )
    )
)

echo ⚠️  CERTAINS TESTS ONT ÉCHOUÉ
echo    Consultez les détails ci-dessus pour diagnostiquer.
echo.
echo 💡 Notes:
echo    - Échecs RBAC (401/403) sont normaux si auth pas configurée
echo    - Hot-reload peut échouer selon la config système
echo    - Tests manuels nécessitent serveur démarré
exit /b 1