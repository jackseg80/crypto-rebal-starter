/**
 * Phase Tilts Helpers - Risky-only, zero-sum allocation adjustments
 * Architecture: Never touch Stablecoins allocation, operate only within risky pool
 */

/**
 * Apply multiplicative tilts within risky pool with zero-sum compensation
 * @param {Object} T - Target allocations (will be mutated)
 * @param {Object} ups - Multiplicative tilts { asset: multiplier }
 * @param {Array<string>} downsKeys - Assets to compensate from (default: all risky)
 * @returns {Object} Modified targets with tilts applied
 */
export function tiltRiskyZeroSum(T, ups = {}, downsKeys = []) {
  if (!T || typeof T !== 'object') {
    console.warn('⚠️ TiltHelpers: Invalid targets object');
    return T;
  }

  const stables = T['Stablecoins'] || 0;
  const riskyKeys = Object.keys(T).filter(k => k !== 'Stablecoins');

  console.debug('🔧 TiltHelpers: Applying risky zero-sum tilts:', {
    ups,
    downsKeys,
    stablesPreserved: stables.toFixed(2) + '%',
    riskyKeys: riskyKeys.length
  });

  // 1) Apply multiplicative increases
  let totalIncrease = 0;
  for (const [asset, multiplier] of Object.entries(ups)) {
    if (!T[asset]) {
      console.debug(`⚠️ TiltHelpers: Asset '${asset}' not found in targets, skipping`);
      continue;
    }

    const before = T[asset];
    const after = before * multiplier;
    const delta = Math.max(0, after - before);

    totalIncrease += delta;
    T[asset] = after;

    console.debug(`📈 TiltHelpers: Tilted ${asset}:`, {
      before: before.toFixed(2) + '%',
      multiplier: `×${multiplier}`,
      after: after.toFixed(2) + '%',
      delta: `+${delta.toFixed(2)}%`
    });
  }

  if (totalIncrease <= 0) {
    console.debug('✅ TiltHelpers: No net increase, no compensation needed');
    return T;
  }

  // 2) Compensate from specified pool (or all risky if not specified)
  const compensationPool = (downsKeys.length ? downsKeys : riskyKeys)
    .filter(k => (T[k] || 0) > 0);

  if (compensationPool.length === 0) {
    console.warn('⚠️ TiltHelpers: No valid compensation pool, cannot apply tilts');
    return T;
  }

  const poolSum = compensationPool.reduce((sum, k) => sum + (T[k] || 0), 0);
  if (poolSum <= 0) {
    console.warn('⚠️ TiltHelpers: Compensation pool sum is zero');
    return T;
  }

  console.debug('💰 TiltHelpers: Compensating from pool:', {
    pool: compensationPool,
    poolSum: poolSum.toFixed(2) + '%',
    totalDecrease: totalIncrease.toFixed(2) + '%'
  });

  compensationPool.forEach(asset => {
    const weight = (T[asset] || 0) / poolSum;
    const decrease = totalIncrease * weight;
    const before = T[asset];
    T[asset] = Math.max(0, before - decrease);

    console.debug(`📉 TiltHelpers: Compensated ${asset}:`, {
      before: before.toFixed(2) + '%',
      decrease: decrease.toFixed(2) + '%',
      after: T[asset].toFixed(2) + '%',
      weight: (weight * 100).toFixed(1) + '%'
    });
  });

  // 3) Renormalize risky pool to preserve (100 - stables)
  const riskyTarget = 100 - stables;
  const currentRiskySum = riskyKeys.reduce((sum, k) => sum + (T[k] || 0), 0);

  if (currentRiskySum > 0) {
    const normalizationFactor = riskyTarget / currentRiskySum;

    console.debug('🎯 TiltHelpers: Renormalizing risky pool:', {
      riskyTarget: riskyTarget.toFixed(2) + '%',
      currentSum: currentRiskySum.toFixed(2) + '%',
      factor: normalizationFactor.toFixed(4)
    });

    riskyKeys.forEach(asset => {
      if (T[asset]) {
        T[asset] = T[asset] * normalizationFactor;
      }
    });
  }

  // 4) Restore stables unchanged
  T['Stablecoins'] = stables;

  console.debug('✅ TiltHelpers: Zero-sum tilts applied, stables preserved:', {
    finalStables: T['Stablecoins'].toFixed(2) + '%',
    finalRiskySum: riskyKeys.reduce((sum, k) => sum + (T[k] || 0), 0).toFixed(2) + '%'
  });

  return T;
}

