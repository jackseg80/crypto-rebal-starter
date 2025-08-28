/**
 * Targets Coordinator - Strategic Target Management
 * Handles macro vs cycle vs blended targeting strategies
 */

import { store } from '../core/risk-dashboard-store.js';
import { interpretCCS } from './signals-engine.js';
import { getMarketRegime, applyMarketOverrides, calculateRiskBudget, allocateRiskyBudget, generateRegimeRecommendations } from './market-regimes.js';

// Default macro targets (baseline allocation)
export const DEFAULT_MACRO_TARGETS = {
  'BTC': 35.0,
  'ETH': 25.0,
  'Stablecoins': 20.0,
  'L1/L0 majors': 10.0,
  'L2/Scaling': 5.0,
  'DeFi': 3.0,
  'AI/Data': 2.0,
  'Others': 0.0,
  model_version: 'macro-1'
};

/**
 * Normalize targets to sum to 100%
 */
export function normalizeTargets(targets) {
  if (!targets || typeof targets !== 'object') {
    throw new Error('Invalid targets object');
  }
  
  // Separate model_version from numeric targets
  const { model_version, ...numericTargets } = targets;
  
  // Calculate total
  const total = Object.values(numericTargets).reduce((sum, val) => {
    return sum + (typeof val === 'number' ? val : 0);
  }, 0);
  
  if (total <= 0) {
    throw new Error('Total allocation must be positive');
  }
  
  // Normalize
  const normalized = {};
  Object.entries(numericTargets).forEach(([key, value]) => {
    normalized[key] = typeof value === 'number' ? (value / total) * 100 : 0;
  });
  
  // Add model version back
  normalized.model_version = model_version || 'unknown';
  
  return normalized;
}

/**
 * Apply cycle multipliers to macro targets
 */
export function applyCycleMultipliers(macroTargets, multipliers) {
  if (!macroTargets || !multipliers) {
    return macroTargets;
  }
  
  const { model_version, ...numericTargets } = macroTargets;
  const adjusted = {};
  
  Object.entries(numericTargets).forEach(([asset, allocation]) => {
    const multiplier = multipliers[asset] || 1.0;
    adjusted[asset] = allocation * multiplier;
  });
  
  // Normalize to 100%
  const normalized = normalizeTargets(adjusted);
  normalized.model_version = `${model_version}-cycle`;
  
  return normalized;
}

/**
 * Generate targets based on CCS score and strategy mode
 */
export function generateCCSTargets(ccsScore, mode = 'balanced') {
  if (typeof ccsScore !== 'number' || ccsScore < 0 || ccsScore > 100) {
    throw new Error('Invalid CCS score');
  }
  
  const interpretation = interpretCCS(ccsScore);
  let targets = { ...DEFAULT_MACRO_TARGETS };
  
  // Adjust based on CCS score
  switch (interpretation.level) {
    case 'very_high': // 80-100: Very Bullish
      targets.BTC = 40;
      targets.ETH = 30;
      targets.Stablecoins = 10;
      targets['L1/L0 majors'] = 12;
      targets['L2/Scaling'] = 6;
      targets.DeFi = 2;
      break;
      
    case 'high': // 65-79: Bullish
      targets.BTC = 38;
      targets.ETH = 28;
      targets.Stablecoins = 15;
      targets['L1/L0 majors'] = 11;
      targets['L2/Scaling'] = 5;
      targets.DeFi = 3;
      break;
      
    case 'medium': // 50-64: Neutral+
      targets = { ...DEFAULT_MACRO_TARGETS }; // Keep defaults
      break;
      
    case 'low': // 35-49: Neutral-
      targets.BTC = 30;
      targets.ETH = 20;
      targets.Stablecoins = 30;
      targets['L1/L0 majors'] = 8;
      targets['L2/Scaling'] = 4;
      targets.DeFi = 8;
      break;
      
    case 'very_low': // 0-34: Bearish
      targets.BTC = 25;
      targets.ETH = 15;
      targets.Stablecoins = 45;
      targets['L1/L0 majors'] = 5;
      targets['L2/Scaling'] = 3;
      targets.DeFi = 7;
      break;
  }
  
  targets.model_version = `ccs-${interpretation.level}`;
  return normalizeTargets(targets);
}

