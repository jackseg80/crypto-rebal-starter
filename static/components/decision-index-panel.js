/**
 * Decision Index Panel - Composant visuel OPTIMISÉ v3
 *
 * Nouvelles fonctionnalités:
 * - Trend Chip (Δ7j, Δ30j, σ, état Stable/Agité) remplace sparkline
 * - Regime Ribbon (7-14 cases colorées selon phase market)
 * - Système d'aide hybride (popover + icône ℹ️)
 * - Labels centrés dans barre empilée
 * - Tooltips enrichis (part relative + score + poids + w×s)
 * - Accessibilité clavier complète
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
    raw: raw  // Pour tooltips
  };
}

/**
 * Calcule écart-type d'un tableau de nombres
 */
function stddev(arr) {
  if (!arr || arr.length < 2) return 0;
  const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
  const variance = arr.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / arr.length;
  return Math.sqrt(variance);
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
 * Génère Trend Chip (remplace sparkline)
 * Affiche: Δ7j, σ, état Stable/Agité
 */
function renderTrendChip(history = []) {
  const n = history.length;

  // Collecte en cours (< 6 points)
  if (n < 6) {
    return `<div class="di-trend di-trend-collect" title="Collecte historique en cours">` +
      `Trend: collecte (${n}/6)</div>`;
  }

  const last = history[n - 1];
  const idx7 = Math.max(0, n - 7);
  const idx30 = Math.max(0, n - 30);

  const d7 = history[idx7];
  const d30 = history[idx30];

  const delta7 = last - d7;
  const delta30 = last - d30;

  const recent = history.slice(idx7);
  const sigma7 = stddev(recent);

  // Symbole flèche
  let arrow = '→';
  let trendClass = 'flat';
  if (delta7 > 1.0) {
    arrow = '↗︎';
    trendClass = 'up';
  } else if (delta7 < -1.0) {
    arrow = '↘︎';
    trendClass = 'down';
  }

  // État volatilité
  const state = sigma7 < 1.0 ? 'Stable' : 'Agité';

  const tooltipText = `Δ7j: ${delta7.toFixed(1)} • Δ30j: ${delta30.toFixed(1)} • σ_7j: ${sigma7.toFixed(1)}`;

  return `<div class="di-trend di-trend-${trendClass}" title="${tooltipText}">` +
    `Trend: ${arrow} ${delta7 >= 0 ? '+' : ''}${delta7.toFixed(1)} pts (7j) • σ=${sigma7.toFixed(1)} • ${state}</div>`;
}

/**
 * Génère Regime Ribbon (7-14 cases colorées)
 */
function renderRegimeRibbon(regimeHistory = []) {
  if (!regimeHistory || regimeHistory.length === 0) {
    return '';  // Masquer si pas de données
  }

  const cells = regimeHistory.slice(-14).map((regime, idx) => {
    const dayOffset = regimeHistory.length - 1 - idx;
    const phase = regime.phase || regime.name || 'unknown';
    const phaseClass = mapPhaseToClass(phase);

    const capPct = regime.cap != null ? Math.round(regime.cap * 100) : '—';
    const contraPct = regime.contradiction != null ? Math.round(regime.contradiction * 100) : '—';

    const tooltipText = `J-${dayOffset} • Phase: ${phase} • cap: ${capPct}% • contradiction: ${contraPct}%`;

    return `<span class="di-ribbon-cell di-ribbon-${phaseClass}" title="${tooltipText}"></span>`;
  }).join('');

  return `<div class="di-ribbon">${cells}</div>`;
}

/**
 * Map phase name vers classe CSS
 */
function mapPhaseToClass(phase) {
  const p = (phase || '').toLowerCase();
  if (p.includes('bull') || p.includes('euphori') || p.includes('expansion')) return 'bull';
  if (p.includes('bear') || p.includes('risk') || p.includes('prudence')) return 'risk';
  if (p.includes('caution') || p.includes('warning')) return 'caution';
  return 'neutral';
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
            return `${context.dataset.label} ${value.toFixed(0)}%`;
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
 * Monte le popover d'aide (système hybride)
 */
function mountHelpPopover(rootEl) {
  const trigger = rootEl.querySelector('.di-help-trigger');
  const popover = rootEl.querySelector('.di-help');

  if (!trigger || !popover) return;

  // Toggle popover
  const togglePopover = (show) => {
    if (show) {
      helpPopoverState.isOpen = true;
      helpPopoverState.lastFocusedElement = document.activeElement;
      popover.style.display = 'block';
      trigger.setAttribute('aria-expanded', 'true');

      // Focus premier élément focusable
      setTimeout(() => {
        const firstFocusable = popover.querySelector('button, [href], [tabindex]:not([tabindex="-1"])');
        if (firstFocusable) firstFocusable.focus();
      }, 50);
    } else {
      helpPopoverState.isOpen = false;
      popover.style.display = 'none';
      trigger.setAttribute('aria-expanded', 'false');

      // Restaurer focus
      if (helpPopoverState.lastFocusedElement) {
        helpPopoverState.lastFocusedElement.focus();
      }
    }
  };

  // Événement trigger
  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    togglePopover(!helpPopoverState.isOpen);
  });

  // Bouton fermer
  const closeBtn = popover.querySelector('.di-help-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => togglePopover(false));
  }

  // ESC pour fermer
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && helpPopoverState.isOpen) {
      togglePopover(false);
    }
  });

  // Clic hors popover
  document.addEventListener('click', (e) => {
    if (helpPopoverState.isOpen && !popover.contains(e.target) && e.target !== trigger) {
      togglePopover(false);
    }
  });

  // Focus trap simple
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
          <h4>📊 Barre empilée (contributions)</h4>
          <p>La largeur de chaque segment reflète sa contribution relative au DI. Passez la souris pour voir le détail (score, poids, contribution).</p>
        </section>
        <section>
          <h4>📈 Trend Chip</h4>
          <p>Synthétise la dynamique courte (variation 7j/30j) et la volatilité (σ). Une flèche ↗︎ indique une hausse, ↘︎ une baisse. "Stable" signifie faible volatilité (σ < 1.0).</p>
        </section>
        <section>
          <h4>🎨 Regime Ribbon</h4>
          <p>Colorie la phase récente du marché (7-14 derniers pas). Survolez une case pour voir les détails de ce jour (phase, cap, contradiction).</p>
        </section>
        <section>
          <h4>💡 Note importante</h4>
          <p>Un DI stable peut venir d'un cap gouvernance, d'un régime constant, ou d'une faible dispersion des signaux.</p>
        </section>
      </div>
    </div>
  `;
}

/**
 * Fallback texte si Chart.js absent
 */
function renderTextFallback(container, data) {
  console.warn('⚠️ Chart.js not loaded - using text fallback for Decision Index Panel');

  const contribs = calculateRelativeContributions(data.weights, data.scores);

  container.innerHTML = `
    <div class="di-panel di-panel-fallback">
      <div class="di-head">
        <div class="di-title">
          <span>Decision Index</span>
          <button class="di-help-trigger" aria-label="Aide Decision Index" aria-expanded="false" type="button">ℹ️</button>
        </div>
        <div class="di-value">${Math.round(data.di)}</div>
        <div class="di-badges">${renderBadges(data.meta)}</div>
      </div>
      <div style="margin: var(--space-xs) 0; font-size: 0.85rem; color: var(--theme-text-muted);">
        Cycle: ${contribs.cycle.toFixed(1)}% •
        On-Chain: ${contribs.onchain.toFixed(1)}% •
        Risk: ${contribs.risk.toFixed(1)}%
      </div>
      ${renderTrendChip(data.history)}
      ${renderFootnote(data.meta)}
      ${renderHelpContent()}
    </div>
  `;

  mountHelpPopover(container);
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
      history_length: data.history?.length || 0,
      regime_history_length: data.regimeHistory?.length || 0
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

  // Calculer contributions
  const contribs = calculateRelativeContributions(data.weights, data.scores);

  if (window.__DI_DEBUG__ && window.location?.hostname === 'localhost') {
    console.log('🐛 DI Panel Contributions:', contribs);
  }

  // Générer HTML structure
  container.innerHTML = `
    <div class="di-panel">
      <div class="di-head">
        <div class="di-title">
          <span>Decision Index</span>
          <button class="di-help-trigger" aria-label="Aide Decision Index" aria-expanded="false" aria-controls="di-help-popover" type="button">ℹ️</button>
        </div>
        <div class="di-value">${Math.round(data.di)}</div>
        <div class="di-badges">${renderBadges(data.meta)}</div>
      </div>
      <div class="di-stack">
        <canvas id="${container.id}-stack-chart"></canvas>
      </div>
      ${renderTrendChip(data.history)}
      ${renderRegimeRibbon(data.regimeHistory)}
      ${renderFootnote(data.meta)}
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
 *
 * @param {HTMLElement} container - Conteneur DOM
 * @param {Object} data - Données {di, weights, scores, history, regimeHistory, meta}
 * @param {Object} opts - Options {}
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
