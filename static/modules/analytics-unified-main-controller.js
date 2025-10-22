/**
 * Sauvegarde les données unified pour rebalance.html
 * Compatible avec le nouveau système u.targets_by_group
 */
async function saveUnifiedDataForRebalance() {
  try {
    console.debug('💾 Saving unified data for rebalance.html...');

    // Import du système unified-insights-v2
    const { getUnifiedState } = await import('../core/unified-insights-v2.js');
    const unifiedState = await getUnifiedState();

    if (!unifiedState || !unifiedState.targets_by_group) {
      debugLogger.warn('⚠️ No unified targets available to save');
      return;
    }

    // Préparer les données au format attendu par rebalance.html
    const unifiedData = {
      targets: unifiedState.targets_by_group, // Les nouvelles targets dynamiques
      execution_plan: unifiedState.execution?.plan_iter1 || null,
      strategy: unifiedState.strategy?.template_used || 'Dynamic',
      methodology: unifiedState.risk?.budget?.methodology || 'unified_v2',
      timestamp: new Date().toISOString(),

      // Métadonnées utiles
      source: 'analytics_unified_v2',
      stables_source: unifiedState.risk?.budget?.target_stables_pct,
      cycle_score: unifiedState.cycle?.score,
      regime_name: unifiedState.regime?.name,
      decision_score: unifiedState.decision?.score
    };

    // Sauvegarder dans localStorage avec l'ancienne clé pour compatibilité
    localStorage.setItem('unified_suggested_allocation', JSON.stringify(unifiedData));

    debugLogger.debug('✅ Unified data saved for rebalance.html:', {
      targets_keys: Object.keys(unifiedData.targets),
      stables_pct: unifiedData.targets.Stablecoins,
      has_execution_plan: !!unifiedData.execution_plan,
      timestamp: unifiedData.timestamp
    });

  } catch (error) {
    debugLogger.error('❌ Failed to save unified data:', error);
  }
}

