/**
 * Targets Coordinator - Strategic Target Management
 * Handles macro vs cycle vs blended targeting strategies
 */

import { store } from '../core/risk-dashboard-store.js';
import { interpretCCS } from './signals-engine.js';
import { getMarketRegime, applyMarketOverrides, calculateRiskBudget, allocateRiskyBudget, generateRegimeRecommendations } from './market-regimes.js';

// All asset groups (ensures consistent 11-group taxonomy)
const ALL_ASSET_GROUPS = ['BTC', 'ETH', 'Stablecoins', 'SOL', 'L1/L0 majors', 'L2/Scaling', 'DeFi', 'AI/Data', 'Gaming/NFT', 'Memecoins', 'Others'];

// Default macro targets (baseline allocation) - TOUS les 11 groupes
export const DEFAULT_MACRO_TARGETS = {
  'BTC': 35.0,
  'ETH': 25.0,
  'Stablecoins': 20.0,
  'SOL': 5.0,
  'L1/L0 majors': 7.0,
  'L2/Scaling': 4.0,
  'DeFi': 2.0,
  'AI/Data': 1.5,
  'Gaming/NFT': 0.5,
  'Memecoins': 0.0,    // Explicitement 0% mais présent
  'Others': 0.0,       // Explicitement 0% mais présent
  model_version: 'macro-2'
};

/**
 * Ensure all 11 asset groups are present in targets (with 0% if missing)
 */
function ensureAllGroups(targets) {
  const result = { ...targets };
  
  ALL_ASSET_GROUPS.forEach(group => {
    if (!(group in result)) {
      result[group] = 0.0;
    }
  });
  
  return result;
}

/**
 * Normalize targets to sum to 100%
 */
export function normalizeTargets(targets) {
  if (!targets || typeof targets !== 'object') {
    throw new Error('Invalid targets object');
  }
  
  // Ensure all groups are present first
  const completeTargets = ensureAllGroups(targets);
  
  // Separate model_version from numeric targets
  const { model_version, ...numericTargets } = completeTargets;
  
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
  // Start with all groups at 0
  let targets = {};
  ALL_ASSET_GROUPS.forEach(group => {
    targets[group] = 0.0;
  });
  
  // Adjust based on CCS score
  switch (interpretation.level) {
    case 'very_high': // 80-100: Very Bullish
      targets.BTC = 40;
      targets.ETH = 30;
      targets.Stablecoins = 10;
      targets.SOL = 8;
      targets['L1/L0 majors'] = 7;
      targets['L2/Scaling'] = 3;
      targets.DeFi = 1;
      targets['AI/Data'] = 0.5;
      targets['Gaming/NFT'] = 0.5;
      targets.Memecoins = 0;
      targets.Others = 0;
      break;
      
    case 'high': // 65-79: Bullish
      targets.BTC = 38;
      targets.ETH = 28;
      targets.Stablecoins = 15;
      targets.SOL = 7;
      targets['L1/L0 majors'] = 6;
      targets['L2/Scaling'] = 3;
      targets.DeFi = 2;
      targets['AI/Data'] = 0.5;
      targets['Gaming/NFT'] = 0.5;
      targets.Memecoins = 0;
      targets.Others = 0;
      break;
      
    case 'medium': // 50-64: Neutral+
      // Use defaults but ensure all groups present
      Object.assign(targets, DEFAULT_MACRO_TARGETS);
      break;
      
    case 'low': // 35-49: Neutral-
      targets.BTC = 30;
      targets.ETH = 20;
      targets.Stablecoins = 30;
      targets.SOL = 4;
      targets['L1/L0 majors'] = 6;
      targets['L2/Scaling'] = 3;
      targets.DeFi = 5;
      targets['AI/Data'] = 1.5;
      targets['Gaming/NFT'] = 0.5;
      targets.Memecoins = 0;
      targets.Others = 0;
      break;
      
    case 'very_low': // 0-34: Bearish
      targets.BTC = 25;
      targets.ETH = 15;
      targets.Stablecoins = 45;
      targets.SOL = 3;
      targets['L1/L0 majors'] = 4;
      targets['L2/Scaling'] = 2;
      targets.DeFi = 5;
      targets['AI/Data'] = 1;
      targets['Gaming/NFT'] = 0;
      targets.Memecoins = 0;
      targets.Others = 0;
      break;
  }
  
  targets.model_version = `ccs-${interpretation.level}`;
  return normalizeTargets(targets);
}

