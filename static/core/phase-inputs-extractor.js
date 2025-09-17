/**
 * Phase Inputs Extractor - Normalized data extraction for phase detection
 * Handles strict unit normalization and fallbacks for missing data
 */

import { pushSample, getSeries, calculateSlope } from './phase-buffers.js';
import { store } from './risk-dashboard-store.js';

// Utility functions
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const clamp0100 = (x) => Math.max(0, Math.min(100, x));
const isValidNumber = (x) => typeof x === 'number' && isFinite(x);

/**
 * Calculate ETH/BTC ratio proxy from available data
 * @param {Object} state - Store state
 * @returns {number} ETH/BTC ratio (raw value)
 */
function calculateEthBtcRatio(state) {
  try {
    // Try to get from onchain categories (if available)
    const categories = state.scores?.onchain_metadata?.categoryBreakdown;
    if (categories?.ethereum && categories?.bitcoin) {
      // Use inverse of scores (lower score = better performance)
      const ethScore = categories.ethereum.score || 50;
      const btcScore = categories.bitcoin.score || 50;

      // Normalize to ratio-like value (lower score = higher ratio)
      const ratio = (100 - ethScore) / (100 - btcScore);
      return clamp01(ratio * 0.05); // Scale to reasonable range
    }

    // Fallback: use portfolio allocation weights as proxy
    const balances = state.wallet?.balances || [];
    const ethBalance = balances.find(b => b.symbol === 'ETH')?.value_usd || 0;
    const btcBalance = balances.find(b => b.symbol === 'BTC')?.value_usd || 0;

    if (btcBalance > 0) {
      return ethBalance / btcBalance;
    }

    // Default fallback
    return 0.06; // ~6% ratio as neutral

  } catch (e) {
    console.warn('⚠️ PhaseInputs: ETH/BTC ratio calculation failed:', e.message);
    return 0.06;
  }
}

/**
 * Calculate alts/BTC proxy from onchain categories
 * @param {Object} state - Store state
 * @returns {number} Alts/BTC ratio proxy
 */
function calculateAltsBtcProxy(state) {
  try {
    const categories = state.scores?.onchain_metadata?.categoryBreakdown;
    if (!categories) return 0.15; // Default fallback

    // Get non-BTC categories average performance vs BTC
    const nonBtcCategories = Object.entries(categories).filter(([key, _]) =>
      !key.toLowerCase().includes('bitcoin') && !key.toLowerCase().includes('btc')
    );

    if (nonBtcCategories.length === 0) return 0.15;

    // Average score of non-BTC categories (lower = better)
    const avgAltScore = nonBtcCategories.reduce((sum, [_, cat]) =>
      sum + (cat.score || 50), 0) / nonBtcCategories.length;

    const btcScore = categories.bitcoin?.score || categories.btc?.score || 50;

    // Convert to ratio (lower score = better performance)
    const ratio = (100 - avgAltScore) / (100 - btcScore);
    return clamp01(ratio * 0.2); // Scale to reasonable range

  } catch (e) {
    console.warn('⚠️ PhaseInputs: Alts/BTC proxy calculation failed:', e.message);
    return 0.15;
  }
}

/**
 * Calculate breadth_alts (% of non-BTC categories above their threshold)
 * @param {Object} state - Store state
 * @returns {number} Breadth ratio 0..1
 */
function calculateBreadth(state) {
  try {
    const categories = state.scores?.onchain_metadata?.categoryBreakdown;
    if (!categories) return 0.5; // Neutral fallback

    const nonBtcEntries = Object.entries(categories).filter(([key, _]) =>
      !key.toLowerCase().includes('bitcoin') && !key.toLowerCase().includes('btc')
    );

    if (nonBtcEntries.length === 0) return 0.5;

    // Count categories with score < 55 (lower score = better performance)
    const aboveThreshold = nonBtcEntries.filter(([_, cat]) => (cat.score || 50) < 55).length;
    const breadth = aboveThreshold / nonBtcEntries.length;

    console.debug('📊 PhaseInputs: Breadth calculated:', {
      totalCategories: nonBtcEntries.length,
      aboveThreshold,
      breadth: (breadth * 100).toFixed(1) + '%'
    });

    return clamp01(breadth);

  } catch (e) {
    console.warn('⚠️ PhaseInputs: Breadth calculation failed:', e.message);
    return 0.5;
  }
}

