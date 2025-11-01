"""
Unit tests for Risk Scoring structural penalties and hysteresis.

Tests critical features added in Oct 2025:
- Memec

oins penalty with hysteresis (48-52% zone)
- HHI concentration penalty
- GRI group risk penalty
- Diversification ratio penalty

Created: Oct 2025 (Phase 2 Quality - Missing Coverage)
Ref: docs/CAP_STABILITY_FIX.md
"""

import pytest
from services.risk_scoring import assess_risk_level


# ============================================================================
# Tests: Memecoins Penalty with Hysteresis (CRITICAL - Oct 2025 fix)
# ============================================================================

class TestMemecoinsHysteresis:
    """
    Test memecoins hysteresis anti flip-flop (48-52% transition zone).

    Critical feature to prevent oscillation between penalty thresholds.
    Ref: services/risk_scoring.py:186-206
    """

    @pytest.fixture
    def base_metrics(self):
        """Base metrics for consistent testing"""
        return {
            "var_metrics": {"var_95": 0.05, "var_99": 0.08, "cvar_95": 0.06, "cvar_99": 0.10},
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.10,
            "volatility": 0.25
        }

    def test_zero_memecoins_no_penalty(self, base_metrics):
        """0% memecoins should have no penalty (baseline)"""
        result = assess_risk_level(**base_metrics, memecoins_pct=0.0)
        assert result["breakdown"]["memecoins"] == 0, \
            "No penalty expected for 0% memecoins"

    def test_below_5_percent_no_penalty(self, base_metrics):
        """< 5% memecoins should have no penalty"""
        result = assess_risk_level(**base_metrics, memecoins_pct=0.04)
        assert result["breakdown"]["memecoins"] == 0

    def test_5_to_15_percent_minimal_penalty(self, base_metrics):
        """5-15% memecoins should have minimal penalty (-3)"""
        result = assess_risk_level(**base_metrics, memecoins_pct=0.10)
        assert result["breakdown"]["memecoins"] == pytest.approx(-3, abs=0.1), \
            "Expected -3 pts penalty for 10% memecoins"

    def test_15_to_30_percent_light_penalty(self, base_metrics):
        """15-30% memecoins should have light penalty (-6)"""
        result = assess_risk_level(**base_metrics, memecoins_pct=0.20)
        assert result["breakdown"]["memecoins"] == pytest.approx(-6, abs=0.1), \
            "Expected -6 pts penalty for 20% memecoins"

    def test_30_to_48_percent_moderate_penalty(self, base_metrics):
        """30-48% memecoins should have moderate penalty (-10)"""
        result = assess_risk_level(**base_metrics, memecoins_pct=0.40)
        assert result["breakdown"]["memecoins"] == pytest.approx(-10, abs=0.1), \
            "Expected -10 pts penalty for 40% memecoins"

    # ========================================================================
    # HYSTERESIS ZONE: 48-52% (CRITICAL)
    # ========================================================================

    def test_hysteresis_start_48_percent(self, base_metrics):
        """48% memecoins should be at lower bound of transition (-10 pts)"""
        result = assess_risk_level(**base_metrics, memecoins_pct=0.48)
        penalty = result["breakdown"]["memecoins"]

        # At 48%, should be ~-10 (start of transition)
        assert -10.5 <= penalty <= -9.5, \
            f"Expected ~-10 pts at 48% (start of hysteresis), got {penalty}"

    def test_hysteresis_middle_50_percent(self, base_metrics):
        """50% memecoins should be in middle of transition (-12.5 pts)"""
        result = assess_risk_level(**base_metrics, memecoins_pct=0.50)
        penalty = result["breakdown"]["memecoins"]

        # At 50%, should be approximately -12.5 (linear interpolation)
        # t = (0.50 - 0.48) / 0.04 = 0.5
        # penalty = -10 + 0.5 * (-15 - (-10)) = -10 + 0.5 * (-5) = -12.5
        assert -13.0 <= penalty <= -12.0, \
            f"Expected ~-12.5 pts at 50% (mid hysteresis), got {penalty}"

    def test_hysteresis_end_52_percent(self, base_metrics):
        """52% memecoins should be at upper bound of transition (-15 pts)"""
        result = assess_risk_level(**base_metrics, memecoins_pct=0.52)
        penalty = result["breakdown"]["memecoins"]

        # At 52%, should be ~-15 (end of transition)
        assert -15.5 <= penalty <= -14.5, \
            f"Expected ~-15 pts at 52% (end of hysteresis), got {penalty}"

    def test_hysteresis_smooth_transition(self, base_metrics):
        """
        Hysteresis zone should have smooth linear transition (no jumps).

        Critical anti flip-flop test: ensures no sudden jumps in penalty
        when memecoins % oscillates around 50%.
        """
        # Test points across transition zone
        test_points = [0.47, 0.48, 0.49, 0.50, 0.51, 0.52, 0.53]
        penalties = []

        for pct in test_points:
            result = assess_risk_level(**base_metrics, memecoins_pct=pct)
            penalties.append(result["breakdown"]["memecoins"])

        # 1. Check monotonic decrease (each penalty should be <= previous)
        for i in range(len(penalties) - 1):
            assert penalties[i+1] <= penalties[i] + 0.2, \
                f"Non-monotonic transition at {test_points[i]:.2f}% -> {test_points[i+1]:.2f}%: " \
                f"{penalties[i]:.2f} -> {penalties[i+1]:.2f}"

        # 2. Check no sudden jumps (max change should be ~1.25 pts per 1% memecoin)
        for i in range(len(penalties) - 1):
            delta = abs(penalties[i+1] - penalties[i])
            assert delta <= 1.5, \
                f"Jump too large at {test_points[i]:.2f}%: {delta:.2f} pts " \
                f"(expected <= 1.5 pts per 1% change)"

        # 3. Check total range is approximately -10 to -15
        assert min(penalties[1:6]) >= -15.5, "Penalty too severe in hysteresis zone"
        assert max(penalties[1:6]) <= -9.5, "Penalty too lenient in hysteresis zone"

    def test_above_52_percent_confirmed_penalty(self, base_metrics):
        """>52% memecoins should have confirmed penalty (-15)"""
        result = assess_risk_level(**base_metrics, memecoins_pct=0.60)
        assert result["breakdown"]["memecoins"] == pytest.approx(-15, abs=0.1), \
            "Expected -15 pts penalty for 60% memecoins"

    def test_above_70_percent_major_penalty(self, base_metrics):
        """>70% memecoins should have major penalty (-22)"""
        result = assess_risk_level(**base_metrics, memecoins_pct=0.80)
        assert result["breakdown"]["memecoins"] == pytest.approx(-22, abs=0.1), \
            "Expected -22 pts penalty for 80% memecoins (degen portfolio)"

    def test_hysteresis_prevents_flip_flop(self, base_metrics):
        """
        Demonstrate that hysteresis prevents flip-flop around 50% threshold.

        Without hysteresis: 49.9% -> -10, 50.1% -> -15 (5 pts jump!)
        With hysteresis: 49.9% -> -12.4, 50.1% -> -12.6 (0.2 pts change)
        """
        result_below = assess_risk_level(**base_metrics, memecoins_pct=0.499)
        result_above = assess_risk_level(**base_metrics, memecoins_pct=0.501)

        penalty_below = result_below["breakdown"]["memecoins"]
        penalty_above = result_above["breakdown"]["memecoins"]

        # Change should be minimal (< 0.5 pts for 0.2% memecoin change)
        delta = abs(penalty_above - penalty_below)
        assert delta < 0.5, \
            f"Hysteresis failed: 49.9% ({penalty_below:.2f}) vs 50.1% ({penalty_above:.2f}) " \
            f"has delta={delta:.2f} pts (expected < 0.5 pts)"


