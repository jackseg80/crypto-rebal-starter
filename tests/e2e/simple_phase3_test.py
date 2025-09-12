"""
Tests rapides Phase 3 - version simple sans emojis
"""
import json
import time
import requests

def test_phase3_integration():
    """Test d'intégration rapide Phase 3"""
    base_url = "http://localhost:8000"
    session = requests.Session()
    
    print("Phase 3 E2E Integration Tests")
    print("=" * 40)
    
    results = {}
    
    try:
        # Test 1: Status Phase 3
        print("1. Testing Phase 3 Status...")
        start = time.time()
        response = session.get(f"{base_url}/api/phase3/status")
        duration = (time.time() - start) * 1000
        
        assert response.status_code == 200
        data = response.json()
        assert "phase_3a_advanced_risk" in data
        assert "phase_3b_realtime_streaming" in data
        assert "phase_3c_hybrid_intelligence" in data
        
        print(f"   [OK] Status API: {duration:.1f}ms")
        results["status"] = {"duration_ms": round(duration, 1), "status": "PASS"}
        
        # Test 2: VaR Analysis
        print("2. Testing VaR Analysis...")
        request_data = {
            "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
            "portfolio_value": 10000,
            "analysis_types": ["var_parametric", "var_historical"],
            "confidence_levels": [0.95],
            "horizons": ["1d"]
        }
        
        start = time.time()
        response = session.post(f"{base_url}/api/phase3/risk/comprehensive-analysis", json=request_data)
        duration = (time.time() - start) * 1000
        
        assert response.status_code == 200
        var_data = response.json()
        assert "var_analysis" in var_data
        assert "95%_1d" in var_data["var_analysis"]
        
        var_95 = var_data["var_analysis"]["95%_1d"]
        param_var = var_95["parametric_var"]
        hist_var = var_95["historical_var"]
        
        print(f"   [OK] VaR API: {duration:.1f}ms")
        print(f"        Parametric VaR: ${param_var:.2f}")
        print(f"        Historical VaR: ${hist_var:.2f}")
        results["var"] = {"duration_ms": round(duration, 1), "param_var": param_var, "hist_var": hist_var, "status": "PASS"}
        
        # Test 3: Real-time System
        print("3. Testing Real-time System...")
        
        # Start engine
        start_response = session.post(f"{base_url}/api/realtime/start")
        assert start_response.status_code == 200
        
        # Check status
        start = time.time()
        status_response = session.get(f"{base_url}/api/realtime/status")
        duration = (time.time() - start) * 1000
        
        assert status_response.status_code == 200
        rt_data = status_response.json()
        assert rt_data["status"] in ["healthy", "running"]
        
        # Check connections
        conn_response = session.get(f"{base_url}/api/realtime/connections")
        assert conn_response.status_code == 200
        conn_data = conn_response.json()
        
        print(f"   [OK] Real-time Status: {duration:.1f}ms")
        print(f"        Active connections: {conn_data.get('total_connections', 0)}")
        results["realtime"] = {"duration_ms": round(duration, 1), "connections": conn_data.get('total_connections', 0), "status": "PASS"}
        
        # Test 4: WebSocket Broadcast
        print("4. Testing WebSocket Broadcast...")
        broadcast_data = {"type": "test", "message": "E2E test"}
        
        start = time.time()
        broadcast_response = session.post(f"{base_url}/api/realtime/broadcast", json=broadcast_data)
        duration = (time.time() - start) * 1000
        
        assert broadcast_response.status_code == 200
        broadcast_result = broadcast_response.json()
        assert broadcast_result["success"] is True
        
        print(f"   [OK] Broadcast: {duration:.1f}ms to {broadcast_result.get('target_connections', 0)} clients")
        results["broadcast"] = {"duration_ms": round(duration, 1), "target_connections": broadcast_result.get('target_connections', 0), "status": "PASS"}
        
        # Test 5: Performance Check
        print("5. Performance Check...")
        var_times = []
        for i in range(3):
            start = time.time()
            response = session.post(f"{base_url}/api/phase3/risk/comprehensive-analysis", json=request_data)
            var_times.append((time.time() - start) * 1000)
            assert response.status_code == 200
        
        avg_time = sum(var_times) / len(var_times)
        print(f"   [OK] Average VaR response: {avg_time:.1f}ms (3 calls)")
        results["performance"] = {"avg_var_ms": round(avg_time, 1), "status": "PASS"}
        
        # Summary
        print("=" * 40)
        passed_tests = len([r for r in results.values() if r["status"] == "PASS"])
        total_tests = len(results)
        print(f"Tests Results: {passed_tests}/{total_tests} PASSED")
        
        if passed_tests == total_tests:
            print("All Phase 3 systems are working correctly!")
        else:
            print("Some tests failed - check results above")
        
        # Save results
        with open("phase3_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("Results saved to: phase3_test_results.json")
        
        return results
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        raise

if __name__ == "__main__":
    test_phase3_integration()