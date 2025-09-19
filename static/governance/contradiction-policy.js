/**
 * Politique de gestion des contradictions
 * Table centralisée des seuils et messages pour éviter les duplications
 */

import { selectContradictionPct, selectContradiction01 } from '../selectors/governance.js';

/**
 * Classification des niveaux de contradiction
 * @param {Object} state - État unifié
 * @returns {Object} - Classification complète
 */
export function classifyContradiction(state) {
  const pct = selectContradictionPct(state);

  if (pct >= 70) {
    return {
      level: 'high',
      priority: 'high',
      severity: 'critical',
      message: `Signaux contradictoires élevés (${pct}%) — approche prudente recommandée.`,
      color: 'var(--danger)',
      bgColor: 'var(--danger-bg)',
      recommendations: [
        'Réduire l\'exposition aux actifs risqués',
        'Privilégier les stablecoins et majors (BTC/ETH)',
        'Reporter les décisions d\'investissement non-urgentes',
        'Surveiller les signaux de marché de près'
      ]
    };
  }

  if (pct >= 40) {
    return {
      level: 'medium',
      priority: 'medium',
      severity: 'warning',
      message: `Signaux contradictoires modérés (${pct}%) — vigilance recommandée.`,
      color: 'var(--warning)',
      bgColor: 'var(--warning-bg)',
      recommendations: [
        'Maintenir une allocation équilibrée',
        'Éviter les positions spéculatives importantes',
        'Surveiller les développements du marché',
        'Préparer des scenarios de contingence'
      ]
    };
  }

  return {
    level: 'low',
    priority: 'low',
    severity: 'info',
    message: `Contradiction faible (${pct}%) — signaux alignés.`,
    color: 'var(--success)',
    bgColor: 'var(--success-bg)',
    recommendations: [
      'Conditions favorables pour les stratégies actives',
      'Opportunité d\'optimiser l\'allocation',
      'Considérer des positions tactiques',
      'Exploiter les signaux de momentum'
    ]
  };
}

/**
 * Calcul des poids adaptatifs basés sur la contradiction
 * Formule: contradiction ↑ → risk ↑, cycle/onchain ↓ (prudence)
 * @param {Object} baseWeights - Poids de base {cycle, onchain, risk}
 * @param {Object} state - État unifié
 * @returns {Object} - Poids ajustés et renormalisés
 */
export function calculateAdaptiveWeights(baseWeights, state) {
  const base = { cycle: 0.4, onchain: 0.35, risk: 0.25, ...baseWeights };
  const c = selectContradiction01(state); // 0-1

  // Coefficients d'ajustement (baseline pour backtesting)
  const cycleReduction = 0.35;    // jusqu'à -35%
  const onchainReduction = 0.15;  // jusqu'à -15% (plus doux)
  const riskIncrease = 0.50;      // jusqu'à +50% (prudence)

  // Application des ajustements
  const cycle = clamp01(base.cycle * (1 - cycleReduction * c));
  const onchain = clamp01(base.onchain * (1 - onchainReduction * c));
  const risk = clamp01(base.risk * (1 + riskIncrease * c));

  // Bornes défensives pour éviter des poids pathologiques
  const floor = 0.12;  // minimum 12%
  const ceil = 0.65;   // maximum 65%

  let weights = {
    cycle: Math.max(floor, Math.min(ceil, cycle)),
    onchain: Math.max(floor, Math.min(ceil, onchain)),
    risk: Math.max(floor, Math.min(ceil, risk))
  };

  // Renormalisation stricte (somme = 1)
  const sum = weights.cycle + weights.onchain + weights.risk;
  weights = {
    cycle: weights.cycle / sum,
    onchain: weights.onchain / sum,
    risk: weights.risk / sum
  };

  return {
    ...weights,
    // Métadonnées pour debugging/monitoring
    meta: {
      contradiction_level: selectContradictionPct(state),
      base_weights: base,
      adjustments: {
        cycle_reduction: Math.round((1 - weights.cycle / base.cycle) * 100),
        onchain_reduction: Math.round((1 - weights.onchain / base.onchain) * 100),
        risk_increase: Math.round((weights.risk / base.risk - 1) * 100)
      },
      sum_check: Math.round(sum * 1000) / 1000 // vérification somme
    }
  };
}

/**
 * Calcul des caps de segments risqués selon la contradiction
 * @param {Object} baseCaps - Caps de base par segment
 * @param {Object} state - État unifié
 * @returns {Object} - Caps ajustés
 */
export function calculateRiskCaps(baseCaps, state) {
  const base = {
    memecoins: 0.15,      // 15% max en normal
    small_caps: 0.25,     // 25% max en normal
    ai_data: 0.20,        // 20% max en normal (futur)
    gaming_nft: 0.18,     // 18% max en normal (futur)
    ...baseCaps
  };

  const c = selectContradiction01(state); // 0-1

  // Réduction progressive des caps selon contradiction
  const caps = {
    memecoins: lerp(base.memecoins, 0.05, c),   // 15% → 5%
    small_caps: lerp(base.small_caps, 0.12, c), // 25% → 12%
    ai_data: lerp(base.ai_data, 0.10, c),       // 20% → 10%
    gaming_nft: lerp(base.gaming_nft, 0.08, c) // 18% → 8%
  };

  return {
    ...caps,
    meta: {
      contradiction_level: selectContradictionPct(state),
      reductions: {
        memecoins: Math.round((1 - caps.memecoins / base.memecoins) * 100),
        small_caps: Math.round((1 - caps.small_caps / base.small_caps) * 100),
        ai_data: Math.round((1 - caps.ai_data / base.ai_data) * 100),
        gaming_nft: Math.round((1 - caps.gaming_nft / base.gaming_nft) * 100)
      }
    }
  };
}

/**
 * Helpers
 */
function clamp01(x) {
  return Math.max(0, Math.min(1, x));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

/**
 * Validation des seuils et cohérence
 * @param {Object} state - État unifié
 * @returns {Object} - Résultat de validation
 */
export function validateContradictionLogic(state) {
  const classification = classifyContradiction(state);
  const weights = calculateAdaptiveWeights({}, state);
  const caps = calculateRiskCaps({}, state);

  return {
    classification,
    weights,
    caps,
    coherence_checks: {
      weights_sum: Math.abs(weights.cycle + weights.onchain + weights.risk - 1) < 0.001,
      risk_increase_with_contradiction: weights.risk >= 0.25, // risk doit augmenter
      caps_decrease_with_contradiction: caps.memecoins <= 0.15 // caps doivent diminuer
    }
  };
}