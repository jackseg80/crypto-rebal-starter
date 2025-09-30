// Strategy API Adapter - Migration PR-C
// Adaptateur pour migrer progressivement de calculateIntelligentDecisionIndex vers /api/strategy/*
// Garde la compatibilité ascendante tout en utilisant le backend unifié

import { store } from './risk-dashboard-store.js';
import { calculateHierarchicalAllocation } from './allocation-engine.js';
import { GROUP_ORDER, getAssetGroup } from '../shared-asset-groups.js';

// Configuration de migration avec feature flags
const MIGRATION_CONFIG = {
  enabled: true,  // Feature flag principal
  strategy_template: 'balanced',  // Template par défaut
  fallback_on_error: true,  // Fallback vers logique frontend si API échoue
  cache_ttl_ms: 60000,  // Cache 1 minute
  api_timeout_ms: 3000,  // Timeout API 3s
  debug_mode: true,  // Logs de debug ACTIVÉS pour voir V2 en action

  // NOUVEAU - Configuration Allocation Engine V2
  allocation: {
    topdown_v2: true,  // Feature flag pour allocation hiérarchique
    respect_incumbency: true,  // Protection positions détenues
    enable_floors: true  // Floors contextuels activés
  }
};

// Cache simple pour éviter appels répétés
let _strategyCache = { timestamp: 0, data: null, template: null };

// Helper fetch avec timeout
async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), MIGRATION_CONFIG.api_timeout_ms);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
    clearTimeout(timeout);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    clearTimeout(timeout);
    throw error;
  }
}

// Obtenir l'URL de base API
function getApiBaseUrl() {
  const hasGlobalConfig = !!window.globalConfig;
  const apiBaseUrl = hasGlobalConfig ? 
    (window.globalConfig.get?.('api_base_url') || window.globalConfig.get?.('base_url')) : 
    null;
  const finalUrl = apiBaseUrl || window.location.origin;
  
  if (MIGRATION_CONFIG.debug_mode) {
    console.debug('[StrategyAdapter] getApiBaseUrl:', {
      hasGlobalConfig,
      apiBaseUrl,
      finalUrl,
      origin: window.location.origin
    });
  }
  
  return finalUrl;
}

// Logger conditionnel pour debug
function debugLog(...args) {
  if (MIGRATION_CONFIG.debug_mode) {
    console.debug('[StrategyAdapter]', ...args);
  }
}

/**
 * Appelle l'API Strategy pour obtenir une suggestion d'allocation
 * @param {string} templateId - Template à utiliser (balanced, conservative, aggressive)
 * @param {object} customWeights - Poids custom optionnels
 * @returns {Promise<object>} Résultat strategy API
 */
async function getStrategyFromAPI(templateId = 'balanced', customWeights = null) {
  const baseUrl = getApiBaseUrl().replace(/\/$/, '');
  const url = `${baseUrl}/api/strategy/preview`;
  
  const requestBody = {
    template_id: templateId,
    force_refresh: false  // Utiliser le cache backend
  };
  
  if (customWeights) {
    requestBody.custom_weights = customWeights;
  }
  
  debugLog('Calling strategy API:', url, requestBody);
  
  const result = await fetchWithTimeout(url, {
    method: 'POST',
    body: JSON.stringify(requestBody)
  });
  
  debugLog('Strategy API result:', result);
  return result;
}

/**
 * Convertit le résultat Strategy API vers le format legacy expectedu par le frontend
 * @param {object} strategyResult - Résultat de l'API Strategy
 * @param {object} contextData - Données contextuelles (scores, cycle, etc.)
 * @returns {object} Format compatible avec calculateIntelligentDecisionIndex
 */
