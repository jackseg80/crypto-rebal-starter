/**
 * Gestionnaire d'état centralisé pour les données IA en temps réel
 * Architecture événementielle avec cache et synchronisation
 */

/**
 * Classe EventEmitter simplifiée pour la gestion des événements
 */
class EventEmitter {
    constructor() {
        this.events = {};
    }

    on(event, callback) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
        return () => this.off(event, callback);
    }

    off(event, callback) {
        if (!this.events[event]) return;
        this.events[event] = this.events[event].filter(cb => cb !== callback);
    }

    emit(event, data) {
        if (!this.events[event]) return;
        this.events[event].forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error(`Event callback error for ${event}:`, error);
            }
        });
    }

    once(event, callback) {
        const unsubscribe = this.on(event, (data) => {
            callback(data);
            unsubscribe();
        });
        return unsubscribe;
    }
}

/**
 * Cache intelligent avec TTL et invalidation
 */
class SmartCache {
    constructor() {
        this.cache = new Map();
        this.ttl = new Map();
        this.dependencies = new Map();
    }

    set(key, value, ttl = 300000, dependencies = []) { // 5 min par défaut
        this.cache.set(key, value);
        this.ttl.set(key, Date.now() + ttl);
        
        if (dependencies.length > 0) {
            this.dependencies.set(key, dependencies);
        }
    }

    get(key) {
        if (!this.cache.has(key)) return null;

        const expiry = this.ttl.get(key);
        if (expiry && Date.now() > expiry) {
            this.delete(key);
            return null;
        }

        return this.cache.get(key);
    }

    has(key) {
        return this.get(key) !== null;
    }

    delete(key) {
        this.cache.delete(key);
        this.ttl.delete(key);
        this.dependencies.delete(key);
    }

    invalidate(pattern) {
        const keysToDelete = [];
        
        for (const [key, deps] of this.dependencies.entries()) {
            if (deps.includes(pattern) || key.includes(pattern)) {
                keysToDelete.push(key);
            }
        }
        
        keysToDelete.forEach(key => this.delete(key));
    }

    clear() {
        this.cache.clear();
        this.ttl.clear();
        this.dependencies.clear();
    }

    size() {
        return this.cache.size;
    }
}

/**
 * Gestionnaire d'état principal pour les données IA
 */
class AIStateManager extends EventEmitter {
    constructor() {
        super();
        
        // Cache intelligent
        this.cache = new SmartCache();
        
        // État interne
        this.state = {
            volatility: new Map(),
            regime: null,
            correlations: new Map(),
            sentiment: new Map(),
            rebalancing: null,
            health: null
        };
        
        // Configuration
        this.config = {
            updateIntervals: {
                volatility: 60000,    // 1 minute
                regime: 30000,        // 30 secondes
                correlations: 300000, // 5 minutes
                sentiment: 120000,    // 2 minutes
                health: 60000         // 1 minute
            },
            cacheConfig: {
                volatility: 300000,   // 5 minutes
                regime: 180000,       // 3 minutes
                correlations: 600000, // 10 minutes
                sentiment: 240000,    // 4 minutes
                health: 60000         // 1 minute
            }
        };
        
        // Timers et abonnements
        this.timers = new Map();
        this.subscriptions = new Map();
        this.isInitialized = false;
        
        // Statistiques
        this.stats = {
            cacheHits: 0,
            cacheMisses: 0,
            apiCalls: 0,
            errors: 0,
            lastUpdate: null
        };
    }

    /**
     * Initialiser le gestionnaire d'état
     */
    async initialize() {
        console.log('🔄 Initializing AI State Manager...');
        
        try {
            // Vérifier la disponibilité des services IA
            if (!window.aiServiceManager) {
                throw new Error('AI Service Manager not available');
            }

            // Charger l'état initial
            await this.loadInitialState();
            
            // Démarrer les mises à jour automatiques
            this.startAutoUpdates();
            
            // Configuration des événements de nettoyage
            this.setupCleanupEvents();
            
            this.isInitialized = true;
            console.log('✅ AI State Manager initialized');
            this.emit('initialized', { timestamp: new Date() });
            
            return true;
        } catch (error) {
            console.error('❌ AI State Manager initialization failed:', error);
            this.emit('error', { type: 'initialization', error });
            return false;
        }
    }

    /**
     * Charger l'état initial
     */
    async loadInitialState() {
        const loadPromises = [
            this.updateHealthStatus(),
            this.updateMarketRegime()
        ];

        await Promise.allSettled(loadPromises);
    }

