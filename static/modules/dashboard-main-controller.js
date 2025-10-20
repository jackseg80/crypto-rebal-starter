// INTELLIGENT GLOBAL INSIGHT - Using sophisticated unified intelligence
import { getUnifiedState, deriveRecommendations } from '../core/unified-insights-v2.js';
import { store } from '../core/risk-dashboard-store.js';
import { UNIFIED_ASSET_GROUPS, getAssetGroup, groupAssetsByClassification } from '../shared-asset-groups.js';
import { selectCapPercent, selectPolicyCapPercent, selectEngineCapPercent } from '../selectors/governance.js';
// Note: fetchSaxoSummary imported dynamically in refreshSaxoTile() to avoid scope issues

// ✅ Couleur conforme CLAUDE.md: Plus haut = plus robuste = VERT
const colorForScore = (s) => s > 70 ? 'var(--success)' : s >= 40 ? 'var(--warning)' : 'var(--danger)';

async function refreshGI() {
    try {
        console.debug('🧠 Refreshing Global Insight with intelligent analysis...');

        // Use sophisticated unified intelligence
        const unifiedState = await getUnifiedState();
        console.debug('✅ Unified state loaded:', {
            decision_score: unifiedState.decision?.score,
            cycle_score: unifiedState.cycle?.score,
            onchain_score: unifiedState.onchain?.score,
            risk_score: unifiedState.risk?.score
        });
        const recommendations = deriveRecommendations(unifiedState);

        // Update Decision Index with confidence
        const scoreEl = document.getElementById('gi-score');
        if (scoreEl) {
            scoreEl.textContent = unifiedState.decision.score;
            scoreEl.style.color = colorForScore(unifiedState.decision.score);

            // Add confidence tooltip if available
            if (unifiedState.decision.confidence) {
                scoreEl.title = `Confiance: ${Math.round(unifiedState.decision.confidence * 100)}% | ${unifiedState.decision.reasoning || 'Calcul intelligent'}`;
            }
        }

        // Update component scores with enhanced data
        const cycleEl = document.getElementById('gi-cycle');
        if (cycleEl) {
            const cycleScore = unifiedState.cycle?.score ?? '--';
            const cyclePhase = unifiedState.cycle?.phase?.phase;
            cycleEl.textContent = cycleScore;
            cycleEl.title = cyclePhase ? `Phase: ${cyclePhase.replace('_', ' ')} | Confiance: ${Math.round((unifiedState.cycle?.confidence || 0) * 100)}%` : '';
        }

        const onchainEl = document.getElementById('gi-onchain');
        if (onchainEl) {
            const onchainScore = unifiedState.onchain?.score;
            onchainEl.textContent = (onchainScore != null) ? onchainScore : '--';
            if (unifiedState.onchain?.criticalCount > 0) {
                onchainEl.title = `${unifiedState.onchain.criticalCount} indicateur(s) critique(s) détecté(s)`;
                onchainEl.style.fontWeight = '700';
            }
        }

        const riskEl = document.getElementById('gi-risk');
        if (riskEl) {
            const riskScore = unifiedState.risk?.score;
            riskEl.textContent = (riskScore != null) ? riskScore : '--';
            if (unifiedState.risk?.budget?.percentages?.stables) {
                riskEl.title = `Budget recommandé - Stables: ${unifiedState.risk.budget.percentages.stables}%`;
            }
        }

        // INTELLIGENT RECOMMENDATIONS from sophisticated modules
        const recoEl = document.getElementById('gi-reco');
        if (recoEl) {
            if (recommendations.length > 0) {
                const topReco = recommendations[0];
                const urgencyIcon = topReco.priority === 'critical' ? '🚨' : topReco.priority === 'high' ? '⚠️' : topReco.priority === 'medium' ? '💡' : 'ℹ️';
                recoEl.innerHTML = `${urgencyIcon} ${topReco.title}`;
                recoEl.title = `${topReco.reason} | Source: ${topReco.source || 'Intelligence unifiée'}`;

                // Color based on priority
                const priorityColors = {
                    'critical': 'var(--danger)',
                    'high': 'var(--danger)',
                    'medium': 'var(--warning)',
                    'low': 'var(--info)'
                };
                recoEl.style.color = priorityColors[topReco.priority] || 'var(--theme-text)';
            } else {
                recoEl.innerHTML = '🧘 Aucune action urgente';
                recoEl.style.color = 'var(--success)';
                recoEl.title = 'Tous les modules sont en accord - situation stable';
            }
        }

        console.debug('✅ Global Insight refreshed with:', {
            decision_score: unifiedState.decision.score,
            confidence: unifiedState.decision.confidence,
            recommendations_count: recommendations.length,
            top_recommendation: recommendations[0]?.title
        });

        // Update the meta badge with governance data
        updateGlobalInsightMeta();

    } catch (error) {
        debugLogger.warn('⚠️ Global Insight fallback to simple calculation:', error);
        console.debug('Error details:', error.stack || error);

        // Fallback to simple calculation if intelligent system fails
        const st = store.snapshot();
        const blended = st.scores?.blended ?? null;
        const cycle = Math.round(st.cycle?.ccsStar ?? st.cycle?.score ?? 0);
        const onch = st.scores?.onchain ?? null;
        const risk = st.scores?.risk ?? null;
        // ✅ Risk Score utilisé directement (pas d'inversion) - conforme CLAUDE.md
        const score = blended != null ? Math.round(blended) : Math.round(((cycle || 50) * 0.5) + ((onch ?? 50) * 0.3) + ((risk ?? 50) * 0.2));

        const el = document.getElementById('gi-score');
        if (el) { el.textContent = score; el.style.color = colorForScore(score); }

        const ec = document.getElementById('gi-cycle'); if (ec) ec.textContent = cycle || '--';
        const eo = document.getElementById('gi-onchain'); if (eo) eo.textContent = onch != null ? Math.round(onch) : '--';
        const er = document.getElementById('gi-risk'); if (er) er.textContent = risk != null ? Math.round(risk) : '--';

        const reco = document.getElementById('gi-reco');
        if (reco) {
            reco.textContent = score >= 70 ? '⚠️ Alléger 10–20%' : score <= 35 ? '🟢 DCA prudent' : '⏸️ Neutre / Attente';
            reco.title = 'Recommandation basique (système intelligent non disponible)';
        }

        // Update meta badge even in fallback
        updateGlobalInsightMeta();
    }
}

// SMART LOADING - Load data directly if not available in store
async function loadUnifiedDataForDashboard() {
    try {
        debugLogger.debug('🔄 Loading unified data for dashboard...');

        // Import and run the same cache-intelligent loader from analytics-unified
        const { getCurrentCycleMonths, cycleScoreFromMonths, getCyclePhase } = await import('../modules/cycle-navigator.js');

        // 1. Cycle data (quick calculation)
        const c = getCurrentCycleMonths();
        const cycleScore = Math.round(cycleScoreFromMonths(c.months));
        const phase = getCyclePhase(c.months);
        store.set('cycle.months', c.months);
        store.set('cycle.score', cycleScore);
        store.set('cycle.phase', phase);
        // Hydrate governance state to prefer backend Decision Engine
        try {
            await store.syncGovernanceState();
            await store.syncMLSignals();
        } catch { }
        debugLogger.debug('✅ Cycle data loaded for dashboard');

        // 2. Try to get cached scores from localStorage (from analytics-unified cache)
        const getCachedScore = (key) => {
            try {
                const user = localStorage.getItem('activeUser') || 'demo';
                const ds = (window.globalConfig && window.globalConfig.get('data_source')) || 'unknown';
                const fullKey = `${key}_${user}_${ds}`;
                const cached = localStorage.getItem(fullKey) || localStorage.getItem(key);
                if (!cached) return null;
                const data = JSON.parse(cached);
                const age = Date.now() - data.timestamp;
                // Use cache if less than 15 minutes old
                if (age < 15 * 60 * 1000) {
                    return data.data;
                }
            } catch { }
            return null;
        };

        // Try cached on-chain data
        const cachedOnchain = getCachedScore('analytics_unified_onchain');
        if (cachedOnchain && typeof cachedOnchain.score === 'number') {
            store.set('scores.onchain', cachedOnchain.score);
            store.set('scores.onchain_metadata', cachedOnchain.metadata);
            debugLogger.debug('✅ On-chain data loaded from cache for dashboard');
        }

        // Try cached risk data
        const cachedRisk = getCachedScore('analytics_unified_risk');
        if (cachedRisk && cachedRisk.risk_metrics?.risk_score) {
            store.set('scores.risk', cachedRisk.risk_metrics.risk_score);
            store.set('risk.risk_metrics', cachedRisk.risk_metrics); // Full risk metrics for sophisticated analysis
            debugLogger.debug('✅ Risk data loaded from cache for dashboard');
        }

        // Try cached blended data
        const cachedBlended = getCachedScore('analytics_unified_blended');
        if (cachedBlended && typeof cachedBlended.score === 'number') {
            store.set('scores.blended', cachedBlended.score);
            debugLogger.debug('✅ Blended score loaded from cache for dashboard');
        } else {
            // Calculate blended if we have component scores
            // ✅ Respecte docs/RISK_SEMANTICS.md - Risk Score utilisé directement (pas d'inversion)
            const state = store.snapshot();
            const cycleScore = state.cycle?.score ?? 50;
            const onchainScore = state.scores?.onchain ?? 50;
            const riskScore = state.scores?.risk ?? 50;
            const blended = (cycleScore * 0.50) + (onchainScore * 0.30) + (riskScore * 0.20);
            const blendedScore = Math.round(Math.max(0, Math.min(100, blended)));
            store.set('scores.blended', blendedScore);
            debugLogger.debug('✅ Blended score calculated for dashboard');
        }

        // Ensure basic CCS signals data is available for sophisticated modules
        const state = store.snapshot();
        if (!state.ccs?.signals) {
            store.set('ccs.signals', {
                fear_greed: { value: 50 },
                btc_dominance: { value: 57.5 },
                funding_rate: { value: 0.0001 }
            });
            debugLogger.debug('✅ Basic CCS signals data initialized for dashboard');
        }

        debugLogger.debug('🎯 Dashboard data loading completed');
        refreshGI();

    } catch (error) {
        debugLogger.error('❌ Error loading dashboard data:', error);
        // Fallback to basic calculation
        refreshGI();
    }
}

