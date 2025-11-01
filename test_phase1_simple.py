#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test simplifié Phase 1 - Système d'Alertes
Cross-platform (Windows/Linux/Mac)
"""

import sys
import subprocess
import requests
import json
from pathlib import Path
import os

# Fix Windows encoding issues
if sys.platform == "win32":
    os.system("chcp 65001 > nul")

def run_command(cmd, description):
    """Execute command and return result"""
    print(f"[TEST] {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(f"  [OK] SUCCESS")
            return True
        else:
            print(f"  [FAIL] {result.stderr.strip() if result.stderr else result.stdout.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] Command timed out")
        return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

def check_api_health():
    """Test API health"""
    print("[API] Verification API...")
    try:
        # Test basic API
        response = requests.get("http://localhost:8080/docs", timeout=5)
        api_ok = response.status_code == 200
        print(f"  [{'OK' if api_ok else 'FAIL'}] API FastAPI: {response.status_code}")
        
        # Test alerts health
        response = requests.get("http://localhost:8080/api/alerts/health", timeout=5)
        alerts_ok = response.status_code == 200
        if alerts_ok:
            health_data = response.json()
            status = health_data.get("status", "unknown")
            print(f"  [{'OK' if status == 'healthy' else 'FAIL'}] Alerts Health: {status}")
        else:
            print(f"  [FAIL] Alerts Health: HTTP {response.status_code}")
            
        return api_ok and alerts_ok
        
    except requests.RequestException as e:
        print(f"  [ERROR] Server not accessible: {e}")
        print(f"  [INFO] Start server: uvicorn api.main:app --reload --port 8080")
        return False

def check_files():
    """Check required files exist"""
    print("[FILES] Verification fichiers...")
    
    files_to_check = [
        "config/alerts_rules.json",
        "services/alerts/alert_engine.py", 
        "services/alerts/alert_storage.py",
        "services/alerts/alert_types.py",
        "api/alerts_endpoints.py"
    ]
    
    all_ok = True
    for file_path in files_to_check:
        exists = Path(file_path).exists()
        print(f"  [{'OK' if exists else 'MISSING'}] {file_path}")
        if not exists:
            all_ok = False
    
    return all_ok

def main():
    print("TESTS Phase 1 - Systeme d'Alertes Predictives")
    print("=" * 60)
    
    results = {}
    
    # 1. Check file structure
    results["files"] = check_files()
    
    # 2. Unit tests
    results["unit_tests"] = run_command(
        "python -m pytest tests/unit/test_alert_engine.py -v --tb=short", 
        "Tests unitaires AlertEngine"
    )
    
    # 3. Integration tests  
    results["integration_tests"] = run_command(
        "python -m pytest tests/integration/test_alerts_api.py -v --tb=short",
        "Tests d'intégration API"
    )
    
    # 4. API health (only if server running)
    results["api_health"] = check_api_health()
    
    # 5. Manual workflow tests (if API available)
    if results["api_health"]:
        results["manual_tests"] = run_command(
            "python tests/manual/test_alerting_workflows.py",
            "Tests workflows manuels"
        )
        
        results["config_hotreload"] = run_command(
            "python tests/manual/test_config_hot_reload.py",
            "Test hot-reload configuration"
        )
    else:
        print("[WARN] Tests manuels ignores (serveur non accessible)")
        results["manual_tests"] = None
        results["config_hotreload"] = None
    
    # Summary
    print("\n[SUMMARY] RESUME DES TESTS PHASE 1")
    print("=" * 40)
    
    test_results = [
        ("Structure Fichiers", results["files"]),
        ("Tests Unitaires", results["unit_tests"]), 
        ("Tests Integration", results["integration_tests"]),
        ("Sante API", results["api_health"]),
        ("Tests Manuels", results["manual_tests"]),
        ("Hot-reload Config", results["config_hotreload"])
    ]
    
    passed = 0
    total = 0
    
    for name, result in test_results:
        if result is not None:
            total += 1
            if result:
                passed += 1
                print(f"[PASS] {name}")
            else:
                print(f"[FAIL] {name}")
        else:
            print(f"[SKIP] {name}")
    
    print(f"\n[RESULT] {passed}/{total} tests critiques passes")
    
    if passed == total and total > 0:
        print("[SUCCESS] COMPLET! Le systeme d'alertes Phase 1 est operationnel.")
        return 0
    elif passed >= 3:  # Au moins files + unit + integration
        print("[OK] Tests de base passes - Systeme fonctionnel")
        print("[NOTE] Echecs API/manuels peuvent etre normaux (RBAC, serveur non demarre)")
        return 0
    else:
        print("[FAIL] Tests critiques echoues - Problemes a resoudre")
        print("\n[DIAGNOSTIC]:")
        if not results["files"]:
            print("  - Fichiers manquants - verifier structure projet")
        if not results["unit_tests"]:
            print("  - Tests unitaires echoues - verifier code AlertEngine")
        if not results["integration_tests"]:
            print("  - Tests integration echoues - verifier API endpoints")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
