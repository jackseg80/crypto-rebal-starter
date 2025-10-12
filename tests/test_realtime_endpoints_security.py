"""
Tests de sécurité pour les endpoints realtime
Vérifie que les protections dev_guards et WebSocket auth fonctionnent
"""
import pytest
from unittest.mock import patch, Mock, AsyncMock
from fastapi import status
import os


# ============================================================================
# Tests des endpoints NON protégés (accessibles en dev et prod)
# ============================================================================

def test_realtime_status_accessible(test_client):
    """GET /status doit être accessible en développement et production"""
    response = test_client.get("/api/realtime/status")

    # Peut retourner 200 (engine ok) ou 500 (engine error), mais accessible
    assert response.status_code in [200, 500]


def test_realtime_connections_accessible(test_client):
    """GET /connections doit être accessible"""
    response = test_client.get("/api/realtime/connections")

    # Peut retourner 200 ou 500, mais pas bloqué par auth
    assert response.status_code in [200, 500]


# ============================================================================
# Tests des endpoints PROTÉGÉS en mode développement (doivent fonctionner)
# ============================================================================

def test_demo_page_allowed_in_dev(test_client):
    """GET /demo doit fonctionner en développement"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "development"
        mock_settings.debug = True
        mock_get_settings.return_value = mock_settings

        response = test_client.get("/api/realtime/demo")

        # Peut réussir (200) ou échouer pour raisons métier, mais pas 403
        assert response.status_code != status.HTTP_403_FORBIDDEN


def test_simulate_allowed_in_dev_with_flag(test_client):
    """POST /dev/simulate doit fonctionner en dev avec DEBUG_SIMULATION=true"""
    with patch.dict(os.environ, {"DEBUG_SIMULATION": "true"}):
        with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.environment = "development"
            mock_settings.debug = True
            mock_get_settings.return_value = mock_settings

            response = test_client.post("/api/realtime/dev/simulate?kind=risk_alert")

            # Peut réussir ou échouer pour raisons métier, mais pas 403
            assert response.status_code != status.HTTP_403_FORBIDDEN


def test_start_engine_allowed_in_dev(test_client):
    """POST /start doit fonctionner en développement"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "development"
        mock_settings.debug = True
        mock_get_settings.return_value = mock_settings

        response = test_client.post("/api/realtime/start")

        # Peut réussir (200) ou échouer, mais pas 403
        assert response.status_code != status.HTTP_403_FORBIDDEN


def test_stop_engine_allowed_in_dev(test_client):
    """POST /stop doit fonctionner en développement"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "development"
        mock_settings.debug = True
        mock_get_settings.return_value = mock_settings

        response = test_client.post("/api/realtime/stop")

        # Peut réussir (200) ou échouer, mais pas 403
        assert response.status_code != status.HTTP_403_FORBIDDEN


# ============================================================================
# Tests des endpoints PROTÉGÉS en mode production (doivent retourner 403)
# ============================================================================

def test_demo_page_blocked_in_prod(test_client):
    """GET /demo doit être bloqué en production"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        response = test_client.get("/api/realtime/demo")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert "detail" in data


def test_simulate_blocked_without_flag(test_client):
    """POST /dev/simulate doit être bloqué si DEBUG_SIMULATION=false"""
    with patch.dict(os.environ, {"DEBUG_SIMULATION": "false"}):
        with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.environment = "development"
            mock_settings.debug = True
            mock_get_settings.return_value = mock_settings

            response = test_client.post("/api/realtime/dev/simulate")

            assert response.status_code == status.HTTP_403_FORBIDDEN
            data = response.json()
            assert "simulation" in str(data["detail"]).lower()


def test_simulate_blocked_in_prod(test_client):
    """POST /dev/simulate doit être bloqué en production même avec flag"""
    with patch.dict(os.environ, {"DEBUG_SIMULATION": "true"}):
        with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.environment = "production"
            mock_settings.debug = False
            mock_get_settings.return_value = mock_settings

            response = test_client.post("/api/realtime/dev/simulate")

            assert response.status_code == status.HTTP_403_FORBIDDEN


def test_start_engine_blocked_in_prod(test_client):
    """POST /start doit être bloqué en production"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        response = test_client.post("/api/realtime/start")

        assert response.status_code == status.HTTP_403_FORBIDDEN


def test_stop_engine_blocked_in_prod(test_client):
    """POST /stop doit être bloqué en production"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        response = test_client.post("/api/realtime/stop")

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# Tests WebSocket Auth
# ============================================================================

