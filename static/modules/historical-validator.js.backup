/**
 * HISTORICAL VALIDATOR - Framework de validation historique pour système V2
 * 
 * Fonctionnalités :
 * 1. Simulation de données historiques par période de marché
 * 2. Validation des performances V1 vs V2
 * 3. Mesure de l'efficacité des corrélations
 * 4. Analyse des signaux contradictoires historiques
 */

import { calculateCompositeScoreV2, analyzeContradictorySignals } from './composite-score-v2.js';
// Legacy V1 removed - using V2 only

/**
 * Périodes de test historiques avec données de contexte
 */
export const HISTORICAL_PERIODS = {
  bull_2017: {
    name: 'Bull Run 2017',
    start: '2017-01-01',
    end: '2017-12-31',
    context: 'First major crypto bull run',
    expectedPhase: 'euphoria',
    keyEvents: ['BTC $20k peak', 'ICO bubble', 'Mainstream adoption'],
    expectedSignals: {
      onchain_pure: 'bearish', // High MVRV at top
      cycle_technical: 'bearish', // Technical overheating
      sentiment_social: 'bullish', // Extreme greed
      market_context: 'bearish' // Peak conditions
    }
  },
  
  bear_2018: {
    name: 'Bear Market 2018-2019',
    start: '2018-01-01', 
    end: '2019-12-31',
    context: 'Post-bubble correction and accumulation',
    expectedPhase: 'accumulation',
    keyEvents: ['80% crash', 'Capitulation', 'Institutional building'],
    expectedSignals: {
      onchain_pure: 'bullish', // Low MVRV, strong fundamentals
      cycle_technical: 'bullish', // Oversold conditions
      sentiment_social: 'bearish', // Extreme fear
      market_context: 'bullish' // Bottom formation
    }
  },
  
  bull_2020: {
    name: 'Bull Run 2020-2021',
    start: '2020-03-01',
    end: '2021-12-31', 
    context: 'Institutional adoption and COVID stimulus',
    expectedPhase: 'expansion',
    keyEvents: ['Tesla buys BTC', '$69k peak', 'NFT mania', 'DeFi summer'],
    expectedSignals: {
      onchain_pure: 'bearish', // High MVRV at peak
      cycle_technical: 'bearish', // Pi Cycle top
      sentiment_social: 'bullish', // Extreme greed again
      market_context: 'bearish' // Peak indicators
    }
  },
  
  bear_2022: {
    name: 'Bear Market 2022',
    start: '2022-01-01',
    end: '2022-12-31',
    context: 'Fed tightening and crypto winter',
    expectedPhase: 'distribution',
    keyEvents: ['Luna collapse', 'FTX implosion', 'Fed rates up'],
    expectedSignals: {
      onchain_pure: 'bullish', // Reset fundamentals
      cycle_technical: 'bullish', // Oversold bounce
      sentiment_social: 'bearish', // Extreme fear
      market_context: 'bullish' // Bottom signals
    }
  },
  
  current_2023: {
    name: 'Current Cycle 2023+',
    start: '2023-01-01',
    end: '2024-12-31',
    context: 'ETF approval and institutional return',
    expectedPhase: 'early_expansion',
    keyEvents: ['ETF approved', 'Institutional return', 'AI crypto boom'],
    expectedSignals: {
      onchain_pure: 'neutral', // Mixed signals
      cycle_technical: 'bullish', // Early bull signals
      sentiment_social: 'neutral', // Cautious optimism
      market_context: 'bullish' // Positive structure
    }
  }
};

/**
 * Générateur de nombres pseudo-aléatoires avec seed (déterministe)
 */
class SeededRandom {
  constructor(seed) {
    this.seed = seed;
  }
  
  next() {
    this.seed = (this.seed * 9301 + 49297) % 233280;
    return this.seed / 233280;
  }
}

/**
 * Génère des données d'indicateurs simulées pour une période historique
 */
export function generateHistoricalData(period, date, useDeterministicSeed = true) {
  const periodConfig = HISTORICAL_PERIODS[period];
  if (!periodConfig) {
    throw new Error(`Unknown historical period: ${period}`);
  }
  
  // Créer un seed basé sur la période et la date pour la déterminisme
  let random;
  if (useDeterministicSeed) {
    const seed = period.length * 1000 + date.split('-').reduce((sum, part) => sum + parseInt(part), 0);
    random = new SeededRandom(seed);
    const noise = () => (random.next() - 0.5) * 20; // ±10% noise déterministe
    var noiseFunc = noise;
  } else {
    const noise = () => (Math.random() - 0.5) * 20; // ±10% noise aléatoire
    var noiseFunc = noise;
  }
  
  // SUPPRIMÉ: Génération de données mockées - utiliser données réelles
  console.error('⚠️ historical-validator.js: Mock data generation disabled. Use real historical data sources.');
  
  const emptyData = {
    _metadata: {
      period: period,
      date: date,
      context: periodConfig.context,
      source: 'historical_simulation'
    }
  };
  
  // Retourner données vides au lieu de générer des valeurs mockées
  return emptyData;
}

/**
 * Valide les performances d'un système sur une période historique
 */
