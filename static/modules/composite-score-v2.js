/**
 * COMPOSITE SCORE V2 - Version améliorée avec gestion des corrélations
 * 
 * Améliorations :
 * 1. Gestion intelligente des corrélations entre indicateurs
 * 2. Système de consensus voting par catégorie
 * 3. Pondération dynamique selon le contexte de marché
 * 4. Détection des signaux contradictoires
 */

import { 
  INDICATOR_CATEGORIES_V2, 
  classifyIndicatorV2, 
  calculateCategoryConsensus,
  CACHE_CONFIG 
} from './indicator-categories-v2.js';

import { 
  calculateDynamicWeights,
  detectMarketContext,
  compareWeightingMethods
} from './dynamic-weighting.js';

/**
 * Clamp function to ensure values stay within bounds
 */
function clamp01(x) {
  return Math.max(0, Math.min(1, x));
}

/**
 * Normalise et inverse un score d'indicateur selon sa configuration V2
 * with strict [0,100] clamping
 */
function normalizeAndInvertScoreV2(rawValue, classification) {
  // Ensure rawValue is a valid number and clamp to [0,100]
  let normalizedScore = Math.max(0, Math.min(100, Number(rawValue) || 0));

  if (classification.invert) {
    normalizedScore = 100 - normalizedScore;
  }

  // Final clamp to ensure result is always [0,100]
  return Math.max(0, Math.min(100, normalizedScore));
}

/**
 * Applique la réduction de corrélation pour éviter la surpondération
 */
function applyCorrelationReduction(indicators, category) {
  const correlationGroups = {};
  const reducedIndicators = [];
  
  console.debug(`🔍 Analyzing correlations for category "${category}" with ${indicators.length} indicators`);
  
  // Grouper les indicateurs par groupe de corrélation
  indicators.forEach(indicator => {
    const group = indicator.classification.correlationGroup;
    console.debug(`  📊 ${indicator.name}: correlationGroup = ${group}`);
    
    if (group) {
      if (!correlationGroups[group]) {
        correlationGroups[group] = [];
      }
      correlationGroups[group].push(indicator);
    } else {
      // Indicateurs non corrélés - poids normal
      reducedIndicators.push(indicator);
    }
  });
  
  console.debug(`🔗 Found correlation groups:`, Object.keys(correlationGroups));
  
  // Pour chaque groupe corrélé, réduire l'impact global
  Object.entries(correlationGroups).forEach(([groupName, groupIndicators]) => {
    if (groupIndicators.length <= 1) {
      // Pas de corrélation, garder tel quel
      reducedIndicators.push(...groupIndicators);
      return;
    }
    
    // Trouver l'indicateur dominant ou celui avec le poids le plus élevé
    const dominantIndicator = groupIndicators.find(ind => ind.classification.dominant) ||
                             groupIndicators.reduce((prev, curr) => 
                               prev.weight > curr.weight ? prev : curr
                             );
    
    // L'indicateur dominant garde 70% de son poids
    const adjustedDominant = {
      ...dominantIndicator,
      weight: dominantIndicator.weight * 0.7,
      correlationReduction: 'dominant_70%'
    };
    reducedIndicators.push(adjustedDominant);
    
    // Les autres indicateurs du groupe se partagent 30% du poids total
    const remainingIndicators = groupIndicators.filter(ind => ind !== dominantIndicator);
    const sharedWeight = dominantIndicator.weight * 0.3;
    const individualWeight = sharedWeight / remainingIndicators.length;
    
    remainingIndicators.forEach(indicator => {
      reducedIndicators.push({
        ...indicator,
        weight: individualWeight,
        correlationReduction: 'secondary_30%_shared'
      });
    });
    
    console.debug(`🔗 Correlation group "${groupName}": ${groupIndicators.length} indicators, dominant: ${dominantIndicator.name}`);
  });
  
  return reducedIndicators;
}

/**
 * Calcule un score composite V2 avec gestion avancée des corrélations
 */
