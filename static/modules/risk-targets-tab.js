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

// ====== Portfolio Allocation Helper ======
/**
 * Get current portfolio allocation by asset groups
 * @returns {Promise<Object>} Allocation object with percentages by group
 */
export async function getCurrentPortfolioAllocation() {
  let realBalances = [];

  try {
    // Utiliser la source de données configurée
    console.log('🔍 Loading portfolio allocation using configured source...');
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
        console.log('🔍 DEBUG getCurrentPortfolioAllocation: Using real CSV data -', realBalances.length, 'assets, total: —');
      } else {
        const val = realBalances.reduce((s, i) => s + i.value_usd, 0) * rate;
        try {
          const dec = (cur === 'BTC') ? 8 : 2;
          console.log('🔍 DEBUG getCurrentPortfolioAllocation: Using real CSV data -', realBalances.length, 'assets, total:', new Intl.NumberFormat('fr-FR', { style: 'currency', currency: cur, minimumFractionDigits: dec, maximumFractionDigits: dec }).format(val));
        } catch (_) {
          console.log('🔍 DEBUG getCurrentPortfolioAllocation: Using real CSV data -', realBalances.length, 'assets, total:', (val).toFixed(cur === 'BTC' ? 8 : 2), cur);
        }
      }
    })();

  } catch (error) {
    console.error('CRITICAL: Could not load CSV data in getCurrentPortfolioAllocation:', error);
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
    console.log('🔄 Blended score not available, recalculating scores...');
    // ✅ Load scores from orchestrator (no need for riskData/ccsData params)
    await window.loadScoresFromStore();
  }

  // Get updated state after potential score calculation
  const updatedState = window.store.snapshot();

  // Propose different targeting strategies (now with updated scores)
  const macroProposal = proposeTargets('macro');
  const ccsProposal = proposeTargets('ccs');
  const cycleProposal = proposeTargets('cycle');
  const blendedProposal = proposeTargets('blend');
  const smartProposal = proposeTargets('smart');

  // DEBUG: Log what blended proposal contains for display
  console.log('🔍 DEBUG renderTargetsContent - updatedState.scores.blended:', updatedState.scores?.blended);
  console.log('🔍 DEBUG renderTargetsContent - blendedProposal for DISPLAY:', blendedProposal);
  console.log('🔍 DEBUG renderTargetsContent - blendedProposal.strategy:', blendedProposal.strategy);
  console.log('🔍 DEBUG renderTargetsContent - BTC allocation for DISPLAY:', blendedProposal.targets.BTC);

  // Current targets from store or use blended as default display
  const appliedTargets = updatedState.targets?.proposed || blendedProposal.targets;
  const appliedStrategy = updatedState.targets?.strategy || blendedProposal.strategy;

  // Get real current portfolio allocation
  const currentAllocation = await getCurrentPortfolioAllocation();

  container.innerHTML = `
    <div class="risk-grid">
      <!-- Strategy Selection -->
      <div class="risk-card" style="grid-column: 1 / -1;">
        <h3>🎯 Strategic Targeting</h3>
        <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--space-sm); margin: var(--space-lg) 0;">
          <button class="refresh-btn" onclick="applyStrategy('macro')" style="background: #6b7280;">
            📊 Macro Only<br>
            <small>${macroProposal.strategy}</small>
          </button>
          <button class="refresh-btn" onclick="applyStrategy('ccs')" style="background: #3b82f6;">
            📈 CCS Based<br>
            <small>${ccsProposal.strategy}</small>
          </button>
          <button class="refresh-btn" onclick="applyStrategy('cycle')" style="background: #f59e0b;">
            🔄 Cycle Adjusted<br>
            <small>${cycleProposal.strategy}</small>
          </button>
          <button class="refresh-btn" onclick="applyStrategy('blend')" style="background: #10b981;">
            ⚖️ Blended Strategy<br>
            <small>${blendedProposal.strategy}</small>
          </button>
          <button class="refresh-btn" onclick="applyStrategy('smart')" style="background: linear-gradient(135deg, #8b5cf6, #06b6d4); color: white; font-weight: bold; border: 2px solid #8b5cf6;">
            🧠 SMART<br>
            <small style="font-size: 0.75rem;">${smartProposal.strategy}</small>
          </button>
        </div>
      </div>

      <!-- Current vs Proposed -->
      <div class="risk-card">
        <h3>📋 Current Allocation</h3>
        ${renderTargetsTable(currentAllocation, 'Portfolio Actuel')}
      </div>

      <div class="risk-card">
        <h3>🎯 Proposed Targets</h3>
        ${renderTargetsTable(appliedTargets, appliedStrategy)}
        ${renderExposureDelta(smartProposal)}
        <div style="margin-top: var(--space-lg); text-align: center; padding: var(--space-sm); background: var(--info-bg); border-radius: var(--radius-md); border: 1px solid var(--info);">
          <div style="font-size: 0.875rem; color: var(--info); font-weight: 600; margin-bottom: var(--space-xs);">
            💡 Nouvelle méthode d'application
          </div>
          <div style="font-size: 0.75rem; color: var(--theme-text-muted);">
            Les targets sont maintenant synchronisés via <strong>rebalance.html</strong><br>
            Utilisez le bouton "🎯 Sync CCS" dans les stratégies prédéfinies
          </div>
        </div>
      </div>
    </div>

    <!-- Action Plan -->
    ${renderActionPlan(currentAllocation, appliedTargets)}

    <!-- Decision History -->
    ${renderDecisionHistory()}
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
 * Render allocation table for a given strategy
 * @param {Object} targets - Allocation targets by group
 * @param {string} strategy - Strategy name
 * @returns {string} HTML for the table
 */
export function renderTargetsTable(targets, strategy) {
  // Robustly handle invalid inputs
  if (!targets || typeof targets !== 'object') {
    console.warn('[renderTargetsTable] Invalid targets:', targets);
    return `<div style="color: var(--warning); font-size: 0.875rem;">⚠️ Invalid allocation data</div>`;
  }

  const { model_version, ...allocations } = targets;

  // Filter and validate allocations with extra safety
  const validEntries = Object.entries(allocations)
    .filter(([key, value]) => {
      const isValid = value != null && typeof value === 'number' && !isNaN(value);
      if (!isValid && value != null) {
        console.warn(`[renderTargetsTable] Filtered invalid allocation: ${key}=${value} (type: ${typeof value})`);
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

  return `
    <div style="font-size: 0.75rem; color: var(--theme-text-muted); margin-bottom: var(--space-sm);">
      ${strategy} (${model_version || 'unknown'})
    </div>
    <div class="risk-grid">
      ${validEntries.map(([asset, allocation]) => `
          <div class="metric-row">
            <span class="metric-label">${asset}:</span>
            <span class="metric-value">${allocation.toFixed(1)}%</span>
          </div>
        `).join('')}
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
    const capText = cap != null ? `${Math.round(cap)}%` : (backendStatus === 'error' ? '5% (fallback)' : 'n/a');

    return `
      <div style="margin-top: .75rem; padding: .6rem; border-radius: 6px; border: 1px solid var(--theme-border); background: var(--theme-bg);">
        <div style="font-size:.85rem; color: var(--theme-text-muted);">
          Cap d'exposition: <b>${capText}</b>
          ${backendStatus === 'error' ? `<span style="margin-left:.5rem; color: var(--warning);">Backend indisponible — mode prudent</span>` : ''}
        </div>
        ${hasOverflow ? `<div style="margin-top:.25rem; font-size:.85rem; color: var(--warning);">Cible risky ${Math.round(base)}% → Cap ${Math.round(fin)}% (<b>−${delta} pts non exécutables</b>)</div>` : ''}
      </div>
    `;
  } catch { return ''; }
}

