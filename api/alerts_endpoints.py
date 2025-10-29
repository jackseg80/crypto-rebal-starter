"""
API Endpoints pour le système d'alertes prédictives

Expose les fonctionnalités d'alertes avec RBAC, idempotency et validation stricte.
Intègre avec le système de gouvernance Phase 0 sans le violer.
"""

from fastapi import APIRouter, HTTPException, Header, Depends, Query, BackgroundTasks, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
import os
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

class ResolveRequest(BaseModel):
    """Requête de résolution d'alerte"""
    resolution_note: Optional[str] = Field(None, max_length=500, description="Note de résolution")

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

# Guard for test endpoints (disabled by default and always off in production)
from config import get_settings
_settings = get_settings()

def ensure_test_endpoints_enabled(request: Request):
    """Gate test-only endpoints.

    Policy:
    - Always disabled in production.
    - Enabled in any non-production environment (dev/staging) regardless of DEBUG flag.
    - Additionally, can be forced via ENABLE_ALERTS_TEST_ENDPOINTS=true.
    """
    # Always allow from localhost for developer tests
    try:
        client_host = (request.client.host if request and request.client else None)
        host_header = (request.headers.get('host', '') or '').split(':')[0].lower()
    except Exception:
        client_host, host_header = None, ''

    if client_host in ('127.0.0.1', '::1') or host_header in ('localhost', '127.0.0.1', '::1'):
        return True

    # If running in production environment, allow only when explicit flag is set
    if _settings.is_production():
        flag = str(os.getenv("ENABLE_ALERTS_TEST_ENDPOINTS", "false")).strip().lower() == "true"
        if flag:
            return True
        raise HTTPException(status_code=404, detail="test_endpoints_disabled")

    # Non-production environments: allow by default
    return True

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

@router.post("/resolve/{alert_id}")
async def resolve_alert(
    alert_id: str,
    request: ResolveRequest = ResolveRequest(),
    engine: AlertEngine = Depends(get_alert_engine),
    current_user: User = Depends(get_current_user)
):
    """
    Résout définitivement une alerte
    
    Marque l'alerte comme résolue avec une note de résolution.
    Accessible à tous les utilisateurs authentifiés.
    """
    try:
        success = await engine.resolve_alert(alert_id, current_user.username, request.resolution_note)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "success": True,
            "message": f"Alert {alert_id} resolved",
            "resolved_by": current_user.username,
            "resolution_note": request.resolution_note,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
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
        except Exception as e:
            logger.error(f"Storage health check failed: {e}")
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

