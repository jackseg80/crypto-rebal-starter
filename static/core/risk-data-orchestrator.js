// static/core/risk-data-orchestrator.js
// Orchestrateur centralisé pour hydrater le risk store avec toutes les métriques calculées
// Utilisé par rebalance.html, analytics-unified.html, execution.html pour parité avec risk-dashboard.html

import { fetchAndComputeCCS, interpretCCS, DEFAULT_CCS_WEIGHTS } from '../modules/signals-engine.js';
import { estimateCyclePosition, blendCCS, getCyclePhase } from '../modules/cycle-navigator.js';
import { fetchAllIndicators, enhanceCycleScore } from '../modules/onchain-indicators.js';
import { calculateCompositeScoreV2 } from '../modules/composite-score-v2.js';
import { getRegimeDisplayData } from '../modules/market-regimes.js';

// ✅ Singleton guard: empêche doubles initialisations
if (window.__risk_orchestrator_init) {
  console.log('⚠️ Risk orchestrator already initialized, skipping duplicate');
} else {
  window.__risk_orchestrator_init = true;
  console.log('✅ Risk orchestrator initialized (singleton)');
}

/**
 * Hydrate le risk store avec toutes les métriques calculées
 * Appelé après chargement du store pour peupler CCS, Cycle, On-Chain, Regime
 * Ré-émet riskStoreReady après hydratation complète
 *
 * @returns {Promise<void>}
 * @throws {Error} Si riskStore n'est pas disponible ou si calculs échouent
 */