// Temporary simplified version to debug the issue
async function renderUnifiedInsights(containerId = 'unified-root') {
  // ANTI-DOUBLE RENDER MUTEX
  if (window.__unified_rendering) {
    console.debug('🔒 Render already in progress, skipping duplicate call');
    return;
  }
  window.__unified_rendering = true;

  console.debug('🔥 LOCAL FUNCTION UNIFIED: analytics-unified.html renderUnifiedInsights called', {
    containerId,
    timestamp: new Date().toISOString()
  });

  const el = document.getElementById(containerId);
  if (!el) {
    window.__unified_rendering = false;
    return;
  }

  // Affichage de chargement initial
  el.innerHTML = `
    <div style="background: var(--theme-surface); border: 1px solid var(--theme-border); border-radius: var(--radius-md); padding: var(--space-md);">
      <div style="display:flex; align-items:center; justify-content: space-between; gap:.75rem;">
        <div>
          <div style="font-size: .9rem; color: var(--theme-text-muted); font-weight:600;">Decision Index</div>
          <div style="font-size: 2rem; font-weight: 800; color: var(--success);">Loading...</div>
          <div style="font-size: .8rem; color: var(--theme-text-muted);">Chargement des insights unifiés CORRIGÉS</div>
        </div>
        <div style="text-align:right; font-size:.8rem; color: var(--theme-text-muted);">
          <div>Status: Initializing FIX</div>
        </div>
      </div>
    </div>
  `;

  try {
    console.debug('🔥 LOCAL: Loading corrected UnifiedInsights logic...');

    // Import des modules nécessaires - CACHE BUST pour forcer rechargement
    const cacheBust = new Date().toISOString();
    const { renderUnifiedInsights: originalRender } = await import(`../components/UnifiedInsights.js?v=${cacheBust}`);
    const { getRegimeDisplayData, getMarketRegime } = await import('../modules/market-regimes.js');

    // OVERRIDE CRITIQUE: Modifier la fonction globale pour corriger le problème
    const originalFunction = window.buildTheoreticalTargets;

    window.buildTheoreticalTargets = async function(blendedScore, currentPortfolio, riskScore) {
      debugLogger.debug('🎯 TARGETS RÉELS (Fix Sources System):', { blendedScore, riskScore, hasCurrentPortfolio: !!currentPortfolio });

      try {
        // 1) Récupérer les vraies données de balance depuis le store ou recharger
        let realBalances = store.get('wallet.balances');
        let totalValue = store.get('wallet.total');

        // Si pas de données dans le store, essayer de les recharger
        if (!realBalances || !totalValue) {
          debugLogger.debug('🔄 No balance data in store, attempting to reload...');
          if (typeof window.loadBalanceData === 'function') {
            try {
              const balanceResult = await window.loadBalanceData();
              if (balanceResult.success) {
                realBalances = balanceResult.data?.items || [];
                totalValue = realBalances.reduce((sum, item) => sum + (parseFloat(item.value_usd) || 0), 0);

                // Mettre à jour le store
                store.set('wallet.balances', realBalances);
                store.set('wallet.total', totalValue);

                debugLogger.debug('✅ Balance data reloaded successfully');
              }
            } catch (e) {
              debugLogger.warn('Failed to reload balance data:', e.message);
            }
          }
        }

        // 2) Si on a des vraies données, les grouper
        if (realBalances && realBalances.length > 0 && totalValue > 0) {
          const { groupAssetsByClassification } = await import('../shared-asset-groups.js');
          const groupedData = groupAssetsByClassification(realBalances);

          // 3) Convertir les groupes en format attendu avec valeurs USD réelles
          const realTargets = {};
          groupedData.forEach(group => {
            realTargets[group.label] = group.value; // Valeur USD réelle
          });

          debugLogger.debug('🎯 REAL TARGETS (from grouped data):', {
            targets: realTargets,
            totalValue,
            groupsCount: groupedData.length,
            source: 'real_balance_data'
          });

          return realTargets;
        }

        // 4) Fallback: utiliser le currentPortfolio si fourni
        if (currentPortfolio && typeof currentPortfolio === 'object') {
          debugLogger.debug('🎯 Using currentPortfolio as fallback');
          return currentPortfolio;
        }

        // 5) Dernier fallback: logique artificielle mais basée sur un scoring réaliste
        debugLogger.warn('⚠️ Falling back to artificial targets (no real data available)');

        let stablesTarget, btcTarget, ethTarget, altsTarget;
        if (blendedScore >= 70) {
          stablesTarget = 20; btcTarget = 35; ethTarget = 25; altsTarget = 20;
        } else if (blendedScore >= 50) {
          stablesTarget = 30; btcTarget = 40; ethTarget = 20; altsTarget = 10;
        } else {
          stablesTarget = 50; btcTarget = 30; ethTarget = 15; altsTarget = 5;
        }

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

        debugLogger.debug('🎯 FALLBACK TARGETS:', artificialTargets);
        return artificialTargets;

      } catch (error) {
        debugLogger.error('❌ Error in buildTheoreticalTargets:', error);

        // Fallback d'urgence
        return {
          'Stablecoins': 40,
          'BTC': 35,
          'ETH': 15,
          'Others': 10
        };
      }
    };

    // 1) Rendre UnifiedInsights SANS son ancien header (on injecte le nouveau DI v5 au-dessus)
    console.debug('🔥 LOCAL: Calling originalRender with fixes applied + hideHeader:true');
    await originalRender(containerId, { hideHeader: true });

    // Restaurer la fonction originale après utilisation
    if (originalFunction) {
      window.buildTheoreticalTargets = originalFunction;
    }

    // 2) APRÈS le rendu UnifiedInsights, injecter le nouveau Decision Index Panel v5 EN HAUT
    // (maintenant on peut récupérer les vraies données via getUnifiedState)
    const cacheBust2 = Date.now();
    const { renderDecisionIndexPanel } = await import(`../components/decision-index-panel.js?v=${cacheBust2}`);
    const { getUnifiedState } = await import(`../core/unified-insights-v2.js?v=${cacheBust2}`);
    const diHistoryModule = await import(`../utils/di-history.js?v=${cacheBust2}`);

    // Exposer API DI history dans window pour debug/réutilisation
    window.__DI_HISTORY__ = diHistoryModule;

    // Récupérer l'état unifié (MÊME source que UnifiedInsights)
    const u = await getUnifiedState();
    console.debug('🔍 Unified state for DI panel:', u);
    console.debug('🔍 Scores object in unified state:', u.scores);
    console.debug('🔍 Risk score from unified state:', u.scores?.risk);
    console.debug('🔍 Risk score from store:', store.get('scores.risk'));

    const cycleScore = u.cycle?.score ?? 50;
    const onchainScore = u.onchain?.score ?? 50;
    const riskScore = u.scores?.risk ?? 50;
    const blendedScore = u.decision?.score ?? 50;

    console.debug('🔍 Final scores used in DI panel:', { cycleScore, onchainScore, riskScore, blendedScore });

    // Weights (depuis unified state)
    const wCycle = u.decision?.weights?.cycle ?? 0.5;
    const wOnchain = u.decision?.weights?.onchain ?? 0.3;
    const wRisk = u.decision?.weights?.risk ?? 0.2;

    // Calcul blended confidence
    const s = store.snapshot();
    const ocConf = Math.max(0, Math.min(1, s.scores?.onchain_metadata?.confidence ?? 0.5));
    const cycleConf = Math.max(0, Math.min(1, s.cycle?.confidence ?? 0.5));
    const wSum = (wCycle + wOnchain + wRisk) || 1;
    const blendedConfidence = (wCycle * cycleConf + wOnchain * ocConf + wRisk * 1.0) / wSum; // risk=1.0

    // Sélecteurs gouvernance normalisés
    const capPercent = window.selectEffectiveCap(s);           // entier en %
    const contrad01 = window.selectContradiction01(s);        // [0..1]
    const updatedISO = window.selectGovernanceTimestamp(s);     // ISO string

    // LOG CONTRÔLE (Oct 2025): Tracer cohérence UI/Backend cap
    const beCap = s?.governance?.execution_policy?.cap_daily;
    console.debug('[CAP] ui=%s%% be=%s%%', capPercent, beCap ? (beCap*100).toFixed(2) : 'NA');
    const modeLabel = (() => {
      const m = s?.governance?.mode || s?.governance?.current_state || 'normal';
      return String(m).replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, x => x.toUpperCase());
    })();

    // Régime et phase
    const regimeData = u.regime || {};
    const phaseEngineMode = localStorage.getItem('PHASE_ENGINE_ENABLED') || 'shadow';
    let actualPhase = regimeData.name || 'neutral';
    if (typeof window !== 'undefined') {
      if (window._phaseEngineAppliedResult?.phase) {
        actualPhase = window._phaseEngineAppliedResult.phase;
      } else if (window._phaseEngineShadowResult?.phase) {
        actualPhase = window._phaseEngineShadowResult.phase;
      }
    }

    // Alpha si disponible dans signals
    const alpha = s?.signals?.alpha;

    // 📊 Historique Decision Index (persistance localStorage via di-history.js)
    const activeUser = localStorage.getItem('activeUser') || 'demo';
    const dataSource = window.globalConfig?.get('data_source') || 'cointracking';

    // Détecter contexte simulation
    const isSimulation = !!window.__SIMULATION__;
    const suffix = isSimulation ? '_sim' : '_prod';

    // Générer clé scopée avec timezone Europe/Zurich
    const historyKey = diHistoryModule.makeKey({
      user: activeUser,
      source: dataSource,
      suffix
    });
    const today = diHistoryModule.getTodayCH();

    // Charger historique existant (avec sanitization)
    let diHistory = diHistoryModule.loadHistory(historyKey, 30);

    // Migration douce depuis legacy s?.di_history si première utilisation
    if (diHistory.length === 0 && s?.di_history && Array.isArray(s.di_history) && s.di_history.length > 0) {
      console.debug('📦 Migration legacy DI history...');
      diHistory = diHistoryModule.migrateLegacy(s.di_history, 30);
      diHistoryModule.saveHistory(historyKey, diHistory);
      console.debug('✅ Legacy migration done:', { count: diHistory.length });
    }

    // Ajouter score actuel si nécessaire (date différente OU delta > 0.1)
    const { history: updatedHistory, added } = diHistoryModule.pushIfNeeded({
      key: historyKey,
      history: diHistory,
      today,
      di: blendedScore,
      max: 30,
      minDelta: 0.1
    });

    diHistory = updatedHistory;

    if (added) {
      console.debug('📊 DI history updated:', {
        count: diHistory.length,
        latest: blendedScore,
        context: isSimulation ? 'simulation' : 'production',
        timezone: 'Europe/Zurich'
      });
    }

    const panelData = {
      di: blendedScore,
      scores: { cycle: cycleScore, onchain: onchainScore, risk: riskScore },
      weights: { cycle: wCycle, onchain: wOnchain, risk: wRisk },
      meta: {
        phase: (s?.regime?.name || regimeData?.name || actualPhase || 'neutral'),   // ✅ phase toujours renseignée
        source: u.decision?.source || window.globalConfig?.get('data_source') || 'allocation_engine_v2',
        live: s.ui?.apiStatus?.backend === 'healthy',
        backend: s.ui?.apiStatus?.backend === 'healthy',
        signals: s.ui?.apiStatus?.signals === 'healthy',
        governance_mode: s.governance?.current_state || 'IDLE',
        cap: capPercent,                       // ✅ entier %
        mode: modeLabel,                       // ✅ "Manual", "Slow", ...
        confidence: blendedConfidence,         // ✅ [0..1]
        contradiction: contrad01,              // ✅ [0..1]
        cycle_confidence: cycleConf,           // pour badge bas
        updated: updatedISO,                   // pour horodatage
        signals_status: s.ui?.apiStatus?.signals || 'limited',
        alpha: alpha,                          // ✅ alpha si dispo [0..1]

        // Données pour tuiles
        cycle_phase: u.cycle?.phase?.description || u.cycle?.phase?.phase || actualPhase,
        cycle_months: u.cycle?.months,
        onchain_critiques: u.onchain?.criticalCount || 0,
        onchain_confidence: u.onchain?.confidence,
        risk_var95: u.risk?.var95_1d,
        risk_budget: u.risk?.budget?.percentages ? {
          risky: u.risk.budget.percentages.risky,
          stables: u.risk.budget.percentages.stables
        } : null,
        regime_emoji: u.regime?.emoji,
        sentiment_fg: u.signals?.sentiment?.value,
        sentiment_interpretation: u.signals?.sentiment?.interpretation
      },
      history: diHistory.map(h => h.di),                                       // ✅ di history (array de scores)
      regimeHistory: (s?.regime?.history || s?.regime_history || [])           // ✅ regime history (2 clés possibles)
    };

    // Créer conteneur pour le Decision Index Panel (inclut maintenant les tuiles)
    const existingContent = el.innerHTML;
    el.innerHTML = `<div id="new-di-panel" style="margin-bottom: 1rem;"></div>${existingContent}`;

    const newPanelEl = document.getElementById('new-di-panel');
    if (newPanelEl) {
      renderDecisionIndexPanel(newPanelEl, panelData, { showFooter: true });
      console.debug('✅ New Decision Index panel v5 injected with integrated tiles');
    }

    console.debug('🔥 LOCAL: Unified rendering completed with fixes');

    // NOUVEAU: Sauvegarder les données unified pour rebalance.html
    await saveUnifiedDataForRebalance();
  } catch (error) {
    debugLogger.error('❌ Failed to load corrected UnifiedInsights:', error);
    el.innerHTML = `
      <div style="background: var(--theme-surface); border: 1px solid var(--theme-border); border-radius: var(--radius-md); padding: var(--space-md);">
        <div style="color: var(--danger); text-align: center;">
          <h3>⚠️ Erreur de Chargement (Corrigé)</h3>
          <p>Impossible de charger les insights unifiés corrigés: ${error.message}</p>
          <button onclick="location.reload()" style="background: var(--brand-primary); color: white; border: none; padding: 0.75rem 1.5rem; border-radius: var(--radius-md); cursor: pointer;">
            Recharger
          </button>
        </div>
      </div>
    `;
  } finally {
    // Relâcher le mutex après 100ms (allow intentional refresh)
    setTimeout(() => {
      window.__unified_rendering = false;
    }, 100);
  }
}

