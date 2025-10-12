"""
Tests de sécurité pour les endpoints de performance
Vérifie que les protections dev_guards fonctionnent correctement
"""
import pytest
from unittest.mock import patch, Mock
from fastapi import status


# ============================================================================
# Tests des endpoints NON protégés (accessibles en dev et prod)
# ============================================================================

def test_cache_stats_accessible_dev(test_client):
    """GET /cache/stats doit être accessible en développement"""
    response = test_client.get("/api/performance/cache/stats")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "cache_stats" in data
    assert "memory_cache_size" in data["cache_stats"]


def test_cache_stats_accessible_prod(test_client):
    """GET /cache/stats doit être accessible en production (pas protégé)"""
    with patch('config.settings.settings') as mock_settings:
        mock_settings.environment = "production"
        mock_settings.debug = False

        response = test_client.get("/api/performance/cache/stats")
        assert response.status_code == 200


def test_system_memory_accessible_dev(test_client):
    """GET /system/memory doit être accessible en développement"""
    response = test_client.get("/api/performance/system/memory")

    # Peut retourner 200 (psutil installé) ou 500 (psutil manquant)
    assert response.status_code in [200, 500]


# ============================================================================
# Tests des endpoints PROTÉGÉS en mode développement (doivent fonctionner)
# ============================================================================

def test_cache_clear_allowed_in_dev(test_client):
    """POST /cache/clear doit fonctionner en développement"""
    with patch('config.settings.settings') as mock_settings:
        mock_settings.environment = "development"
        mock_settings.debug = True

        response = test_client.post("/api/performance/cache/clear?older_than_days=7")

        # Peut réussir (200) ou échouer pour raisons métier (500), mais pas 403
        assert response.status_code != status.HTTP_403_FORBIDDEN


def test_benchmark_allowed_in_dev(test_client):
    """GET /optimization/benchmark doit fonctionner en développement"""
    with patch('config.settings.settings') as mock_settings:
        mock_settings.environment = "development"
        mock_settings.debug = True

        response = test_client.get("/api/performance/optimization/benchmark?n_assets=10&n_periods=50")

        # Peut réussir (200) ou échouer pour raisons métier (500), mais pas 403
        assert response.status_code != status.HTTP_403_FORBIDDEN


def test_precompute_allowed_in_dev(test_client):
    """POST /optimization/precompute doit fonctionner en développement"""
    with patch('config.settings.settings') as mock_settings:
        mock_settings.environment = "development"
        mock_settings.debug = True

        response = test_client.post("/api/performance/optimization/precompute?n_assets=5")

        # Peut réussir (200) ou échouer pour raisons métier (400/500), mais pas 403
        assert response.status_code != status.HTTP_403_FORBIDDEN


# ============================================================================
# Tests des endpoints PROTÉGÉS en mode production (doivent retourner 403)
# ============================================================================

def test_cache_clear_blocked_in_prod(test_client):
    """POST /cache/clear doit être bloqué en production"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        response = test_client.post("/api/performance/cache/clear")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert "detail" in data
        assert "endpoint_disabled_in_production" in str(data["detail"])


def test_benchmark_blocked_in_prod(test_client):
    """GET /optimization/benchmark doit être bloqué en production"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        response = test_client.get("/api/performance/optimization/benchmark?n_assets=100")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert "detail" in data
        assert "endpoint_disabled_in_production" in str(data["detail"])


def test_precompute_blocked_in_prod(test_client):
    """POST /optimization/precompute doit être bloqué en production"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        response = test_client.post("/api/performance/optimization/precompute")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert "detail" in data
        assert "endpoint_disabled_in_production" in str(data["detail"])


# ============================================================================
# Tests de validation des messages d'erreur
# ============================================================================

def test_dev_guard_error_message_structure(test_client):
    """Vérifier la structure du message d'erreur 403"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        response = test_client.post("/api/performance/cache/clear")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()

        # Vérifier structure détaillée de l'erreur
        detail = data["detail"]
        if isinstance(detail, dict):
            assert "error" in detail
            assert "message" in detail
            assert detail["error"] == "endpoint_disabled_in_production"
            assert "development mode" in detail["message"]
            assert "environment" in detail


def test_dev_guard_logs_access_denied(test_client, caplog):
    """Vérifier que les tentatives d'accès en prod sont loggées"""
    import logging
    caplog.set_level(logging.WARNING)

    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        response = test_client.post("/api/performance/cache/clear")

        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Vérifier qu'un log warning a été émis
        assert any("Access denied" in record.message for record in caplog.records)


# ============================================================================
# Tests des limites de paramètres
# ============================================================================

def test_benchmark_max_assets_limit(test_client):
    """Vérifier la limite de 1000 assets pour benchmark"""
    response = test_client.get("/api/performance/optimization/benchmark?n_assets=1001")

    # Doit retourner 400 (limite dépassée) ou 403 (bloqué en prod selon config)
    assert response.status_code in [400, 403]

    if response.status_code == 400:
        data = response.json()
        assert "1000 assets" in str(data["detail"])


def test_cache_clear_default_parameters(test_client):
    """Vérifier les paramètres par défaut de cache clear"""
    with patch('config.settings.settings') as mock_settings:
        mock_settings.environment = "development"
        mock_settings.debug = True

        response = test_client.post("/api/performance/cache/clear")

        # Doit utiliser older_than_days=7 et clear_memory=True par défaut
        # (Peut réussir ou échouer selon état du cache, mais pas 403)
        assert response.status_code != status.HTTP_403_FORBIDDEN


# ============================================================================
# Tests d'intégration avec différents environments
# ============================================================================

@pytest.mark.parametrize("environment,expected_blocked", [
    ("development", False),
    ("staging", True),
    ("production", True),
])
def test_protection_across_environments(test_client, environment, expected_blocked):
    """Vérifier que la protection fonctionne selon l'environment"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = environment
        mock_settings.debug = (environment == "development")
        mock_get_settings.return_value = mock_settings

        response = test_client.post("/api/performance/cache/clear")

        if expected_blocked:
            assert response.status_code == status.HTTP_403_FORBIDDEN
        else:
            assert response.status_code != status.HTTP_403_FORBIDDEN


# ============================================================================
# Tests de performance et timeout
# ============================================================================

def test_cache_stats_performance(test_client):
    """Vérifier que /cache/stats répond rapidement"""
    import time

    start = time.time()
    response = test_client.get("/api/performance/cache/stats")
    elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 1.0  # Doit répondre en moins d'1 seconde


def test_benchmark_with_minimal_params_fast(test_client):
    """Benchmark avec paramètres minimaux doit être rapide"""
    with patch('config.settings.settings') as mock_settings:
        mock_settings.environment = "development"
        mock_settings.debug = True

        import time
        start = time.time()

        # Paramètres très petits pour test rapide
        response = test_client.get(
            "/api/performance/optimization/benchmark?n_assets=5&n_periods=10"
        )

        elapsed = time.time() - start

        # Doit répondre rapidement avec peu d'assets
        if response.status_code == 200:
            assert elapsed < 5.0  # Moins de 5 secondes pour benchmark minimal


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
