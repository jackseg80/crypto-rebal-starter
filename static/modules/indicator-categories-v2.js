/**
 * INDICATOR CATEGORIES V2 - Restructuration logique
 * Basé sur l'analyse des 30+ indicateurs réels de Crypto-Toolbox
 * 
 * Corrections apportées :
 * 1. Séparation claire entre vrais on-chain vs sociaux/temporels
 * 2. Gestion des corrélations (indicateurs dominants)
 * 3. Pondération plus équilibrée et logique
 * 4. Cache optimisé (1x par jour au lieu de chaque refresh)
 */

export const INDICATOR_CATEGORIES_V2 = {
  // Indicateurs On-Chain PURS (40% du score) - Uniquement données blockchain
  onchain_pure: {
    weight: 0.40,
    description: "Métriques blockchain fondamentales",
    color: "#3b82f6", // Bleu
    indicators: {
      // Évaluation prix/valeur (corrélés - éviter double comptage)
      'mvrv_z_score': { 
        weight: 0.35, 
        invert: true, 
        dominant: true,
        correlation_group: 'valuation'
      },
      'mvrv': { 
        weight: 0.05, 
        invert: true, 
        correlation_group: 'valuation'
      },
      'nupl': { 
        weight: 0.30, 
        invert: true,
        correlation_group: 'valuation'
      },
      'rupl_nupl': { 
        weight: 0.05, 
        invert: true, 
        correlation_group: 'valuation'
      },
      
      // Métriques miniers et réseau (indépendants)
      'sopr': { weight: 0.15, invert: false },
      'coin_days_destroyed': { weight: 0.10, invert: false }
    }
  },
  
  // Indicateurs Cycle/Techniques (35% du score) - Signaux de timing
  cycle_technical: {
    weight: 0.35,
    description: "Signaux de cycle et timing",
    color: "#10b981", // Vert
    indicators: {
      // Indicateurs de cycle (corrélés - éviter surpondération)
      'pi_cycle': { 
        weight: 0.30, 
        invert: true, 
        dominant: true,
        correlation_group: 'cycle_timing'
      },
      'cbbi': { 
        weight: 0.15, 
        invert: true,
        correlation_group: 'cycle_timing'
      },
      '2y_ma': { 
        weight: 0.20, 
        invert: true,
        correlation_group: 'moving_averages'
      },
      'trolololo': { 
        weight: 0.10, 
        invert: true,
        correlation_group: 'trend_lines'
      },
      'reserve_risk': { 
        weight: 0.10, 
        invert: true
      },
      'rsi': { 
        weight: 0.10, 
        invert: true
      },
      'woobull': { 
        weight: 0.08, 
        invert: false
      },
      'mayer_multiple': { 
        weight: 0.07, 
        invert: true
      }
    }
  },
  
  // Indicateurs de Sentiment Social (15% du score) - Psychologie et adoption
  sentiment_social: {
    weight: 0.15,
    description: "Sentiment et adoption sociale",
    color: "#f59e0b", // Orange
    indicators: {
      'fear_greed': { weight: 0.40, invert: true },
      'fear_greed_7d': { weight: 0.10, invert: true },
      'google_crypto': { weight: 0.15, invert: false },
      'google_bitcoin': { weight: 0.15, invert: false },
      'google_buy_crypto': { weight: 0.10, invert: false },
      'dominance_btc': { weight: 0.10, invert: false }
    }
  },
  
  // Indicateurs Temporels/Market Structure (10% du score) - Contexte marché
  market_context: {
    weight: 0.10,
    description: "Contexte et structure de marché",
    color: "#8b5cf6", // Violet
    indicators: {
      'altcoin_season': { weight: 0.20, invert: false },
      'days_since_halving': { weight: 0.15, invert: false },
      'binance_app_rank': { weight: 0.12, invert: true },
      'crypto_com_rank': { weight: 0.12, invert: true },
      'coinbase_rank': { weight: 0.12, invert: true },
      'bmo': { weight: 0.08, invert: false },
      'bmo_7d': { weight: 0.06, invert: false },
      'bmo_30d': { weight: 0.05, invert: false },
      'bmo_90d': { weight: 0.05, invert: false },
      'jvc_connected': { weight: 0.03, invert: false },
      'phantom_rank': { weight: 0.02, invert: true }
    }
  }
};

/**
 * Mapping amélioré pour la classification automatique
 * Inclut les vrais noms des indicateurs de Crypto-Toolbox
 */
