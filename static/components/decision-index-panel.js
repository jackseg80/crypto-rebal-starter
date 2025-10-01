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
 * Génère SVG sparkline pour série temporelle DI
 * @param {number} delta - Delta pour coloration (vert si >0, rouge si <0, gris sinon)
 */
function renderSparkline(series, width = 260, height = 36, dashed = false, delta = 0) {
  if (!Array.isArray(series) || series.length === 0) {
    return `<div class="spark-placeholder">—</div>`;
  }
  const n = series.length;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const span = (max - min) || 1;
  const px = (i) => (i / (n - 1)) * (width - 2) + 1;
  const py = (v) => height - ((v - min) / span) * (height - 2) - 1;
  const d = series.map((v, i) => `${i === 0 ? 'M' : 'L'} ${px(i).toFixed(1)} ${py(v).toFixed(1)}`).join(' ');

  // Coloration selon pente
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

  // 1. Confiance (accepte 0-1 ou 0-100)
  let confPct = meta.confidence || 0;
  if (confPct <= 1) confPct = Math.round(confPct * 100);
  const confClass = confPct < 40 ? 'warning' : confPct < 70 ? 'neutral' : 'success';
  badges.push(
    `<span class="di-badge di-badge-${confClass}" title="Niveau de certitude: ${confPct}%">` +
    `CONF ${confPct}%</span>`
  );

  // 2. Contradiction (accepte 0-1 ou 0-100)
  let contraPct = meta.contradiction || 0;
  if (contraPct <= 1) contraPct = Math.round(contraPct * 100);
  const contraClass = contraPct < 30 ? 'success' : contraPct < 50 ? 'warning' : 'danger';
  badges.push(
    `<span class="di-badge di-badge-${contraClass}" title="Divergence entre sources: ${contraPct}%">` +
    `CONTRAD ${contraPct}%</span>`
  );

  // 3. Cap (accepte 0-1 ou 0-100)
  let capPct = meta.cap;
  if (typeof capPct === 'number' && Number.isFinite(capPct)) {
    if (capPct <= 1) capPct = Math.round(capPct * 100);
    badges.push(
      `<span class="di-badge di-badge-info" title="Cap quotidien gouvernance">` +
      `CAP ${capPct}%</span>`
    );
  } else {
    badges.push(
      `<span class="di-badge di-badge-info" title="Cap quotidien non défini">` +
      `Cap —</span>`
    );
  }

  // 4. Mode (uppercase pour correspondre à l'image)
  const modeText = (meta.mode || 'normal').toUpperCase();
  badges.push(
    `<span class="di-badge di-badge-info" title="Mode stratégique actif">` +
    `MODE ${modeText}</span>`
  );

  return badges.join('');
}

/**
 * Génère métriques Trend (texte compact)
 */
function renderTrendMetrics(history = []) {
  const n = history.length;

  if (n < 3) {
    return `<div class="di-trend-metrics">Trend: collecte (${n}/3)</div>`;
  }

  const last = history[n - 1];
  const idx7 = Math.max(0, n - 7);
  const prev7 = history[idx7];
  const delta7 = last - prev7;

  // Calcul σ sur fenêtre récente
  const slice = history.slice(idx7);
  const mean = slice.reduce((a, b) => a + b, 0) / slice.length;
  const variance = slice.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / slice.length;
  const sigma = Math.sqrt(variance);

  // Flèche
  const arrow = delta7 > 1 ? '↗︎' : delta7 < -1 ? '↘︎' : '→';
  const state = sigma < 1 ? 'Stable' : 'Agité';

  return `<div class="di-trend-metrics">` +
    `Trend: ${arrow} ${delta7 >= 0 ? '+' : ''}${delta7.toFixed(1)} pts (7j) • σ=${sigma.toFixed(1)} • ${state}</div>`;
}

/**
 * Génère Sparkbar (12-20 barres normalisées)
 * Barres colorées selon pente locale: vert (↑), rouge (↓), gris (≈)
 */
