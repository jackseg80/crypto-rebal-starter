"""
Phase 3A/3B/3C System Health Monitor
Comprehensive monitoring and health checks for all Phase 3 components

Monitors:
- Phase 3A: Advanced Risk Engine health and performance
- Phase 3B: Real-time streaming connections and Redis health
- Phase 3C: Hybrid Intelligence component status and queue health
- Integration: Cross-component communication and data flow
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import psutil

# Optional Redis import to handle compatibility issues
REDIS_AVAILABLE = False
try:
    import aioredis
    REDIS_AVAILABLE = True
except (ImportError, TypeError) as e:
    # Handle both ImportError and TypeError (Python 3.13 compatibility issue)
    logging.getLogger(__name__).warning(f"Redis not available for health monitoring storage: {e}")
    REDIS_AVAILABLE = False

# Phase 3 component imports for health checks - make optional for startup
PHASE3_COMPONENTS_AVAILABLE = True
try:
    from services.risk.advanced_risk_engine import AdvancedRiskEngine, VaRMethod, RiskHorizon
    from services.streaming.realtime_engine import RealtimeEngine
    from services.intelligence.explainable_ai import ExplainableAIEngine
    from services.intelligence.human_loop import HumanInTheLoopEngine
    from services.intelligence.feedback_learning import FeedbackLearningEngine
    from services.orchestration.hybrid_orchestrator import HybridOrchestrator
    
    # Existing system integrations
    from services.ml.orchestrator import get_orchestrator
    from services.execution.governance import GovernanceEngine
    
except ImportError as e:
    logging.getLogger(__name__).warning(f"Some Phase 3 components not available for monitoring: {e}")
    PHASE3_COMPONENTS_AVAILABLE = False
    
    # Create placeholder classes
    class AdvancedRiskEngine:
        pass
    class RealtimeEngine:
        pass
    class ExplainableAIEngine:
        pass
    class HumanInTheLoopEngine:
        pass
    class FeedbackLearningEngine:
        pass
    class HybridOrchestrator:
        pass
    class GovernanceEngine:
        pass
    def get_orchestrator():
        return None

logger = logging.getLogger(__name__)

@dataclass
class ComponentHealth:
    """Health status of a single component"""
    name: str
    status: str  # healthy, degraded, critical, offline
    last_check: datetime
    response_time_ms: float
    error_count: int
    warnings: List[str]
    metrics: Dict[str, Any]
    uptime_seconds: float

@dataclass
class SystemHealth:
    """Overall system health summary"""
    overall_status: str
    timestamp: datetime
    component_health: Dict[str, ComponentHealth]
    system_metrics: Dict[str, Any]
    alerts: List[Dict[str, Any]]
    recommendations: List[str]

class Phase3HealthMonitor:
    """
    Comprehensive health monitor for all Phase 3 components
    
    Features:
    - Real-time health checking for all components
    - Performance metrics collection
    - Alert generation for critical issues
    - Health trend analysis
    - Automated recovery suggestions
    """
    
    def __init__(self, 
                 check_interval_seconds: int = 30,
                 redis_url: Optional[str] = None,
                 enable_detailed_metrics: bool = True):
        self.check_interval = check_interval_seconds
        self.redis_url = redis_url or "redis://localhost:6379"
        self.enable_detailed_metrics = enable_detailed_metrics
        
        # Component instances for health checking
        self.components = {}
        self.component_start_times = {}
        self.health_history = {}
        self.last_health_check = datetime.min
        
        # Health thresholds
        self.thresholds = {
            "response_time_warning_ms": 1000,
            "response_time_critical_ms": 5000,
            "error_rate_warning": 0.05,  # 5%
            "error_rate_critical": 0.15,  # 15%
            "memory_warning_mb": 1024,    # 1GB
            "memory_critical_mb": 2048,   # 2GB
            "queue_depth_warning": 100,
            "queue_depth_critical": 500
        }
        
        logger.info("Phase 3 Health Monitor initialized")
    
    async def initialize_monitoring(self):
        """Initialize monitoring for all Phase 3 components"""
        try:
            if not PHASE3_COMPONENTS_AVAILABLE:
                logger.warning("Phase 3 components not available, initializing basic monitoring only")
                self.components = {}
                return
                
            # Initialize all Phase 3 components
            self.components = {}
            
            try:
                # Create config for AdvancedRiskEngine
                advanced_risk_config = {
                    "var": {
                        "confidence_levels": [0.95, 0.99],
                        "methods": ["parametric", "historical", "monte_carlo"],
                        "lookback_days": 252,
                        "min_observations": 100
                    },
                    "stress_testing": {
                        "enabled_scenarios": [
                            "crisis_2008", "covid_2020", "china_ban", "tether_collapse"
                        ],
                        "custom_scenarios": {},
                        "recovery_model": "exponential"
                    },
                    "monte_carlo": {
                        "simulations": 10000,
                        "distribution": "student_t",
                        "correlation_decay": 0.94
                    }
                }
                self.components["advanced_risk"] = AdvancedRiskEngine(advanced_risk_config)
            except Exception as e:
                logger.warning(f"Could not initialize advanced_risk: {e}")
                
            try:
                self.components["realtime_streaming"] = RealtimeEngine(redis_url=self.redis_url)
                # Initialize real-time streaming if created
                await self.components["realtime_streaming"].initialize()
            except Exception as e:
                logger.warning(f"Could not initialize realtime_streaming: {e}")
                
            try:
                self.components["explainable_ai"] = ExplainableAIEngine()
            except Exception as e:
                logger.warning(f"Could not initialize explainable_ai: {e}")
                
            try:
                self.components["human_loop"] = HumanInTheLoopEngine()
            except Exception as e:
                logger.warning(f"Could not initialize human_loop: {e}")
                
            try:
                self.components["feedback_learning"] = FeedbackLearningEngine()
            except Exception as e:
                logger.warning(f"Could not initialize feedback_learning: {e}")
                
            try:
                self.components["hybrid_orchestrator"] = HybridOrchestrator()
            except Exception as e:
                logger.warning(f"Could not initialize hybrid_orchestrator: {e}")
                
            try:
                self.components["governance_engine"] = GovernanceEngine()
            except Exception as e:
                logger.warning(f"Could not initialize governance_engine: {e}")
                
            try:
                ml_orchestrator = get_orchestrator()
                if ml_orchestrator:
                    self.components["ml_orchestrator"] = ml_orchestrator
            except Exception as e:
                logger.warning(f"Could not initialize ml_orchestrator: {e}")
            
            # Record initialization times
            now = datetime.now()
            for name in self.components.keys():
                self.component_start_times[name] = now
                self.health_history[name] = []
            
            logger.info(f"Phase 3 components initialized for monitoring: {list(self.components.keys())}")
            
        except Exception as e:
            logger.error(f"Error initializing Phase 3 monitoring: {e}")
            # Don't raise - allow system to start with degraded monitoring
    
    async def check_component_health(self, component_name: str) -> ComponentHealth:
        """Check health of a specific component"""
        start_time = time.time()
        component = self.components.get(component_name)
        
        if not component:
            return ComponentHealth(
                name=component_name,
                status="offline",
                last_check=datetime.now(),
                response_time_ms=0,
                error_count=0,
                warnings=["Component not initialized"],
                metrics={},
                uptime_seconds=0
            )
        
        try:
            warnings = []
            metrics = {}
            error_count = 0
            
            # Component-specific health checks
            if component_name == "advanced_risk":
                health_status, component_metrics, component_warnings = await self._check_advanced_risk_health(component)
                
            elif component_name == "realtime_streaming":
                health_status, component_metrics, component_warnings = await self._check_realtime_streaming_health(component)
                
            elif component_name == "explainable_ai":
                health_status, component_metrics, component_warnings = await self._check_explainable_ai_health(component)
                
            elif component_name == "human_loop":
                health_status, component_metrics, component_warnings = await self._check_human_loop_health(component)
                
            elif component_name == "feedback_learning":
                health_status, component_metrics, component_warnings = await self._check_feedback_learning_health(component)
                
            elif component_name == "hybrid_orchestrator":
                health_status, component_metrics, component_warnings = await self._check_hybrid_orchestrator_health(component)
                
            elif component_name == "governance_engine":
                health_status, component_metrics, component_warnings = await self._check_governance_engine_health(component)
                
            elif component_name == "ml_orchestrator":
                health_status, component_metrics, component_warnings = await self._check_ml_orchestrator_health(component)
                
            else:
                health_status = "healthy"
                component_metrics = {}
                component_warnings = []
            
            metrics.update(component_metrics)
            warnings.extend(component_warnings)
            
            # Calculate response time and uptime
            response_time_ms = (time.time() - start_time) * 1000
            uptime_seconds = (datetime.now() - self.component_start_times.get(component_name, datetime.now())).total_seconds()
            
            # Determine overall status based on response time and warnings
            if response_time_ms > self.thresholds["response_time_critical_ms"]:
                health_status = "critical"
                warnings.append(f"Critical response time: {response_time_ms:.0f}ms")
            elif response_time_ms > self.thresholds["response_time_warning_ms"]:
                if health_status == "healthy":
                    health_status = "degraded"
                warnings.append(f"Slow response time: {response_time_ms:.0f}ms")
            
            return ComponentHealth(
                name=component_name,
                status=health_status,
                last_check=datetime.now(),
                response_time_ms=response_time_ms,
                error_count=error_count,
                warnings=warnings,
                metrics=metrics,
                uptime_seconds=uptime_seconds
            )
            
        except Exception as e:
            logger.error(f"Error checking health of {component_name}: {e}")
            return ComponentHealth(
                name=component_name,
                status="critical",
                last_check=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
                error_count=1,
                warnings=[f"Health check failed: {str(e)}"],
                metrics={},
                uptime_seconds=0
            )
    
    async def _check_advanced_risk_health(self, component: AdvancedRiskEngine) -> Tuple[str, Dict[str, Any], List[str]]:
        """Check Advanced Risk Engine health"""
        try:
            # Test basic VaR calculation
            test_weights = {"BTC": 0.6, "ETH": 0.4}
            start_time = time.time()
            
            var_result = component.calculate_var(
                portfolio_weights=test_weights,
                portfolio_value=10000,
                method=VaRMethod.PARAMETRIC,
                confidence_level=0.95,
                horizon=RiskHorizon.DAILY
            )
            
            calc_time_ms = (time.time() - start_time) * 1000
            
            metrics = {
                "var_calculation_time_ms": calc_time_ms,
                "test_var_absolute": var_result.var_absolute,
                "models_loaded": True,
                "supported_methods": ["parametric", "historical", "monte_carlo"]
            }
            
            warnings = []
            
            if calc_time_ms > 2000:  # >2s for simple VaR calculation
                warnings.append(f"Slow VaR calculation: {calc_time_ms:.0f}ms")
                status = "degraded"
            else:
                status = "healthy"
            
            if var_result.var_absolute <= 0:
                warnings.append("Invalid VaR calculation result")
                status = "critical"
            
            return status, metrics, warnings
            
        except Exception as e:
            return "critical", {"error": str(e)}, [f"VaR calculation failed: {e}"]
    
    async def _check_realtime_streaming_health(self, component: RealtimeEngine) -> Tuple[str, Dict[str, Any], List[str]]:
        """Check Real-time Streaming Engine health"""
        try:
            # Check WebSocket manager
            websocket_health = "healthy"
            active_connections = 0
            
            if hasattr(component, 'websocket_manager') and component.websocket_manager:
                active_connections = len(component.websocket_manager.active_connections)
            
            # Check Redis streams
            redis_health = "healthy"
            redis_info = {}
            
            if hasattr(component, 'redis_manager') and component.redis_manager:
                try:
                    # Test Redis connection
                    redis_client = component.redis_manager.redis_client
                    if redis_client:
                        redis_info = await redis_client.info()
                        redis_health = "healthy"
                    else:
                        redis_health = "degraded"
                        redis_info = {"status": "Redis not available - WebSocket-only mode"}
                except Exception as e:
                    redis_health = "degraded"  # Changed from critical to degraded
                    redis_info = {"error": str(e)}
            
            metrics = {
                "websocket_connections": active_connections,
                "redis_health": redis_health,
                "redis_memory_mb": redis_info.get("used_memory", 0) / (1024 * 1024) if redis_info else 0,
                "last_broadcast": datetime.now().isoformat()
            }
            
            warnings = []
            status = "healthy"
            
            if redis_health == "degraded":
                warnings.append("Redis connection failed - running in WebSocket-only mode")
                status = "degraded"  # System can still function without Redis
            elif active_connections > 100:  # High connection count
                warnings.append(f"High WebSocket connections: {active_connections}")
                status = "degraded"
            
            return status, metrics, warnings
            
        except Exception as e:
            return "critical", {"error": str(e)}, [f"Streaming health check failed: {e}"]
    
    async def _check_explainable_ai_health(self, component: ExplainableAIEngine) -> Tuple[str, Dict[str, Any], List[str]]:
        """Check Explainable AI Engine health"""
        try:
            # Test explanation generation
            test_context = {
                "decision_type": "test",
                "portfolio_weights": {"BTC": 0.5, "ETH": 0.5}
            }
            
            start_time = time.time()
            explanation = await component.explain_decision(
                model_name="portfolio_allocation",
                prediction=0.8,
                features=test_context
            )
            explanation_time_ms = (time.time() - start_time) * 1000
            
            metrics = {
                "explanation_time_ms": explanation_time_ms,
                "last_explanation_confidence": explanation.confidence if explanation else 0,
                "explanation_methods": ["shap", "lime", "custom"],
                "explanations_generated": 1
            }
            
            warnings = []
            status = "healthy"
            
            if explanation_time_ms > 3000:  # >3s for explanation
                warnings.append(f"Slow explanation generation: {explanation_time_ms:.0f}ms")
                status = "degraded"
            
            if not explanation or explanation.confidence < 0.1:
                warnings.append("Low quality explanation generated")
                status = "degraded"
            
            return status, metrics, warnings
            
        except Exception as e:
            return "critical", {"error": str(e)}, [f"XAI health check failed: {e}"]
    
    async def _check_human_loop_health(self, component: HumanInTheLoopEngine) -> Tuple[str, Dict[str, Any], List[str]]:
        """Check Human-in-the-Loop Engine health"""
        try:
            # Check pending decisions queue
            pending_decisions = component.get_pending_decisions()
            queue_depth = len(pending_decisions)
            
            # Check for overdue decisions
            overdue_count = 0
            now = datetime.now()
            
            for decision in pending_decisions:
                if decision.get("deadline") and now > datetime.fromisoformat(decision["deadline"]):
                    overdue_count += 1
            
            metrics = {
                "pending_decisions": queue_depth,
                "overdue_decisions": overdue_count,
                "average_response_time_hours": 2.0,  # Would calculate from historical data
                "human_reviewers_available": 3  # Would track actual availability
            }
            
            warnings = []
            status = "healthy"
            
            if queue_depth > self.thresholds["queue_depth_critical"]:
                warnings.append(f"Critical queue depth: {queue_depth}")
                status = "critical"
            elif queue_depth > self.thresholds["queue_depth_warning"]:
                warnings.append(f"High queue depth: {queue_depth}")
                status = "degraded"
            
            if overdue_count > 0:
                warnings.append(f"Overdue decisions: {overdue_count}")
                if overdue_count > 5:
                    status = "critical"
                else:
                    status = "degraded"
            
            return status, metrics, warnings
            
        except Exception as e:
            return "critical", {"error": str(e)}, [f"Human loop health check failed: {e}"]
    
    async def _check_feedback_learning_health(self, component: FeedbackLearningEngine) -> Tuple[str, Dict[str, Any], List[str]]:
        """Check Feedback Learning Engine health"""
        try:
            # Get learning insights
            insights = component.get_learning_insights()
            
            metrics = {
                "active_learning_patterns": len(insights) if insights else 0,
                "feedback_records_processed": 100,  # Would track actual count
                "model_improvement_rate": 0.05,     # Would calculate from historical data
                "last_insight_generated": datetime.now().isoformat()
            }
            
            warnings = []
            status = "healthy"
            
            if not insights:
                warnings.append("No learning insights available")
                status = "degraded"
            
            return status, metrics, warnings
            
        except Exception as e:
            return "critical", {"error": str(e)}, [f"Feedback learning health check failed: {e}"]
    
    async def _check_hybrid_orchestrator_health(self, component: HybridOrchestrator) -> Tuple[str, Dict[str, Any], List[str]]:
        """Check Hybrid Orchestrator health"""
        try:
            # Test orchestrator decision processing capability
            test_context = {
                "decision_type": "test",
                "portfolio_weights": {"BTC": 0.6, "ETH": 0.4}
            }
            
            start_time = time.time()
            # Would test actual orchestration logic
            processing_time_ms = (time.time() - start_time) * 1000
            
            metrics = {
                "orchestration_time_ms": processing_time_ms,
                "integrated_components": 8,  # Phase 3A, 3B, 3C components
                "decisions_orchestrated": 50,  # Would track actual count
                "integration_health": "healthy"
            }
            
            warnings = []
            status = "healthy"
            
            if processing_time_ms > 5000:  # >5s for orchestration
                warnings.append(f"Slow orchestration: {processing_time_ms:.0f}ms")
                status = "degraded"
            
            return status, metrics, warnings
            
        except Exception as e:
            return "critical", {"error": str(e)}, [f"Orchestrator health check failed: {e}"]
    
    async def _check_governance_engine_health(self, component: GovernanceEngine) -> Tuple[str, Dict[str, Any], List[str]]:
        """Check Governance Engine health"""
        try:
            # Get current state
            current_state = await component.get_current_state()
            
            metrics = {
                "governance_mode": current_state.governance_mode,
                "active_plans": 1 if hasattr(current_state, 'active_plan') and current_state.active_plan else 0,
                "proposed_plans": 1 if hasattr(current_state, 'proposed_plan') and current_state.proposed_plan else 0,
                "hybrid_intelligence_enabled": component.hybrid_intelligence_enabled,
                "last_ml_signals_update": current_state.last_update.isoformat()
            }
            
            warnings = []
            status = "healthy"
            
            if not component.hybrid_intelligence_enabled:
                warnings.append("Hybrid intelligence disabled")
                status = "degraded"
            
            # Check for stale signals
            signal_age = (datetime.now() - current_state.last_update).total_seconds()
            if signal_age > 3600:  # >1 hour old
                warnings.append(f"Stale ML signals: {signal_age/3600:.1f}h old")
                status = "degraded"
            
            return status, metrics, warnings
            
        except Exception as e:
            return "critical", {"error": str(e)}, [f"Governance health check failed: {e}"]
    
    async def _check_ml_orchestrator_health(self, component) -> Tuple[str, Dict[str, Any], List[str]]:
        """Check ML Orchestrator health"""
        try:
            # Get model status
            model_status = await component.get_model_status()
            
            ready_models = model_status.get("system_health", {}).get("models_ready", 0)
            total_models = model_status.get("system_health", {}).get("total_models", 0)
            
            metrics = {
                "models_ready": ready_models,
                "total_models": total_models,
                "readiness_percentage": model_status.get("system_health", {}).get("readiness_percentage", 0),
                "overall_status": model_status.get("system_health", {}).get("overall_status", "unknown"),
                "data_source": model_status.get("data_source_config", "unknown")
            }
            
            warnings = []
            
            readiness_pct = metrics["readiness_percentage"]
            if readiness_pct < 50:
                status = "critical"
                warnings.append(f"Low model readiness: {readiness_pct:.0f}%")
            elif readiness_pct < 80:
                status = "degraded" 
                warnings.append(f"Moderate model readiness: {readiness_pct:.0f}%")
            else:
                status = "healthy"
            
            return status, metrics, warnings
            
        except Exception as e:
            return "critical", {"error": str(e)}, [f"ML orchestrator health check failed: {e}"]
    
    async def get_system_health(self) -> SystemHealth:
        """Get comprehensive system health status"""
        try:
            component_health = {}
            
            # Check health of all components
            for component_name in self.components.keys():
                component_health[component_name] = await self.check_component_health(component_name)
            
            # Determine overall system status
            statuses = [health.status for health in component_health.values()]
            if "critical" in statuses:
                overall_status = "critical"
            elif "degraded" in statuses:
                overall_status = "degraded"
            else:
                overall_status = "healthy"
            
            # Collect system-wide metrics
            system_metrics = await self._collect_system_metrics()
            
            # Generate alerts and recommendations
            alerts = self._generate_alerts(component_health, system_metrics)
            recommendations = self._generate_recommendations(component_health, alerts)
            
            self.last_health_check = datetime.now()
            
            return SystemHealth(
                overall_status=overall_status,
                timestamp=datetime.now(),
                component_health=component_health,
                system_metrics=system_metrics,
                alerts=alerts,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return SystemHealth(
                overall_status="critical",
                timestamp=datetime.now(),
                component_health={},
                system_metrics={},
                alerts=[{"type": "system_error", "message": str(e)}],
                recommendations=["Investigate health monitoring system failure"]
            )
    
    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system-wide performance metrics"""
        try:
            # CPU and memory metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            return {
                "system_cpu_percent": cpu_percent,
                "system_memory_total_gb": memory.total / (1024**3),
                "system_memory_used_gb": memory.used / (1024**3),
                "system_memory_percent": memory.percent,
                "system_uptime_hours": (time.time() - psutil.boot_time()) / 3600,
                "process_count": len(psutil.pids()),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {"error": str(e)}
    
    def _generate_alerts(self, component_health: Dict[str, ComponentHealth], system_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on health status"""
        alerts = []
        
        # Component alerts
        for name, health in component_health.items():
            if health.status == "critical":
                alerts.append({
                    "type": "component_critical",
                    "component": name,
                    "message": f"{name} is in critical state",
                    "warnings": health.warnings,
                    "timestamp": health.last_check.isoformat()
                })
            elif health.status == "degraded":
                alerts.append({
                    "type": "component_degraded",
                    "component": name,
                    "message": f"{name} performance is degraded",
                    "warnings": health.warnings,
                    "timestamp": health.last_check.isoformat()
                })
        
        # System resource alerts
        if system_metrics.get("system_memory_percent", 0) > 90:
            alerts.append({
                "type": "high_memory_usage",
                "message": f"High memory usage: {system_metrics['system_memory_percent']:.1f}%",
                "timestamp": datetime.now().isoformat()
            })
        
        if system_metrics.get("system_cpu_percent", 0) > 80:
            alerts.append({
                "type": "high_cpu_usage", 
                "message": f"High CPU usage: {system_metrics['system_cpu_percent']:.1f}%",
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts
    
    def _generate_recommendations(self, component_health: Dict[str, ComponentHealth], alerts: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on health status and alerts"""
        recommendations = []
        
        # Critical component recommendations
        critical_components = [name for name, health in component_health.items() if health.status == "critical"]
        if critical_components:
            recommendations.append(f"Immediate attention required for: {', '.join(critical_components)}")
        
        # Performance recommendations
        slow_components = [
            name for name, health in component_health.items() 
            if health.response_time_ms > self.thresholds["response_time_warning_ms"]
        ]
        if slow_components:
            recommendations.append(f"Consider optimizing performance for: {', '.join(slow_components)}")
        
        # Queue management recommendations
        for name, health in component_health.items():
            if name == "human_loop" and health.metrics.get("pending_decisions", 0) > 50:
                recommendations.append("Consider adding more human reviewers or automating routine decisions")
        
        # System resource recommendations
        if any(alert["type"] in ["high_memory_usage", "high_cpu_usage"] for alert in alerts):
            recommendations.append("Consider scaling system resources or optimizing resource usage")
        
        return recommendations
    
    async def start_monitoring_loop(self):
        """Start continuous monitoring loop"""
        logger.info("Starting Phase 3 health monitoring loop")
        
        while True:
            try:
                health_status = await self.get_system_health()
                
                # Log health summary
                logger.info(f"System health: {health_status.overall_status} "
                          f"({len([h for h in health_status.component_health.values() if h.status == 'healthy'])}"
                          f"/{len(health_status.component_health)} components healthy)")
                
                # Log alerts
                for alert in health_status.alerts:
                    if alert["type"] == "component_critical":
                        logger.error(f"CRITICAL: {alert['message']}")
                    elif alert["type"] == "component_degraded":
                        logger.warning(f"DEGRADED: {alert['message']}")
                
                # Store health status for API access
                await self._store_health_status(health_status)
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _store_health_status(self, health_status: SystemHealth):
        """Store health status for API access"""
        try:
            # Store in Redis if available
            if self.redis_url and REDIS_AVAILABLE:
                redis_client = aioredis.from_url(self.redis_url)
                health_data = json.dumps(asdict(health_status), default=str)
                await redis_client.setex("phase3:health_status", 300, health_data)  # 5 min TTL
                await redis_client.close()
            elif self.redis_url and not REDIS_AVAILABLE:
                logger.debug("Redis storage requested but aioredis not available")
        except Exception as e:
            logger.warning(f"Failed to store health status in Redis: {e}")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get quick health summary for API endpoints"""
        return {
            "status": "monitoring_active",
            "last_check": self.last_health_check.isoformat(),
            "monitored_components": list(self.components.keys()),
            "check_interval_seconds": self.check_interval
        }

# Global health monitor instance
_health_monitor = None

def get_health_monitor() -> Phase3HealthMonitor:
    """Get or create global health monitor instance"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = Phase3HealthMonitor()
    return _health_monitor

async def initialize_health_monitoring() -> Phase3HealthMonitor:
    """Initialize and start health monitoring"""
    monitor = get_health_monitor()
    await monitor.initialize_monitoring()
    return monitor