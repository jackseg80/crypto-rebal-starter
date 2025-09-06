0001: /**
0002:  * Analytics Unified - Dynamic Data Loading
0003:  * Récupère les vraies données depuis les APIs backend
0004:  */
0005: 
0006: console.debug('🔄 Analytics Unified - Initialisation');
0007: 
0008: // Configuration
0009: const API_BASE = globalConfig?.get('api_base_url') || 'http://localhost:8000';
0010: 
0011: // Cache simple pour éviter les requêtes multiples
0012: const cache = new Map();
0013: const CACHE_DURATION = 60000; // 1 minute
0014: 
0015: async function fetchWithCache(key, fetchFn) {
0016:     const now = Date.now();
0017:     const cached = cache.get(key);
0018:     
0019:     if (cached && (now - cached.timestamp) < CACHE_DURATION) {
0020:         return cached.data;
0021:     }
0022:     
0023:     try {
0024:         const data = await fetchFn();
0025:         cache.set(key, { data, timestamp: now });
0026:         return data;
0027:     } catch (error) {
0028:         console.warn(`Failed to fetch ${key}:`, error);
0029:         return null;
0030:     }
0031: }
0032: 
0033: // Tab switching functionality
0034: document.addEventListener('DOMContentLoaded', function() {
0035:     setupTabSwitching();
0036:     loadInitialData();
0037:     // Keep metrics in sync with risk-dashboard scores written to localStorage
0038:     window.addEventListener('storage', (e) => {
0039:         if (e.key && e.key.startsWith('risk_score_')) {
0040:             try { refreshScoresFromLocalStorage(); } catch (_) {}
0041:         }
0042:     });
0043: });
0044: 
0045: function getScoresFromLocalStorage() {
0046:     try {
0047:         const onchain = parseFloat(localStorage.getItem('risk_score_onchain'));
0048:         const risk = parseFloat(localStorage.getItem('risk_score_risk'));
0049:         const blended = parseFloat(localStorage.getItem('risk_score_blended'));
0050:         const ccs = parseFloat(localStorage.getItem('risk_score_ccs'));
0051:         const timestamp = localStorage.getItem('risk_score_timestamp');
0052:         return {
0053:             onchain: Number.isFinite(onchain) ? onchain : null,
0054:             risk: Number.isFinite(risk) ? risk : null,
0055:             blended: Number.isFinite(blended) ? blended : null,
0056:             ccs: Number.isFinite(ccs) ? ccs : null,
0057:             timestamp
0058:         };
0059:     } catch (_) {
0060:         return { onchain: null, risk: null, blended: null, ccs: null, timestamp: null };
0061:     }
0062: }
0063: 
0064: function refreshScoresFromLocalStorage() {
0065:     const scores = getScoresFromLocalStorage();
0066:     if (scores.onchain != null) {
0067:         updateMetric('risk-kpi-onchain', Math.round(scores.onchain), 'Fondamentaux on-chain');
0068:     }
0069:     if (scores.blended != null) {
0070:         updateMetric('risk-kpi-blended', Math.round(scores.blended), 'CCS × Cycle (synthèse)');
0071:     }
0072: }
0073: 
0074: function setupTabSwitching() {
0075:     const tabButtons = document.querySelectorAll('.tab-btn');
0076:     const tabPanels = document.querySelectorAll('.tab-panel');
0077:     
0078:     tabButtons.forEach(button => {
0079:         button.addEventListener('click', () => {
0080:             const targetId = button.dataset.target;
0081:             
0082:             // Update active states
0083:             tabButtons.forEach(btn => btn.classList.remove('active'));
0084:             tabPanels.forEach(panel => panel.classList.remove('active'));
0085:             
0086:             button.classList.add('active');
0087:             document.querySelector(targetId).classList.add('active');
0088:             
0089:             // Load data for active tab
0090:             loadTabData(targetId);
0091:         });
0092:     });
0093: }
0094: 
0095: async function loadInitialData() {
0096:     // Load Risk tab data by default
0097:     await loadTabData('#tab-risk');
0098: }
0099: 
0100: async function loadTabData(tabId) {
0101:     const tab = tabId.replace('#tab-', '');
0102:     
0103:     try {
0104:         switch (tab) {
0105:             case 'risk':
0106:                 await loadRiskData();
0107:                 break;
0108:             case 'performance':
0109:                 await loadPerformanceData();
0110:                 break;
0111:             case 'cycles':
0112:                 await loadCycleData();
0113:                 break;
0114:             case 'monitoring':
0115:                 await loadMonitoringData();
0116:                 break;
0117:         }
0118:     } catch (error) {
0119:         console.error(`Error loading ${tab} data:`, error);
0120:         showErrorState(tabId);
0121:     }
0122: }
0123: 
0124:   async function loadRiskData() {
0125:   console.debug('🧮 Loading Risk Dashboard data...');
0126: 
0127:   const riskData = await fetchWithCache('risk-dashboard', async () => {
0128:     const minUsd = globalConfig?.get('min_usd_threshold') || 10;
0129:     const url = ${API_BASE}/api/risk/dashboard?min_usd=&price_history_days=365&lookback_days=90;
0130:     const response = await fetch(url);
0131:     if (!response.ok) throw new Error(HTTP );
0132:     return await response.json();
0133:   });
0134: 
0135:   if (!(riskData?.success && riskData?.risk_metrics)) {
0136:     showRiskError();
0137:     return;
0138:   }
0139: 
0140:   const metrics = riskData.risk_metrics;
0141: 
0142:   // Core risk metrics
0143:   updateMetric('risk-var', formatPercent(Math.abs(metrics.var_95_1d)), '95% confidence level');
0144:   updateMetric('risk-drawdown', formatPercent(Math.abs(metrics.max_drawdown)), 'Current cycle');
0145:   updateMetric('risk-volatility', formatPercent(metrics.volatility_annualized), '30-day annualized');
0146:   updateMetric('risk-score', ${metrics.risk_score || '--'}/100, getRiskLevel(metrics.risk_score));
0147: 
0148:   // Alerts
0149:   updateRiskAlerts(metrics, riskData.portfolio_summary);
0150: 
0151:   // Diversification metrics
0152:   const corr = riskData.correlation_metrics || {};
0153:   if (typeof corr.diversification_ratio === 'number') {
0154:     updateMetric('risk-kpi-diversification', (corr.diversification_ratio).toFixed(2), 'Corrélation de portefeuille');
0155:   } else {
0156:     updateMetric('risk-kpi-diversification', '--', 'Indisponible');
0157:   }
0158:   if (typeof corr.effective_assets === 'number') {
0159:     updateMetric('risk-kpi-effective-assets', Math.round(corr.effective_assets), 'Actifs non-redondants');
0160:   } else {
0161:     updateMetric('risk-kpi-effective-assets', '--', 'Indisponible');
0162:   }
0163: 
0164:   // Scores depuis le Risk Dashboard (source de vérité)
0165:   const ls = getScoresFromLocalStorage();
0166:   if (ls.onchain != null) {
0167:     updateMetric('risk-kpi-onchain', Math.round(ls.onchain), 'Fondamentaux on-chain');
0168:   } else {
0169:     updateMetric('risk-kpi-onchain', '--', 'Fondamentaux on-chain (bientôt)');
0170:   }
0171:   if (ls.blended != null) {
0172:     updateMetric('risk-kpi-blended', Math.round(ls.blended), 'CCS × Cycle (synthèse)');
0173:   } else {
0174:     updateMetric('risk-kpi-blended', '--', 'Synthèse indisponible (ouvrez le Risk Dashboard)');
0175:   }
0176: 
0177:   // Timestamp (si dispo) au bas du panneau
0178:   try {
0179:     const ts = ls.timestamp ? new Date(Number(ls.timestamp)).toLocaleTimeString() : null;
0180:     const panel = document.querySelector('#tab-risk .panel-card');
0181:     if (ts && panel) {
0182:       let info = panel.querySelector('.scores-updated-at');
0183:       if (!info) {
0184:         info = document.createElement('div');
0185:         info.className = 'scores-updated-at';
0186:         info.style.cssText = 'text-align:center; font-size:12px; color: var(--theme-text-muted); margin-top:.25rem;';
0187:         panel.appendChild(info);
0188:       }
0189:       info.textContent = Mis à jour: ;
0190:     }
0191:   } catch (_) { /* ignore */ }
0192: }async function loadPerformanceData() {
0193:       console.debug('💾 Loading Performance Monitor data...');
0194:       
0195:       // Performance Monitor is about SYSTEM performance, not financial performance
0196:       let cacheStats = null, memoryStats = null;
0197:       try {
0198:           cacheStats = await fetchWithCache('cache-stats', async () => {
0199:               const response = await fetch(`${API_BASE}/api/performance/cache/stats`);
0200:               if (!response.ok) throw new Error(`HTTP ${response.status}`);
0201:               return await response.json();
0202:           });
0203:       } catch (e) { console.warn('cache-stats failed', e); }
0204:       try {
0205:           memoryStats = await fetchWithCache('memory-stats', async () => {
0206:               const response = await fetch(`${API_BASE}/api/performance/system/memory`);
0207:               if (!response.ok) throw new Error(`HTTP ${response.status}`);
0208:               return await response.json();
0209:           });
0210:       } catch (e) { console.warn('memory-stats failed', e); }
0211:       
0212:       if (cacheStats?.success) {
0213:           const cache = cacheStats.cache_stats;
0214:           const memory = memoryStats?.memory_usage || {};
0215:       
0216:           // Update Performance metrics with real system data
0217:           updateMetric('perf-cache-size', cache?.memory_cache_size ?? '--', 'Memory cache entries');
0218:           updateMetric('perf-disk-cache', `${(cache?.disk_cache_size_mb ?? '--')} MB`, 'Disk cache usage');
0219:           if (memoryStats?.success) {
0220:               updateMetric('perf-memory', `${(memory.rss_mb || 0).toFixed(0)} MB`, 'Process memory');
0221:               const sysUsedPct = (memory.total_system_mb && memory.available_system_mb)
0222:                 ? (((memory.total_system_mb - memory.available_system_mb) / memory.total_system_mb) * 100)
0223:                 : null;
0224:               updateMetric('perf-system-memory', sysUsedPct != null ? `${sysUsedPct.toFixed(1)}%` : 'N/A', 'System memory usage');
0225:           } else {
0226:               updateMetric('perf-memory', 'N/A', 'psutil non dispo');
0227:               updateMetric('perf-system-memory', 'N/A', 'psutil non dispo');
0228:           }
0229:       
0230:           // Update performance breakdown
0231:           updatePerformanceBreakdown(cache, memory);
0232:       
0233:       } else {
0234:           showPerformanceError();
0235:       }
0236:   }
0237: 
0238: async function loadCycleData() {
0239:     console.debug('🔄 Loading Cycle Analysis data...');
0240:     
0241:     // Import cycle analysis functions (they should be available globally or imported)
0242:     try {
0243:         const cycleModule = await import('./modules/cycle-navigator.js');
0244:         const cycleData = await cycleModule.estimateCyclePosition();
0245:         
0246:         if (cycleData && cycleData.phase) {
0247:             const phase = cycleData.phase;
0248:             const months = Math.round(cycleData.months || 0);
0249:             const confidence = Math.round((cycleData.confidence || 0) * 100);
0250:             
0251:             // Update Cycle metrics with real data
0252:             updateMetric('cycle-phase', phase.phase.replace('_', ' ').toUpperCase(), `${phase.emoji} Current phase`);
0253:             updateMetric('cycle-progress', `${months} months`, 'Post-halving progress');
0254:             updateMetric('cycle-score', Math.round(cycleData.score || 50), 'Cycle position score');
0255:             updateMetric('cycle-confidence', `${confidence}%`, 'Model certainty');
0256:             
0257:             // Update cycle indicators
0258:             updateCycleIndicators(cycleData, phase);
0259:             
0260:         } else {
0261:             showCycleError();
0262:         }
0263:     } catch (error) {
0264:         console.error('Cycle data loading failed:', error);
0265:         showCycleError();
0266:     }
0267: }
0268: 
0269:   async function loadMonitoringData() {
0270:       console.debug('📈 Loading Advanced Analytics data...');
0271:       try {
0272:           const url = `${API_BASE}/analytics/advanced/metrics?days=365`;
0273:           const response = await fetch(url);
0274:           if (!response.ok) throw new Error(`HTTP ${response.status}`);
0275:           const data = await response.json();
0276: 
0277:           // Update 4 KPIs
0278:           updateMetric('monitor-total-return', `${(data.total_return_pct).toFixed(1)}%`, 'Sur la période');
0279:           updateMetric('monitor-sharpe', (data.sharpe_ratio).toFixed(2), 'Risque ajusté');
0280:           updateMetric('monitor-volatility', `${(data.volatility_pct).toFixed(1)}%`, 'Risque de marché');
0281:           updateMetric('monitor-drawdown', `${Math.abs(data.max_drawdown_pct).toFixed(1)}%`, 'Pire baisse');
0282: 
0283:           // Breakdown panel
0284:           const breakdown = document.getElementById('advanced-metrics-breakdown');
0285:           if (breakdown) {
0286:               breakdown.innerHTML = `
0287:                   <div style="display:flex; justify-content:space-between;"><span>Volatility:</span><span>${data.volatility_pct.toFixed(1)}%</span></div>
0288:                   <div style="display:flex; justify-content:space-between;"><span>Sortino:</span><span>${data.sortino_ratio.toFixed(2)}</span></div>
0289:                   <div style="display:flex; justify-content:space-between;"><span>Omega:</span><span>${data.omega_ratio.toFixed(2)}</span></div>
0290:                   <div style="display:flex; justify-content:space-between;"><span>Positive Months:</span><span>${data.positive_months_pct.toFixed(1)}%</span></div>
0291:               `;
0292:           }
0293:       } catch (error) {
0294:           console.error('Advanced analytics loading failed:', error);
0295:           showMonitoringError();
0296:       }
0297:   }
0298: 
0299: // Utility functions
0300: function updateMetric(id, value, subtitle) {
0301:     const tabPrefix = id.split('-')[0];
0302:     const tabMap = { risk: 'risk', perf: 'performance', cycle: 'cycles', monitor: 'monitoring' };
0303:     const panelId = tabMap[tabPrefix] || tabPrefix;
0304:     const panel = document.querySelector(`#tab-${panelId}`);
0305:     if (!panel) return;
0306: 
0307:     // Prefer explicit data-metric mapping when available
0308:     let container = panel.querySelector(`[data-metric="${id}"]`);
0309: 
0310:     // Fallback to positional mapping if no data-metric hook
0311:     if (!container) {
0312:         const cards = panel.querySelectorAll('.metric-card');
0313:         const idx = getMetricIndex(id) - 1; // zero-based
0314:         if (cards[idx]) container = cards[idx];
0315:     }
0316: 
0317:     if (!container) return;
0318: 
0319:     const valueEl = container.querySelector('.metric-value');
0320:     const subtitleEl = container.querySelector('small');
0321: 
0322:     if (valueEl) valueEl.textContent = value;
0323:     if (subtitleEl) subtitleEl.textContent = subtitle;
0324: }
0325: 
0326:   function getMetricIndex(id) {
0327:       const indices = {
0328:           'risk-var': 1,
0329:           'risk-drawdown': 2, 
0330:           'risk-volatility': 3,
0331:           'risk-score': 4,
0332:           'risk-kpi-diversification': 1,
0333:           'risk-kpi-effective-assets': 2,
0334:           'risk-kpi-blended': 3,
0335:           'risk-kpi-onchain': 4,
0336:           'perf-cache-size': 1,
0337:           'perf-disk-cache': 2,
0338:           'perf-memory': 3,
0339:           'perf-system-memory': 4,
0340:           'cycle-phase': 1,
0341:           'cycle-progress': 2,
0342:           'cycle-score': 3,
0343:           'cycle-confidence': 4,
0344:           'monitor-total-return': 1,
0345:           'monitor-sharpe': 2,
0346:           'monitor-volatility': 3,
0347:           'monitor-drawdown': 4
0348:       };
0349:       return indices[id] || 1;
0350:   }
0351: 
0352: function formatPercent(value) {
0353:     if (value == null || isNaN(value)) return 'N/A';
0354:     return `${(value * 100).toFixed(2)}%`;
0355: }
0356: 
0357: function getRiskLevel(score) {
0358:     if (!score) return 'Unknown';
0359:     if (score < 30) return 'Low risk';
0360:     if (score < 70) return 'Moderate risk';
0361:     return 'High risk';
0362: }
0363: 
0364: function updateRiskAlerts(metrics, portfolio) {
0365:     const alertsContainer = document.querySelector('#tab-risk .panel-card div:nth-child(3)');
0366:     if (!alertsContainer) return;
0367:     
0368:     const alerts = [];
0369:     
0370:     if (metrics.var_95_1d && Math.abs(metrics.var_95_1d) > 0.08) {
0371:         alerts.push('⚠️ High VaR detected - consider risk reduction');
0372:     } else {
0373:         alerts.push('✅ VaR within acceptable limits');
0374:     }
0375:     
0376:     if (metrics.max_drawdown && Math.abs(metrics.max_drawdown) > 0.6) {
0377:         alerts.push('⚠️ High maximum drawdown - diversification recommended');
0378:     } else {
0379:         alerts.push('✅ Drawdown risk manageable');
0380:     }
0381:     
0382:     if (portfolio?.concentration_risk > 0.5) {
0383:         alerts.push('⚠️ Portfolio concentration risk elevated');
0384:     } else {
0385:         alerts.push('✅ Portfolio concentration within limits');
0386:     }
0387:     
0388:     alertsContainer.innerHTML = `
0389:         <h4>Risk Alerts</h4>
0390:         ${alerts.map(alert => `<div style="color: var(--theme-text-muted);">• ${alert}</div>`).join('')}
0391:     `;
0392: }
0393: 
0394: function updatePerformanceBreakdown(cache, memory) {
0395:     const breakdownContainer = document.querySelector('#tab-performance .panel-card div:nth-child(3)');
0396:     if (!breakdownContainer) return;
0397:     
0398:     const memEntries = Number(cache?.memory_cache_size);
0399:     const diskFiles = Number(cache?.disk_cache_files);
0400:     const hitRate = (Number.isFinite(memEntries) && Number.isFinite(diskFiles) && (memEntries + diskFiles) > 0)
0401:         ? ((memEntries / (memEntries + diskFiles)) * 100).toFixed(1) + '%'
0402:         : 'N/A';
0403:     const availGb = Number.isFinite(Number(memory?.available_system_mb)) ? (memory.available_system_mb / 1024).toFixed(1) + ' GB' : 'N/A';
0404:     const procEff = (typeof memory?.percent === 'number')
0405:         ? (memory.percent < 5 ? 'Excellent' : memory.percent < 10 ? 'Good' : 'Average')
0406:         : 'N/A';
0407: 
0408:     breakdownContainer.innerHTML = `
0409:         <h4>System Performance</h4>
0410:         <div style="display: grid; gap: 0.5rem;">
0411:             <div style="display: flex; justify-content: space-between;"><span>Memory Cache Hit Rate:</span><span style="color: var(--success);">${hitRate}</span></div>
0412:             <div style="display: flex; justify-content: space-between;"><span>Available Memory:</span><span>${availGb}</span></div>
0413:             <div style="display: flex; justify-content: space-between;"><span>Process Efficiency:</span><span>${procEff}</span></div>
0414:         </div>
0415:     `;
0416: }
0417: 
0418: function updateCycleIndicators(cycleData, phase) {
0419:     const indicatorsContainer = document.querySelector('#tab-cycles .panel-card div:nth-child(3)');
0420:     if (!indicatorsContainer) return;
0421:     
0422:     indicatorsContainer.innerHTML = `
0423:         <h4>Market Cycle Indicators</h4>
0424:         <div style="display: grid; gap: 0.5rem;">
0425:             <div style="display: flex; justify-content: space-between;"><span>Current Phase:</span><span>${phase.phase.replace('_', ' ')}</span></div>
0426:             <div style="display: flex; justify-content: space-between;"><span>Phase Color:</span><span style="color: ${phase.color};">●</span></div>
0427:             <div style="display: flex; justify-content: space-between;"><span>Score Range:</span><span>${Math.round(cycleData.score)}/100</span></div>
0428:         </div>
0429:     `;
0430: }
0431: 
0432:   // No longer needed; advanced metrics are filled inline above
0433: 
0434: // Error state functions
0435: function showErrorState(tabId) {
0436:     const panel = document.querySelector(`${tabId} .panel-card`);
0437:     if (panel) {
0438:         panel.innerHTML = `
0439:             <h3>⚠️ Data Loading Error</h3>
0440:             <p style="color: var(--theme-text-muted);">Unable to load data. Please check if the backend server is running.</p>
0441:             <button onclick="loadTabData('${tabId}')" class="btn btn-primary" style="background: var(--brand-primary); color: white; padding: 0.5rem 1rem; border: none; border-radius: 0.25rem; cursor: pointer;">Retry</button>
0442:         `;
0443:     }
0444: }
0445: 
0446: function showRiskError() {
0447:     showErrorState('#tab-risk');
0448: }
0449: 
0450: function showPerformanceError() {
0451:     showErrorState('#tab-performance'); 
0452: }
0453: 
0454: function showCycleError() {
0455:     showErrorState('#tab-cycles');
0456: }
0457: 
0458: function showMonitoringError() {
0459:     showErrorState('#tab-monitoring');
0460: }
0461: 
0462: // Auto-refresh every 5 minutes
0463: setInterval(() => {
0464:     const activeTab = document.querySelector('.tab-panel.active');
0465:     if (activeTab) {
0466:         cache.clear(); // Clear cache to force refresh
0467:         loadTabData(`#${activeTab.id}`);
0468:     }
0469: }, 5 * 60 * 1000);
0470: 
0471: console.debug('✅ Analytics Unified - Initialization complete');
0472: 
0473: 
0474: 
0475: 