async function waitForStoreReady() {
    const state = store.snapshot();
    const hasBlended = typeof state.scores?.blended === 'number';
    const hasPartialScores = state.cycle?.score != null && state.scores?.onchain != null && state.scores?.risk != null;

    if (hasBlended) {
        debugLogger.debug('🎯 Store ready with blended data, refreshing Global Insight');
        if (typeof state.risk?.risk_budget?.target_stables_pct !== 'number') {
            try {
                const { calculateRiskBudget } = await import('../modules/market-regimes.js');
                const riskBudget = calculateRiskBudget(state.scores.blended, state.scores.risk ?? null);
                store.set('risk.risk_budget', riskBudget);
                console.debug('✅ Synthesized risk budget fallback:', { target_stables_pct: riskBudget.target_stables_pct });
            } catch (fallbackError) {
                debugLogger.warn('⚠️ Unable to synthesize risk budget fallback:', fallbackError);
            }
        }
        refreshGI();
        return;
    }

    if (hasPartialScores) {
        debugLogger.debug('🔁 Partial store data, running unified loader to compute blended score...');
        await loadUnifiedDataForDashboard();
        return;
    }

    debugLogger.debug('⏳ No store data, loading directly for dashboard...');
    await loadUnifiedDataForDashboard();
}

// Update Global Insight meta badge with governance data
function updateGlobalInsightMeta() {
    try {
        const metaEl = document.getElementById('gi-meta');
        if (!metaEl) return;

        // Get data from store
        const ml = store.get('governance.ml_signals');
        const state = (typeof store.snapshot === 'function' ? store.snapshot() : store.getState?.()) || window.realDataStore || {};

        // Format timestamp
        const ts = ml?.timestamp ? new Date(ml.timestamp) : null;
        const timeStr = ts ? ts.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '--:--:--';

        // Get contradiction index (0-1 scale, convert to percentage)
        const contradiction = ml?.contradiction_index != null ? Math.round(ml.contradiction_index * 100) : null;

        const policyCap = selectPolicyCapPercent(state);
        const engineCap = selectEngineCapPercent(state);
        const effectiveCap = selectCapPercent(state);

        const badges = [`Updated: ${timeStr}`];
        if (contradiction !== null) badges.push(`Contrad: ${contradiction}%`);
        if (policyCap != null) {
            let capLabel = `Cap: ${policyCap}%`;
            if (engineCap != null && engineCap !== policyCap) {
                capLabel += ` • SMART ${engineCap}%`;
            }
            badges.push(capLabel);
        } else if (effectiveCap != null) {
            badges.push(`Cap: ${effectiveCap}%`);
        } else {
            badges.push('Cap: —');
        }

        metaEl.textContent = badges.join(' • ');

        console.debug('🏷️ Global Insight meta updated:', {
            timestamp: timeStr,
            contradiction,
            policyCap,
            engineCap,
            effectiveCap,
            text: metaEl.textContent
        });

    } catch (error) {
        debugLogger.warn('Failed to update Global Insight meta:', error);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Subscribe to store changes for reactive updates
    // ✅ Debounce augmenté de 300ms à 500ms pour réduire les appels
    store.subscribe(() => {
        clearTimeout(window.giRefreshTimer);
        window.giRefreshTimer = setTimeout(() => {
            refreshGI();
            updateGlobalInsightMeta();
        }, 500);
    });

    // Smart initial load - wait for data to be ready
    setTimeout(waitForStoreReady, 800); // Give time for analytics-unified to start loading
});

// État global
let dashboardData = { portfolio: null, connections: null, recentActivity: null, executionStats: null };
// ❌ REMOVED: let portfolioChart = null; → Using window.portfolioChart instead to avoid reference mismatch

// ✅ Guards pour éviter les appels concurrents
let isLoadingDashboard = false;
let isRefreshingSaxo = false;
let isRefreshingBanks = false;
let isRefreshingGlobal = false;

// ✅ Interval IDs for cleanup (prevent memory leaks on page refresh)
let dashboardRefreshInterval = null;
let saxoRefreshInterval = null;
let banksRefreshInterval = null;
let globalRefreshInterval = null;
let giRefreshInterval = null;

// ✅ AbortController for event listeners cleanup
let eventListenersController = null;

document.addEventListener('DOMContentLoaded', async () => {
    console.debug('📊 Dashboard unifié initialisé');
    // Navigation thématique initialisée automatiquement

    // Appliquer le thème immédiatement
    console.debug('Initializing theme for dashboard page...');
    if (window.globalConfig && window.globalConfig.applyTheme) {
        window.globalConfig.applyTheme();
    }
    if (window.applyAppearance) {
        window.applyAppearance();
    }
    console.debug('Current theme after dashboard init:', document.documentElement.getAttribute('data-theme'));

    // Configuration Chart.js avec thème
    initChartTheme();

    // Initialize data source tracking for cross-tab synchronization
    window.lastKnownDataSource = globalConfig.get('data_source');
    console.debug(`📊 Dashboard initialized with data source: ${window.lastKnownDataSource}`);

    await loadDashboardData();

    // ✅ Store interval IDs for proper cleanup
    dashboardRefreshInterval = setInterval(loadDashboardData, 60000);

    // ✅ Initialize wealth tiles sequentially to avoid race conditions
    await refreshSaxoTile();
    await refreshBanksTile();
    await refreshGlobalTile();

    // Set up periodic refresh intervals (store IDs for cleanup)
    saxoRefreshInterval = setInterval(refreshSaxoTile, 120000); // Refresh every 2 minutes
    banksRefreshInterval = setInterval(refreshBanksTile, 120000); // Refresh every 2 minutes
    globalRefreshInterval = setInterval(refreshGlobalTile, 120000); // Refresh every 2 minutes

    // Also check for data source changes more frequently (every 5 seconds)
    giRefreshInterval = setInterval(() => {
        const currentSource = globalConfig.get('data_source');
        if (currentSource && currentSource !== window.lastKnownDataSource) {
            console.debug(`🔄 Periodic check: Data source changed from ${window.lastKnownDataSource} to ${currentSource}`);
            window.lastKnownDataSource = currentSource;
            loadDashboardData();
        }
    }, 5000);

    // ✅ Setup AbortController for event listeners cleanup
    eventListenersController = new AbortController();
    const signal = eventListenersController.signal;

    // Écouter les changements de thème et source pour synchronisation cross-tab
    window.addEventListener('storage', function (e) {
        const expectedKey = (window.globalConfig?.getStorageKey && window.globalConfig.getStorageKey()) || 'crypto_rebal_settings_v1';
        if (e.key === expectedKey) {
            console.debug('Settings changed in another tab, checking for theme and data source changes...');

            // Check if data source changed
            const currentSource = globalConfig.get('data_source');
            const previousSource = window.lastKnownDataSource;

            if (currentSource && currentSource !== previousSource) {
                console.debug(`🔄 Data source changed from ${previousSource} to ${currentSource}, reloading dashboard...`);
                console.debug('🔄 Storage event triggered data source change - forcing portfolio refresh...');
                window.lastKnownDataSource = currentSource;

                // Clear portfolio chart cache on source change
                if (window.portfolioChart) {
                    window.portfolioChart.destroy();
                    window.portfolioChart = null;
                }

                loadDashboardData();
            }

            // Apply theme changes
            setTimeout(() => {
                if (window.globalConfig && window.globalConfig.applyTheme) {
                    window.globalConfig.applyTheme();
                }
                if (window.applyAppearance) {
                    window.applyAppearance();
                }
                // Refaire le thème des graphiques aussi
                initChartTheme();
            }, 100);
        }
    }, { signal });

    window.addEventListener('dataSourceChanged', (event) => {
        console.debug(`🔄 Source changée: ${event.detail.oldSource} → ${event.detail.newSource}`);
        console.debug('🔄 Forcing complete portfolio refresh due to data source change...');

        // Clear portfolio cache when source changes
        if (window.portfolioChart) {
            window.portfolioChart.destroy();
            window.portfolioChart = null;
        }

        // ✅ FIX: Clear scores from store when source changes
        // Scores are source-specific, so we need to invalidate them
        console.debug('🧹 Clearing scores from store (source changed)');
        store.set('scores.onchain', null);
        store.set('scores.risk', null);
        store.set('scores.blended', null);
        store.set('ccs.score', null);

        // CRITICAL: Force immediate persist (no debounce) to ensure scores are cleared before page reload
        store.persist();

        // Also clear the persisted store in localStorage directly to be extra safe
        try {
            const persistedState = localStorage.getItem('risk-dashboard-state');
            if (persistedState) {
                const state = JSON.parse(persistedState);
                // Clear all scores from persisted state
                if (state.scores) {
                    state.scores.onchain = null;
                    state.scores.risk = null;
                    state.scores.blended = null;
                }
                if (state.ccs) {
                    state.ccs.score = null;
                }
                state.timestamp = Date.now();
                localStorage.setItem('risk-dashboard-state', JSON.stringify(state));
                console.debug('✅ Persisted store cleared from scores');
            }
        } catch (e) {
            console.warn('Failed to clear persisted store:', e);
        }

        // Also clear localStorage scores for the old source (legacy keys)
        const oldUser = localStorage.getItem('activeUser') || 'demo';
        ['risk_score_onchain', 'risk_score_risk', 'risk_score_blended', 'risk_score_ccs'].forEach(key => {
            localStorage.removeItem(`${key}:${oldUser}`);
        });

        // Update the known source immediately
        window.lastKnownDataSource = event.detail.newSource;

        // Force complete reload of dashboard data
        loadDashboardData();
    }, { signal });

    // ✅ FIX: Listen for Bourse source changes and refresh Saxo tiles
    window.addEventListener('bourseSourceChanged', async (event) => {
        console.debug('🏦 Bourse source changed:', event.detail);

        // Invalidate Saxo summary cache to force reload with new source
        const { invalidateSaxoCache } = await import('../modules/wealth-saxo-summary.js');
        invalidateSaxoCache();

        // Refresh both Saxo tile and Global Overview
        await refreshSaxoTile();
        await refreshGlobalTile();

        console.debug('✅ Saxo tiles refreshed with new source');
    }, { signal });

    // Reformat values when display currency changes
    window.addEventListener('configChanged', (ev) => {
        try {
            const key = ev?.detail?.key;
            if (key === 'display_currency') {
                console.debug('💱 Display currency changed, re-rendering amounts...');
                const cur = (window.globalConfig && window.globalConfig.get('display_currency')) || 'USD';
                const maybeRender = () => {
                    if (dashboardData && dashboardData.portfolio) {
                        updatePortfolioDisplay(dashboardData.portfolio);
                    }
                    if (dashboardData && dashboardData.recentActivity) {
                        updateRecentActivity(dashboardData.recentActivity);
                    }
                    if (dashboardData && dashboardData.executionStats) {
                        updateExecutionStatus(dashboardData.executionStats);
                    }
                };
                if (window.currencyManager && cur !== 'USD') {
                    window.currencyManager.ensureRate(cur).then(maybeRender).catch(maybeRender);
                } else {
                    maybeRender();
                }
            }
        } catch (e) {
            debugLogger.warn('Currency change re-render failed:', e);
        }
        // Update meta badge (Updated / Contrad / Cap)
        updateGlobalInsightMeta();
    }, { signal });

    // Also re-render when async rate fetch completes
    window.addEventListener('currencyRateUpdated', () => {
        try {
            if (dashboardData && dashboardData.portfolio) updatePortfolioDisplay(dashboardData.portfolio);
            if (dashboardData && dashboardData.recentActivity) updateRecentActivity(dashboardData.recentActivity);
            if (dashboardData && dashboardData.executionStats) updateExecutionStatus(dashboardData.executionStats);
        } catch (e) { debugLogger.warn('Re-render on rate update failed:', e); }
    }, { signal });

    // ✅ Setup cleanup on page unload (CRITICAL for preventing memory leaks)
    window.addEventListener('beforeunload', cleanupDashboard);
});

