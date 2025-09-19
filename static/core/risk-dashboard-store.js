/**
 * Store ultra-simple pour Risk Dashboard CCS
 * Objet observable basique avec pub/sub minimal
 */

export class RiskDashboardStore {
  constructor() {
    // Debouncing timers
    this._syncGovernanceTimer = null;
    this._syncMLSignalsTimer = null;
    this._syncDebounceMs = 500; // 500ms debouncing

    this.state = {
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
        model_version: 'ccs-1'
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
        model_version: 'tgt-1'
      },
      
      // Governance state
      governance: {
        current_state: 'IDLE',
        mode: 'manual',
        last_decision_id: null,
        contradiction_index: 0.0,
        ml_signals_timestamp: null,
        active_policy: null,
        pending_approvals: 0,
        next_update_time: null,
        decisions: [],
        ml_signals: null,
        last_sync: null
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
    };
    
    this._subs = [];
  }
  
  // Get nested property
  get(path) {
    return path.split('.').reduce((obj, key) => obj?.[key], this.state);
  }
  
  // Set nested property
  set(path, value) {
    const keys = path.split('.');
    const lastKey = keys.pop();
    const target = keys.reduce((obj, key) => {
      if (!obj[key]) obj[key] = {};
      return obj[key];
    }, this.state);
    
    target[lastKey] = value;
    this._notify();
  }
  
  // Update multiple properties
  update(updates) {
    Object.entries(updates).forEach(([path, value]) => {
      this.set(path, value);
    });
  }
  
  // Get full state snapshot
  snapshot() {
    return JSON.parse(JSON.stringify(this.state));
  }
  
  // Subscribe to changes
  subscribe(callback) {
    this._subs.push(callback);
    // Return unsubscribe function
    return () => {
      const index = this._subs.indexOf(callback);
      if (index > -1) this._subs.splice(index, 1);
    };
  }
  
  // Notify subscribers
  _notify() {
    const snapshot = this.snapshot();
    this._subs.forEach(callback => {
      try {
        callback(snapshot);
      } catch (error) {
        console.error('Store subscriber error:', error);
      }
    });
  }
  
  // Persist key data to localStorage
  persist(key = 'risk-dashboard-state') {
    const toSave = {
      ccs: this.state.ccs,
      cycle: this.state.cycle,
      targets: this.state.targets,
      governance: this.state.governance,
      timestamp: Date.now()
    };
    
    try {
      localStorage.setItem(key, JSON.stringify(toSave));
    } catch (error) {
      console.warn('Failed to persist state:', error);
    }
  }
  
  // Restore from localStorage
  hydrate(key = 'risk-dashboard-state') {
    try {
      const saved = localStorage.getItem(key);
      if (saved) {
        const { ccs, cycle, targets, governance, timestamp } = JSON.parse(saved);
        
        // Only restore if not too old (1 hour max)
        if (Date.now() - timestamp < 60 * 60 * 1000) {
          if (ccs) this.state.ccs = { ...this.state.ccs, ...ccs };
          if (cycle) this.state.cycle = { ...this.state.cycle, ...cycle };
          if (targets) this.state.targets = { ...this.state.targets, ...targets };
          if (governance) this.state.governance = { ...this.state.governance, ...governance };
          
          console.debug('State hydrated from localStorage');
          this._notify();
        }
      }
    } catch (error) {
      console.warn('Failed to hydrate state:', error);
    }
  }

  // Debounced version of syncGovernanceState
  debouncedSyncGovernanceState() {
    if (this._syncGovernanceTimer) {
      clearTimeout(this._syncGovernanceTimer);
    }
    this._syncGovernanceTimer = setTimeout(() => {
      this.syncGovernanceState();
      this._syncGovernanceTimer = null;
    }, this._syncDebounceMs);
  }

  // Debounced version of syncMLSignals
  debouncedSyncMLSignals() {
    if (this._syncMLSignalsTimer) {
      clearTimeout(this._syncMLSignalsTimer);
    }
    this._syncMLSignalsTimer = setTimeout(() => {
      this.syncMLSignals();
      this._syncMLSignalsTimer = null;
    }, this._syncDebounceMs);
  }

  // Governance-specific methods
  async syncGovernanceState() {
    try {
      const response = await fetch(`${window.location.origin}/execution/governance/state`);
      if (response.ok) {
        const governanceState = await response.json();
        this.set('governance.current_state', governanceState.current_state);
        this.set('governance.mode', governanceState.mode);
        this.set('governance.last_decision_id', governanceState.last_decision_id);
        this.set('governance.contradiction_index', governanceState.contradiction_index);
        this.set('governance.ml_signals_timestamp', governanceState.ml_signals_timestamp);
        this.set('governance.active_policy', governanceState.active_policy);
        this.set('governance.pending_approvals', governanceState.pending_approvals);
        this.set('governance.next_update_time', governanceState.next_update_time);
        this.set('governance.last_sync', Date.now());
        
        console.debug('Governance state synced:', governanceState.current_state);
        // Update backend health TTL
        this._updateBackendStatusFromGovernance();
        return true;
      }
    } catch (error) {
      console.error('Failed to sync governance state:', error);
      this.set('ui.errors', [...(this.get('ui.errors') || []), `Governance sync error: ${error.message}`]);
    }
    return false;
  }
  
