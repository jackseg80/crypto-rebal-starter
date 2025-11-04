/**
 * Risk Dashboard - Risk Overview Tab (Complete Implementation)
 * Migrated from risk-dashboard.html (Oct 2025)
 */

// ====== Imports ======
import {
  safeFixed,
  formatMoney,
  formatPercent,
  formatRelativeTime,
  scoreToRiskLevel,
  pickScoreColor,
  getScoreInterpretation,
  getMetricHealth,
  showLoading,
  showError
} from './risk-utils.js';

import { fetchAndComputeCCS, DEFAULT_CCS_WEIGHTS } from './signals-engine.js';

// ====== Constants ======
const analysisDays = 365;
const corrDays = 90;

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

// ====== Tooltip Management ======
let $tip, $tipTitle, $tipBody;

function initTooltips() {
  $tip = document.querySelector('.risk-tooltip');
  $tipTitle = $tip?.querySelector('.tooltip-title');
  $tipBody = $tip?.querySelector('.tooltip-body');
}

function showTip(title, body, x, y) {
  if (!$tip) initTooltips();
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

// ====== Helper Functions ======
const pct = v => (v == null || isNaN(v) ? 'N/A' : (v * 100).toFixed(2) + '%');
const num = v => (v == null || isNaN(v) ? 'N/A' : Number(v).toFixed(2));

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

// ====== API Functions ======
async function fetchRiskData() {
  try {
    // Get the configured data source dynamically
    const dataSource = globalConfig.get('data_source');
    const apiBaseUrl = globalConfig.get('api_base_url');
    const minUsd = globalConfig.get('min_usd_threshold');

    // 🔧 FIX: Read csv_selected_file from window.userSettings (updated by WealthContextBar)
    const csvFile = window.userSettings?.csv_selected_file || 'latest';
    const saxoFile = window.userSettings?.saxo_selected_file || 'latest';

    console.debug(`🔍 Risk Overview using data source: ${dataSource}, csvFile: '${csvFile}', saxoFile: '${saxoFile}'`);

    // Utiliser directement les données de balance et calculer le risque côté client
    const balanceResult = await window.globalConfig.apiRequest('/balances/current', {
      params: { source: dataSource, min_usd: minUsd }
    });

    // Use the real backend endpoint for risk dashboard
    // ✅ Inclure source et user_id pour isolation multi-tenant
    // ✅ NOUVEAU (Phase 5.5): Shadow Mode V2 + Dual Window
    // 🔧 FIX: Add _csv_hint to force backend recalculation when CSV changes
    const cacheBuster = csvFile !== 'latest' ? csvFile : Date.now().toString().substring(0, 10);

    console.debug(`🔍 fetchRiskData - calling /api/risk/dashboard with _csv_hint: '${cacheBuster}'`);

    const apiResult = await window.globalConfig.apiRequest('/api/risk/dashboard', {
      params: {
        source: dataSource,
        min_usd: minUsd,
        price_history_days: analysisDays,
        lookback_days: corrDays,
        risk_version: 'v2_active',  // 🆕 V2 Active: V2 est autoritaire (Oct 2025)
        use_dual_window: true,       // Dual-window metrics actives
        _csv_hint: cacheBuster        // 🔧 Hint for backend cache: changes when CSV changes
      }
    });

    // 🔍 DEBUG: Log la réponse brute avec nouveaux champs V2
    console.debug('🔍 Raw API response (Shadow Mode V2):', JSON.stringify({
      // Legacy scores
      sharpe_legacy: apiResult?.risk_metrics?.sharpe_ratio,
      var95: apiResult?.risk_metrics?.var_95_1d,
      risk_score_legacy: apiResult?.risk_metrics?.risk_score,
      structural_legacy: apiResult?.risk_metrics?.risk_score_structural,
      window_used: apiResult?.risk_metrics?.window_used,
      // V2 Shadow Mode info (🔧 FIX: Chemin correct!)
      risk_version_info: apiResult?.risk_metrics?.risk_version_info ? {
        active_version: apiResult.risk_metrics.risk_version_info.active_version,
        risk_score_v2: apiResult.risk_metrics.risk_version_info.risk_score_v2,
        sharpe_v2: apiResult.risk_metrics.risk_version_info.sharpe_v2,
        portfolio_structure_score: apiResult.risk_metrics.risk_version_info.portfolio_structure_score,
        integrated_structural_legacy: apiResult.risk_metrics.risk_version_info.integrated_structural_legacy
      } : null
    }));

    // Vérifier que apiResult est valide avant de l'utiliser
    if (!apiResult || !apiResult.risk_metrics) {
      throw new Error('Invalid API response structure');
    }

    // Inclure les balances pour calculer concentration/stablecoins côté UI
    try {
      apiResult.balances = Array.isArray(balanceResult?.items) ? balanceResult.items : [];
    } catch (_) { /* ignore */ }

    const m = apiResult.risk_metrics;
    debugLogger.debug(`🧪 SHADOW V2 - Risk metrics from API: VaR 95%: ${(m.var_95_1d * 100).toFixed(2)}%, Sharpe: ${m.sharpe_ratio.toFixed(2)}, Risk Score: ${m.risk_score} (authoritative), Structural: ${m.risk_score_structural || 'N/A'}, Window: ${m.window_used?.actual_data_points || '?'} pts, risk_version_info: ${m.risk_version_info ? 'PRESENT ✅' : 'MISSING ❌'}`);

    // The backend already provides the correct structure, just return it
    return apiResult;
  } catch (error) {
    debugLogger.warn('Risk API unavailable:', error);
    return {
      success: false,
      message: 'Backend de risque indisponible. Assurez-vous que le serveur backend est démarré.',
      error_type: 'connection_error'
    };
  }
}

// ====== Recommendations Generation ======
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

// ====== Main Render Function ======
export async function renderRiskOverview(container) {
  debugLogger.debug('🚀 Rendering Risk Overview tab (complete module)');

  try {
    // Show loading state
    showLoading(container, 'Loading risk data...');

    // Fetch risk data
    const data = await fetchRiskData();

    if (!data || !data.risk_metrics || !data.correlation_metrics || !data.portfolio_summary) {
      showError(container, 'Incomplete data received from API');
      return;
    }

    // Render the dashboard
    renderRiskDashboard(container, data);

    debugLogger.debug('✅ Risk Overview tab rendered successfully');
  } catch (error) {
    debugLogger.error('❌ Failed to render Risk Overview:', error);
    showError(container, 'Failed to load risk dashboard: ' + error.message);
  }
}

function renderRiskDashboard(container, data) {
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

  // Prépare: HTML recommandations et alertes pour la section top-summary
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
        <div>Vue d'ensemble risques & recommandations</div>
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

    <!-- Portfolio Summary -->
    <div class="risk-card">
      <h3>📊 Portfolio Summary</h3>
      <div class="metric-row">
        <span class="metric-label">Total Value:</span>
        <span class="metric-value">${formatMoney(p.total_value)}</span>
      </div>
      <div class="metric-row">
        <span class="metric-label">Number of Assets:</span>
        <span class="metric-value">${p.num_assets}</span>
      </div>
      <div class="metric-row">
        <span class="metric-label">Data Confidence</span>
        <span class="metric-value">${safeFixed((p.confidence_level || 0) * 100, 1)}%</span>
      </div>
    </div>

    <div class="risk-grid">
      <!-- Risk Score Card -->
      <div class="risk-card">
        <h3>🎯 Risk Score <span style="font-size:.8rem; color: var(--theme-text); opacity:.7; font-weight:500; margin-left:.5rem;"><br>Robustness Indicator [0-100]</span></h3>

        <!-- Risk Score Principal -->
        <div class="metric-row">
          <span class="metric-label">Risk Score</span>
          <span class="metric-value hinted" data-key="risk_score" data-value="${m.risk_score}" data-score="risk-display" style="color: ${pickScoreColor(m.risk_score)}">
            ${safeFixed(m.risk_score, 1)}/100
          </span>
          <button class="btn-breakdown-toggle" onclick="window.toggleBreakdown?.('risk-score-breakdown')" title="Voir détail des pénalités" aria-label="Afficher le détail du calcul du Risk Score" style="margin-left: 8px; padding: 2px 8px; font-size: 0.75em; background: rgba(125, 207, 255, 0.15); border: 1px solid var(--brand-primary); border-radius: 4px; color: var(--brand-primary); cursor: pointer;">
            🔍 Détail
          </button>
        </div>

        <!-- Breakdown Panel -->
        <div id="risk-score-breakdown" class="breakdown-panel" style="display: none; margin: 8px 0; padding: 12px; background: rgba(30, 30, 46, 0.6); border-radius: 8px; border: 1px solid rgba(125, 207, 255, 0.2); font-size: 0.85em;">
          <div class="breakdown-header" style="font-weight: 600; color: var(--brand-primary); margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <span>📊 Détail du calcul (Base = 50) ${m.risk_version_info ? `— ${m.risk_version_info.active_version === 'v2' ? 'V2' : 'Legacy'}` : ''}</span>
            <button onclick="window.toggleBreakdown?.('risk-score-breakdown')" style="background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 1.2em;" aria-label="Fermer">×</button>
          </div>
          <div class="breakdown-table" style="display: flex; flex-direction: column; gap: 4px;">
            <div class="breakdown-row breakdown-base" style="display: grid; grid-template-columns: 1fr auto auto; gap: 8px; padding: 4px; background: rgba(125, 207, 255, 0.05); border-radius: 4px;">
              <span class="breakdown-label" style="color: var(--text-secondary);">Base neutre</span>
              <span class="breakdown-value" style="color: var(--text-primary); font-weight: 600;">+50.0</span>
              <span class="breakdown-cumul" style="color: var(--brand-primary); font-weight: 600; min-width: 50px; text-align: right;">50.0</span>
            </div>
            ${(() => {
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

        <!-- Risk Level -->
        <div class="metric-row">
          <span class="metric-label">Risk Level</span>
          <span class="risk-level risk-${scoreToRiskLevel(m.risk_score)}">${scoreToRiskLevel(m.risk_score).replace('-', ' ').toUpperCase()}</span>
        </div>

        <div class="metric-benchmark">
          📊 <strong>Benchmarks:</strong> Très robuste (≥80), Robuste (≥65), Modéré (≥50), Fragile (≥35)
        </div>
      </div>

      <!-- VaR/CVaR -->
      <div class="risk-card">
        <h3>📉 Value at Risk (VaR) <span style="font-size:.8rem; color: var(--theme-text); opacity:.7; font-weight:500; margin-left:.5rem;"><br>lookback 30j (VaR), 60j (CVaR)</span></h3>
        <div class="metric-row">
          <span class="metric-label">VaR 95% (1 day)</span>
          <span class="metric-value hinted" data-key="var95_1d" data-value="${m.var_95_1d}" style="color: ${getMetricHealth('var_95_1d', m.var_95_1d).color}">
            ${formatPercent(m.var_95_1d)}
          </span>
        </div>
        <div class="metric-interpretation">
          💡 ${getMetricHealth('var_95_1d', m.var_95_1d).interpretation}
        </div>
        <div class="metric-row">
          <span class="metric-label">VaR 99% (1 day)</span>
          <span class="metric-value hinted" data-key="var99_1d" data-value="${m.var_99_1d}" style="color: ${getMetricHealth('var_99_1d', m.var_99_1d).color}">
            ${formatPercent(m.var_99_1d)}
          </span>
        </div>
        <div class="metric-interpretation">
          💡 ${getMetricHealth('var_99_1d', m.var_99_1d).interpretation}
        </div>
        <div class="metric-row">
          <span class="metric-label">CVaR 95% (1 day)</span>
          <span class="metric-value hinted" data-key="cvar95_1d" data-value="${m.cvar_95_1d}">${formatPercent(m.cvar_95_1d)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">CVaR 99% (1 day)</span>
          <span class="metric-value hinted" data-key="cvar99_1d" data-value="${m.cvar_99_1d}">${formatPercent(m.cvar_99_1d)}</span>
        </div>
        <div class="metric-benchmark">
          📊 <strong>Benchmarks crypto:</strong> Conservateur: -4%, Typique: -7%, Agressif: -12%
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

      <!-- Drawdowns -->
      <div class="risk-card">
        <h3>📊 Drawdown Analysis <span style="font-size:.8rem; color: var(--theme-text); opacity:.7; font-weight:500; margin-left:.5rem;"><br>lookback 180j</span></h3>
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
        <div class="metric-benchmark">
          📊 <strong>Crypto historique:</strong> Bon: -30%, Typique: -50%, Extrême: -70%+
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
  `;

  // Après rendu : brancher les info-bulles et verdicts
  setTimeout(() => decorateRiskTooltips(container), 100);
}

// ====== Tooltip Decoration ======
function decorateRiskTooltips(container) {
  // Initialize tooltips if not already done
  initTooltips();

  // === Attache dynamique pour les métriques ===
  container.querySelectorAll('.hinted[data-key]').forEach(el => {
    const key = el.getAttribute('data-key');

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
  });
}

// ====== Exports ======
export default {
  renderRiskOverview
};
