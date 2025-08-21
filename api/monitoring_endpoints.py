"""
API Endpoints pour le système de monitoring et notifications

Ces endpoints gèrent les alertes, les notifications et le monitoring
du pipeline de rebalancement.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

from services.notifications.alert_manager import alert_manager, AlertLevel, AlertType
from services.notifications.notification_sender import notification_sender, NotificationConfig
from services.notifications.monitoring import monitoring_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

# Models pour les requêtes/réponses
class AlertResponse(BaseModel):
    """Réponse pour une alerte"""
    id: str
    type: str
    level: str
    source: str
    title: str
    message: str
    data: Dict[str, Any]
    created_at: str
    updated_at: str
    acknowledged: bool
    resolved: bool
    resolved_at: Optional[str] = None
    actions: List[str]

class AlertRuleRequest(BaseModel):
    """Requête pour créer/modifier une règle d'alerte"""
    name: str = Field(..., description="Nom de la règle")
    description: str = Field(..., description="Description de la règle")
    enabled: bool = Field(default=True, description="Règle activée")
    alert_type: str = Field(..., description="Type d'alerte")
    level: str = Field(..., description="Niveau d'alerte")
    metric: str = Field(..., description="Métrique à surveiller")
    threshold_value: float = Field(..., description="Valeur seuil")
    operator: str = Field(..., description="Opérateur (>, <, >=, <=, ==, !=)")
    check_interval_minutes: int = Field(default=5, description="Intervalle de vérification")
    cooldown_minutes: int = Field(default=30, description="Période de cooldown")

class NotificationConfigRequest(BaseModel):
    """Requête pour configurer les notifications"""
    channel_type: str = Field(..., description="Type de canal (console, email, webhook)")
    enabled: bool = Field(default=True, description="Canal activé")
    min_level: str = Field(default="info", description="Niveau minimum")
    alert_types: Optional[List[str]] = Field(default=None, description="Types d'alertes à filtrer")
    config: Dict[str, Any] = Field(default={}, description="Configuration spécifique au canal")

class TestAlertRequest(BaseModel):
    """Requête pour déclencher une alerte de test"""
    level: str = Field(default="info", description="Niveau d'alerte")
    title: Optional[str] = Field(default=None, description="Titre personnalisé")
    message: Optional[str] = Field(default=None, description="Message personnalisé")

