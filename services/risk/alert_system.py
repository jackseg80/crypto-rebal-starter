"""
Alert System - Système d'alertes intelligent

Gère la génération, le suivi et la résolution des alertes de risque.
Extrait de services/risk_management.py pour améliorer la modularité.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .models import RiskAlert, AlertSeverity, AlertCategory

logger = logging.getLogger(__name__)


@dataclass
class AlertSystem:
    """Système d'alertes intelligent avec historique et règles configurables"""

    # Configuration des seuils
    thresholds: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Historique des alertes
    alert_history: List[RiskAlert] = field(default_factory=list)
    active_alerts: Dict[str, RiskAlert] = field(default_factory=dict)

    # Paramètres système
    max_alert_history: int = 1000
    alert_cooldown_hours: int = 24

    def __post_init__(self):
        """Initialise les seuils par défaut"""
        self.thresholds = self._get_default_thresholds()

    def _get_default_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Définit les seuils par défaut pour chaque type d'alerte"""
        return {
            "var_95": {
                "medium": 0.10,    # VaR 95% > 10%
                "high": 0.15,      # VaR 95% > 15%
                "critical": 0.25   # VaR 95% > 25%
            },
            "volatility": {
                "medium": 0.60,    # Volatilité > 60%
                "high": 0.80,      # Volatilité > 80%
                "critical": 1.20   # Volatilité > 120%
            },
            "max_drawdown": {
                "medium": 0.20,    # Max DD > 20%
                "high": 0.35,      # Max DD > 35%
                "critical": 0.50   # Max DD > 50%
            },
            "current_drawdown": {
                "medium": 0.15,    # Drawdown actuel > 15%
                "high": 0.25,      # Drawdown actuel > 25%
                "critical": 0.40   # Drawdown actuel > 40%
            },
            "diversification_ratio": {
                "medium": 0.7,     # Ratio < 0.7 (faible)
                "high": 0.4        # Ratio < 0.4 (très faible)
            },
            "concentration": {
                "medium": 0.60,    # Plus de 60% dans un asset
                "high": 0.75,      # Plus de 75% dans un asset
                "critical": 0.90   # Plus de 90% dans un asset
            },
            "sharpe_ratio": {
                "medium": 0.0,     # Sharpe < 0 (négatif)
                "high": -0.5       # Sharpe < -0.5 (très négatif)
            }
        }

    def generate_alert(
        self,
        alert_type: str,
        severity: AlertSeverity,
        category: AlertCategory,
        title: str,
        message: str,
        recommendation: str,
        current_value: float,
        threshold_value: float,
        affected_assets: List[str] = None
    ) -> RiskAlert:
        """Génère une nouvelle alerte"""

        alert_id = f"{category.value}_{alert_type}_{int(datetime.now().timestamp())}"

        # Vérifier si alerte existe déjà (cooldown)
        existing_alert = self._find_existing_alert(alert_type, category)
        if existing_alert:
            # Mettre à jour l'alerte existante
            existing_alert.trigger_count += 1
            existing_alert.current_value = current_value
            existing_alert.created_at = datetime.now()
            return existing_alert

        # Créer nouvelle alerte
        alert = RiskAlert(
            id=alert_id,
            severity=severity,
            category=category,
            title=title,
            message=message,
            recommendation=recommendation,
            current_value=current_value,
            threshold_value=threshold_value,
            affected_assets=affected_assets or []
        )

        # Ajouter à l'historique et aux alertes actives
        self.alert_history.append(alert)
        self.active_alerts[alert_id] = alert

        # Nettoyer l'historique si nécessaire
        if len(self.alert_history) > self.max_alert_history:
            self.alert_history = self.alert_history[-self.max_alert_history:]

        return alert

    def _find_existing_alert(self, alert_type: str, category: AlertCategory) -> Optional[RiskAlert]:
        """Trouve une alerte existante du même type dans la période de cooldown"""

        cooldown_threshold = datetime.now() - timedelta(hours=self.alert_cooldown_hours)

        for alert in self.active_alerts.values():
            if (alert.category == category and
                alert_type in alert.id and
                alert.created_at > cooldown_threshold and
                alert.is_active):
                return alert

        return None

    def resolve_alert(self, alert_id: str, resolution_note: str = "") -> bool:
        """Résout une alerte active"""

        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.is_active = False
            alert.resolution_note = resolution_note
            alert.expires_at = datetime.now()

            # Retirer des alertes actives
            del self.active_alerts[alert_id]
            return True

        return False

    def get_active_alerts(self, severity_filter: Optional[AlertSeverity] = None) -> List[RiskAlert]:
        """Récupère les alertes actives, optionnellement filtrées par sévérité"""

        alerts = list(self.active_alerts.values())

        if severity_filter:
            alerts = [a for a in alerts if a.severity == severity_filter]

        # Trier par sévérité et date
        severity_order = {
            AlertSeverity.CRITICAL: 5,
            AlertSeverity.HIGH: 4,
            AlertSeverity.MEDIUM: 3,
            AlertSeverity.LOW: 2,
            AlertSeverity.INFO: 1
        }

        alerts.sort(key=lambda x: (severity_order[x.severity], x.created_at), reverse=True)

        return alerts

    def cleanup_expired_alerts(self):
        """Nettoie les alertes expirées"""

        now = datetime.now()
        expired_ids = []

        for alert_id, alert in self.active_alerts.items():
            if alert.expires_at and alert.expires_at < now:
                expired_ids.append(alert_id)

        for alert_id in expired_ids:
            del self.active_alerts[alert_id]


# Instance globale pour réutilisation
_global_alert_system = None


def get_alert_system() -> AlertSystem:
    """Retourne l'instance globale du système d'alertes"""
    global _global_alert_system
    if _global_alert_system is None:
        _global_alert_system = AlertSystem()
    return _global_alert_system