export function calculateCompositeScoreV2(indicators, useDynamicWeighting = false) {
  if (!indicators || Object.keys(indicators).filter(k => !k.startsWith('_')).length === 0) {
    return {
      score: null,
      confidence: 0,
      contributors: [],
      categoryBreakdown: {},
      criticalZoneCount: 0,
      correlationAnalysis: {},
      consensusSignals: {},
      message: 'Aucun indicateur disponible'
    };
  }
  
  const categoryScores = {};
  const categoryWeights = {};
  const categoryContributors = {};
  const correlationAnalysis = {};
  const consensusSignals = {};
  let totalCriticalZone = 0;
  
  // Initialiser les catégories V2
  Object.keys(INDICATOR_CATEGORIES_V2).forEach(categoryKey => {
    categoryScores[categoryKey] = 0;
    categoryWeights[categoryKey] = 0;
    categoryContributors[categoryKey] = [];
  });
  
  // Classer et traiter chaque indicateur
  Object.entries(indicators).forEach(([key, data]) => {
    if (key.startsWith('_') || !data || typeof data !== 'object') {
      return;
    }
    
    const indicatorName = data.name || key;
    const classification = classifyIndicatorV2(indicatorName);
    
    let rawValue = data.value_numeric || data.value || 0;
    if (typeof rawValue !== 'number') {
      debugLogger.warn(`⚠️ Invalid numeric value for ${indicatorName}: ${rawValue}`);
      return;
    }

    // Special handling for problematic indicators with extreme values
    if (indicatorName.includes('Coin Days Destroyed')) {
      // CDD on 90d → score 0..100 by percentile (approximate normalization)
      rawValue = Math.min(100, Math.max(0, (rawValue / 20000000) * 100)); // Rough scaling
    } else if (indicatorName.includes('Jours depuis halving')) {
      // Days since halving → 0..100 on [0..1460] (≈ 4 years)
      rawValue = Math.min(100, Math.max(0, (rawValue / 1460) * 100));
    }

    const normalizedScore = normalizeAndInvertScoreV2(rawValue, classification);
    const indicatorWeight = classification.weight * classification.categoryWeight;
    
    if (data.in_critical_zone) {
      totalCriticalZone++;
    }
    
    // Ajouter aux contributeurs de catégorie
    const category = classification.category;
    categoryContributors[category].push({
      name: indicatorName,
      originalValue: rawValue,
      normalizedScore: normalizedScore,
      weight: indicatorWeight,
      contribution: normalizedScore * indicatorWeight,
      inCriticalZone: data.in_critical_zone || false,
      classification: classification,
      raw_threshold: data.raw_threshold
    });
  });
  
  // Appliquer la réduction de corrélation par catégorie
  Object.keys(categoryContributors).forEach(categoryKey => {
    const indicators = categoryContributors[categoryKey];
    if (indicators.length === 0) return;
    
    const reducedIndicators = applyCorrelationReduction(indicators, categoryKey);
    
    // Calculer le consensus pour la catégorie
    const consensus = calculateCategoryConsensus(reducedIndicators);
    consensusSignals[categoryKey] = consensus;
    
    // Calculer le score de catégorie avec les poids ajustés
    let categoryScore = 0;
    let categoryWeight = 0;
    
    reducedIndicators.forEach(indicator => {
      categoryScore += indicator.normalizedScore * indicator.weight;
      categoryWeight += indicator.weight;
    });
    
    if (categoryWeight > 0) {
      categoryScores[categoryKey] = categoryScore / categoryWeight;
      categoryWeights[categoryKey] = categoryWeight;
    }
    
    // Analyse de corrélation
    correlationAnalysis[categoryKey] = {
      original_count: indicators.length,
      reduced_count: reducedIndicators.length,
      correlation_reduction: indicators.length > reducedIndicators.length,
      weight_adjustment: reducedIndicators.filter(ind => ind.correlationReduction).length
    };
  });
  
  // Calculer le score final avec les poids de catégorie (statiques ou dynamiques)
  let finalScore = 0;
  let totalWeight = 0;
  const categoryBreakdown = {};
  
  // Calcul préliminaire pour obtenir un score approximatif (nécessaire pour la pondération dynamique)
  let preliminaryScore = 0;
  let preliminaryWeight = 0;
  
  Object.entries(categoryScores).forEach(([category, score]) => {
    const weight = categoryWeights[category];
    if (weight > 0) {
      const categoryWeight = INDICATOR_CATEGORIES_V2[category].weight;
      preliminaryScore += score * categoryWeight;
      preliminaryWeight += categoryWeight;
    }
  });
  
  const preliminaryCompositeScore = preliminaryWeight > 0 ? preliminaryScore / preliminaryWeight : 50;
  
  // Déterminer les poids finaux (statiques ou dynamiques)
  let finalCategoryWeights = {};
  let dynamicWeightingResult = null;
  let marketContext = null;
  
  if (useDynamicWeighting) {
    // Détecter le contexte de marché
    marketContext = detectMarketContext(categoryBreakdown, indicators);
    
    // Ajouter les contradictions au contexte
    const contradictions = analyzeContradictorySignals(categoryBreakdown);
    marketContext.contradictions = contradictions;
    
    // Calculer les poids dynamiques
    dynamicWeightingResult = calculateDynamicWeights(preliminaryCompositeScore, marketContext);
    finalCategoryWeights = dynamicWeightingResult.weights;
    
    console.debug(`🤖 Dynamic weighting applied: ${dynamicWeightingResult.phase.name} phase`);
  } else {
    // Utiliser les poids statiques standard
    Object.keys(categoryScores).forEach(category => {
      finalCategoryWeights[category] = INDICATOR_CATEGORIES_V2[category].weight;
    });
  }
  
  // Calcul final avec les poids déterminés
  Object.entries(categoryScores).forEach(([category, score]) => {
    const weight = categoryWeights[category];
    if (weight > 0) {
      const categoryWeight = finalCategoryWeights[category] || INDICATOR_CATEGORIES_V2[category].weight;
      
      finalScore += score * categoryWeight;
      totalWeight += categoryWeight;
      
      categoryBreakdown[category] = {
        score: Math.round(score),
        weight: categoryWeight,
        staticWeight: INDICATOR_CATEGORIES_V2[category].weight, // Pour comparaison
        contributorsCount: categoryContributors[category].length,
        description: INDICATOR_CATEGORIES_V2[category].description,
        color: INDICATOR_CATEGORIES_V2[category].color,
        contributors: categoryContributors[category].sort((a, b) => b.contribution - a.contribution),
        consensus: consensusSignals[category],
        correlationAnalysis: correlationAnalysis[category]
      };
    }
  });
  
  if (totalWeight === 0) {
    return {
      score: null,
      confidence: 0,
      contributors: [],
      categoryBreakdown: {},
      criticalZoneCount: 0,
      correlationAnalysis: {},
      consensusSignals: {},
      message: 'Aucun indicateur réel disponible pour calculer le score composite'
    };
  }
  
  const compositeScore = finalScore / totalWeight;
  
  // Calculer la confiance basée sur le consensus par catégorie
  const avgConsensusConfidence = Object.values(consensusSignals)
    .reduce((sum, consensus) => sum + (consensus.confidence || 0), 0) / 
    Object.keys(consensusSignals).length;
  
  const totalIndicators = Object.values(categoryContributors).flat().length;
  const activeCategories = Object.keys(categoryBreakdown).length;
  
  // Confiance composite : consensus + diversité + volume
  const confidence = Math.min(0.95, 
    (avgConsensusConfidence / 100) * 0.4 +  // 40% basé sur le consensus
    (activeCategories / 4) * 0.3 +          // 30% basé sur la diversité
    Math.min(totalIndicators / 20, 1) * 0.3 // 30% basé sur le volume
  );
  
  const allContributors = Object.values(categoryContributors).flat();
  
  const result = {
    score: Math.round(compositeScore),
    confidence: Math.round(confidence * 100) / 100,
    contributors: allContributors.sort((a, b) => b.contribution - a.contribution),
    categoryBreakdown: categoryBreakdown,
    criticalZoneCount: totalCriticalZone,
    totalIndicators: totalIndicators,
    activeCategories: activeCategories,
    correlationAnalysis: correlationAnalysis,
    consensusSignals: consensusSignals,
    version: useDynamicWeighting ? 'V2-Dynamic' : 'V2',
    improvements: [
      'Gestion des corrélations',
      'Consensus voting par catégorie',
      'Réduction de surpondération',
      'Confiance composite avancée'
    ],
    message: `Score composite V2: ${totalIndicators} indicateurs dans ${activeCategories} catégories (${totalCriticalZone} critiques)`
  };
  
  // Ajouter les informations de pondération dynamique si utilisée
  if (useDynamicWeighting && dynamicWeightingResult) {
    result.dynamicWeighting = {
      phase: dynamicWeightingResult.phase,
      weights: dynamicWeightingResult.weights,
      adjustments: dynamicWeightingResult.adjustments,
      reasoning: dynamicWeightingResult.reasoning,
      weightComparison: compareWeightingMethods(compositeScore, marketContext || {})
    };
    
    result.improvements.push('Pondération dynamique contextuelle');
    result.message += ` | Phase: ${dynamicWeightingResult.phase.name}`;
  }
  
  return result;
}

