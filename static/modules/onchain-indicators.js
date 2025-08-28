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

// Cache pour les données d'indicateurs (évite les appels API répétés)
let indicatorsCache = new Map();
const CACHE_DURATION = 10 * 60 * 1000; // 10 minutes

// Cache pour stabiliser les valeurs simulées (évite la variabilité au refresh)
let stableSimulationCache = null;
let simulationCacheTimestamp = 0;
const SIMULATION_CACHE_DURATION = 5 * 60 * 1000; // 5 minutes pour stabilité

/**
 * Configuration des indicateurs on-chain avec leurs seuils
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
 * Récupère les données Fear & Greed Index
 */
async function fetchFearGreedIndex() {
  try {
    const response = await fetch('https://api.alternative.me/fng/?limit=1');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    
    const data = await response.json();
    if (data.data && data.data[0]) {
      return {
        value: parseInt(data.data[0].value),
        classification: data.data[0].value_classification,
        timestamp: new Date(data.data[0].timestamp * 1000),
        source: 'Alternative.me'
      };
    }
    throw new Error('Invalid response format');
  } catch (error) {
    console.warn('Fear & Greed Index fetch failed:', error.message);
    return null;
  }
}

/**
 * Simule des données MVRV (en attendant l'API réelle) - Version stable
 */
function simulateMVRV() {
  // Vérifier le cache de simulation
  if (stableSimulationCache && (Date.now() - simulationCacheTimestamp < SIMULATION_CACHE_DURATION)) {
    return stableSimulationCache.mvrv;
  }
  
  // Simulation basée sur les patterns historiques
  const now = new Date();
  const currentCycleMonths = ((now - new Date('2024-04-20')) / (1000 * 60 * 60 * 24 * 30.44));
  
  // MVRV suit généralement le cycle avec quelques mois d'avance
  let baseValue = 1.0;
  
  if (currentCycleMonths < 6) {
    baseValue = 0.8 + (currentCycleMonths / 6) * 0.4; // 0.8 → 1.2
  } else if (currentCycleMonths < 18) {
    baseValue = 1.2 + ((currentCycleMonths - 6) / 12) * 1.3; // 1.2 → 2.5
  } else if (currentCycleMonths < 24) {
    baseValue = 2.5 + ((currentCycleMonths - 18) / 6) * 1.0; // 2.5 → 3.5
  } else {
    baseValue = 3.5 - ((currentCycleMonths - 24) / 24) * 2.7; // 3.5 → 0.8
  }
  
  // Bruit réduit et basé sur la date pour stabilité
  const dayOfYear = Math.floor((now - new Date(now.getFullYear(), 0, 0)) / (1000 * 60 * 60 * 24));
  const stableNoise = Math.sin(dayOfYear * 0.017) * 0.1; // Variation lente et prévisible
  
  return Math.max(0.3, baseValue + stableNoise);
}

/**
 * Simule des données NVT - Version stable
 */
function simulateNVT() {
  // Vérifier le cache de simulation
  if (stableSimulationCache && (Date.now() - simulationCacheTimestamp < SIMULATION_CACHE_DURATION)) {
    return stableSimulationCache.nvt;
  }
  
  const currentCycleMonths = ((new Date() - new Date('2024-04-20')) / (1000 * 60 * 60 * 24 * 30.44));
  
  // NVT inversement corrélé aux transactions (plus de spéculation = NVT élevé)
  let baseValue = 50;
  
  if (currentCycleMonths < 12) {
    baseValue = 45 - (currentCycleMonths / 12) * 20; // 45 → 25 (plus d'utilité)
  } else if (currentCycleMonths < 20) {
    baseValue = 25 + ((currentCycleMonths - 12) / 8) * 75; // 25 → 100 (spéculation)
  } else {
    baseValue = 100 + ((currentCycleMonths - 20) / 20) * 50; // 100 → 150
  }
  
  // Bruit réduit et stable basé sur la semaine
  const now = new Date();
  const weekOfYear = Math.floor(((now - new Date(now.getFullYear(), 0, 0)) / (1000 * 60 * 60 * 24)) / 7);
  const stableNoise = Math.cos(weekOfYear * 0.1) * 7; // Variation lente
  
  return Math.max(15, baseValue + stableNoise);
}

/**
 * Simule le Puell Multiple - Version stable
 */
