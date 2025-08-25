/**
 * CCS Signals Engine - MVP Simple Version
 * Fetches market signals and computes CCS score
 */

import { fetchCached } from '../core/fetcher.js';

// Default CCS weights (model version 1)
export const DEFAULT_CCS_WEIGHTS = {
  fear_greed: 0.25,      // Fear & Greed Index
  btc_dominance: 0.20,   // Bitcoin Dominance
  funding_rate: 0.15,    // Futures funding rates
  eth_btc_ratio: 0.15,   // ETH/BTC strength
  volatility: 0.10,      // Market volatility
  trend: 0.15,           // Price trend momentum
  model_version: 'ccs-1'
};

/**
 * Fetch market signals from multiple sources
 */
export async function fetchSignals() {
  // For MVP, we'll create realistic mock data
  // In production, this would fetch from Fear&Greed API, CoinGecko, etc.
  
  const mockSignals = {
    fear_greed: {
      value: 45 + Math.random() * 30, // 45-75 range
      normalized: null, // will be calculated
      timestamp: Date.now(),
      source: 'mock_fear_greed'
    },
    
    btc_dominance: {
      value: 50 + Math.random() * 10, // 50-60% range
      normalized: null,
      timestamp: Date.now(),
      source: 'mock_dominance'
    },
    
    funding_rate: {
      value: -0.01 + Math.random() * 0.02, // -1% to +1%
      normalized: null,
      timestamp: Date.now(),
      source: 'mock_funding'
    },
    
    eth_btc_ratio: {
      value: 0.055 + Math.random() * 0.01, // Around 0.06
      normalized: null,
      timestamp: Date.now(),
      source: 'mock_eth_btc'
    },
    
    volatility: {
      value: 0.3 + Math.random() * 0.4, // 30-70% annual vol
      normalized: null,
      timestamp: Date.now(),
      source: 'mock_volatility'
    },
    
    trend: {
      value: -0.1 + Math.random() * 0.2, // -10% to +10% momentum
      normalized: null,
      timestamp: Date.now(),
      source: 'mock_trend'
    }
  };
  
  return mockSignals;
}

/**
 * Normalize individual signal to 0-100 scale
 */
function normalizeSignal(key, rawValue) {
  switch (key) {
    case 'fear_greed':
      // Already 0-100, just clamp
      return Math.max(0, Math.min(100, rawValue));
      
    case 'btc_dominance':
      // 40-70% dominance → 0-100 scale (higher dominance = lower CCS)
      const domNorm = Math.max(0, Math.min(100, (70 - rawValue) / (70 - 40) * 100));
      return domNorm;
      
    case 'funding_rate':
      // Negative funding (shorts pay longs) = bullish = higher CCS
      const fundNorm = Math.max(0, Math.min(100, 50 - (rawValue * 2000))); // -1% = 100, +1% = 0
      return fundNorm;
      
    case 'eth_btc_ratio':
      // Higher ETH/BTC = alt season = higher CCS
      const ethNorm = Math.max(0, Math.min(100, (rawValue - 0.05) / (0.08 - 0.05) * 100));
      return ethNorm;
      
    case 'volatility':
      // Lower volatility = more mature market = potentially higher CCS
      const volNorm = Math.max(0, Math.min(100, 100 - (rawValue * 100)));
      return volNorm;
      
    case 'trend':
      // Positive trend = higher CCS
      const trendNorm = Math.max(0, Math.min(100, 50 + (rawValue * 250))); // -10% = 25, +10% = 75
      return trendNorm;
      
    default:
      return 50; // Neutral
  }
}

/**
 * Compute CCS score from signals and weights
 */
export function computeCCS(signals, weights = DEFAULT_CCS_WEIGHTS) {
  if (!signals || typeof signals !== 'object') {
    throw new Error('Invalid signals object');
  }
  
  if (!weights || typeof weights !== 'object') {
    throw new Error('Invalid weights object');
  }
  
  let weightedSum = 0;
  let totalWeight = 0;
  const normalizedSignals = {};
  
  // Process each signal
  for (const [key, signal] of Object.entries(signals)) {
    if (key === 'model_version') continue;
    
    const weight = weights[key];
    if (!weight || !signal || typeof signal.value !== 'number') {
      console.warn(`Skipping invalid signal: ${key}`);
      continue;
    }
    
    // Normalize signal
    const normalized = normalizeSignal(key, signal.value);
    normalizedSignals[key] = {
      ...signal,
      normalized,
      weight
    };
    
    // Add to weighted sum
    weightedSum += normalized * weight;
    totalWeight += weight;
  }
  
  // Calculate final CCS score (0-100)
  const ccsScore = totalWeight > 0 ? weightedSum / totalWeight : 50;
  
  // Validation
  if (isNaN(ccsScore) || ccsScore < 0 || ccsScore > 100) {
    throw new Error(`Invalid CCS score: ${ccsScore}`);
  }
  
  return {
    score: Math.round(ccsScore * 100) / 100, // Round to 2 decimals
    signals: normalizedSignals,
    weights,
    calculation_time: new Date().toISOString(),
    model_version: weights.model_version || 'ccs-1'
  };
}

/**
 * Fetch signals with cache and compute CCS
 */
export async function fetchAndComputeCCS(weights = DEFAULT_CCS_WEIGHTS) {
  try {
    // Fetch signals (cached)
    const signals = await fetchCached(
      'market-signals',
      () => fetchSignals(),
      'signals'
    );
    
    // Compute CCS
    const ccs = computeCCS(signals, weights);
    
    console.log(`CCS computed: ${ccs.score} (model: ${ccs.model_version})`);
    
    return ccs;
    
  } catch (error) {
    console.error('Failed to fetch and compute CCS:', error);
    throw error;
  }
}

/**
 * Validate CCS score
 */
export function validateCCS(ccs) {
  if (!ccs || typeof ccs !== 'object') {
    return false;
  }
  
  const { score, signals, model_version } = ccs;
  
  if (typeof score !== 'number' || score < 0 || score > 100) {
    return false;
  }
  
  if (!signals || typeof signals !== 'object') {
    return false;
  }
  
  if (!model_version || typeof model_version !== 'string') {
    return false;
  }
  
  return true;
}

/**
 * Get CCS interpretation
 */
export function interpretCCS(score) {
  if (score >= 80) return { level: 'very_high', label: 'Very Bullish', color: '#10b981' };
  if (score >= 65) return { level: 'high', label: 'Bullish', color: '#059669' };
  if (score >= 50) return { level: 'medium', label: 'Neutral+', color: '#f59e0b' };
  if (score >= 35) return { level: 'low', label: 'Neutral-', color: '#f97316' };
  return { level: 'very_low', label: 'Bearish', color: '#dc2626' };
}