def test_websocket_token_validation_dev_no_token():
    """En dev, WebSocket doit accepter sans token"""
    from api.dependencies.dev_guards import validate_websocket_token

    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "development"
        mock_get_settings.return_value = mock_settings

        result = validate_websocket_token(token=None)
        assert result is True


def test_websocket_token_validation_prod_no_token():
    """En prod, WebSocket doit refuser sans token"""
    from api.dependencies.dev_guards import validate_websocket_token

    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.is_production = Mock(return_value=True)
        mock_get_settings.return_value = mock_settings

        result = validate_websocket_token(token=None)
        assert result is False


def test_websocket_token_validation_prod_valid_token():
    """En prod, WebSocket doit accepter avec token valide"""
    from api.dependencies.dev_guards import validate_websocket_token

    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.security = Mock()
        mock_settings.security.debug_token = "valid_token_12345678"
        mock_get_settings.return_value = mock_settings

        result = validate_websocket_token(token="valid_token_12345678")
        assert result is True


def test_websocket_token_validation_prod_invalid_token():
    """En prod, WebSocket doit refuser avec token invalide"""
    from api.dependencies.dev_guards import validate_websocket_token

    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.security = Mock()
        mock_settings.security.debug_token = "valid_token_12345678"
        mock_settings.is_production = Mock(return_value=True)
        mock_get_settings.return_value = mock_settings

        result = validate_websocket_token(token="wrong_token")
        assert result is False


# ============================================================================
# Tests d'intégration avec différents environments
# ============================================================================

@pytest.mark.parametrize("environment,expected_blocked", [
    ("development", False),
    ("staging", True),
    ("production", True),
])
def test_demo_protection_across_environments(test_client, environment, expected_blocked):
    """Vérifier que /demo est protégé selon l'environment"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = environment
        mock_settings.debug = (environment == "development")
        mock_get_settings.return_value = mock_settings

        response = test_client.get("/api/realtime/demo")

        if expected_blocked:
            assert response.status_code == status.HTTP_403_FORBIDDEN
        else:
            assert response.status_code != status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("flag_value,expected_blocked", [
    ("true", False),
    ("false", True),
    ("1", False),
    ("0", True),
])
def test_simulate_flag_variations(test_client, flag_value, expected_blocked):
    """Tester différentes valeurs du flag DEBUG_SIMULATION"""
    with patch.dict(os.environ, {"DEBUG_SIMULATION": flag_value}):
        with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.environment = "development"
            mock_settings.debug = True
            mock_get_settings.return_value = mock_settings

            response = test_client.post("/api/realtime/dev/simulate")

            if expected_blocked:
                assert response.status_code == status.HTTP_403_FORBIDDEN
            else:
                # Peut réussir ou échouer pour raisons métier, mais pas 403
                assert response.status_code != status.HTTP_403_FORBIDDEN


# ============================================================================
# Tests de messages d'erreur
# ============================================================================

def test_dev_guard_error_message_realtime(test_client):
    """Vérifier la structure du message d'erreur 403 pour realtime"""
    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        response = test_client.get("/api/realtime/demo")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()

        # Vérifier structure de l'erreur
        detail = data["detail"]
        if isinstance(detail, dict):
            assert "error" in detail
            assert "message" in detail


def test_simulation_flag_error_message(test_client):
    """Vérifier le message d'erreur quand DEBUG_SIMULATION=false"""
    with patch.dict(os.environ, {"DEBUG_SIMULATION": "false"}):
        with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.environment = "development"
            mock_get_settings.return_value = mock_settings

            response = test_client.post("/api/realtime/dev/simulate")

            assert response.status_code == status.HTTP_403_FORBIDDEN
            data = response.json()

            # Doit mentionner le flag simulation
            detail_str = str(data["detail"]).lower()
            assert "simulation" in detail_str


# ============================================================================
# Tests de logging
# ============================================================================

def test_websocket_rejection_logged(caplog):
    """Vérifier que les refus WebSocket sont loggés"""
    import logging
    from api.dependencies.dev_guards import validate_websocket_token

    caplog.set_level(logging.WARNING)

    with patch('api.dependencies.dev_guards.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.environment = "production"
        mock_settings.is_production = Mock(return_value=True)
        mock_get_settings.return_value = mock_settings

        result = validate_websocket_token(token=None)

        assert result is False
        assert any("WebSocket connection rejected" in record.message for record in caplog.records)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
