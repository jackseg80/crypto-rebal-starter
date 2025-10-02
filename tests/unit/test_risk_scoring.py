"""
Unit tests for centralized risk scoring logic (services/risk_scoring.py)

These tests ensure:
1. Score-to-level mapping is consistent and never regresses
2. Risk score calculation follows Option A semantics (robustness)
3. Breakdown provides audit trail for all contributions
"""

import pytest
from services.risk_scoring import (
    assess_risk_level,
    score_to_level,
    RISK_LEVEL_THRESHOLDS
)


class TestScoreToLevelMapping:
    """Test canonical score-to-level mapping (non-regression)"""

    def test_very_low_threshold(self):
        """Score >= 80 → very_low"""
        assert score_to_level(85) == "very_low"
        assert score_to_level(80) == "very_low"
        assert score_to_level(100) == "very_low"

    def test_low_threshold(self):
        """Score >= 65 → low"""
        assert score_to_level(70) == "low"
        assert score_to_level(65) == "low"
        assert score_to_level(79) == "low"

    def test_medium_threshold(self):
        """Score >= 50 → medium"""
        assert score_to_level(55) == "medium"
        assert score_to_level(50) == "medium"
        assert score_to_level(64) == "medium"

    def test_high_threshold(self):
        """Score >= 35 → high"""
        assert score_to_level(40) == "high"
        assert score_to_level(35) == "high"
        assert score_to_level(49) == "high"

    def test_very_high_threshold(self):
        """Score >= 20 → very_high"""
        assert score_to_level(25) == "very_high"
        assert score_to_level(20) == "very_high"
        assert score_to_level(34) == "very_high"

    def test_critical_threshold(self):
        """Score < 20 → critical"""
        assert score_to_level(10) == "critical"
        assert score_to_level(0) == "critical"
        assert score_to_level(19) == "critical"

    def test_score_clamping(self):
        """Scores outside [0, 100] are clamped"""
        assert score_to_level(150) == "very_low"  # Clamped to 100
        assert score_to_level(-50) == "critical"  # Clamped to 0


class TestAssessRiskLevel:
    """Test risk score calculation with Option A semantics"""

    def test_neutral_baseline(self):
        """Neutral metrics → score around 50"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.12, "var_99": 0.18},
            sharpe_ratio=0.8,
            max_drawdown=-0.25,
            volatility=0.45
        )
        assert 45 <= result["score"] <= 55
        assert result["level"] == "medium"
        assert "breakdown" in result

    def test_excellent_metrics_high_score(self):
        """Excellent metrics → high score (low risk)"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.03, "var_99": 0.05},  # Low VaR
            sharpe_ratio=2.5,  # Excellent Sharpe
            max_drawdown=-0.08,  # Low drawdown
            volatility=0.15  # Low volatility
        )
        assert result["score"] >= 80
        assert result["level"] in ["very_low", "low"]

    def test_poor_metrics_low_score(self):
        """Poor metrics → low score (high risk)"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.30, "var_99": 0.45},  # High VaR
            sharpe_ratio=-0.5,  # Negative Sharpe
            max_drawdown=-0.60,  # Massive drawdown
            volatility=1.2  # Very high volatility
        )
        assert result["score"] <= 30
        assert result["level"] in ["critical", "very_high", "high"]

    def test_breakdown_components(self):
        """Breakdown contains all component contributions"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.12},
            sharpe_ratio=1.0,
            max_drawdown=-0.25,
            volatility=0.50
        )
        breakdown = result["breakdown"]
        assert "var_95" in breakdown
        assert "sharpe" in breakdown
        assert "drawdown" in breakdown
        assert "volatility" in breakdown
        # Contributions should sum to (score - 50)
        total_contribution = sum(breakdown.values())
        assert abs((50 + total_contribution) - result["score"]) < 0.01

    def test_var_impact_inverted(self):
        """Higher VaR → score decreases (Option A: robustness)"""
        low_var = assess_risk_level(
            var_metrics={"var_95": 0.04},
            sharpe_ratio=1.0,
            max_drawdown=-0.20,
            volatility=0.40
        )
        high_var = assess_risk_level(
            var_metrics={"var_95": 0.30},
            sharpe_ratio=1.0,
            max_drawdown=-0.20,
            volatility=0.40
        )
        assert low_var["score"] > high_var["score"]

    def test_sharpe_impact_direct(self):
        """Higher Sharpe → score increases (Option A: robustness)"""
        low_sharpe = assess_risk_level(
            var_metrics={"var_95": 0.12},
            sharpe_ratio=-0.5,
            max_drawdown=-0.20,
            volatility=0.40
        )
        high_sharpe = assess_risk_level(
            var_metrics={"var_95": 0.12},
            sharpe_ratio=2.0,
            max_drawdown=-0.20,
            volatility=0.40
        )
        assert high_sharpe["score"] > low_sharpe["score"]


class TestThresholdsConfiguration:
    """Test threshold configuration is consistent"""

    def test_thresholds_ordered(self):
        """Thresholds are in descending order"""
        levels = ["very_low", "low", "medium", "high", "very_high", "critical"]
        thresholds = [RISK_LEVEL_THRESHOLDS[level] for level in levels if level in RISK_LEVEL_THRESHOLDS]
        assert thresholds == sorted(thresholds, reverse=True)

    def test_thresholds_cover_full_range(self):
        """Thresholds cover [0, 100] without gaps"""
        assert RISK_LEVEL_THRESHOLDS["critical"] == 0
        assert RISK_LEVEL_THRESHOLDS["very_low"] <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
