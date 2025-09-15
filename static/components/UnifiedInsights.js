// UnifiedInsights UI Component - INTELLIGENT VERSION V2
// Displays sophisticated analysis from all modules - MIGRATED TO V2
import { getUnifiedState, deriveRecommendations } from '../core/unified-insights-v2.js';
import { store } from '../core/risk-dashboard-store.js';

// Lightweight fetch helper with timeout
async function fetchJson(url, opts = {}) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), opts.timeout || 8000);
  try {
    const res = await fetch(url, { ...opts, signal: controller.signal });
    clearTimeout(id);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    clearTimeout(id);
    throw e;
  }
}

// Enhanced in-memory cache for current allocation per user/source/taxonomy to avoid frequent API calls
const _allocCache = { ts: 0, data: null, key: null };

// Current allocation by group using taxonomy aliases
async function getCurrentAllocationByGroup(minUsd = 1.0) {
  try {
    const now = Date.now();
    const user = (localStorage.getItem('activeUser') || 'demo');
    const source = (window.globalConfig && window.globalConfig.get?.('data_source')) || 'unknown';

    // Get taxonomy for hash calculation
    let taxonomyHash = 'unknown';
    try {
      const taxo = await window.globalConfig.apiRequest('/taxonomy').catch(() => null);
      taxonomyHash = taxo?.hash || taxo?.version || 'v2';
    } catch { }

    // Enhanced cache key with taxonomy hash and version
    const cacheKey = `${user}:${source}:${taxonomyHash}:v2`;
    if (_allocCache.data && _allocCache.key === cacheKey && (now - _allocCache.ts) < 60000) { // 60s TTL
      return _allocCache.data;
    }
    // Utiliser le seuil global configuré pour rester cohérent avec dashboard
    const cfgMin = (window.globalConfig && window.globalConfig.get?.('min_usd_threshold')) || minUsd || 1.0;
    // Fetch with X-User via globalConfig
    const [taxo, balances] = await Promise.all([
      window.globalConfig.apiRequest('/taxonomy').catch(() => null),
      window.globalConfig.apiRequest('/balances/current', { params: { min_usd: cfgMin } })
    ]);
    // Mapping d'alias: préférer taxonomy, sinon fallback identique au dashboard
    const fallbackAliases = {
      'BTC': 'BTC', 'TBTC': 'BTC', 'WBTC': 'BTC',
      'ETH': 'ETH', 'WETH': 'ETH', 'STETH': 'ETH', 'WSTETH': 'ETH', 'RETH': 'ETH', 'CBETH': 'ETH',
      'USDC': 'Stablecoins', 'USDT': 'Stablecoins', 'USD': 'Stablecoins', 'DAI': 'Stablecoins', 'TUSD': 'Stablecoins', 'FDUSD': 'Stablecoins', 'BUSD': 'Stablecoins',
      'SOL': 'L1/L0 majors', 'SOL2': 'L1/L0 majors', 'ATOM': 'L1/L0 majors', 'ATOM2': 'L1/L0 majors', 'DOT': 'L1/L0 majors', 'DOT2': 'L1/L0 majors', 'ADA': 'L1/L0 majors',
      'AVAX': 'L1/L0 majors', 'NEAR': 'L1/L0 majors', 'LINK': 'L1/L0 majors', 'XRP': 'L1/L0 majors', 'BCH': 'L1/L0 majors', 'XLM': 'L1/L0 majors', 'LTC': 'L1/L0 majors', 'SUI3': 'L1/L0 majors', 'TRX': 'L1/L0 majors',
      'BNB': 'Exchange Tokens', 'BGB': 'Exchange Tokens', 'CHSB': 'Exchange Tokens',
      'AAVE': 'DeFi', 'JUPSOL': 'DeFi', 'JITOSOL': 'DeFi', 'FET': 'DeFi', 'UNI': 'DeFi', 'SUSHI': 'DeFi', 'COMP': 'DeFi', 'MKR': 'DeFi', '1INCH': 'DeFi', 'CRV': 'DeFi',
      'DOGE': 'Memecoins',
      'XMR': 'Privacy',
      'IMO': 'Others', 'VVV3': 'Others', 'TAO6': 'Others', 'OTHERS': 'Others'
    };
    const aliases = (taxo && taxo.aliases) || fallbackAliases;
    const groups = (taxo && taxo.groups) || Array.from(new Set(Object.values(fallbackAliases)));
    const items = (balances && balances.items) || [];
    const mapAlias = (sym) => aliases[(sym || '').toUpperCase()] || null;
    const fallbackGroup = (sym) => {
      const s = (sym || '').toUpperCase();
      if (s === 'BTC' || s === 'WBTC' || s === 'TBTC') return 'BTC';
      if (s === 'ETH' || s === 'WETH') return 'ETH';
      if (s === 'SOL') return 'SOL';
      if (['USDT','USDC','DAI','TUSD','FDUSD','BUSD'].includes(s)) return 'Stablecoins';
      return 'Others';
    };
    const totals = {};
    let grand = 0;
    for (const r of items) {
      const alias = r.alias || r.symbol;
      const g = mapAlias(alias) || fallbackGroup(alias);
      const v = Number(r.value_usd || 0);
      if (v <= 0) continue;
      totals[g] = (totals[g] || 0) + v;
      grand += v;
    }
    // Ensure all groups present for consistency
    groups.forEach(g => { if (!(g in totals)) totals[g] = 0; });
    const pct = {};
    if (grand > 0) {
      Object.entries(totals).forEach(([g, v]) => { pct[g] = (v / grand) * 100; });
    }
    const result = { totals, pct, grand, groups };
    _allocCache.data = result;
    _allocCache.ts = now;
    _allocCache.key = cacheKey;
    return result;
  } catch (e) {
    console.warn('Current allocation fetch failed:', e.message || e);
    return null;
  }
}

