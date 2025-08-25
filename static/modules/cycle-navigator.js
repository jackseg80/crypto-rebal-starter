/**
 * Cycle Navigator - Bitcoin Halving Cycle Analysis
 * Computes cycle score and blends with CCS for enhanced targeting
 */

/**
 * Calculate cycle score based on months after halving
 * Bitcoin halving cycles: ~4 years (48 months)
 */
export function cycleScoreFromMonths(monthsAfterHalving) {
  if (typeof monthsAfterHalving !== 'number' || monthsAfterHalving < 0) {
    return 50; // Neutral if invalid
  }
  
  // Cycle phases (simplified model)
  // 0-6 months: Accumulation (40-60)
  // 6-18 months: Bull run building (60-90) 
  // 18-30 months: Peak euphoria (90-100 then decline to 40)
  // 30-48 months: Bear/consolidation (20-40)
  
  const m = monthsAfterHalving % 48; // Normalize to 48-month cycle
  
  if (m <= 6) {
    // Accumulation phase: gradual increase
    return 40 + (m / 6) * 20; // 40 → 60
  } else if (m <= 18) {
    // Bull build phase: strong increase
    return 60 + ((m - 6) / 12) * 30; // 60 → 90
  } else if (m <= 24) {
    // Peak phase: maximum then sharp decline
    const peakPosition = (m - 18) / 6; // 0 to 1
    return 100 - (peakPosition * 60); // 100 → 40
  } else if (m <= 36) {
    // Bear phase: continued decline
    return 40 - ((m - 24) / 12) * 20; // 40 → 20
  } else {
    // Late bear/pre-accumulation: gradual recovery
    return 20 + ((m - 36) / 12) * 20; // 20 → 40
  }
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
 * Get current months after halving (mock for MVP)
 * In production, this would calculate from actual halving dates
 */
export function getCurrentCycleMonths() {
  // Mock data for MVP - simulate we're ~18 months after last halving
  // You can adjust this for testing different phases
  const mockMonthsAfterHalving = 18 + Math.random() * 6; // 18-24 months (peak phase)
  
  return {
    months: mockMonthsAfterHalving,
    lastHalving: '2024-04-19', // Approximate last halving
    nextHalving: '2028-04-19', // Approximate next halving
    source: 'mock_calculation'
  };
}

/**
 * Estimate cycle position with confidence
 */
export function estimateCyclePosition() {
  const cycleData = getCurrentCycleMonths();
  const phase = getCyclePhase(cycleData.months);
  const score = cycleScoreFromMonths(cycleData.months);
  
  // Calculate confidence based on how "typical" this position is
  let confidence = 0.8; // Base confidence for mock data
  
  // In production, this would factor in:
  // - Data quality of halving dates
  // - Market correlation with historical cycles  
  // - External factors (regulations, macro environment)
  
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