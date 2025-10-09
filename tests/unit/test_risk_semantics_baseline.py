"""
Baseline Test Suite - Risk Score Semantics Refactoring

Tests de référence pour valider la refonte du Risk Score.
Capture l'état actuel (legacy) et définit les attentes post-refonte.

5 portfolios type:
- Degen: 55% memes, HHI 3.23 → Risk attendu ~30, Stables ~70%
- Agressif: 70% alts, HHI 1.2 → Risk ~45, Stables ~55%
- Équilibré: 30% BTC, 30% ETH, 30% alts → Risk ~65, Stables ~35%
- Conservateur: 50% BTC, 30% ETH, 20% stables → Risk ~80, Stables ~25%
- Ultra-safe: 70% BTC, 30% ETH → Risk ~90, Stables ~15%
"""

import pytest
import numpy as np
from typing import Dict, List, Any


# ============================================================================
# PORTFOLIO TEST DATA
# ============================================================================

PORTFOLIOS = {
    "degen": {
        "name": "Degen (55% Memes)",
        "assets": [
            {"symbol": "PEPE", "group": "Memecoins", "value_usd": 25000, "age_days": 90},
            {"symbol": "BONK", "group": "Memecoins", "value_usd": 20000, "age_days": 110},
            {"symbol": "DOGE", "group": "Memecoins", "value_usd": 10000, "age_days": 365},
            {"symbol": "SOL", "group": "SOL", "value_usd": 15000, "age_days": 180},
            {"symbol": "ETH", "group": "ETH", "value_usd": 5000, "age_days": 365},
            {"symbol": "BTC", "group": "BTC", "value_usd": 3000, "age_days": 365},
            {"symbol": "USDC", "group": "Stablecoins", "value_usd": 2000, "age_days": 365},
        ],
        "expected_legacy": {
            "risk_score_v1": 60,  # Actuel (trop élevé)
            "structural_score": 77,  # Actuel (trop élevé)
            "stables_target": 66,
        },
        "expected_v2": {
            "risk_score_v1": 30,  # Après Dual-Window fix
            "structural_score": 25,  # Après redesign pénalités
            "stables_target": 70,  # Après RiskCap fix
            "tolerance": 5,  # ±5pts acceptable
        },
    },
    "aggressive": {
        "name": "Agressif (70% Alts)",
        "assets": [
            {"symbol": "SOL", "group": "SOL", "value_usd": 30000, "age_days": 200},
            {"symbol": "AVAX", "group": "L1/L0 majors", "value_usd": 20000, "age_days": 250},
            {"symbol": "ARB", "group": "L2/Scaling", "value_usd": 10000, "age_days": 150},
            {"symbol": "UNI", "group": "DeFi", "value_usd": 10000, "age_days": 300},
            {"symbol": "BTC", "group": "BTC", "value_usd": 15000, "age_days": 365},
            {"symbol": "ETH", "group": "ETH", "value_usd": 10000, "age_days": 365},
            {"symbol": "USDC", "group": "Stablecoins", "value_usd": 5000, "age_days": 365},
        ],
        "expected_v2": {
            "risk_score_v1": 45,
            "structural_score": 50,
            "stables_target": 55,
            "tolerance": 5,
        },
    },
    "balanced": {
        "name": "Équilibré (30/30/30)",
        "assets": [
            {"symbol": "BTC", "group": "BTC", "value_usd": 30000, "age_days": 365},
            {"symbol": "ETH", "group": "ETH", "value_usd": 30000, "age_days": 365},
            {"symbol": "SOL", "group": "SOL", "value_usd": 10000, "age_days": 250},
            {"symbol": "AVAX", "group": "L1/L0 majors", "value_usd": 10000, "age_days": 280},
            {"symbol": "ARB", "group": "L2/Scaling", "value_usd": 5000, "age_days": 180},
            {"symbol": "UNI", "group": "DeFi", "value_usd": 5000, "age_days": 300},
            {"symbol": "USDC", "group": "Stablecoins", "value_usd": 10000, "age_days": 365},
        ],
        "expected_v2": {
            "risk_score_v1": 65,
            "structural_score": 70,
            "stables_target": 35,
            "tolerance": 5,
        },
    },
    "conservative": {
        "name": "Conservateur (50% BTC, 30% ETH)",
        "assets": [
            {"symbol": "BTC", "group": "BTC", "value_usd": 50000, "age_days": 365},
            {"symbol": "ETH", "group": "ETH", "value_usd": 30000, "age_days": 365},
            {"symbol": "USDC", "group": "Stablecoins", "value_usd": 20000, "age_days": 365},
        ],
        "expected_v2": {
            "risk_score_v1": 80,
            "structural_score": 85,
            "stables_target": 25,
            "tolerance": 5,
        },
    },
    "ultra_safe": {
        "name": "Ultra-Safe (70% BTC, 30% ETH)",
        "assets": [
            {"symbol": "BTC", "group": "BTC", "value_usd": 70000, "age_days": 365},
            {"symbol": "ETH", "group": "ETH", "value_usd": 30000, "age_days": 365},
        ],
        "expected_v2": {
            "risk_score_v1": 90,
            "structural_score": 95,
            "stables_target": 15,
            "tolerance": 5,
        },
    },
}


