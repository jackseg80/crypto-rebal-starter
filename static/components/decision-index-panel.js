/**
 * Decision Index Panel v6.1 - Health Bar Gaming Design (Compact 2-Column)
 *
 * Layout 2 colonnes compact avec barres de progression gaming
 * - Colonne gauche: Score DI principal + trend
 * - Colonne droite: 3 barres piliers + stats
 * - Design gaming compact et moderne
 * - Performance optimisée
 *
 * @version 6.1.0
 * @date 2025-01-15
 */

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
 * Détermine la couleur en format CSS
 */
function getScoreColor(score) {
  const level = getScoreLevel(score);
  switch(level) {
    case 'excellent': return '#10b981'; // green
    case 'good': return '#3b82f6'; // blue
    case 'medium': return '#f59e0b'; // amber
    case 'warning': return '#ef4444'; // red
    case 'danger': return '#991b1b'; // dark red
    default: return '#6b7280'; // gray
  }
}

/**
 * Génère un gradient pour la barre principale
 */
function getGradientForScore(score) {
  if (score >= 75) {
    return 'linear-gradient(90deg, #059669 0%, #10b981 50%, #34d399 100%)';
  } else if (score >= 60) {
    return 'linear-gradient(90deg, #2563eb 0%, #3b82f6 50%, #60a5fa 100%)';
  } else if (score >= 45) {
    return 'linear-gradient(90deg, #d97706 0%, #f59e0b 50%, #fbbf24 100%)';
  } else if (score >= 30) {
    return 'linear-gradient(90deg, #dc2626 0%, #ef4444 50%, #f87171 100%)';
  }
  return 'linear-gradient(90deg, #7f1d1d 0%, #991b1b 50%, #dc2626 100%)';
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
 * Calcule le texte du niveau
 */
function getLevelText(score) {
  const level = getScoreLevel(score);
  switch(level) {
    case 'excellent': return 'Excellent';
    case 'good': return 'Bon';
    case 'medium': return 'Moyen';
    case 'warning': return 'Faible';
    case 'danger': return 'Critique';
    default: return 'N/A';
  }
}

/**
 * Calcule la trend pour affichage avec sigma
 */
function computeTrendInfo(history) {
  const arr = Array.isArray(history) ? history.map(h => (h?.di ?? h) ?? 0) : [];
  if (arr.length < 2) return { delta: 0, trend: '→', color: 'neutral', sigma: 0, state: 'N/A' };

  const recent = arr.slice(-7);
  const delta = recent[recent.length - 1] - recent[0];

  // Calcul sigma (volatilité)
  const avg = recent.reduce((a, b) => a + b, 0) / recent.length;
  const variance = recent.reduce((a, b) => a + (b - avg) ** 2, 0) / recent.length;
  const sigma = Math.sqrt(variance);

  // État
  let state = 'Stable';
  if (delta > 1) state = 'Haussier';
  else if (delta < -1) state = 'Baissier';

  return {
    delta: _round(delta, 1),
    trend: delta > 0 ? '↗' : delta < 0 ? '↘' : '→',
    color: delta > 1 ? 'positive' : delta < -1 ? 'negative' : 'neutral',
    sigma: _round(sigma, 1),
    state
  };
}

/**
 * Calcule les contributions relatives (w×s)/Σ
 */
function calculateRelativeContributions(weights, scores) {
  const epsilon = 1e-6;

  const raw = {
    cycle: (weights.cycle || 0) * (scores.cycle || 0),
    onchain: (weights.onchain || 0) * (scores.onchain || 0),
    risk: (weights.risk || 0) * (scores.risk || 0)
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
 * Génère mini sparkline SVG compact
 */
function renderMiniSparkline(series, width = 60, height = 16) {
  if (!Array.isArray(series) || series.length < 2) {
    return '<span class="no-data">—</span>';
  }

  const validSeries = series.filter(v => typeof v === 'number' && Number.isFinite(v));
  if (validSeries.length < 2) {
    return '<span class="no-data">—</span>';
  }

  const min = Math.min(...validSeries);
  const max = Math.max(...validSeries);
  const span = (max - min) || 1;
  const px = (i) => (i / (validSeries.length - 1)) * (width - 2) + 1;
  const py = (v) => height - ((v - min) / span) * (height - 2) - 1;
  const d = validSeries.map((v, i) => `${i === 0 ? 'M' : 'L'} ${px(i).toFixed(1)} ${py(v).toFixed(1)}`).join(' ');

  return `
    <svg class="mini-spark" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <path d="${d}" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.6"/>
    </svg>
  `;
}

/**
 * Génère la barre de contributions empilée (CSS pur)
 */
function renderContributionBar(contributions) {
  const c = contributions;
  return `
    <div class="contribution-bar">
      <div class="contribution-seg cycle" style="width: ${c.cycle}%;" title="Cycle: ${c.cycle.toFixed(1)}%"></div>
      <div class="contribution-seg onchain" style="width: ${c.onchain}%;" title="On-Chain: ${c.onchain.toFixed(1)}%"></div>
      <div class="contribution-seg risk" style="width: ${c.risk}%;" title="Risk: ${c.risk.toFixed(1)}%"></div>
    </div>
  `;
}

/**
 * Génère le breakdown des scores (ligne compacte)
 */
function renderScoresBreakdown(scores) {
  return `
    <div class="scores-breakdown">
      <span class="score-item cycle">🔄 <b>${Math.round(scores.cycle || 0)}</b></span>
      <span class="sep">·</span>
      <span class="score-item onchain">🔗 <b>${Math.round(scores.onchain || 0)}</b></span>
      <span class="sep">·</span>
      <span class="score-item risk">🛡️ <b>${Math.round(scores.risk || 0)}</b></span>
    </div>
  `;
}

/**
 * Génère le régime ribbon compact (3 barres)
 */
function renderRegimeRibbon(meta, regimeHistory) {
  const rHist = Array.isArray(regimeHistory) ? regimeHistory.slice(-5) : [];
  const phaseName = (meta?.phase || 'Neutral').toLowerCase();

  let activeIdx = 1; // Neutral par défaut
  if (phaseName.includes('euphor') || phaseName.includes('bull') || phaseName.includes('risk-on')) {
    activeIdx = 0;
  } else if (phaseName.includes('bear') || phaseName.includes('risk-off') || phaseName.includes('prudence')) {
    activeIdx = 2;
  }

  // Override avec historique si disponible
  if (rHist.length > 0) {
    const actives = rHist.filter(x => (x?.active ?? x?.bull ?? x?.risk_on ?? false)).length;
    activeIdx = actives >= 4 ? 0 : (actives <= 1 ? 2 : 1);
  }

  const labels = ['🚀 Bull', '⚖️ Neutral', '🐻 Bear'];
  const bars = labels.map((lab, idx) => {
    const isActive = idx === activeIdx;
    return `<div class="regime-bar ${isActive ? 'active' : ''}" title="${lab}">${lab}</div>`;
  }).join('');

  return `
    <div class="regime-ribbon">
      <div class="regime-title">RÉGIME</div>
      <div class="regime-bars">${bars}</div>
    </div>
  `;
}

/**
 * Génère la colonne gauche avec score principal
 */
function renderLeftColumn(data) {
  const score = Math.round(data.di);
  const gradient = getGradientForScore(score);
  const levelText = getLevelText(score);
  const trendInfo = computeTrendInfo(data.history);
  const sparkline = renderMiniSparkline(data.history?.slice(-7));
  const m = data.meta || {};

  // Calculer contributions
  const contributions = calculateRelativeContributions(data.weights || {}, data.scores || {});
  const contributionBar = renderContributionBar(contributions);
  const scoresBreakdown = renderScoresBreakdown(data.scores || {});
  const regimeRibbon = renderRegimeRibbon(m, data.regimeHistory);

  // Sigma color
  const sigmaColor = trendInfo.sigma < 1 ? 'ok' : trendInfo.sigma <= 2 ? 'warn' : 'danger';

  return `
    <div class="di-left-col">
      <div class="di-header-compact">
        <div class="di-title-row">
          <span class="di-title">DECISION INDEX</span>
          <button class="di-help-btn" aria-label="Aide" type="button">?</button>
        </div>
      </div>

      <div class="di-score-section">
        <div class="di-score-big">${score}</div>
        <div class="di-score-label">${levelText}</div>
      </div>

      <div class="di-main-bar-compact">
        <div class="di-bar-track">
          <div class="di-bar-fill" style="width: ${score}%; background: ${gradient};">
            <div class="di-bar-glow"></div>
          </div>
          <div class="di-bar-segments">
            ${Array(10).fill(0).map((_, i) =>
              `<div class="seg ${(i+1)*10 <= score ? 'on' : ''}"></div>`
            ).join('')}
          </div>
        </div>
        <div class="di-bar-labels">
          <span>0</span>
          <span>25</span>
          <span>50</span>
          <span>75</span>
          <span>100</span>
        </div>
      </div>

      ${scoresBreakdown}

      <div class="contribution-section">
        <div class="contribution-title">CONTRIBUTIONS</div>
        ${contributionBar}
      </div>

      <div class="di-trend-compact">
        <div class="trend-header">
          <span class="trend-title">TREND (7j)</span>
          <div class="trend-badges">
            <span class="trend-badge ${trendInfo.color}">${trendInfo.trend} ${trendInfo.delta > 0 ? '+' : ''}${trendInfo.delta}</span>
            <span class="trend-badge ${sigmaColor}">σ ${trendInfo.sigma}</span>
            <span class="trend-badge state">${trendInfo.state}</span>
          </div>
        </div>
        <div class="trend-spark">${sparkline}</div>
      </div>

      ${regimeRibbon}
    </div>
  `;
}

/**
 * Génère une barre de pilier compacte
 */
function renderCompactPillarBar(label, icon, value, subtext, confidence, color) {
  const percentage = Math.min(100, Math.max(0, value));
  const barColor = color || getScoreColor(value);

  return `
    <div class="pillar-bar-compact">
      <div class="pillar-header">
        <div class="pillar-label">
          <span class="pillar-icon">${icon}</span>
          <span class="pillar-name">${label}</span>
          ${confidence ? `<span class="conf-chip">${confidence}%</span>` : ''}
        </div>
        <div class="pillar-score">${Math.round(value)}</div>
      </div>
      <div class="pillar-track">
        <div class="pillar-fill" style="width: ${percentage}%; background: ${barColor};"></div>
      </div>
      ${subtext ? `<div class="pillar-sub">${subtext}</div>` : ''}
    </div>
  `;
}

/**
 * Génère la colonne droite avec les piliers
 */
function renderRightColumn(data) {
  const s = data.scores || {};
  const m = data.meta || {};

  // Préparer les données pour chaque pilier
  const cycleConf = m.cycle_confidence ? Math.round(m.cycle_confidence * 100) : null;
  const cyclePhase = m.cycle_phase || m.phase || 'Unknown';
  const cycleMonths = m.cycle_months;

  const onchainConf = m.onchain_confidence ? Math.round(m.onchain_confidence * 100) : null;
  const onchainCritiques = m.onchain_critiques || 0;

  const riskVar = m.risk_var95;
  const riskBudget = m.risk_budget;

  const cycleBar = renderCompactPillarBar(
    'Cycle', '🔄', s.cycle || 0,
    cycleMonths ? `${cyclePhase} • ${Math.round(cycleMonths)}m` : cyclePhase,
    cycleConf,
    '#3b82f6'
  );

  const onchainBar = renderCompactPillarBar(
    'On-Chain', '🔗', s.onchain || 0,
    `${onchainCritiques} signaux critiques`,
    onchainConf,
    '#8b5cf6'
  );

  const riskBar = renderCompactPillarBar(
    'Risk', '🛡️', s.risk || 0,
    riskVar ? `VaR: ${Math.round(Math.abs(riskVar) * 1000) / 10}%` :
    (riskBudget ? `R: ${riskBudget.risky}% • S: ${riskBudget.stables}%` : null),
    null,
    '#ef4444'
  );

  // Fear & Greed compact
  const sentimentFG = m.sentiment_fg || '—';
  const sentimentColor = typeof sentimentFG === 'number' ?
    (sentimentFG >= 70 ? '#ef4444' : sentimentFG >= 30 ? '#f59e0b' : '#10b981') : '#6b7280';

  return `
    <div class="di-right-col">
      <div class="pillars-container">
        ${cycleBar}
        ${onchainBar}
        ${riskBar}
      </div>

      <div class="di-footer-stats">
        <div class="footer-stat">
          <span class="footer-label">Fear & Greed</span>
          <span class="footer-value" style="color: ${sentimentColor}">${sentimentFG}</span>
        </div>
        <div class="footer-stat">
          <span class="footer-label">Status</span>
          <span class="footer-value ${m.live ? 'live' : 'offline'}">${m.live ? '● Live' : '○ Off'}</span>
        </div>
        <div class="footer-stat">
          <span class="footer-label">Source</span>
          <span class="footer-value">${m.source || 'N/A'}</span>
        </div>
      </div>
    </div>
  `;
}

/**
 * Génère le contenu d'aide
 */
function renderHelpContent() {
  return `
    <div class="di-help-popup" style="display: none;" role="dialog" aria-labelledby="di-help-title" aria-modal="true">
      <div class="di-help-content">
        <div class="di-help-header">
          <h3 id="di-help-title">📊 Decision Index</h3>
          <button class="di-help-close" aria-label="Fermer" type="button">×</button>
        </div>
        <div class="di-help-body">
          <p><strong>Score DI (0-100)</strong><br>
          Indicateur composite des conditions de marché.<br>
          75+ Excellent | 60+ Bon | 45+ Moyen | 30+ Faible | <30 Critique</p>

          <p><strong>Piliers</strong><br>
          🔄 Cycle: Position dans le cycle de marché<br>
          🔗 On-Chain: Métriques blockchain<br>
          🛡️ Risk: Gestion du risque et volatilité</p>

          <p><strong>Indicateurs</strong><br>
          Trend: Évolution sur 7 jours<br>
          Régime: Phase de marché actuelle<br>
          F&G: Sentiment Fear & Greed</p>
        </div>
      </div>
    </div>
  `;
}

/**
 * Monte le système d'aide
 */
function mountHelpSystem(container) {
  const trigger = container.querySelector('.di-help-btn');
  const popup = container.querySelector('.di-help-popup');
  const closeBtn = container.querySelector('.di-help-close');

  if (!trigger || !popup) return;

  const toggleHelp = (show) => {
    if (show) {
      helpPopoverState.isOpen = true;
      helpPopoverState.lastFocusedElement = document.activeElement;
      popup.style.display = 'block';
      trigger.setAttribute('aria-expanded', 'true');
      setTimeout(() => popup.classList.add('show'), 10);
    } else {
      helpPopoverState.isOpen = false;
      popup.classList.remove('show');
      trigger.setAttribute('aria-expanded', 'false');
      setTimeout(() => popup.style.display = 'none', 300);
    }
  };

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleHelp(!helpPopoverState.isOpen);
  });

  if (closeBtn) {
    closeBtn.addEventListener('click', () => toggleHelp(false));
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && helpPopoverState.isOpen) {
      toggleHelp(false);
    }
  });

  document.addEventListener('click', (e) => {
    if (helpPopoverState.isOpen && !popup.contains(e.target) && e.target !== trigger) {
      toggleHelp(false);
    }
  });
}