function convertStrategyResultToLegacyFormat(strategyResult, contextData = {}) {
  return {
    // Format legacy pour compatibilité
    score: strategyResult.decision_score,
    color: getColorForScore(strategyResult.decision_score),
    confidence: strategyResult.confidence,
    reasoning: strategyResult.rationale.join(' • '),
    
    // Enrichissements pour les dashboards
    policy_hint: strategyResult.policy_hint,
    strategy_used: strategyResult.strategy_used,
    generated_at: strategyResult.generated_at,
    
    // Allocation targets (format adapté)
    targets: strategyResult.targets.map(target => ({
      symbol: target.symbol,
      weight: target.weight,
      weight_pct: Math.round(target.weight * 100),
      rationale: target.rationale
    })),
    
    // Metadata utiles
    source: 'strategy_api',
    api_version: 'v1',
    template_used: strategyResult.strategy_used
  };
}

/**
 * Détermine la couleur pour un score (compatible frontend)
 */
function getColorForScore(score) {
  if (score > 70) return 'var(--danger)';
  if (score >= 40) return 'var(--warning)';
  return 'var(--success)';
}

/**
 * Détermine le template à utiliser basé sur le contexte
 * @param {object} context - Contexte (scores, régime, etc.)
 * @returns {string} Template ID approprié
 */
function determineAppropriateTemplate(context = {}) {
  const riskScore = context.riskScore;
  const contradiction = context.contradiction || 0;
  
  // Logique adaptive pour choisir le template
  if (contradiction > 0.6) {
    return 'contradiction_averse';  // Contradictions élevées
  }
  
  if (riskScore && riskScore < 30) {
    return 'conservative';  // Risque faible = conservateur
  }
  
  if (riskScore && riskScore > 70) {
    return 'aggressive';  // Risque élevé = agressif
  }
  
  // Par défaut : balanced
  return MIGRATION_CONFIG.strategy_template;
}

/**
 * Adaptateur principal qui remplace calculateIntelligentDecisionIndex
 * Utilise l'API Strategy si activée, sinon fallback vers logique legacy
 * 
 * @param {object} context - Contexte legacy (blendedScore, cycleData, regimeData, etc.)
 * @returns {Promise<object>} Résultat au format legacy
 */
export async function calculateIntelligentDecisionIndexAPI(context) {
  // Si migration désactivée, utiliser fallback immédiatement
  if (!MIGRATION_CONFIG.enabled) {
    debugLog('Migration disabled, using fallback');
    return await fallbackToLegacyCalculation(context);
  }
  
  try {
    // Déterminer template approprié
    const templateId = determineAppropriateTemplate(context);
    
    // Vérifier le cache
    const now = Date.now();
    const cacheValid = (
      _strategyCache.data && 
      _strategyCache.template === templateId &&
      (now - _strategyCache.timestamp) < MIGRATION_CONFIG.cache_ttl_ms
    );
    
    if (cacheValid) {
      debugLog('Using cached strategy result');
      return _strategyCache.data;
    }
    
    // NOUVEAU - Utiliser Allocation Engine V2 si activé
    let finalResult;

    if (MIGRATION_CONFIG.allocation.topdown_v2) {
      debugLog('🏗️ Using Allocation Engine V2 for hierarchical allocation');

      // Récupérer positions actuelles depuis le store ou context
      const currentPositions = await getCurrentPositions();

      // Calculer allocation hiérarchique
      const v2Allocation = await calculateHierarchicalAllocation(
        {
          cycleScore: context.cycleData?.score ?? 50,
          onchainScore: context.onchainScore ?? 50,
          riskScore: context.riskScore ?? 50,
          adaptiveWeights: context.adaptiveWeights,
          risk_budget: extractRiskBudgetFromContext(context),
          contradiction: context.contradiction ?? 0,
          execution: { cap_pct_per_iter: (context?.execution?.cap_pct_per_iter ?? context?.governance_cap ?? 7) }
        },
        currentPositions,
        { enableV2: true }
      );

      if (v2Allocation) {
        // Succès V2 - convertir au format legacy
        finalResult = convertV2AllocationToLegacyFormat(v2Allocation, context);
        debugLog('✅ V2 allocation successful, converted to legacy format');
        debugLog('🔍 V2 allocation details:', v2Allocation);
        debugLog('🔍 Final result targets count:', finalResult.targets?.length || 0);
      } else {
        // Fallback API Strategy classique
        debugLog('⚠️ V2 allocation failed, fallback to API Strategy');
        debugLogger.warn('❌ V2 Allocation Engine returned null - checking reasons...');

        try {
          const strategyResult = await getStrategyFromAPI(templateId);
          finalResult = convertStrategyResultToLegacyFormat(strategyResult, context);
        } catch (apiError) {
          debugLogger.warn('⚠️ API Strategy also failed, using hardcoded fallback');
          // Fallback ultime: allocation hardcodée basée sur le cycle
          finalResult = createFallbackAllocation(context);
        }
      }
    } else {
      // V1 classique - API Strategy
      debugLog('Using classic API Strategy (V1)');
      const strategyResult = await getStrategyFromAPI(templateId);
      finalResult = convertStrategyResultToLegacyFormat(strategyResult, context);
    }
    
    // Mettre en cache
    _strategyCache = {
      timestamp: now,
      data: finalResult,
      template: templateId
    };

    debugLog('Strategy processing successful, returning result');
    return finalResult;
    
  } catch (error) {
    debugLogger.warn('Strategy API failed, using fallback:', error.message);
    
    // Fallback vers logique legacy si configuré
    if (MIGRATION_CONFIG.fallback_on_error) {
      return await fallbackToLegacyCalculation(context);
    } else {
      throw error;
    }
  }
}

