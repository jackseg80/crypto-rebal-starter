// Unified Insights Aggregator - INTELLIGENT VERSION
// Connects all sophisticated modules for real intelligence

import { store } from '../core/risk-dashboard-store.js';
import { getRegimeDisplayData, getMarketRegime } from '../modules/market-regimes.js';
import { estimateCyclePosition, getCyclePhase } from '../modules/cycle-navigator.js';
import { interpretCCS } from '../modules/signals-engine.js';
import { analyzeContradictorySignals } from '../modules/composite-score-v2.js';

// Lightweight helpers
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const pct = (x) => Math.round(clamp01(x) * 100);
const colorForScore = (s) => s > 70 ? 'var(--danger)' : s >= 40 ? 'var(--warning)' : 'var(--success)';

// INTELLIGENT STATE AGGREGATION using sophisticated modules
export async function getUnifiedState() {
  const state = store.snapshot();

  // Extract base scores
  const onchainScore = state.scores?.onchain ?? null;
  const riskScore = state.scores?.risk ?? null;
  const blendedScore = state.scores?.blended ?? null;
  const ocMeta = state.scores?.onchain_metadata || {};
  const risk = state.risk?.risk_metrics || {};

  console.debug('🧠 INTELLIGENT UNIFIED STATE - Using sophisticated modules');

  // 1. CYCLE INTELLIGENCE - Use sophisticated cycle analysis
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

  // 2. REGIME INTELLIGENCE - Use sophisticated regime analysis
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

  // 3. SIGNALS INTELLIGENCE - Use CCS interpretation with multi-source sentiment
  let signalsData;
  let sentimentData = null;
  
  // Try to get multi-source sentiment data
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
            // Convert sentiment score (-1 to 1) to Fear & Greed Index (0-100)
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
  
  // Use CCS interpretation with enhanced sentiment
  try {
    signalsData = interpretCCS({
      ccs_score: blendedScore ?? 50,
      fear_greed: sentimentData?.value ?? state.ccs?.signals?.fear_greed?.value ?? null,
      btc_dominance: state.ccs?.signals?.btc_dominance?.value ?? null,
      funding_rate: state.ccs?.signals?.funding_rate?.value ?? null
    });
    
    // Enhance with multi-source data
    if (sentimentData) {
      signalsData.fear_greed = sentimentData;
      signalsData.interpretation = sentimentData.interpretation;
    }
    
    console.debug('✅ Signals Intelligence loaded:', signalsData.interpretation);
  } catch (error) {
    console.warn('⚠️ Signals Intelligence fallback:', error);
    signalsData = { 
      interpretation: sentimentData?.interpretation || 'neutral', 
      confidence: 0.5, 
      signals_strength: 'medium',
      fear_greed: sentimentData || null
    };
  }

  // 4. SOPHISTICATED DECISION INDEX - Context-aware calculation
  const decision = calculateIntelligentDecisionIndex({
    blendedScore,
    cycleData,
    regimeData,
    signalsData,
    onchainScore,
    riskScore
  });

  // 5. SOPHISTICATED ANALYSIS - Use advanced modules
  const ocCategories = ocMeta.categoryBreakdown || {};
  const drivers = Object.entries(ocCategories)
    .map(([key, data]) => ({ 
      key, 
      score: data?.score ?? 0, 
      desc: data?.description, 
      contributors: data?.contributorsCount ?? 0,
      consensus: data?.consensus // From Composite Score V2
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);

  // INTELLIGENT CONTRADICTIONS ANALYSIS
  let contradictions = [];
  try {
    contradictions = analyzeContradictorySignals(ocCategories).slice(0, 2);
    console.debug('✅ Contradictions Intelligence loaded:', contradictions.length);
  } catch (error) {
    contradictions = (state.scores?.contradictory_signals || []).slice(0, 2);
    console.warn('⚠️ Contradictions fallback:', error);
  }

  // ENHANCED HEALTH with intelligence status
  const health = {
    backend: state.ui?.apiStatus?.backend || 'unknown',
    signals: state.ui?.apiStatus?.signals || 'unknown',
    lastUpdate: state.ccs?.lastUpdate || null,
    intelligence_modules: {
      cycle: cycleData.confidence > 0.5 ? 'active' : 'limited',
      regime: regimeData.recommendations?.length > 0 ? 'active' : 'limited', 
      signals: signalsData.confidence > 0.6 ? 'active' : 'limited'
    }
  };

  // RETURN INTELLIGENT UNIFIED STATE
  return {
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
      allocation_bias: regimeData.regime?.allocation_bias,
      overrides: regimeData.regime?.overrides || []
    },
    sentiment: {
      fearGreed: signalsData.fear_greed?.value ?? null,
      sources: signalsData.fear_greed?.sources ?? null,
      regime: regimeData.regime?.name || state.market?.regime?.regime?.name || null,
      interpretation: signalsData.interpretation,
      strength: signalsData.signals_strength
    },
    contradictions,
    health,
    intelligence: {
      regimeRecommendations: regimeData.recommendations || [],
      allocation: regimeData.allocation || {},
      cycleMultipliers: cycleData.multipliers || {},
      signalsInterpretation: signalsData
    }
  };
}

// INTELLIGENT DECISION INDEX calculation
function calculateIntelligentDecisionIndex({ blendedScore, cycleData, regimeData, signalsData, onchainScore, riskScore }) {
  let finalScore;
  let confidence = 0.5;
  let reasoning = [];

  // Use blended if available (most sophisticated)
  if (blendedScore != null) {
    finalScore = Math.round(blendedScore);
    confidence = 0.85;
    reasoning.push('Blended Score disponible (méthode sophistiquée)');
  } else {
    // Intelligent fallback using modules
    const cycleScore = cycleData?.score ?? 50;
    const onScore = onchainScore ?? 50;
    const riskAdjusted = 100 - (riskScore ?? 50);
    
    // Dynamic weighting based on confidence
    const cycleWeight = (cycleData?.confidence ?? 0.3) * 0.4;
    const onchainWeight = 0.35;
    const riskWeight = 0.25;
    
    finalScore = Math.round(cycleScore * cycleWeight + onScore * onchainWeight + riskAdjusted * riskWeight);
    confidence = 0.6;
    reasoning.push('Calcul intelligent avec pondération dynamique');
  }

  // Context adjustments
  if (regimeData?.regime?.overrides?.length > 0) {
    reasoning.push(`Ajustements contextuels: ${regimeData.regime.overrides.length} overrides`);
    confidence += 0.1;
  }

  return {
    score: finalScore,
    color: colorForScore(finalScore),
    confidence: Math.min(confidence, 0.95),
    reasoning: reasoning.join(' • ')
  };
}

// SOPHISTICATED RECOMMENDATIONS using all modules intelligence
export function deriveRecommendations(u) {
  console.debug('🧠 DERIVING INTELLIGENT RECOMMENDATIONS');
  
  let recos = [];

  // 1. USE REGIME RECOMMENDATIONS (most sophisticated)
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

  // 2. CYCLE-BASED RECOMMENDATIONS
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

  // 3. CONTRADICTION ALERTS
  if (u.contradictions?.length > 0) {
    recos.push({
      priority: 'medium',
      title: 'Signaux contradictoires détectés',
      reason: `${u.contradictions.length} divergence(s) entre modules`,
      icon: '⚡',
      source: 'contradiction-analysis'
    });
  }

  // 4. RISK BUDGET RECOMMENDATIONS
  if (u.risk?.budget?.stables_allocation > 0.4) {
    recos.push({
      priority: 'medium',
      title: `Allocation stables: ${u.risk.budget.percentages?.stables}%`,
      reason: 'Budget de risque calculé par algorithme sophistiqué',
      icon: '🛡️',
      source: 'risk-budget'
    });
  }

  // 5. SIGNALS INTERPRETATION
  if (u.sentiment?.interpretation === 'extreme_fear' && u.decision.score < 30) {
    recos.push({
      priority: 'high',
      title: 'Opportunité - Peur extrême',
      reason: 'Signaux temps réel indiquent opportunité d\'achat',
      icon: '🟢',
      source: 'signals-intelligence'
    });
  } else if (u.sentiment?.interpretation === 'extreme_greed' && u.decision.score > 80) {
    recos.push({
      priority: 'high', 
      title: 'Attention - Cupidité extrême',
      reason: 'Signaux temps réel indiquent risque de correction',
      icon: '🔴',
      source: 'signals-intelligence'
    });
  }

  // Sort by priority and limit to top 4
  const priorityOrder = { 'critical': 4, 'high': 3, 'medium': 2, 'low': 1 };
  return recos
    .sort((a, b) => (priorityOrder[b.priority] || 1) - (priorityOrder[a.priority] || 1))
    .slice(0, 4);
}

export default { getUnifiedState, deriveRecommendations };

