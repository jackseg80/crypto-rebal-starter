// static/components/utils.js
// Utilitaires partagés pour les Web Components flyout & risk-snapshot

/**
 * Normalise le pathname pour générer des clés localStorage stables
 * Ex: "/static/risk-dashboard.html" → "risk-dashboard"
 */
export function normalizePathname() {
  return (location.pathname || '/')
    .replace(/^\/static\//, '')
    .replace(/\.html$/, '')
    .replace(/^\//, '') || 'index';
}

/**
 * Génère un namespace unique pour localStorage par page + clé
 * Ex: ns('flyout') → "__ui.flyout.risk-dashboard.flyout"
 */
export function ns(persistKey) {
  return `__ui.flyout.${normalizePathname()}.${persistKey}`;
}

/**
 * Fetch avec timeout automatique + support merge de signal externe
 * @param {string} url - URL à fetcher
 * @param {Object} options
 * @param {number} options.timeoutMs - Timeout en ms (défaut 5000)
 * @param {AbortSignal} options.signal - Signal externe optionnel
 * @returns {Promise<Response>}
 */
export async function fetchWithTimeout(url, { timeoutMs = 5000, signal } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  // Merge signal externe si fourni
  if (signal) {
    signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const resp = await fetch(url, { signal: controller.signal });
    return resp;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Fetch risk data avec fallback automatique
 * Essaie /api/risk/dashboard puis /api/risk/metrics
 * @returns {Promise<Object|null>} JSON data ou null si échec
 */
export async function fetchRisk() {
  // 1) Endpoint canonique
  try {
    const r = await fetchWithTimeout(
      '/api/risk/dashboard?min_usd=0&price_history_days=30&lookback_days=30',
      { timeoutMs: 5000 }
    );
    if (r?.ok) return await r.json();
    console.warn('[risk-snapshot] /api/risk/dashboard not OK:', r?.status);
  } catch (err) {
    console.warn('[risk-snapshot] Primary API failed:', err?.message || err);
  }

  // 2) Fallback
  try {
    const r2 = await fetchWithTimeout('/api/risk/metrics', { timeoutMs: 5000 });
    if (r2?.ok) return await r2.json();
    console.warn('[risk-snapshot] /api/risk/metrics not OK:', r2?.status);
  } catch (err) {
    console.error('[risk-snapshot] Fallback API failed:', err?.message || err);
  }

  return null;
}

/**
 * Attend un event global avec timeout (event-based, pas de busy-loop)
 * @param {string} eventName - Nom de l'event à attendre
 * @param {number} timeoutMs - Timeout en ms
 * @returns {Promise<boolean>} true si event reçu, false si timeout
 */
export function waitForGlobalEventOrTimeout(eventName, timeoutMs = 1500) {
  if (timeoutMs <= 0) return Promise.resolve(false);

  return new Promise(resolve => {
    let to;
    const onReady = () => {
      clearTimeout(to);
      window.removeEventListener(eventName, onReady);
      resolve(true);
    };

    window.addEventListener(eventName, onReady);

    to = setTimeout(() => {
      window.removeEventListener(eventName, onReady);
      resolve(false);
    }, timeoutMs);
  });
}

/**
 * Sélecteurs fallback si selectors/governance.js absent
 * Logique robuste pour extraire contradiction, cap, timestamp
 */
export const fallbackSelectors = {
  /**
   * Extrait contradiction_index normalisé [0..1]
   * @param {Object} s - State
   * @returns {number} Contradiction entre 0 et 1
   */
  selectContradiction01: (s) => {
    const raw = s?.governance?.contradiction_index ?? 0;
    const v = raw > 1 ? raw / 100 : raw;
    return Math.max(0, Math.min(1, Number(v) || 0));
  },

  /**
   * Extrait cap_daily [0..1]
   * @param {Object} s - State
   * @returns {number} Cap daily entre 0 et 1
   */
  selectCapPercent: (s) => {
    let v = s?.governance?.active_policy?.cap_daily;
    if (!Number.isFinite(v)) v = s?.governance?.cap_daily;
    return Number(v) ?? 0.01;
  },

  /**
   * Extrait timestamp de fraîcheur governance
   * @param {Object} s - State
   * @returns {string|null} ISO timestamp ou null
   */
  selectGovernanceTimestamp: (s) =>
    s?.governance?.ml_signals_timestamp || s?.governance?.updated || null,
};
