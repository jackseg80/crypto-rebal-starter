/**
 * Système de logging centralisé pour Crypto Rebalancer
 * 
 * Permet d'activer/désactiver les logs de debug en production
 * tout en gardant les erreurs critiques visibles.
 */

class DebugLogger {
    constructor() {
        // Vérifier si on est en mode debug via localStorage ou variable globale
        this.debugEnabled = this.isDebugEnabled();
        
        // Niveaux de log
        this.LEVELS = {
            ERROR: 0,   // Toujours affiché
            WARN: 1,    // Toujours affiché
            INFO: 2,    // Affiché si debug activé
            DEBUG: 3    // Affiché si debug activé
        };
        
        console.log(`🔧 DebugLogger initialized - Debug mode: ${this.debugEnabled ? 'ON' : 'OFF'}`);
    }
    
    /**
     * Détecte si le mode debug est activé
     */
    isDebugEnabled() {
        // Priorité 1: localStorage (pour toggle runtime)
        const localStorageDebug = localStorage.getItem('crypto_debug_mode');
        if (localStorageDebug !== null) {
            return localStorageDebug === 'true';
        }
        
        // Priorité 2: Variable globale de configuration
        if (window.globalConfig) {
            const debugFromConfig = window.globalConfig.get('debug_mode');
            if (debugFromConfig !== undefined) {
                return debugFromConfig === true;
            }
        }
        
        // Priorité 3: URL parameter pour debug temporaire
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('debug')) {
            return urlParams.get('debug') === 'true';
        }
        
        // Priorité 4: Détection environment (localhost = debug par défaut)
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return true;
        }
        
        // Production par défaut
        return false;
    }
    
    /**
     * Active/désactive le mode debug
     */
    setDebugMode(enabled) {
        this.debugEnabled = enabled;
        localStorage.setItem('crypto_debug_mode', enabled.toString());
        console.log(`🔧 Debug mode ${enabled ? 'ENABLED' : 'DISABLED'}`);
    }
    
    /**
     * Log de niveau ERROR (toujours affiché)
     */
    error(message, ...args) {
        console.error(`❌ ${message}`, ...args);
    }
    
    /**
     * Log de niveau WARN (toujours affiché)
     */
    warn(message, ...args) {
        console.warn(`⚠️ ${message}`, ...args);
    }
    
    /**
     * Log de niveau INFO (affiché uniquement si debug activé)
     */
    info(message, ...args) {
        if (this.debugEnabled) {
            console.log(`ℹ️ ${message}`, ...args);
        }
    }
    
    /**
     * Log de niveau DEBUG (affiché uniquement si debug activé)
     */
    debug(message, ...args) {
        if (this.debugEnabled) {
            console.log(`🔍 DEBUG ${message}`, ...args);
        }
    }
    
    /**
     * Log conditionnel pour les performances critiques
     */
    perf(message, ...args) {
        if (this.debugEnabled) {
            console.time(message);
            console.log(`⚡ PERF ${message}`, ...args);
        }
    }
    
    /**
     * Fin de mesure de performance
     */
    perfEnd(message) {
        if (this.debugEnabled) {
            console.timeEnd(message);
        }
    }
    
    /**
     * Log pour les interactions API
     */
    api(endpoint, data = null) {
        if (this.debugEnabled) {
            console.group(`🌐 API ${endpoint}`);
            if (data) console.log('Data:', data);
            console.groupEnd();
        }
    }
    
    /**
     * Log pour les changements d'état UI
     */
    ui(action, details = null) {
        if (this.debugEnabled) {
            console.log(`🎨 UI ${action}`, details || '');
        }
    }
    
    /**
     * Affiche les statistiques de debug
     */
    stats() {
        if (this.debugEnabled) {
            console.group('📊 Debug Statistics');
            console.log('Debug mode:', this.debugEnabled);
            console.log('Environment:', window.location.hostname);
            console.log('Config available:', !!window.globalConfig);
            console.groupEnd();
        }
    }
}

// Instance globale
const debugLogger = new DebugLogger();

// Export pour utilisation dans d'autres scripts
window.debugLogger = debugLogger;

// Raccourcis pour compatibilité
window.log = {
    error: debugLogger.error.bind(debugLogger),
    warn: debugLogger.warn.bind(debugLogger),
    info: debugLogger.info.bind(debugLogger),
    debug: debugLogger.debug.bind(debugLogger),
    perf: debugLogger.perf.bind(debugLogger),
    perfEnd: debugLogger.perfEnd.bind(debugLogger),
    api: debugLogger.api.bind(debugLogger),
    ui: debugLogger.ui.bind(debugLogger)
};

// Interface pour toggle debug depuis la console
window.toggleDebug = () => {
    debugLogger.setDebugMode(!debugLogger.debugEnabled);
    return `Debug mode is now ${debugLogger.debugEnabled ? 'ON' : 'OFF'}`;
};

console.log('🚀 Debug Logger loaded - Type toggleDebug() to switch modes');