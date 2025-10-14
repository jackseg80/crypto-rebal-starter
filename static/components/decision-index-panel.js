/**
 * Decision Index Panel v5 - Split View Design avec Glassmorphism léger
 *
 * Layout: 2 colonnes
 * - Gauche: Score DI + barre contributions + trend + regime
 * - Droite: Mini-cards Cycle/OnChain/Risk + gouvernance
 *
 * Performance: Optimisé pour systèmes moins performants
 * - Animations GPU-accelerated uniquement (transform, opacity)
 * - Backdrop-filter léger (10px blur)
 * - Pas d'animations continues
 *
 * ⚠️ Chart.js + chartjs-plugin-datalabels doivent être chargés AVANT
 */

// Instances Chart.js (cleanup)
let chartInstances = {
  stacked: null
};

// Debounce timeout
let refreshTimeout = null;

// État du popover d'aide
let helpPopoverState = {
  isOpen: false,
  lastFocusedElement: null
};

/**
 * Détermine le niveau de couleur d'un score (sémantique positive: plus haut = meilleur)
 */
function getScoreLevel(score) {
  if (score == null || isNaN(score)) return 'medium';
  const s = Number(score);
  if (s >= 75) return 'excellent';
  if (s >= 60) return 'good';
  if (s >= 45) return 'medium';
  if (s >= 30) return 'warning';
  return 'danger';
}

/**
 * Palette couleurs - Lire depuis CSS (avec fallback)
 */
function getColors() {
  const root = document.documentElement;
  const getVar = (name, fallback) => {
    const value = getComputedStyle(root).getPropertyValue(name)?.trim();
    return (value && value !== '') ? value : fallback;
  };

  return {
    cycle: getVar('--di-color-cycle', '#7aa2f7'),
    onchain: getVar('--di-color-onchain', '#2ac3de'),
    risk: getVar('--di-color-risk', '#f7768e')
  };
}

/**
 * Helper: valeur sûre (fallback 0)
 */
function _safe(val) {
  return (typeof val === 'number' && Number.isFinite(val)) ? val : 0;
}

/**
 * Helper: arrondi à N décimales
 */
function _round(val, decimals = 1) {
  const v = _safe(val);
  return Number(v.toFixed(decimals));
}

/**
 * Calcule contributions relatives (formule: (w×s)/Σ)
 * ⚠️ PAS d'inversion Risk
 */
function calculateRelativeContributions(weights, scores) {
  const epsilon = 1e-6;

  const clampedScores = {
    cycle: Math.max(0, Math.min(100, scores.cycle || 0)),
    onchain: Math.max(0, Math.min(100, scores.onchain || 0)),
    risk: Math.max(0, Math.min(100, scores.risk || 0))
  };

  const raw = {
    cycle: (weights.cycle || 0) * clampedScores.cycle,
    onchain: (weights.onchain || 0) * clampedScores.onchain,
    risk: (weights.risk || 0) * clampedScores.risk
  };

  const sum = Object.values(raw).reduce((a, b) => a + b, 0) || epsilon;

  return {
    cycle: (raw.cycle / sum) * 100,
    onchain: (raw.onchain / sum) * 100,
    risk: (raw.risk / sum) * 100,
    raw: raw
  };
}

/**
 * Calcule fenêtre de trend (Δ, σ, état) sur historique DI
 */
function computeTrendWindow(history, win = 7) {
  const arr = Array.isArray(history) ? history.map(h => (h?.di ?? h) ?? 0) : [];
  const n = Math.min(win, arr.length);
  if (n < 2) return { ok: false, n, delta: 0, sigma: 0, state: 'Insuffisant', series: arr.slice(-n) };
  const series = arr.slice(-n);
  const first = series[0];
  const last = series[series.length - 1];
  const delta = last - first;
  const avg = series.reduce((a, b) => a + b, 0) / series.length;
  const varg = series.reduce((a, b) => a + (b - avg) ** 2, 0) / series.length;
  const sigma = Math.sqrt(varg);
  let state = 'Stable';
  if (delta > 1) state = 'Haussier';
  else if (delta < -1) state = 'Baissier';
  return { ok: true, n, delta, sigma, state, series };
}

