/**
 * Module de calcul des poids adaptatifs unifiés
 * Remplace les implémentations éparses par une logique centralisée
 */

import { calculateAdaptiveWeights, calculateRiskCaps, classifyContradiction } from '../governance/contradiction-policy.js';
import { selectContradiction01, selectContradictionPct } from '../selectors/governance.js';

/**
 * Calcul principal des poids adaptatifs pour le blending des scores
 * Interface unifiée pour remplacer les fonctions legacy
 * @param {Object} config - Configuration du calcul
 * @param {Object} state - État unifié du système
 * @returns {Object} - Poids calculés avec métadonnées
 */
export function calculateUnifiedAdaptiveWeights(config, state) {
  const {
    cycleData = {},
    onchainScore = 50,
    contradictions = [],
    baseWeights = { cycle: 0.4, onchain: 0.35, risk: 0.25 }
  } = config;

  // 1. Ajustement des poids de base selon le cycle
  const cycleScore = cycleData?.score ?? 50;
  let adjustedBaseWeights = { ...baseWeights };

  if (cycleScore >= 90) {
    // Cycle très fort → boost cycle, réduit onchain
    adjustedBaseWeights = {
      cycle: 0.5,     // +25% vs normal
      onchain: 0.25,  // -29% vs normal
      risk: 0.25      // Stable
    };
  } else if (cycleScore >= 70) {
    // Cycle modéré → ajustement léger
    adjustedBaseWeights = {
      cycle: 0.45,    // +12% vs normal
      onchain: 0.3,   // -14% vs normal
      risk: 0.25      // Stable
    };
  }

  // 2. Application de la contradiction via notre système centralisé
  const result = calculateAdaptiveWeights(adjustedBaseWeights, state);

  // 3. Calcul du multiplicateur de vitesse (legacy compatibility)
  const contradictionPct = selectContradictionPct(state);
  const speedMultiplier = Math.max(0.5, 1 - (contradictionPct / 100) * 0.5);

  // 4. Floor onchain ajusté selon le cycle
  const onchainFloor = cycleScore >= 90 ? 0.3 : 0.0;
  const adjustedOnchainScore = Math.max(onchainFloor * 100, onchainScore);

  // 5. Classification des contradictions pour recommandations
  const contradictionClassification = classifyContradiction(state);

  // 6. Caps de risque adaptatifs
  const riskCaps = calculateRiskCaps({}, state);

  return {
    // Poids finaux
    weights: {
      cycle: result.cycle,
      onchain: result.onchain,
      risk: result.risk
    },

    // Legacy compatibility
    wCycle: result.cycle,
    wOnchain: result.onchain,
    wRisk: result.risk,
    adjustedOnchainScore,
    speedMultiplier,
    onchainFloor,

    // Métadonnées enrichies
    meta: {
      ...result.meta,
      cycle_score: cycleScore,
      cycle_boost: cycleScore >= 70,
      onchain_floor_applied: adjustedOnchainScore > onchainScore,
      speed_reduction: speedMultiplier < 1.0,
      contradiction: {
        ...contradictionClassification,
        percentage: contradictionPct
      }
    },

    // Caps et recommandations
    riskCaps,
    recommendations: contradictionClassification.recommendations,

    // Validation
    validation: {
      weights_sum: Math.abs(result.cycle + result.onchain + result.risk - 1) < 0.001,
      all_weights_positive: result.cycle > 0 && result.onchain > 0 && result.risk > 0,
      contradiction_coherent: result.risk >= 0.12 // Risk doit augmenter avec contradiction
    }
  };
}

/**
 * Version simplifiée pour l'usage dans les tableaux de bord
 * @param {Object} state - État unifié
 * @returns {Object} - Poids simplifiés
 */
export function getDisplayWeights(state) {
  const result = calculateUnifiedAdaptiveWeights({}, state);

  return {
    cycle: Math.round(result.weights.cycle * 100),
    onchain: Math.round(result.weights.onchain * 100),
    risk: Math.round(result.weights.risk * 100),
    contradiction_level: result.meta.contradiction.level,
    message: result.meta.contradiction.message
  };
}

/**
 * Wrapper de compatibilité pour l'ancien calculateAdaptiveWeights
 * @param {Object} cycleData - Données de cycle
 * @param {number} onchainScore - Score onchain
 * @param {Array} contradictions - Array de contradictions (legacy)
 * @param {number} governanceContradiction - Contradiction governance (0-1)
 * @returns {Object} - Résultat compatible
 */
export function calculateAdaptiveWeightsCompat(cycleData, onchainScore, contradictions, governanceContradiction = 0) {
  const state = {
    governance: {
      contradiction_index: governanceContradiction > 0 ? governanceContradiction :
                          (contradictions?.length ?? 0) / 100
    }
  };

  const config = {
    cycleData,
    onchainScore,
    contradictions
  };

  const result = calculateUnifiedAdaptiveWeights(config, state);

  // Format legacy exact
  return {
    wCycle: result.wCycle,
    wOnchain: result.wOnchain,
    wRisk: result.wRisk,
    adjustedOnchainScore: result.adjustedOnchainScore,
    speedMultiplier: result.speedMultiplier,
    onchainFloor: result.onchainFloor,
    reasoning: {
      cycleBoost: result.meta.cycle_boost,
      onchainFloorApplied: result.meta.onchain_floor_applied,
      contradictionLevel: result.meta.contradiction.percentage,
      speedReduction: result.meta.speed_reduction
    },
    meta: result.meta,
    migrated_to_unified: true
  };
}

/**
 * Validation des poids pour debugging
 * @param {Object} weights - Poids à valider
 * @returns {Object} - Résultat de validation
 */
export function validateWeights(weights) {
  const sum = weights.cycle + weights.onchain + weights.risk;
  const tolerance = 0.001;

  return {
    valid: Math.abs(sum - 1) < tolerance,
    sum,
    difference: sum - 1,
    individual_valid: {
      cycle: weights.cycle >= 0.12 && weights.cycle <= 0.65,
      onchain: weights.onchain >= 0.12 && weights.onchain <= 0.65,
      risk: weights.risk >= 0.12 && weights.risk <= 0.65
    }
  };
}

/**
 * Export pour le monitoring et debugging
 */
export function getWeightsDebugInfo(state) {
  const result = calculateUnifiedAdaptiveWeights({}, state);
  const validation = validateWeights(result.weights);

  return {
    weights: result.weights,
    validation,
    contradiction: result.meta.contradiction,
    caps: result.riskCaps,
    recommendations: result.recommendations,
    timestamp: new Date().toISOString()
  };
}