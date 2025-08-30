/**
 * DYNAMIC WEIGHTING SYSTEM - Adaptive category weights based on market conditions
 * 
 * Concept :
 * - Bull markets → Plus de poids sur sentiment (detect FOMO/euphoria)
 * - Bear markets → Plus de poids sur fundamentals (valeur intrinsèque)
 * - Transitions → Équilibrage entre technique et on-chain
 * - Volatilité → Réduction du poids sentiment, augmentation technique
 */

import { INDICATOR_CATEGORIES_V2 } from './indicator-categories-v2.js';

/**
 * Market phases avec leurs caractéristiques de weighting
 */
export const MARKET_PHASES = {
  accumulation: {
    name: 'Accumulation',
    description: 'Bear market bottom, focus on fundamentals',
    scoreRange: [0, 30],
    weights: {
      onchain_pure: 0.50,     // +25% vs base (focus sur valeur)
      cycle_technical: 0.35,   // Stable (timing important)
      sentiment_social: 0.05,  // -67% (sentiment peu fiable)
      market_context: 0.10     // Stable
    },
    reasoning: 'En accumulation, les fondamentaux blockchain sont cruciaux'
  },
  
  early_expansion: {
    name: 'Early Expansion',
    description: 'Bull market start, balanced approach',
    scoreRange: [30, 45],
    weights: {
      onchain_pure: 0.40,     // Base weights
      cycle_technical: 0.35,
      sentiment_social: 0.15,
      market_context: 0.10
    },
    reasoning: 'Période de transition, garder équilibre standard'
  },
  
  expansion: {
    name: 'Expansion',
    description: 'Bull market momentum, technical signals important',
    scoreRange: [45, 70],
    weights: {
      onchain_pure: 0.35,     // -12% (moins critique)
      cycle_technical: 0.40,   // +14% (momentum key)
      sentiment_social: 0.15,  // Stable
      market_context: 0.10
    },
    reasoning: 'Momentum technique devient prioritaire'
  },
  
  euphoria: {
    name: 'Euphoria',
    description: 'Late bull market, sentiment crucial for top detection',
    scoreRange: [70, 90],
    weights: {
      onchain_pure: 0.30,     // -25% (valeur moins importante)
      cycle_technical: 0.30,   // -14% (technique saturée)
      sentiment_social: 0.30,  // +100% (FOMO detection)
      market_context: 0.10
    },
    reasoning: 'Sentiment extrême signal clé pour détection tops'
  },
  
  distribution: {
    name: 'Distribution',
    description: 'Early bear market, mixed signals',
    scoreRange: [90, 100],
    weights: {
      onchain_pure: 0.35,
      cycle_technical: 0.40,   // +14% (signaux de retournement)
      sentiment_social: 0.15,  // Retour normal
      market_context: 0.10
    },
    reasoning: 'Signaux techniques de retournement importants'
  }
};

/**
 * Market volatility adjustments
 */
export const VOLATILITY_ADJUSTMENTS = {
  low: {      // VIX < 20 equivalent crypto
    sentiment_multiplier: 1.2,  // Sentiment plus fiable
    technical_multiplier: 0.9   // Technique moins critique
  },
  medium: {   // Normal volatility
    sentiment_multiplier: 1.0,
    technical_multiplier: 1.0
  },
  high: {     // VIX > 30 equivalent 
    sentiment_multiplier: 0.7,  // Sentiment peu fiable
    technical_multiplier: 1.3   // Technique plus importante
  },
  extreme: {  // Crash conditions
    sentiment_multiplier: 0.5,  // Ignorer sentiment panic
    technical_multiplier: 1.5   // Focus sur signaux techniques
  }
};

/**
 * Calcule les poids dynamiques basés sur le score composite et le contexte
 */