# ============================================================================
# HELPER FUNCTIONS (calculateurs simplifiés pour tests)
# ============================================================================

def calculate_hhi(assets: List[Dict[str, Any]]) -> float:
    """Calculate Herfindahl-Hirschman Index (concentration)"""
    total_value = sum(a["value_usd"] for a in assets)
    if total_value == 0:
        return 0.0

    weights = [a["value_usd"] / total_value for a in assets]
    hhi = sum(w**2 for w in weights)
    return round(hhi, 4)


def calculate_top5_concentration(assets: List[Dict[str, Any]]) -> float:
    """Calculate Top 5 concentration (should be ≤100%)"""
    total_value = sum(a["value_usd"] for a in assets)
    if total_value == 0:
        return 0.0

    # Asset-level weights (normalized to 1.0)
    weights = np.array([a["value_usd"] for a in assets]) / total_value

    # Top 5 assets
    top5_weights = np.sort(weights)[-5:] if len(weights) >= 5 else weights
    top5_concentration = float(np.sum(top5_weights)) * 100.0

    # MUST be ≤100%
    assert top5_concentration <= 100.0, f"Top5 concentration {top5_concentration}% > 100% (BUG!)"

    return round(top5_concentration, 1)


def calculate_gri(assets: List[Dict[str, Any]]) -> float:
    """Calculate Group Risk Index (0-10, high = risky)"""
    # Group concentration
    groups = {}
    total_value = sum(a["value_usd"] for a in assets)

    for asset in assets:
        group = asset["group"]
        groups[group] = groups.get(group, 0) + asset["value_usd"]

    group_weights = [v / total_value for v in groups.values()]
    group_hhi = sum(w**2 for w in group_weights)

    # GRI score (0-10, high = concentration risk)
    gri = min(10.0, group_hhi * 15.0)
    return round(gri, 1)


def calculate_memes_pct(assets: List[Dict[str, Any]]) -> float:
    """Calculate memecoins percentage"""
    total_value = sum(a["value_usd"] for a in assets)
    memes_value = sum(a["value_usd"] for a in assets if a["group"] == "Memecoins")
    return round((memes_value / total_value * 100) if total_value > 0 else 0, 1)


def calculate_effective_assets(assets: List[Dict[str, Any]]) -> int:
    """Calculate effective number of assets (>1% each)"""
    total_value = sum(a["value_usd"] for a in assets)
    return sum(1 for a in assets if (a["value_usd"] / total_value) > 0.01)


# ============================================================================
# TESTS - PORTFOLIO METRICS CALCULATION
# ============================================================================

