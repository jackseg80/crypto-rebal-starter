#!/usr/bin/env python3
"""
Smoke tests pour les endpoints refactorisés
Teste les changements critiques du refactoring d'endpoints
"""

import requests
import json
import sys
import os
from typing import Dict, Any

BASE_URL = "http://localhost:8080"

class SmokeTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self, test_name: str):
        print(f"OK {test_name}")
        self.passed += 1
    
    def add_fail(self, test_name: str, error: str):
        print(f"FAIL {test_name}: {error}")
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n>> Results: {self.passed}/{total} passed")
        if self.errors:
            print("\n!! Errors:")
            for error in self.errors:
                print(f"  - {error}")
        return self.failed == 0

def test_endpoint(method: str, url: str, expected_status: int = 200, data: Dict[Any, Any] = None, headers: Dict[str, str] = None) -> requests.Response:
    """Helper pour tester un endpoint"""
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=10)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return response
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")

def main():
    result = SmokeTestResult()
    
    print(">> Starting smoke tests for refactored endpoints...")
    print(f"Testing against: {BASE_URL}\n")
    
    # Test 1: Vérifier que les anciennes routes retournent 404
    print("1. Testing removed endpoints return 404")
    
    removed_endpoints = [
        ("GET", "/api/ml-predictions/predict"),
        ("POST", "/api/test/risk/dashboard"),
        ("POST", "/api/alerts/test/generate"),
        ("POST", "/api/realtime/publish"),
        ("POST", "/api/realtime/broadcast")
    ]
    
    for method, endpoint in removed_endpoints:
        try:
            response = test_endpoint(method, f"{BASE_URL}{endpoint}")
            if response.status_code == 404:
                result.add_pass(f"Removed endpoint {method} {endpoint} returns 404")
            else:
                result.add_fail(f"Removed endpoint {method} {endpoint}", f"Expected 404, got {response.status_code}")
        except Exception as e:
            if "404" in str(e) or "Not Found" in str(e):
                result.add_pass(f"Removed endpoint {method} {endpoint} returns 404")
            else:
                result.add_fail(f"Removed endpoint {method} {endpoint}", str(e))
    
    # Test 2: Vérifier les nouveaux endpoints unifiés
    print("\n2. Testing unified endpoints")
    
    # Test unified ML namespace
    try:
        response = test_endpoint("GET", f"{BASE_URL}/api/ml/status")
        if response.status_code in [200, 503]:  # 503 si ML pas initialisé
            result.add_pass("Unified ML namespace /api/ml/status accessible")
        else:
            result.add_fail("Unified ML namespace", f"Expected 200/503, got {response.status_code}")
    except Exception as e:
        result.add_fail("Unified ML namespace", str(e))
    
    # Test unified risk namespace
    try:
        response = test_endpoint("GET", f"{BASE_URL}/api/risk/status")
        if response.status_code in [200, 503]:
            result.add_pass("Unified risk namespace /api/risk/status accessible")
        else:
            result.add_fail("Unified risk namespace", f"Expected 200/503, got {response.status_code}")
    except Exception as e:
        result.add_fail("Unified risk namespace", str(e))
    
    # Test consolidé risk/advanced
    try:
        response = test_endpoint("GET", f"{BASE_URL}/api/risk/advanced/methods/info")
        if response.status_code in [200, 503]:
            result.add_pass("Consolidated risk/advanced namespace accessible")
        else:
            result.add_fail("Consolidated risk/advanced namespace", f"Expected 200/503, got {response.status_code}")
    except Exception as e:
        result.add_fail("Consolidated risk/advanced namespace", str(e))
    
    # Test 3: Test endpoints d'alerte centralisés
    print("\n3. Testing centralized alert endpoints")
    
    try:
        response = test_endpoint("GET", f"{BASE_URL}/api/alerts/active")
        if response.status_code in [200, 401]:  # 401 si auth requise
            result.add_pass("Centralized alerts endpoint accessible")
        else:
            result.add_fail("Centralized alerts endpoint", f"Expected 200/401, got {response.status_code}")
    except Exception as e:
        result.add_fail("Centralized alerts endpoint", str(e))
    
    # Test 4: Test admin-protected ML debug
    print("\n4. Testing admin-protected ML debug endpoints")
    
    # Sans auth admin - doit échouer
    try:
        response = test_endpoint("GET", f"{BASE_URL}/api/ml/debug/pipeline-info")
        if response.status_code in [401, 403]:
            result.add_pass("ML debug endpoint requires admin auth (without key)")
        else:
            result.add_fail("ML debug endpoint auth", f"Expected 401/403, got {response.status_code}")
    except Exception as e:
        if "401" in str(e) or "403" in str(e):
            result.add_pass("ML debug endpoint requires admin auth (without key)")
        else:
            result.add_fail("ML debug endpoint auth", str(e))
    
    # Avec auth admin - doit fonctionner
    try:
        # SECURITY: Use ADMIN_KEY from environment (required for tests)
        admin_key = os.getenv("ADMIN_KEY", "test-key-change-in-production")
        headers = {"X-Admin-Key": admin_key}
        response = test_endpoint("GET", f"{BASE_URL}/api/ml/debug/pipeline-info", headers=headers)
        if response.status_code == 200:
            result.add_pass("ML debug endpoint accessible with admin key")
        else:
            result.add_fail("ML debug endpoint with auth", f"Expected 200, got {response.status_code}")
    except Exception as e:
        result.add_fail("ML debug endpoint with auth", str(e))
    
    # Test 5: Test OpenAPI spec accessibility
    print("\n5. Testing OpenAPI spec")
    
    try:
        response = test_endpoint("GET", f"{BASE_URL}/openapi.json")
        if response.status_code == 200:
            spec = response.json()
            if "paths" in spec:
                result.add_pass("OpenAPI spec accessible and valid JSON")
            else:
                result.add_fail("OpenAPI spec validation", "Missing 'paths' key in spec")
        else:
            result.add_fail("OpenAPI spec access", f"Expected 200, got {response.status_code}")
    except Exception as e:
        result.add_fail("OpenAPI spec access", str(e))
    
    print(f"\n{'='*50}")
    success = result.summary()
    
    if success:
        print(">> All smoke tests passed!")
        return 0
    else:
        print("!! Some smoke tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
