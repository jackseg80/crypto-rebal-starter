/**
 * risk-sidebar.js
 * Composant réutilisable pour générer la sidebar Risk avec tous les scores et mises à jour live
 * Peut être utilisé sur n'importe quelle page
 */

export function createRiskSidebar(container) {
  // Générer le HTML complet de la sidebar
  container.innerHTML = `
    <!-- Toggle sidebar -->
    <button id="sidebar-toggle" aria-label="Réduire la barre latérale" title="Réduire/agrandir la barre"
      class="sidebar-toggle-full">
      <span id="sidebar-toggle-icon">⟨⟨</span>
      <span class="sidebar-toggle-text">Réduire</span>
    </button>

    <!-- CCS Mixte (Score Directeur du Marché) -->
    <div class="sidebar-section">
      <div class="sidebar-title">🎯 CCS Mixte (Directeur)</div>
      <div class="ccs-gauge" id="ccs-gauge">
        <div class="ccs-score" id="ccs-ccs-mix" data-score="ccs">--</div>
        <div class="ccs-label" id="ccs-mixte-label">Loading...</div>
      </div>
    </div>

    <!-- On-Chain Composite -->
    <div class="sidebar-section">
      <div class="sidebar-title">🔗 On-Chain Composite</div>
      <div class="ccs-gauge" id="onchain-gauge">
        <div class="ccs-score" id="kpi-onchain" data-score="onchain">--</div>
        <div class="ccs-label" id="onchain-label">Loading...</div>
      </div>
    </div>

    <!-- Risk Score Portfolio -->
    <div class="sidebar-section">
      <div class="sidebar-title">🛡️ Risk Score</div>
      <div class="ccs-gauge" id="risk-gauge">
        <div class="ccs-score" id="kpi-risk" data-score="risk">--</div>
        <div class="ccs-label" id="risk-label">Loading...</div>
      </div>
    </div>

    <!-- Blended Decision Score (Synthèse principale) -->
    <div class="sidebar-section" style="margin-top:1.5rem;">
      <div class="sidebar-title" style="font-size:1rem; font-weight:700;">
        ⚖️ Score Décisionnel
      </div>
      <div class="ccs-gauge decision-card" id="blended-gauge"
        style="padding:1.25rem; border:2px solid var(--theme-border); box-shadow:0 0 12px rgba(0,0,0,0.15);">
        <div class="ccs-score" id="kpi-blended" data-score="blended" style="font-size:3rem;">--</div>
        <div class="ccs-label" id="blended-label" style="font-size:1rem; font-weight:700;">Loading...</div>
        <div class="ccs-meta" id="blended-meta"
          style="font-size:.75rem; color: var(--theme-text-muted); margin-top:.25rem;"></div>
      </div>
    </div>

    <!-- Market Regime -->
    <div class="sidebar-section">
      <div class="sidebar-title">📊 Régime de Marché</div>
      <div id="market-regime">
        <div class="status-indicator">
          <div class="status-dot" id="regime-dot"></div>
          <div class="status-text" id="regime-text">Loading market regime...</div>
        </div>
      </div>
    </div>

    <!-- Cycle Indicator -->
    <div class="sidebar-section">
      <div class="sidebar-title">Cycle Position</div>
      <div id="cycle-indicator">
        <div class="status-indicator">
          <div class="status-dot" id="cycle-dot"></div>
          <div class="status-text" id="cycle-text">Loading cycle data...</div>
        </div>
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
      <div id="api-status">
        <div class="status-indicator">
          <div class="status-dot" id="backend-dot"></div>
          <div class="status-text">Backend API</div>
        </div>
        <div class="status-indicator">
          <div class="status-dot" id="signals-dot"></div>
          <div class="status-text">Market Signals</div>
        </div>
      </div>
    </div>

    <!-- Governance Status -->
    <div class="sidebar-section">
      <div class="sidebar-title">Governance</div>
      <div id="governance-status">
        <div class="status-indicator">
          <div class="status-dot" id="governance-dot"></div>
          <div class="status-text" id="governance-text">Loading...</div>
        </div>
        <div class="governance-details" id="governance-details"
          style="margin-top: 8px; font-size: 0.85em; opacity: 0.8;">
          <div id="governance-mode">Mode: manual</div>
          <div id="governance-contradiction">Contradiction: 0.0%</div>
          <div id="governance-constraints" style="font-size:.75rem;color:var(--warning);margin-top:4px;"></div>
        </div>
      </div>
    </div>

    <!-- Active Alerts -->
    <div class="sidebar-section">
      <div class="sidebar-title">🚨 Active Alerts</div>
      <div id="alerts-status">
        <div id="alerts-summary" class="status-indicator">
          <div class="status-dot" id="alerts-dot"></div>
          <div class="status-text" id="alerts-text">Loading alerts...</div>
        </div>
        <div id="alerts-list" style="margin-top: 8px; max-height: 150px; overflow-y: auto;">
          <!-- Alert items will be populated here (limited to 5 most recent) -->
        </div>
      </div>
    </div>
  `;

  // Connecter les mises à jour live via riskStore
  if (window.riskStore) {
    // Subscribe to store updates
    window.riskStore.subscribe(() => {
      updateScores(window.riskStore.getState());
    });

    // Initial update
    updateScores(window.riskStore.getState());
  } else {
    console.warn('⚠️ riskStore not available, sidebar will not auto-update');
    // Fallback: polling API
    startPolling();
  }

  return {
    refresh: () => {
      if (window.riskStore) {
        updateScores(window.riskStore.getState());
      } else {
        fetchAndUpdate();
      }
    }
  };
}

