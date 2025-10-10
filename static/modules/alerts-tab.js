/**
 * Risk Dashboard - Alerts History Tab
 * Displays and manages alert history with filtering and pagination
 */

import { formatRelativeTime, formatAlertType, showLoading, showError } from './risk-utils.js';

// Pagination state
let alertsHistoryData = [];
let currentAlertsPage = 1;
let totalAlertsPages = 1;
const alertsPerPage = 20;

/**
 * Fetch alerts history from API
 * @param {Object} filters - Filter parameters (severity, type)
 * @returns {Promise<Array>} Array of alerts
 */
async function fetchAlertsHistory(filters = {}) {
  try {
    console.debug('Loading alerts history...', filters);

    // Build query parameters
    const params = new URLSearchParams();
    params.append('limit', '100'); // Fetch more for client-side filtering
    params.append('offset', '0');
    params.append('include_snoozed', 'true');

    // Only add filters if they have values
    if (filters.severity && filters.severity.trim() !== '') {
      params.append('severity_filter', filters.severity);
    }
    if (filters.type && filters.type.trim() !== '') {
      params.append('type_filter', filters.type);
    }

    // Use active endpoint with X-User header via globalConfig
    const alerts = await window.globalConfig.apiRequest('/api/alerts/active', {
      params: Object.fromEntries(params)
    });
    console.debug(`History loaded: ${alerts?.length || 0} alerts`);

    return alerts || [];

  } catch (error) {
    debugLogger.error('Failed to load alerts history:', error);
    throw error;
  }
}

/**
 * Filter alerts by time period
 * @param {Array} alerts - Array of alerts
 * @param {number} days - Number of days to include
 * @returns {Array} Filtered alerts
 */
function filterAlertsHistoryByPeriod(alerts, days) {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - days);

  return alerts.filter(alert => {
    const alertDate = new Date(alert.created_at);
    return alertDate >= cutoffDate;
  });
}

/**
 * Format alert with unified template (client-side)
 * @param {Object} alert - Alert object
 * @returns {Object} Formatted alert { action, impact, reasons, details }
 */
function formatAlertClientSide(alert) {
  const alertType = alert.alert_type;
  const severity = alert.severity;
  const currentValue = alert.data?.current_value || 0;
  const portfolioValue = 100000; // €100k par défaut

  // Templates simplifiés
  const templates = {
    'VOL_Q90_CROSS': {
      'S1': { action: 'Surveillance volatilité', impact_base: 0.5, reasons: ['Volatilité Q90 dépassée', 'Conditions de marché agitées'] },
      'S2': { action: 'Réduction exposition (mode Slow)', impact_base: 2.0, reasons: ['Volatilité critique détectée', 'Risque de drawdown majoré'] },
      'S3': { action: 'Arrêt immédiat trading (Freeze)', impact_base: 8.0, reasons: ['Volatilité extrême mesurée', 'Protection capital prioritaire'] }
    },
    'EXEC_COST_SPIKE': {
      'S1': { action: 'Surveillance coûts exécution', impact_base: 0.2, reasons: ['Coûts trading légèrement élevés', 'Conditions liquidité moyennes'] },
      'S2': { action: 'Ralentissement trading (mode Slow)', impact_base: 1.5, reasons: ['Coûts exécution anormalement hauts', 'Liquidité marché dégradée'] },
      'S3': { action: 'Arrêt trading (mode Freeze)', impact_base: 4.0, reasons: ['Coûts exécution prohibitifs', 'Liquidité marché très dégradée'] }
    },
    'DECISION_DROP': {
      'S1': { action: 'Monitoring confiance décision', impact_base: 0.4, reasons: ['Score décision en baisse', 'Confiance allocation réduite'] },
      'S2': { action: 'Mode prudent allocation', impact_base: 2.2, reasons: ['Chute confiance décision significative', 'Qualité allocation dégradée'] },
      'S3': { action: 'Mode ultra-conservateur (Freeze)', impact_base: 9.0, reasons: ['Effondrement confiance décision', 'Allocations potentiellement erronées'] }
    }
  };

  const template = templates[alertType]?.[severity] ||
    { action: `Alerte ${alertType}`, impact_base: 1.0, reasons: ['Situation détectée', 'Action recommandée'] };

  const impact_euro = portfolioValue * template.impact_base / 100;

  return {
    action: template.action,
    impact: impact_euro >= 1 ? `€${Math.round(impact_euro).toLocaleString()}` : `€${impact_euro.toFixed(2)}`,
    reasons: template.reasons,
    details: `Valeur ${currentValue} détectée - ${severity} à ${new Date(alert.created_at).toLocaleTimeString()}`
  };
}

/**
 * Create table row for alert
 * @param {Object} alert - Alert object
 * @returns {string} HTML string for table row
 */
