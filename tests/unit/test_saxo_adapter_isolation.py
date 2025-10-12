"""
Tests d'isolation multi-tenant pour saxo_adapter
Vérifie que les users ne voient QUE leurs propres données Saxo
"""
import pytest
from pathlib import Path
from adapters.saxo_adapter import _load_snapshot, list_portfolios_overview, get_portfolio_detail


def test_load_snapshot_user_without_data_returns_empty():
    """
    Bug fix test: Un user sans données Saxo ne doit PAS voir les données d'autres users.

    Contexte: Avant le fix (Oct 2025), si user_id était fourni mais qu'aucune donnée
    n'était trouvée dans les sources, le code fallback vers le fichier legacy partagé,
    causant une violation de l'isolation multi-tenant.

    Symptôme: Tous les users voyaient le portfolio de jack (28 positions).

    Solution: Si user_id est fourni mais pas de données → retourner snapshot vide,
    pas de fallback vers legacy partagé.
    """
    # User sans données Saxo
    snapshot = _load_snapshot(user_id="nonexistent_user_xyz")

    # Doit retourner un snapshot vide (pas les données d'un autre user)
    assert snapshot == {"portfolios": []}, "User sans données doit voir snapshot vide"


def test_list_portfolios_overview_user_isolation():
    """
    Vérifie que list_portfolios_overview() respecte l'isolation par user.
    """
    # User sans données
    portfolios_empty = list_portfolios_overview(user_id="test_user_empty")
    assert portfolios_empty == [], "User sans données doit voir liste vide"

    # User avec données (si jack existe)
    portfolios_jack = list_portfolios_overview(user_id="jack")
    # Si jack a des données, la liste ne doit pas être vide
    # (mais on ne teste pas le contenu exact car dépend de l'état du système)
    assert isinstance(portfolios_jack, list), "Doit retourner une liste"


def test_get_portfolio_detail_user_isolation():
    """
    Vérifie que get_portfolio_detail() respecte l'isolation par user.
    """
    # User sans données
    portfolio_empty = get_portfolio_detail("fake_portfolio_id", user_id="test_user_empty")
    assert portfolio_empty == {}, "User sans données doit voir dict vide"


def test_load_snapshot_legacy_mode_still_works():
    """
    Vérifie que le mode legacy (user_id=None) fonctionne toujours.

    Le fallback vers data/wealth/saxo_snapshot.json ne doit se faire
    QUE si user_id est None (mode compatibilité).
    """
    # Mode legacy (pas de user_id)
    snapshot_legacy = _load_snapshot(user_id=None)

    # Doit retourner un snapshot (soit legacy, soit vide si pas de fichier)
    assert isinstance(snapshot_legacy, dict), "Mode legacy doit retourner un dict"
    assert "portfolios" in snapshot_legacy, "Snapshot doit avoir clé portfolios"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
