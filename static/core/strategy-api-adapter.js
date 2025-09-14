// Strategy API Adapter - Migration PR-C
// Adaptateur pour migrer progressivement de calculateIntelligentDecisionIndex vers /api/strategy/*
// Garde la compatibilité ascendante tout en utilisant le backend unifié

import { store } from './risk-dashboard-store.js';

// Configuration de migration avec feature flags
const MIGRATION_CONFIG = {
  enabled: true,  // Feature flag principal
  strategy_template: 'balanced',  // Template par défaut
  fallback_on_error: true,  // Fallback vers logique frontend si API échoue
  cache_ttl_ms: 60000,  // Cache 1 minute
  api_timeout_ms: 3000,  // Timeout API 3s
  debug_mode: false  // Logs de debug
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
    
    // Appeler l'API Strategy
    const strategyResult = await getStrategyFromAPI(templateId);
    
    // Convertir au format legacy
    const legacyResult = convertStrategyResultToLegacyFormat(strategyResult, context);
    
    // Mettre en cache
    _strategyCache = {
      timestamp: now,
      data: legacyResult,
      template: templateId
    };
    
    debugLog('Strategy API successful, returning converted result');
    return legacyResult;
    
  } catch (error) {
    console.warn('Strategy API failed, using fallback:', error.message);
    
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
    console.warn('Failed to fetch strategy templates:', error.message);
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
    console.warn('Failed to compare templates:', error.message);
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

// Export pour compatibilité ascendante
export { calculateIntelligentDecisionIndexAPI as calculateIntelligentDecisionIndex };