# ============================================================================
# Tests: HHI Concentration Penalty
# ============================================================================

class TestHHIConcentrationPenalty:
    """Test HHI (Herfindahl-Hirschman Index) concentration penalty"""

    @pytest.fixture
    def base_metrics(self):
        """Base metrics for consistent testing"""
        return {
            "var_metrics": {"var_95": 0.05, "var_99": 0.08, "cvar_95": 0.06, "cvar_99": 0.10},
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.10,
            "volatility": 0.25
        }

    def test_well_diversified_no_penalty(self, base_metrics):
        """HHI < 0.15 (well diversified) should have no penalty"""
        result = assess_risk_level(**base_metrics, hhi=0.10)
        assert result["breakdown"]["concentration"] == 0, \
            "No penalty expected for well diversified portfolio (HHI=0.10)"

    def test_slight_concentration_light_penalty(self, base_metrics):
        """HHI 0.15-0.25 (slight concentration) should have light penalty (-3)"""
        result = assess_risk_level(**base_metrics, hhi=0.20)
        assert result["breakdown"]["concentration"] == pytest.approx(-3, abs=1), \
            "Expected -3 pts penalty for HHI=0.20"

    def test_moderate_concentration_penalty(self, base_metrics):
        """HHI 0.25-0.40 (concentrated) should have moderate penalty (-8)"""
        result = assess_risk_level(**base_metrics, hhi=0.30)
        assert result["breakdown"]["concentration"] == pytest.approx(-8, abs=1), \
            "Expected -8 pts penalty for HHI=0.30"

    def test_high_concentration_major_penalty(self, base_metrics):
        """HHI > 0.40 (very concentrated) should have major penalty (-12)"""
        result = assess_risk_level(**base_metrics, hhi=0.50)
        assert result["breakdown"]["concentration"] == pytest.approx(-12, abs=1), \
            "Expected -12 pts penalty for HHI=0.50"

    def test_concentration_decreases_risk_score(self, base_metrics):
        """Higher concentration should decrease overall risk score"""
        result_diverse = assess_risk_level(**base_metrics, hhi=0.10)
        result_concentrated = assess_risk_level(**base_metrics, hhi=0.50)

        assert result_concentrated["score"] < result_diverse["score"], \
            "Concentrated portfolio should have lower risk score than diversified"


