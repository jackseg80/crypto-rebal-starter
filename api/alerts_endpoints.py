"""
API Endpoints pour le système d'alertes prédictives

Expose les fonctionnalités d'alertes avec RBAC, idempotency et validation stricte.
Intègre avec le système de gouvernance Phase 0 sans le violer.
"""

from fastapi import APIRouter, HTTPException, Header, Depends, Query, BackgroundTasks
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import uuid
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from services.alerts.alert_engine import AlertEngine
from services.alerts.alert_types import Alert, AlertType, AlertSeverity
from services.alerts.prometheus_metrics import get_alert_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# Modèles Pydantic pour validation stricte

class ApplyPolicyRequest(BaseModel):
    """Requête d'application de policy depuis alerte"""
    mode: str = Field(..., description="Mode de policy")
    cap_daily: float = Field(..., ge=0.0, le=0.2, description="Cap quotidien [0-20%]")
    ramp_hours: int = Field(..., ge=1, le=72, description="Ramping [1-72h]")
    reason: str = Field(..., max_length=140, description="Raison du changement")
    source_alert_id: str = Field(..., description="ID de l'alerte source")
    
    @validator('mode')
    def validate_mode(cls, v):
        allowed_modes = ["Slow", "Normal", "Aggressive"]
        if v not in allowed_modes:
            raise ValueError(f"Mode must be one of {allowed_modes}. Use freeze endpoint for Freeze mode.")
        return v
    
    @validator('reason')
    def validate_reason(cls, v):
        if not v.strip():
            raise ValueError("Reason cannot be empty")
        return v.strip()

class FreezeRequest(BaseModel):
    """Requête de freeze avec TTL"""
    reason: str = Field(..., max_length=140, description="Raison du freeze")
    ttl_minutes: int = Field(default=360, ge=15, le=1440, description="TTL auto-unfreeze [15min-24h]")
    source_alert_id: Optional[str] = Field(None, description="ID alerte source si applicable")
    
    @validator('reason')
    def validate_reason(cls, v):
        if not v.strip():
            raise ValueError("Reason cannot be empty")
        return v.strip()

class SnoozeRequest(BaseModel):
    """Requête de snooze d'alerte"""
    minutes: int = Field(..., ge=5, le=1440, description="Durée snooze [5min-24h]")
    
class AckRequest(BaseModel):
    """Requête d'acquittement (optionnel body)"""
    notes: Optional[str] = Field(None, max_length=200, description="Notes optionnelles")

class AlertResponse(BaseModel):
    """Réponse alerte formatée"""
    id: str
    alert_type: str
    severity: str
    created_at: str
    data: Dict[str, Any]
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    snooze_until: Optional[str] = None
    suggested_action: Dict[str, Any]
    escalation_count: int = 0

class MetricsResponse(BaseModel):
    """Réponse métriques d'observabilité"""
    alert_engine: Dict[str, Any]
    storage: Dict[str, Any] 
    host_info: Dict[str, Any]
    timestamp: str

# Dépendances pour RBAC (simulation - dans vraie implémentation, lire JWT/session)
class User(BaseModel):
    username: str
    roles: List[str]

def get_current_user() -> User:
    """Récupère l'utilisateur actuel (simulation)"""
    # Dans vraie implémentation: décoder JWT, lire session, etc.
    return User(username="system_user", roles=["approver", "viewer"])

def require_role(required_role: str):
    """Decorator pour vérifier les rôles utilisateur"""
    def dependency(current_user: User = Depends(get_current_user)):
        if required_role not in current_user.roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        return current_user
    return dependency

# Instance globale AlertEngine (sera initialisée dans main.py)
alert_engine: Optional[AlertEngine] = None

def get_alert_engine() -> AlertEngine:
    """Dependency injection pour AlertEngine"""
    if not alert_engine:
        raise HTTPException(status_code=503, detail="Alert engine not initialized")
    return alert_engine

# Endpoints

