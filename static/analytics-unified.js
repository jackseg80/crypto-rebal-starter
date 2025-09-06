/**
 * Analytics Unified - Dynamic Data Loading
 * Récupère les vraies données depuis les APIs backend
 */

console.debug('🔄 Analytics Unified - Initialisation');

// Configuration
const API_BASE = globalConfig?.get('api_base_url') || 'http://localhost:8000';

// Cache simple pour éviter les requêtes multiples
const cache = new Map();
const CACHE_DURATION = 60000; // 1 minute

async function fetchWithCache(key, fetchFn) {
    const now = Date.now();
    const cached = cache.get(key);
    
    if (cached && (now - cached.timestamp) < CACHE_DURATION) {
        return cached.data;
    }
    
    try {
        const data = await fetchFn();
        cache.set(key, { data, timestamp: now });
        return data;
    } catch (error) {
        console.warn(`Failed to fetch ${key}:`, error);
        return null;
    }
}

// Tab switching functionality
document.addEventListener('DOMContentLoaded', function() {
    setupTabSwitching();
    loadInitialData();
});

function setupTabSwitching() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.dataset.target;
            
            // Update active states
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanels.forEach(panel => panel.classList.remove('active'));
            
            button.classList.add('active');
            document.querySelector(targetId).classList.add('active');
            
            // Load data for active tab
            loadTabData(targetId);
        });
    });
}

async function loadInitialData() {
    // Load Risk tab data by default
    await loadTabData('#tab-risk');
}

