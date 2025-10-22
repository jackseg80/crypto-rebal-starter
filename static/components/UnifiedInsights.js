// UnifiedInsights UI Component - REFACTORED V3
// Main orchestrator - delegates to specialized modules
// Reduced from 1365 lines to ~350 lines (74% reduction)

import { getUnifiedState, deriveRecommendations } from '../core/unified-insights-v2.js';
import { store } from '../core/risk-dashboard-store.js';
import {
  colorPositive,
  colorRisk,
  card,
  compactCard,
  intelligenceBadge,
  invalidateAllocationCache,
  resolveCapPercent,
  resolvePolicyCapPercent,
  resolveEngineCapPercent
} from './unified-insights/utils.js';
import { getCurrentAllocationByGroup } from './unified-insights/allocation-calculator.js';
import { renderRecommendationsBlock, renderContradictionsBlock } from './unified-insights/recommendations-renderer.js';
import { renderAllocationBlock } from './unified-insights/execution-plan-renderer.js';
import * as governanceSelectors from '../selectors/governance.js';

/**
 * Renders the main header card with Decision Index and status indicators
 */
function renderHeaderCard(u) {
  return card(`
    <div style="display:flex; align-items:center; justify-content: space-between; gap:.75rem;">
      <div>
        <div style="font-size: .9rem; color: var(--theme-text-muted); font-weight:600;">Decision Index ${u.decision.confidence ? `(${Math.round(u.decision.confidence * 100)}%)` : ''}
          <div style="margin-top: .2rem;">
          ${(() => { try {
            const unifiedState = (typeof store.snapshot === 'function' ? store.snapshot() : null) || window.realDataStore || {};
            const ml = unifiedState?.governance?.ml_signals || store.get('governance.ml_signals');
            const ts = ml?.timestamp ? new Date(ml.timestamp) : null;
            const hh = ts ? ts.toLocaleTimeString() : null;
            const ci = ml?.contradiction_index != null ? Math.round(ml.contradiction_index * 100) : null;
            const policy = unifiedState?.governance?.active_policy || store.get('governance.active_policy');
            const policyCapPercent = resolvePolicyCapPercent(unifiedState, governanceSelectors);
            const engineCapPercent = resolveEngineCapPercent(unifiedState, governanceSelectors);
            const capPercent = resolveCapPercent(unifiedState, governanceSelectors);
            const isTightCap = policy?.mode === 'Freeze' || (policyCapPercent != null && policyCapPercent <= 2);
            const source = u.decision_source || 'SMART';
            const backendStatus = store.get('ui.apiStatus.backend');

            const badges = [];
            badges.push(source);
            if (hh) badges.push(`Updated ${hh}`);
            if (ci != null) badges.push(`Contrad ${ci}%`);
            if (policyCapPercent != null) {
              let capLabel = `Cap ${policyCapPercent}%`;
              if (engineCapPercent != null && engineCapPercent !== policyCapPercent) {
                capLabel += ` • SMART ${engineCapPercent}%`;
              }
              badges.push(capLabel);
            } else if (capPercent != null) {
              badges.push(`Cap ${capPercent}%`);
            } else {
              badges.push('Cap —');
            }
            if (isTightCap) {
              const tightLabel = policyCapPercent != null ? ` (±${policyCapPercent}%)` : '';
              badges.push(`🧊 Freeze/Cap serré${tightLabel}`);
            }

            // Phase Engine status
            const phaseEngineMode = localStorage.getItem('PHASE_ENGINE_ENABLED') || 'shadow';
            if (phaseEngineMode !== 'off') {
              let actualPhase = 'neutral';
              if (typeof window !== 'undefined') {
                if (window._phaseEngineAppliedResult?.phase) {
                  actualPhase = window._phaseEngineAppliedResult.phase;
                } else if (window._phaseEngineShadowResult?.phase) {
                  actualPhase = window._phaseEngineShadowResult.phase;
                }
              }

              badges.push(`Phase: ${actualPhase.replace('_', ' ')}`);
              if (actualPhase !== 'neutral') {
                badges.push(`(${phaseEngineMode})`);
              }
            }

            // Overrides count
            const overrides = window.store?.get('governance.overrides_count') || 0;
            if (overrides > 0) badges.push(`Overrides ${overrides}`);

            // Status indicators
            if (backendStatus === 'stale') badges.push('STALE');
            if (backendStatus === 'error') badges.push('ERROR');

            return badges.join(' • ');
          } catch { return 'Source: SMART'; } })()}
          </div>
        </div>
        <div style="font-size: 2rem; font-weight: 800; color:${colorPositive(u.decision.score)};">${u.decision.score}/100</div>
        <div style="font-size: .8rem; color: var(--theme-text-muted);">${u.cycle?.phase?.emoji || ''} ${u.regime?.name || u.cycle?.phase?.phase?.replace('_',' ').toUpperCase() || '—'}</div>
        ${u.decision.reasoning ? `<div style="font-size: .75rem; color: var(--theme-text-muted); margin-top: .25rem; max-width: 300px;">${u.decision.reasoning}</div>` : ''}
        ${(() => {
          // Action mode derived from confidence, contradictions, and governance
          const governanceStatus = store.getGovernanceStatus();
          const conf = u.decision.confidence || 0;
          const contra = (u.contradictions?.length) || 0;

          let mode = 'Observe';
          let bg = 'var(--theme-text-muted)';

          // Check governance first
          if (governanceStatus.state === 'FROZEN') {
            mode = 'Frozen';
            bg = 'var(--error)';
          } else if (governanceStatus.needsAttention) {
            mode = 'Review';
            bg = 'var(--warning)';
          } else {
            if (conf > 0.8 && contra === 0) {
              mode = governanceStatus.mode === 'full_ai' ? 'Auto-Deploy' : 'Deploy';
              bg = 'var(--success)';
            } else if (conf > 0.65 && contra <= 1) {
              mode = governanceStatus.mode === 'manual' ? 'Approve-Rotate' : 'Rotate';
              bg = 'var(--info)';
            } else if (conf > 0.55) {
              mode = 'Hedge';
              bg = 'var(--warning)';
            }
          }

          return `<div style="margin-top:.35rem;"><span style="background:${bg}; color:white; padding:2px 6px; border-radius:4px; font-size:.7rem; font-weight:700;">Mode: ${mode}</span></div>`;
        })()}
      </div>
      <div style="text-align:right; font-size:.8rem; color: var(--theme-text-muted);">
        <div>Backend: ${u.health.backend}</div>
        <div>Signals: ${u.health.signals}</div>
        ${(() => {
          const governanceStatus = store.getGovernanceStatus();
          const stateColor = governanceStatus.state === 'FROZEN' ? 'var(--error)' :
                           governanceStatus.needsAttention ? 'var(--warning)' :
                           governanceStatus.isActive ? 'var(--success)' : 'var(--theme-text-muted)';
          const contradictionColor = governanceStatus.contradictionLevel > 0.7 ? 'var(--error)' :
                                   governanceStatus.contradictionLevel > 0.5 ? 'var(--warning)' : 'var(--success)';
          return `
            <div style="margin-top: .25rem;">Governance:</div>
            <div style="color: ${stateColor};">${governanceStatus.state} (${governanceStatus.mode})</div>
            <div style="color: ${contradictionColor};">Contradiction: ${(governanceStatus.contradictionLevel * 100).toFixed(1)}%</div>
            ${governanceStatus.pendingCount > 0 ? `<div style="color: var(--warning);">Pending: ${governanceStatus.pendingCount}</div>` : ''}
          `;
        })()}
        <div style="margin-top: .25rem;">Intelligence:</div>
        <div>Cycle: ${intelligenceBadge(u.health.intelligence_modules?.cycle || 'unknown')} <span style="font-size: .65rem; color: var(--theme-text-muted);">(score ${u.cycle?.score || '?'}, conf. ${u.cycle?.confidence ? (u.cycle.confidence * 100).toFixed(0) + '%' : '?'})</span></div>
        <div>Regime: ${intelligenceBadge(u.health.intelligence_modules?.regime || 'unknown')}</div>
        <div>Signals: ${intelligenceBadge(u.health.intelligence_modules?.signals || 'unknown')}</div>
        <div style="margin-top: .25rem; font-size: .7rem;">Updated: ${(() => {
          const canonicalTime = u.risk?.budget?.generated_at;
          const fallbackTime = u.risk_budget?.generated_at || u.strategy?.generated_at || u.health?.lastUpdate;
          const timestamp = canonicalTime || fallbackTime || new Date().toISOString();
          return new Date(timestamp).toLocaleString();
        })()}</div>
      </div>
    </div>
  `, { accentLeft: colorPositive(u.decision.score) });
}

