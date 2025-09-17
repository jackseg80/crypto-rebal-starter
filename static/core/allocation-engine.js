// Allocation Engine V2 - Descente hiérarchique avec Feature Flag
// Macro → Secteurs → Coins avec floors contextuels et incumbency protection

import { getAssetGroup, UNIFIED_ASSET_GROUPS, GROUP_ORDER, loadTaxonomyDataSync } from '../shared-asset-groups.js';

// Feature flag pour activation
const ALLOCATION_ENGINE_V2 = true; // Will be controlled by config later

// Configuration des floors contextuels
const FLOORS_CONFIG = {
  // Floors de base par secteur
  base: {
    'BTC': 0.15,      // 15% minimum
    'ETH': 0.12,      // 12% minimum
    'Stablecoins': 0.10, // 10% minimum sécurité
    'SOL': 0.03,      // 3% minimum
    'L1/L0 majors': 0.08, // 8% minimum pour diversification
    'L2/Scaling': 0.03,
    'DeFi': 0.04,
    'Memecoins': 0.02,
    'Gaming/NFT': 0.01,
    'AI/Data': 0.01,
    'Others': 0.01
  },

  // Floors renforcés quand Cycle ≥ 90 (bull market)
  bullish: {
    'SOL': 0.06,
    'L1/L0 majors': 0.12,
    'L2/Scaling': 0.06,
    'DeFi': 0.08,
    'Memecoins': 0.05, // Permis en bull
    'Gaming/NFT': 0.02,
    'AI/Data': 0.02
  },

  // Incumbency: positions détenues ne peuvent pas aller à 0%
  incumbency: 0.03 // 3% minimum pour assets détenus
};

/**
 * Moteur d'allocation hiérarchique V2
 * @param {Object} context - Contexte unifié (scores, adaptive weights, etc.)
 * @param {Array} currentPositions - Positions actuelles du portefeuille
 * @param {Object} options - Options (feature flags, constraints)
 */
