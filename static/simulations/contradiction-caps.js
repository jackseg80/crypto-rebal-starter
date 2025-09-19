/**
 * Module de caps adaptatifs basés sur les contradictions pour le simulateur
 * Applique une logique défensive selon le niveau de contradiction
 */

import { calculateRiskCaps, classifyContradiction } from '../governance/contradiction-policy.js';
import { selectContradictionPct } from '../selectors/governance.js';

/**
 * Applique des caps de risque adaptatifs selon les contradictions
 * @param {Object} policy - Politique de base
 * @param {Object} state - État unifié du système
 * @returns {Object} - Politique modifiée avec caps adaptatifs
 */
export function applyContradictionCaps(policy, state) {
  const baseCaps = {
    memecoins: 0.15,      // 15% max normal
    small_caps: 0.25,     // 25% max normal
    ai_data: 0.20,        // 20% max normal
    gaming_nft: 0.18,     // 18% max normal
    ...policy.caps
  };

  // Calcul des caps adaptatifs
  const adaptedCaps = calculateRiskCaps(baseCaps, state);
  const classification = classifyContradiction(state);

  // Application aux segments risqués
  const updatedPolicy = {
    ...policy,
    caps: {
      ...policy.caps,
      // Caps principaux
      memecoins: Math.min(adaptedCaps.memecoins, policy.caps?.memecoins ?? 1.0),
      small_caps: Math.min(adaptedCaps.small_caps, policy.caps?.small_caps ?? 1.0),
      ai_data: Math.min(adaptedCaps.ai_data, policy.caps?.ai_data ?? 1.0),
      gaming_nft: Math.min(adaptedCaps.gaming_nft, policy.caps?.gaming_nft ?? 1.0),

      // Métadonnées pour debugging
      _contradiction_meta: {
        original_caps: baseCaps,
        adapted_caps: adaptedCaps,
        reductions: adaptedCaps.meta.reductions,
        contradiction_level: classification.level,
        message: classification.message
      }
    }
  };

  return updatedPolicy;
}

/**
 * Calcule les allocations maximales pour les segments risqués
 * @param {number} totalValue - Valeur totale du portfolio
 * @param {Object} state - État unifié
 * @returns {Object} - Allocations max en USD
 */
export function calculateMaxRiskyAllocations(totalValue, state) {
  const caps = calculateRiskCaps({}, state);
  const contradictionPct = selectContradictionPct(state);

  return {
    memecoins: {
      max_pct: caps.memecoins,
      max_usd: totalValue * caps.memecoins,
      reduction_from_normal: Math.round((1 - caps.memecoins / 0.15) * 100),
      reason: contradictionPct >= 70 ? 'high_contradiction' :
              contradictionPct >= 40 ? 'medium_contradiction' : 'normal'
    },
    small_caps: {
      max_pct: caps.small_caps,
      max_usd: totalValue * caps.small_caps,
      reduction_from_normal: Math.round((1 - caps.small_caps / 0.25) * 100),
      reason: contradictionPct >= 70 ? 'high_contradiction' :
              contradictionPct >= 40 ? 'medium_contradiction' : 'normal'
    },
    total_risky: {
      max_pct: caps.memecoins + caps.small_caps,
      max_usd: totalValue * (caps.memecoins + caps.small_caps),
      contradiction_level: contradictionPct,
      defensive_mode: contradictionPct >= 70
    }
  };
}

/**
 * Valide qu'une allocation respecte les caps de contradiction
 * @param {Object} allocation - Allocation proposée
 * @param {Object} state - État unifié
 * @returns {Object} - Résultat de validation
 */
export function validateAllocationCaps(allocation, state) {
  const caps = calculateRiskCaps({}, state);
  const contradictionPct = selectContradictionPct(state);

  const violations = [];
  const warnings = [];

  // Vérification memecoins
  if (allocation.memecoins > caps.memecoins) {
    violations.push({
      segment: 'memecoins',
      current: allocation.memecoins,
      max_allowed: caps.memecoins,
      excess: allocation.memecoins - caps.memecoins
    });
  }

  // Vérification small caps
  if (allocation.small_caps > caps.small_caps) {
    violations.push({
      segment: 'small_caps',
      current: allocation.small_caps,
      max_allowed: caps.small_caps,
      excess: allocation.small_caps - caps.small_caps
    });
  }

  // Warning si proche des limites
  if (allocation.memecoins > caps.memecoins * 0.9) {
    warnings.push({
      segment: 'memecoins',
      message: `Proche du cap adaptatif (${Math.round(caps.memecoins * 100)}%)`
    });
  }

  return {
    valid: violations.length === 0,
    violations,
    warnings,
    caps_applied: caps,
    contradiction_level: contradictionPct,
    adaptive_mode: contradictionPct >= 40,
    recommendations: violations.length > 0 ? [
      'Réduire l\'exposition aux segments violant les caps',
      'Privilégier les majors (BTC/ETH) et stablecoins',
      'Considérer l\'augmentation de la prudence'
    ] : []
  };
}

/**
 * Génère un rapport de caps pour le monitoring
 * @param {Object} state - État unifié
 * @returns {Object} - Rapport détaillé
 */
export function generateCapsReport(state) {
  const caps = calculateRiskCaps({}, state);
  const classification = classifyContradiction(state);
  const contradictionPct = selectContradictionPct(state);

  return {
    timestamp: new Date().toISOString(),
    contradiction: {
      level: classification.level,
      percentage: contradictionPct,
      message: classification.message
    },
    caps: {
      current: caps,
      reductions: caps.meta.reductions,
      normal_caps: {
        memecoins: 15,
        small_caps: 25,
        ai_data: 20,
        gaming_nft: 18
      }
    },
    mode: {
      defensive: contradictionPct >= 70,
      cautious: contradictionPct >= 40,
      normal: contradictionPct < 40
    },
    recommendations: classification.recommendations
  };
}

/**
 * Interface simplifiée pour les dashboards
 * @param {Object} state - État unifié
 * @returns {Object} - Caps formatés pour affichage
 */
export function getDisplayCaps(state) {
  const caps = calculateRiskCaps({}, state);
  const contradictionPct = selectContradictionPct(state);

  return {
    memecoins: Math.round(caps.memecoins * 100),
    small_caps: Math.round(caps.small_caps * 100),
    total_risky: Math.round((caps.memecoins + caps.small_caps) * 100),
    mode: contradictionPct >= 70 ? 'defensive' :
          contradictionPct >= 40 ? 'cautious' : 'normal',
    message: `Caps adaptatifs (contradiction: ${contradictionPct}%)`
  };
}