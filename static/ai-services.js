/**
 * Services Layer pour les interactions avec les backends IA
 * Architecture modulaire et réutilisable
 */

// Configuration des endpoints API
const AI_CONFIG = {
    baseUrl: globalConfig?.get('api_base_url') || 'http://localhost:8000',
    endpoints: {
        volatilityPredictor: '/api/ai/volatility/predict',
        marketRegime: '/api/ai/regime/current',
        correlationForecast: '/api/ai/correlation/forecast',
        sentiment: '/api/ai/sentiment/analysis',
        rebalancing: '/api/ai/rebalancing/suggest',
        // Health checks
        health: '/api/ai/health',
        models: '/api/ai/models/status'
    },
    timeout: 10000,
    retryAttempts: 3
};

/**
 * Classe utilitaire pour les requêtes HTTP
 */
class HttpClient {
    static async request(url, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            timeout: AI_CONFIG.timeout,
            ...options
        };

        try {
            const response = await fetch(url, defaultOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            debugLogger.error(`Request failed for ${url}:`, error);
            throw error;
        }
    }

    static async post(url, data, options = {}) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data),
            ...options
        });
    }

    static async get(url, options = {}) {
        return this.request(url, { method: 'GET', ...options });
    }
}

/**
 * Service de prédiction de volatilité
 */
class VolatilityPredictorService {
    constructor() {
        this.baseUrl = AI_CONFIG.baseUrl + AI_CONFIG.endpoints.volatilityPredictor;
        this.cache = new Map();
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    }

    /**
     * Prédire la volatilité pour des symboles
     */
    async predict(symbols, horizon = 24) {
        const cacheKey = `${symbols.join(',')}_${horizon}`;
        
        // Vérifier le cache
        if (this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.data;
            }
        }

        try {
            const data = await HttpClient.post(this.baseUrl, {
                symbols,
                horizon,
                features: ['price_volatility', 'volume_volatility', 'correlation_features']
            });

            // Mettre en cache
            this.cache.set(cacheKey, {
                data,
                timestamp: Date.now()
            });

            return data;
        } catch (error) {
            debugLogger.error('Volatility prediction failed:', error);
            throw error;
        }
    }

    /**
     * Obtenir l'historique des prédictions
     */
    async getHistory(symbol, days = 7) {
        const url = `${this.baseUrl}/history?symbol=${symbol}&days=${days}`;
        return await HttpClient.get(url);
    }

    /**
     * Obtenir les métriques de performance du modèle
     */
    async getMetrics() {
        const url = `${this.baseUrl}/metrics`;
        return await HttpClient.get(url);
    }
}

/**
 * Service de détection de régime de marché
 */
class MarketRegimeService {
    constructor() {
        this.baseUrl = AI_CONFIG.baseUrl + AI_CONFIG.endpoints.marketRegime;
        this.currentRegime = null;
        this.subscribers = new Set();
    }

    /**
     * Obtenir le régime actuel du marché
     */
    async getCurrentRegime(symbols = ['BTC', 'ETH']) {
        try {
            const data = await HttpClient.post(this.baseUrl, { symbols });
            this.currentRegime = data;
            this.notifySubscribers(data);
            return data;
        } catch (error) {
            debugLogger.error('Market regime detection failed:', error);
            throw error;
        }
    }

    /**
     * S'abonner aux changements de régime
     */
    subscribe(callback) {
        this.subscribers.add(callback);
        return () => this.subscribers.delete(callback);
    }

    /**
     * Notifier les abonnés
     */
    notifySubscribers(data) {
        this.subscribers.forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                debugLogger.error('Subscriber callback failed:', error);
            }
        });
    }

    /**
     * Démarrer la surveillance en temps réel
     */
    startRealTimeMonitoring(interval = 60000) { // 1 minute
        return setInterval(async () => {
            try {
                await this.getCurrentRegime();
            } catch (error) {
                debugLogger.error('Real-time regime monitoring error:', error);
            }
        }, interval);
    }

    /**
     * Obtenir l'historique des régimes
     */
    async getRegimeHistory(days = 30) {
        const url = `${this.baseUrl}/history?days=${days}`;
        return await HttpClient.get(url);
    }
}

/**
 * Service de prévision de corrélation
 */
