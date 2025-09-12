"""
Tests rapides Phase 3 - APIs seulement (pas d'UI)
Pour validation rapide sans dépendances Selenium
"""
import json
import time
import requests
from typing import Dict, Any

class QuickPhase3Test:
    """Tests rapides pour validation Phase 3"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = {}
    
    def test_phase3_status(self) -> Dict[str, Any]:
        """Test 1: Status Phase 3"""
        print("[Status] Testing Phase 3 Status...")
        
        start = time.time()
        response = self.session.get(f"{self.base_url}/api/phase3/status")
        duration = (time.time() - start) * 1000
        
        assert response.status_code == 200
        data = response.json()
        
        required_components = [
            "phase_3a_advanced_risk",
            "phase_3b_realtime_streaming", 
            "phase_3c_hybrid_intelligence"
        ]
        
        for component in required_components:
            assert component in data, f"Missing component: {component}"
            assert data[component]["status"] in ["active", "healthy"], f"{component} not active"
        
        result = {
            "status": "PASS",
            "response_time_ms": round(duration, 1),
            "components_active": len([c for c in required_components if data[c]["status"] in ["active", "healthy"]])
        }
        
        print(f"   [OK] Status API: {duration:.1f}ms - {result['components_active']}/3 components active")
        return result
    
    def test_var_analysis(self) -> Dict[str, Any]:
        """Test 2: Analyse VaR complète"""
        print("📊 Testing VaR Analysis API...")
        
        request_data = {
            "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
            "portfolio_value": 10000,
            "analysis_types": ["var_parametric", "var_historical"],
            "confidence_levels": [0.95],
            "horizons": ["1d"]
        }
        
        start = time.time()
        response = self.session.post(
            f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
            json=request_data
        )
        duration = (time.time() - start) * 1000
        
        assert response.status_code == 200
        data = response.json()
        
        # Vérifications
        assert "var_analysis" in data
        assert "95%_1d" in data["var_analysis"]
        
        var_95 = data["var_analysis"]["95%_1d"]
        assert "parametric_var" in var_95
        assert "historical_var" in var_95
        assert var_95["parametric_var"] > 0
        assert var_95["historical_var"] > 0
        
        result = {
            "status": "✅ PASS",
            "response_time_ms": round(duration, 1),
            "parametric_var": round(var_95["parametric_var"], 2),
            "historical_var": round(var_95["historical_var"], 2),
            "portfolio_value": data["portfolio_value"]
        }
        
        print(f"   ✅ VaR API: {duration:.1f}ms")
        print(f"      Parametric VaR: ${result['parametric_var']}")
        print(f"      Historical VaR: ${result['historical_var']}")
        return result
    
    def test_realtime_system(self) -> Dict[str, Any]:
        """Test 3: Système temps réel"""
        print("⚡ Testing Real-time System...")
        
        # S'assurer que le moteur est démarré
        start_response = self.session.post(f"{self.base_url}/api/realtime/start")
        assert start_response.status_code == 200
        
        # Test status
        start = time.time()
        status_response = self.session.get(f"{self.base_url}/api/realtime/status")
        status_duration = (time.time() - start) * 1000
        
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] in ["healthy", "running"]
        
        # Test connexions
        start = time.time()
        connections_response = self.session.get(f"{self.base_url}/api/realtime/connections")
        conn_duration = (time.time() - start) * 1000
        
        assert connections_response.status_code == 200
        conn_data = connections_response.json()
        
        result = {
            "status": "✅ PASS",
            "status_response_time_ms": round(status_duration, 1),
            "connections_response_time_ms": round(conn_duration, 1),
            "active_connections": conn_data.get("total_connections", 0),
            "engine_status": status_data["status"]
        }
        
        print(f"   ✅ Real-time Status: {status_duration:.1f}ms")
        print(f"   ✅ Connections: {conn_duration:.1f}ms - {result['active_connections']} active")
        return result
    
    def test_websocket_broadcast(self) -> Dict[str, Any]:
        """Test 4: Test de broadcast WebSocket"""
        print("📡 Testing WebSocket Broadcast...")
        
        test_message = {
            "type": "test_message",
            "message": "E2E test broadcast",
            "timestamp": time.time()
        }
        
        start = time.time()
        response = self.session.post(
            f"{self.base_url}/api/realtime/broadcast",
            json=test_message
        )
        duration = (time.time() - start) * 1000
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        result = {
            "status": "✅ PASS",
            "response_time_ms": round(duration, 1),
            "target_connections": data.get("target_connections", 0),
            "broadcast_successful": data["success"]
        }
        
        print(f"   ✅ Broadcast: {duration:.1f}ms to {result['target_connections']} connections")
        return result
    
    def test_error_handling(self) -> Dict[str, Any]:
        """Test 5: Gestion d'erreurs"""
        print("🛡️ Testing Error Handling...")
        
        # Test avec données invalides
        invalid_data = {
            "portfolio_weights": {"INVALID": 1.0},
            "portfolio_value": -1000,
            "analysis_types": ["invalid_method"],
            "confidence_levels": [1.5],  # > 1.0
            "horizons": ["invalid"]
        }
        
        start = time.time()
        response = self.session.post(
            f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
            json=invalid_data
        )
        duration = (time.time() - start) * 1000
        
        # Devrait retourner une erreur, pas un crash
        assert response.status_code in [400, 422, 500]
        
        result = {
            "status": "✅ PASS",
            "response_time_ms": round(duration, 1),
            "error_code": response.status_code,
            "graceful_error_handling": True
        }
        
        print(f"   ✅ Error Handling: {duration:.1f}ms - Status {response.status_code}")
        return result
    
    def test_performance_benchmarks(self) -> Dict[str, Any]:
        """Test 6: Benchmarks de performance"""
        print("🏃 Running Performance Benchmarks...")
        
        benchmarks = {}
        
        # Test VaR performance (5 appels)
        var_times = []
        for i in range(5):
            start = time.time()
            response = self.session.post(
                f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
                json={
                    "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
                    "portfolio_value": 10000,
                    "analysis_types": ["var_parametric"],
                    "confidence_levels": [0.95],
                    "horizons": ["1d"]
                }
            )
            duration = (time.time() - start) * 1000
            var_times.append(duration)
            assert response.status_code == 200
        
        # Test Status performance (10 appels)
        status_times = []
        for i in range(10):
            start = time.time()
            response = self.session.get(f"{self.base_url}/api/phase3/status")
            duration = (time.time() - start) * 1000
            status_times.append(duration)
            assert response.status_code == 200
        
        result = {
            "status": "✅ PASS",
            "var_api": {
                "avg_ms": round(sum(var_times) / len(var_times), 1),
                "min_ms": round(min(var_times), 1),
                "max_ms": round(max(var_times), 1)
            },
            "status_api": {
                "avg_ms": round(sum(status_times) / len(status_times), 1),
                "min_ms": round(min(status_times), 1),
                "max_ms": round(max(status_times), 1)
            }
        }
        
        print(f"   ✅ VaR API: avg {result['var_api']['avg_ms']}ms (min: {result['var_api']['min_ms']}, max: {result['var_api']['max_ms']})")
        print(f"   ✅ Status API: avg {result['status_api']['avg_ms']}ms (min: {result['status_api']['min_ms']}, max: {result['status_api']['max_ms']})")
        
        return result
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Exécuter tous les tests"""
        print("🧪 Phase 3 E2E Quick Test Suite")
        print("=" * 50)
        
        results = {}
        total_start = time.time()
        
        try:
            results["phase3_status"] = self.test_phase3_status()
            results["var_analysis"] = self.test_var_analysis()
            results["realtime_system"] = self.test_realtime_system()
            results["websocket_broadcast"] = self.test_websocket_broadcast()
            results["error_handling"] = self.test_error_handling()
            results["performance_benchmarks"] = self.test_performance_benchmarks()
            
            total_duration = time.time() - total_start
            
            # Résumé
            passed_tests = len([r for r in results.values() if r["status"] == "✅ PASS"])
            total_tests = len(results)
            
            print("=" * 50)
            print(f"🎉 Test Suite Completed in {total_duration:.1f}s")
            print(f"✅ {passed_tests}/{total_tests} tests passed")
            
            if passed_tests == total_tests:
                print("🚀 All Phase 3 systems are working correctly!")
            else:
                print("⚠️ Some tests failed - check results above")
            
            results["summary"] = {
                "total_duration_s": round(total_duration, 1),
                "tests_passed": passed_tests,
                "tests_total": total_tests,
                "success_rate": round((passed_tests / total_tests) * 100, 1)
            }
            
            return results
            
        except Exception as e:
            print(f"❌ Test suite failed: {e}")
            raise

if __name__ == "__main__":
    # Exécution directe
    tester = QuickPhase3Test()
    results = tester.run_all_tests()
    
    # Optionally save results
    with open("phase3_test_results.json", "w") as f:
        json.dump(results, f, indent=2)