    /**
     * Démarrer les mises à jour automatiques
     */
    startAutoUpdates() {
        Object.entries(this.config.updateIntervals).forEach(([type, interval]) => {
            const timer = setInterval(() => {
                this.performUpdate(type);
            }, interval);
            
            this.timers.set(type, timer);
        });
    }

    /**
     * Effectuer une mise à jour spécifique
     */
    async performUpdate(type) {
        try {
            switch (type) {
                case 'volatility':
                    // Mise à jour seulement si on a des symboles suivis
                    if (this.getTrackedSymbols().length > 0) {
                        await this.updateVolatilityData();
                    }
                    break;
                case 'regime':
                    await this.updateMarketRegime();
                    break;
                case 'correlations':
                    if (this.getTrackedSymbols().length > 1) {
                        await this.updateCorrelationData();
                    }
                    break;
                case 'sentiment':
                    if (this.getTrackedSymbols().length > 0) {
                        await this.updateSentimentData();
                    }
                    break;
                case 'health':
                    await this.updateHealthStatus();
                    break;
            }
        } catch (error) {
            console.error(`Update failed for ${type}:`, error);
            this.stats.errors++;
            this.emit('error', { type: 'update', category: type, error });
        }
    }

    /**
     * === VOLATILITY DATA ===
     */
    async updateVolatilityData(symbols = null) {
        const targetSymbols = symbols || this.getTrackedSymbols();
        if (targetSymbols.length === 0) return;

        const cacheKey = `volatility_${targetSymbols.join(',')}_24`;
        
        if (this.cache.has(cacheKey)) {
            this.stats.cacheHits++;
            return this.cache.get(cacheKey);
        }

        try {
            this.stats.apiCalls++;
            const data = await window.aiServiceManager.volatilityService.predict(targetSymbols, 24);
            
            // Mettre à jour l'état
            targetSymbols.forEach(symbol => {
                if (data.predictions && data.predictions[symbol]) {
                    this.state.volatility.set(symbol, {
                        ...data.predictions[symbol],
                        timestamp: Date.now()
                    });
                }
            });
            
            // Mettre en cache
            this.cache.set(cacheKey, data, this.config.cacheConfig.volatility, ['volatility']);
            this.stats.cacheMisses++;
            
            // Émettre l'événement
            this.emit('volatility:updated', {
                symbols: targetSymbols,
                data: data,
                timestamp: Date.now()
            });
            
            return data;
        } catch (error) {
            console.error('Volatility update failed:', error);
            throw error;
        }
    }

    getVolatilityData(symbol) {
        return this.state.volatility.get(symbol) || null;
    }

    /**
     * === MARKET REGIME ===
     */
    async updateMarketRegime(symbols = ['BTC', 'ETH']) {
        const cacheKey = `regime_${symbols.join(',')}`;
        
        if (this.cache.has(cacheKey)) {
            this.stats.cacheHits++;
            return this.cache.get(cacheKey);
        }

        try {
            this.stats.apiCalls++;
            const data = await window.aiServiceManager.regimeService.getCurrentRegime(symbols);
            
            // Vérifier s'il y a un changement de régime
            const previousRegime = this.state.regime;
            const hasChanged = !previousRegime || 
                              previousRegime.regime?.type !== data.regime?.type;
            
            this.state.regime = {
                ...data,
                timestamp: Date.now()
            };
            
            // Mettre en cache
            this.cache.set(cacheKey, data, this.config.cacheConfig.regime, ['regime']);
            this.stats.cacheMisses++;
            
            // Émettre les événements
            this.emit('regime:updated', {
                data: data,
                changed: hasChanged,
                previous: previousRegime,
                timestamp: Date.now()
            });
            
            if (hasChanged) {
                this.emit('regime:changed', {
                    newRegime: data.regime,
                    oldRegime: previousRegime?.regime,
                    timestamp: Date.now()
                });
            }
            
            return data;
        } catch (error) {
            console.error('Market regime update failed:', error);
            throw error;
        }
    }

    getMarketRegime() {
        return this.state.regime;
    }

    /**
     * === CORRELATION DATA ===
     */
    async updateCorrelationData(symbols = null) {
        const targetSymbols = symbols || this.getTrackedSymbols();
        if (targetSymbols.length < 2) return;

        const cacheKey = `correlations_${targetSymbols.join(',')}`;
        
        if (this.cache.has(cacheKey)) {
            this.stats.cacheHits++;
            return this.cache.get(cacheKey);
        }

        try {
            this.stats.apiCalls++;
            const data = await window.aiServiceManager.correlationService.getCurrentCorrelations(targetSymbols);
            
            // Mettre à jour l'état
            const correlationKey = targetSymbols.sort().join('_');
            this.state.correlations.set(correlationKey, {
                ...data,
                symbols: targetSymbols,
                timestamp: Date.now()
            });
            
            // Mettre en cache
            this.cache.set(cacheKey, data, this.config.cacheConfig.correlations, ['correlations']);
            this.stats.cacheMisses++;
            
            // Émettre l'événement
            this.emit('correlations:updated', {
                symbols: targetSymbols,
                data: data,
                timestamp: Date.now()
            });
            
            return data;
        } catch (error) {
            console.error('Correlation update failed:', error);
            throw error;
        }
    }

