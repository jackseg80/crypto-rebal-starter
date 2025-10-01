// static/core/risk-data-orchestrator.js
// Orchestrateur centralisé pour hydrater le risk store avec toutes les métriques calculées
// Utilisé par rebalance.html, analytics-unified.html, execution.html pour parité avec risk-dashboard.html

import { fetchAndComputeCCS, DEFAULT_CCS_WEIGHTS } from '../modules/signals-engine.js';
import { estimateCyclePosition, blendCCS, getCyclePhase } from '../modules/cycle-navigator.js';
import { fetchAllIndicators, calculateCompositeScore, enhanceCycleScore } from '../modules/onchain-indicators.js';
import { detectMarketRegime } from '../modules/market-regimes.js';

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
    // Calculer toutes les métriques en parallèle pour performance optimale
    const [ccsResult, cycleResult, indicatorsResult, regimeResult] = await Promise.allSettled([
      fetchAndComputeCCS().catch(err => {
        console.warn('⚠️ CCS calculation failed:', err);
        return null;
      }),
      estimateCyclePosition().catch(err => {
        console.warn('⚠️ Cycle estimation failed:', err);
        return null;
      }),
      fetchAllIndicators().catch(err => {
        console.warn('⚠️ On-chain indicators fetch failed:', err);
        return null;
      }),
      detectMarketRegime().catch(err => {
        console.warn('⚠️ Market regime detection failed:', err);
        return null;
      })
    ]);

    // Extraire les résultats (null si échec)
    const ccs = ccsResult.status === 'fulfilled' ? ccsResult.value : null;
    const cycle = cycleResult.status === 'fulfilled' ? cycleResult.value : null;
    const indicators = indicatorsResult.status === 'fulfilled' ? indicatorsResult.value : null;
    const regime = regimeResult.status === 'fulfilled' ? regimeResult.value : null;

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
          regime: regime !== null
        }
      }
    }));

    const duration = Math.round(performance.now() - startTime);
    console.log(`✅ Risk store hydrated successfully in ${duration}ms`, {
      ccs: ccs ? `${ccs.score} (${ccs.interpretation})` : 'N/A',
      cycle: cycle ? `${cycle.phase} (${cycle.months}mo)` : 'N/A',
      onchain: onchainScore !== null ? onchainScore.toFixed(1) : 'N/A',
      blended: blendedScore !== null ? blendedScore.toFixed(1) : 'N/A',
      regime: regime ? regime.phase : 'N/A'
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
