/**
 * Stability Engine - Hystérésis & EMA Anti-Flickering
 * Prevents rapid oscillations with deadband ±2% and persistence 3 ticks
 */

import { selectContradiction01, selectGovernanceTimestamp } from '../selectors/governance.js';
import { isStale } from '../utils/time.js';

// Configuration
const HYSTERESIS_CONFIG = {
  deadband: 0.02,        // ±2% deadband
  persistence: 3,        // 3 ticks required for change
  ema_alpha: 0.3,        // EMA smoothing coefficient
  stale_threshold: 30    // 30 minutes stale threshold
};

// Global state for stability tracking
let stabilityState = {
  raw_contradiction: null,
  smooth_contradiction: null,
  direction_buffer: [],      // Buffer for direction persistence
  last_stable_value: null,   // Last confirmed stable value
  last_update: null,
  staleness_frozen: false    // Flag for staleness gating
};

/**
 * Apply hystérésis with deadband and persistence
 * @param {number} newValue - New contradiction value (0-1)
 * @param {Object} state - Current application state
 * @returns {number} - Stabilized contradiction value
 */
export function applyHysteresis(newValue, state) {
  const timestamp = selectGovernanceTimestamp(state);
  const isDataStale = isStale(timestamp, HYSTERESIS_CONFIG.stale_threshold);

  // Staleness gating: freeze adaptive weights if stale
  if (isDataStale && !stabilityState.staleness_frozen) {
    console.warn('🔒 Staleness gating: freezing adaptive weights at last stable value');
    stabilityState.staleness_frozen = true;
    // Return last stable value to freeze weights
    return stabilityState.last_stable_value ?? newValue;
  }

  // Reset staleness flag when data is fresh
  if (!isDataStale && stabilityState.staleness_frozen) {
    console.info('🔓 Staleness gating: resuming adaptive weights');
    stabilityState.staleness_frozen = false;
  }

  // Initialize if first run
  if (stabilityState.smooth_contradiction === null) {
    stabilityState.raw_contradiction = newValue;
    stabilityState.smooth_contradiction = newValue;
    stabilityState.last_stable_value = newValue;
    stabilityState.last_update = Date.now();
    return newValue;
  }

  // EMA smoothing first
  const emaValue = HYSTERESIS_CONFIG.ema_alpha * newValue +
                   (1 - HYSTERESIS_CONFIG.ema_alpha) * stabilityState.smooth_contradiction;

  // Calculate direction relative to last stable value
  const delta = emaValue - stabilityState.last_stable_value;
  const direction = Math.abs(delta) > HYSTERESIS_CONFIG.deadband ? Math.sign(delta) : 0;

  // Update direction buffer
  stabilityState.direction_buffer.push(direction);
  if (stabilityState.direction_buffer.length > HYSTERESIS_CONFIG.persistence) {
    stabilityState.direction_buffer.shift();
  }

  // Check for consistent direction over persistence period
  const consistent = stabilityState.direction_buffer.length === HYSTERESIS_CONFIG.persistence &&
                     stabilityState.direction_buffer.every(d => d === direction && d !== 0);

  let finalValue = stabilityState.last_stable_value;

  if (consistent) {
    // Apply the change if persistence is met
    finalValue = emaValue;
    stabilityState.last_stable_value = finalValue;
    stabilityState.direction_buffer = []; // Reset buffer after change

    console.debug(`🎯 Hysteresis: stable change detected (${(delta*100).toFixed(1)}% → ${(finalValue*100).toFixed(1)}%)`);
  }

  // Update internal state
  stabilityState.raw_contradiction = newValue;
  stabilityState.smooth_contradiction = emaValue;
  stabilityState.last_update = Date.now();

  return finalValue;
}

/**
 * Get stable contradiction value with all protections
 * @param {Object} state - Application state
 * @returns {number} - Stabilized contradiction (0-1)
 */
export function getStableContradiction(state) {
  const rawContradiction = selectContradiction01(state);
  return applyHysteresis(rawContradiction, state);
}

/**
 * Get debug information about stability state
 * @returns {Object} - Debug info
 */
export function getStabilityDebugInfo() {
  return {
    config: HYSTERESIS_CONFIG,
    state: {
      ...stabilityState,
      direction_buffer_status: `${stabilityState.direction_buffer.length}/${HYSTERESIS_CONFIG.persistence}`,
      time_since_update: stabilityState.last_update ? Date.now() - stabilityState.last_update : null
    },
    analysis: {
      is_stable: stabilityState.direction_buffer.length < HYSTERESIS_CONFIG.persistence,
      deadband_active: stabilityState.smooth_contradiction !== null &&
                       Math.abs(stabilityState.raw_contradiction - stabilityState.last_stable_value) <= HYSTERESIS_CONFIG.deadband,
      staleness_frozen: stabilityState.staleness_frozen
    }
  };
}

/**
 * Reset stability state (for testing)
 */
export function resetStabilityState() {
  stabilityState = {
    raw_contradiction: null,
    smooth_contradiction: null,
    direction_buffer: [],
    last_stable_value: null,
    last_update: null,
    staleness_frozen: false
  };
  console.info('🔄 Stability state reset');
}

/**
 * Force staleness gating for testing
 * @param {boolean} forced - Whether to force staleness
 */
export function forceStalenessFrozen(forced) {
  stabilityState.staleness_frozen = forced;
  console.info(`🧪 Staleness gating ${forced ? 'forced ON' : 'forced OFF'}`);
}

// Export for global debugging
if (typeof window !== 'undefined') {
  window.stabilityEngine = {
    getDebugInfo: getStabilityDebugInfo,
    reset: resetStabilityState,
    forceStale: forceStalenessFrozen
  };
}