class CorrelationForecastService {
    constructor() {
        this.baseUrl = AI_CONFIG.baseUrl + AI_CONFIG.endpoints.correlationForecast;
    }

    /**
     * Prévoir les corrélations entre assets
     */
    async forecast(symbols, horizon = 7) {
        try {
            return await HttpClient.post(this.baseUrl, {
                symbols,
                horizon_days: horizon,
                model_type: 'transformer'
            });
        } catch (error) {
            debugLogger.error('Correlation forecast failed:', error);
            throw error;
        }
    }

    /**
     * Obtenir la matrice de corrélation actuelle
     */
    async getCurrentCorrelations(symbols) {
        const url = `${this.baseUrl}/current`;
        return await HttpClient.post(url, { symbols });
    }

    /**
     * Analyser les breakdowns de corrélation
     */
    async analyzeBreakdowns(symbols, threshold = 0.3) {
        const url = `${this.baseUrl}/breakdowns`;
        return await HttpClient.post(url, { symbols, threshold });
    }
}

/**
 * Service d'analyse de sentiment
 */
class SentimentAnalysisService {
    constructor() {
        this.baseUrl = AI_CONFIG.baseUrl + AI_CONFIG.endpoints.sentiment;
        this.realTimeData = null;
    }

    /**
     * Analyser le sentiment pour des symboles
     */
    async analyze(symbols, sources = ['twitter', 'reddit', 'news']) {
        try {
            return await HttpClient.post(this.baseUrl, {
                symbols,
                sources,
                aggregation_window: '4h'
            });
        } catch (error) {
            debugLogger.error('Sentiment analysis failed:', error);
            throw error;
        }
    }

    /**
     * Obtenir le sentiment en temps réel
     */
    async getRealTimeSentiment(symbol) {
        const url = `${this.baseUrl}/realtime?symbol=${symbol}`;
        const data = await HttpClient.get(url);
        this.realTimeData = data;
        return data;
    }

    /**
     * Obtenir l'historique du sentiment
     */
    async getSentimentHistory(symbol, days = 7) {
        const url = `${this.baseUrl}/history?symbol=${symbol}&days=${days}`;
        return await HttpClient.get(url);
    }

    /**
     * Obtenir les alertes de sentiment
     */
    async getSentimentAlerts(threshold = 0.8) {
        const url = `${this.baseUrl}/alerts?threshold=${threshold}`;
        return await HttpClient.get(url);
    }
}

/**
 * Service de rééquilibrage automatisé
 */
class AutoRebalancingService {
    constructor() {
        this.baseUrl = AI_CONFIG.baseUrl + AI_CONFIG.endpoints.rebalancing;
        this.safetyChecks = true;
    }

    /**
     * Obtenir des suggestions de rééquilibrage
     */
    async getSuggestions(portfolio, constraints = {}) {
        const defaultConstraints = {
            max_single_trade_size: 0.1, // 10% max
            min_trade_size: 0.01, // 1% min
            risk_tolerance: 'moderate',
            rebalance_frequency: 'weekly',
            ...constraints
        };

        try {
            return await HttpClient.post(this.baseUrl, {
                portfolio,
                constraints: defaultConstraints,
                safety_checks: this.safetyChecks
            });
        } catch (error) {
            debugLogger.error('Rebalancing suggestions failed:', error);
            throw error;
        }
    }

    /**
     * Exécuter un rééquilibrage (simulation)
     */
    async simulateRebalancing(portfolio, suggestions) {
        const url = `${this.baseUrl}/simulate`;
        return await HttpClient.post(url, {
            portfolio,
            suggestions,
            include_costs: true,
            slippage_model: 'conservative'
        });
    }

    /**
     * Obtenir l'historique des rééquilibrages
     */
    async getRebalancingHistory(days = 30) {
        const url = `${this.baseUrl}/history?days=${days}`;
        return await HttpClient.get(url);
    }

    /**
     * Activer/désactiver les vérifications de sécurité
     */
    setSafetyChecks(enabled) {
        this.safetyChecks = enabled;
    }
}

/**
 * Service de santé et monitoring des modèles IA
 */