@router.get("/alerts")
async def get_alerts(
    level: Optional[str] = Query(default=None, description="Filtrer par niveau"),
    alert_type: Optional[str] = Query(default=None, description="Filtrer par type"),
    unresolved_only: bool = Query(default=True, description="Seulement les non résolues"),
    limit: int = Query(default=50, le=100, description="Nombre maximum d'alertes")
):
    """
    Obtenir la liste des alertes
    
    Permet de filtrer par niveau, type, et statut de résolution.
    """
    try:
        # Convertir les paramètres
        alert_level = None
        if level:
            try:
                alert_level = AlertLevel(level.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid alert level: {level}")
        
        alert_type_enum = None
        if alert_type:
            try:
                alert_type_enum = AlertType(alert_type.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid alert type: {alert_type}")
        
        # Obtenir les alertes
        alerts = alert_manager.get_active_alerts(
            level=alert_level,
            alert_type=alert_type_enum,
            unresolved_only=unresolved_only
        )
        
        # Limiter le nombre de résultats
        alerts = alerts[:limit]
        
        # Convertir en réponses
        alert_responses = []
        for alert in alerts:
            alert_responses.append(AlertResponse(
                id=alert.id,
                type=alert.type.value,
                level=alert.level.value,
                source=alert.source,
                title=alert.title,
                message=alert.message,
                data=alert.data,
                created_at=alert.created_at.isoformat(),
                updated_at=alert.updated_at.isoformat(),
                acknowledged=alert.acknowledged,
                resolved=alert.resolved,
                resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
                actions=alert.actions
            ))
        
        return {
            "alerts": alert_responses,
            "total": len(alert_responses),
            "filters": {
                "level": level,
                "alert_type": alert_type,
                "unresolved_only": unresolved_only
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """
    Accuser réception d'une alerte
    
    Marque l'alerte comme accusée réception par un utilisateur.
    """
    try:
        success = alert_manager.acknowledge_alert(alert_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"success": True, "message": f"Alert {alert_id} acknowledged"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution_note: str = Body("", description="Note de résolution")
):
    """
    Résoudre une alerte
    
    Marque l'alerte comme résolue avec une note explicative optionnelle.
    """
    try:
        success = alert_manager.resolve_alert(alert_id, resolution_note)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"success": True, "message": f"Alert {alert_id} resolved"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts/stats")
async def get_alert_stats():
    """
    Obtenir les statistiques des alertes
    
    Retourne des métriques sur le nombre d'alertes par niveau,
    type, temps de résolution moyen, etc.
    """
    try:
        stats = alert_manager.get_alert_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting alert stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/test")
async def trigger_test_alert(request: TestAlertRequest):
    """
    Déclencher une alerte de test
    
    Utile pour tester le système de notifications et la configuration
    des canaux.
    """
    try:
        # Convertir le niveau
        try:
            level = AlertLevel(request.level.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid alert level: {request.level}")
        
        # Déclencher l'alerte de test
        alert = monitoring_service.trigger_test_alert(level)
        
        # Personnaliser si demandé
        if request.title:
            alert.title = request.title
        if request.message:
            alert.message = request.message
        
        return {
            "success": True,
            "alert_id": alert.id,
            "message": f"Test alert triggered at {level.value} level"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering test alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_monitoring_status():
    """
    Obtenir le statut global du monitoring
    
    Retourne l'état du service de monitoring, les métriques récentes,
    et les statistiques du système d'alertes.
    """
    try:
        status = monitoring_service.get_monitoring_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start")
async def start_monitoring(
    interval_seconds: int = Query(default=300, ge=60, le=3600, description="Intervalle de monitoring en secondes")
):
    """
    Démarrer le service de monitoring
    
    Lance la surveillance automatique des métriques et la vérification
    des règles d'alertes.
    """
    try:
        await monitoring_service.start_monitoring(interval_seconds)
        
        return {
            "success": True,
            "message": f"Monitoring started with {interval_seconds}s interval"
        }
        
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_monitoring():
    """
    Arrêter le service de monitoring
    
    Stoppe la surveillance automatique. Les alertes manuelles
    restent fonctionnelles.
    """
    try:
        await monitoring_service.stop_monitoring()
        
        return {
            "success": True,
            "message": "Monitoring stopped"
        }
        
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notifications/config")
async def add_notification_config(request: NotificationConfigRequest):
    """
    Ajouter une configuration de notification
    
    Configure un nouveau canal de notification (email, webhook, etc.)
    avec ses paramètres et filtres.
    """
    try:
        # Valider le niveau minimum
        try:
            min_level = AlertLevel(request.min_level.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid alert level: {request.min_level}")
        
        # Créer la configuration
        config = NotificationConfig(
            channel_type=request.channel_type,
            enabled=request.enabled,
            config=request.config,
            min_level=min_level,
            alert_types=request.alert_types
        )
        
        notification_sender.add_config(config)
        
        return {
            "success": True,
            "message": f"Notification config added for {request.channel_type}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding notification config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/notifications/config/{channel_type}")
async def remove_notification_config(channel_type: str):
    """
    Supprimer une configuration de notification
    
    Retire un canal de notification et arrête l'envoi d'alertes
    via ce canal.
    """
    try:
        success = notification_sender.remove_config(channel_type)
        
        if not success:
            raise HTTPException(status_code=404, detail="Notification config not found")
        
        return {
            "success": True,
            "message": f"Notification config removed for {channel_type}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing notification config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notifications/status")
async def get_notification_status():
    """
    Obtenir le statut des notifications
    
    Retourne la configuration actuelle des canaux de notification
    et leurs paramètres.
    """
    try:
        status = notification_sender.get_config_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting notification status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics")
async def get_current_metrics():
    """
    Obtenir les métriques actuelles
    
    Retourne les dernières métriques collectées par le système
    de monitoring.
    """
    try:
        return {
            "metrics": monitoring_service.metrics,
            "last_update": monitoring_service.last_metrics_update.isoformat() if monitoring_service.last_metrics_update else None,
            "execution_stats": monitoring_service.execution_stats
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/metrics")
async def update_metrics(metrics: Dict[str, float] = Body(..., description="Nouvelles métriques")):
    """
    Mettre à jour les métriques manuellement
    
    Permet d'injecter des métriques externes pour déclencher
    des vérifications d'alertes.
    """
    try:
        monitoring_service.update_metrics(metrics)
        
        return {
            "success": True,
            "message": f"Updated {len(metrics)} metrics",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error updating metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))