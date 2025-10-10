/**
 * Store centralisé pour l'état de l'application Risk & Analytics.
 * Utilise un pattern pub/sub simple, inspiré de Zustand, pour une gestion d'état
 * réactive et prévisible sans framework lourd.
 *
 * Intègre la logique de gouvernance, la synchronisation des signaux, la persistance,
 * et le Stability Engine pour l'hystérésis.
 */

/**
 * Crée une instance de store avec un état observable.
 * @param {Function} createInitialState - Une fonction qui retourne l'état initial.
 * @returns {{getState: Function, setState: Function, subscribe: Function}}
 */
function createStore(createInitialState) {
  let state = createInitialState();
  const listeners = new Set();

  const getState = () => state;

  const setState = (patch, action = 'anonymous') => {
    const oldState = state;
    const nextState = typeof patch === 'function' ? patch(state) : { ...state, ...patch };
    state = nextState;
    listeners.forEach(l => l(state, oldState, action));
  };

  const subscribe = (listener) => {
    listeners.add(listener);
    // Retourne une fonction de désinscription
    return () => listeners.delete(listener);
  };

  return { getState, setState, subscribe };
}

const initialStateFactory = () => ({
  // Risk metrics (existing)
  riskMetrics: null,
  portfolioSummary: null,
  correlationMetrics: null,

  // CCS data
  ccs: {
    score: null,
    weights: {},
    signals: null,
    lastUpdate: null,
    model_version: 'ccs-1',
  },

  // Cycle data
  cycle: {
    months: null,
    weight: 0.3,
    ccsStar: null,
    multiplier: 1.0
  },

  // Targets
  targets: {
    current: null,
    proposed: null,
    plan: null,
    model_version: 'tgt-1',
  },

  // Governance state
  governance: {
    current_state: 'IDLE',
    mode: 'manual',
    last_decision_id: null,
    contradiction_index: 0.0,
    ml_signals_timestamp: null,
    active_policy: { cap_daily: 0.08 },  // FIX Oct 2025: Default fallback 8% (safe conservative, not 1%)
    pending_approvals: [],
    next_update_time: null,
    decisions: [],
    ml_signals: null,
    last_sync: null,
  },

  // UI state
  ui: {
    activeTab: 'risk',
    loading: false,
    errors: [],
    apiStatus: {
      backend: 'unknown',
      signals: 'unknown',
      lastCheck: null
    }
  }
});

const { getState, setState, subscribe } = createStore(initialStateFactory);

// helpers profonds
function deepGet(obj, path) {
  return path.split('.').reduce((o, k) => (o && typeof o === 'object' ? o[k] : undefined), obj);
}
function deepSet(obj, path, value) {
  const keys = path.split('.');
  const last = keys.pop();
  let cur = obj;
  for (const k of keys) {
    if (cur[k] == null || typeof cur[k] !== 'object') cur[k] = {};
    cur = cur[k];
  }
  cur[last] = value;
}

