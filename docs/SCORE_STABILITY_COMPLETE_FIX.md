# Score Stability - Complete Fix (Oct 2, 2025)

**Status:** ✅ **RESOLVED** - All scores and recommendations now stable across refreshes

## Executive Summary

Fixed critical instability issues affecting OnChain scores, Risk scores, and recommendations that were varying between page refreshes. Root causes included:
1. V1/V2 calculation divergence (OnChain: 36 vs 42)
2. Race condition overwriting orchestrator values (Risk: 37 vs 50)
3. Missing ccsStar storage causing blended score variation
4. Incorrect blended score formula (blendedCCS vs true blended)

## Problems Identified

### 1. OnChain Score Inconsistency (36 vs 42)

**Symptom:**
- risk-dashboard.html Market Cycles tab: OnChain = 36
- analytics-unified.html: OnChain = 42
- Score changed when navigating between pages

**Root Cause:**
- Orchestrator used V1 `calculateCompositeScore()` → 42
- Market Cycles tab used V2 `calculateCompositeScoreV2()` → 36
- Different calculation methods, different results

**Fix (Commit `74ef1ce`):**
- Migrated orchestrator to V2
- Removed V1 function entirely (132 lines)
- Forced dynamic weighting ON everywhere
- Removed "Adaptation contextuelle" checkbox (obsolete)

**Files Modified:**
- `static/core/risk-data-orchestrator.js` - Import V2, force dynamic weighting
- `static/modules/onchain-indicators.js` - Remove V1 calculateCompositeScore()
- `static/risk-dashboard.html` - Remove checkbox, force V2
- `static/analytics-unified.html` - Force V2, add hard refresh detection
- `static/simulations.html` - Force V2

### 2. Risk Score Hard Refresh Instability (37 vs 50)

**Symptom:**
- Hard refresh (Ctrl+Shift+R): Risk = 37
- Normal refresh (F5): Risk = 50

**Root Cause:**
- Orchestrator hydrated store with Risk = 50 ✅
- `loadUnifiedData()` in analytics-unified.html then fetched from cache/API
- Cache had stale value (37) which overwrote correct value (50) ❌

**Fix (Commit `74ef1ce`):**
```javascript
// BEFORE: analytics-unified.html fetched Risk from API/cache
const riskData = await apiRequest('/api/risk/dashboard');
store.set('scores.risk', riskData.risk_score); // ❌ Overwrites orchestrator

// AFTER: Read from orchestrator-hydrated store
const existingRiskScore = store.get('scores.risk'); // ✅ Already correct
if (typeof existingRiskScore === 'number') {
  console.log(`✅ Risk score already hydrated by orchestrator: ${existingRiskScore}`);
}
```

**Result:** Risk = 50 everywhere, even on hard refresh ✅

### 3. Recommendations Instability (40% vs 67% stables)

**Symptom:**
- Refresh 1: "Euphorie détectée" → Stablecoins 40%
- Refresh 2: "Expansion en cours" → Stablecoins 67%
- Recommendations varied randomly

**Root Cause Chain:**

#### Issue 3A: Missing ccsStar (Commit `9c5e138`)

```javascript
// Orchestrator calculated blendedCCS but didn't store it
const blendResult = blendCCS(ccs.score, cycle.months);
const blendedScore = blendResult?.blendedCCS ?? null; // Calculated
// But: cycle.ccsStar = null ❌

// analytics-unified.html fallback behavior
const ccsMixteScore = s.cycle?.ccsStar ?? s.cycle?.score ?? 50;
//                    ↑ undefined    ↑ fallback to ~100 (sigmoid)
```

**Consequence:** ccsMixteScore unstable → blendedScore unstable

**Fix:**
```javascript
cycle: cycle ? {
  ...cycle,
  ccsStar: blendedScore // ✅ Store blendedCCS
} : { ... }
```

#### Issue 3B: Incorrect Blended Score Formula (Commit `d54791d`)

**Root Cause:** Orchestrator stored `blendedCCS` as final `blendedScore`

```javascript
// WRONG: blendedCCS is NOT the final blended score
blendedScore = blendCCS(ccs, cycle) // This is just CCS×Cycle
store.set('scores.blended', blendedScore) // ❌ Incomplete formula
```

**Correct Formula (docs/RISK_SEMANTICS.md):**
```
blendedScore = 0.5*ccsStar + 0.3*onchain + 0.2*risk
```

**Fix:**
```javascript
// Step 1: Calculate ccsStar (CCS blended with Cycle)
let ccsStar = null;
if (ccs && cycle) {
  const blendResult = blendCCS(ccs.score, cycle.months || 18);
  ccsStar = blendResult?.blendedCCS ?? null;
}

// Step 2: Calculate final blended score
let blendedScore = null;
if (ccsStar !== null || onchainScore !== null || riskScore !== null) {
  const wCCS = 0.50;
  const wOnchain = 0.30;
  const wRisk = 0.20;

  let totalScore = 0;
  let totalWeight = 0;

  if (ccsStar !== null) {
    totalScore += ccsStar * wCCS;
    totalWeight += wCCS;
  }
  if (onchainScore !== null) {
    totalScore += onchainScore * wOnchain;
    totalWeight += wOnchain;
  }
  if (riskScore !== null) {
    totalScore += riskScore * wRisk;
    totalWeight += wRisk;
  }

  blendedScore = totalWeight > 0 ? Math.round(totalScore / totalWeight) : null;
}

// Step 3: Store both correctly
cycle.ccsStar = ccsStar;           // CCS×Cycle
scores.blended = blendedScore;      // Final blended (0.5*ccsStar + 0.3*onchain + 0.2*risk)
```