/**
 * Fallback vers la logique legacy calculateIntelligentDecisionIndex
 */
async function fallbackToLegacyCalculation(context) {
  // Import dynamique pour éviter les cycles
  const { calculateIntelligentDecisionIndex } = await import('./unified-insights.js');
  return calculateIntelligentDecisionIndex(context);
}

/**
 * Obtient la liste des templates disponibles
 * @returns {Promise<object>} Templates disponibles
 */
export async function getAvailableStrategyTemplates() {
  try {
    const baseUrl = getApiBaseUrl().replace(/\/$/, '');
    const url = `${baseUrl}/api/strategy/templates`;
    
    const templates = await fetchWithTimeout(url);
    debugLog('Available templates:', Object.keys(templates));
    return templates;
    
  } catch (error) {
    debugLogger.warn('Failed to fetch strategy templates:', error.message);
    return {
      balanced: { name: 'Balanced', template: 'balanced', risk_level: 'medium' },
      conservative: { name: 'Conservative', template: 'conservative', risk_level: 'low' },
      aggressive: { name: 'Aggressive', template: 'aggressive', risk_level: 'high' }
    };
  }
}

/**
 * Compare plusieurs templates
 * @param {string[]} templateIds - IDs des templates à comparer
 * @returns {Promise<object>} Comparaisons
 */
export async function compareStrategyTemplates(templateIds = ['conservative', 'balanced', 'aggressive']) {
  try {
    const baseUrl = getApiBaseUrl().replace(/\/$/, '');
    const url = `${baseUrl}/api/strategy/compare`;
    
    const comparison = await fetchWithTimeout(url, {
      method: 'POST',
      body: JSON.stringify(templateIds)
    });
    
    debugLog('Template comparison:', comparison);
    return comparison;
    
  } catch (error) {
    debugLogger.warn('Failed to compare templates:', error.message);
    return { comparisons: {}, generated_at: new Date().toISOString() };
  }
}

/**
 * Configuration API pour les dashboards
 */
export const StrategyConfig = {
  // Activer/désactiver la migration
  setEnabled(enabled) {
    MIGRATION_CONFIG.enabled = enabled;
    _strategyCache = { timestamp: 0, data: null, template: null }; // Clear cache
    debugLog('Migration', enabled ? 'enabled' : 'disabled');
  },
  
  // Définir template par défaut
  setDefaultTemplate(templateId) {
    MIGRATION_CONFIG.strategy_template = templateId;
    _strategyCache = { timestamp: 0, data: null, template: null }; // Clear cache
    debugLog('Default template set to:', templateId);
  },
  
  // Activer/désactiver le debug
  setDebugMode(debug) {
    MIGRATION_CONFIG.debug_mode = debug;
    debugLog('Debug mode', debug ? 'enabled' : 'disabled');
  },
  
  // Obtenir la config actuelle
  getConfig() {
    return { ...MIGRATION_CONFIG };
  },
  
  // Clear cache
  clearCache() {
    _strategyCache = { timestamp: 0, data: null, template: null };
    debugLog('Cache cleared');
  }
};