/**
 * Génère SVG sparkline
 */
function renderSparkline(series, width = 260, height = 36, dashed = false, delta = 0) {
  if (!Array.isArray(series) || series.length === 0) {
    return `<div class="spark-placeholder">—</div>`;
  }
  const n = series.length;
  if (n === 1) {
    return `<div class="spark-placeholder" title="1 point (min 2 requis)">●</div>`;
  }

  const validSeries = series.filter(v => typeof v === 'number' && Number.isFinite(v));
  if (validSeries.length < 2) {
    return `<div class="spark-placeholder" title="Données invalides">—</div>`;
  }

  const min = Math.min(...validSeries);
  const max = Math.max(...validSeries);
  const span = (max - min) || 1;
  const px = (i) => (i / (validSeries.length - 1)) * (width - 2) + 1;
  const py = (v) => height - ((v - min) / span) * (height - 2) - 1;
  const d = validSeries.map((v, i) => `${i === 0 ? 'M' : 'L'} ${px(i).toFixed(1)} ${py(v).toFixed(1)}`).join(' ');

  let colorClass = 'neutral';
  if (delta > 0.5) colorClass = 'up';
  else if (delta < -0.5) colorClass = 'down';

  const cls = dashed ? `spark-line dashed ${colorClass}` : `spark-line ${colorClass}`;
  return `
    <svg class="spark" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <path d="${d}" class="${cls}"/>
    </svg>`;
}

/**
 * Render barre empilée Chart.js (SANS axes/grilles)
 */
function renderStackedBar(canvas, contributions, weights, scores, opts = {}) {
  const ctx = canvas.getContext('2d');
  const colors = getColors();

  const config = {
    type: 'bar',
    data: {
      labels: ['Contributions'],
      datasets: [
        {
          label: 'Cycle',
          data: [contributions.cycle],
          backgroundColor: colors.cycle,
          borderWidth: 0,
          _meta: {
            score: Math.round(scores.cycle || 0),
            weight: weights.cycle || 0,
            wxs: contributions.raw.cycle
          }
        },
        {
          label: 'On-Chain',
          data: [contributions.onchain],
          backgroundColor: colors.onchain,
          borderWidth: 0,
          _meta: {
            score: Math.round(scores.onchain || 0),
            weight: weights.onchain || 0,
            wxs: contributions.raw.onchain
          }
        },
        {
          label: 'Risk',
          data: [contributions.risk],
          backgroundColor: colors.risk,
          borderWidth: 0,
          _meta: {
            score: Math.round(scores.risk || 0),
            weight: weights.risk || 0,
            wxs: contributions.raw.risk
          }
        }
      ]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          stacked: true,
          display: false,
          min: 0,
          max: 100,
          grid: { display: false }
        },
        y: {
          stacked: true,
          display: false,
          grid: { display: false }
        }
      },
      plugins: {
        legend: {
          display: false
        },
        datalabels: {
          display: (context) => {
            if (!context.parsed || typeof context.parsed.x !== 'number') {
              return false;
            }
            const value = context.parsed.x;
            const chart = context.chart;
            const meta = chart.getDatasetMeta(context.datasetIndex);
            const bar = meta.data[context.dataIndex];
            const segmentWidth = bar ? bar.width : 0;
            return value >= 10 && segmentWidth >= 52;
          },
          color: '#ffffff',
          font: { weight: 600, size: 11 },
          textShadowColor: 'rgba(0, 0, 0, 0.5)',
          textShadowBlur: 4,
          formatter: (value, context) => {
            return `${context.dataset.label} ${value.toFixed(1)}%`;
          },
          anchor: 'center',
          align: 'center',
          clamp: true,
          offset: 0
        },
        tooltip: {
          callbacks: {
            title: () => '',
            label: (context) => {
              const pillar = context.dataset.label;
              const pct = (context.parsed.x ?? 0).toFixed(1);
              const m = context.dataset._meta || {};
              const score = m.score != null ? m.score : '?';
              const weight = m.weight != null ? m.weight.toFixed(2) : '?';
              const wxs = m.wxs != null ? m.wxs.toFixed(1) : '?';
              return `${pillar} — ${pct}% (score ${score}, w ${weight}, w×s ${wxs})`;
            }
          }
        }
      },
      animation: {
        duration: 300
      }
    }
  };

  return new Chart(ctx, config);
}

