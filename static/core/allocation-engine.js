// Allocation Engine V2 - Descente hiérarchique avec Feature Flag
// Macro → Secteurs → Coins avec floors contextuels et incumbency protection

import { getAssetGroup, UNIFIED_ASSET_GROUPS, GROUP_ORDER } from '../shared-asset-groups.js';

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

    // 7. LOGS POUR DEBUG
    logAllocationDecisions({
      context,
      macro: macroAllocation,
      sectors: sectorAllocation,
      coins: coinAllocation,
      execution: executionPlan
    });

    return {
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

  // Base allocation selon cycle
  let btcTarget, ethTarget, stablesTarget, altsTarget;

  if (cycleScore >= 90) {
    // Bull market: plus d'alts
    btcTarget = 0.25;
    ethTarget = 0.20;
    stablesTarget = risk_budget.target_stables_pct ? risk_budget.target_stables_pct / 100 : 0.15;
    altsTarget = 1 - btcTarget - ethTarget - stablesTarget;
  } else if (cycleScore >= 70) {
    // Modéré: équilibré
    btcTarget = 0.30;
    ethTarget = 0.22;
    stablesTarget = risk_budget.target_stables_pct ? risk_budget.target_stables_pct / 100 : 0.20;
    altsTarget = 1 - btcTarget - ethTarget - stablesTarget;
  } else {
    // Bearish: défensif
    btcTarget = 0.35;
    ethTarget = 0.25;
    stablesTarget = risk_budget.target_stables_pct ? risk_budget.target_stables_pct / 100 : 0.30;
    altsTarget = 1 - btcTarget - ethTarget - stablesTarget;
  }

  // Appliquer floors
  btcTarget = Math.max(btcTarget, floors.BTC || 0);
  ethTarget = Math.max(ethTarget, floors.ETH || 0);
  stablesTarget = Math.max(stablesTarget, floors.Stablecoins || 0);

  // Normaliser
  const total = btcTarget + ethTarget + stablesTarget + altsTarget;
  if (total > 1) {
    const excess = total - 1;
    altsTarget = Math.max(0.05, altsTarget - excess); // Réduire alts si dépassement
  }

  return {
    BTC: btcTarget,
    ETH: ethTarget,
    Stablecoins: stablesTarget,
    Alts: altsTarget
  };
}

/**
 * Niveau 2: Redistribution des Alts vers secteurs
 */
function calculateSectorAllocation(macroAllocation, floors, isBullishPhase) {
  const altsTotal = macroAllocation.Alts;

  // Secteurs alts à distribuer
  const altSectors = ['SOL', 'L1/L0 majors', 'L2/Scaling', 'DeFi', 'Memecoins', 'Gaming/NFT', 'AI/Data', 'Others'];

  let allocation = {
    BTC: macroAllocation.BTC,
    ETH: macroAllocation.ETH,
    Stablecoins: macroAllocation.Stablecoins
  };

  if (isBullishPhase) {
    // Distribution bullish (plus d'exposition alts)
    allocation.SOL = Math.max(floors.SOL || 0, altsTotal * 0.25);
    allocation['L1/L0 majors'] = Math.max(floors['L1/L0 majors'] || 0, altsTotal * 0.30);
    allocation['L2/Scaling'] = Math.max(floors['L2/Scaling'] || 0, altsTotal * 0.15);
    allocation.DeFi = Math.max(floors.DeFi || 0, altsTotal * 0.20);
    allocation.Memecoins = Math.max(floors.Memecoins || 0, altsTotal * 0.05);
    allocation['Gaming/NFT'] = Math.max(floors['Gaming/NFT'] || 0, altsTotal * 0.03);
    allocation['AI/Data'] = Math.max(floors['AI/Data'] || 0, altsTotal * 0.02);
  } else {
    // Distribution modérée/bearish
    allocation.SOL = Math.max(floors.SOL || 0, altsTotal * 0.20);
    allocation['L1/L0 majors'] = Math.max(floors['L1/L0 majors'] || 0, altsTotal * 0.40);
    allocation['L2/Scaling'] = Math.max(floors['L2/Scaling'] || 0, altsTotal * 0.10);
    allocation.DeFi = Math.max(floors.DeFi || 0, altsTotal * 0.15);
    allocation.Memecoins = Math.max(floors.Memecoins || 0, altsTotal * 0.02);
    allocation['Gaming/NFT'] = Math.max(floors['Gaming/NFT'] || 0, altsTotal * 0.01);
    allocation['AI/Data'] = Math.max(floors['AI/Data'] || 0, altsTotal * 0.01);
  }

  // Others = reste
  const allocatedAlts = Object.entries(allocation)
    .filter(([key]) => altSectors.includes(key))
    .reduce((sum, [, value]) => sum + (isNaN(value) ? 0 : value), 0);

  const othersWeight = Math.max(floors.Others || 0, altsTotal - allocatedAlts);
  allocation.Others = isNaN(othersWeight) ? floors.Others || 0.01 : othersWeight;

  return allocation;
}

