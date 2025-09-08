"""
Tests pour le pipeline ML optimisé
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile
import torch
import pickle
import json

from services.ml_pipeline_manager_optimized import OptimizedMLPipelineManager, LRUCache


class TestLRUCache:
    """Tests pour le cache LRU optimisé"""
    
    def test_cache_basic_operations(self):
        cache = LRUCache(max_size=3)
        
        # Test ajout d'éléments
        cache.put("key1", "value1", size=1.0)
        cache.put("key2", "value2", size=1.5)
        cache.put("key3", "value3", size=2.0)
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.size == 3
        assert cache.total_size_mb == 4.5
    
    def test_cache_eviction_by_size(self):
        cache = LRUCache(max_size=2)
        
        cache.put("key1", "value1", size=1.0)
        cache.put("key2", "value2", size=1.0)
        
        # Ajouter un troisième élément devrait évincer le premier
        cache.put("key3", "value3", size=1.0)
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.size == 2
    
    def test_cache_lru_ordering(self):
        cache = LRUCache(max_size=3)
        
        cache.put("key1", "value1", size=1.0)
        cache.put("key2", "value2", size=1.0)
        cache.put("key3", "value3", size=1.0)
        
        # Accéder à key1 le rend plus récent
        cache.get("key1")
        
        # Ajouter key4 devrait évincer key2 (pas key1)
        cache.put("key4", "value4", size=1.0)
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"
    
    def test_cache_clear(self):
        cache = LRUCache(max_size=3)
        
        cache.put("key1", "value1", size=1.0)
        cache.put("key2", "value2", size=1.0)
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.size == 0
        assert cache.total_size_mb == 0


class TestOptimizedMLPipelineManager:
    """Tests pour le gestionnaire de pipeline ML optimisé"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.pipeline = OptimizedMLPipelineManager(models_path=self.temp_dir)
    
    def teardown_method(self):
        """Cleanup après chaque test"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_pipeline_initialization(self):
        """Test de l'initialisation du pipeline"""
        assert self.pipeline.models_path == self.temp_dir
        assert self.pipeline.model_cache is not None
        assert self.pipeline.model_cache.max_size == 8
        assert self.pipeline.loading_lock is not None
        assert isinstance(self.pipeline.stats, dict)
    
    def test_volatility_model_path_resolution(self):
        """Test de la résolution des chemins de modèles de volatilité"""
        symbol = "BTC"
        paths = self.pipeline._get_volatility_model_paths(symbol)
        
        expected_base = self.temp_dir / "volatility"
        assert paths["model"] == expected_base / f"{symbol}_volatility_best.pth"
        assert paths["scaler"] == expected_base / f"{symbol}_scaler.pkl"
        assert paths["metadata"] == expected_base / f"{symbol}_metadata.pkl"
    
    def test_regime_model_path_resolution(self):
        """Test de la résolution des chemins du modèle de régime"""
        paths = self.pipeline._get_regime_model_paths()
        
        expected_base = self.temp_dir / "regime"
        assert paths["model"] == expected_base / "regime_neural_best.pth"
        assert paths["scaler"] == expected_base / "regime_scaler.pkl"
        assert paths["metadata"] == expected_base / "regime_metadata.pkl"
        assert paths["features"] == expected_base / "regime_features.pkl"
    
    def test_model_cache_key_generation(self):
        """Test de la génération des clés de cache"""
        volatility_key = self.pipeline._get_cache_key("volatility", "BTC")
        regime_key = self.pipeline._get_cache_key("regime")
        
        assert volatility_key == "volatility_BTC"
        assert regime_key == "regime"
    
    @patch('torch.load')
    @patch('pickle.load')
    @patch('builtins.open', create=True)
    def test_volatility_model_loading_success(self, mock_open, mock_pickle, mock_torch):
        """Test du chargement réussi d'un modèle de volatilité"""
        # Setup mocks
        mock_model = Mock()
        mock_scaler = Mock()
        mock_metadata = {"training_date": "2024-01-01", "accuracy": 0.85}
        
        mock_torch.return_value = mock_model
        mock_pickle.return_value = mock_scaler
        
        # Créer les fichiers mock
        symbol = "BTC"
        paths = self.pipeline._get_volatility_model_paths(symbol)
        paths["model"].parent.mkdir(parents=True, exist_ok=True)
        paths["model"].touch()
        paths["scaler"].touch()
        paths["metadata"].touch()
        
        # Mock file reading for metadata
        mock_file = Mock()
        mock_file.read.return_value = json.dumps(mock_metadata)
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Test loading
        result = self.pipeline.load_volatility_model(symbol)
        
        assert result is True
        assert self.pipeline.model_cache.get(f"volatility_{symbol}") is not None
        assert self.pipeline.stats["models_loaded"] == 1
    
    def test_volatility_model_loading_missing_files(self):
        """Test du chargement d'un modèle de volatilité avec fichiers manquants"""
        symbol = "NONEXISTENT"
        result = self.pipeline.load_volatility_model(symbol)
        
        assert result is False
        assert self.pipeline.model_cache.get(f"volatility_{symbol}") is None
    
    def test_get_pipeline_status(self):
        """Test de l'obtention du statut du pipeline"""
        status = self.pipeline.get_pipeline_status()
        
        assert "pipeline_initialized" in status
        assert "models_base_path" in status
        assert "timestamp" in status
        assert "volatility_models" in status
        assert "regime_models" in status
        assert "loaded_models_count" in status
        assert "total_models_count" in status
        
        # Test des sous-structures
        vol_status = status["volatility_models"]
        assert "models_count" in vol_status
        assert "models_loaded" in vol_status
        assert "last_updated" in vol_status
        
        regime_status = status["regime_models"]
        assert "model_exists" in regime_status
        assert "model_loaded" in regime_status
        assert "last_updated" in regime_status
    
    def test_preload_models(self):
        """Test du préchargement des modèles"""
        symbols = ["BTC", "ETH"]
        
        with patch.object(self.pipeline, 'load_volatility_model') as mock_vol_load, \
             patch.object(self.pipeline, 'load_regime_model') as mock_regime_load:
            
            mock_vol_load.return_value = True
            mock_regime_load.return_value = True
            
            result = self.pipeline.preload_models(symbols)
            
            assert result["success"] is True
            assert result["total_requested"] == 3  # 2 volatility + 1 regime
            assert result["loaded_models"] == 3
            assert "preload_results" in result
            
            # Vérifier les appels
            assert mock_vol_load.call_count == 2
            mock_vol_load.assert_any_call("BTC")
            mock_vol_load.assert_any_call("ETH")
            mock_regime_load.assert_called_once()
    
    def test_clear_cache(self):
        """Test du vidage du cache"""
        # Ajouter quelques éléments au cache
        self.pipeline.model_cache.put("test_key", {"model": "test"}, size=1.0)
        self.pipeline.stats["models_loaded"] = 1
        
        assert self.pipeline.model_cache.size == 1
        
        # Vider le cache
        result = self.pipeline.clear_cache()
        
        assert result["success"] is True
        assert result["models_cleared"] == 1
        assert self.pipeline.model_cache.size == 0
        assert self.pipeline.stats["models_loaded"] == 0
    
    def test_memory_optimization(self):
        """Test de l'optimisation mémoire"""
        # Simuler un cache plein
        for i in range(10):
            self.pipeline.model_cache.put(f"key_{i}", f"value_{i}", size=1.0)
        
        initial_size = self.pipeline.model_cache.size
        
        result = self.pipeline.optimize_memory()
        
        assert result["success"] is True
        assert result["memory_freed_mb"] >= 0
        # Le cache ne devrait pas dépasser sa taille maximale
        assert self.pipeline.model_cache.size <= self.pipeline.model_cache.max_size
    
    def test_get_cache_stats(self):
        """Test de l'obtention des statistiques de cache"""
        # Ajouter des éléments au cache
        self.pipeline.model_cache.put("vol_BTC", {"model": "btc"}, size=2.0)
        self.pipeline.model_cache.put("regime", {"model": "regime"}, size=1.5)
        
        stats = self.pipeline.get_cache_stats()
        
        assert stats["success"] is True
        assert "cache_stats" in stats
        
        cache_stats = stats["cache_stats"]
        assert cache_stats["cached_models"] == 2
        assert cache_stats["total_size_mb"] == 3.5
        assert cache_stats["max_size"] == 8
        assert "loading_status" in cache_stats
        assert "memory_usage_percent" in cache_stats


