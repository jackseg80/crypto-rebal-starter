/**
 * Market Regimes Module - Système de Régimes de Marché Intelligent
 * Détermine le régime actuel basé sur Blended Score et applique des règles de rebalancing
 */

/**
 * Configuration des 4 régimes de marché
 */
export const MARKET_REGIMES = {
  accumulation: {
    name: 'Accumulation',
    emoji: '🔵',
    range: [0, 39],
    color: '#3b82f6',
    description: 'Phase d\'accumulation - Marché bearish/neutre',
    strategy: 'BTC/ETH principalement, peu d\'alts, stables réduits',
    allocation_bias: {
      btc_boost: 10,
      eth_boost: 5,
      alts_reduction: -15,
      stables_target: 15,
      meme_cap: 0
    }
  },
  
  expansion: {
    name: 'Expansion',
    emoji: '🟢',
    range: [40, 69],
    color: '#10b981',
    description: 'Phase d\'expansion - Marché haussier modéré',
    strategy: 'ETH + midcaps progressifs, équilibre',
    allocation_bias: {
      btc_boost: 0,
      eth_boost: 0,
      alts_reduction: 0,
      stables_target: 20,
      meme_cap: 5
    }
  },
  
  euphoria: {
    name: 'Euphorie',
    emoji: '🟡',
    range: [70, 84],
    color: '#f59e0b',
    description: 'Phase d\'euphorie - Bulle en formation',
    strategy: 'Alts boostés, memes autorisés (max 15%)',
    allocation_bias: {
      btc_boost: -5,
      eth_boost: 5,
      alts_reduction: 10,
      stables_target: 15,
      meme_cap: 15
    }
  },
  
  distribution: {
    name: 'Distribution',
    emoji: '🔴',
    range: [85, 100],
    color: '#dc2626',
    description: 'Phase de distribution - Pic probable',
    strategy: 'Retour stables + BTC, réduction alts',
    allocation_bias: {
      btc_boost: 5,
      eth_boost: -5,
      alts_reduction: -15,
      stables_target: 30,
      meme_cap: 0
    }
  }
};

/**
 * Détermine le régime de marché basé sur le Blended Score
 */
export function getMarketRegime(blendedScore) {
  if (typeof blendedScore !== 'number' || blendedScore < 0 || blendedScore > 100) {
    return {
      ...MARKET_REGIMES.expansion, // Fallback neutre
      score: blendedScore,
      confidence: 0.1,
      warning: 'Score invalide'
    };
  }
  
  // Trouver le régime correspondant
  for (const [key, regime] of Object.entries(MARKET_REGIMES)) {
    const [min, max] = regime.range;
    if (blendedScore >= min && blendedScore <= max) {
      return {
        ...regime,
        key,
        score: blendedScore,
        confidence: calculateRegimeConfidence(blendedScore, regime),
        transition: getTransitionStatus(blendedScore, regime)
      };
    }
  }
  
  // Fallback (ne devrait pas arriver)
  return {
    ...MARKET_REGIMES.expansion,
    key: 'expansion',
    score: blendedScore,
    confidence: 0.3,
    warning: 'Régime non déterminé'
  };
}

/**
 * Calcule la confiance dans le régime actuel
 */
function calculateRegimeConfidence(score, regime) {
  const [min, max] = regime.range;
  const center = (min + max) / 2;
  const distance = Math.abs(score - center);
  const maxDistance = (max - min) / 2;
  
  // Plus proche du centre = plus de confiance
  return Math.max(0.3, 1.0 - (distance / maxDistance) * 0.7);
}

/**
 * Détermine si on est en transition entre régimes
 */
function getTransitionStatus(score, regime) {
  const [min, max] = regime.range;
  const buffer = 3; // Zone de transition de 3 points
  
  if (score <= min + buffer) {
    return {
      status: 'entering',
      direction: 'from_below',
      strength: (score - min) / buffer
    };
  } else if (score >= max - buffer) {
    return {
      status: 'exiting',
      direction: 'to_above', 
      strength: (max - score) / buffer
    };
  }
  
  return {
    status: 'stable',
    direction: 'none',
    strength: 1.0
  };
}

/**
 * Applique des overrides basés sur les conditions de marché avec hysteresis
 */
