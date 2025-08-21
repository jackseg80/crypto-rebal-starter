"""
Monitoring Service - Service de surveillance et monitoring

Ce module intègre le système d'alertes avec les autres composants
pour surveiller en continu l'état du système.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import asyncio
import logging
from datetime import datetime, timezone

from .alert_manager import alert_manager, AlertType, AlertLevel, Alert
from .notification_sender import notification_sender
from ..execution.execution_engine import ExecutionEvent

logger = logging.getLogger(__name__)

class MonitoringService:
    """Service principal de monitoring"""
    
    def __init__(self):
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Métriques collectées
        self.metrics: Dict[str, float] = {}
        self.last_metrics_update: Optional[datetime] = None
        
        # Statistiques d'exécution
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_orders": 0,
            "successful_orders": 0,
            "failed_orders": 0
        }
        
        # Connecter les événements d'exécution
        self._setup_execution_monitoring()
        
        # Connecter les alertes aux notifications
        self._setup_alert_notifications()
    
    def _setup_execution_monitoring(self) -> None:
        """Configurer le monitoring des exécutions"""
        
        def handle_execution_event(event: ExecutionEvent) -> None:
            """Traiter les événements d'exécution"""
            
            if event.type == "plan_start":
                self.execution_stats["total_executions"] += 1
                
            elif event.type == "plan_complete":
                self.execution_stats["successful_executions"] += 1
                
                # Créer une alerte info pour les exécutions réussies
                alert_manager.create_alert(
                    alert_type=AlertType.SYSTEM_ERROR,  # Pas de type spécifique pour succès
                    level=AlertLevel.INFO,
                    title="Execution Completed Successfully",
                    message=event.message,
                    data=event.data or {},
                    source="execution_engine"
                )
                
            elif event.type == "plan_error":
                self.execution_stats["failed_executions"] += 1
                
                # Créer une alerte d'erreur
                alert_manager.create_alert(
                    alert_type=AlertType.EXECUTION_FAILURE,
                    level=AlertLevel.ERROR,
                    title="Execution Failed",
                    message=event.message,
                    data=event.data or {},
                    source="execution_engine"
                )
                
            elif event.type == "order_complete":
                self.execution_stats["total_orders"] += 1
                self.execution_stats["successful_orders"] += 1
                
            elif event.type in ["order_fail", "order_error"]:
                self.execution_stats["total_orders"] += 1
                self.execution_stats["failed_orders"] += 1
        
        # Note: Cette intégration nécessiterait d'ajouter le callback au execution_engine
        # execution_engine.add_event_callback(handle_execution_event)
    
    def _setup_alert_notifications(self) -> None:
        """Configurer l'envoi automatique des notifications pour les alertes"""
        
        async def send_alert_notification(alert: Alert) -> None:
            """Envoyer une notification pour une alerte"""
            try:
                results = await notification_sender.send_alert(alert)
                
                success_count = sum(1 for success in results.values() if success)
                total_count = len(results)
                
                if success_count > 0:
                    logger.info(f"Alert {alert.id} sent via {success_count}/{total_count} channels")
                else:
                    logger.warning(f"Failed to send alert {alert.id} via any channel")
                    
            except Exception as e:
                logger.error(f"Error sending alert notification: {e}")
        
        # S'abonner aux nouvelles alertes
        alert_manager.subscribe(lambda alert: asyncio.create_task(send_alert_notification(alert)))
    
    def update_metrics(self, new_metrics: Dict[str, float]) -> None:
        """Mettre à jour les métriques et vérifier les alertes"""
        
        self.metrics.update(new_metrics)
        self.last_metrics_update = datetime.now(timezone.utc)
        
        # Ajouter les métriques d'exécution
        execution_metrics = self._calculate_execution_metrics()
        self.metrics.update(execution_metrics)
        
        # Vérifier les règles d'alertes
        triggered_alerts = alert_manager.check_rules(self.metrics)
        
        if triggered_alerts:
            logger.info(f"Triggered {len(triggered_alerts)} alerts based on metrics")
    
    def _calculate_execution_metrics(self) -> Dict[str, float]:
        """Calculer les métriques d'exécution"""
        
        metrics = {}
        
        # Taux de succès des exécutions
        if self.execution_stats["total_executions"] > 0:
            success_rate = (self.execution_stats["successful_executions"] / 
                          self.execution_stats["total_executions"]) * 100
            metrics["execution_success_rate"] = success_rate
            metrics["execution_failure_rate"] = 100 - success_rate
        
        # Taux de succès des ordres
        if self.execution_stats["total_orders"] > 0:
            order_success_rate = (self.execution_stats["successful_orders"] / 
                                self.execution_stats["total_orders"]) * 100
            metrics["order_success_rate"] = order_success_rate
            metrics["order_failure_rate"] = 100 - order_success_rate
        
        return metrics
    
    async def start_monitoring(self, interval_seconds: int = 300) -> None:
        """Démarrer le monitoring périodique"""
        
        if self.running:
            logger.warning("Monitoring already running")
            return
        
        self.running = True
        logger.info(f"Starting monitoring service with {interval_seconds}s interval")
        
        self.monitor_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )
    
    async def stop_monitoring(self) -> None:
        """Arrêter le monitoring"""
        
        self.running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Monitoring service stopped")
    
    async def _monitoring_loop(self, interval_seconds: int) -> None:
        """Boucle principale de monitoring"""
        
        while self.running:
            try:
                # Collecter les métriques du système
                system_metrics = await self._collect_system_metrics()
                
                # Mettre à jour et vérifier les alertes
                self.update_metrics(system_metrics)
                
                # Nettoyer les anciennes alertes résolues
                self._cleanup_old_alerts()
                
                # Attendre avant le prochain cycle
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def _collect_system_metrics(self) -> Dict[str, float]:
        """Collecter les métriques système"""
        
        metrics = {}
        
        try:
            # Métriques système de base
            metrics["system_timestamp"] = datetime.now(timezone.utc).timestamp()
            
            # TODO: Ajouter d'autres métriques selon les besoins:
            # - Dérive du portfolio (nécessite accès aux données de portfolio)
            # - Performance des API (temps de réponse)
            # - Utilisation mémoire/CPU
            # - Santé des exchanges
            
            # Métriques d'alertes
            alert_stats = alert_manager.get_alert_stats()
            metrics["active_alerts_count"] = alert_stats["active_alerts"]
            metrics["critical_alerts_count"] = alert_stats["by_level"].get("critical", 0)
            metrics["error_alerts_count"] = alert_stats["by_level"].get("error", 0)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
        
        return metrics
    
    def _cleanup_old_alerts(self, max_age_days: int = 30) -> None:
        """Nettoyer les anciennes alertes résolues"""
        
        from datetime import timedelta
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        
        old_alerts = [
            alert_id for alert_id, alert in alert_manager.alerts.items()
            if alert.resolved and alert.resolved_at and alert.resolved_at < cutoff_date
        ]
        
        for alert_id in old_alerts:
            del alert_manager.alerts[alert_id]
        
        if old_alerts:
            logger.info(f"Cleaned up {len(old_alerts)} old alerts")
    
    def trigger_test_alert(self, level: AlertLevel = AlertLevel.INFO) -> Alert:
        """Déclencher une alerte de test"""
        
        return alert_manager.create_alert(
            alert_type=AlertType.SYSTEM_ERROR,
            level=level,
            title="Test Alert",
            message=f"This is a test alert at {level.value} level",
            data={"test": True, "timestamp": datetime.now(timezone.utc).isoformat()},
            source="monitoring_test"
        )
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Obtenir le statut du monitoring"""
        
        return {
            "running": self.running,
            "last_metrics_update": self.last_metrics_update.isoformat() if self.last_metrics_update else None,
            "metrics_count": len(self.metrics),
            "execution_stats": self.execution_stats.copy(),
            "alert_stats": alert_manager.get_alert_stats(),
            "notification_config": notification_sender.get_config_status()
        }

# Instance globale du service de monitoring
monitoring_service = MonitoringService()