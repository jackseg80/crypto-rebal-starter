/**
 * Configuration Globale Centralisée - Crypto Rebalancer
 * 
 * Ce module gère la configuration partagée entre toutes les pages.
 * Utilise localStorage pour la persistance.
 */

// Configuration par défaut
// Helper: detect sensible default API base depending on where the page runs
function detectDefaultApiBase() {
  try {
    const origin = (typeof window !== 'undefined' && window.location && window.location.origin) ? window.location.origin : '';
    if (origin && (origin.startsWith('http://') || origin.startsWith('https://'))) {
      return origin; // use same origin by default
    }
  } catch (_) { /* ignore */ }
  return 'http://127.0.0.1:8000';
}

// Source de vérité centralisée des sources de données disponibles
// Ajoutez/retirez des entrées ici pour les rendre disponibles partout
window.DATA_SOURCES = {
  stub_conservative: { label: 'Démo Conservative', icon: '🛡️', kind: 'stub' },
  stub_balanced:     { label: 'Démo Équilibrée',  icon: '⚖️', kind: 'stub' },
  stub_shitcoins:    { label: 'Démo Risquée',      icon: '🎲', kind: 'stub' },
  cointracking:      { label: 'CoinTracking CSV',  icon: '📄', kind: 'csv' },
  cointracking_api:  { label: 'CoinTracking API',  icon: '🌐', kind: 'api' }
};

/**
 * Récupère l'utilisateur actuel depuis le système de navigation
 * @returns {string} ID de l'utilisateur actuel
 */
window.getCurrentUser = function() {
  // Récupérer depuis localStorage (géré par nav.js)
  const activeUser = localStorage.getItem('activeUser');
  if (activeUser) {
    return activeUser;
  }

  // Fallback: essayer de récupérer depuis le sélecteur d'utilisateur
  const userSelector = document.getElementById('user-selector');
  if (userSelector && userSelector.value) {
    return userSelector.value;
  }

  // Fallback final: demo
  return 'demo';
};

// Ordre d'affichage par défaut
window.DATA_SOURCE_ORDER = [
  'stub_conservative',
  'stub_balanced',
  'stub_shitcoins',
  'cointracking',
  'cointracking_api'
];

// Helpers d'accès
window.getDataSourceKeys = function() {
  const keys = Array.isArray(window.DATA_SOURCE_ORDER) && window.DATA_SOURCE_ORDER.length
    ? window.DATA_SOURCE_ORDER.slice()
    : Object.keys(window.DATA_SOURCES);
  // Filtrer les clés inconnues
  return keys.filter(k => !!window.DATA_SOURCES[k]);
};

window.getDataSourceLabel = function(key) {
  const meta = window.DATA_SOURCES[key];
  if (!meta) return key;
  return `${meta.icon || ''} ${meta.label || key}`.trim();
};

window.isValidDataSource = function(key) {
  return !!window.DATA_SOURCES[key];
};

const DEFAULT_SETTINGS = {
  data_source: 'stub_balanced',
  pricing: 'local',
  display_currency: 'USD',
  min_usd_threshold: 1.00,
  coingecko_api_key: '',
  cointracking_api_key: '',
  cointracking_api_secret: '',
  fred_api_key: '',
  api_base_url: detectDefaultApiBase(),
  // Admin/debug access for protected endpoints (dev only)
  admin_key: '',
  refresh_interval: 5,
  enable_coingecko_classification: true,
  enable_portfolio_snapshots: true,
  enable_performance_tracking: true,
  // Thème centralisé
  theme: 'auto', // 'auto', 'light', 'dark'
  // Mode debug pour accès aux tests
  debug_mode: false,
  // État du workflow
  has_generated_plan: false,
  unknown_aliases_count: 0,
  last_plan_timestamp: null,
  // Persistance du dernier plan
  last_plan_data: null
};

class GlobalConfig {
  constructor() {
    this.settings = { ...DEFAULT_SETTINGS };
    this.load();
  }

