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
  console.debug('🔍 Fetching REAL market signals...');
  
  const signals = {};
  
  try {
    // 1. Fear & Greed Index (Alternative.me API)
    try {
      const fearGreedResponse = await fetch('https://api.alternative.me/fng/', {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      
      if (fearGreedResponse.ok) {
        const fearGreedData = await fearGreedResponse.json();
        const fearGreedValue = parseInt(fearGreedData.data[0].value);
        signals.fear_greed = {
          value: fearGreedValue,
          normalized: null,
          timestamp: Date.now(),
          source: 'alternative.me'
        };
        console.debug('✅ Fear & Greed loaded:', fearGreedValue);
      } else {
        throw new Error('Fear & Greed API failed');
      }
    } catch (error) {
      debugLogger.warn('⚠️ Fear & Greed fallback:', error);
      signals.fear_greed = {
        value: 48, // Static fallback to current real value
        normalized: null,
        timestamp: Date.now(),
        source: 'fallback_static'
      };
    }

    // 2. BTC Dominance (CoinGecko)
    try {
      const dominanceResponse = await fetch('https://api.coingecko.com/api/v3/global', {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      
      if (dominanceResponse.ok) {
        const dominanceData = await dominanceResponse.json();
        const btcDominance = dominanceData.data.market_cap_percentage.btc;
        signals.btc_dominance = {
          value: btcDominance,
          normalized: null,
          timestamp: Date.now(),
          source: 'coingecko'
        };
        console.debug('✅ BTC Dominance loaded:', btcDominance.toFixed(1) + '%');
      } else {
        throw new Error('CoinGecko API failed');
      }
    } catch (error) {
      debugLogger.warn('⚠️ BTC Dominance fallback:', error);
      signals.btc_dominance = {
        value: 57.5, // Current approximate value
        normalized: null,
        timestamp: Date.now(),
        source: 'fallback_static'
      };
    }

    // 3. Funding Rate (Binance API)
    try {
      const fundingResponse = await fetch('https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT', {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      
      if (fundingResponse.ok) {
        const fundingData = await fundingResponse.json();
        const fundingRate = parseFloat(fundingData.lastFundingRate); // Already in decimal (e.g., 0.0001 = 0.01%)
        signals.funding_rate = {
          value: fundingRate,
          normalized: null,
          timestamp: Date.now(),
          source: 'binance'
        };
        console.debug('✅ Funding Rate loaded:', (fundingRate * 100).toFixed(4) + '%');
      } else {
        throw new Error('Binance API failed');
      }
    } catch (error) {
      debugLogger.warn('⚠️ Funding Rate fallback:', error);
      signals.funding_rate = {
        value: 0.0001, // Neutral funding rate (0.01%)
        normalized: null,
        timestamp: Date.now(),
        source: 'fallback_static'
      };
    }

    // 4. ETH/BTC Ratio (CoinGecko)
    try {
      const pricesResponse = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd', {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      
      if (pricesResponse.ok) {
        const pricesData = await pricesResponse.json();
        console.debug('🔍 ETH/BTC API response:', pricesData);
        
        const btcPrice = pricesData.bitcoin?.usd;
        const ethPrice = pricesData.ethereum?.usd;
        
        if (btcPrice && ethPrice && btcPrice > 0 && ethPrice > 0) {
          const ethBtcRatio = ethPrice / btcPrice;
          
          signals.eth_btc_ratio = {
            value: ethBtcRatio,
            normalized: null,
            timestamp: Date.now(),
            source: 'coingecko'
          };
          console.debug('✅ ETH/BTC Ratio loaded:', ethBtcRatio.toFixed(6));
        } else {
          throw new Error(`Invalid price data: BTC=${btcPrice}, ETH=${ethPrice}`);
        }
      } else {
        throw new Error(`CoinGecko prices API failed with status: ${pricesResponse.status}`);
      }
    } catch (error) {
      debugLogger.warn('⚠️ ETH/BTC Ratio fallback:', error);
      signals.eth_btc_ratio = {
        value: 0.037, // Approximate current ratio
        normalized: null,
        timestamp: Date.now(),
        source: 'fallback_static'
      };
    }

    // 5. Volatility (calculated from recent BTC price changes)
    try {
      const volatilityResponse = await fetch('https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=7&interval=daily', {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      
      if (volatilityResponse.ok) {
        const volatilityData = await volatilityResponse.json();
        const prices = volatilityData.prices.map(p => p[1]);
        
        // Calculate 7-day volatility
        const returns = [];
        for (let i = 1; i < prices.length; i++) {
          returns.push((prices[i] - prices[i-1]) / prices[i-1]);
        }
        
        const volatility = Math.sqrt(returns.reduce((sum, ret) => sum + ret * ret, 0) / returns.length) * Math.sqrt(365); // Annualized volatility as decimal
        
        signals.volatility = {
          value: volatility,
          normalized: null,
          timestamp: Date.now(),
          source: 'coingecko_calculated'
        };
        console.debug('✅ Volatility loaded:', (volatility * 100).toFixed(1) + '%');
      } else {
        throw new Error('CoinGecko market chart API failed');
      }
    } catch (error) {
      debugLogger.warn('⚠️ Volatility fallback:', error);
      signals.volatility = {
        value: 0.65, // 65% typical crypto volatility
        normalized: null,
        timestamp: Date.now(),
        source: 'fallback_static'
      };
    }

    // 6. Trend (7-day price momentum)
    try {
      const trendResponse = await fetch('https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false', {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      
      if (trendResponse.ok) {
        const trendData = await trendResponse.json();
        const priceChange7d = trendData.market_data.price_change_percentage_7d / 100; // Convert to decimal
        
        signals.trend = {
          value: priceChange7d,
          normalized: null,
          timestamp: Date.now(),
          source: 'coingecko'
        };
        console.debug('✅ Trend loaded:', (priceChange7d * 100).toFixed(2) + '%');
      } else {
        throw new Error('CoinGecko trend API failed');
      }
    } catch (error) {
      debugLogger.warn('⚠️ Trend fallback:', error);
      signals.trend = {
        value: 0.025, // 2.5% slight positive trend
        normalized: null,
        timestamp: Date.now(),
        source: 'fallback_static'
      };
    }

  } catch (globalError) {
    console.error('❌ Global error fetching signals:', globalError);
    // Return all fallback data if everything fails
    return {
      fear_greed: { value: 48, normalized: null, timestamp: Date.now(), source: 'fallback' },
      btc_dominance: { value: 57.5, normalized: null, timestamp: Date.now(), source: 'fallback' },
      funding_rate: { value: 0.0001, normalized: null, timestamp: Date.now(), source: 'fallback' },
      eth_btc_ratio: { value: 0.037, normalized: null, timestamp: Date.now(), source: 'fallback' },
      volatility: { value: 0.65, normalized: null, timestamp: Date.now(), source: 'fallback' },
      trend: { value: 0.025, normalized: null, timestamp: Date.now(), source: 'fallback' }
    };
  }

  console.debug('🔍 Fetched REAL signals:', signals);
  return signals;
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
      // Handle edge case where rawValue might be 0 or very small
      if (rawValue <= 0) {
        debugLogger.warn('ETH/BTC ratio is 0 or negative, using neutral score');
        return 50; // Neutral score
      }
      const ethNorm = Math.max(0, Math.min(100, (rawValue - 0.025) / (0.06 - 0.025) * 100)); // Adjusted range: 0.025-0.06
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
      debugLogger.warn(`Skipping invalid signal: ${key}`);
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
    
    console.debug(`CCS computed: ${ccs.score} (model: ${ccs.model_version})`);
    
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
