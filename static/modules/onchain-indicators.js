/**
 * On-Chain Indicators Module
 * Intègre des métriques Bitcoin on-chain pour améliorer la précision du modèle de cycle
 * 
 * SOURCES D'INDICATEURS:
 * 
 * 1. Fear & Greed Index - DISPONIBLE
 *    Source: Alternative.me API (https://api.alternative.me/fng/)
 *    Fréquence: Quotidienne
 *    Fiabilité: ✅ Production ready
 * 
 * 2. MVRV Ratio - SIMULATION (API réelle disponible via services payants)
 *    Sources possibles: Glassnode, CoinMetrics, LookIntoBitcoin
 *    API publique gratuite: ❌ Non disponible
 *    Status: Simulé avec patterns historiques réalistes
 * 
 * 3. NVT Ratio - SIMULATION (calcul complexe requis)
 *    Calcul: (Market Cap) / (Transaction Volume * 365)
 *    Sources données: CoinGecko (price), Blockchain.info (volume)
 *    Status: Simulé - intégration API possible
 * 
 * 4. Puell Multiple - SIMULATION (données minières requises)
 *    Calcul: (Daily Revenue) / (365-day MA Daily Revenue)
 *    Sources: Blockchain.info, Glassnode
 *    Status: Simulé - intégration complexe
 * 
 * 5. RHODL Ratio - NON IMPLÉMENTÉ
 *    Calcul très complexe nécessitant données UTXO
 *    Sources: Glassnode uniquement (payant)
 *    Status: Non prioritaire
 */

// ===== INTELLIGENT CACHING SYSTEM =====

/**
 * Advanced caching system with adaptive TTL and performance optimization
 */
class IntelligentCache {
  constructor() {
    this.cache = new Map();
    this.accessPatterns = new Map();
    this.performanceMetrics = {
      hits: 0,
      misses: 0,
      totalRequests: 0,
      avgResponseTime: 0
    };
  }

  /**
   * Get adaptive TTL based on market volatility and access patterns
   */
  getAdaptiveTTL(key, baseMs = 10 * 60 * 1000) {
    const pattern = this.accessPatterns.get(key);
    if (!pattern) return baseMs;

    // High frequency access = shorter TTL for freshness
    if (pattern.accessCount > 10 && pattern.avgInterval < 30000) {
      return baseMs * 0.5; // 5 minutes for high frequency
    }

    // Low frequency access = longer TTL for performance  
    if (pattern.accessCount < 3 && pattern.avgInterval > 300000) {
      return baseMs * 2; // 20 minutes for low frequency
    }

    return baseMs;
  }

  /**
   * Set cache entry with metadata
   */
  set(key, value, customTtl = null) {
    const ttl = customTtl || this.getAdaptiveTTL(key);
    const entry = {
      value,
      timestamp: Date.now(),
      ttl,
      accessCount: 0,
      lastAccess: Date.now()
    };

    this.cache.set(key, entry);
    this.updateAccessPattern(key);
    return entry;
  }

  /**
   * Get cache entry if still valid
   */
  get(key) {
    const entry = this.cache.get(key);
    if (!entry) {
      this.performanceMetrics.misses++;
      this.performanceMetrics.totalRequests++;
      return null;
    }

    const age = Date.now() - entry.timestamp;
    if (age > entry.ttl) {
      this.cache.delete(key);
      this.performanceMetrics.misses++;
      this.performanceMetrics.totalRequests++;
      return null;
    }

    // Update access metadata
    entry.accessCount++;
    entry.lastAccess = Date.now();
    this.updateAccessPattern(key);
    
    this.performanceMetrics.hits++;
    this.performanceMetrics.totalRequests++;
    
    return entry.value;
  }

  /**
   * Update access patterns for adaptive TTL
   */
  updateAccessPattern(key) {
    const now = Date.now();
    const pattern = this.accessPatterns.get(key) || {
      accessCount: 0,
      lastAccess: now,
      intervals: [],
      avgInterval: 0
    };

    if (pattern.lastAccess > 0) {
      const interval = now - pattern.lastAccess;
      pattern.intervals.push(interval);
      
      // Keep only last 10 intervals for rolling average
      if (pattern.intervals.length > 10) {
        pattern.intervals.shift();
      }
      
      pattern.avgInterval = pattern.intervals.reduce((a, b) => a + b, 0) / pattern.intervals.length;
    }

    pattern.accessCount++;
    pattern.lastAccess = now;
    this.accessPatterns.set(key, pattern);
  }

  /**
   * Check if cache entry exists and is still valid
   */
  has(key) {
    const entry = this.cache.get(key);
    if (!entry) return false;
    
    const age = Date.now() - entry.timestamp;
    return age <= entry.ttl;
  }

  /**
   * Get cache statistics
   */
  getStats() {
    const hitRate = this.performanceMetrics.totalRequests > 0 
      ? (this.performanceMetrics.hits / this.performanceMetrics.totalRequests) * 100 
      : 0;

    return {
      ...this.performanceMetrics,
      hitRate: Math.round(hitRate * 100) / 100,
      cacheSize: this.cache.size,
      patterns: this.accessPatterns.size
    };
  }

  /**
   * Clear expired entries and optimize memory
   */
  cleanup() {
    const now = Date.now();
    let cleaned = 0;

    for (const [key, entry] of this.cache.entries()) {
      const age = now - entry.timestamp;
      if (age > entry.ttl) {
        this.cache.delete(key);
        cleaned++;
      }
    }

    // Clean old access patterns
    for (const [key, pattern] of this.accessPatterns.entries()) {
      if (now - pattern.lastAccess > 24 * 60 * 60 * 1000) { // 24h
        this.accessPatterns.delete(key);
      }
    }

    console.log(`🧹 Cache cleanup: ${cleaned} expired entries removed`);
    return cleaned;
  }

  /**
   * Force refresh of specific key
   */
  invalidate(key) {
    this.cache.delete(key);
  }

  /**
   * Clear all cache
   */
  clear() {
    this.cache.clear();
    this.accessPatterns.clear();
    this.performanceMetrics = { hits: 0, misses: 0, totalRequests: 0, avgResponseTime: 0 };
  }
}