export const INDICATOR_MAPPINGS_V2 = {
  // On-Chain Pure
  'mvrv z-score': { category: 'onchain_pure', key: 'mvrv_z_score' },
  'mvrv': { category: 'onchain_pure', key: 'mvrv' },
  'cointime mvrv-z score': { category: 'onchain_pure', key: 'mvrv_z_score' },
  'nupl': { category: 'onchain_pure', key: 'nupl' },
  'rupl/nupl': { category: 'onchain_pure', key: 'rupl_nupl' },
  'sopr': { category: 'onchain_pure', key: 'sopr' },
  'coin days destroyed': { category: 'onchain_pure', key: 'coin_days_destroyed' },
  
  // Cycle/Technical
  'pi cycle': { category: 'cycle_technical', key: 'pi_cycle' },
  'cbbi': { category: 'cycle_technical', key: 'cbbi' },
  '2y ma': { category: 'cycle_technical', key: '2y_ma' },
  'trolololo trend line': { category: 'cycle_technical', key: 'trolololo' },
  'reserve risk': { category: 'cycle_technical', key: 'reserve_risk' },
  'rsi mensuel': { category: 'cycle_technical', key: 'rsi' },
  'woobull': { category: 'cycle_technical', key: 'woobull' },
  'mayer mutiple': { category: 'cycle_technical', key: 'mayer_multiple' },
  'mayer multiple': { category: 'cycle_technical', key: 'mayer_multiple' },
  
  // Sentiment Social  
  'fear & greed': { category: 'sentiment_social', key: 'fear_greed' },
  'fear & greed (moyenne 7 jours)': { category: 'sentiment_social', key: 'fear_greed_7d' },
  'google trend "crypto"': { category: 'sentiment_social', key: 'google_crypto' },
  'google trend "bitcoin"': { category: 'sentiment_social', key: 'google_bitcoin' },
  'google trend "buy crypto"': { category: 'sentiment_social', key: 'google_buy_crypto' },
  'google trend "ethereum"': { category: 'sentiment_social', key: 'google_ethereum' },
  'dominance btc': { category: 'sentiment_social', key: 'dominance_btc' },
  
  // Market Context
  'altcoin season index': { category: 'market_context', key: 'altcoin_season' },
  'jours depuis halving': { category: 'market_context', key: 'days_since_halving' },
  'binance app rank': { category: 'market_context', key: 'binance_app_rank' },
  'binance app rank (fr)': { category: 'market_context', key: 'binance_app_rank' },
  'binance app rank (uk)': { category: 'market_context', key: 'binance_app_rank' },
  'crypto.com app rank': { category: 'market_context', key: 'crypto_com_rank' },
  'crypto.com app rank (us)': { category: 'market_context', key: 'crypto_com_rank' },
  'coinbase app rank': { category: 'market_context', key: 'coinbase_rank' },
  'coinbase app rank (us)': { category: 'market_context', key: 'coinbase_rank' },
  'phantom app rank (us)': { category: 'market_context', key: 'phantom_rank' },
  'nombre de connectés jvc': { category: 'market_context', key: 'jvc_connected' },
  // BMO indicators (market context as they're social sentiment)
  'bmo (par prof. chaîne)': { category: 'market_context', key: 'bmo' },
  'bmo (par prof. chaîne) (ema 7j)': { category: 'market_context', key: 'bmo_7d' },
  'bmo (par prof. chaîne) (ema 30j)': { category: 'market_context', key: 'bmo_30d' },
  'bmo (par prof. chaîne) (ema 90j)': { category: 'market_context', key: 'bmo_90d' }
};

/**
 * Fonction de classification améliorée avec gestion des corrélations
 */
export function classifyIndicatorV2(indicatorName) {
  const name = indicatorName.toLowerCase().trim();
  
  // Recherche exacte d'abord
  for (const [pattern, mapping] of Object.entries(INDICATOR_MAPPINGS_V2)) {
    if (name.includes(pattern.toLowerCase())) {
      const category = INDICATOR_CATEGORIES_V2[mapping.category];
      const config = category.indicators[mapping.key];
      
      if (config) {
        return {
          category: mapping.category,
          key: mapping.key,
          weight: config.weight,
          invert: config.invert,
          categoryWeight: category.weight,
          dominant: config.dominant || false,
          correlationGroup: config.correlation_group
        };
      }
    }
  }
  
  // Classification par défaut pour indicateurs inconnus
  console.warn(`⚠️ Unknown indicator for V2 classification: ${indicatorName}`);
  return {
    category: 'market_context',
    key: 'unknown',
    weight: 0.05,
    invert: false,
    categoryWeight: 0.10,
    dominant: false
  };
}

/**
 * Système de consensus voting pour éviter les signaux isolés
 */
export function calculateCategoryConsensus(categoryIndicators) {
  if (!categoryIndicators || categoryIndicators.length === 0) {
    return { consensus: 'neutral', confidence: 0, signal_strength: 0 };
  }
  
  let bullishCount = 0;
  let bearishCount = 0;
  let totalWeight = 0;
  
  categoryIndicators.forEach(indicator => {
    const score = indicator.normalizedScore;
    const weight = indicator.weight;
    
    totalWeight += weight;
    
    // Score < 40 = bullish, > 60 = bearish
    if (score < 40) {
      bullishCount += weight;
    } else if (score > 60) {
      bearishCount += weight;
    }
  });
  
  const bullishRatio = bullishCount / totalWeight;
  const bearishRatio = bearishCount / totalWeight;
  
  let consensus = 'neutral';
  let signalStrength = 0;
  
  if (bullishRatio > 0.6) {
    consensus = 'bullish';
    signalStrength = bullishRatio;
  } else if (bearishRatio > 0.6) {
    consensus = 'bearish';
    signalStrength = bearishRatio;
  }
  
  const confidence = Math.max(bullishRatio, bearishRatio);
  
  return {
    consensus,
    confidence: Math.round(confidence * 100),
    signal_strength: Math.round(signalStrength * 100),
    bullish_weight: Math.round(bullishRatio * 100),
    bearish_weight: Math.round(bearishRatio * 100)
  };
}

/**
 * Cache configuration - 1 fois par jour au lieu de chaque refresh
 */
export const CACHE_CONFIG = {
  // Cache principal des indicateurs - 24h
  indicators_ttl: 24 * 60 * 60 * 1000, // 24 heures
  
  // Cache du score composite - 1h (peut être recalculé plus souvent)
  composite_score_ttl: 60 * 60 * 1000, // 1 heure
  
  // Cache des corrélations - 1 semaine (stable)
  correlations_ttl: 7 * 24 * 60 * 60 * 1000, // 1 semaine
  
  // Retry configuration pour le scraping
  max_retries: 3,
  retry_delay: 2000 // 2 secondes
};