/**
 * Cleanup function to prevent memory leaks on page refresh/unload
 * Clears all intervals and event listeners
 */
function cleanupDashboard() {
    console.debug('🧹 Cleaning up dashboard resources...');

    // Clear all intervals
    if (dashboardRefreshInterval) {
        clearInterval(dashboardRefreshInterval);
        dashboardRefreshInterval = null;
    }
    if (saxoRefreshInterval) {
        clearInterval(saxoRefreshInterval);
        saxoRefreshInterval = null;
    }
    if (banksRefreshInterval) {
        clearInterval(banksRefreshInterval);
        banksRefreshInterval = null;
    }
    if (globalRefreshInterval) {
        clearInterval(globalRefreshInterval);
        globalRefreshInterval = null;
    }
    if (giRefreshInterval) {
        clearInterval(giRefreshInterval);
        giRefreshInterval = null;
    }

    // Abort all event listeners
    if (eventListenersController) {
        eventListenersController.abort();
        eventListenersController = null;
    }

    // Destroy chart
    if (window.portfolioChart) {
        window.portfolioChart.destroy();
        window.portfolioChart = null;
    }

    // ✅ Clear all cached data references
    dashboardData.portfolio = null;
    dashboardData.connections = null;
    dashboardData.recentActivity = null;
    dashboardData.executionStats = null;

    // ✅ Clear guards
    isLoadingDashboard = false;
    isRefreshingSaxo = false;
    isRefreshingBanks = false;
    isRefreshingGlobal = false;

    console.debug('✅ Dashboard cleanup complete');
}

async function loadDashboardData() {
    // ✅ Guard: éviter appels concurrents
    if (isLoadingDashboard) {
        console.debug('⏭️ loadDashboardData already in progress, skipping...');
        return;
    }

    isLoadingDashboard = true;
    try {
        // ✅ CRITICAL: Clear old data to prevent memory leaks
        dashboardData.portfolio = null;
        dashboardData.connections = null;
        dashboardData.recentActivity = null;
        dashboardData.executionStats = null;

        // Clear any potential cached data
        const currentTimestamp = Date.now();
        console.debug(`🔄 loadDashboardData called at ${currentTimestamp} with source: ${globalConfig.get('data_source')}`);

        // Charger d'abord les groupes depuis alias-manager
        await loadAssetGroups();

        const [portfolioData, connectionsData, historyData, executionStatus, scoresData] = await Promise.allSettled([
            loadPortfolioData(), loadConnectionsStatus(), loadRecentHistory(), loadExecutionStatus(), loadScoresData()
        ]);
        const portfolioResult = portfolioData.status === 'fulfilled' ? portfolioData.value : null;
        console.debug('📊 About to update portfolio display with:', {
            hasData: !!portfolioResult,
            totalValue: portfolioResult?.metrics?.total_value_usd,
            assetCount: portfolioResult?.metrics?.asset_count
        });
        // Store for re-rendering on currency change
        dashboardData.portfolio = portfolioResult;
        dashboardData.connections = connectionsData.status === 'fulfilled' ? connectionsData.value : null;
        dashboardData.recentActivity = historyData.status === 'fulfilled' ? historyData.value : null;
        dashboardData.executionStats = executionStatus.status === 'fulfilled' ? executionStatus.value : null;

        await updatePortfolioDisplay(dashboardData.portfolio);
        updateConnectionsDisplay(dashboardData.connections);
        updateRecentActivity(dashboardData.recentActivity);
        updateExecutionStatus(dashboardData.executionStats);
        updateScoresDisplay(scoresData.status === 'fulfilled' ? scoresData.value : null);
        updateSystemHealth();

        console.debug('✅ Dashboard data loaded successfully');
    } catch (e) {
        log.error('Erreur chargement dashboard:', e);
        showError('Impossible de charger les données du dashboard. Vérifiez votre connexion.');
        showError('Erreur lors du chargement des données');
    } finally {
        isLoadingDashboard = false;
    }
}

async function loadPortfolioData() {
    try {
        const currentSource = globalConfig.get('data_source');
        console.debug(`📊 Loading REAL portfolio data with source: ${currentSource}`);
        return await loadRealCSVPortfolioData();
    } catch (e) {
        log.error('Erreur portfolio CSV non disponible:', e);
        showError('Fichier CSV du portfolio non accessible.');
        return null; // Pas de fallback hardcodé
    }
}

// Fallback: API should always be available with new architecture
async function loadDirectCSV() {
    const configuredSource = globalConfig.get('data_source');
    console.warn(`⚠️ API not available, cannot load data for source: ${configuredSource}`);

    return {
        success: false,
        error: `API not available - please ensure backend is running`,
        source: configuredSource
    };
}

async function loadRealCSVPortfolioData() {
    console.debug('🔄 Loading portfolio data using configured source...');
    const currentSource = globalConfig.get('data_source');
    console.debug(`📊 Using data source: ${currentSource}`);

    // Update source display (show actual CSV filename when using CSV files)
    const sourceDisplay = document.getElementById('portfolio-source-display');
    if (sourceDisplay) {
        let displaySource = currentSource || 'Unknown';

        // If using cointracking source, try to get the actual CSV filename
        if (displaySource === 'cointracking') {
            try {
                const userSettings = await fetch('/api/users/settings', {
                    headers: { 'X-User': localStorage.getItem('activeUser') || 'demo' }
                }).then(r => r.ok ? r.json() : null);

                const csvFileName = userSettings?.csv_selected_file;
                if (csvFileName) {
                    displaySource = csvFileName;
                } else {
                    displaySource = 'cointracking_csv';
                }
            } catch (e) {
                displaySource = 'cointracking_csv';
            }
        }
        sourceDisplay.textContent = displaySource;
    }

    // Load balances first (original working code)
    console.debug('📡 About to call window.loadBalanceData()...');
    let balanceResult;

    try {
        balanceResult = await window.loadBalanceData();
        console.debug('📊 Balance result received:', {
            success: balanceResult?.success,
            source: balanceResult?.source,
            hasData: !!balanceResult?.data,
            hasCsvText: !!balanceResult?.csvText,
            dataItemsCount: balanceResult?.data?.items?.length || 0
        });
    } catch (error) {
        debugLogger.warn('📊 API not available, trying direct CSV access...', error.message);
        // Fallback: try direct CSV access since API is not available
        balanceResult = await loadDirectCSV();
    }

    if (!balanceResult || !balanceResult.success) {
        const msg = balanceResult?.error || 'Failed to load balance data';
        log.error(msg);
        throw new Error(msg);
    }

    let balances;

    if (balanceResult.csvText) {
        // Source CSV locale
        const csvText = balanceResult.csvText;
        const minThreshold = (window.globalConfig && window.globalConfig.get('min_usd_threshold')) || 1.0;
        balances = parseCSVBalancesAuto(csvText, { thresholdUSD: minThreshold });
    } else if (balanceResult.data && Array.isArray(balanceResult.data.items)) {
        // Source API
        balances = balanceResult.data.items.map(item => ({
            symbol: item.symbol,
            balance: item.balance,
            value_usd: item.value_usd
        }));
    } else {
        throw new Error('Invalid data format received');
    }

    const totalValue = balances.reduce((sum, it) => sum + (parseFloat(it.value_usd) || 0), 0);
    const assetCount = balances.length;

    console.debug(`✅ REAL data loaded: ${assetCount} assets, total: $${totalValue.toFixed(2)}`);
    console.debug('📊 Final portfolio metrics calculated:', {
        source: currentSource,
        totalValue: totalValue,
        assetCount: assetCount,
        sampleAssets: balances.slice(0, 5).map(b => `${b.symbol}: $${b.value_usd}`)
    });

    // Try to fetch P&L from API (non-blocking)
    let performance = {
        performance_available: false,
        current_value_usd: totalValue,
        absolute_change_usd: 0
    };

    try {
        const activeUser = localStorage.getItem('activeUser') || 'demo';
        const pnlUrl = `${window.location.origin}/portfolio/metrics?source=${currentSource}&user_id=${activeUser}`;
        const pnlResponse = await fetch(pnlUrl);

        if (pnlResponse.ok) {
            const pnlData = await pnlResponse.json();
            if (pnlData.ok && pnlData.performance && pnlData.performance.performance_available) {
                performance = pnlData.performance;
                debugLogger.debug('✅ [PNL] P&L loaded from API:', {
                    pnl: performance.absolute_change_usd,
                    pnlPct: performance.percentage_change
                });
            }
        }
    } catch (e) {
        debugLogger.warn('⚠️ Could not fetch P&L from API:', e.message);
    }

    return {
        ok: true,
        metrics: {
            total_value_usd: totalValue,
            asset_count: assetCount,
            last_updated: new Date().toISOString()
        },
        performance: performance,
        balances: {
            items: balances,
            total_count: balances.length,
            timestamp: new Date().toISOString()
        }
    };
}


