"""
Tests de performance pour le système ML
"""

import pytest
import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
import tempfile
from pathlib import Path

from services.ml_pipeline_manager_optimized import OptimizedMLPipelineManager
from fastapi.testclient import TestClient
from api.main import app


@pytest.mark.performance
class TestMLPerformance:
    """Tests de performance pour le système ML"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.pipeline = OptimizedMLPipelineManager(models_path=self.temp_dir)
        self.client = TestClient(app)
    
    def teardown_method(self):
        """Cleanup après chaque test"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cache_performance_large_models(self):
        """Test de performance du cache avec de gros modèles"""
        # Simuler de gros modèles
        large_models = []
        for i in range(10):
            large_model = {
                "model": Mock(),
                "scaler": Mock(),
                "metadata": {"size": f"large_{i}"},
                "data": "x" * 1000000  # 1MB de données simulées
            }
            large_models.append(large_model)
        
        # Mesurer le temps d'ajout au cache
        start_time = time.time()
        
        for i, model in enumerate(large_models):
            self.pipeline.model_cache.put(f"large_model_{i}", model, size=1.0)
        
        cache_time = time.time() - start_time
        
        # Le cache ne devrait pas prendre plus de 100ms pour 10 modèles
        assert cache_time < 0.1, f"Cache trop lent: {cache_time:.3f}s"
        
        # Vérifier que les modèles sont bien évincés par taille
        assert self.pipeline.model_cache.size <= self.pipeline.model_cache.max_size
    
    def test_concurrent_cache_access_performance(self):
        """Test de performance d'accès concurrent au cache"""
        # Précharger le cache
        for i in range(5):
            self.pipeline.model_cache.put(f"model_{i}", f"data_{i}", size=0.5)
        
        results = []
        errors = []
        
        def worker(thread_id):
            try:
                start_time = time.time()
                
                # Effectuer plusieurs opérations
                for i in range(20):
                    # Lecture
                    self.pipeline.model_cache.get(f"model_{i % 5}")
                    
                    # Écriture
                    self.pipeline.model_cache.put(f"temp_{thread_id}_{i}", f"data_{i}", size=0.1)
                    
                    # Statistiques
                    self.pipeline.get_cache_stats()
                
                elapsed = time.time() - start_time
                results.append((thread_id, elapsed))
                
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Lancer plusieurs threads
        threads = []
        for tid in range(5):
            t = threading.Thread(target=worker, args=(tid,))
            threads.append(t)
        
        start_time = time.time()
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        total_time = time.time() - start_time
        
        # Vérifier qu'il n'y a pas d'erreurs
        assert len(errors) == 0, f"Erreurs dans les threads: {errors}"
        
        # Vérifier que les opérations sont rapides
        avg_time = sum(elapsed for _, elapsed in results) / len(results)
        assert avg_time < 0.5, f"Opérations trop lentes: {avg_time:.3f}s en moyenne"
        assert total_time < 2.0, f"Temps total trop long: {total_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_prediction_endpoint_performance(self):
        """Test de performance de l'endpoint de prédiction"""
        request_data = {
            "assets": ["BTC", "ETH", "SOL"],
            "horizons": [1, 7, 30],
            "include_volatility": True,
            "include_regime": True,
            "include_confidence": True
        }
        
        # Mesurer le temps de réponse
        start_time = time.time()
        
        response = self.client.post("/api/ml/predict", json=request_data)
        
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        # L'endpoint devrait répondre en moins de 200ms (même sans modèles chargés)
        assert response_time < 0.2, f"Endpoint trop lent: {response_time:.3f}s"
        
        data = response.json()
        assert data["success"] is True
    
    def test_multiple_concurrent_predictions(self):
        """Test de prédictions concurrentes multiples"""
        request_data = {
            "assets": ["BTC"],
            "horizon_days": 30,
            "include_volatility": True
        }
        
        def make_prediction(thread_id):
            start_time = time.time()
            response = self.client.post("/api/ml/predict", json=request_data)
            elapsed = time.time() - start_time
            
            return (thread_id, response.status_code, elapsed, response.json())
        
        # Lancer plusieurs requêtes en parallèle
        with ThreadPoolExecutor(max_workers=10) as executor:
            start_time = time.time()
            
            futures = [executor.submit(make_prediction, i) for i in range(20)]
            results = [future.result() for future in futures]
            
            total_time = time.time() - start_time
        
        # Vérifier que toutes les requêtes ont réussi
        for thread_id, status_code, elapsed, data in results:
            assert status_code == 200, f"Thread {thread_id} a échoué"
            assert data["success"] is True
            # Chaque requête devrait prendre moins de 500ms
            assert elapsed < 0.5, f"Thread {thread_id} trop lent: {elapsed:.3f}s"
        
        # Le temps total ne devrait pas dépasser 3 secondes
        assert total_time < 3.0, f"Requêtes concurrentes trop lentes: {total_time:.3f}s"
    
    def test_memory_usage_under_load(self):
        """Test d'utilisation mémoire sous charge"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Charger beaucoup d'éléments dans le cache
        for i in range(100):
            large_data = {
                "model": Mock(),
                "data": "x" * 100000,  # 100KB par modèle
                "metadata": {"id": i}
            }
            self.pipeline.model_cache.put(f"stress_model_{i}", large_data, size=0.1)
        
        # Faire beaucoup d'opérations
        for i in range(1000):
            self.pipeline.get_pipeline_status()
            self.pipeline.get_cache_stats()
            self.pipeline.model_cache.get(f"stress_model_{i % 100}")
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # L'augmentation mémoire ne devrait pas dépasser 50MB
        assert memory_increase < 50, f"Consommation mémoire excessive: +{memory_increase:.1f}MB"
        
        # Le cache devrait respecter sa limite
        assert self.pipeline.model_cache.size <= self.pipeline.model_cache.max_size
    
    @pytest.mark.asyncio
    async def test_cache_expiration_performance(self):
        """Test de performance de l'expiration du cache"""
        # Ajouter beaucoup d'éléments avec TTL
        import time
        
        for i in range(50):
            self.pipeline.model_cache.put(f"expiring_{i}", f"data_{i}", size=0.1)
        
        # Simuler le passage du temps
        time.sleep(0.1)
        
        # Mesurer le temps de nettoyage
        start_time = time.time()
        
        # Forcer une optimisation mémoire
        result = self.pipeline.optimize_memory()
        
        cleanup_time = time.time() - start_time
        
        # Le nettoyage devrait être rapide
        assert cleanup_time < 0.05, f"Nettoyage cache trop lent: {cleanup_time:.3f}s"
        assert result["success"] is True
    
    def test_pipeline_status_performance(self):
        """Test de performance de l'obtention du statut"""
        # Précharger le cache avec plusieurs modèles
        for i in range(20):
            self.pipeline.model_cache.put(f"perf_model_{i}", {"data": f"model_{i}"}, size=0.2)
        
        # Mesurer le temps pour obtenir le statut
        times = []
        
        for _ in range(100):
            start_time = time.time()
            status = self.pipeline.get_pipeline_status()
            elapsed = time.time() - start_time
            times.append(elapsed)
            
            # Vérifier la cohérence
            assert "pipeline_initialized" in status
            assert "loaded_models_count" in status
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        # Le statut devrait être obtenu très rapidement
        assert avg_time < 0.01, f"get_pipeline_status trop lent en moyenne: {avg_time:.4f}s"
        assert max_time < 0.05, f"get_pipeline_status pic trop lent: {max_time:.4f}s"


