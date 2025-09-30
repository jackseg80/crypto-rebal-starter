/**
 * Decision Index Panel - Composant visuel OPTIMISÉ v2
 *
 * Améliorations:
 * - Palette vive (contraste dark mode)
 * - Charts sans axes/grilles (progress bar + sparkline)
 * - Placeholder si historique < 3 points
 * - Micropuces métriques (Cycle/OnChain/Risk avec w×s)
 * - Layout compact + footnote alignée droite
 *
 * ⚠️ Chart.js doit être chargé AVANT ce module
 */

// Instances Chart.js (cleanup)
let chartInstances = {
  stacked: null,
  sparkline: null
};

// Debounce timeout
let refreshTimeout = null;

/**
 * Palette couleurs - Lire depuis CSS (avec fallback)
 */
function getColors() {
  // Lire les variables CSS (fallback sur couleurs vives si absent)
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
 * Calcule contributions relatives (formule: (w×s)/Σ)
 * ⚠️ PAS d'inversion Risk
 */
function calculateRelativeContributions(weights, scores) {
  const epsilon = 1e-6;

  // Clamp scores [0, 100]
  const clampedScores = {
    cycle: Math.max(0, Math.min(100, scores.cycle || 0)),
    onchain: Math.max(0, Math.min(100, scores.onchain || 0)),
    risk: Math.max(0, Math.min(100, scores.risk || 0))  // ✅ PAS d'inversion
  };

  // Valeurs brutes (w × s)
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
    raw: raw  // Pour tooltips + micropuces
  };
}

/**
 * Génère badges avec couleurs conditionnelles
 */
function renderBadges(meta) {
  const badges = [];

  // 1. Confiance
  const confPct = Math.round((meta.confidence || 0) * 100);
  const confClass = confPct < 40 ? 'warning' : confPct < 70 ? 'neutral' : 'success';
  badges.push(
    `<span class="di-badge di-badge-${confClass}" title="Niveau de certitude: ${confPct}%">` +
    `Conf ${confPct}%</span>`
  );

  // 2. Contradiction
  const contraPct = Math.round((meta.contradiction || 0) * 100);
  const contraClass = contraPct < 30 ? 'success' : contraPct < 50 ? 'warning' : 'danger';
  badges.push(
    `<span class="di-badge di-badge-${contraClass}" title="Divergence entre sources: ${contraPct}%">` +
    `Contrad ${contraPct}%</span>`
  );

  // 3. Cap
  let capPct = meta.cap;
  if (typeof capPct === 'number' && Number.isFinite(capPct)) {
    if (capPct <= 1) capPct = Math.round(capPct * 100);
    badges.push(
      `<span class="di-badge di-badge-info" title="Cap quotidien gouvernance">` +
      `Cap ${capPct}%</span>`
    );
  } else {
    badges.push(
      `<span class="di-badge di-badge-info" title="Cap quotidien non défini">` +
      `Cap —</span>`
    );
  }

  // 4. Mode
  badges.push(
    `<span class="di-badge di-badge-info" title="Mode stratégique actif">` +
    `Mode ${meta.mode || '—'}</span>`
  );

  return badges.join('');
}

/**
 * Génère micropuces métriques (sous la barre)
 * Affiche: Cycle 88 (w 0.65) • OnChain 41 (w 0.25) • Risk 57 (w 0.10)
 */
function renderMetrics(weights, scores, contribs) {
  const metrics = [];

  const addMetric = (label, score, weight, color) => {
    metrics.push(
      `<div class="di-metric-item" style="color: ${color};">` +
      `<span class="di-metric-label">${label}</span>` +
      `<span class="di-metric-value">${Math.round(score)}</span>` +
      `<span style="opacity: 0.7; font-size: 0.65rem;">(w ${weight.toFixed(2)})</span>` +
      `</div>`
    );
  };

  const colors = getColors();
  addMetric('Cycle', scores.cycle || 0, weights.cycle || 0, colors.cycle);
  addMetric('OnChain', scores.onchain || 0, weights.onchain || 0, colors.onchain);
  addMetric('Risk', scores.risk || 0, weights.risk || 0, colors.risk);

  return `<div class="di-metrics">${metrics.join(' • ')}</div>`;
}

/**
 * Footnote compacte (alignée droite)
 */
function renderFootnote(meta) {
  const liveStyle = meta.live ? '' : 'opacity: 0.6;';
  return `<div class="di-foot" style="${liveStyle}">Source: ${meta.source || '—'} • Live: ${meta.live ? 'ON' : 'OFF'}</div>`;
}

/**
 * Render barre empilée Chart.js (SANS axes/grilles, progress bar style)
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
            score: scores.cycle || 0,
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
            score: scores.onchain || 0,
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
            score: scores.risk || 0,
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
            const label = context.dataset.label;
            return `${label} ${value.toFixed(0)}%`;
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
              const pct = context.parsed.x?.toFixed(1) ?? '0.0';
              const meta = context.dataset._meta || {};
              const score = meta.score != null ? Math.round(meta.score) : '?';
              const weight = meta.weight != null ? meta.weight.toFixed(2) : '?';
              const wxs = meta.wxs != null ? meta.wxs.toFixed(1) : '?';
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
 * Render sparkline Chart.js (SANS axes/grilles, mini)
 * Retourne null si history < 6 points (placeholder géré dans HTML)
 */