function renderSparkbar(history = []) {
  if (!Array.isArray(history) || history.length < 3) {
    return '';  // Pas assez de données
  }

  const N = Math.min(20, history.length);
  const slice = history.slice(-N);

  // Normalisation min-max pour toujours remplir la hauteur
  const min = Math.min(...slice);
  const max = Math.max(...slice);
  const span = Math.max(1e-6, max - min);  // Éviter division par zéro

  const bars = slice.map((v, i) => {
    const h = ((v - min) / span) * 100;  // 0-100%
    const hClamped = Math.max(6, h);      // Min 6% pour visibilité

    // Pente locale
    const prev = i > 0 ? slice[i - 1] : v;
    const delta = v - prev;
    const cls = Math.abs(delta) < 0.25 ? 'flat' : (delta > 0 ? 'up' : 'down');

    const dayOffset = N - 1 - i;
    const title = `J-${dayOffset} • DI: ${v.toFixed(1)}`;

    return `<span class="sb-bar sb-bar-${cls}" style="--h: ${hClamped}%" title="${title}"></span>`;
  }).join('');

  return `<div class="di-sparkbar" aria-label="Decision Index recent trend">${bars}</div>`;
}

/**
 * Génère breakdown line (scores avec typographie uniforme)
 */
function renderBreakdown(weights, scores) {
  const s = scores || {};

  return `
    <div class="di-subline">
      <span class="lbl lbl-cycle">Cycle <b>${_round(s.cycle || 0)}</b></span>
      <span class="dot">·</span>
      <span class="lbl lbl-oc">On-Chain <b>${_round(s.onchain || 0, 1)}</b></span>
      <span class="dot">·</span>
      <span class="lbl lbl-risk">Risk <b>${_round(s.risk || 0)}</b></span>
    </div>`;
}

/**
 * Calcule trend (Δ7j, sigma, état)
 */
function calculateTrend(history = []) {
  const n = (history || []).length;
  if (n < 3) return { delta: 0, sigma: 0, state: 'Collecte' };

  const last = _safe(history[n - 1]);
  const idx7 = Math.max(0, n - 7);
  const prev7 = _safe(history[idx7]);
  const delta = _round(last - prev7, 1);

  // Calcul σ sur fenêtre récente
  const slice = history.slice(idx7);
  const mean = slice.reduce((a, b) => a + b, 0) / slice.length;
  const variance = slice.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / slice.length;
  const sigma = _round(Math.sqrt(variance), 1);

  let state = 'Stable';
  if (sigma >= 2) state = 'Agité';
  else if (delta > 2) state = 'Haussier';
  else if (delta < -2) state = 'Baissier';

  return { delta, sigma, state };
}

/**
 * Génère events array
 */
function calculateEvents(meta = {}) {
  const events = [];

  // Cap actif
  const cap = _safe(meta.cap);
  if (cap > 0) {
    events.push({ icon: '⚡', text: `Cap actif ${cap}%`, type: 'info' });
  }

  // Contradiction haute
  const contrad = _safe(meta.contradiction);
  if (contrad >= 0.5) {
    events.push({ icon: '🛑', text: `Contradiction ${_round(contrad * 100, 0)}%`, type: 'warning' });
  }

  // Mode non-normal
  if (meta.mode && meta.mode.toLowerCase() !== 'normal' && meta.mode !== '—') {
    events.push({ icon: '🎛', text: `Mode ${meta.mode}`, type: 'info' });
  }

  // Alpha disponible
  if (meta.alpha !== undefined && meta.alpha !== null) {
    const alphaVal = _round(meta.alpha * 100, 0);
    events.push({ icon: '🎯', text: `Alpha ${alphaVal}%`, type: 'success' });
  }

  return events;
}

/**
 * Render events badges
 */
function renderEventsBadges(events = []) {
  if (!events.length) return '';

  const badges = events.map(e =>
    `<span class="di-ev di-ev-${e.type || 'info'}"><span class="di-ico">${e.icon}</span> ${e.text}</span>`
  ).join('');

  return `<div class="di-events">${badges}</div>`;
}

