// UnifiedInsights UI Component - INTELLIGENT VERSION V2
// Displays sophisticated analysis from all modules - MIGRATED TO V2
import { getUnifiedState, deriveRecommendations } from '../core/unified-insights-v2.js';
import { store } from '../core/risk-dashboard-store.js';
import * as governanceSelectors from '../selectors/governance.js';
import { KNOWN_ASSET_MAPPING, getAssetGroup, GROUP_ORDER, getAllGroups, getAliasMapping } from '../shared-asset-groups.js';

// Governance selectors can desync across deployments; use resilient fallbacks.
const {
  selectCapPercent: rawSelectCapPercent,
  selectPolicyCapPercent: rawSelectPolicyCapPercent,
  selectEngineCapPercent: rawSelectEngineCapPercent,
} = governanceSelectors;

function resolveCapPercent(state) {
  try {
    if (typeof rawSelectCapPercent === "function") {
      const cap = rawSelectCapPercent(state);
      if (cap != null) return cap;
    }
    if (typeof rawSelectPolicyCapPercent === "function") {
      const policy = rawSelectPolicyCapPercent(state);
      if (policy != null) return policy;
    }
    if (typeof rawSelectEngineCapPercent === "function") {
      return rawSelectEngineCapPercent(state);
    }
  } catch (error) {
    console.debug('resolveCapPercent fallback failed', error);
  }
  return null;
}

function resolvePolicyCapPercent(state) {
  try {
    if (typeof rawSelectPolicyCapPercent === "function") {
      const policy = rawSelectPolicyCapPercent(state);
      if (policy != null) return policy;
    }
  } catch (error) {
    console.debug('resolvePolicyCapPercent primary failed', error);
  }
  return resolveCapPercent(state);
}

function resolveEngineCapPercent(state) {
  try {
    if (typeof rawSelectEngineCapPercent === "function") {
      const engine = rawSelectEngineCapPercent(state);
      if (engine != null) return engine;
    }
  } catch (error) {
    console.debug('resolveEngineCapPercent primary failed', error);
  }
  return resolveCapPercent(state);
}

// buildTheoreticalTargets removed - using u.targets_by_group (dynamic computation)

/**
 * Normalise les alias crypto (SOL2→SOL, UNI2→UNI, etc.) via taxonomy
 */
function normalizeAlias(symbol) {
  if (!symbol) return symbol;

  const upperSymbol = symbol.toUpperCase();

  // Utiliser la map d'aliases si disponible
  if (KNOWN_ASSET_MAPPING && KNOWN_ASSET_MAPPING[upperSymbol]) {
    const group = KNOWN_ASSET_MAPPING[upperSymbol];
    // Si l'alias mappe vers un groupe qui a le même nom qu'un coin, retourner le coin
    if (['BTC', 'ETH', 'SOL'].includes(group)) {
      return group;
    }
  }

  // Fallback: suppression suffixes numériques courants (SOL2→SOL, UNI2→UNI)
  const normalized = upperSymbol.replace(/[2-9]+$/, '');

  console.debug(`🔄 Normalize alias: ${symbol} → ${normalized}`);
  return normalized;
}

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

/**
 * Calcule les mouvements avec contrainte cap ±X% et somme nulle
 * Algorithme : prioriser les mouvements les plus urgents sans dépasser le cap global
 */
function calculateZeroSumCappedMoves(entries, cap) {
  // Clone entries to avoid mutation
  const result = entries.map(entry => ({...entry, suggested: 0}));

  console.debug('🔄 CORRECT LOGIC: Applying individual cap ±' + cap + '% to each asset independently');

  // Phase 1: Appliquer le cap individuellement à chaque asset
  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    const requestedMove = entry.delta;

    // Appliquer le cap INDIVIDUELLEMENT (pas de budget global)
    if (requestedMove > cap) {
      result[i].suggested = cap; // Limité à +cap%
    } else if (requestedMove < -cap) {
      result[i].suggested = -cap; // Limité à -cap%
    } else {
      result[i].suggested = requestedMove; // Mouvement complet si dans la limite
    }

    result[i].suggested = Math.round(result[i].suggested * 10) / 10;
  }

  console.debug('🔄 Individual moves after cap:', result.map(r =>
    `${r.k}: requested=${r.delta.toFixed(1)}%, capped=${r.suggested.toFixed(1)}%`
  ));

  // Phase 2: Vérifier contrainte zéro-somme et ajuster proportionnellement
  const totalSuggested = result.reduce((sum, entry) => sum + entry.suggested, 0);

  console.debug('🔄 Zero-sum check:', {
    total_suggested: totalSuggested.toFixed(1) + '%',
    needs_adjustment: Math.abs(totalSuggested) > 0.1
  });

  if (Math.abs(totalSuggested) > 0.1) {
    // Ajustement zéro-somme INTELLIGENT qui respecte les caps individuels
    let remaining = totalSuggested;
    const maxIterations = 5;
    let iteration = 0;

    console.debug('🔄 Zero-sum adjustment needed:', {
      excess: totalSuggested.toFixed(1) + '%',
      starting_adjustment: 'intelligent cap-respecting'
    });

    while (Math.abs(remaining) > 0.1 && iteration < maxIterations) {
      iteration++;
      const adjustableEntries = result.filter(r => {
        const currentSuggested = r.suggested;
        const delta = r.delta;

        // Peut-on ajuster cette entrée sans violer le cap ?
        if (remaining > 0) {
          // Besoin de réduire les mouvements positifs ou augmenter les négatifs
          return (currentSuggested > -cap) && (currentSuggested > delta - cap);
        } else {
          // Besoin d'augmenter les mouvements positifs ou réduire les négatifs
          return (currentSuggested < cap) && (currentSuggested < delta + cap);
        }
      });

      if (adjustableEntries.length === 0) {
        (window.debugLogger?.warn || console.warn)('🔄 Cannot achieve zero-sum without violating caps');
        break;
      }

      const adjustment = -remaining / adjustableEntries.length;

      adjustableEntries.forEach(entry => {
        const newValue = entry.suggested + adjustment;
        // Appliquer l'ajustement en respectant les caps
        entry.suggested = Math.max(-cap, Math.min(cap, newValue));
        entry.suggested = Math.round(entry.suggested * 10) / 10;
      });

      remaining = result.reduce((sum, entry) => sum + entry.suggested, 0);
    }

    console.debug('🔄 Zero-sum adjustment completed:', {
      iterations: iteration,
      final_total: remaining.toFixed(1) + '%',
      converged: Math.abs(remaining) <= 0.1,
      final_moves: result.map(r => `${r.k}: ${r.suggested.toFixed(1)}%`)
    });
  }

  return result;
}

