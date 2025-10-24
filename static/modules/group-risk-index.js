/**
 * Group Risk Index (GRI) Module
 * Analyzes risk concentration by asset groups and provides diversification insights
 */

import { Taxonomy } from './taxonomy-utils.js';

export class GroupRiskIndex {
    constructor() {
        this.cache = new Map();
        this.cache_ttl = 30 * 60 * 1000; // 30 minutes (optimized: based on portfolio/risk updates)
        this.taxonomy = new Taxonomy();
    }

    /**
     * Calculate comprehensive Group Risk Index
     * @param {Object} holdings - Portfolio holdings with values
     * @param {Object} riskMetrics - Risk metrics per asset
     * @param {Object} correlations - Correlation matrix
     * @returns {Object} GRI analysis with group breakdowns
     */
    calculateGRI(holdings, riskMetrics = {}, correlations = {}) {
        if (!holdings || Object.keys(holdings).length === 0) {
            return this._getEmptyGRI();
        }

        const cacheKey = this._getCacheKey(holdings, riskMetrics);
        const cached = this._getFromCache(cacheKey);
        if (cached) return cached;

        // Group assets by taxonomy
        const groupedHoldings = this._groupAssetsByTaxonomy(holdings);

        // Calculate risk concentration by group
        const groupRisks = this._calculateGroupRisks(groupedHoldings, riskMetrics);

        // Calculate diversification metrics
        const diversificationMetrics = this._calculateDiversificationMetrics(groupRisks, correlations);

        // Calculate concentration risk
        const concentrationRisk = this._calculateConcentrationRisk(groupRisks);

        // Generate recommendations
        const recommendations = this._generateGRIRecommendations(groupRisks, concentrationRisk);

        const result = {
            groups: groupRisks,
            diversification: diversificationMetrics,
            concentration: concentrationRisk,
            recommendations,
            overall_gri_score: this._calculateOverallGRIScore(groupRisks, concentrationRisk),
            metadata: {
                total_groups: Object.keys(groupRisks).length,
                calculation_time: new Date().toISOString(),
                confidence: this._assessGRIConfidence(groupRisks)
            }
        };

        this._setCache(cacheKey, result);
        return result;
    }

    /**
     * Group assets by their taxonomy classification
     */
    _groupAssetsByTaxonomy(holdings) {
        const groups = {};
        const totalPortfolioValue = Object.values(holdings).reduce((sum, h) => sum + (h.value_usd || 0), 0);

        for (const [symbol, holding] of Object.entries(holdings)) {
            const classification = this.taxonomy.getAssetClassification(symbol);
            const group = classification.layer_1 || 'Unknown';

            if (!groups[group]) {
                groups[group] = {
                    assets: [],
                    total_value: 0,
                    weight: 0,
                    primary_layer: classification.layer_1,
                    secondary_layers: []
                };
            }

            const assetValue = holding.value_usd || 0;
            groups[group].assets.push({
                symbol,
                value: assetValue,
                weight: assetValue / totalPortfolioValue,
                classification: classification
            });

            groups[group].total_value += assetValue;
            groups[group].weight += assetValue / totalPortfolioValue;

            // Track secondary classifications
            if (classification.layer_2 && !groups[group].secondary_layers.includes(classification.layer_2)) {
                groups[group].secondary_layers.push(classification.layer_2);
            }
        }

        return groups;
    }

    /**
     * Calculate risk metrics for each group
     */
    _calculateGroupRisks(groupedHoldings, riskMetrics) {
        const groupRisks = {};

        for (const [groupName, groupData] of Object.entries(groupedHoldings)) {
            // Calculate weighted average volatility for the group
            let weightedVolatility = 0;
            let weightedVaR = 0;
            let totalGroupWeight = 0;

            for (const asset of groupData.assets) {
                const assetRisk = riskMetrics[asset.symbol] || {};
                const assetWeight = asset.weight;

                weightedVolatility += (assetRisk.volatility || 0.3) * assetWeight; // Default 30% volatility
                weightedVaR += (assetRisk.var_95 || 0.05) * assetWeight; // Default 5% VaR
                totalGroupWeight += assetWeight;
            }

            // Calculate concentration within group (Herfindahl index)
            const assetWeightsInGroup = groupData.assets.map(a => a.value / groupData.total_value);
            const herfindahlIndex = assetWeightsInGroup.reduce((sum, w) => sum + w * w, 0);

            // Calculate group risk level
            const riskLevel = this._assessGroupRiskLevel(weightedVolatility, groupData.weight, herfindahlIndex);

            groupRisks[groupName] = {
                ...groupData,
                weighted_volatility: weightedVolatility,
                weighted_var_95: weightedVaR,
                herfindahl_index: herfindahlIndex,
                concentration_score: herfindahlIndex * 100, // 0-100 scale
                diversification_score: (1 - herfindahlIndex) * 100, // Inverse of concentration
                risk_level: riskLevel,
                risk_score: this._calculateGroupRiskScore(weightedVolatility, groupData.weight, herfindahlIndex),
                asset_count: groupData.assets.length,
                effective_assets: 1 / herfindahlIndex // Effective number of assets
            };
        }

        return groupRisks;
    }

