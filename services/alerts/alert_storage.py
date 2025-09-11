"""
Stockage et persistance des alertes avec résilience multi-worker

Implémente un système hybride Redis ZSET/HASH + fichier JSON + in-memory avec:
- Redis ZSET pour indexation temporelle + HASH pour données
- Lua scripts atomiques pour opérations complexes  
- Cascade fallback: Redis → File → In-memory
- Single scheduler protection avec SETNX
- Rotation automatique et TTL
- Observabilité avec métriques dégradées
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from filelock import FileLock
from contextlib import contextmanager

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .alert_types import Alert, AlertType, AlertSeverity

logger = logging.getLogger(__name__)

class AlertStorage:
    """
    Stockage hybride alertes avec résilience multi-worker
    
    Features Phase 2A:
    - Redis ZSET/HASH architecture pour performance
    - Lua scripts atomiques pour opérations critiques
    - Cascade fallback: Redis → File → In-memory
    - Dedup/rate-limit distribués avec TTL
    - Auto-rotation et purge intelligente
    - Métriques dégradation observabilité
    """
    
    def __init__(self, 
                 redis_url: Optional[str] = None,
                 json_file: str = "data/alerts.json",
                 max_alerts: int = 1000,
                 purge_days: int = 30,
                 enable_fallback_cascade: bool = True):
        
        self.json_file = Path(json_file)
        self.json_file.parent.mkdir(exist_ok=True)
        self.lock_file = self.json_file.with_suffix('.lock')
        self.max_alerts = max_alerts
        self.purge_days = purge_days
        self.enable_fallback_cascade = enable_fallback_cascade
        
        # Redis connection (optionnel)
        self.redis_client = None
        self.redis_available = False
        self.storage_mode = "in_memory"  # Track current storage mode
        self._degraded_alerts = []  # In-memory fallback
        self._degraded_metrics = {"redis_failures": 0, "file_failures": 0}
        
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, 
                                                  decode_responses=True,
                                                  socket_timeout=2,
                                                  socket_connect_timeout=2)
                self.redis_client.ping()
                self.redis_available = True
                self.storage_mode = "redis"
                logger.info("Redis connection established for alert storage")
                # Initialize Redis Lua scripts
                self._register_lua_scripts()
            except Exception as e:
                logger.warning(f"Redis unavailable, using file fallback: {e}")
                self.redis_available = False
                self.storage_mode = "file" if self.enable_fallback_cascade else "in_memory"
        
        # Thread-local storage pour cache
        self._local = threading.local()
        
        # Initialiser le stockage
        self._ensure_storage_exists()
        
        # Redis keys namespace
        self.ALERTS_ZSET = "alerts:timeline"  # ZSET for time ordering
        self.ALERTS_HASH_PREFIX = "alerts:data:"  # HASH prefix for alert data
        self.ACTIVE_ALERTS_SET = "alerts:active"  # SET for active alerts
        self.RATE_LIMIT_PREFIX = "alerts:rate:"  # Rate limit counters
        self.DEDUP_PREFIX = "alerts:dedup:"  # Deduplication keys
    
    @contextmanager
    def _file_lock(self):
        """Context manager pour file locking"""
        lock = FileLock(str(self.lock_file), timeout=5)
        try:
            with lock:
                yield
        except Exception as e:
            logger.error(f"File lock error: {e}")
            raise
    
    def _ensure_storage_exists(self):
        """Initialise le fichier JSON s'il n'existe pas"""
        if not self.json_file.exists():
            with self._file_lock():
                initial_data = {
                    "alerts": [],
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "version": "1.0",
                        "last_purge": datetime.now().isoformat()
                    }
                }
                self.json_file.write_text(json.dumps(initial_data, indent=2))
    
    def acquire_scheduler_lock(self, host_id: str, ttl_seconds: int = 90) -> bool:
        """
        Acquiert le verrou scheduler (un seul actif par cluster)
        
        Returns:
            True si verrou acquis, False sinon
        """
        lock_key = "alerts:scheduler_lock"
        
        if self.redis_available:
            try:
                # SETNX avec TTL atomique
                result = self.redis_client.set(lock_key, host_id, nx=True, ex=ttl_seconds)
                if result:
                    logger.info(f"Scheduler lock acquired by {host_id}")
                    return True
                else:
                    current_holder = self.redis_client.get(lock_key)
                    logger.debug(f"Scheduler lock held by {current_holder}")
                    return False
                    
            except Exception as e:
                logger.error(f"Redis scheduler lock error: {e}")
                # Fallback vers file lock
        
        # File-based fallback
        try:
            lock_file = self.json_file.parent / "scheduler.lock"
            
            if lock_file.exists():
                # Vérifier TTL
                stat = lock_file.stat()
                age = time.time() - stat.st_mtime
                
                if age < ttl_seconds:
                    return False  # Verrou encore valide
                else:
                    lock_file.unlink()  # Verrou expiré
            
            # Créer nouveau verrou
            lock_file.write_text(f"{host_id}:{datetime.now().isoformat()}")
            logger.info(f"File scheduler lock acquired by {host_id}")
            return True
            
        except Exception as e:
            logger.error(f"File scheduler lock error: {e}")
            return False
    
    def release_scheduler_lock(self, host_id: str):
        """Libère le verrou scheduler"""
        if self.redis_available:
            try:
                # Libération conditionnelle (seulement si détenteur)
                script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                self.redis_client.eval(script, 1, "alerts:scheduler_lock", host_id)
                logger.info(f"Scheduler lock released by {host_id}")
                return
            except Exception as e:
                logger.error(f"Redis lock release error: {e}")
        
        # File fallback
        try:
            lock_file = self.json_file.parent / "scheduler.lock"
            if lock_file.exists():
                content = lock_file.read_text()
                if content.startswith(f"{host_id}:"):
                    lock_file.unlink()
                    logger.info(f"File scheduler lock released by {host_id}")
        except Exception as e:
            logger.error(f"File lock release error: {e}")
    
    def store_alert(self, alert: Alert) -> bool:
        """
        Stocke une nouvelle alerte avec dedup et cascade fallback
        
        Cascade: Redis → File → In-memory
        
        Returns:
            True si stockée, False si dupliquée ou erreur totale
        """
        if not self.enable_fallback_cascade:
            # Legacy behavior for backward compatibility
            return self._store_alert_legacy(alert)
        
        # Phase 2A: Cascade fallback
        try:
            # Try Redis first
            if self.storage_mode == "redis":
                success, reason = self._try_redis_store_alert(alert)
                if success:
                    return True
                elif "duplicate" in reason:
                    return False
                else:
                    # Redis failed, degrade to file
                    logger.warning(f"Redis storage failed for {alert.id}: {reason}, trying file")
                    self.storage_mode = "file"
            
            # Try File storage
            if self.storage_mode == "file":
                success, reason = self._try_file_store_alert(alert)
                if success:
                    return True
                elif "duplicate" in reason:
                    return False
                else:
                    # File failed, degrade to memory
                    logger.error(f"File storage failed for {alert.id}: {reason}, trying memory")
                    self.storage_mode = "in_memory"
            
            # Try In-memory (last resort)
            if self.storage_mode == "in_memory":
                success, reason = self._try_memory_store_alert(alert)
                if success:
                    # Alert stored but in degraded mode
                    logger.critical(f"Alert system degraded: storing in memory only")
                    return True
                elif "duplicate" in reason:
                    return False
                else:
                    logger.critical(f"Total storage failure for {alert.id}: {reason}")
                    return False
            
            return False
            
        except Exception as e:
            logger.critical(f"Critical error in store_alert cascade: {e}")
            return False
    
    def _store_alert_legacy(self, alert: Alert) -> bool:
        """Legacy store method for backward compatibility"""
        try:
            # Vérifier dedup
            if self._is_duplicate(alert):
                logger.debug(f"Alert {alert.id} is duplicate, skipping")
                return False
            
            # Stocker l'alerte
            alert_dict = alert.dict()
            alert_dict['created_at'] = alert.created_at.isoformat()
            
            with self._file_lock():
                data = self._load_json_data()
                data['alerts'].append(alert_dict)
                
                # Auto-rotation si trop d'alertes
                if len(data['alerts']) > self.max_alerts:
                    data['alerts'] = data['alerts'][-self.max_alerts:]
                    logger.info(f"Alert storage rotated to {self.max_alerts} entries")
                
                self._save_json_data(data)
            
            # Mettre à jour dedup cache
            self._update_dedup_cache(alert)
            
            logger.info(f"Alert {alert.id} stored successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error storing alert {alert.id}: {e}")
            return False
    
    def get_active_alerts(self, include_snoozed: bool = False) -> List[Alert]:
        """
        Récupère les alertes actives avec cascade fallback
        
        Cascade: Redis → File → In-memory
        
        Args:
            include_snoozed: Inclure les alertes snoozées
        """
        if not self.enable_fallback_cascade:
            # Legacy behavior
            return self._get_active_alerts_legacy(include_snoozed)
        
        # Phase 2A: Cascade fallback
        try:
            # Try Redis first
            if self.storage_mode == "redis":
                alerts, reason = self._try_redis_get_active_alerts(include_snoozed)
                if alerts is not None:
                    return alerts
                else:
                    logger.warning(f"Redis get active alerts failed: {reason}, trying file")
                    self.storage_mode = "file"
            
            # Try File storage
            if self.storage_mode == "file":
                alerts, reason = self._try_file_get_active_alerts(include_snoozed)
                if alerts is not None:
                    return alerts
                else:
                    logger.error(f"File get active alerts failed: {reason}, trying memory")
                    self.storage_mode = "in_memory"
            
            # Try In-memory (last resort)
            if self.storage_mode == "in_memory":
                alerts, reason = self._try_memory_get_active_alerts(include_snoozed)
                if alerts is not None:
                    return alerts
                else:
                    logger.critical(f"Total failure getting active alerts: {reason}")
                    return []
            
            return []
            
        except Exception as e:
            logger.critical(f"Critical error in get_active_alerts cascade: {e}")
            return []
    
    def _get_active_alerts_legacy(self, include_snoozed: bool = False) -> List[Alert]:
        """Legacy get_active_alerts for backward compatibility"""
        try:
            with self._file_lock():
                data = self._load_json_data()
            
            active_alerts = []
            now = datetime.now()
            
            for alert_dict in data['alerts']:
                # Skip si ACK ou résolue
                if alert_dict.get('acknowledged_at') or alert_dict.get('resolved_at'):
                    continue
                
                # Skip si snoozée (sauf si demandé)
                if not include_snoozed and alert_dict.get('snooze_until'):
                    snooze_until = datetime.fromisoformat(alert_dict['snooze_until'])
                    if now < snooze_until:
                        continue
                
                # Convertir en objet Alert
                alert_dict['created_at'] = datetime.fromisoformat(alert_dict['created_at'])
                
                # Convertir dates optionnelles
                for date_field in ['acknowledged_at', 'snooze_until', 'resolved_at', 'applied_at']:
                    if alert_dict.get(date_field):
                        alert_dict[date_field] = datetime.fromisoformat(alert_dict[date_field])
                
                alert = Alert(**alert_dict)
                active_alerts.append(alert)
            
            return active_alerts
            
        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return []
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Marque une alerte comme acquittée"""
        return self._update_alert_field(alert_id, {
            'acknowledged_at': datetime.now().isoformat(),
            'acknowledged_by': acknowledged_by
        })
    
    def snooze_alert(self, alert_id: str, minutes: int) -> bool:
        """Snooze une alerte pour X minutes"""
        snooze_until = datetime.now() + timedelta(minutes=minutes)
        return self._update_alert_field(alert_id, {
            'snooze_until': snooze_until.isoformat()
        })
    
    def mark_alert_applied(self, alert_id: str, applied_by: str) -> bool:
        """Marque une alerte comme appliquée (action exécutée)"""
        return self._update_alert_field(alert_id, {
            'applied_at': datetime.now().isoformat(),
            'applied_by': applied_by
        })
    
    def check_rate_limit(self, alert_type: AlertType, severity: AlertSeverity, 
                        window_minutes: int = 30) -> bool:
        """
        Vérifie si l'alerte respecte les limites de taux avec cascade fallback
        
        Returns:
            True si OK, False si rate-limited
        """
        if not self.enable_fallback_cascade:
            return self._check_rate_limit_legacy(alert_type, severity, window_minutes)
        
        # Phase 2A: Try Redis rate limit with fallback
        try:
            # Try Redis first
            if self.storage_mode == "redis":
                result, reason = self._try_redis_rate_limit(alert_type, severity, window_minutes)
                if result is not None:
                    return result
                else:
                    logger.warning(f"Redis rate limit check failed: {reason}, using file fallback")
                    # Continue to file fallback
            
            # File fallback for rate limiting
            return self._check_rate_limit_legacy(alert_type, severity, window_minutes)
            
        except Exception as e:
            logger.error(f"Error in rate limit check cascade: {e}")
            return True  # Allow on error
    
    def _check_rate_limit_legacy(self, alert_type: AlertType, severity: AlertSeverity, 
                                window_minutes: int = 30) -> bool:
        """Legacy rate limit check"""
        try:
            # Budgets par gravité (par fenêtre de 30min)
            rate_limits = {
                AlertSeverity.S3: 1,   # Max 1 S3 / 30min
                AlertSeverity.S2: 2,   # Max 2 S2 / 30min  
                AlertSeverity.S1: 5    # Max 5 S1 / 30min
            }
            
            limit = rate_limits.get(severity, 999)
            rate_key = f"rate_limit:{alert_type}:{severity}"
            
            if self.redis_available:
                try:
                    # Pipeline Redis pour atomicité
                    pipe = self.redis_client.pipeline()
                    pipe.incr(rate_key)
                    pipe.expire(rate_key, window_minutes * 60)
                    results = pipe.execute()
                    
                    current_count = results[0]
                    is_within_limit = current_count <= limit
                    
                    if not is_within_limit:
                        logger.warning(f"Rate limit exceeded for {alert_type}:{severity} "
                                     f"({current_count}/{limit})")
                    
                    return is_within_limit
                    
                except Exception as e:
                    logger.error(f"Redis rate limit check error: {e}")
                    # Fallback vers file
            
            # File-based fallback (simplifié)
            now = datetime.now()
            cutoff = now - timedelta(minutes=window_minutes)
            
            with self._file_lock():
                data = self._load_json_data()
                
                # Compter alertes récentes du même type/gravité
                count = 0
                for alert_dict in data['alerts']:
                    if (alert_dict['alert_type'] == alert_type and 
                        alert_dict['severity'] == severity):
                        
                        created_at = datetime.fromisoformat(alert_dict['created_at'])
                        if created_at > cutoff:
                            count += 1
                
                return count < limit
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True  # En cas d'erreur, autoriser
    
    def purge_old_alerts(self) -> int:
        """
        Purge les alertes anciennes (>30 jours)
        
        Returns:
            Nombre d'alertes supprimées
        """
        try:
            cutoff = datetime.now() - timedelta(days=self.purge_days)
            
            with self._file_lock():
                data = self._load_json_data()
                original_count = len(data['alerts'])
                
                # Filtrer alertes récentes
                data['alerts'] = [
                    alert for alert in data['alerts']
                    if datetime.fromisoformat(alert['created_at']) > cutoff
                ]
                
                data['metadata']['last_purge'] = datetime.now().isoformat()
                self._save_json_data(data)
                
                purged_count = original_count - len(data['alerts'])
                
                if purged_count > 0:
                    logger.info(f"Purged {purged_count} old alerts")
                
                return purged_count
            
        except Exception as e:
            logger.error(f"Error purging alerts: {e}")
            return 0
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retourne métriques de stockage pour observabilité avec Phase 2A"""
        try:
            # Base metrics from current storage mode
            base_metrics = self._get_storage_metrics()
            
            # Phase 2A: Add degradation metrics
            degradation_metrics = {
                "storage_mode": self.storage_mode,
                "fallback_cascade_enabled": self.enable_fallback_cascade,
                "redis_failures": self._degraded_metrics.get("redis_failures", 0),
                "file_failures": self._degraded_metrics.get("file_failures", 0),
                "memory_alerts_count": len(self._degraded_alerts),
                "is_degraded": self.storage_mode == "in_memory"
            }
            
            # Redis-specific metrics (if available)
            redis_metrics = {}
            if self.redis_available and self.storage_mode == "redis":
                try:
                    # Redis info
                    redis_info = self.redis_client.info('memory')
                    redis_metrics = {
                        "redis_memory_used": redis_info.get('used_memory', 0),
                        "redis_memory_peak": redis_info.get('used_memory_peak', 0),
                        "redis_connected_clients": redis_info.get('connected_clients', 0)
                    }
                    
                    # Count alerts in Redis structures
                    redis_metrics.update({
                        "redis_timeline_count": self.redis_client.zcard(self.ALERTS_ZSET) or 0,
                        "redis_active_count": self.redis_client.scard(self.ACTIVE_ALERTS_SET) or 0
                    })
                except Exception as e:
                    redis_metrics["redis_metrics_error"] = str(e)
            
            # Combine all metrics
            return {
                **base_metrics,
                **degradation_metrics,
                **redis_metrics,
                "phase": "2A",
                "lua_scripts_loaded": all([
                    hasattr(self, '_store_alert_script') and self._store_alert_script,
                    hasattr(self, '_rate_limit_script') and self._rate_limit_script,
                    hasattr(self, '_get_active_alerts_script') and self._get_active_alerts_script,
                    hasattr(self, '_update_alert_script') and self._update_alert_script
                ]) if self.redis_available else False
            }
            
        except Exception as e:
            logger.error(f"Error getting storage metrics: {e}")
            return {"error": str(e), "storage_mode": getattr(self, 'storage_mode', 'unknown')}
    
    def _get_storage_metrics(self) -> Dict[str, Any]:
        """Get metrics from current storage mode"""
        try:
            if self.storage_mode == "redis" and self.redis_available:
                return self._get_redis_storage_metrics()
            elif self.storage_mode == "file" or not self.enable_fallback_cascade:
                return self._get_file_storage_metrics()
            elif self.storage_mode == "in_memory":
                return self._get_memory_storage_metrics()
            else:
                return self._get_file_storage_metrics()  # Default fallback
        except Exception as e:
            logger.error(f"Error getting storage metrics for mode {self.storage_mode}: {e}")
            return {"error": str(e)}
    
    def _get_redis_storage_metrics(self) -> Dict[str, Any]:
        """Get metrics from Redis storage"""
        try:
            # This would require implementing Redis-specific metrics gathering
            # For now, fall back to file metrics as baseline
            return self._get_file_storage_metrics()
        except Exception as e:
            return {"error": f"redis_metrics_error: {e}"}
    
    def _get_file_storage_metrics(self) -> Dict[str, Any]:
        """Get metrics from file storage (original implementation)"""
        try:
            with self._file_lock():
                data = self._load_json_data()
            
            now = datetime.now()
            
            # Statistiques par type/gravité
            stats_by_type = {}
            stats_by_severity = {}
            active_count = 0
            snoozed_count = 0
            
            for alert in data['alerts']:
                # Stats par type
                alert_type = alert['alert_type']
                stats_by_type[alert_type] = stats_by_type.get(alert_type, 0) + 1
                
                # Stats par gravité
                severity = alert['severity']
                stats_by_severity[severity] = stats_by_severity.get(severity, 0) + 1
                
                # Stats état
                if not alert.get('acknowledged_at') and not alert.get('resolved_at'):
                    active_count += 1
                    
                    if alert.get('snooze_until'):
                        snooze_until = datetime.fromisoformat(alert['snooze_until'])
                        if now < snooze_until:
                            snoozed_count += 1
            
            return {
                "total_alerts": len(data['alerts']),
                "active_alerts": active_count,
                "snoozed_alerts": snoozed_count,
                "stats_by_type": stats_by_type,
                "stats_by_severity": stats_by_severity,
                "redis_available": self.redis_available,
                "last_purge": data['metadata'].get('last_purge'),
                "storage_file": str(self.json_file),
                "max_alerts": self.max_alerts
            }
            
        except Exception as e:
            return {"error": f"file_metrics_error: {e}"}
    
    def _get_memory_storage_metrics(self) -> Dict[str, Any]:
        """Get metrics from in-memory storage (degraded mode)"""
        try:
            now = datetime.now()
            
            stats_by_type = {}
            stats_by_severity = {}
            active_count = 0
            snoozed_count = 0
            
            for alert in self._degraded_alerts:
                # Stats par type
                alert_type = alert['alert_type']
                stats_by_type[alert_type] = stats_by_type.get(alert_type, 0) + 1
                
                # Stats par gravité
                severity = alert['severity']
                stats_by_severity[severity] = stats_by_severity.get(severity, 0) + 1
                
                # Stats état
                if not alert.get('acknowledged_at') and not alert.get('resolved_at'):
                    active_count += 1
                    
                    if alert.get('snooze_until'):
                        try:
                            snooze_until = datetime.fromisoformat(alert['snooze_until'])
                            if now < snooze_until:
                                snoozed_count += 1
                        except:
                            pass
            
            return {
                "total_alerts": len(self._degraded_alerts),
                "active_alerts": active_count,
                "snoozed_alerts": snoozed_count,
                "stats_by_type": stats_by_type,
                "stats_by_severity": stats_by_severity,
                "redis_available": self.redis_available,
                "last_purge": "memory_mode_no_purge",
                "storage_file": "memory_only",
                "max_alerts": self.max_alerts
            }
            
        except Exception as e:
            return {"error": f"memory_metrics_error: {e}"}
    
    def ping(self) -> bool:
        """Test de connectivité storage pour health checks"""
        try:
            if self.redis_available:
                # Test Redis ping
                response = self.redis_client.ping()
                return response is True
            else:
                # Test file access
                return self.json_file.exists() or self.json_file.parent.exists()
                
        except Exception as e:
            logger.error(f"Storage ping failed: {e}")
            return False
    
    # Méthodes privées
    
    def _load_json_data(self) -> Dict[str, Any]:
        """Charge les données JSON avec gestion d'erreur"""
        try:
            return json.loads(self.json_file.read_text())
        except Exception as e:
            logger.error(f"Error loading JSON data: {e}")
            return {"alerts": [], "metadata": {}}
    
    def _save_json_data(self, data: Dict[str, Any]):
        """Sauvegarde les données JSON"""
        self.json_file.write_text(json.dumps(data, indent=2))
    
    def _is_duplicate(self, alert: Alert) -> bool:
        """
        Vérifie si l'alerte est un duplicata (dedup intelligent)
        
        Clé de dedup: (type, bucket_5min, direction/valeur)
        """
        try:
            # Créer clé de dedup temporelle (buckets de 5 minutes)
            bucket_time = alert.created_at.replace(minute=alert.created_at.minute // 5 * 5, 
                                                 second=0, microsecond=0)
            
            # Create stable signature from rounded values to avoid tiny differences
            current_val = alert.data.get("current_value", 0)
            threshold_val = alert.data.get("adaptive_threshold", 0)
            
            # Round to 2 decimal places for stability  
            current_rounded = round(float(current_val), 2) if current_val else 0
            threshold_rounded = round(float(threshold_val), 2) if threshold_val else 0
            
            direction = "up" if current_rounded > threshold_rounded else "down"
            
            # Include rounded values in key for more specific dedup
            value_signature = f"{current_rounded}:{threshold_rounded}"
            dedup_key = f"{alert.alert_type}:{bucket_time.isoformat()}:{direction}:{value_signature}"
            
            if self.redis_available:
                try:
                    # Check + set atomique avec TTL 5 minutes
                    result = self.redis_client.set(f"dedup:{dedup_key}", "1", nx=True, ex=300)
                    return not result  # Si set failed, c'est un duplicate
                except Exception as e:
                    logger.error(f"Redis dedup check error: {e}")
                    # Fallback vers file
            
            # File-based dedup (moins précis mais fonctionnel)
            cache = getattr(self._local, 'dedup_cache', set())
            
            if dedup_key in cache:
                return True
            
            # Nettoyer cache ancien (>5 min)
            cutoff = datetime.now() - timedelta(minutes=5)
            cache = {key for key in cache if not key.endswith(cutoff.strftime(":%Y-%m-%dT%H:%M"))}
            
            cache.add(dedup_key)
            self._local.dedup_cache = cache
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return False  # En cas d'erreur, considérer comme non-duplicate
    
    def _update_dedup_cache(self, alert: Alert):
        """Met à jour le cache de deduplication après stockage"""
        # Implémentation pour cohérence avec _is_duplicate
        pass
    
    def _update_alert_field(self, alert_id: str, fields: Dict[str, str]) -> bool:
        """Met à jour des champs d'une alerte spécifique"""
        try:
            with self._file_lock():
                data = self._load_json_data()
                
                for alert_dict in data['alerts']:
                    if alert_dict['id'] == alert_id:
                        alert_dict.update(fields)
                        self._save_json_data(data)
                        logger.info(f"Alert {alert_id} updated: {fields}")
                        return True
                
                logger.warning(f"Alert {alert_id} not found for update")
                return False
                
        except Exception as e:
            logger.error(f"Error updating alert {alert_id}: {e}")
            return False
    
    # ==========================================
    # PHASE 2A: Redis ZSET/HASH + Lua Scripts
    # ==========================================
    
    def _register_lua_scripts(self):
        """Register Lua scripts for atomic operations"""
        if not self.redis_available:
            return
            
        try:
            # Script 1: Atomic alert storage with dedup + ZSET + HASH
            self._store_alert_script = self.redis_client.register_script("""
                local alert_id = ARGV[1]
                local alert_data = ARGV[2]
                local created_timestamp = ARGV[3]
                local dedup_key = ARGV[4]
                local dedup_ttl = ARGV[5]
                local is_active = ARGV[6]
                
                -- Check dedup first
                if redis.call('EXISTS', dedup_key) == 1 then
                    return {0, 'duplicate'}
                end
                
                -- Set dedup with TTL
                redis.call('SETEX', dedup_key, dedup_ttl, '1')
                
                -- Store in ZSET (timeline) and HASH (data)
                redis.call('ZADD', KEYS[1], created_timestamp, alert_id)
                redis.call('HSET', KEYS[2] .. alert_id, unpack(cjson.decode(alert_data)))
                
                -- Add to active set if active
                if is_active == '1' then
                    redis.call('SADD', KEYS[3], alert_id)
                end
                
                return {1, 'stored'}
            """)
            
            # Script 2: Rate limit check with sliding window
            self._rate_limit_script = self.redis_client.register_script("""
                local rate_key = KEYS[1]
                local window_seconds = ARGV[1]
                local max_count = ARGV[2]
                local current_time = ARGV[3]
                
                -- Remove expired entries
                redis.call('ZREMRANGEBYSCORE', rate_key, '-inf', current_time - window_seconds)
                
                -- Count current entries
                local current_count = redis.call('ZCARD', rate_key)
                
                if current_count >= tonumber(max_count) then
                    return {0, current_count, max_count}
                end
                
                -- Add current entry
                redis.call('ZADD', rate_key, current_time, current_time)
                redis.call('EXPIRE', rate_key, window_seconds)
                
                return {1, current_count + 1, max_count}
            """)
            
            # Script 3: Batch get active alerts with filtering
            self._get_active_alerts_script = self.redis_client.register_script("""
                local active_set = KEYS[1]
                local data_prefix = KEYS[2]
                local include_snoozed = ARGV[1] == '1'
                local current_time = tonumber(ARGV[2])
                
                local active_ids = redis.call('SMEMBERS', active_set)
                local result = {}
                
                for i, alert_id in ipairs(active_ids) do
                    local alert_data = redis.call('HGETALL', data_prefix .. alert_id)
                    
                    if #alert_data > 0 then
                        -- Convert array to hash table
                        local alert_hash = {}
                        for j = 1, #alert_data, 2 do
                            alert_hash[alert_data[j]] = alert_data[j + 1]
                        end
                        
                        -- Check if should include
                        local should_include = true
                        
                        -- Skip if ACK or resolved
                        if alert_hash.acknowledged_at and alert_hash.acknowledged_at ~= '' then
                            should_include = false
                        elseif alert_hash.resolved_at and alert_hash.resolved_at ~= '' then
                            should_include = false
                        end
                        
                        -- Skip if snoozed (unless include_snoozed)
                        if not include_snoozed and alert_hash.snooze_until and alert_hash.snooze_until ~= '' then
                            -- Simple timestamp comparison (assumes ISO format can be compared as strings)
                            if alert_hash.snooze_until > tostring(current_time) then
                                should_include = false
                            end
                        end
                        
                        if should_include then
                            table.insert(result, cjson.encode(alert_hash))
                        end
                    end
                end
                
                return result
            """)
            
            # Script 4: Atomic alert update
            self._update_alert_script = self.redis_client.register_script("""
                local alert_id = ARGV[1]
                local updates = cjson.decode(ARGV[2])
                local hash_key = KEYS[1] .. alert_id
                
                if redis.call('EXISTS', hash_key) == 0 then
                    return 0
                end
                
                for field, value in pairs(updates) do
                    redis.call('HSET', hash_key, field, value)
                end
                
                return 1
            """)
            
            logger.info("Redis Lua scripts registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register Lua scripts: {e}")
            self._store_alert_script = None
            self._rate_limit_script = None
            self._get_active_alerts_script = None
            self._update_alert_script = None
    
    def _try_redis_store_alert(self, alert: Alert) -> Tuple[bool, str]:
        """Try to store alert using Redis ZSET/HASH with Lua script"""
        if not self.redis_available or not self._store_alert_script:
            return False, "redis_unavailable"
            
        try:
            # Prepare data
            alert_dict = alert.dict()
            alert_dict['created_at'] = alert.created_at.isoformat()
            
            # Convert to JSON for Lua script
            alert_data = json.dumps(alert_dict)
            created_timestamp = alert.created_at.timestamp()
            
            # Create dedup key with stable signature
            bucket_time = alert.created_at.replace(minute=alert.created_at.minute // 5 * 5, 
                                                 second=0, microsecond=0)
            
            # Create stable signature from rounded values to avoid tiny differences
            current_val = alert.data.get("current_value", 0)
            threshold_val = alert.data.get("adaptive_threshold", 0)
            
            # Round to 2 decimal places for stability  
            current_rounded = round(float(current_val), 2) if current_val else 0
            threshold_rounded = round(float(threshold_val), 2) if threshold_val else 0
            
            direction = "up" if current_rounded > threshold_rounded else "down"
            
            # Include rounded values in key for more specific dedup
            value_signature = f"{current_rounded}:{threshold_rounded}"
            dedup_key = f"{self.DEDUP_PREFIX}{alert.alert_type}:{bucket_time.isoformat()}:{direction}:{value_signature}"
            dedup_ttl = 300  # 5 minutes
            
            # Determine if active
            is_active = "1" if not alert.acknowledged_at and not alert.resolved_at else "0"
            
            # Execute Lua script
            result = self._store_alert_script(
                keys=[self.ALERTS_ZSET, self.ALERTS_HASH_PREFIX, self.ACTIVE_ALERTS_SET],
                args=[alert.id, alert_data, created_timestamp, dedup_key, dedup_ttl, is_active]
            )
            
            if result[0] == 1:
                logger.info(f"Alert {alert.id} stored in Redis successfully")
                return True, "stored"
            else:
                logger.debug(f"Alert {alert.id} was duplicate in Redis")
                return False, result[1]
                
        except Exception as e:
            logger.error(f"Redis store failed for alert {alert.id}: {e}")
            self._degraded_metrics["redis_failures"] += 1
            return False, f"redis_error: {e}"
    
    def _try_redis_get_active_alerts(self, include_snoozed: bool = False) -> Tuple[Optional[List[Alert]], str]:
        """Try to get active alerts using Redis with Lua script"""
        if not self.redis_available or not self._get_active_alerts_script:
            return None, "redis_unavailable"
            
        try:
            current_time = datetime.now().timestamp()
            
            # Execute Lua script
            result = self._get_active_alerts_script(
                keys=[self.ACTIVE_ALERTS_SET, self.ALERTS_HASH_PREFIX],
                args=["1" if include_snoozed else "0", str(current_time)]
            )
            
            # Parse results
            alerts = []
            for alert_json in result:
                try:
                    alert_dict = json.loads(alert_json)
                    
                    # Convert timestamps back
                    alert_dict['created_at'] = datetime.fromisoformat(alert_dict['created_at'])
                    for date_field in ['acknowledged_at', 'snooze_until', 'resolved_at', 'applied_at']:
                        if alert_dict.get(date_field) and alert_dict[date_field] != '':
                            alert_dict[date_field] = datetime.fromisoformat(alert_dict[date_field])
                        else:
                            alert_dict[date_field] = None
                    
                    alert = Alert(**alert_dict)
                    alerts.append(alert)
                    
                except Exception as e:
                    logger.error(f"Failed to parse alert from Redis: {e}")
                    continue
            
            logger.debug(f"Retrieved {len(alerts)} active alerts from Redis")
            return alerts, "success"
            
        except Exception as e:
            logger.error(f"Redis get active alerts failed: {e}")
            self._degraded_metrics["redis_failures"] += 1
            return None, f"redis_error: {e}"
    
    def _try_redis_rate_limit(self, alert_type: AlertType, severity: AlertSeverity, 
                             window_minutes: int = 30) -> Tuple[Optional[bool], str]:
        """Try rate limit check using Redis with Lua script"""
        if not self.redis_available or not self._rate_limit_script:
            return None, "redis_unavailable"
            
        try:
            # Rate limits by severity
            rate_limits = {
                AlertSeverity.S3: 1,   # Max 1 S3 / 30min
                AlertSeverity.S2: 2,   # Max 2 S2 / 30min  
                AlertSeverity.S1: 5    # Max 5 S1 / 30min
            }
            
            max_count = rate_limits.get(severity, 999)
            rate_key = f"{self.RATE_LIMIT_PREFIX}{alert_type}:{severity}"
            window_seconds = window_minutes * 60
            current_time = time.time()
            
            # Execute Lua script
            result = self._rate_limit_script(
                keys=[rate_key],
                args=[str(window_seconds), str(max_count), str(current_time)]
            )
            
            is_allowed = result[0] == 1
            current_count = result[1]
            
            if not is_allowed:
                logger.warning(f"Rate limit exceeded for {alert_type}:{severity} "
                             f"({current_count}/{max_count})")
            
            return is_allowed, "success"
            
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            self._degraded_metrics["redis_failures"] += 1
            return None, f"redis_error: {e}"
    
    # ==========================================
    # PHASE 2A: Fallback Cascade System
    # ==========================================
    
    def _try_file_store_alert(self, alert: Alert) -> Tuple[bool, str]:
        """Try to store alert using file system"""
        try:
            # Use existing file storage logic
            if self._is_duplicate(alert):
                logger.debug(f"Alert {alert.id} is duplicate, skipping")
                return False, "duplicate"
            
            alert_dict = alert.dict()
            alert_dict['created_at'] = alert.created_at.isoformat()
            
            with self._file_lock():
                data = self._load_json_data()
                data['alerts'].append(alert_dict)
                
                # Auto-rotation
                if len(data['alerts']) > self.max_alerts:
                    data['alerts'] = data['alerts'][-self.max_alerts:]
                    logger.info(f"Alert storage rotated to {self.max_alerts} entries")
                
                self._save_json_data(data)
            
            logger.info(f"Alert {alert.id} stored in file successfully")
            return True, "stored"
            
        except Exception as e:
            logger.error(f"File store failed for alert {alert.id}: {e}")
            self._degraded_metrics["file_failures"] += 1
            return False, f"file_error: {e}"
    
    def _try_memory_store_alert(self, alert: Alert) -> Tuple[bool, str]:
        """Try to store alert in memory (last resort)"""
        try:
            # Simple in-memory dedup check
            alert_key = f"{alert.alert_type}_{alert.created_at.strftime('%Y%m%d%H%M')}"
            existing_keys = [a.get('_memory_key') for a in self._degraded_alerts]
            
            if alert_key in existing_keys:
                logger.debug(f"Alert {alert.id} is duplicate in memory, skipping")
                return False, "duplicate"
            
            # Store in memory
            alert_dict = alert.dict()
            alert_dict['created_at'] = alert.created_at.isoformat()
            alert_dict['_memory_key'] = alert_key
            alert_dict['_stored_mode'] = 'memory'
            alert_dict['_stored_at'] = datetime.now().isoformat()
            
            self._degraded_alerts.append(alert_dict)
            
            # Auto-rotation for memory
            if len(self._degraded_alerts) > self.max_alerts:
                self._degraded_alerts = self._degraded_alerts[-self.max_alerts:]
                logger.info(f"Memory alert storage rotated to {self.max_alerts} entries")
            
            logger.warning(f"Alert {alert.id} stored in MEMORY (degraded mode)")
            return True, "stored_degraded"
            
        except Exception as e:
            logger.error(f"Memory store failed for alert {alert.id}: {e}")
            return False, f"memory_error: {e}"
    
    def _try_file_get_active_alerts(self, include_snoozed: bool = False) -> Tuple[Optional[List[Alert]], str]:
        """Try to get active alerts from file"""
        try:
            # Use existing file logic
            with self._file_lock():
                data = self._load_json_data()
            
            active_alerts = []
            now = datetime.now()
            
            for alert_dict in data['alerts']:
                # Skip if ACK or resolved
                if alert_dict.get('acknowledged_at') or alert_dict.get('resolved_at'):
                    continue
                
                # Skip if snoozed (unless requested)
                if not include_snoozed and alert_dict.get('snooze_until'):
                    snooze_until = datetime.fromisoformat(alert_dict['snooze_until'])
                    if now < snooze_until:
                        continue
                
                # Convert to Alert object
                alert_dict['created_at'] = datetime.fromisoformat(alert_dict['created_at'])
                
                for date_field in ['acknowledged_at', 'snooze_until', 'resolved_at', 'applied_at']:
                    if alert_dict.get(date_field):
                        alert_dict[date_field] = datetime.fromisoformat(alert_dict[date_field])
                
                alert = Alert(**alert_dict)
                active_alerts.append(alert)
            
            logger.debug(f"Retrieved {len(active_alerts)} active alerts from file")
            return active_alerts, "success"
            
        except Exception as e:
            logger.error(f"File get active alerts failed: {e}")
            self._degraded_metrics["file_failures"] += 1
            return None, f"file_error: {e}"
    
    def _try_memory_get_active_alerts(self, include_snoozed: bool = False) -> Tuple[Optional[List[Alert]], str]:
        """Try to get active alerts from memory (last resort)"""
        try:
            active_alerts = []
            now = datetime.now()
            
            for alert_dict in self._degraded_alerts:
                # Skip if ACK or resolved
                if alert_dict.get('acknowledged_at') or alert_dict.get('resolved_at'):
                    continue
                
                # Skip if snoozed (unless requested)
                if not include_snoozed and alert_dict.get('snooze_until'):
                    try:
                        snooze_until = datetime.fromisoformat(alert_dict['snooze_until'])
                        if now < snooze_until:
                            continue
                    except:
                        pass
                
                # Convert to Alert object
                try:
                    alert_copy = alert_dict.copy()
                    alert_copy['created_at'] = datetime.fromisoformat(alert_copy['created_at'])
                    
                    for date_field in ['acknowledged_at', 'snooze_until', 'resolved_at', 'applied_at']:
                        if alert_copy.get(date_field) and alert_copy[date_field] != '':
                            alert_copy[date_field] = datetime.fromisoformat(alert_copy[date_field])
                        else:
                            alert_copy[date_field] = None
                    
                    # Remove memory-specific fields
                    for key in ['_memory_key', '_stored_mode', '_stored_at']:
                        alert_copy.pop(key, None)
                    
                    alert = Alert(**alert_copy)
                    active_alerts.append(alert)
                    
                except Exception as e:
                    logger.error(f"Failed to parse memory alert: {e}")
                    continue
            
            logger.warning(f"Retrieved {len(active_alerts)} active alerts from MEMORY (degraded mode)")
            return active_alerts, "success_degraded"
            
        except Exception as e:
            logger.error(f"Memory get active alerts failed: {e}")
            return None, f"memory_error: {e}"