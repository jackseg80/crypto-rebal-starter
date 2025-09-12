"""
Unit tests for Phase 3A Advanced Risk Engine
Tests VaR calculations, stress testing, Monte Carlo simulation, and risk attribution
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from typing import Dict

from services.risk.advanced_risk_engine import (
    AdvancedRiskEngine, create_advanced_risk_engine,
    VaRMethod, RiskHorizon, StressScenario,
    VaRResult, StressTestResult, MonteCarloResult, RiskAttributionResult
)


class TestAdvancedRiskEngine:
    """Test cases for the Advanced Risk Engine"""
    
    @pytest.fixture
    def config(self):
        """Default configuration for testing"""
        return {
            "enabled": True,
            "var": {
                "confidence_levels": [0.95, 0.99],
                "methods": ["parametric", "historical", "monte_carlo"],
                "lookback_days": 252,
                "min_observations": 100
            },
            "var_limits": {
                "daily_95": 0.05,
                "daily_99": 0.08,
                "weekly_95": 0.12,
                "monthly_95": 0.20
            },
            "stress_testing": {
                "enabled_scenarios": ["crisis_2008", "covid_2020", "china_ban"],
                "max_acceptable_loss": 0.15,
                "recovery_model": "exponential"
            },
            "monte_carlo": {
                "simulations": 1000,  # Reduced for faster tests
                "max_horizon_days": 30,
                "distribution": "student_t",
                "correlation_model": "dynamic",
                "extreme_percentiles": [1, 5, 95, 99]
            }
        }
    
    @pytest.fixture
    def sample_portfolio(self):
        """Sample portfolio for testing"""
        return {
            "weights": {"BTC": 0.4, "ETH": 0.3, "SOL": 0.2, "AVAX": 0.1},
            "value": 100000.0
        }
    
    @pytest.fixture
    def mock_data_fetcher(self):
        """Mock data fetcher with sample price data"""
        # Create sample price data (252 days, 4 assets)
        np.random.seed(42)  # For reproducible tests
        dates = pd.date_range(end=datetime.now(), periods=252, freq='D')
        
        # Simulate crypto-like returns with higher volatility
        btc_returns = np.random.normal(0.001, 0.04, 252)  # 4% daily vol
        eth_returns = np.random.normal(0.0008, 0.05, 252)  # 5% daily vol, correlated
        sol_returns = np.random.normal(0.002, 0.07, 252)  # 7% daily vol
        avax_returns = np.random.normal(0.001, 0.06, 252)  # 6% daily vol
        
        # Add some correlation
        eth_returns = 0.7 * btc_returns + 0.3 * eth_returns
        
        price_data = pd.DataFrame({
            'BTC': 50000 * np.exp(np.cumsum(btc_returns)),
            'ETH': 3000 * np.exp(np.cumsum(eth_returns)),
            'SOL': 100 * np.exp(np.cumsum(sol_returns)),
            'AVAX': 50 * np.exp(np.cumsum(avax_returns))
        }, index=dates)
        
        return price_data
    
    @pytest.fixture
    def risk_engine(self, config, mock_data_fetcher):
        """Create risk engine with mocked data"""
        with patch('services.risk.advanced_risk_engine.get_historical_prices', 
                  return_value=mock_data_fetcher):
            engine = create_advanced_risk_engine(config)
            return engine
    
    @pytest.mark.asyncio
    async def test_parametric_var_calculation(self, risk_engine, sample_portfolio):
        """Test parametric VaR calculation"""
        result = await risk_engine.calculate_var(
            portfolio_weights=sample_portfolio["weights"],
            portfolio_value=sample_portfolio["value"],
            method=VaRMethod.PARAMETRIC,
            confidence_level=0.95,
            horizon=RiskHorizon.DAILY
        )
        
        assert isinstance(result, VaRResult)
        assert result.method == VaRMethod.PARAMETRIC
        assert result.confidence_level == 0.95
        assert result.horizon == RiskHorizon.DAILY
        assert result.portfolio_value == sample_portfolio["value"]
        assert result.var_value > 0  # Should be positive (loss amount)
        assert result.expected_shortfall >= result.var_value  # CVaR >= VaR
        assert isinstance(result.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_historical_var_calculation(self, risk_engine, sample_portfolio):
        """Test historical VaR calculation"""
        result = await risk_engine.calculate_var(
            portfolio_weights=sample_portfolio["weights"],
            portfolio_value=sample_portfolio["value"],
            method=VaRMethod.HISTORICAL,
            confidence_level=0.99,
            horizon=RiskHorizon.WEEKLY
        )
        
        assert isinstance(result, VaRResult)
        assert result.method == VaRMethod.HISTORICAL
        assert result.confidence_level == 0.99
        assert result.horizon == RiskHorizon.WEEKLY
        assert result.var_value > 0
        assert result.expected_shortfall >= result.var_value
    
    @pytest.mark.asyncio
    async def test_stress_test_2008_crisis(self, risk_engine, sample_portfolio):
        """Test stress testing with 2008 crisis scenario"""
        result = await risk_engine.run_stress_test(
            portfolio_weights=sample_portfolio["weights"],
            portfolio_value=sample_portfolio["value"],
            scenario=StressScenario.CRISIS_2008
        )
        
        assert isinstance(result, StressTestResult)
        assert result.scenario == StressScenario.CRISIS_2008
        assert result.portfolio_loss > 0  # Should show losses
        assert result.portfolio_loss_pct < 0  # Negative percentage (loss)
        assert len(result.asset_impacts) == 4  # All assets should be impacted
        assert len(result.shock_applied) == 4  # Shocks should be applied to all
        assert isinstance(result.timestamp, datetime)
        
        # Check that BTC and ETH have appropriate crisis-level shocks
        assert "BTC" in result.shock_applied
        assert "ETH" in result.shock_applied
        assert result.shock_applied["BTC"] < -0.1  # At least 10% shock
    
    @pytest.mark.asyncio
    async def test_stress_test_covid_crash(self, risk_engine, sample_portfolio):
        """Test COVID crash scenario"""
        result = await risk_engine.run_stress_test(
            portfolio_weights=sample_portfolio["weights"],
            portfolio_value=sample_portfolio["value"],
            scenario=StressScenario.COVID_2020
        )
        
        assert isinstance(result, StressTestResult)
        assert result.scenario == StressScenario.COVID_2020
        assert result.portfolio_loss > 0
        assert result.recovery_estimate_days is None or result.recovery_estimate_days > 0
    
    @pytest.mark.asyncio
    async def test_monte_carlo_simulation(self, risk_engine, sample_portfolio):
        """Test Monte Carlo simulation"""
        result = await risk_engine.run_monte_carlo_simulation(
            portfolio_weights=sample_portfolio["weights"],
            portfolio_value=sample_portfolio["value"],
            num_simulations=500,  # Reduced for faster tests
            horizon_days=30,
            distribution="student_t"
        )
        
        assert isinstance(result, MonteCarloResult)
        assert result.simulations == 500
        assert len(result.var_estimates) >= 2  # Should have multiple confidence levels
        assert "95%" in result.var_estimates or "99%" in result.var_estimates
        assert isinstance(result.expected_return, float)
        assert isinstance(result.volatility, float)
        assert result.volatility > 0
        assert isinstance(result.skewness, float)
        assert isinstance(result.kurtosis, float)
        assert len(result.extreme_scenarios) >= 2  # Multiple percentiles
        assert isinstance(result.tail_expectation, float)
    
    @pytest.mark.asyncio
    async def test_risk_attribution(self, risk_engine, sample_portfolio):
        """Test risk attribution calculation"""
        result = await risk_engine.get_risk_attribution(
            portfolio_weights=sample_portfolio["weights"],
            portfolio_value=sample_portfolio["value"],
            confidence_level=0.95
        )
        
        assert isinstance(result, RiskAttributionResult)
        assert len(result.marginal_var) == 4  # All assets
        assert len(result.component_var) == 4
        assert len(result.risk_contribution_pct) == 4
        assert isinstance(result.concentration_risk, float)
        assert 0 <= result.concentration_risk <= 1  # Should be normalized
        assert isinstance(result.diversification_ratio, float)
        assert result.diversification_ratio > 0
        
        # Risk contributions should sum to approximately 100%
        total_contribution = sum(result.risk_contribution_pct.values())
        assert abs(total_contribution - 100.0) < 1.0  # Within 1% tolerance
    
    @pytest.mark.asyncio
    async def test_var_method_enum_validation(self, risk_engine, sample_portfolio):
        """Test that invalid VaR methods raise appropriate errors"""
        with pytest.raises(ValueError):
            await risk_engine.calculate_var(
                portfolio_weights=sample_portfolio["weights"],
                portfolio_value=sample_portfolio["value"],
                method="invalid_method",  # Should fail
                confidence_level=0.95,
                horizon=RiskHorizon.DAILY
            )
    
    @pytest.mark.asyncio
    async def test_confidence_level_validation(self, risk_engine, sample_portfolio):
        """Test confidence level validation"""
        # Test invalid confidence levels
        with pytest.raises(ValueError):
            await risk_engine.calculate_var(
                portfolio_weights=sample_portfolio["weights"],
                portfolio_value=sample_portfolio["value"],
                method=VaRMethod.PARAMETRIC,
                confidence_level=1.1,  # > 1.0
                horizon=RiskHorizon.DAILY
            )
        
        with pytest.raises(ValueError):
            await risk_engine.calculate_var(
                portfolio_weights=sample_portfolio["weights"],
                portfolio_value=sample_portfolio["value"],
                method=VaRMethod.PARAMETRIC,
                confidence_level=0.5,  # Too low
                horizon=RiskHorizon.DAILY
            )
    
    @pytest.mark.asyncio
    async def test_portfolio_weights_validation(self, risk_engine):
        """Test portfolio weights validation"""
        # Test weights that don't sum to 1.0
        invalid_weights = {"BTC": 0.6, "ETH": 0.6}  # Sums to 1.2
        
        with pytest.raises(ValueError):
            await risk_engine.calculate_var(
                portfolio_weights=invalid_weights,
                portfolio_value=100000.0,
                method=VaRMethod.PARAMETRIC,
                confidence_level=0.95,
                horizon=RiskHorizon.DAILY
            )
    
    def test_create_advanced_risk_engine(self, config):
        """Test risk engine factory function"""
        engine = create_advanced_risk_engine(config)
        assert isinstance(engine, AdvancedRiskEngine)
        assert engine.config == config
    
    def test_create_risk_engine_disabled(self):
        """Test creating risk engine when disabled"""
        disabled_config = {"enabled": False}
        engine = create_advanced_risk_engine(disabled_config)
        assert engine is None
    
    @pytest.mark.asyncio
    async def test_horizon_scaling(self, risk_engine, sample_portfolio):
        """Test that different horizons produce appropriately scaled results"""
        # Calculate VaR for different horizons
        daily_result = await risk_engine.calculate_var(
            portfolio_weights=sample_portfolio["weights"],
            portfolio_value=sample_portfolio["value"],
            method=VaRMethod.PARAMETRIC,
            confidence_level=0.95,
            horizon=RiskHorizon.DAILY
        )
        
        weekly_result = await risk_engine.calculate_var(
            portfolio_weights=sample_portfolio["weights"],
            portfolio_value=sample_portfolio["value"],
            method=VaRMethod.PARAMETRIC,
            confidence_level=0.95,
            horizon=RiskHorizon.WEEKLY
        )
        
        # Weekly VaR should be higher than daily (roughly sqrt(7) scaling)
        assert weekly_result.var_value > daily_result.var_value
        # Rough check for square root of time scaling
        scaling_ratio = weekly_result.var_value / daily_result.var_value
        assert 2.0 < scaling_ratio < 3.5  # Should be around sqrt(7) ≈ 2.65


class TestStressScenarios:
    """Test predefined stress scenarios"""
    
    def test_crisis_2008_scenario_exists(self):
        """Test that 2008 crisis scenario is properly defined"""
        assert StressScenario.CRISIS_2008 in StressScenario
        
    def test_covid_2020_scenario_exists(self):
        """Test that COVID 2020 scenario is properly defined"""
        assert StressScenario.COVID_2020 in StressScenario
        
    def test_china_ban_scenario_exists(self):
        """Test that China ban scenario is properly defined"""
        assert StressScenario.CHINA_BAN in StressScenario


# Integration test with alert system
class TestRiskEngineIntegration:
    """Integration tests with alert system"""
    
    @pytest.mark.asyncio
    async def test_integration_with_alert_engine(self, config):
        """Test that risk engine integrates properly with alert system"""
        from services.alerts.alert_engine import AlertEngine
        
        # Mock alert config with advanced risk enabled
        alert_config = {
            "alerting_config": {
                "enabled": True,
                "advanced_risk": config
            },
            "alert_types": {
                "VAR_BREACH": {"enabled": True, "thresholds": {"S2": 0.05, "S3": 0.08}},
                "STRESS_TEST_FAILED": {"enabled": True, "thresholds": {"S2": 0.10, "S3": 0.15}}
            }
        }
        
        # Create alert engine (should initialize risk engine)
        alert_engine = AlertEngine(alert_config)
        
        # Verify risk engine was created and enabled
        assert hasattr(alert_engine, 'risk_engine_enabled')
        assert alert_engine.risk_engine_enabled == True
        assert hasattr(alert_engine, 'risk_engine')
        assert alert_engine.risk_engine is not None