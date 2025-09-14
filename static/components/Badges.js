/**
 * Composant de badges standardisé (ES module)
 * Format: "Source • Updated HH:MM:SS • Contrad XX% • Cap YY% • Overrides N"
 * Integré avec store unified et timezone Europe/Zurich
 */

import { formatZurich, isStale } from '../utils/time.js';

// Constants
const TTL_STALE_MINUTES = 30;

/**
 * Store selectors - helpers robustes qui ne plantent jamais
 */

/**
 * Get decision source from governance state
 * @param {Object} state - Unified state
 * @returns {string} - 'backend'|'blended'|'fallback'|'-'
 */
function getDecisionSource(state) {
  try {
    return state?.governance?.ml_signals?.decision_source ||
           state?.governance?.decision_source ||
           'backend';
  } catch (error) {
    return '-';
  }
}

/**
 * Get updated timestamp from governance or blended signals
 * @param {Object} state - Unified state
 * @returns {string|null} - ISO timestamp or null
 */
function getUpdatedTs(state) {
  try {
    // Priority order: governance signals > blended > fallback
    return state?.governance?.ml_signals?.updated ||
           state?.governance?.updated ||
           state?.scores?.updated ||
           state?.ui?.lastUpdate ||
           null;
  } catch (error) {
    return null;
  }
}

/**
 * Get contradiction percentage (0-1 converted to 0-100)
 * @param {Object} state - Unified state
 * @returns {number|null} - Percentage or null
 */
function getContradiction(state) {
  try {
    const rawContrad = state?.governance?.status?.contradiction ||
                      state?.governance?.contradiction ||
                      null;

    if (rawContrad === null || rawContrad === undefined) return null;

    // Convert 0-1 range to 0-100 percentage
    const percentage = typeof rawContrad === 'number' ? rawContrad * 100 : parseFloat(rawContrad) * 100;
    return Math.round(percentage);
  } catch (error) {
    return null;
  }
}

/**
 * Compute effective cap based on priority order
 * Order: error 5% > stale 8% > alert_cap > engine_cap > active_policy.cap_daily
 * @param {Object} state - Unified state
 * @returns {number|null} - Effective cap percentage or null
 */
function computeEffectiveCap(state) {
  try {
    const backendStatus = getBackendStatus(state);
    const updated = getUpdatedTs(state);

    // Priority 1: Error state = 5%
    if (backendStatus === 'error') {
      return 5;
    }

    // Priority 2: Stale state = 8%
    if (backendStatus === 'stale' || isStale(updated, TTL_STALE_MINUTES)) {
      return 8;
    }

    // Priority 3: Alert cap (if alerts are active)
    const alertCap = state?.governance?.caps?.alert_cap ||
                     state?.alerts?.active_cap ||
                     null;
    if (alertCap !== null && typeof alertCap === 'number') {
      return Math.round(alertCap);
    }

    // Priority 4: Engine cap (dynamically computed)
    const engineCap = state?.governance?.caps?.engine_cap ||
                      state?.governance?.computed_cap ||
                      null;
    if (engineCap !== null && typeof engineCap === 'number') {
      return Math.round(engineCap);
    }

    // Priority 5: Active policy cap (configured baseline)
    const policyCap = state?.governance?.active_policy?.cap_daily ||
                      state?.governance?.policy?.cap_daily ||
                      null;
    if (policyCap !== null && typeof policyCap === 'number') {
      return Math.round(policyCap);
    }

    return null;
  } catch (error) {
    return null;
  }
}

/**
 * Get effective cap percentage (alias for computeEffectiveCap)
 * @param {Object} state - Unified state
 * @returns {number|null} - Effective cap percentage or null
 */
function getEffectiveCap(state) {
  return computeEffectiveCap(state);
}

/**
 * Get count of active overrides
 * @param {Object} state - Unified state
 * @returns {number} - Count of overrides (0 if none)
 */
function getOverridesCount(state) {
  try {
    // Check different possible locations for overrides
    const overrides = state?.governance?.overrides ||
                     state?.governance?.active_overrides ||
                     state?.overrides ||
                     [];

    if (Array.isArray(overrides)) {
      return overrides.length;
    }

    if (typeof overrides === 'object' && overrides !== null) {
      return Object.keys(overrides).filter(key => overrides[key]).length;
    }

    // Check specific override flags
    let count = 0;
    if (state?.governance?.flags?.euphoria_override) count++;
    if (state?.governance?.flags?.divergence_override) count++;
    if (state?.governance?.flags?.risk_low_override) count++;

    return count;
  } catch (error) {
    return 0;
  }
}

/**
 * Get backend status
 * @param {Object} state - Unified state
 * @returns {string} - 'healthy'|'stale'|'error'
 */
function getBackendStatus(state) {
  try {
    const apiStatus = state?.ui?.apiStatus?.backend;

    if (apiStatus === 'error' || apiStatus === 'failed') {
      return 'error';
    }

    if (apiStatus === 'stale') {
      return 'stale';
    }

    // Check if data is stale based on timestamp
    const updated = getUpdatedTs(state);
    if (isStale(updated, TTL_STALE_MINUTES)) {
      return 'stale';
    }

    return apiStatus === 'healthy' ? 'healthy' : 'healthy';
  } catch (error) {
    return 'error';
  }
}