async function loadTabData(tabId) {
    const tab = tabId.replace('#tab-', '');
    
    try {
        switch (tab) {
            case 'risk':
                await loadRiskData();
                break;
            case 'performance':
                await loadPerformanceData();
                break;
            case 'cycles':
                await loadCycleData();
                break;
            case 'monitoring':
                await loadMonitoringData();
                break;
        }
    } catch (error) {
        console.error(`Error loading ${tab} data:`, error);
        showErrorState(tabId);
    }
}

  async function loadRiskData() {
    console.debug('📊 Loading Risk Dashboard data...');
    
    const riskData = await fetchWithCache('risk-dashboard', async () => {
        const minUsd = globalConfig?.get('min_usd_threshold') || 10;
        const url = `${API_BASE}/api/risk/dashboard?min_usd=${minUsd}&price_history_days=365&lookback_days=90`;
        
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    });
    
      if (riskData?.success && riskData?.risk_metrics) {
          const metrics = riskData.risk_metrics;
        
        // Update Risk metrics with real data
        updateMetric('risk-var', formatPercent(Math.abs(metrics.var_95_1d)), '95% confidence level');
        updateMetric('risk-drawdown', formatPercent(Math.abs(metrics.max_drawdown)), 'Current cycle');
        updateMetric('risk-volatility', formatPercent(metrics.volatility_annualized), '30-day annualized');
        updateMetric('risk-score', `${metrics.risk_score || '--'}/100`, getRiskLevel(metrics.risk_score));
        
          // Update alerts with real risk assessment
          updateRiskAlerts(metrics, riskData.portfolio_summary);

          // Key scores (no duplication, sourced from same API when possible)
          try {
              // Diversification metrics
              const corr = riskData.correlation_metrics || {};
              if (typeof corr.diversification_ratio === 'number') {
                  updateMetric('risk-kpi-diversification', (corr.diversification_ratio).toFixed(2), 'Corrélation de portefeuille');
              } else {
                  updateMetric('risk-kpi-diversification', '--', 'Indisponible');
              }
              if (typeof corr.effective_assets === 'number') {
                  updateMetric('risk-kpi-effective-assets', Math.round(corr.effective_assets), 'Actifs non-redondants');
              } else {
                  updateMetric('risk-kpi-effective-assets', '--', 'Indisponible');
              }

              // On-Chain Composite (placeholder until backend provides it)
              updateMetric('risk-kpi-onchain', '--', 'Fondamentaux on-chain (bientôt)');

              // Blended Decision Score = blend(CCS, Cycle) when CCS available
              try {
                  const cycleModule = await import('./modules/cycle-navigator.js');
                  const cycleData = cycleModule.estimateCyclePosition();

                  let blendedScore = null;
                  try {
                      const resp = await fetch(`${API_BASE}/strategies/generate-ccs`, { method: 'POST' });
                      if (resp.ok) {
                          const js = await resp.json();
                          const ccs = Number(js?.ccs_score);
                          if (!isNaN(ccs) && cycleData?.months != null) {
                              const blended = cycleModule.blendCCS(ccs, Number(cycleData.months));
                              blendedScore = Math.round((blended?.blendedCCS ?? 0));
                          }
                      }
                  } catch (_) { /* ignore */ }

                  if (blendedScore != null) {
                      updateMetric('risk-kpi-blended', blendedScore, 'CCS × Cycle (synthèse)');
                  } else {
                      updateMetric('risk-kpi-blended', '--', 'Synthèse indisponible');
                  }
              } catch (_) {
                  updateMetric('risk-kpi-blended', '--', 'Synthèse indisponible');
              }
          } catch (e) {
              console.warn('Failed updating key risk scores:', e);
          }

      } else {
          showRiskError();
      }
  }

  async function loadPerformanceData() {
      console.debug('💾 Loading Performance Monitor data...');
      
      // Performance Monitor is about SYSTEM performance, not financial performance
      let cacheStats = null, memoryStats = null;
      try {
          cacheStats = await fetchWithCache('cache-stats', async () => {
              const response = await fetch(`${API_BASE}/api/performance/cache/stats`);
              if (!response.ok) throw new Error(`HTTP ${response.status}`);
              return await response.json();
          });
      } catch (e) { console.warn('cache-stats failed', e); }
      try {
          memoryStats = await fetchWithCache('memory-stats', async () => {
              const response = await fetch(`${API_BASE}/api/performance/system/memory`);
              if (!response.ok) throw new Error(`HTTP ${response.status}`);
              return await response.json();
          });
      } catch (e) { console.warn('memory-stats failed', e); }
      
      if (cacheStats?.success) {
          const cache = cacheStats.cache_stats;
          const memory = memoryStats?.memory_usage || {};
      
          // Update Performance metrics with real system data
          updateMetric('perf-cache-size', cache?.memory_cache_size ?? '--', 'Memory cache entries');
          updateMetric('perf-disk-cache', `${(cache?.disk_cache_size_mb ?? '--')} MB`, 'Disk cache usage');
          if (memoryStats?.success) {
              updateMetric('perf-memory', `${(memory.rss_mb || 0).toFixed(0)} MB`, 'Process memory');
              const sysUsedPct = (memory.total_system_mb && memory.available_system_mb)
                ? (((memory.total_system_mb - memory.available_system_mb) / memory.total_system_mb) * 100)
                : null;
              updateMetric('perf-system-memory', sysUsedPct != null ? `${sysUsedPct.toFixed(1)}%` : 'N/A', 'System memory usage');
          } else {
              updateMetric('perf-memory', 'N/A', 'psutil non dispo');
              updateMetric('perf-system-memory', 'N/A', 'psutil non dispo');
          }
      
          // Update performance breakdown
          updatePerformanceBreakdown(cache, memory);
      
      } else {
          showPerformanceError();
      }
  }