/**
 * Mapping phase name → index (0=Bull, 1=Neutral, 2=Bear)
 */
function phaseToIndex(name) {
  const n = String(name || '').toLowerCase();
  if (n.includes('euphor') || n.includes('bull') || n.includes('risk-on') || n.includes('expansion')) return 0;
  if (n.includes('bear') || n.includes('risk-off') || n.includes('prudence')) return 2;
  return 1; // Neutral par défaut
}

/**
 * Génère regime ribbon (3 barres: Euphorie/Neutral/Bearish) avec fallback sur meta.phase
 */
function renderRegimeRibbon(meta, regimeHistoryRaw) {
  const rHist = Array.isArray(regimeHistoryRaw) ? regimeHistoryRaw.slice(-5) : [];
  let activeIdx = phaseToIndex(meta?.phase);

  // Si historique exploitable, déduire niveau d'après nb d'éléments "actifs"
  if (rHist.length > 0) {
    const actives = rHist.filter(x => (x?.active ?? x?.bull ?? x?.risk_on ?? false)).length;
    // 0..5 actifs → 0..2 index
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
    <div class="di-ribbon">
      <div class="di-ribbon-title">Regime</div>
      <div class="rg-row">${bars}</div>
    </div>`;
}

/**
 * Génère regime dots (5 pastilles récentes)
 */
function renderRegimeDots(regimeHistory = []) {
  const arr = Array.isArray(regimeHistory) ? regimeHistory.slice(-5) : [];

  if (arr.length === 0) return '';

  const dots = arr.map((r, i) => {
    const phase = (r.phase || 'neutral').toLowerCase();
    const phaseClass = mapPhaseToClass(phase);
    const k = arr.length - 1 - i;

    const label = r.label || phase;
    const title = `J-${k} • ${label}`;

    return `<span class="rg-dot rg-dot-${phaseClass}" title="${title}"></span>`;
  }).join('');

  return `<div class="di-ribbon"><span class="rg">${dots}</span></div>`;
}

/**
 * Génère Events (icônes conditionnelles)
 */
function renderEvents(meta = {}) {
  const out = [];

  // Cap actif (> 0)
  if (typeof meta.cap === 'number' && meta.cap > 0) {
    out.push('⚡ cap actif');
  }

  // Contradiction haute (≥ 50%)
  if (typeof meta.contradiction === 'number' && meta.contradiction >= 0.5) {
    out.push('🛑 contradiction haute');
  }

  // Mode non-normal
  if (meta.mode && meta.mode.toLowerCase() !== 'normal' && meta.mode !== '—') {
    out.push(`🎛 mode ${meta.mode}`);
  }

  // Changement de phase (optionnel)
  if (meta.changedPhase) {
    out.push('🧭 changement de phase');
  }

  return out.length ? `<div class="di-events">${out.join('  •  ')}</div>` : '';
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
 * Footer status (rangée badges bas) - optionnel
 */
function renderFooterStatus(data) {
  const m = data.meta || {};
  const scoreCycle = Number.isFinite(data?.scores?.cycle) ? Math.round(data.scores.cycle) : null;
  const confCycle = Number.isFinite(m.cycle_confidence) ? Math.round(m.cycle_confidence * 100) : null;
  const timeStr = (() => {
    try { return m.updated ? new Date(m.updated).toLocaleTimeString() : ''; } catch { return ''; }
  })();
  const pill = (txt) => `<span class="di-mini">${txt}</span>`;
  const good = (txt) => `<span class="di-mini di-mini-good">${txt}</span>`;

  return `
    <div class="di-footer">
      <div class="di-footer-left">
        ${good(`● ${m.phase || 'Neutral'}`)}
      </div>
      <div class="di-footer-right">
        ${pill(`Backend ${m.backend ? 'healthy' : 'check'}`)}
        ${pill(`Signals ${m.signals ? 'healthy' : (m.signals_status || 'limited')}`)}
        ${m.governance_mode ? pill(`Governance ${m.governance_mode}`) : ''}
        ${scoreCycle != null ? pill(`Cycle ${scoreCycle}${confCycle != null ? ' (' + confCycle + '%)' : ''}`) : ''}
        ${timeStr ? pill(timeStr) : ''}
      </div>
    </div>
  `;
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
            // ✅ Pas de puce/symbole, juste le texte
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
 * Monte tooltip sur hover des segments de la barre
 */
function mountSegmentTooltip(container, data) {
  const canvas = container.querySelector('.di-stack-canvas');
  if (!canvas || !chartInstances.stacked) return;

  let tooltip = container.querySelector('.di-tip');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.className = 'di-tip';
    tooltip.style.display = 'none';
    container.appendChild(tooltip);
  }

  const showTooltip = (text, x, y) => {
    tooltip.innerHTML = text;
    tooltip.style.display = 'block';
    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;
  };

  const hideTooltip = () => {
    tooltip.style.display = 'none';
  };

  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Détecter segment via Chart.js
    const elements = chartInstances.stacked.getElementsAtEventForMode(e, 'nearest', { intersect: true }, false);

    if (elements.length > 0) {
      const index = elements[0].index;
      const pillarNames = ['Cycle', 'On-Chain', 'Risk'];
      const pillar = pillarNames[index] || '';
      const score = data.scores?.[pillar.toLowerCase().replace('-', '')] || 0;
      const weight = data.weights?.[pillar.toLowerCase().replace('-', '')] || 0;
      const contribution = _round(weight * score, 1);

      const text = `<strong>${pillar}</strong><br/>Score: ${_round(score, 1)}<br/>Poids: ${_round(weight * 100, 0)}%<br/>Contribution: ${contribution}`;

      showTooltip(text, e.clientX - rect.left + 10, e.clientY - rect.top - 10);
    } else {
      hideTooltip();
    }
  });

  canvas.addEventListener('mouseleave', hideTooltip);
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

  // Calculer breakdown, trend, regime ribbon
  const breakdown = renderBreakdown(data.weights, data.scores);

  // Nouveau calcul trend avec sparkline
  const tw = computeTrendWindow(data.history, 7);
  const trendDelta = _round(tw.delta, 1);
  const trendSigma = _round(tw.sigma, 1);
  const trendState = tw.state;
  const dashed = !tw.ok;
  const trendSpark = renderSparkline(tw.series, 280, 40, dashed, trendDelta);

  // Affichage à droite : soit les 3 pills (Δ / σ / État), soit le badge "Historique insuffisant"
  const deltaBadge = `${trendDelta === 0 ? '→' : (trendDelta > 0 ? '↗' : '↘')} ${trendDelta > 0 ? '+' : ''}${trendDelta} pts`;
  const toneSigma = trendSigma < 1 ? 'ok' : trendSigma <= 2 ? 'warn' : 'danger';

  const trendRight = tw.ok
    ? `
        <span class="pill pill--${trendDelta > 1 ? 'ok' : (trendDelta < -1 ? 'danger' : 'warn')}">${deltaBadge}</span>
        <span class="pill pill--${toneSigma}">σ ${trendSigma}</span>
        <span class="pill pill--${trendState === 'Haussier' ? 'ok' : (trendState === 'Baissier' ? 'danger' : 'warn')}">${trendState}</span>
      `
    : `<span class="pill pill--muted pill--ellipsis">… Historique insuffisant</span>`;

  // Regime avec titre séparé
  const regimeRibbon = `
    <div class="regime-section">
      <div class="reg-title">REGIME</div>
      ${renderRegimeRibbon(data.meta, data.regimeHistory)}
    </div>`;

  const m = data.meta || {};

  // ---------- Tones & seuils (cohérents projet) ----------
  // Contradiction (ratio [0..1])
  const contrad01 = _safe(m.contradiction || 0);
  const contradPct = Math.round(contrad01 * 100);
  const toneContrad = contrad01 >= 0.70 ? 'danger' : contrad01 >= 0.45 ? 'warn' : 'ok';

  // Cap (en % entier)
  const capPct = Math.round(_safe(m.cap || 0));
  const toneCap = capPct >= 10 ? 'danger' : capPct >= 5 ? 'warn' : capPct > 0 ? 'info' : 'muted';

  // Mode de gouvernance (impact vitesse d'exécution)
  const modeStr = String(m?.mode || 'Normal');
  const toneMode = /slow/i.test(modeStr) ? 'warn'
                   : /manual/i.test(modeStr) ? 'info'
                   : /auto|normal/i.test(modeStr) ? 'ok'
                   : 'muted';

  // Phase → ton direct (bull/neutral/bear)
  const phaseStr = String(m?.phase || 'neutral').toLowerCase();
  const tonePhase = phaseStr.includes('euphor') || phaseStr.includes('bull') ? 'ok'
                   : phaseStr.includes('bear') || phaseStr.includes('risk-off') ? 'danger'
                   : 'warn';

  // Footer source + live + time
  const timeStr = (() => {
    try { return m.updated ? new Date(m.updated).toLocaleTimeString() : ''; } catch { return ''; }
  })();

  container.innerHTML = `
    <div class="di-panel">
      <div class="di-grid">
        <div class="di-left">
          <div class="di-title-row">
            <div class="di-title">DECISION INDEX</div>
            <button class="di-help-trigger" aria-label="Aide Decision Index" aria-expanded="false" aria-controls="di-help-popover" type="button">ℹ️</button>
          </div>
          <div class="di-score">${Math.round(data.di)}</div>

          <div class="di-progress">
            <canvas id="${container.id}-stack-chart" class="di-stack-canvas"></canvas>
          </div>

          ${breakdown}

          <div class="trend-section">
            <div class="trend-title">Trend (${tw.n}j)</div>
            <div class="trend-grid">
              <div class="trend-left">
                ${trendSpark}
              </div>
              <div class="trend-right">
                ${trendRight}
              </div>
            </div>
          </div>

          ${regimeRibbon}
        </div>

        <div class="di-right">
          <div class="di-rightgrid">
            <div class="box box-decision">
              <div class="box-title">Décision</div>
              <div class="kv"><span>Phase</span><span class="pill pill--${tonePhase}">${m.phase || 'Neutral'}</span></div>
              <div class="kv"><span>Contradiction</span><span class="pill pill--${toneContrad}">${contradPct}%</span></div>
              <div class="kv"><span>Cap actif</span><span class="pill pill--${toneCap}">${capPct}%</span></div>
              <div class="kv"><span>Mode</span><span class="pill pill--${toneMode}">${modeStr}</span></div>
            </div>
            <div class="box box-system">
              <div class="box-title">Système</div>
              <div class="kv"><span>Backend</span><span class="pill pill--${m.backend ? 'ok':'danger'}">${m.backend ? 'healthy':'down'}</span></div>
              <div class="kv"><span>Signals</span><span class="pill pill--${m.signals ? 'ok':'warn'}">${m.signals ? 'healthy' : (m.signals_status || 'limited')}</span></div>
              <div class="kv"><span>Governance</span><span class="pill pill--info">${m.governance_mode || '—'}</span></div>
            </div>
          </div>
        </div>
      </div>

      <div class="di-footer-compact">
        Source: ${m.source || '—'} • Live: ${m.live ? 'ON' : 'OFF'}${timeStr ? ' • ' + timeStr : ''}
      </div>

      ${renderHelpContent()}
    </div>
  `;

  // Render chart
  const stackCanvas = document.getElementById(`${container.id}-stack-chart`);
  if (stackCanvas) {
    chartInstances.stacked = renderStackedBar(stackCanvas, contribs, data.weights, data.scores, opts);
  }

  // Monter tooltip sur barre
  mountSegmentTooltip(container, data);

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
