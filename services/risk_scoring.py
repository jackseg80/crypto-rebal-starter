"""
Centralized Risk Scoring Logic - Single Source of Truth

This module contains the canonical implementation of risk score calculation
and risk level mapping according to Option A semantics (docs/RISK_SEMANTICS.md).

⚠️ CRITICAL: This is the ONLY place where score-to-level mapping should exist.
Any other module needing risk assessment MUST import from here.

Semantic Rule (Option A):
- Risk Score = POSITIVE indicator of robustness [0..100]
- Higher score = more robust = LOWER perceived risk
- Therefore: good metrics → score increases, bad metrics → score decreases
"""

from typing import Dict, Any

# ============================================================================
# CANONICAL SCORE-TO-LEVEL MAPPING (docs/RISK_SEMANTICS.md)
# ============================================================================

RISK_LEVEL_THRESHOLDS = {
    "very_low": 80,   # score >= 80
    "low": 65,        # score >= 65
    "medium": 50,     # score >= 50
    "high": 35,       # score >= 35
    "very_high": 20,  # score >= 20
    "critical": 0     # score < 20
}

def score_to_level(score: float) -> str:
    """
    Canonical mapping: Risk Score → Risk Level

    Args:
        score: Risk score [0..100], higher = more robust

    Returns:
        Risk level string: "very_low", "low", "medium", "high", "very_high", "critical"

    Examples:
        >>> score_to_level(85)
        'very_low'
        >>> score_to_level(70)
        'low'
        >>> score_to_level(55)
        'medium'
        >>> score_to_level(40)
        'high'
        >>> score_to_level(25)
        'very_high'
        >>> score_to_level(10)
        'critical'
    """
    score = max(0, min(100, score))  # Clamp to [0, 100]

    if score >= RISK_LEVEL_THRESHOLDS["very_low"]:
        return "very_low"
    elif score >= RISK_LEVEL_THRESHOLDS["low"]:
        return "low"
    elif score >= RISK_LEVEL_THRESHOLDS["medium"]:
        return "medium"
    elif score >= RISK_LEVEL_THRESHOLDS["high"]:
        return "high"
    elif score >= RISK_LEVEL_THRESHOLDS["very_high"]:
        return "very_high"
    else:
        return "critical"


# ============================================================================
# RISK SCORE CALCULATION (Quantitative - Authoritative)
# ============================================================================

def assess_risk_level(
    var_metrics: Dict[str, float],
    sharpe_ratio: float,
    max_drawdown: float,
    volatility: float
) -> Dict[str, Any]:
    """
    Calculate authoritative Risk Score based on quantitative metrics.

    This is the canonical implementation for Option A semantics:
    - Risk Score = robustness indicator [0..100]
    - Good metrics (low VaR, high Sharpe) → score increases
    - Bad metrics (high VaR, low Sharpe) → score decreases

    Args:
        var_metrics: Dict with 'var_95', 'var_99', 'cvar_95', 'cvar_99'
        sharpe_ratio: Sharpe ratio (risk-adjusted return)
        max_drawdown: Maximum drawdown (negative value)
        volatility: Annualized volatility

    Returns:
        Dict with:
        - "score": float [0..100]
        - "level": str ("very_low", "low", "medium", "high", "very_high", "critical")
        - "breakdown": Dict with component contributions (for audit)
    """
    score = 50.0  # Start neutral
    breakdown = {}

    # VaR impact (higher VaR = LESS robust → score decreases)
    var_95 = abs(var_metrics.get("var_95", 0.0))
    if var_95 > 0.25:
        delta = -30  # ❌ Very high VaR → score drops
    elif var_95 > 0.15:
        delta = -15
    elif var_95 < 0.05:
        delta = +10  # ✅ Low VaR → score rises
    elif var_95 < 0.10:
        delta = +5
    else:
        delta = 0
    score += delta
    breakdown['var_95'] = delta

    # Sharpe ratio impact (higher Sharpe = MORE robust → score increases)
    if sharpe_ratio < 0:
        delta = -15  # ❌ Negative Sharpe → score drops
    elif sharpe_ratio > 2.0:
        delta = +20  # ✅ Excellent Sharpe → score rises
    elif sharpe_ratio > 1.5:
        delta = +15
    elif sharpe_ratio > 1.0:
        delta = +10
    elif sharpe_ratio > 0.5:
        delta = +5
    else:
        delta = 0
    score += delta
    breakdown['sharpe'] = delta

    # Debug log
    import logging
    logging.getLogger(__name__).debug(f"🔍 Risk Score calc: sharpe={sharpe_ratio:.4f}, delta={delta}, score after={score:.1f}")

    # Max Drawdown impact (higher DD = LESS robust → score decreases)
    abs_dd = abs(max_drawdown)
    if abs_dd > 0.50:
        delta = -25  # ❌ Drawdown > 50% → score drops
    elif abs_dd > 0.30:
        delta = -15
    elif abs_dd < 0.10:
        delta = +10  # ✅ Low drawdown → score rises
    elif abs_dd < 0.20:
        delta = +5
    else:
        delta = 0
    score += delta
    breakdown['drawdown'] = delta

    # Volatility impact (higher vol = LESS robust → score decreases)
    if volatility > 1.0:
        delta = -10  # ❌ Volatility > 100% → score drops
    elif volatility > 0.60:
        delta = -5
    elif volatility < 0.20:
        delta = +10  # ✅ Low volatility → score rises
    elif volatility < 0.40:
        delta = +5
    else:
        delta = 0
    score += delta
    breakdown['volatility'] = delta

    # Clamp score to [0, 100]
    score = max(0, min(100, score))

    # Map to level using canonical function
    level = score_to_level(score)

    return {
        "score": score,
        "level": level,
        "breakdown": breakdown
    }
