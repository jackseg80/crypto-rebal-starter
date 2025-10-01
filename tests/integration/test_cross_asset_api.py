"""
Integration tests for Phase 2B2 Cross-Asset Correlation API endpoints

Tests the FastAPI endpoints for cross-asset correlation functionality,
including response schemas, error handling, and performance.
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from datetime import datetime, timezone

from api.main import app
from services.alerts.cross_asset_correlation import (
    CorrelationSpike,
    ConcentrationCluster,  # Renamed from CorrelationCluster
    CrossAssetStatus  # Replaces SystemicRiskScore
)


class TestCrossAssetAPI:
    """Integration tests for cross-asset correlation API"""
    
    @pytest.fixture
    def client(self):
        """Create FastAPI test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_analyzer_data(self):
        """Mock correlation analyzer data"""
        return {
            "status_response": {
                "matrix": {
                    "total_assets": 3,
                    "shape": [3, 3],
                    "avg_correlation": 0.65,
                    "max_correlation": 0.85
                },
                "risk_assessment": {
                    "systemic_risk_score": 0.4,
                    "risk_level": "medium"
                },
                "concentration": {
                    "active_clusters": 1,
                    "clusters": [
                        CorrelationCluster(
                            assets=["BTC", "ETH"],
                            avg_correlation=0.85,
                            concentration_score=0.7,
                            risk_level="high"
                        )
                    ]
                },
                "recent_activity": {
                    "spikes_1h": 1,
                    "spikes": [
                        CorrelationSpike(
                            asset_pair=("BTC", "ETH"),
                            current_correlation=0.85,
                            historical_avg=0.60,
                            relative_change=0.417,
                            absolute_change=0.25,
                            timeframe="1h",
                            detected_at=datetime.now(timezone.utc)
                        )
                    ]
                }
            },
            "systemic_risk": SystemicRiskScore(
                score=0.45,
                level="medium",
                factors={
                    "avg_correlation": 0.65,
                    "cluster_concentration": 0.7,
                    "recent_spike_count": 1
                },
                calculated_at=datetime.now(timezone.utc)
            ),
            "top_correlated": [
                {
                    "asset_pair": ["BTC", "ETH"],
                    "correlation": 0.85,
                    "significance": "high"
                },
                {
                    "asset_pair": ["ETH", "SOL"],
                    "correlation": 0.72,
                    "significance": "medium"
                }
            ]
        }
    
    def test_cross_asset_status_endpoint(self, client, mock_analyzer_data):
        """Test /api/alerts/cross-asset/status endpoint"""
        mock_status = mock_analyzer_data["status_response"]
        
        with patch('api.alerts_endpoints.get_alert_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.cross_asset_analyzer.get_correlation_status.return_value = mock_status
            mock_get_engine.return_value = mock_engine
            
            # Test basic request
            response = client.get("/api/alerts/cross-asset/status")
            
            assert response.status_code == 200
            data = response.json()
            
            # Validate response structure
            assert "timestamp" in data
            assert "timeframe" in data
            assert "matrix" in data
            assert "risk_assessment" in data
            assert "concentration" in data
            assert "recent_activity" in data
            assert "performance" in data
            
            # Validate matrix data
            matrix = data["matrix"]
            assert matrix["total_assets"] == 3
            assert matrix["shape"] == [3, 3]
            assert 0 <= matrix["avg_correlation"] <= 1
            assert 0 <= matrix["max_correlation"] <= 1
            
            # Validate risk assessment
            risk = data["risk_assessment"]
            assert 0 <= risk["systemic_risk_score"] <= 1
            assert risk["risk_level"] in ["low", "medium", "high", "systemic"]
    
    def test_cross_asset_status_with_timeframe(self, client):
        """Test status endpoint with different timeframes"""
        with patch('api.alerts_endpoints.get_alert_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.cross_asset_analyzer.get_correlation_status.return_value = {
                "matrix": {"total_assets": 0, "shape": [0, 0], "avg_correlation": 0.0, "max_correlation": 0.0},
                "risk_assessment": {"systemic_risk_score": 0.0, "risk_level": "low"},
                "concentration": {"active_clusters": 0, "clusters": []},
                "recent_activity": {"spikes_1h": 0, "spikes": []}
            }
            mock_get_engine.return_value = mock_engine
            
            # Test each timeframe
            for timeframe in ["1h", "4h", "1d"]:
                response = client.get(f"/api/alerts/cross-asset/status?timeframe={timeframe}")
                assert response.status_code == 200
                data = response.json()
                assert data["timeframe"] == timeframe
    
    def test_systemic_risk_endpoint(self, client, mock_analyzer_data):
        """Test /api/alerts/cross-asset/systemic-risk endpoint"""
        mock_risk = mock_analyzer_data["systemic_risk"]
        
        with patch('api.alerts_endpoints.get_alert_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.cross_asset_analyzer.calculate_systemic_risk.return_value = mock_risk
            mock_get_engine.return_value = mock_engine
            
            response = client.get("/api/alerts/cross-asset/systemic-risk")
            
            assert response.status_code == 200
            data = response.json()
            
            # Validate response structure
            assert "timeframe" in data
            assert "systemic_risk" in data
            assert "recommendations" in data
            assert "calculated_at" in data
            
            # Validate systemic risk data
            risk_data = data["systemic_risk"]
            assert 0 <= risk_data["score"] <= 1
            assert risk_data["level"] in ["low", "medium", "high", "systemic"]
            assert "factors" in risk_data
            
            # Validate factors
            factors = risk_data["factors"]
            assert "avg_correlation" in factors
            assert isinstance(data["recommendations"], list)
    
    def test_top_correlated_endpoint(self, client, mock_analyzer_data):
        """Test /api/alerts/cross-asset/top-correlated endpoint"""
        mock_pairs = mock_analyzer_data["top_correlated"]
        
        with patch('api.alerts_endpoints.get_alert_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.cross_asset_analyzer.get_top_correlated_pairs.return_value = mock_pairs
            mock_get_engine.return_value = mock_engine
            
            # Test with default limit
            response = client.get("/api/alerts/cross-asset/top-correlated")
            
            assert response.status_code == 200
            data = response.json()
            
            # Validate response structure
            assert "timeframe" in data
            assert "top_n" in data
            assert "pairs" in data
            assert "calculated_at" in data
            
            # Validate pairs data
            pairs = data["pairs"]
            assert isinstance(pairs, list)
            for pair in pairs:
                assert "asset_pair" in pair
                assert "correlation" in pair
                assert "significance" in pair
                assert len(pair["asset_pair"]) == 2
                assert 0 <= pair["correlation"] <= 1
    
    def test_top_correlated_with_limit(self, client):
        """Test top-correlated endpoint with custom limit"""
        with patch('api.alerts_endpoints.get_alert_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.cross_asset_analyzer.get_top_correlated_pairs.return_value = []
            mock_get_engine.return_value = mock_engine
            
            # Test with custom limit
            response = client.get("/api/alerts/cross-asset/top-correlated?limit=10")
            assert response.status_code == 200
            data = response.json()
            assert data["top_n"] == 10
            
            # Test with maximum limit (should be capped)
            response = client.get("/api/alerts/cross-asset/top-correlated?limit=1000")
            assert response.status_code == 200
            data = response.json()
            assert data["top_n"] <= 50  # Should be capped at 50
    
    def test_cross_asset_disabled_scenario(self, client):
        """Test endpoints when cross-asset analysis is disabled"""
        with patch('api.alerts_endpoints.get_alert_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.cross_asset_analyzer = None  # Disabled
            mock_get_engine.return_value = mock_engine
            
            # All endpoints should return appropriate responses
            endpoints = [
                "/api/alerts/cross-asset/status",
                "/api/alerts/cross-asset/systemic-risk",
                "/api/alerts/cross-asset/top-correlated"
            ]
            
            for endpoint in endpoints:
                response = client.get(endpoint)
                assert response.status_code in [200, 503]  # Either works with defaults or service unavailable
    
    def test_invalid_timeframe_parameter(self, client):
        """Test endpoints with invalid timeframe parameters"""
        with patch('api.alerts_endpoints.get_alert_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.cross_asset_analyzer.get_correlation_status.side_effect = ValueError("Invalid timeframe")
            mock_get_engine.return_value = mock_engine
            
            response = client.get("/api/alerts/cross-asset/status?timeframe=invalid")
            assert response.status_code == 400
    
    def test_error_handling(self, client):
        """Test error handling for various failure scenarios"""
        with patch('api.alerts_endpoints.get_alert_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.cross_asset_analyzer.get_correlation_status.side_effect = Exception("Internal error")
            mock_get_engine.return_value = mock_engine
            
            response = client.get("/api/alerts/cross-asset/status")
            assert response.status_code == 500
            
            error_data = response.json()
            assert "detail" in error_data
    
    def test_response_performance(self, client):
        """Test API response performance requirements"""
        import time
        
        with patch('api.alerts_endpoints.get_alert_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.cross_asset_analyzer.get_correlation_status.return_value = {
                "matrix": {"total_assets": 0, "shape": [0, 0], "avg_correlation": 0.0, "max_correlation": 0.0},
                "risk_assessment": {"systemic_risk_score": 0.0, "risk_level": "low"},
                "concentration": {"active_clusters": 0, "clusters": []},
                "recent_activity": {"spikes_1h": 0, "spikes": []},
                "performance": {"calculation_latency_ms": 25.0}
            }
            mock_get_engine.return_value = mock_engine
            
            start_time = time.time()
            response = client.get("/api/alerts/cross-asset/status")
            elapsed_ms = (time.time() - start_time) * 1000
            
            assert response.status_code == 200
            assert elapsed_ms < 100, f"API response too slow: {elapsed_ms:.1f}ms > 100ms"
    
    def test_response_schemas(self, client, mock_analyzer_data):
        """Test that response schemas match expected formats"""
        # This test ensures our API responses match the expected JSON schemas
        with patch('api.alerts_endpoints.get_alert_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.cross_asset_analyzer.get_correlation_status.return_value = mock_analyzer_data["status_response"]
            mock_get_engine.return_value = mock_engine
            
            response = client.get("/api/alerts/cross-asset/status")
            assert response.status_code == 200
            
            # Validate response can be parsed as JSON
            data = response.json()
            
            # Validate required fields are present and correct types
            assert isinstance(data["timestamp"], str)
            assert isinstance(data["timeframe"], str)
            assert isinstance(data["matrix"], dict)
            assert isinstance(data["risk_assessment"], dict)
            assert isinstance(data["concentration"], dict)
            assert isinstance(data["recent_activity"], dict)
            assert isinstance(data["performance"], dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])