const storeActions = {
  // Get nested property (lecture pure)
  get(path, def = undefined) {
    const v = deepGet(getState(), path);
    return v === undefined ? def : v;
  },

  // Set nested property
  set(path, value, action = 'set') {
    setState(prev => {
      const next = typeof structuredClone === 'function' ? structuredClone(prev) : JSON.parse(JSON.stringify(prev));
      deepSet(next, path, value);
      return next;
    }, action);
  },

  // Update multiple properties
  update(updates, action = 'update') {
    setState(prevState => {
      const newState = JSON.parse(JSON.stringify(prevState)); // Deep copy for safety
      Object.entries(updates).forEach(([path, value]) => {
        deepSet(newState, path, value);
      });
      return newState;
    }, action);
  },

  // Persist key data to localStorage
  persist(key = 'risk-dashboard-state') {
    const state = getState();
    const toSave = {
      ccs: state.ccs,
      cycle: state.cycle,
      targets: state.targets,
      governance: state.governance,
      timestamp: Date.now()
    };

    try {
      localStorage.setItem(key, JSON.stringify(toSave));
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('Failed to persist state:', error);
    }
  },

  // Restore from localStorage
  hydrate(key = 'risk-dashboard-state') {
    try {
      const saved = localStorage.getItem(key);
      if (saved) {
        const { ccs, cycle, targets, governance, timestamp } = JSON.parse(saved);

        // Only restore if not too old (1 hour max)
        if (Date.now() - timestamp < 60 * 60 * 1000) {
          setState(prevState => ({
            ...prevState,
            ccs: { ...prevState.ccs, ...ccs },
            cycle: { ...prevState.cycle, ...cycle },
            targets: { ...prevState.targets, ...targets },
            governance: { ...prevState.governance, ...governance },
          }), 'hydrate');

          console.debug('State hydrated from localStorage');
        }
      }
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('Failed to hydrate state:', error);
    }
  },

  // --- DEBOUNCING TIMERS ---
  _syncGovernanceTimer: null,
  _syncMLSignalsTimer: null,
  _syncDebounceMs: 500,

  // Debounced version of syncGovernanceState
  debouncedSyncGovernanceState() {
    if (this._syncGovernanceTimer) {
      clearTimeout(this._syncGovernanceTimer);
    }
    this._syncGovernanceTimer = setTimeout(() => {
      storeActions.syncGovernanceState();
      this._syncGovernanceTimer = null;
    }, this._syncDebounceMs);
  },

  // Debounced version of syncMLSignals
  debouncedSyncMLSignals() {
    if (this._syncMLSignalsTimer) {
      clearTimeout(this._syncMLSignalsTimer);
    }
    this._syncMLSignalsTimer = setTimeout(() => {
      storeActions.syncMLSignals();
      this._syncMLSignalsTimer = null;
    }, this._syncDebounceMs);
  },

  // Governance-specific methods
  async syncGovernanceState() {
    try {
      const response = await fetch(`${window.location.origin}/execution/governance/state`);
      if (response.ok) {
        const governanceState = await response.json();
        this.update({
          'governance.current_state': governanceState.current_state,
          'governance.mode': governanceState.mode,
          'governance.last_decision_id': governanceState.last_decision_id,
          'governance.contradiction_index': governanceState.contradiction_index,
          'governance.ml_signals_timestamp': governanceState.ml_signals_timestamp,
          'governance.active_policy': governanceState.active_policy ?? { cap_daily: 0.08 },  // FIX Oct 2025: Safe fallback 8%
          'governance.pending_approvals': Array.isArray(governanceState.pending_approvals) ? governanceState.pending_approvals : [],
          'governance.next_update_time': governanceState.next_update_time,
          'governance.last_sync': Date.now()
        });

        console.debug('Governance state synced:', governanceState.current_state);
        // Update backend health TTL
        storeActions._updateBackendStatusFromGovernance();
        return true;
      }
    } catch (error) {
      debugLogger.error('Failed to sync governance state:', error);
      this.update({ 'ui.errors': [...(getState().ui.errors || []), `Governance sync error: ${error.message}`] });
    }
    return false;
  },

  // Last-good fallback pour 429 rate limiting
  _lastGoodMLSignals: null,
  _mlSignalsBackoffDelay: 1000,

  async syncMLSignals() {
    try {
      const response = await fetch(`${window.location.origin}/execution/governance/signals`);

      // Rate limited: use last-good snapshot avec backoff exponentiel
      if (response.status === 429) {
        debugLogger.warn('⚠️ Rate limited (429), using last-good ML signals snapshot');
        this._mlSignalsBackoffDelay = Math.min(this._mlSignalsBackoffDelay * 2, 30000);

        // Retourner last-good si disponible
        if (this._lastGoodMLSignals) {
          return this._lastGoodMLSignals;
        }
        return null;
      }

      if (response.ok) {
        const data = await response.json();

        // Sauvegarder last-good snapshot
        this._lastGoodMLSignals = data.signals;
        this._mlSignalsBackoffDelay = 1000; // Reset backoff

        this.update({
          'governance.ml_signals': data.signals,
          'governance.last_sync': Date.now()
        });

        console.debug('ML signals synced, contradiction index:', data.signals?.contradiction_index);
        // Update backend health TTL
        storeActions._updateBackendStatusFromGovernance();
        return data.signals;
      }
    } catch (error) {
      debugLogger.error('Failed to sync ML signals:', error);
      this.update({ 'ui.errors': [...(getState().ui.errors || []), `ML signals sync error: ${error.message}`] });

      // Graceful degradation: retourner last-good si disponible
      if (this._lastGoodMLSignals) {
        debugLogger.warn('⚠️ Using last-good ML signals after error');
        return this._lastGoodMLSignals;
      }
    }
    return null;
  },

  // Update governance ML signals with client-side context (e.g., blended_score)
  async updateGovernanceBlendedScore(score) {
    try {
      if (typeof score !== 'number') return false;
      const now = Date.now();
      this._lastBlendUpdate = this._lastBlendUpdate || 0;
      if (now - this._lastBlendUpdate < 3000) {
        // debounce to avoid spamming the backend
        return false;
      }
      this._lastBlendUpdate = now;
      const response = await fetch(`${window.location.origin}/execution/governance/signals/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ blended_score: score })
      });
      if (response.ok) {
        const data = await response.json();
        // Optionally refresh governance state to reflect changes 
        try { this.debouncedSyncGovernanceState(); } catch { }
        console.debug('Blended score sent to governance:', data?.updated?.blended_score);
        return true;
      }
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('Failed to update governance blended score:', error);
    }
    return false;
  },

  // Recompute blended score server-side from components (preferred path)
  async recomputeGovernanceBlended(ccsMixte, onchainScore, riskScore) {
    try {
      const now = Date.now();
      this._lastBlendRecompute = this._lastBlendRecompute || 0;
      if (now - this._lastBlendRecompute < 3000) {
        // debounce: skip if called too frequently
        return false;
      }
      this._lastBlendRecompute = now;

      const body = {
        ccs_mixte: typeof ccsMixte === 'number' ? ccsMixte : null,
        onchain_score: typeof onchainScore === 'number' ? onchainScore : null,
        risk_score: typeof riskScore === 'number' ? riskScore : null
      };
      // Generate simple idempotency key and CSRF token (UI scope)
      const idemKey = `blend-${now}-${Math.random().toString(36).slice(2, 10)}`;
      const csrf = localStorage.getItem('csrf_token') || Math.random().toString(36).slice(2, 10);
      try { localStorage.setItem('csrf_token', csrf); } catch { }
      const response = await fetch(`${window.location.origin}/execution/governance/signals/recompute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idemKey,
          'X-CSRF-Token': csrf
        },
        body: JSON.stringify(body)
      });
      if (response.ok) {
        const data = await response.json();
        try { this.debouncedSyncGovernanceState(); } catch { }
        console.debug('Blended score recomputed server-side:', data?.blended_score);
        return true;
      }
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('Failed to recompute governance blended score:', error);
    }
    return false;
  },

  // Compute backend health based on governance timestamps (TTL in minutes)
  _updateBackendStatusFromGovernance(ttlMinutes = 30) {
    try {
      const gov = getState().governance;
      const ts = gov?.ml_signals?.timestamp ? new Date(gov.ml_signals.timestamp).getTime() : (gov?.last_sync || 0);
      const age = ts ? (Date.now() - ts) : Number.POSITIVE_INFINITY;
      const ttlMs = ttlMinutes * 60 * 1000;
      const current = getState().ui.apiStatus.backend || 'unknown';
      const next = age === Number.POSITIVE_INFINITY ? current : (age > ttlMs ? 'stale' : 'healthy');
      if (next !== current) this.update({ 'ui.apiStatus.backend': next });
    } catch { }
  },

  async approveDecision(decisionId, approved, reason = null) {
    try {
      const response = await fetch(`${window.location.origin}/execution/governance/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision_id: decisionId,
          approved: approved,
          reason: reason
        })
      });

      if (response.ok) {
        const result = await response.json();
        (window.debugLogger?.debug || console.log)('Decision approval result:', result);

        // Refresh governance state after approval
        this.debouncedSyncGovernanceState();
        return true;
      }
    } catch (error) {
      debugLogger.error('Failed to approve decision:', error);
      this.update({ 'ui.errors': [...(getState().ui.errors || []), `Decision approval error: ${error.message}`] });
    }
    return false;
  },

  async freezeSystem(reason, options = {}) {
    try {
      const { idempotencyKey, ttl_minutes = 360, source = 'ui' } = options;
      const headers = {
        'Content-Type': 'application/json'
      };

      // Add idempotency key if provided
      if (idempotencyKey) {
        headers['Idempotency-Key'] = idempotencyKey;
      }

      const response = await fetch(`${window.location.origin}/execution/governance/freeze`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          reason: reason,
          ttl_minutes: ttl_minutes,
          source_alert_id: source === 'alert' ? options.alertId : null
        })
      });

      if (response.ok) {
        const result = await response.json();
        (window.debugLogger?.debug || console.log)('System freeze result:', result);

        // Refresh governance state after freeze
        this.debouncedSyncGovernanceState();
        return result;
      } else if (response.status === 409) {
        // Idempotent request - already processed
        const error = new Error('Action already processed (idempotent request)');
        error.idempotent = true;
        throw error;
      }
    } catch (error) {
      if (error.idempotent) {
        throw error;
      }
      debugLogger.error('Failed to freeze system:', error);
      this.update({ 'ui.errors': [...(getState().ui.errors || []), `System freeze error: ${error.message}`] });
    }
    return false;
  },

  async unfreezeSystem(options = {}) {
    try {
      const { idempotencyKey, source = 'ui' } = options;
      const headers = {
        'Content-Type': 'application/json'
      };

      // Add idempotency key if provided
      if (idempotencyKey) {
        headers['Idempotency-Key'] = idempotencyKey;
      }

      const response = await fetch(`${window.location.origin}/execution/governance/unfreeze`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ source })
      });

      if (response.ok) {
        const result = await response.json();
        (window.debugLogger?.debug || console.log)('System unfreeze result:', result);

        // Refresh governance state after unfreeze
        this.debouncedSyncGovernanceState();
        return result;
      } else if (response.status === 409) {
        // Idempotent request - already processed
        const error = new Error('Action already processed (idempotent request)');
        error.idempotent = true;
        throw error;
      }
    } catch (error) {
      if (error.idempotent) {
        throw error;
      }
      debugLogger.error('Failed to unfreeze system:', error);
      this.update({ 'ui.errors': [...(getState().ui.errors || []), `System unfreeze error: ${error.message}`] });
    }
    return false;
  },

  async setGovernanceMode(mode, reason = 'Mode change from UI') {
    try {
      const response = await fetch(`${window.location.origin}/execution/governance/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: mode,
          reason: reason
        })
      });

      if (response.ok) {
        const result = await response.json();
        (window.debugLogger?.debug || console.log)('Governance mode change result:', result);

        // Refresh governance state after mode change
        this.debouncedSyncGovernanceState();
        return true;
      }
    } catch (error) {
      debugLogger.error('Failed to set governance mode:', error);
      this.update({ 'ui.errors': [...(getState().ui.errors || []), `Mode change error: ${error.message}`] });
    }
    return false;
  },

  async proposeDecision(targets = null, reason = 'Test proposal from UI') {
    try {
      const defaultTargets = [
        { symbol: 'BTC', weight: 0.6 },
        { symbol: 'ETH', weight: 0.3 },
        { symbol: 'SOL', weight: 0.1 }
      ];

      const response = await fetch(`${window.location.origin}/execution/governance/propose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          targets: targets || defaultTargets,
          reason: reason
        })
      });

      if (response.ok) {
        const result = await response.json();
        (window.debugLogger?.debug || console.log)('Decision proposal result:', result);

        // Refresh governance state after proposal
        this.debouncedSyncGovernanceState();
        return result;
      }
    } catch (error) {
      debugLogger.error('Failed to propose decision:', error);
      this.update({ 'ui.errors': [...(getState().ui.errors || []), `Proposal error: ${error.message}`] });
    }
    return false;
  },

  // Get governance status for UI display
  getGovernanceStatus() {
    const gov = getState().governance;
    const pendingCount = Array.isArray(gov.pending_approvals) ? gov.pending_approvals.length : Number(gov.pending_approvals || 0);
    const hasSignals = !!gov.ml_signals_timestamp || !!gov.ml_signals;
    return {
      state: gov.current_state || 'UNKNOWN',
      mode: gov.mode || 'manual',
      isActive: ['DRAFT', 'APPROVED', 'ACTIVE'].includes(gov.current_state),
      hasSignals,
      contradictionLevel: gov.contradiction_index || 0,
      pendingCount,
      needsAttention: pendingCount > 0 || (gov.contradiction_index || 0) > 0.7,
      lastSync: gov.last_sync ? new Date(gov.last_sync) : null
    };
  },

  // --- Stability Engine Integration ---
  _stabilityEngine: null,

  // Initialisation asynchrone du moteur de stabilité
  async _initStabilityEngine() {
    try {
      // Dynamic import pour éviter les problèmes de chargement
      const { getStableContradiction, resetStabilityState, getStabilityDebugInfo } =
        await import('../governance/stability-engine.js');

      this._stabilityEngine = {
        getStableContradiction,
        resetStabilityState,
        getStabilityDebugInfo
      };

      (window.debugLogger?.debug || console.log)('🎯 Stability Engine intégré au store');
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('⚠️ Stability Engine non disponible:', error.message);
      // Fallback simple sans hystérésis
      this._stabilityEngine = {
        getStableContradiction: (state) => state?.governance?.contradiction_index ?? 0,
        resetStabilityState: () => { },
        getStabilityDebugInfo: () => ({ disabled: true })
      };
    }
  },

  /**
   * Get stabilized contradiction with hystérésis protection
   * @returns {number} - Stabilized contradiction (0-1)
   */
  getStableContradiction() {
    if (!storeActions._stabilityEngine) {
      return getState().governance.contradiction_index ?? 0;
    }

    return storeActions._stabilityEngine.getStableContradiction(getState());
  },

  /**
   * Get stabilized contradiction as percentage for UI
   * @returns {number} - Stabilized contradiction (0-100%)
   */
  getStableContradictionPct() {
    const stable = this.getStableContradiction();
    return Math.round(stable * 100);
  },

  /**
   * Reset stability engine state (pour tests et debug)
   */
  resetStability() {
    if (storeActions._stabilityEngine) {
      storeActions._stabilityEngine.resetStabilityState();
      (window.debugLogger?.debug || console.log)('🔄 Stability Engine reset');
    }
  },

  /**
   * Get stability debug info for monitoring
   * @returns {Object} - Debug information
   */
  getStabilityDebugInfo() {
    if (!storeActions._stabilityEngine) {
      return { disabled: true };
    }

    return storeActions._stabilityEngine.getStabilityDebugInfo();
  }
};

// Initialisation asynchrone des dépendances du store
async function initializeStoreDependencies() {
  await storeActions._initStabilityEngine();
}

initializeStoreDependencies();

// Global store instance
export const store = {
  getState,
  setState,
  subscribe,
  ...storeActions,
  // Exposer le snapshot pour la compatibilité
  snapshot: getState,
};

// Also make it available globally for non-module scripts
window.riskStore = store;

// Emit event to signal store is ready (for Web Components)
window.dispatchEvent(new CustomEvent('riskStoreReady', { detail: { store: window.riskStore } }));

// Legacy aliases for existing dashboards
window.store = store;
window.__store = store;

// Auto-persist on changes (debounced)
let persistTimeout;
subscribe(() => {
  clearTimeout(persistTimeout);
  persistTimeout = setTimeout(() => storeActions.persist(), 1000);
});

export function selectFreshness(s) {
  const ts = s?.governance?.ml_signals_timestamp;
  if (!ts) return { stale: true, age_s: Infinity };
  const age_s = (Date.now() - new Date(ts).getTime()) / 1000;
  return { stale: age_s > 60, age_s };
}