/**
 * Main render function for badges
 * @param {HTMLElement} containerEl - Container element
 * @param {Object} props - Optional props to override store data
 */
function renderBadges(containerEl, props = {}) {
  if (!containerEl) {
    console.warn('renderBadges: containerEl is required');
    return;
  }

  // Inject CSS if not already present
  injectBadgeCSS();

  // Get state from window.store or use fallback
  const state = getUnifiedState();

  // Extract badge data (props override store data)
  const badgeData = {
    source: props.source || getDecisionSource(state),
    updated: props.updated || getUpdatedTs(state),
    contradiction: props.contradiction !== undefined ? props.contradiction : getContradiction(state),
    cap: props.cap !== undefined ? props.cap : getEffectiveCap(state),
    overrides: props.overrides !== undefined ? props.overrides : getOverridesCount(state),
    status: props.status || getBackendStatus(state)
  };

  // Build badge HTML
  const badgeHtml = buildBadgeHtml(badgeData);

  // Set container content with accessibility
  containerEl.innerHTML = badgeHtml;
  containerEl.setAttribute('aria-label', `Status: ${badgeData.source}, Updated: ${formatZurich(badgeData.updated)}`);
}

/**
 * Build badge HTML string
 * @param {Object} data - Badge data object
 * @returns {string} - HTML string
 */
function buildBadgeHtml(data) {
  const parts = [];

  // Source
  if (data.source && data.source !== '-') {
    parts.push(`<span class="badge-value">${data.source}</span>`);
    parts.push('<span class="badge-separator">•</span>');
  }

  // Updated timestamp with status flag
  const formattedTime = formatZurich(data.updated);
  const statusFlag = data.status === 'stale' ? ' STALE' : data.status === 'error' ? ' ERROR' : '';
  parts.push(`<span>Updated <span class="badge-value">${formattedTime}</span>${statusFlag}</span>`);

  // Contradiction
  if (data.contradiction !== null && data.contradiction !== undefined) {
    parts.push('<span class="badge-separator">•</span>');
    parts.push(`<span>Contrad <span class="badge-value">${data.contradiction}%</span></span>`);
  }

  // Cap (effective)
  if (data.cap !== null && data.cap !== undefined) {
    parts.push('<span class="badge-separator">•</span>');
    parts.push(`<span>Cap <span class="badge-value">${data.cap}%</span></span>`);
  }

  // Overrides
  if (data.overrides > 0) {
    parts.push('<span class="badge-separator">•</span>');
    parts.push(`<span>Overrides <span class="badge-value">${data.overrides}</span></span>`);
  }

  const statusClass = getStatusClass(data.status);
  return `<div class="badges"><div class="badge ${statusClass}" aria-label="Governance status badge">${parts.join('')}</div></div>`;
}

/**
 * Get CSS class for status
 * @param {string} status - Status string
 * @returns {string} - CSS class name
 */
function getStatusClass(status) {
  switch (status) {
    case 'healthy': return 'badge-status-healthy';
    case 'stale': return 'badge-status-stale';
    case 'error': return 'badge-status-error';
    default: return 'badge-status-unknown';
  }
}

/**
 * Get unified state from available sources
 * @returns {Object} - State object
 */
function getUnifiedState() {
  // Try different global state sources - Real API data first
  return window.store?.snapshot?.() ||
         window.store?.getState?.() ||
         window.realDataStore ||  // Real API data from WealthContextBar
         window.globalStore ||
         window.state ||
         {};
}

/**
 * Inject badge CSS styles
 */
function injectBadgeCSS() {
  if (document.getElementById('governance-badges-css')) return;

  const style = document.createElement('style');
  style.id = 'governance-badges-css';
  style.textContent = `
    .badges {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
    }

    .badge {
      font-size: 11px;
      font-family: system-ui, monospace;
      padding: 4px 8px;
      border-radius: var(--radius-sm, 4px);
      border: 1px solid var(--theme-border);
      background: var(--theme-bg);
      color: var(--theme-text-muted);
      white-space: nowrap;
      display: inline-flex;
      align-items: center;
      gap: 2px;
      line-height: 1.2;
    }

    .badge-status-healthy {
      border-color: var(--success);
      background: color-mix(in oklab, var(--success) 10%, var(--theme-bg));
      color: var(--theme-text);
    }

    .badge-status-stale {
      border-color: var(--warning);
      background: color-mix(in oklab, var(--warning) 15%, var(--theme-bg));
      color: var(--warning);
    }

    .badge-status-error {
      border-color: var(--danger);
      background: color-mix(in oklab, var(--danger) 15%, var(--theme-bg));
      color: var(--danger);
    }

    .badge-status-unknown {
      border-color: var(--theme-border);
      background: var(--theme-bg);
      color: var(--theme-text-muted);
    }

    .badge-separator {
      color: var(--theme-text-muted);
      margin: 0 1px;
      opacity: 0.7;
    }

    .badge-value {
      font-weight: 600;
      color: var(--theme-text);
    }

    .badge-status-stale .badge-value,
    .badge-status-error .badge-value {
      color: inherit;
    }
  `;
  document.head.appendChild(style);
}

// Export all functions
export {
  renderBadges,
  formatZurich,
  isStale,
  computeEffectiveCap,
  getDecisionSource,
  getUpdatedTs,
  getContradiction,
  getEffectiveCap,
  getOverridesCount,
  getBackendStatus
};