/**
 * Renders the intelligent quadrant with compact cards
 */
function renderQuadrant(u) {
  return `
    <div style="display: flex; flex-direction: column; gap: .5rem;">
      ${compactCard(`
        <div style="font-weight:700; display: flex; align-items: center; gap: .4rem; font-size: .85rem;">🔄 Cycle
          ${u.cycle.confidence ? `<span style="background: var(--info); color: white; padding: 1px 4px; border-radius: 3px; font-size: .65rem;">${Math.round(u.cycle.confidence * 100)}%</span>` : ''}
        </div>
        <div style="font-size:1.5rem; font-weight:800; color:${colorRisk(u.cycle.score)}; line-height: 1.1;">${u.cycle.score || '—'}</div>
        <div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">${u.cycle?.phase?.description || u.cycle?.phase?.phase?.replace('_',' ') || '—'}</div>
        <div style="font-size:.7rem; color: var(--theme-text-muted); margin-top: .15rem;">${u.cycle.months ? Math.round(u.cycle.months)+'m post-halving' : '—'}</div>
      `)}
      ${compactCard(`
        <div style="font-weight:700; display:flex; align-items:center; gap:.4rem; font-size: .85rem;">🔗 On-Chain
          ${Number.isFinite(u.onchain.confidence) ? `<span style="background: var(--info); color: white; padding: 1px 4px; border-radius: 3px; font-size: .65rem;">${Math.round((u.onchain.confidence || 0) * 100)}%</span>` : ''}
        </div>
        <div style="font-size:1.5rem; font-weight:800; color:${colorRisk(u.onchain.score ?? 50)}; line-height: 1.1;">${u.onchain.score ?? '—'}</div>
        <div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">Critiques: ${u.onchain.criticalCount}</div>
        ${u.onchain.drivers && u.onchain.drivers.length ? `<div style="margin-top:.2rem; font-size:.7rem; color: var(--theme-text-muted);">Top: ${u.onchain.drivers.slice(0,1).map(d => `${d.key} (${d.score})`).join(', ')}</div>` : ''}
      `)}
      ${compactCard(`
        <div style="font-weight:700; font-size: .85rem;">🛡️ Risque & Budget</div>
        <div style="font-size:1.5rem; font-weight:800; color:${colorRisk(u.risk.score ?? 50)}; line-height: 1.1;">${u.risk.score ?? '—'}</div>
        <div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">VaR95: ${u.risk.var95_1d != null ? (Math.round(Math.abs(u.risk.var95_1d)*1000)/10)+'%' : '—'}</div>
        ${u.risk.budget ? `<div style="font-size:.7rem; color: var(--theme-text); margin-top: .25rem; padding: .2rem; background: var(--theme-bg); border-radius: var(--radius-sm);">Risky: ${u.risk.budget.percentages?.risky}% • Stables: ${u.risk.budget.percentages?.stables}%</div>` : ''}
      `)}
      ${compactCard(`
        <div style="font-weight:700; font-size: .85rem;">🤖 Régime & Sentiment</div>
        <div style="font-size:1.1rem; font-weight:800; display: flex; align-items: center; gap: .4rem; line-height: 1.1;">
          ${u.regime?.emoji || '🤖'} ${u.regime?.name || u.sentiment?.regime || '—'}
          ${u.regime?.confidence ? `<span style="background: var(--info); color: white; padding: 1px 4px; border-radius: 3px; font-size: .65rem;">${Math.round(u.regime.confidence * 100)}%</span>` : ''}
        </div>
        <div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">F&G: ${u.sentiment?.fearGreed ?? '—'}</div>
        <div style="font-size:.7rem; color: var(--theme-text-muted); margin-top: .15rem;">${u.sentiment?.interpretation || 'Neutre'}</div>
      `)}
    </div>
  `;
}