// Fonction pour mettre à jour tous les scores
function updateScores(state) {
  // CCS Mixte
  updateScore('ccs-ccs-mix', 'ccs-mixte-label', state.ccs_mix, 'ccs');

  // On-Chain
  updateScore('kpi-onchain', 'onchain-label', state.onchain, 'onchain');

  // Risk Score
  updateScore('kpi-risk', 'risk-label', state.risk, 'risk');

  // Blended Decision
  updateScore('kpi-blended', 'blended-label', state.blended, 'blended');
  if (state.blended_meta) {
    const metaEl = document.getElementById('blended-meta');
    if (metaEl) metaEl.textContent = state.blended_meta;
  }

  // Market Regime
  if (state.regime) {
    updateRegime(state.regime);
  }

  // Governance
  if (state.governance) {
    updateGovernance(state.governance);
  }

  // Alerts
  if (state.alerts) {
    updateAlerts(state.alerts);
  }
}

// Fonction helper pour mettre à jour un score individuel
function updateScore(scoreId, labelId, value, type) {
  const scoreEl = document.getElementById(scoreId);
  const labelEl = document.getElementById(labelId);

  if (!scoreEl || !labelEl) return;

  if (value === null || value === undefined) {
    scoreEl.textContent = '--';
    labelEl.textContent = 'N/A';
    return;
  }

  const numValue = typeof value === 'object' ? value.value : value;
  const label = typeof value === 'object' ? value.label : getLabel(numValue, type);

  scoreEl.textContent = Math.round(numValue);
  labelEl.textContent = label;

  // Color coding
  scoreEl.className = 'ccs-score';
  if (numValue >= 70) scoreEl.classList.add('score-high');
  else if (numValue >= 40) scoreEl.classList.add('score-medium');
  else scoreEl.classList.add('score-low');
}

// Fonction pour obtenir le label d'un score
function getLabel(value, type) {
  if (type === 'ccs') {
    if (value >= 80) return 'Euphorie';
    if (value >= 60) return 'Bull';
    if (value >= 40) return 'Neutral';
    if (value >= 20) return 'Prudence';
    return 'Risk-Off';
  }
  if (type === 'risk') {
    if (value >= 70) return 'Robuste';
    if (value >= 40) return 'Modéré';
    return 'Élevé';
  }
  if (value >= 70) return 'Favorable';
  if (value >= 40) return 'Neutre';
  return 'Défavorable';
}

