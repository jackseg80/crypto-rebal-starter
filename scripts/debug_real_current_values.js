/**
 * Test avec les VRAIES valeurs ACTUELLES du système live
 */

const scenarios = [
  {
    name: 'High Risk (LIVE NOW)',
    blended: 55,
    risk_v1: 60,      // NEW: was 40
    structural: 77,   // NEW: was 62 (76.9 arrondi)
    observed: null    // À vérifier dans le UI
  }
];

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
    stablesPct,
    riskyPct,
    riskCap,
    baseRisky,
    riskyAllocation,
    stablesAllocation
  };
}

console.log('='.repeat(80));
console.log('CALCUL AVEC VRAIES VALEURS LIVE (High Risk Portfolio)');
console.log('='.repeat(80));
console.log('');

scenarios.forEach(s => {
  console.log(s.name + ':');
  console.log('  Input: Blended=' + s.blended + ', Risk v1=' + s.risk_v1 + ', Structural=' + s.structural);
  console.log('');

  const withV1 = calculateRiskBudget(s.blended, s.risk_v1);
  const withStructural = calculateRiskBudget(s.blended, s.structural);

  console.log('  Calcul avec Risk v1 (' + s.risk_v1 + '):');
  console.log('    - RiskCap: ' + withV1.riskCap.toFixed(3));
  console.log('    - BaseRisky: ' + withV1.baseRisky.toFixed(3));
  console.log('    - Risky: ' + withV1.riskyPct + '% / Stables: ' + withV1.stablesPct + '%');
  console.log('');

  console.log('  Calcul avec Structural (' + s.structural + '):');
  console.log('    - RiskCap: ' + withStructural.riskCap.toFixed(3));
  console.log('    - BaseRisky: ' + withStructural.baseRisky.toFixed(3));
  console.log('    - Risky: ' + withStructural.riskyPct + '% / Stables: ' + withStructural.stablesPct + '%');
  console.log('');
});

console.log('='.repeat(80));
console.log('ACTION REQUISE:');
console.log('Vérifier dans le UI actuel (analytics-unified.html):');
console.log('1. Section "Budget & Objectifs → Objectifs Théoriques"');
console.log('2. Ligne "Stablecoins → Objectif → X.X%"');
console.log('3. Reporter la valeur observée pour comparaison');
console.log('='.repeat(80));
