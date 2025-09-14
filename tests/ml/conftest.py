"""
Configuration et fixtures partagées pour les tests ML
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock
import torch
import pickle
import json

from services.ml_pipeline_manager_optimized import OptimizedMLPipelineManager


@pytest.fixture
def temp_models_dir():
    """Fixture qui crée un répertoire temporaire pour les modèles"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture  
def mock_pipeline_manager(temp_models_dir):
    """Fixture qui crée un pipeline manager avec répertoire temporaire"""
    return OptimizedMLPipelineManager(models_path=temp_models_dir)


@pytest.fixture
def mock_volatility_model():
    """Fixture qui crée un modèle de volatilité mock"""
    model = Mock()
    model.eval = Mock()
    model.state_dict = Mock(return_value={})
    return model


@pytest.fixture
def mock_regime_model():
    """Fixture qui crée un modèle de régime mock"""
    model = Mock()
    model.eval = Mock()
    model.state_dict = Mock(return_value={})
    return model


@pytest.fixture
def mock_scaler():
    """Fixture qui crée un scaler mock"""
    scaler = Mock()
    scaler.transform = Mock(return_value=[[0.1, 0.2, 0.3]])
    scaler.inverse_transform = Mock(return_value=[[1.0, 2.0, 3.0]])
    return scaler


@pytest.fixture
def sample_volatility_metadata():
    """Fixture qui retourne des métadonnées de modèle de volatilité sample"""
    return {
        "model_type": "LSTM",
        "training_date": "2024-01-01",
        "accuracy": 0.85,
        "val_loss": 0.003,
        "features": ["close", "volume", "rsi", "macd", "bb_upper"],
        "sequence_length": 60,
        "symbol": "BTC"
    }


@pytest.fixture
def sample_regime_metadata():
    """Fixture qui retourne des métadonnées de modèle de régime sample"""
    return {
        "model_type": "RegimeClassifier",
        "training_date": "2024-01-01",
        "accuracy": 0.78,
        "val_loss": 0.45,
        "features": ["rsi", "macd", "bb_width", "volume_sma", "price_change"],
        "num_classes": 4,
        "regime_mapping": {
            "0": "bull",
            "1": "bear", 
            "2": "sideways",
            "3": "distribution"
        }
    }


@pytest.fixture
def loaded_pipeline_manager(mock_pipeline_manager, mock_volatility_model, 
                           mock_regime_model, mock_scaler, 
                           sample_volatility_metadata, sample_regime_metadata):
    """Fixture qui crée un pipeline manager avec des modèles chargés"""
    pipeline = mock_pipeline_manager
    
    # Charger un modèle de volatilité BTC
    pipeline.model_cache.put("volatility_BTC", {
        "model": mock_volatility_model,
        "scaler": mock_scaler,
        "metadata": sample_volatility_metadata
    }, size=2.0)
    
    # Charger le modèle de régime
    pipeline.model_cache.put("regime", {
        "model": mock_regime_model,
        "scaler": mock_scaler,
        "metadata": sample_regime_metadata
    }, size=1.5)
    
    # Mettre à jour les stats
    pipeline.stats["models_loaded"] = 2
    pipeline.stats["total_loading_time"] = 1.2
    
    return pipeline


@pytest.fixture
def sample_prediction_request():
    """Fixture qui retourne une requête de prédiction sample"""
    return {
        "assets": ["BTC", "ETH"],
        "horizon_days": 30,
        "horizons": [1, 7, 30],
        "include_regime": True,
        "include_volatility": True,
        "include_confidence": True
    }


@pytest.fixture
def sample_prediction_response():
    """Fixture qui retourne une réponse de prédiction sample"""
    return {
        "predictions": {
            "BTC": {
                "volatility": 0.045,
                "horizon_1d": {
                    "volatility": 0.043,
                    "expected_return": 0.001,
                    "horizon_days": 1,
                    "confidence": 0.92
                },
                "horizon_7d": {
                    "volatility": 0.048,
                    "expected_return": 0.025,
                    "horizon_days": 7,
                    "confidence": 0.85
                },
                "horizon_30d": {
                    "volatility": 0.055,
                    "expected_return": 0.08,
                    "horizon_days": 30,
                    "confidence": 0.78
                },
                "confidence_metrics": {
                    "model_confidence": 0.78,
                    "data_quality_score": 0.85,
                    "prediction_stability": 0.72,
                    "overall_confidence": 0.787
                }
            },
            "ETH": {
                "volatility": 0.062,
                "confidence_metrics": {
                    "model_confidence": 0.65,
                    "data_quality_score": 0.85,
                    "prediction_stability": 0.72,
                    "overall_confidence": 0.752
                }
            }
        },
        "regime_prediction": {
            "regime": "bull",
            "confidence": 0.78,
            "probabilities": {
                "bull": 0.78,
                "bear": 0.05,
                "sideways": 0.12,
                "distribution": 0.05
            }
        },
        "volatility_forecast": {
            "BTC": 0.045,
            "ETH": 0.062
        },
        "model_status": {
            "volatility_loaded": True,
            "regime_loaded": True,
            "models_count": 2
        }
    }


# Configuration pytest
def pytest_configure(config):
    """Configuration globale pour les tests ML"""
    # Supprimer les warnings PyTorch pour les tests
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="torch")
    warnings.filterwarnings("ignore", category=FutureWarning, module="torch")


def pytest_collection_modifyitems(config, items):
    """Modifier la collection de tests pour ajouter des marqueurs"""
    for item in items:
        # Marquer tous les tests async
        if "async" in str(item.function):
            item.add_marker(pytest.mark.asyncio)
        
        # Marquer les tests d'intégration
        if "integration" in item.name.lower() or "Integration" in item.name:
            item.add_marker(pytest.mark.integration)
        
        # Marquer les tests qui nécessitent des modèles
        if any(keyword in item.name.lower() for keyword in ["model", "pipeline", "prediction"]):
            item.add_marker(pytest.mark.ml_models)