export async function calculateHierarchicalAllocation(context, currentPositions = [], options = {}) {
  const enableV2 = options.enableV2 ?? ALLOCATION_ENGINE_V2;

  console.debug('🏗️ Allocation Engine called:', { enableV2, contextualScores: !!context.adaptiveWeights });

  if (!enableV2) {
    console.debug('⚠️ Allocation Engine V2 disabled, using fallback');
    return null; // Fallback vers V1
  }

  try {
    // Ensure taxonomy data is loaded before proceeding
    try {
      loadTaxonomyDataSync(); // Fonction synchrone, pas d'await
      console.debug('✅ Taxonomy data loaded for allocation engine');
    } catch (taxonomyError) {
      console.warn('⚠️ Taxonomy loading failed, continuing with fallback:', taxonomyError.message);
      // Continue quand même, getAssetGroup aura ses fallbacks
    }
    // 1. EXTRACTION DU CONTEXTE
    const {
      cycleScore = 50,
      onchainScore = 50,
      riskScore = 50,
      adaptiveWeights = {},
      risk_budget = {},
      contradiction = 0
    } = context;

    // 2. DÉTECTION PHASE MARCHÉ
    const isBullishPhase = cycleScore >= 90;
    const isModeratePhase = cycleScore >= 70 && cycleScore < 90;
    const selectedFloors = isBullishPhase ? { ...FLOORS_CONFIG.base, ...FLOORS_CONFIG.bullish } : FLOORS_CONFIG.base;

    console.debug('📊 Market phase detection:', { cycleScore, isBullishPhase, isModeratePhase });

    // 3. ALLOCATION NIVEAU 1 - MACRO
    const macroAllocation = calculateMacroAllocation(context, selectedFloors);
    console.debug('🌍 Macro allocation:', macroAllocation);

    // 4. ALLOCATION NIVEAU 2 - SECTEURS
    const sectorAllocation = calculateSectorAllocation(macroAllocation, selectedFloors, isBullishPhase);
    console.debug('🏭 Sector allocation:', sectorAllocation);

    // 5. ALLOCATION NIVEAU 3 - COINS (Incumbency Protection)
    const coinAllocation = calculateCoinAllocation(sectorAllocation, currentPositions, selectedFloors);
    console.debug('🪙 Coin allocation:', coinAllocation);

    // 6. CALCUL ITERATIONS ESTIMÉES
    const executionPlan = calculateExecutionPlan(coinAllocation, currentPositions, context.execution);

    // 7. VALIDATION FINALE + CHECKSUM + CONTRÔLES
    const totalCheck = validateTotalAllocation(coinAllocation);
    const allocationEntries = Object.entries(coinAllocation);

    // CONTRÔLES HIÉRARCHIQUES
    const hierarchyCheck = validateHierarchy(coinAllocation, currentPositions);
    console.debug('🔍 Hierarchy validation:', hierarchyCheck);

    // GUARD: target_sum_mismatch
    const targetSum = Object.values(coinAllocation).reduce((sum, val) =>
      sum + (typeof val === 'number' && !isNaN(val) ? val : 0), 0
    );
    if (Math.abs(targetSum - 1.0) > 0.01) {
      console.warn(`⚠️ target_sum_mismatch: somme secteurs = ${(targetSum * 100).toFixed(1)}% (≠ 100%)`);
    }

    // CHECKSUM DÉTAILLÉ
    console.debug('💯 CHECKSUM:', {
      total_allocation: totalCheck.total,
      entries_count: allocationEntries.length,
      valid_entries: allocationEntries.filter(([k, v]) => v > 0.001).length,
      is_normalized: totalCheck.isValid,
      hierarchy_ok: hierarchyCheck.valid,
      target_sum_ok: Math.abs(targetSum - 1.0) <= 0.01,
      allocation_breakdown: Object.fromEntries(
        allocationEntries
          .filter(([k, v]) => v > 0.001)
          .map(([k, v]) => [k, `${(v * 100).toFixed(1)}%`])
      )
    });

    if (!totalCheck.isValid) {
      console.error('❌ Invalid allocation total:', totalCheck.total);
      // Normaliser l'allocation si nécessaire
      const scale = 1 / totalCheck.total;
      Object.keys(coinAllocation).forEach(key => {
        coinAllocation[key] *= scale;
      });
      console.warn('⚠️ Allocation normalized to sum to 1.0');
    }

    // 8. LOGS POUR DEBUG
    logAllocationDecisions({
      context,
      macro: macroAllocation,
      sectors: sectorAllocation,
      coins: coinAllocation,
      execution: executionPlan
    });

    const result = {
      version: 'v2',
      allocation: coinAllocation,
      execution: executionPlan,
      metadata: {
        phase: isBullishPhase ? 'bullish' : isModeratePhase ? 'moderate' : 'bearish',
        floors_applied: selectedFloors,
        adaptive_weights: adaptiveWeights,
        total_check: validateTotalAllocation(coinAllocation)
      }
    };

    console.debug('🎯 Final V2 allocation result:', result);
    return result;

  } catch (error) {
    console.error('❌ Allocation Engine V2 failed:', error);
    return null; // Fallback vers V1
  }
}

/**
 * Niveau 1: Allocation Macro (BTC, ETH, Stables, Alts total)
 */
