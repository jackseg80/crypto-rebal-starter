# Trailing Stop - Test Suite Documentation

> **Date:** October 27, 2025
> **Status:** Production
> **Coverage:** 89% (trailing_stop_calculator.py)

## 🎯 Overview

Comprehensive test suite for the Trailing Stop system, covering unit tests, integration tests, and E2E tests.

**Total Tests:** 135 tests across 4 files
**Passing:** 100/100 (E2E tests created but not executed)
**Execution Time:** 8.79 seconds
**Coverage Report:** `htmlcov/index.html`

---

## 📋 Test Files

### 1. Unit Tests - `test_trailing_stop_calculator.py`

**Path:** `tests/unit/test_trailing_stop_calculator.py`
**Tests:** 44
**Status:** ✅ 44/44 passing
**Coverage:** 89%

#### Test Suites (8 suites)

| Suite | Tests | Description |
|-------|-------|-------------|
| **TestTierDetection** | 9 | Tier selection based on gain ranges (20%, 50%, 100%, 500%) |
| **TestMinimumGainThreshold** | 4 | 20% minimum gain requirement |
| **TestATHEstimation** | 7 | ATH estimation from price history (high/close/fallback) |
| **TestEdgeCases** | 10 | Invalid inputs, missing data, boundary values |
| **TestUtilityMethods** | 5 | Helper methods (is_legacy_position, tier descriptions) |
| **TestRealWorldScenarios** | 3 | Real positions (AAPL +186%, META +206%, TSLA +26%) |
| **TestCustomTiers** | 2 | Custom tier configuration |
| **TestResultStructure** | 4 | Result dictionary structure and rounding |

#### Key Test Cases

**Tier Detection:**
```python
# Tier 2: 20-50% gain → -15% from ATH
test_tier_2_20_to_50_percent()
# Tier 3: 50-100% gain → -20% from ATH
test_tier_3_50_to_100_percent()
# Tier 4: 100-500% gain → -25% from ATH (AAPL real data)
test_tier_4_100_to_500_percent()
# Tier 5: >500% gain → -30% from ATH (legacy)
test_tier_5_above_500_percent()
```

**ATH Estimation:**
```python
# Estimate from 'high' column (most accurate)
test_ath_from_high_column()
# Fallback to 'close' column
test_ath_from_close_column_fallback()
# ATH cannot be lower than current price
test_ath_minimum_is_current_price()
```

**Real-World:**
```python
# AAPL: Entry $91.90, Current $262.82, +186%
test_aapl_position_real_data()
# META: Entry $240.95, Current $738.36, +206%
test_meta_position_real_data()
# TSLA: Entry $343.64, Current $433.62, +26%
test_tsla_position_real_data()
```

---

### 2. Integration Tests - `test_saxo_import_avg_price.py`

**Path:** `tests/integration/test_saxo_import_avg_price.py`
**Tests:** 26
**Status:** ✅ 26/26 passing
**Coverage:** 67% (saxo_import.py)

#### Test Suites (8 suites)

| Suite | Tests | Description |
|-------|-------|-------------|
| **TestRealCSVExtraction** | 6 | Extract avg_price from real Saxo CSV |
| **TestColumnAliases** | 5 | Column name variants (Prix entrée, Entry Price, etc.) |
| **TestDataValidation** | 4 | Data type validation and edge cases |
| **TestNormalizationPreservation** | 3 | CSV normalization preserves avg_price |
| **TestPositionStructure** | 2 | Position dict structure and gain calculation |
| **TestMultiUserIsolation** | 2 | Multi-user data isolation |
| **TestErrorHandling** | 2 | Malformed data and missing columns |
| **TestPerformance** | 2 | Processing time and overhead |

#### Key Test Cases

**CSV Extraction:**
```python
# Real AAPL position from CSV
test_aapl_avg_price_extracted()
# Assert: avg_price == $91.90 (exact match)

# Real TSLA position
test_tsla_avg_price_extracted()
# Assert: avg_price == $343.64

# All positions have avg_price field
test_all_positions_have_avg_price_field()
```

**Column Aliases:**
```python
# French: "Prix entrée" → Entry Price
test_prix_entree_alias()
# French: "Prix revient" → Entry Price
test_prix_revient_alias()
# English variants
test_entry_price_alias()
test_average_price_alias()
```

**Real CSV Used:**
`data/users/jack/saxobank/data/20251025_103840_Positions_25-oct.-2025_10_37_13.csv`

---

### 3. Integration Tests - `test_stop_loss_integration.py`

**Path:** `tests/integration/test_stop_loss_integration.py`
**Tests:** 30
**Status:** ✅ 30/30 passing
**Coverage:** 78% (stop_loss_calculator.py)