// ====== Action Plan Renderer ======
/**
 * Render action plan showing differences between current and proposed
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

    return `
      <div class="risk-card">
        <h3>📝 Action Plan</h3>
        <div style="font-size: 0.875rem; color: var(--theme-text-muted); margin-bottom: var(--space-lg);">
          ${plan.num_changes} changes needed • ${plan.total_reallocation.toFixed(1)}% to reallocate • Complexity: ${plan.complexity}
        </div>
        <div class="risk-grid">
          ${plan.actions.map(action => {
            const color = action.action === 'buy' ? 'var(--success)' : 'var(--danger)';
            const icon = action.action === 'buy' ? '🟢' : '🔴';

            return `
              <div class="metric-row">
                <span class="metric-label">${icon} ${action.asset}:</span>
                <span class="metric-value" style="color: ${color};">
                  ${action.action === 'buy' ? '+' : ''}${action.amount.toFixed(1)}% (${action.current.toFixed(1)}% → ${action.target.toFixed(1)}%)
                </span>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    `;
  } catch (error) {
    console.error('Error rendering action plan:', error);
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
      <div class="risk-card">
        <h3>📚 Decision History</h3>
        <p style="text-align: center; color: var(--theme-text-muted);">No previous decisions</p>
      </div>
    `;
  }

  return `
    <div class="risk-card">
      <h3>📚 Decision History</h3>
      <div style="font-size: 0.75rem; color: var(--theme-text-muted); margin-bottom: var(--space-sm);">
        Last ${history.length} decisions
      </div>
      ${history.map(entry => `
        <div class="metric-row" style="border-bottom: 1px solid var(--theme-border); padding: var(--space-sm) 0;">
          <div>
            <div style="font-weight: 500;">${entry.strategy}</div>
            <div style="font-size: 0.75rem; opacity: 0.7;">
              ${new Date(entry.timestamp).toLocaleString()} •
              CCS: ${Math.round(entry.ccs_score || 0)} •
              Confidence: ${Math.round((entry.confidence || 0) * 100)}%
            </div>
          </div>
        </div>
      `).join('')}
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
    console.log('🔍 DEBUG applyStrategy called with mode:', mode);
    console.log('🔍 DEBUG store state before:', window.store.snapshot());

    const proposal = proposeTargets(mode);
    console.log('🔍 DEBUG proposal result:', proposal);
    console.log('🔍 DEBUG proposal BTC allocation:', proposal.targets.BTC);

    // Instead of direct applyTargets, create governance decision
    const currentAllocation = await getCurrentPortfolioAllocation();

    // Convert proposal targets to Target format for governance
    const targets = Object.entries(proposal.targets)
      .filter(([key]) => key !== 'model_version')
      .map(([symbol, target_pct]) => ({
        symbol: symbol,
        alias: symbol,
        current_pct: currentAllocation[symbol] || 0,
        target_pct: target_pct,
        group: symbol // Simplified for now
      }));

    console.log('🔍 Creating governance decision with targets:', targets);

    // Sync governance state first
    await window.store.syncGovernanceState();
    const governanceStatus = window.store.getGovernanceStatus();

    if (governanceStatus.state === 'FROZEN') {
      alert('❄️ System is frozen. Cannot create new decisions.');
      return;
    }

    // For now, still apply locally for backward compatibility
    // TODO: Replace with actual governance decision creation when endpoint is ready
    await applyTargets(proposal);

    // Update governance state to reflect the decision
    window.store.set('targets.governance_mode', governanceStatus.mode);
    window.store.set('targets.strategy', `${proposal.strategy} (via governance)`);

    // Refresh targets content to show updated data
    if (window.store.get('ui.activeTab') === 'targets') {
      renderTargetsContent().catch(err => console.error('Failed to render targets after strategy apply:', err));
    }

    console.log(`Applied strategy via governance: ${mode} - ${proposal.strategy}`);
    console.log(`Governance mode: ${governanceStatus.mode}, state: ${governanceStatus.state}`);

  } catch (error) {
    console.error('Failed to apply strategy:', error);
    alert('Failed to apply strategy: ' + error.message);
  }
};
