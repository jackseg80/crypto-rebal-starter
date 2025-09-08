"""
Tests pour les endpoints ML unifiés
"""

import pytest
from fastapi.testclient import TestClient
import json
from unittest.mock import Mock, patch, AsyncMock

from api.main import app


class TestMLEndpoints:
    """Tests pour les endpoints ML unifiés"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.client = TestClient(app)
    
    def test_ml_status_endpoint(self):
        """Test de l'endpoint de statut ML"""
        response = self.client.get("/api/ml/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "success" in data
        assert "pipeline_status" in data
        assert "timestamp" in data
        
        pipeline_status = data["pipeline_status"]
        assert "pipeline_initialized" in pipeline_status
        assert "models_base_path" in pipeline_status
        assert "volatility_models" in pipeline_status
        assert "regime_models" in pipeline_status
        assert "loaded_models_count" in pipeline_status
    
    @patch('api.unified_ml_endpoints.get_ml_predictions')
    def test_unified_predictions_basic(self, mock_predictions):
        """Test des prédictions unifiées basiques"""
        # Mock de la réponse
        mock_predictions.return_value = {
            "predictions": {
                "BTC": {"volatility": 0.045, "trend": "bullish"},
                "ETH": {"volatility": 0.062, "trend": "neutral"}
            },
            "regime": {"current": "bull", "confidence": 0.78},
            "volatility": {"BTC": 0.045, "ETH": 0.062},
            "model_status": {"volatility_loaded": True, "regime_loaded": True}
        }
        
        request_data = {
            "assets": ["BTC", "ETH"],
            "horizon_days": 30,
            "include_regime": True,
            "include_volatility": True
        }
        
        response = self.client.post("/api/ml/predict", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "predictions" in data
        assert "regime_prediction" in data
        assert "volatility_forecast" in data
        assert "model_status" in data
        assert "timestamp" in data
        
        # Vérifier les prédictions
        predictions = data["predictions"]
        assert "BTC" in predictions
        assert "ETH" in predictions
    
    @patch('api.unified_ml_endpoints.get_ml_predictions')
    @patch('api.unified_ml_endpoints._get_multi_horizon_predictions')
    def test_unified_predictions_multi_horizon(self, mock_multi_horizon, mock_predictions):
        """Test des prédictions multi-horizon"""
        # Mock des prédictions de base
        mock_predictions.return_value = {
            "predictions": {"BTC": {"volatility": 0.045}},
            "regime": {"current": "bull", "confidence": 0.78},
            "model_status": {"volatility_loaded": True}
        }
        
        # Mock des prédictions multi-horizon
        mock_multi_horizon.return_value = {
            "BTC": {
                "horizon_1d": {"volatility": 0.043, "expected_return": 0.001, "horizon_days": 1},
                "horizon_7d": {"volatility": 0.048, "expected_return": 0.025, "horizon_days": 7},
                "horizon_30d": {"volatility": 0.055, "expected_return": 0.08, "horizon_days": 30}
            }
        }
        
        request_data = {
            "assets": ["BTC"],
            "horizons": [1, 7, 30],
            "include_regime": True,
            "include_volatility": True,
            "include_confidence": False
        }
        
        response = self.client.post("/api/ml/predict", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        
        # Vérifier que les fonctions ont été appelées
        mock_multi_horizon.assert_called_once_with(["BTC"], [1, 7, 30], False)
        
        # Vérifier la structure des prédictions
        predictions = data["predictions"]
        assert "BTC" in predictions
        btc_predictions = predictions["BTC"]
        assert "horizon_1d" in btc_predictions
        assert "horizon_7d" in btc_predictions
        assert "horizon_30d" in btc_predictions
    
    @patch('api.unified_ml_endpoints.get_ml_predictions')
    @patch('api.unified_ml_endpoints._add_confidence_metrics')
    def test_unified_predictions_with_confidence(self, mock_confidence, mock_predictions):
        """Test des prédictions avec métriques de confiance"""
        # Mock des prédictions de base
        mock_predictions.return_value = {
            "predictions": {"BTC": {"volatility": 0.045}},
            "regime": {"current": "bull", "confidence": 0.78},
            "model_status": {"volatility_loaded": True}
        }
        
        # Mock des métriques de confiance
        mock_confidence.return_value = {
            "BTC": {
                "volatility": 0.045,
                "confidence_metrics": {
                    "model_confidence": 0.78,
                    "data_quality_score": 0.85,
                    "prediction_stability": 0.72,
                    "overall_confidence": 0.787
                }
            }
        }
        
        request_data = {
            "assets": ["BTC"],
            "include_confidence": True
        }
        
        response = self.client.post("/api/ml/predict", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        
        # Vérifier que la fonction de confiance a été appelée
        mock_confidence.assert_called_once()
        
        # Vérifier les métriques de confiance
        predictions = data["predictions"]
        assert "BTC" in predictions
        btc_predictions = predictions["BTC"]
        assert "confidence_metrics" in btc_predictions
        
        confidence = btc_predictions["confidence_metrics"]
        assert "model_confidence" in confidence
        assert "overall_confidence" in confidence
    
    def test_volatility_prediction_endpoint(self):
        """Test de l'endpoint de prédiction de volatilité spécifique"""
        symbol = "BTC"
        horizon = 30
        
        response = self.client.get(f"/api/ml/volatility/predict/{symbol}?horizon_days={horizon}")
        
        # L'endpoint devrait répondre même avec des modèles non chargés (fallback)
        assert response.status_code == 200
        data = response.json()
        
        assert "symbol" in data
        assert data["symbol"] == symbol
        assert "volatility_forecast" in data or "error" in data
    
    def test_regime_prediction_endpoint(self):
        """Test de l'endpoint de prédiction de régime"""
        response = self.client.get("/api/ml/regime/predict")
        
        assert response.status_code == 200
        data = response.json()
        
        # L'endpoint devrait répondre même sans modèle chargé
        assert "regime" in data or "error" in data
    
    def test_sentiment_endpoint(self):
        """Test de l'endpoint de sentiment"""
        symbol = "BTC"
        response = self.client.get(f"/api/ml/sentiment/{symbol}?days=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["symbol"] == symbol
        assert "aggregated_sentiment" in data
        assert "sources_used" in data
    
    def test_fear_greed_endpoint(self):
        """Test de l'endpoint Fear & Greed"""
        response = self.client.get("/api/ml/sentiment/fear-greed?days=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "fear_greed_data" in data
        
        fear_greed = data["fear_greed_data"]
        assert "value" in fear_greed
        assert "classification" in fear_greed
        assert 0 <= fear_greed["value"] <= 100
    
    @patch('api.unified_ml_endpoints.optimized_pipeline_manager')
    def test_preload_models_endpoint(self, mock_pipeline):
        """Test de l'endpoint de préchargement des modèles"""
        # Mock de la réponse du pipeline
        mock_pipeline.preload_models.return_value = {
            "success": True,
            "total_requested": 3,
            "loaded_models": 2,
            "preload_results": {
                "volatility_BTC": True,
                "volatility_ETH": False,
                "regime": True
            }
        }
        
        response = self.client.post("/api/ml/models/preload?symbols=BTC&symbols=ETH")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["loaded_models"] == 2
        assert data["total_requested"] == 3
        assert "preload_results" in data
    
    @patch('api.unified_ml_endpoints.optimized_pipeline_manager')
    def test_cache_stats_endpoint(self, mock_pipeline):
        """Test de l'endpoint des statistiques de cache"""
        # Mock de la réponse du pipeline
        mock_pipeline.get_cache_stats.return_value = {
            "success": True,
            "cache_stats": {
                "cached_models": 2,
                "total_size_mb": 3.5,
                "max_size": 8,
                "memory_usage_percent": 43.75,
                "loading_status": {
                    "volatility_BTC": "loaded",
                    "regime": "loaded"
                }
            }
        }
        
        response = self.client.get("/api/ml/cache/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "cache_stats" in data
        
        cache_stats = data["cache_stats"]
        assert cache_stats["cached_models"] == 2
        assert cache_stats["total_size_mb"] == 3.5
        assert "loading_status" in cache_stats
    
    @patch('api.unified_ml_endpoints.optimized_pipeline_manager')
    def test_memory_optimize_endpoint(self, mock_pipeline):
        """Test de l'endpoint d'optimisation mémoire"""
        # Mock de la réponse du pipeline
        mock_pipeline.optimize_memory.return_value = {
            "success": True,
            "memory_freed_mb": 2.5,
            "models_cleared": 1,
            "cache_cleared": False
        }
        
        request_data = {"force_clear_all": False}
        response = self.client.post("/api/ml/memory/optimize", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["memory_freed_mb"] == 2.5
        assert data["models_cleared"] == 1
    
    def test_training_endpoint_background(self):
        """Test de l'endpoint d'entraînement en arrière-plan"""
        request_data = {
            "assets": ["BTC", "ETH"],
            "lookback_days": 365,
            "include_market_indicators": True,
            "save_models": True
        }
        
        response = self.client.post("/api/ml/train", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "Training started" in data["message"]
        assert data["background_task"] is True
        assert data["assets"] == ["BTC", "ETH"]
    
    def test_invalid_prediction_request(self):
        """Test de requête de prédiction invalide"""
        # Requête sans assets
        request_data = {
            "horizon_days": 30
        }
        
        response = self.client.post("/api/ml/predict", json=request_data)
        
        # Devrait retourner une erreur de validation
        assert response.status_code == 422
    
    def test_invalid_symbol_format(self):
        """Test avec un symbole invalide"""
        response = self.client.get("/api/ml/volatility/predict/INVALID_SYMBOL_123")
        
        # L'endpoint devrait gérer gracieusement les symboles invalides
        assert response.status_code in [200, 400, 422]
    
    def test_cache_functionality(self):
        """Test de la fonctionnalité de cache des endpoints"""
        request_data = {
            "assets": ["BTC"],
            "horizon_days": 30
        }
        
        # Première requête
        response1 = self.client.post("/api/ml/predict", json=request_data)
        assert response1.status_code == 200
        
        # Deuxième requête identique (devrait utiliser le cache)
        response2 = self.client.post("/api/ml/predict", json=request_data)
        assert response2.status_code == 200
        
        # Les réponses devraient être identiques (du cache)
        assert response1.json() == response2.json()


class TestMLHelperFunctions:
    """Tests pour les fonctions helper ML"""
    
    @pytest.mark.asyncio
    async def test_get_multi_horizon_predictions(self):
        """Test de la fonction multi-horizon"""
        from api.unified_ml_endpoints import _get_multi_horizon_predictions
        
        assets = ["BTC", "ETH"]
        horizons = [1, 7, 30]
        include_confidence = True
        
        result = await _get_multi_horizon_predictions(assets, horizons, include_confidence)
        
        assert isinstance(result, dict)
        assert "BTC" in result
        assert "ETH" in result
        
        for symbol in assets:
            symbol_data = result[symbol]
            assert "horizon_1d" in symbol_data
            assert "horizon_7d" in symbol_data
            assert "horizon_30d" in symbol_data
            
            for horizon_key, horizon_data in symbol_data.items():
                assert "volatility" in horizon_data
                assert "expected_return" in horizon_data
                assert "horizon_days" in horizon_data
                
                if include_confidence:
                    assert "confidence" in horizon_data
                    assert "prediction_interval" in horizon_data
    
    @pytest.mark.asyncio
    async def test_add_confidence_metrics(self):
        """Test de la fonction d'ajout de métriques de confiance"""
        from api.unified_ml_endpoints import _add_confidence_metrics
        
        predictions = {
            "BTC": {"volatility": 0.045},
            "ETH": {"volatility": 0.062}
        }
        assets = ["BTC", "ETH"]
        
        result = await _add_confidence_metrics(predictions, assets)
        
        assert isinstance(result, dict)
        assert "BTC" in result
        assert "ETH" in result
        
        for symbol in assets:
            symbol_data = result[symbol]
            assert "confidence_metrics" in symbol_data
            
            confidence = symbol_data["confidence_metrics"]
            assert "model_confidence" in confidence
            assert "data_quality_score" in confidence
            assert "prediction_stability" in confidence
            assert "overall_confidence" in confidence
            
            # Vérifier les plages de valeurs
            assert 0 <= confidence["overall_confidence"] <= 1


class TestMLEndpointIntegration:
    """Tests d'intégration pour les endpoints ML"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.client = TestClient(app)
    
    def test_full_prediction_workflow(self):
        """Test du workflow complet de prédiction"""
        # 1. Vérifier le statut du pipeline
        status_response = self.client.get("/api/ml/status")
        assert status_response.status_code == 200
        
        # 2. Obtenir des prédictions
        request_data = {
            "assets": ["BTC", "ETH"],
            "horizons": [1, 30],
            "include_regime": True,
            "include_volatility": True,
            "include_confidence": True
        }
        
        pred_response = self.client.post("/api/ml/predict", json=request_data)
        assert pred_response.status_code == 200
        
        pred_data = pred_response.json()
        assert pred_data["success"] is True
        
        # 3. Vérifier les statistiques de cache
        cache_response = self.client.get("/api/ml/cache/stats")
        assert cache_response.status_code == 200
    
    def test_error_handling_pipeline_unavailable(self):
        """Test de gestion d'erreur quand le pipeline n'est pas disponible"""
        with patch('api.unified_ml_endpoints.optimized_pipeline_manager') as mock_pipeline:
            mock_pipeline.get_pipeline_status.side_effect = Exception("Pipeline not available")
            
            response = self.client.get("/api/ml/status")
            assert response.status_code == 200
            
            data = response.json()
            assert data["success"] is False
            assert "error" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])