function simulatePuellMultiple() {
  // Vérifier le cache de simulation
  if (stableSimulationCache && (Date.now() - simulationCacheTimestamp < SIMULATION_CACHE_DURATION)) {
    return stableSimulationCache.puell;
  }
  
  const currentCycleMonths = ((new Date() - new Date('2024-04-20')) / (1000 * 60 * 60 * 24 * 30.44));
  
  // Puell Multiple tend à être élevé avant les pics et bas après
  let baseValue = 1.0;
  
  if (currentCycleMonths < 8) {
    baseValue = 0.6 + (currentCycleMonths / 8) * 0.5; // 0.6 → 1.1
  } else if (currentCycleMonths < 20) {
    baseValue = 1.1 + ((currentCycleMonths - 8) / 12) * 1.4; // 1.1 → 2.5
  } else {
    baseValue = 2.5 - ((currentCycleMonths - 20) / 28) * 1.9; // 2.5 → 0.6
  }
  
  // Variation stable basée sur le mois
  const now = new Date();
  const monthNoise = Math.sin((now.getMonth() + 1) * 0.5) * 0.15;
  
  return Math.max(0.3, baseValue + monthNoise);
}

/**
 * Récupère tous les indicateurs disponibles avec cache stable
 */
export async function fetchAllIndicators() {
  console.log('🔍 Fetching on-chain indicators...');
  
  const indicators = {};
  
  try {
    // Initialiser le cache stable si nécessaire
    const now = Date.now();
    if (!stableSimulationCache || (now - simulationCacheTimestamp >= SIMULATION_CACHE_DURATION)) {
      console.log('🔄 Refreshing simulation cache...');
      
      stableSimulationCache = {
        mvrv: simulateMVRV(),
        nvt: simulateNVT(),
        puell: simulatePuellMultiple(),
        timestamp: now
      };
      simulationCacheTimestamp = now;
    }
    
    // Fear & Greed Index (API réelle)
    const fgData = await fetchFearGreedIndex();
    if (fgData) {
      indicators.fear_greed = {
        value: fgData.value,
        score: indicatorToScore(fgData.value, INDICATORS_CONFIG.fear_greed),
        classification: fgData.classification,
        source: fgData.source,
        timestamp: fgData.timestamp
      };
    }
    
    // MVRV (simulation stable)
    const mvrvValue = stableSimulationCache.mvrv;
    indicators.mvrv = {
      value: parseFloat(mvrvValue.toFixed(3)),
      score: indicatorToScore(mvrvValue, INDICATORS_CONFIG.mvrv),
      source: 'Simulated (stable)',
      timestamp: new Date(stableSimulationCache.timestamp)
    };
    
    // NVT (simulation stable)
    const nvtValue = stableSimulationCache.nvt;
    indicators.nvt = {
      value: parseFloat(nvtValue.toFixed(1)),
      score: indicatorToScore(nvtValue, INDICATORS_CONFIG.nvt),
      source: 'Simulated (stable)', 
      timestamp: new Date(stableSimulationCache.timestamp)
    };
    
    // Puell Multiple (simulation stable)
    const puellValue = stableSimulationCache.puell;
    indicators.puell_multiple = {
      value: parseFloat(puellValue.toFixed(3)),
      score: indicatorToScore(puellValue, INDICATORS_CONFIG.puell_multiple),
      source: 'Simulated (stable)',
      timestamp: new Date(stableSimulationCache.timestamp)
    };
    
    console.log('✅ Indicators fetched (stable):', Object.keys(indicators));
    console.log('🔍 MVRV:', mvrvValue.toFixed(3), 'Score:', indicators.mvrv.score);
    console.log('🔍 NVT:', nvtValue.toFixed(1), 'Score:', indicators.nvt.score);
    console.log('🔍 Puell:', puellValue.toFixed(3), 'Score:', indicators.puell_multiple.score);
    
    return indicators;
    
  } catch (error) {
    console.error('❌ Error fetching indicators:', error);
    return {};
  }
}

/**
 * Calcule un score composite basé sur les indicateurs on-chain
 */
export function calculateCompositeScore(indicators) {
  if (!indicators || Object.keys(indicators).length === 0) {
    return {
      score: 50,
      confidence: 0.1,
      contributors: [],
      message: 'Aucun indicateur disponible'
    };
  }
  
  let weightedSum = 0;
  let totalWeight = 0;
  const contributors = [];
  
  // Calculer la moyenne pondérée des scores
  Object.entries(indicators).forEach(([key, data]) => {
    const config = INDICATORS_CONFIG[key];
    if (config && typeof data.score === 'number') {
      const weight = config.weight;
      weightedSum += data.score * weight;
      totalWeight += weight;
      
      contributors.push({
        name: config.name,
        score: data.score,
        weight: weight,
        value: data.value,
        contribution: data.score * weight
      });
    }
  });
  
  const compositeScore = totalWeight > 0 ? weightedSum / totalWeight : 50;
  const confidence = Math.min(0.9, totalWeight * 1.5); // Plus d'indicateurs = plus de confiance
  
  return {
    score: Math.round(compositeScore),
    confidence: Math.round(confidence * 100) / 100,
    contributors: contributors.sort((a, b) => b.contribution - a.contribution),
    message: `Score composite basé sur ${contributors.length} indicateurs`
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