@pytest.mark.performance
class TestMLStressTest:
    """Tests de stress pour le système ML"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.temp_dir = Path(tempfile.mkdtemp()) 
        self.pipeline = OptimizedMLPipelineManager(models_path=self.temp_dir)
        self.client = TestClient(app)
    
    def teardown_method(self):
        """Cleanup après chaque test"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cache_stress_rapid_additions(self):
        """Test de stress avec ajouts rapides au cache"""
        start_time = time.time()
        
        # Ajouter 1000 éléments rapidement
        for i in range(1000):
            self.pipeline.model_cache.put(f"rapid_{i}", f"data_{i}", size=0.001)
        
        total_time = time.time() - start_time
        
        # Devrait traiter 1000 éléments en moins d'1 seconde
        assert total_time < 1.0, f"Ajouts cache trop lents: {total_time:.3f}s pour 1000 éléments"
        
        # Le cache devrait gérer l'éviction automatiquement
        assert self.pipeline.model_cache.size <= self.pipeline.model_cache.max_size
    
    def test_endpoint_stress_burst_requests(self):
        """Test de stress avec salves de requêtes"""
        request_data = {"assets": ["BTC"], "horizon_days": 30}
        
        # Faire 50 requêtes rapidement
        start_time = time.time()
        responses = []
        
        for i in range(50):
            response = self.client.post("/api/ml/predict", json=request_data)
            responses.append(response)
        
        total_time = time.time() - start_time
        
        # Vérifier que toutes les requêtes ont réussi
        for i, response in enumerate(responses):
            assert response.status_code == 200, f"Requête {i} a échoué"
        
        # 50 requêtes en moins de 5 secondes
        assert total_time < 5.0, f"Salve de requêtes trop lente: {total_time:.3f}s pour 50 requêtes"
        
        # Taux de traitement minimum
        requests_per_second = len(responses) / total_time
        assert requests_per_second > 10, f"Débit trop faible: {requests_per_second:.1f} req/s"
    
    def test_memory_leak_detection(self):
        """Test de détection de fuites mémoire"""
        import psutil
        import os
        import gc
        
        process = psutil.Process(os.getpid())
        
        # Mesure initiale
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Faire beaucoup d'opérations cycliques
        for cycle in range(10):
            # Ajouter des modèles
            for i in range(20):
                model_data = {"model": Mock(), "data": "x" * 50000}  # 50KB
                self.pipeline.model_cache.put(f"cycle_{cycle}_model_{i}", model_data, size=0.05)
            
            # Faire des prédictions
            for i in range(10):
                request_data = {"assets": ["BTC"], "horizon_days": 30}
                self.client.post("/api/ml/predict", json=request_data)
            
            # Nettoyer
            self.pipeline.clear_cache()
            gc.collect()
        
        # Mesure finale
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Après nettoyage, l'augmentation mémoire devrait être minimale
        assert memory_increase < 10, f"Possible fuite mémoire: +{memory_increase:.1f}MB après cycles"
    
    @pytest.mark.slow
    def test_long_running_stability(self):
        """Test de stabilité sur une longue durée"""
        import random
        
        start_time = time.time()
        operation_count = 0
        errors = []
        
        # Simuler une charge pendant 30 secondes
        while time.time() - start_time < 30:
            try:
                operation = random.choice([
                    "cache_add",
                    "cache_get", 
                    "status",
                    "prediction",
                    "cache_stats"
                ])
                
                if operation == "cache_add":
                    key = f"stability_{operation_count}"
                    self.pipeline.model_cache.put(key, f"data_{operation_count}", size=0.01)
                
                elif operation == "cache_get":
                    if self.pipeline.model_cache.size > 0:
                        # Choisir une clé aléatoire
                        self.pipeline.model_cache.get(f"stability_{random.randint(0, operation_count)}")
                
                elif operation == "status":
                    self.pipeline.get_pipeline_status()
                
                elif operation == "prediction":
                    request_data = {"assets": ["BTC"], "horizon_days": 30}
                    self.client.post("/api/ml/predict", json=request_data)
                
                elif operation == "cache_stats":
                    self.pipeline.get_cache_stats()
                
                operation_count += 1
                
                # Pause courte pour éviter de saturer
                time.sleep(0.001)
                
            except Exception as e:
                errors.append((operation_count, operation, str(e)))
        
        duration = time.time() - start_time
        ops_per_second = operation_count / duration
        
        # Vérifier la stabilité
        assert len(errors) == 0, f"Erreurs pendant test de stabilité: {errors[:5]}"
        assert ops_per_second > 100, f"Performance dégradée: {ops_per_second:.1f} ops/s"
        assert operation_count > 1000, f"Pas assez d'opérations effectuées: {operation_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance"])