function createAlertsHistoryRow(alert) {
  const formatTime = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const getStatusText = (alert) => {
    if (alert.acknowledged_at) {
      return `<span style="color: var(--success)">✅ Acknowledged</span>`;
    }
    if (alert.snooze_until && new Date(alert.snooze_until) > new Date()) {
      return `<span style="color: var(--warning)">⏸️ Snoozed</span>`;
    }
    return `<span style="color: var(--error)">🚨 Active</span>`;
  };

  // Format unified alert
  const formatted = formatAlertClientSide(alert);

  const formattedMessage = `
    <div class="alert-unified-format">
      <div class="alert-action">
        <strong>🎯 ${formatted.action}</strong>
      </div>
      <div class="alert-impact">
        💰 Impact: <span class="alert-impact-value">${formatted.impact}</span>
      </div>
      <div class="alert-reasons">
        📋 Raisons:
        <ul class="alert-reasons-list">
          ${formatted.reasons.map(reason => `<li>${reason}</li>`).join('')}
        </ul>
      </div>
      <div class="alert-details">
        ℹ️ ${formatted.details}
      </div>
    </div>
  `;

  return `
    <tr>
      <td>
        <span class="alert-severity-badge ${alert.severity}">${alert.severity}</span>
      </td>
      <td>
        <div class="alert-type-label">${formatAlertType(alert.alert_type)}</div>
      </td>
      <td class="alert-message-cell">
        ${formattedMessage}
      </td>
      <td>
        <div class="alert-timestamp">${formatTime(alert.created_at)}</div>
        <div class="alert-timestamp" style="font-size: 0.7rem; color: var(--text-muted);">${formatRelativeTime(alert.created_at)}</div>
      </td>
      <td>
        ${getStatusText(alert)}
      </td>
      <td>
        <button
          class="alert-action-btn"
          onclick="alert('Alert details modal not implemented yet')"
          title="View alert details">
          📋 Details
        </button>
      </td>
    </tr>
  `;
}

/**
 * Update alerts statistics display
 * @param {Array} alerts - Array of alerts
 */
function updateAlertsStats(alerts) {
  console.debug('Updating alerts stats for', alerts?.length || 0, 'alerts');

  const stats = {
    total: alerts?.length || 0,
    S1: alerts?.filter(a => a.severity === 'S1').length || 0,
    S2: alerts?.filter(a => a.severity === 'S2').length || 0,
    S3: alerts?.filter(a => a.severity === 'S3').length || 0,
    acknowledged: alerts?.filter(a => a.acknowledged_at).length || 0
  };

  console.debug('Computed stats:', stats);

  const statsHtml = `
    <div class="alerts-stats" id="alerts-stats-display">
      <div class="alerts-stat">
        <div class="alerts-stat-number">${stats.total}</div>
        <div class="alerts-stat-label">Total</div>
      </div>
      <div class="alerts-stat">
        <div class="alerts-stat-number">${stats.S3}</div>
        <div class="alerts-stat-label">Critical</div>
      </div>
      <div class="alerts-stat">
        <div class="alerts-stat-number">${stats.S2}</div>
        <div class="alerts-stat-label">Warnings</div>
      </div>
      <div class="alerts-stat">
        <div class="alerts-stat-number">${stats.S1}</div>
        <div class="alerts-stat-label">Info</div>
      </div>
      <div class="alerts-stat">
        <div class="alerts-stat-number">${stats.acknowledged}</div>
        <div class="alerts-stat-label">Acknowledged</div>
      </div>
    </div>
  `;

  const container = document.getElementById('alerts-history-content');
  if (container) {
    // Remove existing stats if present
    const existingStats = document.getElementById('alerts-stats-display');
    if (existingStats) {
      existingStats.remove();
    }

    container.insertAdjacentHTML('afterbegin', statsHtml);
    console.debug('Stats HTML inserted into container');
  } else {
    debugLogger.warn('alerts-history-content container not found');
  }
}

/**
 * Render alerts history page with pagination
 */
function renderAlertsHistoryPage() {
  const container = document.getElementById('alerts-history-content');
  const paginationContainer = document.getElementById('alerts-pagination');

  if (!alertsHistoryData.length) {
    container.innerHTML = '<div class="loading-center">No alerts found for the selected criteria.</div>';
    if (paginationContainer) paginationContainer.style.display = 'none';
    return;
  }

  // Calculate pagination
  const start = (currentAlertsPage - 1) * alertsPerPage;
  const end = start + alertsPerPage;
  const pageAlerts = alertsHistoryData.slice(start, end);

  // Render alerts table
  const table = document.createElement('table');
  table.className = 'alerts-table';

  // Table header
  table.innerHTML = `
    <thead>
      <tr>
        <th>Severity</th>
        <th>Type</th>
        <th>Message</th>
        <th>Created</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      ${pageAlerts.map(alert => createAlertsHistoryRow(alert)).join('')}
    </tbody>
  `;

  container.innerHTML = '';
  container.appendChild(table);

  // Update pagination
  updateAlertsPagination();
}