/**
 * NOUVELLES FONCTIONS UTILITAIRES POUR V2
 */

/**
 * Récupère les positions actuelles du portefeuille
 */
async function getCurrentPositions() {
  try {
    // Essayer d'obtenir depuis le globalConfig ou API
    if (window.globalConfig) {
      const apiResponse = await window.globalConfig.apiRequest('/balances/current');
      return apiResponse?.items || [];
    }

    // Fallback: positions mockées pour développement
    console.debug('⚠️ Using mock positions for V2 allocation engine');
    return [
      { symbol: 'BTC', value_usd: 1000 },
      { symbol: 'ETH', value_usd: 800 },
      { symbol: 'SOL', value_usd: 300 },
      { symbol: 'USDC', value_usd: 1500 },
      { symbol: 'LINK', value_usd: 200 }
    ];
  } catch (error) {
    debugLogger.warn('Failed to get current positions:', error.message);
    return [];
  }
}

/**
 * Extrait le budget de risque depuis le contexte
 */
function extractRiskBudgetFromContext(context) {
  // SOURCE UNIQUE STABLES: priorité absolue à regimeData.risk_budget
  const targetStablesPct =
    context.regimeData?.risk_budget?.target_stables_pct ??
    context.regimeData?.risk_budget?.percentages?.stables ??
    (context.regimeData?.risk_budget?.stables_allocation != null
      ? Math.round(context.regimeData.risk_budget.stables_allocation * 100)
      : null
    );

  if (targetStablesPct == null) {
    console.debug('[adapter] missing target_stables_pct - check market-regimes pipeline');
  } else {
    console.debug('🎯 Single source stables target:', targetStablesPct + '%');
  }

  return {
    target_stables_pct: targetStablesPct,
    methodology: 'regime_based'
  };
}

/**
 * Convertit l'allocation V2 au format legacy
 */
function convertV2AllocationToLegacyFormat(v2Allocation, context) {
  const allocation = v2Allocation.allocation;

  // Conversion allocation vers targets format
  const targets = Object.entries(allocation).map(([asset, weight]) => ({
    symbol: asset,
    weight: weight,
    weight_pct: Math.round(weight * 100),
    rationale: `V2 engine allocation (${v2Allocation.metadata.phase} phase)`
  }));

  // Calculer decision score basé sur la cohérence
  const decisionScore = v2Allocation.metadata.total_check.isValid ? 65 : 45;

  return {
    score: decisionScore,
    color: getColorForScore(decisionScore),
    confidence: 0.8, // Bonne confiance avec V2
    reasoning: `V2 hierarchical allocation • ${v2Allocation.metadata.phase} phase • Floors applied`,

    // Données V2 spécifiques
    policy_hint: v2Allocation.execution.convergence_strategy === 'gradual' ? 'Slow' : 'Normal',
    strategy_used: 'topdown_v2',
    generated_at: new Date().toISOString(),

    // Allocation targets
    targets,

    // Metadata
    source: 'allocation_engine_v2',
    api_version: 'v2',
    template_used: 'hierarchical',
    governance_cap: v2Allocation.execution.cap_per_iter || 7,

    // Données d'exécution exposées
    execution_plan: {
      estimated_iters: v2Allocation.execution.estimated_iters_to_target,
      convergence_time: v2Allocation.execution.convergence_time_estimate
    }
  };
}

/**
 * Fallback ultime: créer une allocation basique quand tout échoue
 */