**Impact of Fix:**

Before: `blendedScore` varied → regime flipped between Expansion (≤69) and Euphoria (≥70)
- Expansion [40-69]: 67% stables
- Euphoria [70-84]: 40% stables (+10% divergence)

After: `blendedScore` stable → regime stable → recommendations stable ✅

## Final Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              risk-data-orchestrator.js (SSOT)               │
│                                                             │
│  1. Fetch: CCS, Cycle, OnChain indicators, Risk data       │
│                                                             │
│  2. Calculate scores:                                       │
│     ccsStar = blendCCS(ccs.score, cycle.months)            │
│     onchainScore = calculateCompositeScoreV2(indicators, true) │
│     riskScore = from API /api/risk/dashboard               │
│                                                             │
│  3. Calculate final blended:                                │
│     blendedScore = 0.5*ccsStar + 0.3*onchain + 0.2*risk    │
│                                                             │
│  4. Calculate regime:                                       │
│     regime = getMarketRegime(blendedScore)                 │
│                                                             │
│  5. Store in riskStore:                                     │
│     cycle.ccsStar = ccsStar                                │
│     scores.onchain = onchainScore                          │
│     scores.risk = riskScore                                │
│     scores.blended = blendedScore                          │
│     regime = regime                                        │
│                                                             │
│  6. Emit riskStoreReady event                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ All pages read from store
                          ▼
        ┌──────────────────────────────────────┐
        │  Consumer Pages (read-only)          │
        ├──────────────────────────────────────┤
        │  • analytics-unified.html            │
        │  • risk-dashboard.html               │
        │  • simulations.html                  │
        │  • rebalance.html                    │
        │                                      │
        │  const score = store.get('scores.*') │
        │  ✅ No recalculation                 │
        │  ✅ No cache race conditions         │
        └──────────────────────────────────────┘
```

## Verification Results

### Test 1: OnChain Score Stability
```bash
# Before: 42 (orchestrator V1) vs 36 (Market Cycles V2)
# After:  36 everywhere (V2 with dynamic weighting)
✅ PASS
```

### Test 2: Risk Score Hard Refresh
```bash
# Before: Ctrl+Shift+R → Risk = 37 (stale cache)
# After:  Ctrl+Shift+R → Risk = 50 (orchestrator)
✅ PASS
```

### Test 3: Recommendations Stability (3 consecutive refreshes)
```
Refresh 1:
- 🎯 Allocation Stablecoins: 67%
- 💡 Budget risque élevé détecté: 67%
- 💡 Expansion en cours
- 🛡️ Allocation stables: 67%

Refresh 2: IDENTICAL ✅

Refresh 3: IDENTICAL ✅
```

### Final Score Table

| Score | Value | Source | Stability |
|-------|-------|--------|-----------|
| **OnChain** | 36 | V2 (dynamic weights) | ✅ Stable |
| **Risk** | 50 | Orchestrator → API | ✅ Stable (even hard refresh) |
| **CCS Mixte (ccsStar)** | Variable | blendCCS(ccs, cycle) | ✅ Stable |
| **Blended** | Variable | 0.5*ccsStar + 0.3*onchain + 0.2*risk | ✅ Stable |
| **Regime** | Expansion | Based on blendedScore | ✅ Stable |

## Commits Timeline

1. **`74ef1ce`** - feat(scores): migrate OnChain score from V1 to V2 with unified architecture
   - Migration V1 → V2
   - Fix Risk Score race condition
   - Remove obsolete checkbox
   - +2255 lines, -673 lines

2. **`9c5e138`** - fix(recommendations): stabilize blended score calculation via ccsStar
   - Store blendedCCS in cycle.ccsStar
   - Prevent fallback to cycle.score

3. **`d54791d`** - fix(blended-score): calculate true blended score in orchestrator
   - Separate ccsStar (CCS×Cycle) from blendedScore (final formula)
   - Implement canonical formula: 0.5*ccsStar + 0.3*onchain + 0.2*risk

## Documentation

- **Migration Guide:** [docs/ONCHAIN_SCORE_V2_MIGRATION.md](ONCHAIN_SCORE_V2_MIGRATION.md)
- **Risk Semantics:** [docs/RISK_SEMANTICS.md](RISK_SEMANTICS.md)
- **Score Consistency:** [docs/SCORE_CONSISTENCY_FIX.md](SCORE_CONSISTENCY_FIX.md)
- **Cache Fix:** [docs/SCORE_CACHE_HARD_REFRESH_FIX.md](SCORE_CACHE_HARD_REFRESH_FIX.md)
- **This Document:** [docs/SCORE_STABILITY_COMPLETE_FIX.md](SCORE_STABILITY_COMPLETE_FIX.md)

## Known Remaining Issue (Low Priority)

**Duplicate Recommendations:** 67% stables appears 3 times
- 🎯 Strategy source (V2 engine)
- 💡 Regime source (Market regime)
- 🛡️ Risk source (Risk budget)

**Status:** Cosmetic only - values are consistent
**Fix Required:** Enhance deduplication in unified-insights-v2.js to detect semantic duplicates

## Success Criteria ✅

- [x] OnChain score consistent across all pages (36)
- [x] Risk score stable on hard refresh (50)
- [x] Recommendations identical across refreshes
- [x] No V1 calculation references remaining
- [x] Blended score uses correct formula
- [x] ccsStar properly stored and used
- [x] All tests passing
- [x] Documentation updated

**Status: COMPLETE** 🎉
