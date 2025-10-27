"""
Unit tests for TrailingStopCalculator (services/stop_loss/trailing_stop_calculator.py)

Tests the generic trailing stop calculator that protects unrealized gains
on long-term winning positions (legacy holdings).

Test Coverage:
1. Tier detection (5 tiers based on gain ranges)
2. Minimum gain threshold (20%)
3. ATH estimation from price history
4. Edge cases (invalid inputs, missing data)
5. Utility methods (is_legacy_position, tier descriptions)
"""

import pytest
import pandas as pd
import numpy as np
from services.stop_loss.trailing_stop_calculator import TrailingStopCalculator


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def trailing_calculator():
    """Standard trailing stop calculator with default settings"""
    return TrailingStopCalculator(ath_lookback_days=365)


@pytest.fixture
def mock_price_data():
    """Mock OHLC price history (30 days)"""
    return pd.DataFrame({
        'high': [100, 150, 200, 180, 170, 165, 160, 155, 150, 145,
                 140, 135, 130, 125, 120, 125, 130, 135, 140, 145,
                 150, 155, 160, 165, 170, 175, 180, 185, 190, 195],
        'close': [95, 145, 195, 175, 165, 160, 155, 150, 145, 140,
                  135, 130, 125, 120, 115, 120, 125, 130, 135, 140,
                  145, 150, 155, 160, 165, 170, 175, 180, 185, 190]
    })


@pytest.fixture
def mock_price_data_no_high():
    """Mock price history without 'high' column (fallback to 'close')"""
    return pd.DataFrame({
        'close': [95, 145, 195, 175, 165, 160, 155, 150, 145, 140,
                  135, 130, 125, 120, 115, 120, 125, 130, 135, 140,
                  145, 150, 155, 160, 165, 170, 175, 180, 185, 190]
    })


# ============================================================================
# Test Suite 1: Tier Detection
# ============================================================================

class TestTierDetection:
    """Test trailing stop tier selection based on gain ranges"""

    def test_tier_1_not_applicable(self, trailing_calculator):
        """Tier 1 (0-20%): Not applicable, use standard stop"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=110.0,
            avg_price=100.0,
            ath=110.0
        )
        assert result['applicable'] is False
        assert 'min_threshold' in result
        assert result['unrealized_gain_pct'] == pytest.approx(10.0, abs=0.01)

    def test_tier_2_20_to_50_percent(self, trailing_calculator):
        """Tier 2 (20-50%): -15% from ATH"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=135.0,
            avg_price=100.0,
            ath=140.0
        )
        assert result['applicable'] is True
        assert result['unrealized_gain_pct'] == 35.0
        assert result['tier'] == (0.20, 0.50)
        assert result['trail_pct'] == 0.15
        assert result['stop_loss'] == 119.0  # 140 × 0.85

    def test_tier_3_50_to_100_percent(self, trailing_calculator):
        """Tier 3 (50-100%): -20% from ATH"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=175.0,
            avg_price=100.0,
            ath=180.0
        )
        assert result['applicable'] is True
        assert result['unrealized_gain_pct'] == 75.0
        assert result['tier'] == (0.50, 1.00)
        assert result['trail_pct'] == 0.20
        assert result['stop_loss'] == 144.0  # 180 × 0.8

    def test_tier_4_100_to_500_percent(self, trailing_calculator):
        """Tier 4 (100-500%): -25% from ATH (like real AAPL position)"""
        # Real AAPL position: avg_price=$91.90, current=$262.82, gain=+185.99%
        result = trailing_calculator.calculate_trailing_stop(
            current_price=262.82,
            avg_price=91.90,
            ath=270.0  # Estimated ATH slightly above current
        )
        assert result['applicable'] is True
        assert result['unrealized_gain_pct'] == pytest.approx(186.0, rel=0.01)
        assert result['tier'] == (1.00, 5.00)
        assert result['trail_pct'] == 0.25
        assert result['stop_loss'] == pytest.approx(202.5, rel=0.01)  # 270 × 0.75

    def test_tier_5_above_500_percent(self, trailing_calculator):
        """Tier 5 (>500%): -30% from ATH (legacy positions)"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=700.0,
            avg_price=100.0,
            ath=750.0
        )
        assert result['applicable'] is True
        assert result['unrealized_gain_pct'] == 600.0
        assert result['tier'] == (5.00, float('inf'))
        assert result['trail_pct'] == 0.30
        assert result['stop_loss'] == 525.0  # 750 × 0.7

    @pytest.mark.parametrize("current,avg,ath,expected_tier,expected_trail", [
        (135, 100, 140, (0.20, 0.50), 0.15),         # +35% → Tier 2
        (175, 100, 180, (0.50, 1.00), 0.20),         # +75% → Tier 3
        (300, 100, 320, (1.00, 5.00), 0.25),         # +200% → Tier 4
        (700, 100, 750, (5.00, float('inf')), 0.30), # +600% → Tier 5
    ])
    def test_tier_detection_parametrized(
        self,
        trailing_calculator,
        current,
        avg,
        ath,
        expected_tier,
        expected_trail
    ):
        """Test tier detection with multiple gain scenarios"""
        result = trailing_calculator.calculate_trailing_stop(current, avg, ath)
        assert result['applicable'] is True
        assert result['tier'] == expected_tier
        assert result['trail_pct'] == expected_trail