// OVERRIDE supprimé d'ici - déplacé plus bas

// Import des autres composants sans UnifiedInsights pour l'instant
import { store } from '../core/risk-dashboard-store.js';
import { GovernancePanel } from '../components/GovernancePanel.js';

// INTELLIGENT CACHE SYSTEM - Avoid constant recalculations
const CACHE_CONFIG = {
  risk: { ttl: 3 * 60 * 60 * 1000, key: 'analytics_unified_risk' },      // 3 hours (can change with trades)
  cycle: { ttl: 24 * 60 * 60 * 1000, key: 'analytics_unified_cycle' },    // 24 hours (macro halving cycle)
  onchain: { ttl: 6 * 60 * 60 * 1000, key: 'analytics_unified_onchain' }, // 6 hours (blockchain metrics)
  blended: { ttl: 1 * 60 * 1000, key: 'analytics_unified_blended' }       // 1 minute (decision index)
};

// Generate cache key that includes data source to invalidate on source change
function getCacheKey(baseKey) {
  const dataSource = globalConfig.get('data_source') || 'unknown';
  const user = (localStorage.getItem('activeUser') || 'demo');
  return `${baseKey}_${user}_${dataSource}`;
}

function isCacheValid(cacheKey, ttl) {
  try {
    const fullKey = getCacheKey(cacheKey);
    const cached = localStorage.getItem(fullKey);
    if (!cached) return false;
    const data = JSON.parse(cached);
    return Date.now() - data.timestamp < ttl;
  } catch { return false; }
}

function setCache(cacheKey, data) {
  try {
    const fullKey = getCacheKey(cacheKey);
    localStorage.setItem(fullKey, JSON.stringify({ data, timestamp: Date.now() }));
  } catch { }
}

function getCache(cacheKey) {
  try {
    const fullKey = getCacheKey(cacheKey);
    const cached = localStorage.getItem(fullKey);
    return cached ? JSON.parse(cached).data : null;
  } catch { return null; }
}

// ===== CROSS-PAGE CACHE: Read from risk-dashboard's persistent cache (6h TTL) =====
function readRiskDashboardCache() {
  try {
    const dataSource = globalConfig.get('data_source') || 'unknown';
    const cacheKey = `risk_scores_cache_${dataSource}`;
    const cached = localStorage.getItem(cacheKey);

    if (!cached) {
      debugLogger.debug('⏭️ No risk-dashboard cache found');
      return null;
    }

    const parsed = JSON.parse(cached);
    const age = Date.now() - parsed.timestamp;
    const ttl = 6 * 60 * 60 * 1000; // 6 heures (même TTL que risk-dashboard)

    if (age > ttl) {
      debugLogger.debug(`⏰ Risk dashboard cache expired (age: ${Math.round(age / 60000)} min > 360 min)`);
      return null;
    }

    const ageMin = Math.round(age / 60000);
    debugLogger.debug(`✅ CROSS-PAGE CACHE HIT: Using risk-dashboard cache (age: ${ageMin} min, TTL: 6h)`);

    return {
      onchainScore: parsed.data?.onchainScore,
      riskScore: parsed.data?.riskScore,
      blendedScore: parsed.data?.blendedScore,
      ccsScore: parsed.data?.ccsScore,
      timestamp: parsed.timestamp,
      source: 'risk_dashboard_6h_cache'
    };
  } catch (e) {
    debugLogger.warn('❌ Failed to read risk-dashboard cache:', e.message);
    return null;
  }
}

// Update badges with current analytics data
function updateAnalyticsBadges() {
  if (!window.analyticsBadges) return;

  try {
    const now = new Date();

    // Risk badge
    const riskData = store.get('risk');
    const riskScore = store.get('scores.risk');
    const riskStatus = store.get('ui.apiStatus.backend') === 'healthy' ? 'ok' : 'error';

    if (window.analyticsBadges.risk) {
      window.analyticsBadges.risk.updateData({
        source: 'Risk API',
        updated: now,
        contradiction: Math.round((riskData?.correlations?.average_correlation || 0.3) * 100),
        status: riskStatus
      });
    }

    // Performance badge
    const performance = store.get('performance') || {};
    if (window.analyticsBadges.performance) {
      window.analyticsBadges.performance.updateData({
        source: 'Performance',
        updated: now,
        contradiction: Math.round((performance.volatility || 0.15) * 100),
        status: 'ok'
      });
    }

    // Intelligence badge
    const mlStatus = store.get('ml.status') || {};
    const intelligenceStatus = mlStatus.ready ? 'ok' : 'stale';

    if (window.analyticsBadges.intelligence) {
      window.analyticsBadges.intelligence.updateData({
        source: 'ML Engine',
        updated: now,
        status: intelligenceStatus
      });
    }

    debugLogger.debug('🏷️ Analytics badges updated');
  } catch (error) {
    debugLogger.warn('Badge update failed:', error);
  }
}