/**
 * Apply per-bucket caps and normalize with stables floor check
 * @param {Object} T - Target allocations
 * @param {Object} caps - Per-asset caps { asset: maxPercent }
 * @param {number} stablesFloor - Minimum stables percentage (default: 5)
 * @returns {Object|null} Normalized targets or null if floor breached
 */
export function applyCapsAndNormalize(T, caps = {}, stablesFloor = 5) {
  if (!T || typeof T !== 'object') {
    console.warn('⚠️ TiltHelpers: Invalid targets for caps');
    return null;
  }

  console.debug('🧢 TiltHelpers: Applying caps and normalization:', {
    caps,
    stablesFloor: stablesFloor + '%'
  });

  const result = { ...T }; // Clone to avoid mutation
  let capsTriggered = [];

  // 1) Apply per-bucket caps
  for (const [asset, cap] of Object.entries(caps)) {
    if (result[asset] && result[asset] > cap) {
      const before = result[asset];
      result[asset] = cap;
      capsTriggered.push({
        asset,
        before: before.toFixed(2) + '%',
        capped: cap.toFixed(2) + '%'
      });
    }

    // Ensure no negative values
    if (result[asset] && result[asset] < 0) {
      result[asset] = 0;
    }
  }

  if (capsTriggered.length > 0) {
    console.debug('🚫 TiltHelpers: Caps triggered:', capsTriggered);
  }

  // 2) Stables floor check (abort if breached)
  const currentStables = result['Stablecoins'] || 0;
  if (currentStables < stablesFloor) {
    console.warn('🚨 TiltHelpers: Stables floor breached - aborting tilts this tick:', {
      current: currentStables.toFixed(2) + '%',
      floor: stablesFloor + '%'
    });
    return null; // Signal to abort tilts
  }

  // 3) Final normalization to 100%
  const totalSum = Object.values(result).reduce((sum, val) => sum + (val || 0), 0);

  if (totalSum <= 0) {
    console.error('🚨 TiltHelpers: Total sum is zero after caps');
    return null;
  }

  if (Math.abs(totalSum - 100) > 1e-6) {
    console.debug('🎯 TiltHelpers: Normalizing to 100%:', {
      beforeSum: totalSum.toFixed(4) + '%',
      normalizationFactor: (100 / totalSum).toFixed(6)
    });

    for (const asset of Object.keys(result)) {
      if (result[asset]) {
        result[asset] = (result[asset] * 100) / totalSum;
      }
    }
  }

  const finalSum = Object.values(result).reduce((sum, val) => sum + (val || 0), 0);
  console.debug('✅ TiltHelpers: Caps and normalization complete:', {
    finalSum: finalSum.toFixed(4) + '%',
    capsTriggered: capsTriggered.length,
    stablesPreserved: (result['Stablecoins'] || 0).toFixed(2) + '%'
  });

  return result;
}

/**
 * Apply min-effect filter to avoid micro-orders
 * @param {Object} tiltedTargets - Targets after tilts
 * @param {Object} originalTargets - Original targets before tilts
 * @param {number} threshold - Minimum effect threshold (default: 0.5%)
 * @returns {Object} Filtered targets
 */