/**
 * Calculate dispersion (percentile of cross-category standard deviation)
 * @param {Object} state - Store state
 * @returns {number} Dispersion percentile 0..1
 */
function calculateDispersion(state) {
  try {
    const categories = state.scores?.onchain_metadata?.categoryBreakdown;
    if (!categories) return 0.5;

    const scores = Object.values(categories)
      .map(cat => cat.score || 50)
      .filter(score => isValidNumber(score));

    if (scores.length < 2) return 0.5;

    // Calculate standard deviation
    const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
    const variance = scores.reduce((sum, score) => sum + Math.pow(score - mean, 2), 0) / scores.length;
    const stdDev = Math.sqrt(variance);

    // Normalize to percentile (higher stdDev = higher dispersion)
    // Typical range: 5-25, map to 0..1
    const dispersion = clamp01((stdDev - 5) / 20);

    console.debug('📊 PhaseInputs: Dispersion calculated:', {
      scoresCount: scores.length,
      mean: mean.toFixed(1),
      stdDev: stdDev.toFixed(2),
      dispersion: (dispersion * 100).toFixed(1) + '%'
    });

    return dispersion;

  } catch (e) {
    console.warn('⚠️ PhaseInputs: Dispersion calculation failed:', e.message);
    return 0.5;
  }
}

/**
 * Calculate correlation proxy (alts vs BTC)
 * @param {Object} state - Store state
 * @returns {number} Correlation percentile 0..1 (lower = less correlated)
 */
function calculateCorrelationProxy(state) {
  try {
    // For now, use a simple proxy based on breadth and dispersion
    // High breadth + high dispersion = low correlation
    const breadth = calculateBreadth(state);
    const dispersion = calculateDispersion(state);

    // Invert: higher breadth+dispersion = lower correlation
    const correlation = 1 - (breadth * 0.6 + dispersion * 0.4);

    return clamp01(correlation);

  } catch (e) {
    console.warn('⚠️ PhaseInputs: Correlation proxy calculation failed:', e.message);
    return 0.5; // Neutral correlation
  }
}

/**
 * Extract and normalize all phase inputs with proper units
 * @param {Object} storeInstance - Risk dashboard store instance (optional)
 * @returns {Object} PhaseInputs with normalized units and metadata
 */
