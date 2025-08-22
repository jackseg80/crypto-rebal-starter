/**
 * Configuration Globale Centralisée - Crypto Rebalancer
 * 
 * Ce module gère la configuration partagée entre toutes les pages.
 * Utilise localStorage pour la persistance.
 */

// Configuration par défaut
const DEFAULT_SETTINGS = {
  data_source: 'cointracking',
  pricing: 'local',
  display_currency: 'USD',
  min_usd_threshold: 1.00,
  coingecko_api_key: '',
  cointracking_api_key: '',
  cointracking_api_secret: '',
  api_base_url: 'http://127.0.0.1:8000',
  refresh_interval: 5,
  enable_coingecko_classification: true,
  enable_portfolio_snapshots: true,
  enable_performance_tracking: true,
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
      console.log('Configuration sauvegardée');
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
    this.settings[key] = value;
    this.save();
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

// Événements pour synchronisation cross-tab
window.addEventListener('storage', (e) => {
  if (e.key === 'crypto_rebalancer_settings') {
    globalConfig.load();
    // Déclencher événement personnalisé pour les pages qui écoutent
    window.dispatchEvent(new CustomEvent('configChanged', {
      detail: globalConfig.getAll()
    }));
  }
});

console.log('🚀 Configuration globale chargée:', globalConfig.getAll());
