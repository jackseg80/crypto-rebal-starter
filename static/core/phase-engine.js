/**
 * Phase Engine - Proactive market phase detection and allocation tilts
 * Implements rules for ETH expansion, large-cap altseason, full altseason phases
 * with zero-sum risky pool tilts and strict caps/normalization
 */

import { calculateSlope } from './phase-buffers.js';

// Phase memory for hysteresis
const phaseMemory = {
  history: [], // Last 5 evaluations
  lastPhase: 'neutral',
  lastEvaluationTime: 0
};

// Constants
const PHASE_CAPS = {
  'L2/Scaling': 8,
  'DeFi': 8,
  'Gaming/NFT': 5,
  'Memecoins': 2
};

const STABLES_FLOOR = 5; // Minimum 5% stables

/**
 * Phase detection rules with hysteresis
 * @param {Object} phaseInputs - Normalized phase inputs
 * @param {number} histWindow - Historical window for slope calculations (default: 14)
 * @returns {string} Detected phase: 'risk_off', 'eth_expansion', 'largecap_altseason', 'full_altseason', 'neutral'
 */
export function inferPhase(phaseInputs, histWindow = 14) {
  // Debug override for testing specific phases (persisted in localStorage)
  const forcedPhase = getDebugForcePhase();
  if (forcedPhase) {
    console.warn('🔧 PhaseEngine: DEBUG - Using forced phase (persisted):', forcedPhase);
    return forcedPhase;
  }

  if (!phaseInputs || phaseInputs.partial) {
    console.debug('🧘 PhaseEngine: Insufficient data, defaulting to neutral');
    return 'neutral';
  }

  const {
    DI,
    btc_dom,
    eth_btc,
    alts_btc,
    breadth_alts,
    dispersion,
    corr_alts_btc
  } = phaseInputs;

  // Calculate slopes (14-day trends)
  const delta_btc_dom = calculateSlope(Array.isArray(btc_dom) ? btc_dom : [btc_dom, btc_dom]);
  const delta_eth_btc = calculateSlope(eth_btc);
  const delta_alts_btc = calculateSlope(alts_btc);

  console.debug('📊 PhaseEngine: Slopes calculated:', {
    delta_btc_dom: (delta_btc_dom * 100).toFixed(2) + '%',
    delta_eth_btc: (delta_eth_btc * 100).toFixed(2) + '%',
    delta_alts_btc: (delta_alts_btc * 100).toFixed(2) + '%'
  });

  // Bull context determination
  const bull_ctx = (DI >= 60) || (DI >= 55 && breadth_alts >= 0.55);

  console.debug('🐂 PhaseEngine: Bull context:', {
    bull_ctx,
    DI,
    breadth_alts: (breadth_alts * 100).toFixed(1) + '%',
    reason: DI >= 60 ? 'DI >= 60' : (DI >= 55 && breadth_alts >= 0.55) ? 'DI >= 55 & breadth >= 55%' : 'bearish/neutral'
  });

  let detectedPhase = 'neutral';

  // Phase detection rules (in order of specificity)

  // 1) Risk-off (overrides everything)
  if (DI < 35) {
    detectedPhase = 'risk_off';
    console.debug('🛡️ PhaseEngine: Risk-off detected (DI < 35)');
  }
  // 2) Full altseason (most restrictive)
  else if (bull_ctx &&
           breadth_alts >= 0.75 &&
           dispersion >= 0.75 &&
           corr_alts_btc <= 0.30 &&
           delta_btc_dom < -0.02 &&
           delta_alts_btc > 0.03) {
    detectedPhase = 'full_altseason';
    console.debug('🚀 PhaseEngine: Full altseason detected:', {
      breadth: (breadth_alts * 100).toFixed(1) + '%',
      dispersion: (dispersion * 100).toFixed(1) + '%',
      correlation: (corr_alts_btc * 100).toFixed(1) + '%',
      btc_dom_decline: (delta_btc_dom * 100).toFixed(2) + '%',
      alts_surge: (delta_alts_btc * 100).toFixed(2) + '%'
    });
  }
  // 3) Large-cap altseason
  else if (bull_ctx &&
           delta_btc_dom <= 0 &&
           breadth_alts >= 0.65 &&
           dispersion >= 0.60 &&
           delta_alts_btc > 0.015) {
    detectedPhase = 'largecap_altseason';
    console.debug('📈 PhaseEngine: Large-cap altseason detected:', {
      btc_dom_flat: delta_btc_dom <= 0,
      breadth: (breadth_alts * 100).toFixed(1) + '%',
      dispersion: (dispersion * 100).toFixed(1) + '%',
      alts_growth: (delta_alts_btc * 100).toFixed(2) + '%'
    });
  }
  // 4) ETH expansion
  else if (bull_ctx &&
           delta_btc_dom < 0 &&
           delta_eth_btc > 0.02 &&
           delta_eth_btc > (delta_alts_btc + 0.01)) {
    detectedPhase = 'eth_expansion';
    console.debug('⚡ PhaseEngine: ETH expansion detected:', {
      btc_dom_declining: (delta_btc_dom * 100).toFixed(2) + '%',
      eth_outperforming: (delta_eth_btc * 100).toFixed(2) + '%',
      eth_vs_alts_edge: ((delta_eth_btc - delta_alts_btc) * 100).toFixed(2) + '%'
    });
  }
  // 5) Default to neutral
  else {
    detectedPhase = 'neutral';
    console.debug('😐 PhaseEngine: Neutral phase (no specific conditions met)');
  }

  // Apply hysteresis
  const finalPhase = applyHysteresis(detectedPhase, DI);

  console.debug('🧠 PhaseEngine: Phase detection complete:', {
    detected: detectedPhase,
    final: finalPhase,
    hysteresisApplied: detectedPhase !== finalPhase,
    DI,
    bull_ctx
  });

  return finalPhase;
}