// Fonction pour mettre à jour le régime de marché
function updateRegime(regime) {
  const dotEl = document.getElementById('regime-dot');
  const textEl = document.getElementById('regime-text');

  if (!dotEl || !textEl) return;

  textEl.textContent = regime.text || regime;

  // Color based on regime
  const regimeStr = (regime.text || regime).toLowerCase();
  dotEl.className = 'status-dot';
  if (regimeStr.includes('bull') || regimeStr.includes('euphori')) {
    dotEl.classList.add('status-success');
  } else if (regimeStr.includes('bear') || regimeStr.includes('risk')) {
    dotEl.classList.add('status-error');
  } else {
    dotEl.classList.add('status-warning');
  }
}

// Fonction pour mettre à jour la governance
function updateGovernance(governance) {
  const dotEl = document.getElementById('governance-dot');
  const textEl = document.getElementById('governance-text');
  const modeEl = document.getElementById('governance-mode');
  const contradictionEl = document.getElementById('governance-contradiction');
  const constraintsEl = document.getElementById('governance-constraints');

  if (textEl) textEl.textContent = governance.status || 'Active';
  if (modeEl) modeEl.textContent = `Mode: ${governance.mode || 'manual'}`;
  if (contradictionEl) {
    const contradiction = governance.contradiction || 0;
    contradictionEl.textContent = `Contradiction: ${(contradiction * 100).toFixed(1)}%`;
  }
  if (constraintsEl && governance.constraints) {
    constraintsEl.textContent = governance.constraints;
  }

  if (dotEl) {
    dotEl.className = 'status-dot status-success';
    if (governance.contradiction && governance.contradiction > 0.3) {
      dotEl.className = 'status-dot status-warning';
    }
  }
}

// Fonction pour mettre à jour les alertes
function updateAlerts(alerts) {
  const dotEl = document.getElementById('alerts-dot');
  const textEl = document.getElementById('alerts-text');
  const listEl = document.getElementById('alerts-list');

  const activeAlerts = Array.isArray(alerts) ? alerts.filter(a => a.status === 'active') : [];

  if (textEl) {
    textEl.textContent = activeAlerts.length === 0
      ? 'No active alerts'
      : `${activeAlerts.length} active alert${activeAlerts.length > 1 ? 's' : ''}`;
  }

  if (dotEl) {
    dotEl.className = 'status-dot';
    if (activeAlerts.length === 0) {
      dotEl.classList.add('status-success');
    } else {
      const hasCritical = activeAlerts.some(a => a.severity === 'S3');
      dotEl.classList.add(hasCritical ? 'status-error' : 'status-warning');
    }
  }

  if (listEl) {
    if (activeAlerts.length === 0) {
      listEl.innerHTML = '<div style="font-size:0.85rem;opacity:0.7;">All clear ✓</div>';
    } else {
      const items = activeAlerts.slice(0, 5).map(alert => `
        <div style="padding:4px 0; font-size:0.85rem; border-bottom:1px solid var(--theme-border-subtle);">
          <span style="color:${alert.severity === 'S3' ? 'var(--danger)' : 'var(--warning)'};">
            ${alert.severity === 'S3' ? '🔴' : '🟡'}
          </span>
          ${alert.message || alert.type}
        </div>
      `).join('');
      listEl.innerHTML = items;
    }
  }
}

// Fallback: polling API si riskStore n'est pas disponible
let pollingInterval;
function startPolling() {
  fetchAndUpdate();
  pollingInterval = setInterval(fetchAndUpdate, 30000); // 30s
}

async function fetchAndUpdate() {
  try {
    const base = window.globalConfig?.get('api_base_url') || '';
    const response = await fetch(`${base}/api/risk/scores/all`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    updateScores(data);
  } catch (error) {
    console.warn('Failed to fetch risk scores:', error);
  }
}

// Cleanup
export function destroyRiskSidebar() {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
}