    getCorrelationData(symbols) {
        const key = symbols.sort().join('_');
        return this.state.correlations.get(key) || null;
    }

    /**
     * === SENTIMENT DATA ===
     */
    async updateSentimentData(symbols = null) {
        const targetSymbols = symbols || this.getTrackedSymbols();
        if (targetSymbols.length === 0) return;

        const cacheKey = `sentiment_${targetSymbols.join(',')}`;
        
        if (this.cache.has(cacheKey)) {
            this.stats.cacheHits++;
            return this.cache.get(cacheKey);
        }

        try {
            this.stats.apiCalls++;
            const data = await window.aiServiceManager.sentimentService.analyze(targetSymbols);
            
            // Mettre à jour l'état pour chaque symbole
            targetSymbols.forEach(symbol => {
                if (data.sentiment && data.sentiment[symbol]) {
                    this.state.sentiment.set(symbol, {
                        ...data.sentiment[symbol],
                        timestamp: Date.now()
                    });
                }
            });
            
            // Mettre en cache
            this.cache.set(cacheKey, data, this.config.cacheConfig.sentiment, ['sentiment']);
            this.stats.cacheMisses++;
            
            // Émettre l'événement
            this.emit('sentiment:updated', {
                symbols: targetSymbols,
                data: data,
                timestamp: Date.now()
            });
            
            return data;
        } catch (error) {
            console.error('Sentiment update failed:', error);
            throw error;
        }
    }

    getSentimentData(symbol) {
        return this.state.sentiment.get(symbol) || null;
    }

    /**
     * === HEALTH STATUS ===
     */
    async updateHealthStatus() {
        const cacheKey = 'health_status';
        
        if (this.cache.has(cacheKey)) {
            this.stats.cacheHits++;
            return this.cache.get(cacheKey);
        }

        try {
            this.stats.apiCalls++;
            const data = await window.aiServiceManager.healthService.checkHealth();
            
            this.state.health = {
                ...data,
                timestamp: Date.now()
            };
            
            // Mettre en cache
            this.cache.set(cacheKey, data, this.config.cacheConfig.health, ['health']);
            this.stats.cacheMisses++;
            
            // Émettre l'événement
            this.emit('health:updated', {
                data: data,
                timestamp: Date.now()
            });
            
            return data;
        } catch (error) {
            console.error('Health status update failed:', error);
            this.state.health = {
                status: 'error',
                error: error.message,
                timestamp: Date.now()
            };
            throw error;
        }
    }

    getHealthStatus() {
        return this.state.health;
    }

    /**
     * === REBALANCING ===
     */
    async updateRebalancingSuggestions(portfolio) {
        const cacheKey = `rebalancing_${JSON.stringify(portfolio).substring(0, 50)}`;
        
        if (this.cache.has(cacheKey)) {
            this.stats.cacheHits++;
            return this.cache.get(cacheKey);
        }

        try {
            this.stats.apiCalls++;
            const data = await window.aiServiceManager.rebalancingService.getSuggestions(portfolio);
            
            this.state.rebalancing = {
                ...data,
                portfolio,
                timestamp: Date.now()
            };
            
            // Mettre en cache (courte durée pour les suggestions)
            this.cache.set(cacheKey, data, 120000, ['rebalancing']); // 2 minutes
            this.stats.cacheMisses++;
            
            // Émettre l'événement
            this.emit('rebalancing:updated', {
                data: data,
                portfolio,
                timestamp: Date.now()
            });
            
            return data;
        } catch (error) {
            console.error('Rebalancing update failed:', error);
            throw error;
        }
    }

    getRebalancingSuggestions() {
        return this.state.rebalancing;
    }

    /**
     * === GESTION DES SYMBOLES SUIVIS ===
     */
    addTrackedSymbol(symbol) {
        const tracked = this.getTrackedSymbols();
        if (!tracked.includes(symbol)) {
            tracked.push(symbol);
            localStorage.setItem('ai_tracked_symbols', JSON.stringify(tracked));
            
            // Invalider les caches concernés
            this.cache.invalidate(symbol);
            
            this.emit('symbols:updated', { symbols: tracked, added: symbol });
        }
    }

