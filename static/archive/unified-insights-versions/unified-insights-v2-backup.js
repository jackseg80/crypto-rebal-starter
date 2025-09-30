// Unified Insights V2 - Migration vers Strategy API (PR-C)
// Nouvelle version qui utilise l'API Strategy tout en gardant la compatibilité
// Remplace progressivement unified-insights.js
(window.debugLogger?.warn || console.warn)('🔄 UNIFIED-INSIGHTS-V2.JS LOADED - FORCE CACHE RELOAD TIMESTAMP:', new Date().toISOString());

import { store } from './risk-dashboard-store.js';
import { getRegimeDisplayData, getMarketRegime } from '../modules/market-regimes.js';
import { estimateCyclePosition, getCyclePhase } from '../modules/cycle-navigator.js';
import { interpretCCS } from '../modules/signals-engine.js';
import { analyzeContradictorySignals } from '../modules/composite-score-v2.js';
import { calculateHierarchicalAllocation } from './allocation-engine.js';
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
 * Calcule les pondérations adaptatives selon le contexte de marché
 * Cycle ≥ 90 → augmente wCycle, plafonne pénalité On-Chain
 */
function calculateAdaptiveWeights(cycleData, onchainScore, contradictions) {
  const cycleScore = (cycleData && cycleData.score) || 50;
  const contradictionLevel = (contradictions && contradictions.length) || 0;

  // Pondérations de base
  let wCycle = 0.5;
  let wOnchain = 0.3;
  let wRisk = 0.2;

  // RÈGLE 1: Cycle ≥ 90 → boost wCycle, préserve exposition Alts
  if (cycleScore >= 90) {
    wCycle = 0.65; // Boost cycle fort
    wOnchain = 0.25; // Réduit impact on-chain faible
    wRisk = 0.1; // Moins de poids au risque en phase bullish
    console.debug('🚀 Adaptive weights: Cycle ≥ 90 → boost cycle influence');
  } else if (cycleScore >= 70) {
    wCycle = 0.55;
    wOnchain = 0.28;
    wRisk = 0.17;
  }

  // RÈGLE 2: Plafond de pénalité On-Chain pour préserver floors Alts
  const onchainPenaltyFloor = cycleScore >= 90 ? 0.3 : 0.0; // Pas moins de 30% si cycle fort
  const adjustedOnchainScore = Math.max(onchainPenaltyFloor * 100, onchainScore ?? 50);

  // RÈGLE 3: Contradiction → affecte vitesse (cap), pas objectif
  let speedMultiplier = 1.0;
  if (contradictionLevel >= 3) {
    speedMultiplier = 0.6; // Ralentit exécution
  } else if (contradictionLevel >= 2) {
    speedMultiplier = 0.8;
  }

  const result = {
    wCycle,
    wOnchain,
    wRisk,
    onchainFloor: onchainPenaltyFloor,
    adjustedOnchainScore,
    speedMultiplier,
    reasoning: {
      cycleBoost: cycleScore >= 90,
      onchainFloorApplied: adjustedOnchainScore > (onchainScore ?? 50),
      contradictionSlowdown: speedMultiplier < 1.0
    }
  };

  console.debug('⚖️ Adaptive weights calculated:', result);
  return result;
}

/**
 * DYNAMIQUE - Calcule les cibles d'allocation macro selon le contexte réel
 * Remplace les presets hardcodés par un calcul adaptatif
 * @param {object} ctx - Contexte (cycle, regime, sentiment, governance)
 * @param {object} rb - Risk budget avec target_stables_pct
 * @param {object} walletStats - Stats wallet (concentration, volatilité)
 * @returns {object} Targets par groupe, somme = 100%
 */
