/**
 * VaR Calculator Module - Advanced Value at Risk calculations
 * Implements multiple VaR methodologies for crypto portfolios
 */

export class VaRCalculator {
    constructor() {
        this.confidence_levels = [0.95, 0.99, 0.999];
        this.time_horizons = [1, 7, 30]; // 1 day, 1 week, 1 month
        this.cache = new Map();
        this.cache_ttl = 30 * 60 * 1000; // 30 minutes (optimized: based on daily historical data)
    }

    /**
     * Calculate VaR using multiple methodologies
     * @param {Array} returns - Array of portfolio returns
     * @param {Object} options - Calculation options
     * @returns {Object} VaR results with multiple methods
     */
    calculateVaR(returns, options = {}) {
        if (!returns || returns.length < 30) {
            return this._getEmptyVaRResult();
        }

        const cacheKey = this._getCacheKey(returns, options);
        const cached = this._getFromCache(cacheKey);
        if (cached) return cached;

        const result = {
            historical: this._calculateHistoricalVaR(returns),
            parametric: this._calculateParametricVaR(returns),
            monte_carlo: this._calculateMonteCarloVaR(returns),
            ewma: this._calculateEWMAVaR(returns), // Exponentially Weighted Moving Average
            summary: {},
            metadata: {
                data_points: returns.length,
                calculation_time: new Date().toISOString(),
                confidence: this._assessConfidence(returns)
            }
        };

        // Create summary with best estimates
        result.summary = this._createVaRSummary(result);

        this._setCache(cacheKey, result);
        return result;
    }

    /**
     * Historical VaR - Uses empirical percentiles
     */
    _calculateHistoricalVaR(returns) {
        const sortedReturns = [...returns].sort((a, b) => a - b);
        const n = sortedReturns.length;

        const results = {};

        for (const confidence of this.confidence_levels) {
            const alpha = 1 - confidence;
            const index = Math.ceil(alpha * n) - 1;
            const var_value = -sortedReturns[Math.max(0, index)];

            // Calculate Conditional VaR (Expected Shortfall)
            const tail_returns = sortedReturns.slice(0, index + 1);
            const cvar_value = -tail_returns.reduce((sum, r) => sum + r, 0) / tail_returns.length;

            results[`var_${Math.round(confidence * 100)}`] = var_value;
            results[`cvar_${Math.round(confidence * 100)}`] = cvar_value;
        }

        return {
            method: 'Historical Simulation',
            values: results,
            description: 'Empirical percentiles from historical data'
        };
    }

    /**
     * Parametric VaR - Assumes normal distribution
     */
    _calculateParametricVaR(returns) {
        const mean = returns.reduce((sum, r) => sum + r, 0) / returns.length;
        const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / (returns.length - 1);
        const std = Math.sqrt(variance);

        const results = {};

        for (const confidence of this.confidence_levels) {
            // Z-score for normal distribution
            const z_score = this._getZScore(confidence);
            const var_value = -(mean + z_score * std);

            // For normal distribution, CVaR = VaR + (std * pdf(z_score) / (1 - confidence))
            const pdf_z = Math.exp(-0.5 * z_score * z_score) / Math.sqrt(2 * Math.PI);
            const cvar_value = var_value + (std * pdf_z / (1 - confidence));

            results[`var_${Math.round(confidence * 100)}`] = var_value;
            results[`cvar_${Math.round(confidence * 100)}`] = cvar_value;
        }

        return {
            method: 'Parametric (Normal)',
            values: results,
            parameters: { mean, std, skewness: this._calculateSkewness(returns, mean, std) },
            description: 'Assumes normal distribution of returns'
        };
    }

