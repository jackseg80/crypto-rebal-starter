/**
 * Test: Et si calculateRiskBudget() utilise STRUCTURAL au lieu de Risk v1 ?
 */

const scenarios = [
  { name: 'High Risk',   blended: 55, risk_v1: 40, structural: 62, observed: 68 },
  { name: 'Medium Risk', blended: 55, risk_v1: 85, structural: 75, observed: 65 },
  { name: 'Low Risk',    blended: 55, risk_v1: 70, structural: 65, observed: 65 }
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

  return stablesPct;
}

console.log('='.repeat(80));
console.log('HYPOTHESIS: calculateRiskBudget() uses STRUCTURAL instead of Risk v1');
console.log('='.repeat(80));
console.log('');

scenarios.forEach(s => {
  const withV1 = calculateRiskBudget(s.blended, s.risk_v1);
  const withStructural = calculateRiskBudget(s.blended, s.structural);

  console.log(s.name + ':');
  console.log('  With Risk v1 (' + s.risk_v1 + '):        ' + withV1 + '% (delta: ' + (withV1 - s.observed) + ')');
  console.log('  With Structural (' + s.structural + '):    ' + withStructural + '% (delta: ' + (withStructural - s.observed) + ')');

  const matchV1 = Math.abs(withV1 - s.observed) < 1 ? '✅ MATCH' : '❌';
  const matchStructural = Math.abs(withStructural - s.observed) < 1 ? '✅ MATCH' : '❌';

  console.log('  Observed:                ' + s.observed + '%');
  console.log('  V1 match: ' + matchV1);
  console.log('  Structural match: ' + matchStructural);
  console.log('');
});

console.log('='.repeat(80));
console.log('CONCLUSION:');
console.log('If Structural scores match better, the bug is that calculateRiskBudget()');
console.log('receives the WRONG risk score (structural instead of v1 authoritative)');
console.log('='.repeat(80));