# ============================================================================
# Test Suite 2: Minimum Gain Threshold
# ============================================================================

class TestMinimumGainThreshold:
    """Test 20% minimum gain requirement"""

    def test_below_threshold(self, trailing_calculator):
        """Gain <20%: Not applicable"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=110.0,
            avg_price=100.0,
            ath=110.0
        )
        assert result['applicable'] is False
        assert result['unrealized_gain_pct'] == pytest.approx(10.0, abs=0.01)
        assert result['min_threshold'] == 20.0

    def test_exactly_at_threshold(self, trailing_calculator):
        """Gain exactly 20%: Should be applicable (Tier 2)"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=121.0,  # Need >20% due to strict threshold check
            avg_price=100.0,
            ath=121.0
        )
        assert result['applicable'] is True
        assert result['unrealized_gain_pct'] == pytest.approx(21.0, abs=0.01)
        assert result['tier'] == (0.20, 0.50)

    def test_just_above_threshold(self, trailing_calculator):
        """Gain 21%: Should be applicable"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=121.0,
            avg_price=100.0,
            ath=121.0
        )
        assert result['applicable'] is True
        assert result['unrealized_gain_pct'] == 21.0

    def test_negative_gain(self, trailing_calculator):
        """Negative gain (loss): Not applicable"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=80.0,
            avg_price=100.0,
            ath=100.0
        )
        assert result['applicable'] is False
        assert result['unrealized_gain_pct'] == pytest.approx(-20.0, abs=0.01)


# ============================================================================
# Test Suite 3: ATH Estimation
# ============================================================================

