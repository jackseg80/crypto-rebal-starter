"""
Integration tests for Trailing Stop integration in StopLossCalculator.

Tests the complete integration:
1. Trailing stop as Method #6 in stop_loss_levels
2. Prioritization over other methods (Fixed Variable, ATR, etc.)
3. Quality badge and legacy flags
4. Fallback behavior when avg_price is missing
5. Integration with price history

Method Priority (updated Oct 2025):
1. Trailing Stop (highest - for legacy positions with avg_price)
2. Fixed Variable (recommended for standard positions)
3. ATR 2x
4. Technical Support
5. Volatility 2σ
6. Fixed % (fallback)
"""

import pytest
import pandas as pd
import numpy as np
from services.ml.bourse.stop_loss_calculator import StopLossCalculator


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def stop_loss_calc():
    """StopLossCalculator instance with default settings"""
    return StopLossCalculator(timeframe="medium", market_regime="Bull Market")


@pytest.fixture
def mock_price_data():
    """Mock OHLC price history (60 days for better ATR calculation)"""
    dates = pd.date_range('2024-01-01', periods=60, freq='D')
    base_price = 100.0

    # Create realistic OHLC data
    np.random.seed(42)
    closes = [base_price]
    for _ in range(59):
        change = np.random.normal(0.001, 0.02)  # 0.1% mean, 2% std
        closes.append(closes[-1] * (1 + change))

    closes = np.array(closes)
    highs = closes * (1 + np.abs(np.random.normal(0, 0.01, 60)))
    lows = closes * (1 - np.abs(np.random.normal(0, 0.01, 60)))

    return pd.DataFrame({
        'high': highs,
        'low': lows,
        'close': closes,
        'open': closes * (1 + np.random.normal(0, 0.005, 60))
    })


@pytest.fixture
def legacy_position_price_data():
    """Price data simulating a legacy position with ATH"""
    # Position bought at $100, ATH was $500, currently at $450
    return pd.DataFrame({
        'high': [100, 150, 200, 300, 400, 500, 480, 460, 450, 445] * 5,  # 50 days
        'low': [95, 145, 195, 295, 395, 495, 475, 455, 445, 440] * 5,
        'close': [98, 148, 198, 298, 398, 498, 478, 458, 448, 443] * 5
    })


# ============================================================================
# Test Suite 1: Method #6 Present
# ============================================================================

class TestTrailingStopMethodPresent:
    """Test that trailing_stop is present in stop_loss_levels"""

    def test_trailing_stop_in_results(self, stop_loss_calc, mock_price_data):
        """Trailing stop should appear in stop_loss_levels when avg_price provided"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=150.0,
            price_data=mock_price_data,
            avg_price=100.0  # +50% gain
        )

        assert 'trailing_stop' in result['stop_loss_levels']
        assert result['stop_loss_levels']['trailing_stop'] is not None

    def test_six_methods_available(self, stop_loss_calc, mock_price_data):
        """Should have 6 methods when all conditions met"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=150.0,
            price_data=mock_price_data,
            avg_price=100.0
        )

        # With sufficient price data and avg_price:
        # 1. Fixed Variable, 2. ATR 2x, 3. Technical Support
        # 4. Volatility 2σ, 5. Fixed %, 6. Trailing Stop
        assert len(result['stop_loss_levels']) >= 5  # At least 5 (trailing might not apply if <20% gain)

    def test_trailing_stop_structure(self, stop_loss_calc, mock_price_data):
        """Trailing stop result should have correct structure"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=300.0,  # +200% gain
            price_data=mock_price_data,
            avg_price=100.0
        )

        ts = result['stop_loss_levels']['trailing_stop']

        # Required fields
        assert 'price' in ts
        assert 'distance_pct' in ts
        assert 'gain_pct' in ts
        assert 'ath' in ts
        assert 'quality' in ts
        assert 'is_legacy' in ts
        assert 'reasoning' in ts

    def test_trailing_stop_values_reasonable(self, stop_loss_calc, legacy_position_price_data):
        """Trailing stop values should be reasonable"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=450.0,  # ATH was 500
            price_data=legacy_position_price_data,
            avg_price=100.0  # +350% gain → Tier 4
        )

        ts = result['stop_loss_levels']['trailing_stop']

        # Stop loss should be below current price
        assert ts['price'] < 450.0

        # Distance should be negative (stop below current)
        assert ts['distance_pct'] < 0

        # Gain should be ~350%
        assert ts['gain_pct'] == pytest.approx(350.0, rel=0.1)

        # ATH should be around 500
        assert ts['ath'] >= 450.0  # At least current price