async function loadCycleData() {
    console.debug('🔄 Loading Cycle Analysis data...');
    
    // Import cycle analysis functions (they should be available globally or imported)
    try {
        const cycleModule = await import('./modules/cycle-navigator.js');
        const cycleData = await cycleModule.estimateCyclePosition();
        
        if (cycleData && cycleData.phase) {
            const phase = cycleData.phase;
            const months = Math.round(cycleData.months || 0);
            const confidence = Math.round((cycleData.confidence || 0) * 100);
            
            // Update Cycle metrics with real data
            updateMetric('cycle-phase', phase.phase.replace('_', ' ').toUpperCase(), `${phase.emoji} Current phase`);
            updateMetric('cycle-progress', `${months} months`, 'Post-halving progress');
            updateMetric('cycle-score', Math.round(cycleData.score || 50), 'Cycle position score');
            updateMetric('cycle-confidence', `${confidence}%`, 'Model certainty');
            
            // Update cycle indicators
            updateCycleIndicators(cycleData, phase);
            
        } else {
            showCycleError();
        }
    } catch (error) {
        console.error('Cycle data loading failed:', error);
        showCycleError();
    }
}

  async function loadMonitoringData() {
      console.debug('📈 Loading Advanced Analytics data...');
      try {
          const url = `${API_BASE}/analytics/advanced/metrics?days=365`;
          const response = await fetch(url);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const data = await response.json();

          // Update 4 KPIs
          updateMetric('monitor-total-return', `${(data.total_return_pct).toFixed(1)}%`, 'Sur la période');
          updateMetric('monitor-sharpe', (data.sharpe_ratio).toFixed(2), 'Risque ajusté');
          updateMetric('monitor-volatility', `${(data.volatility_pct).toFixed(1)}%`, 'Risque de marché');
          updateMetric('monitor-drawdown', `${Math.abs(data.max_drawdown_pct).toFixed(1)}%`, 'Pire baisse');

          // Breakdown panel
          const breakdown = document.getElementById('advanced-metrics-breakdown');
          if (breakdown) {
              breakdown.innerHTML = `
                  <div style="display:flex; justify-content:space-between;"><span>Volatility:</span><span>${data.volatility_pct.toFixed(1)}%</span></div>
                  <div style="display:flex; justify-content:space-between;"><span>Sortino:</span><span>${data.sortino_ratio.toFixed(2)}</span></div>
                  <div style="display:flex; justify-content:space-between;"><span>Omega:</span><span>${data.omega_ratio.toFixed(2)}</span></div>
                  <div style="display:flex; justify-content:space-between;"><span>Positive Months:</span><span>${data.positive_months_pct.toFixed(1)}%</span></div>
              `;
          }
      } catch (error) {
          console.error('Advanced analytics loading failed:', error);
          showMonitoringError();
      }
  }

// Utility functions
function updateMetric(id, value, subtitle) {
    const tabPrefix = id.split('-')[0];
    const tabMap = { risk: 'risk', perf: 'performance', cycle: 'cycles', monitor: 'monitoring' };
    const panelId = tabMap[tabPrefix] || tabPrefix;
    const panel = document.querySelector(`#tab-${panelId}`);
    if (!panel) return;

    // Prefer explicit data-metric mapping when available
    let container = panel.querySelector(`[data-metric="${id}"]`);

    // Fallback to positional mapping if no data-metric hook
    if (!container) {
        const cards = panel.querySelectorAll('.metric-card');
        const idx = getMetricIndex(id) - 1; // zero-based
        if (cards[idx]) container = cards[idx];
    }

    if (!container) return;

    const valueEl = container.querySelector('.metric-value');
    const subtitleEl = container.querySelector('small');

    if (valueEl) valueEl.textContent = value;
    if (subtitleEl) subtitleEl.textContent = subtitle;
}

  function getMetricIndex(id) {
      const indices = {
          'risk-var': 1,
          'risk-drawdown': 2, 
          'risk-volatility': 3,
          'risk-score': 4,
          'risk-kpi-diversification': 1,
          'risk-kpi-effective-assets': 2,
          'risk-kpi-blended': 3,
          'risk-kpi-onchain': 4,
          'perf-cache-size': 1,
          'perf-disk-cache': 2,
          'perf-memory': 3,
          'perf-system-memory': 4,
          'cycle-phase': 1,
          'cycle-progress': 2,
          'cycle-score': 3,
          'cycle-confidence': 4,
          'monitor-total-return': 1,
          'monitor-sharpe': 2,
          'monitor-volatility': 3,
          'monitor-drawdown': 4
      };
      return indices[id] || 1;
  }

function formatPercent(value) {
    if (value == null || isNaN(value)) return 'N/A';
    return `${(value * 100).toFixed(2)}%`;
}

function getRiskLevel(score) {
    if (!score) return 'Unknown';
    if (score < 30) return 'Low risk';
    if (score < 70) return 'Moderate risk';
    return 'High risk';
}