async function loadConnectionsStatus() {
    try {
        // TODO: Implement real API endpoint /api/exchanges/status
        // For now, check if exchanges are configured via API keys in backend
        debugLogger.debug('📡 Loading exchange connections status...');

        // Temporary: Return mock data based on actual exchange adapter registrations
        // The exchange_adapter.py registers exchanges: simulator, binance, kraken
        return {
            binance: {
                name: "Binance",
                connected: false,  // Will be true when API keys are configured
                type: "centralized"
            },
            kraken: {
                name: "Kraken",
                connected: false,  // Will be true when API keys are configured
                type: "centralized"
            },
            simulator: {
                name: "Simulator",
                connected: true,  // Always available
                type: "simulator"
            }
        };
    } catch (e) {
        debugLogger.warn('Exchange status check failed:', e);
        return null;
    }
}

async function loadRecentHistory() {
    // TODO: Endpoint /api/execution/history/recent does not exist - deprecated
    // Consider using /execution/pipeline-status or another alternative
    // For now, return empty sessions to avoid 404 errors
    return { sessions: [] };

    /* DEPRECATED CODE - endpoint does not exist
    try {
        // Load from execution history API
        const response = await fetch(`${window.location.origin}/api/execution/history/recent?limit=5`);
        if (response.ok) {
            const data = await response.json();
            return { sessions: data.sessions || [] };
        }
        return { sessions: [] };
    } catch (e) {
        debugLogger.warn('Execution history not available:', e);
        return { sessions: [] };
    }
    */
}

async function loadExecutionStatus() {
    // TODO: Endpoint /api/execution/status/24h does not exist - deprecated
    // Consider using /execution/pipeline-status or another alternative
    // For now, return null to avoid 404 errors
    return null;

    /* DEPRECATED CODE - endpoint does not exist
    try {
        // Load from execution status API
        const response = await fetch(`${window.location.origin}/api/execution/status/24h`);
        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (e) {
        debugLogger.warn('Execution status not available:', e);
        return null;
    }
    */
}

// ✅ FIX: Charger les scores depuis le STORE au lieu de localStorage
// Cela synchronise avec les autres pages (analytics-unified, rebalance) qui utilisent le store
async function loadScoresData() {
    try {
        console.debug('📊 Loading scores data from store...');

        // Lire directement depuis le store (comme Global Insight)
        const state = store.snapshot();
        const result = {};
        let hasValidScores = false;

        // Extraire les scores du store
        if (state.scores) {
            if (typeof state.scores.onchain === 'number') {
                result.onchain = state.scores.onchain;
                hasValidScores = true;
            }
            if (typeof state.scores.risk === 'number') {
                result.risk = state.scores.risk;
                hasValidScores = true;
            }
            if (typeof state.scores.blended === 'number') {
                result.blended = state.scores.blended;
                hasValidScores = true;
            }
        }

        // CCS score est stocké différemment dans le store
        if (state.ccs?.score && typeof state.ccs.score === 'number') {
            result.ccs = state.ccs.score;
            hasValidScores = true;
        }

        // Timestamp du store
        if (state._hydration_timestamp) {
            result.timestamp = state._hydration_timestamp;
        }

        if (hasValidScores) {
            console.debug('✅ Scores loaded from store:', result);
            return result;
        }

        // Fallback: Si le store est vide, essayer localStorage COMME BEFORE
        // (pour compatibilité si risk-dashboard n'a pas encore chargé le store)
        console.debug('⚠️ Store empty, trying localStorage fallback...');
        const __user = localStorage.getItem('activeUser') || 'demo';
        const get = (k) => {
            const withPrefix = localStorage.getItem(`${k}:${__user}`);
            if (withPrefix !== null && withPrefix !== '') {
                return withPrefix;
            }
            const withoutPrefix = localStorage.getItem(k);
            return (withoutPrefix !== null && withoutPrefix !== '') ? withoutPrefix : null;
        };

        const scores = {
            onchain: get('risk_score_onchain'),
            risk: get('risk_score_risk'),
            blended: get('risk_score_blended'),
            ccs: get('risk_score_ccs'),
            timestamp: get('risk_score_timestamp')
        };

        const fallbackResult = {};
        let hasFallbackScores = false;

        if (scores.timestamp && !isNaN(parseInt(scores.timestamp))) {
            const age = Date.now() - parseInt(scores.timestamp);
            if (age < 12 * 60 * 60 * 1000) { // 12 heures
                fallbackResult.timestamp = parseInt(scores.timestamp);
                if (scores.onchain && !isNaN(parseFloat(scores.onchain))) {
                    fallbackResult.onchain = parseFloat(scores.onchain);
                    hasFallbackScores = true;
                }
                if (scores.risk && !isNaN(parseFloat(scores.risk))) {
                    fallbackResult.risk = parseFloat(scores.risk);
                    hasFallbackScores = true;
                }
                if (scores.blended && !isNaN(parseFloat(scores.blended))) {
                    fallbackResult.blended = parseFloat(scores.blended);
                    hasFallbackScores = true;
                }
                if (scores.ccs && !isNaN(parseFloat(scores.ccs))) {
                    fallbackResult.ccs = parseFloat(scores.ccs);
                    hasFallbackScores = true;
                }
            }
        }

        if (hasFallbackScores) {
            console.debug('✅ Scores loaded from localStorage fallback:', fallbackResult);
            return fallbackResult;
        }

        console.debug('⚠️ No scores available from store or localStorage');
        return null;

    } catch (e) {
        debugLogger.error('Erreur chargement scores:', e);
        return null;
    }
}

async function updatePortfolioDisplay(data) {
    console.debug('📊 updatePortfolioDisplay called with:', {
        hasData: !!data,
        isOk: data?.ok,
        totalValue: data?.metrics?.total_value_usd,
        assetCount: data?.metrics?.asset_count
    });

    if (!data || !data.ok) {
        console.debug('❌ Portfolio data invalid or missing, showing error');
        document.getElementById('total-value').textContent = 'Erreur';
        document.getElementById('daily-pnl').textContent = 'Erreur';
        const st = document.getElementById('portfolio-status');
        st.className = 'status-badge status-error'; st.textContent = 'Erreur';
        return;
    }
    const { metrics, performance } = data;

    document.getElementById('total-value').textContent = formatUSD(metrics.total_value_usd || 0);

    const dailyPnl = performance?.absolute_change_usd || 0;
    const dailyPnlPct = performance?.percentage_change || 0;
    debugLogger.debug('🔍 [PNL Display] Values:', {
        raw_performance: performance,
        absolute_change_usd: performance?.absolute_change_usd,
        percentage_change: performance?.percentage_change,
        dailyPnl: dailyPnl,
        dailyPnlPct: dailyPnlPct,
        formatted: formatUSD(dailyPnl)
    });
    const pnlEl = document.getElementById('daily-pnl');

    // Format: "+25,833.28$ (+6.11%)" ou "-1,234.56$ (-2.34%)"
    const pnlSign = dailyPnl >= 0 ? '+' : '';
    const pctSign = dailyPnlPct >= 0 ? '+' : '';
    const pnlText = `${pnlSign}${formatUSD(dailyPnl)} (${pctSign}${dailyPnlPct.toFixed(2)}%)`;

    pnlEl.textContent = pnlText;
    pnlEl.style.color = dailyPnl >= 0 ? 'var(--success)' : 'var(--danger)';

    document.getElementById('assets-count').textContent = metrics.asset_count || 0;

    console.debug('✅ Portfolio display updated:', {
        totalValueDisplayed: document.getElementById('total-value').textContent,
        assetsCountDisplayed: document.getElementById('assets-count').textContent,
        sourceDisplayed: document.getElementById('portfolio-source-display')?.textContent
    });

    const statusEl = document.getElementById('portfolio-status');
    if ((metrics.total_value_usd || 0) > 0) { statusEl.className = 'status-badge status-active'; statusEl.textContent = 'Actif'; }
    else { statusEl.className = 'status-badge status-warning'; statusEl.textContent = 'Vide'; }

    log.debug('About to call updatePortfolioChart with:', data.balances);
    await updatePortfolioChart(data.balances);
    // N'appeler le breakdown que si le conteneur est présent dans le DOM
    if (document.getElementById('breakdown-list')) {
        await updatePortfolioBreakdown(data.balances);
    }
}
function updateConnectionsDisplay(data) {
    const container = document.getElementById('connections-grid');
    if (!data) { container.innerHTML = '<div class="error">Erreur de chargement</div>'; return; }

    const html = Object.values(data).map(conn => {
        const cls = conn.connected ? 'status-active' : 'status-error';
        const txt = conn.connected ? 'Online' : 'Offline';
        return `
          <div class="connection-item">
            <div class="connection-name">${conn.name}</div>
            <div class="status-badge ${cls}">${txt}</div>
          </div>`;
    }).join('');
    container.innerHTML = html;
}

function updateRecentActivity(data) {
    const container = document.getElementById('recent-activity');
    if (!data || !data.sessions || data.sessions.length === 0) {
        container.innerHTML = `
          <div class="activity-item">
            <div>
              <div>Aucune activité récente</div>
              <div class="activity-desc">Les sessions d'exécution apparaîtront ici</div>
            </div>
            <div class="activity-time">--</div>
          </div>`;
        return;
    }
    const html = data.sessions.slice(0, 5).map(s => `
        <div class="activity-item">
          <div>
            <div>${s.total_orders || 0} ordres sur ${s.exchange || 'Exchange'}</div>
            <div class="activity-desc">${s.successful_orders || 0} réussis, ${formatUSD(s.total_volume_usd || 0)} volume</div>
          </div>
          <div class="activity-time">${formatTimeAgo(s.timestamp)}</div>
        </div>`).join('');
    container.innerHTML = html;
}