class TestATHEstimation:
    """Test All-Time High estimation from price history"""

    def test_ath_from_high_column(self, trailing_calculator, mock_price_data):
        """ATH should be estimated from 'high' column (most accurate)"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=170.0,
            avg_price=100.0,
            ath=None,  # Will be estimated
            price_history=mock_price_data
        )
        assert result['applicable'] is True
        assert result['ath'] == 200.0  # Max of 'high' column
        assert result['ath_estimated'] is True

    def test_ath_from_close_column_fallback(self, trailing_calculator, mock_price_data_no_high):
        """ATH from 'close' column when 'high' is not available"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=170.0,
            avg_price=100.0,
            ath=None,
            price_history=mock_price_data_no_high
        )
        assert result['applicable'] is True
        assert result['ath'] == 195.0  # Max of 'close' column
        assert result['ath_estimated'] is True

    def test_ath_minimum_is_current_price(self, trailing_calculator):
        """ATH cannot be lower than current price"""
        # Price history with max=180, but current=200
        price_data = pd.DataFrame({
            'high': [100, 150, 180, 170, 160],
            'close': [95, 145, 175, 165, 155]
        })
        result = trailing_calculator.calculate_trailing_stop(
            current_price=200.0,
            avg_price=100.0,
            ath=None,
            price_history=price_data
        )
        assert result['applicable'] is True
        assert result['ath'] == 200.0  # Should use current_price, not 180

    def test_ath_provided_not_estimated(self, trailing_calculator):
        """When ATH is provided, don't estimate"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=170.0,
            avg_price=100.0,
            ath=250.0,  # Provided
            price_history=None
        )
        assert result['applicable'] is True
        assert result['ath'] == 250.0
        assert result['ath_estimated'] is False

    def test_no_price_history_uses_current_as_ath(self, trailing_calculator):
        """Without price history, use current_price as ATH"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=170.0,
            avg_price=100.0,
            ath=None,
            price_history=None
        )
        assert result['applicable'] is True
        assert result['ath'] == 170.0
        assert result['ath_estimated'] is True

    def test_empty_price_history(self, trailing_calculator):
        """Empty DataFrame should fallback to current_price"""
        empty_df = pd.DataFrame()
        result = trailing_calculator.calculate_trailing_stop(
            current_price=170.0,
            avg_price=100.0,
            ath=None,
            price_history=empty_df
        )
        assert result['applicable'] is True
        assert result['ath'] == 170.0

    def test_ath_lookback_period(self):
        """Test custom ATH lookback period"""
        calc = TrailingStopCalculator(ath_lookback_days=10)  # Only 10 days

        # Create 30 days of data, but ATH in first 10 days
        price_data = pd.DataFrame({
            'high': [200, 190, 180, 170, 160, 150, 140, 130, 120, 110,
                     100, 100, 100, 100, 100, 100, 100, 100, 100, 100,
                     100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
        })

        result = calc.calculate_trailing_stop(
            current_price=110.0,
            avg_price=80.0,
            ath=None,
            price_history=price_data
        )
        # Should only look at last 10 days, so ATH should be 110 (not 200)
        assert result['ath'] >= 100.0  # At least 100 from recent history


# ============================================================================
# Test Suite 4: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and invalid inputs"""

    def test_no_avg_price(self, trailing_calculator):
        """Without avg_price, should return None"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=170.0,
            avg_price=None,
            ath=200.0
        )
        assert result is None

    def test_avg_price_zero(self, trailing_calculator):
        """avg_price=0 should return None"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=170.0,
            avg_price=0.0,
            ath=200.0
        )
        assert result is None

    def test_avg_price_negative(self, trailing_calculator):
        """Negative avg_price should return None"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=170.0,
            avg_price=-100.0,
            ath=200.0
        )
        assert result is None

    def test_current_price_zero(self, trailing_calculator):
        """current_price=0 should return None"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=0.0,
            avg_price=100.0,
            ath=200.0
        )
        assert result is None

    def test_current_price_negative(self, trailing_calculator):
        """Negative current_price should return None"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=-170.0,
            avg_price=100.0,
            ath=200.0
        )
        assert result is None

    def test_price_history_missing_columns(self, trailing_calculator):
        """Price history without 'high' or 'close' should fallback"""
        bad_df = pd.DataFrame({'open': [100, 150, 200]})
        result = trailing_calculator.calculate_trailing_stop(
            current_price=170.0,
            avg_price=100.0,
            ath=None,
            price_history=bad_df
        )
        # Should fallback to current_price as ATH
        assert result['ath'] == 170.0

    def test_tier_boundary_20_percent(self, trailing_calculator):
        """Test exact tier boundary at 20%"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=121.0,  # >20% to be applicable
            avg_price=100.0,
            ath=121.0
        )
        assert result['applicable'] is True
        assert result['tier'] == (0.20, 0.50)

    def test_tier_boundary_50_percent(self, trailing_calculator):
        """Test exact tier boundary at 50%"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=150.0,
            avg_price=100.0,
            ath=150.0
        )
        assert result['applicable'] is True
        # 50% gain (ratio 0.5) is start of Tier 3 [0.50, 1.00)
        assert result['tier'] == (0.50, 1.00)

    def test_tier_boundary_100_percent(self, trailing_calculator):
        """Test exact tier boundary at 100%"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=200.0,
            avg_price=100.0,
            ath=200.0
        )
        assert result['applicable'] is True
        # 100% gain (ratio 1.0) is start of Tier 4 [1.00, 5.00)
        assert result['tier'] == (1.00, 5.00)

    def test_tier_boundary_500_percent(self, trailing_calculator):
        """Test exact tier boundary at 500%"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=600.0,
            avg_price=100.0,
            ath=600.0
        )
        assert result['applicable'] is True
        # 500% gain (ratio 5.0) is start of Tier 5 [5.00, inf)
        assert result['tier'] == (5.00, float('inf'))


# ============================================================================
# Test Suite 5: Utility Methods
# ============================================================================

class TestUtilityMethods:
    """Test helper methods"""

    def test_is_legacy_position_default_threshold(self, trailing_calculator):
        """Test is_legacy_position with default 100% threshold"""
        # Above threshold
        assert trailing_calculator.is_legacy_position(
            current_price=250.0,
            avg_price=100.0
        ) is True

        # Below threshold
        assert trailing_calculator.is_legacy_position(
            current_price=150.0,
            avg_price=100.0
        ) is False

        # Exactly at threshold
        assert trailing_calculator.is_legacy_position(
            current_price=200.0,
            avg_price=100.0
        ) is True

    def test_is_legacy_position_custom_threshold(self, trailing_calculator):
        """Test is_legacy_position with custom threshold"""
        # 50% threshold
        assert trailing_calculator.is_legacy_position(
            current_price=160.0,
            avg_price=100.0,
            legacy_threshold=0.50
        ) is True

        assert trailing_calculator.is_legacy_position(
            current_price=140.0,
            avg_price=100.0,
            legacy_threshold=0.50
        ) is False

    def test_is_legacy_position_no_avg_price(self, trailing_calculator):
        """Without avg_price, should return False"""
        assert trailing_calculator.is_legacy_position(
            current_price=250.0,
            avg_price=None
        ) is False

    def test_get_tier_description(self, trailing_calculator):
        """Test human-readable tier descriptions"""
        # Tier 2
        desc = trailing_calculator._get_tier_description((0.20, 0.50), 0.15)
        assert "20-50%" in desc
        assert "15%" in desc

        # Tier 5 (legacy)
        desc = trailing_calculator._get_tier_description((5.00, float('inf')), 0.30)
        assert ">500%" in desc or "Legacy" in desc
        assert "30%" in desc

    def test_find_tier(self, trailing_calculator):
        """Test _find_tier method"""
        # 35% gain → Tier 2
        tier, trail = trailing_calculator._find_tier(0.35)
        assert tier == (0.20, 0.50)
        assert trail == 0.15

        # 600% gain → Tier 5
        tier, trail = trailing_calculator._find_tier(6.0)
        assert tier == (5.00, float('inf'))
        assert trail == 0.30


# ============================================================================
# Test Suite 6: Real-World Scenarios
# ============================================================================

class TestRealWorldScenarios:
    """Test with real position data from Saxo CSV (Oct 25, 2025)"""

    def test_aapl_position_real_data(self, trailing_calculator):
        """Real AAPL position: Entry $91.90, Current $262.82, Gain +186%"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=262.82,
            avg_price=91.90,
            ath=270.0  # Estimated ATH slightly above current
        )

        assert result['applicable'] is True
        assert result['unrealized_gain_pct'] == pytest.approx(186.0, rel=0.01)
        assert result['tier'] == (1.00, 5.00)  # Tier 4
        assert result['trail_pct'] == 0.25
        assert result['stop_loss'] == pytest.approx(202.5, abs=1.0)  # ~$203
        assert 'reasoning' in result

    def test_meta_position_real_data(self, trailing_calculator):
        """Real META position: Entry $240.95, Current $738.36, Gain +206%"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=738.36,
            avg_price=240.95,
            ath=750.0
        )

        assert result['applicable'] is True
        assert result['unrealized_gain_pct'] == pytest.approx(206.4, rel=0.01)
        assert result['tier'] == (1.00, 5.00)  # Tier 4
        assert result['trail_pct'] == 0.25
        assert result['stop_loss'] == pytest.approx(562.5, abs=1.0)

    def test_tsla_position_real_data(self, trailing_calculator):
        """Real TSLA position: Entry $343.64, Current $433.62, Gain +26%"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=433.62,
            avg_price=343.64,
            ath=440.0
        )

        assert result['applicable'] is True
        assert result['unrealized_gain_pct'] == pytest.approx(26.2, rel=0.1)
        assert result['tier'] == (0.20, 0.50)  # Tier 2
        assert result['trail_pct'] == 0.15
        assert result['stop_loss'] == pytest.approx(374.0, abs=1.0)


