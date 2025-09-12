"""
Tests des scénarios d'échec et de récupération Phase 3
Valide la résilience du système face aux pannes
"""
import json
import time
import requests
from typing import Dict, Any

class FailureScenarioTests:
    """Tests de résilience et récupération"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_invalid_var_requests(self) -> Dict[str, Any]:
        """Test 1: Requêtes VaR invalides"""
        print("1. Testing Invalid VaR Requests...")
        
        test_cases = [
            {
                "name": "negative_portfolio_value",
                "data": {
                    "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
                    "portfolio_value": -10000,  # Négatif
                    "analysis_types": ["var_parametric"],
                    "confidence_levels": [0.95],
                    "horizons": ["1d"]
                },
                "expected_status": [400, 422]
            },
            {
                "name": "invalid_confidence_level",
                "data": {
                    "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
                    "portfolio_value": 10000,
                    "analysis_types": ["var_parametric"],
                    "confidence_levels": [1.5],  # > 1.0
                    "horizons": ["1d"]
                },
                "expected_status": [400, 422]
            },
            {
                "name": "invalid_weights_sum",
                "data": {
                    "portfolio_weights": {"BTC": 0.8, "ETH": 0.4},  # Sum > 1.0
                    "portfolio_value": 10000,
                    "analysis_types": ["var_parametric"],
                    "confidence_levels": [0.95],
                    "horizons": ["1d"]
                },
                "expected_status": [400, 422]
            },
            {
                "name": "unknown_asset",
                "data": {
                    "portfolio_weights": {"UNKNOWN_COIN": 1.0},
                    "portfolio_value": 10000,
                    "analysis_types": ["var_parametric"],
                    "confidence_levels": [0.95],
                    "horizons": ["1d"]
                },
                "expected_status": [400, 422, 500]
            }
        ]
        
        results = {}
        for test_case in test_cases:
            print(f"   Testing {test_case['name']}...")
            
            start = time.time()
            response = self.session.post(
                f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
                json=test_case["data"]
            )
            duration = (time.time() - start) * 1000
            
            # Vérifier que l'erreur est gérée gracieusement
            status_ok = response.status_code in test_case["expected_status"]
            
            results[test_case["name"]] = {
                "status_code": response.status_code,
                "duration_ms": round(duration, 1),
                "graceful_error": status_ok,
                "status": "PASS" if status_ok else "FAIL"
            }
            
            print(f"      [{results[test_case['name']]['status']}] Status: {response.status_code}, Duration: {duration:.1f}ms")
        
        passed = len([r for r in results.values() if r["status"] == "PASS"])
        total = len(results)
        print(f"   [OK] Invalid requests handled: {passed}/{total}")
        
        return results
    
    def test_malformed_requests(self) -> Dict[str, Any]:
        """Test 2: Requêtes malformées"""
        print("2. Testing Malformed Requests...")
        
        test_cases = [
            {
                "name": "missing_required_fields",
                "data": {"portfolio_value": 10000},  # Manque portfolio_weights
                "expected_status": [400, 422]
            },
            {
                "name": "wrong_data_types",
                "data": {
                    "portfolio_weights": "not_a_dict",  # String au lieu de dict
                    "portfolio_value": "not_a_number",  # String au lieu de nombre
                    "analysis_types": ["var_parametric"],
                    "confidence_levels": [0.95],
                    "horizons": ["1d"]
                },
                "expected_status": [400, 422]
            },
            {
                "name": "empty_request",
                "data": {},
                "expected_status": [400, 422]
            }
        ]
        
        results = {}
        for test_case in test_cases:
            print(f"   Testing {test_case['name']}...")
            
            start = time.time()
            try:
                response = self.session.post(
                    f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
                    json=test_case["data"]
                )
                duration = (time.time() - start) * 1000
                
                status_ok = response.status_code in test_case["expected_status"]
                
                results[test_case["name"]] = {
                    "status_code": response.status_code,
                    "duration_ms": round(duration, 1),
                    "graceful_error": status_ok,
                    "status": "PASS" if status_ok else "FAIL"
                }
            except Exception as e:
                duration = (time.time() - start) * 1000
                results[test_case["name"]] = {
                    "status_code": "EXCEPTION",
                    "duration_ms": round(duration, 1),
                    "error": str(e),
                    "status": "FAIL"
                }
            
            print(f"      [{results[test_case['name']]['status']}] Response: {results[test_case['name']]['status_code']}")
        
        passed = len([r for r in results.values() if r["status"] == "PASS"])
        total = len(results)
        print(f"   [OK] Malformed requests handled: {passed}/{total}")
        
        return results
    
    def test_websocket_resilience(self) -> Dict[str, Any]:
        """Test 3: Résilience WebSocket"""
        print("3. Testing WebSocket Resilience...")
        
        results = {}
        
        # Test arrêt/redémarrage du moteur temps réel
        print("   Testing engine stop/start cycle...")
        
        # Arrêter le moteur
        stop_response = self.session.post(f"{self.base_url}/api/realtime/stop")
        assert stop_response.status_code == 200
        
        # Vérifier le statut
        status_response = self.session.get(f"{self.base_url}/api/realtime/status")
        status_data = status_response.json()
        
        results["stop_engine"] = {
            "status": "PASS" if status_data["status"] in ["stopped", "inactive"] else "FAIL",
            "engine_status": status_data["status"]
        }
        
        # Redémarrer le moteur
        start_response = self.session.post(f"{self.base_url}/api/realtime/start")
        assert start_response.status_code == 200
        
        # Vérifier que le redémarrage fonctionne
        time.sleep(1)  # Laisser le temps au moteur de démarrer
        status_response = self.session.get(f"{self.base_url}/api/realtime/status")
        status_data = status_response.json()
        
        results["restart_engine"] = {
            "status": "PASS" if status_data["status"] in ["healthy", "running"] else "FAIL",
            "engine_status": status_data["status"]
        }
        
        print(f"      [OK] Engine stop/restart cycle completed")
        
        # Test broadcast sans connexions actives
        print("   Testing broadcast with no active connections...")
        broadcast_data = {"type": "test", "message": "No connections test"}
        
        broadcast_response = self.session.post(f"{self.base_url}/api/realtime/broadcast", json=broadcast_data)
        broadcast_result = broadcast_response.json()
        
        results["broadcast_no_connections"] = {
            "status": "PASS" if broadcast_result["success"] else "FAIL",
            "target_connections": broadcast_result.get("target_connections", 0),
            "success": broadcast_result["success"]
        }
        
        print(f"      [OK] Broadcast without connections handled")
        
        return results
    
    def test_high_load_var_requests(self) -> Dict[str, Any]:
        """Test 4: Charge élevée sur VaR API"""
        print("4. Testing High Load on VaR API...")
        
        request_data = {
            "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
            "portfolio_value": 10000,
            "analysis_types": ["var_parametric"],
            "confidence_levels": [0.95],
            "horizons": ["1d"]
        }
        
        # Faire 10 requêtes rapidement
        print("   Sending 10 concurrent-ish requests...")
        times = []
        errors = 0
        
        for i in range(10):
            start = time.time()
            try:
                response = self.session.post(
                    f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
                    json=request_data,
                    timeout=30  # 30 secondes timeout
                )
                duration = (time.time() - start) * 1000
                times.append(duration)
                
                if response.status_code != 200:
                    errors += 1
                    
            except Exception as e:
                duration = (time.time() - start) * 1000
                times.append(duration)
                errors += 1
                print(f"      Request {i+1} failed: {e}")
        
        avg_time = sum(times) / len(times) if times else 0
        max_time = max(times) if times else 0
        min_time = min(times) if times else 0
        success_rate = ((10 - errors) / 10) * 100
        
        results = {
            "total_requests": 10,
            "errors": errors,
            "success_rate_pct": round(success_rate, 1),
            "avg_response_ms": round(avg_time, 1),
            "min_response_ms": round(min_time, 1),
            "max_response_ms": round(max_time, 1),
            "status": "PASS" if success_rate >= 80 else "FAIL"  # Au moins 80% de succès
        }
        
        print(f"   [OK] High load test: {success_rate:.1f}% success rate, avg {avg_time:.1f}ms")
        
        return results
    
    def test_recovery_after_errors(self) -> Dict[str, Any]:
        """Test 5: Récupération après erreurs"""
        print("5. Testing Recovery After Errors...")
        
        # Générer plusieurs erreurs consécutives
        print("   Generating consecutive errors...")
        for i in range(3):
            invalid_data = {"portfolio_weights": {"INVALID": i}}
            response = self.session.post(
                f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
                json=invalid_data
            )
            # Ces requêtes doivent échouer
            assert response.status_code in [400, 422, 500]
        
        # Vérifier que le système peut encore traiter des requêtes valides
        print("   Testing recovery with valid request...")
        valid_data = {
            "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
            "portfolio_value": 10000,
            "analysis_types": ["var_parametric"],
            "confidence_levels": [0.95],
            "horizons": ["1d"]
        }
        
        start = time.time()
        response = self.session.post(
            f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
            json=valid_data
        )
        duration = (time.time() - start) * 1000
        
        recovery_success = response.status_code == 200
        
        results = {
            "errors_generated": 3,
            "recovery_successful": recovery_success,
            "recovery_response_time_ms": round(duration, 1),
            "status": "PASS" if recovery_success else "FAIL"
        }
        
        print(f"   [OK] Recovery test: {'SUCCESS' if recovery_success else 'FAILED'}")
        
        return results
    
    def run_all_failure_tests(self) -> Dict[str, Any]:
        """Exécuter tous les tests d'échec"""
        print("Phase 3 Failure & Recovery Test Suite")
        print("=" * 45)
        
        all_results = {}
        start_time = time.time()
        
        try:
            all_results["invalid_var_requests"] = self.test_invalid_var_requests()
            all_results["malformed_requests"] = self.test_malformed_requests()
            all_results["websocket_resilience"] = self.test_websocket_resilience()
            all_results["high_load_test"] = self.test_high_load_var_requests()
            all_results["recovery_test"] = self.test_recovery_after_errors()
            
            total_duration = time.time() - start_time
            
            # Compter les succès
            test_categories = len(all_results)
            successful_categories = 0
            
            for category, results in all_results.items():
                if isinstance(results, dict):
                    if "status" in results and results["status"] == "PASS":
                        successful_categories += 1
                    elif isinstance(results, dict) and all(
                        r.get("status") == "PASS" for r in results.values() if isinstance(r, dict)
                    ):
                        successful_categories += 1
            
            print("=" * 45)
            print(f"Failure Tests Completed in {total_duration:.1f}s")
            print(f"Categories passed: {successful_categories}/{test_categories}")
            
            if successful_categories == test_categories:
                print("System demonstrates excellent resilience!")
            else:
                print("Some resilience issues detected - review results")
            
            all_results["summary"] = {
                "total_duration_s": round(total_duration, 1),
                "categories_passed": successful_categories,
                "categories_total": test_categories,
                "resilience_score": round((successful_categories / test_categories) * 100, 1)
            }
            
            return all_results
            
        except Exception as e:
            print(f"[ERROR] Failure test suite failed: {e}")
            raise

if __name__ == "__main__":
    tester = FailureScenarioTests()
    results = tester.run_all_failure_tests()
    
    # Sauvegarder les résultats
    with open("phase3_failure_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: phase3_failure_test_results.json")