    /**
     * Calculate portfolio-wide diversification metrics
     */
    _calculateDiversificationMetrics(groupRisks, correlations) {
        const groups = Object.keys(groupRisks);
        const groupWeights = groups.map(g => groupRisks[g].weight);

        // Calculate group concentration (portfolio level)
        const portfolioHerfindahl = groupWeights.reduce((sum, w) => sum + w * w, 0);

        // Calculate effective number of groups
        const effectiveGroups = 1 / portfolioHerfindahl;

        // Calculate inter-group correlation (simplified)
        let avgInterGroupCorrelation = 0.6; // Default moderate correlation
        if (Object.keys(correlations).length > 0) {
            const correlationValues = [];
            for (let i = 0; i < groups.length; i++) {
                for (let j = i + 1; j < groups.length; j++) {
                    // Simplified: use first asset of each group as proxy
                    const asset1 = groupRisks[groups[i]].assets[0]?.symbol;
                    const asset2 = groupRisks[groups[j]].assets[0]?.symbol;
                    if (asset1 && asset2 && correlations[asset1] && correlations[asset1][asset2]) {
                        correlationValues.push(Math.abs(correlations[asset1][asset2]));
                    }
                }
            }
            if (correlationValues.length > 0) {
                avgInterGroupCorrelation = correlationValues.reduce((sum, c) => sum + c, 0) / correlationValues.length;
            }
        }

        // Calculate diversification ratio
        const weightedVariance = groupWeights.reduce((sum, w, i) => {
            const groupVol = groupRisks[groups[i]].weighted_volatility;
            return sum + w * w * groupVol * groupVol;
        }, 0);

        const portfolioVolatility = Math.sqrt(weightedVariance);
        const weightedAverageVolatility = groupWeights.reduce((sum, w, i) => {
            return sum + w * groupRisks[groups[i]].weighted_volatility;
        }, 0);

        const diversificationRatio = weightedAverageVolatility / portfolioVolatility;

        return {
            portfolio_herfindahl: portfolioHerfindahl,
            effective_groups: effectiveGroups,
            diversification_ratio: diversificationRatio,
            avg_inter_group_correlation: avgInterGroupCorrelation,
            diversification_score: Math.min(100, (effectiveGroups / groups.length) * 100),
            correlation_risk: avgInterGroupCorrelation > 0.8 ? 'HIGH' : avgInterGroupCorrelation > 0.6 ? 'MEDIUM' : 'LOW'
        };
    }

    /**
     * Calculate concentration risk metrics
     */
    _calculateConcentrationRisk(groupRisks) {
        const groups = Object.values(groupRisks).sort((a, b) => b.weight - a.weight);

        // Top group concentration
        const topGroupWeight = groups[0]?.weight || 0;
        const top3GroupsWeight = groups.slice(0, 3).reduce((sum, g) => sum + g.weight, 0);

        // Risk-weighted concentration (weight * risk)
        const riskWeightedConcentration = groups.reduce((sum, group) => {
            return sum + group.weight * group.risk_score / 100;
        }, 0);

        // Concentration risk level
        let concentrationLevel = 'LOW';
        if (topGroupWeight > 0.6 || top3GroupsWeight > 0.8) {
            concentrationLevel = 'HIGH';
        } else if (topGroupWeight > 0.4 || top3GroupsWeight > 0.7) {
            concentrationLevel = 'MEDIUM';
        }

        return {
            top_group_weight: topGroupWeight,
            top_3_groups_weight: top3GroupsWeight,
            risk_weighted_concentration: riskWeightedConcentration,
            concentration_level: concentrationLevel,
            concentration_score: Math.min(100, topGroupWeight * 100 + (top3GroupsWeight - topGroupWeight) * 50),
            dominant_group: groups[0]?.primary_layer || 'Unknown'
        };
    }

    /**
     * Generate GRI-based recommendations
     */
    _generateGRIRecommendations(groupRisks, concentrationRisk) {
        const recommendations = [];
        const groups = Object.values(groupRisks).sort((a, b) => b.weight - a.weight);

        // High concentration warnings
        if (concentrationRisk.concentration_level === 'HIGH') {
            recommendations.push({
                type: 'concentration_warning',
                priority: 'high',
                title: `Concentration élevée en ${concentrationRisk.dominant_group}`,
                description: `${Math.round(concentrationRisk.top_group_weight * 100)}% du portfolio concentré dans un seul groupe`,
                action: 'Diversifier vers d\'autres groupes d\'assets',
                impact: 'Réduction du risque non-systématique'
            });
        }

        // Low diversification in groups
        for (const group of groups.slice(0, 3)) { // Check top 3 groups
            if (group.diversification_score < 40 && group.weight > 0.1) {
                recommendations.push({
                    type: 'group_diversification',
                    priority: 'medium',
                    title: `Diversification limitée dans ${group.primary_layer}`,
                    description: `Seulement ${group.asset_count} assets, concentration interne élevée`,
                    action: `Ajouter plus d'assets dans le groupe ${group.primary_layer}`,
                    impact: 'Réduction du risque spécifique au groupe'
                });
            }
        }

        // High risk groups
        for (const group of groups) {
            if (group.risk_level === 'HIGH' && group.weight > 0.15) {
                recommendations.push({
                    type: 'high_risk_group',
                    priority: 'medium',
                    title: `Groupe à haut risque: ${group.primary_layer}`,
                    description: `Volatilité de ${Math.round(group.weighted_volatility * 100)}% avec ${Math.round(group.weight * 100)}% du portfolio`,
                    action: 'Considérer réduire l\'exposition ou ajouter des hedges',
                    impact: 'Réduction de la volatilité du portfolio'
                });
            }
        }

        return recommendations;
    }

