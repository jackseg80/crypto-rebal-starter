/**
 * Decision Index Panel - Composant visuel réutilisable
 *
 * Affiche le Decision Index avec:
 * - Barre empilée (contributions relatives des 3 piliers)
 * - Sparkline (historique DI)
 * - Badges compacts (Confiance, Contradiction, Cap, Mode)
 * - Footnote (Source + Live status)
 *
 * ⚠️ IMPORTANT: Chart.js doit être chargé AVANT ce module
 *
 * ⚠️ IMPORTANT — Sémantique Risk:
 * Risk est un score POSITIF (0..100, plus haut = mieux).
 * Ne jamais inverser (pas de 100 - risk).
 * Contributions UI: (w * score) / Σ(w * score).
 */

// Instances Chart.js (pour cleanup proper)
let chartInstances = {
  stacked: null,
  sparkline: null
};

// Debounce timeout
let refreshTimeout = null;

/**
 * Palette couleurs (CSS variables pour dark mode)
 */
const COLORS = {
  cycle: 'var(--di-color-cycle, #3b82f6)',    // bleu
  onchain: 'var(--di-color-onchain, #06b6d4)', // cyan
  risk: 'var(--di-color-risk, #ec4899)'        // rose
};

/**
 * Calcule les contributions relatives de chaque pilier au DI
 *
 * Formule: part_i = (weight_i × score_i) / Σ(weight_k × score_k)
 *
 * ⚠️ CRITIQUE: NE PAS inverser le score Risk (100 - x)
 * Le score Risk est déjà normalisé (0-100, plus haut = meilleur)
 *
 * @param {Object} weights - Poids POST-adaptatifs {cycle, onchain, risk}
 * @param {Object} scores - Scores bruts {cycle, onchain, risk}
 * @returns {Object} Contributions en % + valeurs brutes pour tooltips
 */
function calculateRelativeContributions(weights, scores) {
  const epsilon = 1e-6;

  // Clamp scores [0, 100] + filtre null/undefined
  const clampedScores = {
    cycle: Math.max(0, Math.min(100, scores.cycle || 0)),
    onchain: Math.max(0, Math.min(100, scores.onchain || 0)),
    risk: Math.max(0, Math.min(100, scores.risk || 0))  // ✅ PAS d'inversion (100 - x)
  };

  // Valeurs brutes (w × s)
  const raw = {
    cycle: (weights.cycle || 0) * clampedScores.cycle,
    onchain: (weights.onchain || 0) * clampedScores.onchain,
    risk: (weights.risk || 0) * clampedScores.risk
  };

  // Somme totale (avec epsilon pour éviter division par zéro)
  const sum = Object.values(raw).reduce((a, b) => a + b, 0) || epsilon;

  // Contributions relatives (%)
  return {
    cycle: (raw.cycle / sum) * 100,
    onchain: (raw.onchain / sum) * 100,
    risk: (raw.risk / sum) * 100,
    raw: raw  // Pour tooltips "w×s = X"
  };
}

/**
 * Génère les badges avec couleurs conditionnelles et tooltips
 *
 * @param {Object} meta - Métadonnées {confidence, contradiction, cap, mode}
 * @returns {string} HTML des badges
 */