/**
 * Update pagination controls
 */
function updateAlertsPagination() {
  const paginationContainer = document.getElementById('alerts-pagination');
  const prevBtn = document.getElementById('alerts-prev-btn');
  const nextBtn = document.getElementById('alerts-next-btn');
  const pageInfo = document.getElementById('alerts-page-info');

  if (!paginationContainer) return;

  if (totalAlertsPages <= 1) {
    paginationContainer.style.display = 'none';
    return;
  }

  paginationContainer.style.display = 'flex';
  if (prevBtn) prevBtn.disabled = currentAlertsPage <= 1;
  if (nextBtn) nextBtn.disabled = currentAlertsPage >= totalAlertsPages;
  if (pageInfo) pageInfo.textContent = `Page ${currentAlertsPage} of ${totalAlertsPages}`;
}

/**
 * Load alerts history with current filters
 */
async function loadAlertsHistory() {
  try {
    const severityFilterEl = document.getElementById('alerts-severity-filter');
    const typeFilterEl = document.getElementById('alerts-type-filter');
    const periodFilterEl = document.getElementById('alerts-period-filter');

    const severityFilter = severityFilterEl ? severityFilterEl.value : '';
    const typeFilter = typeFilterEl ? typeFilterEl.value : '';
    const periodDays = periodFilterEl ? parseInt(periodFilterEl.value) : 7;

    console.debug('Loading alerts with filters:', { severityFilter, typeFilter, periodDays });

    // Show loading state
    const container = document.getElementById('alerts-history-content');
    if (container) {
      showLoading(container, 'Loading alerts history...');
    }

    // Fetch all alerts with basic filters
    let alerts = await fetchAlertsHistory({
      severity: severityFilter,
      type: typeFilter
    });

    // Filter by period client-side
    alerts = filterAlertsHistoryByPeriod(alerts, periodDays);

    alertsHistoryData = alerts;

    // Store globally for modal system (if needed)
    window.currentAlertsData = alerts;

    currentAlertsPage = 1;
    totalAlertsPages = Math.ceil(alerts.length / alertsPerPage);

    renderAlertsHistoryPage();
    updateAlertsStats(alerts);

  } catch (error) {
    debugLogger.error('Error loading alerts history:', error);
    const container = document.getElementById('alerts-history-content');
    if (container) {
      showError(container, 'Failed to load alerts history. Please try again.');
    }
  }
}

/**
 * Navigate to previous page
 */
function loadPreviousAlertsPage() {
  if (currentAlertsPage > 1) {
    currentAlertsPage--;
    renderAlertsHistoryPage();
  }
}

/**
 * Navigate to next page
 */
function loadNextAlertsPage() {
  if (currentAlertsPage < totalAlertsPages) {
    currentAlertsPage++;
    renderAlertsHistoryPage();
  }
}

/**
 * Render the Alerts History tab
 * @param {HTMLElement} container - Container element
 */
export async function renderAlertsTab(container) {
  debugLogger.debug('🚀 Rendering Alerts History tab');

  // Build tab HTML structure
  container.innerHTML = `
    <div class="alerts-header">
      <h2>Alerts History</h2>
      <div class="alerts-controls">
        <select id="alerts-period-filter" onchange="window.filterAlertsHistory()">
          <option value="1">Last 24h</option>
          <option value="7" selected>Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
        </select>
        <select id="alerts-severity-filter" onchange="window.filterAlertsHistory()">
          <option value="">All Severities</option>
          <option value="S1">S1 (Info)</option>
          <option value="S2">S2 (Warning)</option>
          <option value="S3">S3 (Critical)</option>
        </select>
        <select id="alerts-type-filter" onchange="window.filterAlertsHistory()">
          <option value="">All Types</option>
          <option value="VOL_Q90_CROSS">Volatility</option>
          <option value="EXEC_COST_SPIKE">Execution Cost</option>
          <option value="DECISION_DROP">Decision Drop</option>
        </select>
        <button class="refresh-btn" onclick="window.filterAlertsHistory()">
          🔄 Refresh
        </button>
      </div>
    </div>

    <div id="alerts-history-content">
      <div class="loading-center">Loading alerts...</div>
    </div>

    <div id="alerts-pagination" class="alerts-pagination" style="display: none;">
      <button id="alerts-prev-btn" onclick="window.loadPreviousAlertsPage()">← Previous</button>
      <span id="alerts-page-info">Page 1 of 1</span>
      <button id="alerts-next-btn" onclick="window.loadNextAlertsPage()">Next →</button>
    </div>
  `;

  // Expose functions globally for onclick handlers
  window.filterAlertsHistory = loadAlertsHistory;
  window.loadPreviousAlertsPage = loadPreviousAlertsPage;
  window.loadNextAlertsPage = loadNextAlertsPage;

  // Load alerts
  await loadAlertsHistory();
}

// Export main function
export default {
  renderAlertsTab
};
