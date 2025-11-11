// ==============================
// Targets Tab Module
// ==============================
// Extracted from risk-dashboard.html
// Handles strategic targeting, portfolio allocations, and action plans
//
// Dependencies:
// - ./targets-coordinator.js (proposeTargets, applyTargets, computePlan, getDecisionLog)
// - ../shared-asset-groups.js (getAssetGroup, UNIFIED_ASSET_GROUPS, GROUP_ORDER)
// - window.store (state management)
// - window.loadBalanceData (portfolio loading)
// - window.parseCSVBalances (CSV parsing)

import { proposeTargets, applyTargets, computePlan, getDecisionLog } from './targets-coordinator.js';

// ====== Dev Environment Detection ======
/**
 * Detect if running in dev environment (localhost or LAN IPs)
 * Used to auto-bypass cooldown for development convenience
 * @returns {boolean} True if dev environment
 */
function isDevEnvironment() {
  const hostname = window.location.hostname;
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    hostname.startsWith('172.16.') ||
    hostname.startsWith('172.17.') ||
    hostname.startsWith('172.18.') ||
    hostname.startsWith('172.19.') ||
    hostname.startsWith('172.20.') ||
    hostname.startsWith('172.21.') ||
    hostname.startsWith('172.22.') ||
    hostname.startsWith('172.23.') ||
    hostname.startsWith('172.24.') ||
    hostname.startsWith('172.25.') ||
    hostname.startsWith('172.26.') ||
    hostname.startsWith('172.27.') ||
    hostname.startsWith('172.28.') ||
    hostname.startsWith('172.29.') ||
    hostname.startsWith('172.30.') ||
    hostname.startsWith('172.31.')
  );
}

// ====== Portfolio Allocation Helper ======
/**
 * Get current portfolio allocation by asset groups
 * @returns {Promise<Object>} Allocation object with percentages by group
 */
export async function getCurrentPortfolioAllocation() {
  let realBalances = [];

  try {
    // Utiliser la source de données configurée
    debugLogger.debug('🔍 Loading portfolio allocation using configured source...');
    const balanceResult = await window.loadBalanceData();

    if (!balanceResult.success) {
      throw new Error(balanceResult.error);
    }

    let balances;

    if (balanceResult.csvText) {
      // Source CSV locale
      balances = window.parseCSVBalances(balanceResult.csvText);
    } else if (balanceResult.data && balanceResult.data.items) {
      // Source API (stub ou cointracking_api)
      balances = balanceResult.data.items.map(item => ({
        symbol: item.symbol,
        balance: item.balance,
        value_usd: item.value_usd
      }));
    } else {
      throw new Error('Invalid data format received');
    }

    realBalances = balances.map(item => ({
      symbol: item.symbol,
      value_usd: item.value_usd
    }));

    (function () {
      const cur = (window.globalConfig && window.globalConfig.get('display_currency')) || 'USD';
      const rate = (window.currencyManager && window.currencyManager.getRateSync(cur)) || 1;
      if (cur !== 'USD' && (!rate || rate <= 0)) {
        debugLogger.debug('🔍 DEBUG getCurrentPortfolioAllocation: Using real CSV data -', realBalances.length, 'assets, total: —');
      } else {
        const val = realBalances.reduce((s, i) => s + i.value_usd, 0) * rate;
        try {
          const dec = (cur === 'BTC') ? 8 : 2;
          debugLogger.debug('🔍 DEBUG getCurrentPortfolioAllocation: Using real CSV data -', realBalances.length, 'assets, total:', new Intl.NumberFormat('fr-FR', { style: 'currency', currency: cur, minimumFractionDigits: dec, maximumFractionDigits: dec }).format(val));
        } catch (_) {
          debugLogger.debug('🔍 DEBUG getCurrentPortfolioAllocation: Using real CSV data -', realBalances.length, 'assets, total:', (val).toFixed(cur === 'BTC' ? 8 : 2), cur);
        }
      }
    })();

  } catch (error) {
    debugLogger.error('CRITICAL: Could not load CSV data in getCurrentPortfolioAllocation:', error);
    throw error; // Don't fallback - fail properly so we know there's an issue
  }

  const totalValue = realBalances.reduce((sum, item) => sum + item.value_usd, 0);

  // Use the unified asset classification system
  const { getAssetGroup, UNIFIED_ASSET_GROUPS, GROUP_ORDER } = await import('../shared-asset-groups.js');

  // Initialize allocation object with all groups
  const allocation = {};
  GROUP_ORDER.forEach(category => {
    allocation[category] = 0;
  });
  allocation.model_version = 'portfolio-actuel';

  // Classifier chaque asset using unified system
  realBalances.forEach(item => {
    const symbol = item.symbol.toUpperCase();
    const targetGroup = getAssetGroup(symbol);
    allocation[targetGroup] += (item.value_usd / totalValue) * 100;
  });

  return allocation;
}

