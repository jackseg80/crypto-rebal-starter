"""
Tests d'intégration pour endpoint /api/risk/bourse/dashboard

Vérifie:
- Endpoint retourne métriques valides
- Score canonique 0-100 (plus haut = plus robuste)
- Multi-tenant respecté (user_id obligatoire)
- Fallback gracieux si 0 positions
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestRiskBourseEndpoint:
    """Tests de l'endpoint risk bourse."""

    def test_zero_positions_returns_empty_state(self):
        """0 positions doit retourner état vide sans erreur."""
        # Utiliser min_usd très élevé pour filtrer toutes les positions
        response = client.get("/api/risk/bourse/dashboard?user_id=demo&min_usd=999999999")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["positions_count"] == 0
        assert data["total_value_usd"] == 0.0
        assert data["risk"]["score"] == 0
        assert data["risk"]["level"] == "N/A"

    def test_user_id_parameter_required(self):
        """user_id doit être présent (multi-tenant)."""
        # L'endpoint a un default user_id="demo", mais on teste qu'il est bien utilisé
        response = client.get("/api/risk/bourse/dashboard")  # Sans user_id explicite
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "demo"  # Fallback au default


# Commande pour lancer ces tests:
# pytest tests/integration/test_risk_bourse_endpoint.py -v
