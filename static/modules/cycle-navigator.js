/**
 * Cycle Navigator - Bitcoin Halving Cycle Analysis
 * Computes cycle score and blends with CCS for enhanced targeting
 * Ajout : paramètres globaux calibrables + calibration sur historiques
 */

/**
 * Calculate cycle score based on months after halving
 * Bitcoin halving cycles: ~4 years (48 months)
 */

// --- Paramètres globaux (défauts = mêmes courbes que ta version actuelle) ---
let CYCLE_PARAMS = {
  m_rise_center: 8.0,   // centre montée (comme avant)
  m_fall_center: 32.0,  // centre descente (comme avant)
  k_rise: 0.9,          // pente montée (comme avant)
  k_fall: 0.9,          // pente descente (comme avant)
  p_shape: 0.9,         // expo "douce" (comme avant)
  floor: 0,             // on garde 0..100 pour ne rien changer par défaut
  ceil: 100
};

export function getCycleParams() { return { ...CYCLE_PARAMS }; }
export function setCycleParams(p) { 
  CYCLE_PARAMS = { ...CYCLE_PARAMS, ...p }; 
  console.debug('🔄 Cycle parameters updated:', CYCLE_PARAMS);
}

// Auto-load calibrated parameters on module initialization
function autoLoadCalibrationParams() {
  try {
    const saved = localStorage.getItem('bitcoin_cycle_params');
    if (saved) {
      const data = JSON.parse(saved);
      // Check data is not too old (24h)
      if (Date.now() - data.timestamp < 24 * 60 * 60 * 1000) {
        CYCLE_PARAMS = { ...CYCLE_PARAMS, ...data.params };
        console.debug('✅ Auto-loaded calibrated cycle parameters', CYCLE_PARAMS);
        return true;
      }
    }
  } catch (error) {
    console.error('❌ Error auto-loading cycle parameters:', error);
  }
  return false;
}

// Initialize on module load
autoLoadCalibrationParams();

export function cycleScoreFromMonths(monthsAfterHalving, opts = {}) {

  // Modèle lissé : produit de 2 sigmoïdes (montée puis descente), échelle 0–100.
  if (typeof monthsAfterHalving !== 'number' || monthsAfterHalving < 0) return 50;
  const m48 = monthsAfterHalving % 48; // cycle ~4 ans

  // Paramètres : globaux (CYCLE_PARAMS) + overrides éventuels
  const {
    m_rise_center, m_fall_center, k_rise, k_fall, p_shape, floor, ceil
  } = { ...CYCLE_PARAMS, ...opts };

  const rise = 1 / (1 + Math.exp(-k_rise * (m48 - m_rise_center)));
  const fall = 1 / (1 + Math.exp(-k_fall * (m_fall_center - m48)));
  const base = rise * fall;                 // cloche 0..1
  let score = Math.pow(base, p_shape) * 100; // normalisation (idem avant via p_shape=0.9)

  // clamps doux (par défaut 0..100 donc neutre)
  if (score < floor) score = floor;
  if (score > ceil) score = ceil;
  return score;
}

/**
 * Get cycle phase description
 */
export function getCyclePhase(monthsAfterHalving) {
  if (typeof monthsAfterHalving !== 'number') {
    return { phase: 'unknown', description: 'Invalid cycle data' };
  }

  const m = monthsAfterHalving % 48;

  if (m <= 6) {
    return {
      phase: 'accumulation',
      description: `Accumulation Phase (${Math.round(m)}m post-halving)`,
      color: '#f59e0b',
      emoji: '🟡'
    };
  } else if (m <= 18) {
    return {
      phase: 'bull_build',
      description: `Bull Market Building (${Math.round(m)}m post-halving)`,
      color: '#10b981',
      emoji: '🟢'
    };
  } else if (m <= 24) {
    return {
      phase: 'peak',
      description: `Peak/Euphoria Phase (${Math.round(m)}m post-halving)`,
      color: '#8b5cf6',
      emoji: '🟣'
    };
  } else if (m <= 36) {
    return {
      phase: 'bear',
      description: `Bear Market (${Math.round(m)}m post-halving)`,
      color: '#dc2626',
      emoji: '🔴'
    };
  } else {
    return {
      phase: 'pre_accumulation',
      description: `Pre-Accumulation (${Math.round(m)}m post-halving)`,
      color: '#6b7280',
      emoji: '⚫'
    };
  }
}

/**
 * Calculate cycle multipliers for different phases
 */