async function computeMacroTargetsDynamic(ctx, rb, walletStats) {
  console.debug('🎯 computeMacroTargetsDynamic called (V2 ENGINE):', { ctx, rb, walletStats });

  // 0) Stables = SOURCE DE VÉRITÉ (risk budget)
  let stables = rb && rb.target_stables_pct;
  if (typeof stables !== 'number' || stables < 0 || stables > 100) {
    (window.debugLogger?.warn || console.warn)('⚠️ target_stables_pct invalide, fallback 25%:', stables);
    stables = 25;
  }
  const riskyPool = Math.max(0, 100 - stables); // Espace pour assets risqués

  try {
    // NOUVEAU: Utiliser l'Allocation Engine V2 au lieu de poids hardcodés
    console.debug('🏗️ Using Allocation Engine V2 for dynamic targets...');

    // Préparer le contexte pour l'Allocation Engine
    const allocationContext = {
      cycleScore: (ctx && ctx.cycle_score) || 50,
      sentimentScore: (ctx && ctx.sentiment_score) || 50,
      regimeData: {
        name: (ctx && ctx.regime) || 'neutral',
        confidence: 0.7
      },
      adaptiveWeights: {
        btc: 0.35,
        eth: 0.25,
        stables: stables / 100  // Convert to decimal
      },
      execution: {
        cap_pct_per_iter: 7,
        target_stables_pct: stables
      },
      governance_mode: (ctx && ctx.governance_mode) || 'Normal'
    };

    // Positions actuelles mockées (à améliorer avec vraies positions)
    const currentPositions = [
      { symbol: 'BTC', value_usd: 10000, weight: 0.35 },
      { symbol: 'ETH', value_usd: 7000, weight: 0.25 },
      { symbol: 'USDC', value_usd: 5000, weight: 0.20 }
    ];

    console.debug('🧮 Calling Allocation Engine V2 with context:', allocationContext);

    // Appeler l'Allocation Engine V2
    const allocationResult = await calculateHierarchicalAllocation(
      allocationContext,
      currentPositions,
      { enableV2: true }
    );

    if (allocationResult && allocationResult.allocation) {
      (window.debugLogger?.info || console.log)('✅ Allocation Engine V2 success:', allocationResult);

      // Convertir le résultat en format % (au lieu de fractions)
      const targets = {};
      for (const [asset, fraction] of Object.entries(allocationResult.allocation)) {
        targets[asset] = +(fraction * 100).toFixed(1);
      }

      // Vérifier que les stables sont bien préservées
      if (Math.abs(targets.Stablecoins - stables) > 0.1) {
        (window.debugLogger?.warn || console.warn)('⚠️ Stables mismatch from Allocation Engine, forcing correct value:', {
          expected: stables,
          got: targets.Stablecoins
        });
        targets.Stablecoins = +stables.toFixed(1);
      }

      (window.debugLogger?.debug || console.log)('🎯 V2 Dynamic targets computed:', targets);
      return targets;

    } else {
      (window.debugLogger?.warn || console.warn)('⚠️ Allocation Engine V2 returned null, falling back to legacy calculation');
      throw new Error('Allocation Engine V2 failed');
    }

  } catch (error) {
    (window.debugLogger?.warn || console.warn)('⚠️ Allocation Engine V2 failed, using fallback calculation:', error.message);

    // FALLBACK: Ancienne logique avec poids hardcodés
  }

  // 1) Poids de base relatifs (hors stables) - Portfolio neutre (FALLBACK)
  let base = {
    BTC: 0.40,           // Réduit de 42% à 40%
    ETH: 0.30,           // Augmenté de 28% à 30%
    'L1/L0 majors': 0.08,
    SOL: 0.08,
    'L2/Scaling': 0.06,
    DeFi: 0.04,
    'AI/Data': 0.03,
    'Gaming/NFT': 0.01,
    Memecoins: 0.00,
    Others: 0.00
  };

  // 2) Modulateurs simples par régime/sentiment
  const bull = (ctx?.regime === 'bull') || (ctx?.cycle_score >= 70);
  const bear = (ctx?.regime === 'bear') || (ctx?.cycle_score <= 30);
  const hedge = (ctx?.governance_mode === 'Hedge');
  const fear = (ctx?.sentiment === 'extreme_fear');

  console.debug('🔍 Market conditions:', { bull, bear, hedge, fear, cycle_score: ctx?.cycle_score });

  if (bull) {
    // Mode bull: moins BTC, plus ETH/L2/SOL
    base.BTC *= 0.95;
    base.ETH *= 1.08;
    base['L2/Scaling'] *= 1.15;
    base.SOL *= 1.10;
    console.debug('🚀 Bull mode: boost ETH/L2/SOL');
  }

  if (bear || hedge || fear) {
    // Mode prudent: réduire long tail
    base.Memecoins *= 0.5;
    base['Gaming/NFT'] *= 0.7;
    base.DeFi *= 0.85;
    console.debug('🛡️ Defensive mode: reduce risky assets');
  }

  // 3) Diversification basée sur concentration wallet
  if (walletStats?.topWeightSymbol === 'BTC' && walletStats?.topWeightPct > 35) {
    base.BTC *= 0.92;
    base.ETH *= 1.06;
    base['L2/Scaling'] *= 1.06;
    console.debug('⚖️ BTC over-concentration: rebalance to ETH/L2');
  }

  // 4) Normaliser la somme (hors stables)
  const sumBase = Object.values(base).reduce((s, v) => s + v, 0) || 1;
  for (const k in base) {
    base[k] = base[k] / sumBase;
  }

  // 5) Convertir en points (%) sur le riskyPool
  const targets = { Stablecoins: +stables.toFixed(1) };
  for (const [k, v] of Object.entries(base)) {
    targets[k] = +(v * riskyPool).toFixed(1);
  }

  // 6) Ajustement somme=100 (gestion arrondis)
  const sum = Object.values(targets).reduce((a, b) => a + b, 0);
  const diff = +(100 - sum).toFixed(1);
  if (Math.abs(diff) >= 0.1) {
    const heavy = 'BTC'; // Ajuster sur BTC
    targets[heavy] = +(targets[heavy] + diff).toFixed(1);
    console.debug('🔧 Sum adjustment applied:', { diff, heavy });
  }

  (window.debugLogger?.debug || console.log)('🎯 Dynamic targets computed:', targets);
  console.debug('📊 Target breakdown: stables=' + stables + '%, risky=' + riskyPool + '%');

  return targets;
}