function calculateMacroAllocation(context, floors) {
  const { cycleScore = 50, adaptiveWeights = {}, risk_budget = {} } = context;

  // SOURCE UNIQUE: risk_budget.target_stables_pct avec fallback regime_based
  const stablesTarget = risk_budget.target_stables_pct ?
    risk_budget.target_stables_pct / 100 :
    (cycleScore >= 90 ? 0.15 : cycleScore >= 70 ? 0.20 : 0.30);

  // RENORMALISATION PROPORTIONNELLE des non-stables
  const nonStablesSpace = 1 - stablesTarget;

  // Ratios de base selon cycle (avant renormalisation)
  let baseBtcRatio, baseEthRatio, baseAltsRatio;
  if (cycleScore >= 90) {
    // Bull market: plus d'alts
    baseBtcRatio = 0.25;
    baseEthRatio = 0.20;
    baseAltsRatio = 0.55; // Le reste
  } else if (cycleScore >= 70) {
    // Modéré: équilibré
    baseBtcRatio = 0.30;
    baseEthRatio = 0.22;
    baseAltsRatio = 0.48;
  } else {
    // Bearish: défensif
    baseBtcRatio = 0.35;
    baseEthRatio = 0.25;
    baseAltsRatio = 0.40;
  }

  // Renormalisation proportionnelle pour respecter l'espace non-stables
  const baseTotal = baseBtcRatio + baseEthRatio + baseAltsRatio;
  let btcTarget = (baseBtcRatio / baseTotal) * nonStablesSpace;
  let ethTarget = (baseEthRatio / baseTotal) * nonStablesSpace;
  let altsTarget = (baseAltsRatio / baseTotal) * nonStablesSpace;

  // Appliquer floors (après renormalisation)
  btcTarget = Math.max(btcTarget, floors.BTC || 0);
  ethTarget = Math.max(ethTarget, floors.ETH || 0);
  const finalStablesTarget = Math.max(stablesTarget, floors.Stablecoins || 0);

  // Renormalisation finale si floors causent dépassement
  const preNormTotal = btcTarget + ethTarget + finalStablesTarget + altsTarget;
  if (preNormTotal > 1) {
    const excess = preNormTotal - 1;
    // Réduire alts en priorité, puis BTC/ETH proportionnellement
    if (altsTarget >= excess) {
      altsTarget = Math.max(0.05, altsTarget - excess);
    } else {
      altsTarget = 0.05;
      const remainingExcess = excess - (altsTarget - 0.05);
      const btcEthTotal = btcTarget + ethTarget;
      if (btcEthTotal > 0) {
        btcTarget *= (1 - remainingExcess / btcEthTotal);
        ethTarget *= (1 - remainingExcess / btcEthTotal);
      }
    }
  }

  return {
    BTC: btcTarget,
    ETH: ethTarget,
    Stablecoins: finalStablesTarget,
    Alts: altsTarget
  };
}

/**
 * Niveau 2: Redistribution des Alts vers secteurs
 */
function calculateSectorAllocation(macroAllocation, floors, isBullishPhase) {
  const altsTotal = macroAllocation.Alts;

  // Debug: log the floors being used
  console.debug('🏗️ Sector allocation floors:', floors);
  console.debug('📊 Bullish phase:', isBullishPhase, 'Alts total:', altsTotal);

  // Secteurs alts à distribuer
  const altSectors = ['SOL', 'L1/L0 majors', 'L2/Scaling', 'DeFi', 'Memecoins', 'Gaming/NFT', 'AI/Data', 'Others'];

  let allocation = {
    BTC: macroAllocation.BTC,
    ETH: macroAllocation.ETH,
    Stablecoins: macroAllocation.Stablecoins
  };

  // Ratios souhaités par secteur alts
  const sectorRatios = isBullishPhase ? {
    'SOL': 0.25,
    'L1/L0 majors': 0.30,
    'L2/Scaling': 0.15,
    'DeFi': 0.20,
    'Memecoins': 0.05,
    'Gaming/NFT': 0.03,
    'AI/Data': 0.02
  } : {
    'SOL': 0.20,
    'L1/L0 majors': 0.40,
    'L2/Scaling': 0.10,
    'DeFi': 0.15,
    'Memecoins': 0.02,
    'Gaming/NFT': 0.01,
    'AI/Data': 0.01
  };

  // Calcul initial avec floors
  let sectorWeights = {};
  Object.entries(sectorRatios).forEach(([sector, ratio]) => {
    const desiredWeight = altsTotal * ratio;
    const floorWeight = floors[sector] || 0;
    sectorWeights[sector] = Math.max(floorWeight, desiredWeight);
  });

  // NORMALISATION: si la somme des floors > budget alts, réduire proportionnellement
  const totalSectorWeights = Object.values(sectorWeights).reduce((sum, w) => sum + w, 0);
  const othersFloor = floors.Others || 0.01;
  const availableForSectors = Math.max(0, altsTotal - othersFloor);

  if (totalSectorWeights > availableForSectors) {
    const scale = availableForSectors / totalSectorWeights;
    console.debug(`🔧 Sector floors exceed budget alts (${(totalSectorWeights * 100).toFixed(1)}% > ${(availableForSectors * 100).toFixed(1)}%), scaling by ${scale.toFixed(3)}`);
    Object.keys(sectorWeights).forEach(sector => {
      sectorWeights[sector] *= scale;
    });
  }

  // Appliquer les poids normalisés
  Object.entries(sectorWeights).forEach(([sector, weight]) => {
    allocation[sector] = weight;
  });

  // Others = reste disponible
  const finalAllocated = Object.values(sectorWeights).reduce((sum, w) => sum + w, 0);
  allocation.Others = Math.max(othersFloor, altsTotal - finalAllocated);

  return allocation;
}