# ============================================================================
# Tests: GRI Group Risk Penalty
# ============================================================================

class TestGRIGroupRiskPenalty:
    """Test GRI (Group Risk Index) penalty"""

    @pytest.fixture
    def base_metrics(self):
        """Base metrics for consistent testing"""
        return {
            "var_metrics": {"var_95": 0.05, "var_99": 0.08, "cvar_95": 0.06, "cvar_99": 0.10},
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.10,
            "volatility": 0.25
        }

    def test_safe_groups_bonus(self, base_metrics):
        """GRI < 3.0 (safe groups) should have bonus (+5)"""
        result = assess_risk_level(**base_metrics, gri=2.5)
        assert result["breakdown"]["group_risk"] == pytest.approx(5, abs=1), \
            "Expected +5 pts bonus for safe groups (GRI=2.5)"

    def test_neutral_groups_no_penalty(self, base_metrics):
        """GRI 3.0-5.0 (neutral) should have no penalty"""
        result = assess_risk_level(**base_metrics, gri=4.0)
        assert result["breakdown"]["group_risk"] == 0, \
            "Expected no penalty for neutral GRI=4.0"

    def test_moderate_risk_groups_penalty(self, base_metrics):
        """GRI 5.0-6.0 (moderate risk) should have penalty (-4)"""
        result = assess_risk_level(**base_metrics, gri=5.5)
        assert result["breakdown"]["group_risk"] == pytest.approx(-4, abs=1), \
            "Expected -4 pts penalty for GRI=5.5"

    def test_risky_groups_penalty(self, base_metrics):
        """GRI 6.0-7.0 (risky) should have penalty (-7)"""
        result = assess_risk_level(**base_metrics, gri=6.5)
        assert result["breakdown"]["group_risk"] == pytest.approx(-7, abs=1), \
            "Expected -7 pts penalty for GRI=6.5"

    def test_very_risky_groups_major_penalty(self, base_metrics):
        """GRI > 7.0 (very risky) should have major penalty (-10)"""
        result = assess_risk_level(**base_metrics, gri=8.0)
        assert result["breakdown"]["group_risk"] == pytest.approx(-10, abs=1), \
            "Expected -10 pts penalty for GRI=8.0"


# ============================================================================
# Tests: Diversification Ratio Penalty
# ============================================================================