/**
 * Apply on-chain intelligence to refine market regime assessment
 */
function applyOnChainIntelligence(baseRegime, onchainMetadata) {
  const { categoryBreakdown, criticalZoneCount, totalIndicators, activeCategories } = onchainMetadata;
  
  let adjustedRegime = { ...baseRegime };
  let adjustments = [];
  
  // Critical zone analysis - force defensive if too many critical indicators
  if (criticalZoneCount > 0) {
    const criticalRatio = criticalZoneCount / totalIndicators;
    
    if (criticalRatio > 0.3) { // Plus de 30% en zone critique
      adjustments.push('🚨 Zone critique détectée');
      
      // Force defensive allocation
      adjustedRegime.risk_tolerance = Math.min(adjustedRegime.risk_tolerance, 0.4);
      adjustedRegime.name += ' (Crit)';
      adjustedRegime.description += ` ${criticalZoneCount}/${totalIndicators} indicateurs en zone critique.`;
    }
  }
  
  // Category-specific intelligence
  if (categoryBreakdown) {
    // On-chain fundamentals dominance
    if (categoryBreakdown.onchain_fundamentals) {
      const onchainScore = categoryBreakdown.onchain_fundamentals.score;
      
      if (onchainScore < 30) { // Fondamentaux très bullish (scores inversés)
        adjustments.push('🔗 Fondamentaux bullish');
        adjustedRegime.confidence += 0.1;
        
      } else if (onchainScore > 70) { // Fondamentaux très bearish
        adjustments.push('🔗 Fondamentaux bearish');
        adjustedRegime.risk_tolerance *= 0.8; // Réduire le risque
      }
    }
    
    // Cycle/Technical signals
    if (categoryBreakdown.cycle_technical) {
      const cycleScore = categoryBreakdown.cycle_technical.score;
      
      if (cycleScore > 75) { // Signaux de cycle bearish
        adjustments.push('📊 Signaux de top');
        adjustedRegime.risk_tolerance *= 0.7; // Très défensif
        
      } else if (cycleScore < 25) { // Signaux de cycle bullish  
        adjustments.push('📊 Signaux de bottom');
        adjustedRegime.confidence += 0.15;
      }
    }
    
    // Sentiment extremes
    if (categoryBreakdown.sentiment) {
      const sentimentScore = categoryBreakdown.sentiment.score;
      
      if (sentimentScore > 80) { // Fear extreme = contrarian bullish
        adjustments.push('😨 Fear extrême');
        adjustedRegime.confidence += 0.05;
        
      } else if (sentimentScore < 20) { // Greed extreme = bearish
        adjustments.push('🤑 Greed extrême');
        adjustedRegime.risk_tolerance *= 0.9;
      }
    }
  }
  
  // Log des ajustements appliqués
  if (adjustments.length > 0) {
    console.debug('🧠 On-chain intelligence adjustments:', adjustments.join(', '));
  }
  
  return adjustedRegime;
}

/**
 * Generate smart targets using market regime system with enhanced on-chain intelligence
 */