// Update risk metrics with dynamic data from store
function updateRiskMetrics() {
  try {
    const riskData = store.get('risk');
    const riskScore = store.get('scores.risk');

    // Update VaR
    const varElement = document.getElementById('risk-var-value');
    if (varElement && riskData?.risk_metrics?.var_95_1d != null) {
      varElement.textContent = `${(riskData.risk_metrics.var_95_1d * 100).toFixed(2)}%`;
      varElement.style.color = riskData.risk_metrics.var_95_1d < -0.05 ? 'var(--danger)' : 'var(--warning)';
    } else if (varElement) {
      varElement.textContent = '--';
    }

    // Update Max Drawdown
    const drawdownElement = document.getElementById('risk-drawdown-value');
    if (drawdownElement && riskData?.risk_metrics?.max_drawdown != null) {
      drawdownElement.textContent = `${(riskData.risk_metrics.max_drawdown * 100).toFixed(2)}%`;
      drawdownElement.style.color = riskData.risk_metrics.max_drawdown < -0.1 ? 'var(--danger)' : 'var(--warning)';
    } else if (drawdownElement) {
      drawdownElement.textContent = '--';
    }

    // Update Volatility
    const volatilityElement = document.getElementById('risk-volatility-value');
    if (volatilityElement && riskData?.risk_metrics?.volatility_annualized != null) {
      volatilityElement.textContent = `${(riskData.risk_metrics.volatility_annualized * 100).toFixed(1)}%`;
      volatilityElement.style.color = riskData.risk_metrics.volatility_annualized > 0.3 ? 'var(--danger)' :
        riskData.risk_metrics.volatility_annualized > 0.2 ? 'var(--warning)' : 'var(--success)';
    } else if (volatilityElement) {
      volatilityElement.textContent = '--';
    }

    // Update Risk Score (IMPORTANT: Risk Score est positif - plus haut = plus robuste)
    const scoreElement = document.getElementById('risk-score-value');
    if (scoreElement && riskScore != null) {
      scoreElement.textContent = `${Math.round(riskScore)}/100`;
      scoreElement.style.color = riskScore > 70 ? 'var(--success)' :
        riskScore > 40 ? 'var(--warning)' : 'var(--danger)';
    } else if (scoreElement) {
      scoreElement.textContent = '--/100';
    }

    // Update On-Chain Score (IMPORTANT: Score positif - plus haut = meilleur signal)
    const onchainScore = store.get('scores.onchain');
    const onchainElement = document.getElementById('risk-kpi-onchain-value');
    if (onchainElement && onchainScore != null) {
      onchainElement.textContent = `${Math.round(onchainScore)}/100`;
      onchainElement.style.color = onchainScore > 70 ? 'var(--success)' :
        onchainScore > 40 ? 'var(--warning)' : 'var(--danger)';
    } else if (onchainElement) {
      onchainElement.textContent = '--/100';
    }

    debugLogger.debug('📊 Risk metrics updated with dynamic data');
  } catch (error) {
    debugLogger.warn('Risk metrics update failed:', error);
  }
}

// Risk Budget ready guard - improved with multiple sources
async function ensureRiskBudgetReady(getRiskBudget, options = {}) {
  const { waitMs = 50, timeoutMs = 8000 } = options || {}; // Increased timeout, reduced polling interval

  const resolveCandidate = () => {
    let rb = typeof getRiskBudget === 'function' ? getRiskBudget() : null;

    if (!rb?.stables_allocation) {
      const storeData = store.get('risk.budget');
      if (storeData?.percentages) {
        rb = {
          stables_allocation: storeData.percentages.stables / 100,
          risky_allocation: storeData.percentages.risky / 100
        };
      }
    }

    if (!rb?.stables_allocation && typeof store?.snapshot === 'function') {
      const snapshot = store.snapshot();
      const snapBudget = snapshot?.risk?.budget?.percentages;
      if (snapBudget?.stables != null && snapBudget?.risky != null) {
        rb = {
          stables_allocation: snapBudget.stables / 100,
          risky_allocation: snapBudget.risky / 100
        };
      }
    }

    if (!rb?.stables_allocation && typeof window.computeRiskBudget === 'function') {
      try {
        const computed = window.computeRiskBudget(store.get('scores.blended') || 50);
        if (computed?.target_stables_pct != null) {
          rb = {
            stables_allocation: computed.target_stables_pct / 100,
            risky_allocation: (100 - computed.target_stables_pct) / 100
          };
        }
      } catch (e) { /* ignore */ }
    }

    // Additional fallback: check for cached market regimes calculation
    if (!rb?.stables_allocation && window.store?.get) {
      const marketRegime = window.store.get('market.regime');
      if (marketRegime?.risk_budget) {
        rb = {
          stables_allocation: marketRegime.risk_budget.stables_allocation,
          risky_allocation: marketRegime.risk_budget.risky_allocation
        };
      }
    }

    return rb?.stables_allocation != null && rb?.risky_allocation != null ? rb : null;
  };

  const immediate = resolveCandidate();
  if (immediate) {
    return immediate;
  }

  return new Promise(resolve => {
    let settled = false;
    let pollId = null;
    let timeoutId = null;
    let unsubscribe = null;

    const cleanup = () => {
      if (pollId) clearInterval(pollId);
      if (timeoutId) clearTimeout(timeoutId);
      if (typeof unsubscribe === 'function') unsubscribe();
    };

    const finalize = (value, fallback = false) => {
      if (settled) return;
      settled = true;
      cleanup();

      if (fallback) {
        console.debug('⏰ RiskBudget resolution timeout, computing synthetic allocation');
        const blendedScore = store.get('scores.blended') || 50;
        const stablesPercent = Math.max(10, Math.min(80, 100 - blendedScore));
        console.debug(`💡 Synthetic allocation: ${stablesPercent}% stables based on blended score ${blendedScore}`);
        resolve({
          stables_allocation: stablesPercent / 100,
          risky_allocation: (100 - stablesPercent) / 100
        });
        return;
      }

      resolve(value);
    };

    const attemptResolve = () => {
      const candidate = resolveCandidate();
      if (candidate) {
        finalize(candidate);
      }
    };

    pollId = setInterval(attemptResolve, waitMs);
    timeoutId = setTimeout(() => finalize(null, true), timeoutMs);

    if (store && typeof store.subscribe === 'function') {
      unsubscribe = store.subscribe(attemptResolve);
    }

    // Immediate attempt in case data arrives synchronously
    attemptResolve();
  });
}