function renderSparkline(canvas, history, opts = {}) {
  if (!Array.isArray(history) || history.length < 6) {
    return null;
  }

  const ctx = canvas.getContext('2d');
  const data = history.slice(-100);  // Max 100 points

  const config = {
    type: 'line',
    data: {
      labels: data.map((_, i) => i),
      datasets: [{
        data: data,
        borderColor: getColors().cycle,  // Couleur cycle pour cohérence
        borderWidth: 1.5,
        fill: false,
        pointRadius: 0,
        tension: 0.35
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          display: false,  // ✅ MASQUER axes complètement
          grid: { display: false }
        },
        y: {
          display: false,  // ✅ MASQUER axes complètement
          min: 0,
          max: 100,
          grid: { display: false }
        }
      },
      elements: {
        point: { radius: 0 }  // ✅ Pas de points visibles
      },
      plugins: {
        legend: { display: false },
        datalabels: { display: false },  // ✅ FORCER OFF (même si global=false)
        tooltip: {
          enabled: true,  // Garde tooltip simple
          callbacks: {
            label: (context) => `DI: ${context.parsed.y.toFixed(0)}`
          }
        }
      },
      animation: {
        duration: 0
      }
    }
  };

  return new Chart(ctx, config);
}

/**
 * Fallback texte si Chart.js absent
 */
function renderTextFallback(container, data) {
  console.warn('⚠️ Chart.js not loaded - using text fallback for Decision Index Panel');

  const contribs = calculateRelativeContributions(data.weights, data.scores);
  const historyText = data.history && data.history.length > 0
    ? data.history.slice(-5).join(' → ')
    : 'indisponible';

  container.innerHTML = `
    <div class="di-panel di-panel-fallback">
      <div class="di-head">
        <div class="di-value">${Math.round(data.di)}</div>
        <div class="di-badges">${renderBadges(data.meta)}</div>
      </div>
      <div style="margin: var(--space-xs) 0; font-size: 0.85rem; color: var(--theme-text-muted);">
        Cycle: ${contribs.cycle.toFixed(1)}% •
        On-Chain: ${contribs.onchain.toFixed(1)}% •
        Risk: ${contribs.risk.toFixed(1)}%
      </div>
      <div style="font-size: 0.8rem; color: var(--theme-text-muted);">
        Historique: ${historyText}
      </div>
      ${renderFootnote(data.meta)}
    </div>
  `;
}

/**
 * Render interne (sans debounce)
 */
function _renderDIPanelInternal(container, data, opts = {}) {
  if (!container) {
    console.error('❌ DI Panel: container element not found');
    return;
  }

  // Debug toggle
  if (window.__DI_DEBUG__ && window.location?.hostname === 'localhost') {
    console.log('🐛 DI Panel Input:', {
      di: data.di,
      weights: data.weights,
      scores: data.scores,
      cap: data.meta?.cap,
      history_length: data.history?.length || 0
    });
  }

  // Vérifier Chart.js
  if (!window.Chart) {
    return renderTextFallback(container, data);
  }

  // Cleanup Chart.js
  if (chartInstances.stacked) {
    chartInstances.stacked.destroy();
    chartInstances.stacked = null;
  }
  if (chartInstances.sparkline) {
    chartInstances.sparkline.destroy();
    chartInstances.sparkline = null;
  }

  // Calculer contributions
  const contribs = calculateRelativeContributions(data.weights, data.scores);

  if (window.__DI_DEBUG__ && window.location?.hostname === 'localhost') {
    console.log('🐛 DI Panel Contributions:', contribs);
  }

  // Générer HTML structure
  const showSparkline = data.history && data.history.length >= 6;

  container.innerHTML = `
    <div class="di-panel">
      <div class="di-head">
        <div class="di-value">${Math.round(data.di)}</div>
        <div class="di-badges">${renderBadges(data.meta)}</div>
      </div>
      <div class="di-stack">
        <canvas id="${container.id}-stack-chart"></canvas>
      </div>
      ${renderMetrics(data.weights, data.scores, contribs)}
      <div class="di-spark">
        ${showSparkline
          ? `<canvas id="${container.id}-spark-chart"></canvas>`
          : `<div class="di-spark-placeholder">Historique en cours de collecte (${data.history?.length || 0}/6 points)</div>`
        }
      </div>
      ${renderFootnote(data.meta)}
    </div>
  `;

  // Render charts
  const stackCanvas = document.getElementById(`${container.id}-stack-chart`);
  if (stackCanvas) {
    chartInstances.stacked = renderStackedBar(stackCanvas, contribs, data.weights, data.scores, opts);
  }

  if (showSparkline) {
    const sparkCanvas = document.getElementById(`${container.id}-spark-chart`);
    if (sparkCanvas) {
      chartInstances.sparkline = renderSparkline(sparkCanvas, data.history, opts);
    }
  }
}

/**
 * Fonction principale - Render le panneau Decision Index
 *
 * @param {HTMLElement} container - Conteneur DOM
 * @param {Object} data - Données {di, weights, scores, history, meta}
 * @param {Object} opts - Options {heightStacked, heightSpark}
 */
export function renderDecisionIndexPanel(container, data, opts = {}) {
  // Debounce 150ms
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
  if (chartInstances.sparkline) {
    chartInstances.sparkline.destroy();
    chartInstances.sparkline = null;
  }
}

/**
 * Helper pour initialiser Chart.js (idempotent)
 */
export async function ensureChartJSLoaded() {
  if (window.Chart) {
    return true;
  }

  console.warn('⚠️ Chart.js not found - attempting to load from CDN...');

  return new Promise((resolve) => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
    script.onload = () => {
      console.log('✅ Chart.js loaded dynamically');
      resolve(true);
    };
    script.onerror = () => {
      console.error('❌ Failed to load Chart.js from CDN');
      resolve(false);
    };
    document.head.appendChild(script);
  });
}