@pytest.mark.parametrize("portfolio_key", ["degen", "aggressive", "balanced", "conservative", "ultra_safe"])
def test_portfolio_metrics_calculation(portfolio_key):
    """Test basic metrics calculation for each portfolio type"""
    portfolio = PORTFOLIOS[portfolio_key]
    assets = portfolio["assets"]

    # Calculate metrics
    hhi = calculate_hhi(assets)
    top5 = calculate_top5_concentration(assets)
    gri = calculate_gri(assets)
    memes_pct = calculate_memes_pct(assets)
    eff_assets = calculate_effective_assets(assets)

    # Sanity checks
    assert 0 <= hhi <= 1.0, f"{portfolio['name']}: HHI should be in [0, 1]"
    assert 0 <= top5 <= 100, f"{portfolio['name']}: Top5 should be in [0%, 100%]"
    assert 0 <= gri <= 10, f"{portfolio['name']}: GRI should be in [0, 10]"
    assert 0 <= memes_pct <= 100, f"{portfolio['name']}: Memes% should be in [0%, 100%]"
    assert eff_assets >= 0, f"{portfolio['name']}: Effective assets should be ≥0"

    print(f"\n{portfolio['name']} Metrics:")
    print(f"  HHI: {hhi:.4f}")
    print(f"  Top5: {top5:.1f}%")
    print(f"  GRI: {gri:.1f}/10")
    print(f"  Memes: {memes_pct:.1f}%")
    print(f"  Effective Assets: {eff_assets}")


def test_degen_portfolio_high_concentration():
    """Degen portfolio should have extreme concentration metrics"""
    assets = PORTFOLIOS["degen"]["assets"]

    hhi = calculate_hhi(assets)
    gri = calculate_gri(assets)
    memes_pct = calculate_memes_pct(assets)

    # Degen = high risk indicators
    assert hhi > 0.15, "Degen portfolio should have high HHI (concentration)"
    assert gri > 5.0, "Degen portfolio should have high GRI"
    assert memes_pct > 50.0, "Degen portfolio should have >50% memecoins"


def test_ultra_safe_portfolio_low_concentration():
    """Ultra-safe portfolio should have low concentration metrics"""
    assets = PORTFOLIOS["ultra_safe"]["assets"]

    hhi = calculate_hhi(assets)
    gri = calculate_gri(assets)
    memes_pct = calculate_memes_pct(assets)

    # Ultra-safe = low risk indicators
    assert hhi < 0.60, "Ultra-safe portfolio should have low HHI"
    assert gri < 8.0, "Ultra-safe portfolio should have low-medium GRI"
    assert memes_pct == 0.0, "Ultra-safe portfolio should have 0% memecoins"


# ============================================================================
# TESTS - MONOTONICITY (Risk Score vs Metrics)
# ============================================================================

def test_risk_score_decreases_with_concentration():
    """Risk Score should decrease (less robust) as concentration increases"""
    # À implémenter après Phase 3 (Dual-Window fix)
    # Pour l'instant, capture baseline
    pass


def test_structural_score_decreases_with_memes():
    """Structural Score should decrease as memecoins % increases"""
    # À implémenter après Phase 4 (Structural redesign)
    # Pour l'instant, capture baseline
    pass


def test_stables_target_increases_with_fragility():
    """Stables target should increase as Risk Score decreases (more fragile)"""
    # À implémenter après Phase 2 (RiskCap fix)
    # Pour l'instant, juste documenter attente

    # Expected behavior (post-fix):
    # - Degen (Risk ~30) → Stables ~70%
    # - Conservative (Risk ~80) → Stables ~25%
    # - Ultra-safe (Risk ~90) → Stables ~15%
    pass


# ============================================================================
# TESTS - DUAL-WINDOW PENALTIES
# ============================================================================

def test_dual_window_penalty_triggers_on_low_coverage():
    """Dual-Window should apply penalties when coverage <80% or days <120"""
    # À implémenter après Phase 3
    pass