  /**
   * Charge la configuration depuis localStorage
   */
  load() {
    try {
      const saved = localStorage.getItem('crypto_rebalancer_settings');
      if (saved) {
        const parsed = JSON.parse(saved);
        this.settings = { ...DEFAULT_SETTINGS, ...parsed };
        // Ensure api_base_url is always set to a usable default if missing/empty
        if (!this.settings.api_base_url) {
          this.settings.api_base_url = detectDefaultApiBase();
        }
      }
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('Erreur chargement configuration:', error);
      this.settings = { ...DEFAULT_SETTINGS };
    }
  }

  /**
   * Sauvegarde la configuration dans localStorage
   */
  save() {
    try {
      localStorage.setItem('crypto_rebalancer_settings', JSON.stringify(this.settings));
      console.debug('Configuration sauvegardée');
    } catch (error) {
      debugLogger.error('Erreur sauvegarde configuration:', error);
    }
  }

  /**
   * Récupère une valeur de configuration
   */
  get(key) {
    return this.settings[key];
  }

  /**
   * Définit une valeur de configuration
   */
  set(key, value) {
    const oldValue = this.settings[key];
    this.settings[key] = value;
    this.save();
    
    // Émettre un événement si la valeur a changé
    if (oldValue !== value) {
      this.emitConfigChange(key, value, oldValue);
    }
  }
  
  /**
   * Émet un événement de changement de configuration
   */
  emitConfigChange(key, newValue, oldValue) {
    const event = new CustomEvent('configChanged', {
      detail: { key, newValue, oldValue }
    });
    window.dispatchEvent(event);
    
    // Événement spécifique pour les changements de source de données
    if (key === 'data_source') {
      const dataSourceEvent = new CustomEvent('dataSourceChanged', {
        detail: { newSource: newValue, oldSource: oldValue }
      });
      window.dispatchEvent(dataSourceEvent);

      // Auto-invalidation des caches quand la source change
      if (oldValue && oldValue !== newValue) {
        (window.debugLogger?.debug || console.log)(`🔄 Global config data source changed: ${oldValue} -> ${newValue}, clearing caches`);

        // Vider le cache balance pour tous les utilisateurs
        if (typeof balanceCache !== 'undefined') {
          balanceCache.clear();
        }

        // Vider les caches localStorage
        try {
          const cacheKeys = Object.keys(localStorage).filter(key =>
            key.startsWith('cache:') ||
            key.includes('risk_score') ||
            key.includes('balance_') ||
            key.includes('portfolio_')
          );
          cacheKeys.forEach(key => localStorage.removeItem(key));
          (window.debugLogger?.debug || console.log)(`🧹 Cleared ${cacheKeys.length} localStorage cache entries`);
        } catch (e) {
          console.debug('Cache clearing error (non-critical):', e);
        }
      }
    }
    
    // Événement spécifique pour les changements de thème
    if (key === 'theme') {
      const themeEvent = new CustomEvent('themeChanged', {
        detail: { newTheme: newValue, oldTheme: oldValue }
      });
      window.dispatchEvent(themeEvent);
    }
  }

  /**
   * Récupère toute la configuration
   */
  getAll() {
    return { ...this.settings };
  }

  /**
   * Met à jour plusieurs valeurs à la fois
   */
  update(updates) {
    this.settings = { ...this.settings, ...updates };
    this.save();
  }

  /**
   * Remet la configuration par défaut
   */
  reset() {
    this.settings = { ...DEFAULT_SETTINGS };
    localStorage.removeItem('crypto_rebalancer_settings');
  }