function createFallbackAllocation(context) {
  const cycleScore = context.cycleData?.score ?? 50;

  // Allocation basique selon le cycle
  let allocation;
  if (cycleScore >= 80) {
    // Bull market
    allocation = {
      'BTC': 30,
      'ETH': 25,
      'Stablecoins': 15,
      'SOL': 10,
      'L1/L0 majors': 10,
      'DeFi': 6,
      'L2/Scaling': 4
    };
  } else if (cycleScore >= 60) {
    // Modéré
    allocation = {
      'BTC': 35,
      'ETH': 25,
      'Stablecoins': 20,
      'SOL': 8,
      'L1/L0 majors': 7,
      'DeFi': 3,
      'L2/Scaling': 2
    };
  } else {
    // Bear/prudent
    allocation = {
      'BTC': 40,
      'ETH': 20,
      'Stablecoins': 30,
      'SOL': 4,
      'L1/L0 majors': 4,
      'DeFi': 1,
      'L2/Scaling': 1
    };
  }

  // Convertir en format targets
  const targets = Object.entries(allocation).map(([symbol, weight]) => ({
    symbol,
    weight: weight / 100,
    weight_pct: weight,
    rationale: `Fallback allocation (Cycle=${cycleScore})`
  }));

  return {
    score: Math.max(40, Math.min(80, cycleScore * 0.8)), // Score raisonnable
    confidence: 0.6, // Confiance modérée pour fallback
    reasoning: `Fallback allocation based on cycle score ${cycleScore}`,
    targets,
    source: 'fallback_hardcoded',
    template_used: 'fallback',
    generated_at: new Date().toISOString()
  };
}

/**
 * SOURCE UNIQUE - Construit les objectifs théoriques avec stables préservées
 * @param {object} u - État unifié (unifiedState)
 * @returns {object} Map { groupTopLevel -> % } de 11 entrées, somme ≈ 100
 */
export function buildTheoreticalTargets(u) {
  debugLogger.warn('🚨 buildTheoreticalTargets FONCTION OVERRIDE APPELÉE !', new Date().toISOString());

  // VERROUILLAGE STABLES: Utiliser source canonique pour cohérence parfaite
  if (u?.targets_by_group) {
    debugLogger.info('✅ STABLES VERROUILLÉES: Utilisation source canonique u.targets_by_group');
    console.debug('🔒 buildTheoreticalTargets source: CANONICAL_TARGETS_BY_GROUP', u.targets_by_group);
    return u.targets_by_group;
  }

  // FALLBACK: Logique artificielle si pas de source canonique (cas edge)
  const blendedScore = u?.scores?.blended || u?.decision?.score || 50;
  debugLogger.warn('⚠️ FALLBACK vers logique artificielle - targets_by_group manquant', { blendedScore });

  let stablesTarget, btcTarget, ethTarget, altsTarget;

  if (blendedScore >= 70) {
    // Euphorie: moins de stables, plus d'alts
    stablesTarget = 20; btcTarget = 35; ethTarget = 25; altsTarget = 20;
  } else if (blendedScore >= 50) {
    // Expansion: équilibré
    stablesTarget = 30; btcTarget = 40; ethTarget = 20; altsTarget = 10;
  } else {
    // Accumulation: beaucoup de stables, BTC dominante
    stablesTarget = 50; btcTarget = 30; ethTarget = 15; altsTarget = 5;
  }

  // Créer allocation théorique cohérente
  const artificialTargets = {
    'Stablecoins': stablesTarget,
    'BTC': btcTarget,
    'ETH': ethTarget,
    'SOL': altsTarget * 0.3,
    'L1/L0 majors': altsTarget * 0.4,
    'L2/Scaling': altsTarget * 0.2,
    'DeFi': altsTarget * 0.1,
    'AI/Data': 0,
    'Gaming/NFT': 0,
    'Memecoins': 0,
    'Others': 0
  };

  debugLogger.debug('🎯 FALLBACK TARGETS (buildTheoreticalTargets):', artificialTargets);
  console.debug('📊 buildTheoreticalTargets source: FALLBACK_REGIME_LOGIC', { blendedScore, regime: blendedScore >= 70 ? 'Euphoria' : blendedScore >= 50 ? 'Expansion' : 'Accumulation' });

  return artificialTargets;
}

// Export pour compatibilité ascendante
export { calculateIntelligentDecisionIndexAPI as calculateIntelligentDecisionIndex };
