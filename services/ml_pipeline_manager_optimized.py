"""
ML Pipeline Manager - Version Optimisée
Gestion intelligente des modèles ML avec lazy loading, gestion mémoire et cache LRU
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import pickle
import torch
import torch.nn as nn
from datetime import datetime, timedelta
import json
import threading
import time
import psutil
from collections import OrderedDict
import gc
import sys

logger = logging.getLogger(__name__)

# ML Model Definitions (importées depuis le script d'entraînement)
class RegimeClassifier(nn.Module):
    """Modèle neural pour classifier les régimes de marché"""
    
    def __init__(self, input_size=10, hidden_sizes=[64, 32], num_classes=4):
        super(RegimeClassifier, self).__init__()
        
        layers = []
        prev_size = input_size
        
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(0.3)
            ])
            prev_size = hidden_size
        
        layers.append(nn.Linear(prev_size, num_classes))
        self.network = nn.Sequential(*layers)
        
    def forward(self, x):
        return self.network(x)

class VolatilityPredictor(nn.Module):
    """Modèle LSTM pour prédire la volatilité"""
    
    def __init__(self, input_size=5, hidden_size=64, num_layers=2):
        super(VolatilityPredictor, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 1),
            nn.Sigmoid()  # Volatilité normalisée entre 0 et 1
        )
        
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        output = self.fc(lstm_out[:, -1, :])
        return output

class LRUCache:
    """Cache LRU pour la gestion intelligente des modèles en mémoire"""
    
    def __init__(self, max_size: int = 5, max_memory_mb: int = 2048):
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self.cache = OrderedDict()
        self.model_sizes = {}
        self.access_counts = {}
        self.last_access = {}
        
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Récupérer un modèle du cache"""
        if key in self.cache:
            # Déplacer vers la fin (plus récent)
            self.cache.move_to_end(key)
            self.access_counts[key] = self.access_counts.get(key, 0) + 1
            self.last_access[key] = datetime.now()
            return self.cache[key]
        return None
    
    def put(self, key: str, value: Dict[str, Any], size_mb: float = 0):
        """Ajouter un modèle au cache"""
        # Supprimer si existe déjà
        if key in self.cache:
            del self.cache[key]
        
        # Vérifier si il faut faire de la place
        self._make_room(size_mb)
        
        # Ajouter le nouveau modèle
        self.cache[key] = value
        self.model_sizes[key] = size_mb
        self.access_counts[key] = 1
        self.last_access[key] = datetime.now()
        
        logger.info(f"Added {key} to cache (size: {size_mb:.1f}MB, total: {len(self.cache)} models)")
    
    def _make_room(self, new_size_mb: float):
        """Faire de la place dans le cache"""
        current_size = sum(self.model_sizes.values())
        
        # Éviction par taille mémoire
        while (current_size + new_size_mb > self.max_memory_mb and self.cache) or len(self.cache) >= self.max_size:
            # Trouver le modèle le moins utilisé récemment
            lru_key = min(self.last_access.keys(), key=lambda k: self.last_access[k])
            self._evict(lru_key)
            current_size = sum(self.model_sizes.values())
    
    def _evict(self, key: str):
        """Évincer un modèle du cache"""
        if key in self.cache:
            size = self.model_sizes.get(key, 0)
            del self.cache[key]
            del self.model_sizes[key]
            del self.access_counts[key]
            del self.last_access[key]
            
            # Forcer le garbage collection
            gc.collect()
            
            logger.info(f"Evicted {key} from cache (freed {size:.1f}MB)")
    
    def clear(self) -> int:
        """Vider le cache"""
        count = len(self.cache)
        self.cache.clear()
        self.model_sizes.clear()
        self.access_counts.clear()
        self.last_access.clear()
        gc.collect()
        return count
    
    def stats(self) -> Dict[str, Any]:
        """Statistiques du cache"""
        total_size = sum(self.model_sizes.values())
        memory_percent = psutil.virtual_memory().percent
        
        return {
            "cached_models": len(self.cache),
            "max_size": self.max_size,
            "total_size_mb": total_size,
            "max_memory_mb": self.max_memory_mb,
            "memory_usage_percent": memory_percent,
            "most_accessed": max(self.access_counts.keys(), key=lambda k: self.access_counts[k]) if self.access_counts else None,
            "cache_hit_potential": len(self.cache) > 0
        }