export function applyMinEffectFilter(tiltedTargets, originalTargets, threshold = 0.5) {
  if (!tiltedTargets || !originalTargets) {
    console.warn('⚠️ TiltHelpers: Invalid targets for min-effect filter');
    return tiltedTargets;
  }

  const result = { ...tiltedTargets };
  let filtered = [];

  console.debug('🔍 TiltHelpers: Applying min-effect filter:', {
    threshold: threshold + '%'
  });

  for (const asset of Object.keys(result)) {
    const tilted = result[asset] || 0;
    const original = originalTargets[asset] || 0;
    const delta = Math.abs(tilted - original);

    if (delta < threshold && delta > 0) {
      result[asset] = original; // Revert to original
      filtered.push({
        asset,
        delta: delta.toFixed(3) + '%',
        reverted: true
      });
    }
  }

  if (filtered.length > 0) {
    console.debug('🎛️ TiltHelpers: Min-effect filter applied:', filtered);
  }

  // Re-normalize after filtering
  const sum = Object.values(result).reduce((total, val) => total + (val || 0), 0);
  if (Math.abs(sum - 100) > 1e-6) {
    console.debug('🎯 TiltHelpers: Re-normalizing after filter:', {
      sum: sum.toFixed(4) + '%'
    });

    for (const asset of Object.keys(result)) {
      if (result[asset]) {
        result[asset] = (result[asset] * 100) / sum;
      }
    }
  }

  return result;
}

/**
 * Validate targets integrity (sum=100%, no negatives, stables preserved)
 * @param {Object} targets - Targets to validate
 * @param {Object} originalTargets - Original targets for comparison
 * @returns {Object} Validation result with warnings
 */
export function validateTargetsIntegrity(targets, originalTargets = null) {
  const warnings = [];
  const metrics = {};

  if (!targets) {
    return { valid: false, warnings: ['Targets object is null'], metrics };
  }

  // Check sum = 100%
  const sum = Object.values(targets).reduce((total, val) => total + (val || 0), 0);
  metrics.sum = sum;

  if (Math.abs(sum - 100) > 0.01) {
    warnings.push(`Sum not 100%: ${sum.toFixed(4)}%`);
  }

  // Check for negative values
  const negatives = Object.entries(targets).filter(([_, val]) => val < 0);
  if (negatives.length > 0) {
    warnings.push(`Negative values: ${negatives.map(([k, v]) => `${k}=${v.toFixed(2)}%`).join(', ')}`);
  }

  // Check stables preservation (if original provided)
  if (originalTargets && originalTargets['Stablecoins']) {
    const originalStables = originalTargets['Stablecoins'];
    const currentStables = targets['Stablecoins'] || 0;
    const stablesDelta = Math.abs(currentStables - originalStables);

    metrics.stablesPreserved = stablesDelta < 0.01;
    if (stablesDelta > 0.01) {
      warnings.push(`Stables not preserved: ${originalStables.toFixed(2)}% → ${currentStables.toFixed(2)}%`);
    }
  }

  // Check risky pool zero-sum (if original provided)
  if (originalTargets) {
    const originalRisky = Object.keys(originalTargets)
      .filter(k => k !== 'Stablecoins')
      .reduce((sum, k) => sum + (originalTargets[k] || 0), 0);

    const currentRisky = Object.keys(targets)
      .filter(k => k !== 'Stablecoins')
      .reduce((sum, k) => sum + (targets[k] || 0), 0);

    const riskyDelta = Math.abs(currentRisky - originalRisky);
    metrics.riskyZeroSum = riskyDelta < 0.01;

    if (riskyDelta > 0.01) {
      warnings.push(`Risky pool not zero-sum: ${originalRisky.toFixed(2)}% → ${currentRisky.toFixed(2)}%`);
    }
  }

  return {
    valid: warnings.length === 0,
    warnings,
    metrics
  };
}

// Development helpers
if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
  window.debugTiltHelpers = {
    tiltRiskyZeroSum,
    applyCapsAndNormalize,
    applyMinEffectFilter,
    validateTargetsIntegrity
  };

  console.debug('🔧 Debug: window.debugTiltHelpers available for testing');
}