/**
 * Niveau 3: Distribution intra-secteur avec protection incumbency
 */
function calculateCoinAllocation(sectorAllocation, currentPositions, floors) {
  const coinAllocation = {};
  const heldAssets = new Set(currentPositions.map(pos => pos.symbol?.toUpperCase()).filter(Boolean));

  console.debug('🔒 Incumbency protection for held assets:', Array.from(heldAssets));

  // Debug: check how assets are classified
  currentPositions.forEach(pos => {
    const symbol = pos.symbol?.toUpperCase();
    const group = getAssetGroup(symbol);
    console.debug(`🏷️ Asset ${symbol} → Group: ${group}`);
  });

  // Debug: show UNIFIED_ASSET_GROUPS structure
  console.debug('🏗️ UNIFIED_ASSET_GROUPS:', UNIFIED_ASSET_GROUPS);

  // Pour chaque secteur, distribuer vers les coins
  Object.entries(sectorAllocation).forEach(([sector, sectorWeight]) => {
    // Ensure sectorWeight is a valid number
    const validSectorWeight = isNaN(sectorWeight) || sectorWeight == null ? 0 : sectorWeight;

    if (['BTC', 'ETH', 'Stablecoins'].includes(sector)) {
      // Pas de subdivision pour ces secteurs majeurs
      coinAllocation[sector] = validSectorWeight;
    } else {
      // Secteurs avec subdivision possible
      const sectorAssets = UNIFIED_ASSET_GROUPS[sector] || [];
      const heldInSector = sectorAssets.filter(asset => heldAssets.has(asset));

      if (heldInSector.length === 0) {
        // Pas d'assets détenus dans ce secteur
        coinAllocation[sector] = validSectorWeight;
      } else {
        // INCUMBENCY BORNÉ: si n*3% > secteur, répartir secteur/n, reste = 0
        const desiredIncumbencyFloor = floors.incumbency || 0.03;
        const desiredIncumbencyTotal = heldInSector.length * desiredIncumbencyFloor;

        let actualIncumbencyFloor, remainingWeight;
        if (desiredIncumbencyTotal > validSectorWeight) {
          // Cas: incumbency dépasserait le secteur → répartir équitablement
          actualIncumbencyFloor = validSectorWeight / heldInSector.length;
          remainingWeight = 0;
          console.debug(`⚠️ Incumbency capped for ${sector}: ${heldInSector.length} × ${desiredIncumbencyFloor.toFixed(3)} → ${actualIncumbencyFloor.toFixed(3)} each`);
        } else {
          // Cas normal: incumbency + reste
          actualIncumbencyFloor = desiredIncumbencyFloor;
          remainingWeight = validSectorWeight - desiredIncumbencyTotal;
        }

        // HIERARCHIE STRICTE: soit secteur global, soit coins individuels, jamais les deux
        if (heldInSector.length === 1 && validSectorWeight > 0.05) {
          // Un seul coin détenu avec allocation significative → l'exposer directement
          const assetWeight = validSectorWeight;
          coinAllocation[heldInSector[0]] = assetWeight;
          // NE PAS ajouter le secteur global pour éviter double-comptage
        } else if (heldInSector.length > 1) {
          // Plusieurs coins détenus → distribution avec incumbency borné
          heldInSector.forEach(asset => {
            const assetWeight = actualIncumbencyFloor + (remainingWeight / heldInSector.length);
            coinAllocation[asset] = isNaN(assetWeight) ? actualIncumbencyFloor : assetWeight;
          });
          // NE PAS ajouter le secteur global
        } else {
          // Aucun coin détenu → allocation au secteur global uniquement
          coinAllocation[sector] = validSectorWeight;
        }
      }
    }
  });

  return coinAllocation;
}