@pytest.fixture
def pipeline_with_models():
    """Fixture avec des modèles mock chargés"""
    temp_dir = Path(tempfile.mkdtemp())
    pipeline = OptimizedMLPipelineManager(models_path=temp_dir)
    
    # Ajouter des modèles mock au cache
    pipeline.model_cache.put("volatility_BTC", {
        "model": Mock(),
        "scaler": Mock(),
        "metadata": {"accuracy": 0.85, "training_date": "2024-01-01"}
    }, size=2.0)
    
    pipeline.model_cache.put("regime", {
        "model": Mock(),
        "scaler": Mock(),
        "metadata": {"accuracy": 0.78, "training_date": "2024-01-01"}
    }, size=1.5)
    
    pipeline.stats["models_loaded"] = 2
    
    yield pipeline
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_integration_pipeline_with_loaded_models(pipeline_with_models):
    """Test d'intégration avec des modèles chargés"""
    pipeline = pipeline_with_models
    
    # Test du statut avec modèles chargés
    status = pipeline.get_pipeline_status()
    assert status["loaded_models_count"] == 2
    
    # Test des statistiques de cache
    cache_stats = pipeline.get_cache_stats()
    assert cache_stats["cache_stats"]["cached_models"] == 2
    
    # Test de la présence des modèles
    btc_model = pipeline.model_cache.get("volatility_BTC")
    assert btc_model is not None
    assert "model" in btc_model
    assert "metadata" in btc_model
    
    regime_model = pipeline.model_cache.get("regime")
    assert regime_model is not None
    assert "model" in regime_model
    assert "metadata" in regime_model


def test_concurrent_access():
    """Test d'accès concurrent au pipeline"""
    import threading
    import time
    
    temp_dir = Path(tempfile.mkdtemp())
    pipeline = OptimizedMLPipelineManager(models_path=temp_dir)
    
    results = []
    errors = []
    
    def worker(thread_id):
        try:
            for i in range(5):
                # Simuler des opérations concurrentes
                status = pipeline.get_pipeline_status()
                cache_stats = pipeline.get_cache_stats()
                
                # Ajouter au cache
                pipeline.model_cache.put(f"test_{thread_id}_{i}", f"value_{thread_id}_{i}", size=0.1)
                
                time.sleep(0.01)  # Petite pause
                
                results.append((thread_id, i, status["timestamp"]))
        except Exception as e:
            errors.append((thread_id, str(e)))
    
    # Lancer plusieurs threads
    threads = []
    for tid in range(3):
        t = threading.Thread(target=worker, args=(tid,))
        threads.append(t)
        t.start()
    
    # Attendre la fin
    for t in threads:
        t.join()
    
    # Vérifier les résultats
    assert len(errors) == 0, f"Erreurs dans les threads: {errors}"
    assert len(results) == 15  # 3 threads * 5 opérations
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])