function renderBadges(meta) {
  const badges = [];

  // 1. CONFIANCE (<40% warning, 40-70% neutral, >70% success)
  const confPct = Math.round((meta.confidence || 0) * 100);
  const confClass = confPct < 40 ? 'warning' : confPct < 70 ? 'neutral' : 'success';
  badges.push(
    `<span class="di-badge di-badge-${confClass}" title="Niveau de certitude: ${confPct}%">` +
    `Conf. ${confPct}%</span>`
  );

  // 2. CONTRADICTION (<30% success, 30-50% warning, >50% danger)
  const contraPct = Math.round((meta.contradiction || 0) * 100);
  const contraClass = contraPct < 30 ? 'success' : contraPct < 50 ? 'warning' : 'danger';
  badges.push(
    `<span class="di-badge di-badge-${contraClass}" title="Divergence entre sources: ${contraPct}%">` +
    `Contrad. ${contraPct}%</span>`
  );

  // 3. CAP (valider unité: 0-1 → ×100, NaN → —)
  let capPct = meta.cap;
  if (typeof capPct === 'number' && Number.isFinite(capPct)) {
    if (capPct <= 1) {
      capPct = Math.round(capPct * 100);
    }
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

  // 4. MODE (toujours info)
  badges.push(
    `<span class="di-badge di-badge-info" title="Mode stratégique actif">` +
    `Mode ${meta.mode || '—'}</span>`
  );

  return badges.join('');
}

/**
 * Génère la footnote compacte
 *
 * @param {Object} meta - Métadonnées {source, live}
 * @returns {string} HTML de la footnote
 */
function renderFootnote(meta) {
  const liveStyle = meta.live ? '' : 'opacity: 0.6;';
  return `<div class="di-foot" style="${liveStyle}">Source: ${meta.source || '—'} • Live: ${meta.live ? 'ON' : 'OFF'}</div>`;
}

/**
 * Render la barre empilée Chart.js (contributions relatives)
 *
 * @param {HTMLCanvasElement} canvas - Canvas élément
 * @param {Object} contributions - Contributions relatives calculées
 * @param {Object} opts - Options {heightStacked, palette}
 */
function renderStackedBar(canvas, contributions, opts = {}) {
  const ctx = canvas.getContext('2d');
  const height = opts.heightStacked || 80;
  canvas.height = height;

  const config = {
    type: 'bar',
    data: {
      labels: ['Contributions'],
      datasets: [
        {
          label: 'Cycle',
          data: [contributions.cycle],
          backgroundColor: COLORS.cycle,
          borderWidth: 0
        },
        {
          label: 'On-Chain',
          data: [contributions.onchain],
          backgroundColor: COLORS.onchain,
          borderWidth: 0
        },
        {
          label: 'Risk',
          data: [contributions.risk],
          backgroundColor: COLORS.risk,
          borderWidth: 0
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
          display: true,
          max: 100,
          ticks: {
            callback: (value) => value + '%'
          }
        },
        y: {
          stacked: true,
          display: false
        }
      },
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: {
            boxWidth: 12,
            padding: 8
          }
        },
        tooltip: {
          callbacks: {
            label: (context) => {
              const pillar = context.dataset.label;
              const pct = context.parsed.x.toFixed(1);
              const rawValue = contributions.raw[pillar.toLowerCase().replace('-', '')] || 0;
              return `${pillar}: ${pct}% (w×s = ${rawValue.toFixed(1)})`;
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
 * Render la sparkline Chart.js (historique DI)
 *
 * @param {HTMLCanvasElement} canvas - Canvas élément
 * @param {Array<number>} history - Historique DI (0-100)
 * @param {Object} opts - Options {heightSpark}
 */
function renderSparkline(canvas, history, opts = {}) {
  const ctx = canvas.getContext('2d');
  const height = opts.heightSpark || 60;
  canvas.height = height;

  // Limiter à 100 points max
  const data = (history || []).slice(-100);

  if (data.length === 0) {
    // Pas de données: afficher message
    ctx.font = '12px sans-serif';
    ctx.fillStyle = 'var(--theme-text-muted)';
    ctx.textAlign = 'center';
    ctx.fillText('Historique indisponible', canvas.width / 2, canvas.height / 2);
    return null;
  }

  const config = {
    type: 'line',
    data: {
      labels: data.map((_, i) => i),
      datasets: [{
        data: data,
        borderColor: 'var(--brand-primary)',
        borderWidth: 2,
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
          display: false
        },
        y: {
          display: true,
          min: 0,
          max: 100,
          ticks: {
            callback: (value) => value
          }
        }
      },
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
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
 *
 * @param {HTMLElement} container - Conteneur DOM
 * @param {Object} data - Données complètes
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
      <div style="margin: var(--space-sm) 0; font-size: 0.9rem; color: var(--theme-text-muted);">
        Cycle: ${contribs.cycle.toFixed(1)}% •
        On-Chain: ${contribs.onchain.toFixed(1)}% •
        Risk: ${contribs.risk.toFixed(1)}%
      </div>
      <div style="font-size: 0.85rem; color: var(--theme-text-muted);">
        Historique: ${historyText}
      </div>
      ${renderFootnote(data.meta)}
    </div>
  `;
}

/**
 * Render interne (sans debounce)
 *
 * @param {HTMLElement} container - Conteneur DOM
 * @param {Object} data - Données complètes
 * @param {Object} opts - Options
 */
function _renderDIPanelInternal(container, data, opts = {}) {
  if (!container) {
    console.error('❌ DI Panel: container element not found');
    return;
  }

  // Debug toggle (localhost uniquement)
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

  // Détruire anciennes instances Chart.js (évite fuites mémoire)
  if (chartInstances.stacked) {
    chartInstances.stacked.destroy();
    chartInstances.stacked = null;
  }
  if (chartInstances.sparkline) {
    chartInstances.sparkline.destroy();
    chartInstances.sparkline = null;
  }

  // Calculer contributions relatives
  const contribs = calculateRelativeContributions(data.weights, data.scores);

  if (window.__DI_DEBUG__ && window.location?.hostname === 'localhost') {
    console.log('🐛 DI Panel Contributions:', contribs);
  }

  // Générer HTML structure
  container.innerHTML = `
    <div class="di-panel">
      <div class="di-head">
        <div class="di-value">${Math.round(data.di)}</div>
        <div class="di-badges">${renderBadges(data.meta)}</div>
      </div>
      <div class="di-stack">
        <canvas id="${container.id}-stack-chart"></canvas>
      </div>
      <div class="di-spark">
        <canvas id="${container.id}-spark-chart"></canvas>
      </div>
      ${renderFootnote(data.meta)}
    </div>
  `;

  // Render charts
  const stackCanvas = document.getElementById(`${container.id}-stack-chart`);
  const sparkCanvas = document.getElementById(`${container.id}-spark-chart`);

  if (stackCanvas) {
    chartInstances.stacked = renderStackedBar(stackCanvas, contribs, opts);
  }

  if (sparkCanvas) {
    chartInstances.sparkline = renderSparkline(sparkCanvas, data.history, opts);
  }
}

/**
 * Fonction principale - Render le panneau Decision Index
 *
 * @param {HTMLElement} container - Conteneur DOM où dessiner le panneau
 * @param {Object} data - Données structurées {di, weights, scores, history, meta}
 * @param {Object} opts - Options {heightStacked, heightSpark, palette}
 *
 * Structure data attendue:
 * {
 *   di: number (0-100),
 *   weights: { cycle: number, onchain: number, risk: number },  // POST-adaptatifs
 *   scores: { cycle: number, onchain: number, risk: number },   // 0-100
 *   history: number[],  // 0-100, max 100 points
 *   meta: {
 *     confidence: number (0-1),
 *     contradiction: number (0-1),
 *     cap: number (% ou 0-1) | null,
 *     mode: string,
 *     source: string,
 *     live: boolean
 *   }
 * }
 */
export function renderDecisionIndexPanel(container, data, opts = {}) {
  // Debounce 150ms (évite jank sur rafales de MAJ)
  clearTimeout(refreshTimeout);
  refreshTimeout = setTimeout(() => {
    _renderDIPanelInternal(container, data, opts);
  }, 150);
}

/**
 * Cleanup global (appeler avant destruction page)
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
 * ⚠️ À appeler depuis les pages, PAS automatiquement
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
