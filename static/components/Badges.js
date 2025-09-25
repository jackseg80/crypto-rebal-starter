/**
 * Composant de badges standardisé (ES module)
 * Format: "Source • Updated HH:MM:SS • Contrad XX% • Cap YY% • Overrides N"
 * Integré avec store unified et timezone Europe/Zurich
 */

import { formatZurich, isStale } from '../utils/time.js';
import { selectContradictionPct, selectEffectiveCap, selectOverridesCount, selectGovernanceTimestamp, selectDecisionSource, selectCapPercent, selectPolicyCapPercent, selectEngineCapPercent } from '../selectors/governance.js';

// Constants
const TTL_STALE_MINUTES = 30;

function normalizeCapDisplay(raw) {
  if (typeof raw !== 'number' || !Number.isFinite(raw)) {
    return null;
  }
  const absolute = Math.abs(raw);
  const percent = absolute <= 1 ? absolute * 100 : absolute;
  const rounded = Math.round(percent);
  return Number.isFinite(rounded) ? rounded : null;
}

/**
 * Store selectors - helpers robustes qui ne plantent jamais
 */

// Note: getDecisionSource remplacé par selectDecisionSource du module centralisé

// Note: getUpdatedTs remplacé par selectGovernanceTimestamp du module centralisé

// Note: getContradiction remplacé par selectContradictionPct du module centralisé



/**
 * Compute effective cap based on priority order
 * Order: error 5% > stale 8% > alert_cap > active_policy.cap_daily > engine_cap
 * @param {Object} state - Unified state
 * @returns {number|null} - Effective cap percentage or null
 */
function computeEffectiveCap(state) {
  try {
    const backendStatus = getBackendStatus(state);

    if (backendStatus === 'error') {
      return 5;
    }

    if (backendStatus === 'stale') {
      return 8;
    }

    const alertCap = normalizeCapDisplay(state?.governance?.caps?.alert_cap ?? state?.alerts?.active_cap);
    if (alertCap != null) {
      return alertCap;
    }

    const policyCap = selectCapPercent(state);
    if (policyCap != null) {
      return policyCap;
    }

    const engineCap = normalizeCapDisplay(state?.governance?.caps?.engine_cap ??
                      state?.governance?.computed_cap ??
                      state?.governance?.engine_cap_daily);
    if (engineCap != null) {
      return engineCap;
    }

    return null;
  } catch (error) {
    return null;
  }
}

// Note: getEffectiveCap remplacé par selectEffectiveCap du module centralisé

// Note: getOverridesCount remplacé par selectOverridesCount du module centralisé

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
    const updated = selectGovernanceTimestamp(state);
    if (isStale(updated, TTL_STALE_MINUTES)) {
      return 'stale';
    }

    return apiStatus === 'healthy' ? 'healthy' : 'healthy';
  } catch (error) {
    return 'error';
  }
}


function computeOverrideFlags(props = {}) {
  return {
    source: Object.prototype.hasOwnProperty.call(props, 'source'),
    updated: Object.prototype.hasOwnProperty.call(props, 'updated'),
    contradiction: Object.prototype.hasOwnProperty.call(props, 'contradiction'),
    cap: Object.prototype.hasOwnProperty.call(props, 'cap'),
    overrides: Object.prototype.hasOwnProperty.call(props, 'overrides'),
    status: Object.prototype.hasOwnProperty.call(props, 'status')
  };
}

function collectBadgeData(state = {}, props = {}, overrideFlags = computeOverrideFlags({})) {
  return {
    source: overrideFlags.source ? props.source : selectDecisionSource(state),
    updated: overrideFlags.updated ? props.updated : selectGovernanceTimestamp(state),
    contradiction: overrideFlags.contradiction ? props.contradiction : selectContradictionPct(state),
    cap: overrideFlags.cap ? props.cap : selectEffectiveCap(state),
    capPolicy: selectPolicyCapPercent(state),
    capEngine: selectEngineCapPercent(state),
    overrides: overrideFlags.overrides ? props.overrides : selectOverridesCount(state),
    status: overrideFlags.status ? props.status : getBackendStatus(state)
  };
}

function getFallbackState(primaryState) {
  if (typeof window === 'undefined') {
    return null;
  }

  const candidates = [
    window.realDataStore,
    window.globalStore,
    window.state
  ];

  for (const candidate of candidates) {
    if (candidate && candidate !== primaryState) {
      return candidate;
    }
  }

  return null;
}