def test_dual_window_excludes_young_memes():
    """Assets <120 days should be penalized if memecoins"""
    assets = PORTFOLIOS["degen"]["assets"]

    # PEPE (90d), BONK (110d) sont jeunes ET memes
    young_memes = [a for a in assets if a["group"] == "Memecoins" and a["age_days"] < 120]

    assert len(young_memes) >= 2, "Degen portfolio should have ≥2 young memecoins"

    # Après Phase 3: ces assets doivent pénaliser le Risk Score
    # Expected: -10 à -25 pts sur Risk Score final


# ============================================================================
# TESTS - BUG FIXES
# ============================================================================

def test_top5_never_exceeds_100_percent():
    """Bug fix: Top5 concentration should NEVER exceed 100%"""
    for portfolio_key, portfolio in PORTFOLIOS.items():
        assets = portfolio["assets"]
        top5 = calculate_top5_concentration(assets)

        assert top5 <= 100.0, (
            f"{portfolio['name']}: Top5={top5:.1f}% >100% (BUG DETECTED!)\n"
            f"This indicates mixing group-level and asset-level calculations."
        )


def test_hhi_normalized_to_one():
    """HHI should be normalized to [0, 1] range"""
    for portfolio_key, portfolio in PORTFOLIOS.items():
        assets = portfolio["assets"]
        hhi = calculate_hhi(assets)

        assert 0 <= hhi <= 1.0, (
            f"{portfolio['name']}: HHI={hhi:.4f} out of range [0, 1]\n"
            f"HHI should use asset-level weights normalized to 1.0"
        )


# ============================================================================
# BASELINE CAPTURE (for regression testing)
# ============================================================================

def test_capture_legacy_baseline(tmp_path):
    """Capture current (legacy) scores as baseline for comparison"""
    import json

    baseline = {}
    for portfolio_key, portfolio in PORTFOLIOS.items():
        assets = portfolio["assets"]

        baseline[portfolio_key] = {
            "name": portfolio["name"],
            "metrics": {
                "hhi": calculate_hhi(assets),
                "top5": calculate_top5_concentration(assets),
                "gri": calculate_gri(assets),
                "memes_pct": calculate_memes_pct(assets),
                "effective_assets": calculate_effective_assets(assets),
            },
            "expected_v2": portfolio.get("expected_v2", {}),
            "expected_legacy": portfolio.get("expected_legacy", {}),
        }

    # Save baseline
    baseline_file = tmp_path / "baseline_legacy.json"
    with open(baseline_file, "w") as f:
        json.dump(baseline, f, indent=2)

    print(f"\n[OK] Baseline captured at: {baseline_file}")
    print(json.dumps(baseline, indent=2))


# ============================================================================
# MAIN (for manual testing)
# ============================================================================

if __name__ == "__main__":
    # Run metrics calculation for all portfolios
    print("=" * 80)
    print("BASELINE PORTFOLIO METRICS")
    print("=" * 80)

    for key, portfolio in PORTFOLIOS.items():
        assets = portfolio["assets"]
        print(f"\n{portfolio['name']}:")
        print(f"  Assets: {len(assets)}")
        print(f"  Total Value: ${sum(a['value_usd'] for a in assets):,.0f}")
        print(f"  HHI: {calculate_hhi(assets):.4f}")
        print(f"  Top5: {calculate_top5_concentration(assets):.1f}%")
        print(f"  GRI: {calculate_gri(assets):.1f}/10")
        print(f"  Memes%: {calculate_memes_pct(assets):.1f}%")
        print(f"  Effective Assets: {calculate_effective_assets(assets)}")

        if "expected_v2" in portfolio:
            exp = portfolio["expected_v2"]
            print(f"  Expected v2:")
            print(f"    - Risk Score: {exp['risk_score_v1']}")
            print(f"    - Structural: {exp['structural_score']}")
            print(f"    - Stables: {exp['stables_target']}%")
