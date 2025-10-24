# System Formulas Reference — Complete Technical Specification

> **Document Type**: Technical Reference (Exact Formulas & Thresholds)
>
> **Date**: October 2025
>
> **Purpose**: Consolidate ALL exact formulas, thresholds, and calculation methods across the system
>
> **Audience**: AI agents, developers needing precise implementation details

---

## 📐 Table of Contents

1. [Contradiction Policy & Adaptive Weights](#1-contradiction-policy--adaptive-weights)
2. [Phase Engine Detection Rules](#2-phase-engine-detection-rules)
3. [Structure Scores (V2 vs Legacy)](#3-structure-scores-v2-vs-legacy)
4. [ML Sentiment System](#4-ml-sentiment-system)
5. [Risk Score Calculations](#5-risk-score-calculations)
6. [Decision Index Logic](#6-decision-index-logic)
7. [GRI (Group Risk Index)](#7-gri-group-risk-index)

---

## 1. Contradiction Policy & Adaptive Weights

### 1.1 Core Formula

**File**: `static/governance/contradiction-policy.js` (lines 74-120)

```javascript
// Input: contradiction ∈ [0, 1] (normalized from 0-100)
const c = contradiction;

// Base weights (default)
const base = { cycle: 0.4, onchain: 0.35, risk: 0.25 };

// Modulation coefficients
const cycleReduction = 0.35;    // Max -35%
const onchainReduction = 0.15;  // Max -15%
const riskIncrease = 0.50;      // Max +50%

// Apply modulation
weights = {
  cycle: base.cycle × (1 - 0.35 × c),
  onchain: base.onchain × (1 - 0.15 × c),
  risk: base.risk × (1 + 0.50 × c)
};

// Apply bounds [0.12, 0.65]
weights = {
  cycle: clamp(weights.cycle, 0.12, 0.65),
  onchain: clamp(weights.onchain, 0.12, 0.65),
  risk: clamp(weights.risk, 0.12, 0.65)
};

// Renormalize to sum = 1.0
const sum = weights.cycle + weights.onchain + weights.risk;
weights = {
  cycle: weights.cycle / sum,
  onchain: weights.onchain / sum,
  risk: weights.risk / sum
};
```

**Example (c = 0.5 / 50% contradiction):**
```
Before modulation: {cycle: 0.4, onchain: 0.35, risk: 0.25}
After modulation:  {cycle: 0.330, onchain: 0.324, risk: 0.3125}
After bounds:      {cycle: 0.330, onchain: 0.324, risk: 0.3125}
After renormalization: {cycle: 0.3415, onchain: 0.3354, risk: 0.3231}
Sum: 1.0000 ✓
```

### 1.2 Contradiction Classification

| Threshold | Level | Severity | Recommendations |
|-----------|-------|----------|-----------------|
| **≥ 70%** | HIGH | CRITICAL | Reduce risky exposure, favor stables/majors |
| **40-69%** | MEDIUM | WARNING | Maintain balanced allocation, monitor closely |
| **< 40%** | LOW | INFO | Favorable conditions, optimize allocation |

### 1.3 Risk Caps (LERP)

**Formula**: `cap = base + (min - base) × contradiction`

```javascript
// At contradiction c ∈ [0, 1]
memecoins_cap  = lerp(0.15, 0.05, c)  // 15% → 5%
small_caps_cap = lerp(0.25, 0.12, c)  // 25% → 12%
ai_data_cap    = lerp(0.20, 0.10, c)  // 20% → 10%
gaming_nft_cap = lerp(0.18, 0.08, c)  // 18% → 8%
```

**Example (c = 0.6):**
```
memecoins = 0.15 + (0.05 - 0.15) × 0.6 = 0.09 (9%)
```

### 1.4 Speed Multiplier

```javascript
speedMultiplier = max(0.5, 1 - (contradiction% / 100) × 0.5)

// Examples:
// c = 0%   → multiplier = 1.0 (full speed)
// c = 50%  → multiplier = 0.75
// c = 100% → multiplier = 0.5 (half speed)
```

### 1.5 Stability Engine Protection

**File**: `static/governance/stability-engine.js`

**Layer 1 - EMA Smoothing:**
```javascript
emaValue = 0.3 × newValue + 0.7 × previousSmoothedValue
// Alpha = 0.3 (30% weight on new value)
```

**Layer 2 - Deadband:**
```javascript
const rawDelta = newValue - lastStableValue;
const direction = abs(rawDelta) > 0.02 ? sign(rawDelta) : 0;
// Changes < 2% ignored
```

**Layer 3 - Persistence:**
```javascript
// Require 3 consecutive evaluations in same direction
if (directionBuffer.every(d => d === direction && d !== 0)) {
  // Accept change
}
```

**Staleness Gating:**
```javascript
if (age > 30 minutes) {
  // Freeze at last stable value
  stabilityState.staleness_frozen = true;
}
```

---

## 2. Phase Engine Detection Rules

**File**: `static/core/phase-engine.js`

### 2.1 Detection Hierarchy (Priority Order)

| Phase | Priority | Conditions (ALL required with AND) |
|-------|----------|-------------------------------------|
| **risk_off** | 1 (Override) | `DI < 35` |
| **full_altseason** | 2 | `bull_ctx` AND `breadth_alts ≥ 75%` AND `dispersion ≥ 75%` AND `corr_alts_btc ≤ 30%` AND `Δbtc_dom < -2%` AND `Δalts_btc > 3%` |
| **largecap_altseason** | 3 | `bull_ctx` AND `Δbtc_dom ≤ 0` AND `breadth_alts ≥ 65%` AND `dispersion ≥ 60%` AND `Δalts_btc > 1.5%` |
| **eth_expansion** | 4 | `bull_ctx` AND `Δbtc_dom < 0` AND `Δeth_btc > 2%` AND `Δeth_btc > (Δalts_btc + 1%)` |
| **neutral** | 5 (Default) | None of above |

### 2.2 Bull Context (Prerequisite)

```javascript
bull_ctx = (DI ≥ 60) || (DI ≥ 55 && breadth_alts ≥ 0.55)
```

**Required for**: eth_expansion, largecap_altseason, full_altseason

**Not required for**: risk_off (override), neutral (default)

### 2.3 Slope Calculations (14-Day Trends)

```javascript
// From 14-day historical buffer
slope = (last_value - first_value) / abs(first_value)

// Returns decimal: 0.02 = +2%, -0.03 = -3%

// Calculated for:
Δbtc_dom:    BTC dominance trend (14-day)
Δeth_btc:    ETH/BTC ratio trend (14-day)
Δalts_btc:   Altcoins/BTC ratio trend (14-day)
```

### 2.4 Partial Data Fallback

**When data incomplete (`phaseInputs.partial = true`):**

```javascript
if (DI < 35)
  return 'risk_off';
else if (DI ≥ 70 && breadth_alts ≥ 0.7)
  return 'largecap_altseason';
else if (DI ≥ 60 && breadth_alts ≥ 0.55)
  return 'eth_expansion';
else
  return 'neutral';
```

### 2.5 Hysteresis (Consensus)

```javascript
// Memory: Last 5 evaluations
// Require 3/5 same phase for change (2/5 in debug mode)

if (consensusStrength ≥ 3) {
  return currentConsensus;
} else {
  return phaseMemory.lastPhase;  // Stick with last known
}

// Emergency exits (immediate, no hysteresis):
if (DI < 35) return 'risk_off';
if (DI < 45) return 'neutral';
```

### 2.6 Buffer Persistence

**File**: `static/core/phase-buffers.js`

```javascript
// Ring Buffer Configuration
maxSize: 60 samples
TTL: 7 days (604,800,000 ms)
Storage: localStorage key 'phase_buffers_v1'

// Managed Time Series
Keys: ['btc_dom', 'eth_btc', 'alts_btc']

// Sample Format
{t: timestamp, v: value}
```

---

## 3. Structure Scores (V2 vs Legacy)

### 3.1 Portfolio Structure Score V2 (Pure)

**File**: `services/risk/structural_score_v2.py`

```python
# Base Score
base = 100.0

# Penalty Calculations
penalty_hhi = max(0, (hhi - 0.25) × 100)
penalty_memecoins = memecoins_pct × 40.0
penalty_gri = gri × 5.0
penalty_low_div = 10.0 if effective_assets < 5 else 0.0

# Final Score
total_penalties = penalty_hhi + penalty_memecoins + penalty_gri + penalty_low_div
final_score = clamp(100 - total_penalties, 0, 100)
```

**Example (Balanced Portfolio):**
```
Base:           100.0
HHI (0.18):     -0.0   (0.18 < 0.25 threshold)
Memecoins (0%): -0.0
GRI (3.2):      -16.0  (3.2 × 5.0)
Low Div (eff=7): -0.0
─────────────────────
Final:          84.0
```

### 3.2 Integrated Structural Legacy

**File**: `services/risk_scoring.py` / `api/risk_endpoints.py` lines 96-214

```python
# Base Score
base = 50.0

# Delta Components
d_var = {
  var95 < 0.04:  -5.0,
  var95 ≤ 0.08:   0.0,
  var95 > 0.08:  +5.0
}

d_cvar = {
  cvar95 < 0.06:  -3.0,
  cvar95 ≤ 0.12:   0.0,
  cvar95 > 0.12:  +3.0
}

d_dd = {
  |dd| < 0.15:  -10.0,  # Low DD = boring (no gains)
  |dd| ≤ 0.30:    0.0,
  |dd| ≤ 0.50:  +10.0,
  |dd| > 0.50:  +20.0
}

d_vol = {
  vol < 0.20:  +10.0,
  vol < 0.30:   +5.0,
  vol ≤ 0.60:    0.0,
  vol ≤ 1.0:    -5.0,
  vol > 1.0:   -10.0
}

d_perf = {
  sharpe/sortino < 0:    -15.0,
  < 0.5: -10.0,
  ≤ 1.0:   0.0,
  ≤ 1.5:  +5.0,
  ≤ 2.0: +10.0,
  > 2.0: +15.0
}

d_stables = {
  stables ≥ 20%: -5.0,
  stables ≥ 10%: -2.0,
  stables < 5%:  +3.0,
  else: 0.0
}

d_conc = {
  top5 > 80%: +5.0,
  hhi > 20%:  +3.0,
  else: 0.0
}

d_div = {
  div_ratio > 0.7:  0.0,
  div_ratio ≥ 0.4: +3.0,
  else: +6.0
}

d_gri = clamp((gri - 4.0) × 2.0, 0.0, 10.0)

# Final Score
score = base + d_var + d_cvar + d_dd + d_vol + d_perf + d_stables + d_conc + d_div + d_gri
final = clamp(score, 0, 100)
```

### 3.3 HHI (Herfindahl-Hirschman Index)

```python
weights = [value_asset_i / total_value for each asset]
hhi = sum(w_i² for all weights)

# Range: [0, 1]
# 0 = perfect diversification
# 1 = complete concentration
# 0.25 = 4 equal-weight assets

# Thresholds in Penalties
hhi ≤ 0.25: No penalty (acceptable)
0.25 < hhi ≤ 0.40: Moderate penalty
hhi > 0.40: High penalty
```

---

## 4. ML Sentiment System

### 4.1 Aggregation Formula

**File**: `services/ml/models/sentiment_analyzer.py`

```python
# Multi-source aggregation
sentiment_ml = (
  0.25 × fear_greed_sentiment +    # Alternative.me mapped
  0.35 × social_media_sentiment +  # Twitter/Reddit
  0.40 × news_sentiment            # News analysis
)

# Range: sentiment_ml ∈ [-1.0, +1.0]

# Convert to 0-100 scale
fear_greed_value = 50 + (sentiment_ml × 50)

# Examples:
# sentiment_ml =  0.6 → fear_greed_value = 80 (Extreme Greed)
# sentiment_ml = -0.4 → fear_greed_value = 30 (Fear)
# sentiment_ml =  0.0 → fear_greed_value = 50 (Neutral)
```

### 4.2 Fear & Greed Index Mapping

**From alternative.me API (0-100) to sentiment score (-1 to +1):**

```python
if fg_value ≤ 25:
    sentiment = -0.8 + (fg_value / 25) × 0.4        # -0.8 to -0.4
elif fg_value ≤ 45:
    sentiment = -0.4 + ((fg_value - 25) / 20) × 0.3 # -0.4 to -0.1
elif fg_value ≤ 55:
    sentiment = -0.1 + ((fg_value - 45) / 10) × 0.2 # -0.1 to +0.1
elif fg_value ≤ 75:
    sentiment = 0.1 + ((fg_value - 55) / 20) × 0.3  # +0.1 to +0.4
else:
    sentiment = 0.4 + ((fg_value - 75) / 25) × 0.4  # +0.4 to +0.8
```

### 4.3 Usage in 3-Level Hierarchy

**File**: `static/core/unified-insights-v2.js` (lines 206-268)

```javascript
const mlSentiment = ctx?.sentiment_value || 50;
const extremeFear = mlSentiment < 25;
const extremeGreed = mlSentiment > 75;

// LEVEL 1 (Absolute Priority) - Extreme Sentiments
if (extremeFear && bullContext) {
  // Opportunistic: ETH ×1.15, SOL ×1.20, L2 ×1.20, DeFi ×1.10
}
else if (extremeFear && bearContext) {
  // Defensive: Memecoins ×0.3, DeFi ×0.7, Gaming ×0.5
}

if (extremeGreed) {
  // Always take profits: Memecoins ×0.3, Gaming ×0.5, AI ×0.7, DeFi ×0.8
}

// LEVEL 2 - Phase Engine (if Level 1 not active)
// LEVEL 3 - Base Modulators (if both inactive)
```

---

## 5. Risk Score Calculations

### 5.1 Risk Score (Performance-Based)

**See**: [RISK_SEMANTICS.md](RISK_SEMANTICS.md) for complete details

**Key Formula (Integrated Legacy):**
```python
score = 50.0  # Neutral baseline
score += var_impact + cvar_impact + dd_impact + vol_impact
score += sharpe_impact + stables_impact + concentration_impact
score += diversification_impact + gri_impact
final = clamp(score, 0, 100)
```

**Semantic Rule**: Higher score = More robust (NEVER invert with `100 - score`)

### 5.2 Dual-Window Blend

**File**: `services/portfolio_metrics.py` (line 169)

```python
# Mode 1: full_intersection_only
w_full = 1.0
w_long = 0.0
risk_score = risk_score_full

# Mode 2: blend (when long-term available)
w_full = dynamic weight (e.g., 0.62)
w_long = 1 - w_full (e.g., 0.38)
risk_score = (risk_score_full × w_full) + (risk_score_long × w_long)

# Example:
# full = 57, long = 77, w_full = 0.62
# blended = (57 × 0.62) + (77 × 0.38) = 64.57
```

**Activation Criteria:**
- Coverage ≥ 80% in long-term window
- Data points ≥ 180 days
- Asset count ≥ 5

---

## 6. Decision Index Logic

**File**: `static/core/strategy-api-adapter.js` (line 448)

### 6.1 Binary Score

```javascript
const decisionScore = v2Allocation.metadata.total_check.isValid ? 65 : 45;
```

**Rule:**
- **65** = Allocation valid (sum = 100% ± 0.1%)
- **45** = Allocation invalid (constraint violated)

### 6.2 Validation Check

**File**: `static/core/allocation-engine.js` (lines 607-620)

```javascript
function validateTotalAllocation(allocation) {
  const validValues = Object.values(allocation).filter(val =>
    val !== null && val !== undefined && !isNaN(val) && typeof val === 'number'
  );
  const total = validValues.reduce((sum, val) => sum + val, 0);

  // Tolerance: 0.1% (0.001 in decimal)
  const isValid = abs(total - 1) < 0.001;

  return { total, isValid };
}
```

---

## 7. GRI (Group Risk Index)

### 7.1 Formula

```python
GRI = sum(exposure_by_group[g] × risk_level[g] for all groups)
# Clamped to [0, 10]
```

### 7.2 Group Risk Levels (Canonical)

```python
GROUP_RISK_LEVELS = {
    'Stablecoins': 0,
    'BTC': 2,
    'ETH': 3,
    'L2/Scaling': 5,
    'DeFi': 5,
    'AI/Data': 5,
    'SOL': 6,
    'L1/L0 majors': 6,
    'Gaming/NFT': 6,
    'Others': 7,
    'Memecoins': 9
}
```

### 7.3 Examples

```
Portfolio: 40% BTC + 30% ETH + 30% USDC
GRI = (0.40 × 2) + (0.30 × 3) + (0.30 × 0)
    = 0.8 + 0.9 + 0
    = 1.7 (very safe)

Portfolio: 50% Memecoins + 50% Altcoins
GRI = (0.50 × 9) + (0.50 × 7)
    = 4.5 + 3.5
    = 8.0 (very risky)
```

### 7.4 GRI Contribution to Scores

**V2 Pure Structural:**
```python
penalty_gri = gri × 5.0
```

**Integrated Legacy:**
```python
d_gri = clamp((gri - 4.0) × 2.0, 0.0, 10.0)
```

---

## 📚 References

### Related Documentation
- [DECISION_INDEX_V2.md](DECISION_INDEX_V2.md) - Decision Index vs Regime Score
- [RISK_SEMANTICS.md](RISK_SEMANTICS.md) - Risk Score semantics and formulas
- [PHASE_ENGINE.md](PHASE_ENGINE.md) - Phase detection system
- [contradiction-system.md](contradiction-system.md) - Contradiction detection

### Source Code Files
- `static/governance/contradiction-policy.js` - Adaptive weights
- `static/governance/stability-engine.js` - Hysteresis protection
- `static/core/phase-engine.js` - Phase detection
- `static/core/phase-buffers.js` - Time series persistence
- `static/core/allocation-engine.js` - Allocation validation
- `static/core/strategy-api-adapter.js` - Decision Index calculation
- `static/core/unified-insights-v2.js` - ML Sentiment hierarchy
- `services/risk/structural_score_v2.py` - Structure Score V2
- `services/risk_scoring.py` - Integrated Structural Legacy
- `services/ml/models/sentiment_analyzer.py` - ML Sentiment aggregation

---

*Last Updated: 2025-10-22*
*Document Status: Complete Technical Reference*
