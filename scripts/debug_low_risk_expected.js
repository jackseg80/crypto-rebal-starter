/**
 * Debug: Calcul attendu pour Low_Risk portfolio
 *
 * Hypothèses basées sur portfolio équilibré (40% BTC, 30% ETH, 30% stables/autres)
 * - Decision Index (DI): ~55-60 (estimation)
 * - Risk Score v1 (legacy): ~70 (estimation pour portfolio équilibré)
 */

function calculateStablesTarget(blended, risk, mode = 'legacy') {
  const blendedRounded = Math.round(blended);
  const riskRounded = Math.round(risk);

  let risk_factor;

  if (mode === 'legacy') {
    risk_factor = 1 - 0.5 * (riskRounded / 100);
  } else if (mode === 'v2_conservative') {
    risk_factor = 0.5 + 0.5 * (riskRounded / 100);
  } else if (mode === 'v2_aggressive') {
    risk_factor = 0.4 + 0.7 * (riskRounded / 100);
  }

  const baseRisky = Math.max(0, Math.min(1, (blendedRounded - 35) / 45));
  const riskyAllocation = Math.max(0.20, Math.min(0.85, baseRisky * risk_factor));
  const stablesPct = 100 - Math.round(riskyAllocation * 100);

  return {
    risk_factor: risk_factor.toFixed(3),
    baseRisky: baseRisky.toFixed(3),
    riskyAllocation: (riskyAllocation * 100).toFixed(1),
    stablesPct
  };
}

console.log('='.repeat(80));
console.log('LOW_RISK PORTFOLIO - Expected Stables Calculation');
console.log('='.repeat(80));
console.log('');

// Test avec différentes hypothèses de scores
const scenarios = [
  { name: 'Hypothèse 1: DI=55, Risk=70', blended: 55, risk: 70 },
  { name: 'Hypothèse 2: DI=57, Risk=65', blended: 57, risk: 65 },
  { name: 'Hypothèse 3: DI=60, Risk=75', blended: 60, risk: 75 },
];

scenarios.forEach(s => {
  console.log(s.name + ':');
  console.log('  Input: DI=' + s.blended + ', Risk=' + s.risk);

  const legacy = calculateStablesTarget(s.blended, s.risk, 'legacy');
  const v2_cons = calculateStablesTarget(s.blended, s.risk, 'v2_conservative');

  console.log('  Legacy:          Stables=' + legacy.stablesPct + '% (risk_factor=' + legacy.risk_factor + ')');
  console.log('  v2_conservative: Stables=' + v2_cons.stablesPct + '% (risk_factor=' + v2_cons.risk_factor + ')');
  console.log('  Delta: ' + (v2_cons.stablesPct - legacy.stablesPct) + '% (v2 vs legacy)');
  console.log('');
});

console.log('='.repeat(80));
console.log('ACTION REQUISE:');
console.log('1. Dans analytics-unified.html avec wallet Low_Risk:');
console.log('   - Ouvrir la console navigateur (F12)');
console.log('   - Chercher les logs: "💰 Risk Budget calculated:"');
console.log('   - Noter les valeurs: blended_score, risk_score');
console.log('');
console.log('2. Comparer "Budget stables théorique" affiché:');
console.log('   - Mode legacy: localStorage.setItem("RISK_SEMANTICS_MODE", "legacy")');
console.log('   - Mode v2: localStorage.setItem("RISK_SEMANTICS_MODE", "v2_conservative")');
console.log('   - Recharger (F5) après chaque changement');
console.log('');
console.log('3. Si AUCUNE différence visible:');
console.log('   - Le Risk Score est probablement = 50 (point équilibre)');
console.log('   - OU le cache est actif (TTL 30s dans market-regimes.js)');
console.log('   - OU le mode n\'est pas détecté (vérifier console log)');
console.log('='.repeat(80));