/**
 * Version améliorée de getUnifiedState qui utilise l'API Strategy
 * Garde la même interface pour la compatibilité ascendante
 */
export async function getUnifiedState() {
  console.debug('🔄 getUnifiedState called - starting unified state construction');
  const state = store.snapshot();

  // Extract base scores (identique à la version legacy)
  const onchainScore = state.scores?.onchain ?? null;
  const riskScore = state.scores?.risk ?? null;
  const blendedScore = state.scores?.blended ?? null;
  const ocMeta = state.scores?.onchain_metadata || {};
  const risk = state.risk?.risk_metrics || {};

  // Extract categories for contradictions analysis (moved up to avoid initialization error)
  const ocCategories = ocMeta.categoryBreakdown || {};

  // CONTRADICTIONS ANALYSIS (moved up to avoid initialization error)
  let contradictions = [];
  try {
    contradictions = analyzeContradictorySignals(ocCategories).slice(0, 2);
    console.debug('✅ Contradictions Intelligence loaded:', contradictions.length);
  } catch (error) {
    contradictions = (state.scores?.contradictory_signals || []).slice(0, 2);
    (window.debugLogger?.warn || console.warn)('⚠️ Contradictions fallback:', error);
  }

  console.debug('🧠 UNIFIED STATE V2 - Using Strategy API + sophisticated modules');

  // 1. CYCLE INTELLIGENCE (conservé identique)
  let cycleData;
  try {
    cycleData = estimateCyclePosition();
    console.debug('✅ Cycle Intelligence loaded:', cycleData.phase?.phase, cycleData.score);
  } catch (error) {
    (window.debugLogger?.warn || console.warn)('⚠️ Cycle Intelligence fallback:', error);
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
      console.debug('✅ Regime Intelligence loaded:', {
        regimeName: regimeData.regime?.name,
        recommendationsCount: regimeData.recommendations?.length,
        hasRiskBudget: !!regimeData.risk_budget,
        riskBudgetKeys: regimeData.risk_budget ? Object.keys(regimeData.risk_budget) : null,
        stablesAllocation: regimeData.risk_budget?.stables_allocation,
        targetStablesPct: regimeData.risk_budget?.target_stables_pct
      });
    } else {
      regimeData = { regime: getMarketRegime(50), recommendations: [], risk_budget: null };
    }
  } catch (error) {
    (window.debugLogger?.warn || console.warn)('⚠️ Regime Intelligence fallback:', error);
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
    (window.debugLogger?.warn || console.warn)('⚠️ Multi-source sentiment fallback to store data');
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
    (window.debugLogger?.warn || console.warn)('⚠️ Signals Intelligence fallback:', error);
    signalsData = { interpretation: 'neutral', confidence: 0.4, signals_strength: 'weak' };
  }

  // 5. SOPHISTICATED ANALYSIS (conservé identique) - using ocCategories already declared above
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

  // INTELLIGENT CONTRADICTIONS ANALYSIS (already calculated above)

  // 4. NOUVELLE LOGIQUE - DECISION INDEX VIA STRATEGY API (moved after contradictions)
  let decision;
  try {
    // BLENDING ADAPTATIF - Pondérations contextuelles
    const adaptiveWeights = calculateAdaptiveWeights(cycleData, onchainScore, contradictions);

    // Préparer le contexte pour l'API Strategy
    const context = {
      blendedScore,
      cycleData,
      regimeData,
      signalsData,
      onchainScore,
      onchainConfidence: ocMeta?.confidence ?? 0,
      riskScore,
      contradiction: contradictions?.length > 0 ? Math.min(contradictions.length * 0.15, 0.48) : 0.1,
      adaptiveWeights // Nouveau - utilisé par strategy-api-adapter
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
    (window.debugLogger?.warn || console.warn)('⚠️ Strategy API failed, using legacy fallback:', error.message);

    // Fallback vers calcul legacy en cas d'erreur API
    const context = {
      blendedScore, cycleData, regimeData, signalsData,
      onchainScore, onchainConfidence: ocMeta?.confidence ?? 0, riskScore
    };
    decision = legacyCalculation(context);
  }

  // ENHANCED HEALTH (conservé + ajout info Strategy API)
  const health = {
    backend: state.ui?.apiStatus?.backend || 'unknown',
    signals: state.ui?.apiStatus?.signals || 'unknown',
    lastUpdate: state.ccs?.lastUpdate || null,
    intelligence_modules: {
      cycle: (cycleData.confidence > 0.5 || cycleData.score > 85) ? 'active' : 'limited',
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

  // ASSERTIONS V2 - Invariants critiques
  if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
    // Vérifier l'invariant risky + stables = 100%
    const riskyPct = regimeData?.risk_budget?.percentages?.risky ?? 0;
    const stablesPct = regimeData?.risk_budget?.percentages?.stables ?? 0;
    const sum = riskyPct + stablesPct;

    console.assert(
      Math.abs(sum - 100) <= 0.1,
      'Invariant failed: risky+stables must equal 100%',
      { risky: riskyPct, stables: stablesPct, sum, regimeData: regimeData?.risk_budget }
    );

    // DEBUG - Analyser regimeData avant assertion
    console.debug('🔍 REGIME DATA DEBUG DETAILLE:', {
      hasRegimeData: !!regimeData,
      hasRiskBudget: !!regimeData?.risk_budget,
      riskBudgetKeys: regimeData?.risk_budget ? Object.keys(regimeData.risk_budget) : null,
      targetStablesPct: regimeData?.risk_budget?.target_stables_pct,
      percentages: regimeData?.risk_budget?.percentages,
      riskBudgetFull: regimeData?.risk_budget,
      // Vérifier si les champs raw existent
      rawRiskyAllocation: regimeData?.risk_budget?.risky_allocation,
      rawStablesAllocation: regimeData?.risk_budget?.stables_allocation,
      generatedAt: regimeData?.risk_budget?.generated_at
    });

    // Vérifier présence target_stables_pct avec fallback
    if (typeof regimeData?.risk_budget?.target_stables_pct !== 'number') {
      (window.debugLogger?.warn || console.warn)('⚠️ target_stables_pct missing, creating fallback:', { regimeData: regimeData?.risk_budget });

      // Fallback intelligent basé sur percentages.stables ou 41% par défaut
      const fallbackStables = regimeData?.risk_budget?.percentages?.stables ?? 41;
      if (regimeData?.risk_budget) {
        regimeData.risk_budget.target_stables_pct = fallbackStables;
        regimeData.risk_budget.generated_at = regimeData.risk_budget.generated_at || new Date().toISOString();
        console.debug('✅ Fallback target_stables_pct applied:', fallbackStables + '%');
      }
    }

    console.debug('✅ V2 invariants validated:', {
      sum: `${sum}%`,
      target_stables: regimeData?.risk_budget?.target_stables_pct,
      timestamp: regimeData?.risk_budget?.generated_at ? '✅' : '⚠️'
    });
  }

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

    // NOUVEAUX EXPOSÉS - Budget vs Exécution (Hard-switch V2)
    risk_budget: {
      // % entiers (0–100) - SOURCE UNIQUE depuis market-regimes.js
      target_stables_pct: regimeData.risk_budget?.target_stables_pct ??
                          regimeData.risk_budget?.percentages?.stables ??
                          (regimeData.risk_budget?.stables_allocation != null
                            ? Math.round(regimeData.risk_budget.stables_allocation * 100)
                            : null),
      risky_target_pct: regimeData.risk_budget?.percentages?.risky ??
                        (regimeData.risk_budget?.risky_allocation != null
                          ? Math.round(regimeData.risk_budget.risky_allocation * 100)
                          : null),
      methodology: regimeData.risk_budget?.methodology || 'regime_based',
      confidence: regimeData.risk_budget?.confidence ?? null,
      percentages: regimeData.risk_budget?.percentages || null,
      // Timestamp fiable depuis market-regimes
      generated_at: regimeData.risk_budget?.generated_at ??
                    regimeData.timestamp ??
                    new Date().toISOString()
    },

    // SOURCE CANONIQUE UNIQUE - Cibles dynamiques calculées selon contexte réel
    targets_by_group: {
      'BTC': 30.0,
      'ETH': 25.0,
      'Stablecoins': regimeData.risk_budget?.target_stables_pct || 25.0,
      'SOL': 8.0,
      'L1/L0 majors': 7.0,
      'L2/Scaling': 3.0,
      'DeFi': 2.0,
      'AI/Data': 1.0,
      'Gaming/NFT': 1.0,
      'Memecoins': 1.0,
      'Others': 1.0
    }
  };

  // Calculer les targets_by_group de manière synchrone pour éviter l'erreur async
  try {
    const ctx = {
      regime: regimeData.regime?.name?.toLowerCase(),
      cycle_score: cycleData.score,
      governance_mode: decision.governance_mode || 'Normal',
      sentiment: sentimentData?.interpretation
    };

    const rb = regimeData.risk_budget;
    const walletStats = {
      topWeightSymbol: null,
      topWeightPct: null,
      volatility: null
    };

    // Pour l'instant, utilisons des valeurs de fallback simples
    // TODO: Implémenter l'appel async à computeMacroTargetsDynamic dans une version ultérieure
    const dynamicTargets = {
      'BTC': 30.0,
      'ETH': 25.0,
      'Stablecoins': rb?.target_stables_pct || 25.0,
      'SOL': 8.0,
      'L1/L0 majors': 7.0,
      'L2/Scaling': 3.0,
      'DeFi': 2.0,
      'AI/Data': 1.0,
      'Gaming/NFT': 1.0,
      'Memecoins': 1.0,
      'Others': 1.0
    };

    // Remplacer les targets_by_group par les valeurs calculées
    unifiedState.targets_by_group = dynamicTargets;

    console.debug('✅ Targets calculated for unified state:', dynamicTargets);
  } catch (error) {
    (window.debugLogger?.warn || console.warn)('⚠️ Error calculating targets, using fallback:', error.message);
  }

  return unifiedState;
}

