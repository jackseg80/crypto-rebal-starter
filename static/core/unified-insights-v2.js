// Unified Insights V2 - Migration vers Strategy API (PR-C)
// Nouvelle version qui utilise l'API Strategy tout en gardant la compatibilité
// Remplace progressivement unified-insights.js

import { store } from './risk-dashboard-store.js';
import { getRegimeDisplayData, getMarketRegime } from '../modules/market-regimes.js';
import { estimateCyclePosition, getCyclePhase } from '../modules/cycle-navigator.js';
import { interpretCCS } from '../modules/signals-engine.js';
import { analyzeContradictorySignals } from '../modules/composite-score-v2.js';
import { calculateIntelligentDecisionIndexAPI, StrategyConfig } from './strategy-api-adapter.js';

// Import de fallback vers l'ancienne version si nécessaire
import { calculateIntelligentDecisionIndex as legacyCalculation } from './unified-insights.js';

// Lightweight helpers (conservés pour compatibilité)
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const pct = (x) => Math.round(clamp01(x) * 100);
const colorForScore = (s) => s > 70 ? 'var(--danger)' : s >= 40 ? 'var(--warning)' : 'var(--success)';

// Debug flag pour comparaison legacy vs API
const ENABLE_COMPARISON_LOGGING = false;

/**
 * Version améliorée de getUnifiedState qui utilise l'API Strategy
 * Garde la même interface pour la compatibilité ascendante
 */