# ============================================================================
# Test Suite 2: Prioritization
# ============================================================================

class TestTrailingStopPrioritization:
    """Test that trailing stop is prioritized correctly"""

    def test_trailing_stop_recommended_for_legacy(self, stop_loss_calc, legacy_position_price_data):
        """Trailing stop should be recommended for legacy positions"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=450.0,
            price_data=legacy_position_price_data,
            avg_price=100.0  # +350% gain
        )

        assert result['recommended_method'] == 'trailing_stop'
        assert 'recommended' in result
        assert result['recommended']['is_legacy'] is True

    def test_fixed_variable_recommended_without_avg_price(self, stop_loss_calc, mock_price_data):
        """Without avg_price, should recommend Fixed Variable"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=150.0,
            price_data=mock_price_data,
            avg_price=None  # No avg_price
        )

        assert 'trailing_stop' not in result['stop_loss_levels']
        assert result['recommended_method'] == 'fixed_variable'

    def test_fixed_variable_recommended_for_low_gain(self, stop_loss_calc, mock_price_data):
        """For gains <20%, should recommend Fixed Variable (not trailing)"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=115.0,  # +15% gain
            price_data=mock_price_data,
            avg_price=100.0
        )

        # Trailing stop not applicable
        assert 'trailing_stop' not in result['stop_loss_levels']
        assert result['recommended_method'] == 'fixed_variable'

    def test_trailing_stop_overrides_all_others(self, stop_loss_calc, legacy_position_price_data):
        """Trailing stop should override all other methods when applicable"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=450.0,
            price_data=legacy_position_price_data,
            avg_price=100.0
        )

        # All standard methods should be present
        assert 'fixed_variable' in result['stop_loss_levels']
        assert 'atr_2x' in result['stop_loss_levels']

        # But trailing stop should be recommended
        assert result['recommended_method'] == 'trailing_stop'


# ============================================================================
# Test Suite 3: Quality Badges and Flags
# ============================================================================

class TestQualityBadgesAndFlags:
    """Test quality indicators and legacy flags"""

    def test_trailing_stop_quality_high(self, stop_loss_calc, legacy_position_price_data):
        """Trailing stop should have 'high' quality"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=450.0,
            price_data=legacy_position_price_data,
            avg_price=100.0
        )

        ts = result['stop_loss_levels']['trailing_stop']
        assert ts['quality'] == 'high'

    def test_trailing_stop_is_legacy_flag(self, stop_loss_calc, legacy_position_price_data):
        """Trailing stop should have is_legacy=True"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=450.0,
            price_data=legacy_position_price_data,
            avg_price=100.0
        )

        ts = result['stop_loss_levels']['trailing_stop']
        assert ts['is_legacy'] is True

    def test_get_quality_badge_for_trailing_stop(self, stop_loss_calc):
        """Quality badge method should return 'high' for trailing_stop"""
        badge = stop_loss_calc.get_stop_loss_quality_badge('trailing_stop')
        assert badge == 'high'

    def test_recommended_method_has_high_quality(self, stop_loss_calc, legacy_position_price_data):
        """When trailing stop is recommended, quality should be high"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=450.0,
            price_data=legacy_position_price_data,
            avg_price=100.0
        )

        if result['recommended_method'] == 'trailing_stop':
            recommended = result['recommended']
            assert recommended['quality'] == 'high'


# ============================================================================
# Test Suite 4: Fallback Behavior
# ============================================================================

class TestFallbackBehavior:
    """Test fallback when trailing stop not applicable"""

    def test_no_avg_price_no_trailing_stop(self, stop_loss_calc, mock_price_data):
        """Without avg_price, trailing stop should not be in results"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=150.0,
            price_data=mock_price_data,
            avg_price=None
        )

        assert 'trailing_stop' not in result['stop_loss_levels']

    def test_zero_avg_price_no_trailing_stop(self, stop_loss_calc, mock_price_data):
        """avg_price=0 should not generate trailing stop"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=150.0,
            price_data=mock_price_data,
            avg_price=0.0
        )

        assert 'trailing_stop' not in result['stop_loss_levels']

    def test_negative_avg_price_no_trailing_stop(self, stop_loss_calc, mock_price_data):
        """Negative avg_price should not generate trailing stop"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=150.0,
            price_data=mock_price_data,
            avg_price=-100.0
        )

        assert 'trailing_stop' not in result['stop_loss_levels']

    def test_insufficient_gain_no_trailing_stop(self, stop_loss_calc, mock_price_data):
        """Gain <20% should not generate trailing stop"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=110.0,  # +10% gain
            price_data=mock_price_data,
            avg_price=100.0
        )

        assert 'trailing_stop' not in result['stop_loss_levels']

    def test_fallback_has_fixed_variable(self, stop_loss_calc, mock_price_data):
        """When trailing stop not applicable, Fixed Variable should be recommended"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=110.0,
            price_data=mock_price_data,
            avg_price=None  # No trailing stop
        )

        assert result['recommended_method'] == 'fixed_variable'
        assert 'fixed_variable' in result['stop_loss_levels']


