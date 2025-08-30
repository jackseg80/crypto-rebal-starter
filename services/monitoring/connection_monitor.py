#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Connection Monitor - Surveillance avancée des connexions exchanges

Ce module implémente un système de monitoring sophistiqué pour:
- Tracking santé connexions en temps réel
- Métriques de performance et latence
- Détection de dégradations de service
- Alertes automatiques et notifications
- Historique de disponibilité
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import statistics
from pathlib import Path

logger = logging.getLogger(__name__)

class ConnectionStatus(Enum):
    """Statuts possibles des connexions"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNSTABLE = "unstable"
    CRITICAL = "critical"
    OFFLINE = "offline"

class AlertLevel(Enum):
    """Niveaux d'alerte"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class ConnectionMetrics:
    """Métriques de connexion"""
    exchange: str
    timestamp: str
    connected: bool
    response_time_ms: float
    success_rate_1h: float
    success_rate_24h: float
    uptime_percentage: float
    error_count_1h: int
    last_error: Optional[str]
    api_calls_count: int
    status: ConnectionStatus
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Convert enum to string for JSON serialization
        result['status'] = self.status.value
        return result

@dataclass
class Alert:
    """Alerte système"""
    id: str
    exchange: str
    level: AlertLevel
    message: str
    timestamp: str
    resolved: bool = False
    resolution_time: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Convert enum to string for JSON serialization
        result['level'] = self.level.value
        return result