/**
 * Génère breakdown line (scores avec typographie uniforme)
 */
function renderBreakdown(weights, scores) {
  const s = scores || {};

  return `
    <div class="di-breakdown">
      <span class="lbl lbl-cycle">Cycle <b>${_round(s.cycle || 0)}</b></span>
      <span class="dot">·</span>
      <span class="lbl lbl-oc">On-Chain <b>${_round(s.onchain || 0, 1)}</b></span>
      <span class="dot">·</span>
      <span class="lbl lbl-risk">Risk <b>${_round(s.risk || 0)}</b></span>
    </div>`;
}

/**
 * Mapping phase name → index (0=Bull, 1=Neutral, 2=Bear)
 */
function phaseToIndex(name) {
  const n = String(name || '').toLowerCase();
  if (n.includes('euphor') || n.includes('bull') || n.includes('risk-on') || n.includes('expansion')) return 0;
  if (n.includes('bear') || n.includes('risk-off') || n.includes('prudence')) return 2;
  return 1;
}

/**
 * Génère regime ribbon (3 barres: Euphorie/Neutral/Bearish)
 */
function renderRegimeRibbon(meta, regimeHistoryRaw) {
  const rHist = Array.isArray(regimeHistoryRaw) ? regimeHistoryRaw.slice(-5) : [];
  let activeIdx = phaseToIndex(meta?.phase);

  if (rHist.length > 0) {
    const actives = rHist.filter(x => (x?.active ?? x?.bull ?? x?.risk_on ?? false)).length;
    const level = actives >= 4 ? 0 : (actives <= 1 ? 2 : 1);
    activeIdx = level;
  }

  const labels = ['Euphorie', 'Neutral', 'Bearish'];
  const bars = labels.map((lab, idx) => {
    const on = idx === activeIdx ? 'on' : '';
    return `
      <div class="rg-item">
        <div class="rg-label ${on}">${lab}</div>
        <div class="rg-bar ${on}"></div>
      </div>`;
  }).join('');

  return `
    <div class="regime-section">
      <div class="reg-title">REGIME</div>
      <div class="rg-row">${bars}</div>
    </div>`;
}

/**
 * Génère la colonne GAUCHE (DI + barre + trend + regime)
 */