/**
 * Ajoute les styles CSS
 */
function injectStyles() {
  const styleId = 'di-gaming-styles';
  if (document.getElementById(styleId)) return;

  const styles = document.createElement('style');
  styles.id = styleId;
  styles.textContent = `
    /* Container principal 2 colonnes */
    .di-panel-gaming {
      background: linear-gradient(135deg,
        rgba(15, 23, 42, 0.95) 0%,
        rgba(30, 41, 59, 0.95) 100%);
      border: 1px solid rgba(148, 163, 184, 0.1);
      border-radius: 12px;
      padding: 1.25rem;
      backdrop-filter: blur(10px);
      box-shadow:
        0 10px 25px -5px rgba(0, 0, 0, 0.1),
        0 8px 10px -6px rgba(0, 0, 0, 0.1);
      position: relative;
      overflow: hidden;
    }

    /* Layout 2 colonnes */
    .di-layout-2col {
      display: grid;
      grid-template-columns: 1fr 1.2fr;
      gap: 2rem;
      position: relative;
      z-index: 1;
    }

    /* Colonne gauche */
    .di-left-col {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .di-header-compact {
      margin-bottom: 0.25rem;
    }

    .di-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .di-title {
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: rgba(148, 163, 184, 0.8);
    }

    .di-help-btn {
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: rgba(59, 130, 246, 0.2);
      border: 1px solid rgba(59, 130, 246, 0.3);
      color: #60a5fa;
      font-size: 0.75rem;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .di-help-btn:hover {
      background: rgba(59, 130, 246, 0.3);
      transform: scale(1.1);
    }

    .di-score-section {
      display: flex;
      align-items: baseline;
      gap: 1rem;
      margin: 0.5rem 0;
    }

    .di-score-big {
      font-size: 3.5rem;
      font-weight: 800;
      line-height: 1;
      background: linear-gradient(135deg, #fff 0%, #cbd5e1 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .di-score-label {
      font-size: 1rem;
      font-weight: 600;
      color: rgba(148, 163, 184, 0.8);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    /* Barre principale compacte */
    .di-main-bar-compact {
      margin: 0.75rem 0;
    }

    .di-bar-track {
      position: relative;
      height: 24px;
      background: rgba(15, 23, 42, 0.5);
      border-radius: 999px;
      overflow: hidden;
      box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
    }

    .di-bar-fill {
      height: 100%;
      position: relative;
      border-radius: 999px;
      transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 0 20px rgba(0, 0, 0, 0.3);
    }

    .di-bar-glow {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 40%;
      background: linear-gradient(180deg,
        rgba(255, 255, 255, 0.3) 0%,
        transparent 100%);
    }

    .di-bar-segments {
      position: absolute;
      top: 2px;
      left: 2px;
      right: 2px;
      bottom: 2px;
      display: flex;
      gap: 2px;
      pointer-events: none;
    }

    .di-bar-segments .seg {
      flex: 1;
      background: rgba(0, 0, 0, 0.3);
      border-radius: 2px;
      transition: all 0.3s;
    }

    .di-bar-segments .seg.on {
      background: transparent;
    }

    .di-bar-labels {
      display: flex;
      justify-content: space-between;
      margin-top: 0.25rem;
      font-size: 0.625rem;
      color: rgba(148, 163, 184, 0.5);
    }

    /* Scores breakdown */
    .scores-breakdown {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      padding: 0.375rem 0;
      font-size: 0.75rem;
      color: rgba(226, 232, 240, 0.8);
    }

    .score-item {
      display: flex;
      align-items: center;
      gap: 0.25rem;
    }

    .score-item b {
      font-weight: 700;
      color: rgba(226, 232, 240, 1);
    }

    .scores-breakdown .sep {
      color: rgba(148, 163, 184, 0.4);
      font-weight: 300;
    }

    /* Contribution bar */
    .contribution-section {
      margin: 0.75rem 0;
    }

    .contribution-title {
      font-size: 0.625rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: rgba(148, 163, 184, 0.6);
      margin-bottom: 0.375rem;
    }

    .contribution-bar {
      display: flex;
      height: 16px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(15, 23, 42, 0.5);
      box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3);
    }

    .contribution-seg {
      height: 100%;
      transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      cursor: help;
    }

    .contribution-seg.cycle {
      background: linear-gradient(90deg, #2563eb 0%, #3b82f6 100%);
    }

    .contribution-seg.onchain {
      background: linear-gradient(90deg, #7c3aed 0%, #8b5cf6 100%);
    }

    .contribution-seg.risk {
      background: linear-gradient(90deg, #dc2626 0%, #ef4444 100%);
    }

    .contribution-seg::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 40%;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.3) 0%, transparent 100%);
    }

    /* Trend compact amélioré */
    .di-trend-compact {
      background: rgba(30, 41, 59, 0.3);
      border-radius: 6px;
      padding: 0.5rem 0.75rem;
      border: 1px solid rgba(148, 163, 184, 0.05);
    }

    .trend-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.375rem;
    }

    .trend-title {
      font-size: 0.625rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: rgba(148, 163, 184, 0.6);
    }

    .trend-badges {
      display: flex;
      gap: 0.25rem;
    }

    .trend-badge {
      background: rgba(15, 23, 42, 0.5);
      padding: 0.125rem 0.375rem;
      border-radius: 999px;
      font-size: 0.625rem;
      font-weight: 600;
      border: 1px solid rgba(148, 163, 184, 0.1);
    }

    .trend-badge.positive {
      color: #10b981;
      background: rgba(16, 185, 129, 0.1);
      border-color: rgba(16, 185, 129, 0.3);
    }

    .trend-badge.negative {
      color: #ef4444;
      background: rgba(239, 68, 68, 0.1);
      border-color: rgba(239, 68, 68, 0.3);
    }

    .trend-badge.neutral {
      color: #f59e0b;
      background: rgba(245, 158, 11, 0.1);
      border-color: rgba(245, 158, 11, 0.3);
    }

    .trend-badge.ok {
      color: #10b981;
    }

    .trend-badge.warn {
      color: #f59e0b;
    }

    .trend-badge.danger {
      color: #ef4444;
    }

    .trend-badge.state {
      color: rgba(226, 232, 240, 0.8);
    }

    .trend-spark {
      display: flex;
      justify-content: center;
      margin-top: 0.25rem;
    }

    /* Regime ribbon */
    .regime-ribbon {
      background: rgba(30, 41, 59, 0.3);
      border-radius: 6px;
      padding: 0.5rem 0.75rem;
      border: 1px solid rgba(148, 163, 184, 0.05);
    }

    .regime-title {
      font-size: 0.625rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: rgba(148, 163, 184, 0.6);
      margin-bottom: 0.375rem;
    }

    .regime-bars {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.375rem;
    }

    .regime-bar {
      text-align: center;
      padding: 0.25rem 0.375rem;
      border-radius: 4px;
      font-size: 0.625rem;
      font-weight: 600;
      background: rgba(15, 23, 42, 0.3);
      color: rgba(148, 163, 184, 0.5);
      border: 1px solid rgba(148, 163, 184, 0.1);
      transition: all 0.3s;
    }

    .regime-bar.active {
      background: rgba(59, 130, 246, 0.2);
      color: #60a5fa;
      border-color: rgba(59, 130, 246, 0.4);
      box-shadow: 0 0 10px rgba(59, 130, 246, 0.2);
    }

    /* Meta info compact */
    .di-meta-compact {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }

    .meta-item {
      background: rgba(30, 41, 59, 0.3);
      border-radius: 6px;
      padding: 0.5rem;
      border: 1px solid rgba(148, 163, 184, 0.05);
    }

    .meta-label {
      display: block;
      font-size: 0.625rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: rgba(148, 163, 184, 0.6);
      margin-bottom: 0.125rem;
    }

    .meta-value {
      font-size: 0.875rem;
      font-weight: 600;
      color: rgba(226, 232, 240, 0.9);
    }

    /* Colonne droite */
    .di-right-col {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .pillars-container {
      display: flex;
      flex-direction: column;
      gap: 0.875rem;
    }

    /* Barres de piliers compactes */
    .pillar-bar-compact {
      background: rgba(30, 41, 59, 0.3);
      border-radius: 6px;
      padding: 0.625rem 0.75rem;
      border: 1px solid rgba(148, 163, 184, 0.05);
      transition: all 0.3s;
    }

    .pillar-bar-compact:hover {
      background: rgba(30, 41, 59, 0.5);
      transform: translateX(2px);
    }

    .pillar-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.375rem;
    }

    .pillar-label {
      display: flex;
      align-items: center;
      gap: 0.375rem;
    }

    .pillar-icon {
      font-size: 0.875rem;
    }

    .pillar-name {
      font-size: 0.75rem;
      font-weight: 600;
      color: rgba(226, 232, 240, 0.9);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .conf-chip {
      background: rgba(59, 130, 246, 0.2);
      color: #60a5fa;
      padding: 0.125rem 0.25rem;
      border-radius: 999px;
      font-size: 0.5rem;
      font-weight: 600;
    }

    .pillar-score {
      font-size: 1.25rem;
      font-weight: 700;
      color: rgba(226, 232, 240, 1);
    }

    .pillar-track {
      position: relative;
      height: 12px;
      background: rgba(15, 23, 42, 0.5);
      border-radius: 999px;
      overflow: hidden;
      box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.3);
    }

    .pillar-fill {
      height: 100%;
      position: relative;
      border-radius: 999px;
      transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 0 8px currentColor;
    }

    .pillar-sub {
      margin-top: 0.25rem;
      font-size: 0.625rem;
      color: rgba(148, 163, 184, 0.7);
    }

    /* Footer stats */
    .di-footer-stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.5rem;
      margin-top: auto;
      padding-top: 0.75rem;
      border-top: 1px solid rgba(148, 163, 184, 0.1);
    }

    .footer-stat {
      text-align: center;
    }

    .footer-label {
      display: block;
      font-size: 0.5rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: rgba(148, 163, 184, 0.5);
      margin-bottom: 0.125rem;
    }

    .footer-value {
      font-size: 0.75rem;
      font-weight: 600;
      color: rgba(226, 232, 240, 0.8);
    }

    .footer-value.live {
      color: #10b981;
    }

    .footer-value.offline {
      color: #ef4444;
    }

    /* Sparkline */
    .mini-spark {
      display: block;
      color: rgba(148, 163, 184, 0.5);
    }

    .no-data {
      color: rgba(148, 163, 184, 0.3);
      font-size: 0.75rem;
    }

    /* Popup d'aide compact */
    .di-help-popup {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%) scale(0.95);
      width: min(400px, 90vw);
      max-height: 70vh;
      background: linear-gradient(135deg,
        rgba(15, 23, 42, 0.98) 0%,
        rgba(30, 41, 59, 0.98) 100%);
      border: 1px solid rgba(148, 163, 184, 0.2);
      border-radius: 12px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
      z-index: 1000;
      opacity: 0;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      backdrop-filter: blur(20px);
    }

    .di-help-popup.show {
      opacity: 1;
      transform: translate(-50%, -50%) scale(1);
    }

    .di-help-content {
      padding: 1.25rem;
      overflow-y: auto;
      max-height: 70vh;
    }

    .di-help-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }

    .di-help-header h3 {
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
      color: rgba(226, 232, 240, 1);
    }

    .di-help-close {
      background: none;
      border: none;
      font-size: 1.25rem;
      color: rgba(148, 163, 184, 0.5);
      cursor: pointer;
      padding: 0.25rem;
      transition: all 0.2s;
      border-radius: 4px;
    }

    .di-help-close:hover {
      color: rgba(226, 232, 240, 1);
      background: rgba(239, 68, 68, 0.1);
    }

    .di-help-body {
      color: rgba(203, 213, 225, 0.9);
      line-height: 1.5;
      font-size: 0.75rem;
    }

    .di-help-body p {
      margin: 0 0 0.75rem 0;
    }

    .di-help-body p:last-child {
      margin-bottom: 0;
    }

    /* Responsive */
    @media (max-width: 768px) {
      .di-layout-2col {
        grid-template-columns: 1fr;
        gap: 1.5rem;
      }

      .di-score-big {
        font-size: 3rem;
      }

      .di-footer-stats {
        grid-template-columns: repeat(3, 1fr);
      }
    }

    @media (max-width: 480px) {
      .di-panel-gaming {
        padding: 1rem;
      }

      .di-score-big {
        font-size: 2.5rem;
      }

      .di-meta-compact {
        grid-template-columns: 1fr;
      }
    }

    /* Light mode */
    @media (prefers-color-scheme: light) {
      .di-panel-gaming {
        background: linear-gradient(135deg,
          rgba(255, 255, 255, 0.95) 0%,
          rgba(248, 250, 252, 0.95) 100%);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05);
      }

      .di-bar-track,
      .pillar-track {
        background: rgba(226, 232, 240, 0.5);
      }

      .pillar-bar-compact,
      .di-trend-compact,
      .meta-item {
        background: rgba(248, 250, 252, 0.5);
      }

      .di-score-big {
        background: linear-gradient(135deg, #1e293b 0%, #475569 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }

      .pillar-name,
      .pillar-score,
      .meta-value {
        color: #1e293b;
      }

      .di-title,
      .trend-title,
      .meta-label {
        color: #64748b;
      }
    }
  `;

  document.head.appendChild(styles);
}