export function applyMarketOverrides(regime, onchainScore, riskScore) {
  // DEEP COPY to avoid mutating the original regime object
  let adjustedRegime = {
    ...regime,
    allocation_bias: { ...regime.allocation_bias } // Deep copy allocation_bias
  };
  const overrides = [];

  // Init flags hysteresis
  if (!window.__marketOverrideFlags) window.__marketOverrideFlags = {};
  const flags = window.__marketOverrideFlags;

  // Fonction flip pour Schmitt trigger
  const flip = (prev, val, up, down) => prev ? (val > down) : (val >= up);

  // Override 1: Divergence On-Chain avec hysteresis ÉLARGIE (up=30, down=20)
  // Élargi pour éviter flip-flop: gap de 10pts (était 4pts avant)
  if (onchainScore != null) {
    const divergence = Math.abs(regime.score - onchainScore);
    flags.onchain_div = flip(flags.onchain_div, divergence, 30, 20);  // ÉLARGI

    if (flags.onchain_div) {
      adjustedRegime.allocation_bias.stables_target += 10;
      overrides.push({
        type: 'onchain_divergence',
        message: `Divergence On-Chain détectée (${divergence.toFixed(1)} pts)`,
        adjustment: '+10% stables'
      });
    }
  }
  
  // Override 2: Risk Score ≥ 80 (très risqué)
  if (riskScore != null && riskScore >= 80) {
    adjustedRegime.allocation_bias.stables_target = Math.max(50, adjustedRegime.allocation_bias.stables_target);
    adjustedRegime.allocation_bias.alts_reduction -= 10; // Encore moins d'alts
    adjustedRegime.allocation_bias.meme_cap = 0; // Pas de memes
    overrides.push({
      type: 'high_risk',
      message: `Risk Score très élevé (${riskScore})`,
      adjustment: 'Stables ≥50%, alts ≤20%, memes=0%'
    });
  }
  
  // Override 3: Risk Score ≤ 30 (très peu risqué)
  if (riskScore != null && riskScore <= 30) {
    adjustedRegime.allocation_bias.alts_reduction += 5; // Plus d'alts permis
    adjustedRegime.allocation_bias.meme_cap += 5; // Plus de memes
    overrides.push({
      type: 'low_risk',
      message: `Risk Score très faible (${riskScore})`,
      adjustment: '+5% alts/memes autorisés'
    });
  }
  
  adjustedRegime.overrides = overrides;
  return adjustedRegime;
}

// Cache Risk Budget avec TTL 30s et clé basée sur scores arrondis
let _riskBudgetCache = { key: null, data: null, timestamp: 0 };

/**
 * Calcule le budget de risque global selon la formule stratégique avec cache snapshot
 */