export async function validatePeriod(period, scoringFunction, label = 'System') {
  const periodConfig = HISTORICAL_PERIODS[period];
  if (!periodConfig) {
    throw new Error(`Unknown period: ${period}`);
  }
  
  (window.debugLogger?.debug || console.log)(`🧪 Validating ${label} for period: ${periodConfig.name}`);
  
  let correctSignals = 0;
  let totalSignals = 0;
  let scores = [];
  let contradictions = [];
  
  // Simuler plusieurs points dans la période (mensuel)
  const testDates = generateTestDates(periodConfig.start, periodConfig.end, 'monthly');
  
  for (const date of testDates) {
    try {
      const historicalData = generateHistoricalData(period, date);
      const result = scoringFunction(historicalData);
      
      if (result && typeof result.score === 'number') {
        scores.push(result.score);
        totalSignals++;
        
        // Validation basée sur la phase attendue du marché
        const expectedScore = getExpectedScore(periodConfig.expectedPhase, date, periodConfig);
        const scoreAccuracy = 100 - Math.abs(result.score - expectedScore);
        
        if (scoreAccuracy > 60) { // Seuil d'acceptation à 60%
          correctSignals++;
        }
        
        // Analyser les contradictions si disponible (V2 seulement)
        if (result.categoryBreakdown && analyzeContradictorySignals) {
          const periodContradictions = analyzeContradictorySignals(result.categoryBreakdown);
          contradictions.push(...periodContradictions);
        }
      }
    } catch (error) {
      (window.debugLogger?.warn || console.warn)(`⚠️ Error validating date ${date}:`, error.message);
    }
  }
  
  const accuracy = totalSignals > 0 ? (correctSignals / totalSignals) * 100 : 0;
  const avgScore = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
  const contradictionRate = contradictions.length / Math.max(totalSignals, 1);
  
  return {
    period: periodConfig.name,
    accuracy: accuracy,
    averageScore: avgScore,
    correctSignals: correctSignals,
    totalSignals: totalSignals,
    contradictions: contradictions.length,
    contradictionRate: contradictionRate,
    scores: scores
  };
}

/**
 * Compare les performances V1 vs V2 sur toutes les périodes
 */
export async function runFullBacktest() {
  (window.debugLogger?.debug || console.log)('🚀 Starting full historical backtest...');
  
  const results = {
    v1: {},
    v2: {},
    comparison: {}
  };
  
  for (const period of Object.keys(HISTORICAL_PERIODS)) {
    (window.debugLogger?.debug || console.log)(`\n📊 Testing period: ${HISTORICAL_PERIODS[period].name}`);

    // Test V2 system (V1 removed - production uses V2 only)
    const v2Results = await validatePeriod(period, calculateCompositeScoreV2, 'V2');
    results.v2[period] = v2Results;

    (window.debugLogger?.debug || console.log)(`✅ ${HISTORICAL_PERIODS[period].name}:`);
    (window.debugLogger?.debug || console.log)(`   V2: ${v2Results.accuracy.toFixed(1)}% accuracy`);
  }
  
  // Calculate overall metrics
  const overallV1Accuracy = Object.values(results.v1).reduce((sum, r) => sum + r.accuracy, 0) / Object.keys(results.v1).length;
  const overallV2Accuracy = Object.values(results.v2).reduce((sum, r) => sum + r.accuracy, 0) / Object.keys(results.v2).length;
  
  results.overall = {
    v1Accuracy: overallV1Accuracy,
    v2Accuracy: overallV2Accuracy,
    overallImprovement: overallV2Accuracy - overallV1Accuracy,
    periodsImproved: Object.values(results.comparison).filter(c => c.accuracyImprovement > 0).length
  };
  
  (window.debugLogger?.debug || console.log)('\n🎯 Overall Results:');
  (window.debugLogger?.debug || console.log)(`V1 Average: ${overallV1Accuracy.toFixed(1)}%`);
  (window.debugLogger?.debug || console.log)(`V2 Average: ${overallV2Accuracy.toFixed(1)}%`);
  (window.debugLogger?.debug || console.log)(`Improvement: +${results.overall.overallImprovement.toFixed(1)}%`);
  (window.debugLogger?.debug || console.log)(`Periods improved: ${results.overall.periodsImproved}/${Object.keys(HISTORICAL_PERIODS).length}`);
  
  return results;
}

/**
 * Utilitaires pour les calculs de validation
 */

function generateTestDates(start, end, frequency = 'monthly') {
  const dates = [];
  const startDate = new Date(start);
  const endDate = new Date(end);
  
  const increment = frequency === 'weekly' ? 7 : frequency === 'monthly' ? 30 : 1;
  
  let currentDate = new Date(startDate);
  while (currentDate <= endDate) {
    dates.push(currentDate.toISOString().split('T')[0]);
    currentDate.setDate(currentDate.getDate() + increment);
  }
  
  return dates;
}

function getExpectedScore(phase, date, periodConfig) {
  // Scores attendus selon la phase de marché
  const phaseScores = {
    'accumulation': 25, // Bottom - should signal buy
    'early_expansion': 40,
    'expansion': 60, 
    'euphoria': 85,    // Top - should signal sell
    'distribution': 75,
    'decline': 45,
    'despair': 15      // Bottom - should signal buy
  };
  
  return phaseScores[phase] || 50;
}

function calculateStability(scores) {
  if (scores.length <= 1) return 0;
  
  const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
  const variance = scores.reduce((sum, score) => sum + Math.pow(score - mean, 2), 0) / scores.length;
  const standardDeviation = Math.sqrt(variance);
  
  // Return inverted stability (lower std dev = higher stability)
  return Math.max(0, 100 - standardDeviation);
}

/**
 * Export des fonctions principales pour utilisation externe
 */
export {
  runFullBacktest,
  validatePeriod,
  generateHistoricalData,
  HISTORICAL_PERIODS
};