    /**
     * Monte Carlo VaR - Simulates future returns
     */
    _calculateMonteCarloVaR(returns, simulations = 10000) {
        const mean = returns.reduce((sum, r) => sum + r, 0) / returns.length;
        const std = Math.sqrt(returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / (returns.length - 1));

        // Generate random returns
        const simulatedReturns = [];
        for (let i = 0; i < simulations; i++) {
            // Box-Muller transform for normal distribution
            const u1 = Math.random();
            const u2 = Math.random();
            const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
            simulatedReturns.push(mean + std * z);
        }

        return this._calculateHistoricalVaR(simulatedReturns);
    }

    /**
     * EWMA VaR - Exponentially weighted moving average
     */
    _calculateEWMAVaR(returns, lambda = 0.94) {
        const n = returns.length;
        const weights = [];
        let totalWeight = 0;

        // Calculate EWMA weights
        for (let i = 0; i < n; i++) {
            const weight = Math.pow(lambda, i);
            weights.unshift(weight);
            totalWeight += weight;
        }

        // Normalize weights
        const normalizedWeights = weights.map(w => w / totalWeight);

        // Calculate weighted mean and variance
        let weightedMean = 0;
        let weightedVariance = 0;

        for (let i = 0; i < n; i++) {
            weightedMean += returns[i] * normalizedWeights[i];
        }

        for (let i = 0; i < n; i++) {
            weightedVariance += normalizedWeights[i] * Math.pow(returns[i] - weightedMean, 2);
        }

        const weightedStd = Math.sqrt(weightedVariance);

        const results = {};

        for (const confidence of this.confidence_levels) {
            const z_score = this._getZScore(confidence);
            const var_value = -(weightedMean + z_score * weightedStd);

            const pdf_z = Math.exp(-0.5 * z_score * z_score) / Math.sqrt(2 * Math.PI);
            const cvar_value = var_value + (weightedStd * pdf_z / (1 - confidence));

            results[`var_${Math.round(confidence * 100)}`] = var_value;
            results[`cvar_${Math.round(confidence * 100)}`] = cvar_value;
        }

        return {
            method: 'EWMA (λ=0.94)',
            values: results,
            parameters: { lambda, weightedMean, weightedStd },
            description: 'Exponentially weighted moving average giving more weight to recent data'
        };
    }

    /**
     * Create summary with best VaR estimates
     */
    _createVaRSummary(varResults) {
        const methods = ['historical', 'parametric', 'monte_carlo', 'ewma'];
        const summary = {};

        for (const confidence of this.confidence_levels) {
            const conf_key = Math.round(confidence * 100);
            const var_key = `var_${conf_key}`;
            const cvar_key = `cvar_${conf_key}`;

            // Collect all VaR estimates
            const var_estimates = methods.map(method => varResults[method]?.values?.[var_key]).filter(v => v != null);
            const cvar_estimates = methods.map(method => varResults[method]?.values?.[cvar_key]).filter(v => v != null);

            if (var_estimates.length > 0) {
                // Use median as robust estimate
                var_estimates.sort((a, b) => a - b);
                cvar_estimates.sort((a, b) => a - b);

                summary[var_key] = var_estimates[Math.floor(var_estimates.length / 2)];
                summary[cvar_key] = cvar_estimates[Math.floor(cvar_estimates.length / 2)];

                // Calculate confidence interval
                summary[`${var_key}_range`] = {
                    min: Math.min(...var_estimates),
                    max: Math.max(...var_estimates),
                    spread: Math.max(...var_estimates) - Math.min(...var_estimates)
                };
            }
        }

        return summary;
    }

    /**
     * Calculate portfolio component VaR
     */
    calculateComponentVaR(portfolioWeights, assetReturns, correlationMatrix) {
        const components = {};
        const portfolioVar = this.calculateVaR(this._calculatePortfolioReturns(portfolioWeights, assetReturns));

        for (const [asset, weight] of Object.entries(portfolioWeights)) {
            if (weight > 0 && assetReturns[asset]) {
                const assetVar = this.calculateVaR(assetReturns[asset]);
                const correlation = this._getAverageCorrelation(asset, correlationMatrix);

                // Component VaR = weight * (asset VaR) * correlation with portfolio
                components[asset] = {
                    component_var_95: weight * assetVar.summary.var_95 * correlation,
                    marginal_var: assetVar.summary.var_95 * correlation,
                    contribution_pct: (weight * assetVar.summary.var_95 * correlation) / portfolioVar.summary.var_95 * 100
                };
            }
        }

        return {
            components,
            total_var: portfolioVar.summary.var_95,
            diversification_benefit: Object.values(components).reduce((sum, comp) => sum + comp.component_var_95, 0) - portfolioVar.summary.var_95
        };
    }