function updateExecutionStatus(data) {
    if (!data || !data.recent_24h) {
        document.getElementById('last-execution').textContent = 'Aucune';
        document.getElementById('success-rate').textContent = '--';
        document.getElementById('volume-24h').textContent = '$0.00';
        const st = document.getElementById('execution-status'); st.className = 'status-badge status-warning'; st.textContent = 'En attente';
        return;
    }
    document.getElementById('last-execution').textContent = data.recent_24h?.total_orders > 0 ? 'Récent' : 'Aucune';
    const sr = data.recent_24h?.success_rate;
    document.getElementById('success-rate').textContent = (sr !== undefined) ? sr.toFixed(1) + '%' : '--';
    document.getElementById('volume-24h').textContent = formatUSD(data.recent_24h?.total_volume || 0);

    const st = document.getElementById('execution-status');
    if (sr >= 95) { st.className = 'status-badge status-active'; st.textContent = 'Excellent'; }
    else if (sr >= 90) { st.className = 'status-badge status-warning'; st.textContent = 'Bon'; }
    else if (sr !== undefined) { st.className = 'status-badge status-error'; st.textContent = 'À améliorer'; }
    else { st.className = 'status-badge status-warning'; st.textContent = 'En attente'; }
}

function updateSystemHealth() {
    document.getElementById('api-status').textContent = 'Online';
    document.getElementById('data-freshness').textContent = 'Récente';
    document.getElementById('safety-status').textContent = 'Actif';
    const st = document.getElementById('system-health'); st.className = 'status-badge status-active'; st.textContent = 'Healthy';
}

// Mettre à jour l'affichage des scores
function updateScoresDisplay(scoresData) {
    const container = document.getElementById('scores-content');
    const statusEl = document.getElementById('scores-status');

    if (!scoresData) {
        // Aucun score disponible - afficher message avec lien vers risk-dashboard
        container.innerHTML = `
                    <div style="text-align: center; padding: var(--space-lg); color: var(--theme-text-muted);">
                        <div style="font-size: 2rem; margin-bottom: var(--space-md);">📊</div>
                        <div style="margin-bottom: var(--space-md);">Aucun score de risque disponible</div>
                        <a href="risk-dashboard.html"
                           class="action-btn"
                           style="text-decoration: none; display: inline-block; padding: 8px 16px; margin-top: 8px;">
                            Calculer les scores
                        </a>
                    </div>
                `;
        if (statusEl) {
            statusEl.className = 'status-badge status-warning';
            statusEl.textContent = 'Données manquantes';
        }
        return;
    }

    // Scores disponibles - afficher les valeurs disponibles
    const { onchain, risk, blended, ccs, timestamp } = scoresData;
    const STALE_MINUTES = 30; // au-delà: afficher l'étiquette Cache
    const ageMin = timestamp ? Math.round((Date.now() - timestamp) / 60000) : null;
    const isStale = ageMin != null && ageMin >= STALE_MINUTES;

    // Compter combien de scores sont disponibles
    const availableScores = [risk, onchain, blended, ccs].filter(s => s !== null && s !== undefined).length;

    // ✅ Couleurs conformes CLAUDE.md: Plus haut = plus robuste = VERT
    const getScoreColor = (score) => {
        if (score > 70) return 'var(--success)';  // Robuste = vert
        if (score >= 40) return 'var(--warning)';  // Moyen = orange
        return 'var(--danger)';  // Faible = rouge
    };

    const getScoreLabel = (score) => {
        if (score > 70) return 'Robuste';  // Positif
        if (score >= 40) return 'Moyen';
        return 'Risqué';  // Négatif
    };

    let scoresHTML = '';

    // Afficher chaque score disponible
    if (blended !== undefined && blended !== null) {
        scoresHTML += `
                    <div class="metric" style="margin: 6px 0;">
                        <span class="metric-label">⚖️ Score Stratégique</span>
                        <span class="metric-value" style="color: ${getScoreColor(blended)};">
                            ${Math.round(blended)}/100
                            <span style="font-size: 0.8em; color: var(--theme-text-muted);">(${getScoreLabel(blended)})</span>
                        </span>
                    </div>
                `;
    }

    if (ccs !== undefined && ccs !== null) {
        scoresHTML += `
                    <div class="metric" style="margin: 6px 0;">
                        <span class="metric-label">📊 CCS Score</span>
                        <span class="metric-value" style="color: ${getScoreColor(ccs)};">
                            ${Math.round(ccs)}/100
                            <span style="font-size: 0.8em; color: var(--theme-text-muted);">(${getScoreLabel(ccs)})</span>
                        </span>
                    </div>
                `;
    }

    if (onchain !== undefined && onchain !== null) {
        scoresHTML += `
                    <div class="metric" style="margin: 6px 0;">
                        <span class="metric-label">🔗 On-Chain</span>
                        <span class="metric-value" style="color: ${getScoreColor(onchain)};">
                            ${Math.round(onchain)}/100
                            <span style="font-size: 0.8em; color: var(--theme-text-muted);">(${getScoreLabel(onchain)})</span>
                        </span>
                    </div>
                `;
    }

    if (risk !== undefined && risk !== null) {
        scoresHTML += `
                    <div class="metric" style="margin: 6px 0;">
                        <span class="metric-label">🛡️ Risk</span>
                        <span class="metric-value" style="color: ${getScoreColor(risk)};">
                            ${Math.round(risk)}/100
                            <span style="font-size: 0.8em; color: var(--theme-text-muted);">(${getScoreLabel(risk)})</span>
                        </span>
                    </div>
                `;
    }

    // Message pour les scores manquants
    if (scoresHTML === '') {
        scoresHTML = `
                    <div style="text-align: center; color: var(--theme-text-muted); padding: var(--space-md);">
                        <div>📊 Aucun score disponible</div>
                        <div style="font-size: 0.9em; margin-top: var(--space-xs);">
                            Visitez le risk dashboard pour générer des scores
                        </div>
                    </div>
                `;
    }

    container.innerHTML = `
                <div style="display: grid; gap: 2px;">
                    ${scoresHTML}

                    <!-- Message informatif si scores partiels -->
                    ${availableScores > 0 && availableScores < 4 ? `
                    <div style="text-align: center; font-size: 0.75em; color: var(--theme-text-muted); margin-top: 6px; padding: 4px; background: var(--theme-surface-elevated); border-radius: 4px;">
                        💡 Visitez <a href="risk-dashboard.html" style="color: var(--brand-primary);">Risk Dashboard</a> pour calculer tous les scores
                    </div>
                    ` : ''}

                    <!-- Timestamp -->
                    ${timestamp ? `
                    <div style="text-align: center; font-size: 0.8em; color: var(--theme-text-muted); margin-top: 6px;">
                        Mis à jour: ${new Date(timestamp).toLocaleTimeString()}${isStale ? ` · <span class=\"status-badge status-warning\">Cache</span>` : ''}
                    </div>
                    ` : ''}
                </div>
            `;

    if (statusEl) {
        if (isStale) {
            statusEl.className = 'status-badge status-warning';
            statusEl.textContent = 'Cache';
        } else {
            statusEl.className = 'status-badge status-active';
            statusEl.textContent = 'À jour';
        }
    }
}

function formatUSD(v) {
    const cur = (window.globalConfig && window.globalConfig.get('display_currency')) || 'USD';
    const rate = (window.currencyManager && window.currencyManager.getRateSync(cur)) || 1;
    if (cur !== 'USD' && (!rate || rate <= 0)) return '—';
    const val = (v == null || isNaN(v)) ? 0 : (v * rate);
    try {
        // BTC is not a standard ISO code; Intl may throw
        const decimals = (cur === 'BTC') ? 8 : 0;
        const out = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: cur, minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(val);
        return (cur === 'USD') ? out.replace(/\s?US$/, '') : out;
    } catch (_) {
        const decimals = (cur === 'BTC') ? 8 : 0;
        return `${val.toFixed(decimals)} ${cur}`;
    }
}
function formatTimeAgo(ts) {
    if (!ts) return 'N/A';
    const d = new Date(ts), now = new Date(), dm = Math.floor((now - d) / (1000 * 60));
    if (dm < 60) return `${dm}min`;
    if (dm < 1440) return `${Math.floor(dm / 60)}h`;
    return `${Math.floor(dm / 1440)}j`;
}
function showError(m) {
    log.error(m);
    // Afficher l'erreur à l'utilisateur via UI
    const errorDiv = document.getElementById('error-display') || createErrorDisplay();
    errorDiv.textContent = m;
    errorDiv.style.display = 'block';
    setTimeout(() => errorDiv.style.display = 'none', 5000);
}

function createErrorDisplay() {
    const div = document.createElement('div');
    div.id = 'error-display';
    div.style.cssText = `
                position: fixed; top: 20px; right: 20px; z-index: 9999;
                background: var(--theme-error, #ff4444); color: white;
                padding: 12px 16px; border-radius: 8px; max-width: 400px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2); display: none;
            `;
    document.body.appendChild(div);
    return div;
}

// Configuration Chart.js avec thème adaptatif
function initChartTheme() {
    if (typeof Chart !== 'undefined') {
        Chart.defaults.color = 'var(--theme-text)';
        Chart.defaults.borderColor = 'var(--theme-border)';
        Chart.defaults.backgroundColor = 'var(--theme-surface)';
        Chart.defaults.plugins.tooltip.backgroundColor = 'var(--theme-surface-elevated)';
        Chart.defaults.plugins.tooltip.titleColor = 'var(--theme-text)';
        Chart.defaults.plugins.tooltip.bodyColor = 'var(--theme-text)';
        Chart.defaults.plugins.tooltip.borderColor = 'var(--theme-border)';
        Chart.defaults.plugins.tooltip.borderWidth = 1;
    }
}

// Couleurs pour le graphique portfolio (11 couleurs pour les 11 groupes canoniques)
const PORTFOLIO_COLORS = [
    '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
    '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6366f1',
    '#14b8a6'  // Ajout 11ème couleur (teal)
];

// Classification dynamique - sera chargée depuis alias-manager
let ASSET_GROUPS = null;

// Force reload taxonomy pour classification correcte des 11 groupes
async function loadAssetGroups() {
    try {
        console.debug('🔄 [Dashboard] Force reloading taxonomy for proper asset classification...');
        const { forceReloadTaxonomy, UNIFIED_ASSET_GROUPS } = await import('../shared-asset-groups.js');
        await forceReloadTaxonomy();

        if (!Object.keys(UNIFIED_ASSET_GROUPS || {}).length) {
            debugLogger.warn('⚠️ [Dashboard] Taxonomy non chargée – risque de "Others" gonflé');
        } else {
            debugLogger.debug('✅ [Dashboard] Taxonomy loaded:', Object.keys(UNIFIED_ASSET_GROUPS).length, 'groupes');
        }
    } catch (error) {
        debugLogger.error('❌ [Dashboard] Failed to load taxonomy:', error);
    }
}