# ============================================================================
# Test Suite 7: Custom Tiers
# ============================================================================

class TestCustomTiers:
    """Test calculator with custom tier configuration"""

    def test_custom_tiers(self):
        """Test with custom tier configuration"""
        custom_tiers = {
            (0.0, 0.30): None,           # 0-30%: Not applicable
            (0.30, 0.60): 0.18,          # 30-60%: -18%
            (0.60, 1.50): 0.22,          # 60-150%: -22%
            (1.50, 10.0): 0.28,          # 150-1000%: -28%
            (10.0, float('inf')): 0.35   # >1000%: -35%
        }

        calc = TrailingStopCalculator(
            custom_tiers=custom_tiers,
            min_gain_threshold=0.30
        )

        # 50% gain → Custom Tier 2
        result = calc.calculate_trailing_stop(
            current_price=150.0,
            avg_price=100.0,
            ath=155.0
        )

        assert result['applicable'] is True
        assert result['tier'] == (0.30, 0.60)
        assert result['trail_pct'] == 0.18

    def test_custom_min_gain_threshold(self):
        """Test with custom minimum gain threshold"""
        calc = TrailingStopCalculator(min_gain_threshold=0.30)  # 30% minimum

        # 25% gain → Below threshold
        result = calc.calculate_trailing_stop(
            current_price=125.0,
            avg_price=100.0,
            ath=125.0
        )

        assert result['applicable'] is False
        assert result['min_threshold'] == 30.0