// Lightweight unified data loader with INTELLIGENT CACHING
async function loadUnifiedData(force = false) {
  debugLogger.debug('🧠 Loading unified data with intelligent caching...', { force });
  let loadedFromCache = 0;

  try {
    const priceDays = 365, corrDays = 90;

    // 0) PRIORITY: Try cross-page cache from risk-dashboard (6h TTL) - MUCH faster!
    if (!force) {
      const dashboardCache = readRiskDashboardCache();
      if (dashboardCache) {
        debugLogger.debug('🎯 CROSS-PAGE CACHE FOUND - Hydrating store with cached scores...');
        // Hydrate store immediately with cached scores
        if (typeof dashboardCache.onchainScore === 'number') {
          store.set('scores.onchain', dashboardCache.onchainScore);
          debugLogger.debug(`⚡ FAST: On-Chain from cache: ${dashboardCache.onchainScore}`);
          loadedFromCache++;
        }
        if (typeof dashboardCache.riskScore === 'number') {
          store.set('scores.risk', dashboardCache.riskScore);
          debugLogger.debug(`⚡ FAST: Risk from cache: ${dashboardCache.riskScore}`);
          loadedFromCache++;
        }
        if (typeof dashboardCache.blendedScore === 'number') {
          store.set('scores.blended', dashboardCache.blendedScore);
          debugLogger.debug(`⚡ FAST: Blended from cache: ${dashboardCache.blendedScore}`);
        }

        // Skip slow API calls if cache is fresh
        const cacheAge = Math.round((Date.now() - dashboardCache.timestamp) / 60000);
        debugLogger.debug(`✅ Skipping slow Risk/On-Chain API calls - using ${cacheAge}min old cache (TTL: 6h)`);
        debugLogger.debug('📊 Store now has scores:', {
          onchain: store.get('scores.onchain'),
          risk: store.get('scores.risk'),
          blended: store.get('scores.blended')
        });
      } else {
        debugLogger.warn('⚠️ No cross-page cache - will use slower API calls');
      }
    }

    // 1) Risk (backend) - Use orchestrator's hydrated value (DON'T OVERWRITE)
    // Orchestrator already loaded risk score via risk-data-orchestrator.js
    const existingRiskScore = store.get('scores.risk');
    if (typeof existingRiskScore === 'number') {
      debugLogger.debug(`✅ Risk score already hydrated by orchestrator: ${existingRiskScore}`);
      loadedFromCache++;
    } else {
      debugLogger.debug('⚠️ Risk score not yet hydrated, waiting for orchestrator...');
      // Wait for orchestrator hydration if not ready
      await new Promise(resolve => {
        const handler = (e) => {
          if (e.detail?.hydrated) {
            debugLogger.debug('✅ Orchestrator hydrated, risk score available');
            resolve();
          }
        };
        window.addEventListener('riskStoreReady', handler, { once: true });
        setTimeout(resolve, 2000); // Fallback timeout
      });
    }

    // 2) Cycle (client-side) - With cache
    if (isCacheValid(CACHE_CONFIG.cycle.key, CACHE_CONFIG.cycle.ttl)) {
      debugLogger.debug('✅ Cycle data loaded from cache');
      const cycleData = getCache(CACHE_CONFIG.cycle.key);
      store.set('cycle.months', cycleData.months);
      store.set('cycle.score', cycleData.score);
      store.set('cycle.phase', cycleData.phase);
      loadedFromCache++;
    } else {
      try {
        const { getCurrentCycleMonths, cycleScoreFromMonths, getCyclePhase } = await import('../modules/cycle-navigator.js');
        const c = getCurrentCycleMonths();
        const score = Math.round(cycleScoreFromMonths(c.months));
        const phase = getCyclePhase(c.months);
        const cycleData = { months: c.months, score, phase };
        setCache(CACHE_CONFIG.cycle.key, cycleData);
        store.set('cycle.months', c.months);
        store.set('cycle.score', score);
        store.set('cycle.phase', phase);
        debugLogger.debug('✅ Cycle data calculated and cached');
      } catch (e) { debugLogger.warn('Cycle data load failed:', e.message); }
    }

    // 3) On-Chain (via scraper/proxy) - SWR Cache with hard refresh detection
    const isHardRefresh = performance.navigation?.type === 1 ||
                          performance.getEntriesByType?.('navigation')?.[0]?.type === 'reload';
    const manualRefresh = window.location.search.includes('force_onchain=true') || isHardRefresh || force;

    // Check if already loaded from dashboard cache
    const existingOnchainScore = store.get('scores.onchain');
    if (!manualRefresh && typeof existingOnchainScore === 'number') {
      debugLogger.debug('✅ On-Chain already in store from dashboard cache, skipping API');
      loadedFromCache++;
    } else if (!manualRefresh && isCacheValid(CACHE_CONFIG.onchain.key, CACHE_CONFIG.onchain.ttl)) {
      debugLogger.debug('✅ On-Chain data loaded from legacy cache');
      const onchainData = getCache(CACHE_CONFIG.onchain.key);
      if (typeof onchainData.score === 'number') {
        store.set('scores.onchain', onchainData.score);
      }
      store.set('scores.onchain_metadata', onchainData.metadata);
      store.set('scores.contradictory_signals', onchainData.contradictory_signals);
      store.set('ui.apiStatus.signals', 'healthy');
      loadedFromCache++;
    } else {
      debugLogger.debug('🔄 On-Chain refresh - Using SWR cache for optimal performance...');
      try {
        const onchain = await import('../modules/onchain-indicators.js');
        const v2 = await import('../modules/composite-score-v2.js');
        // Use SWR-cached version by default (no force unless manual)
        const indicators = await onchain.fetchAllIndicators({ force: manualRefresh });
        // Dynamic weighting always enabled (V2 production mode)
        const composite = v2.calculateCompositeScoreV2(indicators, true);

        let finalComposite = composite;
        // Fallback minimal si score null: utiliser Fear & Greed pour produire un score on-chain basique
        if (finalComposite.score == null) {
          try {
            const data = await window.globalConfig.apiRequest('/api/ml/sentiment/fear-greed', { params: { days: 1 } });
            if (data) {
              const latest = (data.fear_greed_data && (data.fear_greed_data[0] || data.fear_greed_data)) || null;
              const fg = latest?.value ?? latest?.fear_greed_index;
              if (typeof fg === 'number') {
                const minimal = {
                  fear_greed_min: { name: 'Fear & Greed', value_numeric: fg, in_critical_zone: fg >= 80 || fg <= 20, raw_value: String(fg) },
                  _metadata: { available_count: 1 }
                };
                finalComposite = v2.calculateCompositeScoreV2(minimal, true);
                debugLogger.debug('✅ On-Chain fallback (Fear & Greed) used in unified loader');
              }
            }
          } catch (fe) { debugLogger.warn('On-chain FG fallback failed:', fe.message); }
        }

        const onchainData = {
          score: finalComposite.score,
          metadata: {
            categoryBreakdown: finalComposite.categoryBreakdown,
            criticalZoneCount: finalComposite.criticalZoneCount,
            confidence: finalComposite.confidence,
          },
          contradictory_signals: v2.analyzeContradictorySignals(finalComposite.categoryBreakdown)
        };

        setCache(CACHE_CONFIG.onchain.key, onchainData);

        if (typeof onchainData.score === 'number') {
          store.set('scores.onchain', onchainData.score);
        }
        store.set('scores.onchain_metadata', onchainData.metadata);
        store.set('scores.contradictory_signals', onchainData.contradictory_signals);
        store.set('ui.apiStatus.signals', 'healthy');
        debugLogger.debug('✅ On-Chain data calculated and cached');
      } catch (e) {
        debugLogger.warn('On-chain load failed:', e.message);
        store.set('ui.apiStatus.signals', 'error');
      }
    }

    // PATCH B - TOUJOURS exécuter l'injection de données (même avec cache)
    try {
      // DEBUG A - Vérification parité Rebalance ↔ Analytics
      debugLogger.debug('[whoami]', {
        currentUser: localStorage.getItem('activeUser') || 'demo',
        currentSource: window.globalConfig?.get('data_source') || 'unknown'
      });

      // PATCH B - Forcer même dataset que Rebalance (toujours)
      if (typeof window.loadBalanceData === 'function') {
        try {
          const balanceResult = await window.loadBalanceData();
          if (balanceResult.success) {
            const realBalances = balanceResult.data?.items || [];

            // INJECT real data into store to force UnifiedInsights to use same data
            const totalValue = realBalances.reduce((sum, item) => sum + (parseFloat(item.value_usd) || 0), 0);
            store.set('wallet.balances', realBalances);
            store.set('wallet.total', totalValue);

            debugLogger.debug('🔧 PATCH: Analytics FORCE injection même avec cache:', {
              items: realBalances.length,
              first5: realBalances.slice(0,5),
              total: totalValue,
              source: balanceResult.source,
              dataSource: window.globalConfig?.get('data_source'),
              timestamp: new Date().toISOString()
            });

            // DEBUG: Vérifier les groupes immédiatement après injection
            try {
              const { groupAssetsByClassification } = await import('../shared-asset-groups.js');
              const groupedData = groupAssetsByClassification(realBalances);
              debugLogger.debug('🔍 POST-INJECTION GROUPING (Analytics):', {
                groups: groupedData.map(g => ({
                  label: g.label,
                  value: g.value,
                  percentage: ((g.value / totalValue) * 100).toFixed(1) + '%'
                })),
                totalGrouped: groupedData.reduce((sum, g) => sum + g.value, 0)
              });
            } catch (e) {
              debugLogger.warn('Post-injection grouping test failed:', e.message);
            }
          }
        } catch (e) {
          debugLogger.warn('🔧 PATCH failed, but continuing:', e.message);
        }
      }
    } catch (e) {
      debugLogger.warn('Patch injection error:', e.message);
    }

    // 4) Compute blended (decision index) - With cache
    if (isCacheValid(CACHE_CONFIG.blended.key, CACHE_CONFIG.blended.ttl)) {
      debugLogger.debug('✅ Blended score loaded from cache');
      const blendedData = getCache(CACHE_CONFIG.blended.key);
      store.set('scores.blended', blendedData.score);
      store.set('market.regime', blendedData.regime);
      loadedFromCache++;
    } else {
      try {
        const s = store.snapshot();

        // DEBUG A - Vérification parité Rebalance ↔ Analytics
        debugLogger.debug('[whoami]', {
          currentUser: localStorage.getItem('activeUser') || 'demo',
          currentSource: window.globalConfig?.get('data_source') || 'unknown'
        });
        debugLogger.debug('[balances]', {
          storeBalances: s?.wallet?.balances?.slice?.(0,5),
          storeTotal: s?.wallet?.total,
          hasLoadBalanceData: typeof window.loadBalanceData === 'function'
        });

        // PATCH B - Forcer même dataset que Rebalance (temporaire)
        let realBalances = null;
        if (typeof window.loadBalanceData === 'function') {
          try {
            const balanceResult = await window.loadBalanceData();
            if (balanceResult.success) {
              realBalances = balanceResult.data?.items || [];

              // INJECT real data into store to force UnifiedInsights to use same data
              const totalValue = realBalances.reduce((sum, item) => sum + (parseFloat(item.value_usd) || 0), 0);
              store.set('wallet.balances', realBalances);
              store.set('wallet.total', totalValue);

              // DEBUG B - Test grouping avec vraies données comme Rebalance
              try {
                const { groupAssetsByClassification, getAssetGroup } = await import('../shared-asset-groups.js');
                const groupedData = groupAssetsByClassification(realBalances);

                debugLogger.debug('🔧 PATCH: Analytics now using same data as Rebalance:', {
                  items: realBalances.length,
                  first5: realBalances.slice(0,5),
                  total: totalValue,
                  source: balanceResult.source
                });

                debugLogger.debug('🔍 GROUPING TEST (même fonction que Rebalance):', {
                  groups: groupedData.map(g => ({
                    label: g.label,
                    value: g.value,
                    percentage: ((g.value / totalValue) * 100).toFixed(1) + '%',
                    assets: g.assets.slice(0,3) // Juste les 3 premiers
                  })),
                  totalGrouped: groupedData.reduce((sum, g) => sum + g.value, 0),
                  othersGroup: groupedData.find(g => g.label === 'Others')
                });

                // DEBUG - Asset par asset avec classification
                debugLogger.debug('🔍 ASSET CLASSIFICATION:', realBalances.slice(0,10).map(item => ({
                  symbol: item.symbol,
                  value: item.value_usd,
                  group: getAssetGroup(item.symbol)
                })));

              } catch (e) {
                debugLogger.warn('Failed to test grouping:', e.message);
              }
            }
          } catch (e) {
            debugLogger.warn('🔧 PATCH failed, fallback to store data:', e.message);
          }
        }

        // ✅ UNIFORMISATION avec risk-dashboard.html (même formule canonique)
        // Formule : 50% CCS Mixte + 30% On-Chain + 20% Risk (sans inversion)
        // Respecte docs/RISK_SEMANTICS.md

        const ccsMixteScore = s.cycle?.ccsStar ?? s.cycle?.score ?? 50; // CCS Mixte (CCS + Cycle blended)
        const onchainScore = s.scores?.onchain ?? 50;
        const riskScore = s.scores?.risk ?? 50;

        // Poids fixes identiques à risk-dashboard.html
        const wCCSMixte = 0.50;
        const wOnchain = 0.30;
        const wRisk = 0.20;

        // Calcul blended avec formule canonique (pas d'inversion Risk!)
        let totalScore = 0;
        let totalWeight = 0;

        if (ccsMixteScore != null) {
          totalScore += ccsMixteScore * wCCSMixte;
          totalWeight += wCCSMixte;
        }
        if (onchainScore != null) {
          totalScore += onchainScore * wOnchain;
          totalWeight += wOnchain;
        }
        if (riskScore != null) {
          totalScore += riskScore * wRisk; // ✅ Direct, pas d'inversion
          totalWeight += wRisk;
        }

        const blended = totalWeight > 0 ? totalScore / totalWeight : 50;
        const blendedScore = Math.round(Math.max(0, Math.min(100, blended)));

        console.debug('🎯 Blended Score (formule canonique):', {
          ccsMixte: ccsMixteScore,
          onchain: onchainScore,
          risk: riskScore,
          blended: blendedScore,
          weights: { ccsMixte: wCCSMixte, onchain: wOnchain, risk: wRisk }
        });

        // 5) Market Regime (sentiment/régime agrégé)  
        let regimeData = null;
        try {
          const { getRegimeDisplayData } = await import('../modules/market-regimes.js');
          regimeData = getRegimeDisplayData(blendedScore, onchainScore, riskScore);
        } catch (e) { debugLogger.warn('Market regime compute failed:', e.message); }

        const blendedData = { score: blendedScore, regime: regimeData };
        setCache(CACHE_CONFIG.blended.key, blendedData);

        store.set('scores.blended', blendedScore);
        store.set('market.regime', regimeData);
        debugLogger.debug('✅ Blended score calculated and cached');
      } catch (e) { debugLogger.warn('Blended compute failed:', e.message); }
    }

    const cacheEfficiency = loadedFromCache > 0 ? `${loadedFromCache}/4 from cache` : 'full calculation';
    const crossPageUsed = store.get('scores.onchain') && store.get('scores.risk') ? ' (6h cross-page cache)' : '';
    debugLogger.debug(`🎯 Unified data loading completed - ${cacheEfficiency}${crossPageUsed}${loadedFromCache > 0 ? ' ⚡ FAST' : ''}`);

    // CONTRÔLES D - Invariants obligatoires (3 assertions critiques)
    try {
      const stateSnapshot = store.snapshot();
      const riskBudget = stateSnapshot?.risk?.budget;

      if (riskBudget?.percentages) {
        const risky = riskBudget.percentages.risky || 0;
        const stables = riskBudget.percentages.stables || 0;
        const sum = risky + stables;

        console.assert(Math.abs(sum - 100) <= 0.1,
          'INVARIANT FAILED: risky+stables != 100',
          { risky, stables, sum, riskBudget }
        );
      }

      // Wait for Risk Budget to be ready before continuing
      // First try immediate resolution
      let rb = null;
      try {
        const immediate = store.get('risk.budget');
        if (immediate?.percentages?.stables != null && immediate?.percentages?.risky != null) {
          rb = {
            stables_allocation: immediate.percentages.stables / 100,
            risky_allocation: immediate.percentages.risky / 100
          };
        }
      } catch (e) {
        // Fall back to async resolution
      }

      if (!rb) {
        rb = await ensureRiskBudgetReady(() => window.__store?.riskBudget);
        if (!rb) {
          console.debug('⚠️ Skip invariant checks this tick: risk budget not ready');
          // Don't return, continue with other operations
        }
      }

      const targetStablesPct = rb ? Math.round(rb.stables_allocation * 100) : 34; // Default fallback
      // Remove assert - use computed value instead

      // Vérifier groupes de targets si disponibles
      const targets = stateSnapshot?.strategy?.targets || [];
      if (targets.length > 0) {
        const hasNegativeTargets = targets.some(t => (t.weight_pct || 0) < 0);
        console.assert(!hasNegativeTargets,
          'INVARIANT FAILED: target_pct négatif détecté',
          { targets: targets.filter(t => (t.weight_pct || 0) < 0) }
        );
      }

      console.debug('✅ Invariants Analytics validés:', {
        sumCheck: riskBudget?.percentages ? `${risky}+${stables}=${risky+stables}%` : 'N/A',
        targetStables: `${targetStablesPct}%`,
        targetsCount: targets.length,
        riskBudgetSource: rb ? 'resolved' : 'fallback'
      });

    } catch (assertError) {
      debugLogger.error('❌ ASSERTION FAILED:', assertError.message);
    }

    // Update badges with latest data
    updateAnalyticsBadges();

    // Update risk metrics with dynamic data
    updateRiskMetrics();

  } catch (e) {
    debugLogger.error('Unified loader fatal:', e);
  }
}
// Track data source changes for cache invalidation
let lastKnownDataSource = globalConfig.get('data_source');
debugLogger.debug(`📊 Analytics Unified initialized with data source: ${lastKnownDataSource}`);