    removeTrackedSymbol(symbol) {
        const tracked = this.getTrackedSymbols();
        const index = tracked.indexOf(symbol);
        if (index > -1) {
            tracked.splice(index, 1);
            localStorage.setItem('ai_tracked_symbols', JSON.stringify(tracked));
            
            // Nettoyer l'état
            this.state.volatility.delete(symbol);
            this.state.sentiment.delete(symbol);
            
            // Invalider les caches
            this.cache.invalidate(symbol);
            
            this.emit('symbols:updated', { symbols: tracked, removed: symbol });
        }
    }

    getTrackedSymbols() {
        try {
            return JSON.parse(localStorage.getItem('ai_tracked_symbols') || '["BTC", "ETH"]');
        } catch {
            return ['BTC', 'ETH'];
        }
    }

    setTrackedSymbols(symbols) {
        localStorage.setItem('ai_tracked_symbols', JSON.stringify(symbols));
        this.cache.clear(); // Nettoyer complètement le cache
        this.emit('symbols:updated', { symbols });
    }

    /**
     * === UTILITAIRES ===
     */
    getStats() {
        return {
            ...this.stats,
            cacheSize: this.cache.size(),
            activeTimers: this.timers.size,
            lastUpdate: this.stats.lastUpdate,
            uptime: this.isInitialized ? Date.now() - this.stats.lastUpdate : 0
        };
    }

    getFullState() {
        return {
            volatility: Object.fromEntries(this.state.volatility),
            regime: this.state.regime,
            correlations: Object.fromEntries(this.state.correlations),
            sentiment: Object.fromEntries(this.state.sentiment),
            rebalancing: this.state.rebalancing,
            health: this.state.health,
            trackedSymbols: this.getTrackedSymbols(),
            stats: this.getStats()
        };
    }

    /**
     * Force la mise à jour de toutes les données
     */
    async forceUpdate() {
        console.log('🔄 Force updating all AI data...');
        
        // Vider le cache
        this.cache.clear();
        
        // Effectuer toutes les mises à jour
        const updates = [
            this.updateHealthStatus(),
            this.updateMarketRegime(),
            this.updateVolatilityData(),
            this.updateCorrelationData(),
            this.updateSentimentData()
        ];
        
        const results = await Promise.allSettled(updates);
        
        const failed = results.filter(result => result.status === 'rejected');
        if (failed.length > 0) {
            console.warn(`${failed.length} updates failed during force update`);
        }
        
        this.emit('force:updated', { 
            successful: results.length - failed.length, 
            failed: failed.length 
        });
        
        return results;
    }

    /**
     * Configuration des événements de nettoyage
     */
    setupCleanupEvents() {
        // Nettoyage lors du changement de page
        window.addEventListener('beforeunload', () => {
            this.dispose();
        });

        // Nettoyage lors de la perte de visibilité
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.pauseUpdates();
            } else {
                this.resumeUpdates();
            }
        });
    }

    /**
     * Mettre en pause les mises à jour
     */
    pauseUpdates() {
        this.timers.forEach(timer => clearInterval(timer));
        console.log('⏸️  AI updates paused');
    }

    /**
     * Reprendre les mises à jour
     */
    resumeUpdates() {
        if (this.isInitialized) {
            this.startAutoUpdates();
            console.log('▶️  AI updates resumed');
        }
    }

    /**
     * Nettoyer les ressources
     */
    dispose() {
        // Arrêter tous les timers
        this.timers.forEach(timer => clearInterval(timer));
        this.timers.clear();
        
        // Nettoyer le cache
        this.cache.clear();
        
        // Nettoyer les événements
        this.events = {};
        
        console.log('🔄 AI State Manager disposed');
    }
}

// Instance globale du gestionnaire d'état
window.aiStateManager = new AIStateManager();

// Auto-initialisation
document.addEventListener('DOMContentLoaded', async () => {
    // Attendre que le service manager soit prêt
    if (window.aiServiceManager) {
        await window.aiStateManager.initialize();
    } else {
        // Écouter l'initialisation du service manager
        const checkServiceManager = setInterval(async () => {
            if (window.aiServiceManager && window.aiServiceManager.isInitialized) {
                clearInterval(checkServiceManager);
                await window.aiStateManager.initialize();
            }
        }, 1000);
        
        // Timeout de sécurité
        setTimeout(() => {
            clearInterval(checkServiceManager);
            console.warn('AI Service Manager not available for state manager initialization');
        }, 10000);
    }
});

// Export pour utilisation en modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        AIStateManager,
        SmartCache,
        EventEmitter
    };
}