/**
 * Calcul du plan d'exécution (iterations estimées)
 */
function calculateExecutionPlan(targetAllocation, currentPositions, executionContext = {}) {
  const capPerIterPct = executionContext.cap_pct_per_iter ?? 7; // ex: 7 (%)
  const capPerIter = capPerIterPct / 100;                       // 0.07 (fraction)

  // Calculer les écarts max
  const currentAlloc = calculateCurrentAllocation(currentPositions);
  let maxDelta = 0;
  let maxDeltaGroup = '';

  const deltas = [];
  Object.entries(targetAllocation).forEach(([asset, target]) => {
    const current = currentAlloc[asset] || 0;
    const delta = Math.abs(target - current);
    deltas.push({ asset, current: current * 100, target: target * 100, delta: delta * 100 });

    if (delta > maxDelta) {
      maxDelta = delta;
      maxDeltaGroup = asset;
    }
  });

  // Estimer les iterations nécessaires (maxDelta et capPerIter sont tous deux en fraction 0-1)
  const estimatedIters = Math.ceil(maxDelta / capPerIter);

  console.debug('🔄 Convergence calculation:', {
    maxDeltaPct: (maxDelta * 100).toFixed(1),
    maxDeltaGroup,
    capPerIter,
    estimatedIters,
    formula: `ceil(${(maxDelta * 100).toFixed(1)}% / ${capPerIter}%) = ${estimatedIters}`,
    allDeltas: deltas.filter(d => d.delta > 0.1).map(d => `${d.asset}: ${d.current.toFixed(1)}% → ${d.target.toFixed(1)}% (Δ${d.delta.toFixed(1)}%)`)
  });

  return {
    estimated_iters_to_target: estimatedIters,
    max_delta_pct: maxDelta * 100,
    cap_per_iter: capPerIterPct, // exposé en % pour l'affichage
    convergence_time_estimate: `${estimatedIters} rebalances`
  };
}

/**
 * Utilitaires
 */
function calculateCurrentAllocation(positions) {
  const total = positions.reduce((sum, pos) => sum + (parseFloat(pos.value_usd) || 0), 0);
  const allocation = {};

  positions.forEach(pos => {
    const group = getAssetGroup(pos.symbol);
    const weight = (parseFloat(pos.value_usd) || 0) / total;
    allocation[group] = (allocation[group] || 0) + weight;
  });

  return allocation;
}

function validateTotalAllocation(allocation) {
  // Filter out null, undefined, and NaN values before summing
  const validValues = Object.values(allocation).filter(val =>
    val !== null && val !== undefined && !isNaN(val) && typeof val === 'number'
  );
  const total = validValues.reduce((sum, val) => sum + val, 0);
  const isValid = Math.abs(total - 1) < 0.001; // Tolérance 0.1%

  if (!isValid) {
    console.warn('⚠️ Total allocation mismatch:', total, 'from values:', validValues);
  }

  return { total, isValid };
}