# ============================================================================
# Test Suite 8: Result Structure
# ============================================================================

class TestResultStructure:
    """Test result dictionary structure and completeness"""

    def test_result_keys_applicable(self, trailing_calculator):
        """When applicable, result should have all required keys"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=170.0,
            avg_price=100.0,
            ath=200.0
        )

        required_keys = [
            'applicable', 'stop_loss', 'distance_pct', 'unrealized_gain_pct',
            'ath', 'ath_estimated', 'trail_pct', 'tier', 'reasoning'
        ]

        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_result_keys_not_applicable(self, trailing_calculator):
        """When not applicable, result should have minimal keys"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=110.0,
            avg_price=100.0,
            ath=110.0
        )

        assert 'applicable' in result
        assert result['applicable'] is False
        assert 'unrealized_gain_pct' in result

    def test_stop_loss_rounded_correctly(self, trailing_calculator):
        """Stop loss should be rounded to 2 decimals"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=135.5555,
            avg_price=100.0,
            ath=140.6789
        )

        # Should be rounded to 2 decimals
        assert isinstance(result['stop_loss'], float)
        assert result['stop_loss'] == round(140.6789 * 0.85, 2)

    def test_distance_pct_rounded_correctly(self, trailing_calculator):
        """Distance percentage should be rounded to 1 decimal"""
        result = trailing_calculator.calculate_trailing_stop(
            current_price=135.0,
            avg_price=100.0,
            ath=140.0
        )

        assert isinstance(result['distance_pct'], float)
        # Distance from 135 to 119 should be negative
        assert result['distance_pct'] < 0
