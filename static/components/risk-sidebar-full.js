// static/components/risk-sidebar-full.js
// Web Component : Parité pixel-par-pixel avec l'ancienne sidebar de risk-dashboard.html
// Affiche tous les scores + governance + alerts avec les mêmes styles

import { fetchRisk, waitForGlobalEventOrTimeout } from './utils.js';

/**
 * Normalise la réponse API vers le contrat RiskState attendu par _updateFromState()
 * Tolère structure à plat ou imbriquée sous { risk: {...} }
 * @param {Object} apiJson - Réponse brute de /api/risk/dashboard ou /api/risk/metrics
 * @returns {Object} RiskState normalisé
 */
function normalizeRiskState(apiJson) {
  if (!apiJson || typeof apiJson !== 'object') return {};

  // 1) Choisir la racine (plat vs sous 'risk')
  const root = apiJson.risk && typeof apiJson.risk === 'object' ? apiJson.risk : apiJson;

  // 2) Picks tolérants
  const governance = root.governance || {};
  const scores = root.scores || {};
  const ccs = root.ccs || {};
  const cycle = root.cycle || {};
  const targets = root.targets || root.target_changes || {};
  const alerts = Array.isArray(root.alerts) ? root.alerts : (root.active_alerts || []);

  // 3) Normalisations légères
  // contradiction: accepte 0..1 ou 0..100
  const rawContrad = governance.contradiction_index;
  let contradiction_index = Number(rawContrad);
  if (Number.isFinite(contradiction_index)) {
    if (contradiction_index > 1) contradiction_index = contradiction_index / 100;
    contradiction_index = Math.max(0, Math.min(1, contradiction_index));
  } else {
    contradiction_index = undefined;
  }

  // cap_daily: nombre 0..1
  let cap_daily = governance.cap_daily;
  if (!Number.isFinite(cap_daily)) cap_daily = governance.active_policy?.cap_daily;

  // timestamp
  const ml_signals_timestamp = governance.ml_signals_timestamp || governance.updated || null;

  // blended: accepter 2 noms
  const blended =
    Number.isFinite(scores.blended) ? scores.blended :
    (Number.isFinite(scores.blendedDecision) ? scores.blendedDecision : undefined);

  return {
    ccs: {
      score: Number.isFinite(ccs.score) ? ccs.score : undefined,
      label: ccs.label || ccs.status || undefined,
      ...ccs
    },
    scores: {
      onchain: Number.isFinite(scores.onchain) ? scores.onchain : undefined,
      risk: Number.isFinite(scores.risk) ? scores.risk : undefined,
      blended,
      blendedDecision: blended,
      ...scores
    },
    cycle,
    targets,
    governance: {
      ...governance,
      contradiction_index,
      cap_daily: Number.isFinite(cap_daily) ? cap_daily : undefined,
      ml_signals_timestamp
    },
    alerts
  };
}

