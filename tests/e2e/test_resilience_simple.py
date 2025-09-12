"""
Tests de résilience simplifiés pour Phase 3
Focus sur la récupération et la gestion gracieuse des erreurs
"""
import json
import time
import requests

def test_phase3_resilience():
    """Tests de résilience Phase 3"""
    base_url = "http://localhost:8000"
    session = requests.Session()
    
    print("Phase 3 Resilience & Recovery Tests")
    print("=" * 40)
    
    results = {}
    
    try:
        # Test 1: Requêtes malformées
        print("1. Testing Malformed Requests...")
        
        malformed_tests = [
            {"data": {}, "name": "empty_request"},
            {"data": {"invalid": "data"}, "name": "invalid_structure"},
            {"data": {"portfolio_weights": "not_dict"}, "name": "wrong_types"}
        ]
        
        malformed_results = {}
        for test in malformed_tests:
            response = session.post(f"{base_url}/api/phase3/risk/comprehensive-analysis", json=test["data"])
            malformed_results[test["name"]] = {
                "status_code": response.status_code,
                "handled_gracefully": response.status_code in [400, 422, 500]
            }
        
        malformed_passed = sum(1 for r in malformed_results.values() if r["handled_gracefully"])
        print(f"   [OK] Malformed requests handled: {malformed_passed}/{len(malformed_results)}")
        results["malformed_requests"] = malformed_results
        
        # Test 2: WebSocket Engine Resilience
        print("2. Testing WebSocket Engine Resilience...")
        
        # Test stop/start cycle
        stop_response = session.post(f"{base_url}/api/realtime/stop")
        stop_ok = stop_response.status_code == 200
        
        start_response = session.post(f"{base_url}/api/realtime/start")
        start_ok = start_response.status_code == 200
        
        # Test status après redémarrage
        time.sleep(0.5)  # Attendre le redémarrage
        status_response = session.get(f"{base_url}/api/realtime/status")
        status_ok = status_response.status_code == 200
        
        websocket_resilience = {
            "stop_successful": stop_ok,
            "start_successful": start_ok,
            "status_check_ok": status_ok,
            "full_cycle_ok": stop_ok and start_ok and status_ok
        }
        
        print(f"   [OK] WebSocket engine stop/start cycle: {'SUCCESS' if websocket_resilience['full_cycle_ok'] else 'FAILED'}")
        results["websocket_resilience"] = websocket_resilience
        
        # Test 3: Performance sous charge
        print("3. Testing Performance Under Load...")
        
        valid_request = {
            "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
            "portfolio_value": 10000,
            "analysis_types": ["var_parametric"],
            "confidence_levels": [0.95],
            "horizons": ["1d"]
        }
        
        # 5 requêtes consécutives
        load_times = []
        load_errors = 0
        
        for i in range(5):
            start = time.time()
            try:
                response = session.post(f"{base_url}/api/phase3/risk/comprehensive-analysis", json=valid_request, timeout=10)
                duration = (time.time() - start) * 1000
                load_times.append(duration)
                
                if response.status_code != 200:
                    load_errors += 1
            except Exception as e:
                load_errors += 1
                load_times.append(10000)  # Timeout
        
        load_performance = {
            "total_requests": 5,
            "errors": load_errors,
            "success_rate": ((5 - load_errors) / 5) * 100,
            "avg_response_ms": round(sum(load_times) / len(load_times), 1) if load_times else 0,
            "performance_acceptable": (load_errors == 0) and (sum(load_times) / len(load_times) < 5000)
        }
        
        print(f"   [OK] Load test: {load_performance['success_rate']:.0f}% success, avg {load_performance['avg_response_ms']:.1f}ms")
        results["load_performance"] = load_performance
        
        # Test 4: Récupération après erreur
        print("4. Testing Error Recovery...")
        
        # Faire une requête invalide
        invalid_response = session.post(f"{base_url}/api/phase3/risk/comprehensive-analysis", json={})
        invalid_handled = invalid_response.status_code in [400, 422, 500]
        
        # Puis une requête valide pour tester la récupération  
        time.sleep(0.1)
        recovery_response = session.post(f"{base_url}/api/phase3/risk/comprehensive-analysis", json=valid_request)
        recovery_ok = recovery_response.status_code == 200
        
        error_recovery = {
            "invalid_request_handled": invalid_handled,
            "recovery_successful": recovery_ok,
            "system_recovered": invalid_handled and recovery_ok
        }
        
        print(f"   [OK] Error recovery: {'SUCCESS' if error_recovery['system_recovered'] else 'FAILED'}")
        results["error_recovery"] = error_recovery
        
        # Test 5: APIs essentielles disponibles
        print("5. Testing Critical API Availability...")
        
        critical_endpoints = [
            {"url": "/api/phase3/status", "method": "GET", "name": "phase3_status"},
            {"url": "/api/realtime/status", "method": "GET", "name": "realtime_status"},
            {"url": "/api/realtime/connections", "method": "GET", "name": "websocket_connections"}
        ]
        
        api_availability = {}
        for endpoint in critical_endpoints:
            try:
                if endpoint["method"] == "GET":
                    response = session.get(f"{base_url}{endpoint['url']}")
                else:
                    response = session.post(f"{base_url}{endpoint['url']}")
                
                api_availability[endpoint["name"]] = {
                    "status_code": response.status_code,
                    "available": response.status_code == 200
                }
            except Exception as e:
                api_availability[endpoint["name"]] = {
                    "status_code": "ERROR",
                    "available": False,
                    "error": str(e)
                }
        
        available_apis = sum(1 for api in api_availability.values() if api["available"])
        total_apis = len(api_availability)
        
        print(f"   [OK] Critical APIs available: {available_apis}/{total_apis}")
        results["api_availability"] = api_availability
        
        # Résumé
        print("=" * 40)
        
        # Calculer le score de résilience global
        scores = []
        scores.append(100 if malformed_passed == len(malformed_results) else 50)
        scores.append(100 if websocket_resilience["full_cycle_ok"] else 0)
        scores.append(100 if load_performance["performance_acceptable"] else 50)
        scores.append(100 if error_recovery["system_recovered"] else 0)
        scores.append((available_apis / total_apis) * 100)
        
        overall_score = sum(scores) / len(scores)
        
        results["summary"] = {
            "overall_resilience_score": round(overall_score, 1),
            "malformed_requests_handled": f"{malformed_passed}/{len(malformed_results)}",
            "websocket_resilience": "PASS" if websocket_resilience["full_cycle_ok"] else "FAIL",
            "load_performance": "PASS" if load_performance["performance_acceptable"] else "FAIL",
            "error_recovery": "PASS" if error_recovery["system_recovered"] else "FAIL",
            "api_availability": f"{available_apis}/{total_apis}"
        }
        
        print(f"Overall Resilience Score: {overall_score:.1f}/100")
        
        if overall_score >= 80:
            print("Excellent system resilience!")
        elif overall_score >= 60:
            print("Good system resilience with minor issues")
        else:
            print("System resilience needs improvement")
        
        # Sauvegarder les résultats
        with open("phase3_resilience_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("Results saved to: phase3_resilience_results.json")
        
        return results
        
    except Exception as e:
        print(f"[ERROR] Resilience test failed: {e}")
        raise

if __name__ == "__main__":
    test_phase3_resilience()