// static/core/risk-data-orchestrator.js
// Orchestrateur centralisé pour hydrater le risk store avec toutes les métriques calculées
// Utilisé par rebalance.html, analytics-unified.html, execution.html pour parité avec risk-dashboard.html

import { fetchAndComputeCCS, DEFAULT_CCS_WEIGHTS } from '../modules/signals-engine.js';
import { estimateCyclePosition, blendCCS, getCyclePhase } from '../modules/cycle-navigator.js';
import { fetchAllIndicators, calculateCompositeScore, enhanceCycleScore } from '../modules/onchain-indicators.js';
import { getRegimeDisplayData } from '../modules/market-regimes.js';

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

  try {
    // Fetch alerts d'abord (asynchrone, indépendant des autres calculs)
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

    // Calculer toutes les métriques en parallèle pour performance optimale
    // NOTE: estimateCyclePosition() est SYNCHRONE, on le wrap dans Promise.resolve()
    const [ccsResult, cycleResult, indicatorsResult, alertsResult] = await Promise.allSettled([
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
      fetchAllIndicators().catch(err => {
        console.warn('⚠️ On-chain indicators fetch failed:', err);
        return null;
      }),
      fetchAlerts()
    ]);

    // Extraire les résultats (null si échec)
    const ccs = ccsResult.status === 'fulfilled' ? ccsResult.value : null;
    const cycle = cycleResult.status === 'fulfilled' ? cycleResult.value : null;
    const indicators = indicatorsResult.status === 'fulfilled' ? indicatorsResult.value : null;
    const alerts = alertsResult.status === 'fulfilled' ? alertsResult.value : [];

    // Calculer score composite on-chain
    let onchainScore = null;
    if (indicators && indicators.length > 0) {
      try {
        onchainScore = calculateCompositeScore(indicators);
      } catch (err) {
        console.warn('⚠️ On-chain composite score calculation failed:', err);
      }
    }

    // Calculer blended score (CCS + Cycle)
    let blendedScore = null;
    if (ccs && cycle) {
      try {
        blendedScore = blendCCS(ccs.score, cycle.ccsStar || ccs.score);
      } catch (err) {
        console.warn('⚠️ Blended score calculation failed:', err);
      }
    }

    // Calculer market regime (nécessite blended + onchain + risk scores)
    let regime = null;
    if (blendedScore !== null || onchainScore !== null) {
      try {
        // getRegimeDisplayData retourne { phase, cap, contradiction, ... }
        const riskScore = currentState.scores?.risk || null;
        regime = getRegimeDisplayData(
          blendedScore || 50,
          onchainScore || 50,
          riskScore || 50
        );
      } catch (err) {
        console.warn('⚠️ Market regime calculation failed:', err);
      }
    }

    // Récupérer état actuel pour préserver données existantes
    const currentState = window.riskStore.getState();

    // Construire nouveau état avec métriques calculées
    const newState = {
      ...currentState,
      // CCS Mixte
      ccs: ccs || currentState.ccs || { score: null },

      // Cycle position
      cycle: cycle || currentState.cycle || {
        ccsStar: null,
        months: null,
        phase: null
      },

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
        // Préserver risk score existant (calculé par backend)
        risk: currentState.scores?.risk
      },

      // Alerts (IMPORTANT: doit être un tableau pour risk-sidebar-full.js)
      alerts: alerts || [],

      // Metadata hydratation
      _hydrated: true,
      _hydration_timestamp: new Date().toISOString(),
      _hydration_duration_ms: Math.round(performance.now() - startTime)
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
          regime: regime !== null,
          alerts: alerts.length > 0
        }
      }
    }));

    const duration = Math.round(performance.now() - startTime);
    console.log(`✅ Risk store hydrated successfully in ${duration}ms`, {
      ccs: ccs ? `${ccs.score} (${ccs.interpretation})` : 'N/A',
      cycle: cycle ? `${cycle.phase} (${cycle.months}mo)` : 'N/A',
      onchain: onchainScore !== null ? onchainScore.toFixed(1) : 'N/A',
      blended: blendedScore !== null ? blendedScore.toFixed(1) : 'N/A',
      regime: regime ? regime.phase : 'N/A',
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
