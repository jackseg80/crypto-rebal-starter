"""
Unified Phase 3A/3B/3C API Endpoints
Orchestrates Advanced Risk, Real-time Streaming, and Hybrid Intelligence

This module provides unified access to all Phase 3 components:
- Phase 3A: Advanced Risk Management (VaR, stress tests, Monte Carlo)
- Phase 3B: Real-time Streaming (WebSocket, Redis Streams)
- Phase 3C: Hybrid Intelligence (XAI, Human-in-the-loop, Feedback Learning)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Phase 3 component imports
from services.risk.advanced_risk_engine import AdvancedRiskEngine, VaRMethod, RiskHorizon
from services.streaming.realtime_engine import RealtimeEngine
from services.intelligence.explainable_ai import ExplainableAIEngine
from services.intelligence.human_loop import HumanInTheLoopEngine
from services.intelligence.feedback_learning import FeedbackLearningEngine
from services.orchestration.hybrid_orchestrator import HybridOrchestrator

# Existing system integration
from services.ml.orchestrator import get_orchestrator
from services.execution.governance import GovernanceEngine
from services.alerts.alert_engine import AlertEngine

# Phase 3 Health Monitoring
from services.monitoring.phase3_health_monitor import get_health_monitor, initialize_health_monitoring

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/phase3", tags=["Phase 3 Unified"])

# Pydantic models for API
class UnifiedDecisionRequest(BaseModel):
    """Request for unified Phase 3 decision processing"""
    decision_type: str = Field(..., description="Type of decision (allocation, risk_management, alert)")
    portfolio_weights: Dict[str, float] = Field(..., description="Current portfolio allocation")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    require_explanation: bool = Field(default=True, description="Generate XAI explanation")
    human_oversight: bool = Field(default=True, description="Enable human-in-the-loop when needed")
    real_time_broadcast: bool = Field(default=True, description="Broadcast decision via streaming")

class UnifiedSystemStatus(BaseModel):
    """Status of all Phase 3 components"""
    timestamp: datetime
    phase_3a_advanced_risk: Dict[str, Any]
    phase_3b_realtime_streaming: Dict[str, Any]
    phase_3c_hybrid_intelligence: Dict[str, Any]
    unified_orchestration: Dict[str, Any]
    system_health: str

class RiskAnalysisRequest(BaseModel):
    """Request for comprehensive risk analysis"""
    portfolio_weights: Dict[str, float]
    portfolio_value: float = Field(default=100000, ge=1000)
    confidence_levels: List[float] = Field(default=[0.95, 0.99])
    horizons_days: List[int] = Field(default=[1, 7, 30])
    include_stress_tests: bool = Field(default=True)
    include_monte_carlo: bool = Field(default=True)

# Global instances (initialized on startup)
_advanced_risk_engine = None
_realtime_engine = None
_explainable_ai = None
_human_loop = None
_feedback_learning = None
_hybrid_orchestrator = None
_governance_engine = None
_ml_orchestrator = None

async def get_phase3_components():
    """Initialize and get all Phase 3 components"""
    global _advanced_risk_engine, _realtime_engine, _explainable_ai, _human_loop
    global _feedback_learning, _hybrid_orchestrator, _governance_engine, _ml_orchestrator
    
    if _advanced_risk_engine is None:
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
            _advanced_risk_engine = AdvancedRiskEngine(advanced_risk_config)
            _realtime_engine = RealtimeEngine()
            _explainable_ai = ExplainableAIEngine()
            _human_loop = HumanInTheLoopEngine()
            _feedback_learning = FeedbackLearningEngine()
            _hybrid_orchestrator = HybridOrchestrator()
            _governance_engine = GovernanceEngine()
            _ml_orchestrator = get_orchestrator()
            
            # Initialize components
            await _realtime_engine.initialize()
            
            logger.info("All Phase 3 components initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Phase 3 components: {e}")
            raise HTTPException(status_code=500, detail="Phase 3 components initialization failed")
    
    return {
        "advanced_risk": _advanced_risk_engine,
        "realtime": _realtime_engine, 
        "explainable_ai": _explainable_ai,
        "human_loop": _human_loop,
        "feedback_learning": _feedback_learning,
        "hybrid_orchestrator": _hybrid_orchestrator,
        "governance": _governance_engine,
        "ml_orchestrator": _ml_orchestrator
    }

@router.get("/status", response_model=UnifiedSystemStatus)
async def get_unified_system_status():
    """Get comprehensive status of all Phase 3 components"""
    try:
        components = await get_phase3_components()
        
        status = UnifiedSystemStatus(
            timestamp=datetime.now(),
            phase_3a_advanced_risk={
                "status": "active" if components["advanced_risk"] else "inactive",
                "risk_models_loaded": True,
                "last_calculation": datetime.now().isoformat(),
                "supported_methods": ["parametric", "historical", "monte_carlo"]
            },
            phase_3b_realtime_streaming={
                "status": "active" if components["realtime"] else "inactive",
                "websocket_connections": getattr(components["realtime"], 'active_connections', 0),
                "redis_streams_active": True,
                "last_broadcast": datetime.now().isoformat()
            },
            phase_3c_hybrid_intelligence={
                "status": "active",
                "explainable_ai_ready": bool(components["explainable_ai"]),
                "human_loop_active": bool(components["human_loop"]),
                "feedback_learning_enabled": bool(components["feedback_learning"]),
                "decisions_processed": 0  # Would track actual count
            },
            unified_orchestration={
                "orchestrator_status": "active",
                "integration_health": "healthy",
                "last_decision_processed": datetime.now().isoformat()
            },
            system_health="healthy"
        )
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting unified system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/decision/process")
async def process_unified_decision(request: UnifiedDecisionRequest, background_tasks: BackgroundTasks):
    """Process a decision using all Phase 3 components in orchestrated fashion"""
    try:
        components = await get_phase3_components()
        
        decision_id = f"decision_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create decision context for hybrid orchestrator
        decision_context = {
            "decision_id": decision_id,
            "decision_type": request.decision_type,
            "portfolio_weights": request.portfolio_weights,
            "context": request.context,
            "timestamp": datetime.now().isoformat(),
            "require_explanation": request.require_explanation,
            "human_oversight": request.human_oversight,
            "real_time_broadcast": request.real_time_broadcast
        }
        
        # Process through hybrid orchestrator (Phase 3A/3B/3C integration)
        orchestrated_result = await components["hybrid_orchestrator"].process_hybrid_decision(
            decision_context=decision_context,
            ml_predictions=await components["ml_orchestrator"].get_unified_predictions(),
            governance_state=await components["governance"].get_current_state()
        )
        
        # Real-time broadcasting if enabled
        if request.real_time_broadcast and components["realtime"]:
            background_tasks.add_task(
                _broadcast_decision_result,
                components["realtime"],
                decision_id,
                orchestrated_result
            )
        
        return {
            "decision_id": decision_id,
            "status": "processed",
            "result": orchestrated_result,
            "timestamp": datetime.now().isoformat(),
            "components_used": ["phase_3a", "phase_3b", "phase_3c"],
            "next_steps": orchestrated_result.get("recommendations", [])
        }
        
    except Exception as e:
        logger.error(f"Error processing unified decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risk/comprehensive-analysis")
async def comprehensive_risk_analysis(request: RiskAnalysisRequest):
    """Perform comprehensive risk analysis using Phase 3A Advanced Risk Engine"""
    try:
        components = await get_phase3_components()
        risk_engine = components["advanced_risk"]
        
        if not risk_engine:
            raise HTTPException(status_code=503, detail="Advanced Risk Engine not available")
        
        portfolio_value = request.portfolio_value
        results = {
            "analysis_id": f"risk_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "portfolio_value": portfolio_value,
            "var_analysis": {},
            "stress_tests": {},
            "monte_carlo": {},
            "risk_summary": {}
        }
        
        # VaR calculations for different methods and horizons
        for confidence_level in request.confidence_levels:
            for horizon_days in request.horizons_days:
                horizon = RiskHorizon.DAILY if horizon_days == 1 else RiskHorizon.WEEKLY if horizon_days <= 7 else RiskHorizon.MONTHLY
                
                # Parametric VaR
                var_param = risk_engine.calculate_var(
                    portfolio_weights=request.portfolio_weights,
                    portfolio_value=portfolio_value,
                    method=VaRMethod.PARAMETRIC,
                    confidence_level=confidence_level,
                    horizon=horizon
                )
                
                # Historical VaR
                var_hist = risk_engine.calculate_var(
                    portfolio_weights=request.portfolio_weights,
                    portfolio_value=portfolio_value,
                    method=VaRMethod.HISTORICAL,
                    confidence_level=confidence_level,
                    horizon=horizon
                )
                
                key = f"{int(confidence_level*100)}%_{horizon_days}d"
                results["var_analysis"][key] = {
                    "parametric_var": var_param.var_absolute,
                    "historical_var": var_hist.var_absolute,
                    "cvar_absolute_param": var_param.cvar_absolute,
                    "cvar_absolute_hist": var_hist.cvar_absolute,
                    "method_comparison": {
                        "ratio": var_hist.var_absolute / max(var_param.var_absolute, 0.001),
                        "preferred": "historical" if var_hist.var_absolute > var_param.var_absolute * 1.1 else "parametric"
                    }
                }
        
        # Stress tests
        if request.include_stress_tests:
            stress_scenarios = ["covid_2020", "crypto_winter_2022", "china_ban_2021", "fed_tightening_2022"]
            
            for scenario in stress_scenarios:
                try:
                    stress_result = await risk_engine.run_stress_test(
                        portfolio_weights=request.portfolio_weights,
                        portfolio_value=portfolio_value,
                        scenario_name=scenario
                    )
                    
                    results["stress_tests"][scenario] = {
                        "portfolio_loss": stress_result.portfolio_loss,
                        "loss_percentage": stress_result.loss_percentage,
                        "worst_affected_assets": dict(list(stress_result.asset_impacts.items())[:3]),
                        "recovery_days": stress_result.recovery_estimate_days
                    }
                    
                except Exception as e:
                    results["stress_tests"][scenario] = {"error": str(e)}
        
        # Monte Carlo simulation
        if request.include_monte_carlo:
            try:
                mc_result = await risk_engine.run_monte_carlo_simulation(
                    portfolio_weights=request.portfolio_weights,
                    portfolio_value=portfolio_value,
                    days=max(request.horizons_days),
                    simulations=10000,
                    confidence_level=request.confidence_levels[0]
                )
                
                results["monte_carlo"] = {
                    "var_absolute": mc_result.var_absolute,
                    "expected_return": mc_result.expected_return,
                    "volatility": mc_result.volatility,
                    "skewness": mc_result.skewness,
                    "kurtosis": mc_result.kurtosis,
                    "simulations": mc_result.simulations,
                    "tail_risk": mc_result.tail_risk_metrics
                }
                
            except Exception as e:
                results["monte_carlo"] = {"error": str(e)}
        
        # Risk summary and recommendations
        max_var = max([
            data.get("historical_var", 0) 
            for data in results["var_analysis"].values()
        ])
        
        worst_stress_loss = max([
            data.get("loss_percentage", 0) 
            for data in results["stress_tests"].values() 
            if isinstance(data, dict) and "loss_percentage" in data
        ], default=0)
        
        if max_var > 0.1 or worst_stress_loss > 0.4:
            risk_level = "high"
            recommendation = "Consider reducing position sizes and increasing diversification"
        elif max_var > 0.05 or worst_stress_loss > 0.2:
            risk_level = "moderate"
            recommendation = "Monitor closely and consider hedging strategies"
        else:
            risk_level = "low"
            recommendation = "Risk levels appear manageable"
        
        results["risk_summary"] = {
            "overall_risk_level": risk_level,
            "max_daily_var_95": max_var,
            "worst_stress_scenario_loss": worst_stress_loss,
            "recommendation": recommendation,
            "confidence": 0.85
        }
        
        return results
        
    except Exception as e:
        logger.error(f"Error in comprehensive risk analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/streaming/active-connections")
async def get_active_streaming_connections():
    """Get information about active real-time streaming connections"""
    try:
        components = await get_phase3_components()
        realtime_engine = components["realtime"]
        
        if not realtime_engine:
            return {"active_connections": 0, "status": "inactive"}
        
        connections_info = await realtime_engine.get_connection_status()
        
        return {
            "active_connections": connections_info.get("websocket_connections", 0),
            "redis_streams": connections_info.get("redis_streams", []),
            "last_activity": connections_info.get("last_activity", "never"),
            "status": "active" if connections_info.get("websocket_connections", 0) > 0 else "standby"
        }
        
    except Exception as e:
        logger.error(f"Error getting streaming connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/intelligence/human-decisions")
async def get_pending_human_decisions():
    """Get pending human-in-the-loop decisions"""
    try:
        components = await get_phase3_components()
        human_loop = components["human_loop"]
        
        if not human_loop:
            return {"pending_decisions": [], "status": "inactive"}
        
        pending_decisions = human_loop.get_pending_decisions()
        
        return {
            "pending_decisions": pending_decisions,
            "count": len(pending_decisions),
            "status": "active"
        }
        
    except Exception as e:
        logger.error(f"Error getting pending human decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/intelligence/submit-human-feedback")
async def submit_human_feedback(
    decision_id: str = Query(..., description="Decision ID"),
    approved: bool = Query(..., description="Human approval decision"),
    feedback: Optional[str] = Query(None, description="Optional feedback text"),
    confidence: float = Query(0.8, ge=0.0, le=1.0, description="Human confidence level")
):
    """Submit human feedback for a pending decision"""
    try:
        components = await get_phase3_components()
        human_loop = components["human_loop"]
        feedback_learning = components["feedback_learning"]
        
        if not human_loop:
            raise HTTPException(status_code=503, detail="Human-in-the-loop engine not available")
        
        # Submit human decision
        result = await human_loop.submit_human_decision(
            decision_id=decision_id,
            approved=approved,
            feedback=feedback,
            confidence=confidence
        )
        
        # Record for feedback learning
        if feedback_learning:
            await feedback_learning.record_human_feedback(
                decision_id=decision_id,
                feedback_type="approval",
                feedback_data={
                    "approved": approved,
                    "feedback": feedback,
                    "confidence": confidence,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        return {
            "status": "submitted",
            "decision_id": decision_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error submitting human feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/learning/insights")
async def get_learning_insights():
    """Get insights from feedback learning system"""
    try:
        components = await get_phase3_components()
        feedback_learning = components["feedback_learning"]
        
        if not feedback_learning:
            return {"insights": [], "status": "inactive"}
        
        insights = feedback_learning.get_learning_insights()
        
        return {
            "insights": insights,
            "generated_at": datetime.now().isoformat(),
            "status": "active"
        }
        
    except Exception as e:
        logger.error(f"Error getting learning insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/orchestrate/full-workflow") 
async def orchestrate_full_workflow(
    portfolio_weights: Dict[str, float],
    decision_context: Dict[str, Any] = {},
    background_tasks: BackgroundTasks = None
):
    """Execute complete Phase 3A/3B/3C workflow with all components"""
    try:
        components = await get_phase3_components()
        
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 1. Phase 3A: Advanced Risk Analysis
        risk_analysis = components["advanced_risk"].calculate_var(
            portfolio_weights=portfolio_weights,
            portfolio_value=100000,
            method=VaRMethod.HISTORICAL,
            confidence_level=0.95,
            horizon=RiskHorizon.DAILY
        )
        
        # 2. Phase 3C: Explainable AI Analysis
        explanation = await components["explainable_ai"].explain_decision(
            decision_type="portfolio_rebalancing",
            decision_context={
                "portfolio_weights": portfolio_weights,
                "risk_analysis": {
                    "var_absolute": risk_analysis.var_absolute,
                    "cvar_absolute": risk_analysis.cvar_absolute
                }
            },
            model_predictions=await components["ml_orchestrator"].get_unified_predictions()
        )
        
        # 3. Phase 3C: Human oversight assessment
        requires_human_review = (
            risk_analysis.var_absolute > 0.05 or  # >5% daily VaR
            explanation.confidence_score < 0.7    # Low AI confidence
        )
        
        # 4. Phase 3C: Human-in-the-loop if needed
        human_decision = None
        if requires_human_review:
            human_decision = await components["human_loop"].request_human_decision(
                decision_request={
                    "workflow_id": workflow_id,
                    "risk_var": risk_analysis.var_absolute,
                    "ai_confidence": explanation.confidence_score,
                    "portfolio_changes": portfolio_weights
                },
                urgency="medium"
            )
        
        # 5. Phase 3B: Real-time broadcasting
        workflow_result = {
            "workflow_id": workflow_id,
            "risk_analysis": {
                "var_absolute": risk_analysis.var_absolute,
                "cvar_absolute": risk_analysis.cvar_absolute,
                "risk_level": "high" if risk_analysis.var_absolute > 0.05 else "moderate"
            },
            "ai_explanation": {
                "confidence": explanation.confidence_score,
                "key_factors": [f.feature_name for f in explanation.feature_contributions[:3]],
                "explanation": explanation.explanation_text
            },
            "human_oversight": {
                "required": requires_human_review,
                "status": "pending" if human_decision and not human_decision.get("completed") else "completed"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        if components["realtime"] and background_tasks:
            background_tasks.add_task(
                _broadcast_workflow_result,
                components["realtime"],
                workflow_id,
                workflow_result
            )
        
        # 6. Phase 3C: Record for feedback learning
        if components["feedback_learning"]:
            background_tasks.add_task(
                _record_workflow_feedback,
                components["feedback_learning"],
                workflow_id,
                workflow_result
            )
        
        return {
            "status": "completed",
            "workflow_result": workflow_result,
            "next_actions": [
                "Monitor portfolio performance",
                "Review risk metrics daily",
                "Update allocations if VaR exceeds threshold"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error orchestrating full workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task functions
async def _broadcast_decision_result(realtime_engine, decision_id: str, result: Dict[str, Any]):
    """Broadcast decision result via real-time streaming"""
    try:
        await realtime_engine.broadcast_event(
            event_type="decision_processed",
            data={
                "decision_id": decision_id,
                "result": result,
                "timestamp": datetime.now().isoformat()
            },
            stream_name="decisions"
        )
    except Exception as e:
        logger.error(f"Error broadcasting decision result: {e}")

async def _broadcast_workflow_result(realtime_engine, workflow_id: str, result: Dict[str, Any]):
    """Broadcast workflow result via real-time streaming"""
    try:
        await realtime_engine.broadcast_event(
            event_type="workflow_completed",
            data={
                "workflow_id": workflow_id,
                "result": result,
                "timestamp": datetime.now().isoformat()
            },
            stream_name="workflows"
        )
    except Exception as e:
        logger.error(f"Error broadcasting workflow result: {e}")

async def _record_workflow_feedback(feedback_learning, workflow_id: str, result: Dict[str, Any]):
    """Record workflow result for feedback learning"""
    try:
        await feedback_learning.record_decision_outcome(
            decision_id=workflow_id,
            outcome="completed",
            feedback_data={
                "workflow_result": result,
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Error recording workflow feedback: {e}")

@router.get("/health/comprehensive")
async def get_comprehensive_health_status():
    """Get comprehensive health status of all Phase 3 components"""
    try:
        health_monitor = get_health_monitor()
        
        # Initialize monitoring if not already done
        if not hasattr(health_monitor, 'components') or not health_monitor.components:
            await health_monitor.initialize_monitoring()
        
        health_status = await health_monitor.get_system_health()
        
        return {
            "overall_status": health_status.overall_status,
            "timestamp": health_status.timestamp.isoformat(),
            "components": {
                name: {
                    "status": health.status,
                    "response_time_ms": health.response_time_ms,
                    "uptime_seconds": health.uptime_seconds,
                    "warnings": health.warnings,
                    "key_metrics": health.metrics
                }
                for name, health in health_status.component_health.items()
            },
            "system_metrics": health_status.system_metrics,
            "alerts": health_status.alerts,
            "recommendations": health_status.recommendations,
            "summary": {
                "healthy_components": len([h for h in health_status.component_health.values() if h.status == "healthy"]),
                "total_components": len(health_status.component_health),
                "critical_issues": len([a for a in health_status.alerts if a.get("type") == "component_critical"]),
                "degraded_components": len([h for h in health_status.component_health.values() if h.status == "degraded"])
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting comprehensive health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health/component/{component_name}")
async def get_component_health(component_name: str):
    """Get detailed health status of a specific Phase 3 component"""
    try:
        health_monitor = get_health_monitor()
        
        if not hasattr(health_monitor, 'components') or not health_monitor.components:
            await health_monitor.initialize_monitoring()
        
        if component_name not in health_monitor.components:
            available_components = list(health_monitor.components.keys())
            raise HTTPException(
                status_code=404, 
                detail=f"Component '{component_name}' not found. Available: {available_components}"
            )
        
        component_health = await health_monitor.check_component_health(component_name)
        
        return {
            "component": component_name,
            "status": component_health.status,
            "last_check": component_health.last_check.isoformat(),
            "response_time_ms": component_health.response_time_ms,
            "uptime_seconds": component_health.uptime_seconds,
            "error_count": component_health.error_count,
            "warnings": component_health.warnings,
            "detailed_metrics": component_health.metrics,
            "health_trend": "stable"  # Would calculate from historical data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting component health for {component_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health/alerts")
async def get_active_health_alerts():
    """Get active health alerts for all Phase 3 components"""
    try:
        health_monitor = get_health_monitor()
        
        if not hasattr(health_monitor, 'components') or not health_monitor.components:
            await health_monitor.initialize_monitoring()
        
        health_status = await health_monitor.get_system_health()
        
        # Categorize alerts
        critical_alerts = [a for a in health_status.alerts if "critical" in a.get("type", "")]
        warning_alerts = [a for a in health_status.alerts if "degraded" in a.get("type", "") or "high_" in a.get("type", "")]
        info_alerts = [a for a in health_status.alerts if a not in critical_alerts and a not in warning_alerts]
        
        return {
            "alert_summary": {
                "total_alerts": len(health_status.alerts),
                "critical": len(critical_alerts),
                "warning": len(warning_alerts),
                "info": len(info_alerts)
            },
            "alerts": {
                "critical": critical_alerts,
                "warning": warning_alerts,
                "info": info_alerts
            },
            "recommendations": health_status.recommendations,
            "last_updated": health_status.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting health alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/health/initialize-monitoring")
async def initialize_phase3_monitoring():
    """Initialize comprehensive Phase 3 health monitoring"""
    try:
        health_monitor = await initialize_health_monitoring()
        
        return {
            "status": "initialized",
            "monitoring_active": True,
            "components_monitored": list(health_monitor.components.keys()),
            "check_interval_seconds": health_monitor.check_interval,
            "monitoring_started": datetime.now().isoformat(),
            "message": "Phase 3 health monitoring initialized successfully"
        }
        
    except Exception as e:
        logger.error(f"Error initializing Phase 3 monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))