function updateRiskAlerts(metrics, portfolio) {
    const alertsContainer = document.querySelector('#tab-risk .panel-card div:nth-child(3)');
    if (!alertsContainer) return;
    
    const alerts = [];
    
    if (metrics.var_95_1d && Math.abs(metrics.var_95_1d) > 0.08) {
        alerts.push('⚠️ High VaR detected - consider risk reduction');
    } else {
        alerts.push('✅ VaR within acceptable limits');
    }
    
    if (metrics.max_drawdown && Math.abs(metrics.max_drawdown) > 0.6) {
        alerts.push('⚠️ High maximum drawdown - diversification recommended');
    } else {
        alerts.push('✅ Drawdown risk manageable');
    }
    
    if (portfolio?.concentration_risk > 0.5) {
        alerts.push('⚠️ Portfolio concentration risk elevated');
    } else {
        alerts.push('✅ Portfolio concentration within limits');
    }
    
    alertsContainer.innerHTML = `
        <h4>Risk Alerts</h4>
        ${alerts.map(alert => `<div style="color: var(--theme-text-muted);">• ${alert}</div>`).join('')}
    `;
}

function updatePerformanceBreakdown(cache, memory) {
    const breakdownContainer = document.querySelector('#tab-performance .panel-card div:nth-child(3)');
    if (!breakdownContainer) return;
    
    const memEntries = Number(cache?.memory_cache_size);
    const diskFiles = Number(cache?.disk_cache_files);
    const hitRate = (Number.isFinite(memEntries) && Number.isFinite(diskFiles) && (memEntries + diskFiles) > 0)
        ? ((memEntries / (memEntries + diskFiles)) * 100).toFixed(1) + '%'
        : 'N/A';
    const availGb = Number.isFinite(Number(memory?.available_system_mb)) ? (memory.available_system_mb / 1024).toFixed(1) + ' GB' : 'N/A';
    const procEff = (typeof memory?.percent === 'number')
        ? (memory.percent < 5 ? 'Excellent' : memory.percent < 10 ? 'Good' : 'Average')
        : 'N/A';

    breakdownContainer.innerHTML = `
        <h4>System Performance</h4>
        <div style="display: grid; gap: 0.5rem;">
            <div style="display: flex; justify-content: space-between;"><span>Memory Cache Hit Rate:</span><span style="color: var(--success);">${hitRate}</span></div>
            <div style="display: flex; justify-content: space-between;"><span>Available Memory:</span><span>${availGb}</span></div>
            <div style="display: flex; justify-content: space-between;"><span>Process Efficiency:</span><span>${procEff}</span></div>
        </div>
    `;
}

function updateCycleIndicators(cycleData, phase) {
    const indicatorsContainer = document.querySelector('#tab-cycles .panel-card div:nth-child(3)');
    if (!indicatorsContainer) return;
    
    indicatorsContainer.innerHTML = `
        <h4>Market Cycle Indicators</h4>
        <div style="display: grid; gap: 0.5rem;">
            <div style="display: flex; justify-content: space-between;"><span>Current Phase:</span><span>${phase.phase.replace('_', ' ')}</span></div>
            <div style="display: flex; justify-content: space-between;"><span>Phase Color:</span><span style="color: ${phase.color};">●</span></div>
            <div style="display: flex; justify-content: space-between;"><span>Score Range:</span><span>${Math.round(cycleData.score)}/100</span></div>
        </div>
    `;
}

  // No longer needed; advanced metrics are filled inline above

// Error state functions
function showErrorState(tabId) {
    const panel = document.querySelector(`${tabId} .panel-card`);
    if (panel) {
        panel.innerHTML = `
            <h3>⚠️ Data Loading Error</h3>
            <p style="color: var(--theme-text-muted);">Unable to load data. Please check if the backend server is running.</p>
            <button onclick="loadTabData('${tabId}')" class="btn btn-primary" style="background: var(--brand-primary); color: white; padding: 0.5rem 1rem; border: none; border-radius: 0.25rem; cursor: pointer;">Retry</button>
        `;
    }
}

function showRiskError() {
    showErrorState('#tab-risk');
}

function showPerformanceError() {
    showErrorState('#tab-performance'); 
}

function showCycleError() {
    showErrorState('#tab-cycles');
}

function showMonitoringError() {
    showErrorState('#tab-monitoring');
}

// Auto-refresh every 5 minutes
setInterval(() => {
    const activeTab = document.querySelector('.tab-panel.active');
    if (activeTab) {
        cache.clear(); // Clear cache to force refresh
        loadTabData(`#${activeTab.id}`);
    }
}, 5 * 60 * 1000);

console.debug('✅ Analytics Unified - Initialization complete');
