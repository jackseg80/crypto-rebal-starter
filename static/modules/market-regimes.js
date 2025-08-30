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
 * Applique des overrides basés sur les conditions de marché
 */
export function applyMarketOverrides(regime, onchainScore, riskScore) {
  let adjustedRegime = { ...regime };
  const overrides = [];
  
  // Override 1: Divergence On-Chain > 25 pts
  if (onchainScore != null && Math.abs(regime.score - onchainScore) > 25) {
    adjustedRegime.allocation_bias.stables_target += 10;
    overrides.push({
      type: 'onchain_divergence',
      message: `Divergence On-Chain détectée (${Math.abs(regime.score - onchainScore).toFixed(1)} pts)`,
      adjustment: '+10% stables'
    });
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

/**
 * Calcule le budget de risque global selon la formule stratégique
 */
export function calculateRiskBudget(blendedScore, riskScore) {
  console.log('💰 Calculating Risk Budget:', { blendedScore, riskScore });
  
  // Formule: RiskCap = 1 - 0.5 × (RiskScore/100)
  const riskCap = riskScore != null ? 1 - 0.5 * (riskScore / 100) : 0.75;
  
  // BaseRisky = clamp((Blended - 35)/45, 0, 1)
  const baseRisky = Math.max(0, Math.min(1, (blendedScore - 35) / 45));
  
  // Risky = clamp(BaseRisky × RiskCap, 20%, 85%)
  const riskyAllocation = Math.max(0.20, Math.min(0.85, baseRisky * riskCap));
  
  // Stables = 1 - Risky
  const stablesAllocation = 1 - riskyAllocation;
  
  const result = {
    risk_cap: riskCap,
    base_risky: baseRisky,
    risky_allocation: riskyAllocation,
    stables_allocation: stablesAllocation,
    percentages: {
      risky: Math.round(riskyAllocation * 100),
      stables: Math.round(stablesAllocation * 100)
    }
  };
  
  console.log('💰 Risk Budget calculated:', result);
  return result;
}

/**
 * Répartit l'allocation "risky" selon le régime de marché
 */
export function allocateRiskyBudget(riskyPercentage, regime) {
  // Base par défaut : BTC 50% / ETH 30% / Midcaps 20%
  let allocation = {
    btc: 50,
    eth: 30,
    midcaps: 15,
    meme: 5
  };
  
  // Ajustements selon le régime
  const bias = regime.allocation_bias;
  
  allocation.btc += bias.btc_boost || 0;
  allocation.eth += bias.eth_boost || 0;
  allocation.midcaps += (bias.alts_reduction || 0);
  allocation.meme = Math.min(allocation.meme, bias.meme_cap || 5);
  
  // Normaliser à 100%
  const total = allocation.btc + allocation.eth + allocation.midcaps + allocation.meme;
  if (total !== 100) {
    const factor = 100 / total;
    allocation.btc = Math.round(allocation.btc * factor);
    allocation.eth = Math.round(allocation.eth * factor);
    allocation.midcaps = Math.round(allocation.midcaps * factor);
    allocation.meme = Math.round(allocation.meme * factor);
  }
  
  // Appliquer le pourcentage risky
  const riskyFactor = riskyPercentage / 100;
  
  return {
    BTC: allocation.btc * riskyFactor,
    ETH: allocation.eth * riskyFactor,
    SOL: allocation.midcaps * riskyFactor * 0.2,
    'L1/L0 majors': allocation.midcaps * riskyFactor * 0.4,
    'L2/Scaling': allocation.midcaps * riskyFactor * 0.3,
    'DeFi': allocation.midcaps * riskyFactor * 0.1,
    'AI/Data': allocation.meme * riskyFactor * 0.5,
    'Gaming/NFT': allocation.meme * riskyFactor * 0.3,
    'Memecoins': allocation.meme * riskyFactor * 0.2,
    'Stablecoins': 100 - riskyPercentage,
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
 * Exporte les données du régime pour l'interface
 */
export function getRegimeDisplayData(blendedScore, onchainScore, riskScore) {
  const regime = getMarketRegime(blendedScore);
  const adjustedRegime = applyMarketOverrides(regime, onchainScore, riskScore);
  const riskBudget = calculateRiskBudget(blendedScore, riskScore);
  const allocation = allocateRiskyBudget(riskBudget.percentages.risky, adjustedRegime);
  const recommendations = generateRegimeRecommendations(adjustedRegime, riskBudget);
  
  return {
    regime: adjustedRegime,
    risk_budget: riskBudget,
    allocation,
    recommendations,
    timestamp: new Date().toISOString()
  };
}