function applyCycleMultipliersToTargets(targets, multipliers) {
  try {
    if (!targets || !multipliers) return targets || {};
    const adjusted = {};
    let sum = 0;
    for (const [k, v] of Object.entries(targets)) {
      if (typeof v !== 'number') continue;
      const m = typeof multipliers[k] === 'number' ? multipliers[k] : 1;
      adjusted[k] = Math.max(0, v * m);
      sum += adjusted[k];
    }
    if (sum > 0) {
      Object.keys(adjusted).forEach(k => { adjusted[k] = adjusted[k] * (100 / sum); });
    }
    return adjusted;
  } catch {
    return targets || {};
  }
}

// Color scales
// - Positive scale: high = good (green)
// - Risk scale: high = risky (red)
const colorPositive = (s) => s > 70 ? 'var(--success)' : s >= 40 ? 'var(--warning)' : 'var(--danger)';
const colorRisk = (s) => s > 70 ? 'var(--danger)' : s >= 40 ? 'var(--warning)' : 'var(--success)';

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
        <div style="font-size: .9rem; color: var(--theme-text-muted); font-weight:600;">Decision Index ${u.decision.confidence ? `(${Math.round(u.decision.confidence * 100)}%)` : ''}
          <div style="margin-top: .2rem;">
          ${(() => { try {
            const ml = store.get('governance.ml_signals');
            const ts = ml?.timestamp ? new Date(ml.timestamp) : null;
            const hh = ts ? ts.toLocaleTimeString() : null;
            const ci = ml?.contradiction_index != null ? Math.round(ml.contradiction_index * 100) : null;
            const policy = store.get('governance.active_policy');
            const cap = policy && typeof policy.cap_daily === 'number' ? Math.round(policy.cap_daily * 100) : null;
            const source = u.decision_source || 'SMART';
            const backendStatus = store.get('ui.apiStatus.backend');

            // Phase 1D: Badges parité Analytics/Risk - Format identique
            const badges = [];
            badges.push(source);
            if (hh) badges.push(`Updated ${hh}`);
            if (ci != null) badges.push(`Contrad ${ci}%`);
            if (cap != null) badges.push(`Cap ${cap}%`);

            // Overrides count (simulate for now)
            const overrides = 0; // TODO: Get from governance state
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
            // Standard logic with governance policy consideration
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
        <div>Cycle: ${intelligenceBadge(u.health.intelligence_modules?.cycle || 'unknown')}</div>
        <div>Regime: ${intelligenceBadge(u.health.intelligence_modules?.regime || 'unknown')}</div>
        <div>Signals: ${intelligenceBadge(u.health.intelligence_modules?.signals || 'unknown')}</div>
        <div style="margin-top: .25rem; font-size: .7rem;">Updated: ${u.health.lastUpdate ? new Date(u.health.lastUpdate).toLocaleString() : '—'}</div>
      </div>
    </div>
  `, { accentLeft: colorPositive(u.decision.score) });

  // INTELLIGENT QUADRANT with sophisticated data
  const quad = `
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--space-md);">
      ${card(`
        <div style="font-weight:700; display: flex; align-items: center; gap: .5rem;">🔄 Cycle 
          ${u.cycle.confidence ? `<span style="background: var(--info); color: white; padding: 1px 4px; border-radius: 3px; font-size: .7rem;">${Math.round(u.cycle.confidence * 100)}%</span>` : ''}
        </div>
        <div style="font-size:1.6rem; font-weight:800; color:${colorRisk(u.cycle.score)};">${u.cycle.score || '—'}</div>
        <div style="font-size:.85rem; color: var(--theme-text-muted);">${u.cycle?.phase?.description || u.cycle?.phase?.phase?.replace('_',' ') || '—'}</div>
        <div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">${u.cycle.months ? Math.round(u.cycle.months)+'m post-halving' : '—'}</div>
        ${u.regime?.strategy ? `<div style="font-size:.75rem; color: var(--theme-text); margin-top: .5rem; padding: .25rem; background: var(--theme-bg); border-radius: var(--radius-sm);">💡 ${u.regime.strategy}</div>` : ''}
      `)}
      ${card(`
        <div style="font-weight:700; display:flex; align-items:center; gap:.5rem;">🔗 On-Chain
          ${Number.isFinite(u.onchain.confidence) ? `<span data-tooltip=\"Confiance du module en %\" title=\"Confiance du module en %\" style=\"background: var(--info); color: white; padding: 1px 4px; border-radius: 3px; font-size: .7rem;\">${Math.round((u.onchain.confidence || 0) * 100)}%</span>` : ''}
        </div>
        <div style="font-size:1.6rem; font-weight:800; color:${colorRisk(u.onchain.score ?? 50)};">${u.onchain.score ?? '—'}</div>
        <div style="font-size:.85rem; color: var(--theme-text-muted);">Critiques: ${u.onchain.criticalCount}</div>
        ${u.onchain.drivers && u.onchain.drivers.length ? `<div style="margin-top:.5rem; font-size:.75rem; color: var(--theme-text-muted);">Top Drivers: ${u.onchain.drivers.slice(0,2).map(d => `${d.key} (${d.score})`).join(', ')}</div>` : ''}
        ${u.onchain.drivers && u.onchain.drivers.some(d => d.consensus) ? `<div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">Consensus: ${u.onchain.drivers.filter(d => d.consensus?.consensus).map(d => d.consensus.consensus).join(', ')}</div>` : ''}
      `)}
      ${card(`
        <div style="font-weight:700;">🛡️ Risque & Budget</div>
        <div style="font-size:1.6rem; font-weight:800; color:${colorRisk(u.risk.score ?? 50)};">${u.risk.score ?? '—'}</div>
        <div style="font-size:.85rem; color: var(--theme-text-muted);">VaR95: ${u.risk.var95_1d != null ? (Math.round(Math.abs(u.risk.var95_1d)*1000)/10)+'%' : '—'} • Vol: ${u.risk.volatility != null ? (Math.round(Math.abs(u.risk.volatility)*100)/10)+'%' : '—'}</div>
        ${u.risk.budget ? `<div style="font-size:.75rem; color: var(--theme-text); margin-top: .5rem; padding: .25rem; background: var(--theme-bg); border-radius: var(--radius-sm);">💰 Risky: ${u.risk.budget.percentages?.risky}% • Stables: ${u.risk.budget.percentages?.stables}%</div>` : ''}
        ${u.risk.sharpe != null ? `<div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">Sharpe: ${u.risk.sharpe.toFixed(2)}</div>` : ''}
      `)}
      ${card(`
        <div style="font-weight:700;">🤖 Régime & Sentiment</div>
        <div style="font-size:1.2rem; font-weight:800; display: flex; align-items: center; gap: .5rem;">
          ${u.regime?.emoji || '🤖'} ${u.regime?.name || u.sentiment?.regime || '—'}
          ${u.regime?.confidence ? `<span style="background: var(--info); color: white; padding: 1px 4px; border-radius: 3px; font-size: .7rem;">${Math.round(u.regime.confidence * 100)}%</span>` : ''}
        </div>
        <div style="font-size:.85rem; color: var(--theme-text-muted);">${u.sentiment?.sources && u.sentiment.sources.length > 1 ? `Sentiment (${u.sentiment.sources.length} sources): ${u.sentiment.fearGreed ?? '—'}` : `Fear & Greed: ${u.sentiment?.fearGreed ?? '—'}`} • ${u.sentiment?.interpretation || 'Neutre'}</div>
        ${u.sentiment?.sources && u.sentiment.sources.length > 1 ? `<div style="font-size:.75rem; color: var(--theme-text-muted); margin-top: .25rem;">${u.sentiment.sources.map(s => s.replace('_', ' ')).join(', ')}</div>` : ''}
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
  
  // ALLOCATION INSIGHTS unifiées, infos visibles sans survol
  let allocationBlock = '';
  try {
    // Support both legacy (u.intelligence.allocation) and new Strategy API (u.strategy.targets)
    const allocation = u.intelligence?.allocation ||
                      (u.strategy?.targets ?
                        u.strategy.targets.reduce((acc, target) => {
                          acc[target.symbol] = target.weight * 100; // Convert to percentage
                          return acc;
                        }, {}) : null);

    if (allocation && Object.keys(allocation).length > 0) {
      const conf = u.decision.confidence || 0;
      const contra = (u.contradictions?.length) || 0;
      const governanceStatus = store.getGovernanceStatus();
      
      // Get governance-derived policy
      const governanceState = store.get('governance');
      const activePolicy = governanceState?.active_policy;
      
      // Derive mode and cap from governance or fallback to standard logic
      let mode = { name: 'Observe', cap: 0 };
      
      if (governanceStatus.state === 'FROZEN') {
        mode = { name: 'Frozen', cap: 0 };
      } else if (activePolicy && activePolicy.cap_daily) {
        // Use governance-derived policy
        const cap = Math.round(activePolicy.cap_daily * 100); // Convert to percentage
        const policyMode = activePolicy.mode || 'Normal';
        mode = { 
          name: `${policyMode} (Gov)`, 
          cap: cap
        };
      } else {
        // Fallback to standard logic
        mode = conf > 0.8 && contra === 0 ? { name: 'Deploy', cap: 12 } :
               conf > 0.65 && contra <= 1 ? { name: 'Rotate', cap: 7 } :
               conf > 0.55 ? { name: 'Hedge', cap: 3 } : { name: 'Observe', cap: 0 };
      }

      const current = await getCurrentAllocationByGroup(5.0);
      const targetAdj = applyCycleMultipliersToTargets(allocation, u.cycle?.multipliers || {});

      // Persist suggested allocation for rebalance.html consumption
      try {
        if (targetAdj && Object.keys(targetAdj).length > 0) {
          const payload = {
            targets: targetAdj,
            strategy: 'Regime-Based Allocation',
            timestamp: new Date().toISOString(),
            source: 'analytics-unified'
          };
          localStorage.setItem('unified_suggested_allocation', JSON.stringify(payload));
          window.dispatchEvent(new CustomEvent('unifiedSuggestedAllocationUpdated', { detail: payload }));
        }
      } catch (e) {
        console.warn('Persist unified suggested allocation failed:', e?.message || e);
      }

      const keys = new Set([
        ...Object.keys(targetAdj || {}),
        ...Object.keys((current && current.pct) || {})
      ]);

      const entries = Array.from(keys).map(k => {
        const cur = Number((current?.pct || {})[k] || 0);
        const tgt = Number((targetAdj || {})[k] || 0);
        const delta = Math.round((tgt - cur) * 10) / 10;
        const suggested = Math.round((Math.max(-mode.cap, Math.min(mode.cap, delta))) * 10) / 10;
        return { k, cur, tgt, delta, suggested };
      });

      const visible = entries
        .filter(e => (e.tgt > 0.1) || Math.abs(e.delta) > 0.2)
        .sort((a, b) => (b.tgt - a.tgt))
        .slice(0, 12);

      allocationBlock = card(`
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:.5rem;">
          <div style="font-weight:700;">🎯 Allocation Suggérée</div>
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            ${activePolicy ? `<div style="font-size:.7rem; color: var(--success); background: var(--theme-bg); border:1px solid var(--success); padding:.1rem .4rem; border-radius: 999px;">🏛️ Governance</div>` : ''}
            <div style="font-size:.75rem; color:var(--theme-text-muted); background: var(--theme-bg); border:1px solid var(--theme-border); padding:.2rem .6rem; border-radius: 999px;">
              Mode: <b>${mode.name}</b> (cap ±${mode.cap}%)
            </div>
          </div>
        </div>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:.45rem; font-size:.8rem;">
          ${visible.map(({k, cur, tgt, delta, suggested}) => {
            const moveColor = suggested >= 0 ? 'var(--success)' : 'var(--danger)';
            const sign = (v) => v > 0 ? '+' : '';
            const curW = Math.max(0, Math.min(100, cur));
            const tgtW = Math.max(0, Math.min(100, tgt));
            const grand = Number(current?.grand || 0);
            const curUsd = (cur / 100) * grand;
            const tgtUsd = (tgt / 100) * grand;
            const curUsdStr = `$${Math.round(curUsd).toLocaleString('en-US')}`;
            const tgtUsdStr = `$${Math.round(tgtUsd).toLocaleString('en-US')}`;
            const tip = `Actuel: ${curUsdStr} • Cible: ${tgtUsdStr}`;
            return `
              <div data-tooltip="${tip}" style="padding:.5rem .6rem; background: var(--theme-bg); border-radius: var(--radius-sm); border: 1px solid var(--theme-border);">
                <div style="font-weight: 700; margin-bottom:.25rem;">${k}</div>
                <div style="display:flex; justify-content:space-between; color: var(--theme-text-muted);">
                  <span>Actuel</span><span>${cur.toFixed(1)}%</span>
                </div>
                <div style="height:4px; background: var(--theme-border); border-radius:3px; overflow:hidden;">
                  <div style="width:${curW}%; height:100%; background: color-mix(in oklab, var(--theme-text) 25%, transparent);"></div>
                </div>
                <div style="display:flex; justify-content:space-between; color: var(--theme-text-muted); margin-top:.25rem;">
                  <span>Cible</span><span>${tgt.toFixed(1)}%</span>
                </div>
                <div style="height:4px; background: var(--theme-border); border-radius:3px; overflow:hidden;">
                  <div style="width:${tgtW}%; height:100%; background: var(--brand-primary);"></div>
                </div>
                <div style="margin-top:.35rem; font-size:.75rem; color:${moveColor}; font-weight:600; text-align:right;">Δ ${sign(delta)}${delta}% • ${sign(suggested)}${suggested}%</div>
              </div>
            `;
          }).join('')}
        </div>
        <div style="margin-top:.45rem; font-size:.75rem; color:var(--theme-text-muted);">Tri: Cible décroissant • Cap ±${mode.cap}%</div>
      `, { title: 'Régime-Based Allocation' });
    }
  } catch (e) {
    console.warn('Unified allocation render skipped:', e.message || e);
  }

  // Section des écarts séparée supprimée pour simplifier l'UI
  const deltasBlock = '';

  el.innerHTML = `
    ${header}
    <div style="height: .5rem;"></div>
    ${quad}
    <div style="height: .5rem;"></div>
    ${recBlock}
    <div style="height: .5rem;"></div>
    ${contraBlock}
    ${allocationBlock}
    ${deltasBlock}
    <div style="display:none">${card(`
      <div style="font-weight:700; margin-bottom:.25rem;">🧪 Qualité des données</div>
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr)); gap:.4rem; font-size:.8rem; color:var(--theme-text);">
        <div style="background:var(--theme-bg); padding:.4rem; border-radius:6px;">On-Chain conf: <b>${Math.round((u.onchain.confidence || 0)*100)}%</b></div>
        <div style="background:var(--theme-bg); padding:.4rem; border-radius:6px;">Cycle conf: <b>${Math.round((u.cycle.confidence || 0)*100)}%</b></div>
        <div style="background:var(--theme-bg); padding:.4rem; border-radius:6px;">Regime conf: <b>${Math.round((u.regime.confidence || 0)*100 || 0)}%</b></div>
        <div style="background:var(--theme-bg); padding:.4rem; border-radius:6px;">Contradictions: <b>${u.contradictions?.length || 0}</b></div>
        ${(() => { try { const p = parseFloat(localStorage.getItem('cycle_model_precision') || ''); if (!isNaN(p) && p>0) { return `<div style=\"background:var(--theme-bg); padding:.4rem; border-radius:6px;\">Cycle precision: <b>${Math.round(p*100)}%</b></div>`; } } catch(e){} return ''; })()}
      </div>
    `)}</div>
  `;
  
  console.log('🧠 INTELLIGENT UNIFIED INSIGHTS rendered with:', {
    recommendations: recos.length,
    contradictions: u.contradictions?.length || 0,
    intelligence_active: u.health.intelligence_modules,
    decision_confidence: u.decision.confidence
  });
}

// Cache invalidation helpers
function invalidateAllocationCache() {
  _allocCache.data = null;
  _allocCache.key = null;
  _allocCache.ts = 0;
  console.log('🗑️ Allocation cache invalidated due to source/user/taxonomy change');
}

// Listen for data source and user changes to invalidate cache
if (typeof window !== 'undefined') {
  window.addEventListener('dataSourceChanged', (event) => {
    console.debug(`🔄 Data source change detected: ${event.detail?.oldSource || 'unknown'} → ${event.detail?.newSource || 'unknown'}`);
    invalidateAllocationCache();
  });

  window.addEventListener('activeUserChanged', (event) => {
    console.debug(`👤 Active user change detected: ${event.detail?.oldUser || 'unknown'} → ${event.detail?.newUser || 'unknown'}`);
    invalidateAllocationCache();
  });

  window.addEventListener('storage', (event) => {
    if (event.key === 'activeUser' || event.key?.includes('crypto_rebal_settings')) {
      console.debug('📊 Settings change detected via storage, invalidating cache');
      setTimeout(invalidateAllocationCache, 100); // Small delay to ensure settings are updated
    }
  });
}

export { getCurrentAllocationByGroup, invalidateAllocationCache };
export default { renderUnifiedInsights };

// DEBUG: Log sophisticated data structure for development
if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
  window.debugUnifiedState = getUnifiedState;
  window.debugGetCurrentAllocation = getCurrentAllocationByGroup;
  window.debugInvalidateCache = invalidateAllocationCache;
  console.debug('🔧 Debug: window.debugUnifiedState(), window.debugGetCurrentAllocation() and window.debugInvalidateCache() available for inspection');
}