/**
 * Render principal du panneau
 */
function _renderDIPanelInternal(container, data, opts = {}) {
  if (!container) {
    console.error('❌ DI Panel: container element not found');
    return;
  }

  // Injecter les styles si nécessaire
  injectStyles();

  // Générer les colonnes
  const leftCol = renderLeftColumn(data);
  const rightCol = renderRightColumn(data);

  // Construire le panneau complet
  container.innerHTML = `
    <div class="di-panel-gaming">
      <div class="di-layout-2col">
        ${leftCol}
        ${rightCol}
      </div>
      ${renderHelpContent()}
    </div>
  `;

  // Monter le système d'aide
  mountHelpSystem(container);
}

/**
 * Fonction publique principale avec debounce
 */
export function renderDecisionIndexPanel(container, data, opts = {}) {
  clearTimeout(refreshTimeout);
  refreshTimeout = setTimeout(() => {
    _renderDIPanelInternal(container, data, opts);
  }, 100);
}

/**
 * Cleanup
 */
export function destroyDIPanelCharts() {
  // Plus de charts à détruire dans cette version
  // Gardé pour compatibilité
}

/**
 * Helper pour s'assurer que les dépendances sont chargées
 */
export async function ensureChartJSLoaded() {
  // Plus besoin de Chart.js dans cette version
  // Gardé pour compatibilité
  return true;
}

// Logger minimal
const debugLogger = {
  debug: (...args) => console.debug('[DI Panel]', ...args),
  error: (...args) => console.error('[DI Panel]', ...args),
  warn: (...args) => console.warn('[DI Panel]', ...args)
};

if (typeof window !== 'undefined') {
  window.debugLogger = debugLogger;
}