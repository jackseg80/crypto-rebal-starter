"""
Alert Manager - Système de gestion des alertes et notifications

Ce module gère les alertes pour le pipeline de rebalancement :
- Seuils de dérive de portfolio
- Échecs d'exécution
- Performances anormales
- Alertes techniques (API down, etc.)
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """Niveaux d'alerte"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertType(Enum):
    """Types d'alertes"""
    PORTFOLIO_DRIFT = "portfolio_drift"
    EXECUTION_FAILURE = "execution_failure"
    PERFORMANCE_ANOMALY = "performance_anomaly"
    API_CONNECTIVITY = "api_connectivity"
    THRESHOLD_BREACH = "threshold_breach"
    SYSTEM_ERROR = "system_error"

@dataclass
class Alert:
    """Alerte système"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Classification
    type: AlertType = AlertType.SYSTEM_ERROR
    level: AlertLevel = AlertLevel.INFO
    source: str = "system"
    
    # Contenu
    title: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # État
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    # Actions
    actions: List[str] = field(default_factory=list)
    
    def acknowledge(self) -> None:
        """Marquer l'alerte comme accusée réception"""
        self.acknowledged = True
        self.updated_at = datetime.now(timezone.utc)
    
    def resolve(self, resolution_note: str = "") -> None:
        """Résoudre l'alerte"""
        self.resolved = True
        self.resolved_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        if resolution_note:
            self.data["resolution_note"] = resolution_note

@dataclass
class AlertRule:
    """Règle de génération d'alertes"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Configuration
    name: str = ""
    description: str = ""
    enabled: bool = True
    
    # Conditions
    alert_type: AlertType = AlertType.THRESHOLD_BREACH
    level: AlertLevel = AlertLevel.WARNING
    
    # Paramètres de seuils
    metric: str = ""  # Ex: "portfolio_drift_pct", "execution_success_rate"
    threshold_value: float = 0.0
    operator: str = ">"  # >, <, >=, <=, ==, !=
    
    # Fréquence et délais
    check_interval_minutes: int = 5
    cooldown_minutes: int = 30  # Éviter le spam d'alertes
    
    # Dernier check
    last_check: Optional[datetime] = None
    last_alert: Optional[datetime] = None
    
    def should_check(self) -> bool:
        """Vérifier s'il faut effectuer le check maintenant"""
        if not self.enabled:
            return False
            
        if not self.last_check:
            return True
            
        next_check = self.last_check + timedelta(minutes=self.check_interval_minutes)
        return datetime.now(timezone.utc) >= next_check
    
    def is_in_cooldown(self) -> bool:
        """Vérifier si la règle est en période de cooldown"""
        if not self.last_alert:
            return False
            
        cooldown_end = self.last_alert + timedelta(minutes=self.cooldown_minutes)
        return datetime.now(timezone.utc) < cooldown_end

