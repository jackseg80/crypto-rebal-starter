"""
Unified Alert Facade - Simplified interface for legacy systems

This module provides a simple facade over the AlertEngine that legacy systems
can use to send alerts without needing to understand the full AlertEngine API.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import asyncio
from enum import Enum

from services.alerts.alert_types import Alert, AlertType, AlertSeverity
from services.alerts.migration_adapters import MigrationManager

logger = logging.getLogger(__name__)


class UnifiedAlertFacade:
    """
    Simplified facade for sending alerts to the unified AlertEngine
    
    This provides a simple interface that legacy systems can use without
    needing to understand the full AlertEngine complexity.
    """
    
    def __init__(self, alert_engine):
        self.alert_engine = alert_engine
        self.migration_manager = MigrationManager(alert_engine)
    
    async def send_portfolio_drift_alert(self, 
                                       current_drift: float,
                                       threshold: float, 
                                       assets_affected: List[str],
                                       severity: str = "S2",
                                       additional_data: Dict[str, Any] = None) -> Optional[str]:
        """Send a portfolio drift alert"""
        try:
            severity_enum = AlertSeverity(severity)
            
            alert_data = {
                "current_drift": current_drift,
                "threshold": threshold,
                "assets_affected": assets_affected,
                "drift_pct": (current_drift / threshold) if threshold > 0 else 0,
                "source": "portfolio_monitoring"
            }
            
            if additional_data:
                alert_data.update(additional_data)
            
            suggested_action = {
                "type": "rebalance" if severity_enum == AlertSeverity.S2 else "immediate_rebalance",
                "description": f"Portfolio drift {current_drift:.2%} exceeds threshold {threshold:.2%}",
                "assets_to_rebalance": assets_affected
            }
            
            alert = self.alert_engine._create_alert(
                AlertType.PORTFOLIO_DRIFT,
                severity_enum,
                alert_data
            )
            alert.suggested_action = suggested_action
            
            if self.alert_engine.storage.store_alert(alert):
                logger.info(f"Portfolio drift alert sent: {alert.id}")
                return alert.id
            
        except Exception as e:
            logger.error(f"Failed to send portfolio drift alert: {e}")
        return None
    
    async def send_execution_failure_alert(self,
                                         failed_orders: List[Dict[str, Any]], 
                                         success_rate: float,
                                         severity: str = "S2",
                                         additional_data: Dict[str, Any] = None) -> Optional[str]:
        """Send an execution failure alert"""
        try:
            severity_enum = AlertSeverity(severity)
            
            alert_data = {
                "failed_orders": failed_orders,
                "success_rate": success_rate,
                "failure_rate": 1.0 - success_rate,
                "total_failures": len(failed_orders),
                "source": "execution_monitor"
            }
            
            if additional_data:
                alert_data.update(additional_data)
            
            suggested_action = {
                "type": "investigate_execution" if severity_enum == AlertSeverity.S2 else "halt_trading",
                "description": f"Execution success rate {success_rate:.1%} below acceptable threshold",
                "failed_count": len(failed_orders)
            }
            
            alert = self.alert_engine._create_alert(
                AlertType.EXECUTION_FAILURE,
                severity_enum,
                alert_data
            )
            alert.suggested_action = suggested_action
            
            if self.alert_engine.storage.store_alert(alert):
                logger.info(f"Execution failure alert sent: {alert.id}")
                return alert.id
                
        except Exception as e:
            logger.error(f"Failed to send execution failure alert: {e}")
        return None
    
    async def send_api_connectivity_alert(self,
                                        api_name: str,
                                        error_message: str,
                                        response_time: Optional[float] = None,
                                        severity: str = "S2",
                                        additional_data: Dict[str, Any] = None) -> Optional[str]:
        """Send an API connectivity alert"""
        try:
            severity_enum = AlertSeverity(severity)
            
            alert_data = {
                "api_name": api_name,
                "error_message": error_message,
                "response_time_ms": response_time,
                "connectivity_issue": True,
                "source": "api_monitor"
            }
            
            if additional_data:
                alert_data.update(additional_data)
            
            suggested_action = {
                "type": "retry_connection" if severity_enum == AlertSeverity.S1 else "investigate_api",
                "description": f"API connectivity issue with {api_name}: {error_message}",
                "api_name": api_name
            }
            
            alert = self.alert_engine._create_alert(
                AlertType.API_CONNECTIVITY,
                severity_enum,
                alert_data
            )
            alert.suggested_action = suggested_action
            
            if self.alert_engine.storage.store_alert(alert):
                logger.info(f"API connectivity alert sent: {alert.id}")
                return alert.id
                
        except Exception as e:
            logger.error(f"Failed to send API connectivity alert: {e}")
        return None
    
    async def send_connection_health_alert(self,
                                         exchange: str,
                                         status: str,
                                         response_time_ms: float,
                                         success_rate: float,
                                         severity: str = "S2",
                                         additional_data: Dict[str, Any] = None) -> Optional[str]:
        """Send a connection health alert"""
        try:
            severity_enum = AlertSeverity(severity)
            
            # Choose alert type based on severity and status
            if status.lower() == "offline" or success_rate < 0.1:
                alert_type = AlertType.EXCHANGE_OFFLINE
            else:
                alert_type = AlertType.CONNECTION_HEALTH
            
            alert_data = {
                "exchange": exchange,
                "status": status,
                "response_time_ms": response_time_ms,
                "success_rate": success_rate,
                "health_degraded": success_rate < 0.8 or response_time_ms > 5000,
                "source": "connection_monitor"
            }
            
            if additional_data:
                alert_data.update(additional_data)
            
            suggested_action = {
                "type": "monitor_connection" if severity_enum == AlertSeverity.S1 else "investigate_exchange",
                "description": f"Connection health degraded for {exchange}: {status}",
                "exchange": exchange,
                "response_time_ms": response_time_ms,
                "success_rate": success_rate
            }
            
            alert = self.alert_engine._create_alert(
                alert_type,
                severity_enum,
                alert_data
            )
            alert.suggested_action = suggested_action
            
            if self.alert_engine.storage.store_alert(alert):
                logger.info(f"Connection health alert sent: {alert.id}")
                return alert.id
                
        except Exception as e:
            logger.error(f"Failed to send connection health alert: {e}")
        return None
    
    async def send_performance_anomaly_alert(self,
                                           metric_name: str,
                                           current_value: float,
                                           expected_range: tuple,
                                           severity: str = "S2",
                                           additional_data: Dict[str, Any] = None) -> Optional[str]:
        """Send a performance anomaly alert"""
        try:
            severity_enum = AlertSeverity(severity)
            
            alert_data = {
                "metric_name": metric_name,
                "current_value": current_value,
                "expected_min": expected_range[0],
                "expected_max": expected_range[1],
                "deviation": max(
                    abs(current_value - expected_range[0]),
                    abs(current_value - expected_range[1])
                ),
                "source": "performance_monitor"
            }
            
            if additional_data:
                alert_data.update(additional_data)
            
            suggested_action = {
                "type": "investigate_performance",
                "description": f"Performance anomaly in {metric_name}: {current_value} outside expected range {expected_range}",
                "metric_name": metric_name
            }
            
            alert = self.alert_engine._create_alert(
                AlertType.PERFORMANCE_ANOMALY,
                severity_enum,
                alert_data
            )
            alert.suggested_action = suggested_action
            
            if self.alert_engine.storage.store_alert(alert):
                logger.info(f"Performance anomaly alert sent: {alert.id}")
                return alert.id
                
        except Exception as e:
            logger.error(f"Failed to send performance anomaly alert: {e}")
        return None
    
    async def send_risk_threshold_alert(self,
                                      metric_name: str,
                                      current_value: float,
                                      threshold: float,
                                      risk_category: str,
                                      severity: str = "S2",
                                      additional_data: Dict[str, Any] = None) -> Optional[str]:
        """Send a legacy risk threshold alert"""
        try:
            severity_enum = AlertSeverity(severity)
            
            alert_data = {
                "metric_name": metric_name,
                "current_value": current_value,
                "threshold": threshold,
                "risk_category": risk_category,
                "threshold_breach": current_value > threshold,
                "breach_magnitude": (current_value / threshold) if threshold > 0 else 0,
                "source": "risk_management_legacy"
            }
            
            if additional_data:
                alert_data.update(additional_data)
            
            suggested_action = {
                "type": "review_risk_limits" if severity_enum == AlertSeverity.S2 else "immediate_risk_action",
                "description": f"Risk threshold breached: {metric_name} = {current_value} > {threshold}",
                "metric_name": metric_name,
                "risk_category": risk_category
            }
            
            alert = self.alert_engine._create_alert(
                AlertType.RISK_THRESHOLD_LEGACY,
                severity_enum,
                alert_data
            )
            alert.suggested_action = suggested_action
            
            if self.alert_engine.storage.store_alert(alert):
                logger.info(f"Risk threshold alert sent: {alert.id}")
                return alert.id
                
        except Exception as e:
            logger.error(f"Failed to send risk threshold alert: {e}")
        return None
    
    def get_active_alerts_by_type(self, alert_type: str) -> List[Alert]:
        """Get active alerts of a specific type"""
        try:
            all_alerts = self.alert_engine.get_active_alerts()
            return [alert for alert in all_alerts if alert.alert_type.value == alert_type]
        except Exception as e:
            logger.error(f"Failed to get alerts by type {alert_type}: {e}")
            return []
    
    def get_migration_stats(self) -> Dict[str, Any]:
        """Get migration statistics"""
        return self.migration_manager.get_migration_stats()


# Singleton instance for easy access
_unified_alert_facade = None

def get_unified_alert_facade(alert_engine=None):
    """Get or create the unified alert facade singleton"""
    global _unified_alert_facade
    if _unified_alert_facade is None and alert_engine is not None:
        _unified_alert_facade = UnifiedAlertFacade(alert_engine)
    return _unified_alert_facade


# Convenience functions for legacy systems
async def send_portfolio_drift_alert(*args, **kwargs):
    """Convenience function for sending portfolio drift alerts"""
    facade = get_unified_alert_facade()
    if facade:
        return await facade.send_portfolio_drift_alert(*args, **kwargs)
    return None

async def send_execution_failure_alert(*args, **kwargs):
    """Convenience function for sending execution failure alerts"""
    facade = get_unified_alert_facade()
    if facade:
        return await facade.send_execution_failure_alert(*args, **kwargs)
    return None

async def send_api_connectivity_alert(*args, **kwargs):
    """Convenience function for sending API connectivity alerts"""
    facade = get_unified_alert_facade()
    if facade:
        return await facade.send_api_connectivity_alert(*args, **kwargs)
    return None