export function calculateRiskBudget(blendedScore, riskScore) {
  // ARRONDIR les scores d'entrée pour stabilité (éviter micro-variations 68.3 vs 68.7)
  const blendedRounded = Math.round(blendedScore);
  const riskRounded = Math.round(riskScore || 0);

  // FEATURE FLAG: Risk semantics version (legacy, v2_conservative, v2_aggressive)
  // IMPORTANT: Lire AVANT le cache pour inclure dans la clé
  // FIXÉ À v2_conservative (Oct 2025) pour cohérence - migration progressive
  const riskSemanticsMode = (typeof localStorage !== 'undefined')
    ? localStorage.getItem('RISK_SEMANTICS_MODE') || 'v2_conservative'  // CHANGED: default v2_conservative
    : 'v2_conservative';

  const now = Date.now();
  const cacheKey = `${blendedRounded}-${riskRounded}-${riskSemanticsMode}`; // Include mode in key!

  // CACHE RÉACTIVÉ (Oct 2025) - TTL 30s pour stabilité
  if (_riskBudgetCache.key === cacheKey && now - _riskBudgetCache.timestamp < 30000) {
    console.debug('💰 Risk Budget from cache:', cacheKey);
    return JSON.parse(JSON.stringify(_riskBudgetCache.data));
  }
  console.debug('💰 Cache MISS - Calculating fresh Risk Budget (key:', cacheKey, ')');

  (window.debugLogger?.info || console.log)('💰 Calculating Risk Budget:', {
    original: { blended: blendedScore, risk: riskScore },
    rounded: { blended: blendedRounded, risk: riskRounded },
    mode: riskSemanticsMode
  });

  let risk_factor;

  if (riskSemanticsMode === 'legacy') {
    // LEGACY (INVERSÉ): RiskCap = 1 - 0.5 × (RiskScore/100)
    // ❌ BUG: Traite Risk Score comme danger (haut=dangereux) au lieu de robustesse
    const riskCap = riskRounded != null ? 1 - 0.5 * (riskRounded / 100) : 0.75;
    risk_factor = riskCap;
    console.debug('⚠️ LEGACY MODE: Using inverted risk semantics (will be deprecated)');
  } else if (riskSemanticsMode === 'v2_conservative') {
    // V2 CONSERVATIVE: risk_factor = 0.5 + 0.5 × (RiskScore/100)
    // ✅ CORRECT: Risk Score = robustesse (haut=robuste → plus de risky autorisé)
    // Range: [0.5 .. 1.0]
    risk_factor = 0.5 + 0.5 * (riskRounded / 100);
    console.debug('✅ V2 CONSERVATIVE: risk_factor =', risk_factor.toFixed(3));
  } else if (riskSemanticsMode === 'v2_aggressive') {
    // V2 AGGRESSIVE: risk_factor = 0.4 + 0.7 × (RiskScore/100)
    // ✅ CORRECT: Plus de différenciation entre portfolios fragiles/robustes
    // Range: [0.4 .. 1.1]
    risk_factor = 0.4 + 0.7 * (riskRounded / 100);
    console.debug('✅ V2 AGGRESSIVE: risk_factor =', risk_factor.toFixed(3));
  } else {
    // Fallback to conservative if unknown mode
    risk_factor = 0.5 + 0.5 * (riskRounded / 100);
    console.warn('Unknown RISK_SEMANTICS_MODE:', riskSemanticsMode, '- using v2_conservative');
  }

  // BaseRisky = clamp((Blended - 35)/45, 0, 1) - utiliser score arrondi
  const baseRisky = Math.max(0, Math.min(1, (blendedRounded - 35) / 45));

  // Risky = clamp(BaseRisky × risk_factor, 20%, 85%)
  const riskyAllocation = Math.max(0.20, Math.min(0.85, baseRisky * risk_factor));

  // Stables = 1 - Risky
  const stablesAllocation = 1 - riskyAllocation;

  // Arrondi unique pour éviter 101%
  const riskyPct = Math.round(riskyAllocation * 100);
  const stablesPct = 100 - riskyPct;

  // DEBUG - Vérifier l'arrondi
  console.debug('🔍 ARRONDI DEBUG:', {
    riskyAllocation,
    stablesAllocation,
    riskyRaw: riskyAllocation * 100,
    stablesRaw: stablesAllocation * 100,
    riskyPct,
    stablesPct,
    sum: riskyPct + stablesPct,
    shouldBe100: (riskyPct + stablesPct) === 100
  });

  const result = {
    risk_factor: risk_factor,  // NEW: Expose risk_factor for debugging
    base_risky: baseRisky,
    risky_allocation: riskyAllocation,
    stables_allocation: stablesAllocation,
    percentages: { risky: riskyPct, stables: stablesPct },
    // Champ canonique pour source unique
    target_stables_pct: stablesPct,
    generated_at: new Date().toISOString(),
    // NEW: Metadata for traceability
    metadata: {
      semantics_mode: riskSemanticsMode,
      blended_score: blendedRounded,
      risk_score: riskRounded,
      formula_version: riskSemanticsMode === 'legacy' ? 'v1_inverted' : 'v2_correct'
    }
  };

  // Sauvegarder dans cache
  _riskBudgetCache = {
    key: cacheKey,
    data: result,
    timestamp: now
  };

  (window.debugLogger?.info || console.log)('💰 Risk Budget calculated:', result);
  return result;
}

/**
 * Répartit l'allocation "risky" selon le régime de marché
 */
export function allocateRiskyBudget(riskyPercentage, regime) {
  console.log('🚨 [allocateRiskyBudget] CALLED - riskyPercentage:', riskyPercentage, 'regime:', regime?.name, 'bias:', regime?.allocation_bias);

  // Base par défaut : BTC 50% / ETH 30% / Midcaps 20%
  let allocation = {
    btc: 50,
    eth: 30,
    midcaps: 15,
    meme: 5
  };

  console.log('🚨 [allocateRiskyBudget] BEFORE bias - allocation:', {...allocation});

  // Ajustements selon le régime
  const bias = regime.allocation_bias;
  
  allocation.btc += bias.btc_boost || 0;
  allocation.eth += bias.eth_boost || 0;
  allocation.midcaps += (bias.alts_reduction || 0);
  allocation.meme = Math.min(allocation.meme, bias.meme_cap || 5);

  console.log('🚨 [allocateRiskyBudget] AFTER bias - allocation:', {...allocation});

  // Normaliser à 100% (déterministe: arrondir puis ajuster le reste sur BTC)
  const total = allocation.btc + allocation.eth + allocation.midcaps + allocation.meme;
  console.log('🚨 [allocateRiskyBudget] Total before normalization:', total);
  if (total !== 100) {
    const factor = 100 / total;
    allocation.btc = Math.floor(allocation.btc * factor);
    allocation.eth = Math.floor(allocation.eth * factor);
    allocation.midcaps = Math.floor(allocation.midcaps * factor);
    allocation.meme = Math.floor(allocation.meme * factor);

    // Ajuster le reste sur BTC (groupe principal) pour garantir 100%
    const currentTotal = allocation.btc + allocation.eth + allocation.midcaps + allocation.meme;
    allocation.btc += (100 - currentTotal);
  }
  
  // Appliquer le pourcentage risky (sur la partie risky uniquement, pas sur stables)
  const riskyFactor = riskyPercentage / 100;

  // Calculer les allocations risky (en % du TOTAL portfolio)
  const btcAlloc = allocation.btc * riskyFactor;
  const ethAlloc = allocation.eth * riskyFactor;
  const solAlloc = allocation.midcaps * riskyFactor * 0.2;
  const l1Alloc = allocation.midcaps * riskyFactor * 0.4;
  const l2Alloc = allocation.midcaps * riskyFactor * 0.3;
  const defiAlloc = allocation.midcaps * riskyFactor * 0.1;
  const aiAlloc = allocation.meme * riskyFactor * 0.5;
  const gameAlloc = allocation.meme * riskyFactor * 0.3;
  const memeAlloc = allocation.meme * riskyFactor * 0.2;

  // Calculer le total risky effectif (pour vérifier)
  const totalRisky = btcAlloc + ethAlloc + solAlloc + l1Alloc + l2Alloc + defiAlloc + aiAlloc + gameAlloc + memeAlloc;

  // Ajuster stables pour garantir 100% exact
  const stablesAlloc = 100 - totalRisky;

  console.log('🚨 [allocateRiskyBudget] FINAL RESULT:', {
    riskyPercentage,
    BTC: btcAlloc.toFixed(2),
    ETH: ethAlloc.toFixed(2),
    totalRisky: totalRisky.toFixed(2),
    stables: stablesAlloc.toFixed(2),
    sum: (totalRisky + stablesAlloc).toFixed(2)
  });

  return {
    BTC: btcAlloc,
    ETH: ethAlloc,
    SOL: solAlloc,
    'L1/L0 majors': l1Alloc,
    'L2/Scaling': l2Alloc,
    'DeFi': defiAlloc,
    'AI/Data': aiAlloc,
    'Gaming/NFT': gameAlloc,
    'Memecoins': memeAlloc,
    'Stablecoins': stablesAlloc,
    'Others': 0
  };
}