class RiskSidebarFull extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.pollMs = Number(this.getAttribute('poll-ms') || 30000); // 0 => pas de polling
    this._unsub = null;
    this._poll = null;
  }

  connectedCallback() {
    this._render();
    this._afterConnect();
  }

  disconnectedCallback() {
    if (typeof this._unsub === 'function') {
      this._unsub();
      this._unsub = null;
    }
    if (this._poll) {
      clearInterval(this._poll);
      this._poll = null;
    }
  }

  async _afterConnect() {
    // Récupérer tous les éléments du Shadow DOM
    this.$ = {
      // CCS Mixte
      ccsMix: this.shadowRoot.querySelector('#ccs-ccs-mix'),
      ccsMixLabel: this.shadowRoot.querySelector('#ccs-mixte-label'),
      // On-Chain
      onchain: this.shadowRoot.querySelector('#kpi-onchain'),
      onchainLabel: this.shadowRoot.querySelector('#onchain-label'),
      // Risk
      risk: this.shadowRoot.querySelector('#kpi-risk'),
      riskLabel: this.shadowRoot.querySelector('#risk-label'),
      // Blended
      blended: this.shadowRoot.querySelector('#kpi-blended'),
      blendedLabel: this.shadowRoot.querySelector('#blended-label'),
      blendedMeta: this.shadowRoot.querySelector('#blended-meta'),
      // Market Regime
      regimeDot: this.shadowRoot.querySelector('#regime-dot'),
      regimeText: this.shadowRoot.querySelector('#regime-text'),
      // Cycle
      cycleDot: this.shadowRoot.querySelector('#cycle-dot'),
      cycleText: this.shadowRoot.querySelector('#cycle-text'),
      // Targets
      targetsSummary: this.shadowRoot.querySelector('#targets-summary'),
      // API Health
      backendDot: this.shadowRoot.querySelector('#backend-dot'),
      signalsDot: this.shadowRoot.querySelector('#signals-dot'),
      // Governance
      governanceDot: this.shadowRoot.querySelector('#governance-dot'),
      governanceText: this.shadowRoot.querySelector('#governance-text'),
      governanceMode: this.shadowRoot.querySelector('#governance-mode'),
      governanceContradiction: this.shadowRoot.querySelector('#governance-contradiction'),
      governanceConstraints: this.shadowRoot.querySelector('#governance-constraints'),
      // Alerts
      alertsDot: this.shadowRoot.querySelector('#alerts-dot'),
      alertsText: this.shadowRoot.querySelector('#alerts-text'),
      alertsList: this.shadowRoot.querySelector('#alerts-list'),
      alertsButton: this.shadowRoot.querySelector('#alerts-button'),
    };

    // Bouton "View All History" contextuel
    if (this.$.alertsButton) {
      this.$.alertsButton.addEventListener('click', () => {
        if (typeof window.switchTab === 'function') {
          // Sur risk-dashboard.html
          window.switchTab('alerts');
        } else {
          // Sur les autres pages : redirection
          window.location.href = '/static/risk-dashboard.html#alerts';
        }
      });
    }

    // Connexion store ou polling
    if (window.riskStore?.subscribe) {
      this._connectStore();
      return;
    }

    const ready = await waitForGlobalEventOrTimeout('riskStoreReady', 1500);
    if (ready && window.riskStore?.subscribe) {
      this._connectStore();
      return;
    }

    if (this.pollMs > 0) {
      await this._pollOnce();
      this._poll = setInterval(() => this._pollOnce(), this.pollMs);
    }
  }

  _connectStore() {
    const push = () => {
      const state = window.riskStore?.getState?.() || {};
      console.log('[risk-sidebar-full] Store state:', state);
      this._updateFromState(state);
    };
    push();
    this._unsub = window.riskStore.subscribe(push);
  }

  async _pollOnce() {
    const j = await fetchRisk();
    console.log('[risk-sidebar-full] Raw API response:', j);
    if (!j) return; // Conserve valeurs précédentes
    const state = normalizeRiskState(j);
    console.log('[risk-sidebar-full] Normalized state:', state);
    this._updateFromState(state);
  }

  /**
   * Mise à jour depuis le state (port de l'ancienne fonction updateSidebar())
   * @param {Object} state - RiskState normalisé
   */
  _updateFromState(state) {
    if (!state || !this.$) return;

    // CCS Mixte (ccsStar ou score)
    const ccsScore = state.cycle?.ccsStar ?? state.ccs?.score;
    console.log('[risk-sidebar-full] CCS score check:', {
      ccsStar: state.cycle?.ccsStar,
      ccsScore: state.ccs?.score,
      final: ccsScore,
      cycle: state.cycle,
      ccs: state.ccs
    });
    if (Number.isFinite(ccsScore)) {
      this.$.ccsMix.textContent = Math.round(ccsScore);
      this.$.ccsMixLabel.textContent = this._getScoreLabel(ccsScore);
      this._applyScoreClass(this.$.ccsMix, ccsScore);
    } else {
      this.$.ccsMix.textContent = '--';
      this.$.ccsMixLabel.textContent = 'N/A';
    }

    // On-Chain
    const onchainScore = state.scores?.onchain;
    if (Number.isFinite(onchainScore)) {
      this.$.onchain.textContent = Math.round(onchainScore);
      this.$.onchainLabel.textContent = this._getScoreLabel(onchainScore);
      this._applyScoreClass(this.$.onchain, onchainScore);
    } else {
      this.$.onchain.textContent = '--';
      this.$.onchainLabel.textContent = 'N/A';
    }

    // Risk
    const riskScore = state.scores?.risk;
    if (Number.isFinite(riskScore)) {
      this.$.risk.textContent = Math.round(riskScore);
      this.$.riskLabel.textContent = this._getScoreLabel(riskScore);
      this._applyScoreClass(this.$.risk, riskScore);
    } else {
      this.$.risk.textContent = '--';
      this.$.riskLabel.textContent = 'N/A';
    }

    // Blended Decision
    const blendedScore = state.scores?.blended ?? state.scores?.blendedDecision;
    if (Number.isFinite(blendedScore)) {
      this.$.blended.textContent = Math.round(blendedScore);
      this.$.blendedLabel.textContent = this._getScoreLabel(blendedScore);
      this._applyScoreClass(this.$.blended, blendedScore);

      // Meta info (confidence, contradiction)
      const parts = [];
      if (Number.isFinite(state.decision?.confidence)) {
        parts.push(`Confidence: ${Math.round(state.decision.confidence * 100)}%`);
      }
      if (Number.isFinite(state.governance?.contradiction_index)) {
        parts.push(`Contradiction: ${Math.round(state.governance.contradiction_index * 100)}%`);
      }
      this.$.blendedMeta.textContent = parts.join(' • ');
    } else {
      this.$.blended.textContent = '--';
      this.$.blendedLabel.textContent = 'N/A';
      this.$.blendedMeta.textContent = '';
    }

    // Market Regime
    if (state.regime?.phase) {
      this.$.regimeDot.className = 'status-dot ' + this._getRegimeClass(state.regime.phase);
      this.$.regimeText.textContent = state.regime.phase;
    } else {
      this.$.regimeDot.className = 'status-dot';
      this.$.regimeText.textContent = 'Unknown';
    }

    // Cycle Position
    if (state.cycle?.months && state.cycle?.phase) {
      const months = Math.round(state.cycle.months);
      const phase = state.cycle.phase;
      this.$.cycleDot.className = 'status-dot healthy';
      this.$.cycleText.innerHTML = `
        <strong>${phase.emoji || ''} ${phase.phase?.replace('_', ' ').toUpperCase() || 'Unknown'}</strong><br>
        <span style="font-size: 0.7rem; opacity: 0.8;">Month ${months} post-halving</span>
      `;
    } else {
      this.$.cycleDot.className = 'status-dot';
      this.$.cycleText.textContent = 'Loading cycle data...';
    }

    // Targets Summary
    if (state.targets?.changes && state.targets.changes.length > 0) {
      this.$.targetsSummary.innerHTML = `
        <div class="status-text">${state.targets.changes.length} change${state.targets.changes.length !== 1 ? 's' : ''} proposed</div>
      `;
    } else {
      this.$.targetsSummary.innerHTML = '<div class="status-text">No changes proposed</div>';
    }

    // API Health (basique)
    this.$.backendDot.className = 'status-dot healthy';
    this.$.signalsDot.className = 'status-dot healthy';

    // Governance Status
    const govMode = state.governance?.mode || 'manual';
    const isActive = govMode === 'auto' || govMode === 'guardian';
    this.$.governanceDot.className = 'status-dot ' + (isActive ? 'healthy' : '');
    this.$.governanceText.textContent = isActive ? 'Active' : 'Manual';
    this.$.governanceMode.textContent = `Mode: ${govMode}`;

    const contraPct = (state.governance?.contradiction_index ?? 0) * 100;
    this.$.governanceContradiction.textContent = `Contradiction: ${contraPct.toFixed(1)}%`;

    // Constraints
    if (state.governance?.constraints) {
      const activeConstraints = Object.entries(state.governance.constraints)
        .filter(([_, active]) => active)
        .map(([name, _]) => name);

      if (activeConstraints.length > 0) {
        this.$.governanceConstraints.textContent = `⚠️ Active: ${activeConstraints.join(', ')}`;
      } else {
        this.$.governanceConstraints.textContent = '';
      }
    }

    // Active Alerts
    const alerts = state.alerts || [];
    const activeAlerts = alerts.filter(a => a.status === 'active');
    const count = activeAlerts.length;

    if (count === 0) {
      this.$.alertsDot.className = 'status-dot healthy';
      this.$.alertsText.textContent = 'No active alerts';
      this.$.alertsList.innerHTML = '<div class="status-text" style="text-align: center; opacity: 0.6;">No active alerts</div>';
    } else {
      const highSeverity = activeAlerts.some(a => a.severity === 'high' || a.severity === 'critical');
      this.$.alertsDot.className = 'status-dot ' + (highSeverity ? 'error' : 'warning');
      this.$.alertsText.textContent = `${count} active alert${count !== 1 ? 's' : ''}`;

      this.$.alertsList.innerHTML = activeAlerts.slice(0, 5).map(alert => `
        <div style="padding: 6px 8px; margin: 4px 0; background: var(--theme-bg); border-left: 3px solid var(--${this._getSeverityColor(alert.severity)}); border-radius: 4px; font-size: 0.7rem;">
          <div style="font-weight: 600; color: var(--${this._getSeverityColor(alert.severity)});">${alert.type}</div>
          <div style="opacity: 0.8; margin-top: 2px;">${alert.message}</div>
        </div>
      `).join('');
    }
  }

  _getScoreLabel(score) {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Bon';
    if (score >= 40) return 'Neutre';
    if (score >= 20) return 'Faible';
    return 'Critique';
  }

  _applyScoreClass(el, score) {
    el.className = 'ccs-score';
    if (score >= 80) el.classList.add('score-excellent');
    else if (score >= 60) el.classList.add('score-good');
    else if (score >= 40) el.classList.add('score-neutral');
    else if (score >= 20) el.classList.add('score-warning');
    else el.classList.add('score-critical');
  }

  _getRegimeClass(phase) {
    const p = (phase || '').toLowerCase();
    if (p.includes('bull') || p.includes('expansion')) return 'healthy';
    if (p.includes('bear') || p.includes('risk')) return 'error';
    if (p.includes('neutral')) return '';
    return 'warning';
  }

  _getSeverityColor(severity) {
    switch (severity) {
      case 'critical': return 'danger';
      case 'high': return 'warning';
      case 'medium': return 'warning';
      case 'low': return 'info';
      default: return 'theme-text-muted';
    }
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --card-bg: var(--theme-surface, #0f1115);
          --card-fg: var(--theme-fg, #e5e7eb);
          --card-border: var(--theme-border, #2a2f3b);
          --brand-primary: var(--brand-primary, #7aa2f7);
          --success: var(--success, #10b981);
          --warning: var(--warning, #f59e0b);
          --danger: var(--danger, #ef4444);
          --info: var(--info, #3b82f6);
          --theme-bg: var(--theme-bg, #1a1b26);
          --theme-text-muted: var(--theme-text-muted, #9ca3af);
          --space-xs: 0.25rem;
          --space-sm: 0.5rem;
          --space-md: 0.75rem;
          --space-lg: 1rem;
          --space-xl: 1.5rem;
          --radius-sm: 4px;
          --radius-md: 8px;
        }

        .sidebar-section {
          margin-bottom: var(--space-xl);
        }

        .sidebar-section:last-child {
          margin-bottom: 0;
        }

        .sidebar-title {
          font-size: 0.875rem;
          font-weight: 600;
          color: var(--theme-text-muted);
          margin-bottom: var(--space-sm);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .ccs-gauge {
          text-align: center;
          padding: var(--space-lg);
          background: var(--theme-bg);
          border-radius: var(--radius-md);
          border: 2px solid var(--brand-primary);
        }

        .ccs-score {
          font-size: 2.5rem;
          font-weight: 700;
          color: var(--brand-primary);
          line-height: 1;
          margin-bottom: var(--space-xs);
        }

        .ccs-score.score-excellent { color: var(--success); }
        .ccs-score.score-good { color: var(--brand-primary); }
        .ccs-score.score-neutral { color: var(--info); }
        .ccs-score.score-warning { color: var(--warning); }
        .ccs-score.score-critical { color: var(--danger); }

        .ccs-label {
          font-size: 0.75rem;
          color: var(--theme-text-muted);
          font-weight: 500;
        }

        .ccs-meta {
          font-size: 0.75rem;
          color: var(--theme-text-muted);
          margin-top: var(--space-xs);
        }

        .decision-card {
          padding: 2rem;
          border: 2px solid var(--card-border);
          box-shadow: 0 0 12px rgba(0, 0, 0, 0.15);
        }

        .decision-card .ccs-score {
          font-size: 3rem;
        }

        .decision-card .ccs-label {
          font-size: 1rem;
          font-weight: 700;
        }

        .status-indicator {
          display: flex;
          align-items: center;
          gap: var(--space-xs);
          padding: var(--space-sm);
          background: var(--theme-bg);
          border-radius: var(--radius-sm);
          margin-bottom: var(--space-sm);
        }

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--theme-text-muted);
          flex-shrink: 0;
        }

        .status-dot.healthy {
          background: var(--success);
        }

        .status-dot.warning {
          background: var(--warning);
        }

        .status-dot.error {
          background: var(--danger);
        }

        .status-text {
          font-size: 0.75rem;
          color: var(--theme-text-muted);
        }

        .governance-details {
          margin-top: 8px;
          font-size: 0.85em;
          opacity: 0.8;
        }

        .governance-details > div {
          margin-bottom: 4px;
        }

        #alerts-list {
          margin-top: 8px;
          max-height: 200px;
          overflow-y: auto;
        }

        button {
          background: var(--brand-primary);
          color: white;
          border: none;
          padding: 6px 12px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 0.75rem;
          font-weight: 500;
        }

        button:hover {
          opacity: 0.9;
        }
      </style>

      <!-- CCS Mixte -->
      <div class="sidebar-section">
        <div class="sidebar-title">🎯 CCS Mixte (Directeur)</div>
        <div class="ccs-gauge">
          <div class="ccs-score" id="ccs-ccs-mix">--</div>
          <div class="ccs-label" id="ccs-mixte-label">Loading...</div>
        </div>
      </div>

      <!-- On-Chain Composite -->
      <div class="sidebar-section">
        <div class="sidebar-title">🔗 On-Chain Composite</div>
        <div class="ccs-gauge">
          <div class="ccs-score" id="kpi-onchain">--</div>
          <div class="ccs-label" id="onchain-label">Loading...</div>
        </div>
      </div>

      <!-- Risk Score Portfolio -->
      <div class="sidebar-section">
        <div class="sidebar-title">🛡️ Risk Score</div>
        <div class="ccs-gauge">
          <div class="ccs-score" id="kpi-risk">--</div>
          <div class="ccs-label" id="risk-label">Loading...</div>
        </div>
      </div>

      <!-- Blended Decision Score -->
      <div class="sidebar-section" style="margin-top:1.5rem;">
        <div class="sidebar-title" style="font-size:1rem; font-weight:700;">
          ⚖️ Score Décisionnel
        </div>
        <div class="ccs-gauge decision-card">
          <div class="ccs-score" id="kpi-blended">--</div>
          <div class="ccs-label" id="blended-label">Loading...</div>
          <div class="ccs-meta" id="blended-meta"></div>
        </div>
      </div>

      <!-- Market Regime -->
      <div class="sidebar-section">
        <div class="sidebar-title">📊 Régime de Marché</div>
        <div class="status-indicator">
          <div class="status-dot" id="regime-dot"></div>
          <div class="status-text" id="regime-text">Loading...</div>
        </div>
      </div>

      <!-- Cycle Position -->
      <div class="sidebar-section">
        <div class="sidebar-title">Cycle Position</div>
        <div class="status-indicator">
          <div class="status-dot" id="cycle-dot"></div>
          <div class="status-text" id="cycle-text">Loading...</div>
        </div>
      </div>

      <!-- Targets Summary -->
      <div class="sidebar-section">
        <div class="sidebar-title">Target Changes</div>
        <div id="targets-summary">
          <div class="status-text">No changes proposed</div>
        </div>
      </div>

      <!-- API Status -->
      <div class="sidebar-section">
        <div class="sidebar-title">API Health</div>
        <div class="status-indicator">
          <div class="status-dot" id="backend-dot"></div>
          <div class="status-text">Backend API</div>
        </div>
        <div class="status-indicator">
          <div class="status-dot" id="signals-dot"></div>
          <div class="status-text">Market Signals</div>
        </div>
      </div>

      <!-- Governance Status -->
      <div class="sidebar-section">
        <div class="sidebar-title">Governance</div>
        <div class="status-indicator">
          <div class="status-dot" id="governance-dot"></div>
          <div class="status-text" id="governance-text">Loading...</div>
        </div>
        <div class="governance-details">
          <div id="governance-mode">Mode: manual</div>
          <div id="governance-contradiction">Contradiction: 0.0%</div>
          <div id="governance-constraints"></div>
        </div>
      </div>

      <!-- Active Alerts -->
      <div class="sidebar-section">
        <div class="sidebar-title">🚨 Active Alerts</div>
        <div class="status-indicator">
          <div class="status-dot" id="alerts-dot"></div>
          <div class="status-text" id="alerts-text">Loading...</div>
        </div>
        <div id="alerts-list"></div>
        <div style="text-align: center; margin-top: 8px;">
          <button id="alerts-button">📋 View All History</button>
        </div>
      </div>
    `;
  }
}

customElements.define('risk-sidebar-full', RiskSidebarFull);
export { RiskSidebarFull };