    // Helper methods
    _getZScore(confidence) {
        // Approximate Z-scores for common confidence levels
        const z_scores = {
            0.95: -1.645,
            0.99: -2.326,
            0.999: -3.090
        };
        return z_scores[confidence] || -1.645;
    }

    _calculateSkewness(returns, mean, std) {
        const n = returns.length;
        const skew = returns.reduce((sum, r) => sum + Math.pow((r - mean) / std, 3), 0) / n;
        return skew;
    }

    _assessConfidence(returns) {
        // Assess confidence based on data quality
        const n = returns.length;
        if (n < 30) return 0.3;
        if (n < 100) return 0.6;
        if (n < 250) return 0.8;
        return 0.9;
    }

    _calculatePortfolioReturns(weights, assetReturns) {
        const portfolioReturns = [];
        const assets = Object.keys(weights);
        const maxLength = Math.max(...assets.map(asset => assetReturns[asset]?.length || 0));

        for (let i = 0; i < maxLength; i++) {
            let portfolioReturn = 0;
            let totalWeight = 0;

            for (const [asset, weight] of Object.entries(weights)) {
                if (assetReturns[asset] && assetReturns[asset][i] != null) {
                    portfolioReturn += weight * assetReturns[asset][i];
                    totalWeight += weight;
                }
            }

            if (totalWeight > 0) {
                portfolioReturns.push(portfolioReturn / totalWeight);
            }
        }

        return portfolioReturns;
    }

    _getAverageCorrelation(asset, correlationMatrix) {
        if (!correlationMatrix || !correlationMatrix[asset]) return 0.5; // Default correlation

        const correlations = Object.values(correlationMatrix[asset]).filter(corr => !isNaN(corr) && corr !== 1);
        return correlations.length > 0 ? correlations.reduce((sum, corr) => sum + corr, 0) / correlations.length : 0.5;
    }

    _getEmptyVaRResult() {
        return {
            historical: { method: 'Historical', values: {}, description: 'Insufficient data' },
            parametric: { method: 'Parametric', values: {}, description: 'Insufficient data' },
            monte_carlo: { method: 'Monte Carlo', values: {}, description: 'Insufficient data' },
            ewma: { method: 'EWMA', values: {}, description: 'Insufficient data' },
            summary: {},
            metadata: { data_points: 0, confidence: 0 }
        };
    }

    // Cache management
    _getCacheKey(returns, options) {
        return `var_${returns.length}_${JSON.stringify(options)}`;
    }

    _getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cache_ttl) {
            return cached.data;
        }
        return null;
    }

    _setCache(key, data) {
        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });

        // Cleanup old entries
        if (this.cache.size > 50) {
            const oldestKey = this.cache.keys().next().value;
            this.cache.delete(oldestKey);
        }
    }
}

// Export singleton instance
export const varCalculator = new VaRCalculator();

// Export utility functions
export function formatVaRForDisplay(varResult, confidence = 95) {
    const varKey = `var_${confidence}`;
    const cvarKey = `cvar_${confidence}`;

    return {
        var: varResult.summary[varKey] || 0,
        cvar: varResult.summary[cvarKey] || 0,
        var_pct: (varResult.summary[varKey] || 0) * 100,
        cvar_pct: (varResult.summary[cvarKey] || 0) * 100,
        confidence_level: confidence,
        method_count: Object.keys(varResult).filter(k => k !== 'summary' && k !== 'metadata').length
    };
}