/**
 * Apply hysteresis to phase detection (smoothing)
 * @param {string} detectedPhase - Raw detected phase
 * @param {number} DI - Decision Index for exit conditions
 * @returns {string} Final phase after hysteresis
 */
function applyHysteresis(detectedPhase, DI) {
  const now = Date.now();

  // Emergency exit conditions (immediate phase change)
  if (DI < 35) {
    console.debug('🚨 PhaseEngine: Emergency exit to risk_off (DI < 35)');
    phaseMemory.history = ['risk_off'];
    phaseMemory.lastPhase = 'risk_off';
    return 'risk_off';
  }

  if (DI < 45) {
    console.debug('🚨 PhaseEngine: Emergency exit to neutral (DI < 45)');
    phaseMemory.history = ['neutral'];
    phaseMemory.lastPhase = 'neutral';
    return 'neutral';
  }

  // Update evaluation history
  phaseMemory.history.push(detectedPhase);
  if (phaseMemory.history.length > 5) {
    phaseMemory.history.shift();
  }

  phaseMemory.lastEvaluationTime = now;

  // Count occurrences in recent history
  const phaseCounts = phaseMemory.history.reduce((counts, phase) => {
    counts[phase] = (counts[phase] || 0) + 1;
    return counts;
  }, {});

  // Hysteresis rule: need 3/5 evaluations to change phase
  const currentConsensus = Object.keys(phaseCounts).reduce((a, b) =>
    phaseCounts[a] > phaseCounts[b] ? a : b
  );

  const consensusStrength = phaseCounts[currentConsensus] || 0;

  console.debug('🧠 PhaseEngine: Hysteresis analysis:', {
    history: phaseMemory.history,
    phaseCounts,
    currentConsensus,
    consensusStrength: `${consensusStrength}/5`,
    lastPhase: phaseMemory.lastPhase
  });

  // If we have strong consensus (3+ votes), use it
  if (consensusStrength >= 3) {
    phaseMemory.lastPhase = currentConsensus;
    return currentConsensus;
  }

  // For testing/debugging: be more aggressive with phase changes (2+ votes)
  if (consensusStrength >= 2 && typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
    console.debug('🔧 PhaseEngine: DEBUG mode - using 2+ consensus:', currentConsensus);
    phaseMemory.lastPhase = currentConsensus;
    return currentConsensus;
  }

  // Otherwise, stick with last stable phase
  console.debug('🔒 PhaseEngine: Insufficient consensus, maintaining last phase:', phaseMemory.lastPhase);
  return phaseMemory.lastPhase;
}

/**
 * Apply multiplicative tilts to all assets (including Stablecoins)
 * @param {Object} targets - Original targets allocation
 * @param {Object} tilts - Multiplicative tilts {asset: multiplier}
 * @returns {Object} Adjusted targets (will be normalized later)
 */
