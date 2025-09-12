"""
Phase 3B Integration - AlertEngine Real-time Streaming Integration
Connects AlertEngine with streaming system for real-time alert broadcasting
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from .alert_types import Alert, AlertSeverity, AlertType
from ..streaming.realtime_engine import (
    get_realtime_engine, RealtimeEngine, StreamEventType, StreamEvent
)

log = logging.getLogger(__name__)


class RealtimeAlertBroadcaster:
    """
    Broadcaster d'alertes en temps réel pour Phase 3B
    S'intègre avec AlertEngine pour diffuser les alertes via WebSocket et Redis Streams
    """
    
    def __init__(self):
        self.engine: Optional[RealtimeEngine] = None
        self.enabled = False
        self.metrics = {
            "alerts_broadcasted": 0,
            "broadcasts_failed": 0,
            "start_time": None
        }
    
    async def initialize(self, enabled: bool = True):
        """Initialiser le broadcaster d'alertes"""
        self.enabled = enabled
        
        if not enabled:
            log.info("Realtime alert broadcasting disabled")
            return
        
        try:
            # Récupérer l'instance du moteur de streaming
            self.engine = await get_realtime_engine()
            
            # Démarrer le moteur s'il n'est pas déjà actif
            if not self.engine.running:
                await self.engine.start()
            
            self.metrics["start_time"] = datetime.now()
            log.info("Realtime alert broadcaster initialized successfully")
            
        except Exception as e:
            log.error(f"Failed to initialize realtime alert broadcaster: {e}")
            self.enabled = False
            raise
    
    async def broadcast_alert(self, alert: Alert) -> bool:
        """
        Diffuser une alerte en temps réel
        
        Args:
            alert: L'alerte à diffuser
            
        Returns:
            bool: True si la diffusion a réussi
        """
        if not self.enabled or not self.engine:
            return False
        
        try:
            # Convertir l'alerte en données sérialisables
            alert_data = self._convert_alert_to_data(alert)
            
            # Déterminer le type d'événement de streaming
            stream_event_type = self._get_stream_event_type(alert.alert_type)
            
            # Publier l'événement de risque
            await self.engine.publish_risk_event(
                event_type=stream_event_type,
                data=alert_data,
                source="alert_engine"
            )
            
            self.metrics["alerts_broadcasted"] += 1
            log.debug(f"Broadcasted alert {alert.alert_id}: {alert.alert_type.value} - {alert.severity.value}")
            
            return True
            
        except Exception as e:
            log.error(f"Failed to broadcast alert {alert.alert_id}: {e}")
            self.metrics["broadcasts_failed"] += 1
            return False
    
    async def broadcast_alert_batch(self, alerts: List[Alert]) -> Dict[str, int]:
        """
        Diffuser un lot d'alertes en temps réel
        
        Args:
            alerts: Liste des alertes à diffuser
            
        Returns:
            Dict avec le décompte des succès/échecs
        """
        if not self.enabled or not self.engine:
            return {"success": 0, "failed": len(alerts)}
        
        results = {"success": 0, "failed": 0}
        
        # Traitement parallèle des alertes (par lots de 10)
        batch_size = 10
        for i in range(0, len(alerts), batch_size):
            batch = alerts[i:i + batch_size]
            
            # Traitement parallèle du lot
            tasks = [self.broadcast_alert(alert) for alert in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    results["failed"] += 1
                elif result:
                    results["success"] += 1
                else:
                    results["failed"] += 1
        
        log.info(f"Batch broadcast completed: {results['success']} success, {results['failed']} failed")
        return results
    
    async def broadcast_risk_event(self, event_type: str, data: Dict[str, Any], 
                                   severity: str = "S2") -> bool:
        """
        Diffuser un événement de risque personnalisé
        
        Args:
            event_type: Type d'événement (VAR_BREACH, STRESS_TEST, etc.)
            data: Données de l'événement
            severity: Sévérité (S1, S2, S3)
            
        Returns:
            bool: True si la diffusion a réussi
        """
        if not self.enabled or not self.engine:
            return False
        
        try:
            # Ajouter métadonnées
            enriched_data = {
                **data,
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
                "source": "alert_engine",
                "event_id": f"risk_{int(datetime.now().timestamp())}"
            }
            
            # Convertir le type d'événement
            try:
                stream_event_type = StreamEventType(event_type.lower())
            except ValueError:
                stream_event_type = StreamEventType.RISK_ALERT
            
            # Publier
            await self.engine.publish_risk_event(
                event_type=stream_event_type,
                data=enriched_data,
                source="alert_engine"
            )
            
            return True
            
        except Exception as e:
            log.error(f"Failed to broadcast risk event {event_type}: {e}")
            return False
    
    async def broadcast_system_status(self, status: Dict[str, Any]) -> bool:
        """
        Diffuser le status du système d'alerte
        
        Args:
            status: Dictionnaire avec le status système
            
        Returns:
            bool: True si la diffusion a réussi
        """
        if not self.enabled or not self.engine:
            return False
        
        try:
            # Créer un événement de status système
            event = StreamEvent(
                event_type=StreamEventType.SYSTEM_STATUS,
                timestamp=datetime.now(),
                data={
                    "component": "alert_engine",
                    "status": status,
                    "broadcaster_metrics": self.get_metrics()
                },
                source="alert_engine"
            )
            
            # Diffuser via WebSocket seulement (pas Redis Stream pour éviter spam)
            await self.engine.websocket_manager.broadcast_event(event)
            
            return True
            
        except Exception as e:
            log.error(f"Failed to broadcast system status: {e}")
            return False
    
    def _convert_alert_to_data(self, alert: Alert) -> Dict[str, Any]:
        """Convertir une alerte en dictionnaire sérialisable"""
        return {
            "alert_id": alert.alert_id,
            "alert_type": alert.alert_type.value,
            "severity": alert.severity.value,
            "message": alert.message,
            "asset": alert.asset,
            "value": alert.value,
            "threshold": alert.threshold,
            "timestamp": alert.timestamp.isoformat(),
            "metadata": alert.metadata or {},
            "suggested_action": alert.suggested_action or {},
            
            # Données additionnelles pour le frontend
            "display_title": self._get_alert_title(alert),
            "display_color": self._get_alert_color(alert.severity),
            "display_icon": self._get_alert_icon(alert.alert_type),
            "urgency_level": self._get_urgency_level(alert.severity)
        }
    
    def _get_stream_event_type(self, alert_type: AlertType) -> StreamEventType:
        """Mapper AlertType vers StreamEventType"""
        mapping = {
            AlertType.VAR_BREACH: StreamEventType.VAR_BREACH,
            AlertType.STRESS_TEST_FAILED: StreamEventType.STRESS_TEST,
            AlertType.MONTE_CARLO_EXTREME: StreamEventType.RISK_ALERT,
            AlertType.RISK_CONCENTRATION: StreamEventType.RISK_ALERT,
            AlertType.CORR_HIGH: StreamEventType.CORRELATION_SPIKE,
            AlertType.VOL_Q90_CROSS: StreamEventType.RISK_ALERT,
            AlertType.REGIME_FLIP: StreamEventType.RISK_ALERT,
            AlertType.CONTRADICTION_SPIKE: StreamEventType.RISK_ALERT,
            AlertType.DECISION_DROP: StreamEventType.RISK_ALERT,
            AlertType.EXEC_COST_SPIKE: StreamEventType.RISK_ALERT,
        }
        
        return mapping.get(alert_type, StreamEventType.RISK_ALERT)
    
    def _get_alert_title(self, alert: Alert) -> str:
        """Générer un titre d'affichage pour l'alerte"""
        titles = {
            AlertType.VAR_BREACH: f"Dépassement VaR - {alert.asset or 'Portfolio'}",
            AlertType.STRESS_TEST_FAILED: f"Échec Test de Stress - {alert.asset or 'Portfolio'}",
            AlertType.MONTE_CARLO_EXTREME: f"Scénario Extrême Détecté - {alert.asset or 'Portfolio'}",
            AlertType.RISK_CONCENTRATION: f"Concentration de Risque - {alert.asset or 'Portfolio'}",
            AlertType.CORR_HIGH: f"Corrélation Élevée - {alert.asset or 'Marché'}",
            AlertType.VOL_Q90_CROSS: f"Seuil Volatilité Q90 - {alert.asset or 'Marché'}",
            AlertType.REGIME_FLIP: f"Changement de Régime - {alert.asset or 'Marché'}",
        }
        
        return titles.get(alert.alert_type, f"Alerte {alert.alert_type.value}")
    
    def _get_alert_color(self, severity: AlertSeverity) -> str:
        """Couleur d'affichage selon la sévérité"""
        colors = {
            AlertSeverity.S1: "#17a2b8",  # Info (bleu)
            AlertSeverity.S2: "#ffc107",  # Warning (jaune)
            AlertSeverity.S3: "#dc3545"   # Critical (rouge)
        }
        return colors.get(severity, "#6c757d")
    
    def _get_alert_icon(self, alert_type: AlertType) -> str:
        """Icône d'affichage selon le type"""
        icons = {
            AlertType.VAR_BREACH: "⚠️",
            AlertType.STRESS_TEST_FAILED: "💥",
            AlertType.MONTE_CARLO_EXTREME: "🎲",
            AlertType.RISK_CONCENTRATION: "📊",
            AlertType.CORR_HIGH: "🔗",
            AlertType.VOL_Q90_CROSS: "📈",
            AlertType.REGIME_FLIP: "🔄",
            AlertType.CONTRADICTION_SPIKE: "❗",
            AlertType.DECISION_DROP: "⬇️",
            AlertType.EXEC_COST_SPIKE: "💰"
        }
        return icons.get(alert_type, "🔔")
    
    def _get_urgency_level(self, severity: AlertSeverity) -> int:
        """Niveau d'urgence numérique (1-3)"""
        levels = {
            AlertSeverity.S1: 1,  # Low urgency
            AlertSeverity.S2: 2,  # Medium urgency  
            AlertSeverity.S3: 3   # High urgency
        }
        return levels.get(severity, 1)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Métriques du broadcaster"""
        uptime = 0
        if self.metrics["start_time"]:
            uptime = (datetime.now() - self.metrics["start_time"]).total_seconds()
        
        return {
            **self.metrics,
            "enabled": self.enabled,
            "engine_running": self.engine.running if self.engine else False,
            "uptime_seconds": uptime,
            "success_rate": (
                self.metrics["alerts_broadcasted"] / 
                max(self.metrics["alerts_broadcasted"] + self.metrics["broadcasts_failed"], 1)
            )
        }
    
    async def cleanup(self):
        """Nettoyer les ressources"""
        if self.engine:
            # On ne stoppe pas le moteur car d'autres composants peuvent l'utiliser
            pass
        
        self.enabled = False
        log.info("Realtime alert broadcaster cleaned up")


# Singleton pour l'application
_global_broadcaster: Optional[RealtimeAlertBroadcaster] = None

async def get_alert_broadcaster(enabled: bool = True) -> RealtimeAlertBroadcaster:
    """Factory pour récupérer le broadcaster global"""
    global _global_broadcaster
    
    if _global_broadcaster is None:
        _global_broadcaster = RealtimeAlertBroadcaster()
        await _global_broadcaster.initialize(enabled)
    
    return _global_broadcaster


async def broadcast_phase3a_risk_event(event_type: str, data: Dict[str, Any], 
                                       severity: str = "S2") -> bool:
    """
    Helper function pour broadcaster des événements Phase 3A depuis n'importe où
    
    Args:
        event_type: Type d'événement (var_breach, stress_test, etc.)
        data: Données de l'événement
        severity: Sévérité (S1, S2, S3)
        
    Returns:
        bool: True si la diffusion a réussi
    """
    try:
        broadcaster = await get_alert_broadcaster()
        return await broadcaster.broadcast_risk_event(event_type, data, severity)
    except Exception as e:
        log.error(f"Failed to broadcast Phase 3A risk event: {e}")
        return False