export function cycleMultipliers(monthsAfterHalving) {
  const cycleScore = cycleScoreFromMonths(monthsAfterHalving);
  const phase = getCyclePhase(monthsAfterHalving);

  // Multipliers based on cycle phase
  let btcMultiplier = 1.0;
  let ethMultiplier = 1.0;
  let altMultiplier = 1.0;
  let stableMultiplier = 1.0;

  switch (phase.phase) {
    case 'accumulation':
      btcMultiplier = 1.1;   // Slight BTC preference
      ethMultiplier = 1.05;
      altMultiplier = 0.9;   // Reduce alts
      stableMultiplier = 0.95;
      break;

    case 'bull_build':
      btcMultiplier = 1.2;   // Strong BTC preference
      ethMultiplier = 1.15;
      altMultiplier = 1.1;   // Start increasing alts
      stableMultiplier = 0.8; // Reduce stables
      break;

    case 'peak':
      btcMultiplier = 0.9;   // Take profits from BTC
      ethMultiplier = 1.0;
      altMultiplier = 1.3;   // Alt season
      stableMultiplier = 1.2; // Increase cash for volatility
      break;

    case 'bear':
      btcMultiplier = 1.0;   // Neutral BTC
      ethMultiplier = 0.9;
      altMultiplier = 0.7;   // Heavily reduce alts
      stableMultiplier = 1.4; // Flight to safety
      break;

    case 'pre_accumulation':
      btcMultiplier = 1.05;  // Slight accumulation
      ethMultiplier = 1.0;
      altMultiplier = 0.8;   // Still cautious on alts
      stableMultiplier = 1.1;
      break;

    default:
      // No adjustments
      break;
  }

  return {
    BTC: btcMultiplier,
    ETH: ethMultiplier,
    'Stablecoins': stableMultiplier,
    'L1/L0 majors': altMultiplier,
    'L2/Scaling': altMultiplier,
    'DeFi': altMultiplier * 1.1, // Slightly higher alt preference
    'AI/Data': altMultiplier,
    'Gaming/NFT': altMultiplier * 0.9, // Lower preference
    'Memecoins': Math.max(0.1, altMultiplier * 0.8), // Very cautious
    'Others': altMultiplier
  };
}

/**
 * Blend CCS score with cycle score
 */
export function blendCCS(ccsScore, cycleMonths, cycleWeight = 0.3) {
  if (typeof ccsScore !== 'number' || typeof cycleWeight !== 'number') {
    throw new Error('Invalid inputs for CCS blending');
  }

  // Validate inputs
  if (ccsScore < 0 || ccsScore > 100) {
    throw new Error(`Invalid CCS score: ${ccsScore}`);
  }

  if (cycleWeight < 0 || cycleWeight > 1) {
    throw new Error(`Invalid cycle weight: ${cycleWeight}`);
  }

  const cycleScore = cycleScoreFromMonths(cycleMonths);

  // Weighted blend
  const blendedScore = ccsScore * (1 - cycleWeight) + cycleScore * cycleWeight;

  return {
    originalCCS: ccsScore,
    cycleScore: cycleScore,
    blendedCCS: Math.round(blendedScore * 100) / 100,
    cycleWeight: cycleWeight,
    phase: getCyclePhase(cycleMonths)
  };
}

/**
 * Get current months after halving (real calculation)
 * Calculates actual months since the last Bitcoin halving
 */
export function getCurrentCycleMonths() {
  // Real Bitcoin halving date (April 20, 2024)
  const lastHalvingDate = new Date('2024-04-20');
  const now = new Date();

  // Calculate months difference
  const yearDiff = now.getFullYear() - lastHalvingDate.getFullYear();
  const monthDiff = now.getMonth() - lastHalvingDate.getMonth();
  const dayDiff = now.getDate() - lastHalvingDate.getDate();

  // Total months (with fraction for days)
  let totalMonths = yearDiff * 12 + monthDiff;
  if (dayDiff > 0) {
    totalMonths += dayDiff / 30; // Approximate days to month fraction
  }

  // Ensure non-negative
  totalMonths = Math.max(0, totalMonths);

  console.debug('🔍 DEBUG getCurrentCycleMonths:', {
    lastHalving: lastHalvingDate.toISOString(),
    now: now.toISOString(),
    yearDiff,
    monthDiff,
    dayDiff,
    totalMonths,
    rounded: Math.round(totalMonths)
  });

  return {
    months: totalMonths,
    lastHalving: '2024-04-20', // Actual last halving
    nextHalving: '2028-04-20', // Estimated next halving (~4 years)
    source: 'real_calculation'
  };
}

// ---------------- Calibration sur ancres historiques ----------------
// Ancres par défaut (pics/creux historiques; modifiables côté UI si besoin)
const DEF_ANCHORS = [
  { halving: '2012-11-28', peak: '2013-11-30', bottom: '2015-01-14' },
  { halving: '2016-07-09', peak: '2017-12-17', bottom: '2018-12-15' },
  { halving: '2020-05-11', peak: '2021-11-10', bottom: '2022-11-21' },
];

function monthsBetween(a, b) {
  return (new Date(b) - new Date(a)) / (1000 * 60 * 60 * 24 * 30.44);
}

