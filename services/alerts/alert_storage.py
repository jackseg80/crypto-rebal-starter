"""
Stockage et persistance des alertes avec résilience multi-worker

Implémente un système hybride Redis + fichier JSON avec:
- Redis primary pour dedup/rate-limit distribué
- File-lock fallback si Redis indisponible  
- Single scheduler protection avec SETNX
- Rotation automatique et TTL
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
    
    Features:
    - Redis primary pour coordination distribuée  
    - JSON file fallback avec file-lock
    - Dedup/rate-limit centralisés
    - Auto-rotation et purge
    """
    
    def __init__(self, 
                 redis_url: Optional[str] = None,
                 json_file: str = "data/alerts.json",
                 max_alerts: int = 1000,
                 purge_days: int = 30):
        
        self.json_file = Path(json_file)
        self.json_file.parent.mkdir(exist_ok=True)
        self.lock_file = self.json_file.with_suffix('.lock')
        self.max_alerts = max_alerts
        self.purge_days = purge_days
        
        # Redis connection (optionnel)
        self.redis_client = None
        self.redis_available = False
        
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, 
                                                  decode_responses=True,
                                                  socket_timeout=2,
                                                  socket_connect_timeout=2)
                self.redis_client.ping()
                self.redis_available = True
                logger.info("Redis connection established for alert storage")
            except Exception as e:
                logger.warning(f"Redis unavailable, using file fallback: {e}")
                self.redis_available = False
        
        # Thread-local storage pour cache
        self._local = threading.local()
        
        # Initialiser le stockage
        self._ensure_storage_exists()
    
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
        Stocke une nouvelle alerte avec dedup
        
        Returns:
            True si stockée, False si dupliquée
        """
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
        Récupère les alertes actives (non-ACK, non-résolues)
        
        Args:
            include_snoozed: Inclure les alertes snoozées
        """
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
        Vérifie si l'alerte respecte les limites de taux
        
        Returns:
            True si OK, False si rate-limited
        """
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
        """Retourne métriques de stockage pour observabilité"""
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
            logger.error(f"Error getting storage metrics: {e}")
            return {"error": str(e)}
    
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
            
            # Direction/valeur pour différencier UP vs DOWN
            direction = "up" if alert.data.get("current_value", 0) > alert.data.get("adaptive_threshold", 0) else "down"
            
            dedup_key = f"{alert.alert_type}:{bucket_time.isoformat()}:{direction}"
            
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