// ====== Targets Content Renderer ======
/**
 * Render the Targets tab content with strategy selection and allocations
 */
export async function renderTargetsContent() {
  const container = document.getElementById('targets-content');

  // IMPORTANT: Ensure scores are calculated first
  const state = window.store.snapshot();
  if (!state.scores?.blended) {
    debugLogger.debug('🔄 Blended score not available, recalculating scores...');
    // ✅ Load scores from orchestrator (no need for riskData/ccsData params)
    await window.loadScoresFromStore();
  }

  // Get updated state after potential score calculation
  const updatedState = window.store.snapshot();

  // Check cooldown status
  let cooldownStatus = null;
  try {
    const apiUrl = window.globalConfig ? window.globalConfig.getApiUrl('/execution/governance/cooldown-status') : '/execution/governance/cooldown-status';
    const activeUser = localStorage.getItem('activeUser') || 'demo';
    const response = await fetch(`${apiUrl}?user_id=${activeUser}`);
    if (response.ok) {
      cooldownStatus = await response.json();
    }
  } catch (error) {
    debugLogger.warn('Could not fetch cooldown status:', error.message);
  }

  // Propose different targeting strategies (now with updated scores)
  const macroProposal = proposeTargets('macro');
  const ccsProposal = proposeTargets('ccs');
  const cycleProposal = proposeTargets('cycle');
  const blendedProposal = proposeTargets('blend');
  const smartProposal = proposeTargets('smart');

  // DEBUG: Log what blended proposal contains for display
  debugLogger.debug('🔍 DEBUG renderTargetsContent - updatedState.scores.blended:', updatedState.scores?.blended);
  debugLogger.debug('🔍 DEBUG renderTargetsContent - blendedProposal for DISPLAY:', blendedProposal);
  debugLogger.debug('🔍 DEBUG renderTargetsContent - blendedProposal.strategy:', blendedProposal.strategy);
  debugLogger.debug('🔍 DEBUG renderTargetsContent - BTC allocation for DISPLAY:', blendedProposal.targets.BTC);

  // Current targets from store or use blended as default display
  const appliedTargets = updatedState.targets?.proposed || blendedProposal.targets;
  const appliedStrategy = updatedState.targets?.strategy || blendedProposal.strategy;

  // Get real current portfolio allocation
  const currentAllocation = await getCurrentPortfolioAllocation();

  // Determine if cooldown is active
  const isCooldownActive = cooldownStatus && !cooldownStatus.can_publish;
  const cooldownMessage = cooldownStatus?.message || '';
  const cooldownHoursRemaining = cooldownStatus?.remaining_hours || 0;

  // Check if we're in dev environment (auto-bypass)
  const isDev = isDevEnvironment();
  const hostname = window.location.hostname;

  const buttonDisabled = isCooldownActive && !isDev ? 'disabled' : '';
  const buttonTitle = isCooldownActive && !isDev ? `Cooldown active: ${cooldownHoursRemaining.toFixed(1)}h remaining` : '';

  container.innerHTML = `
    <div style="max-width: 1400px; margin: 0 auto; width: 100%;">
      <!-- Strategy Selection -->
      <div class="risk-card" style="margin-bottom: var(--space-lg);">
        <h3>🎯 Strategic Targeting</h3>

        <!-- Cooldown Status Banner -->
        ${isCooldownActive ? `
          <div style="margin-bottom: var(--space-md); padding: var(--space-md); border-radius: var(--radius-md); background: ${isDev ? 'color-mix(in oklab, var(--info) 10%, transparent)' : 'color-mix(in oklab, var(--warning) 10%, transparent)'}; border: 1px solid ${isDev ? 'var(--info)' : 'var(--warning)'};">
            <div style="display: flex; align-items: center; gap: var(--space-sm);">
              <span style="font-size: 1.25rem;">${isDev ? 'ℹ️' : '⏳'}</span>
              <div style="flex: 1;">
                <div style="font-weight: 600; color: var(--theme-text); margin-bottom: 0.25rem;">
                  ${isDev ? 'Cooldown Active (Dev Auto-Bypass Enabled)' : 'Plan Publication Cooldown Active'}
                </div>
                <div style="font-size: 0.875rem; color: var(--theme-text-muted);">
                  ${isDev
                    ? `Detected dev environment (${hostname}). Cooldown will be automatically bypassed when you click a strategy.`
                    : `${cooldownMessage} - Next publication available in ${cooldownHoursRemaining.toFixed(1)} hours.`
                  }
                </div>
              </div>
            </div>
          </div>
        ` : ''}

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-sm); margin: var(--space-lg) 0;">
          <button class="refresh-btn" onclick="applyStrategy('macro')" ${buttonDisabled} title="${buttonTitle}" style="background: #6b7280; ${buttonDisabled ? 'opacity: 0.5; cursor: not-allowed;' : ''}">
            📊 Macro Only<br>
            <small>${macroProposal.strategy}</small>
          </button>
          <button class="refresh-btn" onclick="applyStrategy('ccs')" ${buttonDisabled} title="${buttonTitle}" style="background: #3b82f6; ${buttonDisabled ? 'opacity: 0.5; cursor: not-allowed;' : ''}">
            📈 CCS Based<br>
            <small>${ccsProposal.strategy}</small>
          </button>
          <button class="refresh-btn" onclick="applyStrategy('cycle')" ${buttonDisabled} title="${buttonTitle}" style="background: #f59e0b; ${buttonDisabled ? 'opacity: 0.5; cursor: not-allowed;' : ''}">
            🔄 Cycle Adjusted<br>
            <small>${cycleProposal.strategy}</small>
          </button>
          <button class="refresh-btn" onclick="applyStrategy('blend')" ${buttonDisabled} title="${buttonTitle}" style="background: #10b981; ${buttonDisabled ? 'opacity: 0.5; cursor: not-allowed;' : ''}">
            ⚖️ Blended Strategy<br>
            <small>${blendedProposal.strategy}</small>
          </button>
          <button class="refresh-btn" onclick="applyStrategy('smart')" ${buttonDisabled} title="${buttonTitle}" style="background: linear-gradient(135deg, #8b5cf6, #06b6d4); color: white; font-weight: bold; border: 2px solid #8b5cf6; ${buttonDisabled ? 'opacity: 0.5; cursor: not-allowed;' : ''}">
            🧠 SMART<br>
            <small style="font-size: 0.75rem;">${smartProposal.strategy}</small>
          </button>
        </div>
      </div>

      <!-- Current vs Proposed (Responsive Grid) -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 500px), 1fr)); gap: var(--space-lg); margin-bottom: var(--space-lg);">
        <!-- Current Allocation -->
        <div class="risk-card">
          <h3>📋 Current Allocation</h3>
          ${renderTargetsTable(currentAllocation, 'Portfolio Actuel')}
        </div>

        <!-- Proposed Targets -->
        <div class="risk-card">
          <h3>🎯 Proposed Targets</h3>
          ${renderTargetsTable(appliedTargets, appliedStrategy)}
          ${renderExposureDelta(smartProposal)}
        </div>
      </div>

      <!-- Action Plan -->
      ${renderActionPlan(currentAllocation, appliedTargets)}

      <!-- Decision History -->
      ${renderDecisionHistory()}
    </div>
  `;

  // Update badges with current data
  const badgePayload = {
    risk_metrics: updatedState.riskMetrics ?? null,
    portfolio_summary: updatedState.portfolioSummary ?? null,
    correlation_metrics: updatedState.correlationMetrics ?? null,
    overrides_count: updatedState.governance?.overrides_count ?? 0
  };
  window.updateRiskDashboardBadges(badgePayload);
}