export function generateSmartTargets() {
  const state = store.snapshot();
  const blendedScore = state.scores?.blended;
  const onchainScore = state.scores?.onchain;
  const riskScore = state.scores?.risk;
  const onchainMetadata = state.scores?.onchain_metadata;
  const backendSignals = state.governance?.ml_signals || null;
  const backendStatus = state.ui?.apiStatus?.backend || 'unknown';
  
  console.debug('🧠 Generating SMART targets with scores:', { 
    blendedScore, 
    onchainScore, 
    riskScore,
    criticalCount: onchainMetadata?.criticalZoneCount
  });
  
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
    let adjustedRegime = applyMarketOverrides(regime, onchainScore, riskScore);
    
    // Apply enhanced on-chain intelligence if available
    if (onchainMetadata) {
      adjustedRegime = applyOnChainIntelligence(adjustedRegime, onchainMetadata);
    }
    
    // Calculate risk budget (context)
    const riskBudget = calculateRiskBudget(blendedScore, riskScore);

    // Backend-driven exposure cap (Decision Engine)
    let exposureCap = null;
    let exposureSource = 'fallback';
    try {
      if (backendSignals && typeof backendSignals.decision_score === 'number') {
        const ds = backendSignals.decision_score;           // 0..1
        const dc = Math.max(0, Math.min(1, backendSignals.confidence ?? 0.5));
        const volVals = backendSignals.volatility ? Object.values(backendSignals.volatility).filter(v => typeof v === 'number') : [];
        const avgVol = volVals.length ? (volVals.reduce((a, b) => a + b, 0) / volVals.length) : 0.0; // decimal (e.g., 0.25)
        const raw = ds * dc;
        // Base cap tiers
        let cap = (raw >= 0.8 && blendedScore >= 70) ? 85 : (raw >= 0.65 ? 70 : 55);
        // Volatility adjustment: downscale if vol high (>20%)
        const volPenalty = Math.max(0, Math.round((avgVol - 0.20) * 100)); // e.g., 0.30 -> 10
        cap = Math.max(30, Math.min(95, cap - Math.min(15, volPenalty)));
        exposureCap = cap; // percent of portfolio risky max
        exposureSource = 'backend';
      }
    } catch {}

    // Final risky budget after cap and backend fallback
    const baseRisky = riskBudget.percentages.risky; // % risky suggested by regime/risk
    let finalRisky = (typeof exposureCap === 'number') ? Math.min(baseRisky, exposureCap) : baseRisky;
    // If backend is down, enforce a prudent fallback cap (5%)
    if (backendStatus === 'error') {
      finalRisky = Math.min(finalRisky, 5);
    } else if (backendStatus === 'stale') {
      // If signals are stale, enforce a conservative cap (8%)
      finalRisky = Math.min(finalRisky, 8);
    }

    // Allocate risky budget according to regime with finalRisky
    const smartAllocation = allocateRiskyBudget(finalRisky, adjustedRegime);
    
    // Generate recommendations
    const recommendations = generateRegimeRecommendations(adjustedRegime, riskBudget);
    
    console.debug('🧠 Smart allocation calculated:', smartAllocation);
    console.debug('📊 Risk budget:', riskBudget.percentages);
    console.debug('🎯 Regime:', adjustedRegime.name);
    
    const strategy = `${adjustedRegime.emoji} ${adjustedRegime.name} (${Math.round(blendedScore)}) | ${Math.round(100 - finalRisky)}% Stables${exposureCap != null ? ` | Cap ${exposureCap}% (Decision Engine)` : ''}`;
    
    return {
      targets: normalizeTargets(smartAllocation),
      strategy,
      mode: 'smart',
      regime: adjustedRegime,
      risk_budget: riskBudget,
      recommendations,
      confidence: adjustedRegime.confidence,
      base_risky: baseRisky,
      final_risky: finalRisky,
      exposure_cap: exposureCap,
      exposure_source: exposureSource,
      backend_status: backendStatus,
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
          proposedTargets = {};
          ALL_ASSET_GROUPS.forEach(group => {
            proposedTargets[group] = 0.0;
          });
          proposedTargets.BTC = 45.0;
          proposedTargets.ETH = 30.0;
          proposedTargets.Stablecoins = 10.0;
          proposedTargets.SOL = 6.0;
          proposedTargets['L1/L0 majors'] = 5.0;
          proposedTargets['L2/Scaling'] = 2.5;
          proposedTargets.DeFi = 1.0;
          proposedTargets['AI/Data'] = 0.5;
          proposedTargets['Gaming/NFT'] = 0.0;
          proposedTargets.Memecoins = 0.0;
          proposedTargets.Others = 0.0;
          proposedTargets.model_version = 'ccs-fallback-aggressive';
          strategy = 'CCS Aggressive (simulated)';
        } else {
          proposedTargets = generateCCSTargets(ccsScore);
          strategy = `CCS-based (${Math.round(ccsScore)})`;
        }
        break;
        
      case 'cycle':
        if (!cycleMultipliers) {
          // Fallback : stratégie cycle bear market (plus défensive)
          proposedTargets = {};
          ALL_ASSET_GROUPS.forEach(group => {
            proposedTargets[group] = 0.0;
          });
          proposedTargets.BTC = 28.0;
          proposedTargets.ETH = 18.0;
          proposedTargets.Stablecoins = 40.0;
          proposedTargets.SOL = 4.0;
          proposedTargets['L1/L0 majors'] = 5.0;
          proposedTargets['L2/Scaling'] = 2.5;
          proposedTargets.DeFi = 2.0;
          proposedTargets['AI/Data'] = 0.5;
          proposedTargets['Gaming/NFT'] = 0.0;
          proposedTargets.Memecoins = 0.0;
          proposedTargets.Others = 0.0;
          proposedTargets.model_version = 'cycle-bear-fallback';
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
          proposedTargets = {};
          ALL_ASSET_GROUPS.forEach(group => {
            proposedTargets[group] = 0.0;
          });
          proposedTargets.BTC = 33.0;
          proposedTargets.ETH = 27.0;
          proposedTargets.Stablecoins = 22.0;
          proposedTargets.SOL = 5.0;
          proposedTargets['L1/L0 majors'] = 6.5;
          proposedTargets['L2/Scaling'] = 3.5;
          proposedTargets.DeFi = 2.5;
          proposedTargets['AI/Data'] = 0.5;
          proposedTargets['Gaming/NFT'] = 0.0;
          proposedTargets.Memecoins = 0.0;
          proposedTargets.Others = 0.0;
          proposedTargets.model_version = 'blend-fallback';
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
    console.debug('🔍 DEBUG proposeTargets - before normalization BTC:', proposedTargets.BTC);
    
    // Final normalization
    proposedTargets = normalizeTargets(proposedTargets);
    
    // DEBUG: Log after normalization
    console.debug('🔍 DEBUG proposeTargets - after normalization BTC:', proposedTargets.BTC);
    
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
    console.debug('🔍 DEBUG applyTargets - proposalResult.targets:', proposalResult.targets);
    console.debug('🔍 DEBUG applyTargets - BTC allocation:', proposalResult.targets.BTC);
    
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
    
    console.debug('🔍 DEBUG applyTargets - Full proposal result:', proposalResult);
    console.debug('🔍 DEBUG applyTargets - Targets being saved:', proposalResult.targets);
    console.debug('🔍 DEBUG applyTargets - BTC before save:', dataToSave.targets.BTC);
    console.debug('🔍 DEBUG applyTargets - ETH before save:', dataToSave.targets.ETH);
    localStorage.setItem('last_targets', JSON.stringify(dataToSave));
    
    // Verify what was actually saved
    const savedData = JSON.parse(localStorage.getItem('last_targets'));
    console.debug('🔍 DEBUG applyTargets - BTC after save:', savedData.targets.BTC);
    console.debug('🔍 DEBUG applyTargets - ETH after save:', savedData.targets.ETH);
    
    // Dispatch event for external listeners (rebalance.html)
    window.dispatchEvent(new CustomEvent('targetsUpdated', {
      detail: {
        targets: proposalResult.targets,
        strategy: proposalResult.strategy,
        source: 'ccs-integration'
      }
    }));
    
    console.debug('Targets applied successfully:', proposalResult.strategy);
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