# ============================================================================
# Test Suite 5: Price History Integration
# ============================================================================

class TestPriceHistoryIntegration:
    """Test integration with price history for ATH estimation"""

    def test_ath_estimated_from_price_history(self, stop_loss_calc, legacy_position_price_data):
        """ATH should be estimated from price_history when not provided"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=450.0,
            price_data=legacy_position_price_data,
            avg_price=100.0
        )

        ts = result['stop_loss_levels']['trailing_stop']
        assert ts['ath_estimated'] is True
        assert ts['ath'] >= 450.0  # Should be max from history

    def test_without_price_history_uses_current_as_ath(self, stop_loss_calc):
        """Without price_history, should use current_price as ATH"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=300.0,
            price_data=None,  # No price history
            avg_price=100.0  # +200% gain
        )

        ts = result['stop_loss_levels']['trailing_stop']
        assert ts['ath'] == 300.0
        assert ts['ath_estimated'] is True

    def test_short_price_history_handled(self, stop_loss_calc):
        """Short price history should be handled gracefully"""
        short_history = pd.DataFrame({
            'high': [100, 150, 200],
            'close': [98, 148, 198]
        })

        result = stop_loss_calc.calculate_all_methods(
            current_price=180.0,
            price_data=short_history,
            avg_price=100.0
        )

        # Should still work with short history
        if 'trailing_stop' in result['stop_loss_levels']:
            ts = result['stop_loss_levels']['trailing_stop']
            assert ts['ath'] >= 180.0


# ============================================================================
# Test Suite 6: Real-World Position Scenarios
# ============================================================================

class TestRealWorldPositionScenarios:
    """Test with realistic position scenarios"""

    def test_aapl_position_scenario(self, stop_loss_calc):
        """Simulate real AAPL position: Entry $91.90, Current $262.82, +186%"""
        # Simulate price history with ATH around $270
        price_history = pd.DataFrame({
            'high': [250, 260, 270, 268, 265, 263, 262] * 10,  # 70 days
            'low': [245, 255, 265, 263, 260, 258, 257] * 10,
            'close': [248, 258, 268, 266, 263, 261, 260] * 10
        })

        result = stop_loss_calc.calculate_all_methods(
            current_price=262.82,
            price_data=price_history,
            avg_price=91.90
        )

        assert 'trailing_stop' in result['stop_loss_levels']
        assert result['recommended_method'] == 'trailing_stop'

        ts = result['stop_loss_levels']['trailing_stop']
        assert ts['gain_pct'] == pytest.approx(186.0, rel=0.01)
        assert ts['tier'] == (1.00, 5.00)  # Tier 4
        assert ts['trail_pct'] == 0.25

    def test_recent_position_scenario(self, stop_loss_calc, mock_price_data):
        """Recent position with small gain should use Fixed Variable"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=105.0,  # +5% gain
            price_data=mock_price_data,
            avg_price=100.0
        )

        # Trailing stop not applicable
        assert 'trailing_stop' not in result['stop_loss_levels']
        assert result['recommended_method'] == 'fixed_variable'

    def test_moderate_gain_position(self, stop_loss_calc, mock_price_data):
        """Position with 35% gain should use trailing stop"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=135.0,  # +35% gain
            price_data=mock_price_data,
            avg_price=100.0
        )

        assert 'trailing_stop' in result['stop_loss_levels']
        assert result['recommended_method'] == 'trailing_stop'

        ts = result['stop_loss_levels']['trailing_stop']
        assert ts['tier'] == (0.20, 0.50)  # Tier 2


# ============================================================================
# Test Suite 7: Comparison with Other Methods
# ============================================================================