export async function hydrateRiskStore() {
  if (!window.riskStore) {
    throw new Error('riskStore not available - ensure core/risk-dashboard-store.js is loaded first');
  }

  console.log('🔄 Starting risk store hydration...');
  const startTime = performance.now();

  // ✅ Détecter hard refresh (Ctrl+Shift+R) pour forcer cache bust
  const isHardRefresh = performance.navigation?.type === 1 ||
                        performance.getEntriesByType?.('navigation')?.[0]?.type === 'reload';
  const forceRefresh = isHardRefresh || false;
  if (forceRefresh) {
    console.log('🔄 Hard refresh detected, forcing cache refresh');
  }

  try {
    // Fetch alerts (asynchrone, indépendant des autres calculs)
    const fetchAlerts = async () => {
      try {
        if (!window.globalConfig?.apiRequest) {
          console.warn('⚠️ globalConfig.apiRequest not available for alerts');
          return [];
        }
        const alertsData = await window.globalConfig.apiRequest('/api/alerts/active', {
          params: { include_snoozed: false }
        });
        return Array.isArray(alertsData) ? alertsData : [];
      } catch (err) {
        console.warn('⚠️ Alerts fetch failed:', err);
        return [];
      }
    };

    // Fetch risk data from API (pour risk score)
    const fetchRiskData = async () => {
      try {
        if (!window.globalConfig?.apiRequest) {
          console.warn('⚠️ globalConfig.apiRequest not available for risk data');
          return null;
        }
        const riskData = await window.globalConfig.apiRequest('/api/risk/dashboard', {
          params: { min_usd: 1.0, price_history_days: 365, lookback_days: 90 }
        });
        return riskData;
      } catch (err) {
        console.warn('⚠️ Risk data fetch failed:', err);
        return null;
      }
    };

    // Fetch governance state (pour contradiction_index autoritaire)
    const fetchGovernanceState = async () => {
      try {
        const response = await fetch(`${window.location.origin}/execution/governance/state`);
        if (!response.ok) {
          console.warn('⚠️ Governance state fetch failed:', response.status);
          return null;
        }
        return await response.json();
      } catch (err) {
        console.warn('⚠️ Governance state fetch failed:', err);
        return null;
      }
    };

    // Calculer risk score depuis risk_metrics (même logique que risk-dashboard.html)
    const calculateRiskScore = (riskData) => {
      if (!riskData?.risk_metrics) return null;

      const metrics = riskData.risk_metrics;
      let score = 50; // Start neutral
      let factors = 0;

      // Sharpe ratio (higher is better)
      if (metrics.sharpe_ratio != null) {
        score += metrics.sharpe_ratio > 1 ? 20 : metrics.sharpe_ratio > 0.5 ? 10 : -10;
        factors++;
      }

      // Volatility (lower is better for risk score)
      if (metrics.volatility != null) {
        const vol = Math.abs(metrics.volatility);
        score += vol < 0.2 ? 15 : vol < 0.4 ? 5 : -15;
        factors++;
      }

      // Max Drawdown (lower is better)
      if (metrics.max_drawdown != null) {
        const dd = Math.abs(metrics.max_drawdown);
        score += dd < 0.15 ? 10 : dd < 0.3 ? 0 : -10;
        factors++;
      }

      // Correlation (lower is better - more diversification)
      if (metrics.avg_correlation != null) {
        const corr = Math.abs(metrics.avg_correlation);
        score += corr < 0.3 ? 10 : corr < 0.5 ? 5 : -5;
        factors++;
      }

      return factors > 0 ? Math.max(0, Math.min(100, score)) : 50;
    };

    // Calculer toutes les métriques en parallèle pour performance optimale
    // NOTE: estimateCyclePosition() est SYNCHRONE, on le wrap dans Promise.resolve()
    const [ccsResult, cycleResult, indicatorsResult, alertsResult, riskResult, governanceResult] = await Promise.allSettled([
      fetchAndComputeCCS().catch(err => {
        console.warn('⚠️ CCS calculation failed:', err);
        return null;
      }),
      Promise.resolve().then(() => {
        try {
          return estimateCyclePosition();
        } catch (err) {
          console.warn('⚠️ Cycle estimation failed:', err);
          return null;
        }
      }),
      fetchAllIndicators({ force: forceRefresh }).catch(err => {
        console.warn('⚠️ On-chain indicators fetch failed:', err);
        return null;
      }),
      fetchAlerts(),
      fetchRiskData(),
      fetchGovernanceState()
    ]);

    // Extraire les résultats (null si échec)
    let ccs = ccsResult.status === 'fulfilled' ? ccsResult.value : null;
    const cycle = cycleResult.status === 'fulfilled' ? cycleResult.value : null;
    const indicators = indicatorsResult.status === 'fulfilled' ? indicatorsResult.value : null;
    const alerts = alertsResult.status === 'fulfilled' ? alertsResult.value : [];
    const riskData = riskResult.status === 'fulfilled' ? riskResult.value : null;
    const governanceState = governanceResult.status === 'fulfilled' ? governanceResult.value : null;

    // Calculer risk score depuis riskData
    const riskScore = riskData ? calculateRiskScore(riskData) : null;

    // Utiliser contradiction_index autoritaire depuis governance state (source de vérité backend)
    const contradiction = governanceState?.contradiction_index ?? null;

    // Ajouter interpretation au CCS si manquant
    if (ccs && !ccs.interpretation) {
      ccs = { ...ccs, interpretation: interpretCCS(ccs.score) };
    }

    // Calculer score composite on-chain avec V2 (plus précis, dynamic weighting always enabled)
    let onchainScore = null;
    if (indicators && Object.keys(indicators).length > 0) {
      try {
        const compositeResult = calculateCompositeScoreV2(indicators, true);
        // calculateCompositeScoreV2 returns { score, confidence, contributors, ... }
        onchainScore = compositeResult?.score ?? null;
      } catch (err) {
        console.warn('⚠️ On-chain composite score calculation failed:', err);
      }
    }

    // Récupérer état actuel AVANT tout calcul (pour préserver données existantes)
    const currentState = window.riskStore.getState();

    // Calculer blended score (CCS + Cycle)
    // Blend CCS with Cycle to get ccsStar
    let ccsStar = null;
    if (ccs && cycle) {
      try {
        const blendResult = blendCCS(ccs.score, cycle.months || 18);
        // blendCCS returns { originalCCS, cycleScore, blendedCCS, cycleWeight, phase }
        ccsStar = blendResult?.blendedCCS ?? null;
      } catch (err) {
        console.warn('⚠️ CCS blend calculation failed:', err);
      }
    }

    // Calculate final blended score (CCS*0.5 + OnChain*0.3 + Risk*0.2)
    let blendedScore = null;
    if (ccsStar !== null || onchainScore !== null || riskScore !== null) {
      const wCCS = 0.50;
      const wOnchain = 0.30;
      const wRisk = 0.20;

      let totalScore = 0;
      let totalWeight = 0;

      if (ccsStar !== null) {
        totalScore += ccsStar * wCCS;
        totalWeight += wCCS;
      }
      if (onchainScore !== null) {
        totalScore += onchainScore * wOnchain;
        totalWeight += wOnchain;
      }
      if (riskScore !== null) {
        totalScore += riskScore * wRisk;
        totalWeight += wRisk;
      }

      blendedScore = totalWeight > 0 ? Math.round(totalScore / totalWeight) : null;
    }

    // Calculer market regime (nécessite blended + onchain + risk scores)
    let regime = null;
    if (blendedScore !== null || onchainScore !== null) {
      try {
        // Utiliser le risk score calculé, sinon fallback sur store existant
        const finalRiskScore = riskScore ?? currentState.scores?.risk ?? 50;
        const regimeData = getRegimeDisplayData(
          blendedScore || 50,
          onchainScore || 50,
          finalRiskScore
        );
        // getRegimeDisplayData returns { regime: {...}, risk_budget, allocation, recommendations }
        regime = regimeData?.regime ?? null;
      } catch (err) {
        console.warn('⚠️ Market regime calculation failed:', err);
      }
    }

    // Construire nouveau état avec métriques calculées
    const newState = {
      ...currentState,
      // CCS Mixte
      ccs: ccs || currentState.ccs || { score: null },

      // Cycle position
      cycle: cycle ? {
        ...cycle,
        ccsStar: ccsStar // CCS blended with cycle
      } : (currentState.cycle || {
        ccsStar: null,
        months: null,
        phase: null
      }),

      // Market regime
      regime: regime || currentState.regime || {
        phase: null,
        confidence: null,
        divergence: null
      },

      // Scores unifiés
      scores: {
        ...(currentState.scores || {}),
        onchain: onchainScore,
        blended: blendedScore,
        // Risk score calculé depuis API /api/risk/dashboard
        risk: riskScore ?? currentState.scores?.risk
      },

      // Governance (pour compatibilité avec risk-sidebar-full.js)
      governance: {
        ...(currentState.governance || {}),
        // Contradiction doit être dans governance.contradiction_index (0..1)
        contradiction_index: contradiction ?? currentState.governance?.contradiction_index
      },

      // Contradiction (stockage racine pour compatibilité legacy)
      contradiction: contradiction ?? currentState.contradiction,

      // Alerts (IMPORTANT: doit être un tableau pour risk-sidebar-full.js)
      alerts: alerts || [],

      // Metadata hydratation
      _hydrated: true,
      _hydration_timestamp: new Date().toISOString(),
      _hydration_duration_ms: Math.round(performance.now() - startTime),
      _hydration_source: 'risk-data-orchestrator'  // ✅ Traçabilité source
    };

    // Mise à jour atomique du store
    window.riskStore.setState(newState);

    // Ré-émettre riskStoreReady APRÈS hydratation complète
    // Detail inclut flag hydrated:true pour différencier du premier event (store vide)
    window.dispatchEvent(new CustomEvent('riskStoreReady', {
      detail: {
        store: window.riskStore,
        hydrated: true,
        timestamp: Date.now(),
        metrics: {
          ccs: ccs !== null,
          cycle: cycle !== null,
          onchain: onchainScore !== null,
          blended: blendedScore !== null,
          risk: riskScore !== null,
          regime: regime !== null,
          contradiction: contradiction !== null,
          alerts: alerts.length > 0
        }
      }
    }));

    const duration = Math.round(performance.now() - startTime);
    console.log(`✅ Risk store hydrated successfully in ${duration}ms`, {
      ccs: ccs ? `${ccs.score} (${ccs.interpretation?.label || ccs.interpretation})` : 'N/A',
      cycle: cycle ? `${cycle.phase?.phase || cycle.phase} (${cycle.months}mo)` : 'N/A',
      onchain: onchainScore !== null && typeof onchainScore === 'number' ? onchainScore.toFixed(1) : (onchainScore || 'N/A'),
      blended: blendedScore !== null && typeof blendedScore === 'number' ? blendedScore.toFixed(1) : (blendedScore || 'N/A'),
      risk: riskScore !== null && typeof riskScore === 'number' ? riskScore.toFixed(1) : (riskScore || 'N/A'),
      regime: regime ? regime.phase : 'N/A',
      contradiction: contradiction !== null && typeof contradiction === 'number' ? contradiction.toFixed(2) : (contradiction || 'N/A'),
      alerts: `${alerts.length} alerts`
    });

  } catch (err) {
    console.error('❌ Failed to hydrate risk store:', err);

    // Marquer échec d'hydratation dans le store
    const currentState = window.riskStore.getState();
    window.riskStore.setState({
      ...currentState,
      _hydrated: false,
      _hydration_error: err.message,
      _hydration_timestamp: new Date().toISOString()
    });

    throw err;
  }
}

/**
 * Auto-init : Hydrate le store dès que le DOM est prêt
 * Garantit que les modules de calcul sont exécutés et le store rempli
 */
function autoInit() {
  // Attendre que riskStore soit disponible (chargé par risk-dashboard-store.js)
  if (window.riskStore) {
    hydrateRiskStore().catch(err => {
      console.error('Auto-init hydration failed:', err);
    });
  } else {
    // Retry après 100ms si store pas encore chargé
    console.log('⏳ Waiting for riskStore to be available...');
    setTimeout(autoInit, 100);
  }
}

// Démarrer auto-init selon état du DOM
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', autoInit);
} else {
  // DOM déjà prêt (module chargé tardivement)
  autoInit();
}
