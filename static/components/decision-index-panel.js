/**
 * Decision Index Panel v7.1 - Actionnable Design with Smart Recommendations
 *
 * Layout 2 colonnes équilibré avec recommandations contextuelles
 * - Colonne gauche: Score DI + Barre + Contributions annotées + Métadonnées
 * - Colonne droite: Recommandation intelligente + 3 piliers (Cycle, On-Chain, Risk) + Footer stats
 * - Design gaming compact et moderne
 * - Focus sur l'actionnable (suppression trend/régime redondants)
 *
 * Changements v7.1:
 * - ✅ Recommandations contextuelles intelligentes basées sur DI + piliers
 * - ✅ Actions spécifiques avec pourcentages d'allocation
 * - ✅ Alertes adaptatives (On-Chain critique, Risk faible, etc.)
 * - ✅ Format structuré : Titre + Action + Détails
 *
 * Changements v7.0:
 * - ✅ Contributions annotées (scores alignés avec barres)
 * - ✅ Recommandation actionnable basée sur le DI (déplacée à droite pour équilibrage)
 * - ✅ Métadonnées utiles (confiance, mode, freshness)
 * - ❌ Supprimé: Trend 7j + sparkline (jamais visible)
 * - ❌ Supprimé: Régime ribbon (redondant avec piliers droite)
 *
 * @version 7.1.0
 * @date 2025-01-20
 */

// Debounce timeout
let refreshTimeout = null;

// État du popover d'aide
let helpPopoverState = {
  isOpen: false,
  lastFocusedElement: null
};

// AbortController pour nettoyer les event listeners (prévenir memory leaks)
let helpSystemController = null;

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
 * Génère un gradient progressif rouge → vert pour la barre principale
 * Utilise un dégradé continu basé sur le score actuel
 */
