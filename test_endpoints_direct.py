#!/usr/bin/env python3
"""
Test direct des nouveaux endpoints pour vérifier qu'ils sont bien définis
"""
import uvicorn
from api.main import app
import asyncio
from fastapi.testclient import TestClient

def test_routes_definition():
    """Vérifier que les routes sont bien définies"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append((route.path, route.methods))
    
    # Rechercher nos nouveaux endpoints
    health_detailed = [r for r in routes if '/health/detailed' in r[0]]
    pricing_diagnostic = [r for r in routes if '/pricing/diagnostic' in r[0]]
    
    print("=== VERIFICATION DES ROUTES ===")
    print(f"Total routes: {len(routes)}")
    
    print(f"\nHealth detailed: {health_detailed}")
    print(f"Pricing diagnostic: {pricing_diagnostic}")
    
    return len(health_detailed) > 0 and len(pricing_diagnostic) > 0

def test_endpoints_with_testclient():
    """Tester les endpoints avec TestClient (sans serveur)"""
    client = TestClient(app)
    
    print("\n=== TESTS AVEC TESTCLIENT ===")
    
    # Test 1: Health simple
    response = client.get("/healthz")
    print(f"GET /healthz: {response.status_code} - {response.json()}")
    
    # Test 2: Health détaillé
    try:
        response = client.get("/health/detailed")
        print(f"GET /health/detailed: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  - OK: {data.get('ok')}")
            print(f"  - Memory: {data.get('system_metrics', {}).get('memory_used_mb', 'N/A')} MB")
        else:
            print(f"  - Error: {response.text}")
    except Exception as e:
        print(f"GET /health/detailed: ERROR - {e}")
    
    # Test 3: Pricing diagnostic
    try:
        response = client.get("/pricing/diagnostic?limit=2")
        print(f"GET /pricing/diagnostic: {response.status_code}")
        if response.status_code != 200:
            print(f"  - Error: {response.text}")
    except Exception as e:
        print(f"GET /pricing/diagnostic: ERROR - {e}")
    
    # Test 4: Vérifier les headers de sécurité
    response = client.get("/healthz")
    headers = response.headers
    security_headers = [
        'x-content-type-options',
        'x-frame-options', 
        'x-process-time'
    ]
    
    print(f"\n=== HEADERS DE SECURITE ===")
    for header in security_headers:
        value = headers.get(header, "ABSENT")
        print(f"{header}: {value}")

if __name__ == "__main__":
    print("TEST DIRECT DES NOUVEAUX ENDPOINTS")
    print("=" * 40)
    
    # Test 1: Vérifier définition des routes
    routes_ok = test_routes_definition()
    print(f"\nRoutes définies: {'OK' if routes_ok else 'FAIL'}")
    
    # Test 2: Tester avec TestClient
    test_endpoints_with_testclient()
    
    if routes_ok:
        print(f"\n🎯 CONCLUSION: Les endpoints sont bien définis dans le code.")
        print("Si ils n'apparaissent pas dans /docs, le serveur doit être redémarré.")
    else:
        print(f"\n❌ PROBLEME: Les endpoints ne sont pas correctement définis.")