// Parser CSV : wrapper auto qui utilise window.parseCSVBalances si dispo, sinon notre local
function parseCSVBalancesAuto(csvText, { thresholdUSD = 1.0 } = {}) {
    if (typeof window.parseCSVBalances === 'function') {
        return window.parseCSVBalances(csvText);
    }
    return parseCSVBalancesLocal(csvText, { thresholdUSD });
}

// Implémentation locale robuste
function parseCSVBalancesLocal(csvText, { thresholdUSD = 1.0 } = {}) {
    const cleanedText = csvText.replace(/^\ufeff/, '');
    const lines = cleanedText.split(/\r?\n/);
    const balances = [];
    const minThreshold = (window.globalConfig && window.globalConfig.get('min_usd_threshold')) || thresholdUSD || 1.0;

    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;

        try {
            const columns = parseCSVLineLocal(line);
            if (columns.length >= 5) {
                const ticker = columns[0];
                const norm = s => parseFloat(String(s).replace(/[,\u00A0]/g, ''));
                const amount = norm(columns[3]);
                const valueUSD = norm(columns[4]);

                if (ticker && !isNaN(amount) && !isNaN(valueUSD) && valueUSD >= minThreshold) {
                    balances.push({
                        symbol: ticker.toUpperCase(),
                        balance: amount,
                        value_usd: valueUSD
                    });
                }
            }
        } catch (error) {
            debugLogger.warn('Erreur parsing ligne CSV:', error.message);
        }
    }

    return balances;
}

function parseCSVLineLocal(line) {
    const result = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
        const char = line[i];

        if (char === '"') {
            inQuotes = !inQuotes;
        } else if (char === ';' && !inQuotes) {
            result.push(current.trim().replace(/^"|"$/g, ''));
            current = '';
        } else {
            current += char;
        }
    }

    if (current) {
        result.push(current.trim().replace(/^"|"$/g, ''));
    }

    return result;
}

async function groupAssetsByAliases(items) {
    // Utiliser la fonction unifiée de groupement directement depuis le module
    try {
        debugLogger.debug('🔄 [Dashboard] Classifying', items.length, 'assets with unified taxonomy');
        const { groupAssetsByClassification } = await import('../shared-asset-groups.js');

        if (!groupAssetsByClassification) {
            throw new ReferenceError('groupAssetsByClassification not available');
        }

        const result = groupAssetsByClassification(items);
        debugLogger.debug('✅ [Dashboard] Unified grouping succeeded, found', result.length, 'groups');
        return result;
    } catch (error) {
        debugLogger.warn('⚠️ [Dashboard] Unified grouping failed, using fallback:', error);
        // Fallback qui utilise aussi le groupement par classification
        const groups = new Map();
        const resolveGroup = (typeof window !== 'undefined' && typeof window.getAssetGroup === 'function')
            ? window.getAssetGroup
            : null;

        items.forEach(item => {
            const symbol = (item.symbol || '').toUpperCase();
            let group;

            // Essayer d'abord l'API taxonomy directement
            group = getGroupFromTaxonomyAPI(symbol);

            if (!group && resolveGroup) {
                try {
                    group = resolveGroup(symbol);
                } catch (e) {
                    group = autoClassifySymbol(symbol);
                }
            }

            if (!group) {
                group = autoClassifySymbol(symbol);
            }

            // Debug temporaire pour voir les classifications
            if (parseFloat(item.value_usd || 0) > 100) { // Seulement pour les assets significatifs
                debugLogger.debug(`🔍 ${symbol} → ${group} ($${parseFloat(item.value_usd || 0).toFixed(2)})`);
            }

            if (!groups.has(group)) {
                groups.set(group, {
                    label: group,
                    value: 0,
                    assets: []
                });
            }
            const groupObj = groups.get(group);
            groupObj.value += parseFloat(item.value_usd || 0);
            groupObj.assets.push(symbol);
        });

        return Array.from(groups.values());
    }
}

// Cache local pour l'API taxonomy - chargé de manière asynchrone au démarrage
let taxonomyAPICache = null;

// Chargement asynchrone de la taxonomy au démarrage de la page
(async function loadTaxonomyCache() {
    try {
        const response = await fetch('/taxonomy');
        if (response.ok) {
            const data = await response.json();
            taxonomyAPICache = data.aliases || {};
            debugLogger.debug('✅ Taxonomy cache loaded asynchronously');
        }
    } catch (e) {
        debugLogger.warn('Could not preload taxonomy cache:', e);
    }
})();

// Fonction pour récupérer depuis le cache taxonomy (pas de chargement synchrone)
function getGroupFromTaxonomyAPI(symbol) {
    // Utilise seulement le cache si déjà chargé - pas de XHR synchrone bloquant
    return taxonomyAPICache ? (taxonomyAPICache[symbol] || null) : null;
}

// Fonction de classification basique en cas d'urgence
function autoClassifySymbol(symbol) {
    const upperSymbol = symbol.toUpperCase();

    if (upperSymbol.includes('BTC') || upperSymbol.includes('WBTC')) {
        return 'BTC';
    } else if (upperSymbol.includes('ETH') || upperSymbol.includes('STETH') || upperSymbol.includes('RETH')) {
        return 'ETH';
    } else if (['USDT', 'USDC', 'DAI', 'USD', 'BUSD', 'TUSD', 'EUR'].includes(upperSymbol)) {
        return 'Stablecoins';
    } else if (upperSymbol.includes('SOL')) {
        return 'SOL';
    } else {
        return 'Others';
    }
}

// Créer ou mettre à jour le graphique portfolio
async function updatePortfolioChart(balancesData) {
    log.debug('updatePortfolioChart - balancesData:', balancesData);

    if (!balancesData || !balancesData.items) {
        console.debug('❌ No balances data or items');
        document.getElementById('portfolio-chart').innerHTML = '<div style="text-align: center; padding: 20px; color: var(--warning);">⏳ Chargement des données...</div>';
        return;
    }

    // Plus besoin de vérifier ASSET_GROUPS, utilise directement les fonctions

    let canvas = document.getElementById('portfolioChartCanvas');
    if (!canvas) {
        console.debug('❌ Canvas element not found, creating it...');
        // Créer le canvas manquant
        const chartContainer = document.getElementById('portfolio-chart');
        if (chartContainer) {
            chartContainer.innerHTML = '<canvas id="portfolioChartCanvas"></canvas>';
            canvas = document.getElementById('portfolioChartCanvas');
            console.debug('✅ Canvas element created successfully');
        } else {
            console.debug('❌ Portfolio chart container not found');
            return;
        }
    }

    // Vérifier que Chart.js est chargé
    if (typeof Chart === 'undefined') {
        console.debug('❌ Chart.js not loaded, trying to reload...');
        document.getElementById('portfolio-chart').innerHTML = '<div style="text-align: center; padding: 20px; color: var(--danger);">❌ Chart.js non chargé - rechargez la page</div>';
        return;
    }

    const ctx = canvas.getContext('2d');
    log.debug('Number of items:', balancesData.items.length);

    // Traiter les données pour le graphique avec regroupement par aliases
    const items = balancesData.items || [];
    const filteredItems = items.filter(item => parseFloat(item.value_usd || 0) > 0);

    // Regrouper par aliases
    log.debug('Filtered items for chart:', filteredItems.length);
    const groupedData = await groupAssetsByAliases(filteredItems);
    log.debug('Grouped data:', groupedData.length, 'groups');

    // Trier par valeur et afficher TOUS les groupes (11 groupes canoniques)
    const sortedData = groupedData
        .sort((a, b) => b.value - a.value);

    const labels = sortedData.map(item => item.label);
    const values = sortedData.map(item => item.value);

    // Use real total from ALL assets, not just top 8 groups shown
    const realTotal = groupedData.reduce((sum, item) => sum + item.value, 0);
    const total = realTotal;

    log.debug('Chart data:', { labels, values, total: total.toFixed(2) });

    // Si aucune donnée, afficher un message explicatif
    if (labels.length === 0 || total === 0) {
        console.debug('❌ No chart data available, showing placeholder');
        document.getElementById('portfolio-chart').innerHTML = `
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 200px; color: var(--theme-text-muted);">
                        <div style="font-size: 2rem; margin-bottom: 12px;">📊</div>
                        <div style="font-weight: 600; margin-bottom: 4px;">Données en cours de chargement</div>
                        <div style="font-size: 0.875rem;">Le graphique s'affichera quand les données seront disponibles</div>
                    </div>
                `;
        return;
    }

    // Détruire l'ancien graphique s'il existe (FIX: use window.portfolioChart consistently)
    if (window.portfolioChart) {
        window.portfolioChart.destroy();
        window.portfolioChart = null;
    }

    // Obtenir les couleurs du thème actuel
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const tooltipBg = isDark ? '#374151' : '#f9fafb';
    const tooltipText = isDark ? '#f9fafb' : '#1f2937';
    const tooltipBorder = isDark ? '#6b7280' : '#d1d5db';

    // Créer le nouveau graphique (FIX: assign to window.portfolioChart consistently)
    window.portfolioChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: values.map((_, i) => PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length]),
                borderColor: isDark ? '#374151' : '#ffffff',
                borderWidth: 2,
                hoverBorderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: tooltipBg,
                    titleColor: tooltipText,
                    bodyColor: tooltipText,
                    borderColor: tooltipBorder,
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                    callbacks: {
                        label: function (context) {
                            const value = context.parsed;
                            const percentage = ((value / total) * 100).toFixed(1);
                            const groupData = sortedData[context.dataIndex];
                            let label = `${context.label}: ${formatUSD(value)} (${percentage}%)`;

                            // Ajouter les assets du groupe si c'est un groupe
                            if (groupData.assets && groupData.assets.length > 1) {
                                label += `\nAssets: ${groupData.assets.join(', ')}`;
                            }

                            return label;
                        }
                    }
                }
            },
            cutout: '60%',
            animation: {
                animateRotate: true,
                duration: 1000
            },
            interaction: {
                intersect: false,
                mode: 'point'
            }
        }
    });
}

