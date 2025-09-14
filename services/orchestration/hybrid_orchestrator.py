"""
Unified Orchestrator for Phase 3A/3B/3C Integration
Orchestrates Advanced Risk, Real-time Streaming, and Hybrid Intelligence systems
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from ..intelligence.explainable_ai import get_explainable_ai_engine, ExplainableAIEngine
from ..intelligence.human_loop import get_human_loop_engine, HumanInTheLoopEngine, UrgencyLevel
from ..intelligence.feedback_learning import get_feedback_learning_engine, FeedbackLearningEngine
from ..streaming.realtime_engine import get_realtime_engine, RealtimeEngine
from ..alerts.realtime_integration import get_alert_broadcaster

log = logging.getLogger(__name__)


@dataclass
class HybridDecisionContext:
    """Context complet pour une décision hybride"""
    decision_id: str
    decision_type: str
    original_ml_decision: Any
    confidence_score: float
    risk_level: float
    
    # Données de marché et portfolio
    market_data: Dict[str, Any]
    portfolio_data: Dict[str, Any]
    
    # Métriques Phase 3A (Advanced Risk)
    var_metrics: Optional[Dict[str, Any]] = None
    stress_test_results: Optional[Dict[str, Any]] = None
    monte_carlo_results: Optional[Dict[str, Any]] = None
    
    # État de streaming Phase 3B
    streaming_enabled: bool = False
    real_time_alerts: List[Dict[str, Any]] = None
    
    # Intelligence hybride Phase 3C
    explanation: Optional[Dict[str, Any]] = None
    human_intervention_required: bool = False
    human_decision: Optional[Any] = None
    learning_insights: List[Dict[str, Any]] = None


class HybridOrchestrator:
    """
    Orchestrateur principal pour l'intelligence hybride
    Coordonne Phases 3A, 3B, 3C avec le Decision Engine existant
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Engines Phase 3C
        self.xai_engine: Optional[ExplainableAIEngine] = None
        self.human_loop_engine: Optional[HumanInTheLoopEngine] = None
        self.learning_engine: Optional[FeedbackLearningEngine] = None
        
        # Engine Phase 3B
        self.realtime_engine: Optional[RealtimeEngine] = None
        
        # Phase 3A integration (via AlertEngine)
        self.advanced_risk_enabled = self.config.get("advanced_risk_enabled", True)
        
        # Configuration de l'orchestrateur
        self.orchestration_config = self.config.get("orchestration", {
            "auto_explain_decisions": True,
            "human_intervention_threshold": 0.7,  # Risque > 70%
            "real_time_broadcasting": True,
            "learning_feedback_enabled": True,
            "risk_analysis_enabled": True
        })
        
        self.initialized = False
        self.running = False
        self.orchestration_task: Optional[asyncio.Task] = None
        
        # Métriques de performance
        self.metrics = {
            "decisions_processed": 0,
            "explanations_generated": 0,
            "human_interventions_triggered": 0,
            "real_time_events_broadcasted": 0,
            "learning_insights_generated": 0,
            "start_time": None
        }
        
        log.info("HybridOrchestrator initialized")
    
    async def initialize(self):
        """Initialiser tous les composants de l'orchestrateur"""
        if self.initialized:
            return
        
        try:
            # Initialiser Phase 3C (Intelligence Hybride)
            if self.orchestration_config.get("auto_explain_decisions", True):
                self.xai_engine = await get_explainable_ai_engine()
                log.info("XAI Engine initialized")
            
            if self.orchestration_config.get("human_intervention_threshold", 0) < 1.0:
                self.human_loop_engine = await get_human_loop_engine()
                log.info("Human-in-the-loop Engine initialized")
            
            if self.orchestration_config.get("learning_feedback_enabled", True):
                self.learning_engine = await get_feedback_learning_engine()
                log.info("Feedback Learning Engine initialized")
            
            # Initialiser Phase 3B (Real-time Streaming)
            if self.orchestration_config.get("real_time_broadcasting", True):
                self.realtime_engine = await get_realtime_engine()
                log.info("Real-time Engine initialized")
            
            self.initialized = True
            self.metrics["start_time"] = datetime.now()
            
            log.info("HybridOrchestrator fully initialized")
            
        except Exception as e:
            log.error(f"Failed to initialize HybridOrchestrator: {e}")
            raise
    
    async def start(self):
        """Démarrer l'orchestrateur"""
        if not self.initialized:
            await self.initialize()
        
        if self.running:
            return
        
        self.running = True
        
        # Démarrer la tâche d'orchestration en arrière-plan
        self.orchestration_task = asyncio.create_task(self._orchestration_loop())
        
        log.info("HybridOrchestrator started")
    
    async def stop(self):
        """Arrêter l'orchestrateur"""
        if not self.running:
            return
        
        self.running = False
        
        if self.orchestration_task:
            self.orchestration_task.cancel()
            try:
                await self.orchestration_task
            except asyncio.CancelledError:
                pass
        
        log.info("HybridOrchestrator stopped")
    
    async def process_hybrid_decision(self, 
                                    decision_type: str,
                                    ml_decision: Any,
                                    context: Dict[str, Any]) -> HybridDecisionContext:
        """
        Traitement complet d'une décision avec intelligence hybride
        
        Args:
            decision_type: Type de décision (risk_assessment, portfolio_change, etc.)
            ml_decision: Décision originale du ML
            context: Contexte de la décision (features, données marché, etc.)
            
        Returns:
            HybridDecisionContext avec toutes les analyses
        """
        if not self.initialized:
            await self.initialize()
        
        decision_id = f"HYB-{int(datetime.now().timestamp())}"
        
        # Créer le contexte de base
        hybrid_context = HybridDecisionContext(
            decision_id=decision_id,
            decision_type=decision_type,
            original_ml_decision=ml_decision,
            confidence_score=context.get("confidence", 0.5),
            risk_level=context.get("risk_level", 0.5),
            market_data=context.get("market_data", {}),
            portfolio_data=context.get("portfolio_data", {}),
            real_time_alerts=[]
        )
        
        try:
            # Phase 3A: Advanced Risk Analysis
            if self.orchestration_config.get("risk_analysis_enabled", True):
                await self._perform_risk_analysis(hybrid_context, context)
            
            # Phase 3C.1: Generate AI Explanation
            if self.orchestration_config.get("auto_explain_decisions", True):
                await self._generate_explanation(hybrid_context, context)
            
            # Phase 3C.2: Determine Human Intervention Need
            await self._evaluate_human_intervention(hybrid_context)
            
            # Phase 3B: Real-time Broadcasting
            if self.orchestration_config.get("real_time_broadcasting", True):
                await self._broadcast_decision_event(hybrid_context)
            
            # Phase 3C.3: Learning and Feedback
            if self.orchestration_config.get("learning_feedback_enabled", True):
                await self._capture_learning_opportunity(hybrid_context)
            
            self.metrics["decisions_processed"] += 1
            
            log.info(f"Hybrid decision {decision_id} processed successfully")
            return hybrid_context
            
        except Exception as e:
            log.error(f"Error processing hybrid decision {decision_id}: {e}")
            raise
    
    async def _perform_risk_analysis(self, context: HybridDecisionContext, input_context: Dict[str, Any]):
        """Phase 3A: Analyse de risque avancée"""
        if not self.advanced_risk_enabled:
            return
        
        try:
            # Extraire les données de portfolio pour l'analyse de risque
            portfolio_weights = input_context.get("portfolio_weights", {})
            portfolio_value = input_context.get("portfolio_value", 100000)
            
            if not portfolio_weights:
                # Portfolio par défaut si pas fourni
                portfolio_weights = {"BTC": 0.4, "ETH": 0.3, "SOL": 0.2, "AVAX": 0.1}
            
            # Simuler l'appel à l'Advanced Risk Engine
            # En production, on utiliserait l'API /api/advanced-risk/summary
            var_metrics = {
                "var_daily_95": portfolio_value * context.risk_level * 0.05,
                "var_daily_99": portfolio_value * context.risk_level * 0.08,
                "confidence_level": 0.95,
                "method": "parametric"
            }
            
            stress_test_results = {
                "worst_case_scenario": "crisis_2008",
                "portfolio_loss_pct": -context.risk_level * 20,  # Max 20% loss
                "recovery_estimate_days": int(context.risk_level * 90)
            }
            
            monte_carlo_results = {
                "simulations": 10000,
                "var_estimates": {
                    "95%": var_metrics["var_daily_95"] * 1.1,
                    "99%": var_metrics["var_daily_99"] * 1.05
                },
                "tail_expectation": var_metrics["var_daily_95"] * 1.2
            }
            
            # Mettre à jour le contexte
            context.var_metrics = var_metrics
            context.stress_test_results = stress_test_results
            context.monte_carlo_results = monte_carlo_results
            
            log.debug(f"Risk analysis completed for decision {context.decision_id}")
            
        except Exception as e:
            log.warning(f"Risk analysis failed for decision {context.decision_id}: {e}")
    
    async def _generate_explanation(self, context: HybridDecisionContext, input_context: Dict[str, Any]):
        """Phase 3C.1: Génération d'explication IA"""
        if not self.xai_engine:
            return
        
        try:
            # Préparer les features pour l'explication
            features = input_context.get("features", {})
            if not features:
                # Features simulées basées sur le contexte
                features = {
                    "risk_level": context.risk_level,
                    "confidence": context.confidence_score,
                    "market_volatility": context.market_data.get("volatility", 0.02),
                    "portfolio_value": context.portfolio_data.get("value", 100000),
                    "decision_complexity": len(str(context.original_ml_decision)) / 100
                }
            
            # Générer l'explication
            explanation = await self.xai_engine.explain_decision(
                model_name=context.decision_type,
                prediction=context.confidence_score,
                features=features,
                model_data={"context": input_context}
            )
            
            context.explanation = explanation.to_dict()
            self.metrics["explanations_generated"] += 1
            
            log.debug(f"Explanation generated for decision {context.decision_id}")
            
        except Exception as e:
            log.warning(f"Explanation generation failed for decision {context.decision_id}: {e}")
    
    async def _evaluate_human_intervention(self, context: HybridDecisionContext):
        """Phase 3C.2: Évaluation du besoin d'intervention humaine"""
        if not self.human_loop_engine:
            return
        
        try:
            intervention_threshold = self.orchestration_config["human_intervention_threshold"]
            
            # Critères d'intervention
            needs_intervention = (
                context.risk_level > intervention_threshold or
                context.confidence_score < 0.6 or
                (context.var_metrics and context.var_metrics.get("var_daily_95", 0) > 10000) or
                (context.stress_test_results and context.stress_test_results.get("portfolio_loss_pct", 0) < -15)
            )
            
            if needs_intervention:
                # Créer une demande d'intervention humaine
                decision_request = await self.human_loop_engine.request_human_decision(
                    decision_type=context.decision_type,
                    original_decision=context.original_ml_decision,
                    explanation=context.explanation,
                    context={
                        "risk_level": context.risk_level,
                        "confidence": context.confidence_score,
                        "var_metrics": context.var_metrics,
                        "stress_results": context.stress_test_results
                    }
                )
                
                context.human_intervention_required = True
                self.metrics["human_interventions_triggered"] += 1
                
                log.info(f"Human intervention requested for decision {context.decision_id}: {decision_request.request_id}")
            else:
                context.human_intervention_required = False
                log.debug(f"No human intervention needed for decision {context.decision_id}")
                
        except Exception as e:
            log.warning(f"Human intervention evaluation failed for decision {context.decision_id}: {e}")
    
    async def _broadcast_decision_event(self, context: HybridDecisionContext):
        """Phase 3B: Diffusion temps réel de l'événement de décision"""
        if not self.realtime_engine:
            return
        
        try:
            # Préparer les données pour la diffusion
            event_data = {
                "decision_id": context.decision_id,
                "decision_type": context.decision_type,
                "risk_level": context.risk_level,
                "confidence": context.confidence_score,
                "human_intervention_required": context.human_intervention_required,
                "explanation_available": context.explanation is not None,
                "risk_metrics": {
                    "var_95": context.var_metrics.get("var_daily_95") if context.var_metrics else None,
                    "stress_test_loss": context.stress_test_results.get("portfolio_loss_pct") if context.stress_test_results else None
                }
            }
            
            # Diffuser l'événement
            await self.realtime_engine.publish_risk_event(
                event_type="hybrid_decision",
                data=event_data,
                source="hybrid_orchestrator"
            )
            
            context.streaming_enabled = True
            self.metrics["real_time_events_broadcasted"] += 1
            
            log.debug(f"Decision event broadcasted for {context.decision_id}")
            
        except Exception as e:
            log.warning(f"Real-time broadcasting failed for decision {context.decision_id}: {e}")
    
    async def _capture_learning_opportunity(self, context: HybridDecisionContext):
        """Phase 3C.3: Capture d'opportunité d'apprentissage"""
        if not self.learning_engine:
            return
        
        try:
            # Identifier les patterns d'apprentissage potentiels
            learning_insights = []
            
            # Insight 1: Décision à haute confiance mais haut risque
            if context.confidence_score > 0.8 and context.risk_level > 0.7:
                learning_insights.append({
                    "pattern": "high_confidence_high_risk",
                    "description": "Confiance élevée avec risque élevé - potentiel biais de surconfiance",
                    "recommendation": "Review confidence calibration"
                })
            
            # Insight 2: Intervention humaine fréquente
            if context.human_intervention_required:
                learning_insights.append({
                    "pattern": "frequent_human_intervention",
                    "description": "Intervention humaine nécessaire - calibrage automatique insuffisant",
                    "recommendation": "Adjust automation thresholds"
                })
            
            # Insight 3: Métriques de risque incohérentes
            if (context.var_metrics and context.stress_test_results and
                abs(context.var_metrics.get("var_daily_95", 0) - 
                    abs(context.stress_test_results.get("portfolio_loss_pct", 0) * 1000)) > 5000):
                learning_insights.append({
                    "pattern": "risk_metrics_inconsistency", 
                    "description": "Incohérence entre VaR et stress tests",
                    "recommendation": "Calibrate risk model parameters"
                })
            
            context.learning_insights = learning_insights
            
            if learning_insights:
                self.metrics["learning_insights_generated"] += len(learning_insights)
                log.debug(f"Generated {len(learning_insights)} learning insights for decision {context.decision_id}")
            
        except Exception as e:
            log.warning(f"Learning opportunity capture failed for decision {context.decision_id}: {e}")
    
    async def _orchestration_loop(self):
        """Loop d'orchestration en arrière-plan"""
        while self.running:
            try:
                # Vérifications périodiques de santé des composants
                await self._health_check_components()
                
                # Nettoyage des métriques anciennes
                await self._cleanup_old_metrics()
                
                # Attendre avant la prochaine itération
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in orchestration loop: {e}")
                await asyncio.sleep(60)
    
    async def _health_check_components(self):
        """Vérification de santé des composants"""
        try:
            components_status = {}
            
            # Check XAI Engine
            if self.xai_engine:
                components_status["xai_engine"] = "healthy"
            
            # Check Human Loop Engine
            if self.human_loop_engine:
                components_status["human_loop_engine"] = "healthy" if self.human_loop_engine.running else "inactive"
            
            # Check Learning Engine
            if self.learning_engine:
                components_status["learning_engine"] = "healthy" if self.learning_engine.running else "inactive"
            
            # Check Realtime Engine
            if self.realtime_engine:
                components_status["realtime_engine"] = "healthy" if self.realtime_engine.running else "inactive"
            
            # Log status if any component is not healthy
            unhealthy = [k for k, v in components_status.items() if v != "healthy"]
            if unhealthy:
                log.warning(f"Unhealthy components detected: {unhealthy}")
            
        except Exception as e:
            log.error(f"Health check failed: {e}")
    
    async def _cleanup_old_metrics(self):
        """Nettoyage des métriques anciennes"""
        # Reset daily metrics if needed
        if self.metrics["start_time"]:
            uptime = (datetime.now() - self.metrics["start_time"]).days
            if uptime >= 1:
                # Reset counters for new day but keep cumulative stats
                self.metrics["start_time"] = datetime.now()
    
    # API Methods for external access
    
    def get_metrics(self) -> Dict[str, Any]:
        """Métriques de l'orchestrateur hybride"""
        uptime = 0
        if self.metrics["start_time"]:
            uptime = (datetime.now() - self.metrics["start_time"]).total_seconds()
        
        return {
            **self.metrics,
            "uptime_seconds": uptime,
            "running": self.running,
            "initialized": self.initialized,
            "components_initialized": {
                "xai_engine": self.xai_engine is not None,
                "human_loop_engine": self.human_loop_engine is not None,
                "learning_engine": self.learning_engine is not None,
                "realtime_engine": self.realtime_engine is not None
            }
        }
    
    def get_component_status(self) -> Dict[str, str]:
        """Status des composants"""
        return {
            "xai_engine": "active" if self.xai_engine else "inactive",
            "human_loop": "active" if (self.human_loop_engine and self.human_loop_engine.running) else "inactive",
            "learning": "active" if (self.learning_engine and self.learning_engine.running) else "inactive",
            "realtime": "active" if (self.realtime_engine and self.realtime_engine.running) else "inactive"
        }
    
    async def simulate_decision_flow(self, decision_type: str = "risk_assessment", risk_level: float = 0.7) -> Dict[str, Any]:
        """Simuler un flux complet de décision hybride (pour tests/démo)"""
        try:
            # Simuler une décision ML
            ml_decision = {
                "action": "reduce_exposure" if risk_level > 0.6 else "maintain",
                "percentage": risk_level * 20,
                "confidence": 0.9 - risk_level * 0.2
            }
            
            # Simuler le contexte
            context = {
                "confidence": 0.9 - risk_level * 0.2,
                "risk_level": risk_level,
                "features": {
                    "volatility_btc": risk_level * 0.05,
                    "correlation_level": 0.6 + risk_level * 0.3,
                    "sentiment_score": 0.5 - risk_level * 0.2
                },
                "portfolio_weights": {"BTC": 0.4, "ETH": 0.3, "SOL": 0.2, "AVAX": 0.1},
                "portfolio_value": 100000,
                "market_data": {"volatility": risk_level * 0.03},
                "portfolio_data": {"value": 100000}
            }
            
            # Traiter la décision hybride
            result = await self.process_hybrid_decision(decision_type, ml_decision, context)
            
            return {
                "simulation_success": True,
                "decision_context": asdict(result),
                "components_used": {
                    "risk_analysis": result.var_metrics is not None,
                    "ai_explanation": result.explanation is not None,
                    "human_intervention": result.human_intervention_required,
                    "real_time_broadcast": result.streaming_enabled,
                    "learning_insights": len(result.learning_insights or [])
                }
            }
            
        except Exception as e:
            log.error(f"Simulation failed: {e}")
            return {"simulation_success": False, "error": str(e)}


# Factory and singleton management
_global_hybrid_orchestrator: Optional[HybridOrchestrator] = None

async def get_hybrid_orchestrator(config: Dict[str, Any] = None) -> HybridOrchestrator:
    """Récupérer l'instance globale de l'orchestrateur hybride"""
    global _global_hybrid_orchestrator
    
    if _global_hybrid_orchestrator is None:
        _global_hybrid_orchestrator = HybridOrchestrator(config)
        await _global_hybrid_orchestrator.initialize()
    
    return _global_hybrid_orchestrator

def create_hybrid_orchestrator(config: Dict[str, Any] = None) -> HybridOrchestrator:
    """Factory pour créer un orchestrateur hybride"""
    return HybridOrchestrator(config)