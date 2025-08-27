/**
 * Système de validation des inputs utilisateur pour Crypto Rebalancer
 * 
 * Valide les données avant traitement pour éviter les erreurs
 * et améliorer l'expérience utilisateur.
 */

class InputValidator {
    constructor() {
        this.errors = [];
        
        // Patterns de validation
        this.patterns = {
            percentage: /^(100(\.0+)?|\d{1,2}(\.\d+)?)$/,
            usd_amount: /^\d+(\.\d{1,2})?$/,
            symbol: /^[A-Z0-9]+$/,
            api_key: /^[a-zA-Z0-9]+$/
        };
        
        // Limites par défaut
        this.limits = {
            min_percentage: 0,
            max_percentage: 100,
            min_usd: 0.01,
            max_usd: 1000000,
            min_trade_usd: 1,
            max_symbols_per_group: 50
        };
    }
    
    /**
     * Valide les targets de rebalancement
     */
    validateTargets(targets) {
        this.errors = [];
        
        if (!targets || typeof targets !== 'object') {
            this.errors.push('Les targets doivent être un objet valide');
            return false;
        }
        
        const entries = Object.entries(targets);
        if (entries.length === 0) {
            this.errors.push('Au moins un groupe doit être spécifié');
            return false;
        }
        
        let totalPercentage = 0;
        
        for (const [group, percentage] of entries) {
            // Validation du nom de groupe
            if (!group || typeof group !== 'string' || group.trim().length === 0) {
                this.errors.push(`Nom de groupe invalide: "${group}"`);
                continue;
            }
            
            // Validation du pourcentage
            const pct = parseFloat(percentage);
            if (isNaN(pct)) {
                this.errors.push(`Pourcentage invalide pour ${group}: "${percentage}"`);
                continue;
            }
            
            if (pct < this.limits.min_percentage || pct > this.limits.max_percentage) {
                this.errors.push(`Pourcentage hors limites pour ${group}: ${pct}% (doit être entre ${this.limits.min_percentage}-${this.limits.max_percentage}%)`);
                continue;
            }
            
            totalPercentage += pct;
        }
        
        // Validation du total (tolérance de 0.1% pour erreurs d'arrondi)
        if (Math.abs(totalPercentage - 100) > 0.1) {
            this.errors.push(`Total des pourcentages: ${totalPercentage.toFixed(1)}% (doit être 100%)`);
        }
        
        return this.errors.length === 0;
    }
    
    /**
     * Valide les paramètres de configuration
     */
    validateConfig(config) {
        this.errors = [];
        
        if (!config || typeof config !== 'object') {
            this.errors.push('Configuration invalide');
            return false;
        }
        
        // Validation source de données
        const validSources = ['cointracking', 'cointracking_api', 'stub'];
        if (config.data_source && !validSources.includes(config.data_source)) {
            this.errors.push(`Source de données invalide: "${config.data_source}". Sources valides: ${validSources.join(', ')}`);
        }
        
        // Validation seuil minimum USD
        if (config.min_usd_threshold !== undefined) {
            const minUsd = parseFloat(config.min_usd_threshold);
            if (isNaN(minUsd) || minUsd < this.limits.min_usd || minUsd > this.limits.max_usd) {
                this.errors.push(`Seuil minimum USD invalide: ${config.min_usd_threshold} (doit être entre ${this.limits.min_usd}-${this.limits.max_usd})`);
            }
        }
        
        // Validation trade minimum
        if (config.min_trade_usd !== undefined) {
            const minTrade = parseFloat(config.min_trade_usd);
            if (isNaN(minTrade) || minTrade < this.limits.min_trade_usd) {
                this.errors.push(`Montant minimum de trade invalide: ${config.min_trade_usd} (doit être >= ${this.limits.min_trade_usd})`);
            }
        }
        
        // Validation clés API
        if (config.cointracking_api_key && !this.patterns.api_key.test(config.cointracking_api_key)) {
            this.errors.push('Clé API CoinTracking invalide (caractères alphanumériques uniquement)');
        }
        
        if (config.coingecko_api_key && !this.patterns.api_key.test(config.coingecko_api_key)) {
            this.errors.push('Clé API CoinGecko invalide (caractères alphanumériques uniquement)');
        }
        
        return this.errors.length === 0;
    }
    