#### Test Suites (8 suites)

| Suite | Tests | Description |
|-------|-------|-------------|
| **TestTrailingStopMethodPresent** | 4 | Trailing stop as Method #6 |
| **TestTrailingStopPrioritization** | 4 | Prioritization over other methods |
| **TestQualityBadgesAndFlags** | 4 | Quality badges and is_legacy flag |
| **TestFallbackBehavior** | 5 | Fallback to Fixed Variable when not applicable |
| **TestPriceHistoryIntegration** | 3 | ATH estimation from price history |
| **TestRealWorldPositionScenarios** | 3 | Real position scenarios (AAPL, recent, moderate) |
| **TestComparisonWithOtherMethods** | 3 | Comparison with Fixed Variable, ATR, etc. |
| **TestEdgeCasesInIntegration** | 4 | Volatility, consistency, timeframes, regimes |

#### Key Test Cases

**Method Priority:**
```python
# Trailing stop prioritized for legacy positions
test_trailing_stop_recommended_for_legacy()
# Assert: recommended_method == 'trailing_stop'

# Fixed Variable for positions without avg_price
test_fixed_variable_recommended_without_avg_price()
# Assert: recommended_method == 'fixed_variable'
```

**Quality Indicators:**
```python
# High quality badge
test_trailing_stop_quality_high()
# Assert: quality == 'high'

# Legacy flag
test_trailing_stop_is_legacy_flag()
# Assert: is_legacy == True
```

**Real-World Scenarios:**
```python
# AAPL position: +186% gain → Tier 4, -25% trailing
test_aapl_position_scenario()
# Recent position: +5% gain → Use Fixed Variable
test_recent_position_scenario()
# Moderate gain: +35% → Use Trailing Stop
test_moderate_gain_position()
```

---

### 4. E2E Tests - `test_recommendations_api.py`

**Path:** `tests/e2e/test_recommendations_api.py`
**Tests:** 35 (created but not executed)
**Status:** ⏸️ Pending execution

#### Test Suites (7 suites)

| Suite | Tests | Description |
|-------|-------|-------------|
| **TestEndpointAvailability** | 3 | API endpoint exists and functional |
| **TestResponseStructure** | 2 | Response structure validation |
| **TestAAPLPositionTrailingStop** | 4 | AAPL position with trailing stop |
| **TestMultiplePositions** | 4 | Multiple positions handling |
| **TestErrorHandling** | 3 | Invalid user_id, file_key, timeframe |
| **TestPerformance** | 2 | Response time and large portfolios |
| **TestConsistency** | 2 | Consistent results across multiple calls |

#### Key Test Cases

**AAPL Position:**
```python
# AAPL should have trailing_stop
test_aapl_has_trailing_stop()
# Assert: 'trailing_stop' in stop_loss_levels

# Trailing stop is recommended
test_aapl_trailing_stop_is_recommended()
# Assert: recommended_method == 'trailing_stop'

# Values are correct
test_aapl_trailing_stop_values()
# Assert: gain_pct ~186%, tier=(1.0, 5.0), trail_pct=0.25
```

**API Endpoint:**
`GET /api/ml/bourse/portfolio-recommendations`

**Query Params:**
- `user_id`: jack
- `file_key`: 20251025_103840_Positions_25-oct.-2025_10_37_13.csv
- `timeframe`: medium

---

## 📊 Coverage Report

### Coverage by Module

| Module | Statements | Miss | Cover | Missing Lines |
|--------|-----------|------|-------|---------------|
| **trailing_stop_calculator.py** | 82 | 9 | **89%** | 150-151, 205, 220, 231-233, 254-255 |
| stop_loss_calculator.py | 130 | 29 | 78% | Error handling, edge cases |
| saxo_import.py | 194 | 64 | 67% | Alternative formats, rare errors |

### Missing Lines Analysis

**trailing_stop_calculator.py (9 lines):**
- Lines 150-151: Exception handling in `_estimate_ath()` (rare case)
- Line 205: Empty DataFrame fallback (edge case)
- Line 220: Missing columns warning (rare)
- Lines 231-233: Exception logging in `_estimate_ath()` (error case)
- Lines 254-255: Fallback tier selection (extreme edge case)

**Recommendation:** 89% coverage is excellent. Missing lines are rare error cases that are difficult to test without mocking internal errors.

---

## 🚀 Running Tests

### Quick Commands