function getGradientForScore(score) {
  // Dégradé global rouge → orange → jaune → vert (fond de la track)
  const baseGradient = 'linear-gradient(90deg, ' +
    '#991b1b 0%, ' +      // 0%: Rouge foncé
    '#dc2626 15%, ' +     // 15%: Rouge
    '#ef4444 30%, ' +     // 30%: Rouge vif
    '#f97316 40%, ' +     // 40%: Orange
    '#f59e0b 50%, ' +     // 50%: Jaune-orange
    '#fbbf24 60%, ' +     // 60%: Jaune
    '#84cc16 70%, ' +     // 70%: Vert-jaune
    '#22c55e 80%, ' +     // 80%: Vert clair
    '#10b981 90%, ' +     // 90%: Vert
    '#059669 100%)';      // 100%: Vert vif

  // Calculer la couleur de fin basée sur le score
  let endColor;
  if (score <= 30) {
    endColor = '#dc2626'; // Rouge
  } else if (score <= 45) {
    endColor = '#f97316'; // Orange
  } else if (score <= 60) {
    endColor = '#fbbf24'; // Jaune
  } else if (score <= 75) {
    endColor = '#22c55e'; // Vert clair
  } else {
    endColor = '#10b981'; // Vert vif
  }

  // Gradient de la barre remplie (du rouge au score actuel)
  const fillGradient = 'linear-gradient(90deg, ' +
    '#991b1b 0%, ' +
    '#dc2626 15%, ' +
    '#ef4444 30%, ' +
    '#f97316 40%, ' +
    '#f59e0b 50%, ' +
    '#fbbf24 60%, ' +
    '#84cc16 70%, ' +
    '#22c55e 80%, ' +
    '#10b981 90%, ' +
    `${endColor} 100%)`;

  return fillGradient;
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
 * Génère la section complète Scores + Contributions (Option 2: Barre Annotée)
 */
function renderScoresAndContributions(scores, contributions) {
  const items = [
    { key: 'cycle', icon: '🔄', pct: contributions.cycle },
    { key: 'onchain', icon: '🔗', pct: contributions.onchain },
    { key: 'risk', icon: '🛡️', pct: contributions.risk }
  ];

  return `
    <div class="scores-contrib-annotated">
      <div class="contrib-title">CONTRIBUTIONS</div>

      <!-- Ligne 1: Icons + Scores -->
      <div class="contrib-labels-row">
        ${items.map(item => `
          <div class="contrib-label" style="width: ${item.pct}%;">
            <span class="label-icon">${item.icon}</span>
            <span class="label-score">${Math.round(scores[item.key] || 0)}</span>
          </div>
        `).join('')}
      </div>

      <!-- Ligne 2: Barre empilée -->
      <div class="contrib-bar-stacked">
        <div class="contrib-seg cycle" style="width: ${contributions.cycle}%;"></div>
        <div class="contrib-seg onchain" style="width: ${contributions.onchain}%;"></div>
        <div class="contrib-seg risk" style="width: ${contributions.risk}%;"></div>
      </div>

      <!-- Ligne 3: Pourcentages -->
      <div class="contrib-pcts-row">
        ${items.map(item => `
          <div class="contrib-pct" style="width: ${item.pct}%;">
            ${item.pct.toFixed(0)}%
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

/**
 * Génère la recommandation actionnable basée sur le DI et les piliers
 */
function renderRecommendation(score, meta, scores = {}) {
  let icon = '💡';
  let title = 'Position neutre';
  let action = 'Surveillance recommandée';
  let details = '';
  let colorClass = 'neutral';

  // Extraire les scores des piliers
  const cycle = scores.cycle || 0;
  const onchain = scores.onchain || 0;
  const risk = scores.risk || 0;

  // Détection d'alertes spécifiques
  const criticalOnchain = onchain < 30;
  const lowRisk = risk < 40;
  const strongCycle = cycle >= 70;

  // Logique de recommandation basée sur le DI global
  if (score >= 75) {
    icon = '🚀';
    title = 'Excellent timing';
    colorClass = 'bullish';

    if (strongCycle && onchain >= 50) {
      action = 'Allouer 15-20% vers actifs risqués';
      details = 'Cycle expansion + On-Chain favorable → Opportunité d\'accumulation';
    } else if (criticalOnchain) {
      action = 'Allouer avec prudence (10-15%)';
      details = 'Malgré DI élevé, signaux on-chain faibles → Vigilance requise';
    } else {
      action = 'Augmenter exposition risque progressivement';
      details = 'Conditions favorables → Réduire stables à 10-15%';
    }

  } else if (score >= 60) {
    icon = '✅';
    title = 'Position favorable';
    colorClass = 'positive';

    if (cycle >= 60 && risk >= 50) {
      action = 'Maintenir allocation actuelle';
      details = `Cycle ${Math.round(cycle)} + Risk ${Math.round(risk)} → Équilibre stable`;
    } else if (criticalOnchain) {
      action = 'Conserver mais surveiller on-chain';
      details = 'Signaux on-chain dégradés → Préparer ajustements si nécessaire';
    } else {
      action = 'Maintenir allocation, ajustements mineurs OK';
      details = 'Position solide → Rééquilibrage opportuniste possible';
    }

  } else if (score >= 45) {
    icon = '⚠️';
    title = 'Position mitigée';
    colorClass = 'warning';

    if (lowRisk) {
      action = 'Réduire exposition, sécuriser gains';
      details = `Risk faible (${Math.round(risk)}) → Augmenter stables à 25-30%`;
    } else if (criticalOnchain) {
      action = 'Privilégier la prudence absolue';
      details = 'Signaux on-chain critiques → Éviter nouvelles positions risquées';
    } else {
      action = 'Attente et surveillance renforcée';
      details = 'Contexte incertain → Éviter changements majeurs';
    }

  } else if (score >= 30) {
    icon = '🛡️';
    title = 'Position défavorable';
    colorClass = 'defensive';

    if (lowRisk && criticalOnchain) {
      action = 'Réduire exposition immédiatement';
      details = 'Risk + On-Chain faibles → Sécuriser 40-50% en stables';
    } else {
      action = 'Réduire actifs risqués à 30-40%';
      details = 'Conditions dégradées → Protéger le capital';
    }

  } else {
    icon = '🚨';
    title = 'ALERTE - Position critique';
    colorClass = 'critical';

    action = 'Sécuriser le portefeuille immédiatement';
    details = `DI ${score} → Passer 60-70% en stables, réduire levier`;
  }

  return `
    <div class="di-recommendation ${colorClass}">
      <div class="reco-content">
        <div class="reco-header">
          <span class="reco-icon">${icon}</span>
          <span class="reco-title">${title}</span>
        </div>
        <div class="reco-action">${action}</div>
        ${details ? `<div class="reco-details">${details}</div>` : ''}
      </div>
    </div>
  `;
}

/**
 * Génère les métadonnées utiles
 */
function renderMetadata(meta) {
  const confidence = meta.confidence ? `${Math.round(meta.confidence * 100)}%` : 'N/A';
  const mode = meta.mode || 'Standard';
  const source = meta.source || 'N/A';
  const timestamp = meta.timestamp || meta.last_update;

  let freshness = 'N/A';
  if (timestamp) {
    try {
      const diff = Date.now() - new Date(timestamp).getTime();
      const minutes = Math.floor(diff / 60000);
      if (minutes < 1) freshness = 'À l\'instant';
      else if (minutes < 60) freshness = `Il y a ${minutes}min`;
      else if (minutes < 1440) freshness = `Il y a ${Math.floor(minutes / 60)}h`;
      else freshness = `Il y a ${Math.floor(minutes / 1440)}j`;
    } catch (e) {
      freshness = 'Inconnu';
    }
  }

  return `
    <div class="di-metadata">
      <div class="meta-row">
        <span class="meta-label">Confiance</span>
        <span class="meta-value">${confidence}</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">Mode</span>
        <span class="meta-value">${mode}</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">Mise à jour</span>
        <span class="meta-value">${freshness}</span>
      </div>
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
  const m = data.meta || {};

  // Calculer contributions
  const contributions = calculateRelativeContributions(data.weights || {}, data.scores || {});
  const scoresAndContributions = renderScoresAndContributions(data.scores || {}, contributions);
  const metadata = renderMetadata(m);

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

      ${scoresAndContributions}
      ${metadata}
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
 * Génère la colonne droite avec recommandation + piliers
 */
function renderRightColumn(data) {
  const score = Math.round(data.di);
  const s = data.scores || {};
  const m = data.meta || {};

  // Recommandation en haut (avec scores pour contexte)
  const recommendation = renderRecommendation(score, m, s);

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
      ${recommendation}

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

          <p><strong>Piliers (colonne droite)</strong><br>
          🔄 Cycle: Position dans le cycle de marché<br>
          🔗 On-Chain: Métriques blockchain fondamentales<br>
          🛡️ Risk: Gestion du risque et volatilité</p>

          <p><strong>Contributions</strong><br>
          Pondération relative de chaque pilier dans le score final.<br>
          Les pourcentages indiquent l'impact de chaque dimension.</p>

          <p><strong>Recommandation</strong><br>
          Conseil d'action contextuel basé sur le DI + piliers:<br>
          • 75+ : Allouer vers risque (15-20%)<br>
          • 60-74 : Maintenir allocation actuelle<br>
          • 45-59 : Attente et prudence<br>
          • 30-44 : Réduire exposition (30-40% actifs)<br>
          • <30 : Sécuriser immédiatement (60-70% stables)<br>
          <br>
          La recommandation s'adapte selon les piliers :<br>
          • Si On-Chain critique : alertes spécifiques<br>
          • Si Risk faible : augmentation stables recommandée<br>
          • Si Cycle fort : opportunités d'accumulation</p>

          <p><strong>Métadonnées</strong><br>
          Confiance : Niveau de certitude du modèle<br>
          Mode : Type de calcul (Standard/Priority)<br>
          Mise à jour : Fraîcheur des données</p>
        </div>
      </div>
    </div>
  `;
}

/**
 * Monte le système d'aide avec cleanup automatique (prévenir memory leaks)
 */
function mountHelpSystem(container) {
  const trigger = container.querySelector('.di-help-btn');
  const popup = container.querySelector('.di-help-popup');
  const closeBtn = container.querySelector('.di-help-close');

  if (!trigger || !popup) return;

  // Cleanup des event listeners précédents
  if (helpSystemController) {
    helpSystemController.abort();
  }

  // Nouveau controller pour gérer tous les listeners de ce panel
  helpSystemController = new AbortController();
  const signal = helpSystemController.signal;

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

  // Tous les listeners utilisent le même signal pour cleanup automatique
  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleHelp(!helpPopoverState.isOpen);
  }, { signal });

  if (closeBtn) {
    closeBtn.addEventListener('click', () => toggleHelp(false), { signal });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && helpPopoverState.isOpen) {
      toggleHelp(false);
    }
  }, { signal });

  document.addEventListener('click', (e) => {
    if (helpPopoverState.isOpen && !popup.contains(e.target) && e.target !== trigger) {
      toggleHelp(false);
    }
  }, { signal });
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
      box-shadow:
        0 0 20px rgba(0, 0, 0, 0.3),
        0 0 30px currentColor,
        inset 0 1px 0 rgba(255, 255, 255, 0.2);
      overflow: hidden;
    }

    .di-bar-glow {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 50%;
      background: linear-gradient(180deg,
        rgba(255, 255, 255, 0.4) 0%,
        rgba(255, 255, 255, 0.1) 50%,
        transparent 100%);
      border-radius: 999px 999px 0 0;
    }

    /* Animation de brillance subtile */
    @keyframes shine {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }

    .di-bar-fill::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 30%;
      height: 100%;
      background: linear-gradient(90deg,
        transparent 0%,
        rgba(255, 255, 255, 0.3) 50%,
        transparent 100%);
      animation: shine 3s ease-in-out infinite;
      pointer-events: none;
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
      background: rgba(0, 0, 0, 0.15);
      border-radius: 2px;
      transition: all 0.3s;
      border-right: 1px solid rgba(0, 0, 0, 0.1);
    }

    .di-bar-segments .seg:last-child {
      border-right: none;
    }

    .di-bar-segments .seg.on {
      background: rgba(255, 255, 255, 0.05);
      border-right-color: rgba(255, 255, 255, 0.1);
    }

    .di-bar-labels {
      display: flex;
      justify-content: space-between;
      margin-top: 0.25rem;
      font-size: 0.625rem;
      color: rgba(148, 163, 184, 0.5);
    }

    /* Scores + Contributions Annotées (Option 2) */
    .scores-contrib-annotated {
      background: rgba(30, 41, 59, 0.3);
      border-radius: 6px;
      padding: 0.75rem;
      border: 1px solid rgba(148, 163, 184, 0.05);
      margin: 0.75rem 0;
    }

    .contrib-title {
      font-size: 0.625rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: rgba(148, 163, 184, 0.6);
      margin-bottom: 0.5rem;
      text-align: center;
    }

    /* Ligne 1: Labels (icons + scores) */
    .contrib-labels-row {
      display: flex;
      margin-bottom: 0.375rem;
    }

    .contrib-label {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.125rem;
      font-size: 0.75rem;
    }

    .label-icon {
      font-size: 0.875rem;
    }

    .label-score {
      font-weight: 700;
      color: rgba(226, 232, 240, 1);
      font-size: 0.875rem;
    }

    /* Ligne 2: Barre empilée */
    .contrib-bar-stacked {
      display: flex;
      height: 20px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(15, 23, 42, 0.5);
      box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
      margin-bottom: 0.375rem;
    }

    .contrib-seg {
      height: 100%;
      transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
    }

    .contrib-seg.cycle {
      background: linear-gradient(90deg, #2563eb 0%, #3b82f6 100%);
    }

    .contrib-seg.onchain {
      background: linear-gradient(90deg, #7c3aed 0%, #8b5cf6 100%);
    }

    .contrib-seg.risk {
      background: linear-gradient(90deg, #dc2626 0%, #ef4444 100%);
    }

    .contrib-seg::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 40%;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.3) 0%, transparent 100%);
    }

    /* Ligne 3: Pourcentages */
    .contrib-pcts-row {
      display: flex;
    }

    .contrib-pct {
      display: flex;
      justify-content: center;
      font-size: 0.625rem;
      font-weight: 600;
      color: rgba(148, 163, 184, 0.8);
    }

    /* Recommandation actionnable */
    .di-recommendation {
      background: rgba(30, 41, 59, 0.3);
      border-radius: 6px;
      padding: 0.875rem;
      border: 1px solid rgba(148, 163, 184, 0.1);
      margin-bottom: 1rem;
    }

    /* Recommandation dans colonne gauche (si elle y reste) */
    .di-left-col .di-recommendation {
      margin: 0.75rem 0;
    }

    /* Recommandation dans colonne droite (en haut) */
    .di-right-col .di-recommendation {
      margin: 0 0 1rem 0;
    }

    .reco-content {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .reco-header {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }

    .reco-icon {
      font-size: 1.25rem;
      flex-shrink: 0;
    }

    .reco-title {
      font-size: 0.8rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: rgba(226, 232, 240, 1);
    }

    .reco-action {
      font-size: 0.875rem;
      line-height: 1.4;
      color: rgba(226, 232, 240, 0.95);
      font-weight: 600;
    }

    .reco-details {
      font-size: 0.75rem;
      line-height: 1.5;
      color: rgba(148, 163, 184, 0.8);
      padding-top: 0.25rem;
      font-style: italic;
    }

    /* Variantes de couleur pour recommandation */
    .di-recommendation.bullish {
      border-color: rgba(16, 185, 129, 0.3);
      background: rgba(16, 185, 129, 0.05);
    }

    .di-recommendation.positive {
      border-color: rgba(59, 130, 246, 0.3);
      background: rgba(59, 130, 246, 0.05);
    }

    .di-recommendation.warning {
      border-color: rgba(245, 158, 11, 0.3);
      background: rgba(245, 158, 11, 0.05);
    }

    .di-recommendation.defensive {
      border-color: rgba(239, 68, 68, 0.3);
      background: rgba(239, 68, 68, 0.05);
    }

    .di-recommendation.critical {
      border-color: rgba(153, 27, 27, 0.4);
      background: rgba(153, 27, 27, 0.1);
    }

    /* Métadonnées */
    .di-metadata {
      background: rgba(30, 41, 59, 0.3);
      border-radius: 6px;
      padding: 0.75rem;
      border: 1px solid rgba(148, 163, 184, 0.05);
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.75rem;
    }

    .meta-row {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
      text-align: center;
    }

    .meta-label {
      font-size: 0.625rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: rgba(148, 163, 184, 0.6);
    }

    .meta-value {
      font-size: 0.75rem;
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

      .di-metadata {
        grid-template-columns: 1fr;
        gap: 0.5rem;
      }

      .meta-row {
        flex-direction: row;
        justify-content: space-between;
        text-align: left;
      }
    }

    @media (max-width: 480px) {
      .di-panel-gaming {
        padding: 1rem;
      }

      .di-score-big {
        font-size: 2.5rem;
      }

      .contrib-labels-row,
      .contrib-pcts-row {
        font-size: 0.65rem;
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
      .pillar-track,
      .contrib-bar-stacked {
        background: rgba(226, 232, 240, 0.5);
      }

      .pillar-bar-compact,
      .scores-contrib-annotated,
      .di-recommendation,
      .di-metadata {
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
      .meta-value,
      .label-score,
      .reco-title,
      .reco-action {
        color: #1e293b;
      }

      .di-title,
      .contrib-title,
      .meta-label,
      .reco-details {
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
 * Cleanup (détruit les event listeners pour prévenir memory leaks)
 */
export function destroyDIPanelCharts() {
  // Cleanup event listeners
  if (helpSystemController) {
    helpSystemController.abort();
    helpSystemController = null;
  }

  // Reset state
  helpPopoverState.isOpen = false;
  helpPopoverState.lastFocusedElement = null;
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