    /**
     * Calculate overall GRI score (0-100)
     */
    _calculateOverallGRIScore(groupRisks, concentrationRisk) {
        const diversificationComponent = Math.max(0, 100 - concentrationRisk.concentration_score);

        const riskAdjustedComponent = Object.values(groupRisks).reduce((acc, group) => {
            return acc + group.weight * (100 - group.risk_score);
        }, 0);

        // Weight the components
        const overallScore = (diversificationComponent * 0.4 + riskAdjustedComponent * 0.6);

        return Math.round(Math.max(0, Math.min(100, overallScore)));
    }

    // Helper methods
    _assessGroupRiskLevel(volatility, weight, concentration) {
        const riskScore = volatility * weight * (1 + concentration);

        if (riskScore > 0.15) return 'HIGH';
        if (riskScore > 0.08) return 'MEDIUM';
        return 'LOW';
    }

    _calculateGroupRiskScore(volatility, weight, concentration) {
        // Combine volatility, portfolio weight, and internal concentration
        const baseRisk = Math.min(100, volatility * 200); // Normalize volatility to 0-100
        const weightPenalty = weight * 50; // Higher weight = higher contribution to portfolio risk
        const concentrationPenalty = concentration * 30; // Higher concentration = higher risk

        return Math.round(Math.min(100, baseRisk + weightPenalty + concentrationPenalty));
    }

    _assessGRIConfidence(groupRisks) {
        const totalGroups = Object.keys(groupRisks).length;
        const totalAssets = Object.values(groupRisks).reduce((sum, g) => sum + g.asset_count, 0);

        if (totalAssets < 5) return 0.3;
        if (totalGroups < 3) return 0.5;
        if (totalAssets < 10) return 0.7;
        return 0.9;
    }

    _getEmptyGRI() {
        return {
            groups: {},
            diversification: {
                portfolio_herfindahl: 1,
                effective_groups: 1,
                diversification_ratio: 1,
                diversification_score: 0
            },
            concentration: {
                concentration_level: 'UNKNOWN',
                concentration_score: 100
            },
            recommendations: [],
            overall_gri_score: 0,
            metadata: { total_groups: 0, confidence: 0 }
        };
    }

    // Cache management
    _getCacheKey(holdings, riskMetrics) {
        const holdingsKey = Object.keys(holdings).sort().join(',');
        return `gri_${holdingsKey}_${Object.keys(riskMetrics).length}`;
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

        if (this.cache.size > 20) {
            const oldestKey = this.cache.keys().next().value;
            this.cache.delete(oldestKey);
        }
    }
}

// Simple taxonomy utility (fallback if main taxonomy not available)
class SimpleTaxonomy {
    getAssetClassification(symbol) {
        const classifications = {
            'BTC': { layer_1: 'Store of Value', layer_2: 'Digital Gold' },
            'ETH': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1' },
            'BNB': { layer_1: 'Exchange Token', layer_2: 'Centralized Exchange' },
            'ADA': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1' },
            'SOL': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1' },
            'AVAX': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1' },
            'DOT': { layer_1: 'Interoperability', layer_2: 'Cross-Chain' },
            'LINK': { layer_1: 'Oracle', layer_2: 'Data Provider' },
            'UNI': { layer_1: 'DeFi', layer_2: 'DEX Token' },
            'AAVE': { layer_1: 'DeFi', layer_2: 'Lending' }
        };

        return classifications[symbol] || { layer_1: 'Other', layer_2: 'Unknown' };
    }
}

// Export singleton instance
export const groupRiskIndex = new GroupRiskIndex();

// Export utility functions
export function formatGRIForDisplay(griResult) {
    const topGroups = Object.entries(griResult.groups)
        .sort(([,a], [,b]) => b.weight - a.weight)
        .slice(0, 5)
        .map(([name, data]) => ({
            name,
            weight: Math.round(data.weight * 100),
            risk_level: data.risk_level,
            diversification: Math.round(data.diversification_score),
            asset_count: data.asset_count
        }));

    return {
        overall_score: griResult.overall_gri_score,
        concentration_level: griResult.concentration.concentration_level,
        effective_groups: Math.round(griResult.diversification.effective_groups * 10) / 10,
        top_groups: topGroups,
        high_priority_recommendations: griResult.recommendations.filter(r => r.priority === 'high').length
    };
}