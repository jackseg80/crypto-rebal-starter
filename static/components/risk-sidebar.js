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

  // Exposer la fonction de mise à jour globalement pour que risk-dashboard.html puisse l'appeler
  window.updateRiskSidebar = (state) => {
    updateSidebarFromState(state);
  };

  // Connecter les mises à jour live via riskStore
  if (window.riskStore) {
    // Subscribe to store updates
    window.riskStore.subscribe(() => {
      updateSidebarFromState(window.riskStore.getState());
    });

    // Initial update avec un délai pour attendre le chargement
    setTimeout(() => {
      updateSidebarFromState(window.riskStore.getState());
    }, 100);
  } else {
    console.warn('⚠️ riskStore not available, sidebar will use fallback');
  }

  return {
    refresh: () => {
      if (window.riskStore) {
        updateSidebarFromState(window.riskStore.getState());
      } else {
        fetchAndUpdate();
      }
    }
  };
}

// Fonction pour mettre à jour tous les scores depuis le state (format risk-dashboard.html)
function updateSidebarFromState(state) {
  if (!state) return;

  console.debug('🔄 Updating Risk Sidebar from state:', state);

  // CCS Mixte (ccsStar depuis state.cycle)
  const ccsScore = state.cycle?.ccsStar || state.ccs?.score;
  updateScoreElement('ccs-ccs-mix', 'ccs-mixte-label', ccsScore, 'ccs');

  // On-Chain (depuis state.scores)
  const onchainScore = state.scores?.onchain;
  updateScoreElement('kpi-onchain', 'onchain-label', onchainScore, 'onchain');

  // Risk Score (depuis state.scores)
  const riskScore = state.scores?.risk;
  updateScoreElement('kpi-risk', 'risk-label', riskScore, 'risk');

  // Blended Decision (depuis state.scores)
  const blendedScore = state.scores?.blended;
  updateScoreElement('kpi-blended', 'blended-label', blendedScore, 'blended');

  // Cycle indicator
  if (state.cycle?.months && state.cycle?.phase) {
    const cycleText = document.getElementById('cycle-text');
    const cycleDot = document.getElementById('cycle-dot');
    if (cycleText && cycleDot) {
      const months = Math.round(state.cycle.months);
      const phase = state.cycle.phase;
      cycleText.innerHTML = `
        <div style="font-size: 11px; font-weight: 600;">${phase.emoji || ''} ${phase.phase?.replace('_', ' ').toUpperCase() || 'Unknown'}</div>
        <div style="font-size: 10px; opacity: 0.8;">Month ${months} post-halving</div>
      `;
      cycleDot.style.backgroundColor = phase.color || 'var(--theme-text-muted)';
    }
  }

  // Market Regime
  updateMarketRegimeFromState(state);

  // Governance
  updateGovernanceFromState(state);

  // Alerts
  updateAlertsFromState(state);
}

// Mise à jour Market Regime depuis state
function updateMarketRegimeFromState(state) {
  const regimeDot = document.getElementById('regime-dot');
  const regimeText = document.getElementById('regime-text');

  if (!regimeDot || !regimeText) return;

  // Utiliser la logique de risk-dashboard.html
  const blendedScore = state.scores?.blended || 0;
  let regime = 'Neutral';
  let dotClass = 'status-dot';

  if (blendedScore >= 70) {
    regime = 'Bull Market';
    dotClass += ' status-success';
  } else if (blendedScore >= 40) {
    regime = 'Neutral';
    dotClass += ' status-warning';
  } else {
    regime = 'Risk-Off';
    dotClass += ' status-error';
  }

  regimeDot.className = dotClass;
  regimeText.textContent = regime;
}

// Mise à jour Governance depuis state
function updateGovernanceFromState(state) {
  const governanceDot = document.getElementById('governance-dot');
  const governanceText = document.getElementById('governance-text');
  const governanceMode = document.getElementById('governance-mode');
  const governanceContradiction = document.getElementById('governance-contradiction');

  if (!window.store) return;

  const governanceStatus = window.store.getGovernanceStatus();

  if (governanceDot && governanceText) {
    let dotClass = 'status-dot';
    let statusText = governanceStatus.state;

    if (governanceStatus.state === 'FROZEN') {
      dotClass += ' status-error';
      statusText = '❄️ Frozen';
    } else if (governanceStatus.needsAttention) {
      dotClass += ' status-warning';
      statusText = '⚠️ Needs attention';
    } else if (governanceStatus.isActive) {
      dotClass += ' status-success';
      statusText = '✓ Active';
    } else {
      dotClass += ' idle';
      statusText = '○ Idle';
    }

    governanceDot.className = dotClass;
    governanceText.textContent = statusText;
  }

  if (governanceMode && governanceContradiction) {
    governanceMode.textContent = `Mode: ${governanceStatus.mode}`;
    const contraPct = (governanceStatus.contradictionLevel * 100);
    governanceContradiction.textContent = `Contradiction: ${contraPct.toFixed(1)}%`;
  }
}

// Mise à jour Alerts depuis state
function updateAlertsFromState(state) {
  // Les alertes sont gérées par loadAlertsForSidebar() dans risk-dashboard.html
  // On ne fait rien ici pour éviter les conflits
}

// Fonction helper pour mettre à jour un score individuel
function updateScoreElement(scoreId, labelId, value, type) {
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

