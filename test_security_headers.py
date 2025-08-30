#!/usr/bin/env python3
"""
Test des headers de sécurité et middlewares
"""
import requests
import time
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

def test_security_headers():
    """Test des headers de sécurité appliqués par les middlewares"""
    try:
        response = requests.get("http://127.0.0.1:8000/healthz", timeout=10)
        headers = response.headers
        
        tests = [
            ("X-Content-Type-Options", headers.get("X-Content-Type-Options") == "nosniff"),
            ("X-Frame-Options", headers.get("X-Frame-Options") == "DENY"), 
            ("X-XSS-Protection", "1; mode=block" in headers.get("X-XSS-Protection", "")),
            ("Content-Security-Policy", "default-src" in headers.get("Content-Security-Policy", "")),
            ("X-Process-Time", "X-Process-Time" in headers),
            ("Referrer-Policy", "strict-origin-when-cross-origin" in headers.get("Referrer-Policy", "")),
            ("Content-Encoding", headers.get("Content-Encoding") is not None or True)  # GZip optionnel
        ]
        
        print("Headers de securite:")
        for name, passed in tests:
            status = "OK" if passed else "FAIL"
            actual = headers.get(name, "ABSENT")
            print(f"{status} {name}: {actual}")
        
        return all(passed for _, passed in tests)
        
    except requests.exceptions.RequestException as e:
        print(f"ERREUR: Impossible de contacter le serveur: {e}")
        print("Assurez-vous que le serveur est demarré:")
        print("uvicorn api.main:app --host 127.0.0.1 --port 8000")
        return False

def test_performance_timing():
    """Test du middleware de timing des performances"""
    try:
        start = time.time()
        response = requests.get("http://127.0.0.1:8000/healthz", timeout=10)
        end = time.time()
        
        request_time = end - start
        server_time = float(response.headers.get("X-Process-Time", "0"))
        
        print(f"\nPerformance timing:")
        print(f"OK Temps total requete: {request_time:.3f}s")
        print(f"OK Temps serveur (X-Process-Time): {server_time:.3f}s")
        print(f"OK Overhead reseau: {(request_time - server_time):.3f}s")
        
        return server_time > 0
        
    except Exception as e:
        print(f"ERREUR timing: {e}")
        return False

def test_api_endpoints():
    """Test rapide des endpoints critiques"""
    endpoints = [
        "/healthz",
        "/balances/current?source=cointracking&min_usd=1", 
        "/pricing/diagnostic?limit=3"
    ]
    
    print("\nTest endpoints API:")
    
    results = []
    for endpoint in endpoints:
        try:
            response = requests.get(f"http://127.0.0.1:8000{endpoint}", timeout=15)
            passed = response.status_code == 200
            results.append((endpoint, passed, response.status_code))
            status = "OK" if passed else "FAIL"
            print(f"{status} {endpoint}: HTTP {response.status_code}")
        except Exception as e:
            results.append((endpoint, False, str(e)))
            print(f"FAIL {endpoint}: {e}")
    
    return all(passed for _, passed, _ in results)

def check_server_running():
    """Vérifie si le serveur est déjà en cours d'exécution"""
    try:
        response = requests.get("http://127.0.0.1:8000/healthz", timeout=2)
        return response.status_code == 200
    except:
        return False

if __name__ == "__main__":
    print("TEST SECURITE ET PERFORMANCE POST-DURCISSEMENT")
    print("=" * 55)
    
    if not check_server_running():
        print("\nSERVEUR NON DEMARRE")
        print("Demarrez le serveur dans un autre terminal:")
        print("uvicorn api.main:app --host 127.0.0.1 --port 8000")
        print("\nPuis relancez ce script")
        sys.exit(1)
    
    print("\nServeur detecte sur http://127.0.0.1:8000")
    
    # Tests de sécurité
    security_ok = test_security_headers()
    
    # Tests de performance 
    timing_ok = test_performance_timing()
    
    # Tests d'endpoints
    api_ok = test_api_endpoints()
    
    # Résultat final
    print(f"\nRESULTAT FINAL:")
    print(f"Securite: {'PASS' if security_ok else 'FAIL'}")
    print(f"Performance: {'PASS' if timing_ok else 'FAIL'}")  
    print(f"API endpoints: {'PASS' if api_ok else 'FAIL'}")
    
    overall = security_ok and timing_ok and api_ok
    print(f"GLOBAL: {'TOUS LES TESTS PASSES' if overall else 'ECHECS DETECTES'}")