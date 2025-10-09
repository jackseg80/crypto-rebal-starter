/**
 * Reverse engineer: Quel Blended Score produit exactement 66% avec Risk=60 ?
 */

function calculateStables(blended, risk) {
  const blendedRounded = Math.round(blended);
  const riskRounded = Math.round(risk);

  const riskCap = 1 - 0.5 * (riskRounded / 100);
  const baseRisky = Math.max(0, Math.min(1, (blendedRounded - 35) / 45));
  const riskyAllocation = Math.max(0.20, Math.min(0.85, baseRisky * riskCap));

  const riskyPct = Math.round(riskyAllocation * 100);
  const stablesPct = 100 - riskyPct;

  return stablesPct;
}

console.log('='.repeat(80));
console.log('REVERSE ENGINEERING: Quel Blended → 66% stables avec Risk=60 ?');
console.log('='.repeat(80));
console.log('');

const targetStables = 66;
const riskScore = 60;

console.log('Target: ' + targetStables + '% stables');
console.log('Risk Score: ' + riskScore);
console.log('');
console.log('Testing Blended scores from 45 to 65:');
console.log('');

for (let blended = 45; blended <= 65; blended++) {
  const stables = calculateStables(blended, riskScore);
  const match = stables === targetStables ? ' ✅ MATCH!' : '';
  console.log('  Blended=' + blended + ' → Stables=' + stables + '%' + match);
}

console.log('');
console.log('='.repeat(80));
console.log('Testing with CCS=55 and varying Risk scores:');
console.log('='.rect(80));
console.log('');

const blendedScore = 55;
console.log('Blended (CCS): ' + blendedScore);
console.log('');

for (let risk = 50; risk <= 70; risk++) {
  const stables = calculateStables(blendedScore, risk);
  const match = stables === targetStables ? ' ✅ MATCH!' : '';
  console.log('  Risk=' + risk + ' → Stables=' + stables + '%' + match);
}

console.log('');
console.log('='.repeat(80));
console.log('CONCLUSION:');
console.log('La combinaison exacte (Blended, Risk) qui produit 66% révèle');
console.log('quelle valeur est réellement passée à calculateRiskBudget()');
console.log('='.repeat(80));