  /**
   * Construit l'URL API avec les paramètres par défaut
   */
  getApiUrl(endpoint, additionalParams = {}) {
    const base = this.settings.api_base_url;

    // Normalize endpoint to avoid /api/api duplication
    let normalizedEndpoint = endpoint;
    if (base.endsWith('/api') && /^\/+api(\/|$)/i.test(endpoint)) {
      normalizedEndpoint = endpoint.replace(/^\/+api/, '');
      if (!normalizedEndpoint.startsWith('/')) {
        normalizedEndpoint = '/' + normalizedEndpoint;
      }
    }

    const url = new URL(normalizedEndpoint, base.endsWith('/') ? base : base + '/');

    const defaults = {
      source: this.settings.data_source,
      pricing: this.settings.pricing,
      min_usd: this.settings.min_usd_threshold
    };

    const all = { ...defaults, ...additionalParams };
    Object.entries(all).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
    });

    return url.toString();
  }

  /**
   * Effectue une requête API avec la configuration globale
   */
  async apiRequest(endpoint, options = {}) {
    const url = this.getApiUrl(endpoint, options.params || {});

    // Ajouter automatiquement le header X-User
    const activeUser = localStorage.getItem('activeUser') || 'demo';

    const requestOptions = {
      ...options, // ← d'abord
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-User': activeUser,
        ...(options.headers || {})
      }
    };
    delete requestOptions.params;
    const response = await fetch(url, requestOptions);
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    return await response.json();
  }

  /**
   * Teste la connexion avec la configuration actuelle
   */
  async testConnection() {
    try {
      const health = await this.apiRequest('/healthz');
      const balances = await this.apiRequest('/balances/current');

      return {
        backend: health ? 'OK' : 'Erreur',
        balances: balances?.items?.length > 0 ? `OK (${balances.items.length} assets)` : 'Vide',
        source: balances?.source_used || 'Inconnue'
      };
    } catch (error) {
      return {
        backend: `Erreur: ${error.message}`,
        balances: 'N/A',
        source: 'N/A'
      };
    }
  }

  /**
   * Valide la configuration actuelle
   */
  validate() {
    const issues = [];

    if (!this.settings.api_base_url) {
      issues.push('URL API manquante');
    }

    if (this.settings.data_source === 'cointracking_api' && (!this.settings.cointracking_api_key || !this.settings.cointracking_api_secret)) {
      issues.push('Clé API + Secret CoinTracking requis pour la source API');
    }

    if (this.settings.min_usd_threshold < 0) {
      issues.push('Seuil minimum USD doit être positif');
    }

    return {
      valid: issues.length === 0,
      issues
    };
  }

  /**
   * Exporte la configuration vers un fichier JSON
   */
  export() {
    const blob = new Blob([JSON.stringify(this.settings, null, 2)], {
      type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `crypto-rebalancer-config-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  /**
   * Importe la configuration depuis un fichier JSON
   */
  async importFromFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const imported = JSON.parse(e.target.result);
          this.settings = { ...DEFAULT_SETTINGS, ...imported };
          this.save();
          resolve(this.settings);
        } catch (error) {
          reject(new Error(`Erreur import: ${error.message}`));
        }
      };
      reader.onerror = () => reject(new Error('Erreur lecture fichier'));
      reader.readAsText(file);
    });
  }

  /**
   * Marque qu'un plan a été généré avec succès
   */
  markPlanGenerated(unknownAliasesCount = 0, planData = null) {
    this.set('has_generated_plan', true);
    this.set('unknown_aliases_count', unknownAliasesCount);
    this.set('last_plan_timestamp', Date.now());

    // Sauvegarder les données du plan pour persistance
    if (planData) {
      this.set('last_plan_data', planData);
    }

    // Déclencher un événement pour mettre à jour la navigation
    window.dispatchEvent(new CustomEvent('planGenerated', {
      detail: {
        unknownAliasesCount,
        timestamp: Date.now()
      }
    }));
  }

  /**
   * Vérifie si un plan a été généré
   */
  hasPlan() {
    return this.settings.has_generated_plan === true;
  }

  /**
   * Retourne le nombre d'unknown aliases du dernier plan
   */
  getUnknownAliasesCount() {
    return this.settings.unknown_aliases_count || 0;
  }

  /**
   * Retourne les données du dernier plan généré
   */
  getLastPlanData() {
    return this.settings.last_plan_data;
  }

  /**
   * Remet à zéro l'état du plan (utile pour debug/reset)
   */
  resetPlanState() {
    this.set('has_generated_plan', false);
    this.set('unknown_aliases_count', 0);
    this.set('last_plan_timestamp', null);
    this.set('last_plan_data', null);

    // Déclencher un événement pour mettre à jour la navigation
    window.dispatchEvent(new CustomEvent('planReset'));
  }

  /**
   * Récupère le thème effectif (résout 'auto' vers 'light'/'dark')
   */
  getEffectiveTheme() {
    const theme = this.settings.theme;
    if (theme === 'auto') {
      // Détecter les préférences système
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark';
      } else {
        return 'light';
      }
    }
    return theme;
  }

  /**
   * Définit le thème et l'applique immédiatement
   */
  setTheme(theme) {
    this.set('theme', theme);
    this.applyTheme();
  }

  /**
   * Applique le thème effectif au document
   */
  applyTheme() {
    const effectiveTheme = this.getEffectiveTheme();
    document.documentElement.setAttribute('data-theme', effectiveTheme);
    
    // Sauvegarder le thème effectif pour les CSS qui en ont besoin
    document.documentElement.style.setProperty('--effective-theme', effectiveTheme);
    
    console.debug(`🎨 Thème appliqué: ${this.settings.theme} (effectif: ${effectiveTheme})`);
  }

  /**
   * Active/désactive le mode debug
   */
  setDebugMode(enabled) {
    this.set('debug_mode', enabled);
    console.debug(`🛠️ Mode debug ${enabled ? 'activé' : 'désactivé'}`);
    
    // Émettre un événement spécifique pour le mode debug
    const event = new CustomEvent('debugModeChanged', {
      detail: { enabled }
    });
    window.dispatchEvent(event);
  }

  /**
   * Vérifie si le mode debug est actif (config + URL param)
   */
  isDebugMode() {
    // Vérifier le paramètre URL d'abord
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('debug') === 'true') {
      return true;
    }
    
    // Ensuite la configuration sauvegardée
    return this.get('debug_mode') === true;
  }

  /**
   * Toggle debug mode
   */
  toggleDebugMode() {
    const currentMode = this.get('debug_mode');
    this.setDebugMode(!currentMode);
    return !currentMode;
  }
}

// Instance globale
const globalConfig = new GlobalConfig();

// Export pour utilisation dans d'autres scripts
window.globalConfig = globalConfig;

// Fonctions utilitaires pour rétrocompatibilité
window.getGlobalSettings = () => globalConfig.getAll();
window.updateGlobalSetting = (key, value) => globalConfig.set(key, value);
window.getApiUrl = (endpoint, params) => globalConfig.getApiUrl(endpoint, params);
window.apiRequest = (endpoint, options) => globalConfig.apiRequest(endpoint, options);

// Fonctions de gestion du cache balance
window.clearBalanceCache = (user = null) => balanceCache.clear(user);
window.refreshBalanceData = () => window.loadBalanceData(true); // Force refresh

// Fonction pour forcer le refresh de toutes les données
window.refreshAllData = () => {
  (window.debugLogger?.debug || console.log)('🔄 Refreshing all data sources...');

  // Vider tous les caches
  if (typeof balanceCache !== 'undefined') balanceCache.clear();
  if (typeof window.clearBalanceCache === 'function') window.clearBalanceCache();

  // Vider localStorage
  const cacheKeys = Object.keys(localStorage).filter(key =>
    key.startsWith('cache:') ||
    key.includes('risk_score') ||
    key.includes('balance_') ||
    key.includes('portfolio_')
  );
  cacheKeys.forEach(key => localStorage.removeItem(key));

  // Forcer le refresh des données balance
  if (typeof window.loadBalanceData === 'function') {
    window.loadBalanceData(true);
  }

  // Émettre un événement pour que les autres composants se rechargent
  window.dispatchEvent(new CustomEvent('dataRefreshRequested'));

  (window.debugLogger?.debug || console.log)(`🧹 Cleared ${cacheKeys.length} cache entries and requested data refresh`);
};

/**
 * Cache intelligent pour les données de balance
 */
const balanceCache = {
  data: null,
  timestamp: 0,
  ttl: 2 * 60 * 1000, // 2 minutes TTL par défaut

  isValid(user = 'default') {
    if (!this.data || !this.data[user]) return false;
    return (Date.now() - this.data[user].timestamp) < this.ttl;
  },

  set(data, user = 'default') {
    if (!this.data) this.data = {};
    this.data[user] = { data, timestamp: Date.now() };
  },

  get(user = 'default') {
    return this.data?.[user]?.data || null;
  },

  clear(user = null) {
    if (user) {
      if (this.data) delete this.data[user];
    } else {
      this.data = null;
    }
  }
};

/**
 * Fonction centralisée pour charger les données de balance selon la source configurée
 */
window.loadBalanceData = async function(forceRefresh = false) {
  const dataSource = globalConfig.get('data_source');
  const apiBaseUrl = globalConfig.get('api_base_url');
  const currentUser = localStorage.getItem('activeUser') || 'demo';

  // Vérifier cache (sauf si refresh forcé)
  if (!forceRefresh && balanceCache.isValid(currentUser)) {
    console.debug(`🚀 Balance data loaded from cache (user: ${currentUser})`);
    return { success: true, data: balanceCache.get(currentUser), source: 'cache', cached: true };
  }

  // Cache miss ou refresh forcé - charger depuis API
  const timestamp = forceRefresh ? Date.now() : '';
  console.debug(`🔍 Loading balance data using source: ${dataSource} (user: ${currentUser}, cache-bust: ${timestamp || 'none'})`);

  try {
    switch (dataSource) {
      case 'cointracking_api': {
        // CoinTracking API via backend
        console.debug('📡 Using CoinTracking API source');
        const params = { source: 'cointracking_api' };
        if (forceRefresh) params._t = timestamp;
        const apiData = await globalConfig.apiRequest('/balances/current', { params });
        const result = { success: true, data: apiData, source: apiData?.source_used || 'cointracking_api' };
        balanceCache.set(apiData, currentUser);
        return result;
      }

      // All stub flavors should use the backend stub variants
      case 'stub':
      case 'stub_balanced':
      case 'stub_conservative':
      case 'stub_shitcoins': {
        const chosen = dataSource;
        console.debug(`🧪 Using stub data source: ${chosen}`);
        const params = { source: chosen };
        if (forceRefresh) params._t = timestamp;
        const stubData = await globalConfig.apiRequest('/balances/current', { params });
        const result = { success: true, data: stubData, source: stubData?.source_used || chosen };
        balanceCache.set(stubData, currentUser);
        return result;
      }

      case 'csv_0':
      case 'csv_1':
      case 'csv_2': {
        // User-specific CSV files via API backend
        console.debug(`📄 Using user CSV files via API (${dataSource})`);
        const params = { source: dataSource };
        if (forceRefresh) params._t = timestamp;
        const csvData = await globalConfig.apiRequest('/balances/current', { params });
        const result = { success: true, data: csvData, source: csvData?.source_used || dataSource };
        balanceCache.set(csvData, currentUser);
        return result;
      }

      case 'cointracking':
      default: {
        // Local CoinTracking CSV via API backend
        console.debug('📄 Using local CoinTracking CSV files via API');
        const params = { source: 'cointracking' };
        if (forceRefresh) params._t = timestamp;
        const csvData = await globalConfig.apiRequest('/balances/current', { params });
        const result = { success: true, data: csvData, source: csvData?.source_used || 'cointracking' };
        balanceCache.set(csvData, currentUser);
        return result;
      }
    }
  } catch (error) {
    debugLogger.error(`❌ Error loading balance data via API (source: ${dataSource}):`, error);
    (window.debugLogger?.debug || console.log)('🔄 Trying fallback: direct CSV file loading...');
    
    // Fallback: try to load CSV files directly
    try {
      const csvFiles = [
        'data/raw/CoinTracking - Current Balance.csv',
        'data/raw/CoinTracking - Balance by Exchange - 26.08.2025.csv'
      ];
      
      for (const csvFile of csvFiles) {
        try {
          (window.debugLogger?.debug || console.log)(`📄 Attempting to load: ${csvFile}`);
          const response = await fetch(csvFile);
          if (response.ok) {
            const csvText = await response.text();
            (window.debugLogger?.debug || console.log)(`✅ Successfully loaded ${csvFile} (${csvText.length} characters)`);
            return {
              success: true,
              csvText: csvText,
              source: 'csv_direct',
              file: csvFile
            };
          }
        } catch (fileError) {
          (window.debugLogger?.debug || console.log)(`⚠️ Could not load ${csvFile}:`, fileError.message);
        }
      }
      
      // Si aucun fichier CSV accessible et API échoué
      debugLogger.error('📊 No CSV files accessible and API failed.');

      // Pour les sources réelles (csv_*, cointracking_api), ne pas fallback vers stub
      if (dataSource.startsWith('csv_') || dataSource === 'cointracking_api') {
        debugLogger.error(`❌ Real data source '${dataSource}' failed, not falling back to stub`);
        return {
          success: false,
          error: `Failed to load data from source: ${dataSource}`,
          source: dataSource
        };
      }

      // Pour les sources stub ou legacy, fallback vers stub
      try {
        const stubFlavor = dataSource.startsWith('stub') ? dataSource : 'stub_balanced';
        (window.debugLogger?.debug || console.log)(`🔄 Falling back to stub: ${stubFlavor}`);
        const stubData = await globalConfig.apiRequest('/balances/current', {
          params: { source: stubFlavor, _t: timestamp }
        });
        (window.debugLogger?.info || console.log)('✅ Successfully loaded stub data from API');
        return { success: true, data: stubData, source: stubData?.source_used || stubFlavor };
      } catch (stubError) {
        debugLogger.error('❌ Stub data via API also failed:', stubError);
      }
      
      // Dernière option: retourner erreur - pas de données mockées
      return {
        success: false,
        error: `All data sources failed. Configure valid data source in settings: API=${error.message}`,
        source: 'none'
      };
      
    } catch (fallbackError) {
      debugLogger.error('❌ Fallback also failed:', fallbackError);
      return {
        success: false,
        error: `API failed: ${error.message}, Fallback failed: ${fallbackError.message}`,
        source: dataSource
      };
    }
  }
};

/**
 * Fonction pour parser les données CSV de balance (commune à toutes les pages)
 */
window.parseCSVBalances = function(csvText) {
  const cleanedText = csvText.replace(/^\ufeff/, '');
  const lines = cleanedText.split('\n');
  const balances = [];
  const minThreshold = globalConfig.get('min_usd_threshold') || 1.0;

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    try {
      const columns = window.parseCSVLine(line);
      if (columns.length >= 5) {
        const ticker = columns[0];
        const amount = parseFloat(columns[3]);
        const valueUSD = parseFloat(columns[4]);
        
        if (ticker && !isNaN(amount) && !isNaN(valueUSD) && valueUSD >= minThreshold) {
          balances.push({
            symbol: ticker.toUpperCase(),
            balance: amount,
            value_usd: valueUSD
          });
        }
      }
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('Error parsing CSV line:', error);
    }
  }

  return balances;
};

/**
 * Fonction pour parser une ligne CSV (gère les guillemets et points-virgules)
 */
window.parseCSVLine = function(line) {
  const result = [];
  let current = '';
  let inQuotes = false;
  
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ';' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  
  result.push(current);
  return result.map(item => item.replace(/^"|"$/g, ''));
};

// Événements pour synchronisation cross-tab
window.addEventListener('storage', (e) => {
  if (e.key === 'crypto_rebalancer_settings') {
    globalConfig.load();
    // Déclencher événement personnalisé pour les pages qui écoutent
    window.dispatchEvent(new CustomEvent('configChanged', {
      detail: globalConfig.getAll()
    }));
    // Réappliquer le thème après changement cross-tab
    globalConfig.applyTheme();
  }
});

// Écouter les changements de préférences système pour le thème auto
if (window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (globalConfig.get('theme') === 'auto') {
      globalConfig.applyTheme();
      // Émettre un événement pour que les pages se mettent à jour
      window.dispatchEvent(new CustomEvent('themeChanged', {
        detail: { 
          newTheme: 'auto', 
          oldTheme: 'auto',
          effectiveTheme: globalConfig.getEffectiveTheme()
        }
      }));
    }
  });
}

// Appliquer le thème au chargement
globalConfig.applyTheme();

console.debug('🚀 Configuration globale chargée:', globalConfig.getAll());

// ====== Currency conversion helper (USD -> display currency) ======
window.currencyManager = (function(){
  // Fallback rates (synchronized with backend, updated Oct 2025)
  const FALLBACK_RATES = {
    USD: 1.0,
    EUR: 0.920,    // 1 USD = 0.920 EUR (inverted from backend: 1 EUR = 1.087 USD)
    CHF: 0.880,    // 1 USD = 0.880 CHF (inverted from backend: 1 CHF = 1.136 USD)
    GBP: 0.769,    // 1 USD = 0.769 GBP (inverted from backend: 1 GBP = 1.30 USD)
    DKK: 6.849,    // 1 USD = 6.849 DKK
    SEK: 10.417,   // 1 USD = 10.417 SEK
    NOK: 10.753,   // 1 USD = 10.753 NOK
    JPY: 151.515,  // 1 USD = 151.515 JPY
    CAD: 1.389,    // 1 USD = 1.389 CAD
    AUD: 1.538,    // 1 USD = 1.538 AUD
    SGD: 1.333,    // 1 USD = 1.333 SGD
  };

  const rates = { ...FALLBACK_RATES };
  let fetching = null;
  let lastFetch = 0;
  const CACHE_TTL = 3600000; // 1 hour cache

  async function fetchAllRates() {
    // Fetch all rates from backend API
    try {
      const apiUrl = (typeof globalConfig !== 'undefined' && globalConfig.getApiUrl)
        ? globalConfig.getApiUrl('/api/fx/rates?base=USD')
        : 'http://localhost:8000/api/fx/rates?base=USD';

      const res = await fetch(apiUrl, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!res.ok) throw new Error('HTTP ' + res.status);

      const response = await res.json();

      if (response?.ok && response?.data?.rates) {
        const fetchedRates = response.data.rates;
        console.debug('✅ FX rates fetched from backend:', Object.keys(fetchedRates).length, 'currencies');

        // Update rates cache
        for (const [currency, rate] of Object.entries(fetchedRates)) {
          if (typeof rate === 'number' && rate > 0) {
            rates[currency] = rate;
          }
        }

        lastFetch = Date.now();
        return true;
      } else {
        throw new Error('Invalid response format');
      }
    } catch (error) {
      console.debug('⚠️ FX rates fetch failed, using fallback rates:', error.message);
      // Fallback rates already loaded
      return false;
    }
  }

  async function ensureRate(currency) {
    const cur = (currency || '').toUpperCase();
    if (!cur || cur === 'USD') { rates.USD = 1; return 1; }

    // Check if we need to refresh rates
    const now = Date.now();
    if (now - lastFetch > CACHE_TTL && !fetching) {
      // Fetch all rates if cache expired
      fetching = fetchAllRates();
    }

    // Wait for fetch if in progress
    if (fetching) {
      await fetching;
      fetching = null;
    }

    // Return rate (from cache or fallback)
    const rate = rates[cur];
    if (rate && rate > 0) {
      try {
        window.dispatchEvent(new CustomEvent('currencyRateUpdated', { detail: { currency: cur, rate } }));
      } catch (_) {}
      return rate;
    }

    // No rate available, return fallback
    const fallback = FALLBACK_RATES[cur] || 1;
    rates[cur] = fallback;
    return fallback;
  }

  function getRateSync(currency) {
    const cur = (currency || '').toUpperCase();
    if (!cur || cur === 'USD') return 1;
    // Return cached rate or fallback
    return (cur in rates && rates[cur] > 0) ? rates[cur] : (FALLBACK_RATES[cur] || 1);
  }

  // Preload rates on initialization
  try {
    // Pre-fetch all rates from backend on page load
    fetchAllRates().then(() => {
      console.debug('💱 Currency rates initialized from backend');
    }).catch(() => {
      console.debug('💱 Currency rates initialized with fallbacks');
    });

    // Preload display currency if not USD
    const cur = (typeof globalConfig !== 'undefined' && globalConfig.get('display_currency')) || 'USD';
    if (cur && cur !== 'USD') ensureRate(cur);

    // React on config changes
    window.addEventListener('configChanged', (ev) => {
      if (ev?.detail?.key === 'display_currency') {
        const c = ev.detail.newValue || ev.detail.value || globalConfig.get('display_currency');
        if (c && c !== 'USD') ensureRate(c);
      }
    });
  } catch (_) {}

  return { ensureRate, getRateSync };
})();
