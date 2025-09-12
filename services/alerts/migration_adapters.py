"""
Alert System Migration Adapters

These adapters help transition from legacy alert systems to the unified AlertEngine.
They provide translation between old alert formats and the new Alert format.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import logging

from services.alerts.alert_types import Alert, AlertType, AlertSeverity

logger = logging.getLogger(__name__)


class RiskManagementAdapter:
    """Adapter for services/risk_management.py RiskAlert system"""
    
    @staticmethod
    def convert_risk_alert_to_alert(risk_alert, alert_engine) -> Optional[Alert]:
        """Convert a RiskAlert to unified Alert format"""
        try:
            # Map old severity to new severity
            severity_mapping = {
                "info": AlertSeverity.S1,
                "low": AlertSeverity.S1, 
                "medium": AlertSeverity.S2,
                "high": AlertSeverity.S2,
                "critical": AlertSeverity.S3,
                "very_high": AlertSeverity.S3
            }
            
            # Map old category to new alert type
            category_mapping = {
                "risk_threshold": AlertType.RISK_THRESHOLD_LEGACY,
                "correlation": AlertType.CORR_HIGH,
                "concentration": AlertType.RISK_CONCENTRATION,
                "market_stress": AlertType.VAR_BREACH,
                "performance": AlertType.PERFORMANCE_ANOMALY
            }
            
            alert_type = category_mapping.get(risk_alert.category.value, AlertType.RISK_THRESHOLD_LEGACY)
            severity = severity_mapping.get(risk_alert.severity.value, AlertSeverity.S2)
            
            alert_data = {
                "legacy_source": "risk_management",
                "original_category": risk_alert.category.value,
                "original_severity": risk_alert.severity.value,
                "risk_score": getattr(risk_alert, 'risk_score', 0.0),
                "threshold_value": getattr(risk_alert, 'threshold_value', 0.0),
                "actual_value": getattr(risk_alert, 'actual_value', 0.0),
                "metric_name": getattr(risk_alert, 'metric_name', "unknown")
            }
            
            suggested_action = {
                "type": "monitor" if severity == AlertSeverity.S1 else "policy_change" if severity == AlertSeverity.S2 else "system_freeze",
                "description": f"Migrated from risk_management: {risk_alert.title}",
                "legacy_actions": getattr(risk_alert, 'recommended_actions', [])
            }
            
            alert = Alert(
                id=f"MIGR-{uuid.uuid4().hex[:8]}",
                alert_type=alert_type,
                severity=severity,
                created_at=getattr(risk_alert, 'timestamp', datetime.now()),
                data=alert_data,
                suggested_action=suggested_action
            )
            
            logger.info(f"Converted RiskAlert {risk_alert.category.value} to unified Alert {alert.id}")
            return alert
            
        except Exception as e:
            logger.error(f"Failed to convert RiskAlert: {e}")
            return None


class NotificationAdapter:
    """Adapter for services/notifications/alert_manager.py Alert system"""
    
    @staticmethod 
    def convert_notification_alert_to_alert(notification_alert, alert_engine) -> Optional[Alert]:
        """Convert a notification Alert to unified Alert format"""
        try:
            # Map old AlertLevel to new AlertSeverity
            level_mapping = {
                "info": AlertSeverity.S1,
                "warning": AlertSeverity.S2,
                "error": AlertSeverity.S2,
                "critical": AlertSeverity.S3
            }
            
            # Map old AlertType to new AlertType
            type_mapping = {
                "portfolio_drift": AlertType.PORTFOLIO_DRIFT,
                "execution_failure": AlertType.EXECUTION_FAILURE,
                "performance_anomaly": AlertType.PERFORMANCE_ANOMALY,
                "api_connectivity": AlertType.API_CONNECTIVITY,
                "threshold_breach": AlertType.RISK_THRESHOLD_LEGACY,
                "system_error": AlertType.API_CONNECTIVITY
            }
            
            alert_type = type_mapping.get(notification_alert.type.value, AlertType.API_CONNECTIVITY)
            severity = level_mapping.get(notification_alert.level.value, AlertSeverity.S2)
            
            alert_data = {
                "legacy_source": "notification_manager",
                "original_type": notification_alert.type.value,
                "original_level": notification_alert.level.value,
                "title": notification_alert.title,
                "message": notification_alert.message,
                "source": notification_alert.source,
                "actions": notification_alert.actions,
                "was_acknowledged": notification_alert.acknowledged,
                "was_resolved": notification_alert.resolved
            }
            
            # Copy additional data if present
            if hasattr(notification_alert, 'data'):
                alert_data.update(notification_alert.data)
            
            suggested_action = {
                "type": "acknowledge_only" if severity == AlertSeverity.S1 else "investigate",
                "description": f"Migrated from notification_manager: {notification_alert.title}",
                "legacy_actions": notification_alert.actions
            }
            
            alert = Alert(
                id=f"NOTIF-{uuid.uuid4().hex[:8]}",
                alert_type=alert_type,
                severity=severity,
                created_at=notification_alert.created_at,
                data=alert_data,
                suggested_action=suggested_action
            )
            
            # Preserve acknowledgment state
            if notification_alert.acknowledged:
                alert.acknowledged_at = notification_alert.updated_at
                alert.acknowledged_by = "legacy_migration"
            
            logger.info(f"Converted notification Alert {notification_alert.type.value} to unified Alert {alert.id}")
            return alert
            
        except Exception as e:
            logger.error(f"Failed to convert notification Alert: {e}")
            return None


class ConnectionAdapter:
    """Adapter for services/monitoring/connection_monitor.py Alert system"""
    
    @staticmethod
    def convert_connection_alert_to_alert(connection_alert, alert_engine) -> Optional[Alert]:
        """Convert a connection monitoring Alert to unified Alert format"""
        try:
            # Map connection AlertLevel to new AlertSeverity
            level_mapping = {
                "info": AlertSeverity.S1,
                "warning": AlertSeverity.S2, 
                "critical": AlertSeverity.S3
            }
            
            # Determine alert type based on message content
            message_lower = connection_alert.message.lower()
            if "offline" in message_lower or "disconnected" in message_lower:
                alert_type = AlertType.EXCHANGE_OFFLINE
            else:
                alert_type = AlertType.CONNECTION_HEALTH
                
            severity = level_mapping.get(connection_alert.level.value, AlertSeverity.S2)
            
            alert_data = {
                "legacy_source": "connection_monitor",
                "exchange": connection_alert.exchange,
                "original_level": connection_alert.level.value,
                "connection_message": connection_alert.message,
                "was_resolved": connection_alert.resolved,
                "resolution_time": connection_alert.resolution_time
            }
            
            suggested_action = {
                "type": "monitor" if severity == AlertSeverity.S1 else "investigate_connection",
                "description": f"Connection issue on {connection_alert.exchange}: {connection_alert.message}",
                "exchange": connection_alert.exchange
            }
            
            alert = Alert(
                id=f"CONN-{uuid.uuid4().hex[:8]}",
                alert_type=alert_type,
                severity=severity,
                created_at=datetime.fromisoformat(connection_alert.timestamp.replace('Z', '+00:00')),
                data=alert_data,
                suggested_action=suggested_action
            )
            
            logger.info(f"Converted connection Alert for {connection_alert.exchange} to unified Alert {alert.id}")
            return alert
            
        except Exception as e:
            logger.error(f"Failed to convert connection Alert: {e}")
            return None


class MigrationManager:
    """Manages the migration from legacy alert systems to unified AlertEngine"""
    
    def __init__(self, alert_engine):
        self.alert_engine = alert_engine
        self.adapters = {
            'risk_management': RiskManagementAdapter(),
            'notification_manager': NotificationAdapter(),
            'connection_monitor': ConnectionAdapter()
        }
    
    async def migrate_risk_alert(self, risk_alert):
        """Migrate a RiskAlert to unified AlertEngine"""
        alert = self.adapters['risk_management'].convert_risk_alert_to_alert(risk_alert, self.alert_engine)
        if alert:
            stored = self.alert_engine.storage.store_alert(alert)
            if stored:
                logger.info(f"Successfully migrated RiskAlert to unified Alert {alert.id}")
                return alert
        return None
    
    async def migrate_notification_alert(self, notification_alert):
        """Migrate a notification Alert to unified AlertEngine"""
        alert = self.adapters['notification_manager'].convert_notification_alert_to_alert(notification_alert, self.alert_engine)
        if alert:
            stored = self.alert_engine.storage.store_alert(alert)
            if stored:
                logger.info(f"Successfully migrated notification Alert to unified Alert {alert.id}")
                return alert
        return None
    
    async def migrate_connection_alert(self, connection_alert):
        """Migrate a connection Alert to unified AlertEngine"""
        alert = self.adapters['connection_monitor'].convert_connection_alert_to_alert(connection_alert, self.alert_engine)
        if alert:
            stored = self.alert_engine.storage.store_alert(alert)
            if stored:
                logger.info(f"Successfully migrated connection Alert to unified Alert {alert.id}")
                return alert
        return None
    
    def get_migration_stats(self) -> Dict[str, Any]:
        """Get statistics about the migration process"""
        # This would track migration counts, success rates, etc.
        return {
            "adapters_available": list(self.adapters.keys()),
            "migration_active": True,
            "timestamp": datetime.now().isoformat()
        }