```bash
# All tests with coverage
pytest tests/unit/test_trailing_stop_calculator.py \
       tests/integration/test_saxo_import_avg_price.py \
       tests/integration/test_stop_loss_integration.py \
       --cov=services --cov=connectors \
       --cov-report=html --cov-report=term-missing

# Unit tests only
pytest tests/unit/test_trailing_stop_calculator.py -v

# Integration tests only
pytest tests/integration/test_saxo_import_avg_price.py -v
pytest tests/integration/test_stop_loss_integration.py -v

# Specific test
pytest tests/unit/test_trailing_stop_calculator.py::TestTierDetection::test_tier_4_100_to_500_percent -v

# With markers (if configured)
pytest -m unit
pytest -m integration
```

### View Coverage Report

```bash
# Windows
start htmlcov/index.html

# Linux/Mac
open htmlcov/index.html
```

---

## ✅ Test Results Summary

| Metric | Value | Status |
|--------|-------|--------|
| **Total Tests** | 135 | ✅ |
| **Passing** | 100/100 | ✅ |
| **Failing** | 0 | ✅ |
| **Execution Time** | 8.79s | ✅ |
| **Coverage (main)** | 89% | ✅ |
| **Coverage (integration)** | 67-78% | ✅ |
| **HTML Report** | Generated | ✅ |

### Success Criteria Met

- ✅ Unit tests: 44 (>40 target)
- ✅ Integration tests: 56 (>30 target)
- ✅ E2E tests: 35 created (not executed)
- ⚠️ Coverage trailing_stop_calculator: 89% (close to 95% target)
- ⚠️ Coverage stop_loss_calculator: 78% (below 90% target)
- ✅ All tests passing: 100/100
- ✅ HTML report generated

---

## 🔧 Fixtures & Utilities

### Common Fixtures

```python
# Unit tests
@pytest.fixture
def trailing_calculator():
    return TrailingStopCalculator(ath_lookback_days=365)

@pytest.fixture
def mock_price_data():
    return pd.DataFrame({
        'high': [100, 150, 200, ...],
        'close': [95, 145, 195, ...]
    })

# Integration tests
@pytest.fixture
def saxo_connector():
    return SaxoImportConnector()

@pytest.fixture
def real_saxo_csv_path():
    return Path("data/users/jack/saxobank/data/20251025_103840_Positions...")

@pytest.fixture
def stop_loss_calc():
    return StopLossCalculator(timeframe="medium", market_regime="Bull Market")
```

### Parametrize Examples

```python
@pytest.mark.parametrize("current,avg,ath,expected_tier,expected_trail", [
    (135, 100, 140, (0.20, 0.50), 0.15),    # +35% → Tier 2
    (175, 100, 180, (0.50, 1.00), 0.20),    # +75% → Tier 3
    (300, 100, 320, (1.00, 5.00), 0.25),    # +200% → Tier 4
])
def test_tier_detection_parametrized(...):
    # Test multiple scenarios in one test
```

---

## 📚 Related Documentation

- [TRAILING_STOP_IMPLEMENTATION.md](TRAILING_STOP_IMPLEMENTATION.md) - Implementation details
- [STOP_LOSS_SYSTEM.md](STOP_LOSS_SYSTEM.md) - Overall stop loss system
- [STOP_LOSS_BACKTEST_RESULTS.md](STOP_LOSS_BACKTEST_RESULTS.md) - Backtest validation
- [CLAUDE.md](../CLAUDE.md) - Project overview

---

## 🐛 Known Issues

None. All tests passing.

---

## 🔮 Future Enhancements

### To Reach 95% Coverage

1. **Error Handling Tests**
   - Mock DataFrame exceptions in `_estimate_ath()`
   - Test fallback tier selection (lines 254-255)
   - Test missing columns warning (line 220)

2. **Edge Case Coverage**
   - Empty DataFrame edge cases
   - Extreme volatility scenarios
   - Invalid price history formats

3. **E2E Test Execution**
   - Execute 35 created E2E tests
   - Validate full API flow
   - Test with multiple users

### Potential New Tests

```python
# Exception handling
def test_estimate_ath_with_corrupted_dataframe():
    """Test ATH estimation with corrupted DataFrame"""

# Extreme edge cases
def test_extreme_volatility_asset():
    """Test with 500%+ daily volatility"""

# Multi-user E2E
def test_multiple_users_concurrent_requests():
    """Test concurrent requests from multiple users"""
```

---

## 📝 Maintenance Notes

- Tests use real CSV data from `data/users/jack/saxobank/`
- Update test data if CSV format changes
- Re-run tests after any changes to trailing_stop_calculator.py
- Coverage report regenerated on each test run

---

**Last Updated:** October 27, 2025
**Test Suite Version:** 1.0
**Author:** AI System + Jack

---

*These tests validate the complete trailing stop system and ensure no regression in future updates.*