function renderLeftColumn(data, contribs, tw, trendDelta) {
  const breakdown = renderBreakdown(data.weights, data.scores);
  const dashed = !tw.ok;
  const trendSpark = renderSparkline(tw.series, 280, 40, dashed, trendDelta);

  const deltaBadge = `${trendDelta === 0 ? '→' : (trendDelta > 0 ? '↗' : '↘')} ${trendDelta > 0 ? '+' : ''}${trendDelta} pts`;
  const toneSigma = tw.sigma < 1 ? 'ok' : tw.sigma <= 2 ? 'warn' : 'danger';

  const trendRight = tw.ok
    ? `
        <span class="pill pill--${trendDelta > 1 ? 'ok' : (trendDelta < -1 ? 'danger' : 'warn')}">${deltaBadge}</span>
        <span class="pill pill--${toneSigma}">σ ${tw.sigma}</span>
        <span class="pill pill--${tw.state === 'Haussier' ? 'ok' : (tw.state === 'Baissier' ? 'danger' : 'warn')}">${tw.state}</span>
      `
    : '';

  const trendLeft = tw.ok
    ? trendSpark
    : `
        <div style="display: flex; align-items: center; gap: 12px;">
          ${trendSpark}
          <span class="pill pill--muted pill--ellipsis" style="margin-left: 8px;">… Historique insuffisant</span>
        </div>
      `;

  const regimeRibbon = renderRegimeRibbon(data.meta, data.regimeHistory);

  return `
    <div class="di-left">
      <div class="di-header">
        <div class="di-title-row">
          <div class="di-title">DECISION INDEX</div>
          <button class="di-help-trigger" aria-label="Aide Decision Index" aria-expanded="false" type="button">ℹ️</button>
        </div>
        <div class="di-status-badges">
          <span class="status-badge status-badge--${data.meta.live ? 'live' : 'muted'}">${data.meta.live ? '● LIVE' : '○ OFF'}</span>
          <span class="status-badge status-badge--muted">${data.meta.source || 'N/A'}</span>
        </div>
      </div>

      <div class="di-score-container">
        <div class="di-score" data-score-level="${getScoreLevel(data.di)}">${Math.round(data.di)}</div>
        <div class="di-score-label">${getScoreLevel(data.di) === 'excellent' ? 'Excellent ✨' : getScoreLevel(data.di) === 'good' ? 'Bon' : getScoreLevel(data.di) === 'medium' ? 'Moyen' : getScoreLevel(data.di) === 'warning' ? 'Attention' : 'Critique'}</div>
      </div>

      <div class="di-progress">
        <canvas id="${data.containerId}-stack-chart" class="di-stack-canvas"></canvas>
      </div>

      ${breakdown}

      <div class="trend-section">
        <div class="trend-title">TREND (${tw.n}j)</div>
        <div class="trend-grid">
          <div class="trend-left">${trendLeft}</div>
          <div class="trend-right">${trendRight}</div>
        </div>
      </div>

      ${regimeRibbon}
    </div>
  `;
}

/**
 * Génère la colonne DROITE (mini-cards piliers + gouvernance)
 */