  async syncMLSignals() {
    try {
      const response = await fetch(`${window.location.origin}/execution/governance/signals`);
      if (response.ok) {
        const data = await response.json();
        this.set('governance.ml_signals', data.signals);
        this.set('governance.last_sync', Date.now());
        
        console.debug('ML signals synced, contradiction index:', data.signals?.contradiction_index);
        // Update backend health TTL
        this._updateBackendStatusFromGovernance();
        return data.signals;
      }
    } catch (error) {
      console.error('Failed to sync ML signals:', error);
      this.set('ui.errors', [...(this.get('ui.errors') || []), `ML signals sync error: ${error.message}`]);
    }
    return null;
  }

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
        try { this.debouncedSyncGovernanceState(); } catch {}
        console.debug('Blended score sent to governance:', data?.updated?.blended_score);
        return true;
      }
    } catch (error) {
      console.warn('Failed to update governance blended score:', error);
    }
    return false;
  }

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
      try { localStorage.setItem('csrf_token', csrf); } catch {}
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
        try { this.debouncedSyncGovernanceState(); } catch {}
        console.debug('Blended score recomputed server-side:', data?.blended_score);
        return true;
      }
    } catch (error) {
      console.warn('Failed to recompute governance blended score:', error);
    }
    return false;
  }

  // Compute backend health based on governance timestamps (TTL in minutes)
  _updateBackendStatusFromGovernance(ttlMinutes = 30) {
    try {
      const gov = this.get('governance');
      const ts = gov?.ml_signals?.timestamp ? new Date(gov.ml_signals.timestamp).getTime() : (gov?.last_sync || 0);
      const age = ts ? (Date.now() - ts) : Number.POSITIVE_INFINITY;
      const ttlMs = ttlMinutes * 60 * 1000;
      const current = this.get('ui.apiStatus.backend') || 'unknown';
      const next = age === Number.POSITIVE_INFINITY ? current : (age > ttlMs ? 'stale' : 'healthy');
      if (next !== current) this.set('ui.apiStatus.backend', next);
    } catch {}
  }
  
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
        console.log('Decision approval result:', result);
        
        // Refresh governance state after approval
        this.debouncedSyncGovernanceState();
        return true;
      }
    } catch (error) {
      console.error('Failed to approve decision:', error);
      this.set('ui.errors', [...(this.get('ui.errors') || []), `Decision approval error: ${error.message}`]);
    }
    return false;
  }
  
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
        console.log('System freeze result:', result);
        
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
      console.error('Failed to freeze system:', error);
      this.set('ui.errors', [...(this.get('ui.errors') || []), `System freeze error: ${error.message}`]);
    }
    return false;
  }
  
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
        console.log('System unfreeze result:', result);
        
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
      console.error('Failed to unfreeze system:', error);
      this.set('ui.errors', [...(this.get('ui.errors') || []), `System unfreeze error: ${error.message}`]);
    }
    return false;
  }

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
        console.log('Governance mode change result:', result);
        
        // Refresh governance state after mode change
        this.debouncedSyncGovernanceState();
        return true;
      }
    } catch (error) {
      console.error('Failed to set governance mode:', error);
      this.set('ui.errors', [...(this.get('ui.errors') || []), `Mode change error: ${error.message}`]);
    }
    return false;
  }

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
        console.log('Decision proposal result:', result);
        
        // Refresh governance state after proposal
        this.debouncedSyncGovernanceState();
        return result;
      }
    } catch (error) {
      console.error('Failed to propose decision:', error);
      this.set('ui.errors', [...(this.get('ui.errors') || []), `Proposal error: ${error.message}`]);
    }
    return false;
  }
  
  // Get governance status for UI display
  getGovernanceStatus() {
    const gov = this.get('governance');
    return {
      state: gov.current_state || 'UNKNOWN',
      mode: gov.mode || 'manual',
      isActive: ['DRAFT', 'APPROVED', 'ACTIVE'].includes(gov.current_state),
      hasSignals: gov.ml_signals_timestamp !== null,
      contradictionLevel: gov.contradiction_index || 0,
      pendingCount: gov.pending_approvals || 0,
      needsAttention: gov.pending_approvals > 0 || gov.contradiction_index > 0.7,
      lastSync: gov.last_sync ? new Date(gov.last_sync) : null
    };
  }
}

// Global store instance
export const store = new RiskDashboardStore();

// Also make it available globally for non-module scripts
window.riskStore = store;

// Legacy aliases for existing dashboards
window.store = window.store || store;
window.__store = window.__store || store;

// Auto-persist on changes (debounced)
let persistTimeout;
store.subscribe(() => {
  clearTimeout(persistTimeout);
  persistTimeout = setTimeout(() => store.persist(), 1000);
});