// Global intelligent cache instance
const intelligentCache = new IntelligentCache();

// Legacy cache variables (for backward compatibility)
let indicatorsCache = intelligentCache;
const CACHE_DURATION = 10 * 60 * 1000; // 10 minutes

// Plus de cache de simulation - données réelles uniquement

// Auto-cleanup every 30 minutes
setInterval(() => {
  intelligentCache.cleanup();
}, 30 * 60 * 1000);

// ===== INDICATOR CATEGORIES AND WEIGHTS =====

/**
 * Catégorisation intelligente des indicateurs avec pondérations
 * Basée sur l'analyse des 30+ indicateurs de Crypto-Toolbox
 */
export const INDICATOR_CATEGORIES = {
  // Indicateurs On-Chain Fondamentaux (60% du score) - Données blockchain pures
  onchain_fundamentals: {
    weight: 0.60,
    description: "Métriques blockchain fondamentales",
    indicators: {
      // Évaluation de prix vs valeur intrinsèque
      'mvrv': { weight: 0.25, invert: true }, // High MVRV = overvalued = bearish
      'mvrv_z_score': { weight: 0.25, invert: true },
      'nupl': { weight: 0.20, invert: true }, // High NUPL = profit zone = bearish
      'rupl_nupl': { weight: 0.20, invert: true },
      'rupl': { weight: 0.20, invert: true },
      
      // Métriques miniers et réseau
      'puell': { weight: 0.15, invert: false }, // Puell Multiple pattern varies
      'puell_multiple': { weight: 0.15, invert: false },
      'sopr': { weight: 0.10, invert: false }, // SOPR >1 = profits realized
      'rhodl': { weight: 0.05, invert: true }
    }
  },
  
  // Indicateurs Cycle/Techniques (30% du score) - Signaux de timing
  cycle_technical: {
    weight: 0.30,
    description: "Signaux de cycle et techniques",
    indicators: {
      'pi_cycle': { weight: 0.35, invert: true }, // High = top signal
      'pi': { weight: 0.35, invert: true },
      'cbbi': { weight: 0.30, invert: true }, // Colin Bicknell Bitcoin Index
      'rainbow': { weight: 0.20, invert: true }, // Rainbow Chart position
      'rsi': { weight: 0.15, invert: true }, // RSI Bitcoin mensuel
      'stock_to_flow': { weight: 0.0, invert: false } // Modèle controversé
    }
  },
  
  // Indicateurs de Sentiment (10% du score) - Psychologie de marché
  sentiment: {
    weight: 0.10,
    description: "Sentiment et psychologie de marché", 
    indicators: {
      'fear_greed': { weight: 0.60, invert: true }, // High Fear & Greed = bearish
      'fear_greed_7d': { weight: 0.40, invert: true },
      'fear': { weight: 0.60, invert: true }
    }
  }
};

/**
 * Fonction pour classer automatiquement un indicateur selon son nom
 */
export function classifyIndicator(indicatorName) {
  const name = indicatorName.toLowerCase().trim();
  
  // Patterns spéciaux pour indicateurs de Crypto-Toolbox
  const specialMappings = {
    'pi cycle': { category: 'cycle_technical', key: 'pi_cycle' },
    'cbbi': { category: 'cycle_technical', key: 'cbbi' },
    'mvrv z-score': { category: 'onchain_fundamentals', key: 'mvrv_z_score' },
    'mvrv': { category: 'onchain_fundamentals', key: 'mvrv' },
    'puell multiple': { category: 'onchain_fundamentals', key: 'puell_multiple' },
    'puell': { category: 'onchain_fundamentals', key: 'puell' },
    'rupl/nupl': { category: 'onchain_fundamentals', key: 'rupl_nupl' },
    'nupl': { category: 'onchain_fundamentals', key: 'nupl' },
    'rupl': { category: 'onchain_fundamentals', key: 'rupl' },
    'rsi bitcoin': { category: 'cycle_technical', key: 'rsi' },
    'rsi mensuel': { category: 'cycle_technical', key: 'rsi' },
    'rsi': { category: 'cycle_technical', key: 'rsi' },
    'fear & greed': { category: 'sentiment', key: 'fear_greed' },
    'fear and greed': { category: 'sentiment', key: 'fear_greed' },
    'sopr': { category: 'onchain_fundamentals', key: 'sopr' }
  };
  
  // Recherche par correspondance exacte d'abord
  for (const [pattern, mapping] of Object.entries(specialMappings)) {
    if (name.includes(pattern)) {
      const category = INDICATOR_CATEGORIES[mapping.category];
      const config = category.indicators[mapping.key];
      
      if (config) {
        return {
          category: mapping.category,
          key: mapping.key,
          weight: config.weight,
          invert: config.invert,
          categoryWeight: category.weight
        };
      }
    }
  }
  
  // Recherche générique dans chaque catégorie
  for (const [categoryKey, category] of Object.entries(INDICATOR_CATEGORIES)) {
    for (const [indicatorKey, config] of Object.entries(category.indicators)) {
      // Correspondance partielle
      if (name.includes(indicatorKey) || indicatorKey.includes(name.split(' ')[0])) {
        return {
          category: categoryKey,
          key: indicatorKey,
          weight: config.weight,
          invert: config.invert,
          categoryWeight: category.weight
        };
      }
    }
  }
  
  // Par défaut, classer comme sentiment avec poids faible
  console.warn(`⚠️ Unknown indicator classification: ${indicatorName}`);
  return {
    category: 'sentiment',
    key: 'unknown',
    weight: 0.1,
    invert: false,
    categoryWeight: 0.10
  };
}

/**
 * Configuration des indicateurs on-chain avec leurs seuils (LEGACY)
 */