// Afficher la liste détaillée des allocations
async function updatePortfolioBreakdown(balancesData) {
    const container = document.getElementById('breakdown-list');
    // Si le conteneur n'existe pas sur cette page, on sort proprement
    if (!container) {
        return;
    }
    if (!balancesData || !balancesData.items) {
        container.innerHTML = '<div style="color: var(--danger);">❌ Pas de données</div>';
        return;
    }

    const items = balancesData.items || [];
    const filteredItems = items.filter(item => parseFloat(item.value_usd || 0) > 0);

    // Regrouper par aliases comme le graphique
    const groupedData = await groupAssetsByAliases(filteredItems);
    const sortedData = groupedData.sort((a, b) => b.value - a.value);
    const total = sortedData.reduce((sum, item) => sum + item.value, 0);

    log.debug('updatePortfolioBreakdown - total:', total, 'groups:', sortedData.length);

    const html = sortedData.map((group, index) => {
        const percentage = ((group.value / total) * 100).toFixed(1);
        const assets = group.assets ? ` (${group.assets.join(', ')})` : '';
        return `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0; border-bottom: 1px solid var(--theme-border);">
                        <span style="color: var(--theme-text);">${group.label}${assets}</span>
                        <span style="font-weight: 600; color: var(--theme-text);">${formatUSD(group.value)} (${percentage}%)</span>
                    </div>
                `;
    }).join('');

    container.innerHTML = html + `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; margin-top: 8px; font-weight: 700; border-top: 2px solid var(--theme-border);">
                    <span>TOTAL</span>
                    <span>${formatUSD(total)} (100%)</span>
                </div>
            `;
}

// Forcer un refresh des données avec la source actuelle
async function forceRefreshData() {
    console.debug('🔄 Force refresh demandé par utilisateur');
    console.debug('📊 Current source before refresh:', globalConfig.get('data_source'));
    console.debug('📊 Known source before refresh:', window.lastKnownDataSource);

    // Clear any potential caches
    if (window.portfolioChart) {
        window.portfolioChart.destroy();
        window.portfolioChart = null;
    }

    // Force reload taxonomy
    if (window.forceReloadTaxonomy) {
        window.forceReloadTaxonomy();
    }

    // Force reload
    await loadDashboardData();
}

// Function for debugging - call from browser console
window.debugPortfolioData = async function () {
    console.group('🔍 Portfolio Data Debug');

    const currentSource = globalConfig.get('data_source');
    debugLogger.debug('Current configured source:', currentSource);

    debugLogger.debug('Testing direct API calls...');

    // Test stub source
    try {
        const stubResponse = await fetch(`${globalConfig.get('api_base_url')}/balances/current?source=stub&_t=${Date.now()}`);
        const stubData = await stubResponse.json();
        const stubTotal = stubData.items?.reduce((sum, item) => sum + (item.value_usd || 0), 0) || 0;
        debugLogger.debug('✅ Stub source API response:', {
            success: stubResponse.ok,
            itemCount: stubData.items?.length,
            totalValue: stubTotal
        });
    } catch (e) {
        debugLogger.error('❌ Stub source failed:', e);
    }

    // Test cointracking source
    try {
        const csvResponse = await fetch(`${globalConfig.get('api_base_url')}/balances/current?source=cointracking&_t=${Date.now()}`);
        const csvData = await csvResponse.json();
        const csvTotal = csvData.items?.reduce((sum, item) => sum + (item.value_usd || 0), 0) || 0;
        debugLogger.debug('✅ CoinTracking source API response:', {
            success: csvResponse.ok,
            itemCount: csvData.items?.length,
            totalValue: csvTotal
        });
    } catch (e) {
        debugLogger.error('❌ CoinTracking source failed:', e);
    }

    // Test current configured source
    debugLogger.debug(`Testing current configured source: ${currentSource}`);
    try {
        const currentResponse = await window.loadBalanceData();
        debugLogger.debug('✅ Current source via loadBalanceData():', {
            success: currentResponse?.success,
            source: currentResponse?.source,
            hasData: !!currentResponse?.data,
            hasCsvText: !!currentResponse?.csvText,
            dataItemsCount: currentResponse?.data?.items?.length || 0
        });

        if (currentResponse?.data?.items) {
            const total = currentResponse.data.items.reduce((sum, item) => sum + (item.value_usd || 0), 0);
            debugLogger.debug('Calculated total from current source:', total);
        }
    } catch (e) {
        debugLogger.error('❌ Current source failed:', e);
    }

    console.groupEnd();
};


// ---- Drag & Drop des cartes du dashboard ----
(function () {
    const GRID_SELECTOR = '.dashboard-grid';
    const STORAGE_KEY = 'dashboard_card_order_v1';

    let dragEl = null;
    let usingHandle = false;

    document.addEventListener('DOMContentLoaded', () => {
        initCardOrdering();
    });

    function initCardOrdering() {
        const grid = document.querySelector(GRID_SELECTOR);
        if (!grid) return;

        // 1) Restaurer l'ordre sauvegardé
        restoreOrder(grid);

        // 2) Brancher les events
        grid.querySelectorAll('.card[draggable="true"]').forEach(card => {
            // Si tu veux drag uniquement via l'entête:
            const handle = card.querySelector('.card-header');
            if (handle) {
                handle.setAttribute('data-drag-handle', 'true');
                handle.style.cursor = 'move';
                handle.addEventListener('mousedown', () => usingHandle = true);
                handle.addEventListener('mouseup', () => usingHandle = false);
                handle.addEventListener('mouseleave', () => usingHandle = false);
            }

            card.addEventListener('dragstart', onDragStart);
            card.addEventListener('dragend', onDragEnd);
            card.addEventListener('dragover', onDragOver);
            card.addEventListener('dragleave', onDragLeave);
            card.addEventListener('drop', onDrop);
        });

        // Permettre le drop partout dans la grille
        grid.addEventListener('dragover', e => e.preventDefault());
        grid.addEventListener('drop', e => {
            e.preventDefault();
            clearDropIndicators(grid);
            saveOrder(grid);
        });
    }

    function onDragStart(e) {
        // Si handle requis : empêcher le drag initié ailleurs que sur le handle
        const wantsHandle = true; // passe à false pour autoriser drag partout
        if (wantsHandle) {
            const isOnHandle = e.target.closest('[data-drag-handle="true"]');
            if (!isOnHandle && !usingHandle) {
                e.preventDefault();
                return;
            }
        }
        dragEl = e.currentTarget;
        e.dataTransfer.effectAllowed = 'move';
        // Set data (certains navigateurs exigent une data)
        e.dataTransfer.setData('text/plain', dragEl.id || '');
        dragEl.classList.add('dragging');
    }

    function onDragEnd() {
        if (dragEl) dragEl.classList.remove('dragging');
        dragEl = null;
        usingHandle = false;
    }

    function onDragOver(e) {
        e.preventDefault();
        const card = e.currentTarget;
        if (!dragEl || card === dragEl) return;

        // Feedback visuel
        card.classList.add('drop-target');

        // Insertion live : on calcule si on met avant ou après la carte survolée
        const grid = card.parentElement;
        const above = shouldInsertBefore(e, card);
        if (above) grid.insertBefore(dragEl, card);
        else grid.insertBefore(dragEl, card.nextSibling);
    }

    function onDragLeave(e) {
        e.currentTarget.classList.remove('drop-target');
    }

    function onDrop(e) {
        e.preventDefault();
        e.currentTarget.classList.remove('drop-target');
        const grid = e.currentTarget.parentElement;
        saveOrder(grid);
    }

    function shouldInsertBefore(e, targetCard) {
        const rect = targetCard.getBoundingClientRect();
        // Heuristique : si on est sur la moitié supérieure, on insère avant
        return (e.clientY - rect.top) < (rect.height / 2);
    }

    function saveOrder(grid) {
        const order = Array.from(grid.querySelectorAll('.card[draggable="true"]')).map(c => c.id);
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(order));
        } catch { }
    }

    function restoreOrder(grid) {
        let raw = null;
        try { raw = localStorage.getItem(STORAGE_KEY); } catch { }
        if (!raw) return;

        try {
            const order = JSON.parse(raw);
            const map = new Map(Array.from(grid.children).map(el => [el.id, el]));
            order.forEach(id => {
                const el = map.get(id);
                if (el) grid.appendChild(el);
            });
        } catch { }
    }

    function clearDropIndicators(root) {
        root.querySelectorAll('.drop-target').forEach(el => el.classList.remove('drop-target'));
    }
})();

// === SAXO TILE FUNCTIONS ===
async function refreshSaxoTile() {
    // ✅ Guard: éviter appels concurrents
    if (isRefreshingSaxo) {
        console.debug('⏭️ refreshSaxoTile already in progress, skipping...');
        return;
    }

    isRefreshingSaxo = true;
    debugLogger.debug('🏦 Refreshing Saxo tile...');

    const statusEl = document.getElementById('saxo-status');
    const totalValueEl = document.getElementById('saxo-total-value');
    const positionsCountEl = document.getElementById('saxo-positions-count');
    const lastImportEl = document.getElementById('saxo-last-import');
    const emptyStateEl = document.getElementById('saxo-empty-state');

    // Set loading state
    if (statusEl) statusEl.textContent = 'Loading';
    if (statusEl) statusEl.className = 'status-badge status-loading';

    try {
        // Dynamic import to access module functions
        const { fetchSaxoSummary, formatCurrency, getMetricColor } = await import('../modules/wealth-saxo-summary.js');
        const summary = await fetchSaxoSummary();

        if (summary.isEmpty || summary.error) {
            // Empty state or error
            if (totalValueEl) totalValueEl.textContent = formatCurrency(0);
            if (positionsCountEl) positionsCountEl.textContent = '0';
            if (lastImportEl) lastImportEl.textContent = summary.asof || 'Aucune donnée';

            if (emptyStateEl) emptyStateEl.style.display = 'block';
            if (statusEl) {
                statusEl.textContent = summary.error ? 'Erreur' : 'Vide';
                statusEl.className = 'status-badge status-warning';
            }

            debugLogger.warn('[Saxo Tile] Empty state or error:', summary.error || 'No positions');
        } else {
            // Success with data
            if (totalValueEl) {
                totalValueEl.textContent = formatCurrency(summary.total_value);
                totalValueEl.style.color = getMetricColor(summary.total_value);
            }
            if (positionsCountEl) positionsCountEl.textContent = summary.positions_count.toString();
            if (lastImportEl) lastImportEl.textContent = summary.asof;

            if (emptyStateEl) emptyStateEl.style.display = 'none';
            if (statusEl) {
                statusEl.textContent = 'OK';
                statusEl.className = 'status-badge status-active';
            }

            debugLogger.debug('✅ Saxo tile updated:', {
                total_value: summary.total_value,
                positions_count: summary.positions_count,
                asof: summary.asof
            });
        }

        // Console assertion for sanity check
        console.assert(
            summary.positions_count >= 0,
            '[Saxo Tile] Positions count should be >= 0, got:', summary.positions_count
        );

    } catch (error) {
        debugLogger.error('[Saxo Tile] Error refreshing:', error);

        if (totalValueEl) totalValueEl.textContent = '--';
        if (positionsCountEl) positionsCountEl.textContent = '--';
        if (lastImportEl) lastImportEl.textContent = 'Erreur';

        if (emptyStateEl) emptyStateEl.style.display = 'block';
        if (statusEl) {
            statusEl.textContent = 'Erreur';
            statusEl.className = 'status-badge status-error';
        }
    } finally {
        isRefreshingSaxo = false;
    }
}

