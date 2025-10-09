/**
 * Debug script pour tracer le calcul target_stables_pct
 * Simule la formule de market-regimes.js avec les données benchmark
 */

// Formule exacte de market-regimes.js:234-248
function calculateStablesFormula(blendedScore, riskScore) {
  const blendedRounded = Math.round(blendedScore);
  const riskRounded = Math.round(riskScore || 0);

  // RiskCap = 1 - 0.5 × (RiskScore/100)
  const riskCap = riskRounded != null ? 1 - 0.5 * (riskRounded / 100) : 0.75;

  // BaseRisky = clamp((Blended - 35)/45, 0, 1)
  const baseRisky = Math.max(0, Math.min(1, (blendedRounded - 35) / 45));

  // Risky = clamp(BaseRisky × RiskCap, 20%, 85%)
  const riskyAllocation = Math.max(0.20, Math.min(0.85, baseRisky * riskCap));

  // Stables = 1 - Risky
  const stablesAllocation = 1 - riskyAllocation;

  // Arrondi
  const riskyPct = Math.round(riskyAllocation * 100);
  const stablesPct = 100 - riskyPct;

  return {
    inputs: { blended: blendedRounded, risk: riskRounded },
    riskCap,
    baseRisky,
    riskyAllocation,
    stablesAllocation,
    riskyPct,
    stablesPct
  };
}

// Test avec les 3 benchmarks
console.log('='.repeat(80));
console.log('BENCHMARK STABLES CALCULATION DEBUG');
console.log('='.repeat(80));

// Données des benchmarks (CORRIGÉ avec CCS/Blended Score réel)
const scenarios = [
  { name: 'High Risk',   blended: 55, risk: 40, structural: 62, observed: 61 }, // CCS=55 from bench line 146
  { name: 'Medium Risk', blended: 55, risk: 85, structural: 75, observed: 65 }, // Estimation
  { name: 'Low Risk',    blended: 55, risk: 70, structural: 65, observed: 65 }  // Estimation
];

scenarios.forEach(scenario => {
  const result = calculateStablesFormula(scenario.blended, scenario.risk);

  console.log(`\n${scenario.name}:`);
  console.log(`  Inputs: Blended=${scenario.blended}, Risk=${scenario.risk}`);
  console.log(`  RiskCap: ${result.riskCap.toFixed(3)}`);
  console.log(`  BaseRisky: ${result.baseRisky.toFixed(3)}`);
  console.log(`  RiskyAllocation: ${result.riskyAllocation.toFixed(3)} (${result.riskyPct}%)`);
  console.log(`  StablesAllocation: ${result.stablesAllocation.toFixed(3)} (${result.stablesPct}%)`);
  console.log(`  ❌ Calculated: ${result.stablesPct}% vs Observed: ${scenario.observed}%`);
  console.log(`  📊 Delta: ${Math.abs(result.stablesPct - scenario.observed)}% difference`);
});

console.log('\n' + '='.repeat(80));
console.log('CONCLUSION:');
console.log('Si delta > 5%, il y a un OVERRIDE après calculateRiskBudget()');
console.log('='.repeat(80));