class AlertManager:
    """Gestionnaire principal des alertes"""
    
    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.rules: Dict[str, AlertRule] = {}
        self.subscribers: List[Callable[[Alert], None]] = []
        
        # Métriques pour le monitoring
        self.metrics_cache: Dict[str, float] = {}
        self.last_metrics_update: Optional[datetime] = None
        
        # Configurer les règles par défaut
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Configurer les règles d'alertes par défaut"""
        
        # Dérive de portfolio > 5%
        drift_rule = AlertRule(
            name="Portfolio Drift Alert",
            description="Alerte quand la dérive du portfolio dépasse 5%",
            alert_type=AlertType.PORTFOLIO_DRIFT,
            level=AlertLevel.WARNING,
            metric="portfolio_drift_pct",
            threshold_value=5.0,
            operator=">",
            check_interval_minutes=15,
            cooldown_minutes=60
        )
        self.add_rule(drift_rule)
        
        # Taux d'échec d'exécution > 20%
        execution_rule = AlertRule(
            name="Execution Failure Rate",
            description="Alerte quand le taux d'échec d'exécution dépasse 20%",
            alert_type=AlertType.EXECUTION_FAILURE,
            level=AlertLevel.ERROR,
            metric="execution_failure_rate",
            threshold_value=20.0,
            operator=">",
            check_interval_minutes=5,
            cooldown_minutes=30
        )
        self.add_rule(execution_rule)
        
        # Performance anormalement basse
        performance_rule = AlertRule(
            name="Low Performance Alert",
            description="Alerte quand la performance est anormalement basse",
            alert_type=AlertType.PERFORMANCE_ANOMALY,
            level=AlertLevel.WARNING,
            metric="portfolio_performance_24h",
            threshold_value=-10.0,
            operator="<",
            check_interval_minutes=30,
            cooldown_minutes=120
        )
        self.add_rule(performance_rule)
    
    def add_rule(self, rule: AlertRule) -> None:
        """Ajouter une règle d'alerte"""
        self.rules[rule.id] = rule
        logger.info(f"Alert rule added: {rule.name}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """Supprimer une règle d'alerte"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Alert rule removed: {rule_id}")
            return True
        return False
    
    def subscribe(self, callback: Callable[[Alert], None]) -> None:
        """S'abonner aux notifications d'alertes"""
        self.subscribers.append(callback)
    
    def create_alert(self, alert_type: AlertType, level: AlertLevel, 
                    title: str, message: str, data: Optional[Dict[str, Any]] = None,
                    source: str = "system") -> Alert:
        """Créer une nouvelle alerte"""
        
        alert = Alert(
            type=alert_type,
            level=level,
            title=title,
            message=message,
            data=data or {},
            source=source
        )
        
        # Suggestions d'actions selon le type
        alert.actions = self._get_suggested_actions(alert_type, level)
        
        self.alerts[alert.id] = alert
        
        # Notifier les abonnés
        for callback in self.subscribers:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
        
        logger.info(f"Alert created: {level.value.upper()} - {title}")
        return alert
    
    def _get_suggested_actions(self, alert_type: AlertType, level: AlertLevel) -> List[str]:
        """Obtenir les actions suggérées pour un type d'alerte"""
        
        actions = []
        
        if alert_type == AlertType.PORTFOLIO_DRIFT:
            actions = [
                "Vérifier les paramètres de rebalancement",
                "Lancer un rebalancement manuel",
                "Vérifier les données de prix"
            ]
        elif alert_type == AlertType.EXECUTION_FAILURE:
            actions = [
                "Vérifier la connectivité des exchanges",
                "Contrôler les balances disponibles",
                "Examiner les logs d'exécution"
            ]
        elif alert_type == AlertType.API_CONNECTIVITY:
            actions = [
                "Vérifier les clés API",
                "Tester la connectivité réseau",
                "Vérifier les limites de rate"
            ]
        elif alert_type == AlertType.PERFORMANCE_ANOMALY:
            actions = [
                "Analyser les mouvements de marché",
                "Vérifier la stratégie de rebalancement",
                "Examiner les dernières transactions"
            ]
        
        if level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            actions.append("Contacter l'administrateur système")
        
        return actions
    
    def check_rules(self, metrics: Dict[str, float]) -> List[Alert]:
        """Vérifier toutes les règles contre les métriques actuelles"""
        
        self.metrics_cache.update(metrics)
        self.last_metrics_update = datetime.now(timezone.utc)
        
        triggered_alerts = []
        
        for rule in self.rules.values():
            if not rule.should_check():
                continue
                
            rule.last_check = datetime.now(timezone.utc)
            
            # Vérifier si la métrique existe
            if rule.metric not in metrics:
                continue
            
            metric_value = metrics[rule.metric]
            threshold = rule.threshold_value
            
            # Évaluer la condition
            triggered = False
            if rule.operator == ">":
                triggered = metric_value > threshold
            elif rule.operator == "<":
                triggered = metric_value < threshold
            elif rule.operator == ">=":
                triggered = metric_value >= threshold
            elif rule.operator == "<=":
                triggered = metric_value <= threshold
            elif rule.operator == "==":
                triggered = metric_value == threshold
            elif rule.operator == "!=":
                triggered = metric_value != threshold
            
            # Créer l'alerte si conditions remplies
            if triggered and not rule.is_in_cooldown():
                alert = self.create_alert(
                    alert_type=rule.alert_type,
                    level=rule.level,
                    title=rule.name,
                    message=f"{rule.description}. Valeur actuelle: {metric_value:.2f}, seuil: {threshold:.2f}",
                    data={
                        "rule_id": rule.id,
                        "metric": rule.metric,
                        "value": metric_value,
                        "threshold": threshold,
                        "operator": rule.operator
                    },
                    source="rule_engine"
                )
                
                triggered_alerts.append(alert)
                rule.last_alert = datetime.now(timezone.utc)
        
        return triggered_alerts
    
    def get_active_alerts(self, level: Optional[AlertLevel] = None,
                         alert_type: Optional[AlertType] = None,
                         unresolved_only: bool = True) -> List[Alert]:
        """Obtenir les alertes actives"""
        
        alerts = list(self.alerts.values())
        
        # Filtres
        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
            
        if alert_type:
            alerts = [a for a in alerts if a.type == alert_type]
        
        # Trier par date de création (plus récent d'abord)
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        
        return alerts
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Accuser réception d'une alerte"""
        if alert_id in self.alerts:
            self.alerts[alert_id].acknowledge()
            return True
        return False
    
    def resolve_alert(self, alert_id: str, resolution_note: str = "") -> bool:
        """Résoudre une alerte"""
        if alert_id in self.alerts:
            self.alerts[alert_id].resolve(resolution_note)
            return True
        return False
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Obtenir les statistiques des alertes"""
        
        all_alerts = list(self.alerts.values())
        active_alerts = self.get_active_alerts()
        
        # Par niveau
        by_level = {}
        for level in AlertLevel:
            count = sum(1 for a in active_alerts if a.level == level)
            by_level[level.value] = count
        
        # Par type
        by_type = {}
        for alert_type in AlertType:
            count = sum(1 for a in active_alerts if a.type == alert_type)
            by_type[alert_type.value] = count
        
        # Temps de résolution moyen
        resolved_alerts = [a for a in all_alerts if a.resolved and a.resolved_at]
        avg_resolution_time = 0.0
        
        if resolved_alerts:
            total_time = sum(
                (a.resolved_at - a.created_at).total_seconds()
                for a in resolved_alerts
            )
            avg_resolution_time = total_time / len(resolved_alerts) / 60  # en minutes
        
        return {
            "total_alerts": len(all_alerts),
            "active_alerts": len(active_alerts),
            "by_level": by_level,
            "by_type": by_type,
            "avg_resolution_time_minutes": avg_resolution_time,
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules.values() if r.enabled)
        }

# Instance globale du gestionnaire d'alertes
alert_manager = AlertManager()