function applyAllTilts(targets, tilts) {
  console.debug('🔄 PhaseEngine: Applying all tilts (including Stablecoins):', { tilts });

  const T = { ...targets }; // Clone to avoid mutation

  // Apply all tilts
  for (const [asset, multiplier] of Object.entries(tilts)) {
    if (T[asset] !== undefined) {
      const before = T[asset];
      const after = before * multiplier;
      T[asset] = after;

      console.debug(`📊 PhaseEngine: Tilted ${asset}:`, {
        before: before.toFixed(2) + '%',
        multiplier: `×${multiplier}`,
        after: after.toFixed(2) + '%',
        change: `${after > before ? '+' : ''}${((after - before) / before * 100).toFixed(1)}%`
      });
    }
  }

  console.debug('✅ PhaseEngine: All tilts applied, sum before normalization:',
    Object.values(T).reduce((sum, val) => sum + val, 0).toFixed(2) + '%');

  return T;
}

/**
 * Apply caps, stables floor, and normalization (fixed order)
 * @param {Object} targets - Target allocations
 * @param {Object} options - Options {caps, stablesFloor, phase}
 * @returns {Object} Finalized targets
 */
function finalizeCapsAndNormalize(targets, options = {}) {
  const { caps = PHASE_CAPS, stablesFloor = STABLES_FLOOR, phase = 'neutral' } = options;

  console.debug('🔧 PhaseEngine: Finalizing caps and normalization:', { caps, stablesFloor });

  const T = { ...targets };

  // Step 1: Apply per-bucket caps
  let capsTriggered = [];
  for (const [asset, cap] of Object.entries(caps)) {
    if ((T[asset] || 0) > cap) {
      const before = T[asset];
      T[asset] = cap;
      capsTriggered.push(`${asset}: ${before.toFixed(1)}% → ${cap}%`);
      console.debug(`🧢 PhaseEngine: Cap applied to ${asset}:`, {
        before: before.toFixed(2) + '%',
        cap: cap + '%'
      });
    }
  }

  // Step 2: Stables floor
  let stablesFloorHit = false;
  if ((T['Stablecoins'] || 0) < stablesFloor) {
    const need = stablesFloor - (T['Stablecoins'] || 0);
    const riskyKeys = Object.keys(T).filter(k => k !== 'Stablecoins');
    const riskySum = riskyKeys.reduce((sum, k) => sum + (T[k] || 0), 0);

    if (riskySum > 0) {
      // Reduce risky assets pro-rata to fund stables floor
      riskyKeys.forEach(asset => {
        const reduction = need * (T[asset] || 0) / riskySum;
        T[asset] = Math.max(0, (T[asset] || 0) - reduction);
      });
    }

    T['Stablecoins'] = stablesFloor;
    stablesFloorHit = true;

    console.debug('🏛️ PhaseEngine: Stables floor applied:', {
      required: stablesFloor + '%',
      fundeBy: 'reducing risky assets pro-rata'
    });
  }

  // Step 3: Normalize to 100% while preserving stables floor
  const sum = Object.values(T).reduce((total, value) => total + (value || 0), 0);
  if (sum > 0 && Math.abs(sum - 100) > 0.01) {
    const scaleFactor = 100 / sum;

    // If stables floor was hit, protect it during normalization
    if (stablesFloorHit) {
      // Scale only risky assets to preserve stables floor
      const riskyKeys = Object.keys(T).filter(k => k !== 'Stablecoins');
      const riskySum = riskyKeys.reduce((sum, k) => sum + (T[k] || 0), 0);
      const stablesValue = T['Stablecoins'] || 0;
      const targetRiskySum = 100 - stablesValue; // Remaining for risky assets

      if (riskySum > 0) {
        const riskyScaleFactor = targetRiskySum / riskySum;
        riskyKeys.forEach(asset => {
          T[asset] = (T[asset] || 0) * riskyScaleFactor;
        });

        console.debug('📊 PhaseEngine: Normalized risky assets while preserving stables floor:', {
          originalSum: sum.toFixed(2) + '%',
          stablesFloor: stablesValue.toFixed(2) + '%',
          riskySum: riskySum.toFixed(2) + '%',
          riskyScaleFactor: riskyScaleFactor.toFixed(4),
          finalSum: Object.values(T).reduce((a, b) => a + b, 0).toFixed(2) + '%'
        });
      }
    } else {
      // Normal scaling when no floor constraints
      Object.keys(T).forEach(asset => {
        T[asset] = (T[asset] || 0) * scaleFactor;
      });

      console.debug('📊 PhaseEngine: Normalized to 100%:', {
        originalSum: sum.toFixed(2) + '%',
        scaleFactor: scaleFactor.toFixed(4),
        finalSum: Object.values(T).reduce((a, b) => a + b, 0).toFixed(2) + '%'
      });
    }
  }

  return {
    targets: T,
    original: { ...targets }, // Store original for comparison
    metadata: {
      tiltsApplied: phase !== 'neutral',
      phase,
      capsTriggered,
      stablesFloorHit,
      finalSum: Object.values(T).reduce((a, b) => a + b, 0)
    }
  };
}

