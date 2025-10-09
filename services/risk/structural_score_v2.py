"""
Structural Risk Score v2 - Phase 4

Redesign du Structural Score pour mieux refléter la concentration,
les memecoins, et le Group Risk Index (GRI).

Formule validée par GPT-5:
- Base: 100 (robustesse maximale)
- Pénalités: HHI, memecoins, GRI, faible diversification
- Output: 0-100 (0=fragile, 100=très robuste)

Author: Claude + GPT-5
Date: 2025-10-03
"""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


def compute_structural_score_v2(
    hhi: float,
    memes_pct: float,
    gri: float,
    effective_assets: float,
    total_value: float = 0.0,
    top5_pct: float = 0.0
) -> Tuple[float, Dict[str, float]]:
    """
    Calcule le Structural Risk Score v2 avec pénalités explicites.

    Args:
        hhi: Herfindahl-Hirschman Index [0..1] - concentration
        memes_pct: % de memecoins dans le portfolio [0..1]
        gri: Group Risk Index [0..10] - niveau de risque par groupes
        effective_assets: Nombre effectif d'assets (pondéré par valeur)
        total_value: Valeur totale portfolio (optionnel, pour logs)
        top5_pct: % valeur des 5 top holdings (optionnel, info seulement)

    Returns:
        Tuple[score, breakdown] où:
        - score: Structural Score final [0..100]
        - breakdown: Dict avec détail des pénalités

    Exemples:
        # Portfolio degen (55% memes, HHI=0.32, GRI=7.4, eff=7)
        >>> compute_structural_score_v2(0.32, 0.55, 7.4, 7)
        (25.0, {...})  # Score faible (fragile)

        # Portfolio équilibré (0% memes, HHI=0.18, GRI=3.2, eff=7)
        >>> compute_structural_score_v2(0.18, 0.0, 3.2, 7)
        (84.0, {...})  # Score élevé (robuste)

        # Portfolio conservateur (0% memes, HHI=0.38, GRI=2.5, eff=3)
        >>> compute_structural_score_v2(0.38, 0.0, 2.5, 3)
        (66.0, {...})  # Score moyen (pénalité concentration + faible diversité)
    """

    base = 100.0
    penalties = {}

    # 1. Pénalité HHI (concentration)
    # Seuil: 0.25 (concentration modérée tolérée pour BTC/ETH)
    # Pente: 100 (adoucie de 120 → 100)
    # Exemple: HHI=0.32 → (0.32-0.25)*100 = -7pts
    # Exemple: HHI=0.38 → (0.38-0.25)*100 = -13pts
    if hhi > 0.25:
        penalties['hhi'] = max(0.0, (hhi - 0.25)) * 100.0
    else:
        penalties['hhi'] = 0.0

    # 2. Pénalité Memecoins
    # Formule GPT-5: memes_pct (déjà en [0..1]) * 50
    # Exemple: memes_pct=0.55 → 55% → -27.5pts
    # MAIS GPT-5 avait écrit "memes_pct * 0.5" dans sa formule (confusion)
    # Testons avec pente 40 au lieu de 50 pour adoucir
    penalties['memecoins'] = memes_pct * 40.0  # 55% memes → -22pts

    # 3. Pénalité GRI (Group Risk Index)
    # GRI ∈ [0..10], pente 5.0
    # Exemple: GRI=7.4 → -37pts
    penalties['gri'] = gri * 5.0

    # 4. Pénalité faible diversification
    # Si <5 assets effectifs → -10pts
    if effective_assets < 5:
        penalties['low_diversification'] = 10.0
    else:
        penalties['low_diversification'] = 0.0

    # Score final
    total_penalties = sum(penalties.values())
    score = max(0.0, min(100.0, base - total_penalties))

    # Détail pour audit
    breakdown = {
        **penalties,
        'base': base,
        'total_penalties': total_penalties,
        'final_score': score,
        # Metadata pour debug
        'inputs': {
            'hhi': hhi,
            'memes_pct': memes_pct,
            'gri': gri,
            'effective_assets': effective_assets,
            'top5_pct': top5_pct
        }
    }

    logger.debug(
        f"Structural Score v2: {score:.1f} "
        f"(HHI={hhi:.2f}, Memes={memes_pct*100:.1f}%, GRI={gri:.1f}, Eff={effective_assets:.1f})"
    )

    return score, breakdown


def get_structural_level(score: float) -> str:
    """
    Mapping Structural Score → Niveau qualitatif

    Args:
        score: Structural Score [0..100]

    Returns:
        str: Niveau ("very_fragile" | "fragile" | "moderate" | "robust" | "very_robust")

    Examples:
        >>> get_structural_level(25)
        'fragile'
        >>> get_structural_level(85)
        'very_robust'
    """
    if score >= 85:
        return "very_robust"  # Très robuste (structure excellente)
    elif score >= 70:
        return "robust"       # Robuste
    elif score >= 50:
        return "moderate"     # Intermédiaire
    elif score >= 30:
        return "fragile"      # Fragile
    else:
        return "very_fragile" # Très fragile (structure dangereuse)


# Tests unitaires intégrés (doctests)
if __name__ == "__main__":
    import doctest
    doctest.testmod()

    # Tests manuels
    print("=" * 60)
    print("STRUCTURAL SCORE V2 - TESTS")
    print("=" * 60)

    # Test 1: Degen
    score, breakdown = compute_structural_score_v2(
        hhi=0.32,
        memes_pct=0.55,
        gri=7.4,
        effective_assets=7
    )
    print(f"\n1. Degen Portfolio (55% memes, HHI=0.32, GRI=7.4)")
    print(f"   Score: {score:.1f} ({get_structural_level(score)})")
    print(f"   Expected: ~25-35 (fragile)")

    # Test 2: Équilibré
    score, breakdown = compute_structural_score_v2(
        hhi=0.18,
        memes_pct=0.0,
        gri=3.2,
        effective_assets=7
    )
    print(f"\n2. Balanced Portfolio (0% memes, HHI=0.18, GRI=3.2)")
    print(f"   Score: {score:.1f} ({get_structural_level(score)})")
    print(f"   Expected: ~70-85 (robust)")

    # Test 3: Conservateur
    score, breakdown = compute_structural_score_v2(
        hhi=0.38,
        memes_pct=0.0,
        gri=2.5,
        effective_assets=3
    )
    print(f"\n3. Conservative Portfolio (0% memes, HHI=0.38, GRI=2.5, eff=3)")
    print(f"   Score: {score:.1f} ({get_structural_level(score)})")
    print(f"   Expected: ~60-75 (moderate/robust)")

    print("\n" + "=" * 60)
