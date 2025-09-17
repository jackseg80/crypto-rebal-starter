/**
 * Simplified Taxonomy Utility for asset classification
 * Used by GRI and other risk modules when main taxonomy service is not available
 */

export class Taxonomy {
    constructor() {
        this.classifications = this._initializeClassifications();
    }

    getAssetClassification(symbol) {
        const normalizedSymbol = symbol?.toUpperCase();
        return this.classifications[normalizedSymbol] || this._getDefaultClassification(normalizedSymbol);
    }

    _initializeClassifications() {
        return {
            // Store of Value / Digital Gold
            'BTC': { layer_1: 'Store of Value', layer_2: 'Digital Gold', layer_3: 'Proof of Work' },
            'LTC': { layer_1: 'Store of Value', layer_2: 'Silver to Gold', layer_3: 'Proof of Work' },

            // Smart Contract Platforms - Layer 1
            'ETH': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1', layer_3: 'Proof of Stake' },
            'ADA': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1', layer_3: 'Ouroboros PoS' },
            'SOL': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1', layer_3: 'Proof of History' },
            'AVAX': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1', layer_3: 'Avalanche Consensus' },
            'DOT': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 0', layer_3: 'Relay Chain' },
            'ATOM': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 0', layer_3: 'Cosmos Hub' },
            'NEAR': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1', layer_3: 'Nightshade Sharding' },
            'FTM': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1', layer_3: 'Lachesis Consensus' },
            'ALGO': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1', layer_3: 'Pure Proof of Stake' },
            'TEZOS': { layer_1: 'Smart Contract Platform', layer_2: 'Layer 1', layer_3: 'Liquid Proof of Stake' },

            // Layer 2 Solutions
            'MATIC': { layer_1: 'Scaling Solution', layer_2: 'Layer 2', layer_3: 'Polygon PoS' },
            'OP': { layer_1: 'Scaling Solution', layer_2: 'Layer 2', layer_3: 'Optimistic Rollup' },
            'ARB': { layer_1: 'Scaling Solution', layer_2: 'Layer 2', layer_3: 'Arbitrum Rollup' },
            'LRC': { layer_1: 'Scaling Solution', layer_2: 'Layer 2', layer_3: 'zkRollup' },

            // Exchange Tokens
            'BNB': { layer_1: 'Exchange Token', layer_2: 'Centralized Exchange', layer_3: 'Binance' },
            'FTT': { layer_1: 'Exchange Token', layer_2: 'Centralized Exchange', layer_3: 'FTX' },
            'CRO': { layer_1: 'Exchange Token', layer_2: 'Centralized Exchange', layer_3: 'Crypto.com' },
            'HT': { layer_1: 'Exchange Token', layer_2: 'Centralized Exchange', layer_3: 'Huobi' },
            'OKB': { layer_1: 'Exchange Token', layer_2: 'Centralized Exchange', layer_3: 'OKEx' },
            'KCS': { layer_1: 'Exchange Token', layer_2: 'Centralized Exchange', layer_3: 'KuCoin' },

            // DeFi Protocols
            'UNI': { layer_1: 'DeFi', layer_2: 'DEX', layer_3: 'Automated Market Maker' },
            'SUSHI': { layer_1: 'DeFi', layer_2: 'DEX', layer_3: 'Automated Market Maker' },
            'CAKE': { layer_1: 'DeFi', layer_2: 'DEX', layer_3: 'Automated Market Maker' },
            'AAVE': { layer_1: 'DeFi', layer_2: 'Lending', layer_3: 'Money Market' },
            'COMP': { layer_1: 'DeFi', layer_2: 'Lending', layer_3: 'Money Market' },
            'CRV': { layer_1: 'DeFi', layer_2: 'DEX', layer_3: 'Curve AMM' },
            'SNX': { layer_1: 'DeFi', layer_2: 'Derivatives', layer_3: 'Synthetic Assets' },
            'YFI': { layer_1: 'DeFi', layer_2: 'Yield Farming', layer_3: 'Vault Aggregator' },
            'INCH': { layer_1: 'DeFi', layer_2: 'DEX Aggregator', layer_3: 'Multi-DEX' },
            'BAL': { layer_1: 'DeFi', layer_2: 'DEX', layer_3: 'Weighted Pool AMM' },

            // Oracles & Data
            'LINK': { layer_1: 'Oracle', layer_2: 'Data Provider', layer_3: 'Decentralized Oracle Network' },
            'BAND': { layer_1: 'Oracle', layer_2: 'Data Provider', layer_3: 'Cross-Chain Oracle' },
            'TRB': { layer_1: 'Oracle', layer_2: 'Data Provider', layer_3: 'Proof of Work Oracle' },

            // Privacy Coins
            'XMR': { layer_1: 'Privacy', layer_2: 'Privacy Coin', layer_3: 'Ring Signatures' },
            'ZEC': { layer_1: 'Privacy', layer_2: 'Privacy Coin', layer_3: 'zk-SNARKs' },
            'DASH': { layer_1: 'Privacy', layer_2: 'Privacy Coin', layer_3: 'CoinJoin' },

            // Meme Coins
            'DOGE': { layer_1: 'Meme', layer_2: 'Community Token', layer_3: 'Proof of Work' },
            'SHIB': { layer_1: 'Meme', layer_2: 'Community Token', layer_3: 'ERC-20' },

            // Infrastructure & Web3
            'FIL': { layer_1: 'Infrastructure', layer_2: 'Storage', layer_3: 'Decentralized Storage' },
            'AR': { layer_1: 'Infrastructure', layer_2: 'Storage', layer_3: 'Permanent Storage' },
            'THETA': { layer_1: 'Infrastructure', layer_2: 'Media', layer_3: 'Video Delivery' },
            'GRT': { layer_1: 'Infrastructure', layer_2: 'Indexing', layer_3: 'Graph Protocol' },

            // Gaming & NFTs
            'AXS': { layer_1: 'Gaming', layer_2: 'Play-to-Earn', layer_3: 'Axie Infinity' },
            'SAND': { layer_1: 'Gaming', layer_2: 'Metaverse', layer_3: 'Virtual World' },
            'MANA': { layer_1: 'Gaming', layer_2: 'Metaverse', layer_3: 'Virtual World' },
            'ENJ': { layer_1: 'Gaming', layer_2: 'NFT Platform', layer_3: 'Gaming Items' },

            // Stablecoins
            'USDT': { layer_1: 'Stablecoin', layer_2: 'Centralized', layer_3: 'Fiat Collateralized' },
            'USDC': { layer_1: 'Stablecoin', layer_2: 'Centralized', layer_3: 'Fiat Collateralized' },
            'DAI': { layer_1: 'Stablecoin', layer_2: 'Decentralized', layer_3: 'Crypto Collateralized' },
            'BUSD': { layer_1: 'Stablecoin', layer_2: 'Centralized', layer_3: 'Fiat Collateralized' },
            'UST': { layer_1: 'Stablecoin', layer_2: 'Algorithmic', layer_3: 'Terra Ecosystem' },
            'FRAX': { layer_1: 'Stablecoin', layer_2: 'Algorithmic', layer_3: 'Fractional Reserve' },

            // Real World Assets
            'RWA': { layer_1: 'Real World Assets', layer_2: 'Tokenized Assets', layer_3: 'Multi-Asset' },
            'GOLD': { layer_1: 'Real World Assets', layer_2: 'Commodities', layer_3: 'Precious Metals' }
        };
    }

