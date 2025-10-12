"""
Configuration globale pytest pour tous les tests.

Ajoute le répertoire racine du projet au PYTHONPATH
pour permettre les imports relatifs (ex: from services.xxx import ...)
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from typing import Dict, Any

# Ajouter le répertoire racine du projet au sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# Fixtures pour isolation des services
# ============================================================================

@pytest.fixture
def mock_pricing_service():
    """
    Mock du service de pricing pour éviter les appels API réels.

    Returns:
        Mock avec méthodes get_price, get_prices_batch, etc.
    """
    mock = Mock()
    mock.get_price = Mock(return_value={"price": 50000.0, "symbol": "BTC"})
    mock.get_prices_batch = Mock(return_value={
        "BTC": 50000.0,
        "ETH": 3000.0,
        "USDT": 1.0
    })
    mock.get_cached_history = Mock(return_value=[
        [1609459200, 29000.0],  # 2021-01-01
        [1609545600, 30000.0],
        [1609632000, 31000.0],
    ])
    return mock


@pytest.fixture
def mock_portfolio_service():
    """
    Mock du service portfolio pour éviter la lecture de fichiers.

    Returns:
        Mock avec méthodes calculate_performance_metrics, etc.
    """
    mock = Mock()
    mock.calculate_performance_metrics = Mock(return_value={
        "total_value_usd": 100000.0,
        "asset_count": 5,
        "diversity_score": 2,
        "sharpe_ratio": 1.5,
        "max_drawdown": -0.15,
        "returns_1d": 0.02,
        "returns_7d": 0.08,
        "returns_30d": 0.15,
    })
    mock.save_portfolio_snapshot = Mock()
    return mock


@pytest.fixture
def mock_cointracking_connector():
    """
    Mock du connecteur CoinTracking pour éviter les appels API.

    Returns:
        Mock avec méthode get_current_balances
    """
    mock = Mock()
    mock.get_current_balances = AsyncMock(return_value={
        "ok": True,
        "items": [
            {
                "symbol": "BTC",
                "amount": 1.5,
                "value_usd": 75000.0,
                "price_usd": 50000.0,
            },
            {
                "symbol": "ETH",
                "amount": 10.0,
                "value_usd": 30000.0,
                "price_usd": 3000.0,
            },
        ],
        "meta": {
            "total_value_usd": 105000.0,
            "asset_count": 2,
        }
    })
    return mock


@pytest.fixture
def mock_ml_orchestrator():
    """
    Mock de MLOrchestrator pour éviter le chargement de modèles.

    Returns:
        Mock avec méthodes predict_volatility, predict_returns, etc.
    """
    mock = Mock()
    mock.predict_volatility = AsyncMock(return_value={
        "predictions": {"BTC": 0.05, "ETH": 0.08},
        "confidence": 0.85,
    })
    mock.predict_returns = AsyncMock(return_value={
        "predictions": {"BTC": 0.02, "ETH": 0.03},
        "confidence": 0.82,
    })
    mock.is_ready = Mock(return_value=True)
    return mock


# ============================================================================
# Fixtures pour TestClient avec services mockés
# ============================================================================

@pytest.fixture
def test_client_isolated(
    mock_pricing_service,
    mock_portfolio_service,
    mock_cointracking_connector,
    mock_ml_orchestrator
):
    """
    TestClient avec tous les services mockés pour isolation complète.

    Utilise des patches pour remplacer les services réels par des mocks.
    Évite les appels réseau, lecture fichiers, chargement modèles ML.

    Returns:
        TestClient FastAPI avec services mockés

    Example:
        def test_endpoint(test_client_isolated):
            response = test_client_isolated.get("/api/risk/dashboard")
            assert response.status_code == 200
    """
    with patch('services.pricing.pricing_service', mock_pricing_service), \
         patch('services.portfolio.portfolio_service', mock_portfolio_service), \
         patch('connectors.cointracking_api.connector', mock_cointracking_connector), \
         patch('services.ml.orchestrator.ml_orchestrator', mock_ml_orchestrator):

        from api.main import app
        client = TestClient(app)
        yield client


@pytest.fixture
def test_client():
    """
    TestClient FastAPI standard (sans mocks).

    Utilise les services réels. À privilégier pour tests d'intégration.

    Returns:
        TestClient FastAPI standard

    Example:
        def test_integration(test_client):
            response = test_client.get("/api/risk/dashboard")
            assert response.status_code == 200
    """
    from api.main import app
    return TestClient(app)


# ============================================================================
# Fixtures pour données de test
# ============================================================================

@pytest.fixture
def sample_portfolio_data() -> Dict[str, Any]:
    """
    Données de portfolio sample pour tests.

    Returns:
        Dict avec structure complète d'un portfolio
    """
    return {
        "ok": True,
        "items": [
            {
                "symbol": "BTC",
                "amount": 1.0,
                "value_usd": 50000.0,
                "price_usd": 50000.0,
                "group": "large_caps",
                "allocation_pct": 0.50,
            },
            {
                "symbol": "ETH",
                "amount": 10.0,
                "value_usd": 30000.0,
                "price_usd": 3000.0,
                "group": "large_caps",
                "allocation_pct": 0.30,
            },
            {
                "symbol": "USDT",
                "amount": 20000.0,
                "value_usd": 20000.0,
                "price_usd": 1.0,
                "group": "stablecoins",
                "allocation_pct": 0.20,
            },
        ],
        "meta": {
            "total_value_usd": 100000.0,
            "asset_count": 3,
            "group_count": 2,
        }
    }


@pytest.fixture
def sample_price_history() -> Dict[str, Any]:
    """
    Historique de prix sample pour tests.

    Returns:
        Dict avec historique de prix sur 30 jours
    """
    import pandas as pd
    dates = pd.date_range('2024-01-01', periods=30, freq='D')

    return {
        "BTC": [(int(d.timestamp()), 50000.0 + i * 100) for i, d in enumerate(dates)],
        "ETH": [(int(d.timestamp()), 3000.0 + i * 50) for i, d in enumerate(dates)],
        "USDT": [(int(d.timestamp()), 1.0) for d in dates],
    }
