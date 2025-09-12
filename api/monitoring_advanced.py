#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Monitoring Avancé - Endpoints pour surveillance avancée

Ce module fournit les endpoints API pour le monitoring avancé:
- Métriques de performance en temps réel
- Alertes et notifications
- Historique et analytics
- Gestion de la santé système
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Body
from fastapi.responses import JSONResponse
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
import logging
from datetime import datetime, timezone, timedelta

from services.monitoring.connection_monitor import (
    connection_monitor, ConnectionStatus, AlertLevel
)
from services.notifications.alert_manager import alert_manager, AlertType
from services.notifications.notification_sender import notification_sender, NotificationConfig
from services.notifications.monitoring import monitoring_service

logger = logging.getLogger(__name__)

# Router pour les endpoints monitoring avancé
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# Modèles Pydantic pour notifications (migrés depuis monitoring_endpoints.py)
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

# Note: FastAPI lifecycle events will be handled by the main app
# The monitoring will start automatically when first accessed

@router.get("/health")
async def get_system_health():
    """Vue d'ensemble de la santé du système"""
    try:
        # Données simulées pour le développement 
        mock_current_status = {
            "binance": {"status": "healthy", "response_time_ms": 85},
            "kraken": {"status": "healthy", "response_time_ms": 120},
            "coinbase": {"status": "degraded", "response_time_ms": 350}
        }
        
        mock_performance_summary = {
            "total_exchanges": 3,
            "healthy_exchanges": 2,
            "degraded_exchanges": 1,
            "critical_exchanges": 0,
            "offline_exchanges": 0,
            "average_response_time": 185.0,
            "overall_uptime": 94.2
        }
        
        mock_active_alerts = []
        
        current_status = mock_current_status
        performance_summary = mock_performance_summary
        active_alerts = mock_active_alerts
        
        # Code original commenté pour le développement
        # if not connection_monitor.monitoring_active:
        #     await connection_monitor.start_monitoring()
        # current_status = connection_monitor.get_current_status()
        # performance_summary = connection_monitor.get_performance_summary()
        # active_alerts = connection_monitor.get_alerts(resolved=False)
        
        # Déterminer statut global
        if performance_summary.get("critical_exchanges", 0) > 0:
            global_status = "critical"
        elif performance_summary.get("degraded_exchanges", 0) > 0:
            global_status = "degraded"  
        elif performance_summary.get("offline_exchanges", 0) > 0:
            global_status = "warning"
        else:
            global_status = "healthy"
            
        return JSONResponse({
            "global_status": global_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "monitoring_active": connection_monitor.monitoring_active,
            "summary": performance_summary,
            "exchanges": current_status,
            "active_alerts_count": len(active_alerts),
            "last_check": max([
                status.get("last_check", "") 
                for status in current_status.values()
            ], default="")
        })
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/detailed")
async def get_detailed_status():
    """Statut détaillé avec métriques complètes"""
    try:
        # Données simulées pour le développement
        detailed_status = {
            "binance": {
                "status": "healthy",
                "response_time_ms": 85,
                "success_rate_1h": 98.5,
                "uptime_percentage": 99.2,
                "error_count_1h": 2,
                "connection_stability": 96,
                "response_trend": "stable",
                "last_check": datetime.now(timezone.utc).isoformat()
            },
            "kraken": {
                "status": "healthy", 
                "response_time_ms": 120,
                "success_rate_1h": 97.1,
                "uptime_percentage": 98.8,
                "error_count_1h": 4,
                "connection_stability": 94,
                "response_trend": "improving",
                "last_check": datetime.now(timezone.utc).isoformat()
            },
            "coinbase": {
                "status": "degraded",
                "response_time_ms": 350,
                "success_rate_1h": 89.2,
                "uptime_percentage": 92.5,
                "error_count_1h": 12,
                "connection_stability": 78,
                "response_trend": "degrading",
                "last_check": datetime.now(timezone.utc).isoformat()
            }
        }
        
        return JSONResponse({
            "exchanges": detailed_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Code original commenté pour le développement
        # current_status = connection_monitor.get_current_status()        
        # for exchange, status in current_status.items():
        #     metrics_history = connection_monitor.metrics_history.get(exchange, [])
        #     if metrics_history:
        #         recent_10 = metrics_history[-10:]
        #         response_times = [m.response_time_ms for m in recent_10 if m.connected]
        #         response_trend = "stable"
        #         if len(response_times) >= 3:
        #             if response_times[-1] > response_times[0] * 1.2:
        #                 response_trend = "increasing"
        #             elif response_times[-1] < response_times[0] * 0.8:
        #                 response_trend = "decreasing"
        
    except Exception as e:
        logger.error(f"Error getting detailed status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts")
async def get_alerts(
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    level: Optional[str] = Query(None, description="Filter by alert level"),
    exchange: Optional[str] = Query(None, description="Filter by exchange"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of alerts")
):
    """Obtenir les alertes avec filtres"""
    try:
        # Données simulées pour le développement
        mock_alerts = [
            {
                "id": "alert_1",
                "level": "warning",
                "exchange": "coinbase",
                "message": "Response time elevated - averaging 350ms",
                "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(),
                "resolved": False
            },
            {
                "id": "alert_2", 
                "level": "info",
                "exchange": "kraken",
                "message": "Connection restored - performance improving",
                "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                "resolved": True
            }
        ]
        
        alerts = mock_alerts
        
        # Code original commenté pour le développement
        # alerts = connection_monitor.get_alerts(resolved=resolved)
        # if level:
        #     try:
        #         alert_level = AlertLevel(level.lower())
        #         alerts = [a for a in alerts if a.get("level") == alert_level.value]
        #     except ValueError:
        #         raise HTTPException(status_code=400, detail=f"Invalid alert level: {level}")
        # if exchange:
        #     alerts = [a for a in alerts if a.get("exchange") == exchange]
        # alerts = alerts[:limit]
        
        total_alerts = len(alerts)
        active_alerts = len([a for a in alerts if not a.get("resolved", False)])
        
        return JSONResponse({
            "alerts": alerts,
            "pagination": {
                "total": total_alerts,
                "active": active_alerts,
                "returned": len(alerts),
                "limit": limit
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# REMOVED: Duplicate alert resolution endpoint - use /api/alerts/resolve/{alert_id} instead
# Alert management should be centralized in alerts_endpoints.py

@router.get("/metrics/{exchange}")
async def get_exchange_metrics(
    exchange: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history to include")
):
    """Métriques détaillées pour un exchange spécifique"""
    try:
        # Données simulées pour le développement
        mock_metrics = [
            {
                "timestamp": (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
                "connected": True if i % 10 != 0 else False,
                "response_time_ms": 85 + (i % 50),
                "success_rate_1h": 95.0 + (i % 10),
                "uptime_percentage": 98.0 + (i % 3),
                "last_error": None if i % 15 != 0 else f"Mock error #{i}"
            }
            for i in range(min(hours, 100))  # Limiter pour éviter trop de données
        ]
        
        filtered_metrics = mock_metrics
        
        # Code original commenté pour le développement
        # if exchange not in connection_monitor.metrics_history:
        #     raise HTTPException(status_code=404, detail="Exchange not found in monitoring data")
        # cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        # metrics_list = connection_monitor.metrics_history[exchange]
        # filtered_metrics = [
        #     m for m in metrics_list
        #     if datetime.fromisoformat(m.timestamp.replace('Z', '+00:00')) > cutoff
        # ]
        
        if not filtered_metrics:
            return JSONResponse({
                "exchange": exchange,
                "metrics": [],
                "summary": {"message": "No metrics found for the specified period"},
                "period_hours": hours
            })
            
        # Calculer statistiques
        response_times = [m["response_time_ms"] for m in filtered_metrics if m["connected"]]
        connected_count = sum(1 for m in filtered_metrics if m["connected"])
        
        summary = {
            "total_checks": len(filtered_metrics),
            "successful_connections": connected_count,
            "uptime_percentage": round((connected_count / len(filtered_metrics)) * 100, 2),
            "avg_response_time": round(sum(response_times) / len(response_times), 2) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "total_errors": sum(1 for m in filtered_metrics if m.get("last_error")),
            "current_status": "healthy" if filtered_metrics and filtered_metrics[-1]["connected"] else "offline"
        }
        
        return JSONResponse({
            "exchange": exchange,
            "period_hours": hours,
            "summary": summary,
            "metrics": filtered_metrics,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metrics for {exchange}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/performance")
async def get_performance_analytics(
    period_hours: int = Query(24, ge=1, le=168, description="Analysis period in hours")
):
    """Analytics de performance agrégées"""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=period_hours)
        
        analytics = {
            "period_hours": period_hours,
            "exchanges": {},
            "global_stats": {
                "total_checks": 0,
                "total_successful": 0,
                "total_errors": 0,
                "avg_response_time": 0,
                "best_performer": None,
                "worst_performer": None
            }
        }
        
        all_response_times = []
        exchange_performance = {}
        
        for exchange, metrics_list in connection_monitor.metrics_history.items():
            # Filtrer par période
            filtered_metrics = [
                m for m in metrics_list
                if datetime.fromisoformat(m.timestamp.replace('Z', '+00:00')) > cutoff
            ]
            
            if not filtered_metrics:
                continue
                
            # Statistiques par exchange
            response_times = [m.response_time_ms for m in filtered_metrics if m.connected]
            successful = sum(1 for m in filtered_metrics if m.connected)
            errors = sum(1 for m in filtered_metrics if m.last_error)
            
            exchange_stats = {
                "total_checks": len(filtered_metrics),
                "successful_connections": successful,
                "error_count": errors,
                "uptime_percentage": round((successful / len(filtered_metrics)) * 100, 2),
                "avg_response_time": round(sum(response_times) / len(response_times), 2) if response_times else 0,
                "reliability_score": round(
                    ((successful / len(filtered_metrics)) * 0.7 + 
                     (1 - min(1, sum(response_times) / len(response_times) / 1000) if response_times else 0) * 0.3) * 100, 2
                )
            }
            
            analytics["exchanges"][exchange] = exchange_stats
            exchange_performance[exchange] = exchange_stats["reliability_score"]
            
            # Agréger pour stats globales
            analytics["global_stats"]["total_checks"] += len(filtered_metrics)
            analytics["global_stats"]["total_successful"] += successful
            analytics["global_stats"]["total_errors"] += errors
            all_response_times.extend(response_times)
            
        # Finaliser stats globales
        if analytics["global_stats"]["total_checks"] > 0:
            analytics["global_stats"]["overall_uptime"] = round(
                (analytics["global_stats"]["total_successful"] / analytics["global_stats"]["total_checks"]) * 100, 2
            )
            
        if all_response_times:
            analytics["global_stats"]["avg_response_time"] = round(
                sum(all_response_times) / len(all_response_times), 2
            )
            
        # Meilleur et pire performer
        if exchange_performance:
            analytics["global_stats"]["best_performer"] = max(exchange_performance, key=exchange_performance.get)
            analytics["global_stats"]["worst_performer"] = min(exchange_performance, key=exchange_performance.get)
            
        return JSONResponse(analytics)
        
    except Exception as e:
        logger.error(f"Error getting performance analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/trends")
async def get_trend_analytics(
    exchange: Optional[str] = Query(None, description="Specific exchange or all"),
    hours: int = Query(24, ge=6, le=168, description="Period for trend analysis")
):
    """Analysis des tendances de performance"""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Sélectionner exchanges à analyser
        exchanges_to_analyze = [exchange] if exchange else list(connection_monitor.metrics_history.keys())
        
        trends = {}
        
        for exch in exchanges_to_analyze:
            if exch not in connection_monitor.metrics_history:
                continue
                
            metrics_list = connection_monitor.metrics_history[exch]
            filtered_metrics = [
                m for m in metrics_list
                if datetime.fromisoformat(m.timestamp.replace('Z', '+00:00')) > cutoff
            ]
            
            if len(filtered_metrics) < 10:  # Besoin de suffisamment de données
                trends[exch] = {"message": "Insufficient data for trend analysis"}
                continue
                
            # Diviser en périodes pour analyse tendance
            period_size = len(filtered_metrics) // 4  # 4 périodes
            periods = [
                filtered_metrics[i:i+period_size] 
                for i in range(0, len(filtered_metrics), period_size)
            ][:4]
            
            period_stats = []
            for i, period in enumerate(periods):
                if not period:
                    continue
                    
                response_times = [m.response_time_ms for m in period if m.connected]
                successful = sum(1 for m in period if m.connected)
                
                period_stats.append({
                    "period": i + 1,
                    "uptime": round((successful / len(period)) * 100, 2),
                    "avg_response_time": round(sum(response_times) / len(response_times), 2) if response_times else 0,
                    "error_rate": round((sum(1 for m in period if m.last_error) / len(period)) * 100, 2)
                })
            
            # Calculer tendances
            if len(period_stats) >= 3:
                uptime_trend = "stable"
                response_trend = "stable"
                
                # Tendance uptime
                first_half_uptime = sum(p["uptime"] for p in period_stats[:2]) / 2
                second_half_uptime = sum(p["uptime"] for p in period_stats[2:]) / 2
                
                if second_half_uptime > first_half_uptime + 2:
                    uptime_trend = "improving"
                elif second_half_uptime < first_half_uptime - 2:
                    uptime_trend = "degrading"
                    
                # Tendance temps de réponse
                first_half_response = sum(p["avg_response_time"] for p in period_stats[:2]) / 2
                second_half_response = sum(p["avg_response_time"] for p in period_stats[2:]) / 2
                
                if second_half_response > first_half_response * 1.1:
                    response_trend = "slowing"
                elif second_half_response < first_half_response * 0.9:
                    response_trend = "improving"
                    
                trends[exch] = {
                    "uptime_trend": uptime_trend,
                    "response_trend": response_trend,
                    "period_stats": period_stats,
                    "overall_direction": "improving" if uptime_trend == "improving" and response_trend != "slowing" else
                                      "degrading" if uptime_trend == "degrading" or response_trend == "slowing" else "stable"
                }
            else:
                trends[exch] = {"message": "Insufficient periods for trend analysis"}
                
        return JSONResponse({
            "trends": trends,
            "analysis_period_hours": hours,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting trend analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/monitoring/restart")
async def restart_monitoring():
    """Redémarrer le monitoring"""
    try:
        await connection_monitor.stop_monitoring()
        await connection_monitor.start_monitoring()
        
        return JSONResponse({
            "message": "Monitoring restarted successfully",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error restarting monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/monitoring/config")
async def get_monitoring_config():
    """Configuration actuelle du monitoring"""
    return JSONResponse({
        "check_interval_seconds": connection_monitor.check_interval,
        "retention_hours": connection_monitor.metrics_retention_hours,
        "alert_thresholds": connection_monitor.alert_thresholds,
        "monitoring_active": connection_monitor.monitoring_active,
        "storage_path": str(connection_monitor.storage_path),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@router.put("/monitoring/config")
async def update_monitoring_config(config: Dict[str, Any]):
    """Mettre à jour la configuration du monitoring"""
    try:
        updated_fields = []
        
        if "check_interval_seconds" in config:
            connection_monitor.check_interval = max(10, min(300, int(config["check_interval_seconds"])))
            updated_fields.append("check_interval_seconds")
            
        if "retention_hours" in config:
            connection_monitor.metrics_retention_hours = max(1, min(168, int(config["retention_hours"])))
            updated_fields.append("retention_hours")
            
        if "alert_thresholds" in config and isinstance(config["alert_thresholds"], dict):
            for key, value in config["alert_thresholds"].items():
                if key in connection_monitor.alert_thresholds:
                    connection_monitor.alert_thresholds[key] = float(value)
                    updated_fields.append(f"alert_thresholds.{key}")
                    
        return JSONResponse({
            "message": "Configuration updated successfully",
            "updated_fields": updated_fields,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error updating monitoring config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINTS NOTIFICATIONS (migrés depuis monitoring_endpoints.py) ---

@router.post("/notifications/config")
async def add_notification_config(request: NotificationConfigRequest):
    """
    Ajouter ou mettre à jour une configuration de notification
    """
    try:
        # Mapper les niveaux string vers les enums
        level_map = {
            "debug": AlertLevel.DEBUG,
            "info": AlertLevel.INFO,  
            "warning": AlertLevel.WARNING,
            "error": AlertLevel.ERROR,
            "critical": AlertLevel.CRITICAL
        }
        
        min_level_enum = level_map.get(request.min_level.lower(), AlertLevel.INFO)
        
        # Mapper les types d'alertes si spécifiés
        alert_types_enums = None
        if request.alert_types:
            type_map = {
                "system": AlertType.SYSTEM,
                "portfolio": AlertType.PORTFOLIO,
                "exchange": AlertType.EXCHANGE,
                "price": AlertType.PRICE,
                "balance": AlertType.BALANCE
            }
            alert_types_enums = [
                type_map.get(t.lower()) for t in request.alert_types 
                if t.lower() in type_map
            ]
        
        # Créer la configuration
        config = NotificationConfig(
            channel_type=request.channel_type,
            enabled=request.enabled,
            min_level=min_level_enum,
            alert_types=alert_types_enums,
            **request.config
        )
        
        # Ajouter la configuration
        notification_sender.add_notification_config(config)
        
        return {
            "success": True,
            "message": f"Configuration {request.channel_type} ajoutée"
        }
        
    except Exception as e:
        logger.error(f"Error adding notification config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/notifications/config/{channel_type}")
async def remove_notification_config(channel_type: str):
    """
    Supprimer une configuration de notification
    """
    try:
        # Essayer de supprimer la configuration
        removed = notification_sender.remove_notification_config(channel_type)
        
        if removed:
            return {
                "success": True,
                "message": f"Configuration {channel_type} supprimée"
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Configuration {channel_type} non trouvée"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing notification config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notifications/status")
async def get_notification_status():
    """
    Obtenir le statut des notifications
    """
    try:
        configs = notification_sender.get_notification_configs()
        
        return {
            "success": True,
            "configs": [
                {
                    "channel_type": config.channel_type,
                    "enabled": config.enabled,
                    "min_level": config.min_level.value if hasattr(config.min_level, 'value') else str(config.min_level),
                    "alert_types": [t.value if hasattr(t, 'value') else str(t) for t in (config.alert_types or [])],
                    "config_keys": list(config.config.keys()) if hasattr(config, 'config') else []
                }
                for config in configs
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting notification status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/test")
async def test_alert(request: TestAlertRequest):
    """
    Déclencher une alerte de test
    """
    try:
        # Mapper le niveau
        level_map = {
            "debug": AlertLevel.DEBUG,
            "info": AlertLevel.INFO,  
            "warning": AlertLevel.WARNING,
            "error": AlertLevel.ERROR,
            "critical": AlertLevel.CRITICAL
        }
        
        level_enum = level_map.get(request.level.lower(), AlertLevel.INFO)
        
        # Créer l'alerte
        alert_manager.create_alert(
            alert_type=AlertType.SYSTEM,
            level=level_enum,
            source="api_test",
            title=request.title or f"Test Alert - {request.level.upper()}",
            message=request.message or f"Ceci est un test du système d'alerte de niveau {request.level}",
            data={"test": True, "timestamp": datetime.now().isoformat()}
        )
        
        return {
            "success": True,
            "message": "Alerte de test envoyée",
            "level": request.level
        }
        
    except Exception as e:
        logger.error(f"Error sending test alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start")
async def start_monitoring():
    """
    Démarrer le service de monitoring
    """
    try:
        monitoring_service.start()
        return {
            "success": True,
            "message": "Service de monitoring démarré"
        }
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_monitoring():
    """
    Arrêter le service de monitoring
    """
    try:
        monitoring_service.stop()
        return {
            "success": True,
            "message": "Service de monitoring arrêté"
        }
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))