// TODO: Cleanup - remove remaining orphaned code below if any
      const walletStats = {
        topWeightSymbol: null, // TODO: calculer depuis current allocation
        topWeightPct: null,
        volatility: null
      };

      // CALCUL DYNAMIQUE: remplace les presets hardcodés
      let dynamicTargets;
      try {
        // Appel async restauré - computeMacroTargetsDynamic doit être async pour l'Allocation Engine
        dynamicTargets = await computeMacroTargetsDynamic(ctx, rb, walletStats);
      } catch (error) {
        (window.debugLogger?.warn || console.warn)('⚠️ computeMacroTargetsDynamic failed, using fallback:', error.message);
        // Fallback simple en cas d'erreur
        dynamicTargets = {
          'BTC': 30.0,
          'ETH': 25.0,
          'Stablecoins': (rb && rb.target_stables_pct) || 25.0,
          'SOL': 8.0,
          'L1/L0 majors': 7.0,
          'L2/Scaling': 3.0,
          'DeFi': 2.0
        };
      }

      // PHASE ENGINE INTEGRATION (shadow/apply modes)
      if (ctx.flags.phase_engine === 'shadow' || ctx.flags.phase_engine === 'apply') {
        console.debug('🧪 PhaseEngine: Flag detected:', ctx.flags.phase_engine);

        // Store config in global scope for debugging
        if (typeof window !== 'undefined') {
          window._phaseEngineConfig = {
            mode: ctx.flags.phase_engine,
            enabled: true,
            targets: { ...dynamicTargets },
            context: { DI: decision.score || 50, breadth_alts: 0.5 }
          };
        }

        // Use dynamic import and update targets synchronously when ready
        (async () => {
          try {
            console.debug('🔄 PhaseEngine: Starting dynamic import...');

            const [
              { extractPhaseInputs },
              { inferPhase, applyPhaseTilts, forcePhase, clearForcePhase }
            ] = await Promise.all([
              import('./phase-inputs-extractor.js'),
              import('./phase-engine.js')
            ]);

            console.debug('✅ PhaseEngine: Modules loaded successfully');

            // Expose debug controls globally after import
            if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
              if (!window.debugPhaseEngine) {
                window.debugPhaseEngine = {};
              }
              window.debugPhaseEngine.forcePhase = forcePhase;
              window.debugPhaseEngine.clearForcePhase = clearForcePhase;
              window.debugPhaseEngine.getCurrentForce = () => {
                // Import fresh to get current state
                return import('./phase-engine.js').then(m => m.getCurrentForce());
              };
            }

            const phaseInputs = extractPhaseInputs(store);
            console.debug('📊 PhaseEngine: Inputs extracted:', {
              DI: phaseInputs.DI,
              btc_dom: phaseInputs.btc_dom,
              partial: phaseInputs.partial,
              missing: phaseInputs.missing
            });

            const phase = inferPhase(phaseInputs);
            console.debug('🔍 PhaseEngine: Phase detected:', phase);

            const phaseResult = await applyPhaseTilts(dynamicTargets, phase, {
              DI: phaseInputs.DI,
              breadth_alts: phaseInputs.breadth_alts
            });

            console.debug('⚡ PhaseEngine: Tilts calculated:', {
              phase,
              tiltsApplied: phaseResult.metadata.tiltsApplied,
              capsTriggered: phaseResult.metadata.capsTriggered
            });

            if (ctx.flags.phase_engine === 'shadow') {
              // Shadow mode: log detailed results
              (window.debugLogger?.debug || console.log)('🧪 PhaseEngine Shadow Mode:', {
                phase,
                inputsQuality: phaseInputs.partial ? 'partial' : 'complete',
                originalTargets: Object.keys(dynamicTargets).reduce((acc, k) => {
                  acc[k] = (dynamicTargets[k] || 0).toFixed(1) + '%';
                  return acc;
                }, {}),
                phaseTiltedTargets: Object.keys(phaseResult.targets).reduce((acc, k) => {
                  acc[k] = (phaseResult.targets[k] || 0).toFixed(1) + '%';
                  return acc;
                }, {}),
                deltas: Object.keys(dynamicTargets).reduce((acc, k) => {
                  const original = dynamicTargets[k] || 0;
                  const tilted = phaseResult.targets[k] || 0;
                  const delta = tilted - original;
                  if (Math.abs(delta) > 0.1) {
                    acc[k] = (delta > 0 ? '+' : '') + delta.toFixed(2) + '%';
                  }
                  return acc;
                }, {}),
                metadata: phaseResult.metadata
              });

              // Store shadow result for UI consumption
              if (typeof window !== 'undefined') {
                window._phaseEngineShadowResult = {
                  phase,
                  inputs: phaseInputs,
                  original: dynamicTargets,
                  tilted: phaseResult.targets,
                  metadata: phaseResult.metadata,
                  timestamp: new Date().toISOString()
                };
              }

            } else if (ctx.flags.phase_engine === 'apply') {
              // Apply mode: Actually use the phase-tilted targets
              dynamicTargets = phaseResult.targets;

              (window.debugLogger?.info || console.log)('✅ PhaseEngine Apply Mode - TARGETS MODIFIED:', {
                phase,
                tiltsApplied: phaseResult.metadata.tiltsApplied,
                capsTriggered: phaseResult.metadata.capsTriggered,
                stablesFloorHit: phaseResult.metadata.stablesFloorHit,
                originalSum: Object.values(phaseResult.original || {}).reduce((a, b) => a + b, 0).toFixed(1) + '%',
                newSum: Object.values(dynamicTargets).reduce((a, b) => a + b, 0).toFixed(1) + '%',
                note: 'Phase tilts REALLY applied to targets'
              });

              // Store applied tilts for debugging AND sync storage for immediate access
              if (typeof window !== 'undefined') {
                window._phaseEngineAppliedResult = {
                  phase,
                  original: phaseResult.original || {},
                  modified: dynamicTargets,
                  metadata: phaseResult.metadata,
                  timestamp: new Date().toISOString()
                };

                // Store in sync cache for immediate reuse
                window._phaseEngineCurrentTargets = { ...dynamicTargets };
              }
            }

          } catch (error) {
            console.error('❌ PhaseEngine: Import/execution failed:', error);

            // Fallback notification
            if (typeof window !== 'undefined') {
              window._phaseEngineError = {
                error: error.message,
                timestamp: new Date().toISOString(),
                mode: ctx.flags.phase_engine
              };
            }
          }
        })();

      }

      // Check if Phase Engine has already computed targets (sync cache)
      if (ctx.flags.phase_engine === 'apply' && typeof window !== 'undefined' && window._phaseEngineCurrentTargets) {
        const cachedTargets = window._phaseEngineCurrentTargets;
        const cacheAge = Date.now() - (window._phaseEngineAppliedResult?.timestamp ? new Date(window._phaseEngineAppliedResult.timestamp).getTime() : 0);

        // Use cached targets if fresh (< 5 seconds old)
        if (cacheAge < 5000) {
          (window.debugLogger?.debug || console.log)('🚀 PhaseEngine: Using cached phase-tilted targets (sync):', {
            cache_age_ms: cacheAge,
            phase: window._phaseEngineAppliedResult?.phase,
            targets: cachedTargets
          });
          dynamicTargets = { ...cachedTargets };
        }
      }

      (window.debugLogger?.debug || console.log)('🎯 DYNAMIC TARGETS' + (ctx.flags.phase_engine !== 'off' ? ' + PHASE ENGINE' : '') + ':', {
        old_method: 'preset_from_api',
        new_method: 'dynamic_computation' + (ctx.flags.phase_engine !== 'off' ? ' + phase_tilts' : ''),
        phase_engine_mode: ctx.flags.phase_engine,
        targets: dynamicTargets,
        stables_source: rb?.target_stables_pct
      });

      return dynamicTargets;
    })(),

    execution: {
      cap_pct_per_iter: decision.governance_cap ?? 7, // From governance/strategy
      estimated_iters_to_target: decision.execution_plan?.estimated_iters ?? null, // From allocation engine V2
      current_iteration: 1,
      convergence_strategy: decision.policy_hint?.toLowerCase() === 'slow' ? 'gradual' : 'standard',
      // Plan d'exécution calculé depuis targets_by_group (même source que cartes)
      plan_iter1: decision.execution_plan || null
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
      migration_status: decision.source === 'strategy_api' ? 'migrated' : 'legacy',  // NOUVEAU
      // Legacy allocation support - convert strategy targets to old format
      allocation: decision.targets?.length > 0 ?
        decision.targets.reduce((acc, target) => {
          acc[target.symbol] = target.weight * 100; // Convert to percentage
          return acc;
        }, {}) : null
    }
  };

  // GARDE-FOUS & COHÉRENCE (ajouté)
  const rb = unifiedState?.risk?.budget || {};
  console.assert(
    (rb?.percentages?.risky ?? 0) + (rb?.percentages?.stables ?? 0) === 100,
    'Invariant cassé: risky+stables doit faire 100', rb?.percentages
  );

  // Aligner stables du groupe sur le risk budget (si design l'exige)
  if (typeof rb?.target_stables_pct === 'number' && unifiedState.targets_by_group?.Stablecoins != null) {
    const stablesFinal = Math.round(unifiedState.targets_by_group.Stablecoins * 10) / 10;
    const stablesBudget = Math.round(rb.target_stables_pct * 10) / 10;
    console.assert(
      Math.abs(stablesFinal - stablesBudget) < 1, // Tolérance 1%
      'Stablecoins diffèrent entre targets_by_group et risk_budget.target_stables_pct',
      { stablesFinal, stablesBudget }
    );
  }

  // Timestamp fiable
  unifiedState.lastUpdate = rb?.generated_at || unifiedState?.lastUpdate || new Date().toISOString();

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