export function extractPhaseInputs(storeInstance = null) {
  const storeToUse = storeInstance || store;
  const state = storeToUse.snapshot();

  console.debug('🔍 PhaseInputs: Extracting from state:', {
    hasDecision: !!state.decision,
    hasSignals: !!state.signals,
    hasOnchainMeta: !!state.scores?.onchain_metadata,
    hasWallet: !!state.wallet
  });

  // Collect missing signals for partial flag
  const missing = [];

  // 1) Decision Index (0..100)
  let DI = state.decision?.score;
  if (!isValidNumber(DI)) {
    DI = 50; // Neutral fallback
    missing.push('decision_score');
  }
  DI = clamp0100(DI);

  // 2) BTC Dominance (0..1) - from signals-engine
  let btc_dom = state.signals?.btc_dominance?.value;
  if (isValidNumber(btc_dom)) {
    // Normalize if it's in percentage (>1)
    if (btc_dom > 1) btc_dom = btc_dom / 100;
    btc_dom = clamp01(btc_dom);
    pushSample('btc_dom', btc_dom);
  } else {
    btc_dom = 0.6; // Default 60% dominance
    missing.push('btc_dominance');
    console.debug('🔧 PhaseInputs: BTC dominance fallback to 60%');
  }

  // 3) ETH/BTC ratio (raw values) - calculate and store series
  const eth_btc_current = calculateEthBtcRatio(state);
  pushSample('eth_btc', eth_btc_current);
  const eth_btc = getSeries('eth_btc', 14);

  // 4) Alts/BTC proxy (raw values) - calculate and store series
  const alts_btc_current = calculateAltsBtcProxy(state);
  pushSample('alts_btc', alts_btc_current);
  const alts_btc = getSeries('alts_btc', 14);

  // 5) Breadth alts (0..1)
  const breadth_alts = calculateBreadth(state);
  if (breadth_alts === 0.5 && missing.length === 0) {
    missing.push('onchain_categories'); // Only add if this was fallback
  }

  // 6) Dispersion (0..1)
  const dispersion = calculateDispersion(state);

  // 7) Correlation proxy (0..1)
  const corr_alts_btc = calculateCorrelationProxy(state);

  const phaseInputs = {
    // Normalized inputs
    DI,                    // 0..100
    btc_dom,              // 0..1
    eth_btc,              // series (raw ratios)
    alts_btc,             // series (raw ratios)
    breadth_alts,         // 0..1
    dispersion,           // 0..1
    corr_alts_btc,        // 0..1

    // Metadata
    partial: missing.length > 0,
    missing,
    timestamp: new Date().toISOString(),

    // Additional context
    seriesLengths: {
      eth_btc: eth_btc.length,
      alts_btc: alts_btc.length
    }
  };

  console.debug('📊 PhaseInputs: Extracted inputs:', {
    DI: DI.toFixed(1),
    btc_dom: (btc_dom * 100).toFixed(1) + '%',
    eth_btc_current: eth_btc_current.toFixed(4),
    eth_btc_series: eth_btc.length + ' samples',
    breadth_alts: (breadth_alts * 100).toFixed(1) + '%',
    dispersion: (dispersion * 100).toFixed(1) + '%',
    partial: phaseInputs.partial,
    missing: missing.join(', ') || 'none'
  });

  return phaseInputs;
}

/**
 * Validate phase inputs quality
 * @param {Object} inputs - Phase inputs object
 * @returns {Object} Validation result with quality score
 */
export function validatePhaseInputs(inputs) {
  if (!inputs) {
    return { valid: false, quality: 0, issues: ['No inputs provided'] };
  }

  const issues = [];
  let quality = 1.0;

  // Check for partial data
  if (inputs.partial) {
    quality *= 0.7;
    issues.push(`Missing signals: ${inputs.missing.join(', ')}`);
  }

  // Check series length for slope calculations
  if (inputs.eth_btc.length < 5) {
    quality *= 0.8;
    issues.push('Insufficient ETH/BTC history for reliable slope');
  }

  if (inputs.alts_btc.length < 5) {
    quality *= 0.8;
    issues.push('Insufficient Alts/BTC history for reliable slope');
  }

  // Check for reasonable values
  if (inputs.DI < 5 || inputs.DI > 95) {
    quality *= 0.9;
    issues.push('Extreme DI value detected');
  }

  return {
    valid: quality >= 0.5,
    quality,
    issues,
    recommendation: quality < 0.7 ? 'Consider using neutral phase until data quality improves' : 'Data quality sufficient for phase detection'
  };
}

// Development helpers
if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
  window.debugPhaseInputs = {
    extract: extractPhaseInputs,
    validate: validatePhaseInputs,
    calculateBreadth: () => calculateBreadth(store.snapshot()),
    calculateDispersion: () => calculateDispersion(store.snapshot()),
    calculateEthBtcRatio: () => calculateEthBtcRatio(store.snapshot())
  };

  console.debug('🔧 Debug: window.debugPhaseInputs available for testing');
}