export function calculateDynamicWeights(compositeScore, marketContext = {}) {
  // 1. Déterminer la phase de marché
  const phase = determineMarketPhase(compositeScore);
  
  // 2. Commencer avec les poids de base de la phase
  let dynamicWeights = { ...phase.weights };
  
  // 3. Ajustements pour volatilité si disponible
  if (marketContext.volatility) {
    dynamicWeights = applyVolatilityAdjustments(dynamicWeights, marketContext.volatility);
  }
  
  // 4. Ajustements pour tendance si disponible
  if (marketContext.trend) {
    dynamicWeights = applyTrendAdjustments(dynamicWeights, marketContext.trend);
  }
  
  // 5. Ajustements pour contradictions détectées
  if (marketContext.contradictions && marketContext.contradictions.length > 0) {
    dynamicWeights = applyContradictionAdjustments(dynamicWeights, marketContext.contradictions);
  }
  
  // 6. Normaliser les poids pour qu'ils totalisent 1.0
  dynamicWeights = normalizeWeights(dynamicWeights);
  
  return {
    weights: dynamicWeights,
    phase: phase,
    adjustments: {
      volatility: marketContext.volatility,
      trend: marketContext.trend,
      contradictions: marketContext.contradictions?.length || 0
    },
    reasoning: generateWeightingReasoning(phase, marketContext)
  };
}

/**
 * Détermine la phase de marché basée sur le score composite
 */
function determineMarketPhase(score) {
  for (const [phaseKey, phase] of Object.entries(MARKET_PHASES)) {
    const [min, max] = phase.scoreRange;
    if (score >= min && score <= max) {
      return { ...phase, key: phaseKey };
    }
  }
  
  // Fallback to early_expansion if no match
  return { ...MARKET_PHASES.early_expansion, key: 'early_expansion' };
}

/**
 * Applique les ajustements de volatilité
 */
function applyVolatilityAdjustments(weights, volatilityLevel) {
  const adjustments = VOLATILITY_ADJUSTMENTS[volatilityLevel] || VOLATILITY_ADJUSTMENTS.medium;
  
  return {
    onchain_pure: weights.onchain_pure,
    cycle_technical: weights.cycle_technical * adjustments.technical_multiplier,
    sentiment_social: weights.sentiment_social * adjustments.sentiment_multiplier,
    market_context: weights.market_context
  };
}

/**
 * Applique les ajustements de tendance
 */
function applyTrendAdjustments(weights, trend) {
  const adjustmentFactor = 0.1; // 10% adjustment max
  
  if (trend === 'strong_bullish') {
    // Augmenter sentiment, réduire on-chain
    return {
      onchain_pure: weights.onchain_pure * (1 - adjustmentFactor),
      cycle_technical: weights.cycle_technical,
      sentiment_social: weights.sentiment_social * (1 + adjustmentFactor * 2),
      market_context: weights.market_context
    };
  } else if (trend === 'strong_bearish') {
    // Augmenter on-chain, réduire sentiment
    return {
      onchain_pure: weights.onchain_pure * (1 + adjustmentFactor),
      cycle_technical: weights.cycle_technical,
      sentiment_social: weights.sentiment_social * (1 - adjustmentFactor),
      market_context: weights.market_context
    };
  }
  
  return weights; // No adjustment for neutral/weak trends
}

/**
 * Applique les ajustements en cas de signaux contradictoires
 */
function applyContradictionAdjustments(weights, contradictions) {
  // Plus il y a de contradictions, plus on se recentre sur les fondamentaux
  const contradictionFactor = Math.min(contradictions.length * 0.1, 0.3); // Max 30% adjustment
  
  return {
    onchain_pure: weights.onchain_pure * (1 + contradictionFactor), // Augmenter fondamentaux
    cycle_technical: weights.cycle_technical * (1 - contradictionFactor * 0.5), // Réduire technique
    sentiment_social: weights.sentiment_social * (1 - contradictionFactor * 0.7), // Réduire sentiment
    market_context: weights.market_context
  };
}

/**
 * Normalise les poids pour qu'ils totalisent 1.0
 */
function normalizeWeights(weights) {
  const total = Object.values(weights).reduce((sum, weight) => sum + weight, 0);
  
  const normalized = {};
  for (const [category, weight] of Object.entries(weights)) {
    normalized[category] = weight / total;
  }
  
  return normalized;
}

/**
 * Génère l'explication du raisonnement de pondération
 */