/**
 * Niveau 3: Distribution intra-secteur avec protection incumbency
 */
function calculateCoinAllocation(sectorAllocation, currentPositions, floors) {
  const coinAllocation = {};
  const heldAssets = new Set(currentPositions.map(pos => pos.symbol?.toUpperCase()).filter(Boolean));

  console.debug('🔒 Incumbency protection for held assets:', Array.from(heldAssets));

  // Pour chaque secteur, distribuer vers les coins
  Object.entries(sectorAllocation).forEach(([sector, sectorWeight]) => {
    if (['BTC', 'ETH', 'Stablecoins'].includes(sector)) {
      // Pas de subdivision pour ces secteurs majeurs
      coinAllocation[sector] = sectorWeight;
    } else {
      // Secteurs avec subdivision possible
      const sectorAssets = UNIFIED_ASSET_GROUPS[sector] || [];
      const heldInSector = sectorAssets.filter(asset => heldAssets.has(asset));

      if (heldInSector.length === 0) {
        // Pas d'assets détenus dans ce secteur
        coinAllocation[sector] = sectorWeight;
      } else {
        // Redistribuer vers assets détenus avec incumbency protection
        const incumbencyTotal = heldInSector.length * floors.incumbency;
        const remainingWeight = Math.max(0, sectorWeight - incumbencyTotal);

        // Distribution égale + incumbency
        heldInSector.forEach(asset => {
          const assetWeight = floors.incumbency + (remainingWeight / heldInSector.length);
          coinAllocation[asset] = isNaN(assetWeight) ? floors.incumbency : assetWeight;
        });

        // Le reste va au secteur global (pour nouveaux achats potentiels)
        if (remainingWeight > 0) {
          coinAllocation[sector] = Math.max(0, sectorWeight * 0.1); // 10% pour flexibilité
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
  const capPerIter = executionContext.cap_pct_per_iter || 7;

  // Calculer les écarts max
  const currentAlloc = calculateCurrentAllocation(currentPositions);
  let maxDelta = 0;

  Object.entries(targetAllocation).forEach(([asset, target]) => {
    const current = currentAlloc[asset] || 0;
    const delta = Math.abs(target - current);
    maxDelta = Math.max(maxDelta, delta);
  });

  // Estimer les iterations nécessaires
  const estimatedIters = Math.ceil(maxDelta / (capPerIter / 100));

  return {
    estimated_iters_to_target: estimatedIters,
    max_delta_pct: maxDelta * 100,
    cap_per_iter: capPerIter,
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
  const total = Object.values(allocation).reduce((sum, val) => sum + val, 0);
  const isValid = Math.abs(total - 1) < 0.001; // Tolérance 0.1%

  if (!isValid) {
    console.warn('⚠️ Total allocation mismatch:', total);
  }

  return { total, isValid };
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