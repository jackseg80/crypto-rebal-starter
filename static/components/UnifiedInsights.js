// UnifiedInsights UI Component - INTELLIGENT VERSION
// Displays sophisticated analysis from all modules
import { getUnifiedState, deriveRecommendations } from '../core/unified-insights.js';

const colorForScore = (s) => s > 70 ? 'var(--danger)' : s >= 40 ? 'var(--warning)' : 'var(--success)';

function card(inner, opts = {}) {
  const { accentLeft = null, title = null } = opts;
  return `
    <div class="unified-card" style="background: var(--theme-surface); border: 1px solid var(--theme-border); border-radius: var(--radius-md); padding: var(--space-md); ${accentLeft ? `border-left: 4px solid ${accentLeft};` : ''}">
      ${title ? `<div style="font-weight: 700; margin-bottom: .5rem; font-size: .9rem; color: var(--theme-text-muted);">${title}</div>` : ''}
      ${inner}
    </div>
  `;
}

// Intelligence badge helper
function intelligenceBadge(status) {
  const colors = {
    'active': 'var(--success)',
    'limited': 'var(--warning)', 
    'unknown': 'var(--theme-text-muted)'
  };
  return `<span style="background: ${colors[status] || colors.unknown}; color: white; padding: 1px 4px; border-radius: 3px; font-size: .7rem; font-weight: 600;">${status}</span>`;
}

