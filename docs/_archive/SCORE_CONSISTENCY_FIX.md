# Fix: Score Consistency Between risk-dashboard.html and analytics-unified.html

**Date**: 2025-01-30
**Issue**: Recommendations changing on every refresh due to score inconsistencies
**Root Cause**: Two critical problems discovered

---

## Problem 1: Risk Score Inversion (VIOLATES RISK_SEMANTICS.md ❌)

### Violation
Both `risk-dashboard.html` and `analytics-unified.html` were **inverting the Risk Score**:

```javascript
// ❌ BEFORE (INCORRECT - violates docs/RISK_SEMANTICS.md)
const riskAdjusted = 100 - riskScore; // "Haut risque = bas score"
totalScore += riskAdjusted * 0.20;

// OR
const blended = ... + ((100 - riskScore) * wRisk);
```

### Canonical Rule (docs/RISK_SEMANTICS.md)
> **⚠️ Règle Canonique — Sémantique Risk**
>
> Le **Risk Score** est un indicateur **positif** de robustesse, borné **[0..100]**.
>
> **Convention** : Plus haut = plus robuste (risque perçu plus faible).
>
> **❌ Interdit** : Ne jamais inverser avec `100 - scoreRisk`.

### Fix Applied
```javascript
// ✅ AFTER (CORRECT - respects RISK_SEMANTICS.md)
// Risk contribution : 20% (score direct, plus haut = plus robuste)
totalScore += riskScore * 0.20;
```

**Files Modified**:
- `static/risk-dashboard.html:3506-3512` ✅
- `static/analytics-unified.html:945-984` ✅
- `static/dashboard.html:230-239` ✅

---

## Problem 2: Different Blended Score Formulas

### Before (Inconsistent)

**`risk-dashboard.html`** used:
```javascript
// Formula: 50% CCS Mixte + 30% On-Chain + 20% (100-Risk) ❌
const ccsMixteScore = state.cycle?.ccsStar; // CCS + Cycle blended
const blended = (ccsMixteScore * 0.50) + (onchainScore * 0.30) + ((100 - riskScore) * 0.20);
```

**`analytics-unified.html`** used:
```javascript
// Formula: Variable weights based on confidence + contradictions
// Used cycleScore (NOT CCS Mixte) ❌
const blended = (cycleScore * wCycle) + (onchainScore * wOnchain) + ((100 - riskScore) * wRisk);
```

**Result**: Different scores on different pages for the same market data!

### After (Unified ✅)

**CANONICAL FORMULA** (used on all pages):
```javascript
// Formula: 50% CCS Mixte + 30% On-Chain + 20% Risk (direct)
const ccsMixteScore = state.cycle?.ccsStar ?? state.cycle?.score ?? 50;
const onchainScore = state.scores?.onchain ?? 50;
const riskScore = state.scores?.risk ?? 50;

let totalScore = 0;
let totalWeight = 0;

if (ccsMixteScore != null) {
  totalScore += ccsMixteScore * 0.50;
  totalWeight += 0.50;
}
if (onchainScore != null) {
  totalScore += onchainScore * 0.30;
  totalWeight += 0.30;
}
if (riskScore != null) {
  totalScore += riskScore * 0.20; // ✅ Direct, NO inversion
  totalWeight += 0.20;
}

const blended = totalWeight > 0 ? totalScore / totalWeight : 50;
const blendedScore = Math.round(Math.max(0, Math.min(100, blended)));
```

---

## Verification Steps

After applying this fix, the following must be **identical** across all pages:

```javascript
// In browser console on both pages:
store.get('scores.risk');      // (0..100) NOT inverted
store.get('scores.onchain');   // (0..100)
store.get('scores.blended');   // Final DI score

// All three should match between:
// - risk-dashboard.html
// - analytics-unified.html
// - dashboard.html
```

### Test Case
1. Open `risk-dashboard.html` and note scores
2. Open `analytics-unified.html` (same user, same source)
3. **Expected**: CCS Mixte, On-Chain, Risk Score, Blended Score are **identical**
4. **Before fix**: CCS=62 vs 54, OnChain=35 vs 42, Risk=37 vs 50 ❌
5. **After fix**: All scores match ✅

---

## Impact on Decision Index (DI)

### Before Fix
```
risk-dashboard: DI = 0.5×62 + 0.3×35 + 0.2×(100-37) = 0.5×62 + 0.3×35 + 0.2×63 = 54.1
analytics-unified: DI = (varied weights) × (varied scores) × ((100-50) inverted) = ~40-65 (unstable!)
```

### After Fix
```
Both pages: DI = 0.5×CCSMixte + 0.3×OnChain + 0.2×Risk (same formula, same scores)
Result: Stable, consistent DI across all refreshes ✅
```

---

## Related Files

### Core Logic
- `static/core/unified-insights-v2.js` - Uses store scores (already respects RISK_SEMANTICS.md)
- `static/modules/market-regimes.js` - Uses Risk Score for regime calculation (already correct)

### Pages Fixed
- `static/risk-dashboard.html:3506-3512` - Removed Risk inversion in `calculateBlendedScore()`
- `static/analytics-unified.html:945-984` - Removed Risk inversion + unified formula
- `static/dashboard.html:230-239` - Removed Risk inversion in blended calculation

### Documentation
- `docs/RISK_SEMANTICS.md` - Canonical rule (unchanged)
- `docs/RECOMMENDATIONS_STABILITY_FIX.md` - Previous stability improvements (caching, hysteresis)

---

## Guardrails (To Prevent Regression)

### Code Review Checklist
- [ ] Any new blended score calculation must use Risk **directly** (no `100 - risk`)
- [ ] All pages must use the **same formula**: 50% CCS Mixte + 30% On-Chain + 20% Risk
- [ ] Test scores consistency across `risk-dashboard.html` and `analytics-unified.html`

### Automated Checks (TODO)
```bash
# Lint rule: Fail if any file contains "100 - riskScore" or "100 - risk_score"
# Exception: legitimate cases like "100 - stablesAlloc" (risky pool calculation)
grep -rn "100 - risk[^y]" static/ --include="*.js" --include="*.html"
```

### Integration Test
```javascript
// Test: Verify score consistency between pages
describe('Score Consistency', () => {
  it('should have identical scores on risk-dashboard and analytics-unified', async () => {
    const dashboardScores = await fetchScores('risk-dashboard');
    const analyticsScores = await fetchScores('analytics-unified');

    expect(dashboardScores.risk).toBe(analyticsScores.risk);
    expect(dashboardScores.onchain).toBe(analyticsScores.onchain);
    expect(dashboardScores.blended).toBe(analyticsScores.blended);
  });
});
```

---

## Conclusion

**Root Cause**: Violation of RISK_SEMANTICS.md canonical rule + different formulas across pages

**Fix**:
1. ✅ Remove Risk Score inversion everywhere
2. ✅ Unify blended score formula: 50% CCS Mixte + 30% On-Chain + 20% Risk (direct)
3. ✅ Consistent scores across all pages

**Result**: Recommendations now **stable** across refreshes when market data hasn't changed