    _getDefaultClassification(symbol) {
        // Fallback classification logic based on common patterns
        if (!symbol) {
            return { layer_1: 'Unknown', layer_2: 'Unknown', layer_3: 'Unknown' };
        }

        // Pattern matching for unknown tokens
        if (symbol.includes('USD') || symbol.includes('DAI') || symbol.includes('USDT')) {
            return { layer_1: 'Stablecoin', layer_2: 'Unknown Type', layer_3: 'Unknown Mechanism' };
        }

        if (symbol.includes('BTC') && symbol !== 'BTC') {
            return { layer_1: 'Bitcoin Derivative', layer_2: 'Wrapped/Synthetic', layer_3: 'Cross-Chain' };
        }

        if (symbol.includes('ETH') && symbol !== 'ETH') {
            return { layer_1: 'Ethereum Derivative', layer_2: 'Wrapped/Synthetic', layer_3: 'Cross-Chain' };
        }

        return { layer_1: 'Other', layer_2: 'Unknown', layer_3: 'Unknown' };
    }

    /**
     * Get all assets in a specific category
     */
    getAssetsByCategory(layer1Category) {
        const assets = [];
        for (const [symbol, classification] of Object.entries(this.classifications)) {
            if (classification.layer_1 === layer1Category) {
                assets.push(symbol);
            }
        }
        return assets;
    }

    /**
     * Get category statistics
     */
    getCategoryStats() {
        const stats = {};

        for (const classification of Object.values(this.classifications)) {
            const category = classification.layer_1;
            if (!stats[category]) {
                stats[category] = {
                    count: 0,
                    subcategories: new Set()
                };
            }
            stats[category].count++;
            stats[category].subcategories.add(classification.layer_2);
        }

        // Convert sets to arrays
        for (const category of Object.keys(stats)) {
            stats[category].subcategories = Array.from(stats[category].subcategories);
        }

        return stats;
    }

    /**
     * Check if two assets are in the same category
     */
    isSameCategory(symbol1, symbol2, layer = 1) {
        const class1 = this.getAssetClassification(symbol1);
        const class2 = this.getAssetClassification(symbol2);

        const layerKey = `layer_${layer}`;
        return class1[layerKey] === class2[layerKey];
    }

    /**
     * Get risk correlation factor between categories
     */
    getCategoryCorrelationFactor(category1, category2) {
        // Simplified correlation factors between major categories
        const correlationMatrix = {
            'Smart Contract Platform': {
                'Smart Contract Platform': 0.85,
                'DeFi': 0.75,
                'Layer 2': 0.70,
                'Gaming': 0.60,
                'Oracle': 0.65,
                'Store of Value': 0.50,
                'Exchange Token': 0.60,
                'Stablecoin': 0.20,
                'Privacy': 0.45,
                'Meme': 0.40
            },
            'DeFi': {
                'DeFi': 0.90,
                'Smart Contract Platform': 0.75,
                'Layer 2': 0.65,
                'Oracle': 0.70,
                'Gaming': 0.50,
                'Store of Value': 0.45,
                'Exchange Token': 0.55,
                'Stablecoin': 0.25,
                'Privacy': 0.40,
                'Meme': 0.35
            },
            'Store of Value': {
                'Store of Value': 0.80,
                'Smart Contract Platform': 0.50,
                'DeFi': 0.45,
                'Privacy': 0.60,
                'Exchange Token': 0.50,
                'Stablecoin': 0.15,
                'Meme': 0.30
            },
            'Stablecoin': {
                'Stablecoin': 0.95,
                'Store of Value': 0.15,
                'Smart Contract Platform': 0.20,
                'DeFi': 0.25,
                'Exchange Token': 0.30
            }
        };

        return correlationMatrix[category1]?.[category2] ||
               correlationMatrix[category2]?.[category1] ||
               0.50; // Default moderate correlation
    }
}

// Export default instance
export const taxonomy = new Taxonomy();