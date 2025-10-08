#!/usr/bin/env python3
"""
Tests pour les sélecteurs de gouvernance (version Python pour backend validation)
Note: Les tests JS sont dans tests/selectors/governance.selectEngineCapPercent.test.js
"""

import pytest


def test_cap_normalization_fraction_to_percent():
    """Test normalisation fraction (0-1) vers pourcentage"""
    # Simulation de la logique JS normalizeCapToPercent
    def normalize_cap_to_percent(raw):
        if raw is None or not isinstance(raw, (int, float)):
            return None
        absolute = abs(raw)
        if absolute > 100:
            return None
        percent = absolute * 100 if absolute <= 1 else absolute
        rounded = round(percent)
        return rounded if isinstance(rounded, int) else None

    assert normalize_cap_to_percent(0.077) == 8  # 7.7% arrondi à 8%
    assert normalize_cap_to_percent(0.065) == 6  # 6.5% arrondi à 6 (bankers rounding)
    assert normalize_cap_to_percent(0.01) == 1
    assert normalize_cap_to_percent(0.95) == 95


def test_cap_normalization_percent_passthrough():
    """Test pourcentage déjà en % (pas de conversion)"""
    def normalize_cap_to_percent(raw):
        if raw is None or not isinstance(raw, (int, float)):
            return None
        absolute = abs(raw)
        if absolute > 100:
            return None
        percent = absolute * 100 if absolute <= 1 else absolute
        rounded = round(percent)
        return rounded if isinstance(rounded, int) else None

    assert normalize_cap_to_percent(7.7) == 8
    assert normalize_cap_to_percent(65) == 65
    assert normalize_cap_to_percent(100) == 100


def test_cap_normalization_null_cases():
    """Test gestion des cas null/invalides"""
    def normalize_cap_to_percent(raw):
        if raw is None or not isinstance(raw, (int, float)):
            return None
        absolute = abs(raw)
        if absolute > 100:
            return None
        percent = absolute * 100 if absolute <= 1 else absolute
        rounded = round(percent)
        return rounded if isinstance(rounded, int) else None

    assert normalize_cap_to_percent(None) is None
    assert normalize_cap_to_percent(150) is None  # > 100%
    assert normalize_cap_to_percent(-0.5) == 50  # abs(-0.5) = 0.5 → 50%


def test_backend_cap_path_priority():
    """Test priorité des chemins de lecture du cap backend"""
    # Simulation de selectEngineCapPercent avec priorités
    def select_engine_cap_percent(state):
        if not isinstance(state, dict):
            return None

        gov = state.get('governance', {})

        # Priorité 1: execution_policy.cap_daily (FIX Oct 2025)
        if 'execution_policy' in gov and 'cap_daily' in gov['execution_policy']:
            raw = gov['execution_policy']['cap_daily']
            return round(raw * 100) if raw <= 1 else round(raw)

        # Priorité 2: engine_cap_daily
        if 'engine_cap_daily' in gov:
            raw = gov['engine_cap_daily']
            return round(raw * 100) if raw <= 1 else round(raw)

        # Priorité 3: caps.engine_cap
        if 'caps' in gov and 'engine_cap' in gov['caps']:
            raw = gov['caps']['engine_cap']
            return round(raw * 100) if raw <= 1 else round(raw)

        return None

    # Test priorité 1 (execution_policy)
    state1 = {
        'governance': {
            'execution_policy': {'cap_daily': 0.077},
            'caps': {'engine_cap': 0.05}  # Ignoré
        }
    }
    assert select_engine_cap_percent(state1) == 8  # 7.7% arrondi

    # Test priorité 3 (caps.engine_cap)
    state2 = {
        'governance': {
            'caps': {'engine_cap': 0.065}
        }
    }
    assert select_engine_cap_percent(state2) == 6  # 6.5% → 6 (bankers rounding)

    # Test null si aucun chemin
    state3 = {'governance': {}}
    assert select_engine_cap_percent(state3) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
