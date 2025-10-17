// UnifiedInsights - Utility Functions
// Helper functions for color schemes, card builders, and data normalization

import { KNOWN_ASSET_MAPPING } from '../../shared-asset-groups.js';

/**
 * Normalise les alias crypto (SOL2→SOL, UNI2→UNI, etc.) via taxonomy
 */
export function normalizeAlias(symbol) {
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
export async function fetchJson(url, opts = {}) {
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

// Governance selectors - resilient fallbacks
export function resolveCapPercent(state, governanceSelectors) {
  const {
    selectCapPercent: rawSelectCapPercent,
    selectPolicyCapPercent: rawSelectPolicyCapPercent,
    selectEngineCapPercent: rawSelectEngineCapPercent,
  } = governanceSelectors;

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

export function resolvePolicyCapPercent(state, governanceSelectors) {
  const { selectPolicyCapPercent: rawSelectPolicyCapPercent } = governanceSelectors;

  try {
    if (typeof rawSelectPolicyCapPercent === "function") {
      const policy = rawSelectPolicyCapPercent(state);
      if (policy != null) return policy;
    }
  } catch (error) {
    console.debug('resolvePolicyCapPercent primary failed', error);
  }
  return resolveCapPercent(state, governanceSelectors);
}

export function resolveEngineCapPercent(state, governanceSelectors) {
  const { selectEngineCapPercent: rawSelectEngineCapPercent } = governanceSelectors;

  try {
    if (typeof rawSelectEngineCapPercent === "function") {
      const engine = rawSelectEngineCapPercent(state);
      if (engine != null) return engine;
    }
  } catch (error) {
    console.debug('resolveEngineCapPercent primary failed', error);
  }
  return resolveCapPercent(state, governanceSelectors);
}

// Color scales
// - Positive scale: high = good (green)
// - Risk Score scale: high = robust/low risk (green) - See RISK_SEMANTICS.md
export const colorPositive = (s) => s > 70 ? 'var(--success)' : s >= 40 ? 'var(--warning)' : 'var(--danger)';
export const colorRisk = (s) => s > 70 ? 'var(--success)' : s >= 40 ? 'var(--warning)' : 'var(--danger)';

// Card builder
export function card(inner, opts = {}) {
  const { accentLeft = null, title = null } = opts;
  return `
    <div class="unified-card" style="background: var(--theme-surface); border: 1px solid var(--theme-border); border-radius: var(--radius-md); padding: var(--space-md); ${accentLeft ? `border-left: 4px solid ${accentLeft};` : ''}">
      ${title ? `<div style="font-weight: 700; margin-bottom: .5rem; font-size: .9rem; color: var(--theme-text-muted);">${title}</div>` : ''}
      ${inner}
    </div>
  `;
}

// Compact card variant
export function compactCard(inner) {
  return `
    <div class="unified-card" style="background: var(--theme-surface); border: 1px solid var(--theme-border); border-radius: var(--radius-md); padding: .6rem;">
      ${inner}
    </div>
  `;
}

// Intelligence badge helper
export function intelligenceBadge(status) {
  const colors = {
    'active': 'var(--success)',
    'limited': 'var(--warning)',
    'unknown': 'var(--theme-text-muted)'
  };
  return `<span style="background: ${colors[status] || colors.unknown}; color: white; padding: 1px 4px; border-radius: 3px; font-size: .7rem; font-weight: 600;">${status}</span>`;
}

// Cache invalidation helper
const _allocCache = { ts: 0, data: null, key: null };

export function invalidateAllocationCache() {
  _allocCache.data = null;
  _allocCache.key = null;
  _allocCache.ts = 0;
  (window.debugLogger?.debug || console.log)('🗑️ Allocation cache invalidated due to source/user/taxonomy change');
}

export function getAllocCache() {
  return _allocCache;
}