/**
 * Main function: Apply phase-based tilts to target allocations
 * @param {Object} targets - Original target allocations (normalized to 100%)
 * @param {string} phase - Detected phase
 * @param {Object} ctx - Context {DI, breadth_alts}
 * @returns {Object} Adjusted targets with metadata
 */
export function applyPhaseTilts(targets, phase, ctx = {}) {
  console.debug('🎯 PhaseEngine: Applying phase tilts:', { phase, targets: Object.keys(targets) });

  if (!targets || Object.keys(targets).length === 0) {
    console.warn('⚠️ PhaseEngine: No targets provided');
    return { targets: {}, metadata: { error: 'No targets provided' } };
  }

  // If neutral, return targets unchanged
  if (phase === 'neutral') {
    console.debug('😐 PhaseEngine: Neutral phase, no tilts applied');
    return {
      targets: { ...targets },
      metadata: { phase, tiltsApplied: false, reason: 'neutral phase' }
    };
  }

  // Define tilts by phase including Stablecoins adjustments
  const tiltsByPhase = {
    risk_off: {
      Stablecoins: 1.15,   // +15% (flight to safety)
      BTC: 0.92,           // -8% (risk reduction)
      ETH: 0.90,           // -10% (risk reduction)
      SOL: 0.85,           // -15% (highest risk reduction)
      'L2/Scaling': 0.85,  // -15%
      DeFi: 0.80,          // -20%
      'AI/Data': 0.75,     // -25%
      'Gaming/NFT': 0.70,  // -30%
      Memecoins: 0.50      // -50% (extreme risk reduction)
    },
    eth_expansion: {
      ETH: 1.05,           // +5%
      'L2/Scaling': 1.03,  // +3%
      Stablecoins: 0.98,   // -2% (slight risk-on)
      BTC: 0.98            // -2%
    },
    largecap_altseason: {
      'L1/L0 majors': 1.08, // +8%
      SOL: 1.06,           // +6%
      'L2/Scaling': 1.04,  // +4%
      DeFi: 1.03,          // +3%
      Others: 1.20,        // +20% (small caps start to move)
      Stablecoins: 0.95,   // -5% (moderate risk-on)
      BTC: 0.92            // -8%
    },
    full_altseason: {
      'L2/Scaling': 1.10,   // +10%
      DeFi: 1.08,          // +8%
      'AI/Data': 1.06,     // +6%
      'Gaming/NFT': 1.05,  // +5%
      Memecoins: 2.50,     // +150% (meme season boost)
      Others: 2.00,        // +100% (small caps boost)
      Stablecoins: 0.85,   // -15% (strong risk-on, FOMO)
      BTC: 0.90,           // -10% (rotate out of BTC)
      ETH: 0.95            // -5% (slight rotation to alts)
    }
  };

  const tilts = tiltsByPhase[phase] || {};

  if (Object.keys(tilts).length === 0) {
    console.debug('🤷 PhaseEngine: No tilts defined for phase:', phase);
    return {
      targets: { ...targets },
      metadata: { phase, tiltsApplied: false, reason: 'no tilts defined for phase' }
    };
  }

  // Special memecoins handling for full_altseason
  let memecoinsAdjustment = null;
  if (phase === 'full_altseason' && ctx.DI >= 80 && ctx.breadth_alts >= 0.80) {
    const currentMemes = targets['Memecoins'] || 0;
    const maxMemes = 2.0; // 2% cap
    if (currentMemes < maxMemes) {
      const increase = Math.min(1.0, maxMemes - currentMemes); // +1% max
      memecoinsAdjustment = increase;

      console.debug('🐸 PhaseEngine: Memecoins boost activated:', {
        condition: `DI=${ctx.DI} >= 80 && breadth=${(ctx.breadth_alts * 100).toFixed(1)}% >= 80%`,
        current: currentMemes.toFixed(2) + '%',
        increase: `+${increase.toFixed(2)}%`,
        cap: maxMemes + '%'
      });
    }
  }

  // Apply tilts (now includes Stablecoins)
  let adjustedTargets = applyAllTilts(targets, tilts);

  // Apply memecoins adjustment (taken from stables)
  if (memecoinsAdjustment && memecoinsAdjustment > 0) {
    const currentStables = adjustedTargets['Stablecoins'] || 0;
    if (currentStables >= STABLES_FLOOR + memecoinsAdjustment) {
      adjustedTargets['Stablecoins'] = currentStables - memecoinsAdjustment;
      adjustedTargets['Memecoins'] = (adjustedTargets['Memecoins'] || 0) + memecoinsAdjustment;

      console.debug('🐸 PhaseEngine: Memecoins funded from stables:', {
        stablesReduction: `-${memecoinsAdjustment.toFixed(2)}%`,
        memecoinsIncrease: `+${memecoinsAdjustment.toFixed(2)}%`,
        stablesRemaining: adjustedTargets['Stablecoins'].toFixed(2) + '%'
      });
    } else {
      console.debug('🛡️ PhaseEngine: Memecoins adjustment blocked by stables floor');
      memecoinsAdjustment = null;
    }
  }

  // Apply caps, stables floor, and normalization
  const finalized = finalizeCapsAndNormalize(adjustedTargets, {
    caps: PHASE_CAPS,
    stablesFloor: STABLES_FLOOR,
    phase
  });

  const metadata = {
    phase,
    tiltsApplied: true,
    tilts,
    memecoinsAdjustment,
    ...finalized.metadata,
    originalSum: Object.values(targets).reduce((a, b) => a + b, 0),
    context: { DI: ctx.DI, breadth_alts: ctx.breadth_alts }
  };

  console.debug('✅ PhaseEngine: Phase tilts complete:', {
    phase,
    tiltsCount: Object.keys(tilts).length,
    capsTriggered: metadata.capsTriggered.length,
    stablesFloorHit: metadata.stablesFloorHit,
    memecoinsBoost: !!memecoinsAdjustment
  });

  return {
    targets: finalized.targets,
    metadata
  };
}

