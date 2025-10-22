// ⚙️ Unifier l’URL d’import du module (pas de ?v=3 ici)
    import { cycleScoreFromMonths, getCurrentCycleMonths } from './cycle-navigator.js';
    // Note: calibrateCycleParams & getCycleParams seront importés à la volée, ce qui
    // évite tout problème si le bouton est injecté après coup.

    // 🔗 CSP Compliance: Replace inline onclick handlers with event listeners
    document.addEventListener('click', async (e) => {
      // Calibration button (existing)
      const calibrateBtn = e.target?.closest('#btn-calibrate');
      if (calibrateBtn) {
        try {
          const { calibrateCycleParams, getCycleParams } = await import('./cycle-navigator.js');
          const res = calibrateCycleParams(); // ancres par défaut
          console.debug('Cycle params calibrés:', getCycleParams(), 'score=', res.score);
          // ✅ Redessiner le même canvas (force refresh after calibration)
          if (window.Chart) {
            await createBitcoinCycleChart('bitcoin-cycle-chart', true);
          } else {
            debugLogger.debug('📊 Chart.js not loaded, skipping chart refresh');
          }
          // Also clear cycle content cache as calibration affects data
          const cycleContentConfig = CACHE_CONFIG.CYCLE_CONTENT;
          if (cycleContentConfig) localStorage.removeItem(cycleContentConfig.key);
          window.showToast?.('Cycle calibré sur historiques', 'success');
        } catch (e) {
          debugLogger.error(e);
          window.showToast?.('Échec calibration', 'error');
        }
        return;
      }

      // Refresh button
      if (e.target?.closest('#refresh-btn')) {
        refreshDashboard();
        return;
      }

      // Options menu toggle
      if (e.target?.closest('#options-menu-btn')) {
        toggleOptionsMenu(e);
        return;
      }

      // Menu items
      if (e.target?.closest('#force-refresh-btn')) {
        closeOptionsMenu();
        refreshDashboard(true);
        return;
      }

      if (e.target?.closest('#force-cycle-refresh-btn')) {
        closeOptionsMenu();
        forceCycleRefresh();
        return;
      }

      if (e.target?.closest('#test-endpoint-btn')) {
        closeOptionsMenu();
        testEndpoint();
        return;
      }

      // View alerts history button
      if (e.target?.closest('[data-action="view-alerts-history"]')) {
        switchTab('alerts');
        return;
      }

      // Tab switching (CSP-compliant replacement for onclick)
      const tabButton = e.target?.closest('.tab-button[data-tab]');
      if (tabButton) {
        const tabName = tabButton.getAttribute('data-tab');
        if (tabName && typeof switchTab === 'function') {
          switchTab(tabName);
        }
        return;
      }

      // Alerts filters and refresh
      if (e.target?.closest('[data-action="filter-alerts"]')) {
        if (typeof filterAlertsHistory === 'function') {
          filterAlertsHistory();
        }
        return;
      }

      if (e.target?.closest('[data-action="refresh-alerts"]')) {
        if (typeof refreshAlertsHistory === 'function') {
          refreshAlertsHistory();
        }
        return;
      }

      // Alerts pagination
      if (e.target?.closest('[data-action="alerts-prev"]')) {
        if (typeof loadPreviousAlertsPage === 'function') {
          loadPreviousAlertsPage();
        }
        return;
      }

      if (e.target?.closest('[data-action="alerts-next"]')) {
        if (typeof loadNextAlertsPage === 'function') {
          loadNextAlertsPage();
        }
        return;
      }

      // Clear all toasts
      if (e.target?.closest('[data-action="clear-all-toasts"]')) {
        if (typeof hideAllToasts === 'function') {
          hideAllToasts();
        }
        return;
      }

      // Alert modal actions
      if (e.target?.closest('[data-action="close-alert-modal"]')) {
        if (typeof closeAlertModal === 'function') {
          closeAlertModal();
        }
        return;
      }

      if (e.target?.closest('[data-action="snooze-alert"]')) {
        if (typeof snoozeCurrentAlert === 'function') {
          snoozeCurrentAlert();
        }
        return;
      }

      if (e.target?.closest('[data-action="acknowledge-alert"]')) {
        if (typeof acknowledgeCurrentAlert === 'function') {
          acknowledgeCurrentAlert();
        }
        return;
      }

      if (e.target?.closest('[data-action="apply-action"]')) {
        if (typeof applyAction === 'function') {
          applyAction();
        }
        return;
      }
    });

    // 🆕 Oct 2025: Toggle breakdown panel (expose globally for onclick handlers)
    window.toggleBreakdown = function(panelId) {
      const panel = document.getElementById(panelId);
      if (panel) {
        const isVisible = panel.style.display !== 'none';
        panel.style.display = isVisible ? 'none' : 'block';
      }
    };

    // Import core modules
    import { store } from '../core/risk-dashboard-store.js';
    import { fetchCached, clearCache } from '../core/fetcher.js';

    // Import CCS modules
    import { fetchAndComputeCCS, interpretCCS, DEFAULT_CCS_WEIGHTS } from './signals-engine.js';
    import { estimateCyclePosition, blendCCS, getCyclePhase } from './cycle-navigator.js';
    import { proposeTargets, applyTargets, computePlan, DEFAULT_MACRO_TARGETS, getDecisionLog } from './targets-coordinator.js';
    import { fetchAllIndicators, enhanceCycleScore } from './onchain-indicators.js';
    import { calculateCompositeScoreV2, analyzeContradictorySignals } from './composite-score-v2.js';
    import { getMarketRegime, applyMarketOverrides, calculateRiskBudget, getRegimeDisplayData } from './market-regimes.js';

    // Import tab-specific modules
    // Note: Alerts and Risk Overview tabs use dynamic imports in risk-dashboard-main.js
    import { renderCyclesContent, renderCyclesContentUncached, createBitcoinCycleChart, loadOnChainIndicators, fetchBitcoinHistoricalData } from './risk-cycles-tab.js';
    import { renderTargetsContent, getCurrentPortfolioAllocation } from './risk-targets-tab.js';

    // Import utilities and constants (Oct 2025 refactoring - ultra-conservative)
    import { safeFixed, formatPercent, formatNumber, formatMoney, scoreToRiskLevel, pickScoreColor, getScoreInterpretation } from './risk-utils.js';
    import { CACHE_CONFIG } from './risk-constants.js';

    // Global state
    let autoRefreshInterval = null;
    let isRefreshing = false;

    // Variables pour les scores
    let onchainScore = null;
    let riskScore = null;
    let blendedScore = null;

    // ===== PERSISTENT CACHE SYSTEM =====
    // Note: CACHE_CONFIG now imported from risk-constants.js

    function clearAllPersistentCache() {
      // Clear both old format and new data-source-aware format cache entries
      const dataSource = globalConfig.get('data_source') || 'unknown';

      Object.values(CACHE_CONFIG).forEach(config => {
        // Clear old format
        localStorage.removeItem(config.key);
        // Clear new data-source-aware format
        localStorage.removeItem(`${config.key}_${dataSource}`);

        // Also clear other potential data sources to ensure complete cleanup
        ['cointracking', 'api', 'unknown'].forEach(source => {
          localStorage.removeItem(`${config.key}_${source}`);
        });
      });
      debugLogger.debug(`🧹 All persistent cache cleared for source ${dataSource}`);
    }

    // Re-render on currency change (ensure rate then refresh)
    window.addEventListener('configChanged', (ev) => {
      const key = ev?.detail?.key;
      if (key === 'display_currency') {
        const cur = (window.globalConfig && window.globalConfig.get('display_currency')) || 'USD';
        const rerender = () => { try { refreshDashboard(true); } catch (_) { } };
        if (window.currencyManager && cur !== 'USD') {
          window.currencyManager.ensureRate(cur).then(rerender).catch(rerender);
        } else {
          rerender();
        }
      }
    });

    // Fonction pour charger les paramètres de calibration depuis localStorage
    function loadCalibrationParams() {
      try {
        const saved = localStorage.getItem('bitcoin_cycle_params');
        if (saved) {
          const data = JSON.parse(saved);
          // Vérifier que les données ne sont pas trop anciennes (24h)
          if (Date.now() - data.timestamp < 24 * 60 * 60 * 1000) {
            console.debug('✅ Paramètres calibrés chargés depuis localStorage', data.params);
            return data.params;
          }
        }
      } catch (error) {
        debugLogger.error('❌ Erreur chargement paramètres:', error);
      }
      return null;
    }

    // Écouter les mises à jour de paramètres depuis d'autres pages
    window.addEventListener('message', (event) => {
      if (event.data.type === 'CYCLE_PARAMS_UPDATED') {
        console.debug('🔄 Paramètres de cycle mis à jour depuis autre page');
        // Recharger les données avec les nouveaux paramètres
        setTimeout(refreshDashboard, 1000);
      }
    });

    // Track current data source to detect changes
    let lastKnownDataSource = globalConfig.get('data_source');
    console.debug(`📊 Risk Dashboard initialized with data source: ${lastKnownDataSource}`);

    // Listen for data source changes from settings
    window.addEventListener('storage', function (e) {
      const expectedKey = (window.globalConfig?.getStorageKey && window.globalConfig.getStorageKey()) || 'crypto_rebal_settings_v1';
      if (e.key === expectedKey) {
        console.debug('Settings changed in another tab, checking for data source changes...');

        const currentSource = globalConfig.get('data_source');
        if (currentSource && currentSource !== lastKnownDataSource) {
          console.debug(`🔄 Data source changed from ${lastKnownDataSource} to ${currentSource}, auto-refreshing...`);
          lastKnownDataSource = currentSource;
          // Clear cache when source changes
          clearAllPersistentCache();
          setTimeout(() => refreshDashboard(true), 500); // Force refresh to recalculate with new source
        }
      }
    });

    // Listen for explicit data source change events
    window.addEventListener('dataSourceChanged', (event) => {
      console.debug(`🔄 Explicit data source change: ${event.detail.oldSource} → ${event.detail.newSource}`);
      lastKnownDataSource = event.detail.newSource;
      // Clear cache when source changes
      clearAllPersistentCache();
      setTimeout(() => refreshDashboard(true), 500); // Force refresh to recalculate with new source

      // Reload Phase 3A data with new source/user context
      setTimeout(() => {
        if (document.querySelector('.advanced-risk-panel') && typeof loadPhase3AData === 'function') {
          console.debug('🔄 Reloading Phase 3A data after source change...');
          loadPhase3AData().catch(e => debugLogger.warn('Phase 3A reload failed:', e.message));
        }
      }, 1000);
    });

    // Listen for active user changes to reload Phase 3A data
    window.addEventListener('activeUserChanged', (event) => {
      console.debug(`🔄 Active user changed: ${event.detail?.oldUser || 'unknown'} → ${event.detail?.newUser || 'unknown'}`);
      // Reload Phase 3A data with new user context
      setTimeout(() => {
        if (document.querySelector('.advanced-risk-panel') && typeof loadPhase3AData === 'function') {
          console.debug('🔄 Reloading Phase 3A data after user change...');
          loadPhase3AData().catch(e => debugLogger.warn('Phase 3A reload failed:', e.message));
        }
      }, 500);
    });

    // ====== Tab Management ======
    window.switchTab = function (tabName) {
      // Update UI state
      document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

      document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
      document.getElementById(`${tabName}-tab`).classList.add('active');

      // Update store
      store.set('ui.activeTab', tabName);

      // Render content based on active tab
      switch (tabName) {
        case 'risk':
          // Risk content is already rendered by refreshDashboard
          break;
        case 'cycles':
          // Always render cycles content when tab is activated
          renderCyclesContent();
          break;
        case 'targets':
          renderTargetsContent().catch(err => debugLogger.error('Failed to render targets:', err));
          break;
        case 'alerts':
          initializeAlertsTab();
          break;
      }

      console.debug(`Switched to tab: ${tabName}`);
    };

    // ====== Tooltip helpers ======
    const $tip = document.getElementById('tooltip');
    const $tipTitle = $tip?.querySelector('.tip-title');
    const $tipBody = $tip?.querySelector('.tip-body');

    function showTip(title, body, x, y) {
      if (!$tip) return;
      $tipTitle.textContent = title || '';
      $tipBody.textContent = body || '';
      $tip.style.left = x + 'px';
      $tip.style.top = y + 'px';
      $tip.classList.add('show');
      $tip.setAttribute('aria-hidden', 'false');
    }

    function moveTip(x, y) {
      if (!$tip) return;
      $tip.style.left = x + 'px';
      $tip.style.top = y + 'px';
    }

    function hideTip() {
      if (!$tip) return;
      $tip.classList.remove('show');
      $tip.setAttribute('aria-hidden', 'true');
    }

    function attachTip(el, title, body) {
      if (!el) return;
      el.addEventListener('mouseenter', e => showTip(title, body, e.clientX, e.clientY));
      el.addEventListener('mousemove', e => moveTip(e.clientX, e.clientY));
      el.addEventListener('mouseleave', hideTip);
      el.classList.add('hinted');
    }

    // ====== Formatters ======
    const pct = v => (v == null || isNaN(v) ? 'N/A' : (v * 100).toFixed(2) + '%');
    const num = v => (v == null || isNaN(v) ? 'N/A' : Number(v).toFixed(2));

    // ====== Analysis Window Slider ======
    // Fixed windows
    const analysisDays = 365;
    const corrDays = 90;
    function updateWindowLabel(v) {
      const lbl = document.getElementById('window-label');
      if (lbl) lbl.textContent = `${v} jours`;
    }
    // Removed old controls

    // ====== API Functions ======
    async function fetchRiskData() {
      try {
        // Get the configured data source dynamically
        const dataSource = globalConfig.get('data_source');
        const apiBaseUrl = globalConfig.get('api_base_url');
        const minUsd = globalConfig.get('min_usd_threshold');

        console.debug(`🔍 Risk Overview using data source: ${dataSource}`);

        // Use globalConfig to build the API URL with the configured source
        const url = globalConfig.getApiUrl('/balances/current', { min_usd: minUsd });

        // Utiliser directement les données de balance et calculer le risque côté client
        const balanceResult = await fetchCached(
          `risk-dashboard-balance:${(localStorage.getItem('activeUser') || 'demo')}:${dataSource}:${minUsd}`,
          () => window.globalConfig.apiRequest('/balances/current', { params: { source: dataSource, min_usd: minUsd } }),
          'risk'
        );

        // Use the real backend endpoint for risk dashboard
        // ✅ Inclure source et user_id pour isolation multi-tenant
        // ✅ NOUVEAU (Phase 5.5): Shadow Mode V2 + Dual Window
        const apiResult = await window.globalConfig.apiRequest('/api/risk/dashboard', {
          params: {
            source: dataSource,
            min_usd: minUsd,
            price_history_days: analysisDays,
            lookback_days: corrDays,
            risk_version: 'v2_active',  // 🆕 V2 Active: V2 est autoritaire (Oct 2025)
            use_dual_window: true        // Dual-window metrics actives
          }
        });

        // 🔍 DEBUG: Log la réponse brute COMPLÈTE pour diagnostiquer les erreurs
        console.debug('🔍 Raw API response (full object):', apiResult);
        console.debug('🔍 Has risk_metrics?', !!apiResult?.risk_metrics);
        console.debug('🔍 Response keys:', apiResult ? Object.keys(apiResult) : 'null');

        // Vérifier que apiResult est valide avant de l'utiliser
        if (!apiResult || !apiResult.risk_metrics) {
          debugLogger.error('❌ Invalid API response structure:', {
            hasApiResult: !!apiResult,
            hasRiskMetrics: !!apiResult?.risk_metrics,
            responseType: typeof apiResult,
            responseKeys: apiResult ? Object.keys(apiResult) : null,
            fullResponse: apiResult
          });
          throw new Error(`Invalid API response: ${apiResult ? 'missing risk_metrics' : 'null response'} - Check backend logs`);
        }

        // 🔍 DEBUG: Log la réponse brute avec nouveaux champs V2 (seulement si valide)
        console.debug('🔍 Parsed API response (Shadow Mode V2):', JSON.stringify({
          // Legacy scores
          sharpe_legacy: apiResult.risk_metrics.sharpe_ratio,
          var95: apiResult.risk_metrics.var_95_1d,
          risk_score_legacy: apiResult.risk_metrics.risk_score,
          structural_legacy: apiResult.risk_metrics.risk_score_structural,
          window_used: apiResult.risk_metrics.window_used,
          // V2 Shadow Mode info (🔧 FIX: Chemin correct!)
          risk_version_info: apiResult.risk_metrics.risk_version_info ? {
            active_version: apiResult.risk_metrics.risk_version_info.active_version,
            risk_score_v2: apiResult.risk_metrics.risk_version_info.risk_score_v2,
            sharpe_v2: apiResult.risk_metrics.risk_version_info.sharpe_v2,
            portfolio_structure_score: apiResult.risk_metrics.risk_version_info.portfolio_structure_score,
            integrated_structural_legacy: apiResult.risk_metrics.risk_version_info.integrated_structural_legacy
          } : null
        }));

        // Inclure les balances pour calculer concentration/stablecoins côté UI
        try {
          apiResult.balances = Array.isArray(balanceResult?.items) ? balanceResult.items : [];
        } catch (_) { /* ignore */ }

        const m = apiResult.risk_metrics;
        debugLogger.debug(`🧪 SHADOW V2 - Risk metrics from API: VaR 95%: ${(m.var_95_1d * 100).toFixed(2)}%, Sharpe: ${m.sharpe_ratio.toFixed(2)}, Risk Score: ${m.risk_score} (authoritative), Structural: ${m.risk_score_structural || 'N/A'}, Window: ${m.window_used?.actual_data_points || '?'} pts, risk_version_info: ${m.risk_version_info ? 'PRESENT ✅' : 'MISSING ❌'}`);

        // The backend already provides the correct structure, just return it
        return apiResult;
      } catch (error) {
        debugLogger.error('❌ Risk API call failed:', {
          errorMessage: error.message,
          errorStack: error.stack,
          errorType: error.constructor.name,
          dataSource: globalConfig.get('data_source'),
          apiBaseUrl: globalConfig.get('api_base_url')
        });
        return {
          success: false,
          message: `Backend de risque indisponible: ${error.message}. Vérifiez que le serveur backend est démarré et les APIs externes (CoinGecko) ne sont pas rate-limitées.`,
          error_type: 'connection_error',
          error_details: error.message
        };
      }
    }

    // NOTE: getMockRiskData() supprimée - plus de données simulées

    // CSV parsing functions are now centralized in global-config.js

    // NOTE: calculateRealRiskMetrics() supprimée - métriques calculées par le backend Python

    // ====== Metric Health Evaluation & Interpretation ======
    function getMetricHealth(key, value) {
      const healthRules = {
        'var_95_1d': {
          good: [0, 0.04], // 0% to 4%
          warning: [0.04, 0.08], // 4% to 8%
          danger: [0.08, 1], // > 8%
          interpretation: {
            good: "Perte journalière potentielle contenue",
            warning: "Perte potentielle modérée",
            danger: "Perte potentielle élevée - attention"
          }
        },
        'var_99_1d': {
          good: [0, 0.06],
          warning: [0.06, 0.12],
          danger: [0.12, 1],
          interpretation: {
            good: "Perte extrême limitée",
            warning: "Perte extrême modérée",
            danger: "Perte extrême importante"
          }
        },
        'sharpe_ratio': {
          danger: [0, 0.5],
          warning: [0.5, 1.0],
          good: [1.0, 5.0],
          interpretation: {
            danger: "Rendement/risque insuffisant",
            warning: "Rendement/risque acceptable",
            good: "Excellent rendement ajusté au risque"
          }
        },
        'sortino_ratio': {
          danger: [0, 0.8],
          warning: [0.8, 1.2],
          good: [1.2, 5.0],
          interpretation: {
            danger: "Protection baisse insuffisante",
            warning: "Protection baisse correcte",
            good: "Excellente protection contre les baisses"
          }
        },
        'volatility_annualized': {
          good: [0, 0.4], // 0-40%
          warning: [0.4, 0.8], // 40-80%
          danger: [0.8, 2.0], // >80%
          interpretation: {
            good: "Volatilité faible",
            warning: "Volatilité modérée",
            danger: "Volatilité élevée"
          }
        },
        'max_drawdown': {
          good: [0, 0.3], // 0% to 30%
          warning: [0.3, 0.6], // 30% to 60%
          danger: [0.6, 1.0], // > 60%
          interpretation: {
            good: "Drawdown limité",
            warning: "Drawdown crypto typique",
            danger: "Drawdown extrême - diversifier"
          }
        },
        'diversification_ratio': {
          danger: [0, 0.4],
          warning: [0.4, 0.7],
          good: [0.7, 2.0], // >1 possible si corrélations négatives
          interpretation: {
            danger: "Très peu diversifié",
            warning: "Diversification limitée",
            good: "Bien diversifié (corrélations faibles ou négatives)"
          }
        },
        'effective_assets': {
          danger: [0, 10],
          warning: [10, 20],
          good: [20, 999],
          interpretation: {
            danger: "Très peu d'actifs effectifs",
            warning: "Diversification partielle",
            good: "Bonne diversification"
          }
        },
        'risk_score': {
          danger: [0, 40],     // 0-40: faible robustesse
          warning: [40, 65],   // 40-65: robustesse modérée
          good: [65, 100],     // 65-100: bonne robustesse
          interpretation: {
            danger: "Portfolio fragile - risque élevé",
            warning: "Robustesse modérée - surveiller",
            good: "Portfolio robuste - bien protégé"
          }
        }
      };

      const rule = healthRules[key];
      if (!rule) return { level: 'unknown', color: '#6b7280', interpretation: 'Métrique non évaluée' };

      // Check which range the value falls into
      for (const [level, range] of Object.entries(rule)) {
        if (level === 'interpretation') continue;

        const [min, max] = range;
        if (value >= min && value <= max) {
          const color = level === 'good' ? '#10b981' : level === 'warning' ? '#f59e0b' : '#ef4444';
          return {
            level,
            color,
            interpretation: rule.interpretation[level] || 'Pas d\'interprétation disponible'
          };
        }
      }

      return { level: 'unknown', color: '#6b7280', interpretation: 'Valeur hors limites' };
    }

    function getContextualBenchmark(key, value) {
      const benchmarks = {
        'var_95_1d': {
          crypto_conservative: 0.04,
          crypto_typical: 0.07,
          crypto_aggressive: 0.12,
          traditional: 0.02
        },
        'sharpe_ratio': {
          crypto_excellent: 1.5,
          crypto_good: 1.0,
          crypto_acceptable: 0.5,
          traditional_good: 1.0
        },
        'volatility_annualized': {
          crypto_low: 0.4,
          crypto_typical: 0.6,
          crypto_high: 1.0,
          traditional: 0.2
        },
        'max_drawdown': {
          crypto_good: -0.3,
          crypto_typical: -0.5,
          crypto_extreme: -0.8,
          traditional: -0.2
        }
      };

      return benchmarks[key] || {};
    }

    function generateRecommendations(metrics, correlations, groups, fullData) {
      const recommendations = [];

      // VaR recommendations (VaR renvoyé en valeur positive)
      // ⚠️ MODIFIÉ (Phase 1.1): Suppression % stables hardcodé, branché sur risk_budget API
      if (metrics.var_95_1d > 0.08) {
        const riskBudget = fullData?.risk_budget || fullData?.regime?.risk_budget;
        const targetStables = riskBudget?.target_stables_pct;

        let action = 'Augmentez la part de stablecoins ou Bitcoin pour réduire la volatilité';
        if (typeof targetStables === 'number') {
          action = `Allocation stables recommandée: ${targetStables}% (calculée selon votre profil de risque)`;
        }

        recommendations.push({
          priority: 'high',
          icon: '🛡️',
          title: 'Réduire le risque de perte journalière',
          description: 'Votre VaR de ' + formatPercent(metrics.var_95_1d) + ' est élevé.',
          action: action
        });
      }

      // Sharpe ratio recommendations
      if (metrics.sharpe_ratio < 1.0) {
        recommendations.push({
          priority: 'medium',
          icon: '📈',
          title: 'Améliorer le rendement ajusté au risque',
          description: 'Sharpe ratio de ' + safeFixed(metrics.sharpe_ratio) + ' - cherchez des actifs avec meilleur ratio risque/rendement.',
          action: 'Considérez réduire les memecoins, augmenter BTC/ETH'
        });
      }

      // Diversification recommendations (alignée aux seuils UI)
      if (correlations.diversification_ratio < 0.4) {
        recommendations.push({
          priority: 'high',
          icon: '🔄',
          title: 'Améliorer la diversification',
          description: 'Ratio de diversification très faible (' + safeFixed(correlations.diversification_ratio) + '). Portfolio trop corrélé.',
          action: 'Ajoutez des actifs décorrélés: privacy coins, stablecoins, secteurs différents'
        });
      } else if (correlations.diversification_ratio < 0.7) {
        recommendations.push({
          priority: 'medium',
          icon: '🔄',
          title: 'Améliorer la diversification',
          description: 'Diversification limitée (' + safeFixed(correlations.diversification_ratio) + ').',
          action: 'Élargissez les secteurs et réduisez les paires très corrélées'
        });
      }

      // Effective assets recommendations  
      if (correlations.effective_assets < 3) {
        recommendations.push({
          priority: 'medium',
          icon: '⚖️',
          title: 'Réduire la concentration',
          description: 'Portfolio se comporte comme ' + safeFixed(correlations.effective_assets, 1) + ' actifs seulement.',
          action: 'Rééquilibrez: limitez tout actif à <20% du portfolio'
        });
      }

      // Drawdown recommendations (max_drawdown renvoyé en valeur positive)
      if (metrics.max_drawdown > 0.6) {
        recommendations.push({
          priority: 'high',
          icon: '📉',
          title: 'Protéger contre les chutes extrêmes',
          description: 'Max drawdown de ' + formatPercent(metrics.max_drawdown) + ' très élevé.',
          action: 'Stratégie défensive: DCA, stop-loss, ou hedging avec stablecoins'
        });
      }

      // High correlation recommendations
      if (correlations.top_correlations) {
        const highCorrels = correlations.top_correlations.filter(c => Math.abs(c.correlation) > 0.75);
        if (highCorrels.length > 0) {
          recommendations.push({
            priority: 'medium',
            icon: '🔗',
            title: 'Réduire les corrélations élevées',
            description: 'Corrélations >75% détectées entre ' + highCorrels.map(c => c.asset1 + '-' + c.asset2).join(', '),
            action: 'Diversifiez vers des secteurs moins corrélés (BTC vs ETH vs secteurs niche)'
          });
        }
      }

      // If everything is good, add positive reinforcement
      if (recommendations.length === 0) {
        recommendations.push({
          priority: 'low',
          icon: '✅',
          title: 'Portfolio bien équilibré',
          description: 'Vos métriques de risque sont dans les normes crypto acceptables.',
          action: 'Continuez le monitoring et ajustez selon les conditions de marché'
        });
      }

      // Sort by priority
      const priorityOrder = { 'high': 0, 'medium': 1, 'low': 2 };
      return recommendations.sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);
    }

    // NOTE: calculateCorrelationMetrics() supprimée - corrélations calculées par le backend Python

    // Import unified asset grouping functions with forced taxonomy reload
    let groupAssetsByClassification, getAssetGroup;

    // Load unified asset groups dynamically with forced taxonomy reload
    async function initAssetGroups() {
      try {
        console.debug('🔄 [Risk Dashboard] Force reloading taxonomy for proper asset classification...');
        const module = await import('../shared-asset-groups.js');
        await module.forceReloadTaxonomy();

        groupAssetsByClassification = module.groupAssetsByClassification;
        getAssetGroup = module.getAssetGroup;

        if (!Object.keys(module.UNIFIED_ASSET_GROUPS || {}).length) {
          debugLogger.warn('⚠️ [Risk Dashboard] Taxonomy non chargée – risque de "Others" gonflé');
        } else {
          debugLogger.debug('✅ [Risk Dashboard] Taxonomy loaded:', Object.keys(module.UNIFIED_ASSET_GROUPS).length, 'groupes');
        }
      } catch (error) {
        debugLogger.error('❌ [Risk Dashboard] Failed to load taxonomy:', error);
      }
    }

    // Initialize asset groups on page load
    initAssetGroups();

    async function groupAssetsByAliases(items) {
      console.debug('🔍 [Risk Dashboard] Grouping', items.length, 'assets by unified taxonomy');

      // Utiliser le système unifié si disponible
      if (groupAssetsByClassification) {
        return groupAssetsByClassification(items);
      }

      // Si pas encore chargé, charger maintenant
      try {
        console.debug('⏳ [Risk Dashboard] Taxonomy not loaded yet, importing now...');
        const module = await import('../shared-asset-groups.js');
        await module.forceReloadTaxonomy();
        groupAssetsByClassification = module.groupAssetsByClassification;
        getAssetGroup = module.getAssetGroup;
        return groupAssetsByClassification(items);
      } catch (error) {
        // Fallback simple si le module n'est pas encore chargé
        debugLogger.warn('⚠️ [Risk Dashboard] Unified groups failed to load, using simple fallback:', error);
        return items.map(item => ({
          label: item.symbol,
          value: parseFloat(item.value_usd || 0),
          assets: [item.symbol]
        }));
      }
    }

    // ====== CCS Functions ======
    async function loadCCSData() {
      try {
        console.debug('Loading CCS data...');

        // Fetch CCS and cycle data in parallel
        const [ccsResult, cycleData] = await Promise.all([
          fetchAndComputeCCS(DEFAULT_CCS_WEIGHTS),
          estimateCyclePosition()
        ]);

        // Update store with CCS data
        store.set('ccs.score', ccsResult.score);
        store.set('ccs.signals', ccsResult.signals);
        store.set('ccs.weights', ccsResult.weights);
        store.set('ccs.lastUpdate', new Date().toISOString());
        store.set('ccs.model_version', ccsResult.model_version);

        // Update store with cycle data
        store.set('cycle.months', cycleData.months);
        store.set('cycle.phase', cycleData.phase);
        store.set('cycle.score', cycleData.score);
        store.set('cycle.confidence', cycleData.confidence);
        store.set('cycle.multipliers', cycleData.multipliers);

        // Update API status
        store.set('ui.apiStatus.signals', 'healthy');

        console.debug(`CCS loaded: ${ccsResult.score}, Cycle: ${cycleData.phase.phase} (${Math.round(cycleData.months)}m)`);

        return { ccs: ccsResult, cycle: cycleData };

      } catch (error) {
        debugLogger.error('Failed to load CCS data:', error);
        store.set('ui.apiStatus.signals', 'error');
        throw error;
      }
    }

    async function loadBlendedCCS() {
      try {
        const state = store.snapshot();
        const ccsScore = state.ccs?.score;
        const cycleMonths = state.cycle?.months;
        const cycleWeight = state.cycle?.weight || 0.3;

        if (ccsScore && cycleMonths) {
          const blended = blendCCS(ccsScore, cycleMonths, cycleWeight);
          store.set('cycle.ccsStar', blended.blendedCCS);
          return blended;
        }

        return null;
      } catch (error) {
        debugLogger.error('Failed to blend CCS:', error);
        return null;
      }
    }

    // ====== Alerts Functions ======
    async function fetchAlertsData() {
      try {
        console.debug('Loading alerts data...');

        const alertsData = await window.globalConfig.apiRequest('/api/alerts/active', {
          params: { include_snoozed: false }
        });
        console.debug(`Alerts loaded: ${alertsData.length} active alerts`);

        return alertsData;

      } catch (error) {
        debugLogger.error('Failed to load alerts data:', error);
        throw error;
      }
    }

    function updateAlertsDisplay(alertsData) {
      const alertsDot = document.getElementById('alerts-dot');
      const alertsText = document.getElementById('alerts-text');
      const alertsList = document.getElementById('alerts-list');

      if (!alertsDot || !alertsText || !alertsList) {
        // Elements are now in Web Component <risk-sidebar-full>, skip legacy update
        console.debug('Alerts display: skipping legacy DOM update (elements in Web Component)');
        return;
      }

      if (!alertsData || alertsData.length === 0) {
        // No alerts
        alertsDot.className = 'status-dot healthy';
        alertsText.textContent = 'No active alerts';
        alertsList.replaceChildren(); // CSP safe replacement for innerHTML = ''

        // Always show the "View All History" button even when no active alerts
        const historyButton = document.createElement('div');
        historyButton.className = 'alerts-button-container';

        const viewHistoryBtn = document.createElement('button');
        viewHistoryBtn.className = 'alerts-history-btn';
        viewHistoryBtn.textContent = '📋 View All History';
        viewHistoryBtn.setAttribute('data-action', 'view-alerts-history');

        historyButton.appendChild(viewHistoryBtn);
        alertsList.appendChild(historyButton);
        return;
      }

      // Count alerts by severity
      const severityCounts = { S1: 0, S2: 0, S3: 0 };
      alertsData.forEach(alert => {
        if (severityCounts.hasOwnProperty(alert.severity)) {
          severityCounts[alert.severity]++;
        }
      });

      // Set status based on highest severity
      let statusClass = 'healthy';
      let statusText = `${alertsData.length} alert${alertsData.length > 1 ? 's' : ''}`;

      if (severityCounts.S3 > 0) {
        statusClass = 'error';
        statusText = `${severityCounts.S3} critical alert${severityCounts.S3 > 1 ? 's' : ''}`;
      } else if (severityCounts.S2 > 0) {
        statusClass = 'warning';
        statusText = `${severityCounts.S2} warning alert${severityCounts.S2 > 1 ? 's' : ''}`;
      }

      alertsDot.className = `status-dot ${statusClass}`;
      alertsText.textContent = statusText;

      // Render alerts list
      alertsList.replaceChildren(); // CSP safe replacement for innerHTML = ''

      // Sort alerts by severity (S3, S2, S1) and creation time
      const sortedAlerts = [...alertsData].sort((a, b) => {
        const severityOrder = { S3: 0, S2: 1, S1: 2 };
        const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
        if (severityDiff !== 0) return severityDiff;

        // Then by creation time (newest first)
        return new Date(b.created_at) - new Date(a.created_at);
      });

      // Limit to 5 most important alerts in sidebar
      sortedAlerts.slice(0, 5).forEach(alert => {
        const alertItem = createAlertItem(alert);
        alertsList.appendChild(alertItem);
      });

      // Add "show more" indicator if there are more alerts
      if (sortedAlerts.length > 5) {
        const moreItem = document.createElement('div');
        moreItem.style.textAlign = 'center';
        moreItem.style.padding = '4px';
        moreItem.style.fontSize = '0.7rem';
        moreItem.style.color = 'var(--theme-text-muted)';
        moreItem.textContent = `+${sortedAlerts.length - 5} more alerts...`;
        alertsList.appendChild(moreItem);
      }
    }

    function createAlertItem(alert) {
      const item = document.createElement('div');
      item.className = `alert-item severity-${alert.severity}`;

      const severity = document.createElement('div');
      severity.className = `alert-severity ${alert.severity}`;
      severity.textContent = alert.severity;

      const content = document.createElement('div');
      content.className = 'alert-content';

      const type = document.createElement('div');
      type.className = 'alert-type';
      type.textContent = formatAlertType(alert.alert_type);

      const message = document.createElement('div');
      message.className = 'alert-message';
      message.textContent = formatAlertMessage(alert);

      const timestamp = document.createElement('div');
      timestamp.className = 'alert-timestamp';
      timestamp.textContent = formatRelativeTime(alert.created_at);

      content.appendChild(type);
      content.appendChild(message);
      content.appendChild(timestamp);

      // Add action buttons for major alerts
      if (alert.severity === 'S2' || alert.severity === 'S3') {
        const actions = document.createElement('div');
        actions.className = 'alert-actions';

        const ackButton = document.createElement('button');
        ackButton.className = 'alert-action-btn';
        ackButton.textContent = 'Ack';
        ackButton.title = 'Acknowledge alert';
        ackButton.onclick = () => acknowledgeAlert(alert.id);

        const snoozeButton = document.createElement('button');
        snoozeButton.className = 'alert-action-btn';
        snoozeButton.textContent = 'Snooze';
        snoozeButton.title = 'Snooze for 30 minutes';
        snoozeButton.onclick = () => snoozeAlert(alert.id, 30);

        actions.appendChild(ackButton);
        actions.appendChild(snoozeButton);
        content.appendChild(actions);
      }

      item.appendChild(severity);
      item.appendChild(content);

      return item;
    }

    function formatAlertType(alertType) {
      const typeMap = {
        'VOL_Q90_CROSS': 'High Volatility',
        'REGIME_FLIP': 'Regime Change',
        'CORR_HIGH': 'High Correlation',
        'CONTRADICTION_SPIKE': 'ML Contradiction',
        'DECISION_DROP': 'Low Confidence',
        'EXEC_COST_SPIKE': 'High Exec Cost'
      };

      return typeMap[alertType] || alertType;
    }

    function formatAlertMessage(alert) {
      if (alert.data && typeof alert.data === 'object') {
        // Extract meaningful data from alert
        if (alert.data.value !== undefined) {
          return `Value: ${(alert.data.value * 100).toFixed(1)}%`;
        }
        if (alert.data.confidence !== undefined) {
          return `Confidence: ${(alert.data.confidence * 100).toFixed(1)}%`;
        }
      }

      return alert.suggested_action?.reason || 'Alert triggered';
    }

    function formatRelativeTime(timestamp) {
      const now = new Date();
      const alertTime = new Date(timestamp);
      const diffMs = now - alertTime;
      const diffMins = Math.floor(diffMs / 60000);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;

      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}h ago`;

      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d ago`;
    }

    async function acknowledgeAlert(alertId) {
      try {
        const response = await window.globalConfig.apiRequest(`/api/alerts/test/acknowledge/${alertId}`, {
          method: 'POST',
          body: JSON.stringify({ notes: 'Acknowledged from dashboard' })
        });

        if (response && (response.ok || response.success || !response.error)) {
          // Refresh alerts display
          const alertsData = await fetchAlertsData();
          updateAlertsDisplay(alertsData);
          debugLogger.debug(`Alert ${alertId} acknowledged`);
        } else {
          debugLogger.error('Failed to acknowledge alert:', response.status);
        }
      } catch (error) {
        debugLogger.error('Error acknowledging alert:', error);
      }
    }

    async function snoozeAlert(alertId, minutes) {
      try {
        const response = await window.globalConfig.apiRequest(`/api/alerts/test/snooze/${alertId}`, {
          method: 'POST',
          body: JSON.stringify({ minutes })
        });

        if (response && (response.ok || response.success || !response.error)) {
          // Refresh alerts display
          const alertsData = await fetchAlertsData();
          updateAlertsDisplay(alertsData);
          debugLogger.debug(`Alert ${alertId} snoozed for ${minutes} minutes`);
        } else {
          debugLogger.error('Failed to snooze alert:', response.status);
        }
      } catch (error) {
        debugLogger.error('Error snoozing alert:', error);
      }
    }

    // ====== Alerts History Functions ======
    let alertsHistoryData = [];
    let currentAlertsPage = 1;
    let totalAlertsPages = 1;
    const alertsPerPage = 10;

    async function fetchAlertsHistory(filters = {}) {
      try {
        console.debug('Loading alerts history...', filters);

        // Build query parameters
        const params = new URLSearchParams();
        params.append('limit', '100'); // Fetch more for client-side filtering
        params.append('offset', '0');
        params.append('include_snoozed', 'true');

        // Only add filters if they have values (don't filter if empty)
        if (filters.severity && filters.severity.trim() !== '') {
          params.append('severity_filter', filters.severity);
        }
        if (filters.type && filters.type.trim() !== '') {
          params.append('type_filter', filters.type);
        }

        // Use active endpoint with X-User header via globalConfig
        const alerts = await window.globalConfig.apiRequest('/api/alerts/active', {
          params: Object.fromEntries(params)
        });
        console.debug(`History loaded: ${alerts?.length || 0} alerts`, alerts.slice(0, 2));

        return alerts || [];

      } catch (error) {
        debugLogger.error('Failed to load alerts history:', error);
        throw error;
      }
    }

    function filterAlertsHistoryByPeriod(alerts, days) {
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - days);

      return alerts.filter(alert => {
        const alertDate = new Date(alert.created_at);
        return alertDate >= cutoffDate;
      });
    }

    async function loadAlertsHistory() {
      try {
        const severityFilterEl = document.getElementById('alerts-severity-filter');
        const typeFilterEl = document.getElementById('alerts-type-filter');
        const periodFilterEl = document.getElementById('alerts-period-filter');

        const severityFilter = severityFilterEl ? severityFilterEl.value : '';
        const typeFilter = typeFilterEl ? typeFilterEl.value : '';
        const periodDays = periodFilterEl ? parseInt(periodFilterEl.value) : 7;

        console.debug('Loading alerts with filters:', { severityFilter, typeFilter, periodDays });

        // Fetch all alerts with basic filters
        let alerts = await fetchAlertsHistory({
          severity: severityFilter,
          type: typeFilter
        });

        // Filter by period client-side
        alerts = filterAlertsHistoryByPeriod(alerts, periodDays);

        alertsHistoryData = alerts;

        // Store globally for modal system
        window.currentAlertsData = alerts;

        currentAlertsPage = 1;
        totalAlertsPages = Math.ceil(alerts.length / alertsPerPage);

        renderAlertsHistoryPage();
        updateAlertsStats(alerts);

      } catch (error) {
        debugLogger.error('Error loading alerts history:', error);
        const errorContainer = document.getElementById('alerts-history-content');
        if (errorContainer) {
          errorContainer.innerHTML =
            '<div class="error">Failed to load alerts history. Please try again.</div>';
        }
      }
    }

    function renderAlertsHistoryPage() {
      const container = document.getElementById('alerts-history-content');
      const paginationContainer = document.getElementById('alerts-pagination');

      // Guard: Check if elements exist
      if (!container || !paginationContainer) {
        debugLogger.warn('⚠️ Alerts DOM elements not found, skipping render');
        return;
      }

      if (!alertsHistoryData.length) {
        container.innerHTML = '<div class="no-data">No alerts found for the selected criteria.</div>';
        paginationContainer.style.display = 'none';
        return;
      }

      // Calculate pagination
      const start = (currentAlertsPage - 1) * alertsPerPage;
      const end = start + alertsPerPage;
      const pageAlerts = alertsHistoryData.slice(start, end);

      // Render alerts table
      const table = document.createElement('table');
      table.className = 'alerts-table';

      // Table header
      table.innerHTML = `
        <thead>
          <tr>
            <th>Severity</th>
            <th>Type</th>
            <th>Message</th>
            <th>Created</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${pageAlerts.map(alert => createAlertsHistoryRow(alert)).join('')}
        </tbody>
      `;

      container.innerHTML = '';
      container.appendChild(table);

      // Update pagination
      updateAlertsPagination();
    }

    function createAlertsHistoryRow(alert) {
      const formatTime = (timestamp) => {
        if (!timestamp) return '-';
        const date = new Date(timestamp);
        return date.toLocaleString();
      };

      const getStatusText = (alert) => {
        if (alert.acknowledged_at) {
          return `<span style="color: var(--success)">✅ Acknowledged</span>`;
        }
        if (alert.snooze_until && new Date(alert.snooze_until) > new Date()) {
          return `<span style="color: var(--warning)">⏸️ Snoozed</span>`;
        }
        return `<span style="color: var(--error)">🚨 Active</span>`;
      };

      // Format unifié : Action → Impact € → 2 raisons → Détails  
      const formatUnifiedAlert = (alert) => {
        // Simuler le formatage unifié côté client
        const formatted = formatAlertClientSide(alert);

        return `
          <div class="alert-unified-format">
            <div class="alert-action">
              <strong>🎯 ${formatted.action}</strong>
            </div>
            <div class="alert-impact">
              💰 Impact: <span class="alert-impact-value">${formatted.impact}</span>
            </div>
            <div class="alert-reasons">
              📋 Raisons:
              <ul class="alert-reasons-list">
                ${formatted.reasons.map(reason => `<li>${reason}</li>`).join('')}
              </ul>
            </div>
            <div class="alert-details">
              ℹ️ ${formatted.details}
            </div>
          </div>
        `;
      };

      // Formatage unifié côté client
      const formatAlertClientSide = (alert) => {
        const alertType = alert.alert_type;
        const severity = alert.severity;
        const currentValue = alert.data?.current_value || 0;
        const portfolioValue = 100000; // €100k par défaut

        // Templates simplifiés
        const templates = {
          'VOL_Q90_CROSS': {
            'S1': { action: 'Surveillance volatilité', impact_base: 0.5, reasons: ['Volatilité Q90 dépassée', 'Conditions de marché agitées'] },
            'S2': { action: 'Réduction exposition (mode Slow)', impact_base: 2.0, reasons: ['Volatilité critique détectée', 'Risque de drawdown majoré'] },
            'S3': { action: 'Arrêt immédiat trading (Freeze)', impact_base: 8.0, reasons: ['Volatilité extrême mesurée', 'Protection capital prioritaire'] }
          },
          'EXEC_COST_SPIKE': {
            'S1': { action: 'Surveillance coûts exécution', impact_base: 0.2, reasons: ['Coûts trading légèrement élevés', 'Conditions liquidité moyennes'] },
            'S2': { action: 'Ralentissement trading (mode Slow)', impact_base: 1.5, reasons: ['Coûts exécution anormalement hauts', 'Liquidité marché dégradée'] },
            'S3': { action: 'Arrêt trading (mode Freeze)', impact_base: 4.0, reasons: ['Coûts exécution prohibitifs', 'Liquidité marché très dégradée'] }
          },
          'DECISION_DROP': {
            'S1': { action: 'Monitoring confiance décision', impact_base: 0.4, reasons: ['Score décision en baisse', 'Confiance allocation réduite'] },
            'S2': { action: 'Mode prudent allocation', impact_base: 2.2, reasons: ['Chute confiance décision significative', 'Qualité allocation dégradée'] },
            'S3': { action: 'Mode ultra-conservateur (Freeze)', impact_base: 9.0, reasons: ['Effondrement confiance décision', 'Allocations potentiellement erronées'] }
          }
        };

        const template = templates[alertType]?.[severity] ||
          { action: `Alerte ${alertType}`, impact_base: 1.0, reasons: ['Situation détectée', 'Action recommandée'] };

        const impact_euro = portfolioValue * template.impact_base / 100;

        return {
          action: template.action,
          impact: impact_euro >= 1 ? `€${Math.round(impact_euro).toLocaleString()}` : `€${impact_euro.toFixed(2)}`,
          reasons: template.reasons,
          details: `Valeur ${currentValue} détectée - ${severity} à ${new Date(alert.created_at).toLocaleTimeString()}`
        };
      };

      return `
        <tr>
          <td>
            <span class="alert-severity-badge ${alert.severity}">${alert.severity}</span>
          </td>
          <td>
            <div class="alert-type-label">${formatAlertType(alert.alert_type)}</div>
          </td>
          <td class="alert-message-cell">
            ${formatUnifiedAlert(alert)}
          </td>
          <td>
            <div class="alert-timestamp">${formatTime(alert.created_at)}</div>
            <div class="alert-timestamp" style="font-size: 0.7rem; color: var(--text-muted);">${formatRelativeTime(alert.created_at)}</div>
          </td>
          <td>
            ${getStatusText(alert)}
          </td>
          <td>
            <button 
              class="alert-action-btn" 
              onclick="openAlertModal('${alert.id}')"
              title="View alert details">
              📋 Details
            </button>
          </td>
        </tr>
      `;
    }

    function updateAlertsStats(alerts) {
      console.debug('Updating alerts stats for', alerts?.length || 0, 'alerts');

      const stats = {
        total: alerts?.length || 0,
        S1: alerts?.filter(a => a.severity === 'S1').length || 0,
        S2: alerts?.filter(a => a.severity === 'S2').length || 0,
        S3: alerts?.filter(a => a.severity === 'S3').length || 0,
        acknowledged: alerts?.filter(a => a.acknowledged_at).length || 0
      };

      console.debug('Computed stats:', stats);

      const statsHtml = `
        <div class="alerts-stats" id="alerts-stats-display">
          <div class="alerts-stat">
            <div class="alerts-stat-number">${stats.total}</div>
            <div class="alerts-stat-label">Total</div>
          </div>
          <div class="alerts-stat">
            <div class="alerts-stat-number">${stats.S3}</div>
            <div class="alerts-stat-label">Critical</div>
          </div>
          <div class="alerts-stat">
            <div class="alerts-stat-number">${stats.S2}</div>
            <div class="alerts-stat-label">Warnings</div>
          </div>
          <div class="alerts-stat">
            <div class="alerts-stat-number">${stats.S1}</div>
            <div class="alerts-stat-label">Info</div>
          </div>
          <div class="alerts-stat">
            <div class="alerts-stat-number">${stats.acknowledged}</div>
            <div class="alerts-stat-label">Acknowledged</div>
          </div>
        </div>
      `;

      const container = document.getElementById('alerts-history-content');
      if (container) {
        // Remove existing stats if present
        const existingStats = document.getElementById('alerts-stats-display');
        if (existingStats) {
          existingStats.remove();
        }

        container.insertAdjacentHTML('afterbegin', statsHtml);
        console.debug('Stats HTML inserted into container');
      } else {
        debugLogger.warn('alerts-history-content container not found');
      }
    }

    function updateAlertsPagination() {
      const paginationContainer = document.getElementById('alerts-pagination');
      const prevBtn = document.getElementById('alerts-prev-btn');
      const nextBtn = document.getElementById('alerts-next-btn');
      const pageInfo = document.getElementById('alerts-page-info');

      // Guard: Check if pagination elements exist
      if (!paginationContainer || !prevBtn || !nextBtn || !pageInfo) {
        debugLogger.warn('⚠️ Pagination DOM elements not found, skipping update');
        return;
      }

      if (totalAlertsPages <= 1) {
        paginationContainer.style.display = 'none';
        return;
      }

      paginationContainer.style.display = 'flex';
      prevBtn.disabled = currentAlertsPage <= 1;
      nextBtn.disabled = currentAlertsPage >= totalAlertsPages;
      pageInfo.textContent = `Page ${currentAlertsPage} of ${totalAlertsPages}`;
    }

    function loadPreviousAlertsPage() {
      if (currentAlertsPage > 1) {
        currentAlertsPage--;
        renderAlertsHistoryPage();
      }
    }

    function loadNextAlertsPage() {
      if (currentAlertsPage < totalAlertsPages) {
        currentAlertsPage++;
        renderAlertsHistoryPage();
      }
    }

    // DEFINE GLOBALLY
    window.filterAlertsHistory = function () {
      loadAlertsHistory();
    };

    function refreshAlertsHistory() {
      loadAlertsHistory();
    }

    // Load alerts history when the tab is switched to
    function initializeAlertsTab() {
      loadAlertsHistory();
    }

    // ====== Sidebar Updates ======
    // Note: Sidebar now handled by Web Component <risk-sidebar-full> in flyout-panel


    // Risk rating rules for different metrics
    const RISK_RULES = {
      sharpe: { good: [0.5, 999], warn: [0.2, 0.5] },
      sortino: { good: [0.5, 999], warn: [0.2, 0.5] },
      volatility: { good: [0, 0.3], warn: [0.3, 0.6] },
      max_drawdown: { good: [0, 0.2], warn: [0.2, 0.4] },
      var95_1d: { good: [0, 0.05], warn: [0.05, 0.10] },
      var99_1d: { good: [0, 0.08], warn: [0.08, 0.15] },
      cvar95_1d: { good: [0, 0.07], warn: [0.07, 0.12] },
      cvar99_1d: { good: [0, 0.10], warn: [0.10, 0.18] },
      diversification_ratio: { good: [0.7, 2.0], warn: [0.4, 0.7] },
      effective_assets: { good: [10, 999], warn: [5, 10] }
    };

    function rate(key, value) {
      const r = RISK_RULES[key];
      if (!r || value == null || isNaN(value)) return { dot: 'orange', verdict: 'Indisponible', body: 'Donnée indisponible.' };
      const signed = value;
      let v = signed;
      // Pour ces métriques, on évalue la magnitude (valeur absolue) :
      if (['volatility', 'max_drawdown', 'var95_1d', 'var99_1d', 'cvar95_1d', 'cvar99_1d'].includes(key)) v = Math.abs(signed);
      const inR = ([a, b]) => v >= a && v < b;
      let dot = 'red', verdict = 'Élevé / risqué';
      if (inR(r.good)) { dot = 'green'; verdict = 'Plutôt bas / maîtrisé'; }
      else if (inR(r.warn)) { dot = 'orange'; verdict = 'Intermédiaire / à surveiller'; }
      return { dot, verdict, body: '', label: key };
    }

    // Note: Initialization moved to the bottom of the script

    // ====== Main Functions ======
    // ====== Score Calculation Functions ======

    // Calculate On-Chain Score (V2 System with optional dynamic weighting)
    async function calculateOnChainScore() {
      try {
        const indicators = await fetchAllIndicators();
        // Aucun indicateur exploitable → retourner null (et laisser l'UI gérer)
        if (!indicators || (indicators._metadata && indicators._metadata.available_count === 0)) {
          return null;
        }

        // Dynamic weighting always enabled (V2 production mode)
        const composite = calculateCompositeScoreV2(indicators, true);

        console.debug(`📊 Composite result: score=${composite.score}, version=${composite.version}, hasDynamic=${!!composite.dynamicWeighting}`);

        if (composite.dynamicWeighting) {
          console.debug(`🤖 Dynamic weighting applied: ${composite.dynamicWeighting.phase.name} phase`);
        }

        if (composite.score === null) {
          debugLogger.warn('⚠️ No real on-chain data available - returning null score');
          return null;
        }

        console.debug(`📊 On-Chain Score: ${composite.score} (${composite.message})`);

        // Stocker les métadonnées enrichies V2 pour utilisation par SMART
        store.set('scores.onchain_metadata', {
          categoryBreakdown: composite.categoryBreakdown,
          criticalZoneCount: composite.criticalZoneCount,
          totalIndicators: composite.totalIndicators,
          activeCategories: composite.activeCategories,
          contributors: composite.contributors.slice(0, 10), // Top 10 contributeurs
          confidence: composite.confidence,
          // V2 specific properties
          consensusSignals: composite.consensusSignals,
          correlationAnalysis: composite.correlationAnalysis,
          version: composite.version,
          improvements: composite.improvements,
          // Dynamic weighting properties (if enabled)
          dynamicWeighting: composite.dynamicWeighting
        });

        // Analyze contradictory signals V2
        const contradictions = analyzeContradictorySignals(composite.categoryBreakdown);
        if (contradictions.length > 0) {
          debugLogger.warn(`⚠️ ${contradictions.length} signaux contradictoires détectés:`, contradictions);
          store.set('scores.contradictory_signals', contradictions);
        }

        // Log des alertes critiques
        if (composite.criticalZoneCount > 0) {
          debugLogger.warn(`🚨 ${composite.criticalZoneCount} indicateur(s) en zone critique!`);

          const criticalIndicators = composite.contributors.filter(c => c.inCriticalZone);
          criticalIndicators.forEach(indicator => {
            debugLogger.warn(`  ⚠️ ${indicator.name}: ${indicator.originalValue}% (seuil: ${indicator.raw_threshold})`);
          });
        }

        // Log de la répartition par catégorie
        Object.entries(composite.categoryBreakdown).forEach(([category, data]) => {
          const emoji = category === 'onchain_fundamentals' ? '🔗' :
            category === 'cycle_technical' ? '📊' : '😨';
          console.debug(`  ${emoji} ${data.description}: ${data.score}/100 (${data.contributorsCount} indicateurs)`);
        });

        if (indicators._metadata?.missing_apis?.length > 0) {
          debugLogger.warn('⚠️ Missing APIs:', indicators._metadata.missing_apis);
        }

        return composite.score;
      } catch (error) {
        debugLogger.error('❌ Erreur calcul On-Chain Score:', error);
        return null; // Retourner null au lieu de fallback trompeur
      }
    }

    // ❌ SUPPRIMÉ: calculateRiskScore() locale (divergeait de l'orchestrator)
    // ✅ Maintenant calculé par risk-data-orchestrator.js (source unique SSOT)

    // Calculate strategic Blended Score (nouvelle formule market-aware)
    function calculateBlendedScore(ccsMixteScore, onchainScore, riskScore) {
      // Formule stratégique : 50% CCS Mixte + 30% On-Chain + 20% (100-Risk)
      if (ccsMixteScore == null && onchainScore == null && riskScore == null) {
        return 50; // Fallback neutre
      }

      console.debug('🎯 Calcul Blended Score stratégique:', {
        ccsMixte: ccsMixteScore,
        onchain: onchainScore,
        risk: riskScore
      });

      let totalScore = 0;
      let totalWeight = 0;

      // CCS Mixte : 50% (score directeur du marché)
      if (ccsMixteScore != null) {
        totalScore += ccsMixteScore * 0.50;
        totalWeight += 0.50;
        console.debug('  → CCS Mixte contributtion:', ccsMixteScore * 0.50);
      }

      // On-Chain Composite : 30% (fondamentaux réseau)
      if (onchainScore != null) {
        totalScore += onchainScore * 0.30;
        totalWeight += 0.30;
        console.debug('  → On-Chain contribution:', onchainScore * 0.30);
      } else {
        debugLogger.warn('  ⚠️ On-Chain Score non disponible (APIs payantes requises) - poids redistribué');
      }

      // Risk contribution : 20% (score direct, plus haut = plus robuste)
      // ✅ Respecte docs/RISK_SEMANTICS.md - NE PAS inverser
      if (riskScore != null) {
        totalScore += riskScore * 0.20;
        totalWeight += 0.20;
        console.debug('  → Risk contribution (direct):', riskScore * 0.20);
      }

      const finalScore = totalWeight > 0 ? totalScore / totalWeight : 50;
      console.debug('🎯 Final Blended Score:', finalScore, '(weight:', totalWeight, ')');

      return Math.max(0, Math.min(100, finalScore));
    }

    // Apply UI state based on blended decision score
    function applyDecisionState(score) {
      try {
        const el = document.getElementById('blended-gauge');
        if (!el || typeof score !== 'number') return;
        el.classList.remove('decision--bullish', 'decision--neutral', 'decision--defensive');
        let state = 'neutral';
        if (score >= 70) state = 'bullish';
        else if (score < 45) state = 'defensive';
        el.classList.add(`decision--${state}`);
      } catch (e) { /* no-op */ }
    }

    // ✅ REMPLACÉ: Load scores from orchestrator (SSOT)
    async function loadScoresFromStore() {
      try {
        console.debug('🔄 Waiting for orchestrator hydration...');

        // ✅ Attendre hydratation complète du store par l'orchestrator
        if (!store.getState()?._hydrated) {
          await new Promise(resolve => {
            const handler = (e) => {
              if (e.detail?.hydrated) {
                debugLogger.debug('✅ Store hydrated by orchestrator, source:', e.detail.source);
                resolve();
              }
            };
            window.addEventListener('riskStoreReady', handler, { once: true });
          });
        }

        // ✅ Lire scores depuis store (source unique)
        const state = store.snapshot();
        const onchainScore = state.scores?.onchain;
        const riskScore = state.scores?.risk;
        const blendedScore = state.scores?.blended;
        const ccsScore = state.ccs?.score;
        const ccsMixteScore = state.cycle?.ccsStar;

        console.debug('📊 Scores loaded from orchestrator:', {
          onchain: onchainScore,
          risk: riskScore,
          blended: blendedScore,
          ccs: ccsScore,
          ccsMixte: ccsMixteScore,
          source: state._hydration_source,
          duration: state._hydration_duration_ms + 'ms'
        });

        // ✅ Mettre à jour UI
        updateScoreDisplays(onchainScore, riskScore, blendedScore, ccsScore);
        updateMarketRegime(blendedScore, onchainScore, riskScore);

        // ✅ Compatibility: Store in localStorage for legacy cross-page access
        const dataSource = globalConfig.get('data_source') || 'unknown';
        const __user = (localStorage.getItem('activeUser') || 'demo');
        const __prefix = (k) => `${k}:${__user}`;
        try {
          // ✅ FIX: Ne pas stocker de strings vides - seulement stocker si la valeur existe
          // ⚠️ IMPORTANT: Toujours stocker le timestamp, même si certains scores sont null
          if (onchainScore !== null && onchainScore !== undefined) {
            localStorage.setItem(__prefix('risk_score_onchain'), onchainScore.toString());
          } else {
            localStorage.removeItem(__prefix('risk_score_onchain'));
          }
          if (riskScore !== null && riskScore !== undefined) {
            localStorage.setItem(__prefix('risk_score_risk'), riskScore.toString());
          } else {
            localStorage.removeItem(__prefix('risk_score_risk'));
          }
          if (blendedScore !== null && blendedScore !== undefined) {
            localStorage.setItem(__prefix('risk_score_blended'), blendedScore.toString());
          } else {
            localStorage.removeItem(__prefix('risk_score_blended'));
          }
          if (ccsScore !== null && ccsScore !== undefined) {
            localStorage.setItem(__prefix('risk_score_ccs'), ccsScore.toString());
          } else {
            localStorage.removeItem(__prefix('risk_score_ccs'));
          }
          // Toujours stocker le timestamp pour marquer la fraîcheur des données
          localStorage.setItem(__prefix('risk_score_timestamp'), Date.now().toString());
          localStorage.setItem(__prefix('risk_score_data_source'), dataSource);
        } catch (_) { }

        return { onchainScore, riskScore, blendedScore, ccsScore, ccsMixteScore };

      } catch (error) {
        debugLogger.error('❌ Erreur chargement scores depuis store:', error);
        // ✅ Fallback: Use partial data if available
        const state = store.snapshot();
        return {
          onchainScore: state.scores?.onchain ?? null,
          riskScore: state.scores?.risk ?? null,
          blendedScore: state.scores?.blended ?? null,
          ccsScore: state.ccs?.score ?? null,
          ccsMixteScore: state.cycle?.ccsStar ?? null
        };
      }
    }

    // ❌ OBSOLÈTE: calculateAllScores() supprimée (remplacée par loadScoresFromStore)
    // L'orchestrator est maintenant la source unique de vérité (SSOT)

    // ====== Market Regime Functions ======
    function updateMarketRegime(blendedScore, onchainScore, riskScore) {
      try {
        // Calculate regime data
        const regimeData = getRegimeDisplayData(blendedScore, onchainScore, riskScore);
        const regime = regimeData.regime;

        console.debug('📊 Market Regime calculated:', regime);

        // Update Market Regime display
        const regimeDot = document.getElementById('regime-dot');
        const regimeText = document.getElementById('regime-text');

        if (regimeDot && regimeText) {
          regimeDot.style.backgroundColor = regime.color;
          regimeDot.className = 'status-dot active';

          const confidenceText = `${Math.round(regime.confidence * 100)}%`;
          regimeText.innerHTML = `
            <div style="font-weight: bold; color: ${regime.color};">
              ${regime.emoji} ${regime.name}
            </div>
            <div style="font-size: 0.8rem; margin-top: 2px;">
              Score: ${regime.score.toFixed(2)} | Conf: ${confidenceText}
            </div>
          `;

          // Store regime data for other components
          store.set('market.regime', regimeData);
        }

      } catch (error) {
        debugLogger.error('❌ Error updating market regime:', error);

        const regimeText = document.getElementById('regime-text');
        if (regimeText) {
          regimeText.textContent = 'Error calculating regime';
        }
      }
    }

    // ====== Dynamic Weighting Functions ======
    // Fallback banner toggle (backend status)
    setInterval(() => {
      try {
        const status = store.get('ui.apiStatus.backend');
        const banner = document.getElementById('backend-fallback-banner');
        if (!banner) return;
        banner.style.display = (status && status !== 'healthy') ? 'block' : 'none';
      } catch { }
    }, 2000);

    // Dynamic weighting is now always enabled (V2 production mode)
    // Legacy functions removed: toggleDynamicWeighting, initializeDynamicWeightingToggle

    // ====== Section Collapse Functions ======


    window.toggleSection = function (sectionId) {
      const content = document.getElementById(sectionId + '-content');
      const arrow = document.getElementById(sectionId + '-arrow');

      if (!content || !arrow) return;

      const isCollapsed = content.style.display === 'none';

      if (isCollapsed) {
        content.style.display = '';
        arrow.textContent = '▼';
        localStorage.setItem(`section_${sectionId}_collapsed`, 'false');

        // Observe lazy elements; only force-load if they are near viewport
        setTimeout(() => {
          const lazyElements = content.querySelectorAll('[data-lazy-load]');
          debugLogger.debug(`🔍 Section ${sectionId} expanded, checking ${lazyElements.length} lazy elements`);

          const isNearViewport = (el, margin = 150) => {
            try {
              const r = el.getBoundingClientRect();
              const vh = window.innerHeight || document.documentElement.clientHeight;
              return r.top < vh + margin && r.bottom > -margin;
            } catch (_) { return false; }
          };

          lazyElements.forEach(element => {
            if (!element.classList.contains('lazy-loaded') && !element.classList.contains('lazy-error')) {
              if (isNearViewport(element)) {
                debugLogger.debug(`📊 Element near viewport; loading now in section ${sectionId}`);
                window.lazyLoader?.loadVisibleElement(element);
              } else {
                debugLogger.debug(`👁️ Element not near viewport; ensuring observer is attached`);
                if (window.lazyLoader?.intersectionObserver) {
                  try { window.lazyLoader.intersectionObserver.observe(element); } catch (_) { }
                }
              }
            }
          });
        }, 100);
      } else {
        content.style.display = 'none';
        arrow.textContent = '▶';
        localStorage.setItem(`section_${sectionId}_collapsed`, 'true');
      }
    }

    // Initialize section states on page load
    function initializeSectionStates() {
      const sections = ['onchain-indicators', 'bitcoin-cycle', 'dynamic-weighting-info'];

      sections.forEach(sectionId => {
        const isCollapsed = localStorage.getItem(`section_${sectionId}_collapsed`) === 'true';
        const content = document.getElementById(sectionId + '-content');
        const arrow = document.getElementById(sectionId + '-arrow');

        if (content && arrow) {
          if (isCollapsed) {
            content.style.display = 'none';
            arrow.textContent = '▶';
          } else {
            content.style.display = '';
            arrow.textContent = '▼';

            // Ensure lazy elements are observed; only force-load if near viewport
            setTimeout(() => {
              const lazyElements = content.querySelectorAll('[data-lazy-load]');
              if (lazyElements.length > 0) {
                debugLogger.debug(`🔍 Section ${sectionId} is open by default, checking ${lazyElements.length} lazy elements`);

                lazyElements.forEach(element => {
                  if (!element.classList.contains('lazy-loaded') && !element.classList.contains('lazy-error')) {
                    const isNearViewport = (el, margin = 150) => {
                      try {
                        const r = el.getBoundingClientRect();
                        const vh = window.innerHeight || document.documentElement.clientHeight;
                        return r.top < vh + margin && r.bottom > -margin;
                      } catch (_) { return false; }
                    };

                    if (isNearViewport(element)) {
                      debugLogger.debug(`📊 Element near viewport; loading now in open section ${sectionId}`);
                      setTimeout(() => { window.lazyLoader?.loadVisibleElement(element); }, 300);
                    } else {
                      debugLogger.debug(`👁️ Element not near viewport; ensuring observer is attached`);
                      if (window.lazyLoader?.intersectionObserver) {
                        try { window.lazyLoader.intersectionObserver.observe(element); } catch (_) { }
                      }
                    }
                  }
                });
              }
            }, 100);
          }
        }
      });
    }

    async function refreshDashboard(forceRefresh = false) {
      if (isRefreshing) return;
      isRefreshing = true;
      // Ensure currency rate loaded before render when not USD
      try {
        const cur = (window.globalConfig && window.globalConfig.get('display_currency')) || 'USD';
        if (window.currencyManager && cur !== 'USD') {
          await window.currencyManager.ensureRate(cur);
        }
      } catch (_) { }

      const refreshBtn = document.getElementById('refresh-btn');
      refreshBtn.disabled = true;
      // Optional: disable dropdown trigger if present
      const refreshMenuBtn = document.getElementById('refresh-menu-btn');
      if (refreshMenuBtn) refreshMenuBtn.disabled = true;
      const forceRefreshBtn = document.getElementById('force-refresh-btn');
      if (forceRefreshBtn) forceRefreshBtn.disabled = true;
      refreshBtn.textContent = forceRefresh ? '🔄 Force Refreshing…' : '🔄 Refreshing…';

      // Clear cache if force refresh is requested
      if (forceRefresh) {
        clearAllPersistentCache();
        debugLogger.debug('🧹 Force refresh: all cache cleared');
      }

      // Update loading state
      store.set('ui.loading', true);
      store.set('ui.apiStatus.backend', 'unknown');

      try {
        // Fetch risk data, CCS data, and alerts in parallel
        const [riskData, ccsData, alertsData] = await Promise.all([
          fetchRiskData(),
          loadCCSData().catch(err => {
            debugLogger.warn('CCS data failed, continuing with risk only:', err);
            return null;
          }),
          fetchAlertsData().catch(err => {
            debugLogger.warn('Alerts data failed, continuing without alerts:', err);
            return null;
          })
        ]);

        if (riskData && riskData.success) {
          // Update store with risk data
          store.set('riskMetrics', riskData.risk_metrics);
          store.set('portfolioSummary', riskData.portfolio_summary);
          store.set('correlationMetrics', riskData.correlation_metrics);
          store.set('ui.apiStatus.backend', 'healthy');

          // Render risk dashboard in the active tab
          renderRiskDashboard(riskData);

          // Update timestamp
          if (riskData.timestamp && riskData.calculation_time) {
            updateTimestamp(riskData.timestamp, riskData.calculation_time);
          }

          // Load advanced components after main dashboard is rendered
          await loadAdvancedRiskComponents();

          // If CCS data loaded successfully, compute blended CCS
          if (ccsData) {
            await loadBlendedCCS();
          }

          // ✅ Load scores from orchestrator (SSOT)
          await loadScoresFromStore();

          // Force sidebar update after all scores are calculated
          const finalState = store.snapshot();
          // Update alerts in store (for risk-sidebar-full component)
          store.set('alerts', alertsData || []);

          // Update alerts display
          updateAlertsDisplay(alertsData);

          // Also update cycles content (contains composite score display) 
          if (finalState.ccs?.score && finalState.cycle?.months) {
            await renderCyclesContent();
            console.debug('🔄 Cycles content updated with latest data');
          }

          debugLogger.debug('Risk dashboard refreshed successfully');

        } else {
          // Handle API error with informative message, but still compute partial scores (on-chain + defaults)
          store.set('ui.apiStatus.backend', 'error');
          const errorType = riskData?.error_type || 'unknown';
          const errorMessage = riskData?.message || 'Failed to load risk dashboard';

          if (errorType === 'connection_error') {
            renderBackendUnavailable(errorMessage);
          } else {
            renderApiError(errorMessage);
          }

          // Attempt partial scoring so risk-sidebar-full component is still populated
          try {
            if (ccsData) {
              await loadBlendedCCS();
            }
            await loadScoresFromStore();
          } catch (e) {
            debugLogger.warn('Partial score calculation failed:', e);
          }
          return; // Don't throw, just render error state
        }

      } catch (err) {
        debugLogger.error('Dashboard error:', err);
        store.set('ui.apiStatus.backend', 'error');
        renderBackendUnavailable('Erreur de connexion au backend de risque');
      } finally {
        isRefreshing = false;
        store.set('ui.loading', false);
        refreshBtn.disabled = false;
        if (refreshMenuBtn) refreshMenuBtn.disabled = false;
        if (forceRefreshBtn) forceRefreshBtn.disabled = false;
        refreshBtn.textContent = '🔄 Refresh';
      }
    }

    // Update badges with current risk data
    function updateRiskDashboardBadges(data) {
      if (!window.riskDashboardBadges) return;

      try {
        const now = new Date();

        // Risk Overview badge
        const riskMetrics = data?.risk_metrics || {};
        const portfolioSummary = data?.portfolio_summary || {};
        const contradiction = Math.round((data?.correlation_metrics?.average_correlation || 0.3) * 100);
        const varCap = Math.round((riskMetrics.var_95_1d || 0.05) * 100);

        if (window.riskDashboardBadges.riskOverview) {
          window.riskDashboardBadges.riskOverview.updateData({
            source: 'Risk Engine',
            updated: now,
            contradiction: contradiction,
            cap: varCap,
            overrides: data?.overrides_count || 0,
            status: data ? 'ok' : 'error'
          });
        }

        // Cycles badge
        if (window.riskDashboardBadges.cycles) {
          window.riskDashboardBadges.cycles.updateData({
            source: 'Market Cycles',
            updated: now,
            contradiction: Math.round(Math.random() * 50), // Placeholder
            status: 'ok'
          });
        }

        // Targets badge
        if (window.riskDashboardBadges.targets) {
          window.riskDashboardBadges.targets.updateData({
            source: 'Targets',
            updated: now,
            contradiction: Math.round(Math.random() * 30), // Placeholder
            status: 'ok'
          });
        }

        debugLogger.debug('🏷️ Risk dashboard badges updated');
      } catch (error) {
        debugLogger.warn('Risk badge update failed:', error);
      }
    }

    function renderRiskDashboard(data) {
      const container = document.getElementById('risk-dashboard-content');
      if (!data || !data.risk_metrics || !data.correlation_metrics || !data.portfolio_summary) {
        renderError('Incomplete data received from API'); return;
      }

      // Afficher un bandeau pour le mode test
      let testModeBanner = '';
      if (data.test_mode) {
        testModeBanner = `
          <div style="background: var(--info-bg); border: 1px solid var(--info); border-radius: var(--radius-md); padding: 1rem; margin-bottom: 1.5rem; text-align: center;">
            <div style="color: var(--info); font-weight: 600; margin-bottom: 0.5rem;">🧪 MODE TEST - Données Réelles</div>
            <div style="color: var(--theme-text-muted); font-size: 0.9rem;">
              Portfolio de démonstration utilisant le cache d'historique de prix réel (${data.test_holdings?.length || 0} assets, ${formatMoney(data.portfolio_summary.total_value)})
            </div>
          </div>
        `;
      }
      const m = data.risk_metrics;
      const c = data.correlation_metrics;
      const p = data.portfolio_summary;
      const balances = Array.isArray(data.balances) ? data.balances : [];

      // Quick insights from balances for concentration and stablecoins
      const insights = (() => {
        const total = Number(p?.total_value) || balances.reduce((a, b) => a + Number(b.value_usd || 0), 0);
        if (!total || (!balances || balances.length === 0)) {
          return { top5Share: null, hhi: null, stableShare: null };
        }
        const sorted = balances
          .filter(x => Number(x.value_usd) > 0)
          .sort((a, b) => Number(b.value_usd) - Number(a.value_usd));
        const weights = sorted.map(x => Number(x.value_usd) / total);
        const top5Share = weights.slice(0, 5).reduce((a, b) => a + b, 0);
        const hhi = weights.reduce((a, b) => a + b * b, 0);
        // Stablecoins share
        const STABLES = new Set(['USDC', 'USDT', 'USD', 'DAI', 'USTC']);
        const stableValue = sorted
          .filter(x => STABLES.has(String(x.symbol || '').toUpperCase()))
          .reduce((a, b) => a + Number(b.value_usd || 0), 0);
        const stableShare = stableValue / total;
        return { top5Share, hhi, stableShare };
      })();

      // Helper functions are defined at the top of the script

      // Prépare: HTML recommandations et alertes pour la section top-summary
      // ✅ MODIFIÉ (Phase 1.1): Passe fullData pour accès à risk_budget
      const recos = generateRecommendations(m, c, p.groups || {}, data);
      const recommendationsHtml = (() => {
        return recos.map(rec => `
          <div class="recommendation recommendation-${rec.priority}">
            <div class="recommendation-header">
              <span class="recommendation-icon">${rec.icon}</span>
              <span class="recommendation-title">${rec.title}</span>
              <span class="recommendation-priority">${rec.priority === 'high' ? 'PRIORITÉ' : rec.priority === 'medium' ? 'Important' : 'Info'}</span>
            </div>
            <div class="recommendation-description">${rec.description}</div>
            <div class="recommendation-action">▶️ ${rec.action}</div>
          </div>
        `).join('');
      })();

      const alertCount = (data.alerts && data.alerts.length) ? data.alerts.length : 0;
      const severityCounts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
      (data.alerts || []).forEach(a => {
        const lvl = String(a.level || '').toLowerCase();
        if (severityCounts.hasOwnProperty(lvl)) severityCounts[lvl]++;
      });
      const hasSevere = (severityCounts.critical + severityCounts.high) > 0;
      const breakdown = (() => {
        const parts = [];
        if (severityCounts.critical) parts.push(`${severityCounts.critical} critical`);
        if (severityCounts.high) parts.push(`${severityCounts.high} high`);
        if (severityCounts.medium) parts.push(`${severityCounts.medium} medium`);
        if (parts.length === 0) return '';
        return ` (${parts.join(', ')})`;
      })();
      const alertsHtml = (alertCount) ? (
        data.alerts.map(a => `
          <div class="alert alert-${a.level}">
            <strong>${a.message}</strong><br>
            <em>Recommendation: ${a.recommendation}</em>
          </div>
        `).join('')
      ) : `
        <div class="alert alert-low">
          <strong>✅ All Clear</strong><br>
          <em>No significant risk alerts at this time.</em>
        </div>
      `;

      container.innerHTML = `
        ${testModeBanner}
        <!-- Top Summary: Collapsible container -->
        <details class="top-collapsible" ${hasSevere ? 'open' : ''}>
          <summary>
            <div>Vue d’ensemble risques & recommandations</div>
            <div class="summary-right">
              <span class="badge badge-alerts">⚠️ ${alertCount} alertes${breakdown}</span>
              <span class="badge badge-recos">💡 ${recos.length} recos</span>
              <span class="chevron">›</span>
            </div>
          </summary>
          <div class="top-summary">
          <!-- Points clés -->
          <div class="risk-card">
            <h3>📋 Points clés de votre portfolio</h3>
            <div class="insights-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: .75rem;">
              <div class="insight-item">
                <div style="font-weight: 600; color: var(--theme-text);">🎯 Niveau de risque</div>
                <div style="color: var(--theme-text-muted); margin-top: 0.25rem;">
                  ${(() => {
          const riskScore = m.risk_score || 0;
          // IMPORTANT: Risk Score positif - plus haut = meilleur (plus robuste)
          if (riskScore > 70) return 'Excellent - Portfolio très robuste';
          if (riskScore > 50) return 'Bon - Équilibre robustesse/rendement';
          return 'Faible - Attention aux fortes volatilités';
        })()}
                </div>
              </div>
              <div class="insight-item">
                <div style="font-weight: 600; color: var(--theme-text);">📊 Diversification</div>
                <div style="color: var(--theme-text-muted); margin-top: 0.25rem;">
                  ${(() => {
          const div = c.diversification_ratio || 0;
          if (div > 0.7) return 'Excellente - Portfolio bien réparti';
          if (div > 0.4) return 'Limitée - Possibilité d\'amélioration';
          return 'Faible - Trop corrélé, diversifiez';
        })()}
                </div>
              </div>
              <div class="insight-item">
                <div style="font-weight: 600; color: var(--theme-text);">⚡ Performance/Risque</div>
                <div style="color: var(--theme-text-muted); margin-top: 0.25rem;">
                  ${(() => {
          const sharpe = m.sharpe_ratio || 0;
          if (sharpe > 1.2) return 'Excellent - Rendement supérieur pour le risque pris';
          if (sharpe > 0.8) return 'Bon - Rendement acceptable pour le risque';
          return 'À améliorer - Risque élevé vs rendement';
        })()}
                </div>
              </div>
              <div class="insight-item">
                <div style="font-weight: 600; color: var(--theme-text);">🔝 Concentration</div>
                <div style="color: var(--theme-text-muted); margin-top: 0.25rem;">
                  ${(() => {
          const t5 = insights.top5Share;
          const hhi = insights.hhi;
          if (t5 == null || hhi == null) return 'N/A';
          return `Top 5: ${(t5 * 100).toFixed(1)}% • HHI: ${hhi.toFixed(2)}`;
        })()}
                </div>
              </div>
              <div class="insight-item">
                <div style="font-weight: 600; color: var(--theme-text);">💵 Stablecoins</div>
                <div style="color: var(--theme-text-muted); margin-top: 0.25rem;">
                  ${(() => {
          const s = insights.stableShare;
          return (s == null) ? 'N/A' : `${(s * 100).toFixed(1)}% du portefeuille`;
        })()}
                </div>
              </div>
              <div class="insight-item">
                <div style="font-weight: 600; color: var(--theme-text);">🧪 Données de calcul</div>
                <div style="color: var(--theme-text-muted); margin-top: 0.25rem;">
                  ${p.num_assets || (balances?.length || 'N/A')} actifs utilisés
                </div>
              </div>
            </div>
          </div>

          <!-- Risk Alerts -->
          <div class="risk-card">
            <h3>⚠️ Risk Alerts</h3>
            ${alertsHtml}
          </div>

          <!-- Recommandations d'amélioration -->
          <div class="risk-card">
            <h3>💡 Recommandations d'amélioration</h3>
            ${recommendationsHtml}
          </div>
          </div>
        </details>

        <!-- Portfolio Summary - Compact KPI Cards -->
        <div class="portfolio-summary-compact">
          <div class="kpi-card kpi-primary">
            <div class="kpi-icon">💰</div>
            <div class="kpi-content">
              <div class="kpi-label">Total Value</div>
              <div class="kpi-value">${formatMoney(p.total_value)}</div>
            </div>
          </div>

          <div class="kpi-card">
            <div class="kpi-icon">🎯</div>
            <div class="kpi-content">
              <div class="kpi-label">Assets</div>
              <div class="kpi-value">${p.num_assets}</div>
              <div class="kpi-subtext">${(() => {
                const effective = c.effective_assets;
                return effective ? `${safeFixed(effective, 1)} effective` : '';
              })()}</div>
            </div>
          </div>

          <div class="kpi-card">
            <div class="kpi-icon">📊</div>
            <div class="kpi-content">
              <div class="kpi-label">Diversification</div>
              <div class="kpi-value">${safeFixed(c.diversification_ratio, 2)}</div>
              <div class="kpi-subtext">${(() => {
                const div = c.diversification_ratio || 0;
                if (div > 0.7) return 'Excellent';
                if (div > 0.4) return 'Modéré';
                return 'Faible';
              })()}</div>
            </div>
          </div>

          <div class="kpi-card">
            <div class="kpi-icon">🔝</div>
            <div class="kpi-content">
              <div class="kpi-label">Top 5 Share</div>
              <div class="kpi-value">${(() => {
                const t5 = insights.top5Share;
                return t5 != null ? `${(t5 * 100).toFixed(1)}%` : 'N/A';
              })()}</div>
              <div class="kpi-subtext">Concentration</div>
            </div>
          </div>

          <div class="kpi-card">
            <div class="kpi-icon">💵</div>
            <div class="kpi-content">
              <div class="kpi-label">Stablecoins</div>
              <div class="kpi-value">${(() => {
                const s = insights.stableShare;
                return s != null ? `${(s * 100).toFixed(1)}%` : 'N/A';
              })()}</div>
              <div class="kpi-subtext">Protection</div>
            </div>
          </div>

          <div class="kpi-card">
            <div class="kpi-icon">✅</div>
            <div class="kpi-content">
              <div class="kpi-label">Data Quality</div>
              <div class="kpi-value">${safeFixed((p.confidence_level || 0) * 100, 1)}%</div>
              <div class="kpi-subtext">Confidence</div>
            </div>
          </div>
        </div>

        <!-- Key Insights moved to Top Summary -->

        <div class="risk-grid">
          <!-- 🆕 Risk Score Card (Oct 2025) -->
          <div class="risk-card">
            <h3>🎯 Risk Score <span style="font-size:.8rem; color: var(--theme-text); opacity:.7; font-weight:500; margin-left:.5rem;"><br>Robustness Indicator [0-100]</span></h3>

            <!-- Risk Score Principal -->
            <div class="metric-row">
              <span class="metric-label">Risk Score</span>
              <span class="metric-value hinted" data-key="risk_score" data-value="${m.risk_score}" data-score="risk-display" style="color: ${pickScoreColor(m.risk_score)}">
                ${safeFixed(m.risk_score, 1)}/100
              </span>
              <button class="btn-breakdown-toggle" onclick="toggleBreakdown('risk-score-breakdown')" title="Voir détail des pénalités" aria-label="Afficher le détail du calcul du Risk Score" style="margin-left: 8px; padding: 2px 8px; font-size: 0.75em; background: rgba(125, 207, 255, 0.15); border: 1px solid var(--brand-primary); border-radius: 4px; color: var(--brand-primary); cursor: pointer;">
                🔍 Détail
              </button>
            </div>

            <!-- Breakdown Panel -->
            <div id="risk-score-breakdown" class="breakdown-panel" style="display: none; margin: 8px 0; padding: 12px; background: rgba(30, 30, 46, 0.6); border-radius: 8px; border: 1px solid rgba(125, 207, 255, 0.2); font-size: 0.85em;">
              <div class="breakdown-header" style="font-weight: 600; color: var(--brand-primary); margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                <span>📊 Détail du calcul (Base = 50) ${m.risk_version_info ? `— ${m.risk_version_info.active_version === 'v2' ? 'V2' : 'Legacy'}` : ''}</span>
                <button onclick="toggleBreakdown('risk-score-breakdown')" style="background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 1.2em;" aria-label="Fermer">×</button>
              </div>
              <div class="breakdown-table" style="display: flex; flex-direction: column; gap: 4px;">
                <div class="breakdown-row breakdown-base" style="display: grid; grid-template-columns: 1fr auto auto; gap: 8px; padding: 4px; background: rgba(125, 207, 255, 0.05); border-radius: 4px;">
                  <span class="breakdown-label" style="color: var(--text-secondary);">Base neutre</span>
                  <span class="breakdown-value" style="color: var(--text-primary); font-weight: 600;">+50.0</span>
                  <span class="breakdown-cumul" style="color: var(--brand-primary); font-weight: 600; min-width: 50px; text-align: right;">50.0</span>
                </div>
                ${(() => {
                  // 🔧 Oct 2025: Use V2 breakdown when v2_active, otherwise legacy
                  const breakdown = m.structural_breakdown || {};
                  let cumul = 50.0;
                  const rows = [];
                  const order = ['var_95', 'sharpe', 'drawdown', 'volatility', 'memecoins', 'concentration', 'group_risk', 'diversification'];
                  const labels = {
                    var_95: 'VaR 95%',
                    sharpe: 'Sharpe Ratio',
                    drawdown: 'Max Drawdown',
                    volatility: 'Volatilité',
                    memecoins: 'Memecoins %',
                    concentration: 'Concentration (HHI)',
                    group_risk: 'Group Risk Index',
                    diversification: 'Diversification'
                  };
                  for (const key of order) {
                    if (breakdown[key] !== undefined) {
                      const delta = breakdown[key];
                      cumul += delta;
                      const color = delta > 0 ? '#9ece6a' : delta < 0 ? '#f7768e' : 'var(--text-secondary)';
                      rows.push(`
                        <div class="breakdown-row" style="display: grid; grid-template-columns: 1fr auto auto; gap: 8px; padding: 4px; border-radius: 4px;">
                          <span class="breakdown-label" style="color: var(--text-secondary);">${labels[key] || key}</span>
                          <span class="breakdown-value" style="color: ${color}; font-weight: 600;">${delta > 0 ? '+' : ''}${delta.toFixed(1)}</span>
                          <span class="breakdown-cumul" style="color: var(--text-primary); min-width: 50px; text-align: right;">${cumul.toFixed(1)}</span>
                        </div>
                      `);
                    }
                  }
                  return rows.join('');
                })()}
                <div class="breakdown-row breakdown-total" style="display: grid; grid-template-columns: 1fr auto auto; gap: 8px; padding: 6px 4px; margin-top: 4px; border-top: 1px solid rgba(125, 207, 255, 0.3); background: rgba(125, 207, 255, 0.08); border-radius: 4px;">
                  <span class="breakdown-label" style="color: var(--text-primary); font-weight: 700;">Total (clamped [0,100])</span>
                  <span class="breakdown-value" style="color: var(--text-tertiary);">—</span>
                  <span class="breakdown-cumul" style="color: var(--brand-primary); font-weight: 700; font-size: 1.1em; min-width: 50px; text-align: right;">${safeFixed(m.risk_score, 1)}</span>
                </div>
              </div>
            </div>

            <!-- Metric Interpretation -->
            <div class="metric-interpretation">
              💡 ${getScoreInterpretation(m.risk_score)}
            </div>

            <!-- Comparaison des Versions (V2 Autoritaire) -->
            ${m.risk_version_info ? `
            <div style="margin: 8px 0; padding: 8px; background: rgba(158, 206, 106, 0.1); border-radius: 6px; border-left: 3px solid #9ece6a;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 0.8em; font-weight: 600; color: #9ece6a;">
                  📊 Comparaison des Versions
                </span>
                <span style="font-size: 0.7em; color: var(--text-tertiary); font-style: italic;">
                  (Actif: ${m.risk_version_info.active_version})
                </span>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85em;">
                <!-- V2 à gauche (prioritaire) -->
                <div>
                  <div style="color: var(--text-secondary); margin-bottom: 2px;">
                    ${m.risk_version_info.active_version === 'v2' ? '✓ ' : ''}V2 Risk Score:
                  </div>
                  <div style="font-weight: 600; color: ${m.risk_version_info.active_version === 'v2' ? '#9ece6a' : 'var(--text-primary)'};">
                    ${m.risk_version_info.risk_score_v2 != null ? safeFixed(m.risk_version_info.risk_score_v2, 1) : 'N/A'}/100
                  </div>
                  <div style="font-size: 0.75em; color: var(--text-tertiary); margin-top: 2px;">
                    Sharpe: ${m.risk_version_info.sharpe_v2 != null ? safeFixed(m.risk_version_info.sharpe_v2, 2) : 'N/A'}
                  </div>
                </div>
                <!-- Legacy à droite (comparaison) -->
                <div style="opacity: ${m.risk_version_info.active_version === 'v2' ? 0.7 : 1};">
                  <div style="color: var(--text-secondary); margin-bottom: 2px;">
                    ${m.risk_version_info.active_version === 'legacy' ? '✓ ' : ''}Legacy Risk Score:
                  </div>
                  <div style="font-weight: 600; color: ${m.risk_version_info.active_version === 'legacy' ? '#9ece6a' : 'var(--text-secondary)'};">
                    ${m.risk_version_info.risk_score_legacy != null ? safeFixed(m.risk_version_info.risk_score_legacy, 1) : 'N/A'}/100
                  </div>
                  <div style="font-size: 0.75em; color: var(--text-tertiary); margin-top: 2px;">
                    Sharpe: ${m.risk_version_info.sharpe_legacy != null ? safeFixed(m.risk_version_info.sharpe_legacy, 2) : 'N/A'}
                  </div>
                </div>
              </div>
              <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(158, 206, 106, 0.2);">
                <div style="font-size: 0.75em; color: var(--text-tertiary); font-style: italic;">
                  ℹ️ ${m.risk_version_info.active_version === 'v2' ? 'V2 actif' : 'Legacy actif'}: V2 utilise Dual-Window Blend pour meilleure stabilité
                </div>
              </div>
            </div>
            ` : ''}

            <!-- Dual Window Badges -->
            ${m.dual_window?.enabled ? `
            <div style="margin: 8px 0; padding: 8px; background: rgba(122, 162, 247, 0.1); border-radius: 6px; border-left: 3px solid var(--brand-primary);">
              ${m.dual_window.long_term?.available ? `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <span style="font-size: 0.85em; color: var(--text-secondary); cursor: help;" title="Fenêtre Long-Term : Calcule le Risk Score sur ${m.dual_window.long_term.window_days} jours d'historique en excluant les assets récents. Couvre ${(m.dual_window.long_term.coverage_pct * 100).toFixed(0)}% de la valeur du portfolio avec ${m.dual_window.long_term.asset_count} assets ayant un historique suffisant. Métriques plus stables et fiables que l'intersection complète.">
                    📈 Long-Term (${m.dual_window.long_term.window_days}d, ${m.dual_window.long_term.asset_count} assets, ${(m.dual_window.long_term.coverage_pct * 100).toFixed(0)}%) <span style="color: var(--brand-primary); opacity: 0.6;">ℹ️</span>
                  </span>
                  <span style="font-size: 0.85em; font-weight: 600; color: var(--brand-primary);">
                    Sharpe: ${safeFixed(m.dual_window.long_term.metrics?.sharpe_ratio, 2)}
                  </span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-size: 0.85em; color: var(--text-secondary); cursor: help;" title="Fenêtre Full Intersection : Période commune minimale incluant TOUS les assets (${m.dual_window.full_intersection.asset_count} assets). Sur ${m.dual_window.full_intersection.window_days} jours seulement car les assets récents limitent l'historique. Métriques peuvent être instables si fenêtre courte. Utilisé pour comparaison et détection de divergences.">
                    🔍 Full Intersection (${m.dual_window.full_intersection.window_days}d, ${m.dual_window.full_intersection.asset_count} assets) <span style="color: var(--text-secondary); opacity: 0.6;">ℹ️</span>
                  </span>
                  <span style="font-size: 0.85em; color: ${Math.abs(m.dual_window.full_intersection.metrics?.sharpe_ratio - m.dual_window.long_term.metrics?.sharpe_ratio) > 0.5 ? 'var(--theme-error)' : 'var(--text-secondary)'};">
                    Sharpe: ${safeFixed(m.dual_window.full_intersection.metrics?.sharpe_ratio, 2)}
                  </span>
                </div>
                ${m.dual_window.exclusions?.excluded_pct > 0.2 ? `
                <div style="margin-top: 6px; padding: 4px 8px; background: rgba(247, 118, 142, 0.15); border-radius: 4px; cursor: help;" title="Assets exclus de la fenêtre Long-Term car historique < ${m.dual_window.long_term.window_days}j : ${m.dual_window.exclusions.excluded_assets.map(a => a.symbol).join(', ')}. Représentent ${(m.dual_window.exclusions.excluded_pct * 100).toFixed(1)}% de la valeur totale. Le Risk Score est calculé uniquement sur les ${m.dual_window.long_term.asset_count} assets avec historique suffisant pour plus de stabilité.">
                  <span style="font-size: 0.8em; color: var(--theme-error);">
                    ⚠️ ${m.dual_window.exclusions.excluded_assets.length} assets exclus (${(m.dual_window.exclusions.excluded_pct * 100).toFixed(0)}% valeur) - historique court <span style="opacity: 0.6;">ℹ️</span>
                  </span>
                </div>
                ` : ''}
                <div style="margin-top: 6px; font-size: 0.75em; color: var(--text-tertiary); font-style: italic;">
                  ✓ Score autoritaire basé sur Long-Term (stable)
                </div>
              ` : `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-size: 0.85em; color: var(--theme-warning);">
                    ⚠️ Full Intersection only (${m.dual_window.full_intersection.window_days}d, ${m.dual_window.full_intersection.asset_count} assets)
                  </span>
                  <span style="font-size: 0.85em; color: var(--text-secondary);">
                    Sharpe: ${safeFixed(m.dual_window.full_intersection.metrics?.sharpe_ratio, 2)}
                  </span>
                </div>
                <div style="margin-top: 6px; padding: 4px 8px; background: rgba(255, 158, 100, 0.15); border-radius: 4px;">
                  <span style="font-size: 0.8em; color: var(--theme-warning);">
                    ⚠️ Cohorte long-term indisponible - métriques sur fenêtre courte (${m.dual_window.exclusions?.reason || 'unknown'})
                  </span>
                </div>
              `}
            </div>
            ` : ''}

            <!-- Structural Score - Comparaison -->
            ${m.risk_version_info ? `
            <div style="margin: 8px 0; padding: 8px; background: rgba(187, 154, 247, 0.1); border-radius: 6px; border-left: 3px solid #bb9af7;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 0.8em; font-weight: 600; color: #bb9af7;">
                  🏗️ Structural Score - Comparaison
                </span>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85em;">
                <div>
                  <div style="color: var(--text-secondary); margin-bottom: 2px;">Integrated (Legacy):</div>
                  <div style="font-weight: 600; color: var(--text-primary);" title="Structure + Performance (VaR, CVaR, DD, Vol)">
                    ${m.risk_version_info.integrated_structural_legacy != null ? safeFixed(m.risk_version_info.integrated_structural_legacy, 1) : 'N/A'}/100
                  </div>
                  <div style="font-size: 0.7em; color: var(--text-tertiary); margin-top: 2px;">
                    (structure + performance)
                  </div>
                </div>
                <div>
                  <div style="color: var(--text-secondary); margin-bottom: 2px;">Portfolio Structure (V2):</div>
                  <div style="font-weight: 600; color: #bb9af7;" title="HHI, Memecoins, GRI, Diversification uniquement">
                    ${m.risk_version_info.portfolio_structure_score != null ? safeFixed(m.risk_version_info.portfolio_structure_score, 1) : 'N/A'}/100
                  </div>
                  <div style="font-size: 0.7em; color: var(--text-tertiary); margin-top: 2px;">
                    (structure pure)
                  </div>
                </div>
              </div>
              <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(187, 154, 247, 0.2);">
                <div style="font-size: 0.75em; color: var(--text-tertiary); font-style: italic;">
                  ℹ️ V2 = pure structure (HHI, memes, GRI, div) | Legacy = hybrid (+ VaR, CVaR, DD, Vol)
                </div>
              </div>
            </div>
            ` : m.risk_score_structural != null ? `
            <div class="metric-row" style="opacity: 0.8;">
              <span class="metric-label" title="Risk Score Structural : Intègre exposition par groupe (GRI), concentration et structure du portfolio">Structural <span style="font-size: 0.7em; color: var(--theme-accent);">struct</span></span>
              <span class="metric-value" style="font-size: 0.9em;">${safeFixed(m.risk_score_structural, 1)}/100</span>
            </div>
            ` : ''}

            <!-- Structure Modulation V2 (Oct 2025) -->
            ${(() => {
              // Lire structure_modulation depuis unified state (si disponible)
              try {
                const unifiedState = window.store?.snapshot?.();
                const structureMod = unifiedState?.structure_modulation;

                // Afficher seulement si activé ET disponible
                if (!structureMod?.enabled || structureMod.structure_score == null) {
                  return '';
                }

                const structureScore = structureMod.structure_score;
                const deltaStables = structureMod.delta_stables || 0;
                const deltaCap = structureMod.delta_cap || 0;
                const stablesAfter = structureMod.stables_after || 0;
                const capAfter = structureMod.cap_after || 0;

                // Couleur selon impact
                let color = '#7aa2f7'; // Bleu neutre
                if (deltaStables > 0) color = '#f7768e'; // Rouge (plus de stables = prudence)
                else if (deltaStables < 0) color = '#9ece6a'; // Vert (moins de stables = opportunité)

                return `
                <div style="margin: 8px 0; padding: 8px; background: rgba(122, 162, 247, 0.1); border-radius: 6px; border-left: 3px solid ${color};">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 0.8em; font-weight: 600; color: ${color};">
                      🏗️ Structure Modulation V2
                    </span>
                    <span style="font-size: 0.7em; color: var(--text-tertiary); font-style: italic;">
                      active
                    </span>
                  </div>
                  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85em;">
                    <div>
                      <div style="color: var(--text-secondary); margin-bottom: 2px;">Structure Score:</div>
                      <div style="font-weight: 600; color: var(--text-primary);">
                        ${safeFixed(structureScore, 1)}/100
                      </div>
                    </div>
                    <div>
                      <div style="color: var(--text-secondary); margin-bottom: 2px;">Δ Stables:</div>
                      <div style="font-weight: 600; color: ${deltaStables > 0 ? '#f7768e' : deltaStables < 0 ? '#9ece6a' : 'var(--text-primary)'};">
                        ${deltaStables > 0 ? '+' : ''}${deltaStables} pts
                      </div>
                      <div style="font-size: 0.7em; color: var(--text-tertiary); margin-top: 2px;">
                        → ${stablesAfter}% stables
                      </div>
                    </div>
                  </div>
                  <div style="margin-top: 6px; font-size: 0.8em;">
                    <div style="color: var(--text-secondary); margin-bottom: 2px;">Cap effectif:</div>
                    <div style="font-weight: 600; color: var(--text-primary);">
                      ${typeof capAfter === 'number' ? safeFixed(capAfter, 1) : 'N/A'}%
                      ${deltaCap !== 0 ? `<span style="color: ${deltaCap > 0 ? '#9ece6a' : '#f7768e'}; font-size: 0.85em;"> (${deltaCap > 0 ? '+' : ''}${safeFixed(deltaCap, 1)})</span>` : ''}
                    </div>
                  </div>
                  <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(122, 162, 247, 0.2);">
                    <div style="font-size: 0.75em; color: var(--text-tertiary); font-style: italic;">
                      ℹ️ Modulation basée sur la qualité structurelle (HHI, memes, GRI, diversification)
                    </div>
                  </div>
                </div>
                `;
              } catch (error) {
                return '';
              }
            })()}

            <!-- Risk Level -->
            <div class="metric-row">
              <span class="metric-label">Risk Level</span>
              <span class="risk-level risk-${scoreToRiskLevel(m.risk_score)}">${scoreToRiskLevel(m.risk_score).replace('-', ' ').toUpperCase()}</span>
            </div>

            <div class="metric-benchmark">
              📊 <strong>Benchmarks:</strong> Très robuste (≥80), Robuste (≥65), Modéré (≥50), Fragile (≥35)
            </div>
          </div>

          <!-- Loss & Drawdown Analysis (Fusion VaR + Drawdown) -->
          <div class="risk-card">
            <h3>📉 Loss & Drawdown Analysis <span style="font-size:.8rem; color: var(--theme-text); opacity:.7; font-weight:500; margin-left:.5rem;"><br>VaR 30j • CVaR 60j • DD 180j</span></h3>

            <!-- Short-term Loss Risk (VaR) -->
            <div class="risk-subsection">
              <div class="subsection-title">Short-term Loss (1 day)</div>

              <div class="metric-row">
                <span class="metric-label">VaR 95%</span>
                <span class="metric-value hinted" data-key="var95_1d" data-value="${m.var_95_1d}" style="color: ${getMetricHealth('var_95_1d', m.var_95_1d).color}">
                  ${formatPercent(m.var_95_1d)}
                </span>
              </div>
              <div class="metric-interpretation">
                💡 ${getMetricHealth('var_95_1d', m.var_95_1d).interpretation}
              </div>

              <div class="metric-row">
                <span class="metric-label">VaR 99% (extrême)</span>
                <span class="metric-value hinted" data-key="var99_1d" data-value="${m.var_99_1d}" style="color: ${getMetricHealth('var_99_1d', m.var_99_1d).color}">
                  ${formatPercent(m.var_99_1d)}
                </span>
              </div>
            </div>

            <!-- Tail Risk (CVaR) - Collapsible -->
            <details class="risk-details" style="margin: var(--space-md) 0;">
              <summary style="cursor: pointer; color: var(--theme-text-muted); font-size: 0.85rem; padding: var(--space-xs) 0;">
                <span style="color: var(--brand-primary);">▸</span> Tail Risk (CVaR)
              </summary>
              <div style="margin-top: var(--space-sm); padding-left: var(--space-md);">
                <div class="metric-row" style="font-size: 0.9rem;">
                  <span class="metric-label">CVaR 95%</span>
                  <span class="metric-value hinted" data-key="cvar95_1d" data-value="${m.cvar_95_1d}">${formatPercent(m.cvar_95_1d)}</span>
                </div>
                <div class="metric-row" style="font-size: 0.9rem;">
                  <span class="metric-label">CVaR 99%</span>
                  <span class="metric-value hinted" data-key="cvar99_1d" data-value="${m.cvar_99_1d}">${formatPercent(m.cvar_99_1d)}</span>
                </div>
                <div style="font-size: 0.75rem; color: var(--theme-text-muted); font-style: italic; margin-top: var(--space-xs);">
                  ℹ️ Perte moyenne au-delà du VaR
                </div>
              </div>
            </details>

            <!-- Historical Drawdown -->
            <div class="risk-subsection">
              <div class="subsection-title">Historical Drawdown</div>

              <div class="metric-row">
                <span class="metric-label">Max Drawdown</span>
                <span class="metric-value hinted" data-key="max_drawdown" data-value="${m.max_drawdown}" style="color: ${getMetricHealth('max_drawdown', m.max_drawdown).color}">
                  ${formatPercent(m.max_drawdown)}
                </span>
              </div>
              <div class="metric-interpretation">
                💡 ${getMetricHealth('max_drawdown', m.max_drawdown).interpretation}
              </div>

              <div class="metric-row">
                <span class="metric-label">Current Drawdown</span>
                <span class="metric-value hinted" data-key="current_drawdown" data-value="${m.current_drawdown}">${formatPercent(m.current_drawdown)}</span>
              </div>
            </div>

            <div class="metric-benchmark">
              📊 <strong>VaR:</strong> Conservateur: -4%, Typique: -7%, Agressif: -12% • <strong>Drawdown:</strong> Bon: -30%, Typique: -50%, Extrême: -70%+
            </div>
          </div>

          <!-- Performance -->
          <div class="risk-card">
            <h3>📈 Risk-Adjusted Performance <span style="font-size:.8rem; color: var(--theme-text); opacity:.7; font-weight:500; margin-left:.5rem;"><br>Vol 45j • Sharpe 90j • Sortino 120j • Calmar 365j</span></h3>
            <div class="metric-row">
              <span class="metric-label">Volatility (Annual)</span>
              <span class="metric-value hinted" data-key="volatility_ann" data-value="${m.volatility_annualized}" style="color: ${getMetricHealth('volatility_annualized', m.volatility_annualized).color}">
                ${formatPercent(m.volatility_annualized)}
              </span>
            </div>
            <div class="metric-interpretation">
              💡 ${getMetricHealth('volatility_annualized', m.volatility_annualized).interpretation}
            </div>
            <div class="metric-row">
              <span class="metric-label">Sharpe Ratio</span>
              <span class="metric-value hinted" data-key="sharpe" data-value="${m.sharpe_ratio}" style="color: ${getMetricHealth('sharpe_ratio', m.sharpe_ratio).color}">
                ${safeFixed(m.sharpe_ratio)}
              </span>
            </div>
            <div class="metric-interpretation">
              💡 ${getMetricHealth('sharpe_ratio', m.sharpe_ratio).interpretation}
            </div>
            <div class="metric-row">
              <span class="metric-label">Sortino Ratio</span>
              <span class="metric-value hinted" data-key="sortino" data-value="${m.sortino_ratio}" style="color: ${getMetricHealth('sortino_ratio', m.sortino_ratio).color}">
                ${safeFixed(m.sortino_ratio)}
              </span>
            </div>
            <div class="metric-interpretation">
              💡 ${getMetricHealth('sortino_ratio', m.sortino_ratio).interpretation}
            </div>
            <div class="metric-row">
              <span class="metric-label">Calmar Ratio</span>
              <span class="metric-value">${safeFixed(m.calmar_ratio)}</span>
            </div>
            <div class="metric-benchmark">
              📊 <strong>Benchmarks crypto:</strong> Excellent: >1.5, Bon: >1.0, Acceptable: >0.5 (Sharpe)
            </div>
          </div>

          <!-- Diversification -->
          <div class="risk-card">
            <h3>🔗 Diversification Analysis <span style="font-size:.8rem; color: var(--theme-text); opacity:.7; font-weight:500; margin-left:.5rem;">corr 90j</span></h3>
            <div class="metric-row">
              <span class="metric-label">Diversification Ratio</span>
              <span class="metric-value hinted" data-key="diversification_ratio" data-value="${c.diversification_ratio}" style="color: ${getMetricHealth('diversification_ratio', c.diversification_ratio).color}">
                ${safeFixed(c.diversification_ratio)}
              </span>
            </div>
            <div class="metric-interpretation">
              💡 ${getMetricHealth('diversification_ratio', c.diversification_ratio).interpretation}
            </div>
            <div class="metric-row">
              <span class="metric-label">Effective Assets</span>
              <span class="metric-value hinted" data-key="effective_assets" data-value="${c.effective_assets}" style="color: ${getMetricHealth('effective_assets', c.effective_assets).color}">
                ${safeFixed(c.effective_assets, 1)}
              </span>
            </div>
            <div class="metric-interpretation">
              💡 ${getMetricHealth('effective_assets', c.effective_assets).interpretation}
            </div>
            <div class="metric-benchmark">
              📊 <strong>Diversification:</strong> Excellent: >0.7, Limité: 0.4-0.7, Faible: <0.4
            </div>

            ${c.top_correlations && c.top_correlations.length ? `
              <h4>Top Asset Correlations:</h4>
              ${c.top_correlations.slice(0, 3).map(t => `
                <div class="metric-row">
                  <span class="metric-label">${t.asset1} - ${t.asset2}:</span>
                  <span class="metric-value ${(Math.abs(t.correlation || 0) > 0.7) ? 'text-warning' : 'text-success'}">${((t.correlation || 0) * 100).toFixed(1)}%</span>
                </div>
              `).join('')}
            ` : ``}
          </div>
        </div>

        <!-- Recommendations moved to Top Summary -->

        <!-- Alerts moved to Top Summary -->
      `;

      // Après rendu : brancher les info-bulles et verdicts
      decorateRiskTooltips();
    }

    // ====== Bitcoin Cycle Chart Functions ======

    // Bitcoin halving historical data
    const BITCOIN_HALVINGS = [
      { date: '2012-11-28', block: 210000, reward_before: 50, reward_after: 25 },
      { date: '2016-07-09', block: 420000, reward_before: 25, reward_after: 12.5 },
      { date: '2020-05-11', block: 630000, reward_before: 12.5, reward_after: 6.25 },
      { date: '2024-04-20', block: 840000, reward_before: 6.25, reward_after: 3.125 },
      { date: '2028-04-20', block: 1050000, reward_before: 3.125, reward_after: 1.5625, estimated: true }
    ];

    // Expose for modules
    window.BITCOIN_HALVINGS = BITCOIN_HALVINGS;

    // ====== Tab-specific rendering functions ======
    // All tab-specific rendering functions have been moved to dedicated modules:
    // - Cycles tab: modules/risk-cycles-tab.js (Bitcoin chart, on-chain indicators, cycle analysis)
    // - Targets tab: modules/risk-targets-tab.js (allocation tables, action plans, decision history)
    // These modules are imported at the top of the file and called via switchTab()

    function renderError(message) {
      document.getElementById('risk-dashboard-content').innerHTML = `
        <div class="error">
          <h3>❌ Error Loading Dashboard</h3>
          <p>${message}</p>
          <button class="refresh-btn" onclick="refreshDashboard()">Try Again</button>
        </div>
      `;
    }

    function renderBackendUnavailable(message) {
      document.getElementById('risk-dashboard-content').innerHTML = `
        <div style="text-align: center; padding: 3rem; background: var(--warning-bg); border: 1px solid var(--warning); border-radius: var(--radius-lg); color: var(--theme-text);">
          <div style="font-size: 3rem; margin-bottom: 1rem;">⚠️</div>
          <h3 style="color: var(--warning); margin-bottom: 1rem;">Backend de Risque Indisponible</h3>
          <p style="margin-bottom: 1.5rem; color: var(--theme-text-muted);">${message}</p>
          
          <div style="background: var(--theme-bg); padding: 1.5rem; border-radius: var(--radius-md); margin: 1.5rem 0; text-align: left;">
            <h4 style="color: var(--theme-text); margin-bottom: 1rem;">📋 Pour afficher les données réelles de risque :</h4>
            <ol style="color: var(--theme-text-muted); line-height: 1.6;">
              <li>Démarrer le serveur backend Python : <code style="background: var(--theme-surface); padding: 0.2rem 0.4rem; border-radius: 3px;">python main.py</code></li>
              <li>Initialiser le cache d'historique : <code style="background: var(--theme-surface); padding: 0.2rem 0.4rem; border-radius: 3px;">python scripts/init_price_history.py</code></li>
              <li>Vérifier que l'API répond sur <a href="#" onclick="window.open(window.globalConfig.get('api_base_url') + '/api/risk/dashboard'); return false;" target="_blank" style="color: var(--brand-primary);">l'API configurée</a></li>
            </ol>
          </div>

          <div style="margin-top: 2rem;">
            <button class="refresh-btn" onclick="refreshDashboard()">🔄 Réessayer</button>
            <button class="refresh-btn" onclick="testEndpoint()" style="background: var(--info); margin-left: 0.5rem;">🧪 Tester l'API</button>
          </div>
          
          <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--theme-border); color: var(--theme-text-muted); font-size: 0.85rem;">
            💡 <strong>Note :</strong> Ce dashboard utilise maintenant exclusivement des données réelles calculées par le backend Python. 
            Les données simulées ont été supprimées pour garantir l'authenticité des métriques de risque.
          </div>
        </div>
      `;
    }

    function renderApiError(message) {
      document.getElementById('risk-dashboard-content').innerHTML = `
        <div style="text-align: center; padding: 3rem; background: var(--danger-bg); border: 1px solid var(--danger); border-radius: var(--radius-lg);">
          <div style="font-size: 3rem; margin-bottom: 1rem;">🚨</div>
          <h3 style="color: var(--danger); margin-bottom: 1rem;">Erreur API Backend</h3>
          <p style="margin-bottom: 1.5rem; color: var(--theme-text-muted);">${message}</p>
          
          <div style="background: var(--theme-bg); padding: 1.5rem; border-radius: var(--radius-md); margin: 1.5rem 0;">
            <h4 style="color: var(--theme-text); margin-bottom: 1rem;">🔧 Suggestions de dépannage :</h4>
            <ul style="color: var(--theme-text-muted); text-align: left; line-height: 1.6;">
              <li>Vérifiez que le portfolio CoinTracking contient des données valides</li>
              <li>Assurez-vous que les sources de prix configurées sont accessibles</li>
              <li>Consultez les logs du backend pour plus de détails</li>
            </ul>
          </div>

          <button class="refresh-btn" onclick="refreshDashboard()">🔄 Réessayer</button>
        </div>
      `;
    }

    function updateTimestamp(ts, calcTime) {
      const d = new Date(ts);
      const formattedDate = d.toLocaleString('fr-FR', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit'
      });
      document.getElementById('last-update').textContent = `Updated ${formattedDate}`;
    }

    // Test endpoint (identique à ta version)
    async function testEndpoint() {
      try {
        const url = window.globalConfig.getApiUrl('/api/risk/dashboard');
        const r = await fetch(url);
        const t = await r.text();
        try { JSON.parse(t); alert('API Response received. Check console for details.'); }
        catch { alert('API returned non-JSON response: ' + t.substring(0, 200)); }
      } catch (e) { alert('API test failed: ' + e.message); }
    }

    // ===== Décoration des tooltips après rendu =====
    function decorateRiskTooltips() {
      // === Attache dynamique pour les métriques ===
      document.querySelectorAll('.hinted[data-key]').forEach(el => {
        const key = el.getAttribute('data-key');

        // === Tooltips GRI personnalisés ===
        if (key === 'gri_index') {
          el.addEventListener('mouseenter', (e) => {
            const title = 'Group Risk Index (GRI)';
            const body = `Moyenne pondérée des risques par groupe sur échelle 0-10.

Calcul : GRI = Σ (poids × score)

Chaque score groupe intègre :
• Structure (40%) : contrepartie, gouvernance
• Volatilité (30%) : σ historique
• Corrélation (20%) : redondance portefeuille
• Liquidité (10%) : profondeur, custody`;
            showTip(title, body, e.clientX, e.clientY);
          });
          el.addEventListener('mousemove', (e) => moveTip(e.clientX, e.clientY));
          el.addEventListener('mouseleave', hideTip);
          el.classList.add('hinted');
          return;
        }

        if (key === 'gri_level') {
          el.addEventListener('mouseenter', (e) => {
            const title = 'Risk Level';
            const body = `Catégorisation du risque global :

• LOW (< 3.0) : Portefeuille défensif
• MEDIUM (3.0-6.0) : Risque modéré
• HIGH (≥ 6.0) : Risque accru

Basé sur le GRI calculé sur l'ensemble du portefeuille.`;
            showTip(title, body, e.clientX, e.clientY);
          });
          el.addEventListener('mousemove', (e) => moveTip(e.clientX, e.clientY));
          el.addEventListener('mouseleave', hideTip);
          el.classList.add('hinted');
          return;
        }

        if (key === 'groups_count') {
          el.addEventListener('mouseenter', (e) => {
            const title = 'Groups Count';
            const body = `Nombre de catégories d'actifs détectées :
BTC, ETH, L1/L0, Stablecoins, Memecoins, etc.

Reflète la diversification structurelle du portefeuille.`;
            showTip(title, body, e.clientX, e.clientY);
          });
          el.addEventListener('mousemove', (e) => moveTip(e.clientX, e.clientY));
          el.addEventListener('mouseleave', hideTip);
          el.classList.add('hinted');
          return;
        }

        if (key === 'gri_groups_header') {
          el.addEventListener('mouseenter', (e) => {
            const title = 'Exposition & Risque par Groupe';
            const body = `Chaque groupe affiche :
• % du portefeuille (exposition)
• Score 0-10 (risque composite)

Score = 40% structural + 30% vola + 20% correl + 10% liquid`;
            showTip(title, body, e.clientX, e.clientY);
          });
          el.addEventListener('mousemove', (e) => moveTip(e.clientX, e.clientY));
          el.addEventListener('mouseleave', hideTip);
          el.classList.add('hinted');
          return;
        }

        if (key === 'gri_interpretation') {
          el.addEventListener('mouseenter', (e) => {
            const title = 'Interprétation du niveau de risque';
            const body = `Ce niveau est déduit du Group Risk Index
et des simulations Monte Carlo.

Il ne représente pas un conseil d'investissement,
mais une estimation statistique du risque global.`;
            showTip(title, body, e.clientX, e.clientY);
          });
          el.addEventListener('mousemove', (e) => moveTip(e.clientX, e.clientY));
          el.addEventListener('mouseleave', hideTip);
          el.classList.add('hinted');
          return;
        }

        // === Tooltips pour les groupes individuels ===
        if (key.startsWith('group:')) {
          const groupName = key.replace('group:', '');
          const groupTooltips = {
            'BTC': 'Actif de référence du marché.\nFaible volatilité relative, forte liquidité,\ncorrélation modérée avec le marché.',
            'ETH': 'Actif à risque modéré.\nVolatilité supérieure à BTC mais structure solide.',
            'L1/L0 majors': 'Coins d\'infrastructure (SOL, AVAX, etc.).\nPlus volatils, risque structurel moyen à élevé.',
            'L2/Scaling': 'Solutions de scalabilité (Arbitrum, Optimism, Polygon).\nRisque modéré, corrélés à ETH.',
            'DeFi': 'Protocoles de finance décentralisée.\nVolatilité élevée, risque smart contract.',
            'AI/Data': 'Projets IA et data (FET, OCEAN, etc.).\nSecteur émergent, volatilité élevée.',
            'SOL': 'Solana : blockchain haute performance.\nVolatilité importante, corrélation moyenne.',
            'Gaming/NFT': 'Tokens gaming et NFTs.\nForte volatilité, corrélation au sentiment.',
            'Memecoins': 'Tokens spéculatifs (DOGE, SHIB, PEPE).\nVolatilité extrême, risque très élevé.',
            'Stablecoins': 'Coins adossés au dollar (USDT, USDC, DAI).\nRisque faible mais non nul :\n• Contrepartie émetteur\n• Régulation\n• Dépeg potentiel',
            'Others': 'Coins secondaires.\nFaible liquidité, forte corrélation,\nrisque élevé.'
          };

          el.addEventListener('mouseenter', (e) => {
            const riskLevel = el.getAttribute('data-risk-level') || '5';
            const title = `${groupName} — ${riskLevel}/10`;
            const body = groupTooltips[groupName] || 'Groupe d\'actifs non catégorisé.';
            showTip(title, body, e.clientX, e.clientY);
          });
          el.addEventListener('mousemove', (e) => moveTip(e.clientX, e.clientY));
          el.addEventListener('mouseleave', hideTip);
          el.classList.add('hinted');
          return;
        }

        // === Tooltips Monte Carlo ===
        if (key === 'mc_simulations') {
          el.addEventListener('mouseenter', (e) => {
            const title = 'Simulations';
            const body = `Nombre d'itérations Monte Carlo effectuées.

Plus il y en a, plus la distribution est fiable.
10 000 simulations = précision statistique standard.`;
            showTip(title, body, e.clientX, e.clientY);
          });
          el.addEventListener('mousemove', (e) => moveTip(e.clientX, e.clientY));
          el.addEventListener('mouseleave', hideTip);
          el.classList.add('hinted');
          return;
        }

        if (key === 'mc_worst_case') {
          el.addEventListener('mouseenter', (e) => {
            const title = 'Pire scénario (Drawdown maximal simulé)';
            const body = `La plus forte perte observée parmi les 10 000 simulations.

Représente un événement de queue extrême
(< 0.01% de probabilité).`;
            showTip(title, body, e.clientX, e.clientY);
          });
          el.addEventListener('mousemove', (e) => moveTip(e.clientX, e.clientY));
          el.addEventListener('mouseleave', hideTip);
          el.classList.add('hinted');
          return;
        }

        if (key === 'mc_loss_prob') {
          el.addEventListener('mouseenter', (e) => {
            const title = 'Probabilité perte > 20%';
            const body = `Probabilité qu'une perte supérieure à 20%
survienne sur la période simulée.

Basée sur la fréquence observée
dans les 10 000 scénarios.`;
            showTip(title, body, e.clientX, e.clientY);
          });
          el.addEventListener('mousemove', (e) => moveTip(e.clientX, e.clientY));
          el.addEventListener('mouseleave', hideTip);
          el.classList.add('hinted');
          return;
        }

        // === Métriques de risque standard ===
        // attache une bulle "vivante" qui lit la valeur *au moment* du survol
        el.addEventListener('mouseenter', (e) => {
          // 1) essaie data-value
          let raw = el.getAttribute('data-value');

          // 2) fallback: parse le texte visible (ex: "1.23%" -> 0.0123)
          if (!raw || raw === '0') {
            const txt = (el.textContent || '').trim();
            if (txt.endsWith('%')) {
              const n = parseFloat(txt.replace('%', '').replace(',', '.'));
              raw = isFinite(n) ? String(n / 100) : '';
            } else {
              const n = parseFloat(txt.replace(',', '.'));
              raw = isFinite(n) ? String(n) : '';
            }
          }

          const val = Number(String(raw || '').replace(',', '.'));
          const rating = rate(key, isNaN(val) ? null : val);

          const title = rating.label || key;
          const fmt = (key === 'sharpe' || key === 'sortino') ? num : pct;
          let body = `Valeur actuelle : ${isNaN(val) ? 'N/A' : fmt(val)}\nLecture : ${rating.verdict}`;
          if (key === 'diversification_ratio') {
            body += `\nNote: DR≈1 = neutre; >1 suggère corrélations négatives; <1 corrélations positives.\nSeuils: bon ≥0.7, limité 0.4–0.7, faible <0.4.`;
          }

          showTip(title, body, e.clientX, e.clientY);
        });

        el.addEventListener('mousemove', (e) => moveTip(e.clientX, e.clientY));
        el.addEventListener('mouseleave', hideTip);
        el.classList.add('hinted');
      });
    }

    // Expose globally for Phase 3A components
    window.decorateRiskTooltips = decorateRiskTooltips;

    // ====== Initialization & Store Connection ======

    // Subscribe to store changes for content updates
    store.subscribe((state) => {
      // Auto-update active tab content when data changes
      const activeTab = state.ui?.activeTab;
      if (activeTab === 'cycles' && state.ccs?.score && state.cycle?.months) {
        renderCyclesContent();
      }
      if (activeTab === 'targets') {
        renderTargetsContent().catch(err => debugLogger.error('Failed to render targets on store change:', err));
      }
    });

    // ====== Global Functions for UI Interaction ======
    window.refreshDashboard = refreshDashboard;
    window.testEndpoint = testEndpoint;
    // Expose options menu helpers
    window.toggleOptionsMenu = toggleOptionsMenu;
    window.closeOptionsMenu = closeOptionsMenu;
    // Expose cache functions for tab modules
    window.getCachedData = getCachedData;
    window.setCachedData = setCachedData;
    // Expose badge update function for tab modules
    window.updateRiskDashboardBadges = updateRiskDashboardBadges;
    // Expose score loading function for tab modules
    window.loadScoresFromStore = loadScoresFromStore;
    // Expose composite score calculator for on-chain indicators
    window.calculateCompositeScoreV2 = calculateCompositeScoreV2;

    // ===== PHASE 2A: TOAST NOTIFICATION SYSTEM =====
    let toastIdCounter = 0;

    function showToast(message, type = 'info', options = {}) {
      const {
        duration = type === 'error' ? 8000 : 5000,
        actions = [],
        title = null,
        alertData = null
      } = options;

      const toastId = `toast-${++toastIdCounter}`;
      const toastContainer = document.getElementById('toast-container');

      if (!toastContainer) {
        debugLogger.error('Toast container not found');
        return;
      }

      // Map type to severity for styling
      let severityClass = 'toast-s1';
      let severityText = 'INFO';
      let severityIcon = '●';

      if (type === 'error' || type === 'critical' || type === 's3') {
        severityClass = 'toast-s3';
        severityText = 'CRITICAL';
        severityIcon = '⚠';
      } else if (type === 'warning' || type === 's2') {
        severityClass = 'toast-s2';
        severityText = 'WARNING';
        severityIcon = '⚠';
      }

      const toast = document.createElement('div');
      toast.id = toastId;
      toast.className = `toast ${severityClass}`;

      let actionsHtml = '';
      if (actions.length > 0) {
        actionsHtml = `
          <div class="toast-actions">
            ${actions.map(action => `
              <button class="toast-action ${action.secondary ? 'toast-action-secondary' : ''}" 
                      onclick="${action.onclick}">${action.label}</button>
            `).join('')}
          </div>`;
      }

      toast.innerHTML = `
        <div class="toast-header">
          <div class="toast-severity toast-severity-${type === 'error' || type === 's3' ? 's3' : type === 'warning' || type === 's2' ? 's2' : 's1'}">
            <div class="toast-severity-icon"></div>
            ${severityText}
          </div>
          <button class="toast-close" onclick="hideToast('${toastId}')">&times;</button>
        </div>
        <div class="toast-body">
          ${title ? `<div class="toast-title">${title}</div>` : ''}
          <div class="toast-description">${message}</div>
          ${actionsHtml}
        </div>
      `;

      toastContainer.appendChild(toast);

      // Animate in
      setTimeout(() => toast.classList.add('show'), 10);

      // Auto-hide (except for critical alerts)
      if (type !== 'error' && type !== 'critical' && type !== 's3') {
        setTimeout(() => hideToast(toastId), duration);
      }

      return toastId;
    }

    // Track dismissed toasts to prevent re-showing
    const dismissedToasts = new Set();

    // Load previously dismissed alerts from localStorage
    function loadDismissedAlerts() {
      try {
        const stored = localStorage.getItem('dismissedAlerts');
        if (stored) {
          const alertIds = JSON.parse(stored);
          alertIds.forEach(id => dismissedToasts.add(id));
          debugLogger.debug('Loaded dismissed alerts:', alertIds.length);
        }
      } catch (e) {
        debugLogger.warn('Failed to load dismissed alerts:', e);
      }
    }

    // Check if alert should be shown (not dismissed)
    function shouldShowAlert(alertId) {
      return !dismissedToasts.has(alertId);
    }

    // DEFINE GLOBALLY
    window.hideToast = function (toastId) {
      debugLogger.debug('Hiding toast:', toastId);
      const toast = document.getElementById(toastId);
      if (!toast) {
        debugLogger.warn('Toast not found:', toastId);
        return;
      }

      // Extract alert ID from toast ID (format: toast-{alertId})
      const alertId = toastId.replace('toast-', '');
      dismissedToasts.add(alertId);
      debugLogger.debug('Added to dismissed list:', alertId);
      localStorage.setItem('dismissedAlerts', JSON.stringify([...dismissedToasts]));

      debugLogger.debug('Adding hide class to toast:', toastId);
      toast.classList.add('hide');
      debugLogger.debug('Toast classes after adding hide:', toast.className);

      setTimeout(() => {
        if (toast && toast.parentNode) {
          toast.remove();
          debugLogger.debug('Toast removed:', toastId);
        }
      }, 300);
    };

    // Function to hide all toasts - DEFINE GLOBALLY
    window.hideAllToasts = function () {
      debugLogger.debug('Hiding all toasts...');
      const toastContainer = document.getElementById('toast-container');
      if (!toastContainer) {
        debugLogger.debug('Toast container not found');
        return;
      }

      const toasts = toastContainer.querySelectorAll('.toast');
      debugLogger.debug(`Found ${toasts.length} toasts to hide in container`);

      if (toasts.length === 0) {
        // Try fallback - look for toasts anywhere in document
        const allToasts = document.querySelectorAll('.toast');
        debugLogger.debug(`Fallback: Found ${allToasts.length} toasts in entire document`);
        allToasts.forEach((toast, index) => {
          debugLogger.debug(`Force removing toast ${index}:`, toast.id || 'no-id');
          toast.remove();
        });
      } else {
        // Normal path
        toasts.forEach((toast, index) => {
          debugLogger.debug(`Hiding toast ${index}:`, toast.id || 'no-id');
          toast.classList.add('hide');
          setTimeout(() => {
            if (toast && toast.parentNode) {
              toast.remove();
              debugLogger.debug(`Removed toast ${index}`);
            }
          }, 300);
        });
      }

      // Force clear container if needed
      setTimeout(() => {
        const remainingToasts = toastContainer.querySelectorAll('.toast');
        if (remainingToasts.length > 0) {
          debugLogger.debug(`Force clearing ${remainingToasts.length} remaining toasts`);
          toastContainer.innerHTML = '';
        }
      }, 500);

      debugLogger.debug('All toasts cleared');
    };

    // Show toast for S3 alerts specifically
    function showS3AlertToast(alert) {
      // Check if this alert has already been dismissed
      if (!shouldShowAlert(alert.id)) {
        debugLogger.debug('Skipping already dismissed alert:', alert.id);
        return;
      }

      const title = getAlertTypeDisplayName(alert.alert_type);
      const message = `${alert.data.current_value?.toFixed(2) || 'N/A'} > ${alert.data.adaptive_threshold?.toFixed(2) || 'N/A'}`;

      // Use alert ID for consistent tracking
      const nextToastId = `toast-${alert.id}`;

      const actions = [
        {
          label: 'View Details',
          onclick: `window.openAlertModal('${alert.id}').then(() => hideToast('${nextToastId}'))`
        },
        {
          label: 'Dismiss',
          secondary: true,
          onclick: `hideToast('${nextToastId}')`
        }
      ];

      const toastId = showToast(message, 's3', {
        title: `🚨 ${title}`,
        actions,
        duration: 0, // Don't auto-hide critical alerts
        alertData: alert
      });

      // Update the toast ID to match alert ID for proper tracking
      const toastElement = document.getElementById(toastId);
      if (toastElement) {
        toastElement.id = nextToastId;
      }

      return nextToastId;
    }

    // ===== PHASE 2A: ALERT MODAL SYSTEM =====
    let currentAlert = null;

    async function openAlertModal(alertId) {
      debugLogger.debug('Opening modal for alert:', alertId);

      // Try to find alert in current data first
      let alert = findAlertById(alertId);

      // If not found, fetch from API
      if (!alert) {
        debugLogger.debug('Alert not found in cache, fetching from API...');
        try {
          const alerts = await window.globalConfig.apiRequest('/api/alerts/active');
          if (Array.isArray(alerts)) {
            alert = alerts.find(a => a.id === alertId);
            debugLogger.debug('Found alert in API:', !!alert);
          }
        } catch (error) {
          debugLogger.error('Failed to fetch alert from API:', error);
        }
      }

      if (!alert) {
        debugLogger.error('Alert not found anywhere:', alertId);
        showToast('Alert not found', 'error');
        return;
      }

      currentAlert = alert;
      populateAlertModal(alert);

      const modal = document.getElementById('alert-modal');
      modal.classList.add('show');
      document.body.style.overflow = 'hidden';

      // Close on Escape key
      const handleEscape = (e) => {
        if (e.key === 'Escape') {
          closeAlertModal();
          document.removeEventListener('keydown', handleEscape);
        }
      };
      document.addEventListener('keydown', handleEscape);
    }

    function closeAlertModal() {
      const modal = document.getElementById('alert-modal');
      modal.classList.remove('show');
      document.body.style.overflow = '';
      currentAlert = null;
    }

    function populateAlertModal(alert) {
      // Update header
      document.getElementById('modal-severity-badge').textContent = alert.severity;
      document.getElementById('modal-severity-badge').className = `modal-severity-badge modal-severity-${alert.severity.toLowerCase()}`;
      document.getElementById('modal-alert-type').textContent = getAlertTypeDisplayName(alert.alert_type);

      // Update overview
      document.getElementById('modal-alert-id').textContent = alert.id;
      document.getElementById('modal-created-at').textContent = formatDateTime(alert.created_at);
      document.getElementById('modal-current-value').textContent = alert.data.current_value?.toFixed(4) || 'N/A';
      document.getElementById('modal-threshold').textContent = alert.data.adaptive_threshold?.toFixed(4) || 'N/A';

      // Update signals snapshot
      const signalsContainer = document.getElementById('signals-snapshot');
      signalsContainer.innerHTML = '';

      if (alert.data.signals_snapshot) {
        const signals = alert.data.signals_snapshot;

        // Add key signals
        if (signals.volatility) {
          Object.entries(signals.volatility).forEach(([asset, value]) => {
            addSignalCard(signalsContainer, `Volatility ${asset}`, value, 'number');
          });
        }

        if (signals.regime) {
          Object.entries(signals.regime).forEach(([regime, value]) => {
            addSignalCard(signalsContainer, regime.toUpperCase(), value, 'percentage');
          });
        }

        if (signals.correlation) {
          addSignalCard(signalsContainer, 'Avg Correlation', signals.correlation.avg_correlation, 'percentage');
        }

        if (signals.sentiment) {
          addSignalCard(signalsContainer, 'Fear & Greed', signals.sentiment.fear_greed, 'number');
        }

        addSignalCard(signalsContainer, 'Decision Score', signals.decision_score, 'percentage');
        addSignalCard(signalsContainer, 'Confidence', signals.confidence, 'percentage');
        addSignalCard(signalsContainer, 'Contradiction', signals.contradiction_index, 'percentage');
      }

      // Update suggested action
      if (alert.suggested_action) {
        document.getElementById('action-type').textContent = formatActionType(alert.suggested_action.type);
        document.getElementById('action-details').textContent = formatActionDetails(alert.suggested_action);

        // Show/hide apply button based on action type
        const applyBtn = document.getElementById('apply-btn');
        if (alert.suggested_action.type === 'freeze' || alert.suggested_action.type === 'apply_policy') {
          applyBtn.style.display = 'block';
        } else {
          applyBtn.style.display = 'none';
        }
      }

      // Update button states
      updateModalButtonStates(alert);
    }

    function addSignalCard(container, name, value, type) {
      const card = document.createElement('div');
      card.className = 'signal-card';

      let displayValue = '';
      if (type === 'percentage') {
        displayValue = `${(value * 100).toFixed(1)}%`;
      } else if (type === 'number') {
        displayValue = typeof value === 'number' ? value.toFixed(3) : String(value);
      } else {
        displayValue = String(value);
      }

      card.innerHTML = `
        <div class="signal-name">${name}</div>
        <div class="signal-value">${displayValue}</div>
      `;

      container.appendChild(card);
    }

    function formatActionType(type) {
      const typeMap = {
        'freeze': 'Freeze Trading',
        'apply_policy': 'Apply Risk Policy',
        'notify_only': 'Notification Only',
        'escalate': 'Escalate Alert'
      };
      return typeMap[type] || type;
    }

    function formatActionDetails(action) {
      if (action.type === 'freeze') {
        return `Duration: ${action.ttl_minutes} minutes. ${action.reason || ''}`;
      } else if (action.type === 'apply_policy') {
        return `Mode: ${action.mode}, Daily Cap: ${(action.cap_daily * 100).toFixed(1)}%, Ramp Hours: ${action.ramp_hours}`;
      }
      return JSON.stringify(action, null, 2);
    }

    function updateModalButtonStates(alert) {
      const ackBtn = document.getElementById('ack-btn');
      const snoozeBtn = document.getElementById('snooze-btn');

      // Disable if already acknowledged
      if (alert.acknowledged_at) {
        ackBtn.textContent = 'Acknowledged';
        ackBtn.disabled = true;
        ackBtn.classList.add('modal-action-secondary');
        ackBtn.classList.remove('modal-action-primary');
      } else {
        ackBtn.textContent = 'Acknowledge';
        ackBtn.disabled = false;
        ackBtn.classList.add('modal-action-primary');
        ackBtn.classList.remove('modal-action-secondary');
      }

      // Disable snooze if already snoozed
      if (alert.snooze_until && new Date(alert.snooze_until) > new Date()) {
        snoozeBtn.textContent = 'Snoozed';
        snoozeBtn.disabled = true;
      } else {
        snoozeBtn.textContent = 'Snooze 30m';
        snoozeBtn.disabled = false;
      }
    }

    // Modal action functions
    async function acknowledgeCurrentAlert() {
      if (!currentAlert) return;

      try {
        const response = await window.globalConfig.apiRequest(`/api/alerts/test/acknowledge/${currentAlert.id}`, {
          method: 'POST',
          body: JSON.stringify({ notes: 'Acknowledged from dashboard modal' })
        });

        if (response && (response.ok || response.success || !response.error)) {
          showToast('Alert acknowledged successfully', 'success');
          currentAlert.acknowledged_at = new Date().toISOString();
          currentAlert.acknowledged_by = 'user';
          updateModalButtonStates(currentAlert);

          // Refresh alerts history if visible
          refreshAlertsHistory();
        } else {
          throw new Error(`HTTP ${response.status}`);
        }
      } catch (error) {
        debugLogger.error('Failed to acknowledge alert:', error);
        showToast('Failed to acknowledge alert', 'error');
      }
    }

    async function snoozeCurrentAlert() {
      if (!currentAlert) return;

      try {
        const response = await window.globalConfig.apiRequest(`/api/alerts/test/snooze/${currentAlert.id}`, {
          method: 'POST',
          headers: { 'Idempotency-Key': `snooze-${currentAlert.id}-${Date.now()}` },
          body: JSON.stringify({ minutes: 30 })
        });

        if (response.ok) {
          showToast('Alert snoozed for 30 minutes', 'success');
          currentAlert.snooze_until = new Date(Date.now() + 30 * 60 * 1000).toISOString();
          updateModalButtonStates(currentAlert);
          closeAlertModal();

          // Refresh alerts history if visible
          refreshAlertsHistory();
        } else {
          throw new Error(`HTTP ${response.status}`);
        }
      } catch (error) {
        debugLogger.error('Failed to snooze alert:', error);
        showToast('Failed to snooze alert', 'error');
      }
    }

    async function applyAction() {
      if (!currentAlert || !currentAlert.suggested_action) return;

      const action = currentAlert.suggested_action;
      const confirmMessage = `Apply ${formatActionType(action.type)}?\\n\\nDetails: ${formatActionDetails(action)}`;

      if (!confirm(confirmMessage)) {
        return;
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/alerts/${currentAlert.id}/apply`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': `apply-${currentAlert.id}-${Date.now()}`
          },
          body: JSON.stringify({
            applied_by: 'user'
          })
        });

        if (response.ok) {
          showToast(`${formatActionType(action.type)} applied successfully`, 'success');
          currentAlert.applied_at = new Date().toISOString();
          currentAlert.applied_by = 'user';
          closeAlertModal();

          // Refresh alerts
          refreshAlertsHistory();
        } else {
          throw new Error(`HTTP ${response.status}`);
        }
      } catch (error) {
        debugLogger.error('Failed to apply action:', error);
        showToast('Failed to apply action', 'error');
      }
    }

    // Helper functions
    function getAlertTypeDisplayName(alertType) {
      const typeMap = {
        'VOL_Q90_CROSS': 'Volatility Q90 Cross',
        'REGIME_FLIP': 'Regime Flip',
        'CORR_HIGH': 'High Correlation',
        'CONTRADICTION_SPIKE': 'Contradiction Spike',
        'DECISION_DROP': 'Decision Drop',
        'EXEC_COST_SPIKE': 'Execution Cost Spike'
      };
      return typeMap[alertType] || alertType.replace(/_/g, ' ');
    }

    function findAlertById(alertId) {
      // This will be populated by the alerts tab when it loads
      if (window.currentAlertsData) {
        return window.currentAlertsData.find(alert => alert.id === alertId);
      }
      return null;
    }

    function formatDateTime(dateStr) {
      if (!dateStr) return 'N/A';
      const date = new Date(dateStr);
      return date.toLocaleString();
    }

    // ===== PHASE 2A: REAL-TIME S3 ALERT MONITORING =====
    let alertPollingInterval = null;
    let lastKnownAlerts = [];

    function startAlertMonitoring() {
      if (alertPollingInterval) {
        clearInterval(alertPollingInterval);
      }

      // Check for new S3 alerts every 30 seconds
      alertPollingInterval = setInterval(checkForNewS3Alerts, 30000);

      // Initial check
      checkForNewS3Alerts();
    }

    async function checkForNewS3Alerts() {
      try {
        const apiBaseUrl = globalConfig.get('api_base_url');
        const response = await fetch(`${apiBaseUrl}/api/alerts/active?severity_filter=S3`);

        if (response.ok) {
          const currentAlerts = await response.json();

          // Find new S3 alerts
          const newAlerts = currentAlerts.filter(alert =>
            alert.severity === 'S3' &&
            !lastKnownAlerts.some(old => old.id === alert.id)
          );

          // Show toast for each new S3 alert
          newAlerts.forEach(alert => {
            showS3AlertToast(alert);
          });

          lastKnownAlerts = currentAlerts;
        }
      } catch (error) {
        debugLogger.error('Failed to check for new S3 alerts:', error);
      }
    }

    // Expose functions globally
    window.showToast = showToast;
    window.hideToast = hideToast;
    window.openAlertModal = openAlertModal;
    window.closeAlertModal = closeAlertModal;
    window.acknowledgeAlert = acknowledgeAlert;
    window.snoozeAlert = snoozeAlert;
    window.acknowledgeCurrentAlert = acknowledgeCurrentAlert;
    window.snoozeCurrentAlert = snoozeCurrentAlert;
    window.applyAction = applyAction;
    window.startAlertMonitoring = startAlertMonitoring;
    window.refreshAlertsHistory = refreshAlertsHistory;

    // Start monitoring when page loads
    document.addEventListener('DOMContentLoaded', () => {
      loadDismissedAlerts();  // Load previously dismissed alerts
      startAlertMonitoring();

      // Add event delegation for toast dismiss buttons
      const toastContainer = document.getElementById('toast-container');
      if (toastContainer) {
        toastContainer.addEventListener('click', (event) => {
          // Handle close button clicks
          if (event.target.classList.contains('toast-close')) {
            const toast = event.target.closest('.toast');
            if (toast) {
              debugLogger.debug('Toast close button clicked:', toast.id);
              hideToast(toast.id);
            }
          }

          // Handle action button clicks
          if (event.target.classList.contains('toast-action')) {
            const onclickAttr = event.target.getAttribute('onclick');
            if (onclickAttr) {
              // Execute the onclick code safely
              try {
                eval(onclickAttr);
              } catch (error) {
                debugLogger.error('Error executing toast action:', error);
              }
            }
          }
        });
      }

      // Remove old reference since function is now defined globally above
      // window.hideAllToasts = hideAllToasts;

      // Debug logging removed - system ready for production
    });

    // ===== Options menu helpers =====
    function toggleOptionsMenu(event) {
      event.stopPropagation?.();
      const menu = document.getElementById('options-menu');
      const btn = document.getElementById('options-menu-btn');
      if (!menu || !btn) return;
      const isOpen = menu.classList.contains('show');
      if (isOpen) {
        menu.classList.remove('show');
        btn.setAttribute('aria-expanded', 'false');
      } else {
        menu.classList.add('show');
        btn.setAttribute('aria-expanded', 'true');
      }
    }

    function closeOptionsMenu() {
      const menu = document.getElementById('options-menu');
      const btn = document.getElementById('options-menu-btn');
      if (menu) menu.classList.remove('show');
      if (btn) btn.setAttribute('aria-expanded', 'false');
    }

    // Close the menu when clicking outside or pressing Escape
    document.addEventListener('click', (e) => {
      const menu = document.getElementById('options-menu');
      const btn = document.getElementById('options-menu-btn');
      if (!menu || !btn) return;
      if (!menu.contains(e.target) && !e.target.closest('#options-menu-btn')) {
        closeOptionsMenu();
      }
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeOptionsMenu(); });

    // ===== PERSISTENT CACHE SYSTEM (continued) =====
    // CACHE_CONFIG and clearAllPersistentCache moved earlier in file for proper initialization order

    function initPersistentCache() {
      debugLogger.debug('🗄️ Initializing persistent cache system...');

      // Check existing cached scores
      const cachedScores = getCachedData('SCORES');
      if (cachedScores) {
        const age = Math.round((Date.now() - cachedScores.timestamp) / (1000 * 60));
        debugLogger.debug(`✅ Found cached scores (${age} minutes old)`);

        // Restore scores in localStorage for compatibility
        const dataSource = globalConfig.get('data_source') || 'unknown';
        // ✅ FIX: Ne pas stocker de strings vides - seulement stocker si la valeur existe
        if (cachedScores.data.onchainScore !== null && cachedScores.data.onchainScore !== undefined) {
          localStorage.setItem('risk_score_onchain', cachedScores.data.onchainScore.toString());
        }
        if (cachedScores.data.riskScore !== null && cachedScores.data.riskScore !== undefined) {
          localStorage.setItem('risk_score_risk', cachedScores.data.riskScore.toString());
        }
        if (cachedScores.data.blendedScore !== null && cachedScores.data.blendedScore !== undefined) {
          localStorage.setItem('risk_score_blended', cachedScores.data.blendedScore.toString());
        }
        if (cachedScores.data.ccsScore !== null && cachedScores.data.ccsScore !== undefined) {
          localStorage.setItem('risk_score_ccs', cachedScores.data.ccsScore.toString());
        }
        if (cachedScores.timestamp) {
          localStorage.setItem('risk_score_timestamp', cachedScores.timestamp.toString());
        }
        localStorage.setItem('risk_score_data_source', dataSource);
      }

      // Override clearCache to be selective
      window.originalClearCache = window.clearCache;
      window.clearCache = function (force = false) {
        if (force) {
          debugLogger.debug('🧹 Force clearing all cache');
          clearAllPersistentCache();
          window.originalClearCache?.();
        } else {
          debugLogger.debug('⏭️ Selective cache clear - keeping valid cached data');
          cleanExpiredCache();
        }
      };
    }

    function setCachedData(type, data) {
      const config = CACHE_CONFIG[type];
      if (!config) return false;

      // Make cache keys data-source-aware
      const dataSource = globalConfig.get('data_source') || 'unknown';
      const sourceAwareKey = `${config.key}_${dataSource}`;

      const cacheEntry = {
        data: data,
        timestamp: Date.now(),
        ttl: config.ttl,
        source: dataSource
      };

      try {
        localStorage.setItem(sourceAwareKey, JSON.stringify(cacheEntry));
        debugLogger.debug(`💾 Cached ${type} data for source ${dataSource} (TTL: ${Math.round(config.ttl / (1000 * 60 * 60))}h)`);
        return true;
      } catch (error) {
        debugLogger.warn(`Failed to cache ${type}:`, error);
        return false;
      }
    }

    function getCachedData(type) {
      const config = CACHE_CONFIG[type];
      if (!config) return null;

      // Make cache keys data-source-aware
      const dataSource = globalConfig.get('data_source') || 'unknown';
      const sourceAwareKey = `${config.key}_${dataSource}`;

      try {
        const cached = localStorage.getItem(sourceAwareKey);
        if (!cached) return null;

        const cacheEntry = JSON.parse(cached);
        const isExpired = (Date.now() - cacheEntry.timestamp) > cacheEntry.ttl;

        if (isExpired) {
          localStorage.removeItem(sourceAwareKey);
          debugLogger.debug(`⏰ Expired cache removed: ${type} for source ${dataSource}`);
          return null;
        }

        return cacheEntry;
      } catch (error) {
        debugLogger.warn(`Failed to read cache ${type}:`, error);
        localStorage.removeItem(sourceAwareKey);
        return null;
      }
    }

    function cleanExpiredCache() {
      Object.keys(CACHE_CONFIG).forEach(type => {
        getCachedData(type); // This will auto-remove expired entries
      });
    }

    // clearAllPersistentCache() moved earlier in file for proper initialization order

    // ===== CYCLE CACHE SYSTEM =====
    /**
     * Generate hash of cycle data to detect changes
     */
    // generateCycleDataHash() moved to modules/risk-cycles-tab.js or risk-targets-tab.js

    /**
     * Check if cycle content needs refresh based on data changes
     */
    // shouldRefreshCycleContent() moved to modules/risk-cycles-tab.js or risk-targets-tab.js

    function updateScoreDisplays(onchainScore, riskScore, blendedScore, ccsScore) {
      // Update score displays using existing UI update functions
      try {
        if (typeof updateOnChainIndicators === 'function') {
          updateOnChainIndicators();
        }

        // Update the main dashboard scores display
        const scoreElements = {
          onchain: document.querySelector('[data-score="onchain"]'),
          risk: document.querySelector('[data-score="risk"]'),
          blended: document.querySelector('[data-score="blended"]'),
          ccs: document.querySelector('[data-score="ccs"]')
        };

        if (scoreElements.onchain) scoreElements.onchain.textContent = Math.round(onchainScore || 0);
        if (scoreElements.risk) scoreElements.risk.textContent = Math.round(riskScore || 0);
        if (scoreElements.blended) scoreElements.blended.textContent = Math.round(blendedScore || 0);
        if (scoreElements.ccs) scoreElements.ccs.textContent = Math.round(ccsScore || 0);

        // Fallback: also update KPI elements by id (for risk-sidebar-full component)
        const elOn = document.getElementById('kpi-onchain');
        const elRisk = document.getElementById('kpi-risk');
        const elBlend = document.getElementById('kpi-blended');
        const elCcs = document.getElementById('ccs-ccs-mix');
        if (elOn && onchainScore != null) elOn.textContent = String(Math.round(onchainScore));
        if (elRisk && riskScore != null) elRisk.textContent = String(Math.round(riskScore));
        if (elBlend && blendedScore != null) elBlend.textContent = String(Math.round(blendedScore));
        if (elCcs && ccsScore != null) elCcs.textContent = String(Math.round(ccsScore));

        // ✅ CRITIQUE: Mettre à jour l'affichage Risk Score dans Risk Overview (ligne 4238)
        const riskDisplayEl = document.querySelector('[data-score="risk-display"]');
        if (riskDisplayEl && riskScore != null) {
          riskDisplayEl.textContent = `${riskScore.toFixed(1)}/100`;
        }

        debugLogger.debug('📊 Score displays updated from cache');
      } catch (error) {
        debugLogger.warn('Error updating score displays:', error);
      }
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function () {
      debugLogger.debug('Risk Dashboard CCS MVP initializing...');

      // Initialize data source tracking for cross-tab synchronization
      window.lastKnownDataSource = globalConfig.get('data_source');
      debugLogger.debug(`🔗 Risk Dashboard initialized with data source: ${window.lastKnownDataSource}`);

      // Initialize persistent cache system
      initPersistentCache();
      debugLogger.debug('Persistent cache system initialized');

      // Listen for data source changes and clear cache
      window.addEventListener('dataSourceChanged', (event) => {
        debugLogger.debug('🔄 Data source changed, clearing cache and reloading...', event.detail);
        clearCache();
        // Reload the dashboard after source change
        setTimeout(() => refreshDashboard(true), 100);
      });

      // Initialize shared header
      // Navigation thématique initialisée automatiquement

      // Appliquer le thème immédiatement
      debugLogger.debug('Initializing theme for risk-dashboard page...');
      if (window.globalConfig && window.globalConfig.applyTheme) {
        window.globalConfig.applyTheme();
      }
      if (window.applyAppearance) {
        window.applyAppearance();
      }
      debugLogger.debug('Current theme after risk-dashboard init:', document.documentElement.getAttribute('data-theme'));

      // Hydrate store from localStorage
      store.hydrate();

      // Initialize section collapse states
      initializeSectionStates();

      // Load initial data
      // Init analysis window UI then first refresh
      // controls removed
      refreshDashboard();

      // Initialize store state synchronization
      setTimeout(async () => {
        try {
          debugLogger.debug('🔄 Syncing store state...');
          await store.syncGovernanceState();
          await store.syncMLSignals();
          debugLogger.debug('✅ Store state synced');
        } catch (error) {
          debugLogger.warn('⚠️ Failed to sync store state:', error);
        }
      }, 500);

      // Apply blended strategy as default if no strategy is already selected
      setTimeout(() => {
        const currentStrategy = store.get('targets.strategy');
        if (!currentStrategy) {
          debugLogger.debug('No strategy found, applying Blended as default...');
          applyStrategy('blend');
        }
      }, 1000);

      // Écouter les changements de thème et source pour synchronisation cross-tab
      window.addEventListener('storage', function (e) {
        const expectedKey = (window.globalConfig?.getStorageKey && window.globalConfig.getStorageKey()) || 'crypto_rebal_settings_v1';
        if (e.key === expectedKey) {
          debugLogger.debug('Settings changed in another tab, checking for theme and data source changes...');

          // Check if data source changed
          const currentSource = globalConfig.get('data_source');
          const previousSource = window.lastKnownDataSource;

          if (currentSource && currentSource !== previousSource) {
            debugLogger.debug(`🔄 Data source changed from ${previousSource} to ${currentSource}, clearing cache and reloading...`);
            window.lastKnownDataSource = currentSource;
            clearCache();
            // Reload the risk dashboard after source change
            setTimeout(() => {
              window.location.reload();
            }, 500);
          }

          // Apply theme changes
          setTimeout(() => {
            if (window.globalConfig && window.globalConfig.applyTheme) {
              window.globalConfig.applyTheme();
            }
            if (window.applyAppearance) {
              window.applyAppearance();
            }
          }, 100);
        }
      });

      debugLogger.debug('Risk Dashboard CCS MVP initialized');
    });

    // Note: Sidebar toggle now handled by flyout-panel Web Component with integrated pin button