class AIHealthService {
    constructor() {
        this.healthUrl = AI_CONFIG.baseUrl + AI_CONFIG.endpoints.health;
        this.modelsUrl = AI_CONFIG.baseUrl + AI_CONFIG.endpoints.models;
    }

    /**
     * Vérifier la santé globale des services IA
     */
    async checkHealth() {
        try {
            return await HttpClient.get(this.healthUrl);
        } catch (error) {
            debugLogger.error('Health check failed:', error);
            return { status: 'error', error: error.message };
        }
    }

    /**
     * Obtenir le statut des modèles
     */
    async getModelsStatus() {
        try {
            return await HttpClient.get(this.modelsUrl);
        } catch (error) {
            debugLogger.error('Models status check failed:', error);
            return { models: [], status: 'error' };
        }
    }

    /**
     * Redémarrer un modèle spécifique
     */
    async restartModel(modelName) {
        const url = `${this.modelsUrl}/${modelName}/restart`;
        return await HttpClient.post(url);
    }
}

/**
 * Gestionnaire principal des services IA
 */
class AIServiceManager {
    constructor() {
        this.volatilityService = new VolatilityPredictorService();
        this.regimeService = new MarketRegimeService();
        this.correlationService = new CorrelationForecastService();
        this.sentimentService = new SentimentAnalysisService();
        this.rebalancingService = new AutoRebalancingService();
        this.healthService = new AIHealthService();
        
        this.isInitialized = false;
        this.healthCheckInterval = null;
    }

    /**
     * Initialiser tous les services
     */
    async initialize() {
        (window.debugLogger?.debug || console.log)('🤖 Initializing AI Services...');
        
        try {
            // Vérifier la santé des services
            const health = await this.healthService.checkHealth();
            (window.debugLogger?.debug || console.log)('Health check:', health);

            // Démarrer la surveillance des régimes de marché
            this.regimeService.startRealTimeMonitoring();

            // Démarrer les vérifications de santé périodiques
            this.startHealthMonitoring();

            this.isInitialized = true;
            (window.debugLogger?.info || console.log)('✅ AI Services initialized successfully');
            
            return { success: true, health };
        } catch (error) {
            debugLogger.error('❌ AI Services initialization failed:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Démarrer la surveillance de santé
     */
    startHealthMonitoring(interval = 300000) { // 5 minutes
        this.healthCheckInterval = setInterval(async () => {
            try {
                const health = await this.healthService.checkHealth();
                if (health.status !== 'healthy') {
                    (window.debugLogger?.warn || console.warn)('⚠️  AI Services health issue detected:', health);
                    // Émettre un événement pour l'UI
                    window.dispatchEvent(new CustomEvent('aiHealthWarning', { 
                        detail: health 
                    }));
                }
            } catch (error) {
                debugLogger.error('Health monitoring error:', error);
            }
        }, interval);
    }

    /**
     * Arrêter la surveillance
     */
    stopHealthMonitoring() {
        if (this.healthCheckInterval) {
            clearInterval(this.healthCheckInterval);
            this.healthCheckInterval = null;
        }
    }

    /**
     * Obtenir un résumé complet de l'état des services IA
     */
    async getFullStatus() {
        const [health, modelsStatus] = await Promise.all([
            this.healthService.checkHealth(),
            this.healthService.getModelsStatus()
        ]);

        return {
            health,
            models: modelsStatus,
            regime: this.regimeService.currentRegime,
            initialized: this.isInitialized,
            timestamp: new Date().toISOString()
        };
    }

    /**
     * Nettoyer les ressources
     */
    dispose() {
        this.stopHealthMonitoring();
        (window.debugLogger?.debug || console.log)('🔄 AI Services disposed');
    }
}

// Instance globale du gestionnaire
window.aiServiceManager = new AIServiceManager();

// Auto-initialisation
document.addEventListener('DOMContentLoaded', async () => {
    if (window.location.pathname.includes('ai-dashboard') || 
        window.location.search.includes('ai=true')) {
        await window.aiServiceManager.initialize();
    }
});

// Export pour utilisation en modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        AIServiceManager,
        VolatilityPredictorService,
        MarketRegimeService,
        CorrelationForecastService,
        SentimentAnalysisService,
        AutoRebalancingService,
        AIHealthService,
        AI_CONFIG
    };
}