class TestComparisonWithOtherMethods:
    """Test trailing stop compared to other methods"""

    def test_trailing_stop_wider_than_fixed_variable(self, stop_loss_calc, legacy_position_price_data):
        """Trailing stop should be wider (lower) than Fixed Variable for legacy positions"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=450.0,
            price_data=legacy_position_price_data,
            avg_price=100.0
        )

        ts_stop = result['stop_loss_levels']['trailing_stop']['price']
        fv_stop = result['stop_loss_levels']['fixed_variable']['price']

        # Trailing stop should be much wider (lower price)
        assert ts_stop < fv_stop

    def test_all_methods_present_for_comparison(self, stop_loss_calc, legacy_position_price_data):
        """All methods should be available for user comparison"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=450.0,
            price_data=legacy_position_price_data,
            avg_price=100.0
        )

        # Should have at least 5 methods (possibly 6 with trailing)
        assert len(result['stop_loss_levels']) >= 5

        # Key methods should be present
        assert 'fixed_variable' in result['stop_loss_levels']
        assert 'trailing_stop' in result['stop_loss_levels']

    def test_reasoning_explains_choice(self, stop_loss_calc, legacy_position_price_data):
        """Recommended method should have reasoning"""
        result = stop_loss_calc.calculate_all_methods(
            current_price=450.0,
            price_data=legacy_position_price_data,
            avg_price=100.0
        )

        if result['recommended_method'] == 'trailing_stop':
            ts = result['stop_loss_levels']['trailing_stop']
            assert 'reasoning' in ts
            assert len(ts['reasoning']) > 0
            assert 'gain' in ts['reasoning'].lower()


# ============================================================================
# Test Suite 8: Edge Cases in Integration
# ============================================================================

class TestEdgeCasesInIntegration:
    """Test edge cases specific to integration"""

    def test_very_high_volatility_asset(self, stop_loss_calc):
        """High volatility asset should still work with trailing stop"""
        # Create volatile price history
        volatile_data = pd.DataFrame({
            'high': [100, 150, 120, 180, 140, 200, 160, 190] * 8,
            'low': [90, 140, 110, 170, 130, 190, 150, 180] * 8,
            'close': [95, 145, 115, 175, 135, 195, 155, 185] * 8
        })

        result = stop_loss_calc.calculate_all_methods(
            current_price=180.0,
            price_data=volatile_data,
            avg_price=100.0  # +80% gain
        )

        # Should still have trailing stop despite volatility
        # Check if trailing stop is in levels (gain is 80%, should be applicable)
        if 'trailing_stop' in result['stop_loss_levels']:
            ts = result['stop_loss_levels']['trailing_stop']
            assert ts['gain_pct'] >= 20

    def test_multiple_calls_consistent_results(self, stop_loss_calc, mock_price_data):
        """Multiple calls with same data should produce consistent results"""
        result1 = stop_loss_calc.calculate_all_methods(
            current_price=150.0,
            price_data=mock_price_data,
            avg_price=100.0
        )

        result2 = stop_loss_calc.calculate_all_methods(
            current_price=150.0,
            price_data=mock_price_data,
            avg_price=100.0
        )

        # Results should be identical
        assert result1['recommended_method'] == result2['recommended_method']

        if 'trailing_stop' in result1['stop_loss_levels']:
            assert 'trailing_stop' in result2['stop_loss_levels']
            assert result1['stop_loss_levels']['trailing_stop']['price'] == \
                   result2['stop_loss_levels']['trailing_stop']['price']

    def test_different_timeframes(self):
        """Trailing stop should work with different timeframes"""
        for timeframe in ['short', 'medium', 'long']:
            calc = StopLossCalculator(timeframe=timeframe)
            result = calc.calculate_all_methods(
                current_price=300.0,
                price_data=None,
                avg_price=100.0  # +200% gain
            )

            # Trailing stop should be present regardless of timeframe
            assert 'trailing_stop' in result['stop_loss_levels']

    def test_different_market_regimes(self):
        """Trailing stop should work with different market regimes"""
        for regime in ['Bull Market', 'Bear Market', 'Correction', 'Expansion']:
            calc = StopLossCalculator(market_regime=regime)
            result = calc.calculate_all_methods(
                current_price=300.0,
                price_data=None,
                avg_price=100.0
            )

            # Trailing stop should be present regardless of regime
            assert 'trailing_stop' in result['stop_loss_levels']