    /**
     * Valide une liste de symboles crypto
     */
    validateSymbols(symbols) {
        this.errors = [];
        
        if (!Array.isArray(symbols)) {
            this.errors.push('La liste des symboles doit être un tableau');
            return false;
        }
        
        if (symbols.length === 0) {
            this.errors.push('Au moins un symbole doit être spécifié');
            return false;
        }
        
        if (symbols.length > this.limits.max_symbols_per_group) {
            this.errors.push(`Trop de symboles: ${symbols.length} (maximum ${this.limits.max_symbols_per_group})`);
        }
        
        for (const symbol of symbols) {
            if (!symbol || typeof symbol !== 'string') {
                this.errors.push(`Symbole invalide: "${symbol}"`);
                continue;
            }
            
            const upperSymbol = symbol.toUpperCase();
            if (!this.patterns.symbol.test(upperSymbol)) {
                this.errors.push(`Format de symbole invalide: "${symbol}" (lettres et chiffres uniquement)`);
            }
        }
        
        return this.errors.length === 0;
    }
    
    /**
     * Valide un montant en USD
     */
    validateUSDAmount(amount, fieldName = 'Montant') {
        this.errors = [];
        
        const usd = parseFloat(amount);
        if (isNaN(usd)) {
            this.errors.push(`${fieldName} invalide: "${amount}"`);
            return false;
        }
        
        if (usd < this.limits.min_usd || usd > this.limits.max_usd) {
            this.errors.push(`${fieldName} hors limites: ${usd} (doit être entre ${this.limits.min_usd}-${this.limits.max_usd})`);
        }
        
        return this.errors.length === 0;
    }
    
    /**
     * Valide un pourcentage
     */
    validatePercentage(percentage, fieldName = 'Pourcentage') {
        this.errors = [];
        
        const pct = parseFloat(percentage);
        if (isNaN(pct)) {
            this.errors.push(`${fieldName} invalide: "${percentage}"`);
            return false;
        }
        
        if (pct < this.limits.min_percentage || pct > this.limits.max_percentage) {
            this.errors.push(`${fieldName} hors limites: ${pct}% (doit être entre ${this.limits.min_percentage}-${this.limits.max_percentage}%)`);
        }
        
        return this.errors.length === 0;
    }
    
    /**
     * Sanitise une chaîne pour éviter les injections
     */
    sanitizeString(str) {
        if (!str || typeof str !== 'string') return '';
        
        return str
            .trim()
            .replace(/[<>\"']/g, '') // Supprimer caractères dangereux
            .substring(0, 100); // Limiter la longueur
    }
    
    /**
     * Valide et sanitise les données d'un formulaire
     */
    validateAndSanitizeForm(formData) {
        this.errors = [];
        const sanitized = {};
        
        for (const [key, value] of Object.entries(formData)) {
            if (typeof value === 'string') {
                sanitized[key] = this.sanitizeString(value);
            } else if (typeof value === 'number') {
                sanitized[key] = isNaN(value) ? 0 : value;
            } else {
                sanitized[key] = value;
            }
        }
        
        return {
            isValid: this.errors.length === 0,
            data: sanitized,
            errors: this.errors
        };
    }
    
    /**
     * Retourne les erreurs de validation
     */
    getErrors() {
        return this.errors;
    }
    
    /**
     * Formate les erreurs pour affichage à l'utilisateur
     */
    getFormattedErrors() {
        return this.errors.join('\n• ');
    }
    
    /**
     * Réinitialise les erreurs
     */
    clearErrors() {
        this.errors = [];
    }
}

// Instance globale
const inputValidator = new InputValidator();

// Export pour utilisation
window.inputValidator = inputValidator;

// Fonctions utilitaires
window.validateTargets = (targets) => inputValidator.validateTargets(targets);
window.validateConfig = (config) => inputValidator.validateConfig(config);
window.sanitizeString = (str) => inputValidator.sanitizeString(str);

console.log('🛡️ Input Validator loaded - Form validation active');