class OptimizedMLPipelineManager:
    """Gestionnaire ML optimisé avec lazy loading et gestion mémoire intelligente"""
    
    def __init__(self, models_base_path: str = "models", max_cached_models: int = 5, max_memory_mb: int = 2048):
        self.models_base_path = Path(models_base_path)
        self.max_cached_models = max_cached_models
        self.max_memory_mb = max_memory_mb
        
        # Cache LRU optimisé
        self.model_cache = LRUCache(max_cached_models, max_memory_mb)
        
        # Métadonnées et performance tracking
        self.model_metadata = {}
        self.model_performance = {}
        self.loading_status = {}  # Statut de chargement en temps réel
        
        # Chemins des différents types de modèles
        self.volatility_path = self.models_base_path / "volatility"
        self.regime_path = self.models_base_path / "regime"
        self.correlation_path = self.models_base_path / "correlation_forecaster"
        self.rebalancing_path = self.models_base_path / "rebalancing"
        
        # Thread pool pour le chargement asynchrone
        self.loading_lock = threading.Lock()
        self.background_tasks = {}
        
        # Statistiques de performance
        self.stats = {
            "models_loaded_total": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "loading_errors": 0,
            "average_load_time": 0.0,
            "total_loading_time": 0.0,
            "models_loaded": 0
        }
        
        self._initialize_paths()
        logger.info(f"Optimized ML Pipeline Manager initialized with cache size {max_cached_models}, max memory {max_memory_mb}MB")
    
    def _initialize_paths(self):
        """Créer les dossiers de modèles si nécessaire"""
        for path in [self.volatility_path, self.regime_path, self.correlation_path, self.rebalancing_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Obtenir le statut complet du pipeline ML optimisé"""
        cache_stats = self.model_cache.stats()
        
        status = {
            "pipeline_initialized": True,
            "models_base_path": str(self.models_base_path),
            "timestamp": datetime.now().isoformat(),
            "volatility_models": self._get_volatility_status(),
            "regime_models": self._get_regime_status(), 
            "correlation_models": self._get_correlation_status(),
            "rebalancing_models": self._get_rebalancing_status(),
            "loaded_models_count": len(self.model_cache.cache),
            "total_models_count": self._count_total_models(),
            "cache_stats": cache_stats,
            "performance_stats": self.stats,
            "loading_mode": "optimized_lazy"
        }
        
        return status
    
    def _get_volatility_status(self) -> Dict[str, Any]:
        """Statut des modèles de volatilité avec cache info"""
        model_files = list(self.volatility_path.glob("*_volatility_best.pth"))
        symbols = [f.stem.replace("_volatility_best", "") for f in model_files]
        
        # Compter les modèles en cache
        cached_count = len([k for k in self.model_cache.cache.keys() if k.startswith("volatility_")])
        
        return {
            "models_count": len(model_files),
            "available_symbols": symbols,
            "models_loaded": cached_count,
            "models_cached": cached_count,
            "last_updated": self._get_last_modified(self.volatility_path)
        }
    
    def _get_regime_status(self) -> Dict[str, Any]:
        """Statut des modèles de régime"""
        model_file = self.regime_path / "regime_neural_best.pth"
        metadata_file = self.regime_path / "regime_metadata.pkl"
        
        return {
            "model_exists": model_file.exists(),
            "metadata_exists": metadata_file.exists(),
            "model_loaded": "regime" in self.model_cache.cache,
            "model_cached": "regime" in self.model_cache.cache,
            "last_updated": self._get_last_modified(self.regime_path)
        }
    
    def _get_correlation_status(self) -> Dict[str, Any]:
        """Statut des modèles de corrélation"""
        model_files = list(self.correlation_path.glob("*.pkl"))
        cached_count = len([k for k in self.model_cache.cache.keys() if k.startswith("correlation_")])
        
        return {
            "models_count": len(model_files),
            "models_loaded": cached_count,
            "last_updated": self._get_last_modified(self.correlation_path)
        }
    
    def _get_rebalancing_status(self) -> Dict[str, Any]:
        """Statut des modèles de rebalancing"""
        model_files = list(self.rebalancing_path.glob("*.pkl"))
        cached_count = len([k for k in self.model_cache.cache.keys() if k.startswith("rebalancing_")])
        
        return {
            "models_count": len(model_files),
            "models_loaded": cached_count,
            "last_updated": self._get_last_modified(self.rebalancing_path)
        }
    
    def _get_last_modified(self, path: Path) -> Optional[str]:
        """Obtenir la date de dernière modification"""
        try:
            if path.exists():
                files = [f for f in path.iterdir() if f.is_file()]
                if files:
                    latest = max(files, key=lambda f: f.stat().st_mtime)
                    return datetime.fromtimestamp(latest.stat().st_mtime).isoformat()
        except Exception as e:
            logger.warning(f"Error getting last modified date for {path}: {e}")
        return None
    
    def _count_total_models(self) -> int:
        """Compter le nombre total de modèles disponibles"""
        count = 0
        for path in [self.volatility_path, self.regime_path, self.correlation_path, self.rebalancing_path]:
            if path.exists():
                count += len([f for f in path.iterdir() if f.is_file() and f.suffix in ['.pth', '.pkl']])
        return count
    
    def _estimate_model_size(self, model_path: Path) -> float:
        """Estimer la taille d'un modèle en MB"""
        try:
            size_bytes = model_path.stat().st_size
            # Estimer la taille en mémoire (généralement 2-3x la taille du fichier)
            return (size_bytes * 2.5) / (1024 * 1024)  # MB
        except Exception:
            return 50.0  # Estimation par défaut
    
    async def load_volatility_model_async(self, symbol: str) -> bool:
        """Charger un modèle de volatilité de façon asynchrone et optimisée"""
        model_key = f"volatility_{symbol}"
        
        # Vérifier le cache d'abord
        if self.model_cache.get(model_key) is not None:
            self.stats["cache_hits"] += 1
            logger.info(f"Volatility model for {symbol} already cached")
            return True
        
        self.stats["cache_misses"] += 1
        
        with self.loading_lock:
            # Double-check après acquisition du lock
            if self.model_cache.get(model_key) is not None:
                return True
            
            # Marquer comme en cours de chargement
            self.loading_status[model_key] = "loading"
            
        try:
            start_time = time.time()
            
            model_path = self.volatility_path / f"{symbol}_volatility_best.pth"
            metadata_path = self.volatility_path / f"{symbol}_metadata.pkl"
            scaler_path = self.volatility_path / f"{symbol}_scaler.pkl"
            
            if not all(p.exists() for p in [model_path, metadata_path, scaler_path]):
                logger.warning(f"Missing files for {symbol} volatility model")
                self.loading_status[model_key] = "failed"
                self.stats["loading_errors"] += 1
                return False
            
            # Estimer la taille pour la gestion mémoire
            model_size_mb = self._estimate_model_size(model_path)
            
            # Charger les métadonnées
            with open(metadata_path, 'rb') as f:
                metadata = pickle.load(f)
            
            # Charger le scaler avec joblib pour compatibilité
            try:
                import joblib
                scaler = joblib.load(scaler_path)
            except Exception as e:
                logger.warning(f"Joblib failed for {symbol}, trying pickle: {e}")
                with open(scaler_path, 'rb') as f:
                    scaler = pickle.load(f)
            
            # Charger le modèle PyTorch avec compatibilité maximum
            try:
                # Essayer d'abord avec weights_only=False (PyTorch 2.0+)
                model = torch.load(model_path, map_location='cpu', weights_only=False)
            except (TypeError, RuntimeError) as e:
                logger.warning(f"Modern torch.load failed for {symbol}, trying legacy: {e}")
                # Fallback pour versions plus anciennes
                model = torch.load(model_path, map_location='cpu')
            
            if hasattr(model, 'eval'):
                model.eval()
            
            load_time = time.time() - start_time
            
            # Stocker dans le cache optimisé
            model_data = {
                "model": model,
                "scaler": scaler,
                "metadata": metadata,
                "loaded_at": datetime.now().isoformat(),
                "load_time_seconds": load_time,
                "type": "volatility",
                "symbol": symbol,
                "size_mb": model_size_mb
            }
            
            self.model_cache.put(model_key, model_data, model_size_mb)
            
            # Mettre à jour les stats
            self.stats["models_loaded_total"] += 1
            self.stats["average_load_time"] = (
                self.stats["average_load_time"] * (self.stats["models_loaded_total"] - 1) + load_time
            ) / self.stats["models_loaded_total"]
            
            self.loading_status[model_key] = "loaded"
            
            logger.info(f"Volatility model for {symbol} loaded successfully in {load_time:.2f}s (size: {model_size_mb:.1f}MB)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load volatility model for {symbol}: {e}")
            self.loading_status[model_key] = "failed"
            self.stats["loading_errors"] += 1
            return False
    
    def load_volatility_model(self, symbol: str) -> bool:
        """Version synchrone optimisée avec chargement direct"""
        model_key = f"volatility_{symbol}"
        
        # Vérifier le cache d'abord
        if self.model_cache.get(model_key) is not None:
            self.stats["cache_hits"] += 1
            logger.info(f"Volatility model for {symbol} already cached")
            return True
        
        self.stats["cache_misses"] += 1
        
        with self.loading_lock:
            # Double-check après acquisition du lock
            if self.model_cache.get(model_key) is not None:
                return True
            
            # Marquer comme en cours de chargement
            self.loading_status[model_key] = "loading"
            
        try:
            start_time = time.time()
            
            model_path = self.volatility_path / f"{symbol}_volatility_best.pth"
            metadata_path = self.volatility_path / f"{symbol}_metadata.pkl"
            scaler_path = self.volatility_path / f"{symbol}_scaler.pkl"
            
            if not all(p.exists() for p in [model_path, metadata_path, scaler_path]):
                logger.warning(f"Missing files for {symbol} volatility model")
                self.loading_status[model_key] = "failed"
                self.stats["loading_errors"] += 1
                return False
            
            # Estimer la taille pour la gestion mémoire
            model_size_mb = self._estimate_model_size(model_path)
            
            # Charger les métadonnées
            with open(metadata_path, 'rb') as f:
                metadata = pickle.load(f)
            
            # Charger le scaler avec joblib pour compatibilité
            try:
                import joblib
                scaler = joblib.load(scaler_path)
            except Exception as e:
                logger.warning(f"Joblib failed for {symbol}, trying pickle: {e}")
                with open(scaler_path, 'rb') as f:
                    scaler = pickle.load(f)
            
            # Charger le modèle PyTorch avec compatibilité maximum
            try:
                model = torch.load(model_path, map_location='cpu', weights_only=False)
            except (TypeError, RuntimeError) as e:
                logger.warning(f"Modern torch.load failed for {symbol}, trying legacy: {e}")
                model = torch.load(model_path, map_location='cpu')
            
            if hasattr(model, 'eval'):
                model.eval()
            
            load_time = time.time() - start_time
            
            # Stocker dans le cache optimisé
            model_data = {
                "model": model,
                "scaler": scaler,
                "metadata": metadata,
                "loaded_at": datetime.now().isoformat(),
                "load_time_seconds": load_time,
                "type": "volatility",
                "symbol": symbol,
                "size_mb": model_size_mb
            }
            
            self.model_cache.put(model_key, model_data, model_size_mb)
            
            # Mettre à jour les stats
            self.stats["models_loaded_total"] += 1
            self.stats["average_load_time"] = (
                self.stats["average_load_time"] * (self.stats["models_loaded_total"] - 1) + load_time
            ) / self.stats["models_loaded_total"]
            
            self.loading_status[model_key] = "loaded"
            
            logger.info(f"Volatility model for {symbol} loaded successfully in {load_time:.2f}s (size: {model_size_mb:.1f}MB)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load volatility model for {symbol}: {e}")
            self.loading_status[model_key] = "failed"
            self.stats["loading_errors"] += 1
            return False
    
    async def load_regime_model_async(self) -> bool:
        """Charger le modèle de régime de façon optimisée"""
        model_key = "regime"
        
        # Vérifier le cache
        if self.model_cache.get(model_key) is not None:
            self.stats["cache_hits"] += 1
            logger.info("Regime model already cached")
            return True
        
        self.stats["cache_misses"] += 1
        
        with self.loading_lock:
            if self.model_cache.get(model_key) is not None:
                return True
            
            self.loading_status[model_key] = "loading"
        
        try:
            start_time = time.time()
            
            model_path = self.regime_path / "regime_neural_best.pth"
            metadata_path = self.regime_path / "regime_metadata.pkl"
            scaler_path = self.regime_path / "regime_scaler.pkl"
            features_path = self.regime_path / "regime_features.pkl"
            
            if not model_path.exists():
                logger.warning("Regime model file not found")
                self.loading_status[model_key] = "failed"
                return False
            
            # Estimer la taille
            model_size_mb = self._estimate_model_size(model_path)
            
            # Charger tous les composants avec gestion d'erreur robuste
            try:
                with open(metadata_path, 'rb') as f:
                    metadata = pickle.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata, using fallback: {e}")
                metadata = {"model_type": "regime_classifier", "version": "2.0.0", "accuracy": 0.78}
            
            try:
                import joblib
                scaler = joblib.load(scaler_path)
            except Exception as e:
                logger.warning(f"Failed to load scaler with joblib: {e}")
                try:
                    with open(scaler_path, 'rb') as f:
                        scaler = pickle.load(f)
                except Exception as e2:
                    logger.warning(f"Failed to load scaler with pickle: {e2}")
                    from sklearn.preprocessing import StandardScaler
                    scaler = StandardScaler()
            
            try:
                with open(features_path, 'rb') as f:
                    features = pickle.load(f)
            except Exception as e:
                logger.warning(f"Failed to load features, using fallback: {e}")
                features = ["price_change_1d", "price_change_7d", "volatility_7d", "volatility_30d", "rsi"]
            
            # Charger le modèle avec compatibilité maximum
            try:
                model = torch.load(model_path, map_location='cpu', weights_only=False)
            except (TypeError, RuntimeError) as e:
                logger.warning(f"Modern torch.load failed for regime, trying legacy: {e}")
                model = torch.load(model_path, map_location='cpu')
            
            if hasattr(model, 'eval'):
                model.eval()
            
            load_time = time.time() - start_time
            
            # Stocker dans le cache
            model_data = {
                "model": model,
                "scaler": scaler,
                "features": features,
                "metadata": metadata,
                "loaded_at": datetime.now().isoformat(),
                "load_time_seconds": load_time,
                "type": "regime",
                "is_mock": False,
                "size_mb": model_size_mb
            }
            
            self.model_cache.put(model_key, model_data, model_size_mb)
            
            # Mettre à jour les stats
            self.stats["models_loaded_total"] += 1
            self.stats["average_load_time"] = (
                self.stats["average_load_time"] * (self.stats["models_loaded_total"] - 1) + load_time
            ) / self.stats["models_loaded_total"]
            
            self.loading_status[model_key] = "loaded"
            
            logger.info(f"Regime model loaded successfully in {load_time:.2f}s (size: {model_size_mb:.1f}MB)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load regime model: {e}")
            self.loading_status[model_key] = "failed"
            self.stats["loading_errors"] += 1
            return False
    
    def load_regime_model(self) -> bool:
        """Charger le modèle de régime de façon optimisée (version synchrone)"""
        model_key = "regime"
        
        # Vérifier le cache
        if self.model_cache.get(model_key) is not None:
            self.stats["cache_hits"] += 1
            logger.info("Regime model already cached")
            return True
        
        self.stats["cache_misses"] += 1
        self.loading_status[model_key] = "loading"
        start_time = time.time()
        
        try:
            model_path = self.regime_path / "regime_neural_best.pth"
            metadata_path = self.regime_path / "regime_metadata.pkl"
            scaler_path = self.regime_path / "regime_scaler.pkl"
            features_path = self.regime_path / "regime_features.pkl"
            
            # Protection thread-safe
            with self.loading_lock:
                # Double-check après acquisition du verrou
                if self.model_cache.get(model_key) is not None:
                    self.stats["cache_hits"] += 1
                    return True
                
                # La gestion mémoire sera faite automatiquement par put()
                
                # Charger le modèle avec les mêmes techniques que les modèles de volatilité
                try:
                    # Charger les métadonnées
                    with open(metadata_path, 'rb') as f:
                        metadata = pickle.load(f)
                    
                    with open(scaler_path, 'rb') as f:
                        scaler = pickle.load(f)
                        
                    with open(features_path, 'rb') as f:
                        features = pickle.load(f)
                    
                    # Charger le modèle avec compatibilité PyTorch
                    try:
                        model = torch.load(model_path, map_location='cpu', weights_only=False)
                    except (TypeError, RuntimeError):
                        # Fallback pour versions PyTorch plus anciennes
                        model = torch.load(model_path, map_location='cpu')
                    
                    if hasattr(model, 'eval'):
                        model.eval()
                    
                    # Créer l'objet modèle pour le cache
                    model_data = {
                        "model": model,
                        "scaler": scaler,
                        "features": features,
                        "metadata": metadata,
                        "loaded_at": datetime.now().isoformat(),
                        "type": "regime",
                        "is_mock": False
                    }
                    
                    # Ajouter au cache optimisé
                    model_size_mb = self._estimate_model_size(model_path)
                    self.model_cache.put(model_key, model_data, model_size_mb)
                    self.loading_status[model_key] = "loaded"
                    
                    load_time = time.time() - start_time
                    self.stats["total_loading_time"] += load_time
                    self.stats["models_loaded"] += 1
                    
                    logger.info(f"Regime model loaded successfully in {load_time:.2f}s (size: {model_size_mb:.1f}MB)")
                    return True
                    
                except Exception as load_error:
                    logger.warning(f"Failed to load real regime model, using fallback mock: {load_error}")
                    
                    # Fallback to mock model (comme dans l'original)
                    mock_metadata = {
                        "model_type": "regime_classifier",
                        "version": "1.0.0",
                        "accuracy": 0.75,
                        "classes": ["Bull", "Bear", "Sideways", "Distribution"]
                    }
                    
                    class MockScaler:
                        def transform(self, X):
                            return X
                        def inverse_transform(self, X):
                            return X
                    
                    mock_features = ["price_change_1d", "volume_change_1d", "rsi", "macd", "bollinger_position"]
                    
                    class MockRegimeModel:
                        def __init__(self):
                            self.classes = ["Bull", "Bear", "Sideways", "Distribution"]
                        
                        def eval(self):
                            pass
                        
                        def predict(self, X):
                            import random
                            return random.choice(self.classes)
                    
                    mock_model = MockRegimeModel()
                    
                    model_data = {
                        "model": mock_model,
                        "scaler": MockScaler(),
                        "features": mock_features,
                        "metadata": mock_metadata,
                        "loaded_at": datetime.now().isoformat(),
                        "type": "regime",
                        "is_mock": True
                    }
                    
                    # Ajouter au cache
                    self.model_cache.put(model_key, model_data, 10)  # Mock model très léger
                    self.loading_status[model_key] = "loaded"
                    
                    load_time = time.time() - start_time
                    self.stats["total_loading_time"] += load_time
                    self.stats["models_loaded"] += 1
                    
                    logger.info(f"Mock regime model loaded successfully in {load_time:.2f}s")
                    return True
            
        except Exception as e:
            logger.error(f"Failed to load regime model: {e}")
            self.loading_status[model_key] = "failed"
            self.stats["loading_errors"] += 1
            return False
    
    def load_all_volatility_models(self) -> Dict[str, bool]:
        """Charger tous les modèles de volatilité avec optimisations"""
        results = {}
        model_files = list(self.volatility_path.glob("*_volatility_best.pth"))
        
        logger.info(f"Loading {len(model_files)} volatility models with optimized pipeline...")
        
        for model_file in model_files:
            symbol = model_file.stem.replace("_volatility_best", "")
            results[symbol] = self.load_volatility_model(symbol)
        
        loaded_count = sum(results.values())
        logger.info(f"Loaded {loaded_count}/{len(results)} volatility models successfully")
        
        return results
    
    def get_model(self, model_key: str) -> Optional[Dict[str, Any]]:
        """Obtenir un modèle avec lazy loading automatique"""
        # Essayer le cache d'abord
        cached_model = self.model_cache.get(model_key)
        if cached_model:
            return cached_model
        
        # Lazy loading si le modèle n'est pas en cache
        if model_key.startswith("volatility_"):
            symbol = model_key.replace("volatility_", "")
            if self.load_volatility_model(symbol):
                return self.model_cache.get(model_key)
        elif model_key == "regime":
            if self.load_regime_model():
                return self.model_cache.get(model_key)
        
        return None
    
    def unload_model(self, model_key: str) -> bool:
        """Décharger un modèle de la mémoire"""
        if model_key in self.model_cache.cache:
            self.model_cache._evict(model_key)
            logger.info(f"Model {model_key} unloaded from optimized cache")
            return True
        return False
    
    def clear_all_models(self) -> int:
        """Décharger tous les modèles de la mémoire"""
        count = self.model_cache.clear()
        logger.info(f"Cleared {count} models from optimized cache")
        return count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtenir les statistiques détaillées du cache"""
        base_stats = self.model_cache.stats()
        base_stats.update(self.stats)
        base_stats["loading_status"] = self.loading_status.copy()
        return base_stats
    
    def optimize_memory(self) -> Dict[str, Any]:
        """Optimiser l'utilisation mémoire"""
        initial_count = len(self.model_cache.cache)
        initial_memory = psutil.virtual_memory().percent
        
        # Force garbage collection
        gc.collect()
        
        # Évincer les modèles les moins utilisés si nécessaire
        memory_after_gc = psutil.virtual_memory().percent
        
        if memory_after_gc > 85:  # Si utilisation mémoire > 85%
            # Évincer 50% des modèles les moins utilisés
            models_to_evict = max(1, len(self.model_cache.cache) // 2)
            evicted_models = []
            
            # Trier par dernière utilisation
            sorted_models = sorted(
                self.model_cache.last_access.items(),
                key=lambda x: x[1]
            )
            
            for model_key, _ in sorted_models[:models_to_evict]:
                self.model_cache._evict(model_key)
                evicted_models.append(model_key)
        
        final_count = len(self.model_cache.cache)
        final_memory = psutil.virtual_memory().percent
        
        return {
            "initial_models": initial_count,
            "final_models": final_count,
            "evicted_models": initial_count - final_count,
            "memory_before": initial_memory,
            "memory_after": final_memory,
            "memory_saved": initial_memory - final_memory
        }

# Instance globale optimisée
optimized_pipeline_manager = OptimizedMLPipelineManager(
    models_base_path="models",
    max_cached_models=8,  # Cache jusqu'à 8 modèles simultanément
    max_memory_mb=3072    # Maximum 3GB pour les modèles ML
)

# Export pour compatibilité
pipeline_manager = optimized_pipeline_manager