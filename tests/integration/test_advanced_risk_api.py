"""
Integration tests for Phase 3A Advanced Risk API endpoints
Tests REST API functionality for VaR, stress testing, Monte Carlo simulation
"""
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
from datetime import datetime

from api.main import app


class TestAdvancedRiskAPI:
    """Integration tests for Advanced Risk API endpoints"""
    
    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        return TestClient(app)
    
    @pytest.fixture
    def sample_portfolio(self):
        """Sample portfolio request"""
        return {
            "weights": {"BTC": 0.4, "ETH": 0.3, "SOL": 0.2, "AVAX": 0.1},
            "value": 100000.0
        }
    
    @pytest.fixture
    def mock_price_data(self):
        """Mock historical price data"""
        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=252, freq='D')
        
        price_data = pd.DataFrame({
            'BTC': 50000 * np.exp(np.cumsum(np.random.normal(0, 0.04, 252))),
            'ETH': 3000 * np.exp(np.cumsum(np.random.normal(0, 0.05, 252))),
            'SOL': 100 * np.exp(np.cumsum(np.random.normal(0, 0.07, 252))),
            'AVAX': 50 * np.exp(np.cumsum(np.random.normal(0, 0.06, 252)))
        }, index=dates)
        
        return price_data
    
    def test_var_calculate_endpoint(self, client, sample_portfolio, mock_price_data):
        """Test VaR calculation endpoint"""
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_price_data):
            response = client.post(
                "/api/advanced-risk/var/calculate",
                json=sample_portfolio,
                params={
                    "method": "parametric",
                    "confidence_level": 0.95,
                    "horizon": "daily"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify response structure
            assert "var_value" in data
            assert "expected_shortfall" in data
            assert "confidence_level" in data
            assert "method" in data
            assert "horizon" in data
            assert "portfolio_value" in data
            assert "timestamp" in data
            
            # Verify values
            assert data["confidence_level"] == 0.95
            assert data["method"] == "parametric"
            assert data["horizon"] == "daily"
            assert data["portfolio_value"] == 100000.0
            assert data["var_value"] > 0
            assert data["expected_shortfall"] >= data["var_value"]
    
    def test_var_calculate_historical_method(self, client, sample_portfolio, mock_price_data):
        """Test VaR calculation with historical method"""
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_price_data):
            response = client.post(
                "/api/advanced-risk/var/calculate",
                json=sample_portfolio,
                params={
                    "method": "historical",
                    "confidence_level": 0.99,
                    "horizon": "weekly"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["method"] == "historical"
            assert data["confidence_level"] == 0.99
            assert data["horizon"] == "weekly"
    
    def test_var_invalid_method(self, client, sample_portfolio):
        """Test VaR calculation with invalid method"""
        response = client.post(
            "/api/advanced-risk/var/calculate",
            json=sample_portfolio,
            params={
                "method": "invalid_method",
                "confidence_level": 0.95,
                "horizon": "daily"
            }
        )
        
        assert response.status_code == 400
        assert "invalid_parameter" in response.json()["detail"]
    
    def test_var_invalid_portfolio_weights(self, client):
        """Test VaR calculation with invalid portfolio weights"""
        invalid_portfolio = {
            "weights": {"BTC": 0.6, "ETH": 0.6},  # Sums to 1.2
            "value": 100000.0
        }
        
        response = client.post(
            "/api/advanced-risk/var/calculate",
            json=invalid_portfolio,
            params={
                "method": "parametric",
                "confidence_level": 0.95,
                "horizon": "daily"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_stress_test_run_endpoint(self, client, sample_portfolio, mock_price_data):
        """Test stress test execution endpoint"""
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_price_data):
            response = client.post(
                "/api/advanced-risk/stress-test/run",
                json=sample_portfolio,
                params={"scenario": "crisis_2008"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify response structure
            assert "scenario" in data
            assert "portfolio_loss" in data
            assert "portfolio_loss_pct" in data
            assert "asset_impacts" in data
            assert "shock_applied" in data
            assert "timestamp" in data
            
            # Verify values
            assert data["scenario"] == "crisis_2008"
            assert data["portfolio_loss"] > 0
            assert data["portfolio_loss_pct"] < 0  # Should be negative (loss)
            assert len(data["asset_impacts"]) == 4  # All assets
            assert len(data["shock_applied"]) == 4
    
    def test_stress_test_covid_scenario(self, client, sample_portfolio, mock_price_data):
        """Test stress test with COVID scenario"""
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_price_data):
            response = client.post(
                "/api/advanced-risk/stress-test/run",
                json=sample_portfolio,
                params={"scenario": "covid_2020"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["scenario"] == "covid_2020"
    
    def test_stress_test_invalid_scenario(self, client, sample_portfolio):
        """Test stress test with invalid scenario"""
        response = client.post(
            "/api/advanced-risk/stress-test/run",
            json=sample_portfolio,
            params={"scenario": "invalid_scenario"}
        )
        
        assert response.status_code == 400
        assert "invalid_scenario" in response.json()["detail"]
    
    def test_monte_carlo_simulate_endpoint(self, client, sample_portfolio, mock_price_data):
        """Test Monte Carlo simulation endpoint"""
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_price_data):
            response = client.post(
                "/api/advanced-risk/monte-carlo/simulate",
                json=sample_portfolio,
                params={
                    "simulations": 1000,
                    "horizon_days": 30,
                    "distribution": "student_t"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify response structure
            assert "simulations" in data
            assert "var_estimates" in data
            assert "expected_return" in data
            assert "volatility" in data
            assert "skewness" in data
            assert "kurtosis" in data
            assert "extreme_scenarios" in data
            assert "tail_expectation" in data
            assert "timestamp" in data
            
            # Verify values
            assert data["simulations"] == 1000
            assert isinstance(data["var_estimates"], dict)
            assert len(data["var_estimates"]) > 0
            assert data["volatility"] > 0
    
    def test_monte_carlo_validation_limits(self, client, sample_portfolio):
        """Test Monte Carlo simulation parameter validation"""
        # Test too few simulations
        response = client.post(
            "/api/advanced-risk/monte-carlo/simulate",
            json=sample_portfolio,
            params={"simulations": 500}  # Below minimum of 1000
        )
        assert response.status_code == 422
        
        # Test too many simulations
        response = client.post(
            "/api/advanced-risk/monte-carlo/simulate",
            json=sample_portfolio,
            params={"simulations": 150000}  # Above maximum of 100000
        )
        assert response.status_code == 422
    
    def test_risk_attribution_analyze_endpoint(self, client, sample_portfolio, mock_price_data):
        """Test risk attribution analysis endpoint"""
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_price_data):
            response = client.post(
                "/api/advanced-risk/attribution/analyze",
                json=sample_portfolio,
                params={"confidence_level": 0.95}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify response structure
            assert "marginal_var" in data
            assert "component_var" in data
            assert "concentration_risk" in data
            assert "diversification_ratio" in data
            assert "risk_contribution_pct" in data
            assert "timestamp" in data
            
            # Verify values
            assert len(data["marginal_var"]) == 4  # All assets
            assert len(data["component_var"]) == 4
            assert len(data["risk_contribution_pct"]) == 4
            assert 0 <= data["concentration_risk"] <= 1
            assert data["diversification_ratio"] > 0
            
            # Risk contributions should sum to approximately 100%
            total_contribution = sum(data["risk_contribution_pct"].values())
            assert abs(total_contribution - 100.0) < 1.0
    
    def test_risk_summary_endpoint(self, client, sample_portfolio, mock_price_data):
        """Test comprehensive risk summary endpoint"""
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_price_data):
            response = client.post(
                "/api/advanced-risk/summary",
                json=sample_portfolio,
                params={
                    "include_stress_tests": True,
                    "include_monte_carlo": True
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify response structure
            assert "portfolio_value" in data
            assert "var_daily_95" in data
            assert "var_daily_99" in data
            assert "stress_test_worst" in data
            assert "monte_carlo_summary" in data
            assert "concentration_risk" in data
            assert "risk_score" in data
            assert "alerts_triggered" in data
            assert "timestamp" in data
            
            # Verify values
            assert data["portfolio_value"] == 100000.0
            assert data["var_daily_95"] > 0
            assert data["var_daily_99"] > data["var_daily_95"]  # 99% VaR > 95% VaR
            assert 0 <= data["risk_score"] <= 100
            assert isinstance(data["alerts_triggered"], list)
    
    def test_risk_summary_without_optional_components(self, client, sample_portfolio, mock_price_data):
        """Test risk summary without stress tests and Monte Carlo"""
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_price_data):
            response = client.post(
                "/api/advanced-risk/summary",
                json=sample_portfolio,
                params={
                    "include_stress_tests": False,
                    "include_monte_carlo": False
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should still have VaR and attribution
            assert data["var_daily_95"] > 0
            assert data["var_daily_99"] > 0
            
            # Optional components should be None or minimal
            assert data["stress_test_worst"]["scenario"] is None
            assert data["monte_carlo_summary"]["var_95"] is None
    
    def test_scenarios_list_endpoint(self, client):
        """Test stress scenarios listing endpoint"""
        response = client.get("/api/advanced-risk/scenarios/list")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "scenarios" in data
        scenarios = data["scenarios"]
        assert len(scenarios) >= 5  # Should have all predefined scenarios
        
        # Verify scenario structure
        for scenario in scenarios:
            assert "id" in scenario
            assert "name" in scenario
            assert "description" in scenario
        
        # Check for specific scenarios
        scenario_ids = [s["id"] for s in scenarios]
        assert "crisis_2008" in scenario_ids
        assert "covid_2020" in scenario_ids
        assert "china_ban" in scenario_ids
        assert "tether_collapse" in scenario_ids
    
    def test_methods_info_endpoint(self, client):
        """Test methods information endpoint"""
        response = client.get("/api/advanced-risk/methods/info")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "var_methods" in data
        assert "horizons" in data
        assert "distributions" in data
        
        # Verify VaR methods
        var_methods = data["var_methods"]
        assert "parametric" in var_methods
        assert "historical" in var_methods
        assert "monte_carlo" in var_methods
        
        # Each method should have description and performance info
        for method_info in var_methods.values():
            assert "name" in method_info
            assert "description" in method_info
            assert "performance" in method_info
            assert "accuracy" in method_info
        
        # Verify horizons
        horizons = data["horizons"]
        assert "daily" in horizons
        assert "weekly" in horizons
        assert "monthly" in horizons
        
        # Verify distributions
        distributions = data["distributions"]
        assert "normal" in distributions
        assert "student_t" in distributions


class TestAdvancedRiskAPIErrorHandling:
    """Test error handling in Advanced Risk API"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_missing_portfolio_data(self, client):
        """Test API with missing portfolio data"""
        response = client.post(
            "/api/advanced-risk/var/calculate",
            json={},  # Empty portfolio
            params={"method": "parametric", "confidence_level": 0.95}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_invalid_confidence_level(self, client):
        """Test API with invalid confidence level"""
        portfolio = {
            "weights": {"BTC": 1.0},
            "value": 100000.0
        }
        
        response = client.post(
            "/api/advanced-risk/var/calculate",
            json=portfolio,
            params={
                "method": "parametric",
                "confidence_level": 1.5,  # Invalid (> 1.0)
                "horizon": "daily"
            }
        )
        
        assert response.status_code == 422
    
    def test_risk_engine_initialization_failure(self, client):
        """Test API behavior when risk engine fails to initialize"""
        portfolio = {
            "weights": {"BTC": 1.0},
            "value": 100000.0
        }
        
        with patch('api.advanced_risk_endpoints.create_advanced_risk_engine', 
                  side_effect=Exception("Risk engine init failed")):
            response = client.post(
                "/api/advanced-risk/var/calculate",
                json=portfolio,
                params={"method": "parametric", "confidence_level": 0.95}
            )
            
            assert response.status_code == 500
            assert "risk_engine_initialization_failed" in response.json()["detail"]


# Performance tests
class TestAdvancedRiskAPIPerformance:
    """Performance tests for Advanced Risk API"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def large_portfolio(self):
        """Large portfolio with many assets for performance testing"""
        assets = [f"ASSET_{i}" for i in range(20)]  # 20 assets
        weights = {asset: 1.0/20 for asset in assets}
        return {"weights": weights, "value": 1000000.0}
    
    @pytest.mark.performance
    def test_var_calculation_performance(self, client, large_portfolio):
        """Test VaR calculation performance with large portfolio"""
        import time
        
        # Mock data for large portfolio
        mock_data = pd.DataFrame({
            asset: np.random.normal(0, 0.05, 252) 
            for asset in large_portfolio["weights"].keys()
        })
        
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_data):
            start_time = time.time()
            
            response = client.post(
                "/api/advanced-risk/var/calculate",
                json=large_portfolio,
                params={"method": "parametric", "confidence_level": 0.95}
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            assert response.status_code == 200
            assert execution_time < 2.0  # Should complete within 2 seconds
    
    @pytest.mark.performance
    def test_monte_carlo_performance(self, client, large_portfolio):
        """Test Monte Carlo simulation performance"""
        import time
        
        mock_data = pd.DataFrame({
            asset: np.random.normal(0, 0.05, 252) 
            for asset in large_portfolio["weights"].keys()
        })
        
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_data):
            start_time = time.time()
            
            response = client.post(
                "/api/advanced-risk/monte-carlo/simulate",
                json=large_portfolio,
                params={"simulations": 5000, "horizon_days": 30}
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            assert response.status_code == 200
            assert execution_time < 10.0  # Should complete within 10 seconds