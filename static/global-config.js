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
      console.warn('Erreur chargement configuration:', error);
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
      console.error('Erreur sauvegarde configuration:', error);
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
    const url = new URL(endpoint, base.endsWith('/') ? base : base + '/');

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
    const requestOptions = {
      ...options, // ← d'abord
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
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

/**
 * Fonction centralisée pour charger les données de balance selon la source configurée
 */
window.loadBalanceData = async function() {
  const dataSource = globalConfig.get('data_source');
  const apiBaseUrl = globalConfig.get('api_base_url');

  // Add cache-busting timestamp to prevent browser caching
  const timestamp = Date.now();
  console.debug(`🔍 Loading balance data using source: ${dataSource} (cache-bust: ${timestamp})`);

  try {
    switch (dataSource) {
      case 'cointracking_api': {
        // CoinTracking API via backend
        console.debug('📡 Using CoinTracking API source');
        const apiResponse = await fetch(`${apiBaseUrl}/balances/current?source=cointracking_api&_t=${timestamp}`);
        if (!apiResponse.ok) throw new Error(`API Error: ${apiResponse.status}`);
        const apiData = await apiResponse.json();
        return { success: true, data: apiData, source: apiData?.source_used || 'cointracking_api' };
      }

      // All stub flavors should use the backend stub variants
      case 'stub':
      case 'stub_balanced':
      case 'stub_conservative':
      case 'stub_shitcoins': {
        const chosen = dataSource;
        console.debug(`🧪 Using stub data source: ${chosen}`);
        const stubResponse = await fetch(`${apiBaseUrl}/balances/current?source=${chosen}&_t=${timestamp}`);
        if (!stubResponse.ok) throw new Error(`Stub Error: ${stubResponse.status}`);
        const stubData = await stubResponse.json();
        return { success: true, data: stubData, source: stubData?.source_used || chosen };
      }

      case 'cointracking':
      default: {
        // Local CoinTracking CSV via API backend
        console.debug('📄 Using local CoinTracking CSV files via API');
        const csvResponse = await fetch(`${apiBaseUrl}/balances/current?source=cointracking&_t=${timestamp}`);
        if (!csvResponse.ok) throw new Error(`CSV API Error: ${csvResponse.status}`);
        const csvData = await csvResponse.json();
        return { success: true, data: csvData, source: csvData?.source_used || 'cointracking' };
      }
    }
  } catch (error) {
    console.error(`❌ Error loading balance data via API (source: ${dataSource}):`, error);
    console.log('🔄 Trying fallback: direct CSV file loading...');
    
    // Fallback: try to load CSV files directly
    try {
      const csvFiles = [
        'data/raw/CoinTracking - Current Balance.csv',
        'data/raw/CoinTracking - Balance by Exchange - 26.08.2025.csv'
      ];
      
      for (const csvFile of csvFiles) {
        try {
          console.log(`📄 Attempting to load: ${csvFile}`);
          const response = await fetch(csvFile);
          if (response.ok) {
            const csvText = await response.text();
            console.log(`✅ Successfully loaded ${csvFile} (${csvText.length} characters)`);
            return {
              success: true,
              csvText: csvText,
              source: 'csv_direct',
              file: csvFile
            };
          }
        } catch (fileError) {
          console.log(`⚠️ Could not load ${csvFile}:`, fileError.message);
        }
      }
      
      // Si aucun fichier CSV accessible et API échoué, retourner erreur
      console.error('📊 No CSV files accessible and API failed. Using configured stub data source.');
      
      // Forcer l'utilisation de stub data via l'API si configuré
      try {
        // Use the current stub flavor if applicable, else default to plain 'stub'
        const cfg = globalConfig.get('data_source');
        const stubFlavor = (cfg && cfg.startsWith('stub')) ? cfg : 'stub';
        const stubResponse = await fetch(`${globalConfig.get('api_base_url')}/balances/current?source=${stubFlavor}&_t=${timestamp}`);
        if (stubResponse.ok) {
          const stubData = await stubResponse.json();
          console.log('✅ Successfully loaded stub data from API');
          return { success: true, data: stubData, source: stubData?.source_used || stubFlavor };
        }
      } catch (stubError) {
        console.error('❌ Stub data via API also failed:', stubError);
      }
      
      // Dernière option: retourner erreur - pas de données mockées
      return {
        success: false,
        error: `All data sources failed. Configure valid data source in settings: API=${error.message}`,
        source: 'none'
      };
      
    } catch (fallbackError) {
      console.error('❌ Fallback also failed:', fallbackError);
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
      console.warn('Error parsing CSV line:', error);
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