/**
 * Main render function - orchestrates all components
 */
export async function renderUnifiedInsights(containerId = 'unified-root', options = {}) {
  const el = document.getElementById(containerId);
  if (!el) return;

  console.debug('🚀 REFACTORED V3 - renderUnifiedInsights appelée', {
    containerId,
    timestamp: new Date().toISOString(),
    call_count: (window._renderCallCount = (window._renderCallCount || 0) + 1)
  });

  const u = await getUnifiedState();
  const recos = deriveRecommendations(u);

  console.debug('🔍 Unified state loaded:', {
    has_risk_scores: !!u?.risk_scores,
    blended_score: u?.risk_scores?.blended || u?.blended_score,
    recos_count: recos?.length || 0
  });

  // Render components
  const header = options.hideHeader ? '' : renderHeaderCard(u);
  const quad = renderQuadrant(u);
  const recBlock = renderRecommendationsBlock(recos);
  const contraBlock = renderContradictionsBlock(u);
  const allocationBlock = await renderAllocationBlock(u, options);

  el.innerHTML = `
    ${recBlock}
    <div style="height: .5rem;"></div>
    ${contraBlock}
    ${allocationBlock}
  `;

  console.debug('🧠 INTELLIGENT UNIFIED INSIGHTS rendered:', {
    recommendations: recos.length,
    contradictions: u.contradictions?.length || 0,
    intelligence_active: u.health.intelligence_modules,
    decision_confidence: u.decision.confidence
  });
}