// ====== Targets Table Renderer ======
/**
 * Render allocation table for a given strategy (2-column compact layout)
 * @param {Object} targets - Allocation targets by group
 * @param {string} strategy - Strategy name
 * @returns {string} HTML for the table
 */
export function renderTargetsTable(targets, strategy) {
  // Robustly handle invalid inputs
  if (!targets || typeof targets !== 'object') {
    debugLogger.warn('[renderTargetsTable] Invalid targets:', targets);
    return `<div style="color: var(--warning); font-size: 0.875rem;">⚠️ Invalid allocation data</div>`;
  }

  const { model_version, ...allocations } = targets;

  // Filter and validate allocations with extra safety
  const validEntries = Object.entries(allocations)
    .filter(([key, value]) => {
      const isValid = value != null && typeof value === 'number' && !isNaN(value);
      if (!isValid && value != null) {
        debugLogger.warn(`[renderTargetsTable] Filtered invalid allocation: ${key}=${value} (type: ${typeof value})`);
      }
      return isValid;
    })
    .sort(([, a], [, b]) => b - a);

  if (validEntries.length === 0) {
    return `
      <div style="font-size: 0.75rem; color: var(--theme-text-muted); margin-bottom: var(--space-sm);">
        ${strategy} (${model_version || 'unknown'})
      </div>
      <div style="color: var(--warning); font-size: 0.875rem;">⚠️ No valid allocations found</div>
    `;
  }

  // Helper to get color based on allocation percentage
  const getAllocationColor = (pct) => {
    if (pct >= 30) return 'var(--success)';
    if (pct >= 10) return 'var(--theme-text)';
    if (pct >= 1) return 'var(--theme-text-muted)';
    return 'color-mix(in oklab, var(--theme-text-muted) 50%, transparent)';
  };

  // Helper to get icon based on asset category
  const getCategoryIcon = (asset) => {
    const icons = {
      'BTC': '₿',
      'ETH': 'Ξ',
      'STABLES': '💵',
      'L1': '🔷',
      'L2': '⚡',
      'DEFI': '🔄',
      'MEMES': '🐸',
      'GAMING': '🎮',
      'AI': '🤖',
      'REAL_WORLD_ASSETS': '🏛️',
      'PRIVACY': '🔒',
      'INFRA': '🛠️'
    };
    return icons[asset] || '●';
  };

  return `
    <div style="margin-bottom: var(--space-lg); width: 100%;">
      <!-- Header -->
      <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: var(--space-md); padding-bottom: var(--space-xs); border-bottom: 1px solid var(--theme-border);">
        <span style="font-size: 0.95rem; font-weight: 600; color: var(--theme-text);">${strategy}</span>
        <span style="font-size: 0.75rem; color: var(--theme-text-muted); font-family: monospace;">${model_version || 'unknown'}</span>
      </div>

      <!-- Responsive 2-Column Table (1 column on mobile) -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: var(--space-xs) var(--space-md);">
        ${validEntries.map(([asset, allocation]) => `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.65rem 0.85rem; border-radius: var(--radius-sm); background: var(--theme-bg); border: 1px solid var(--theme-border); transition: all 0.2s;">
            <span style="display: flex; align-items: center; gap: 0.6rem; color: var(--theme-text);">
              <span style="opacity: 0.5; font-size: 1.1rem;">${getCategoryIcon(asset)}</span>
              <span style="font-weight: 500; font-size: 1rem;">${asset}</span>
            </span>
            <span style="font-weight: 700; font-family: monospace; font-size: 1.05rem; color: ${getAllocationColor(allocation)};">
              ${allocation.toFixed(1)}%
            </span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

// ====== Exposure Delta Renderer ======
/**
 * Render exposure delta for SMART strategy (shows cap overflow if any)
 * @param {Object} smart - SMART strategy proposal
 * @returns {string} HTML for exposure delta
 */
export function renderExposureDelta(smart) {
  try {
    if (!smart) return '';
    const base = Number(smart.base_risky || 0);
    const fin = Number(smart.final_risky || 0);
    const cap = smart.exposure_cap != null ? Number(smart.exposure_cap) : null;
    const backendStatus = smart.backend_status || 'unknown';
    const delta = Math.round((base - fin) * 10) / 10;
    const hasOverflow = delta > 0.05; // >0.05% considered meaningful

    // Only show if we have meaningful data (cap exists OR backend error OR overflow)
    const hasData = cap != null || backendStatus === 'error' || hasOverflow;
    if (!hasData) return '';

    const capText = cap != null ? `${Math.round(cap)}%` : '5% (fallback)';
    const capColor = cap != null && cap >= 70 ? 'var(--success)' : cap != null && cap >= 50 ? 'var(--warning)' : 'var(--danger)';

    return `
      <div style="margin-top: var(--space-lg); padding: var(--space-md); border-radius: var(--radius-md); border: 2px solid ${cap != null ? 'var(--theme-border)' : 'var(--warning)'}; background: var(--theme-bg);">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: ${hasOverflow ? 'var(--space-sm)' : '0'};">
          <span style="font-size: 0.95rem; font-weight: 600; color: var(--theme-text);">
            🛡️ Cap d'exposition risky
          </span>
          <span style="font-size: 1.1rem; font-weight: 700; font-family: monospace; color: ${capColor};">
            ${capText}
          </span>
        </div>
        ${backendStatus === 'error' ? `
          <div style="margin-top: var(--space-xs); font-size: 0.85rem; color: var(--warning);">
            ⚠️ Backend risk budget indisponible — mode prudent (cap conservateur)
          </div>
        ` : ''}
        ${hasOverflow ? `
          <div style="margin-top: var(--space-xs); padding: var(--space-xs) var(--space-sm); border-radius: var(--radius-sm); background: color-mix(in oklab, var(--warning) 10%, transparent); border: 1px solid color-mix(in oklab, var(--warning) 30%, transparent);">
            <div style="font-size: 0.9rem; color: var(--warning); font-weight: 600;">
              ⚠️ Cap appliqué : ${Math.round(base)}% → ${Math.round(fin)}%
            </div>
            <div style="font-size: 0.85rem; color: var(--theme-text-muted); margin-top: 0.2rem;">
              −${delta}% d'exposition non exécutable (protection contre surrisque)
            </div>
          </div>
        ` : ''}
      </div>
    `;
  } catch { return ''; }
}

// ====== Action Plan Renderer ======
/**
 * Render action plan showing differences between current and proposed (2-column compact layout)
 * @param {Object} current - Current allocation
 * @param {Object} proposed - Proposed allocation
 * @returns {string} HTML for action plan
 */
export function renderActionPlan(current, proposed) {
  if (!current || !proposed) return '';

  try {
    const plan = computePlan(current, proposed);

    if (plan.actions.length === 0) {
      return `
        <div class="risk-card">
          <h3>📝 Action Plan</h3>
          <p style="text-align: center; color: var(--success);">✅ No changes needed - targets already optimal</p>
        </div>
      `;
    }

    // Separate buy and sell actions
    const buyActions = plan.actions.filter(a => a.action === 'buy');
    const sellActions = plan.actions.filter(a => a.action === 'sell');

    return `
      <div class="risk-card" style="margin-bottom: var(--space-lg);">
        <h3>📝 Action Plan</h3>

        <!-- Summary Stats (Responsive) -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: var(--space-md); margin-bottom: var(--space-lg); padding: var(--space-md); background: var(--theme-bg); border-radius: var(--radius-md); border: 1px solid var(--theme-border);">
          <div style="text-align: center;">
            <div style="font-size: 1.75rem; font-weight: 700; color: var(--theme-text);">${plan.num_changes}</div>
            <div style="font-size: 0.85rem; color: var(--theme-text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Changes</div>
          </div>
          <div style="text-align: center;">
            <div style="font-size: 1.75rem; font-weight: 700; color: var(--info);">${plan.total_reallocation.toFixed(1)}%</div>
            <div style="font-size: 0.85rem; color: var(--theme-text-muted); text-transform: uppercase; letter-spacing: 0.05em;">To Reallocate</div>
          </div>
          <div style="text-align: center;">
            <div style="font-size: 1.75rem; font-weight: 700; color: ${plan.complexity === 'low' ? 'var(--success)' : plan.complexity === 'medium' ? 'var(--warning)' : 'var(--danger)'};">${plan.complexity}</div>
            <div style="font-size: 0.85rem; color: var(--theme-text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Complexity</div>
          </div>
        </div>

        <!-- Actions Grid (Responsive: 2 columns on desktop, 1 on mobile) -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 350px), 1fr)); gap: var(--space-lg);">

          <!-- Buy Actions -->
          <div>
            <div style="display: flex; align-items: center; gap: var(--space-xs); margin-bottom: var(--space-md); padding-bottom: var(--space-xs); border-bottom: 2px solid var(--success);">
              <span style="font-size: 1.1rem;">🟢</span>
              <span style="font-size: 0.95rem; font-weight: 700; color: var(--success); text-transform: uppercase; letter-spacing: 0.05em;">Buy (${buyActions.length})</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: var(--space-xs);">
              ${buyActions.length === 0 ? '<div style="text-align: center; color: var(--theme-text-muted); font-size: 0.75rem; padding: var(--space-md);">No buy actions</div>' : ''}
              ${buyActions.map(action => {
                const amount = action.change_pct ?? action.amount;
                const current = action.current_pct ?? action.current;
                const target = action.target_pct ?? action.target;

                if (!action || !action.asset || amount == null || current == null || target == null) {
                  return '';
                }

                return `
                  <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.7rem 0.9rem; border-radius: var(--radius-sm); background: color-mix(in oklab, var(--success) 5%, transparent); border: 1px solid color-mix(in oklab, var(--success) 20%, transparent); transition: all 0.2s;">
                    <div style="display: flex; flex-direction: column; gap: 0.2rem;">
                      <span style="font-weight: 600; color: var(--theme-text); font-size: 1rem;">${action.asset}</span>
                      <span style="font-size: 0.85rem; color: var(--theme-text-muted); font-family: monospace;">${current.toFixed(1)}% → ${target.toFixed(1)}%</span>
                    </div>
                    <span style="font-weight: 700; font-family: monospace; color: var(--success); font-size: 1.1rem;">
                      +${amount.toFixed(1)}%
                    </span>
                  </div>
                `;
              }).join('')}
            </div>
          </div>

          <!-- Sell Actions -->
          <div>
            <div style="display: flex; align-items: center; gap: var(--space-xs); margin-bottom: var(--space-md); padding-bottom: var(--space-xs); border-bottom: 2px solid var(--danger);">
              <span style="font-size: 1.1rem;">🔴</span>
              <span style="font-size: 0.95rem; font-weight: 700; color: var(--danger); text-transform: uppercase; letter-spacing: 0.05em;">Sell (${sellActions.length})</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: var(--space-xs);">
              ${sellActions.length === 0 ? '<div style="text-align: center; color: var(--theme-text-muted); font-size: 0.75rem; padding: var(--space-md);">No sell actions</div>' : ''}
              ${sellActions.map(action => {
                const amount = action.change_pct ?? action.amount;
                const current = action.current_pct ?? action.current;
                const target = action.target_pct ?? action.target;

                if (!action || !action.asset || amount == null || current == null || target == null) {
                  return '';
                }

                return `
                  <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.7rem 0.9rem; border-radius: var(--radius-sm); background: color-mix(in oklab, var(--danger) 5%, transparent); border: 1px solid color-mix(in oklab, var(--danger) 20%, transparent); transition: all 0.2s;">
                    <div style="display: flex; flex-direction: column; gap: 0.2rem;">
                      <span style="font-weight: 600; color: var(--theme-text); font-size: 1rem;">${action.asset}</span>
                      <span style="font-size: 0.85rem; color: var(--theme-text-muted); font-family: monospace;">${current.toFixed(1)}% → ${target.toFixed(1)}%</span>
                    </div>
                    <span style="font-weight: 700; font-family: monospace; color: var(--danger); font-size: 1.1rem;">
                      ${amount.toFixed(1)}%
                    </span>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        </div>
      </div>
    `;
  } catch (error) {
    debugLogger.error('Error rendering action plan:', error);
    return '';
  }
}

// ====== Decision History Renderer ======
/**
 * Render decision history from local storage
 * @returns {string} HTML for decision history
 */
export function renderDecisionHistory() {
  const history = getDecisionLog(5);

  if (history.length === 0) {
    return `
      <div class="risk-card" style="margin-bottom: var(--space-lg);">
        <h3>📚 Decision History</h3>
        <p style="text-align: center; color: var(--theme-text-muted);">No previous decisions</p>
      </div>
    `;
  }

  return `
    <div class="risk-card" style="margin-bottom: var(--space-lg);">
      <h3>📚 Decision History</h3>
      <div style="font-size: 0.85rem; color: var(--theme-text-muted); margin-bottom: var(--space-md);">
        Last ${history.length} decisions
      </div>
      <div style="display: flex; flex-direction: column; gap: var(--space-sm);">
        ${history.map(entry => `
          <div style="border-bottom: 1px solid var(--theme-border); padding: var(--space-sm) 0;">
            <div style="font-size: 0.95rem; font-weight: 500; margin-bottom: var(--space-xs);">${entry.strategy}</div>
            <div style="font-size: 0.8rem; color: var(--theme-text-muted); display: flex; flex-wrap: wrap; gap: var(--space-xs);">
              <span>${new Date(entry.timestamp).toLocaleString()}</span>
              <span>•</span>
              <span>CCS: ${Math.round(entry.ccs_score || 0)}</span>
              <span>•</span>
              <span>Confidence: ${Math.round((entry.confidence || 0) * 100)}%</span>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

// ====== Strategy Application ======
/**
 * Apply a targeting strategy and update governance
 * @param {string} mode - Strategy mode (macro, ccs, cycle, blend, smart)
 */
window.applyStrategy = async function (mode) {
  try {
    debugLogger.debug('🔍 DEBUG applyStrategy called with mode:', mode);
    debugLogger.debug('🔍 DEBUG store state before:', window.store.snapshot());

    const proposal = proposeTargets(mode);
    debugLogger.debug('🔍 DEBUG proposal result:', proposal);
    debugLogger.debug('🔍 DEBUG proposal BTC allocation:', proposal.targets.BTC);

    // Instead of direct applyTargets, create governance decision
    const currentAllocation = await getCurrentPortfolioAllocation();

    // Convert proposal targets to format expected by /execution/governance/propose
    // API expects: [{ symbol: "BTC", weight: 0.35 }] where weight is 0-1 fraction
    // Filter out zero allocations (API rejects weight: 0)
    const targets = Object.entries(proposal.targets)
      .filter(([key, value]) => key !== 'model_version' && value > 0)
      .map(([symbol, target_pct]) => ({
        symbol: symbol,
        weight: target_pct / 100 // Convert percentage to fraction (35% -> 0.35)
      }));

    debugLogger.debug('🔍 Creating governance decision with targets:', targets);
    debugLogger.debug('🔍 Proposal strategy:', proposal.strategy);

    // Sync governance state first
    await window.store.syncGovernanceState();
    const governanceStatus = window.store.getGovernanceStatus();

    if (governanceStatus.state === 'FROZEN') {
      debugLogger.warn('❄️ System is frozen. Cannot create new decisions.');
      return;
    }

    // Create governance decision via API instead of direct apply
    try {
      const apiUrl = window.globalConfig ? window.globalConfig.getApiUrl('/execution/governance/propose') : '/execution/governance/propose';
      const activeUser = localStorage.getItem('activeUser') || 'demo';

      // Auto-bypass cooldown in dev environment (localhost + LAN IPs)
      const isDev = isDevEnvironment();

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User': activeUser
        },
        body: JSON.stringify({
          targets: targets, // Already formatted for governance
          reason: `Strategic targets ${mode}: ${proposal.strategy}`,
          force_override_cooldown: isDev // Auto-bypass cooldown in dev
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();

      if (result.success) {
        debugLogger.debug(`✅ Proposition créée avec succès - Plan ID: ${result.plan_id}, Statut: ${result.state}`);

        // Update local store with proposed targets for display
        await applyTargets(proposal);
        window.store.set('targets.governance_mode', governanceStatus.mode);
        window.store.set('targets.strategy', `${proposal.strategy} (DRAFT - pending approval)`);
        window.store.set('targets.pending_plan_id', result.plan_id);
      } else {
        throw new Error(result.message || 'Failed to create proposal');
      }
    } catch (error) {
      debugLogger.error('Failed to create governance proposal:', error);

      // Fallback to local apply if API fails (backward compatibility)
      debugLogger.warn('⚠️ Governance API unavailable, falling back to local targets:', error.message);
      await applyTargets(proposal);
      window.store.set('targets.governance_mode', 'manual');
      window.store.set('targets.strategy', `${proposal.strategy} (local - governance unavailable)`);
    }

    // Refresh targets content to show updated data
    if (window.store.get('ui.activeTab') === 'targets') {
      renderTargetsContent().catch(err => debugLogger.error('Failed to render targets after strategy apply:', err));
    }

    debugLogger.debug(`Applied strategy via governance: ${mode} - ${proposal.strategy}`);
    debugLogger.debug(`Governance mode: ${governanceStatus.mode}, state: ${governanceStatus.state}`);

  } catch (error) {
    debugLogger.error('❌ Failed to apply strategy:', error.message, error);
  }
};