/**
 * Analyse les signaux contradictoires entre catégories
 */
export function analyzeContradictorySignals(categoryBreakdown) {
  const signals = [];
  const categories = Object.entries(categoryBreakdown);
  
  for (let i = 0; i < categories.length; i++) {
    for (let j = i + 1; j < categories.length; j++) {
      const [cat1Name, cat1Data] = categories[i];
      const [cat2Name, cat2Data] = categories[j];
      
      const consensus1 = cat1Data.consensus?.consensus || 'neutral';
      const consensus2 = cat2Data.consensus?.consensus || 'neutral';
      
      // Détecter les contradictions
      if ((consensus1 === 'bullish' && consensus2 === 'bearish') ||
          (consensus1 === 'bearish' && consensus2 === 'bullish')) {
        
        signals.push({
          type: 'contradiction',
          category1: { name: cat1Name, signal: consensus1, confidence: cat1Data.consensus.confidence },
          category2: { name: cat2Name, signal: consensus2, confidence: cat2Data.consensus.confidence },
          severity: Math.abs(cat1Data.score - cat2Data.score),
          recommendation: 'Attendre confirmation ou privilégier la catégorie avec plus haute confiance'
        });
      }
    }
  }
  
  return signals;
}

/**
 * Cache intelligent pour le score composite avec TTL adaptatif
 */
export class CompositeScoreCache {
  constructor() {
    this.cache = new Map();
  }
  
  getKey(indicators) {
    // Créer une clé basée sur les indicateurs et leurs valeurs
    const keyData = Object.entries(indicators)
      .filter(([key]) => !key.startsWith('_'))
      .map(([key, data]) => `${key}:${data.value_numeric}`)
      .sort()
      .join('|');
    
    return btoa(keyData).substring(0, 16); // Hash court
  }
  
  get(indicators) {
    const key = this.getKey(indicators);
    const entry = this.cache.get(key);
    
    if (!entry) return null;
    
    const age = Date.now() - entry.timestamp;
    if (age > CACHE_CONFIG.composite_score_ttl) {
      this.cache.delete(key);
      return null;
    }
    
    return entry.data;
  }
  
  set(indicators, compositeScore) {
    const key = this.getKey(indicators);
    this.cache.set(key, {
      data: compositeScore,
      timestamp: Date.now()
    });
    
    // Nettoyage automatique si trop d'entrées
    if (this.cache.size > 50) {
      const oldestKey = this.cache.keys().next().value;
      this.cache.delete(oldestKey);
    }
  }
}

// Instance globale du cache
export const compositeScoreCache = new CompositeScoreCache();