@router.get("/multi-timeframe/status")
async def get_multi_timeframe_status(
    engine: AlertEngine = Depends(get_alert_engine)
):
    """
    Phase 2B1: Multi-Timeframe Analysis Status
    
    Retourne le statut complet du système multi-timeframe incluant:
    - Cohérence par timeframe 
    - Signaux récents par timeframe
    - Métriques de performance temporal gating
    """
    try:
        status = engine.get_multi_timeframe_status()
        
        # Ajouter des informations de configuration
        if status.get("enabled", False):
            config = engine.config.get("alerting_config", {}).get("multi_timeframe", {})
            status["configuration"] = {
                "coherence_lookback_minutes": config.get("coherence_lookback_minutes", 60),
                "signal_history_hours": config.get("signal_history_hours", 24),
                "timeframe_weights": config.get("timeframe_weights", {}),
                "temporal_overrides": config.get("temporal_overrides", {})
            }
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting multi-timeframe status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/multi-timeframe/coherence/{alert_type}")
async def get_alert_type_coherence(
    alert_type: str,
    lookback_minutes: int = Query(60, ge=15, le=1440, description="Lookback period in minutes"),
    engine: AlertEngine = Depends(get_alert_engine)
):
    """
    Phase 2B1: Alert Type Coherence Analysis
    
    Analyse la cohérence multi-timeframe pour un type d'alerte spécifique.
    """
    try:
        if not engine.multi_timeframe_enabled or not engine.multi_timeframe_analyzer:
            raise HTTPException(status_code=404, detail="Multi-timeframe analysis not enabled")
        
        # Valider le type d'alerte
        try:
            alert_type_enum = AlertType(alert_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid alert type: {alert_type}")
        
        coherence = engine.multi_timeframe_analyzer.calculate_coherence_score(
            alert_type_enum, lookback_minutes
        )
        
        return {
            "alert_type": alert_type,
            "coherence": {
                "overall_score": coherence.overall_score,
                "timeframe_agreement": coherence.timeframe_agreement,
                "divergence_severity": coherence.divergence_severity,
                "dominant_timeframe": coherence.dominant_timeframe.value if coherence.dominant_timeframe else None,
                "conflicting_signals": [
                    {"tf1": tf1.value, "tf2": tf2.value} 
                    for tf1, tf2 in coherence.conflicting_signals
                ]
            },
            "analysis_period": f"{lookback_minutes}m",
            "calculated_at": coherence.calculated_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error calculating coherence for {alert_type}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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

# Phase 2B2: Cross-Asset Correlation Endpoints

@router.get("/cross-asset/status")
async def get_cross_asset_status(
    timeframe: str = Query("1h", pattern="^(1h|4h|1d)$", description="Analysis timeframe"),
    engine: AlertEngine = Depends(get_alert_engine)
):
    """
    Phase 2B2: Cross-Asset Correlation Status
    
    Retourne le statut complet du système de corrélation cross-asset incluant:
    - Matrice de corrélation actuelle
    - Score de risque systémique  
    - Clusters de concentration détectés
    - Spikes récents
    """
    try:
        if not engine.cross_asset_enabled or not engine.cross_asset_analyzer:
            raise HTTPException(status_code=404, detail="Cross-asset correlation analysis not enabled")
        
        # Obtenir status complet
        status = engine.cross_asset_analyzer.get_status(timeframe)
        
        # Convertir en format JSON-serializable
        return {
            "timestamp": status.timestamp.isoformat(),
            "timeframe": timeframe,
            "matrix": {
                "total_assets": status.total_assets,
                "shape": status.correlation_matrix_shape,
                "avg_correlation": round(status.avg_correlation, 3),
                "max_correlation": round(status.max_correlation, 3)
            },
            "risk_assessment": {
                "systemic_risk_score": round(status.systemic_risk_score, 3),
                "risk_level": (
                    "critical" if status.systemic_risk_score >= 0.8 else
                    "high" if status.systemic_risk_score >= 0.6 else
                    "medium" if status.systemic_risk_score >= 0.4 else
                    "low"
                )
            },
            "concentration": {
                "active_clusters": len(status.active_clusters),
                "clusters": [
                    {
                        "id": cluster.cluster_id,
                        "assets": list(cluster.assets),
                        "avg_correlation": round(cluster.avg_correlation, 3),
                        "risk_score": round(cluster.risk_score, 3)
                    }
                    for cluster in status.active_clusters[:5]  # Top 5 clusters
                ]
            },
            "recent_activity": {
                "spikes_1h": len(status.recent_spikes),
                "spikes": [
                    {
                        "asset_pair": f"{spike.asset_pair[0]}-{spike.asset_pair[1]}",
                        "severity": spike.severity,
                        "change": f"{spike.relative_change:.1%}",
                        "timeframe": spike.timeframe
                    }
                    for spike in status.recent_spikes[:3]  # Top 3 recent spikes
                ]
            },
            "performance": {
                "calculation_latency_ms": round(status.calculation_latency_ms, 1)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting cross-asset status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/cross-asset/top-correlated")
async def get_top_correlated_pairs(
    timeframe: str = Query("1h", pattern="^(1h|4h|1d)$", description="Analysis timeframe"),
    top_n: int = Query(3, ge=1, le=10, description="Number of top pairs to return"),
    engine: AlertEngine = Depends(get_alert_engine)
):
    """
    Phase 2B2: Top Correlated Asset Pairs
    
    Retourne les paires d'assets les plus corrélées pour dashboard temps réel.
    """
    try:
        if not engine.cross_asset_enabled or not engine.cross_asset_analyzer:
            raise HTTPException(status_code=404, detail="Cross-asset correlation analysis not enabled")
        
        # Obtenir top paires corrélées
        top_pairs = engine.cross_asset_analyzer.get_top_correlated_pairs(timeframe, top_n=top_n)
        
        return {
            "timeframe": timeframe,
            "top_n": top_n,
            "pairs": [
                {
                    "rank": pair["rank"],
                    "asset1": pair["asset1"],
                    "asset2": pair["asset2"],
                    "correlation": round(pair["correlation"], 3),
                    "abs_correlation": round(pair["abs_correlation"], 3),
                    "strength": (
                        "very_strong" if pair["abs_correlation"] >= 0.9 else
                        "strong" if pair["abs_correlation"] >= 0.7 else
                        "moderate" if pair["abs_correlation"] >= 0.5 else
                        "weak"
                    )
                }
                for pair in top_pairs
            ],
            "calculated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting top correlated pairs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/cross-asset/systemic-risk")
async def get_systemic_risk(
    timeframe: str = Query("1h", pattern="^(1h|4h|1d)$", description="Analysis timeframe"),
    engine: AlertEngine = Depends(get_alert_engine)
):
    """
    Phase 2B2: Systemic Risk Assessment
    
    Retourne l'évaluation complète du risque systémique.
    """
    try:
        if not engine.cross_asset_enabled or not engine.cross_asset_analyzer:
            raise HTTPException(status_code=404, detail="Cross-asset correlation analysis not enabled")
        
        # Calculer score de risque systémique
        risk_score = engine.cross_asset_analyzer.calculate_systemic_risk_score(timeframe)
        status = engine.cross_asset_analyzer.get_status(timeframe)
        
        return {
            "timeframe": timeframe,
            "systemic_risk": {
                "score": round(risk_score, 3),
                "level": (
                    "critical" if risk_score >= 0.8 else
                    "high" if risk_score >= 0.6 else
                    "medium" if risk_score >= 0.4 else
                    "low"
                ),
                "factors": {
                    "avg_correlation": round(status.avg_correlation, 3),
                    "active_clusters": len(status.active_clusters),
                    "recent_spikes": len(status.recent_spikes)
                }
            },
            "recommendations": (
                ["Immediate freeze recommended", "Review portfolio composition", "Monitor contagion risk"] if risk_score >= 0.8 else
                ["Reduce position sizes", "Enable slow trading mode", "Monitor closely"] if risk_score >= 0.6 else
                ["Continue monitoring", "Review correlation trends"] if risk_score >= 0.4 else
                ["Normal operation", "Standard monitoring"]
            ),
            "calculated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error calculating systemic risk: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# REMOVED: Test endpoints for debugging Phase 3 (production cleanup)
# Former endpoints: /test/generate, /test/clear, /test/force-evaluation
# These were temporary debug endpoints that should not be exposed in production

# Test endpoints without authentication (for debugging/testing only)
@router.post("/test/acknowledge/{alert_id}")
async def test_acknowledge_alert(
    alert_id: str,
    engine: AlertEngine = Depends(get_alert_engine),
    enabled: bool = Depends(ensure_test_endpoints_enabled)
):
    """
    Test endpoint pour acknowledge sans auth (DEBUG ONLY)
    """
    try:
        success = await engine.acknowledge_alert(alert_id, "test_user")
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "success": True,
            "message": f"Alert {alert_id} acknowledged by test_user",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        # Propager 404/503 correctement
        raise
    except Exception as e:
        logger.error(f"Error in test acknowledge: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/test/snooze/{alert_id}")
async def test_snooze_alert(
    alert_id: str,
    payload: Dict[str, Any] = None,
    engine: AlertEngine = Depends(get_alert_engine),
    enabled: bool = Depends(ensure_test_endpoints_enabled)
):
    """
    Test endpoint pour snooze sans auth (DEBUG ONLY)
    """
    try:
        # Support both structured and ad-hoc payloads
        minutes = 60
        if isinstance(payload, dict):
            if 'minutes' in payload and isinstance(payload['minutes'], (int, float)):
                minutes = int(payload['minutes'])
            elif 'snooze_duration_minutes' in payload and isinstance(payload['snooze_duration_minutes'], (int, float)):
                minutes = int(payload['snooze_duration_minutes'])
        if minutes < 5:
            minutes = 5
        success = await engine.snooze_alert(alert_id, minutes)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "success": True,
            "message": f"Alert {alert_id} snoozed for {minutes} minutes",
            "snooze_until": (datetime.now() + timedelta(minutes=minutes)).isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        # Propager 404 correctement
        raise
    except Exception as e:
        logger.error(f"Error in test snooze: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/test/generate/{count}")
async def test_generate_alerts(
    count: int = 3,
    engine: AlertEngine = Depends(get_alert_engine),
    enabled: bool = Depends(ensure_test_endpoints_enabled)
):
    """
    Endpoint de test pour générer des alertes de démonstration (DEBUG ONLY)
    """
    try:
        # Correct imports and object creation
        from services.alerts.alert_types import Alert, AlertType, AlertSeverity
        import uuid
        
        test_alerts = []
        alert_types = [AlertType.PORTFOLIO_DRIFT, AlertType.VOL_Q90_CROSS, AlertType.REGIME_FLIP]
        severities = [AlertSeverity.S1, AlertSeverity.S2, AlertSeverity.S3]
        
        for i in range(min(count, 10)):  # Limit to 10 alerts max
            alert_type = alert_types[i % len(alert_types)]
            severity = severities[i % len(severities)]
            
            alert = Alert(
                id=str(uuid.uuid4()),
                alert_type=alert_type,
                severity=severity,
                data={
                    "test": True,
                    "index": i + 1,
                    "trigger_value": 0.85 + (i * 0.1),
                    "threshold": 0.8
                },
                created_at=datetime.now()
            )
            
            # Store the alert using storage API
            stored = engine.storage.store_alert(alert)
            if stored:
                test_alerts.append(alert)
        
        return {
            "success": True,
            "message": f"Generated {len(test_alerts)} test alerts",
            "alerts": [{"id": a.id, "type": a.alert_type.value, "severity": a.severity.value} for a in test_alerts],
            "alert_id": (test_alerts[0].id if test_alerts else None),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating test alerts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Convenience alias: allow both POST and GET without path param
@router.post("/test/generate")
@router.get("/test/generate")
async def test_generate_alerts_default(
    engine: AlertEngine = Depends(get_alert_engine),
    enabled: bool = Depends(ensure_test_endpoints_enabled)
):
    """Alias sans paramètre de chemin: génère 3 alertes par défaut."""
    return await test_generate_alerts(count=3, engine=engine)

# Hook pour initialisation depuis main.py
def initialize_alert_engine(engine: AlertEngine):
    """Initialise l'instance globale AlertEngine"""
    global alert_engine
    alert_engine = engine
    logger.info("Alert engine initialized for API endpoints")