export const INDICATORS_CONFIG = {
  mvrv: {
    name: "MVRV Ratio",
    description: "Market Value to Realized Value",
    thresholds: {
      extreme_high: 3.5,  // Pic de cycle probable
      high: 2.5,          // Zone de distribution
      normal_high: 1.8,   // Marché chaud
      normal: 1.0,        // Équilibre
      normal_low: 0.8,    // Marché froid
      low: 0.6,           // Zone d'accumulation
      extreme_low: 0.4    // Creux de cycle probable
    },
    weight: 0.25,
    api_available: true
  },
  
  nvt: {
    name: "NVT Ratio", 
    description: "Network Value to Transactions",
    thresholds: {
      extreme_high: 150,  // Très surévalué
      high: 100,          // Surévalué
      normal_high: 75,    // Cher
      normal: 50,         // Équilibre
      normal_low: 35,     // Bon marché
      low: 25,            // Sous-évalué
      extreme_low: 15     // Très sous-évalué
    },
    weight: 0.20,
    api_available: true
  },

  puell_multiple: {
    name: "Puell Multiple",
    description: "Revenus miniers vs moyenne 365j",
    thresholds: {
      extreme_high: 4.0,  // Pic minier - Vente probable
      high: 2.5,          // Zone de distribution
      normal_high: 1.5,   // Au-dessus de la moyenne
      normal: 1.0,        // Moyenne historique
      normal_low: 0.8,    // Sous la moyenne
      low: 0.5,           // Zone d'accumulation
      extreme_low: 0.3    // Capitulation minière
    },
    weight: 0.15,
    api_available: true
  },

  rhodl: {
    name: "RHODL Ratio",
    description: "Realized HODL Ratio",
    thresholds: {
      extreme_high: 50000, // Pic de cycle
      high: 30000,         // Zone de distribution
      normal_high: 20000,  // Marché chaud
      normal: 10000,       // Équilibre
      normal_low: 7000,    // Marché froid
      low: 5000,           // Accumulation
      extreme_low: 3000    // Creux de cycle
    },
    weight: 0.25,
    api_available: false // Plus complexe à calculer
  },

  fear_greed: {
    name: "Fear & Greed Index",
    description: "Sentiment de marché",
    thresholds: {
      extreme_high: 90,   // Extrême cupidité - Vente
      high: 75,           // Cupidité
      normal_high: 60,    // Optimisme
      normal: 50,         // Neutre
      normal_low: 40,     // Peur
      low: 25,            // Peur importante
      extreme_low: 10     // Extrême peur - Achat
    },
    weight: 0.10,
    api_available: true,
    contrarian: true // Indicateur contrarian
  },

  ahr999: {
    name: "Ahr999 Index",
    description: "Indicateur d'achat Bitcoin à long terme",
    thresholds: {
      extreme_high: 4.0,  // Très surévalué
      high: 2.0,          // Surévalué  
      normal_high: 1.2,   // Cher
      normal: 0.8,        // Équilibre
      normal_low: 0.45,   // Zone d'accumulation
      low: 0.25,          // Excellente opportunité
      extreme_low: 0.1    // Opportunité exceptionnelle
    },
    weight: 0.15,
    api_available: true,
    contrarian: true // Plus bas = meilleur pour acheter
  },

  nupl: {
    name: "NUPL (Net Unrealized Profit/Loss)",
    description: "Profit/perte non réalisé du réseau",
    thresholds: {
      extreme_high: 90,   // Euphorie excessive
      high: 75,           // Euphorie/Cupidité
      normal_high: 60,    // Optimisme
      normal: 50,         // Croyance/Déni
      normal_low: 40,     // Espoir/Peur
      low: 25,            // Capitulation
      extreme_low: 10     // Capitulation extrême
    },
    weight: 0.20,
    api_available: true
  },

  rsi: {
    name: "RSI Bitcoin",
    description: "Relative Strength Index pour Bitcoin",
    thresholds: {
      extreme_high: 80,   // Très suracheté
      high: 70,           // Suracheté
      normal_high: 60,    // Tendance haussière
      normal: 50,         // Neutre
      normal_low: 40,     // Tendance baissière
      low: 30,            // Survendu
      extreme_low: 20     // Très survendu
    },
    weight: 0.10,
    api_available: true
  },

  sopr: {
    name: "SOPR (Spent Output Profit Ratio)",
    description: "Ratio de profit des sorties dépensées",
    thresholds: {
      extreme_high: 90,   // Très profitable
      high: 75,           // Profitable
      normal_high: 60,    // Légèrement profitable
      normal: 50,         // Équilibre
      normal_low: 40,     // Légèrement non profitable
      low: 25,            // Non profitable
      extreme_low: 10     // Très non profitable
    },
    weight: 0.10,
    api_available: true
  },

  stock_to_flow_deviation: {
    name: "Stock-to-Flow Deviation",
    description: "Écart entre prix réel et modèle S2F",
    thresholds: {
      extreme_high: 200,  // Très au-dessus du modèle
      high: 100,          // Au-dessus du modèle
      normal_high: 50,    // Légèrement au-dessus
      normal: 0,          // Conforme au modèle
      normal_low: -25,    // Légèrement en dessous
      low: -50,           // En dessous du modèle
      extreme_low: -75    // Très en dessous
    },
    weight: 0.15,
    api_available: false // Calcul custom requis
  }
};

/**
 * Convertit une valeur d'indicateur en score de cycle (0-100)
 */
function indicatorToScore(value, config) {
  const { thresholds, contrarian } = config;
  let score = 50; // Score neutre par défaut

  // Déterminer le niveau de l'indicateur
  if (value >= thresholds.extreme_high) {
    score = contrarian ? 10 : 95;
  } else if (value >= thresholds.high) {
    score = contrarian ? 25 : 85;
  } else if (value >= thresholds.normal_high) {
    score = contrarian ? 40 : 70;
  } else if (value >= thresholds.normal) {
    score = 50;
  } else if (value >= thresholds.normal_low) {
    score = contrarian ? 60 : 40;
  } else if (value >= thresholds.low) {
    score = contrarian ? 75 : 25;
  } else {
    score = contrarian ? 90 : 15;
  }

  return score;
}

/**
 * Export cache stats and control functions
 */
export function getCacheStats() {
  return intelligentCache.getStats();
}

export function clearCache() {
  intelligentCache.clear();
  console.log('🧹 OnChain indicators cache cleared');
}