/**
 * Get current phase memory for debugging
 * @returns {Object} Phase memory state
 */
export function getPhaseMemoryState() {
  return {
    ...phaseMemory,
    lastEvaluationAge: Date.now() - phaseMemory.lastEvaluationTime
  };
}

/**
 * Reset phase memory (useful for testing)
 */
export function resetPhaseMemory() {
  phaseMemory.history = [];
  phaseMemory.lastPhase = 'neutral';
  phaseMemory.lastEvaluationTime = 0;
  console.debug('🔄 PhaseEngine: Memory reset');
}

// Debug override for testing specific phases - persist in localStorage
const DEBUG_FORCE_KEY = 'PHASE_ENGINE_DEBUG_FORCE';

/**
 * Get currently forced phase from localStorage
 * @returns {string|null} Currently forced phase or null
 */
function getDebugForcePhase() {
  if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
    return localStorage.getItem(DEBUG_FORCE_KEY);
  }
  return null;
}

/**
 * Force a specific phase for testing (debug only) - persists across reloads
 * @param {string} phase - Phase to force ('eth_expansion', 'full_altseason', etc.)
 */
export function forcePhase(phase) {
  if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
    localStorage.setItem(DEBUG_FORCE_KEY, phase);
    console.warn('🔧 PhaseEngine: DEBUG - Forcing phase (persisted):', phase);
  } else {
    console.warn('🔧 PhaseEngine: Force phase only available in localhost');
  }
}

/**
 * Clear forced phase (return to normal detection)
 */
export function clearForcePhase() {
  if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
    localStorage.removeItem(DEBUG_FORCE_KEY);
    console.debug('🔧 PhaseEngine: DEBUG - Cleared forced phase, returning to normal detection');
  }
}

/**
 * Get currently forced phase (debug only)
 * @returns {string|null} Currently forced phase or null
 */
export function getCurrentForce() {
  return getDebugForcePhase();
}

// Development helpers
if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
  window.debugPhaseEngine = {
    inferPhase,
    applyPhaseTilts,
    getMemoryState: getPhaseMemoryState,
    resetMemory: resetPhaseMemory,
    testTilts: (targets, phase) => applyPhaseTilts(targets, phase, { DI: 75, breadth_alts: 0.7 }),
    forcePhase,
    clearForcePhase,
    getCurrentForce: () => debugForcePhase
  };

  console.debug('🔧 Debug: window.debugPhaseEngine available for testing');
}