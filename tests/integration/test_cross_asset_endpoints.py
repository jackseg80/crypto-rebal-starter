"""
Simple integration tests for Phase 2B2 Cross-Asset API endpoints

Tests that the API endpoints return valid responses without mocking.
"""

import pytest
import requests
import time


class TestCrossAssetEndpoints:
    """Test cross-asset correlation API endpoints"""
    
    @pytest.fixture(scope="class")
    def base_url(self):
        """Base URL for API testing"""
        return "http://localhost:8000"
    
    @pytest.fixture(scope="class") 
    def wait_for_server(self, base_url):
        """Wait for server to be ready"""
        max_retries = 10
        for i in range(max_retries):
            try:
                response = requests.get(f"{base_url}/docs", timeout=5)
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                if i < max_retries - 1:
                    time.sleep(1)
                    continue
                raise
        return False
    
    def test_cross_asset_status_endpoint(self, base_url, wait_for_server):
        """Test /api/alerts/cross-asset/status endpoint"""
        if not wait_for_server:
            pytest.skip("Server not available")
            
        response = requests.get(f"{base_url}/api/alerts/cross-asset/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        required_fields = ["timestamp", "timeframe", "matrix", "risk_assessment", 
                          "concentration", "recent_activity", "performance"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Validate data types
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["timeframe"], str) 
        assert isinstance(data["matrix"], dict)
        assert isinstance(data["risk_assessment"], dict)
        assert isinstance(data["concentration"], dict)
        assert isinstance(data["recent_activity"], dict)
        assert isinstance(data["performance"], dict)
    
    def test_systemic_risk_endpoint(self, base_url, wait_for_server):
        """Test /api/alerts/cross-asset/systemic-risk endpoint"""
        if not wait_for_server:
            pytest.skip("Server not available")
            
        response = requests.get(f"{base_url}/api/alerts/cross-asset/systemic-risk")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        required_fields = ["timeframe", "systemic_risk", "recommendations", "calculated_at"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Validate systemic risk data
        risk_data = data["systemic_risk"]
        assert "score" in risk_data
        assert "level" in risk_data
        assert "factors" in risk_data
        
        # Validate score is in valid range
        assert 0 <= risk_data["score"] <= 1
        assert risk_data["level"] in ["low", "medium", "high", "systemic"]
    
    def test_top_correlated_endpoint(self, base_url, wait_for_server):
        """Test /api/alerts/cross-asset/top-correlated endpoint"""
        if not wait_for_server:
            pytest.skip("Server not available")
            
        response = requests.get(f"{base_url}/api/alerts/cross-asset/top-correlated")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        required_fields = ["timeframe", "top_n", "pairs", "calculated_at"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Validate pairs data
        assert isinstance(data["pairs"], list)
        assert isinstance(data["top_n"], int)
    
    def test_timeframe_parameter(self, base_url, wait_for_server):
        """Test endpoints with different timeframe parameters"""
        if not wait_for_server:
            pytest.skip("Server not available")
        
        timeframes = ["1h", "4h", "1d"]
        
        for timeframe in timeframes:
            response = requests.get(
                f"{base_url}/api/alerts/cross-asset/status?timeframe={timeframe}"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["timeframe"] == timeframe
    
    def test_limit_parameter(self, base_url, wait_for_server):
        """Test top-correlated endpoint with limit parameter"""
        if not wait_for_server:
            pytest.skip("Server not available")
            
        response = requests.get(
            f"{base_url}/api/alerts/cross-asset/top-correlated?limit=5"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["top_n"] == 5
    
    def test_response_performance(self, base_url, wait_for_server):
        """Test that API responses are reasonably fast"""
        if not wait_for_server:
            pytest.skip("Server not available")
            
        endpoints = [
            "/api/alerts/cross-asset/status",
            "/api/alerts/cross-asset/systemic-risk", 
            "/api/alerts/cross-asset/top-correlated"
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            response = requests.get(f"{base_url}{endpoint}")
            elapsed_ms = (time.time() - start_time) * 1000
            
            assert response.status_code == 200
            assert elapsed_ms < 1000, f"Endpoint {endpoint} too slow: {elapsed_ms:.1f}ms"
    
    def test_invalid_parameters(self, base_url, wait_for_server):
        """Test error handling for invalid parameters"""
        if not wait_for_server:
            pytest.skip("Server not available")
            
        # Test invalid timeframe
        response = requests.get(
            f"{base_url}/api/alerts/cross-asset/status?timeframe=invalid"
        )
        assert response.status_code in [400, 422, 500]  # Some form of error
        
        # Test invalid limit (too high)
        response = requests.get(
            f"{base_url}/api/alerts/cross-asset/top-correlated?limit=1000"
        )
        assert response.status_code == 200  # Should work but cap the limit
        data = response.json()
        assert data["top_n"] <= 50  # Should be capped


if __name__ == "__main__":
    pytest.main([__file__, "-v"])