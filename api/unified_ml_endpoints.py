"""
Unified ML Pipeline API Endpoints
Endpoints consolidés pour la gestion centralisée des modèles ML
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from services.ml_pipeline_manager import pipeline_manager
from api.utils.cache import cache_get, cache_set, cache_clear_expired

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ml/pipeline", tags=["ML Pipeline Manager"])

# Cache pour les endpoints ML unifiés
_unified_ml_cache = {}

@router.get("/status")
async def get_unified_pipeline_status():
    """
    Obtenir le statut complet du pipeline ML unifié
    """
    # Vérifier le cache (TTL de 1 minute)
    cache_key = "pipeline_status"
    cached_result = cache_get(_unified_ml_cache, cache_key, 60)
    if cached_result:
        logger.info("Returning cached pipeline status")
        return cached_result
    
    try:
        # Utiliser le pipeline manager pour obtenir le statut
        status = pipeline_manager.get_pipeline_status()
        
        result = {
            "success": True,
            "pipeline_status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        # Mettre en cache le résultat
        cache_set(_unified_ml_cache, cache_key, result)
        cache_clear_expired(_unified_ml_cache, 60)
        
        logger.info("Pipeline status retrieved successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        # Fallback avec statut de base si le pipeline manager échoue
        fallback_status = {
            "pipeline_initialized": False,
            "models_base_path": "models",
            "timestamp": datetime.now().isoformat(),
            "volatility_models": {"models_count": 21, "models_loaded": 0, "last_updated": None},
            "regime_models": {"model_exists": True, "model_loaded": False, "last_updated": None},
            "loaded_models_count": 0,
            "total_models_count": 22,
            "error": str(e)
        }
        
        return {
            "success": True,
            "pipeline_status": fallback_status,
            "timestamp": datetime.now().isoformat(),
            "warning": "Using fallback status due to pipeline manager error"
        }

@router.post("/models/load-volatility")
async def load_volatility_models(
    symbols: Optional[List[str]] = Query(None, description="Symboles spécifiques à charger (None = tous)"),
    background_tasks: BackgroundTasks = None
):
    """
    Charger les modèles de volatilité
    """
    try:
        if symbols:
            # Charger des symboles spécifiques
            results = {}
            for symbol in symbols:
                results[symbol] = pipeline_manager.load_volatility_model(symbol)
        else:
            # Charger tous les modèles disponibles
            if background_tasks:
                background_tasks.add_task(_load_all_volatility_background)
                return {
                    "success": True,
                    "message": "Loading all volatility models in background",
                    "estimated_duration_minutes": 2
                }
            else:
                results = pipeline_manager.load_all_volatility_models()
        
        loaded_count = sum(1 for success in results.values() if success)
        
        # Invalider le cache de statut
        if "pipeline_status" in _unified_ml_cache:
            del _unified_ml_cache["pipeline_status"]
        
        return {
            "success": True,
            "loaded_models": loaded_count,
            "total_attempted": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error loading volatility models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _load_all_volatility_background():
    """Tâche en arrière-plan pour charger tous les modèles de volatilité"""
    try:
        results = pipeline_manager.load_all_volatility_models()
        logger.info(f"Background loading completed: {results}")
    except Exception as e:
        logger.error(f"Background loading failed: {e}")

@router.post("/models/load-regime")
async def load_regime_model():
    """
    Charger le modèle de détection de régime
    """
    try:
        success = pipeline_manager.load_regime_model()
        
        # Invalider le cache de statut
        if "pipeline_status" in _unified_ml_cache:
            del _unified_ml_cache["pipeline_status"]
        
        if success:
            return {
                "success": True,
                "message": "Regime detection model loaded successfully"
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail="Regime model files not found or incomplete"
            )
            
    except Exception as e:
        logger.error(f"Error loading regime model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/loaded")
async def get_loaded_models():
    """
    Obtenir la liste des modèles actuellement chargés
    """
    # Vérifier le cache (TTL de 30 secondes)
    cache_key = "loaded_models"
    cached_result = cache_get(_unified_ml_cache, cache_key, 30)
    if cached_result:
        logger.info("Returning cached loaded models")
        return cached_result
    
    try:
        summary = pipeline_manager.get_loaded_models_summary()
        
        result = {
            "success": True,
            "loaded_models": summary
        }
        
        # Mettre en cache le résultat
        cache_set(_unified_ml_cache, cache_key, result)
        cache_clear_expired(_unified_ml_cache, 30)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting loaded models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/models/{model_key}")
async def unload_model(model_key: str):
    """
    Décharger un modèle spécifique de la mémoire
    """
    try:
        success = pipeline_manager.unload_model(model_key)
        
        # Invalider les caches
        cache_keys_to_clear = ["pipeline_status", "loaded_models"]
        for key in cache_keys_to_clear:
            if key in _unified_ml_cache:
                del _unified_ml_cache[key]
        
        if success:
            return {
                "success": True,
                "message": f"Model {model_key} unloaded successfully"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Model {model_key} not found in loaded models"
            )
            
    except Exception as e:
        logger.error(f"Error unloading model {model_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/models/clear-all")
async def clear_all_models():
    """
    Décharger tous les modèles de la mémoire
    """
    try:
        count = pipeline_manager.clear_all_models()
        
        # Vider tout le cache
        _unified_ml_cache.clear()
        
        return {
            "success": True,
            "message": f"Cleared {count} models from memory",
            "cleared_count": count
        }
        
    except Exception as e:
        logger.error(f"Error clearing all models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/{model_key}/info")
async def get_model_info(model_key: str):
    """
    Obtenir les informations détaillées d'un modèle chargé
    """
    try:
        model_info = pipeline_manager.get_model(model_key)
        
        if not model_info:
            raise HTTPException(
                status_code=404,
                detail=f"Model {model_key} not loaded"
            )
        
        # Préparer les informations (sans inclure le modèle lui-même)
        safe_info = {
            "type": model_info.get("type"),
            "loaded_at": model_info.get("loaded_at"),
            "metadata": model_info.get("metadata", {}),
            "has_scaler": "scaler" in model_info,
            "has_features": "features" in model_info
        }
        
        return {
            "success": True,
            "model_key": model_key,
            "model_info": safe_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model info for {model_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/summary")
async def get_performance_summary():
    """
    Obtenir un résumé des performances des modèles
    """
    # Vérifier le cache (TTL de 5 minutes)
    cache_key = "performance_summary"
    cached_result = cache_get(_unified_ml_cache, cache_key, 300)
    if cached_result:
        logger.info("Returning cached performance summary")
        return cached_result
    
    try:
        loaded_models = pipeline_manager.get_loaded_models_summary()
        
        # Collecter les métriques de performance si disponibles
        performance_data = {}
        for model_key in pipeline_manager.loaded_models.keys():
            perf = pipeline_manager.get_model_performance(model_key)
            if perf:
                performance_data[model_key] = perf
        
        result = {
            "success": True,
            "summary": {
                "total_loaded_models": loaded_models["total_loaded"],
                "models_by_type": loaded_models["by_type"],
                "performance_data_available": len(performance_data),
                "performance_metrics": performance_data
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Mettre en cache le résultat
        cache_set(_unified_ml_cache, cache_key, result)
        cache_clear_expired(_unified_ml_cache, 300)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting performance summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/clear")
async def clear_ml_cache():
    """
    Vider le cache des endpoints ML
    """
    try:
        cache_size = len(_unified_ml_cache)
        _unified_ml_cache.clear()
        
        return {
            "success": True,
            "message": f"Cleared {cache_size} cache entries",
            "cleared_entries": cache_size
        }
        
    except Exception as e:
        logger.error(f"Error clearing ML cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))