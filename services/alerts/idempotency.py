"""
Gestionnaire d'idempotency pour éviter les double-actions

Simple système de cache avec TTL pour détecter et éviter les requêtes dupliquées.
Intégré avec Redis si disponible, sinon cache mémoire local.
"""

import logging
import time
import threading
from typing import Dict, Any, Optional, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class IdempotencyManager:
    """
    Gestionnaire d'idempotency avec TTL
    
    Stocke les clés d'idempotency avec leur réponse pendant une durée limitée
    pour éviter les double-exécutions (ex: double-clic UI).
    """
    
    def __init__(self, redis_client=None, default_ttl_seconds: int = 300):
        self.redis_client = redis_client
        self.default_ttl = default_ttl_seconds
        
        # Cache mémoire local (fallback)
        self._local_cache = {}
        self._cache_lock = threading.RLock()
        
        # Nettoyage périodique cache local
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # 1 minute
        
        self.redis_available = redis_client is not None
        logger.info(f"IdempotencyManager initialized (redis={self.redis_available})")
    
    def check_and_store(self, key: str, response_data: Dict[str, Any], ttl_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Vérifie si la clé existe et stocke la nouvelle réponse
        
        Args:
            key: Clé d'idempotency unique
            response_data: Données de réponse à stocker
            ttl_seconds: TTL custom, ou default_ttl si None
            
        Returns:
            Réponse précédente si clé existante, None si nouvelle clé
        """
        ttl = ttl_seconds or self.default_ttl
        
        try:
            if self.redis_available:
                return self._redis_check_and_store(key, response_data, ttl)
            else:
                return self._local_check_and_store(key, response_data, ttl)
                
        except Exception as e:
            logger.error(f"Error in idempotency check: {e}")
            # En cas d'erreur, considérer comme nouvelle requête
            return None
    
    def _redis_check_and_store(self, key: str, response_data: Dict[str, Any], ttl: int) -> Optional[Dict[str, Any]]:
        """Implémentation Redis avec SET NX"""
        try:
            cache_key = f"idempotency:{key}"
            
            # Vérifier si clé existe
            existing = self.redis_client.get(cache_key)
            if existing:
                import json
                logger.debug(f"Idempotency key {key} found in Redis")
                return json.loads(existing)
            
            # Stocker nouvelle réponse
            import json
            self.redis_client.setex(cache_key, ttl, json.dumps(response_data))
            logger.debug(f"Idempotency key {key} stored in Redis (TTL {ttl}s)")
            
            return None  # Nouvelle clé
            
        except Exception as e:
            logger.error(f"Redis idempotency error: {e}")
            # Fallback vers cache local
            return self._local_check_and_store(key, response_data, ttl)
    
    def _local_check_and_store(self, key: str, response_data: Dict[str, Any], ttl: int) -> Optional[Dict[str, Any]]:
        """Implémentation cache mémoire local"""
        with self._cache_lock:
            # Nettoyage périodique
            self._cleanup_expired()
            
            # Vérifier si clé existe et valide
            if key in self._local_cache:
                entry = self._local_cache[key]
                if time.time() < entry["expires_at"]:
                    logger.debug(f"Idempotency key {key} found in local cache")
                    return entry["data"]
                else:
                    # Clé expirée
                    del self._local_cache[key]
            
            # Stocker nouvelle entrée
            expires_at = time.time() + ttl
            self._local_cache[key] = {
                "data": response_data,
                "expires_at": expires_at,
                "created_at": time.time()
            }
            
            logger.debug(f"Idempotency key {key} stored in local cache (TTL {ttl}s)")
            return None  # Nouvelle clé
    
    def _cleanup_expired(self):
        """Nettoie les entrées expirées du cache local"""
        now = time.time()
        
        # Nettoyage seulement si intervalle écoulé
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        expired_keys = [
            key for key, entry in self._local_cache.items()
            if now >= entry["expires_at"]
        ]
        
        for key in expired_keys:
            del self._local_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired idempotency keys")
        
        self._last_cleanup = now
    
    def invalidate(self, key: str) -> bool:
        """Invalide manuellement une clé d'idempotency"""
        try:
            if self.redis_available:
                result = self.redis_client.delete(f"idempotency:{key}")
                return result > 0
            else:
                with self._cache_lock:
                    if key in self._local_cache:
                        del self._local_cache[key]
                        return True
                    return False
                    
        except Exception as e:
            logger.error(f"Error invalidating idempotency key: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Statistiques du gestionnaire d'idempotency"""
        stats = {
            "redis_available": self.redis_available,
            "default_ttl_seconds": self.default_ttl
        }
        
        if not self.redis_available:
            with self._cache_lock:
                stats.update({
                    "local_cache_size": len(self._local_cache),
                    "last_cleanup": self._last_cleanup
                })
        
        return stats

# Instance globale
_idempotency_manager = None

def get_idempotency_manager(redis_client=None) -> IdempotencyManager:
    """Factory pour instance globale"""
    global _idempotency_manager
    
    if _idempotency_manager is None:
        _idempotency_manager = IdempotencyManager(redis_client)
    
    return _idempotency_manager