async function refreshBanksTile() {
    // ✅ Guard: éviter appels concurrents
    if (isRefreshingBanks) {
        console.debug('⏭️ refreshBanksTile already in progress, skipping...');
        return;
    }

    isRefreshingBanks = true;
    debugLogger.debug('💰 Refreshing Banks tile...');

    const statusEl = document.getElementById('banks-status');
    const totalValueEl = document.getElementById('banks-total-value');
    const accountsCountEl = document.getElementById('banks-accounts-count');
    const currenciesCountEl = document.getElementById('banks-currencies-count');
    const emptyStateEl = document.getElementById('banks-empty-state');

    // Set loading state
    if (statusEl) statusEl.textContent = 'Loading';
    if (statusEl) statusEl.className = 'status-badge status-loading';

    try {
        const activeUser = localStorage.getItem('activeUser') || 'demo';
        const response = await fetch(`${window.location.origin}/api/wealth/banks/positions?user_id=${activeUser}`, {
            headers: {
                'X-User': activeUser
            }
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const positions = await response.json();
        const formatCurrency = (val) => `$${Math.round(val).toLocaleString()}`;

        // Calculate metrics (market_value is already in USD from backend)
        const totalValueUSD = positions.reduce((sum, pos) => {
            return sum + (pos.market_value || 0);
        }, 0);

        const accountsCount = positions.length;
        const currencies = new Set(positions.map(p => p.currency));
        const currenciesCount = currencies.size;

        // Update UI
        if (positions.length === 0) {
            // Empty state
            if (totalValueEl) totalValueEl.textContent = formatCurrency(0);
            if (accountsCountEl) accountsCountEl.textContent = '0';
            if (currenciesCountEl) currenciesCountEl.textContent = '0';

            if (emptyStateEl) emptyStateEl.style.display = 'block';
            if (statusEl) {
                statusEl.textContent = 'Vide';
                statusEl.className = 'status-badge status-warning';
            }

            debugLogger.warn('[Banks Tile] Empty state - no bank accounts');
        } else {
            // Success with data
            if (totalValueEl) {
                totalValueEl.textContent = formatCurrency(totalValueUSD);
                totalValueEl.style.color = totalValueUSD > 0 ? 'var(--success)' : 'var(--theme-text)';
            }
            if (accountsCountEl) accountsCountEl.textContent = accountsCount.toString();
            if (currenciesCountEl) currenciesCountEl.textContent = currenciesCount.toString();

            if (emptyStateEl) emptyStateEl.style.display = 'none';
            if (statusEl) {
                statusEl.textContent = 'OK';
                statusEl.className = 'status-badge status-active';
            }

            debugLogger.debug('✅ Banks tile updated:', {
                total_value_usd: totalValueUSD,
                accounts_count: accountsCount,
                currencies_count: currenciesCount
            });
        }

    } catch (error) {
        debugLogger.error('[Banks Tile] Error refreshing:', error);

        if (totalValueEl) totalValueEl.textContent = '--';
        if (accountsCountEl) accountsCountEl.textContent = '--';
        if (currenciesCountEl) currenciesCountEl.textContent = '--';

        if (emptyStateEl) emptyStateEl.style.display = 'block';
        if (statusEl) {
            statusEl.textContent = 'Erreur';
            statusEl.className = 'status-badge status-error';
        }
    } finally {
        isRefreshingBanks = false;
    }
}

async function refreshGlobalTile() {
    // ✅ Guard: éviter appels concurrents
    if (isRefreshingGlobal) {
        console.debug('⏭️ refreshGlobalTile already in progress, skipping...');
        return;
    }

    isRefreshingGlobal = true;
    debugLogger.debug('🌐 Refreshing Global tile...');

    const statusEl = document.getElementById('global-status');
    const totalValueEl = document.getElementById('global-total-value');
    const breakdownEl = document.getElementById('global-breakdown');

    // Set loading state
    if (statusEl) statusEl.textContent = 'Loading';
    if (statusEl) statusEl.className = 'status-badge status-loading';

    try {
        const activeUser = localStorage.getItem('activeUser') || 'demo';
        const currentSource = (window.globalConfig && window.globalConfig.get('data_source')) || 'auto';
        const minThreshold = (window.globalConfig && window.globalConfig.get('min_usd_threshold')) || 1.0;

        // ✅ FIX: Get Bourse source from WealthContextBar and extract file_key
        let bourseFileKey = null;
        const bourseSource = window.wealthContextBar?.getContext()?.bourse;
        if (bourseSource && bourseSource !== 'all' && bourseSource.startsWith('saxo:')) {
            const key = bourseSource.substring(5); // Remove 'saxo:' prefix

            // Resolve file_key from source (same logic as wealth-saxo-summary.js)
            if (!window.availableSources) {
                const sourcesResponse = await fetch('/api/users/sources', {
                    headers: { 'X-User': activeUser }
                });
                if (sourcesResponse.ok) {
                    const data = await sourcesResponse.json();
                    window.availableSources = data.sources || [];
                }
            }

            const source = window.availableSources?.find(s => s.key === key);
            if (source?.file_path) {
                bourseFileKey = source.file_path.split(/[/\\]/).pop();
                debugLogger.debug(`[Global Tile] Using Bourse file_key: ${bourseFileKey}`);
            }
        }

        // Build API URL with bourse_file_key if available
        let apiUrl = `${window.location.origin}/api/wealth/global/summary?user_id=${activeUser}&source=${currentSource}&min_usd_threshold=${minThreshold}`;
        if (bourseFileKey) {
            apiUrl += `&bourse_file_key=${encodeURIComponent(bourseFileKey)}`;
        }

        const response = await fetch(apiUrl);

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        const formatCurrency = (val) => `$${Math.round(val).toLocaleString()}`;

        // Update total value
        if (totalValueEl) totalValueEl.textContent = formatCurrency(data.total_value_usd);

        // Build module cards with integrated charts
        if (breakdownEl && data.total_value_usd > 0) {
            const modules = [
                { name: 'Crypto', icon: '₿', value: data.breakdown.crypto, color: '#3b82f6', bgColor: 'rgba(59, 130, 246, 0.1)' },
                { name: 'Bourse', icon: '📈', value: data.breakdown.saxo, color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.1)' },
                { name: 'Banque', icon: '💰', value: data.breakdown.banks, color: '#8b5cf6', bgColor: 'rgba(139, 92, 246, 0.1)' }
            ].filter(m => m.value > 0);

            breakdownEl.innerHTML = modules.map(m => {
                const pct = (m.value / data.total_value_usd) * 100;
                return `
                            <div style="
                                padding:8px;
                                border-radius:6px;
                                background:${m.bgColor};
                                border:1px solid ${m.color}33;
                                transition:all 0.2s ease;
                            "
                            onmouseover="this.style.transform='translateY(-1px)';this.style.boxShadow='0 2px 8px rgba(0,0,0,0.08)';"
                            onmouseout="this.style.transform='translateY(0)';this.style.boxShadow='none';">
                                <!-- Header: Icon + Name + Value inline -->
                                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
                                    <div style="display:flex;align-items:center;gap:6px;">
                                        <span style="font-size:1.1rem;">${m.icon}</span>
                                        <span style="font-size:0.8rem;font-weight:600;color:var(--theme-text);">${m.name}</span>
                                    </div>
                                    <span style="font-size:1rem;font-weight:700;color:${m.color};">
                                        ${formatCurrency(m.value)}
                                    </span>
                                </div>

                                <!-- Progress bar compact -->
                                <div style="position:relative;height:16px;background:var(--theme-bg);border-radius:8px;overflow:hidden;">
                                    <div style="
                                        position:absolute;
                                        top:0;
                                        left:0;
                                        height:100%;
                                        width:${pct}%;
                                        background:linear-gradient(90deg, ${m.color}, ${m.color}dd);
                                        border-radius:8px;
                                        transition:width 0.5s ease;
                                    "></div>
                                    <div style="
                                        position:absolute;
                                        top:0;
                                        left:0;
                                        right:0;
                                        bottom:0;
                                        display:flex;
                                        align-items:center;
                                        justify-content:center;
                                        font-size:0.7rem;
                                        font-weight:600;
                                        color:${pct > 50 ? 'white' : 'var(--theme-text)'};
                                        text-shadow:${pct > 50 ? '0 1px 2px rgba(0,0,0,0.2)' : 'none'};
                                    ">
                                        ${pct.toFixed(0)}%
                                    </div>
                                </div>
                            </div>`;
            }).join('');
        }

        if (statusEl) {
            statusEl.textContent = 'OK';
            statusEl.className = 'status-badge status-active';
        }

        debugLogger.debug('✅ Global tile updated:', data);

    } catch (error) {
        debugLogger.error('[Global Tile] Error refreshing:', error);

        if (totalValueEl) totalValueEl.textContent = '--';
        if (breakdownEl) breakdownEl.innerHTML = '<div style="text-align:center;color:var(--danger);font-size:0.85rem;padding:var(--space-lg);">❌ Erreur de chargement</div>';

        if (statusEl) {
            statusEl.textContent = 'Erreur';
            statusEl.className = 'status-badge status-error';
        }
    } finally {
        isRefreshingGlobal = false;
    }
}

// Make functions globally available for onclick
window.refreshSaxoTile = refreshSaxoTile;
window.refreshBanksTile = refreshBanksTile;
window.refreshGlobalTile = refreshGlobalTile;

// ✅ REMOVED: Auto-refresh Global tile moved to main DOMContentLoaded listener to avoid duplicates