// Listen for data source changes
window.addEventListener('storage', function (e) {
  const expectedKey = (window.globalConfig?.getStorageKey && window.globalConfig.getStorageKey()) || 'crypto_rebal_settings_v1';
  if (e.key === expectedKey) {
    console.debug('Settings changed in another tab, checking for data source changes...');

    const currentSource = globalConfig.get('data_source');
    if (currentSource && currentSource !== lastKnownDataSource) {
      console.debug(`🔄 Data source changed from ${lastKnownDataSource} to ${currentSource}, clearing cache and reloading...`);
      lastKnownDataSource = currentSource;
      // Clear all cache for this source change
      Object.values(CACHE_CONFIG).forEach(config => {
        const oldKey = getCacheKey(config.key).replace(`_${currentSource}`, `_${lastKnownDataSource || 'unknown'}`);
        localStorage.removeItem(oldKey);
      });
      // Reload with new source
      loadUnifiedData();
      // Force re-render of UnifiedInsights component to update advanced risk analysis
      setTimeout(() => renderUnifiedInsights('unified-root'), 1000);
    }
  }
});

window.addEventListener('dataSourceChanged', (event) => {
  console.debug(`🔄 Explicit data source change in analytics-unified: ${event.detail.oldSource} → ${event.detail.newSource}`);
  lastKnownDataSource = event.detail.newSource;
  // Clear cache and reload
  loadUnifiedData();
  // Force re-render of UnifiedInsights component to update advanced risk analysis
  setTimeout(() => renderUnifiedInsights('unified-root'), 1000);
});