function objective(params, anchors) {
  // Erreur quadratique simple sur 3 contraintes :
  // - peak ≈ 100, bottom ≈ 10, early(2m) ≈ 5
  let err = 0;
  for (const a of anchors) {
    const m_peak = monthsBetween(a.halving, a.peak);
    const m_bot = monthsBetween(a.halving, a.bottom);
    const m_early = 2;
    const s_peak = cycleScoreFromMonths(m_peak, params);
    const s_bot = cycleScoreFromMonths(m_bot, params);
    const s_early = cycleScoreFromMonths(m_early, params);
    err += Math.pow(100 - s_peak, 2) * 1.0;
    err += Math.pow(10 - s_bot, 2) * 0.8;
    err += Math.pow(5 - s_early, 2) * 0.6;
  }
  return err;
}

export function calibrateCycleParams(userAnchors) {
  const anchors = Array.isArray(userAnchors) && userAnchors.length ? userAnchors : DEF_ANCHORS;
  // Grid search restreint (rapide et robuste dans le navigateur)
  const mRise = [8, 9, 10, 11, 12];
  const mFall = [26, 27, 28, 29, 30, 31];
  const kRise = [0.8, 0.9, 1.1, 1.3, 1.5];
  const kFall = [0.8, 0.9, 1.1, 1.3];
  const pPow = [0.85, 0.9, 1.0, 1.2, 1.35];
  let best = { params: { ...CYCLE_PARAMS }, score: Infinity };
  for (const r of mRise) {
    for (const f of mFall) {
      if (f - r < 10) continue; // évite un pic trop court
      for (const kr of kRise) {
        for (const kf of kFall) {
          for (const p of pPow) {
            const pset = { m_rise_center: r, m_fall_center: f, k_rise: kr, k_fall: kf, p_shape: p, floor: CYCLE_PARAMS.floor, ceil: CYCLE_PARAMS.ceil };
            const e = objective(pset, anchors);
            if (e < best.score) { best = { params: pset, score: e }; }
          }
        }
      }
    }
  }
  setCycleParams(best.params);
  return best; // { params, score }
}


/**
 * Estimate cycle position with confidence
 */
export function estimateCyclePosition() {
  const cycleData = getCurrentCycleMonths();
  const phase = getCyclePhase(cycleData.months);
  const score = cycleScoreFromMonths(cycleData.months);

  // Heuristic confidence based on phase typicality + calibration freshness
  // Uses existing data only (no new APIs). This mirrors the intelligence
  // demonstrated in the Risk Dashboard / Cycle Analysis without duplicating logic.
  let confidence = 0.0;
  try {
    const m = cycleData.months % 48;
    // Define phase centers and half-widths (months)
    const PHASE_WINDOWS = {
      accumulation: { center: 3, half: 3 },      // 0-6
      bull_build: { center: 12, half: 6 },       // 7-18
      peak: { center: 21, half: 3 },             // 19-24
      bear: { center: 30, half: 6 },             // 25-36
      pre_accumulation: { center: 42, half: 6 }  // 37-48
    };
    const key = phase?.phase || 'unknown';
    const win = PHASE_WINDOWS[key] || { center: 24, half: 8 };
    const dist = Math.abs(m - win.center);
    const norm = Math.min(1, win.half > 0 ? dist / win.half : 1);
    // Base confidence: higher when closer to phase center
    let base = 0.4 + 0.5 * (1 - norm); // 0.4..0.9

    // Calibration freshness bonus if params were calibrated within last 24h
    let calibBonus = 0;
    try {
      const saved = localStorage.getItem('bitcoin_cycle_params');
      if (saved) {
        const data = JSON.parse(saved);
        if (data?.timestamp && (Date.now() - data.timestamp) < 24 * 60 * 60 * 1000) {
          calibBonus = 0.05; // small bonus for fresh calibration
        }
      }
    } catch {}

    confidence = Math.max(0, Math.min(0.95, base + calibBonus));

    // Cap confidence by validated model precision if available (persisted by cycle-analysis.html)
    try {
      const stored = localStorage.getItem('cycle_model_precision');
      if (stored) {
        const prec = Math.max(0, Math.min(1, parseFloat(stored)));
        if (!Number.isNaN(prec) && prec > 0) {
          confidence = Math.min(confidence, prec);
        }
      }
    } catch {}
  } catch {
    confidence = 0.3; // conservative fallback
  }

  return {
    ...cycleData,
    phase,
    score,
    confidence,
    multipliers: cycleMultipliers(cycleData.months)
  };
}

/**
 * Validate cycle data
 */
export function validateCycleData(cycleData) {
  if (!cycleData || typeof cycleData !== 'object') {
    return false;
  }

  const { months, score, phase } = cycleData;

  if (typeof months !== 'number' || months < 0) {
    return false;
  }

  if (typeof score !== 'number' || score < 0 || score > 100) {
    return false;
  }

  if (!phase || typeof phase !== 'object') {
    return false;
  }

  return true;
}