/**
 * Génère les recommandations selon le régime
 */
export function generateRegimeRecommendations(regime, riskBudget) {
  const recommendations = [];
  
  // Recommandations par régime
  switch (regime.key) {
    case 'accumulation':
      recommendations.push({
        type: 'strategy',
        priority: 'high',
        message: 'Phase d\'accumulation détectée',
        action: 'Augmenter BTC/ETH, réduire alts, préparer next bull run'
      });
      break;
      
    case 'expansion':
      recommendations.push({
        type: 'strategy',
        priority: 'medium',
        message: 'Expansion en cours',
        action: 'Maintenir équilibre, rotation progressive vers ETH/midcaps'
      });
      break;
      
    case 'euphoria':
      recommendations.push({
        type: 'warning',
        priority: 'high',
        message: 'Euphorie détectée - Attention au pic !',
        action: 'Préparer strategy de sortie, limiter nouvelles positions'
      });
      break;
      
    case 'distribution':
      recommendations.push({
        type: 'alert',
        priority: 'critical',
        message: 'Phase de distribution - Pic probable imminent',
        action: 'Rotation vers stables/BTC, réduction aggressive des alts'
      });
      break;
  }
  
  // Recommandations basées sur les overrides
  if (regime.overrides?.length > 0) {
    regime.overrides.forEach(override => {
      recommendations.push({
        type: 'override',
        priority: 'medium',
        message: override.message,
        action: override.adjustment
      });
    });
  }
  
  // Recommandations budget de risque
  if (riskBudget.stables_allocation > 0.4) {
    recommendations.push({
      type: 'risk',
      priority: 'medium',
      message: 'Budget risque élevé détecté',
      action: `Allocation stables recommandée: ${riskBudget.percentages.stables}%`
    });
  }
  
  return recommendations;
}

/**
 * Exporte les données du régime pour l'interface avec base/adjusted/effective séparés
 */
export function getRegimeDisplayData(blendedScore, onchainScore, riskScore) {
  const base = getMarketRegime(blendedScore);
  const adjusted = applyMarketOverrides(base, onchainScore, riskScore);

  // Recalculer le regime effectif après ajustements (en cas de changement de score)
  const effectiveScore = adjusted.score;
  const effective = getMarketRegime(effectiveScore);

  // Copier les overrides dans effective pour traçabilité
  effective.overrides = adjusted.overrides;
  effective.allocation_bias = adjusted.allocation_bias;

  const riskBudget = calculateRiskBudget(blendedScore, riskScore);
  const allocation = allocateRiskyBudget(riskBudget.percentages.risky, effective);
  const recommendations = generateRegimeRecommendations(effective, riskBudget);

  return {
    regime: effective,  // ✅ Utiliser effective avec le bon key
    base_regime: base,
    adjusted_regime: adjusted,
    risk_budget: riskBudget,
    allocation,
    recommendations,
    timestamp: new Date().toISOString()
  };
}