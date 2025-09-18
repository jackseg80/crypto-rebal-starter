/**
 * Phase Engine - New risky-only implementation
 * Temporary file for development
 */

/**
 * Apply phase-specific tilts using risky-only, zero-sum architecture
 * @param {Object} targets - Original targets allocation
 * @param {string} phase - Detected phase
 * @param {Object} ctx - Context (DI, breadth_alts, etc.)
 * @returns {Promise<Object>} Result with targets and metadata
 */
export async function applyPhaseTilts(targets, phase, ctx = {}) {
  console.debug('🎯 PhaseEngine: Applying risky-only phase tilts:', {
    phase,
    targetsCount: Object.keys(targets).length,
    stablesPreserved: (targets['Stablecoins'] || 0).toFixed(2) + '%'
  });

  if (!targets || Object.keys(targets).length === 0) {
    console.warn('⚠️ PhaseEngine: No targets provided');
    return { targets: {}, metadata: { error: 'No targets provided' } };
  }

  // If neutral or risk_off, return targets unchanged (no tilts)
  if (phase === 'neutral' || phase === 'risk_off') {
    console.debug(`😐 PhaseEngine: ${phase} phase, no tilts applied (risky-only policy)`);
    return {
      targets: { ...targets },
      metadata: {
        phase,
        tiltsApplied: false,
        reason: `${phase} phase - no tilts in risky-only architecture`,
        stablesPreserved: true
      }
    };
  }

  // Import helpers
  const { tiltRiskyZeroSum, applyCapsAndNormalize, applyMinEffectFilter, validateTargetsIntegrity }
    = await import('./phase-tilts-helpers.js');

  let T = { ...targets }; // Working copy
  const originalTargets = { ...targets }; // Preserve original for comparison

  // Risky asset caps
  const riskyCaps = {
    'L2/Scaling': 8,
    'DeFi': 8,
    'Gaming/NFT': 5,
    'Memecoins': 2,
    'Others': 2
  };

  // Stables floor (from constants)
  const STABLES_FLOOR = 5;

  console.debug('🎯 PhaseEngine: Applying phase-specific tilts for:', phase);

  try {
    // Apply phase-specific tilts with zero-sum compensation
    switch (phase) {
      case 'eth_expansion':
        T = tiltRiskyZeroSum(T, {
          'ETH': 1.05,        // +5%
          'L2/Scaling': 1.03  // +3%
        }, ['BTC']); // Compensate from BTC only
        break;

      case 'largecap_altseason':
        T = tiltRiskyZeroSum(T, {
          'L1/L0 majors': 1.06, // +6%
          'SOL': 1.04           // +4%
        }, ['BTC', 'ETH']); // Compensate from BTC+ETH pro-rata
        break;

      case 'full_altseason':
        // Multiplicative tilts
        T = tiltRiskyZeroSum(T, {
          'L2/Scaling': 1.08,  // +8%
          'DeFi': 1.06,        // +6%
          'AI/Data': 1.04,     // +4%
          'Gaming/NFT': 1.06   // +6%
        }, ['BTC', 'L1/L0 majors']); // Compensate from BTC+L1

        // Memecoins absolute boost (+1% risky-budget aware)
        if (ctx.DI >= 80 && ctx.breadth_alts >= 0.80) {
          const stables = T['Stablecoins'] || 0;
          const riskyBudget = 100 - stables;
          const currentMemes = T['Memecoins'] || 0;
          const targetMemes = Math.min(2.0, currentMemes + Math.min(1.0, riskyBudget * 0.01));
          const delta = targetMemes - currentMemes;

          if (delta > 0) {
            console.debug('🐸 PhaseEngine: Memecoins absolute boost:', {
              condition: `DI=${ctx.DI} >= 80 && breadth=${(ctx.breadth_alts * 100).toFixed(1)}% >= 80%`,
              current: currentMemes.toFixed(2) + '%',
              target: targetMemes.toFixed(2) + '%',
              delta: `+${delta.toFixed(2)}%`,
              riskyBudget: riskyBudget.toFixed(2) + '%'
            });

            // Compensate from BTC+L1 pool
            const compensationPool = ['BTC', 'L1/L0 majors'].filter(k => (T[k] || 0) > 0);
            const poolSum = compensationPool.reduce((sum, k) => sum + (T[k] || 0), 0);

            if (poolSum > 0) {
              compensationPool.forEach(asset => {
                const weight = (T[asset] || 0) / poolSum;
                T[asset] = Math.max(0, T[asset] - delta * weight);
              });

              T['Memecoins'] = targetMemes;

              // Renormalize risky pool
              const riskyKeys = Object.keys(T).filter(k => k !== 'Stablecoins');
              const riskySum = riskyKeys.reduce((sum, k) => sum + (T[k] || 0), 0);
              if (riskySum > 0) {
                const normFactor = riskyBudget / riskySum;
                riskyKeys.forEach(k => { T[k] = T[k] * normFactor; });
              }

              // Restore stables
              T['Stablecoins'] = stables;
            }
          }
        }
        break;

      default:
        console.debug(`🤷 PhaseEngine: No tilts defined for phase: ${phase}`);
        return {
          targets: { ...targets },
          metadata: { phase, tiltsApplied: false, reason: 'no tilts defined for phase' }
        };
    }

    // Apply caps and normalize
    const cappedTargets = applyCapsAndNormalize(T, riskyCaps, STABLES_FLOOR);
    if (!cappedTargets) {
      console.warn('🚨 PhaseEngine: Stables floor breached - aborting tilts');
      return {
        targets: { ...targets },
        metadata: {
          phase,
          tiltsApplied: false,
          reason: 'stables floor breached',
          error: 'floor_breach'
        }
      };
    }

    // Apply min-effect filter (reduced threshold for more sensitive tilts)
    const filteredTargets = applyMinEffectFilter(cappedTargets, originalTargets, 0.03);

    // Validate integrity
    const validation = validateTargetsIntegrity(filteredTargets, originalTargets);
    if (!validation.valid) {
      console.warn('🚨 PhaseEngine: Validation failed:', validation.warnings);
    }

    // Calculate deltas
    const deltas = Object.keys(filteredTargets).reduce((d, asset) => {
      const original = originalTargets[asset] || 0;
      const final = filteredTargets[asset] || 0;
      d[asset] = final - original;
      return d;
    }, {});

    const metadata = {
      phase,
      tiltsApplied: true,
      originalTargets,
      finalTargets: filteredTargets,
      deltas,
      validation,
      context: ctx,
      stablesPreserved: Math.abs((filteredTargets['Stablecoins'] || 0) - (originalTargets['Stablecoins'] || 0)) < 0.01,
      significantChanges: Object.entries(deltas)
        .filter(([_, delta]) => Math.abs(delta) > 0.03)
        .map(([asset, delta]) => `${asset}: ${delta > 0 ? '+' : ''}${delta.toFixed(2)}%`)
    };

    console.debug('✅ PhaseEngine: Risky-only tilts applied successfully:', {
      phase,
      stablesPreserved: metadata.stablesPreserved,
      significantChanges: metadata.significantChanges,
      validationPassed: validation.valid,
      finalSum: Object.values(filteredTargets).reduce((sum, val) => sum + val, 0).toFixed(4) + '%'
    });

    return {
      targets: filteredTargets,
      metadata
    };

  } catch (error) {
    console.error('🚨 PhaseEngine: Error applying tilts:', error);
    return {
      targets: { ...targets },
      metadata: {
        phase,
        tiltsApplied: false,
        reason: 'error applying tilts',
        error: error.message
      }
    };
  }
}