export async function renderUnifiedInsights(containerId = 'unified-root') {
  const el = document.getElementById(containerId);
  if (!el) return;

  const u = await getUnifiedState();
  const recos = deriveRecommendations(u);

  const header = card(`
    <div style="display:flex; align-items:center; justify-content: space-between; gap:.75rem;">
      <div>
        <div style="font-size: .9rem; color: var(--theme-text-muted); font-weight:600;">Decision Index ${u.decision.confidence ? `(${Math.round(u.decision.confidence * 100)}%)` : ''}</div>
        <div style="font-size: 2rem; font-weight: 800; color:${colorForScore(u.decision.score)};">${u.decision.score}/100</div>
        <div style="font-size: .8rem; color: var(--theme-text-muted);">${u.cycle?.phase?.emoji || ''} ${u.regime?.name || u.cycle?.phase?.phase?.replace('_',' ').toUpperCase() || '—'}</div>
        ${u.decision.reasoning ? `<div style="font-size: .75rem; color: var(--theme-text-muted); margin-top: .25rem; max-width: 300px;">${u.decision.reasoning}</div>` : ''}
      </div>
      <div style="text-align:right; font-size:.8rem; color: var(--theme-text-muted);">
        <div>Backend: ${u.health.backend}</div>
        <div>Signals: ${u.health.signals}</div>
        <div style="margin-top: .25rem;">Intelligence:</div>
        <div>Cycle: ${intelligenceBadge(u.health.intelligence_modules?.cycle || 'unknown')}</div>
        <div>Regime: ${intelligenceBadge(u.health.intelligence_modules?.regime || 'unknown')}</div>
        <div>Signals: ${intelligenceBadge(u.health.intelligence_modules?.signals || 'unknown')}</div>
        <div style="margin-top: .25rem; font-size: .7rem;">Updated: ${u.health.lastUpdate ? new Date(u.health.lastUpdate).toLocaleString() : '—'}</div>
      </div>
    </div>
  `, { accentLeft: colorForScore(u.decision.score) });

  // INTELLIGENT QUADRANT with sophisticated data
  const quad = `
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--space-md);">
      ${card(`
        <div style="font-weight:700; display: flex; align-items: center; gap: .5rem;">🔄 Cycle 
          ${u.cycle.confidence ? `<span style="background: var(--info); color: white; padding: 1px 4px; border-radius: 3px; font-size: .7rem;">${Math.round(u.cycle.confidence * 100)}%</span>` : ''}
        </div>
        <div style="font-size:1.6rem; font-weight:800; color:${colorForScore(u.cycle.score)};">${u.cycle.score || '—'}</div>
        <div style="font-size:.85rem; color: var(--theme-text-muted);">${u.cycle?.phase?.description || u.cycle?.phase?.phase?.replace('_',' ') || '—'}</div>
        <div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">${u.cycle.months ? Math.round(u.cycle.months)+'m post-halving' : '—'}</div>
        ${u.regime?.strategy ? `<div style="font-size:.75rem; color: var(--theme-text); margin-top: .5rem; padding: .25rem; background: var(--theme-bg); border-radius: var(--radius-sm);">💡 ${u.regime.strategy}</div>` : ''}
      `)}
      ${card(`
        <div style="font-weight:700;">🔗 On-Chain</div>
        <div style="font-size:1.6rem; font-weight:800; color:${colorForScore(u.onchain.score ?? 50)};">${u.onchain.score ?? '—'}</div>
        <div style="font-size:.85rem; color: var(--theme-text-muted);">Conf: ${(Math.round((u.onchain.confidence || 0) * 100))}% • Critiques: ${u.onchain.criticalCount}</div>
        ${u.onchain.drivers && u.onchain.drivers.length ? `<div style="margin-top:.5rem; font-size:.75rem; color: var(--theme-text-muted);">Top Drivers: ${u.onchain.drivers.slice(0,2).map(d => `${d.key} (${d.score})`).join(', ')}</div>` : ''}
        ${u.onchain.drivers && u.onchain.drivers.some(d => d.consensus) ? `<div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">Consensus: ${u.onchain.drivers.filter(d => d.consensus?.consensus).map(d => d.consensus.consensus).join(', ')}</div>` : ''}
      `)}
      ${card(`
        <div style="font-weight:700;">🛡️ Risque & Budget</div>
        <div style="font-size:1.6rem; font-weight:800; color:${colorForScore(u.risk.score ?? 50)};">${u.risk.score ?? '—'}</div>
        <div style="font-size:.85rem; color: var(--theme-text-muted);">VaR95: ${u.risk.var95_1d != null ? (Math.round(Math.abs(u.risk.var95_1d)*1000)/10)+'%' : '—'} • Vol: ${u.risk.volatility != null ? (Math.round(Math.abs(u.risk.volatility)*100)/10)+'%' : '—'}</div>
        ${u.risk.budget ? `<div style="font-size:.75rem; color: var(--theme-text); margin-top: .5rem; padding: .25rem; background: var(--theme-bg); border-radius: var(--radius-sm);">💰 Risky: ${u.risk.budget.percentages?.risky}% • Stables: ${u.risk.budget.percentages?.stables}%</div>` : ''}
        ${u.risk.sharpe != null ? `<div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">Sharpe: ${u.risk.sharpe.toFixed(2)}</div>` : ''}
      `)}
      ${card(`
        <div style="font-weight:700;">🤖 Régime & Sentiment</div>
        <div style="font-size:1.2rem; font-weight:800; display: flex; align-items: center; gap: .5rem;">
          ${u.regime?.emoji || '🤖'} ${u.regime?.name || u.sentiment.regime || '—'}
          ${u.regime?.confidence ? `<span style="background: var(--info); color: white; padding: 1px 4px; border-radius: 3px; font-size: .7rem;">${Math.round(u.regime.confidence * 100)}%</span>` : ''}
        </div>
        <div style="font-size:.85rem; color: var(--theme-text-muted);">${u.sentiment.sources && u.sentiment.sources.length > 1 ? `Sentiment (${u.sentiment.sources.length} sources): ${u.sentiment.fearGreed ?? '—'}` : `Fear & Greed: ${u.sentiment.fearGreed ?? '—'}`} • ${u.sentiment.interpretation || 'Neutre'}</div>
        ${u.sentiment.sources && u.sentiment.sources.length > 1 ? `<div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">${u.sentiment.sources.map(s => s.replace('_', ' ')).join(', ')}</div>` : ''}
        ${u.regime?.overrides && u.regime.overrides.length > 0 ? `<div style="font-size:.75rem; color: var(--warning); margin-top: .5rem;">⚡ ${u.regime.overrides.length} override(s) actif(s)</div>` : ''}
      `)}
    </div>
  `;

  // INTELLIGENT RECOMMENDATIONS with source attribution
  const recBlock = card(`
    <div style="font-weight:700; margin-bottom:.5rem;">💡 Recommandations Intelligentes</div>
    <div style="display:grid; gap:.5rem;">
      ${recos.length > 0 ? recos.map(r => `
        <div style="padding:.6rem; background: var(--theme-bg); border: 1px solid var(--theme-border); border-radius: var(--radius-sm); border-left: 3px solid ${r.priority==='critical'?'var(--danger)':r.priority==='high'?'var(--danger)':r.priority==='medium'?'var(--warning)':'var(--info)'};">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:.5rem;">
            <div>
              <div style="font-weight:700; display: flex; align-items: center; gap: .5rem;">
                ${r.icon || '💡'} ${r.title}
                ${r.source ? `<span style="background: var(--theme-text-muted); color: white; padding: 1px 4px; border-radius: 3px; font-size: .6rem; opacity: 0.7;">${r.source.split('-')[0]}</span>` : ''}
              </div>
              <div style="font-size:.85rem; color: var(--theme-text-muted); margin-top:.25rem;">${r.reason}</div>
            </div>
            <div style="font-size:.7rem; padding:2px 6px; border-radius:10px; color:white; background:${r.priority==='critical'?'var(--danger)':r.priority==='high'?'var(--danger)':r.priority==='medium'?'var(--warning)':'var(--info)'}; text-transform:uppercase; font-weight:700; flex-shrink: 0;">${r.priority}</div>
          </div>
        </div>
      `).join('') : `
        <div style="padding:.75rem; background: var(--theme-bg); border: 1px solid var(--theme-border); border-radius: var(--radius-sm); text-align: center; color: var(--theme-text-muted);">
          <div style="font-size: 1.5rem; margin-bottom: .25rem;">🧘</div>
          <div>Aucune recommandation urgente</div>
          <div style="font-size: .8rem; margin-top: .25rem;">Tous les modules sont en accord</div>
        </div>
      `}
    </div>
  `);

  // SOPHISTICATED CONTRADICTIONS AND ANALYSIS
  const contradictions = (u.contradictions || []).map(c => {
    const severity = c.severity ? ` (écart: ${Math.round(c.severity)}pts)` : '';
    return `${c.category1?.name || c.category1} vs ${c.category2?.name || c.category2}${severity}`;
  }).join(', ');
  
  const contraBlock = u.contradictions && u.contradictions.length ? card(`
    <div style="font-weight:700; color: var(--warning); margin-bottom: .5rem;">⚠️ Divergences Détectées</div>
    <div style="font-size:.85rem; color: var(--theme-text-muted); margin-bottom: .5rem;">${contradictions}</div>
    ${u.contradictions[0]?.recommendation ? `<div style="font-size:.75rem; color: var(--theme-text); padding: .25rem; background: var(--theme-bg); border-radius: var(--radius-sm); border-left: 3px solid var(--warning);">💡 ${u.contradictions[0].recommendation}</div>` : ''}
  `, { accentLeft: 'var(--warning)' }) : '';
  
  // ALLOCATION INSIGHTS (if available)
  const allocationBlock = u.intelligence?.allocation && Object.keys(u.intelligence.allocation).length > 0 ? card(`
    <div style="font-weight:700; margin-bottom:.5rem;">🎯 Allocation Suggérée</div>
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap:.25rem; font-size:.8rem;">
      ${Object.entries(u.intelligence.allocation)
        .filter(([key, value]) => typeof value === 'number' && value > 0.1)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 8)
        .map(([asset, pct]) => `
          <div style="padding:.25rem .5rem; background: var(--theme-bg); border-radius: var(--radius-sm); text-align: center;">
            <div style="font-weight: 600;">${asset}</div>
            <div style="color: var(--theme-text-muted);">${pct.toFixed(1)}%</div>
          </div>
        `).join('')}
    </div>
  `, { title: 'Régime-Based Allocation' }) : '';

  el.innerHTML = `
    ${header}
    <div style="height: .5rem;"></div>
    ${quad}
    <div style="height: .5rem;"></div>
    ${recBlock}
    <div style="height: .5rem;"></div>
    ${contraBlock}
    ${allocationBlock}
  `;
  
  console.log('🧠 INTELLIGENT UNIFIED INSIGHTS rendered with:', {
    recommendations: recos.length,
    contradictions: u.contradictions?.length || 0,
    intelligence_active: u.health.intelligence_modules,
    decision_confidence: u.decision.confidence
  });
}

export default { renderUnifiedInsights };

// DEBUG: Log sophisticated data structure for development
if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
  window.debugUnifiedState = getUnifiedState;
  console.debug('🔧 Debug: window.debugUnifiedState() available for inspection');
}

