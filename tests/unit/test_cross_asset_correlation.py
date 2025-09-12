"""
Unit tests for Phase 2B2 Cross-Asset Correlation system

Tests the core correlation engine, spike detection, clustering,
and systemic risk scoring functionality.
"""

import pytest
import numpy as np
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from services.alerts.cross_asset_correlation import (
    CrossAssetCorrelationAnalyzer,
    CorrelationSpike,
    ConcentrationCluster,
    CrossAssetStatus
)


class TestCrossAssetCorrelationAnalyzer:
    """Test suite for CrossAssetCorrelationAnalyzer"""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer with test configuration"""
        config = {
            "enabled": True,
            "calculation_windows": {
                "1h": 6,
                "4h": 24,
                "1d": 168
            },
            "correlation_thresholds": {
                "low_risk": 0.6,
                "medium_risk": 0.75,
                "high_risk": 0.85,
                "systemic_risk": 0.95
            },
            "spike_thresholds": {
                "relative_min": 0.15,
                "absolute_min": 0.20
            },
            "concentration_mode": "clustering"
        }
        return CrossAssetCorrelationAnalyzer(config)
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample price data for testing"""
        np.random.seed(42)
        assets = ["BTC", "ETH", "SOL", "AVAX", "DOGE"]
        
        # Generate correlated returns
        n_points = 100
        base_returns = np.random.normal(0, 0.02, n_points)
        data = {}
        
        for i, asset in enumerate(assets):
            # Add asset-specific noise and correlation
            correlation_factor = 0.7 if i < 2 else 0.5  # BTC/ETH more correlated
            noise = np.random.normal(0, 0.01, n_points)
            returns = correlation_factor * base_returns + noise
            
            # Convert to prices (cumulative)
            prices = 100 * np.cumprod(1 + returns)
            timestamps = [datetime.now(timezone.utc)] * n_points
            
            data[asset] = {
                "prices": prices.tolist(),
                "timestamps": timestamps
            }
        
        return data
    
    def test_calculate_correlation_matrix(self, analyzer, sample_data):
        """Test correlation matrix calculation"""
        # Mock the signal data fetching
        with patch.object(analyzer, '_fetch_asset_data', return_value=sample_data):
            matrix, assets = analyzer.calculate_correlation_matrix("1h")
            
            assert isinstance(matrix, np.ndarray)
            assert matrix.shape == (len(sample_data), len(sample_data))
            assert len(assets) == len(sample_data)
            
            # Check matrix properties
            np.testing.assert_array_almost_equal(np.diag(matrix), 1.0)  # Diagonal = 1
            assert np.allclose(matrix, matrix.T)  # Symmetric
            assert np.all(matrix >= -1) and np.all(matrix <= 1)  # Valid range
    
    def test_detect_correlation_spikes_double_criteria(self, analyzer):
        """Test spike detection with double criteria (relative + absolute)"""
        # Create test data with known spikes
        current_corr = 0.85
        historical_corr = [0.60, 0.58, 0.62, 0.61, 0.59]  # avg ~0.60
        
        # Mock correlation data
        mock_data = {
            "BTC": {"prices": [100] * 10, "timestamps": [datetime.now(timezone.utc)] * 10},
            "ETH": {"prices": [50] * 10, "timestamps": [datetime.now(timezone.utc)] * 10}
        }
        
        with patch.object(analyzer, '_fetch_asset_data', return_value=mock_data):
            with patch.object(analyzer, 'calculate_correlation_matrix') as mock_calc:
                # Setup current vs historical correlation
                current_matrix = np.array([[1.0, current_corr], [current_corr, 1.0]])
                mock_calc.return_value = (current_matrix, ["BTC", "ETH"])
                
                # Mock historical data
                with patch.object(analyzer, '_get_historical_correlations') as mock_hist:
                    mock_hist.return_value = {("BTC", "ETH"): historical_corr}
                    
                    spikes = analyzer.detect_correlation_spikes("1h", ["BTC", "ETH"])
                    
                    # Should detect spike: 0.85 vs 0.60 = 41% relative (>15%) and 0.25 absolute (>0.20)
                    assert len(spikes) == 1
                    spike = spikes[0]
                    assert spike.asset_pair == ("BTC", "ETH")
                    assert spike.current_correlation == current_corr
                    assert abs(spike.relative_change - 0.417) < 0.01  # ~41.7%
                    assert abs(spike.absolute_change - 0.25) < 0.01
    
    def test_detect_correlation_spikes_no_spike(self, analyzer):
        """Test that small changes don't trigger spikes"""
        # Small change that doesn't meet double criteria
        current_corr = 0.68
        historical_corr = [0.65, 0.64, 0.66, 0.63, 0.67]  # avg ~0.65
        
        mock_data = {
            "BTC": {"prices": [100] * 10, "timestamps": [datetime.now(timezone.utc)] * 10},
            "ETH": {"prices": [50] * 10, "timestamps": [datetime.now(timezone.utc)] * 10}
        }
        
        with patch.object(analyzer, '_fetch_asset_data', return_value=mock_data):
            with patch.object(analyzer, 'calculate_correlation_matrix') as mock_calc:
                current_matrix = np.array([[1.0, current_corr], [current_corr, 1.0]])
                mock_calc.return_value = (current_matrix, ["BTC", "ETH"])
                
                with patch.object(analyzer, '_get_historical_correlations') as mock_hist:
                    mock_hist.return_value = {("BTC", "ETH"): historical_corr}
                    
                    spikes = analyzer.detect_correlation_spikes("1h", ["BTC", "ETH"])
                    
                    # Should not detect spike: only 4.6% relative and 0.03 absolute
                    assert len(spikes) == 0
    
    def test_detect_concentration_clusters(self, analyzer, sample_data):
        """Test cluster-based concentration detection"""
        with patch.object(analyzer, '_fetch_asset_data', return_value=sample_data):
            clusters = analyzer.detect_concentration_clusters("1h")
            
            assert isinstance(clusters, list)
            for cluster in clusters:
                assert isinstance(cluster, CorrelationCluster)
                assert len(cluster.assets) > 0
                assert 0 <= cluster.concentration_score <= 1
                assert cluster.risk_level in ["low", "medium", "high", "systemic"]
    
    def test_calculate_systemic_risk_score(self, analyzer):
        """Test systemic risk score calculation"""
        # Mock components
        mock_matrix = np.array([
            [1.0, 0.85, 0.75],
            [0.85, 1.0, 0.70],
            [0.75, 0.70, 1.0]
        ])
        
        mock_clusters = [
            CorrelationCluster(
                assets=["BTC", "ETH"],
                avg_correlation=0.85,
                concentration_score=0.8,
                risk_level="high"
            )
        ]
        
        mock_spikes = [
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
        
        risk_score = analyzer.calculate_systemic_risk_score(
            mock_matrix, ["BTC", "ETH", "SOL"], mock_clusters, mock_spikes
        )
        
        assert isinstance(risk_score, SystemicRiskScore)
        assert 0 <= risk_score.score <= 1
        assert risk_score.level in ["low", "medium", "high", "systemic"]
        assert "avg_correlation" in risk_score.factors
        assert "cluster_concentration" in risk_score.factors
        assert "recent_spike_count" in risk_score.factors
    
    def test_performance_requirements(self, analyzer, sample_data):
        """Test performance requirements (<50ms for 10x10 matrix)"""
        import time
        
        # Create 10x10 asset data
        large_data = {}
        for i in range(10):
            asset = f"ASSET_{i:02d}"
            large_data[asset] = sample_data["BTC"]  # Reuse sample data
        
        with patch.object(analyzer, '_fetch_asset_data', return_value=large_data):
            start_time = time.time()
            matrix, assets = analyzer.calculate_correlation_matrix("1h")
            elapsed_ms = (time.time() - start_time) * 1000
            
            assert elapsed_ms < 50, f"Performance requirement failed: {elapsed_ms:.1f}ms > 50ms"
            assert matrix.shape == (10, 10)
            assert len(assets) == 10
    
    def test_configuration_validation(self):
        """Test configuration validation and defaults"""
        # Test with minimal config
        minimal_config = {"enabled": True}
        analyzer = CrossAssetCorrelationAnalyzer(minimal_config)
        
        assert analyzer.enabled
        assert "1h" in analyzer.calculation_windows
        assert "relative_min" in analyzer.spike_thresholds
        
        # Test with invalid config
        with pytest.raises(ValueError):
            CrossAssetCorrelationAnalyzer({"enabled": "invalid"})
    
    def test_edge_cases(self, analyzer):
        """Test edge cases and error handling"""
        # Empty asset list
        with patch.object(analyzer, '_fetch_asset_data', return_value={}):
            matrix, assets = analyzer.calculate_correlation_matrix("1h")
            assert matrix.shape == (0, 0)
            assert len(assets) == 0
        
        # Single asset
        single_asset_data = {
            "BTC": {"prices": [100] * 10, "timestamps": [datetime.now(timezone.utc)] * 10}
        }
        
        with patch.object(analyzer, '_fetch_asset_data', return_value=single_asset_data):
            matrix, assets = analyzer.calculate_correlation_matrix("1h")
            assert matrix.shape == (1, 1)
            assert matrix[0, 0] == 1.0
            
            # No spikes possible with single asset
            spikes = analyzer.detect_correlation_spikes("1h", ["BTC"])
            assert len(spikes) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])