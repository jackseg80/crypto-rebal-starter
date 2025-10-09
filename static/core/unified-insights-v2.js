// Unified Insights V2 - Migration vers Strategy API (PR-C)
// Nouvelle version qui utilise l'API Strategy tout en gardant la compatibilité
// Remplace progressivement unified-insights.js
(window.debugLogger?.warn || console.warn)('🔄 UNIFIED-INSIGHTS-V2.JS LOADED - FORCE CACHE RELOAD TIMESTAMP:', new Date().toISOString());

import { store } from './risk-dashboard-store.js';
import { getRegimeDisplayData, getMarketRegime } from '../modules/market-regimes.js';
import { estimateCyclePosition, getCyclePhase } from '../modules/cycle-navigator.js';
import { interpretCCS } from '../modules/signals-engine.js';
import { analyzeContradictorySignals } from '../modules/composite-score-v2.js';
import { calculateIntelligentDecisionIndexAPI, StrategyConfig } from './strategy-api-adapter.js';
import { calculateAdaptiveWeights as calculateAdaptiveWeightsV2 } from '../governance/contradiction-policy.js';

// Lightweight helpers (conservés pour compatibilité)
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const pct = (x) => Math.round(clamp01(x) * 100);
const colorForScore = (s) => s > 70 ? 'var(--danger)' : s >= 40 ? 'var(--warning)' : 'var(--success)';

/**
 * 🆕 STRUCTURE MODULATION V2 (Oct 2025)
 * Moduler la cible de stables et le cap selon la qualité structurelle du portfolio
 *
 * @param {number} structureScore - Portfolio Structure Score V2 (0-100)
 * @returns {object} { deltaStables, deltaCap }
 *
 * Règles:
 * - Structure faible (< 50) → +10 pts stables, cap -0.5
 * - Structure moyenne (50-60) → +5 pts stables, cap 0
 * - Structure forte (≥ 80) → -5 pts stables, cap +0.5
 * - Sinon (60-80) → Neutre (0, 0)
 */
export function computeStructureModulation(structureScore) {
  if (structureScore == null || Number.isNaN(structureScore)) {
    return { deltaStables: 0, deltaCap: 0 };
  }

  if (structureScore < 50) {
    return { deltaStables: +10, deltaCap: -0.5 };
  }
  if (structureScore < 60) {
    return { deltaStables: +5, deltaCap: 0 };
  }
  if (structureScore >= 80) {
    return { deltaStables: -5, deltaCap: +0.5 };
  }
  // Neutre pour 60-80
  return { deltaStables: 0, deltaCap: 0 };
}

// Simple inline fallback (remplace import legacy archivé)
function simpleFallbackCalculation(context) {
  const { blendedScore = 50, cycleData = {}, onchainScore = 50, riskScore = 50 } = context;
  const cycleScore = cycleData.score ?? 50;
  const weights = { cycle: 0.35, onchain: 0.25, risk: 0.2, blended: 0.2 };
  const score = Math.round(
    weights.cycle * cycleScore +
    weights.onchain * onchainScore +
    weights.risk * riskScore +
    weights.blended * blendedScore
  );
  return {
    score: Math.max(0, Math.min(100, score)),
    confidence: 0.5,
    action: score > 70 ? 'HOLD_STABLE' : score >= 40 ? 'MONITOR' : 'RISK_ON',
    source: 'inline_fallback'
  };
}

/**
 * Calcule les pondérations adaptatives selon le contexte de marché
 * Cycle ≥ 90 → augmente wCycle, plafonne pénalité On-Chain
 *
 * ⚠️ IMPORTANT — Sémantique Risk:
 * Risk est un score POSITIF (0..100, plus haut = mieux).
 * Ne jamais inverser (pas de 100 - risk).
 * Contributions UI: (w * score) / Σ(w * score).
 */