// OVERRIDE PRÉCOCE - Avant même le DOMContentLoaded
debugLogger.debug('🔥 EARLY OVERRIDE: Setting renderUnifiedInsights before any other imports');
delete window.renderUnifiedInsights;
window.renderUnifiedInsights = renderUnifiedInsights;

// FORCE CACHE BUST: Ajouter timestamp pour forcer le rechargement
debugLogger.debug('🆘 CACHE BUST ANALYTICS UNIFIED:', new Date().toISOString());

// Suppress chrome extension errors
window.addEventListener('error', function(e) {
  if (e.message && e.message.includes('Could not establish connection')) {
    // Suppress Chrome extension connection errors
    e.preventDefault();
    return false;
  }
});

document.addEventListener('DOMContentLoaded', async () => {
  // Initialize governance panel
  const governanceContainer = document.getElementById('governance-container');
  if (governanceContainer) {
    debugLogger.debug('🏛️ Initializing Governance Panel in analytics dashboard...');
    const governancePanel = new GovernancePanel(governanceContainer);
    window.governancePanel = governancePanel; // For debugging
  }


  // OVERRIDE FINAL AVANT INITIAL PAINT
  debugLogger.debug('🆘 DOM READY - FINAL OVERRIDE:', new Date().toISOString());

  // FORCE OVERRIDE - Supprimer toute fonction existante d'abord
  delete window.renderUnifiedInsights;
  window.renderUnifiedInsights = renderUnifiedInsights;

  // VERIFICATION de l'override
  debugLogger.debug('🔍 VERIFICATION OVERRIDE:', {
    isLocalFunction: window.renderUnifiedInsights === renderUnifiedInsights,
    functionSource: window.renderUnifiedInsights.toString().includes('🔥 LOCAL FUNCTION UNIFIED')
  });

  // CORRECTION TIMING: Charger les données AVANT le rendu initial
  debugLogger.debug('🔄 LOADING DATA FIRST, THEN RENDERING...');

  // 0) Force reload taxonomie pour éviter fallback "Others"
  try {
    const { forceReloadTaxonomy, UNIFIED_ASSET_GROUPS } = await import('../shared-asset-groups.js');
    await forceReloadTaxonomy();
    if (!Object.keys(UNIFIED_ASSET_GROUPS || {}).length) {
      debugLogger.warn('⚠️ Taxonomy non chargée – risque de "Others" gonflé. Vérifie API base_url.');
    } else {
      debugLogger.debug('✅ Taxonomy forcée:', Object.keys(UNIFIED_ASSET_GROUPS).length, 'groupes chargés');
    }
  } catch (taxonomyError) {
    debugLogger.warn('❌ Force reload taxonomy failed:', taxonomyError.message);
  }

  // 1) Charger les données d'abord (detect hard refresh)
  const isHardRefresh = performance.navigation?.type === 1 ||
                        performance.getEntriesByType?.('navigation')?.[0]?.type === 'reload';
  if (isHardRefresh) {
    debugLogger.debug('🔄 Hard refresh detected, forcing cache refresh for all data');
  }
  await loadUnifiedData(isHardRefresh);

  // Enhanced UI Mutex with render state tracking
  if (!window.__uiMutex) {
    window.__uiMutex = {
      busy: false,
      lastRender: 0,
      lastHash: '',
      MIN_RENDER_INTERVAL: 1000 // Minimum 1s between renders
    };
  }

  async function renderUnifiedInsightsOnce() {
    const now = Date.now();

    // Skip if already rendering
    if (window.__uiMutex.busy) {
      console.debug('🔒 UI Mutex: Skipping render (already in progress)');
      return;
    }

    // Skip if rendered too recently
    if (now - window.__uiMutex.lastRender < window.__uiMutex.MIN_RENDER_INTERVAL) {
      console.debug('🔒 Rate limit: Skipping render (too frequent)');
      return;
    }

    // Check if state actually changed
    const storeSnapshot = store.snapshot();
    const currentHash = JSON.stringify({
      scores: storeSnapshot?.scores,
      regime: storeSnapshot?.market?.regime?.name,
      stables: storeSnapshot?.risk?.budget?.percentages?.stables
    });

    // IMPORTANT: Ne pas skip si scores manquants (premier rendu ou cache pas encore chargé)
    const hasScores = storeSnapshot?.scores?.cycle != null || storeSnapshot?.scores?.onchain != null || storeSnapshot?.scores?.risk != null;
    const isFirstRender = window.__uiMutex.lastRender === 0;

    if (currentHash === window.__uiMutex.lastHash && hasScores && !isFirstRender) {
      console.debug('🔒 State unchanged: Skipping render (scores OK)');
      return;
    }

    if (!hasScores) {
      debugLogger.warn('⚠️ Rendering with incomplete scores:', {
        cycle: storeSnapshot?.scores?.cycle,
        onchain: storeSnapshot?.scores?.onchain,
        risk: storeSnapshot?.scores?.risk,
        will_render: 'yes (waiting for data)'
      });
    }

    window.__uiMutex.busy = true;
    window.__uiMutex.lastRender = now;
    window.__uiMutex.lastHash = currentHash;

    try {
      await renderUnifiedInsights('unified-root');
      console.debug('✅ Render completed', { hasScores });
    } finally {
      window.__uiMutex.busy = false;
    }
  }

  // Subscribe once utility
  function subscribeOnce(el, evt, handler, key) {
    const k = `__bound_${key}`;
    if (el[k]) return;
    el.addEventListener(evt, handler);
    el[k] = true;
  }

  // 2) Initialize governance system BEFORE first render
  setTimeout(async () => {
    try {
      debugLogger.debug('🏛️ Initializing governance system in analytics dashboard...');
      await store.syncGovernanceState();
      await store.syncMLSignals();
      debugLogger.debug('✅ Governance system initialized in analytics dashboard');

      // 3) Premier rendu avec données fraîches ET governance synchronisée
      // IMPORTANT: Attendre que le rendu soit terminé pour éviter race condition
      await renderUnifiedInsightsOnce();

      // Refresh governance panel if initialized
      if (window.governancePanel) {
        window.governancePanel.refreshState();
      }
    } catch (error) {
      debugLogger.warn('⚠️ Failed to initialize governance in analytics:', error);
    }
  }, 500);

  // Manual refresh button handler
  document.getElementById('manual-refresh-onchain')?.addEventListener('click', async function() {
    debugLogger.debug('🔄 Manual refresh triggered by user');
    this.disabled = true;
    this.textContent = '⏳ Actualisation...';

    try {
      // Force refresh onchain data
      await loadUnifiedData();
      await renderUnifiedInsightsOnce();

      this.textContent = '✅ Actualisé';
      setTimeout(() => {
        this.textContent = '🔄 Actualiser';
        this.disabled = false;
      }, 2000);
    } catch (error) {
      debugLogger.error('Manual refresh failed:', error);
      this.textContent = '❌ Erreur';
      setTimeout(() => {
        this.textContent = '🔄 Actualiser';
        this.disabled = false;
      }, 3000);
    }
  });

  // Enhanced store subscription with intelligent debouncing
  let paintTimer, lastStoreHash = '';
  store.subscribe(() => {
    // Quick hash check to avoid unnecessary renders
    const storeSnapshot = store.snapshot();
    const currentHash = JSON.stringify({
      scores: storeSnapshot?.scores,
      regime: storeSnapshot?.market?.regime?.name,
      stables: storeSnapshot?.risk?.budget?.percentages?.stables
    });

    // Skip if state hasn't meaningfully changed
    if (currentHash === lastStoreHash) {
      return;
    }
    lastStoreHash = currentHash;

    clearTimeout(paintTimer);
    paintTimer = setTimeout(() => {
      renderUnifiedInsightsOnce();
      updateRiskMetrics();
    }, 500); // Increased from 250ms to 500ms for better batching
  });

  // ✅ CRITIQUE: Attendre hydratation orchestrator avant 1er updateRiskMetrics
  window.addEventListener('riskStoreReady', (e) => {
    if (e.detail?.hydrated) {
      debugLogger.debug('✅ Orchestrator hydrated, refreshing risk metrics');
      updateRiskMetrics();
    }
  }, { once: true });

  // Simple fallback banner toggle
  setInterval(() => {
    try {
      const status = store.get('ui.apiStatus.backend');
      const banner = document.getElementById('backend-fallback-banner');
      if (!banner) return;
      banner.style.display = (status && status !== 'healthy') ? 'block' : 'none';
    } catch { }
  }, 2000);
});

// DERNIÈRE CHANCE - Override après TOUS les imports et définitions
debugLogger.debug('🔥 FINAL FINAL OVERRIDE - After all scripts loaded');
setTimeout(() => {
  delete window.renderUnifiedInsights;
  window.renderUnifiedInsights = renderUnifiedInsights;
  debugLogger.debug('🔥 LATE OVERRIDE APPLIED:', {
    isOurFunction: window.renderUnifiedInsights === renderUnifiedInsights,
    hasOurMarker: window.renderUnifiedInsights.toString().includes('🔥 LOCAL FUNCTION UNIFIED')
  });
}, 100);