export function invalidateCache(key) {
  intelligentCache.invalidate(key);
  console.log(`🔄 Cache invalidated for: ${key}`);
}

/**
 * Optimized fetch with performance monitoring and rate limiting
 */
async function performanceMonitoredFetch(url, options = {}) {
  const startTime = performance.now();
  
  try {
    const response = await fetch(url, {
      ...options,
      // Add timeout to prevent hanging requests
      signal: AbortSignal.timeout(10000) // 10 second timeout
    });
    
    const endTime = performance.now();
    const responseTime = endTime - startTime;
    
    // Update performance metrics
    const stats = intelligentCache.performanceMetrics;
    stats.avgResponseTime = stats.avgResponseTime === 0 
      ? responseTime 
      : (stats.avgResponseTime + responseTime) / 2;
    
    console.log(`📡 API response time: ${Math.round(responseTime)}ms`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return response;
  } catch (error) {
    const endTime = performance.now();
    const responseTime = endTime - startTime;
    
    if (error.name === 'TimeoutError') {
      console.warn('⏰ API request timed out after 10s');
    } else if (error.name === 'AbortError') {
      console.warn('🚫 API request was aborted');
    } else {
      console.warn(`🌐 Network error (${Math.round(responseTime)}ms):`, error.message);
    }
    
    throw error;
  }
}

/**
 * Récupère les données Fear & Greed Index avec cache intelligent
 */
async function fetchFearGreedIndex() {
  try {
    // Check intelligent cache first
    const cached = intelligentCache.get('fear_greed');
    if (cached) {
      console.log('📊 Fear & Greed from intelligent cache');
      return cached;
    }

    console.log('📡 Fetching Fear & Greed from API...');
    const response = await performanceMonitoredFetch('https://api.alternative.me/fng/?limit=1');
    const data = await response.json();
    if (data.data && data.data[0]) {
      const result = {
        value: parseInt(data.data[0].value),
        classification: data.data[0].value_classification,
        timestamp: new Date(data.data[0].timestamp * 1000),
        source: 'Alternative.me'
      };
      
      // Store in intelligent cache
      intelligentCache.set('fear_greed', result);
      console.log('💾 Fear & Greed cached with adaptive TTL');
      
      return result;
    }
    throw new Error('Invalid response format');
  } catch (error) {
    console.warn('Fear & Greed Index fetch failed:', error.message);
    return null;
  }
}

/**
 * Récupère les indicateurs depuis Crypto-Toolbox.vercel.app
 */
export async function fetchCryptoToolboxIndicators() {
  console.log('🌐 Fetching indicators from Crypto-Toolbox API...');
  
  try {
    const cached = intelligentCache.get('cryptotoolbox_indicators');
    if (cached) {
      console.log('💾 Crypto-Toolbox indicators from cache');
      return cached;
    }
    
    // Appel au backend Python avec Playwright
    const response = await performanceMonitoredFetch('http://127.0.0.1:8001/api/crypto-toolbox');
    
    if (!response.ok) {
      throw new Error(`Backend API error: ${response.status} ${response.statusText}`);
    }
    
    const apiData = await response.json();
    console.log(`📊 API response:`, apiData);
    
    if (!apiData.success) {
      throw new Error(`API returned error: ${apiData.error}`);
    }
    
    // Convertir TOUS les indicateurs API en format pour le nouveau système
    const indicators = {};
    
    if (apiData.indicators && Array.isArray(apiData.indicators)) {
      console.log(`🔄 Processing ${apiData.indicators.length} raw indicators from API...`);
      
      apiData.indicators.forEach(indicator => {
        // Utiliser le nom original comme clé unique (pas de mapping restrictif)
        const originalName = indicator.name;
        const cleanKey = originalName.toLowerCase().replace(/[^a-z0-9]/g, '_');
        
        if (indicator.value_numeric !== undefined) {
          indicators[cleanKey] = {
            name: originalName,
            value_numeric: indicator.value_numeric,
            value: indicator.value, // Texte original "75.39%"
            raw_value: indicator.raw_value,
            threshold_numeric: indicator.threshold_numeric,
            threshold: indicator.threshold,
            raw_threshold: indicator.raw_threshold,
            in_critical_zone: indicator.in_critical_zone,
            threshold_operator: indicator.threshold_operator,
            scraped_at: apiData.scraped_at,
            source: 'crypto-toolbox'
          };
          
          console.log(`✅ Processed: ${originalName} = ${indicator.value_numeric}% ${indicator.in_critical_zone ? '🚨' : ''}`);
        } else {
          console.warn(`⚠️ Skipped indicator without numeric value: ${originalName}`);
        }
      });
    }
    
    console.log(`📊 Converted ${Object.keys(indicators).length} indicators from API`);
    console.log(`📊 Indicators:`, indicators);
    
    if (Object.keys(indicators).length > 0) {
      // Cache pour 24h - les indicateurs on-chain n'évoluent pas rapidement
      const CACHE_24H = 24 * 60 * 60 * 1000; // 24 heures
      intelligentCache.set('cryptotoolbox_indicators', indicators, CACHE_24H);
      console.log('💾 Crypto-Toolbox indicators cached for 24h');
      return indicators;
    }
    
    throw new Error('No valid indicators found in API response');
    
  } catch (error) {
    console.error('❌ Crypto-Toolbox API fetch failed:', error.message);
    
    // Si le backend est inaccessible, essayer de diagnostiquer
    if (error.message.includes('Failed to fetch') || error.message.includes('ERR_CONNECTION_REFUSED')) {
      console.error('🚨 Backend API seems to be down. Please ensure crypto_toolbox_api.py is running on port 8001');
    }
    
    return null;
  }
}

/**
 * Parse le HTML de Crypto-Toolbox pour extraire les indicateurs
 */
function parseCryptoToolboxHTML(html) {
  const indicators = {};
  
  try {
    // Créer un parser DOM
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    
    // Stratégie 1: Parser comme ton code Python - table tbody tr
    const tables = doc.querySelectorAll('table');
    console.log(`🔍 Found ${tables.length} tables to parse`);
    
    tables.forEach((table, tableIndex) => {
      // Chercher tbody tr comme dans ton code Python
      const rows = table.querySelectorAll('tbody tr');
      console.log(`🔍 Table ${tableIndex + 1}: Found ${rows.length} tbody rows`);
      
      if (rows.length === 0) {
        // Fallback: chercher tr directement
        const fallbackRows = table.querySelectorAll('tr');
        console.debug(`🔍 Table ${tableIndex + 1}: Fallback found ${fallbackRows.length} tr rows`);
        
        fallbackRows.forEach(row => parseTableRow(row, tableIndex, indicators));
      } else {
        rows.forEach(row => parseTableRow(row, tableIndex, indicators));
      }
    });
    
    function parseTableRow(row, tableIndex, indicators) {
      const cells = row.querySelectorAll('td');
      if (cells.length < 3) {
        console.debug(`🔍 Row skipped: only ${cells.length} cells`);
        return; // Ignorer les lignes avec moins de 3 colonnes
      }
      
      const name = cells[0]?.textContent?.trim();
      const valueText = cells[1]?.textContent?.trim();
      const thresholdText = cells[2]?.textContent?.trim();
      
      console.debug(`🔍 Raw row data: "${name}" | "${valueText}" | "${thresholdText}"`);
      
      // Vérifier que c'est une ligne de données valide
      if (name && valueText && !name.toLowerCase().includes('indicateur')) {
        // Extraire la valeur numérique (pourcentage ou nombre)
        const valueMatch = valueText.match(/[\d.,]+/);
        if (valueMatch) {
          const numericValue = parseFloat(valueMatch[0].replace(',', '.'));
          
          // Mapper les noms français vers nos clés standards
          const mappedKey = mapCryptoToolboxIndicatorName(name);
          if (mappedKey) {
            indicators[mappedKey] = {
              name: name,
              value_percent: numericValue,
              critical_threshold: thresholdText,
              source: 'Crypto-Toolbox',
              table: tableIndex + 1,
              raw_value: valueText,
              raw_threshold: thresholdText
            };
            
            console.debug(`✅ Mapped: ${name} → ${mappedKey} (${numericValue})`);
          } else {
            console.warn(`⚠️ Unmapped indicator: "${name}"`);
          }
        } else {
          console.warn(`⚠️ No numeric value found in: "${valueText}"`);
        }
      }
    }
    
    // Stratégie 2: Patterns regex en fallback
    if (Object.keys(indicators).length === 0) {
      console.debug('🔄 No table data found, trying regex patterns...');
      
      const patterns = [
        { name: 'mvrv', regex: /MVRV.*?([0-9.]+)%/gi, french: 'MVRV Z-Score' },
        { name: 'puell_multiple', regex: /Puell.*?([0-9.]+)%/gi, french: 'Puell Multiple' },
        { name: 'nupl', regex: /NUPL.*?([0-9.]+)%/gi, french: 'NUPL' },
        { name: 'rsi', regex: /RSI.*?([0-9.]+)%/gi, french: 'RSI Bitcoin' }
      ];
      
      patterns.forEach(pattern => {
        const match = pattern.regex.exec(html);
        if (match && match[1]) {
          indicators[pattern.name] = {
            name: pattern.french,
            value_percent: parseFloat(match[1]),
            source: 'Crypto-Toolbox (regex)',
            raw_value: match[0]
          };
          console.debug(`✅ Regex match: ${pattern.name} = ${match[1]}%`);
        }
      });
    }
    
  } catch (error) {
    console.error('❌ Crypto-Toolbox HTML parsing failed:', error.message);
  }
  
  return indicators;
}

/**
 * Mappe les noms d'indicateurs français de Crypto-Toolbox vers nos clés standards
 */
function mapCryptoToolboxIndicatorName(frenchName) {
  const name = frenchName.toLowerCase().trim();
  
  // Mapping des noms français vers clés standards (basé sur ton code Python)
  const mappings = {
    // Indicateurs de données principaux
    'mvrv z-score': 'mvrv',
    'mvrv': 'mvrv',
    'puell multiple': 'puell_multiple',
    'puell': 'puell_multiple',
    'nupl': 'nupl',
    'rupl/nupl': 'nupl', 
    'rsi mensuel': 'rsi',
    'rsi bitcoin': 'rsi',
    'rsi': 'rsi',
    'sopr (ma 90j)': 'sopr',
    'sopr': 'sopr',
    'coin days destroyed (ma 90j)': 'cdd',
    'coin days destroyed': 'cdd',
    'bmo (par prof. chaîne) (ema 7j)': 'bmo_7',
    'bmo (par prof. chaîne) (ema 30j)': 'bmo_30', 
    'bmo (par prof. chaîne) (ema 90j)': 'bmo_90',
    'bmo': 'bmo',
    
    // Autres indicateurs techniques
    'cbbi*': 'cbbi',
    'pi cycle': 'pi_cycle',
    'rhold': 'rhold',
    '2y ma': 'ma_2y',
    'trolololo trend line': 'trolololo',
    'reserve risk': 'reserve_risk',
    'woobull': 'woobull',
    'cointime mvrv-z score (ema 14j)': 'mvrv_cointime',
    'mayer mutiple': 'mayer_multiple',
    'mayer multiple': 'mayer_multiple',
    
    // Indicateurs sentiment
    'fear & greed (moyenne 7 jours)': 'fear_greed_7d',
    'fear & greed': 'fear_greed',
    'fear and greed': 'fear_greed',
    
    // Dominance et altcoins
    'dominance btc': 'btc_dominance',
    'altcoin season index': 'altseason',
    'altcoin': 'altseason',
    
    // Indicateurs Google trends
    'google trend "crypto"': 'google_crypto',
    'google trend "buy crypto"': 'google_buy_crypto', 
    'google trend "bitcoin"': 'google_bitcoin',
    'google trend "ethereum"': 'google_ethereum',
    
    // Indicateurs apps
    'coinbase app rank (us)': 'coinbase_rank_us',
    'binance app rank (fr)': 'binance_rank_fr',
    'binance app rank (uk)': 'binance_rank_uk',
    'crypto.com app rank (us)': 'crypto_com_rank_us',
    'phantom app rank (us)': 'phantom_rank_us',
    
    // Indicateurs temporels
    'jours depuis halving': 'days_since_halving',
    'days since ath': 'days_since_ath',
    'cycle time': 'cycle_time',
    
    // Autres
    'nombre de connectés jvc': 'jvc_users'
  };
  
  // Recherche exacte
  if (mappings[name]) {
    return mappings[name];
  }
  
  // Recherche par inclusion
  for (const [french, key] of Object.entries(mappings)) {
    if (name.includes(french) || french.includes(name)) {
      return key;
    }
  }
  
  console.warn(`⚠️ Unknown indicator name: "${frenchName}"`);
  return null;
}

/**
 * Convertit un pourcentage Crypto-Toolbox (0-100%) vers notre système de score
 * 0% = Accumulation extrême, 100% = Distribution extrême
 */
function convertCryptoToolboxPercentToScore(percent, isContrarian = false) {
  // Les pourcentages Crypto-Toolbox représentent la position dans le cycle
  // 0% = creux de marché, 100% = pic de marché
  
  if (isContrarian) {
    // Pour les indicateurs contrarian (Fear & Greed), inverser
    return Math.round(100 - percent);
  } else {
    // Pour les indicateurs standards, utiliser directement
    return Math.round(percent);
  }
}

/**
 * Récupère tous les indicateurs disponibles avec cache stable
 */
export async function fetchAllIndicators() {
  console.debug('🔍 Fetching REAL on-chain indicators from unified backend...');
  
  const indicators = {};
  const errors = [];
  
  try {
    // 1. Fetch all indicators from Crypto-Toolbox backend (30+ indicators)
    console.debug('🌐 Calling fetchCryptoToolboxIndicators for all indicators...');
    const cryptoToolboxData = await fetchCryptoToolboxIndicators();
    console.debug('🔍 CryptoToolbox result:', cryptoToolboxData);
    
    const toolboxAvailable = !!(cryptoToolboxData && Object.keys(cryptoToolboxData).filter(k => !k.startsWith('_')).length > 0);
    if (toolboxAvailable) {
      // Process all indicators from the backend
      Object.entries(cryptoToolboxData).forEach(([key, data]) => {
        if (key.startsWith('_') || !data || typeof data !== 'object') {
          return; // Skip metadata
        }
        
        // Use the backend data directly without double conversion
        indicators[key] = {
          name: data.name,
          value: data.value_numeric, // Raw percentage value
          value_numeric: data.value_numeric,
          raw_value: data.raw_value,
          threshold_numeric: data.threshold_numeric,
          in_critical_zone: data.in_critical_zone,
          threshold: data.threshold,
          raw_threshold: data.raw_threshold,
          threshold_operator: data.threshold_operator,
          source: data.source || 'crypto-toolbox',
          scraped_at: data.scraped_at,
          timestamp: new Date()
        };
        
        console.debug(`✅ ${data.name} loaded: ${data.value_numeric}% ${data.in_critical_zone ? '🚨' : ''}`);
      });
      
      console.debug(`✅ Total ${Object.keys(indicators).length} indicators loaded from Crypto-Toolbox`);
      
    } else {
      errors.push('Crypto-Toolbox: Backend unavailable - no indicators loaded');
      console.warn('⚠️ Crypto-Toolbox backend failed, no indicators loaded');
    }
    
    // 2. Add Fear & Greed from Alternative.me only if toolbox data is present (no silent fallback)
    const fearGreedExists = Object.keys(indicators).some(key => 
      indicators[key].name?.toLowerCase().includes('fear') && 
      indicators[key].name?.toLowerCase().includes('greed')
    );
    if (toolboxAvailable && !fearGreedExists) {
      console.debug('🔄 Adding Fear & Greed as fallback indicator...');
      const fgData = await fetchFearGreedIndex();
      if (fgData) {
        indicators.fear_greed_fallback = {
          name: 'Fear & Greed Index',
          value: fgData.value,
          value_numeric: fgData.value,
          classification: fgData.classification,
          source: 'alternative.me',
          timestamp: fgData.timestamp,
          in_critical_zone: fgData.value > 80 || fgData.value < 20
        };
        console.debug('✅ Fear & Greed fallback loaded:', fgData.value, fgData.classification);
      } else {
        errors.push('Fear & Greed fallback API also unavailable');
      }
    }
    
    const successCount = Object.keys(indicators).filter(k => k !== '_metadata').length;
    console.debug(`✅ Real indicators loaded: ${successCount} total indicators`);
    
    if (errors.length > 0) {
      console.warn('⚠️ Some fallback indicators unavailable:', errors);
    }
    
    // Log indicator summary by source
    const sourceStats = {};
    Object.values(indicators).forEach(ind => {
      if (ind.source) {
        sourceStats[ind.source] = (sourceStats[ind.source] || 0) + 1;
      }
    });
    
    console.debug('📊 Indicators by source:', sourceStats);
    
    return {
      ...indicators,
      _metadata: {
        available_count: successCount,
        missing_apis: errors,
        source_stats: sourceStats,
        message: `${successCount} real indicators loaded from Crypto-Toolbox backend.`,
        last_updated: new Date().toISOString()
      }
    };
    
  } catch (error) {
    console.error('❌ Error fetching real indicators:', error);
    return {
      _metadata: {
        available_count: 0,
        error: error.message,
        message: 'Scraping Crypto-Toolbox indisponible',
        last_updated: new Date().toISOString()
      }
    };
  }
}

/**
 * Normalise et inverse un score d'indicateur selon sa configuration
 */
function normalizeAndInvertScore(rawValue, classification) {
  // Normaliser sur 0-100 (les valeurs Crypto-Toolbox sont déjà en %)
  let normalizedScore = Math.max(0, Math.min(100, rawValue));
  
  // Inverser si nécessaire (pour les indicateurs bearish quand élevés)
  if (classification.invert) {
    normalizedScore = 100 - normalizedScore;
  }
  
  return normalizedScore;
}

/**
 * Calcule un score composite amélioré avec catégorisation intelligente
 * Intègre les 30+ indicateurs réels de Crypto-Toolbox
 */
export function calculateCompositeScore(indicators) {
  if (!indicators || Object.keys(indicators).filter(k => k !== '_metadata').length === 0) {
    return {
      score: null,
      confidence: 0,
      contributors: [],
      categoryBreakdown: {},
      criticalZoneCount: 0,
      message: 'Aucun indicateur disponible'
    };
  }
  
  // Structures pour calculer le score par catégorie
  const categoryScores = {};
  const categoryWeights = {};
  const categoryContributors = {};
  let totalCriticalZone = 0;
  
  // Initialiser les catégories
  Object.keys(INDICATOR_CATEGORIES).forEach(categoryKey => {
    categoryScores[categoryKey] = 0;
    categoryWeights[categoryKey] = 0;
    categoryContributors[categoryKey] = [];
  });
  
  // Traiter chaque indicateur avec la nouvelle logique
  Object.entries(indicators).forEach(([key, data]) => {
    // Ignorer les métadonnées
    if (key.startsWith('_') || !data || typeof data !== 'object') {
      return;
    }
    
    // Classer l'indicateur automatiquement
    let indicatorName = data.name || key;
    const classification = classifyIndicator(indicatorName);
    
    // Obtenir la valeur numérique de l'indicateur
    let rawValue = data.value_numeric || data.value || data.percent_in_cycle;
    
    if (typeof rawValue !== 'number') {
      console.warn(`⚠️ Invalid numeric value for ${indicatorName}: ${rawValue}`);
      return;
    }
    
    // Normaliser et inverser si nécessaire
    const normalizedScore = normalizeAndInvertScore(rawValue, classification);
    
    // Calculer la contribution pondérée
    const indicatorWeight = classification.weight * classification.categoryWeight;
    const contribution = normalizedScore * indicatorWeight;
    
    // Ajouter à la catégorie appropriée
    const category = classification.category;
    categoryScores[category] += contribution;
    categoryWeights[category] += indicatorWeight;
    
    // Compter les zones critiques
    if (data.in_critical_zone) {
      totalCriticalZone++;
    }
    
    // Ajouter aux contributeurs
    categoryContributors[category].push({
      name: indicatorName,
      originalValue: rawValue,
      normalizedScore: normalizedScore,
      weight: indicatorWeight,
      contribution: contribution,
      inCriticalZone: data.in_critical_zone || false,
      classification: classification,
      raw_threshold: data.raw_threshold
    });
    
    console.debug(`📊 ${indicatorName}: ${rawValue}% → ${normalizedScore} (${category}, weight: ${indicatorWeight.toFixed(3)})`);
  });
  
  // Calculer le score final par catégorie puis globalement
  let finalScore = 0;
  let totalWeight = 0;
  const categoryBreakdown = {};
  
  Object.entries(categoryScores).forEach(([category, score]) => {
    const weight = categoryWeights[category];
    if (weight > 0) {
      const categoryScore = score / weight;
      const categoryWeight = INDICATOR_CATEGORIES[category].weight;
      
      finalScore += categoryScore * categoryWeight;
      totalWeight += categoryWeight;
      
      categoryBreakdown[category] = {
        score: Math.round(categoryScore),
        weight: categoryWeight,
        contributorsCount: categoryContributors[category].length,
        description: INDICATOR_CATEGORIES[category].description,
        contributors: categoryContributors[category].sort((a, b) => b.contribution - a.contribution)
      };
    }
  });
  
  if (totalWeight === 0) {
    return {
      score: null,
      confidence: 0,
      contributors: [],
      categoryBreakdown: {},
      criticalZoneCount: 0,
      message: 'Aucun indicateur réel disponible pour calculer le score composite'
    };
  }
  
  const compositeScore = finalScore / totalWeight;
  
  // Calculer la confiance basée sur le nombre d'indicateurs et la diversité des catégories
  const totalIndicators = Object.values(categoryContributors).flat().length;
  const activeCategories = Object.keys(categoryBreakdown).length;
  const confidence = Math.min(0.95, (totalIndicators * 0.05) + (activeCategories * 0.15));
  
  // Assembler tous les contributeurs pour la compatibilité
  const allContributors = Object.values(categoryContributors).flat();
  
  return {
    score: Math.round(compositeScore),
    confidence: Math.round(confidence * 100) / 100,
    contributors: allContributors.sort((a, b) => b.contribution - a.contribution),
    categoryBreakdown: categoryBreakdown,
    criticalZoneCount: totalCriticalZone,
    totalIndicators: totalIndicators,
    activeCategories: activeCategories,
    message: `Score composite basé sur ${totalIndicators} indicateur(s) réel(s) dans ${activeCategories} catégorie(s) (${totalCriticalZone} en zone critique)`
  };
}

/**
 * Combine le score de cycle sigmoïde avec les indicateurs on-chain
 */
export function enhanceCycleScore(sigmoidScore, onchainWeight = 0.3) {
  return new Promise(async (resolve) => {
    try {
      // Récupérer les indicateurs
      const indicators = await fetchAllIndicators();
      const composite = calculateCompositeScore(indicators);
      
      // Blend des scores
      const enhancedScore = sigmoidScore * (1 - onchainWeight) + composite.score * onchainWeight;
      
      resolve({
        original_sigmoid: sigmoidScore,
        onchain_composite: composite.score,
        enhanced_score: Math.round(enhancedScore),
        onchain_weight: onchainWeight,
        confidence: composite.confidence,
        indicators_used: Object.keys(indicators),
        contributors: composite.contributors
      });
      
    } catch (error) {
      console.error('Error enhancing cycle score:', error);
      resolve({
        original_sigmoid: sigmoidScore,
        enhanced_score: sigmoidScore,
        error: error.message,
        confidence: 0.5
      });
    }
  });
}

/**
 * Analyse la divergence entre modèle sigmoïde et indicateurs
 */
export function analyzeDivergence(sigmoidScore, indicators) {
  const composite = calculateCompositeScore(indicators);
  const divergence = Math.abs(sigmoidScore - composite.score);
  
  let signal = 'neutral';
  let message = '';
  
  if (divergence > 30) {
    if (composite.score > sigmoidScore) {
      signal = 'onchain_bullish';
      message = 'Indicateurs on-chain plus optimistes que le modèle de cycle';
    } else {
      signal = 'onchain_bearish';
      message = 'Indicateurs on-chain plus pessimistes que le modèle de cycle';
    }
  } else if (divergence > 15) {
    signal = 'moderate_divergence';
    message = 'Divergence modérée entre modèle et indicateurs';
  } else {
    signal = 'convergence';
    message = 'Bonne convergence entre modèle et indicateurs';
  }
  
  return {
    divergence_magnitude: divergence,
    signal,
    message,
    sigmoid_score: sigmoidScore,
    onchain_score: composite.score,
    confidence: composite.confidence
  };
}

/**
 * Recommandations basées sur les indicateurs
 */
export function generateRecommendations(enhancedData) {
  const recommendations = [];
  const { enhanced_score, contributors, confidence } = enhancedData;
  
  // Recommandations basées sur le score enhancé
  if (enhanced_score > 80) {
    recommendations.push({
      type: 'warning',
      title: 'Zone de Distribution Probable',
      message: 'Score élevé - Considérer la prise de profits',
      action: 'Réduire l\'exposition aux altcoins, augmenter les stables'
    });
  } else if (enhanced_score < 30) {
    recommendations.push({
      type: 'opportunity',
      title: 'Zone d\'Accumulation Probable', 
      message: 'Score faible - Opportunité d\'achat potentielle',
      action: 'Considérer l\'augmentation de l\'allocation Bitcoin/ETH'
    });
  }
  
  // Recommandations spécifiques aux indicateurs
  if (contributors.length > 0) {
    const topContributor = contributors[0];
    
    if (topContributor.name === 'Fear & Greed Index' && topContributor.score > 80) {
      recommendations.push({
        type: 'contrarian',
        title: 'Extrême Cupidité Détectée',
        message: 'Sentiment très optimiste - Signal contrarian',
        action: 'Prudence recommandée, pic potentiel proche'
      });
    }
    
    if (topContributor.name === 'MVRV Ratio' && topContributor.score > 85) {
      recommendations.push({
        type: 'technical',
        title: 'MVRV en Zone de Danger',
        message: 'Ratio MVRV élevé - Historiquement près des pics',
        action: 'Surveiller étroitement, préparer stratégie de sortie'
      });
    }
  }
  
  // Recommandations basées sur la confiance
  if (confidence < 0.4) {
    recommendations.push({
      type: 'info',
      title: 'Données Limitées',
      message: 'Peu d\'indicateurs disponibles - Confiance réduite',
      action: 'Intégrer plus de sources de données on-chain'
    });
  }
  
  return recommendations;
}

/**
 * Retourne le statut et les sources de chaque indicateur
 */
export function getIndicatorSources() {
  return {
    fear_greed: {
      status: 'ACTIVE',
      source: 'Alternative.me API',
      url: 'https://api.alternative.me/fng/',
      reliability: 'Production ready',
      cost: 'Free',
      update_frequency: 'Daily'
    },
    mvrv: {
      status: 'SIMULATED',
      source: 'Historical patterns',
      possible_apis: [
        'Glassnode.com (Premium)',
        'CoinMetrics.io (Professional)',
        'LookIntoBitcoin.com (Charts only)'
      ],
      cost: '$39-$499/month',
      complexity: 'Medium',
      implementation_priority: 'High'
    },
    nvt: {
      status: 'SIMULATED',
      source: 'Cycle-based estimation',
      calculation: '(Market Cap) / (Transaction Volume USD * 365)',
      possible_data_sources: [
        'CoinGecko API (market cap) - Free',
        'Blockchain.info API (volume) - Free',
        'CoinMetrics (direct NVT) - Paid'
      ],
      complexity: 'Medium',
      implementation_priority: 'Medium'
    },
    puell_multiple: {
      status: 'SIMULATED',
      source: 'Mining revenue estimation',
      calculation: '(Daily Mining Revenue USD) / (365-day MA Mining Revenue)',
      required_data: [
        'Daily Bitcoin issuance (blocks * 6.25 BTC)',
        'Bitcoin price (CoinGecko)',
        'Transaction fees (Blockchain.info)'
      ],
      complexity: 'High',
      implementation_priority: 'Low'
    },
    rhodl: {
      status: 'NOT_IMPLEMENTED',
      source: 'N/A',
      reason: 'Requires complex UTXO age analysis',
      possible_apis: ['Glassnode (Premium only)'],
      cost: '$99+/month',
      complexity: 'Very High',
      implementation_priority: 'Very Low'
    }
  };
}

/**
 * Fournit des instructions pour intégrer de vraies APIs
 */
export function getImplementationGuide() {
  return {
    priority_1_nvt: {
      title: 'Intégrer NVT Ratio réel',
      steps: [
        '1. Récupérer market cap Bitcoin via CoinGecko API gratuite',
        '2. Récupérer volume transactions via Blockchain.info API',
        '3. Calculer: NVT = MarketCap / (VolumeUSD * 365)',
        '4. Remplacer simulateNVT() par fetchRealNVT()'
      ],
      estimated_time: '4-6 heures',
      difficulty: 'Medium'
    },
    priority_2_mvrv: {
      title: 'Intégrer MVRV Ratio via API payante',
      steps: [
        '1. Souscrire à Glassnode API (plan Studio $39/mois)',
        '2. Implémenter fetchGlassnodeMVRV() avec authentification',
        '3. Gérer les limites de taux (rate limiting)',
        '4. Fallback sur simulation si API indisponible'
      ],
      estimated_time: '6-8 heures',
      difficulty: 'Medium-High'
    },
    priority_3_puell: {
      title: 'Calculer Puell Multiple réel',
      steps: [
        '1. Récupérer données de blocs via Blockchain.info',
        '2. Calculer revenus miniers quotidiens',
        '3. Implémenter moyenne mobile 365 jours',
        '4. Optimiser pour performance (cache agressif)'
      ],
      estimated_time: '8-12 heures',
      difficulty: 'High'
    }
  };
}