function generateWeightingReasoning(phase, marketContext) {
  let reasoning = [phase.reasoning];
  
  if (marketContext.volatility === 'high' || marketContext.volatility === 'extreme') {
    reasoning.push('Haute volatilité → Réduction poids sentiment, augmentation technique');
  }
  
  if (marketContext.trend === 'strong_bullish') {
    reasoning.push('Forte tendance haussière → Augmentation poids sentiment (FOMO detection)');
  } else if (marketContext.trend === 'strong_bearish') {
    reasoning.push('Forte tendance baissière → Focus sur fondamentaux on-chain');
  }
  
  if (marketContext.contradictions && marketContext.contradictions.length > 0) {
    reasoning.push(`${marketContext.contradictions.length} signaux contradictoires → Recentrage sur fondamentaux`);
  }
  
  return reasoning;
}

/**
 * Fonction utilitaire pour comparer les poids statiques vs dynamiques
 */
export function compareWeightingMethods(compositeScore, marketContext = {}) {
  const staticWeights = {
    onchain_pure: INDICATOR_CATEGORIES_V2.onchain_pure.weight,
    cycle_technical: INDICATOR_CATEGORIES_V2.cycle_technical.weight,
    sentiment_social: INDICATOR_CATEGORIES_V2.sentiment_social.weight,
    market_context: INDICATOR_CATEGORIES_V2.market_context.weight
  };
  
  const dynamicResult = calculateDynamicWeights(compositeScore, marketContext);
  
  // Calculer les différences
  const weightDifferences = {};
  for (const category of Object.keys(staticWeights)) {
    const staticWeight = staticWeights[category];
    const dynamicWeight = dynamicResult.weights[category];
    const difference = ((dynamicWeight - staticWeight) / staticWeight) * 100;
    
    weightDifferences[category] = {
      static: Math.round(staticWeight * 100),
      dynamic: Math.round(dynamicWeight * 100),
      change: difference > 0 ? `+${difference.toFixed(1)}%` : `${difference.toFixed(1)}%`
    };
  }
  
  return {
    static: staticWeights,
    dynamic: dynamicResult,
    differences: weightDifferences,
    recommendation: dynamicResult.phase.name !== 'Early Expansion' ? 
      'Dynamic weighting recommended' : 'Static weighting sufficient'
  };
}

/**
 * Détection automatique du contexte de marché basé sur les données disponibles
 */
export function detectMarketContext(categoryBreakdown, indicators = {}) {
  const context = {};
  
  // 1. Détection de volatilité basée sur les zones critiques
  const criticalCount = Object.values(categoryBreakdown).reduce((sum, cat) => 
    sum + (cat.contributors ? cat.contributors.filter(c => c.inCriticalZone).length : 0), 0);
  
  const totalIndicators = Object.values(categoryBreakdown).reduce((sum, cat) => 
    sum + (cat.contributorsCount || 0), 0);
  
  const criticalRatio = criticalCount / Math.max(totalIndicators, 1);
  
  if (criticalRatio > 0.4) context.volatility = 'extreme';
  else if (criticalRatio > 0.25) context.volatility = 'high';
  else if (criticalRatio > 0.15) context.volatility = 'medium';
  else context.volatility = 'low';
  
  // 2. Détection de tendance basée sur consensus des catégories
  const bullishCategories = Object.values(categoryBreakdown).filter(cat => 
    cat.consensus?.consensus === 'bullish').length;
  const bearishCategories = Object.values(categoryBreakdown).filter(cat => 
    cat.consensus?.consensus === 'bearish').length;
  
  if (bullishCategories >= 3) context.trend = 'strong_bullish';
  else if (bullishCategories >= 2) context.trend = 'bullish';
  else if (bearishCategories >= 3) context.trend = 'strong_bearish';
  else if (bearishCategories >= 2) context.trend = 'bearish';
  else context.trend = 'neutral';
  
  return context;
}

export default {
  calculateDynamicWeights,
  compareWeightingMethods,
  detectMarketContext,
  MARKET_PHASES,
  VOLATILITY_ADJUSTMENTS
};