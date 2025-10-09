/**
 * Debug script pour tracer le flow complet regime → risk_budget → targets
 */

// Simulate les scores des 3 portfolios
const scenarios = [
  { name: 'High Risk',   blended: 55, risk: 40, structural: 62, observed_stables: 68 },
  { name: 'Medium Risk', blended: 55, risk: 85, structural: 75, observed_stables: 65 },
  { name: 'Low Risk',    blended: 55, risk: 70, structural: 65, observed_stables: 65 }
];

console.log('='.repeat(80));
console.log('REGIME FLOW DEBUG - Full Pipeline Trace');
console.log('='.repeat(80));
console.log('');

// Reproduire calculateRiskBudget logic
function calculateRiskBudget(blendedScore, riskScore) {
  const blendedRounded = Math.round(blendedScore);
  const riskRounded = Math.round(riskScore);

  const riskCap = riskRounded != null ? 1 - 0.5 * (riskRounded / 100) : 0.75;
  const baseRisky = Math.max(0, Math.min(1, (blendedRounded - 35) / 45));
  const riskyAllocation = Math.max(0.20, Math.min(0.85, baseRisky * riskCap));
  const stablesAllocation = 1 - riskyAllocation;

  const riskyPct = Math.round(riskyAllocation * 100);
  const stablesPct = 100 - riskyPct;

  return {
    risk_cap: riskCap,
    base_risky: baseRisky,
    risky_allocation: riskyAllocation,
    stables_allocation: stablesAllocation,
    percentages: { risky: riskyPct, stables: stablesPct },
    target_stables_pct: stablesPct,
    generated_at: new Date().toISOString()
  };
}

scenarios.forEach(scenario => {
  console.log(scenario.name + ':');
  console.log('  Input: Blended=' + scenario.blended + ', Risk=' + scenario.risk);

  const riskBudget = calculateRiskBudget(scenario.blended, scenario.risk);

  console.log('  calculateRiskBudget() output:');
  console.log('    - target_stables_pct: ' + riskBudget.target_stables_pct + '%');
  console.log('    - risk_cap: ' + riskBudget.risk_cap.toFixed(3));
  console.log('    - base_risky: ' + riskBudget.base_risky.toFixed(3));

  const delta = riskBudget.target_stables_pct - scenario.observed_stables;
  const match = Math.abs(delta) < 1 ? '✅' : '❌';

  console.log('  Comparison:');
  console.log('    - Calculated: ' + riskBudget.target_stables_pct + '%');
  console.log('    - Observed: ' + scenario.observed_stables + '%');
  console.log('    - Delta: ' + delta + '% ' + match);
  console.log('');
});

console.log('='.repeat(80));
console.log('HYPOTHESIS:');
console.log('If deltas persist, investigate:');
console.log('1. Cache invalidation issue (5min TTL in market-regimes.js:274-278)');
console.log('2. Backend override (unlikely - no Python code found)');
console.log('3. Fallback to regimeData.risk_budget.percentages.stables (line 442)');
console.log('4. Store injection overriding calculated values');
console.log('='.repeat(80));