/**
 * Validation hiérarchique - détecte double-comptage et incohérences
 */
function validateHierarchy(allocation, currentPositions) {
  const issues = [];
  const allocationKeys = Object.keys(allocation);

  // Vérifier double-comptage: un coin ne doit pas coexister avec son groupe parent
  currentPositions.forEach(pos => {
    const symbol = pos.symbol?.toUpperCase();
    const group = getAssetGroup(symbol);

    if (allocation[symbol] && allocation[group] && symbol !== group) {
      issues.push(`Double-comptage: ${symbol} (${allocation[symbol].toFixed(3)}) + ${group} (${allocation[group].toFixed(3)})`);
    }
  });

  // Vérifier cohérence des groupes vs sous-éléments avec GROUP_ORDER (synchrone)
  const topLevelGroups = ['BTC', 'ETH', 'Stablecoins', 'SOL', 'L1/L0 majors', 'L2/Scaling', 'DeFi', 'AI/Data', 'Gaming/NFT', 'Memecoins', 'Others'];

  topLevelGroups.forEach(group => {
    const groupWeight = allocation[group] || 0;
    const groupAssets = UNIFIED_ASSET_GROUPS[group] || [];
    const childrenWeights = groupAssets
      .filter(asset => allocation[asset])
      .reduce((sum, asset) => sum + (allocation[asset] || 0), 0);

    if (groupWeight > 0 && childrenWeights > 0) {
      issues.push(`Groupe ${group} (${groupWeight.toFixed(3)}) coexiste avec enfants (${childrenWeights.toFixed(3)})`);
    }

    // GUARD: group_without_descent - affiné selon la demande
    const isTerminal = ['BTC', 'ETH', 'Stablecoins', 'Others'].includes(group);
    if (groupWeight > 0.001 && childrenWeights === 0 && groupAssets.length > 0) {
      if (isTerminal) {
        console.debug(`🔍 group_without_descent (terminal): ${group} (${groupWeight.toFixed(3)}) - OK pour terminal`);
      } else {
        console.debug(`🔍 group_without_descent (secteur): ${group} (${groupWeight.toFixed(3)}) - drill-down vide autorisé`);
      }
    }
  });

  // GUARD: child_at_top_level - WARN seulement si parent a poids > 0 (vrai double-comptage)
  allocationKeys.forEach(key => {
    if (!topLevelGroups.includes(key) && allocation[key] > 0.001) {
      const parentGroup = getAssetGroup(key);
      const parentWeight = allocation[parentGroup] || 0;

      if (parentGroup !== key && parentGroup !== 'Others' && parentWeight > 0.001) {
        console.warn(`⚠️ child_at_top_level: ${key} (${allocation[key].toFixed(3)}) + parent ${parentGroup} (${parentWeight.toFixed(3)}) = vrai double-comptage`);
        issues.push(`child_at_top_level: ${key} → ${parentGroup}`);
      } else if (parentGroup !== key) {
        console.debug(`🔍 child_at_top_level: ${key} (${allocation[key].toFixed(3)}) mais parent ${parentGroup} = 0 - OK`);
      }
    }
  });

  return {
    valid: issues.length === 0,
    issues: issues
  };
}

function logAllocationDecisions(data) {
  console.group('🏗️ Allocation Engine Decisions');
  console.debug('📊 Input context:', {
    cycle: data.context.cycleScore,
    onchain: data.context.onchainScore,
    contradiction: data.context.contradiction,
    adaptive_weights: data.context.adaptiveWeights
  });
  console.debug('🌍 Macro allocation:', data.macro);
  console.debug('🏭 Sector allocation:', data.sectors);
  console.debug('🪙 Final coin allocation:', data.coins);
  console.debug('⏱️ Execution plan:', data.execution);
  console.groupEnd();
}

// Export par défaut pour compatibilité
export default { calculateHierarchicalAllocation };