function renderRightColumn(data) {
  const s = data.scores || {};
  const m = data.meta || {};

  const scoreColor = (score) => {
    if (score >= 70) return 'var(--success)';
    if (score >= 40) return 'var(--warning)';
    return 'var(--danger)';
  };

  const cyclePhase = m.cycle_phase || m.phase || '—';
  const cycleMonths = m.cycle_months || null;
  const cycleConf = m.cycle_confidence ? Math.round(m.cycle_confidence * 100) : null;

  const onchainCritiques = m.onchain_critiques || 0;
  const onchainConf = m.onchain_confidence ? Math.round(m.onchain_confidence * 100) : null;

  const riskVar = m.risk_var95 || null;
  const riskBudget = m.risk_budget || null;

  // Sentiment & Régime
  const regimeName = m.phase || 'Neutral';
  const regimeEmoji = m.regime_emoji || '🤖';
  const sentimentFG = m.sentiment_fg || '—';
  const sentimentInterpretation = m.sentiment_interpretation || 'Neutre';

  // Déterminer la couleur du sentiment selon sa valeur
  const sentimentValue = typeof m.sentiment_fg === 'number' ? m.sentiment_fg :
                         (typeof sentimentFG === 'string' && !isNaN(parseInt(sentimentFG)) ? parseInt(sentimentFG) : 50);
  const sentimentColor = sentimentValue >= 75 ? 'var(--danger)' :
                         sentimentValue >= 55 ? 'var(--warning)' :
                         sentimentValue >= 45 ? 'var(--info)' :
                         'var(--success)';

  return `
    <div class="di-right">
      <div class="pillar-card pillar-card--cycle">
        <div class="pillar-icon">🔄</div>
        <div class="pillar-content">
          <div class="pillar-name">Cycle ${cycleConf ? `<span class="conf-badge">${cycleConf}%</span>` : ''}</div>
          <div class="pillar-score" style="color: ${scoreColor(s.cycle || 0)};">${Math.round(s.cycle || 0)}</div>
          <div class="pillar-detail">${cyclePhase}</div>
          ${cycleMonths ? `<div class="pillar-subdetail">${Math.round(cycleMonths)}m post-halving</div>` : ''}
        </div>
      </div>

      <div class="pillar-card pillar-card--onchain">
        <div class="pillar-icon">🔗</div>
        <div class="pillar-content">
          <div class="pillar-name">On-Chain ${onchainConf ? `<span class="conf-badge">${onchainConf}%</span>` : ''}</div>
          <div class="pillar-score" style="color: ${scoreColor(s.onchain || 0)};">${Math.round(s.onchain || 0)}</div>
          <div class="pillar-detail">Critiques: ${onchainCritiques}</div>
        </div>
      </div>

      <div class="pillar-card pillar-card--risk">
        <div class="pillar-icon">🛡️</div>
        <div class="pillar-content">
          <div class="pillar-name">Risk</div>
          <div class="pillar-score" style="color: ${scoreColor(s.risk || 0)};">${Math.round(s.risk || 0)}</div>
          ${riskVar ? `<div class="pillar-detail">VaR95: ${Math.round(Math.abs(riskVar) * 1000) / 10}%</div>` : '<div class="pillar-detail">—</div>'}
          ${riskBudget ? `<div class="pillar-subdetail">Risky: ${riskBudget.risky}% • Stables: ${riskBudget.stables}%</div>` : ''}
        </div>
      </div>

      <div class="pillar-card pillar-card--sentiment">
        <div class="pillar-icon">${regimeEmoji}</div>
        <div class="pillar-content">
          <div class="pillar-name">Sentiment & Régime</div>
          <div class="pillar-score" style="color: ${sentimentColor}; font-size: clamp(1.2rem, 2.5vw, 1.5rem);">${regimeName}</div>
          <div class="pillar-detail">Fear & Greed: ${sentimentFG}</div>
          <div class="pillar-subdetail">${sentimentInterpretation}</div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Génère contenu du popover d'aide
 */
function renderHelpContent() {
  return `
    <div class="di-help" style="display: none;" role="dialog" aria-labelledby="di-help-title" aria-modal="true">
      <div class="di-help-header">
        <h3 id="di-help-title">Comment lire le Decision Index</h3>
        <button class="di-help-close" aria-label="Fermer l'aide" type="button">×</button>
      </div>
      <div class="di-help-body">
        <section>
          <h4>📊 Score DI (0-100)</h4>
          <p>Composite des 3 piliers (Cycle, On-Chain, Risk). Plus le score est élevé, plus le contexte est favorable pour augmenter l'exposition risquée.</p>
        </section>
        <section>
          <h4>📈 Barre de contributions</h4>
          <p>Montre la part relative de chaque pilier dans le calcul du DI. La largeur reflète (poids × score).</p>
        </section>
        <section>
          <h4>🔄 Piliers</h4>
          <p><b>Cycle:</b> Phase du marché (halving, expansion, contraction).<br>
          <b>On-Chain:</b> Signaux blockchain (metrics critiques).<br>
          <b>Risk:</b> Volatilité, VaR, budget allocation.</p>
        </section>
        <section>
          <h4>📉 Trend</h4>
          <p>Évolution récente du DI. Δ = variation 7j, σ = volatilité.</p>
        </section>
        <section>
          <h4>⚙️ Gouvernance</h4>
          <p><b>Cap actif:</b> Limite de mouvement quotidien.<br>
          <b>Contradiction:</b> Divergence entre signaux (élevé = incertitude).</p>
        </section>
      </div>
    </div>
  `;
}

/**
 * Monte le popover d'aide
 */
function mountHelpPopover(rootEl) {
  const trigger = rootEl.querySelector('.di-help-trigger');
  const popover = rootEl.querySelector('.di-help');

  if (!trigger || !popover) return;

  const togglePopover = (show) => {
    if (show) {
      helpPopoverState.isOpen = true;
      helpPopoverState.lastFocusedElement = document.activeElement;
      popover.style.display = 'block';
      trigger.setAttribute('aria-expanded', 'true');

      setTimeout(() => {
        const firstFocusable = popover.querySelector('button, [href], [tabindex]:not([tabindex="-1"])');
        if (firstFocusable) firstFocusable.focus();
      }, 50);
    } else {
      helpPopoverState.isOpen = false;
      popover.style.display = 'none';
      trigger.setAttribute('aria-expanded', 'false');

      if (helpPopoverState.lastFocusedElement) {
        helpPopoverState.lastFocusedElement.focus();
      }
    }
  };

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    togglePopover(!helpPopoverState.isOpen);
  });

  const closeBtn = popover.querySelector('.di-help-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => togglePopover(false));
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && helpPopoverState.isOpen) {
      togglePopover(false);
    }
  });

  document.addEventListener('click', (e) => {
    if (helpPopoverState.isOpen && !popover.contains(e.target) && e.target !== trigger) {
      togglePopover(false);
    }
  });

  popover.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      const focusables = Array.from(popover.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      ));

      if (focusables.length === 0) return;

      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  });
}

/**
 * Render interne (sans debounce)
 */
function _renderDIPanelInternal(container, data, opts = {}) {
  if (!container) {
    debugLogger.error('❌ DI Panel: container element not found');
    return;
  }

  // Vérifier Chart.js
  if (!window.Chart) {
    debugLogger.error('❌ Chart.js not loaded');
    return;
  }

  // Cleanup Chart.js
  if (chartInstances.stacked) {
    chartInstances.stacked.destroy();
    chartInstances.stacked = null;
  }

  // Calculer contributions
  const contribs = calculateRelativeContributions(data.weights, data.scores);

  // Calculer trend
  const tw = computeTrendWindow(data.history, 7);
  const trendDelta = _round(tw.delta, 1);

  // Ajouter containerId pour canvas ID
  data.containerId = container.id;

  // Render HTML
  const leftCol = renderLeftColumn(data, contribs, tw, trendDelta);
  const rightCol = renderRightColumn(data);

  const timeStr = (() => {
    try { return data.meta.updated ? new Date(data.meta.updated).toLocaleTimeString() : ''; } catch { return ''; }
  })();

  container.innerHTML = `
    <div class="di-panel-v5">
      <div class="di-split-layout">
        ${leftCol}
        ${rightCol}
      </div>

      <div class="di-footer-compact">
        ${timeStr ? `Dernière mise à jour: ${timeStr}` : ''}
      </div>

      ${renderHelpContent()}
    </div>
  `;

  // Render chart
  const stackCanvas = document.getElementById(`${container.id}-stack-chart`);
  if (stackCanvas) {
    chartInstances.stacked = renderStackedBar(stackCanvas, contribs, data.weights, data.scores, opts);
  }

  // Monter popover
  mountHelpPopover(container);
}

/**
 * Fonction principale - Render le panneau Decision Index
 */
export function renderDecisionIndexPanel(container, data, opts = {}) {
  clearTimeout(refreshTimeout);
  refreshTimeout = setTimeout(() => {
    _renderDIPanelInternal(container, data, opts);
  }, 150);
}

/**
 * Cleanup global
 */
export function destroyDIPanelCharts() {
  if (chartInstances.stacked) {
    chartInstances.stacked.destroy();
    chartInstances.stacked = null;
  }
}

/**
 * Helper pour initialiser Chart.js (idempotent)
 */
export async function ensureChartJSLoaded() {
  if (window.Chart) {
    return true;
  }

  debugLogger.warn('⚠️ Chart.js not found - attempting to load from CDN...');

  return new Promise((resolve) => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
    script.onload = () => {
      debugLogger.debug('✅ Chart.js loaded dynamically');
      resolve(true);
    };
    script.onerror = () => {
      debugLogger.error('❌ Failed to load Chart.js from CDN');
      resolve(false);
    };
    document.head.appendChild(script);
  });
}