// Enhanced in-memory cache for current allocation per user/source/taxonomy to avoid frequent API calls
const _allocCache = { ts: 0, data: null, key: null };

// CACHE BUST: getCurrentAllocationByGroup - 2025-09-29T21:32:30Z
// Current allocation by group using taxonomy aliases
async function getCurrentAllocationByGroup(minUsd = 1.0) {
  try {
    (window.debugLogger?.debug || console.log)('🏦 ENTRY: getCurrentAllocationByGroup called - CACHE_BUST_2025-09-29T21:32:30Z', {
      minUsd,
      timestamp: new Date().toISOString(),
      caller: 'UnifiedInsights.js',
      version: 'store_fallback_with_retry'
    });
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
    // IMPORTANT: Ne pas utiliser le cache si grand = 0 (données invalides)
    if (_allocCache.data && _allocCache.key === cacheKey && (now - _allocCache.ts) < 60000 && _allocCache.data.grand > 0) { // 60s TTL + validation
      (window.debugLogger?.info || console.log)('✅ CACHE HIT: Using valid cached allocation data', {
        grand: _allocCache.data.grand,
        groups: Object.keys(_allocCache.data.totals).length,
        age: Math.round((now - _allocCache.ts) / 1000) + 's'
      });
      return _allocCache.data;
    } else if (_allocCache.data && _allocCache.key === cacheKey && (now - _allocCache.ts) < 60000) {
      (window.debugLogger?.warn || console.warn)('🚨 CACHE INVALID: Cached data has grand=0, forcing refresh', {
        grand: _allocCache.data.grand,
        age: Math.round((now - _allocCache.ts) / 1000) + 's'
      });
    }
    // PRIORITÉ: Utiliser les données du store d'abord (déjà injectées par les patches analytics-unified.html)
    let items = null;
    let grand = 0;
    let useStoreData = false;

    // DEBUG: Vérifier l'état du store
    (window.debugLogger?.debug || console.log)('🔍 STORE DEBUG getCurrentAllocationByGroup:', {
      storeExists: !!window.store,
      storeGetFunction: !!(window.store && typeof window.store.get === 'function'),
      storeBalances: window.store ? window.store.get('wallet.balances') : 'no store',
      storeTotal: window.store ? window.store.get('wallet.total') : 'no store',
      timestamp: new Date().toISOString()
    });

    // RETRY LOGIC: Attendre que les données soient injectées par analytics-unified.html
    const waitForStoreData = async (maxRetries = 3, delayMs = 500) => {
      for (let i = 0; i < maxRetries; i++) {
        if (window.store && typeof window.store.get === 'function') {
          const storeBalances = window.store.get('wallet.balances');
          const storeTotal = window.store.get('wallet.total');

          if (storeBalances && storeBalances.length > 0 && storeTotal > 0) {
            (window.debugLogger?.debug || console.log)(`✅ STORE RETRY SUCCESS (attempt ${i + 1}/${maxRetries}):`, {
              items: storeBalances.length,
              total: storeTotal,
              delay: i * delayMs + 'ms'
            });
            return { balances: storeBalances, total: storeTotal };
          }
        }

        if (i < maxRetries - 1) {
          (window.debugLogger?.debug || console.log)(`⏳ STORE RETRY ${i + 1}/${maxRetries}: Waiting ${delayMs}ms for data injection...`);
          await new Promise(resolve => setTimeout(resolve, delayMs));
        }
      }
      return null;
    };

    try {
      // Première tentative immédiate
      if (window.store && typeof window.store.get === 'function') {
        const storeBalances = window.store.get('wallet.balances');
        const storeTotal = window.store.get('wallet.total');

        (window.debugLogger?.debug || console.log)('🔍 STORE DATA CHECK (immediate):', {
          balances: storeBalances ? `${storeBalances.length} items` : 'null/undefined',
          total: storeTotal,
          firstBalance: storeBalances ? storeBalances[0] : 'no data'
        });

        if (storeBalances && storeBalances.length > 0 && storeTotal > 0) {
          items = storeBalances;
          grand = storeTotal;
          useStoreData = true;
          (window.debugLogger?.info || console.log)('✅ STORE IMMEDIATE: Using data from store', {
            items: items.length,
            total: grand,
            source: 'store_immediate'
          });
        } else {
          (window.debugLogger?.debug || console.log)('⏳ STORE INCOMPLETE: Trying retry logic...');
          // Si pas de données, essayer le retry pattern
          const retryResult = await waitForStoreData();
          if (retryResult) {
            items = retryResult.balances;
            grand = retryResult.total;
            useStoreData = true;
          } else {
            (window.debugLogger?.warn || console.warn)('🚨 STORE RETRY FAILED: No data after retries');
          }
        }
      } else {
        (window.debugLogger?.warn || console.warn)('🚨 STORE NOT AVAILABLE:', {
          storeExists: !!window.store,
          hasGetMethod: window.store ? typeof window.store.get === 'function' : false
        });
      }
    } catch (e) {
      (window.debugLogger?.warn || console.warn)('Store data access failed:', e.message);
    }

    // Si pas de données store, essayer l'API (peut échouer avec 429)
    if (!useStoreData) {
      try {
        // Utiliser le seuil global configuré pour rester cohérent avec dashboard
        const cfgMin = (window.globalConfig && window.globalConfig.get?.('min_usd_threshold')) || minUsd || 1.0;
        // Fetch with X-User via globalConfig
        const [taxo, balances] = await Promise.all([
          window.globalConfig.apiRequest('/taxonomy').catch(() => null),
          window.globalConfig.apiRequest('/balances/current', { params: { min_usd: cfgMin } })
        ]);
        items = (balances && balances.items) || [];
        (window.debugLogger?.info || console.log)('✅ API SUCCESS: Using fresh API data', {
          items: items.length,
          source: 'api_direct'
        });
      } catch (apiError) {
        (window.debugLogger?.warn || console.warn)('🚨 API FAILED (probably 429):', apiError.message);

        // Dernier recours: essayer d'utiliser loadBalanceData si disponible
        if (typeof window.loadBalanceData === 'function') {
          try {
            const balanceResult = await window.loadBalanceData();
            if (balanceResult.success && balanceResult.data?.items) {
              items = balanceResult.data.items;
              grand = items.reduce((sum, item) => sum + (parseFloat(item.value_usd) || 0), 0);
              useStoreData = true;
              (window.debugLogger?.info || console.log)('✅ LOADBALANCEDATA FALLBACK: Using cached balance data', {
                items: items.length,
                total: grand,
                source: 'loadBalanceData_cache'
              });
            }
          } catch (e) {
            (window.debugLogger?.warn || console.warn)('loadBalanceData fallback failed:', e.message);
          }
        }

        if (!items) {
          throw new Error('All data sources failed: API, store, and loadBalanceData');
        }
      }
    }

    // Utiliser le système unifié de classification (même logique que dashboard)
    // Priorité: shared-asset-groups -> fallback
    let groups = [];
    try {
      groups = await getAllGroups();
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('⚠️ Failed to get groups from shared-asset-groups, using fallback');
      groups = ['BTC', 'ETH', 'Stablecoins', 'SOL', 'L1/L0 majors', 'L2/Scaling', 'DeFi', 'AI/Data', 'Gaming/NFT', 'Memecoins', 'Others'];
    }

    const totals = {};
    if (!useStoreData) {
      grand = 0; // Recalculer si pas depuis store
    }
    for (const r of items) {
      // Utiliser uniquement le symbol pour la classification (plus simple et cohérent)
      const symbol = r.symbol;
      const g = getAssetGroup(symbol);
      const v = Number(r.value_usd || 0);
      if (v <= 0) continue;
      totals[g] = (totals[g] || 0) + v;
      if (!useStoreData) {
        grand += v;
      }
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

    // DEBUG: Log current allocation result
    console.debug('🏦 CURRENT ALLOCATION RESULT (with store fallback):', {
      pct_keys: Object.keys(pct),
      pct_values: pct,
      pct_total: Object.values(pct).reduce((a, b) => a + b, 0),
      grand_total_usd: grand,
      groups_count: groups.length,
      data_source: useStoreData ? 'store/cache' : 'api'
    });

    return result;
  } catch (e) {
    (window.debugLogger?.warn || console.warn)('Current allocation fetch failed:', e.message || e);
    return null;
  }
}

function applyCycleMultipliersToTargets(targets, multipliers) {
  try {
    if (!targets) return {};
    const STABLE = 'Stablecoins';
    const stables = Number(targets[STABLE] ?? 0);

    // 1) Appliquer les multiplicateurs uniquement sur les non-stables
    const nonStableKeys = Object.keys(targets).filter(k => k !== STABLE);
    const out = {};
    let nonStableSum = 0;

    for (const k of nonStableKeys) {
      const v = Number(targets[k] ?? 0);
      const m = (multipliers && typeof multipliers[k] === 'number') ? multipliers[k] : 1;
      out[k] = Math.max(0, v * m);
      nonStableSum += out[k];
    }

    // 2) Renormaliser UNIQUEMENT les non-stables sur (100 - stables)
    const space = Math.max(0, 100 - stables);
    if (nonStableSum > 0 && space > 0) {
      const scale = space / nonStableSum;
      for (const k of nonStableKeys) out[k] *= scale;
    } else {
      // pas de non-stables → tout en stables (déjà fixé)
      for (const k of nonStableKeys) out[k] = 0;
    }

    // 3) Réinjecter les stables tels quels
    out[STABLE] = stables;

    // 4) Correction d'arrondi douce (ramener la somme à 100%)
    const total = Object.values(out).reduce((a, b) => a + (isFinite(b) ? b : 0), 0);
    const diff = 100 - total;
    if (Math.abs(diff) > 0.1) {
      // pousser le delta vers BTC si présent, sinon vers la plus grosse clé non-stable
      const candidates = nonStableKeys.sort((a, b) => (out[b] || 0) - (out[a] || 0));
      const key = out.BTC != null ? 'BTC' : (candidates[0] || STABLE);
      out[key] = (out[key] || 0) + diff;
    }

    console.debug(`✅ Cycle multipliers applied: stables preserved at ${stables.toFixed(1)}%, non-stables in ${space.toFixed(1)}% space`);
    return out;
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

  console.debug('🚀 VERSION 16:26 - RENDER DEBUG: renderUnifiedInsights appelée', {
    containerId,
    timestamp: new Date().toISOString(),
    call_count: (window._renderCallCount = (window._renderCallCount || 0) + 1)
  });

  const u = await getUnifiedState();

  console.debug('🔍 getUnifiedState returned:', {
    has_risk_scores: !!u?.risk_scores,
    blended_score: u?.risk_scores?.blended || u?.blended_score,
    data_keys: Object.keys(u || {})
  });
  const recos = deriveRecommendations(u);
  console.debug('🔍 RECOMMENDATIONS DEBUG:', {
    recosCount: recos?.length || 0,
    recos: recos,
    firstReco: recos?.[0],
    allPriorities: recos?.map(r => r.priority) || []
  });

  const header = card(`
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
            const policyCapPercent = resolvePolicyCapPercent(unifiedState);
            const engineCapPercent = resolveEngineCapPercent(unifiedState);
            const capPercent = resolveCapPercent(unifiedState);
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

            // NOUVEAU: Phase Engine status
            const phaseEngineMode = localStorage.getItem('PHASE_ENGINE_ENABLED') || 'shadow';
            if (phaseEngineMode !== 'off') {
              // Show actual detected phase if available
              let actualPhase = 'neutral';
              if (typeof window !== 'undefined') {
                if (window._phaseEngineAppliedResult?.phase) {
                  actualPhase = window._phaseEngineAppliedResult.phase;
                } else if (window._phaseEngineShadowResult?.phase) {
                  actualPhase = window._phaseEngineShadowResult.phase;
                }
              }

              badges.push(`Phase: ${actualPhase.replace('_', ' ')}`);

              // Add mode indicator if not neutral
              if (actualPhase !== 'neutral') {
                badges.push(`(${phaseEngineMode})`);
              }
            }

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
        <div>Cycle: ${intelligenceBadge(u.health.intelligence_modules?.cycle || 'unknown')} <span style="font-size: .65rem; color: var(--theme-text-muted);">(score ${u.cycle?.score || '?'}, conf. ${u.cycle?.confidence ? (u.cycle.confidence * 100).toFixed(0) + '%' : '?'})</span></div>
        <div>Regime: ${intelligenceBadge(u.health.intelligence_modules?.regime || 'unknown')}</div>
        <div>Signals: ${intelligenceBadge(u.health.intelligence_modules?.signals || 'unknown')}</div>
        <div style="margin-top: .25rem; font-size: .7rem;">Updated: ${(() => {
          // SOURCE CANONIQUE UNIQUE: Utiliser risk.budget.generated_at en priorité
          const canonicalTime = u.risk?.budget?.generated_at;
          const fallbackTime = u.risk_budget?.generated_at || u.strategy?.generated_at || u.health?.lastUpdate;
          console.debug('🕐 timestamp debug:', { canonicalTime, fallbackTime });
          const timestamp = canonicalTime || fallbackTime || new Date().toISOString();
          return new Date(timestamp).toLocaleString();
        })()}</div>
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
    // SOURCE CANONIQUE UNIQUE: Utiliser targets_by_group (même source que plan d'exécution)
    (window.debugLogger?.warn || console.warn)('🔥 UNIFIED SOURCE: Using u.targets_by_group as canonical source');
    let allocation = u.targets_by_group;
    (window.debugLogger?.warn || console.warn)('🔥 UNIFIED SOURCE: targets_by_group result:', allocation);

    // PATCH C - Moteur unique : utiliser groupAssetsByClassification comme Rebalance (DÉSACTIVÉ pour test)
    let allocation_backup = null;
    try {
      // FORCE: Utiliser toutes les sources possibles pour récupérer les balances
      let balanceData = store.snapshot()?.wallet?.balances || [];

      // Fallback vers les clés store directes si snapshot échoue
      if (balanceData.length === 0) {
        balanceData = store.get('wallet.balances') || [];
        console.debug('🔧 PATCH C: Using direct store access for balances');
      }

      // Dernier recours : attendre que l'injection soit finie et réessayer
      if (balanceData.length === 0) {
        await new Promise(resolve => setTimeout(resolve, 100)); // 100ms
        balanceData = store.snapshot()?.wallet?.balances || store.get('wallet.balances') || [];
        console.debug('🔧 PATCH C: Retry after 100ms delay');
      }

      console.debug('🔧 PATCH C starting with balances:', balanceData.length, 'items', {
        from_snapshot: store.snapshot()?.wallet?.balances?.length || 0,
        from_direct: store.get('wallet.balances')?.length || 0,
        final_used: balanceData.length
      });

      if (balanceData.length > 0) {
        const { groupAssetsByClassification } = await import('../shared-asset-groups.js');
        const groupedData = groupAssetsByClassification(balanceData);
        const totalValue = groupedData.reduce((sum, g) => sum + g.value, 0);

        if (totalValue > 0) {
          // Convertir au format attendu par l'UI (% par groupe)
          allocation = {};
          GROUP_ORDER.forEach(group => {
            const found = groupedData.find(g => g.label === group);
            allocation[group] = found ? (found.value / totalValue) * 100 : 0;
          });

          console.debug('🔧 PATCH C SUCCESS: Analytics utilise maintenant groupAssetsByClassification comme Rebalance:', {
            groups: Object.entries(allocation).map(([k,v]) => `${k}: ${v.toFixed(1)}%`),
            othersCheck: allocation['Others']?.toFixed(1) + '%',
            source: 'groupAssetsByClassification',
            totalValue
          });
        } else {
          (window.debugLogger?.warn || console.warn)('🔧 PATCH C: totalValue is 0, skipping allocation');
        }
      } else {
        (window.debugLogger?.warn || console.warn)('🔧 PATCH C: No balance data available');
      }
    } catch (e) {
      console.error('🔧 PATCH C failed with error:', e.message, e.stack);
    }

    // Fallback vers u.targets_by_group si patch échoue (plus de presets hardcodés)
    if (!allocation || Object.keys(allocation).length === 0) {
      (window.debugLogger?.warn || console.warn)('🚨 PATCH C FAILED - Using dynamic targets_by_group as fallback');

      // Fallback ultime : utiliser les positions actuelles normalisées
      allocation = {};
      GROUP_ORDER.forEach(group => allocation[group] = 0);

      // Utiliser la même logique que PATCH C pour fallback
      try {
        const balanceData = store.snapshot()?.wallet?.balances || [];
        if (balanceData.length > 0) {
          const { groupAssetsByClassification } = await import('../shared-asset-groups.js');
          const groupedData = groupAssetsByClassification(balanceData);
          const totalValue = groupedData.reduce((sum, g) => sum + g.value, 0);

          if (totalValue > 0) {
            GROUP_ORDER.forEach(group => {
              const found = groupedData.find(g => g.label === group);
              allocation[group] = found ? (found.value / totalValue) * 100 : 0;
            });
            console.debug('✅ FALLBACK: Using groupAssetsByClassification as allocation targets');
          }
        }
      } catch (e) {
        console.error('Fallback also failed:', e.message);
      }

      // Dernier recours: utiliser targets_by_group (dynamique)
      if (!allocation || Object.values(allocation).every(v => v === 0)) {
        allocation = u.targets_by_group || {};
        (window.debugLogger?.warn || console.warn)('⚠️ ULTIMATE FALLBACK: u.targets_by_group utilisé (calcul dynamique)');
      }
    }

    // Allocation fournie par u.targets_by_group (calcul dynamique) - vérification
    if (!allocation || Object.keys(allocation).length === 0) {
      console.error('🚨 ERREUR CRITIQUE: targets_by_group vide', { u, allocation });
      return '<div class="error-message">❌ Erreur: calculs dynamiques indisponibles</div>';
    }

    // GARDE-FOUS - Checksum et validation
    const total = Object.values(allocation || {}).reduce((a, b) => a + (isFinite(b) ? b : 0), 0);
    if (Math.abs(total - 100) > 0.5) {
      (window.debugLogger?.warn || console.warn)(`⚠️ target_sum_mismatch: somme = ${total.toFixed(1)}% (≠ 100%)`);
      // Petite normalisation douce (hors stables)
      if (allocation && allocation['Stablecoins'] != null) {
        const st = allocation['Stablecoins'];
        const space = Math.max(0, 100 - st);
        const nonKeys = Object.keys(allocation).filter(k => k !== 'Stablecoins');
        const nonSum = nonKeys.reduce((s, k) => s + allocation[k], 0) || 1;
        nonKeys.forEach(k => allocation[k] = allocation[k] * (space / nonSum));
        const newTotal = Object.values(allocation).reduce((a, b) => a + b, 0);
        if (Math.abs(newTotal - 100) > 0.5) {
          (window.debugLogger?.warn || console.warn)(`⚠️ soft renorm failed: ${newTotal.toFixed(2)}%`);
        }
      }
    }

    // Allocation déjà générée par u.targets_by_group (dynamique) - pas de fallback legacy nécessaire

    if (allocation && Object.keys(allocation).length > 0) {
      const conf = u.decision.confidence || 0;
      const contra = (u.contradictions?.length) || 0;
      const governanceStatus = store.getGovernanceStatus();

      const unifiedStateForCap = (typeof store.snapshot === 'function' ? store.snapshot() : null) || window.realDataStore || {};
      const governanceState = unifiedStateForCap?.governance || store.get('governance');
      const activePolicy = governanceState?.active_policy;

      const policyCapPercent = resolvePolicyCapPercent(unifiedStateForCap);
      const engineCapPercent = resolveEngineCapPercent(unifiedStateForCap);
      const capPercent = resolveCapPercent(unifiedStateForCap);

      let mode = { name: 'Observe', cap: capPercent != null ? capPercent : 0 };

      if (governanceStatus.state === 'FROZEN') {
        mode = { name: 'Frozen', cap: 0 };
      } else if (policyCapPercent != null) {
        const policyMode = activePolicy?.mode || 'Normal';
        mode = {
          name: `${policyMode} (Gov)`,
          cap: policyCapPercent
        };
        if (engineCapPercent != null && engineCapPercent !== policyCapPercent) {
          mode.smartCap = engineCapPercent;
        }
      } else {
        mode = conf > 0.8 && contra === 0 ? { name: 'Deploy', cap: 15 } :
               conf > 0.65 && contra <= 1 ? { name: 'Rotate', cap: 10 } :
               conf > 0.55 ? { name: 'Hedge', cap: 5 } : { name: 'Observe', cap: 0 };
        if (capPercent != null) {
          mode.cap = capPercent;
        }
        if (engineCapPercent != null && mode.cap !== engineCapPercent) {
          mode.smartCap = engineCapPercent;
        }
      }

      const current = await getCurrentAllocationByGroup(5.0);
      // Plus besoin d'applyCycleMultipliersToTargets ni de garde UI - u.targets_by_group (dynamique) fait tout

      // DEBUG: Verify allocation before assigning to targetAdj
      console.debug('🎯 ALLOCATION DEBUG before targetAdj:', {
        allocation_keys: allocation ? Object.keys(allocation) : 'no allocation',
        allocation_values: allocation,
        allocation_total: allocation ? Object.values(allocation).reduce((a, b) => a + b, 0) : 'no allocation'
      });

      // SOURCE CANONIQUE UNIQUE: Utiliser targets_by_group (calculs dynamiques)
      // Plus de presets hardcodés - tout est calculé dynamiquement dans unified-insights-v2.js
      let executionTargets = allocation; // Current allocation (fallback de sécurité)

      // LECTURE DIRECTE: Objectifs théoriques = source canonique dynamique
      if (u.targets_by_group && Object.keys(u.targets_by_group).length > 0) {
        executionTargets = { ...u.targets_by_group };
        (window.debugLogger?.info || console.log)('✅ DYNAMIC TARGETS utilisés (plus de presets!):', {
          source: 'u.targets_by_group (computed dynamically)',
          targets: Object.entries(executionTargets).map(([k,v]) => `${k}: ${v.toFixed(1)}%`),
          stables_pct: executionTargets['Stablecoins']?.toFixed(1) + '%',
          sum: Object.values(executionTargets).reduce((a,b) => a+b, 0).toFixed(1) + '%'
        });
      } else {
        (window.debugLogger?.warn || console.warn)('⚠️ targets_by_group manquant, fallback sur allocation actuelle');
      }

      const targetAdj = executionTargets;

      // CORRECTION UNIFICATION: Forcer l'affichage théorique à utiliser les mêmes targets
      // pour éviter l'incohérence entre objectifs théoriques et plan d'exécution
      console.debug('🔄 BEFORE UNIFICATION:', {
        allocation_before: allocation ? Object.entries(allocation).map(([k,v]) => `${k}: ${v.toFixed(1)}%`) : 'null',
        executionTargets: Object.entries(executionTargets).map(([k,v]) => `${k}: ${v.toFixed(1)}%`)
      });

      allocation = executionTargets;

      console.debug('🔄 AFTER UNIFICATION: Objectifs théoriques forcés à utiliser les mêmes targets que le plan d\'exécution:', {
        allocation_after: Object.entries(allocation).map(([k,v]) => `${k}: ${v.toFixed(1)}%`),
        unified_targets: Object.entries(executionTargets).map(([k,v]) => `${k}: ${v.toFixed(1)}%`),
        note: 'Objectifs et plan maintenant cohérents'
      });

      const keys = new Set([
        ...Object.keys(targetAdj || {}),
        ...Object.keys((current && current.pct) || {})
      ]);

      const entries = Array.from(keys).map(k => {
        const cur = Number((current?.pct || {})[k] || 0);
        const tgt = Number((targetAdj || {})[k] || 0);
        const delta = Math.round((tgt - cur) * 10) / 10;
        return { k, cur, tgt, delta, suggested: 0 }; // suggested will be calculated with zero-sum constraint
      });

      // DEBUG: Log execution plan calculation details
      console.debug('🎯 EXECUTION PLAN DELTAS DEBUG:', {
        cap_limit: mode.cap + '%',
        all_deltas: entries.map(e => ({
          asset: e.k,
          current: e.cur.toFixed(1) + '%',
          target: e.tgt.toFixed(1) + '%',
          delta: e.delta.toFixed(1) + '%',
          urgency: Math.abs(e.delta).toFixed(1)
        })).sort((a, b) => parseFloat(b.urgency) - parseFloat(a.urgency)),
        significant_deltas: entries.filter(e => Math.abs(e.delta) > 0.5).length,
        total_positive_budget_needed: entries.filter(e => e.delta > 0).reduce((s, e) => s + e.delta, 0).toFixed(1) + '%',
        total_negative_budget_needed: entries.filter(e => e.delta < 0).reduce((s, e) => s + Math.abs(e.delta), 0).toFixed(1) + '%'
      });

      // CONTRAINTE ZÉRO-SOMME: calculate suggested moves with cap and zero-sum constraint
      const cappedEntries = calculateZeroSumCappedMoves(entries, mode.cap);
      entries.forEach((entry, i) => {
        entry.suggested = cappedEntries[i].suggested;
      });

      // HIÉRARCHIE STRICTE: seulement les groupes taxonomy autorisés
      const TOP_LEVEL_GROUPS = GROUP_ORDER.length > 0 ? GROUP_ORDER : ['BTC', 'ETH', 'Stablecoins', 'SOL', 'L1/L0 majors', 'L2/Scaling', 'DeFi', 'AI/Data', 'Gaming/NFT', 'Memecoins', 'Others'];

      const visible = entries
        .filter(e => {
          // Filtre significatif
          const isSignificant = (e.tgt > 0.1) || Math.abs(e.delta) > 0.2 || e.cur > 0.1;
          // Filtre hiérarchique - SEULEMENT les groupes top-level
          const isTopLevel = TOP_LEVEL_GROUPS.includes(e.k);

          if (!isTopLevel && isSignificant) {
            console.debug(`🚫 Coin ${e.k} excluded from top-level (child of group)`);
          }

          return isSignificant && isTopLevel;
        })
        .sort((a, b) => (b.tgt - a.tgt) || (b.cur - a.cur))
        .slice(0, 11); // Max 11 groupes

      // Persist suggested allocation for rebalance.html consumption (moved here after 'visible' calculation)
      try {
        if (targetAdj && Object.keys(targetAdj).length > 0) {
          // Utiliser le plan d'exécution pré-calculé (même source que cartes)
          const executionPlan = u.execution?.plan_iter1 || {};
          console.debug('🔄 Using pre-calculated execution plan:', executionPlan);

          const payload = {
            targets: targetAdj, // Final theoretical targets
            execution_plan: executionPlan, // Iteration 1 targets with caps
            cap_percent: mode.cap,
            strategy: 'Regime-Based Allocation',
            timestamp: new Date().toISOString(),
            source: 'analytics-unified'
          };
          localStorage.setItem('unified_suggested_allocation', JSON.stringify(payload));
          window.dispatchEvent(new CustomEvent('unifiedSuggestedAllocationUpdated', { detail: payload }));
          console.debug('✅ Unified suggested allocation persisted:', {
            targetsCount: Object.keys(targetAdj).length,
            visibleCount: visible.length,
            execPlanCount: Object.keys(executionPlan).length,
            cap: mode.cap,
            hasCurrentData: !!(current && current.groups)
          });
        } else {
          (window.debugLogger?.warn || console.warn)('⚠️ No targetAdj data to persist', { targetAdj, keys: Object.keys(targetAdj || {}) });
        }
      } catch (e) {
        (window.debugLogger?.warn || console.warn)('Persist unified suggested allocation failed:', e?.message || e);
      }

      // NOUVEAU - Séparation Budget vs Exécution
      const riskBudget = u.risk_budget || {};
      const execution = u.execution || {};
      const stablesTheorique = riskBudget.target_stables_pct || null;
      let estimatedIters = execution.estimated_iters_to_target ?? 'N/A';
      if (visible.length > 0) {
        const capPctForIterations = capPercent != null ? capPercent : (typeof mode.cap === 'number' ? mode.cap : null);
        const capFraction = capPctForIterations != null ? capPctForIterations / 100 : 0;
        if (capFraction <= 0) {
          estimatedIters = '∞';
        } else {
          const maxDeltaPct = visible.reduce((max, entry) => {
            const current = typeof entry.cur === 'number' ? entry.cur : 0;
            const target = typeof entry.tgt === 'number' ? entry.tgt : 0;
            const diff = Math.abs(target - current);
            return diff > max ? diff : max;
          }, 0);
          const maxDeltaFraction = maxDeltaPct / 100;
          estimatedIters = maxDeltaFraction > 0 ? Math.max(1, Math.ceil(maxDeltaFraction / capFraction)) : 0;
        }
      }

      // TÂCHE 4 - Verrous anti-régression (dev uniquement) avant rendu
      if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
        const stablesEntry = visible.find(v => v.k === 'Stablecoins');
        const totalTgt = visible.reduce((sum, v) => sum + (Number(v.tgt) || 0), 0);

        if (!stablesEntry || stablesEntry.tgt < 0.5) {
          console.error('[ASSERT] UI RENDER: Stablecoins manquantes dans visible targets', { visible, stablesEntry });
        }
        if (Math.abs(totalTgt - 100) > 0.5) {
          console.error('[ASSERT] UI RENDER: Somme targets visible ≠ 100%', { totalTgt, visible });
        }
        console.debug(`✅ UI RENDER: Verrous OK - Stables ${stablesEntry?.tgt?.toFixed(1) || 0}%, Total ${totalTgt.toFixed(1)}%`);
      }

      allocationBlock = `
        ${card(`
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem;">
            <div style="font-weight:700;">💡 Objectifs Théoriques</div>
            <div style="font-size:.75rem; color:var(--theme-text-muted); background: var(--theme-bg); border:1px solid var(--theme-border); padding:.2rem .6rem; border-radius: 999px;">
              Budget Risque: ${riskBudget.methodology || 'regime_based'}
            </div>
          </div>
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:.5rem; font-size:.85rem;">
            ${visible.map(({k, cur, tgt}) => {
              const grand = Number(current?.grand || 0);
              const tgtUsd = (tgt / 100) * grand;
              const tgtUsdStr = `$${Math.round(tgtUsd).toLocaleString('en-US')}`;
              const tgtW = Math.max(0, Math.min(100, tgt));
              return `
                <div style="padding:.5rem .7rem; background: var(--theme-surface); border-radius: var(--radius-sm); border: 1px solid var(--theme-border);">
                  <div style="font-weight: 600; margin-bottom:.3rem; color: var(--theme-text);">${k}</div>
                  <div style="display:flex; justify-content:space-between; margin-bottom:.2rem;">
                    <span style="color: var(--theme-text-muted);">Objectif</span>
                    <span style="font-weight: 600;">${tgt.toFixed(1)}%</span>
                  </div>
                  <div style="height:6px; background: var(--theme-border); border-radius:3px; overflow:hidden;">
                    <div style="width:${tgtW}%; height:100%; background: var(--brand-primary);"></div>
                  </div>
                  <div style="font-size:.75rem; color:var(--theme-text-muted); margin-top:.3rem;">${tgtUsdStr}</div>
                </div>
              `;
            }).join('')}
          </div>
          ${stablesTheorique ? `<div style="margin-top:.6rem; font-size:.75rem; color:var(--theme-text-muted); padding:.4rem; background: var(--theme-bg); border-radius: 6px; border: 1px solid var(--theme-border);">
            💰 Budget stables théorique: <b>${stablesTheorique}%</b> (calculé par algorithme de risque)
          </div>` : ''}
        `, { title: 'Budget & Objectifs' })}

        ${card(`
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem;">
            <div style="font-weight:700;">🎯 Plan d'Exécution (Itération ${execution.current_iteration || 1})</div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              ${activePolicy ? `<div style="font-size:.7rem; color: var(--success); background: var(--theme-bg); border:1px solid var(--success); padding:.1rem .4rem; border-radius: 999px;">🏛️ Governance</div>` : ''}
              <div style="font-size:.75rem; color:var(--theme-text-muted); background: var(--theme-bg); border:1px solid var(--theme-border); padding:.2rem .6rem; border-radius: 999px;">
                Cap ±${mode.cap}%
              </div>
            </div>
          </div>
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:.45rem; font-size:.8rem;">
            ${visible.map(({k, cur, tgt, delta, suggested}) => {
              const moveColor = suggested >= 0 ? 'var(--success)' : 'var(--danger)';
              const sign = (v) => v > 0 ? '+' : '';
              const curW = Math.max(0, Math.min(100, cur));
              const suggestedTgt = cur + suggested; // Cible de cette itération
              const suggestedW = Math.max(0, Math.min(100, suggestedTgt));
              const grand = Number(current?.grand || 0);
              const curUsd = (cur / 100) * grand;
              const suggestedUsd = (suggestedTgt / 100) * grand;
              const curUsdStr = `$${Math.round(curUsd).toLocaleString('en-US')}`;
              const suggestedUsdStr = `$${Math.round(suggestedUsd).toLocaleString('en-US')}`;
              const tip = `Actuel: ${curUsdStr} → Cette itération: ${suggestedUsdStr}`;
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
                    <span>Itération 1</span><span>${suggestedTgt.toFixed(1)}%</span>
                  </div>
                  <div style="height:4px; background: var(--theme-border); border-radius:3px; overflow:hidden;">
                    <div style="width:${suggestedW}%; height:100%; background: var(--warning);"></div>
                  </div>
                  <div style="margin-top:.35rem; font-size:.75rem; color:${moveColor}; font-weight:600; text-align:right;">Δ ${sign(suggested)}${suggested}%</div>
                </div>
              `;
            }).join('')}
          </div>
          <div style="margin-top:.6rem; font-size:.75rem; color:var(--theme-text-muted); padding:.4rem; background: var(--theme-bg); border-radius: 6px; border: 1px solid var(--theme-border);">
            ⏱️ Convergence estimée: <b>${estimatedIters} rebalances</b> pour atteindre les objectifs théoriques
          </div>
        `, { title: 'Exécution Cap ±' + mode.cap + '%' })}
      `;
    }
  } catch (e) {
    (window.debugLogger?.warn || console.warn)('Unified allocation render skipped:', e.message || e);
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

    ${(() => {
      // PHASE ENGINE DIAGNOSTICS PANEL
      const rawPhaseMode = localStorage.getItem('PHASE_ENGINE_ENABLED') || 'shadow';
      const phaseMode = rawPhaseMode.toLowerCase();
      const isDisabled = phaseMode === 'off' || phaseMode === 'disabled' || phaseMode === 'disable';
      const phaseModeBadge = isDisabled ? 'DISABLED' : rawPhaseMode.toUpperCase();
      const shadowResult = typeof window !== 'undefined' ? window._phaseEngineShadowResult : null;
      const phaseConfig = typeof window !== 'undefined' ? window._phaseEngineConfig : null;

      return card(`
        <div style="font-weight:700; margin-bottom:.5rem; display: flex; align-items: center; gap: .5rem;">
          🧪 Phase Engine Diagnostics
          <span style="background: var(--info); color: white; padding: 1px 6px; border-radius: 3px; font-size: .7rem; font-weight: 700;">${phaseModeBadge}</span>
        </div>

        ${isDisabled ? `
          <div style="margin-bottom: .75rem; font-size: .8rem; color: var(--theme-text-muted);">
            Phase engine disabled. Use the controls below to re-enable diagnostics.
          </div>
        ` : ''}

        ${shadowResult ? `
          <div style="margin-bottom: .75rem;">
            <div style="font-weight: 600; margin-bottom: .25rem;">Current Detection:</div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: .5rem; font-size: .8rem;">
              <div style="background: var(--theme-bg); padding: .4rem .6rem; border-radius: var(--radius-sm);">
                <div style="font-weight: 600; color: var(--brand-primary);">${shadowResult.phase.replace('_', ' ').toUpperCase()}</div>
                <div style="font-size: .7rem; color: var(--theme-text-muted); margin-top: .1rem;">Phase</div>
              </div>
              <div style="background: var(--theme-bg); padding: .4rem .6rem; border-radius: var(--radius-sm);">
                <div style="font-weight: 600;">${shadowResult.inputs.DI.toFixed(1)}</div>
                <div style="font-size: .7rem; color: var(--theme-text-muted); margin-top: .1rem;">DI Score</div>
              </div>
              <div style="background: var(--theme-bg); padding: .4rem .6rem; border-radius: var(--radius-sm);">
                <div style="font-weight: 600;">${(shadowResult.inputs.breadth_alts * 100).toFixed(1)}%</div>
                <div style="font-size: .7rem; color: var(--theme-text-muted); margin-top: .1rem;">Breadth</div>
              </div>
              <div style="background: var(--theme-bg); padding: .4rem .6rem; border-radius: var(--radius-sm);">
                <div style="font-weight: 600;">${shadowResult.inputs.partial ? 'Partial' : 'Complete'}</div>
                <div style="font-size: .7rem; color: var(--theme-text-muted); margin-top: .1rem;">Data Quality</div>
              </div>
            </div>
          </div>

          ${shadowResult.metadata.tiltsApplied ? `
            <div style="margin-bottom: .75rem;">
              <div style="font-weight: 600; margin-bottom: .25rem;">Applied Tilts:</div>
              <div style="font-size: .8rem; color: var(--theme-text);">
                ${Object.entries(shadowResult.metadata.tilts || {}).map(([asset, mult]) =>
                  `<span style="margin-right: .5rem; background: var(--theme-surface); padding: .2rem .4rem; border-radius: 3px;">${asset}: ×${mult}</span>`
                ).join('')}
              </div>
              ${shadowResult.metadata.capsTriggered.length > 0 ? `
                <div style="margin-top: .5rem; font-size: .75rem; color: var(--warning);">
                  🧢 Caps triggered: ${shadowResult.metadata.capsTriggered.join(', ')}
                </div>
              ` : ''}
              ${shadowResult.metadata.stablesFloorHit ? `
                <div style="margin-top: .25rem; font-size: .75rem; color: var(--info);">
                  🏛️ Stables floor applied
                </div>
              ` : ''}
            </div>
          ` : ''}

          <div style="margin-bottom: .75rem;">
            <div style="font-weight: 600; margin-bottom: .25rem;">Phase Series Data:</div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: .5rem; font-size: .75rem;">
              <div style="background: var(--theme-bg); padding: .3rem .4rem; border-radius: var(--radius-sm);">
                ETH/BTC: ${shadowResult.inputs.eth_btc.length} samples
              </div>
              <div style="background: var(--theme-bg); padding: .3rem .4rem; border-radius: var(--radius-sm);">
                Alts/BTC: ${shadowResult.inputs.alts_btc.length} samples
              </div>
              <div style="background: var(--theme-bg); padding: .3rem .4rem; border-radius: var(--radius-sm);">
                BTC Dom: ${(shadowResult.inputs.btc_dom * 100).toFixed(1)}%
              </div>
              <div style="background: var(--theme-bg); padding: .3rem .4rem; border-radius: var(--radius-sm);">
                Dispersion: ${(shadowResult.inputs.dispersion * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          <div style="font-size: .7rem; color: var(--theme-text-muted); margin-bottom: .5rem;">
            Last update: ${new Date(shadowResult.timestamp).toLocaleTimeString()}
          </div>
        ` : ''}

        <div style="display: flex; gap: .5rem; flex-wrap: wrap;">
          <button onclick="localStorage.setItem('PHASE_ENGINE_ENABLED', 'shadow'); location.reload();"
                  style="padding: .3rem .6rem; border: 1px solid var(--info); background: ${phaseMode === 'shadow' ? 'var(--info)' : 'transparent'}; color: ${phaseMode === 'shadow' ? 'white' : 'var(--info)'}; border-radius: var(--radius-sm); font-size: .75rem; cursor: pointer;">
            Shadow Mode
          </button>
          <button onclick="localStorage.setItem('PHASE_ENGINE_ENABLED', 'apply'); location.reload();"
                  style="padding: .3rem .6rem; border: 1px solid var(--warning); background: ${phaseMode === 'apply' ? 'var(--warning)' : 'transparent'}; color: ${phaseMode === 'apply' ? 'white' : 'var(--warning)'}; border-radius: var(--radius-sm); font-size: .75rem; cursor: pointer;">
            Apply Mode
          </button>
          <button onclick="localStorage.setItem('PHASE_ENGINE_ENABLED', 'off'); location.reload();"
                  style="padding: .3rem .6rem; border: 1px solid var(--theme-text-muted); background: ${isDisabled ? 'var(--theme-text-muted)' : 'transparent'}; color: ${isDisabled ? 'white' : 'var(--theme-text-muted)'}; border-radius: var(--radius-sm); font-size: .75rem; cursor: pointer;">
            Disabled
          </button>
        </div>

        <div style="margin-top: .5rem; padding: .4rem; background: var(--theme-surface); border-radius: var(--radius-sm); font-size: .7rem; color: var(--theme-text-muted);">
          <strong>Shadow Mode:</strong> Calculate phase tilts but don't apply them (logging only)<br>
          <strong>Apply Mode:</strong> Actually use phase-tilted targets for allocation<br>
          <strong>Disabled:</strong> Use standard dynamic targets without phase engine
        </div>
      `, { title: 'Phase Engine Beta' });
    })()}

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
  
  (window.debugLogger?.debug || console.log)('🧠 INTELLIGENT UNIFIED INSIGHTS rendered with:', {
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
  (window.debugLogger?.debug || console.log)('🗑️ Allocation cache invalidated due to source/user/taxonomy change');
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

    // INVALIDATION MULTI-WALLET: forcer rechargement risk_budget et unified state
    if (typeof window.debugInvalidateRiskBudget === 'function') {
      window.debugInvalidateRiskBudget();
    }

    // Trigger unified state recalculation
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent('riskBudgetInvalidated', {
        detail: { reason: 'user_change', newUser: event.detail?.newUser }
      }));
    }, 200);
  });

  // TÂCHE 3 - Re-rendu événementiel quand budget arrive
  window.addEventListener('riskBudgetInvalidated', (event) => {
    console.debug(`💰 Risk budget invalidated: ${event.detail?.reason || 'unknown'}, re-rendering UnifiedInsights`);

    // Force re-render des insights après invalidation du budget
    setTimeout(async () => {
      try {
        const container = document.querySelector('[data-unified-insights]');
        if (container && typeof window.renderUnifiedInsights === 'function') {
          console.debug('🔄 Re-rendering UnifiedInsights after budget change...');
          await window.renderUnifiedInsights();
        }
      } catch (e) {
        (window.debugLogger?.warn || console.warn)('UnifiedInsights re-render failed:', e.message);
      }
    }, 100); // Court délai pour laisser le budget se mettre à jour
  });

  window.addEventListener('storage', (event) => {
    if (event.key === 'activeUser') {
      console.debug('👤 User change detected via storage, dispatching activeUserChanged and invalidating cache');
      // Dispatch activeUserChanged event for synchronous chaining
      const userChangeEvent = new CustomEvent('activeUserChanged', {
        detail: { oldUser: event.oldValue, newUser: event.newValue }
      });
      window.dispatchEvent(userChangeEvent);
      // Invalidate cache with slight delay to ensure event handlers complete
      setTimeout(invalidateAllocationCache, 50);
    } else if (event.key?.includes('crypto_rebal_settings')) {
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