/**
 * Generate smart targets using market regime system
 */
export function generateSmartTargets() {
  const state = store.snapshot();
  const blendedScore = state.scores?.blended;
  const onchainScore = state.scores?.onchain;
  const riskScore = state.scores?.risk;
  
  console.log('🧠 Generating SMART targets with scores:', { blendedScore, onchainScore, riskScore });
  
  if (blendedScore == null) {
    console.warn('⚠️ Blended score not available for smart targets');
    return {
      targets: normalizeTargets(DEFAULT_MACRO_TARGETS),
      strategy: 'Macro fallback (no blended score)',
      mode: 'fallback',
      confidence: 0.3,
      timestamp: new Date().toISOString()
    };
  }
  
  try {
    // Get market regime
    const regime = getMarketRegime(blendedScore);
    const adjustedRegime = applyMarketOverrides(regime, onchainScore, riskScore);
    
    // Calculate risk budget
    const riskBudget = calculateRiskBudget(blendedScore, riskScore);
    
    // Allocate risky budget according to regime
    const smartAllocation = allocateRiskyBudget(riskBudget.percentages.risky, adjustedRegime);
    
    // Generate recommendations
    const recommendations = generateRegimeRecommendations(adjustedRegime, riskBudget);
    
    console.log('🧠 Smart allocation calculated:', smartAllocation);
    console.log('📊 Risk budget:', riskBudget.percentages);
    console.log('🎯 Regime:', adjustedRegime.name);
    
    const strategy = `${adjustedRegime.emoji} ${adjustedRegime.name} (${Math.round(blendedScore)}) | ${riskBudget.percentages.stables}% Stables`;
    
    return {
      targets: normalizeTargets(smartAllocation),
      strategy,
      mode: 'smart',
      regime: adjustedRegime,
      risk_budget: riskBudget,
      recommendations,
      confidence: adjustedRegime.confidence,
      timestamp: new Date().toISOString()
    };
    
  } catch (error) {
    console.error('❌ Error generating smart targets:', error);
    return {
      targets: normalizeTargets(DEFAULT_MACRO_TARGETS),
      strategy: 'Smart targeting failed - using macro fallback',
      mode: 'fallback',
      confidence: 0.2,
      error: error.message,
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * Main function to propose targets based on strategy mode
 */
export function proposeTargets(mode = 'blend', options = {}) {
  const state = store.snapshot();
  const ccsScore = state.ccs?.score;
  const cycleMultipliers = state.cycle?.multipliers;
  const cycleWeight = state.cycle?.weight || 0.3;
  const blendedCCS = state.cycle?.ccsStar;
  const finalBlendedScore = state.scores?.blended;
  
  let proposedTargets;
  let strategy;
  
  try {
    switch (mode) {
      case 'macro':
        proposedTargets = { ...DEFAULT_MACRO_TARGETS };
        strategy = 'Fixed macro allocation';
        break;
        
      case 'ccs':
        if (!ccsScore) {
          // Fallback : stratégie plus agressive (simule CCS élevé)
          proposedTargets = {
            'BTC': 45.0,
            'ETH': 30.0,
            'Stablecoins': 10.0,
            'L1/L0 majors': 8.0,
            'L2/Scaling': 4.0,
            'DeFi': 2.0,
            'AI/Data': 1.0,
            'Others': 0.0,
            model_version: 'ccs-fallback-aggressive'
          };
          strategy = 'CCS Aggressive (simulated)';
        } else {
          proposedTargets = generateCCSTargets(ccsScore);
          strategy = `CCS-based (${Math.round(ccsScore)})`;
        }
        break;
        
      case 'cycle':
        if (!cycleMultipliers) {
          // Fallback : stratégie cycle bear market (plus défensive)
          proposedTargets = {
            'BTC': 28.0,
            'ETH': 18.0,
            'Stablecoins': 40.0,
            'L1/L0 majors': 8.0,
            'L2/Scaling': 3.0,
            'DeFi': 2.5,
            'AI/Data': 0.5,
            'Others': 0.0,
            model_version: 'cycle-bear-fallback'
          };
          strategy = 'Cycle Bear Market (defensive)';
        } else {
          proposedTargets = applyCycleMultipliers(DEFAULT_MACRO_TARGETS, cycleMultipliers);
          strategy = `Cycle-adjusted (${state.cycle?.phase?.phase || 'unknown'})`;
        }
        break;
        
      case 'smart':
        // New intelligent allocation based on market regimes
        const smartResult = generateSmartTargets();
        proposedTargets = smartResult.targets;
        strategy = smartResult.strategy;
        break;
        
      case 'blend':
      default:
        // Use final blended score if available, fallback to blendedCCS
        const effectiveScore = finalBlendedScore || blendedCCS;
        
        // Deterministic priority logic
        if (!ccsScore || (!finalBlendedScore && !blendedCCS)) {
          // Fallback to balanced blend when no score data
          proposedTargets = {
            'BTC': 33.0,
            'ETH': 27.0,
            'Stablecoins': 22.0,
            'L1/L0 majors': 9.0,
            'L2/Scaling': 4.5,
            'DeFi': 3.5,
            'AI/Data': 1.0,
            'Others': 0.0,
            model_version: 'blend-fallback'
          };
          strategy = 'Balanced Blend (no scores available)';
        } else if (effectiveScore >= 70) {
          // High confidence: use blended CCS
          proposedTargets = generateCCSTargets(blendedCCS);
          if (cycleMultipliers) {
            proposedTargets = applyCycleMultipliers(proposedTargets, cycleMultipliers);
          }
          strategy = `High Score: Blended (${Math.round(effectiveScore)})`;
        } else {
          // Medium/low confidence: macro + light cycle adjustment
          proposedTargets = { ...DEFAULT_MACRO_TARGETS };
          if (cycleMultipliers) {
            // Apply diluted multipliers (50% strength)
            const dilutedMultipliers = {};
            Object.entries(cycleMultipliers).forEach(([asset, mult]) => {
              dilutedMultipliers[asset] = 1 + (mult - 1) * 0.5;
            });
            proposedTargets = applyCycleMultipliers(proposedTargets, dilutedMultipliers);
          }
          strategy = `Conservative: Blended (${Math.round(effectiveScore)})`;
        }
        break;
    }
    
    // DEBUG: Log before normalization
    console.log('🔍 DEBUG proposeTargets - before normalization BTC:', proposedTargets.BTC);
    
    // Final normalization
    proposedTargets = normalizeTargets(proposedTargets);
    
    // DEBUG: Log after normalization
    console.log('🔍 DEBUG proposeTargets - after normalization BTC:', proposedTargets.BTC);
    
    return {
      targets: proposedTargets,
      strategy,
      mode,
      confidence: ccsScore && blendedCCS ? Math.min(1.0, blendedCCS / 100) : 0.5,
      timestamp: new Date().toISOString()
    };
    
  } catch (error) {
    console.error('Failed to propose targets:', error);
    
    // Safe fallback
    return {
      targets: normalizeTargets(DEFAULT_MACRO_TARGETS),
      strategy: 'Safe fallback (error occurred)',
      mode: 'fallback',
      confidence: 0.3,
      timestamp: new Date().toISOString(),
      error: error.message
    };
  }
}

/**
 * Compute rebalancing plan (simplified version)
 * In production, this would integrate with the actual rebalancing logic
 */
export function computePlan(currentAllocations, targetAllocations) {
  if (!currentAllocations || !targetAllocations) {
    throw new Error('Current and target allocations required');
  }
  
  const actions = [];
  let totalToReallocate = 0;
  
  // Calculate differences
  const allAssets = new Set([
    ...Object.keys(currentAllocations),
    ...Object.keys(targetAllocations)
  ]);
  
  allAssets.forEach(asset => {
    if (asset === 'model_version') return;
    
    const current = currentAllocations[asset] || 0;
    const target = targetAllocations[asset] || 0;
    const diff = target - current;
    
    if (Math.abs(diff) > 0.1) { // Only significant changes
      const action = {
        asset,
        current_pct: current,
        target_pct: target,
        change_pct: diff,
        action: diff > 0 ? 'buy' : 'sell',
        priority: Math.abs(diff) > 5 ? 'high' : 'medium'
      };
      
      actions.push(action);
      totalToReallocate += Math.abs(diff);
    }
  });
  
  // Sort by largest changes first
  actions.sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct));
  
  return {
    actions,
    total_reallocation: totalToReallocate,
    num_changes: actions.length,
    complexity: actions.length > 5 ? 'high' : actions.length > 2 ? 'medium' : 'low'
  };
}

/**
 * Apply targets to store and trigger events
 */
export async function applyTargets(proposalResult) {
  if (!proposalResult || !proposalResult.targets) {
    throw new Error('Invalid proposal result');
  }
  
  try {
    // DEBUG: Log what we're about to save
    console.log('🔍 DEBUG applyTargets - proposalResult.targets:', proposalResult.targets);
    console.log('🔍 DEBUG applyTargets - BTC allocation:', proposalResult.targets.BTC);
    
    // Update store with new targets (normalized version for display)
    store.set('targets.proposed', proposalResult.targets);
    store.set('targets.strategy', proposalResult.strategy);
    store.set('targets.confidence', proposalResult.confidence);
    store.set('targets.model_version', proposalResult.targets.model_version);
    
    // Log decision for audit trail
    const decisionEntry = {
      timestamp: new Date().toISOString(),
      mode: proposalResult.mode,
      strategy: proposalResult.strategy,
      targets: proposalResult.targets,
      confidence: proposalResult.confidence,
      ccs_score: store.get('ccs.score'),
      cycle_months: store.get('cycle.months'),
      blended_ccs: store.get('cycle.ccsStar')
    };
    
    // Save to decision log (localStorage)
    appendToDecisionLog(decisionEntry);
    
    // Save to last_targets for rebalance.html communication
    const dataToSave = {
      targets: proposalResult.targets,
      timestamp: decisionEntry.timestamp,
      strategy: proposalResult.strategy,
      source: 'risk-dashboard-ccs'
    };
    
    console.log('🔍 DEBUG applyTargets - Full proposal result:', proposalResult);
    console.log('🔍 DEBUG applyTargets - Targets being saved:', proposalResult.targets);
    console.log('🔍 DEBUG applyTargets - BTC before save:', dataToSave.targets.BTC);
    console.log('🔍 DEBUG applyTargets - ETH before save:', dataToSave.targets.ETH);
    localStorage.setItem('last_targets', JSON.stringify(dataToSave));
    
    // Verify what was actually saved
    const savedData = JSON.parse(localStorage.getItem('last_targets'));
    console.log('🔍 DEBUG applyTargets - BTC after save:', savedData.targets.BTC);
    console.log('🔍 DEBUG applyTargets - ETH after save:', savedData.targets.ETH);
    
    // Dispatch event for external listeners (rebalance.html)
    window.dispatchEvent(new CustomEvent('targetsUpdated', {
      detail: {
        targets: proposalResult.targets,
        strategy: proposalResult.strategy,
        source: 'ccs-integration'
      }
    }));
    
    console.log('Targets applied successfully:', proposalResult.strategy);
    return true;
    
  } catch (error) {
    console.error('Failed to apply targets:', error);
    throw error;
  }
}

/**
 * Append to decision log (JSON Lines format in localStorage)
 */
function appendToDecisionLog(entry) {
  const logKey = 'ccs-decision-log';
  const maxEntries = 100;
  
  try {
    const existingLog = localStorage.getItem(logKey);
    const entries = existingLog ? JSON.parse(existingLog) : [];
    
    entries.push(entry);
    
    // Keep only last maxEntries
    if (entries.length > maxEntries) {
      entries.splice(0, entries.length - maxEntries);
    }
    
    localStorage.setItem(logKey, JSON.stringify(entries));
    
  } catch (error) {
    console.warn('Failed to append to decision log:', error);
  }
}

/**
 * Get decision log history
 */
export function getDecisionLog(limit = 20) {
  try {
    const log = localStorage.getItem('ccs-decision-log');
    const entries = log ? JSON.parse(log) : [];
    return entries.slice(-limit).reverse(); // Most recent first
  } catch (error) {
    console.warn('Failed to read decision log:', error);
    return [];
  }
}

/**
 * Trading Rules Configuration
 */
export const TRADING_RULES = {
  min_change_threshold: 3.0,        // Minimum % change to trigger trade
  min_relative_change: 0.2,         // Minimum 20% relative change
  min_order_size_usd: 200,          // Minimum order size in USD
  max_single_trade_pct: 10,         // Max 10% of portfolio in single trade
  drawdown_circuit_breaker: -0.25,  // Stop if DD > 25%
  risk_circuit_breaker: 45,         // Force stables if onchain < 45
  correlation_threshold: 0.8,       // Reduce alts if correlation > 80%
  rebalance_frequency_hours: 168    // Weekly rebalancing (168h = 7 days)
};

/**
 * Validate if rebalancing should occur based on operational rules
 */
export function validateRebalancing(currentTargets, proposedTargets, options = {}) {
  const validation = {
    valid: true,
    changes: [],
    warnings: [],
    blocked_reasons: [],
    recommendations: []
  };

  if (!currentTargets || !proposedTargets) {
    validation.valid = false;
    validation.blocked_reasons.push('Missing allocation data');
    return validation;
  }

  const { model_version: currentVersion, ...currentAlloc } = currentTargets;
  const { model_version: proposedVersion, ...proposedAlloc } = proposedTargets;

  // Calculate changes for each asset
  const allAssets = new Set([...Object.keys(currentAlloc), ...Object.keys(proposedAlloc)]);
  
  allAssets.forEach(asset => {
    const current = currentAlloc[asset] || 0;
    const proposed = proposedAlloc[asset] || 0;
    const absoluteChange = Math.abs(proposed - current);
    const relativeChange = current > 0 ? absoluteChange / current : (proposed > 0 ? 1 : 0);

    if (absoluteChange > TRADING_RULES.min_change_threshold) {
      validation.changes.push({
        asset,
        current: current.toFixed(2),
        proposed: proposed.toFixed(2),
        absolute_change: absoluteChange.toFixed(2),
        relative_change: (relativeChange * 100).toFixed(1) + '%',
        action: proposed > current ? 'buy' : 'sell',
        priority: absoluteChange > 5 ? 'high' : 'medium'
      });
    }
  });

  // Rule 1: Minimum change threshold
  const significantChanges = validation.changes.filter(change => 
    parseFloat(change.absolute_change) >= TRADING_RULES.min_change_threshold ||
    parseFloat(change.relative_change) >= TRADING_RULES.min_relative_change * 100
  );

  if (significantChanges.length === 0) {
    validation.valid = false;
    validation.blocked_reasons.push(`No significant changes (min ${TRADING_RULES.min_change_threshold}% or ${TRADING_RULES.min_relative_change * 100}% relative)`);
  }

  // Rule 2: Circuit breakers
  if (options.onchainScore != null && options.onchainScore < TRADING_RULES.risk_circuit_breaker) {
    const stablesTarget = proposedAlloc.Stablecoins || 0;
    if (stablesTarget < 40) {
      validation.warnings.push({
        type: 'risk_circuit_breaker',
        message: `On-chain score very low (${options.onchainScore}), recommend min 40% stables`,
        current_stables: stablesTarget
      });
    }
  }

  // Rule 3: Drawdown circuit breaker
  if (options.drawdown != null && options.drawdown < TRADING_RULES.drawdown_circuit_breaker) {
    const stablesTarget = proposedAlloc.Stablecoins || 0;
    if (stablesTarget < 40) {
      validation.valid = false;
      validation.blocked_reasons.push(`Drawdown circuit breaker triggered (${Math.round(options.drawdown * 100)}%), forcing min 40% stables`);
    }
  }

  // Rule 4: Order size validation (requires portfolio value)
  if (options.portfolioValueUSD) {
    validation.changes.forEach(change => {
      const orderValueUSD = (parseFloat(change.absolute_change) / 100) * options.portfolioValueUSD;
      if (orderValueUSD < TRADING_RULES.min_order_size_usd) {
        change.skip_reason = `Order too small ($${orderValueUSD.toFixed(0)} < $${TRADING_RULES.min_order_size_usd})`;
      }
    });
  }

  // Rule 5: Frequency check
  if (options.lastRebalanceTime) {
    const hoursSinceLastRebalance = (Date.now() - options.lastRebalanceTime) / (1000 * 60 * 60);
    if (hoursSinceLastRebalance < TRADING_RULES.rebalance_frequency_hours) {
      const hoursRemaining = TRADING_RULES.rebalance_frequency_hours - hoursSinceLastRebalance;
      validation.warnings.push({
        type: 'frequency_warning',
        message: `Last rebalance was ${Math.round(hoursSinceLastRebalance)}h ago, recommended frequency: ${TRADING_RULES.rebalance_frequency_hours}h`,
        hours_remaining: Math.round(hoursRemaining)
      });
    }
  }

  // Generate recommendations
  if (validation.changes.length > 5) {
    validation.recommendations.push({
      type: 'complexity_warning',
      message: `${validation.changes.length} changes detected - consider phased execution`,
      suggestion: 'Execute high-priority changes first, defer medium-priority ones'
    });
  }

  const totalTradingVolume = validation.changes.reduce((sum, change) => 
    sum + parseFloat(change.absolute_change), 0
  );

  if (totalTradingVolume > 20) {
    validation.recommendations.push({
      type: 'volume_warning', 
      message: `High trading volume: ${totalTradingVolume.toFixed(1)}% of portfolio`,
      suggestion: 'Consider splitting into multiple smaller rebalances'
    });
  }

  return validation;
}

/**
 * Generate execution plan based on validation
 */
export function generateExecutionPlan(validationResult, options = {}) {
  if (!validationResult.valid) {
    return {
      executable: false,
      blocked_reasons: validationResult.blocked_reasons,
      total_changes: 0
    };
  }

  const plan = {
    executable: true,
    phases: [],
    total_changes: validationResult.changes.length,
    estimated_duration: '5-15 minutes',
    gas_estimation: 'Medium'
  };

  // Phase 1: High priority changes
  const highPriorityChanges = validationResult.changes.filter(change => 
    change.priority === 'high' && !change.skip_reason
  );

  if (highPriorityChanges.length > 0) {
    plan.phases.push({
      phase: 1,
      name: 'High Priority Changes',
      changes: highPriorityChanges,
      execute_immediately: true
    });
  }

  // Phase 2: Medium priority changes
  const mediumPriorityChanges = validationResult.changes.filter(change => 
    change.priority === 'medium' && !change.skip_reason
  );

  if (mediumPriorityChanges.length > 0) {
    plan.phases.push({
      phase: 2,
      name: 'Medium Priority Changes',
      changes: mediumPriorityChanges,
      execute_immediately: highPriorityChanges.length <= 3
    });
  }

  // Phase 3: Skipped changes (for info)
  const skippedChanges = validationResult.changes.filter(change => change.skip_reason);
  if (skippedChanges.length > 0) {
    plan.phases.push({
      phase: 3,
      name: 'Skipped (Small Orders)',
      changes: skippedChanges,
      execute_immediately: false
    });
  }

  return plan;
}

/**
 * Validate targets object
 */
export function validateTargets(targets) {
  if (!targets || typeof targets !== 'object') {
    return { valid: false, error: 'Invalid targets object' };
  }
  
  const { model_version, ...numericTargets } = targets;
  
  // Check all values are numbers
  for (const [key, value] of Object.entries(numericTargets)) {
    if (typeof value !== 'number' || value < 0 || value > 100) {
      return { valid: false, error: `Invalid allocation for ${key}: ${value}` };
    }
  }
  
  // Check total is reasonable (should be close to 100 after normalization)
  const total = Object.values(numericTargets).reduce((sum, val) => sum + val, 0);
  if (total < 50 || total > 150) {
    return { valid: false, error: `Unreasonable total allocation: ${total}%` };
  }
  
  return { valid: true };
}