function mergeBadgeDataWithFallback(primary, fallback, overrideFlags = computeOverrideFlags({})) {
  if (!fallback) {
    return primary;
  }

  const result = { ...primary };
  const fallbackStatus = fallback.status;
  const fallbackStatusActionable = fallbackStatus && !['error', 'failed'].includes(fallbackStatus);
  const primaryStatusProblem = !result.status || ['error', 'failed', 'unknown'].includes(result.status);

  let usedFallback = false;
  if (!overrideFlags.status && fallbackStatusActionable && primaryStatusProblem) {
    result.status = fallbackStatus;
    usedFallback = true;
  }

  if (!overrideFlags.source && (!result.source || result.source === '-') && fallback.source) {
    result.source = fallback.source;
  }

  if (!overrideFlags.updated && (!result.updated || usedFallback) && fallback.updated) {
    result.updated = fallback.updated;
  }

  if (!overrideFlags.contradiction) {
    const needsContradiction = usedFallback || !Number.isFinite(result.contradiction);
    if (needsContradiction && Number.isFinite(fallback.contradiction)) {
      result.contradiction = fallback.contradiction;
    }
  }

  if (!overrideFlags.cap) {
    const needsCap = usedFallback || !Number.isFinite(result.cap);
    if (needsCap && Number.isFinite(fallback.cap)) {
      result.cap = fallback.cap;
    }
  }
  if (result.capPolicy == null && Number.isFinite(fallback.capPolicy)) {
    result.capPolicy = fallback.capPolicy;
  }
  if (result.capEngine == null && Number.isFinite(fallback.capEngine)) {
    result.capEngine = fallback.capEngine;
  }

  if (!overrideFlags.overrides) {
    const needsOverrides = usedFallback || result.overrides == null;
    if (needsOverrides && Number.isFinite(fallback.overrides)) {
      result.overrides = fallback.overrides;
    }
  }

  return result;
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
  const overrideFlags = computeOverrideFlags(props);
  let badgeData = collectBadgeData(state, props, overrideFlags);

  const fallbackState = getFallbackState(state);
  if (fallbackState) {
    const fallbackData = collectBadgeData(fallbackState, props, overrideFlags);
    badgeData = mergeBadgeDataWithFallback(badgeData, fallbackData, overrideFlags);
  }

  // Build badge HTML
  const badgeHtml = buildBadgeHtml(badgeData);

  // Set container content with accessibility
  containerEl.innerHTML = badgeHtml;
  const sourceLabel = badgeData.source || 'unknown';
  containerEl.setAttribute('aria-label', `Status: ${sourceLabel}, Updated: ${formatZurich(badgeData.updated)}`);
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
  if (data.capPolicy != null && Number.isFinite(data.capPolicy)) {
    parts.push('<span class="badge-separator">•</span>');
    const capChunks = [`Cap <span class=\"badge-value\">${data.capPolicy}%</span>`];
    if (data.capEngine != null && Number.isFinite(data.capEngine) && data.capEngine !== data.capPolicy) {
      capChunks.push(`SMART <span class=\"badge-value\">${data.capEngine}%</span>`);
    }
    parts.push(`<span>${capChunks.join(' • ')}</span>`);
  } else if (data.cap != null && Number.isFinite(data.cap)) {
    parts.push('<span class="badge-separator">•</span>');
    parts.push(`<span>Cap <span class="badge-value">${data.cap}%</span></span>`);
  } else if (data.cap != null) {
    parts.push('<span class="badge-separator">•</span>');
    parts.push('<span>Cap <span class="badge-value">—</span></span>');
  } else {
    parts.push('<span class="badge-separator">•</span>');
    parts.push('<span>Cap <span class="badge-value">—</span></span>');
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

// Export functions (keeping legacy computeEffectiveCap and getBackendStatus)
export {
  renderBadges,
  formatZurich,
  isStale,
  computeEffectiveCap,
  getBackendStatus
};

// Re-export centralized selectors for backward compatibility
export {
  selectContradictionPct as getContradiction,
  selectEffectiveCap as getEffectiveCap,
  selectOverridesCount as getOverridesCount,
  selectDecisionSource as getDecisionSource,
  selectGovernanceTimestamp as getUpdatedTs
} from '../selectors/governance.js';