// Event listeners for cache invalidation
if (typeof window !== 'undefined') {
  window.addEventListener('dataSourceChanged', (event) => {
    console.debug(`🔄 Data source change: ${event.detail?.oldSource || 'unknown'} → ${event.detail?.newSource || 'unknown'}`);
    invalidateAllocationCache();
  });

  window.addEventListener('activeUserChanged', (event) => {
    console.debug(`👤 User change: ${event.detail?.oldUser || 'unknown'} → ${event.detail?.newUser || 'unknown'}`);
    invalidateAllocationCache();

    if (typeof window.debugInvalidateRiskBudget === 'function') {
      window.debugInvalidateRiskBudget();
    }

    setTimeout(() => {
      window.dispatchEvent(new CustomEvent('riskBudgetInvalidated', {
        detail: { reason: 'user_change', newUser: event.detail?.newUser }
      }));
    }, 200);
  });

  window.addEventListener('riskBudgetInvalidated', (event) => {
    console.debug(`💰 Risk budget invalidated: ${event.detail?.reason || 'unknown'}, re-rendering`);

    setTimeout(async () => {
      try {
        const container = document.querySelector('[data-unified-insights]');
        if (container && typeof window.renderUnifiedInsights === 'function') {
          await window.renderUnifiedInsights();
        }
      } catch (e) {
        console.warn('UnifiedInsights re-render failed:', e.message);
      }
    }, 100);
  });

  window.addEventListener('storage', (event) => {
    if (event.key === 'activeUser') {
      const userChangeEvent = new CustomEvent('activeUserChanged', {
        detail: { oldUser: event.oldValue, newUser: event.newValue }
      });
      window.dispatchEvent(userChangeEvent);
      setTimeout(invalidateAllocationCache, 50);
    } else if (event.key?.includes('crypto_rebal_settings')) {
      setTimeout(invalidateAllocationCache, 100);
    }
  });
}

// Exports
export { getCurrentAllocationByGroup, invalidateAllocationCache };
export default { renderUnifiedInsights };

// Debug helpers
if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
  window.debugUnifiedState = getUnifiedState;
  window.debugGetCurrentAllocation = getCurrentAllocationByGroup;
  window.debugInvalidateCache = invalidateAllocationCache;
  console.debug('🔧 Debug helpers available: debugUnifiedState(), debugGetCurrentAllocation(), debugInvalidateCache()');
}