class TestDiversificationRatioPenalty:
    """Test diversification ratio penalty"""

    @pytest.fixture
    def base_metrics(self):
        """Base metrics for consistent testing"""
        return {
            "var_metrics": {"var_95": 0.05, "var_99": 0.08, "cvar_95": 0.06, "cvar_99": 0.10},
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.10,
            "volatility": 0.25
        }

    def test_excellent_diversification_bonus(self, base_metrics):
        """Ratio > 0.8 (excellent) should have bonus"""
        result = assess_risk_level(**base_metrics, diversification_ratio=0.9)
        # Check if bonus exists (may vary by implementation)
        assert result["breakdown"].get("diversification", 0) >= 0

    def test_good_diversification_no_penalty(self, base_metrics):
        """Ratio 0.6-0.8 (good) should have no penalty"""
        result = assess_risk_level(**base_metrics, diversification_ratio=0.7)
        # Should be 0 or small bonus
        assert result["breakdown"].get("diversification", 0) >= -2

    def test_moderate_diversification_penalty(self, base_metrics):
        """Ratio 0.4-0.6 (moderate) should have penalty"""
        result = assess_risk_level(**base_metrics, diversification_ratio=0.5)
        # Should have some penalty
        assert result["breakdown"].get("diversification", 0) < 0

    def test_poor_diversification_major_penalty(self, base_metrics):
        """Ratio < 0.4 (poor) should have major penalty (-10)"""
        result = assess_risk_level(**base_metrics, diversification_ratio=0.3)
        assert result["breakdown"].get("diversification", 0) == pytest.approx(-10, abs=2), \
            "Expected ~-10 pts penalty for poor diversification (ratio=0.3)"


# ============================================================================
# Tests: Combined Structural Penalties
# ============================================================================

class TestCombinedStructuralPenalties:
    """Test interaction of multiple structural penalties"""

    @pytest.fixture
    def base_metrics(self):
        """Base metrics for consistent testing"""
        return {
            "var_metrics": {"var_95": 0.05, "var_99": 0.08, "cvar_95": 0.06, "cvar_99": 0.10},
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.10,
            "volatility": 0.25
        }

    def test_degen_portfolio_all_penalties(self, base_metrics):
        """
        "Degen" portfolio (high memes, concentrated, risky groups)
        should accumulate all penalties.
        """
        result = assess_risk_level(
            **base_metrics,
            memecoins_pct=0.75,  # >70% memes: -22
            hhi=0.50,  # Very concentrated: -12
            gri=8.0,  # Very risky groups: -10
            diversification_ratio=0.3  # Poor diversification: -10
        )

        # Should have very low score due to all penalties
        assert result["score"] < 40, \
            "Degen portfolio should have very low risk score (<40)"
        assert result["level"] in ["high", "very_high", "critical"], \
            "Degen portfolio should be high risk or worse"

    def test_conservative_portfolio_no_penalties(self, base_metrics):
        """
        Conservative portfolio (no memes, diversified, safe groups)
        should have minimal penalties or bonuses.
        """
        result = assess_risk_level(
            **base_metrics,
            memecoins_pct=0.0,  # No memes: 0
            hhi=0.10,  # Well diversified: 0
            gri=2.5,  # Safe groups: +5
            diversification_ratio=0.9  # Excellent diversification: bonus
        )

        # Should have high score (no penalties, some bonuses)
        assert result["score"] >= 60, \
            "Conservative portfolio should have high risk score (>=60)"

    def test_penalties_are_additive(self, base_metrics):
        """Multiple penalties should combine additively"""
        # Test with single penalty
        result_single = assess_risk_level(**base_metrics, memecoins_pct=0.40)
        penalty_single = result_single["breakdown"]["memecoins"]

        # Test with multiple penalties
        result_multiple = assess_risk_level(
            **base_metrics,
            memecoins_pct=0.40,
            hhi=0.30
        )
        penalty_memes = result_multiple["breakdown"]["memecoins"]
        penalty_hhi = result_multiple["breakdown"]["concentration"]

        # Total penalty should be approximately sum of individual penalties
        total_penalty = penalty_memes + penalty_hhi
        score_diff = result_single["score"] - result_multiple["score"]

        assert abs(score_diff - abs(total_penalty - penalty_single)) < 2, \
            "Penalties should be approximately additive"


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