@router.get("/active", response_model=List[AlertResponse])
async def get_active_alerts(
    include_snoozed: bool = Query(default=False, description="Inclure alertes snoozées"),
    severity_filter: Optional[str] = Query(default=None, description="Filtrer par gravité"),
    type_filter: Optional[str] = Query(default=None, description="Filtrer par type"),
    engine: AlertEngine = Depends(get_alert_engine),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère les alertes actives
    
    Accessible à tous les utilisateurs authentifiés.
    """
    try:
        alerts = engine.get_active_alerts()
        
        # Filtrage optionnel
        if not include_snoozed:
            now = datetime.now()
            alerts = [
                alert for alert in alerts
                if not alert.snooze_until or alert.snooze_until <= now
            ]
        
        if severity_filter:
            alerts = [alert for alert in alerts if alert.severity.value == severity_filter]
            
        if type_filter:
            alerts = [alert for alert in alerts if alert.alert_type.value == type_filter]
        
        # Convertir en format réponse
        response_alerts = []
        for alert in alerts:
            response_alerts.append(AlertResponse(
                id=alert.id,
                alert_type=alert.alert_type.value,
                severity=alert.severity.value,
                created_at=alert.created_at.isoformat(),
                data=alert.data,
                acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                acknowledged_by=alert.acknowledged_by,
                snooze_until=alert.snooze_until.isoformat() if alert.snooze_until else None,
                suggested_action=alert.suggested_action,
                escalation_count=alert.escalation_count
            ))
        
        return response_alerts
        
    except Exception as e:
        logger.error(f"Error getting active alerts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/formatted")
async def get_formatted_alerts(
    include_snoozed: bool = Query(default=False, description="Inclure alertes snoozées"),
    severity_filter: Optional[str] = Query(default=None, description="Filtrer par gravité"),
    type_filter: Optional[str] = Query(default=None, description="Filtrer par type"),
    portfolio_value: Optional[float] = Query(default=None, description="Valeur portfolio pour calcul impact €"),
    engine: AlertEngine = Depends(get_alert_engine),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère les alertes actives avec format unifié pour UI
    
    Format : Action → Impact € → 2 raisons → Détails
    Accessible à tous les utilisateurs authentifiés.
    """
    try:
        alerts = engine.get_active_alerts()
        
        # Filtrage identique à /active
        if not include_snoozed:
            now = datetime.now()
            alerts = [
                alert for alert in alerts
                if not alert.snooze_until or alert.snooze_until <= now
            ]
        
        if severity_filter:
            alerts = [alert for alert in alerts if alert.severity.value == severity_filter]
            
        if type_filter:
            alerts = [alert for alert in alerts if alert.alert_type.value == type_filter]
        
        # Injection valeur portfolio si fournie
        if portfolio_value:
            for alert in alerts:
                if alert.data is None:
                    alert.data = {}
                alert.data["portfolio_value"] = portfolio_value
        
        # Format unifié pour chaque alerte
        formatted_alerts = []
        for alert in alerts:
            formatted = alert.format_unified_message()
            
            formatted_alerts.append({
                "id": alert.id,
                "created_at": alert.created_at.isoformat(),
                "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                "acknowledged_by": alert.acknowledged_by,
                "snooze_until": alert.snooze_until.isoformat() if alert.snooze_until else None,
                "escalation_count": alert.escalation_count,
                # Format unifié
                **formatted
            })
        
        return {
            "alerts": formatted_alerts,
            "meta": {
                "total": len(formatted_alerts),
                "active_only": not include_snoozed,
                "filters": {
                    "severity": severity_filter,
                    "type": type_filter
                },
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting formatted alerts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/acknowledge/{alert_id}")
async def acknowledge_alert(
    alert_id: str,
    request: AckRequest = AckRequest(),
    engine: AlertEngine = Depends(get_alert_engine),
    current_user: User = Depends(get_current_user)
):
    """
    Acquitte une alerte
    
    Accessible à tous les utilisateurs authentifiés.
    """
    try:
        success = await engine.acknowledge_alert(alert_id, current_user.username)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "success": True,
            "message": f"Alert {alert_id} acknowledged",
            "acknowledged_by": current_user.username,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/snooze/{alert_id}")
async def snooze_alert(
    alert_id: str,
    request: SnoozeRequest,
    engine: AlertEngine = Depends(get_alert_engine),
    current_user: User = Depends(get_current_user)
):
    """
    Snooze une alerte pour X minutes
    
    Accessible à tous les utilisateurs authentifiés.
    """
    try:
        success = await engine.snooze_alert(alert_id, request.minutes)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        snooze_until = datetime.now().timestamp() + (request.minutes * 60)
        
        return {
            "success": True,
            "message": f"Alert {alert_id} snoozed for {request.minutes} minutes",
            "snooze_until": datetime.fromtimestamp(snooze_until).isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error snoozing alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/metrics", response_model=MetricsResponse)
async def get_alert_metrics(
    engine: AlertEngine = Depends(get_alert_engine),
    current_user: User = Depends(require_role("viewer"))
):
    """
    Récupère les métriques d'observabilité
    
    Nécessite le rôle 'viewer' minimum.
    """
    try:
        metrics = engine.get_metrics()
        
        return MetricsResponse(
            alert_engine=metrics["alert_engine"],
            storage=metrics["storage"],
            host_info=metrics["host_info"],
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting alert metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/types")
async def get_alert_types():
    """
    Liste les types d'alertes disponibles
    
    Endpoint public pour documentation.
    """
    return {
        "alert_types": [
            {
                "type": alert_type.value,
                "description": _get_alert_description(alert_type)
            }
            for alert_type in AlertType
        ],
        "severities": [
            {
                "severity": severity.value,
                "description": _get_severity_description(severity)
            }
            for severity in AlertSeverity
        ]
    }

@router.get("/history")
async def get_alert_history(
    limit: int = Query(default=50, ge=1, le=200, description="Limite résultats"),
    offset: int = Query(default=0, ge=0, description="Offset pagination"),
    days: int = Query(default=7, ge=1, le=90, description="Période en jours"),
    current_user: User = Depends(get_current_user)
):
    """
    Historique des alertes
    
    Retourne les alertes passées avec pagination.
    """
    try:
        # Pour l'instant, retourner les alertes actives (dans vraie implémentation: query historique)
        all_alerts = alert_engine.storage.get_active_alerts(include_snoozed=True)
        
        # Simulation pagination
        paginated = all_alerts[offset:offset + limit]
        
        response_alerts = []
        for alert in paginated:
            response_alerts.append(AlertResponse(
                id=alert.id,
                alert_type=alert.alert_type.value,
                severity=alert.severity.value,
                created_at=alert.created_at.isoformat(),
                data=alert.data,
                acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                acknowledged_by=alert.acknowledged_by,
                snooze_until=alert.snooze_until.isoformat() if alert.snooze_until else None,
                suggested_action=alert.suggested_action,
                escalation_count=alert.escalation_count
            ))
        
        return {
            "alerts": response_alerts,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(all_alerts),
                "has_next": (offset + limit) < len(all_alerts)
            },
            "filters": {
                "days": days
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting alert history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Fonctions helper

def _get_alert_description(alert_type: AlertType) -> str:
    """Descriptions des types d'alertes"""
    descriptions = {
        AlertType.VOL_Q90_CROSS: "Volatilité dépasse le quantile 90",
        AlertType.REGIME_FLIP: "Changement de régime de marché détecté",
        AlertType.CORR_HIGH: "Corrélation systémique élevée entre assets",
        AlertType.CONTRADICTION_SPIKE: "Index de contradiction ML élevé",
        AlertType.DECISION_DROP: "Chute significative de confiance ML",
        AlertType.EXEC_COST_SPIKE: "Coûts d'exécution anormalement élevés"
    }
    return descriptions.get(alert_type, "Description non disponible")

def _get_severity_description(severity: AlertSeverity) -> str:
    """Descriptions des niveaux de gravité"""
    descriptions = {
        AlertSeverity.S1: "Information - Acquittement uniquement",
        AlertSeverity.S2: "Majeur - Suggère changement policy Slow",
        AlertSeverity.S3: "Critique - Suggère freeze du système"
    }
    return descriptions.get(severity, "Description non disponible")

# Nouveaux endpoints pour configuration

@router.post("/config/reload")
async def reload_config(
    engine: AlertEngine = Depends(get_alert_engine),
    current_user: User = Depends(require_role("approver"))
):
    """
    Recharge la configuration des alertes depuis le fichier
    
    Nécessite le rôle 'approver'. Force le rechargement de alerts_rules.json.
    """
    try:
        reloaded = engine._check_config_reload()
        
        if reloaded:
            return {
                "success": True,
                "message": "Configuration reloaded successfully",
                "config_version": engine.config.get('metadata', {}).get('config_version', 'unknown'),
                "reloaded_by": current_user.username,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "message": "No configuration changes detected",
                "config_version": engine.config.get('metadata', {}).get('config_version', 'unknown'),
                "timestamp": datetime.now().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error reloading config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/config/current")
async def get_current_config(
    engine: AlertEngine = Depends(get_alert_engine),
    current_user: User = Depends(require_role("viewer"))
):
    """
    Retourne la configuration actuelle des alertes
    
    Nécessite le rôle 'viewer' minimum.
    """
    try:
        return {
            "config": engine.config,
            "config_file_path": engine.config_file_path,
            "last_modified": engine._config_mtime,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting current config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/health")
async def get_health_status(
    engine: AlertEngine = Depends(get_alert_engine)
):
    """
    Vérification de santé du système d'alertes
    
    Endpoint public pour monitoring/load balancer.
    """
    try:
        now = datetime.now()
        
        # Vérifier si scheduler actif
        scheduler_healthy = engine.is_scheduler
        last_eval_age = None
        
        if engine.last_evaluation != datetime.min:
            last_eval_age = (now - engine.last_evaluation).total_seconds()
            scheduler_healthy = scheduler_healthy and last_eval_age < 300  # < 5 min
        
        # Vérifier storage
        try:
            storage_healthy = engine.storage.ping()
        except:
            storage_healthy = False
        
        # Statut global
        overall_status = "healthy" if (scheduler_healthy and storage_healthy) else "degraded"
        
        return {
            "status": overall_status,
            "components": {
                "scheduler": {
                    "status": "healthy" if scheduler_healthy else "unhealthy",
                    "is_active": engine.is_scheduler,
                    "last_evaluation_seconds_ago": last_eval_age
                },
                "storage": {
                    "status": "healthy" if storage_healthy else "unhealthy",
                    "type": "redis" if engine.storage.redis_available else "file"
                }
            },
            "host_id": engine.host_id,
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking health status: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics(
    engine: AlertEngine = Depends(get_alert_engine),
    current_user: User = Depends(require_role("viewer"))
):
    """
    Phase 2A Comprehensive Prometheus Metrics
    
    Expose toutes les métriques Phase 2A pour monitoring production.
    Inclut: alertes, storage, performance, dégradation, ML signals.
    """
    try:
        # Update metrics from AlertEngine
        engine_metrics = engine.get_metrics()
        storage_metrics = engine.storage.get_metrics()
        
        # Update Prometheus metrics
        alert_metrics = get_alert_metrics()
        alert_metrics.update_storage_metrics(storage_metrics)
        
        # Update alert counts 
        alert_counts = {
            'active_s1': len([a for a in engine.storage.get_active_alerts() if a.severity.value == 'S1']),
            'active_s2': len([a for a in engine.storage.get_active_alerts() if a.severity.value == 'S2']), 
            'active_s3': len([a for a in engine.storage.get_active_alerts() if a.severity.value == 'S3']),
            'snoozed': len([a for a in engine.storage.get_active_alerts(include_snoozed=True) 
                           if hasattr(a, 'snoozed_until') and a.snoozed_until and a.snoozed_until > datetime.now()])
        }
        alert_metrics.update_alert_counts(alert_counts)
        
        # Record engine run metrics
        last_eval = engine_metrics["alert_engine"]["gauges"].get("last_evaluation_timestamp", 0)
        if last_eval > 0:
            alert_metrics.engine_last_run.set(last_eval)
        
        # Update ML signals if available
        if "ml_signals" in engine_metrics:
            alert_metrics.update_ml_signals(engine_metrics["ml_signals"])
        
        # Generate comprehensive Prometheus output
        return generate_latest().decode('utf-8')
        
    except Exception as e:
        logger.error(f"Error generating Phase 2A Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Hook pour initialisation depuis main.py
def initialize_alert_engine(engine: AlertEngine):
    """Initialise l'instance globale AlertEngine"""
    global alert_engine
    alert_engine = engine
    logger.info("Alert engine initialized for API endpoints")