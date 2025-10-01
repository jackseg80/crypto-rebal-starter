/**
 * Risk Snapshot Component - Reusable
 *
 * Composant qui affiche un snapshot des scores Risk, governance et alertes.
 * Utilisable dans le flyout panel sur n'importe quelle page.
 *
 * Usage:
 *   import { createRiskSnapshot } from '/static/components/risk-snapshot.js';
 *   const container = document.createElement('div');
 *   createRiskSnapshot(container);
 */

/**
 * Crée un snapshot Risk dans un conteneur
 * @param {HTMLElement} container - Conteneur où injecter le snapshot
 * @returns {Object} - Objet avec méthode refresh()
 */
export function createRiskSnapshot(container) {
  // Injecter le HTML
  container.innerHTML = `
    <!-- CCS Mixte (Score Directeur du Marché) -->
    <div class="sidebar-section">
      <div class="sidebar-title">🎯 CCS Mixte (Directeur)</div>
      <div class="ccs-gauge" id="flyout-ccs-gauge">
        <div class="ccs-score" id="flyout-ccs-ccs-mix" data-score="ccs">--</div>
        <div class="ccs-label" id="flyout-ccs-mixte-label">Loading...</div>
      </div>
    </div>

    <!-- On-Chain Composite -->
    <div class="sidebar-section">
      <div class="sidebar-title">🔗 On-Chain Composite</div>
      <div class="ccs-gauge" id="flyout-onchain-gauge">
        <div class="ccs-score" id="flyout-kpi-onchain" data-score="onchain">--</div>
        <div class="ccs-label" id="flyout-onchain-label">Loading...</div>
      </div>
    </div>

    <!-- Risk Score Portfolio -->
    <div class="sidebar-section">
      <div class="sidebar-title">🛡️ Risk Score</div>
      <div class="ccs-gauge" id="flyout-risk-gauge">
        <div class="ccs-score" id="flyout-kpi-risk" data-score="risk">--</div>
        <div class="ccs-label" id="flyout-risk-label">Loading...</div>
      </div>
    </div>

    <!-- Blended Decision Score (Synthèse principale) -->
    <div class="sidebar-section" style="margin-top:1.5rem;">
      <div class="sidebar-title" style="font-size:1rem; font-weight:700;">
        ⚖️ Score Décisionnel
      </div>
      <div class="ccs-gauge decision-card" id="flyout-blended-gauge"
        style="padding:1.25rem; border:2px solid var(--theme-border); box-shadow:0 0 12px rgba(0,0,0,0.15);">
        <div class="ccs-score" id="flyout-kpi-blended" data-score="blended" style="font-size:2.5rem;">--</div>
        <div class="ccs-label" id="flyout-blended-label" style="font-size:0.95rem; font-weight:700;">Loading...</div>
        <div class="ccs-meta" id="flyout-blended-meta"
          style="font-size:.7rem; color: var(--theme-text-muted); margin-top:.25rem;"></div>
      </div>
    </div>

    <!-- Market Regime -->
    <div class="sidebar-section">
      <div class="sidebar-title">📊 Régime de Marché</div>
      <div id="flyout-market-regime">
        <div class="status-indicator">
          <div class="status-dot" id="flyout-regime-dot"></div>
          <div class="status-text" id="flyout-regime-text">Loading market regime...</div>
        </div>
      </div>
    </div>

    <!-- Governance Status -->
    <div class="sidebar-section">
      <div class="sidebar-title">Governance</div>
      <div id="flyout-governance-status">
        <div class="status-indicator">
          <div class="status-dot" id="flyout-governance-dot"></div>
          <div class="status-text" id="flyout-governance-text">Loading...</div>
        </div>
        <div class="governance-details" id="flyout-governance-details"
          style="margin-top: 8px; font-size: 0.85em; opacity: 0.8;">
          <div id="flyout-governance-mode">Mode: manual</div>
          <div id="flyout-governance-contradiction">Contradiction: 0.0%</div>
        </div>
      </div>
    </div>

    <!-- Active Alerts -->
    <div class="sidebar-section">
      <div class="sidebar-title">🚨 Active Alerts</div>
      <div id="flyout-alerts-status">
        <div id="flyout-alerts-summary" class="status-indicator">
          <div class="status-dot" id="flyout-alerts-dot"></div>
          <div class="status-text" id="flyout-alerts-text">Loading alerts...</div>
        </div>
      </div>
    </div>
  `;

  // Fonction pour rafraîchir les données
  async function refresh() {
    try {
      // Charger les scores depuis le store Risk ou l'API
      if (window.riskStore) {
        const state = window.riskStore.getState();
        updateScores(state);
      } else {
        // Fallback: charger depuis l'API
        await loadFromAPI();
      }
    } catch (error) {
      console.error('Failed to refresh risk snapshot:', error);
    }
  }

  // Mettre à jour les scores depuis l'état du store
  function updateScores(state) {
    // CCS Mixte
    const ccsEl = document.getElementById('flyout-ccs-ccs-mix');
    const ccsLabelEl = document.getElementById('flyout-ccs-mixte-label');
    if (ccsEl && state.ccs !== undefined) {
      ccsEl.textContent = Math.round(state.ccs);
      ccsEl.setAttribute('data-score', state.ccs);
      if (ccsLabelEl) ccsLabelEl.textContent = getScoreLabel(state.ccs);
    }

    // On-Chain
    const onchainEl = document.getElementById('flyout-kpi-onchain');
    const onchainLabelEl = document.getElementById('flyout-onchain-label');
    if (onchainEl && state.onchain !== undefined) {
      onchainEl.textContent = Math.round(state.onchain);
      onchainEl.setAttribute('data-score', state.onchain);
      if (onchainLabelEl) onchainLabelEl.textContent = getScoreLabel(state.onchain);
    }

    // Risk
    const riskEl = document.getElementById('flyout-kpi-risk');
    const riskLabelEl = document.getElementById('flyout-risk-label');
    if (riskEl && state.risk !== undefined) {
      riskEl.textContent = Math.round(state.risk);
      riskEl.setAttribute('data-score', state.risk);
      if (riskLabelEl) riskLabelEl.textContent = getScoreLabel(state.risk);
    }

    // Blended
    const blendedEl = document.getElementById('flyout-kpi-blended');
    const blendedLabelEl = document.getElementById('flyout-blended-label');
    if (blendedEl && state.blended !== undefined) {
      blendedEl.textContent = Math.round(state.blended);
      blendedEl.setAttribute('data-score', state.blended);
      if (blendedLabelEl) blendedLabelEl.textContent = getScoreLabel(state.blended);
    }

    // Governance
    updateGovernance(state.governance);
  }

  // Charger depuis l'API
  async function loadFromAPI() {
    const response = await fetch('/api/risk/scores');
    if (response.ok) {
      const data = await response.json();
      updateScores(data);
    }
  }

  // Mettre à jour governance
  function updateGovernance(governance) {
    if (!governance) return;

    const dotEl = document.getElementById('flyout-governance-dot');
    const textEl = document.getElementById('flyout-governance-text');
    const modeEl = document.getElementById('flyout-governance-mode');
    const contradictionEl = document.getElementById('flyout-governance-contradiction');

    if (dotEl) dotEl.className = `status-dot ${governance.active ? 'status-success' : 'status-warning'}`;
    if (textEl) textEl.textContent = governance.active ? 'Active' : 'Inactive';
    if (modeEl) modeEl.textContent = `Mode: ${governance.mode || 'manual'}`;
    if (contradictionEl) {
      const pct = ((governance.contradiction_index || 0) * 100).toFixed(1);
      contradictionEl.textContent = `Contradiction: ${pct}%`;
    }
  }

  // Helper pour obtenir le label d'un score
  function getScoreLabel(score) {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Bon';
    if (score >= 40) return 'Modéré';
    if (score >= 20) return 'Faible';
    return 'Très Faible';
  }

  // S'abonner au store si disponible
  if (window.riskStore) {
    window.riskStore.subscribe(() => {
      const state = window.riskStore.getState();
      updateScores(state);
    });
  }

  // Charger initialement
  refresh();

  // Retourner l'interface publique
  return { refresh };
}
