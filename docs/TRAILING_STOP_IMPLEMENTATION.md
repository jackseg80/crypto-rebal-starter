# Trailing Stop Implementation - Legacy Positions Protection

> **Date:** October 2025
> **Status:** Production
> **Module:** Stop Loss Calculator (Method #6)

## 🎯 Executive Summary

The **Trailing Stop** system protects unrealized gains on long-term winning positions (legacy holdings) by using wider, adaptive stop losses based on All-Time High (ATH) rather than current price.

**Key Benefits:**
- ✅ Lets winners run: +2400% positions get -30% trailing stops (vs -6% standard)
- ✅ Protects capital: Minimum gain threshold prevents premature exits
- ✅ Adaptive tiers: 5 gain ranges with different trail percentages
- ✅ Automatic detection: No manual tagging required
- ✅ Reusable: Works for stocks, crypto, commodities

**Example:**
```
Position bought 10 years ago:
  Entry: $20
  Current: $500 (+2400%)
  ATH: $550
  Standard stop (6%): $470 ❌ (too tight, forces exit on minor correction)
  Trailing stop (30%): $385 ✅ (lets position breathe, protects +1825% min)
```

---

## 📐 Architecture

### System Flow

```
CSV Saxo → SaxoImportConnector (extract avg_price)
           ↓
     Position dict {avg_price, ...}
           ↓
  RecommendationsOrchestrator (pass avg_price)
           ↓
     PriceTargets.calculate_targets(avg_price)
           ↓
  StopLossCalculator.calculate_all_methods(avg_price)
           ↓
   TrailingStopCalculator.calculate_trailing_stop()
           ↓
  [Estimate ATH from price history]
  [Determine gain tier]
  [Calculate trailing stop = ATH × (1 - trail_pct)]
           ↓
     Stop loss result (Method #6)
           ↓
  UI: Badge 🏆 + Modal highlight
```

### Files Modified/Created

| Type | File | Changes |
|------|------|---------|
| **NEW** | `services/stop_loss/trailing_stop_calculator.py` | Generic trailing stop calculator (reusable) |
| **NEW** | `services/stop_loss/__init__.py` | Module init |
| **NEW** | `docs/TRAILING_STOP_IMPLEMENTATION.md` | This documentation |
| Modified | `connectors/saxo_import.py` | Extract avg_price from "Prix entrée" column |
| Modified | `services/ml/bourse/stop_loss_calculator.py` | Add trailing stop as Method #6 |
| Modified | `services/ml/bourse/price_targets.py` | Add avg_price parameter |
| Modified | `services/ml/bourse/recommendations_orchestrator.py` | Pass avg_price to targets |
| Modified | `static/saxo-dashboard.html` | Add 🏆 Legacy badge + modal highlight |

---

## 🔢 Gain Tiers & Trailing Percentages

The system uses **5 adaptive tiers** based on unrealized gains:

| Tier | Gain Range | Trailing % | Stop Loss Logic | Use Case |
|------|------------|------------|-----------------|----------|
| **Tier 1** | 0-20% | N/A | Standard stop | Recent positions |
| **Tier 2** | 20-50% | -15% from ATH | Modest protection | Short-term winners |
| **Tier 3** | 50-100% | -20% from ATH | Moderate protection | Medium-term winners |
| **Tier 4** | 100-500% | -25% from ATH | Strong protection | Long-term winners |
| **Tier 5** | >500% | -30% from ATH | Maximum protection | Legacy positions |

### Tier Selection Examples

**Example 1: Recent position (+10%)**
```python
Entry: $100
Current: $110
Gain: +10%
Tier: 1 (0-20%)
Result: Use standard stop (Fixed Variable 6%) → $103.40
```

**Example 2: Short-term winner (+35%)**
```python
Entry: $100
Current: $135
ATH: $140
Gain: +35%
Tier: 2 (20-50%)
Trailing: -15% from ATH
Stop: $140 × 0.85 = $119
Result: Protects +19% minimum
```

**Example 3: Legacy position (+2400%)**
```python
Entry: $20
Current: $500
ATH: $550 (estimated from 1-year history)
Gain: +2400%
Tier: 5 (>500%)
Trailing: -30% from ATH
Stop: $550 × 0.70 = $385
Result: Protects +1825% minimum
```

---

## 🧮 ATH Estimation

**Why estimate ATH instead of tracking in real-time?**
- ✅ No database tracking required (performance)
- ✅ Fast calculation from existing price history
- ✅ Good enough: 1-year lookback captures recent peaks
- ✅ Conservative: Uses max(historical_high, current_price)

### Estimation Algorithm

```python
def _estimate_ath(price_history: pd.DataFrame, current_price: float) -> float:
    """
    Estimate ATH from last 365 days of price history

    Args:
        price_history: OHLC DataFrame (columns: 'high', 'close')
        current_price: Current market price

    Returns:
        Estimated ATH (always >= current_price)
    """
    # Use 'high' column if available (more accurate)
    if 'high' in price_history.columns:
        recent_high = price_history['high'].tail(365).max()
    else:
        recent_high = price_history['close'].tail(365).max()

    # ATH cannot be lower than current price
    return max(recent_high, current_price)
```

**Lookback period:**
- Default: **365 days** (1 year)
- Rationale: Balances recency vs capturing true peaks
- Configurable: Can be adjusted in `TrailingStopCalculator.__init__(ath_lookback_days=365)`

**Edge cases:**
- No price history → Use current price as ATH
- ATH < current price → Use current price (conservative)

---

## 🏗️ Code Structure

### TrailingStopCalculator Class

**File:** `services/stop_loss/trailing_stop_calculator.py`

```python
class TrailingStopCalculator:
    """Generic trailing stop calculator for any asset class"""

    # Configuration
    TRAILING_TIERS = {
        (0.0, 0.20): None,           # 0-20%: Not applicable
        (0.20, 0.50): 0.15,          # 20-50%: -15%
        (0.50, 1.00): 0.20,          # 50-100%: -20%
        (1.00, 5.00): 0.25,          # 100-500%: -25%
        (5.00, float('inf')): 0.30   # >500%: -30%
    }
    MIN_GAIN_PCT = 0.20  # 20% minimum gain threshold
    DEFAULT_ATH_LOOKBACK = 365  # days

    def calculate_trailing_stop(
        self,
        current_price: float,
        avg_price: Optional[float],
        ath: Optional[float] = None,
        price_history: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Calculate trailing stop based on unrealized gains

        Returns:
            {
                'applicable': bool,
                'stop_loss': float,
                'distance_pct': float,
                'unrealized_gain_pct': float,
                'ath': float,
                'ath_estimated': bool,
                'trail_pct': float,
                'tier': tuple,
                'reasoning': str
            }
        """
```

**Key Methods:**
- `calculate_trailing_stop()` - Main entry point
- `_estimate_ath()` - Estimate ATH from price history
- `_find_tier()` - Determine applicable gain tier
- `_get_tier_description()` - Human-readable tier description
- `is_legacy_position()` - Check if position qualifies as legacy

### Integration in StopLossCalculator

**File:** `services/ml/bourse/stop_loss_calculator.py`

```python
class StopLossCalculator:
    """Multi-method stop loss calculator (now 6 methods)"""

    def calculate_all_methods(
        self,
        current_price: float,
        price_data: Optional[pd.DataFrame] = None,
        volatility: Optional[float] = None,
        avg_price: Optional[float] = None  # NEW parameter
    ) -> Dict[str, Any]:
        # ... existing methods 1-5 ...

        # Method 6: Trailing Stop (NEW)
        if avg_price and avg_price > 0:
            trailing_calc = TrailingStopCalculator(ath_lookback_days=365)
            trailing_result = trailing_calc.calculate_trailing_stop(
                current_price=current_price,
                avg_price=avg_price,
                ath=None,  # Will be estimated
                price_history=price_data
            )

            if trailing_result and trailing_result.get('applicable'):
                result["stop_loss_levels"]["trailing_stop"] = {
                    "price": trailing_result["stop_loss"],
                    "distance_pct": trailing_result["distance_pct"],
                    "gain_pct": trailing_result["unrealized_gain_pct"],
                    "ath": trailing_result["ath"],
                    "quality": "high",
                    "is_legacy": True
                }
```

**Priority Order (updated):**
1. **Trailing Stop** (highest priority for legacy positions)
2. Fixed Variable (recommended for standard positions)
3. ATR 2x
4. Technical Support
5. Volatility 2σ
6. Fixed % (fallback)

---

## 🎨 UI Implementation

### Table Badge (Minimal)

Small 🏆 badge appears next to symbol when trailing stop is active:

```javascript
// In renderRecommendationsTable()
const isTrailingStop = rec.price_targets?.stop_loss_analysis?.recommended_method === 'trailing_stop';
const gainPct = trailingInfo?.gain_pct || 0;
const legacyBadge = isTrailingStop ?
    `<span style="..." title="Legacy position +${gainPct}% (trailing stop active)">🏆</span>` : '';

// Symbol cell
<td>${rec.symbol}${legacyBadge}</td>
```

**Design Principles:**
- ✅ Small badge (0.65rem font)
- ✅ Green background (#10b981)
- ✅ Tooltip with gain percentage
- ✅ Only shown when trailing stop is active

### Modal Highlight

In the stop loss comparison table (modal), trailing stop method is highlighted:

```javascript
// In renderStopLossAnalysis() → renderMethod()
const isTrailingStop = methodKey === 'trailing_stop';
const trailingNote = isTrailingStop ?
    `<div style="color: var(--success); font-size: 0.65rem;">
        Position long terme détectée (+${gain_pct}%)
    </div>` : '';
```

**Design:**
- ✅ Method labeled as "🏆 Trailing Stop (Legacy)"
- ✅ Small note showing gain percentage
- ✅ Green highlight when recommended
- ✅ Reasoning displayed below table

---

## 🧪 Testing & Validation

### Test Cases

**Test 1: avg_price extraction**
```python
# Verify CSV "Prix entrée" column is extracted
from connectors.saxo_import import SaxoImportConnector
connector = SaxoImportConnector()
position = connector._process_position(row_with_prix_entree)
assert position['avg_price'] == 434.58
assert position['avg_price'] is not None
```

**Test 2: Trailing stop calculation**
```python
# Legacy position +2400%
from services.stop_loss.trailing_stop_calculator import TrailingStopCalculator
trailing_calc = TrailingStopCalculator()
result = trailing_calc.calculate_trailing_stop(
    current_price=500.0,
    avg_price=20.0,
    ath=550.0
)
assert result['applicable'] == True
assert result['unrealized_gain_pct'] == 2400.0
assert result['tier'] == (5.00, float('inf'))
assert result['trail_pct'] == 0.30
assert result['stop_loss'] == 385.0  # 550 × 0.7
```

**Test 3: Tier selection**
```python
# Test all tiers
test_cases = [
    (110, 100, None),      # +10%: Not applicable
    (135, 100, 0.15),      # +35%: Tier 2 (-15%)
    (175, 100, 0.20),      # +75%: Tier 3 (-20%)
    (300, 100, 0.25),      # +200%: Tier 4 (-25%)
    (700, 100, 0.30),      # +600%: Tier 5 (-30%)
]
for current, avg, expected_trail in test_cases:
    result = trailing_calc.calculate_trailing_stop(current, avg, ath=current)
    if expected_trail is None:
        assert result['applicable'] == False
    else:
        assert result['trail_pct'] == expected_trail
```

**Test 4: ATH estimation**
```python
# Verify ATH is correctly estimated from price history
import pandas as pd
price_data = pd.DataFrame({
    'high': [100, 150, 200, 180, 170],  # ATH = 200
    'close': [95, 145, 195, 175, 165]
})
result = trailing_calc.calculate_trailing_stop(
    current_price=170,
    avg_price=100,
    ath=None,  # Should be estimated
    price_history=price_data
)
assert result['ath'] == 200.0
assert result['ath_estimated'] == True
```

**Test 5: Prioritization**
```python
# Verify trailing stop is prioritized over Fixed Variable
from services.ml/bourse.stop_loss_calculator import StopLossCalculator
calc = StopLossCalculator()
result = calc.calculate_all_methods(
    current_price=500.0,
    price_data=price_history,
    avg_price=20.0  # Legacy position
)
assert result['recommended_method'] == 'trailing_stop'
assert 'trailing_stop' in result['stop_loss_levels']
```

**Test 6: Fallback to Fixed Variable**
```python
# Without avg_price, should use Fixed Variable
result = calc.calculate_all_methods(
    current_price=500.0,
    price_data=price_history,
    avg_price=None  # No avg_price
)
assert result['recommended_method'] == 'fixed_variable'
assert 'trailing_stop' not in result['stop_loss_levels']
```

### Manual Testing Checklist

- [ ] Upload new Saxo CSV with "Prix entrée" column
- [ ] Verify avg_price is extracted in position data
- [ ] Navigate to Recommendations tab
- [ ] Check for 🏆 badge next to legacy positions (if any)
- [ ] Open recommendation modal for legacy position
- [ ] Verify "🏆 Trailing Stop (Legacy)" appears in stop loss table
- [ ] Check reasoning includes ATH and gain percentage
- [ ] Verify stop loss is wider than Fixed Variable
- [ ] Test with recent position (no trailing stop should appear)

---

## 🔄 Extension for Crypto

The `TrailingStopCalculator` is **generic** and can be used for crypto with minimal changes:

### Crypto Integration Example

```python
# In crypto rebalancing system
from services.stop_loss.trailing_stop_calculator import TrailingStopCalculator

# Get crypto position data
btc_position = {
    'symbol': 'BTC',
    'current_price': 50000,
    'avg_price': 20000,  # From cointracking CSV
    'quantity': 0.5
}

# Calculate trailing stop
trailing_calc = TrailingStopCalculator(
    ath_lookback_days=365  # Can adjust for crypto volatility
)

btc_history = get_crypto_ohlcv('BTC', days=365)  # From your data source

result = trailing_calc.calculate_trailing_stop(
    current_price=btc_position['current_price'],
    avg_price=btc_position['avg_price'],
    ath=None,  # Will be estimated from history
    price_history=btc_history
)

if result and result['applicable']:
    print(f"BTC Trailing Stop: ${result['stop_loss']}")
    print(f"Gain: +{result['unrealized_gain_pct']}%")
    print(f"ATH: ${result['ath']}")
```

### Crypto-Specific Considerations

1. **Higher volatility** → Consider wider trailing percentages
   ```python
   CRYPTO_TRAILING_TIERS = {
       (0.0, 0.50): None,           # 0-50%: Standard stop
       (0.50, 1.00): 0.20,          # 50-100%: -20%
       (1.00, 5.00): 0.30,          # 100-500%: -30%
       (5.00, float('inf')): 0.40   # >500%: -40% (crypto is more volatile)
   }
   ```

2. **Shorter ATH lookback** → Crypto moves faster
   ```python
   trailing_calc = TrailingStopCalculator(ath_lookback_days=180)  # 6 months
   ```

3. **Multiple exchanges** → Use consolidated price history
   ```python
   # Merge OHLCV from multiple exchanges
   btc_history = merge_ohlcv([binance_ohlcv, coinbase_ohlcv, kraken_ohlcv])
   ```

---

## 📊 Performance Comparison

| Position Type | Standard Stop (6%) | Trailing Stop (30%) | Improvement |
|---------------|-------------------|---------------------|-------------|
| Recent (+10%) | $103.40 ✅ | Not applicable | N/A |
| Short-term (+35%) | $126.90 | $119.00 ❌ | -6% (tighter) |
| Mid-term (+75%) | $164.50 | $140.00 ✅ | +18% (wider) |
| Long-term (+200%) | $282.00 | $225.00 ✅ | +25% (wider) |
| Legacy (+2400%) | $470.00 ❌ | $385.00 ✅ | +22% (much wider) |

**Key Insights:**
- ✅ Short-term positions (<50% gain): Standard stop is better
- ✅ Mid-term positions (50-100%): Trailing stop provides breathing room
- ✅ Legacy positions (>500%): Trailing stop is **essential** to avoid premature exits

---

## 🚀 Deployment Notes

### Prerequisites
- Python 3.9+
- Pandas, NumPy
- Existing stop loss infrastructure

### Installation
```bash
# No additional dependencies required
# System is integrated into existing ML Bourse module
```

### Configuration
```python
# Customize tiers (if needed)
from services.stop_loss.trailing_stop_calculator import TrailingStopCalculator

custom_tiers = {
    (0.0, 0.30): None,
    (0.30, 0.60): 0.18,
    (0.60, 1.50): 0.22,
    (1.50, 10.0): 0.28,
    (10.0, float('inf')): 0.35
}

trailing_calc = TrailingStopCalculator(
    custom_tiers=custom_tiers,
    min_gain_threshold=0.30,  # 30% minimum
    ath_lookback_days=180     # 6 months
)
```

### Rollback Plan
If issues arise, the system gracefully falls back:
1. If `avg_price` is missing → Uses Fixed Variable (no breaking change)
2. If `TrailingStopCalculator` fails → Logs error, uses Fixed Variable
3. If ATH estimation fails → Uses current price as ATH (conservative)

---

## 📈 Future Enhancements

### Phase 2 (Optional)
- [ ] **Real-time ATH tracking** - Store ATH in DB for exact tracking
- [ ] **Tax-aware stops** - Factor in capital gains tax rates
- [ ] **Position aging** - Adjust tiers based on holding period (not just gain)
- [ ] **Volatility adjustment** - Wider stops for high-vol assets
- [ ] **User overrides** - Allow manual tier adjustments per position

### Phase 3 (Advanced)
- [ ] **ML-optimized tiers** - Train model to find optimal trail percentages
- [ ] **Dynamic ATH lookback** - Adjust lookback period based on asset volatility
- [ ] **Multi-asset correlation** - Consider portfolio-wide risk
- [ ] **Backtest framework** - Validate trailing stop performance vs Fixed Variable

---

## 📚 References

- [STOP_LOSS_SYSTEM.md](STOP_LOSS_SYSTEM.md) - Main stop loss documentation
- [STOP_LOSS_BACKTEST_RESULTS.md](STOP_LOSS_BACKTEST_RESULTS.md) - Fixed Variable backtest
- [stop_loss_calculator.py](../services/ml/bourse/stop_loss_calculator.py) - Main calculator
- [trailing_stop_calculator.py](../services/stop_loss/trailing_stop_calculator.py) - Trailing stop implementation

---

## 🤝 Contributors

- **AI System** - Initial design and implementation (Oct 2025)
- **User (Jack)** - Requirements and testing

---

*Last Updated: October 2025*
