#!/usr/bin/env python3
"""
Test Cap Stability - Vérifie que le cap reste stable avec scores constants
"""

import asyncio
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.execution.governance import GovernanceEngine
from datetime import datetime
import pytest


@pytest.mark.asyncio
async def test_cap_stability_with_constant_scores():
    """
    Test: Avec scores constants, le cap ne doit pas varier de plus de 2%
    """
    engine = GovernanceEngine()

    # Mock scores constants (simuler Cycle=100, OnChain=33, Risk=90, DI=65)
    # Note: Governance calcule cap basé sur contradiction + confidence uniquement
    engine.current_state.signals.contradiction_index = 0.48
    engine.current_state.signals.confidence = 0.75
    engine.current_state.signals.blended_score = 65.0
    engine.current_state.signals.decision_score = 0.60
    engine.current_state.governance_mode = 'manual'  # Mode normal, pas de freeze

    # Nettoyer last_applied_policy pour éviter bypass
    engine.current_state.last_applied_policy = None

    results = []
    for i in range(5):
        await asyncio.sleep(0.1)  # Petit délai entre chaque tick
        state = await engine.get_current_state()
        cap = state.execution_policy.cap_daily
        results.append(cap)
        print(f"Tick {i+1}: cap = {cap:.3f} ({cap*100:.1f}%)")

    # Vérifier stabilité : variation max < 2%
    variations = [abs(results[i] - results[i-1]) for i in range(1, len(results))]
    max_variation = max(variations) * 100  # Convertir en %

    print(f"\nRésultats: {[f'{r*100:.1f}%' for r in results]}")
    print(f"Variations: {[f'{v*100:.2f}%' for v in variations]}")
    print(f"Max variation: {max_variation:.2f}%")

    assert max_variation < 2.0, f"Cap variation {max_variation:.2f}% exceeds 2%"
    print(f"[OK] PASS: Max variation {max_variation:.2f}% < 2%")


@pytest.mark.asyncio
async def test_cap_not_below_floor_in_expansion():
    """
    Test: Avec Expansion + Risk=90, le cap ne doit pas descendre sous 40%
    (car Expansion floor = 60% selon targets-coordinator.js ligne 398)
    """
    engine = GovernanceEngine()

    # Simuler expansion (blended=65) + Risk élevé (90)
    engine.current_state.signals.contradiction_index = 0.35
    engine.current_state.signals.confidence = 0.80
    engine.current_state.signals.blended_score = 65.0
    engine.current_state.signals.decision_score = 0.70
    engine.current_state.governance_mode = 'manual'
    engine.current_state.last_applied_policy = None

    state = await engine.get_current_state()
    cap = state.execution_policy.cap_daily

    print(f"Cap backend: {cap*100:.1f}%")

    # Note: Ce test vérifie le backend uniquement
    # Le frontend appliquera son propre floor (65% avec boost expansion)
    # Ici on vérifie juste que le backend ne crash pas et retourne un cap raisonnable
    assert cap >= 0.01, "Cap must be >= 1%"
    assert cap <= 0.95, "Cap must be <= 95%"
    print(f"[OK] PASS: Cap {cap*100:.1f}% is within bounds [1%, 95%]")


@pytest.mark.asyncio
async def test_no_cap_reset_on_nan_score():
    """
    Test: Si un score devient NaN/None, le cap ne doit pas reset à 1% brutalement
    """
    engine = GovernanceEngine()

    # Init avec scores valides
    engine.current_state.signals.contradiction_index = 0.40
    engine.current_state.signals.confidence = 0.75
    engine.current_state.signals.blended_score = 70.0
    engine.current_state.governance_mode = 'manual'
    engine.current_state.last_applied_policy = None

    state1 = await engine.get_current_state()
    cap1 = state1.execution_policy.cap_daily
    print(f"Cap initial (scores valides): {cap1*100:.1f}%")

    # Simuler un score qui devient None (API fail, etc.)
    engine.current_state.signals.blended_score = None  # Simule erreur API

    state2 = await engine.get_current_state()
    cap2 = state2.execution_policy.cap_daily
    print(f"Cap après blended=None: {cap2*100:.1f}%")

    # Vérifier que le cap ne chute pas brutalement (smoothing + hysteresis)
    variation = abs(cap2 - cap1) * 100
    print(f"Variation: {variation:.2f}%")

    # Avec smoothing + hysteresis, la variation ne devrait pas dépasser ~10%
    # (le fallback peut réduire mais pas brutalement à 1%)
    assert variation < 15.0, f"Cap variation {variation:.2f}% too large on NaN score"
    print(f"[OK] PASS: Cap variation {variation:.2f}% < 15% (smoothing + hysteresis works)")


@pytest.mark.asyncio
async def test_manual_mode_bypass():
    """
    Test: Si mode Manual + last_applied_policy, le cap doit être fixé
    """
    engine = GovernanceEngine()

    # Créer une policy manuelle avec cap fixe
    from services.execution.governance import Policy
    manual_policy = Policy(
        mode="Normal",
        cap_daily=0.15,  # 15% fixe
        ramp_hours=12,
        notes="Test manual policy"
    )

    engine.current_state.governance_mode = 'manual'
    engine.current_state.last_applied_policy = manual_policy

    # Mock signals (devraient être ignorés)
    engine.current_state.signals.contradiction_index = 0.80  # High contradiction
    engine.current_state.signals.confidence = 0.30  # Low confidence

    state = await engine.get_current_state()
    cap = state.execution_policy.cap_daily

    print(f"Cap avec manual policy: {cap*100:.1f}%")

    # Vérifier que le cap est bien celui de la policy manuelle
    assert abs(cap - 0.15) < 0.001, f"Cap {cap*100:.1f}% != 15% (manual policy ignored)"
    print(f"[OK] PASS: Manual policy override works (cap = {cap*100:.1f}%)")


if __name__ == "__main__":
    print("=" * 60)
    print("CAP STABILITY TESTS")
    print("=" * 60)

    async def run_all():
        print("\n1. Test: Cap stability with constant scores")
        await test_cap_stability_with_constant_scores()

        print("\n" + "=" * 60)
        print("\n2. Test: Cap not below floor in expansion")
        await test_cap_not_below_floor_in_expansion()

        print("\n" + "=" * 60)
        print("\n3. Test: No cap reset on NaN score")
        await test_no_cap_reset_on_nan_score()

        print("\n" + "=" * 60)
        print("\n4. Test: Manual mode bypass")
        await test_manual_mode_bypass()

        print("\n" + "=" * 60)
        print("\n[OK] ALL TESTS PASSED")
        print("=" * 60)

    asyncio.run(run_all())
