/**
 * Test Risk Semantics Modes - Validate legacy vs v2_conservative vs v2_aggressive
 *
 * Simule les 3 modes avec portfolios de référence:
 * - Degen: Risk=30 (fragile) → devrait avoir PLUS de stables avec v2
 * - Ultra-safe: Risk=90 (robuste) → devrait avoir MOINS de stables avec v2
 */

// Simulate calculateRiskBudget logic
function calculateStablesTarget(blended, risk, mode = 'legacy') {
  const blendedRounded = Math.round(blended);
  const riskRounded = Math.round(risk);

  let risk_factor;

  if (mode === 'legacy') {
    // LEGACY (inversé)
    risk_factor = 1 - 0.5 * (riskRounded / 100);
  } else if (mode === 'v2_conservative') {
    // V2 CONSERVATIVE
    risk_factor = 0.5 + 0.5 * (riskRounded / 100);
  } else if (mode === 'v2_aggressive') {
    // V2 AGGRESSIVE
    risk_factor = 0.4 + 0.7 * (riskRounded / 100);
  } else {
    throw new Error('Unknown mode: ' + mode);
  }

  const baseRisky = Math.max(0, Math.min(1, (blendedRounded - 35) / 45));
  const riskyAllocation = Math.max(0.20, Math.min(0.85, baseRisky * risk_factor));
  const stablesPct = 100 - Math.round(riskyAllocation * 100);

  return {
    risk_factor,
    baseRisky,
    riskyAllocation,
    stablesPct,
    mode
  };
}

// Test scenarios
const scenarios = [
  {
    name: 'Degen Portfolio (Risk=30, fragile)',
    blended: 57,  // Decision Index actuel High Risk
    risk: 30,     // Après Dual-Window fix (était 60)
    expected_behavior: 'Plus de stables avec v2 (protéger portfolio fragile)'
  },
  {
    name: 'Medium Risk (Risk=50)',
    blended: 57,
    risk: 50,
    expected_behavior: 'Stables modérés (~50-60%)'
  },
  {
    name: 'Conservative (Risk=80, robuste)',
    blended: 57,
    risk: 80,
    expected_behavior: 'Moins de stables avec v2 (autoriser plus de risky)'
  },
  {
    name: 'Ultra-Safe (Risk=90, très robuste)',
    blended: 57,
    risk: 90,
    expected_behavior: 'Stables minimaux avec v2 (confiance portfolio)'
  }
];

console.log('='.repeat(80));
console.log('RISK SEMANTICS MODES COMPARISON');
console.log('='.repeat(80));
console.log('');

scenarios.forEach(scenario => {
  console.log(scenario.name + ':');
  console.log('  Blended=' + scenario.blended + ', Risk=' + scenario.risk);
  console.log('  Expected: ' + scenario.expected_behavior);
  console.log('');

  const legacy = calculateStablesTarget(scenario.blended, scenario.risk, 'legacy');
  const v2_cons = calculateStablesTarget(scenario.blended, scenario.risk, 'v2_conservative');
  const v2_aggr = calculateStablesTarget(scenario.blended, scenario.risk, 'v2_aggressive');

  console.log('  Mode            | risk_factor | Risky% | Stables%');
  console.log('  ' + '-'.repeat(56));
  console.log('  Legacy          | ' + legacy.risk_factor.toFixed(3) + '       | ' + (Math.round(legacy.riskyAllocation * 100)) + '%    | ' + legacy.stablesPct + '%');
  console.log('  v2_conservative | ' + v2_cons.risk_factor.toFixed(3) + '       | ' + (Math.round(v2_cons.riskyAllocation * 100)) + '%    | ' + v2_cons.stablesPct + '%');
  console.log('  v2_aggressive   | ' + v2_aggr.risk_factor.toFixed(3) + '       | ' + (Math.round(v2_aggr.riskyAllocation * 100)) + '%    | ' + v2_aggr.stablesPct + '%');

  // Validate monotonicity
  const delta_legacy_vs_v2cons = v2_cons.stablesPct - legacy.stablesPct;
  const direction = delta_legacy_vs_v2cons > 0 ? 'UP' : (delta_legacy_vs_v2cons < 0 ? 'DOWN' : 'SAME');

  console.log('');
  console.log('  Change legacy→v2_conservative: ' + (delta_legacy_vs_v2cons >= 0 ? '+' : '') + delta_legacy_vs_v2cons + '% stables (' + direction + ')');
  console.log('');
});

console.log('='.repeat(80));
console.log('VALIDATION RULES:');
console.log('1. Fragile portfolios (Risk<50): v2 should have MORE stables than legacy');
console.log('2. Robust portfolios (Risk>70): v2 should have LESS stables than legacy');
console.log('3. v2_aggressive should amplify differences vs v2_conservative');
console.log('='.repeat(80));
console.log('');

// Validation checks
console.log('VALIDATION CHECKS:');
console.log('');

const degen_legacy = calculateStablesTarget(57, 30, 'legacy');
const degen_v2 = calculateStablesTarget(57, 30, 'v2_conservative');

const safe_legacy = calculateStablesTarget(57, 90, 'legacy');
const safe_v2 = calculateStablesTarget(57, 90, 'v2_conservative');

const check1 = degen_v2.stablesPct > degen_legacy.stablesPct;
const check2 = safe_v2.stablesPct < safe_legacy.stablesPct;

console.log('[' + (check1 ? 'PASS' : 'FAIL') + '] Degen (Risk=30): v2 stables (' + degen_v2.stablesPct + '%) > legacy (' + degen_legacy.stablesPct + '%)');
console.log('[' + (check2 ? 'PASS' : 'FAIL') + '] Ultra-safe (Risk=90): v2 stables (' + safe_v2.stablesPct + '%) < legacy (' + safe_legacy.stablesPct + '%)');
console.log('');

if (check1 && check2) {
  console.log('[OK] All validation checks passed!');
} else {
  console.log('[ERROR] Some validation checks FAILED - formula may still be inverted!');
}