export async function getUnifiedState() {
  const state = store.snapshot();

  // Extract base scores (identique à la version legacy)
  const onchainScore = state.scores?.onchain ?? null;
  const riskScore = state.scores?.risk ?? null;
  const blendedScore = state.scores?.blended ?? null;
  const ocMeta = state.scores?.onchain_metadata || {};
  const risk = state.risk?.risk_metrics || {};

  console.debug('🧠 UNIFIED STATE V2 - Using Strategy API + sophisticated modules');

  // 1. CYCLE INTELLIGENCE (conservé identique)
  let cycleData;
  try {
    cycleData = estimateCyclePosition();
    console.debug('✅ Cycle Intelligence loaded:', cycleData.phase?.phase, cycleData.score);
  } catch (error) {
    console.warn('⚠️ Cycle Intelligence fallback:', error);
    cycleData = {
      months: state.cycle?.months ?? null,
      score: Math.round(state.cycle?.ccsStar ?? state.cycle?.score ?? 50),
      phase: state.cycle?.phase || getCyclePhase(state.cycle?.months ?? 0),
      confidence: 0.3,
      multipliers: {}
    };
  }

  // 2. REGIME INTELLIGENCE (conservé identique)
  let regimeData;
  try {
    if (blendedScore != null) {
      regimeData = getRegimeDisplayData(blendedScore, onchainScore, riskScore);
      console.debug('✅ Regime Intelligence loaded:', regimeData.regime?.name, regimeData.recommendations?.length);
    } else {
      regimeData = { regime: getMarketRegime(50), recommendations: [], risk_budget: null };
    }
  } catch (error) {
    console.warn('⚠️ Regime Intelligence fallback:', error);
    regimeData = { regime: { name: 'Unknown', emoji: '❓' }, recommendations: [], risk_budget: null };
  }

  // 3. SIGNALS INTELLIGENCE (conservé identique pour compatibilité)
  let signalsData;
  let sentimentData = null;
  
  try {
    const globalConfig = window.globalConfig;
    if (globalConfig) {
      const apiBaseUrl = globalConfig.get('api_base_url') || 'http://127.0.0.1:8000';
      const sentimentResponse = await fetch(`${apiBaseUrl}/api/ml/sentiment/symbol/BTC?days=1`);
      if (sentimentResponse.ok) {
        const sentimentResult = await sentimentResponse.json();
        if (sentimentResult.success && sentimentResult.aggregated_sentiment) {
          const fearGreedSource = sentimentResult.aggregated_sentiment.source_breakdown?.fear_greed;
          if (fearGreedSource) {
            const fearGreedValue = Math.max(0, Math.min(100, Math.round(50 + (fearGreedSource.average_sentiment * 50))));
            sentimentData = {
              value: fearGreedValue,
              sources: sentimentResult.sources_used || [],
              interpretation: fearGreedValue < 25 ? 'extreme_fear' : fearGreedValue < 45 ? 'fear' : fearGreedValue < 55 ? 'neutral' : fearGreedValue < 75 ? 'greed' : 'extreme_greed'
            };
            console.debug('✅ Multi-source sentiment loaded:', sentimentData.sources, fearGreedValue);
          }
        }
      }
    }
  } catch (e) {
    console.warn('⚠️ Multi-source sentiment fallback to store data');
  }
  
  try {
    const ccsInterpretation = interpretCCS(typeof blendedScore === 'number' ? blendedScore : 50);
    signalsData = {
      interpretation: ccsInterpretation?.label?.toLowerCase?.() || 'neutral',
      confidence: 0.6,
      signals_strength: 'medium',
      ccs_level: ccsInterpretation?.level || 'medium',
      ccs_color: ccsInterpretation?.color
    };

    if (sentimentData && ['extreme_fear', 'extreme_greed'].includes(sentimentData.interpretation)) {
      signalsData.interpretation = sentimentData.interpretation;
      signalsData.confidence = 0.8;
      signalsData.signals_strength = 'strong';
    }
    
    console.debug('✅ Signals Intelligence loaded:', signalsData.interpretation, signalsData.confidence);
  } catch (error) {
    console.warn('⚠️ Signals Intelligence fallback:', error);
    signalsData = { interpretation: 'neutral', confidence: 0.4, signals_strength: 'weak' };
  }

  // 4. NOUVELLE LOGIQUE - DECISION INDEX VIA STRATEGY API
  let decision;
  try {
    // Préparer le contexte pour l'API Strategy
    const context = {
      blendedScore,
      cycleData,
      regimeData,  
      signalsData,
      onchainScore,
      onchainConfidence: ocMeta?.confidence ?? 0,
      riskScore,
      contradiction: ocMeta?.contradictory_signals?.length > 0 ? 0.3 : 0.1
    };
    
    // Utiliser l'adaptateur Strategy API
    decision = await calculateIntelligentDecisionIndexAPI(context);
    
    console.debug('🚀 Strategy API decision:', {
      score: decision.score,
      confidence: decision.confidence,
      source: decision.source,
      template: decision.template_used
    });
    
    // Comparaison avec legacy pour validation (si activé)
    if (ENABLE_COMPARISON_LOGGING) {
      try {
        const legacyDecision = legacyCalculation(context);
        console.debug('📊 Legacy vs API comparison:', {
          legacy_score: legacyDecision.score,
          api_score: decision.score,
          difference: Math.abs(legacyDecision.score - decision.score),
          legacy_confidence: legacyDecision.confidence,
          api_confidence: decision.confidence
        });
      } catch (e) {
        console.debug('⚠️ Legacy comparison failed:', e.message);
      }
    }
    
  } catch (error) {
    console.warn('⚠️ Strategy API failed, using legacy fallback:', error.message);
    
    // Fallback vers calcul legacy en cas d'erreur API
    const context = {
      blendedScore, cycleData, regimeData, signalsData,
      onchainScore, onchainConfidence: ocMeta?.confidence ?? 0, riskScore
    };
    decision = legacyCalculation(context);
  }

  // 5. SOPHISTICATED ANALYSIS (conservé identique)
  const ocCategories = ocMeta.categoryBreakdown || {};
  const drivers = Object.entries(ocCategories)
    .map(([key, data]) => ({ 
      key, 
      score: data?.score ?? 0, 
      desc: data?.description, 
      contributors: data?.contributorsCount ?? 0,
      consensus: data?.consensus
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);

  // INTELLIGENT CONTRADICTIONS ANALYSIS (conservé)
  let contradictions = [];
  try {
    contradictions = analyzeContradictorySignals(ocCategories).slice(0, 2);
    console.debug('✅ Contradictions Intelligence loaded:', contradictions.length);
  } catch (error) {
    contradictions = (state.scores?.contradictory_signals || []).slice(0, 2);
    console.warn('⚠️ Contradictions fallback:', error);
  }

  // ENHANCED HEALTH (conservé + ajout info Strategy API)
  const health = {
    backend: state.ui?.apiStatus?.backend || 'unknown',
    signals: state.ui?.apiStatus?.signals || 'unknown',
    lastUpdate: state.ccs?.lastUpdate || null,
    intelligence_modules: {
      cycle: cycleData.confidence > 0.5 ? 'active' : 'limited',
      regime: regimeData.recommendations?.length > 0 ? 'active' : 'limited', 
      signals: signalsData.confidence > 0.6 ? 'active' : 'limited',
      strategy_api: decision.source === 'strategy_api' ? 'active' : 'fallback'  // NOUVEAU
    }
  };

  // Adjust decision confidence (conservé)
  try {
    const contraPenalty = Math.min((contradictions?.length || 0) * 0.05, 0.15);
    if (typeof decision.confidence === 'number') {
      decision.confidence = Math.max(0, Math.min(0.95, decision.confidence - contraPenalty));
    }
  } catch {}

  // RETURN ENHANCED UNIFIED STATE
  const unifiedState = {
    decision,
    cycle: {
      months: cycleData.months,
      score: Math.round(cycleData.score ?? 50),
      weight: state.cycle?.weight ?? 0.3,
      phase: cycleData.phase,
      confidence: cycleData.confidence,
      multipliers: cycleData.multipliers
    },
    onchain: {
      score: onchainScore != null ? Math.round(onchainScore) : null,
      confidence: Math.round((ocMeta.confidence ?? 0) * 100) / 100,
      drivers,
      criticalCount: ocMeta.criticalZoneCount || 0,
    },
    risk: {
      score: riskScore != null ? Math.round(riskScore) : null,
      sharpe: risk?.sharpe_ratio ?? null,
      volatility: risk?.volatility_annualized ?? risk?.volatility ?? null,
      var95_1d: risk?.var_95_1d ?? risk?.var95_1d ?? null,
      budget: regimeData.risk_budget
    },
    regime: {
      name: regimeData.regime?.name,
      emoji: regimeData.regime?.emoji,
      confidence: regimeData.regime?.confidence,
      strategy: regimeData.regime?.strategy,
      recommendations: regimeData.recommendations || []
    },
    signals: {
      interpretation: signalsData.interpretation,
      confidence: signalsData.confidence,
      strength: signalsData.signals_strength,
      sentiment: sentimentData
    },
    contradictions,
    health,
    
    // NOUVELLES DONNÉES STRATEGY API
    strategy: {
      enabled: StrategyConfig.getConfig().enabled,
      template_used: decision.template_used || null,
      policy_hint: decision.policy_hint || 'Normal',
      targets: decision.targets || [],
      api_version: decision.api_version || null,
      generated_at: decision.generated_at || null
    },
    
    // Intelligence metadata (conservé + enrichi)
    intelligence: {
      cycleData,
      regimeData,
      regimeRecommendations: regimeData.recommendations,
      signalsData,
      sentimentData,
      version: 'v2',  // NOUVEAU
      migration_status: decision.source === 'strategy_api' ? 'migrated' : 'legacy'  // NOUVEAU
    }
  };
  
  return unifiedState;
}

/**
 * Dérivation des recommandations (conservée identique pour compatibilité)
 */
export function deriveRecommendations(u) {
  console.debug('🧠 DERIVING INTELLIGENT RECOMMENDATIONS V2');
  
  let recos = [];

  // 1. USE STRATEGY API TARGETS si disponibles
  if (u.strategy?.targets?.length > 0) {
    const primaryTarget = u.strategy.targets.reduce((max, target) => 
      target.weight > max.weight ? target : max
    );
    
    recos.push({
      priority: 'high',
      title: `Allocation ${primaryTarget.symbol}: ${Math.round(primaryTarget.weight * 100)}%`,
      reason: primaryTarget.rationale || `Suggestion ${u.strategy.template_used}`,
      icon: '🎯',
      source: 'strategy-api'
    });
  }

  // 2. USE REGIME RECOMMENDATIONS (conservé)
  if (u.intelligence?.regimeRecommendations?.length > 0) {
    u.intelligence.regimeRecommendations.forEach(rec => {
      recos.push({
        priority: rec.priority || 'medium',
        title: rec.message || rec.title || rec.action,
        reason: rec.action || rec.message || 'Recommandation du régime de marché',
        icon: rec.type === 'warning' ? '⚠️' : rec.type === 'alert' ? '🚨' : '💡',
        source: 'regime-intelligence'
      });
    });
  }

  // 3. CYCLE-BASED RECOMMENDATIONS (conservé)
  if (u.cycle?.phase?.phase) {
    const phase = u.cycle.phase.phase;
    if (phase === 'peak' && u.decision.score > 75) {
      recos.push({
        priority: 'high',
        title: 'Prendre des profits progressifs',
        reason: `Phase ${u.cycle.phase.description} + Score élevé`,
        icon: '📈',
        source: 'cycle-intelligence'
      });
    } else if (phase === 'accumulation' && u.decision.score < 40) {
      recos.push({
        priority: 'medium',
        title: 'Accumuler positions de qualité',
        reason: `Phase ${u.cycle.phase.description} + Score bas`,
        icon: '🔵',
        source: 'cycle-intelligence'
      });
    }
  }

  // 4. STRATEGY API POLICY HINTS (NOUVEAU)
  if (u.strategy?.policy_hint) {
    const policyHint = u.strategy.policy_hint;
    if (policyHint === 'Slow') {
      recos.push({
        priority: 'medium',
        title: 'Approche prudente recommandée',
        reason: 'Signaux contradictoires ou confiance faible détectée',
        icon: '🐌',
        source: 'strategy-api-policy'
      });
    } else if (policyHint === 'Aggressive') {
      recos.push({
        priority: 'high', 
        title: 'Opportunité d\'allocation agressive',
        reason: 'Score élevé et signaux cohérents',
        icon: '⚡',
        source: 'strategy-api-policy'
      });
    }
  }

  // 5. CONTRADICTION ALERTS (conservé)
  if (u.contradictions?.length > 0) {
    recos.push({
      priority: 'medium',
      title: 'Signaux contradictoires détectés',
      reason: `${u.contradictions.length} divergence(s) entre modules`,
      icon: '⚡',
      source: 'contradiction-analysis'
    });
  }

  // 6. RISK BUDGET RECOMMENDATIONS (conservé)
  if (u.risk?.budget?.stables_allocation > 0.4) {
    recos.push({
      priority: 'medium',
      title: `Allocation stables: ${u.risk.budget.percentages?.stables}%`,
      reason: 'Budget de risque calculé par algorithme sophistiqué',
      icon: '🛡️',
      source: 'risk-budget'
    });
  }

  console.debug('🎯 Recommendations derived:', recos.length, 'from', [...new Set(recos.map(r => r.source))].join(', '));
  return recos;
}

// Exports pour compatibilité
export { calculateIntelligentDecisionIndexAPI as calculateIntelligentDecisionIndex };
export { clamp01, pct, colorForScore };  // Utilitaires conservés