function calculateAdaptiveWeights(cycleData, onchainScore, contradictions, governanceContradiction = 0) {
  const cycleScore = cycleData?.score ?? 50;
  // Utiliser governance.contradiction_index comme source primaire, fallback sur on-chain
  const contradictionLevel = governanceContradiction > 0 ?
    Math.round(governanceContradiction * 100) :
    (contradictions?.length ?? 0);

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
 * @param {object} rb - Risk budget avec target_stables_pct, min_stables, max_stables
 * @param {object} walletStats - Stats wallet (concentration, volatilité)
 * @param {object} data - Données complètes (pour accès risk_metrics.risk_version_info)
 * @returns {object} Targets par groupe, somme = 100%
 */
function computeMacroTargetsDynamic(ctx, rb, walletStats, data = null) {
  console.debug('🎯 computeMacroTargetsDynamic called:', { ctx, rb, walletStats, hasData: !!data });

  // 0) Stables = SOURCE DE VÉRITÉ (risk budget) avec Structure Modulation V2
  let stablesBase = rb?.target_stables_pct;
  if (typeof stablesBase !== 'number' || stablesBase < 0 || stablesBase > 100) {
    console.debug('⚠️ target_stables_pct invalide, fallback 25%:', stablesBase);
    stablesBase = 25;
  }

  // 🆕 Structure Modulation V2 (Oct 2025)
  const structureScore = data?.risk?.risk_metrics?.risk_version_info?.portfolio_structure_score;
  const { deltaStables, deltaCap } = computeStructureModulation(structureScore);

  // Appliquer modulation avec clamp [min_stables, max_stables]
  const minStables = rb?.min_stables ?? 10;
  const maxStables = rb?.max_stables ?? 60;
  const stablesModulated = Math.max(minStables, Math.min(maxStables, stablesBase + deltaStables));

  // Métadonnées pour UI/logs
  ctx.structure_modulation = {
    structure_score: structureScore ?? null,
    delta_stables: deltaStables,
    delta_cap: deltaCap,
    stables_before: stablesBase,
    stables_after: stablesModulated,
    note: 'V2 portfolio structure modulation',
    enabled: structureScore != null
  };

  console.debug('🏗️ Structure Modulation V2:', ctx.structure_modulation);

  const stables = stablesModulated;
  const riskyPool = Math.max(0, 100 - stables); // Espace pour assets risqués

  // 1) Poids de base relatifs (hors stables) - Portfolio neutre
  let base = {
    BTC: 0.42,           // 42% du risky pool
    ETH: 0.28,           // 28% du risky pool
    'L1/L0 majors': 0.06,
    SOL: 0.06,
    'L2/Scaling': 0.06,
    DeFi: 0.05,
    'AI/Data': 0.04,
    'Gaming/NFT': 0.02,
    Memecoins: 0.01,
    Others: 0.00
  };

  // 2) Modulateurs simples par régime/sentiment
  // IMPORTANT: Désactiver ces modulateurs quand Phase Engine est en mode apply
  // car le Phase Engine gère déjà les tilts de marché de façon plus sophistiquée
  const phaseEngineActive = ctx?.flags?.phase_engine === 'apply';
  const bull = !phaseEngineActive && ((ctx?.regime === 'bull') || (ctx?.cycle_score >= 70));
  const bear = !phaseEngineActive && ((ctx?.regime === 'bear') || (ctx?.cycle_score <= 30));
  const hedge = !phaseEngineActive && (ctx?.governance_mode === 'Hedge');
  const fear = !phaseEngineActive && (ctx?.sentiment === 'extreme_fear');

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

  // Debug logs removed (obsolete, redundant with comprehensive log below)
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

  // 2. REGIME INTELLIGENCE avec scores arrondis pour stabilité
  let regimeData;
  try {
    if (blendedScore != null) {
      // ARRONDIR les scores pour éviter micro-variations (68.3 vs 68.7 → même regime)
      const blendedRounded = Math.round(blendedScore);
      const onchainRounded = onchainScore != null ? Math.round(onchainScore) : null;
      const riskRounded = riskScore != null ? Math.round(riskScore) : null;

      regimeData = getRegimeDisplayData(blendedRounded, onchainRounded, riskRounded);
      console.debug('✅ Regime Intelligence loaded:', {
        regimeName: regimeData.regime?.name,
        recommendationsCount: regimeData.recommendations?.length,
        hasRiskBudget: !!regimeData.risk_budget,
        riskBudgetKeys: regimeData.risk_budget ? Object.keys(regimeData.risk_budget) : null,
        stablesAllocation: regimeData.risk_budget?.stables_allocation,
        targetStablesPct: regimeData.risk_budget?.target_stables_pct,
        scoresUsed: { blended: blendedRounded, onchain: onchainRounded, risk: riskRounded }
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
    // BLENDING ADAPTATIF - Pondérations contextuelles avec governance unifiée
    const governanceContradiction = state.governance?.contradiction_index || 0;
    const adaptiveWeights = calculateAdaptiveWeights(cycleData, onchainScore, contradictions, governanceContradiction);

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

    // Comparaison désactivée (legacy archivé)

  } catch (error) {
    (window.debugLogger?.warn || console.warn)('⚠️ Strategy API failed, using inline fallback:', error.message);

    // Fallback vers calcul simple en cas d'erreur API
    const context = {
      blendedScore, cycleData, regimeData, signalsData,
      onchainScore, onchainConfidence: ocMeta?.confidence ?? 0, riskScore
    };
    decision = simpleFallbackCalculation(context);
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

    // Seulement vérifier l'assertion si on a des données valides
    if (riskyPct > 0 && stablesPct > 0) {
      console.assert(
        Math.abs(sum - 100) <= 0.1,
        'Invariant failed: risky+stables must equal 100%',
        { risky: riskyPct, stables: stablesPct, sum, regimeData: regimeData?.risk_budget }
      );
    } else {
      console.debug('⚠️ Skipping risky+stables assertion: missing valid percentages',
        { risky: riskyPct, stables: stablesPct });
    }

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
      console.debug('⚠️ target_stables_pct missing, creating fallback:', { regimeData: regimeData?.risk_budget });

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
    // Scores consolidés pour Decision Index Panel
    scores: {
      cycle: Math.round(cycleData.score ?? 50),
      onchain: onchainScore != null ? Math.round(onchainScore) : null,
      risk: riskScore != null ? Math.round(riskScore) : null,
      blended: blendedScore != null ? Math.round(blendedScore) : null
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
    targets_by_group: await (async () => {
      // Construire le contexte pour calcul dynamique
      const ctx = {
        regime: regimeData.regime?.name?.toLowerCase(),
        cycle_score: cycleData.score,
        governance_mode: decision.governance_mode || 'Normal',
        sentiment: sentimentData?.interpretation,
        // NOUVEAU: Feature flags pour phase engine
        flags: {
          phase_engine: typeof window !== 'undefined' ?
            localStorage.getItem('PHASE_ENGINE_ENABLED') || 'shadow' : 'off'
        }
      };

      // Risk budget (SOURCE DE VÉRITÉ pour stables)
      const rb = regimeData.risk_budget;

      // Stats wallet basiques (TODO: étendre avec vrais calculs)
      const walletStats = {
        topWeightSymbol: null, // TODO: calculer depuis current allocation
        topWeightPct: null,
        volatility: null
      };

      // CALCUL DYNAMIQUE: remplace les presets hardcodés
      // 🆕 Passer risk_metrics pour Structure Modulation V2
      const dataForModulation = { risk: { risk_metrics: risk } };
      let dynamicTargets = computeMacroTargetsDynamic(ctx, rb, walletStats, dataForModulation);

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

        // CRITICAL FIX: Make Phase Engine awaitable instead of fire-and-forget
        const phaseEnginePromise = (async () => {
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

            console.debug('🔍 PhaseEngine RESULT DEBUG:', {
              phaseResult,
              hasTargets: !!phaseResult?.targets,
              targetsKeys: phaseResult?.targets ? Object.keys(phaseResult.targets) : [],
              hasMetadata: !!phaseResult?.metadata,
              type: typeof phaseResult
            });

            console.debug('⚡ PhaseEngine: Tilts calculated:', {
              phase,
              tiltsApplied: phaseResult.metadata?.tiltsApplied ?? 'unknown',
              capsTriggered: phaseResult.metadata?.capsTriggered ?? 'unknown',
              hasMetadata: !!phaseResult.metadata
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
                phaseTiltedTargets: Object.keys(phaseResult.targets || {}).reduce((acc, k) => {
                  acc[k] = ((phaseResult.targets || {})[k] || 0).toFixed(1) + '%';
                  return acc;
                }, {}),
                deltas: Object.keys(dynamicTargets).reduce((acc, k) => {
                  const original = dynamicTargets[k] || 0;
                  const tilted = ((phaseResult.targets || {})[k]) || 0;
                  const delta = tilted - original;
                  if (Math.abs(delta) > 0.1) {
                    acc[k] = (delta > 0 ? '+' : '') + delta.toFixed(2) + '%';
                  }
                  return acc;
                }, {}),
                metadata: phaseResult.metadata || {}
              });

              // Store shadow result for UI consumption
              if (typeof window !== 'undefined') {
                window._phaseEngineShadowResult = {
                  phase,
                  inputs: phaseInputs,
                  original: dynamicTargets,
                  tilted: phaseResult.targets || {},
                  metadata: phaseResult.metadata || {},
                  timestamp: new Date().toISOString()
                };
              }

            } else if (ctx.flags.phase_engine === 'apply') {
              // Apply mode: Actually use the phase-tilted targets
              if (phaseResult.targets) {
                dynamicTargets = phaseResult.targets;
              } else {
                (window.debugLogger?.warn || console.warn)('⚠️ PhaseEngine: No targets returned, keeping original');
              }

              // Calculate sums properly for logging
              const originalSum = Object.values(phaseResult.original || {}).reduce((a, b) => a + (Number(b) || 0), 0);
              const newSum = Object.values(dynamicTargets || {}).reduce((a, b) => a + (Number(b) || 0), 0);

              (window.debugLogger?.info || console.log)('✅ PhaseEngine Apply Mode - TARGETS MODIFIED:', {
                phase,
                tiltsApplied: phaseResult.metadata?.tiltsApplied ?? 'unknown',
                capsTriggered: phaseResult.metadata?.capsTriggered ?? 'unknown',
                stablesFloorHit: phaseResult.metadata?.stablesFloorHit ?? 'unknown',
                originalSum: originalSum.toFixed(1) + '%',
                newSum: newSum.toFixed(1) + '%',
                note: 'Phase tilts REALLY applied to targets'
              });

              // Store applied tilts for debugging AND sync storage for immediate access
              if (typeof window !== 'undefined') {
                window._phaseEngineAppliedResult = {
                  phase,
                  original: phaseResult.original || {},
                  modified: dynamicTargets,
                  metadata: phaseResult.metadata || {},
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

          // Return the final targets after phase processing
          return dynamicTargets;
        })();

        // CRITICAL: Wait for Phase Engine to complete before continuing
        dynamicTargets = await phaseEnginePromise;
        console.debug('🔥 Phase Engine completed, final targets applied:', dynamicTargets);

      }

      // Sync cache no longer needed since Phase Engine is now awaitable

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
  const riskyPct = rb?.percentages?.risky ?? 0;
  const stablesPct = rb?.percentages?.stables ?? 0;
  const sum = riskyPct + stablesPct;

  // Seulement vérifier si on a des données valides
  if (riskyPct > 0 && stablesPct > 0) {
    console.assert(
      Math.abs(sum - 100) <= 0.1,
      'Invariant cassé: risky+stables doit faire 100', rb?.percentages
    );
  } else {
    console.debug('⚠️ Skipping second risky+stables assertion: missing budget data',
      { risky: riskyPct, stables: stablesPct, rb: rb?.percentages });
  }

  // Aligner stables du groupe sur le risk budget (si design l'exige)
  if (typeof rb?.target_stables_pct === 'number' && unifiedState.targets_by_group?.Stablecoins != null) {
    const stablesFinal = Math.round(unifiedState.targets_by_group.Stablecoins * 10) / 10;
    const stablesBudget = Math.round(rb.target_stables_pct * 10) / 10;
    const diff = Math.abs(stablesFinal - stablesBudget);

    // Log as warning if divergence > 15% (frontend vs backend can differ legitimately)
    if (diff >= 15) {
      (window.debugLogger?.warn || console.warn)('⚠️ Large stablecoins divergence between targets_by_group and risk_budget',
        { stablesFinal, stablesBudget, diff: `${diff.toFixed(1)}%` });
    } else if (diff >= 5) {
      console.debug('ℹ️ Moderate stablecoins divergence (expected):', { stablesFinal, stablesBudget, diff: `${diff.toFixed(1)}%` });
    }
  }

  // 🆕 Exposer Structure Modulation V2 (Oct 2025)
  // ctx.structure_modulation est défini dans computeMacroTargetsDynamic()
  // On le récupère depuis le contexte utilisé pour les targets
  const structureMod = await (async () => {
    try {
      // Reconstruire le contexte (même que pour targets_by_group)
      const ctx = {
        regime: regimeData.regime?.name?.toLowerCase(),
        cycle_score: cycleData.score,
        governance_mode: decision.governance_mode || 'Normal',
        sentiment: sentimentData?.interpretation,
        flags: {
          phase_engine: typeof window !== 'undefined' ?
            localStorage.getItem('PHASE_ENGINE_ENABLED') || 'shadow' : 'off'
        }
      };

      const rb = regimeData.risk_budget;
      const dataForModulation = { risk: { risk_metrics: risk } };

      // Appeler computeMacroTargetsDynamic pour obtenir ctx.structure_modulation
      computeMacroTargetsDynamic(ctx, rb, {}, dataForModulation);

      return ctx.structure_modulation || null;
    } catch (error) {
      console.warn('⚠️ Structure modulation unavailable:', error);
      return null;
    }
  })();

  unifiedState.structure_modulation = structureMod;

  // Timestamp fiable
  unifiedState.lastUpdate = rb?.generated_at || unifiedState?.lastUpdate || new Date().toISOString();

  return unifiedState;
}

/**
 * Génère un ID de snapshot basé sur les données stables (pas les timestamps auto-générés)
 */
function snapshotId(u) {
  return JSON.stringify({
    user: u.user?.id || localStorage.getItem('activeUser') || 'demo',
    source: u.meta?.data_source,
    // Scores arrondis pour stabilité (pas de timestamps qui changent)
    blended: Math.round(u.decision?.score || 50),
    onchain: Math.round(u.scores?.onchain || 50),
    risk: Math.round(u.scores?.risk || 50),
    cycle: Math.round(u.scores?.cycle || 50),
    // Governance stable
    contradiction: Math.round((u.governance?.contradiction_index || 0) * 100),
    // Risk budget stable (arrondi)
    stables_alloc: Math.round((u.risk?.budget?.stables_allocation || 0) * 100),
    // Regime key (pas timestamp)
    regime_key: u.regime?.key,
    // Strategy template (pas generated_at)
    strategy_template: u.strategy?.template_used
  });
}

// Cache snapshot-based avec TTL 30s
let _recoCache = { snapshotId: null, recos: null, timestamp: 0 };

/**
 * Dérivation des recommandations avec cache snapshot-based et stabilité renforcée
 */
export function deriveRecommendations(u) {
  // Vérifier cache snapshot d'abord
  const currentSnapshotId = snapshotId(u);
  const now = Date.now();

  if (_recoCache.snapshotId === currentSnapshotId && now - _recoCache.timestamp < 30000) {
    console.debug('🎯 Recommendations from snapshot cache:', _recoCache.recos.length);
    return _recoCache.recos;
  }

  console.debug('🧠 DERIVING INTELLIGENT RECOMMENDATIONS V2 - Snapshot:', currentSnapshotId.substring(0, 120) + '...');
  console.debug('📊 Snapshot Key Factors:', {
    blended: Math.round(u.decision?.score || 50),
    onchain: Math.round(u.scores?.onchain || 50),
    risk: Math.round(u.scores?.risk || 50),
    cycle: Math.round(u.scores?.cycle || 50),
    contradiction: Math.round((u.governance?.contradiction_index || 0) * 100),
    stables_alloc: Math.round((u.risk?.budget?.stables_allocation || 0) * 100),
    regime_key: u.regime?.key
  });

  let recos = [];

  // 1. USE STRATEGY API TARGETS avec primary stable (tie-breaker)
  if (u.strategy?.targets?.length > 0) {
    // Tri stable: poids DESC puis symbol ASC
    const targets = [...u.strategy.targets].sort((a,b) =>
      (b.weight - a.weight) || (a.symbol||'').localeCompare(b.symbol||'')
    );

    let primaryTarget = targets[0];
    const prevPrimary = window.__prevPrimaryTarget;

    // Hysteresis: si écart < 0.5% avec 2e, garder l'ancien (éviter flip visuel)
    if (prevPrimary && targets[1] && Math.abs(primaryTarget.weight - targets[1].weight) < 0.005) {
      const prevStillTop = targets.find(t => t.symbol === prevPrimary.symbol);
      if (prevStillTop && prevStillTop.weight >= targets[0].weight - 0.005) {
        primaryTarget = prevStillTop;
      }
    }
    window.__prevPrimaryTarget = primaryTarget;

    const isStablesTarget = /stablecoin/i.test(primaryTarget.symbol);
    const allocPct = Math.round(primaryTarget.weight * 100);

    recos.push({
      key: `reco:strategy:primary:${primaryTarget.symbol}`,  // Clé canonique stable
      topic: isStablesTarget ? 'stables_allocation' : undefined,
      value: isStablesTarget ? allocPct : undefined,
      priority: 'high',
      title: `Allocation ${primaryTarget.symbol}: ${allocPct}%`,
      reason: primaryTarget.rationale || `Suggestion ${u.strategy.template_used}`,
      icon: '🎯',
      source: 'strategy-api'
    });
  }

  // 2. USE REGIME RECOMMENDATIONS avec clés canoniques
  if (u.intelligence?.regimeRecommendations?.length > 0) {
    u.intelligence.regimeRecommendations.forEach(rec => {
      // Générer clé stable basée sur type + message
      const regimeKey = rec.type || 'general';
      const msgHash = (rec.message || rec.action || '').toLowerCase().replace(/[^a-z0-9]/g, '_').substring(0, 30);

      // Extract stables percentage if mentioned (check BOTH message AND action)
      const messageText = rec.message || '';
      const actionText = rec.action || '';
      const combinedText = messageText + ' ' + actionText;
      const stablesMatch = combinedText.match(/(\d+)%/);
      const isStablesReco = /stables?/i.test(combinedText);

      // DEBUG: Log detection
      if (isStablesReco) {
        console.log('[CONSOLIDATION DEBUG] Regime stables reco detected:', {
          message: rec.message,
          action: rec.action,
          stablesMatch: stablesMatch?.[1],
          isStablesReco
        });
      }

      recos.push({
        key: `reco:regime:${regimeKey}:${msgHash}`,
        topic: isStablesReco ? 'stables_allocation' : undefined,
        value: isStablesReco && stablesMatch ? parseInt(stablesMatch[1]) : undefined,
        priority: rec.priority || 'medium',
        title: rec.message || rec.title || rec.action,
        reason: rec.action || rec.message || 'Recommandation du régime de marché',
        icon: rec.type === 'warning' ? '⚠️' : rec.type === 'alert' ? '🚨' : '💡',
        source: 'regime-intelligence'
      });
    });
  }

  // 3. CYCLE-BASED RECOMMENDATIONS avec clés canoniques
  if (u.cycle?.phase?.phase) {
    const phase = u.cycle.phase.phase;
    if (phase === 'peak' && u.decision.score > 75) {
      recos.push({
        key: 'reco:cycle:peak_profits',
        priority: 'high',
        title: 'Prendre des profits progressifs',
        reason: `Phase ${u.cycle.phase.description} + Score élevé`,
        icon: '📈',
        source: 'cycle-intelligence'
      });
    } else if (phase === 'accumulation' && u.decision.score < 40) {
      recos.push({
        key: 'reco:cycle:accumulation',
        priority: 'medium',
        title: 'Accumuler positions de qualité',
        reason: `Phase ${u.cycle.phase.description} + Score bas`,
        icon: '🔵',
        source: 'cycle-intelligence'
      });
    }
  }

  // 4. STRATEGY API POLICY HINTS avec clés canoniques
  if (u.strategy?.policy_hint) {
    const policyHint = u.strategy.policy_hint;
    if (policyHint === 'Slow') {
      recos.push({
        key: 'reco:policy:slow',
        priority: 'medium',
        title: 'Approche prudente recommandée',
        reason: 'Signaux contradictoires ou confiance faible détectée',
        icon: '🐌',
        source: 'strategy-api-policy'
      });
    } else if (policyHint === 'Aggressive') {
      recos.push({
        key: 'reco:policy:aggressive',
        priority: 'high',
        title: 'Opportunité d\'allocation agressive',
        reason: 'Score élevé et signaux cohérents',
        icon: '⚡',
        source: 'strategy-api-policy'
      });
    }
  }

  // 5. CONTRADICTION ALERTS avec hysteresis + clés canoniques
  const governanceContradiction = u.governance?.contradiction_index || 0;
  const onchainContradictions = u.contradictions?.length || 0;

  // Init flags hysteresis
  if (!window.__recoFlags) window.__recoFlags = {};
  const flags = window.__recoFlags;

  // Fonction flip pour Schmitt trigger
  const flip = (prev, val, up, down) => prev ? (val > down) : (val >= up);

  // Hysteresis sur contradiction governance (up=0.35, down=0.25)
  flags.contradiction_high = flip(flags.contradiction_high, governanceContradiction, 0.35, 0.25);

  if (flags.contradiction_high) {
    const isVeryHigh = governanceContradiction > 0.7;
    recos.push({
      key: isVeryHigh ? 'reco:gov:contradiction_very_high' : 'reco:gov:contradiction_high',
      priority: isVeryHigh ? 'high' : 'medium',
      title: `Signaux contradictoires: ${Math.round(governanceContradiction * 100)}%`,
      reason: isVeryHigh ?
        'Forte contradiction détectée - approche prudente recommandée' :
        'Contradiction modérée détectée entre sources',
      icon: isVeryHigh ? '🚨' : '⚡',
      source: 'governance-contradiction'
    });
  } else if (onchainContradictions > 0 && governanceContradiction < 0.25) {
    // Fallback vers contradictions on-chain seulement si governance très faible
    recos.push({
      key: 'reco:onchain:contradiction',
      priority: 'medium',
      title: 'Signaux on-chain contradictoires détectés',
      reason: `${onchainContradictions} divergence(s) entre indicateurs`,
      icon: '⚡',
      source: 'onchain-contradiction'
    });
  }

  // 6. RISK BUDGET RECOMMENDATIONS avec hysteresis (up=0.45, down=0.37)
  const stablesAlloc = u.risk?.budget?.stables_allocation || 0;
  flags.stables_high = flip(flags.stables_high, stablesAlloc, 0.45, 0.37);

  if (flags.stables_high) {
    recos.push({
      key: 'reco:risk:stables_high',
      topic: 'stables_allocation',
      value: u.risk.budget.percentages?.stables,
      priority: 'medium',
      title: `Allocation stables: ${u.risk.budget.percentages?.stables}%`,
      reason: 'Budget de risque calculé par algorithme sophistiqué',
      icon: '🛡️',
      source: 'risk-budget'
    });
  }

  // CONSOLIDATION DES RECOMMENDATIONS STABLES (même allocation = 1 seule carte)
  function consolidateStablesRecommendations(recos) {
    const stablesRecs = recos.filter(r => r.topic === 'stables_allocation');

    // DEBUG: Log all stables recommendations detected
    console.log('[CONSOLIDATION DEBUG] Stables recommendations found:', {
      count: stablesRecs.length,
      recos: stablesRecs.map(r => ({
        key: r.key,
        topic: r.topic,
        value: r.value,
        title: r.title,
        reason: r.reason,
        source: r.source
      }))
    });

    if (stablesRecs.length <= 1) return recos; // Pas de duplication

    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    const value = stablesRecs[0].value ?? stablesRecs[0].title?.match(/(\d+)%/)?.[1];
    const sources = [...new Set(stablesRecs.map(r => r.source))];
    const topPriority = stablesRecs.reduce((p, r) =>
      order[p] <= order[r.priority] ? p : r.priority, 'medium'
    );

    // Mapper les sources à des labels lisibles
    const sourceLabels = {
      'strategy-api': 'Strategy',
      'regime-intelligence': 'Regime',
      'risk-budget': 'Risk'
    };

    const merged = {
      key: `reco:stables:consensus:${value}`,
      topic: 'stables_allocation',
      value: value,
      priority: topPriority,
      title: `Allocation stables: ${value}%`,
      subtitle: `Consensus confirmé par ${sources.length} sources`,
      reason: stablesRecs.map(r => {
        const sourceLabel = sourceLabels[r.source] || r.source;
        return `• ${sourceLabel}: ${r.reason || r.title}`;
      }).join('\n'),
      icon: '🎯',
      source: sources.join(' + '),
      consolidated: true,
      sourceCount: sources.length
    };

    console.log('[CONSOLIDATION DEBUG] Merged recommendation:', merged);

    // Remplacer les N cartes par 1
    return [merged, ...recos.filter(r => r.topic !== 'stables_allocation')];
  }

  // Appliquer consolidation
  recos = consolidateStablesRecommendations(recos);

  // DÉDUPLICATION + TRI STABLE par clé canonique
  const prio = { critical: 0, high: 1, medium: 2, low: 3 };
  const uniqueRecos = Array.from(new Map(recos.map(r => [r.key, r])).values())
    .sort((a,b) =>
      (prio[a.priority] - prio[b.priority]) ||
      (a.source||'').localeCompare(b.source||'') ||
      (a.key||'').localeCompare(b.key||'')
    );

  // Sauvegarder dans cache snapshot
  _recoCache = {
    snapshotId: currentSnapshotId,
    recos: uniqueRecos,
    timestamp: now
  };

  console.debug('🎯 Recommendations derived:', uniqueRecos.length, 'unique from', [...new Set(uniqueRecos.map(r => r.source))].join(', '));
  console.debug('🔑 Snapshot ID:', currentSnapshotId.substring(0, 80) + '...');

  return uniqueRecos;
}

// Exports pour compatibilité
export { calculateIntelligentDecisionIndexAPI as calculateIntelligentDecisionIndex };
export { clamp01, pct, colorForScore };  // Utilitaires conservés

// Export de la fonction critique pour simulation-engine.js
export { computeMacroTargetsDynamic };