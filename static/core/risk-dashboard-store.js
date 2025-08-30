/**
 * Store ultra-simple pour Risk Dashboard CCS
 * Objet observable basique avec pub/sub minimal
 */

export class RiskDashboardStore {
  constructor() {
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
        const { ccs, cycle, targets, timestamp } = JSON.parse(saved);
        
        // Only restore if not too old (1 hour max)
        if (Date.now() - timestamp < 60 * 60 * 1000) {
          if (ccs) this.state.ccs = { ...this.state.ccs, ...ccs };
          if (cycle) this.state.cycle = { ...this.state.cycle, ...cycle };
          if (targets) this.state.targets = { ...this.state.targets, ...targets };
          
          console.debug('State hydrated from localStorage');
          this._notify();
        }
      }
    } catch (error) {
      console.warn('Failed to hydrate state:', error);
    }
  }
}

// Global store instance
export const store = new RiskDashboardStore();

// Auto-persist on changes (debounced)
let persistTimeout;
store.subscribe(() => {
  clearTimeout(persistTimeout);
  persistTimeout = setTimeout(() => store.persist(), 1000);
});