class ConnectionMonitor:
    """Moniteur avancé de connexions"""
    
    def __init__(self):
        self.metrics_history: Dict[str, List[ConnectionMetrics]] = {}
        self.alerts: List[Alert] = []
        self.monitoring_active = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.check_interval = 30  # secondes
        self.metrics_retention_hours = 24
        self.alert_thresholds = {
            "response_time_warning": 2000,  # ms
            "response_time_critical": 5000,  # ms
            "success_rate_warning": 95.0,   # %
            "success_rate_critical": 90.0,  # %
            "uptime_warning": 98.0,         # %
            "uptime_critical": 95.0,        # %
        }
        
        # Storage
        self.storage_path = Path("data/monitoring")
        self.storage_path.mkdir(exist_ok=True)
        
    async def start_monitoring(self):
        """Démarrer le monitoring continu"""
        if self.monitoring_active:
            logger.info("Monitoring already active")
            return
            
        self.monitoring_active = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Advanced connection monitoring started")
        
    async def stop_monitoring(self):
        """Arrêter le monitoring"""
        self.monitoring_active = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Connection monitoring stopped")
        
    async def _monitoring_loop(self):
        """Boucle principale de monitoring"""
        while self.monitoring_active:
            try:
                await self._check_all_connections()
                await self._cleanup_old_metrics()
                await self._process_alerts()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _check_all_connections(self):
        """Vérifier toutes les connexions configurées"""
        from services.execution.exchange_adapter import exchange_registry
        
        if not exchange_registry.adapters:
            return
            
        for exchange_name, adapter in exchange_registry.adapters.items():
            try:
                metrics = await self._check_single_connection(exchange_name, adapter)
                self._store_metrics(metrics)
                await self._evaluate_alerts(metrics)
            except Exception as e:
                logger.error(f"Error checking connection {exchange_name}: {e}")
                
    async def _check_single_connection(self, exchange_name: str, adapter) -> ConnectionMetrics:
        """Vérifier une connexion spécifique"""
        start_time = time.time()
        
        # Test de base
        connected = False
        error_message = None
        api_calls_successful = 0
        total_api_calls = 0
        
        try:
            # Test connexion
            if not adapter.connected:
                connected = await adapter.connect()
            else:
                connected = adapter.connected
                
            if connected:
                # Tests API pour mesurer performances
                test_calls = [
                    self._test_api_call(adapter.get_balance, "USDT"),
                    self._test_api_call(adapter.get_current_price, "BTC/USDT"),
                    self._test_api_call(adapter.get_trading_pairs)
                ]
                
                results = await asyncio.gather(*test_calls, return_exceptions=True)
                
                for result in results:
                    total_api_calls += 1
                    if not isinstance(result, Exception):
                        api_calls_successful += 1
                    else:
                        if error_message is None:
                            error_message = str(result)
                        
        except Exception as e:
            error_message = str(e)
            connected = False
            
        response_time_ms = (time.time() - start_time) * 1000
        
        # Calculer métriques historiques
        success_rate_1h = self._calculate_success_rate(exchange_name, hours=1)
        success_rate_24h = self._calculate_success_rate(exchange_name, hours=24)
        uptime_percentage = self._calculate_uptime(exchange_name, hours=24)
        error_count_1h = self._count_errors(exchange_name, hours=1)
        
        # Déterminer statut
        status = self._determine_status(
            connected, response_time_ms, success_rate_1h, 
            success_rate_24h, uptime_percentage
        )
        
        return ConnectionMetrics(
            exchange=exchange_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            connected=connected,
            response_time_ms=response_time_ms,
            success_rate_1h=success_rate_1h,
            success_rate_24h=success_rate_24h,
            uptime_percentage=uptime_percentage,
            error_count_1h=error_count_1h,
            last_error=error_message,
            api_calls_count=api_calls_successful,
            status=status
        )
        
    async def _test_api_call(self, api_func, *args):
        """Tester un appel API spécifique"""
        try:
            result = await api_func(*args) if args else await api_func()
            return result
        except Exception as e:
            raise e
            
    def _store_metrics(self, metrics: ConnectionMetrics):
        """Stocker les métriques en mémoire et sur disque"""
        exchange = metrics.exchange
        
        if exchange not in self.metrics_history:
            self.metrics_history[exchange] = []
            
        self.metrics_history[exchange].append(metrics)
        
        # Sauvegarder sur disque (asynchrone)
        asyncio.create_task(self._persist_metrics(metrics))
        
    async def _persist_metrics(self, metrics: ConnectionMetrics):
        """Persister les métriques sur disque"""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            file_path = self.storage_path / f"metrics_{metrics.exchange}_{date_str}.json"
            
            # Lire données existantes
            existing_data = []
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        existing_data = json.load(f)
                except:
                    existing_data = []
            
            # Ajouter nouvelles métriques
            existing_data.append(metrics.to_dict())
            
            # Limiter à 2880 entrées par jour (30s * 2880 = 24h)
            if len(existing_data) > 2880:
                existing_data = existing_data[-2880:]
                
            # Sauvegarder
            with open(file_path, 'w') as f:
                json.dump(existing_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error persisting metrics: {e}")
            
    def _calculate_success_rate(self, exchange: str, hours: int) -> float:
        """Calculer le taux de succès sur une période"""
        if exchange not in self.metrics_history:
            return 100.0
            
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history[exchange]
            if datetime.fromisoformat(m.timestamp.replace('Z', '+00:00')) > cutoff
        ]
        
        if not recent_metrics:
            return 100.0
            
        successful = sum(1 for m in recent_metrics if m.connected and m.api_calls_count > 0)
        return (successful / len(recent_metrics)) * 100.0
        
    def _calculate_uptime(self, exchange: str, hours: int) -> float:
        """Calculer le taux de disponibilité sur une période"""
        if exchange not in self.metrics_history:
            return 100.0
            
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history[exchange]
            if datetime.fromisoformat(m.timestamp.replace('Z', '+00:00')) > cutoff
        ]
        
        if not recent_metrics:
            return 100.0
            
        connected_count = sum(1 for m in recent_metrics if m.connected)
        return (connected_count / len(recent_metrics)) * 100.0
        
    def _count_errors(self, exchange: str, hours: int) -> int:
        """Compter les erreurs sur une période"""
        if exchange not in self.metrics_history:
            return 0
            
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history[exchange]
            if datetime.fromisoformat(m.timestamp.replace('Z', '+00:00')) > cutoff
        ]
        
        return sum(1 for m in recent_metrics if m.last_error is not None)
        
    def _determine_status(self, connected: bool, response_time: float, 
                         success_rate_1h: float, success_rate_24h: float, 
                         uptime: float) -> ConnectionStatus:
        """Déterminer le statut basé sur les métriques"""
        if not connected:
            return ConnectionStatus.OFFLINE
            
        # Vérifier seuils critiques
        if (response_time > self.alert_thresholds["response_time_critical"] or
            success_rate_1h < self.alert_thresholds["success_rate_critical"] or
            uptime < self.alert_thresholds["uptime_critical"]):
            return ConnectionStatus.CRITICAL
            
        # Vérifier seuils d'avertissement
        if (response_time > self.alert_thresholds["response_time_warning"] or
            success_rate_1h < self.alert_thresholds["success_rate_warning"] or
            uptime < self.alert_thresholds["uptime_warning"]):
            
            # Distinguer entre DEGRADED et UNSTABLE
            if success_rate_24h < 95.0:
                return ConnectionStatus.UNSTABLE
            else:
                return ConnectionStatus.DEGRADED
                
        return ConnectionStatus.HEALTHY
        
    async def _evaluate_alerts(self, metrics: ConnectionMetrics):
        """Évaluer et générer des alertes basées sur les métriques"""
        exchange = metrics.exchange
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Alertes de disponibilité
        if not metrics.connected:
            await self._create_alert(
                exchange, AlertLevel.CRITICAL,
                f"Exchange {exchange} is offline",
                current_time
            )
        elif metrics.status == ConnectionStatus.CRITICAL:
            await self._create_alert(
                exchange, AlertLevel.CRITICAL,
                f"Exchange {exchange} is in critical state (Response: {metrics.response_time_ms:.0f}ms, Success: {metrics.success_rate_1h:.1f}%)",
                current_time
            )
        elif metrics.status == ConnectionStatus.UNSTABLE:
            await self._create_alert(
                exchange, AlertLevel.WARNING,
                f"Exchange {exchange} is unstable (Success rate 24h: {metrics.success_rate_24h:.1f}%)",
                current_time
            )
        elif metrics.status == ConnectionStatus.DEGRADED:
            await self._create_alert(
                exchange, AlertLevel.WARNING,
                f"Exchange {exchange} performance degraded (Response: {metrics.response_time_ms:.0f}ms)",
                current_time
            )
            
        # Alertes d'erreurs fréquentes
        if metrics.error_count_1h >= 5:
            await self._create_alert(
                exchange, AlertLevel.WARNING,
                f"High error rate on {exchange}: {metrics.error_count_1h} errors in last hour",
                current_time
            )
            
    async def _create_alert(self, exchange: str, level: AlertLevel, 
                          message: str, timestamp: str):
        """Créer une nouvelle alerte"""
        # Éviter les alertes en double
        recent_similar = [
            a for a in self.alerts
            if (a.exchange == exchange and 
                a.level == level and 
                not a.resolved and
                abs((datetime.fromisoformat(timestamp.replace('Z', '+00:00')) - 
                     datetime.fromisoformat(a.timestamp.replace('Z', '+00:00'))).total_seconds()) < 300)  # 5 minutes
        ]
        
        if recent_similar:
            return
            
        alert_id = f"{exchange}_{level.value}_{int(time.time())}"
        alert = Alert(
            id=alert_id,
            exchange=exchange,
            level=level,
            message=message,
            timestamp=timestamp
        )
        
        self.alerts.append(alert)
        logger.warning(f"ALERT [{level.value.upper()}] {exchange}: {message}")
        
        # Persister l'alerte
        await self._persist_alert(alert)
        
    async def _persist_alert(self, alert: Alert):
        """Persister une alerte sur disque"""
        try:
            alerts_file = self.storage_path / "alerts.json"
            
            # Lire alertes existantes
            existing_alerts = []
            if alerts_file.exists():
                try:
                    with open(alerts_file, 'r') as f:
                        existing_alerts = json.load(f)
                except:
                    existing_alerts = []
            
            # Ajouter nouvelle alerte
            existing_alerts.append(alert.to_dict())
            
            # Limiter à 1000 alertes
            if len(existing_alerts) > 1000:
                existing_alerts = existing_alerts[-1000:]
                
            # Sauvegarder
            with open(alerts_file, 'w') as f:
                json.dump(existing_alerts, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error persisting alert: {e}")
            
    async def _process_alerts(self):
        """Traiter et résoudre automatiquement certaines alertes"""
        for alert in self.alerts:
            if alert.resolved:
                continue
                
            # Auto-résolution pour alertes temporaires
            alert_age = (datetime.now(timezone.utc) - 
                        datetime.fromisoformat(alert.timestamp.replace('Z', '+00:00'))).total_seconds()
            
            if alert_age > 1800:  # 30 minutes
                # Vérifier si le problème est résolu
                if alert.exchange in self.metrics_history:
                    recent_metrics = self.metrics_history[alert.exchange][-3:]  # 3 dernières métriques
                    if recent_metrics and all(m.status == ConnectionStatus.HEALTHY for m in recent_metrics):
                        alert.resolved = True
                        alert.resolution_time = datetime.now(timezone.utc).isoformat()
                        logger.info(f"Auto-resolved alert {alert.id}")
                        
    async def _cleanup_old_metrics(self):
        """Nettoyer les anciennes métriques en mémoire"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.metrics_retention_hours)
        
        for exchange in list(self.metrics_history.keys()):
            self.metrics_history[exchange] = [
                m for m in self.metrics_history[exchange]
                if datetime.fromisoformat(m.timestamp.replace('Z', '+00:00')) > cutoff
            ]
            
            if not self.metrics_history[exchange]:
                del self.metrics_history[exchange]
                
    def get_current_status(self) -> Dict[str, Any]:
        """Obtenir le statut actuel de tous les exchanges"""
        status = {}
        
        for exchange, metrics_list in self.metrics_history.items():
            if not metrics_list:
                continue
                
            latest = metrics_list[-1]
            status[exchange] = {
                "status": latest.status.value,
                "connected": latest.connected,
                "response_time_ms": latest.response_time_ms,
                "success_rate_1h": latest.success_rate_1h,
                "success_rate_24h": latest.success_rate_24h,
                "uptime_percentage": latest.uptime_percentage,
                "last_check": latest.timestamp,
                "error_count_1h": latest.error_count_1h
            }
            
        return status
        
    def get_alerts(self, resolved: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Obtenir les alertes"""
        alerts = self.alerts
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
            
        return [a.to_dict() for a in sorted(alerts, key=lambda x: x.timestamp, reverse=True)]
        
    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtenir un résumé des performances"""
        if not self.metrics_history:
            return {"message": "No metrics available"}
            
        summary = {
            "total_exchanges": len(self.metrics_history),
            "healthy_exchanges": 0,
            "degraded_exchanges": 0,
            "critical_exchanges": 0,
            "offline_exchanges": 0,
            "average_response_time": 0,
            "overall_uptime": 0,
            "active_alerts": len([a for a in self.alerts if not a.resolved])
        }
        
        all_response_times = []
        all_uptimes = []
        
        for exchange, metrics_list in self.metrics_history.items():
            if not metrics_list:
                continue
                
            latest = metrics_list[-1]
            
            # Compter par statut
            if latest.status == ConnectionStatus.HEALTHY:
                summary["healthy_exchanges"] += 1
            elif latest.status in [ConnectionStatus.DEGRADED, ConnectionStatus.UNSTABLE]:
                summary["degraded_exchanges"] += 1
            elif latest.status == ConnectionStatus.CRITICAL:
                summary["critical_exchanges"] += 1
            elif latest.status == ConnectionStatus.OFFLINE:
                summary["offline_exchanges"] += 1
                
            # Collecter métriques
            if latest.connected:
                all_response_times.append(latest.response_time_ms)
            all_uptimes.append(latest.uptime_percentage)
            
        # Calculer moyennes
        if all_response_times:
            summary["average_response_time"] = statistics.mean(all_response_times)
        if all_uptimes:
            summary["overall_uptime"] = statistics.mean(all_uptimes)
            
        return summary

# Instance globale du moniteur
connection_monitor = ConnectionMonitor()