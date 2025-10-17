// UnifiedInsights - Recommendations Renderer
// Renders intelligent recommendations based on unified state

import { card } from './utils.js';

/**
 * Renders the recommendations block with source attribution
 */
export function renderRecommendationsBlock(recos) {
  return card(`
    <div style="font-weight:700; margin-bottom:.5rem;">💡 Recommandations Intelligentes</div>
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:.5rem;">
      ${recos.length > 0 ? recos.map(r => `
        <div style="padding:.6rem; background: var(--theme-bg); border: 1px solid var(--theme-border); border-radius: var(--radius-sm); border-left: 3px solid ${r.priority==='critical'?'var(--danger)':r.priority==='high'?'var(--danger)':r.priority==='medium'?'var(--warning)':'var(--info)'};">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:.5rem;">
            <div>
              <div style="font-weight:700; display: flex; align-items: center; gap: .5rem;">
                ${r.icon || '💡'} ${r.title}
                ${r.source ? `<span style="background: var(--theme-text-muted); color: white; padding: 1px 4px; border-radius: 3px; font-size: .6rem; opacity: 0.7;">${r.source.split('-')[0]}</span>` : ''}
              </div>
              ${r.subtitle ? `<div style="font-size:.75rem; color: var(--info); margin-top:.25rem; font-style: italic;">${r.subtitle}</div>` : ''}
              <div style="font-size:.85rem; color: var(--theme-text-muted); margin-top:.25rem; white-space: pre-line;">${r.reason}</div>
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
}

/**
 * Renders the contradictions block if any exist
 */
export function renderContradictionsBlock(u) {
  if (!u.contradictions || u.contradictions.length === 0) {
    return '';
  }

  const contradictions = u.contradictions.map(c => {
    const severity = c.severity ? ` (écart: ${Math.round(c.severity)}pts)` : '';
    return `${c.category1?.name || c.category1} vs ${c.category2?.name || c.category2}${severity}`;
  }).join(', ');

  return card(`
    <div style="font-weight:700; color: var(--warning); margin-bottom: .5rem;">⚠️ Divergences Détectées</div>
    <div style="font-size:.85rem; color: var(--theme-text-muted); margin-bottom: .5rem;">${contradictions}</div>
    ${u.contradictions[0]?.recommendation ? `<div style="font-size:.75rem; color: var(--theme-text); padding: .25rem; background: var(--theme-bg); border-radius: var(--radius-sm); border-left: 3px solid var(--warning);">💡 ${u.contradictions[0].recommendation}</div>` : ''}
  `, { accentLeft: 'var(--warning)' });
}
