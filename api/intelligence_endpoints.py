"""
Phase 3C Intelligence API Endpoints - Hybrid Intelligence System
Provides REST API for Explainable AI, Human-in-the-loop, and Feedback Learning
"""
from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union
import logging
from datetime import datetime

from services.intelligence.explainable_ai import (
    get_explainable_ai_engine, ExplainableAIEngine, ExplanationType
)
from services.intelligence.human_loop import (
    get_human_loop_engine, HumanInTheLoopEngine, UrgencyLevel, DecisionStatus
)
from services.intelligence.feedback_learning import (
    get_feedback_learning_engine, FeedbackLearningEngine
)

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])
log = logging.getLogger(__name__)

# Request/Response Models
class ExplanationRequest(BaseModel):
    model_name: str = Field(..., description="Nom du modèle à expliquer")
    prediction: Union[float, int, str] = Field(..., description="Prédiction du modèle")
    features: Dict[str, float] = Field(..., description="Features utilisées")
    model_data: Optional[Dict[str, Any]] = Field(None, description="Données additionnelles du modèle")
    explanation_types: Optional[List[str]] = Field(None, description="Types d'explications demandées")

class DecisionRequest(BaseModel):
    decision_type: str = Field(..., description="Type de décision")
    original_decision: Any = Field(..., description="Décision originale ML")
    prediction: Union[float, int, str] = Field(..., description="Prédiction associée")
    features: Dict[str, float] = Field(..., description="Features de décision")
    context: Optional[Dict[str, Any]] = Field(None, description="Contexte de la décision")
    timeout_action: str = Field("approve", description="Action en cas de timeout")

class HumanDecisionResponse(BaseModel):
    human_decision: Any = Field(..., description="Décision humaine")
    feedback: Optional[str] = Field(None, description="Feedback textuel")
    decided_by: str = Field(..., description="Identifiant du décideur")

class FeedbackRequest(BaseModel):
    request_id: str = Field(..., description="ID de la demande de décision")
    decision_quality: int = Field(..., ge=1, le=5, description="Qualité de la décision (1-5)")
    explanation_clarity: int = Field(..., ge=1, le=5, description="Clarté de l'explication (1-5)")
    confidence_in_ai: int = Field(..., ge=1, le=5, description="Confiance dans l'IA (1-5)")
    feedback_text: str = Field(..., description="Feedback textuel")
    suggestions: Optional[List[str]] = Field(None, description="Suggestions d'amélioration")
    would_decide_differently: bool = Field(False, description="Aurait décidé différemment")
    provided_by: str = Field("anonymous", description="Identifiant du feedback provider")

# Explainable AI Endpoints
@router.post("/explain/decision")
async def explain_decision(
    request: ExplanationRequest,
    xai_engine: ExplainableAIEngine = Depends(get_explainable_ai_engine)
):
    """Générer une explication pour une décision ML"""
    try:
        explanation_types = None
        if request.explanation_types:
            explanation_types = [ExplanationType(et) for et in request.explanation_types]
        
        explanation = await xai_engine.explain_decision(
            model_name=request.model_name,
            prediction=request.prediction,
            features=request.features,
            model_data=request.model_data,
            explanation_types=explanation_types
        )
        
        return explanation.to_dict()
        
    except Exception as e:
        log.error(f"Failed to explain decision: {e}")
        raise HTTPException(500, f"explanation_failed: {str(e)}")

@router.post("/explain/alert")
async def explain_alert(
    alert_data: Dict[str, Any] = Body(...),
    context: Optional[Dict[str, Any]] = Body(None),
    xai_engine: ExplainableAIEngine = Depends(get_explainable_ai_engine)
):
    """Générer une explication pour une alerte de risque"""
    try:
        explanation = await xai_engine.explain_risk_alert(alert_data, context)
        return explanation.to_dict()
        
    except Exception as e:
        log.error(f"Failed to explain alert: {e}")
        raise HTTPException(500, f"alert_explanation_failed: {str(e)}")

@router.post("/explain/counterfactual")
async def generate_counterfactual(
    features: Dict[str, float] = Body(...),
    target_prediction: float = Body(...),
    model_name: str = Body(...),
    xai_engine: ExplainableAIEngine = Depends(get_explainable_ai_engine)
):
    """Générer une explication contrefactuelle"""
    try:
        counterfactual = await xai_engine.generate_counterfactual_explanation(
            features, target_prediction, model_name
        )
        return counterfactual
        
    except Exception as e:
        log.error(f"Failed to generate counterfactual: {e}")
        raise HTTPException(500, f"counterfactual_failed: {str(e)}")

@router.get("/explain/history")
async def get_explanation_history(
    model_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    xai_engine: ExplainableAIEngine = Depends(get_explainable_ai_engine)
):
    """Récupérer l'historique des explications"""
    try:
        history = await xai_engine.get_explanation_history(model_name, limit)
        return {"explanations": history}
        
    except Exception as e:
        log.error(f"Failed to get explanation history: {e}")
        raise HTTPException(500, f"history_failed: {str(e)}")

# Human-in-the-loop Endpoints
@router.post("/human/request-decision")
async def request_human_decision(
    request: DecisionRequest,
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine),
    xai_engine: ExplainableAIEngine = Depends(get_explainable_ai_engine)
):
    """Demander une intervention humaine pour une décision"""
    try:
        # Générer l'explication de la décision
        explanation = await xai_engine.explain_decision(
            model_name=request.decision_type,
            prediction=request.prediction,
            features=request.features,
            model_data={"context": request.context}
        )
        
        # Créer la demande d'intervention humaine
        decision_request = await human_engine.request_human_decision(
            decision_type=request.decision_type,
            original_decision=request.original_decision,
            explanation=explanation,
            context=request.context,
            timeout_action=request.timeout_action
        )
        
        return decision_request.to_dict()
        
    except Exception as e:
        log.error(f"Failed to request human decision: {e}")
        raise HTTPException(500, f"human_request_failed: {str(e)}")

@router.post("/human/provide-decision/{request_id}")
async def provide_human_decision(
    request_id: str,
    response: HumanDecisionResponse,
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine)
):
    """Fournir une décision humaine"""
    try:
        success = await human_engine.provide_decision(
            request_id=request_id,
            human_decision=response.human_decision,
            decided_by=response.decided_by,
            feedback=response.feedback
        )
        
        if not success:
            raise HTTPException(404, f"Decision request {request_id} not found")
        
        return {"success": True, "request_id": request_id}
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to provide human decision: {e}")
        raise HTTPException(500, f"decision_provision_failed: {str(e)}")

@router.get("/human/pending-decisions")
async def get_pending_decisions(
    urgency_filter: Optional[str] = Query(None),
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine)
):
    """Récupérer les décisions en attente"""
    try:
        urgency = None
        if urgency_filter:
            urgency = UrgencyLevel(urgency_filter)
        
        decisions = human_engine.get_pending_decisions(urgency)
        return {"pending_decisions": decisions}
        
    except Exception as e:
        log.error(f"Failed to get pending decisions: {e}")
        raise HTTPException(500, f"pending_decisions_failed: {str(e)}")

@router.get("/human/decision-history")
async def get_decision_history(
    limit: int = Query(50, ge=1, le=500),
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine)
):
    """Récupérer l'historique des décisions"""
    try:
        history = human_engine.get_decision_history(limit)
        return {"decision_history": history}
        
    except Exception as e:
        log.error(f"Failed to get decision history: {e}")
        raise HTTPException(500, f"decision_history_failed: {str(e)}")

@router.get("/human/dashboard-stats")
async def get_human_dashboard_stats(
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine)
):
    """Statistiques pour le dashboard human-in-the-loop"""
    try:
        stats = human_engine.get_dashboard_stats()
        return stats
        
    except Exception as e:
        log.error(f"Failed to get dashboard stats: {e}")
        raise HTTPException(500, f"dashboard_stats_failed: {str(e)}")

@router.post("/human/wait-for-decision/{request_id}")
async def wait_for_decision(
    request_id: str,
    polling_interval: float = Query(1.0, ge=0.1, le=10.0),
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine)
):
    """Attendre une décision humaine (avec polling)"""
    try:
        # Récupérer la demande
        pending_requests = human_engine.decision_queue.pending_requests
        completed_requests = human_engine.decision_queue.completed_requests
        
        request = (pending_requests.get(request_id) or 
                  completed_requests.get(request_id))
        
        if not request:
            raise HTTPException(404, f"Decision request {request_id} not found")
        
        # Si déjà complétée, retourner immédiatement
        if request.status != DecisionStatus.PENDING:
            return {
                "decision": request.human_decision,
                "status": request.status.value,
                "decided_by": request.decided_by,
                "decided_at": request.decided_at.isoformat() if request.decided_at else None
            }
        
        # Attendre la décision
        final_decision = await human_engine.wait_for_decision(request, polling_interval)
        
        # Récupérer le statut final
        final_request = (completed_requests.get(request_id) or 
                        pending_requests.get(request_id))
        
        return {
            "decision": final_decision,
            "status": final_request.status.value if final_request else "unknown",
            "decided_by": final_request.decided_by if final_request else None,
            "decided_at": final_request.decided_at.isoformat() if final_request and final_request.decided_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to wait for decision: {e}")
        raise HTTPException(500, f"decision_wait_failed: {str(e)}")

# Feedback Learning Endpoints
@router.post("/feedback/submit")
async def submit_feedback(
    feedback: FeedbackRequest,
    learning_engine: FeedbackLearningEngine = Depends(get_feedback_learning_engine),
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine)
):
    """Soumettre un feedback sur une décision"""
    try:
        feedback_id = await human_engine.submit_feedback(
            request_id=feedback.request_id,
            quality_rating=feedback.decision_quality,
            clarity_rating=feedback.explanation_clarity,
            confidence_rating=feedback.confidence_in_ai,
            feedback_text=feedback.feedback_text,
            suggestions=feedback.suggestions,
            would_decide_differently=feedback.would_decide_differently,
            provided_by=feedback.provided_by
        )
        
        return {"success": True, "feedback_id": feedback_id}
        
    except Exception as e:
        log.error(f"Failed to submit feedback: {e}")
        raise HTTPException(500, f"feedback_submission_failed: {str(e)}")

@router.get("/learning/insights")
async def get_learning_insights(
    learning_engine: FeedbackLearningEngine = Depends(get_feedback_learning_engine)
):
    """Récupérer les insights d'apprentissage"""
    try:
        insights = learning_engine.get_learning_insights()
        return {"insights": insights}
        
    except Exception as e:
        log.error(f"Failed to get learning insights: {e}")
        raise HTTPException(500, f"learning_insights_failed: {str(e)}")

@router.get("/learning/suggestions")
async def get_model_suggestions(
    status_filter: Optional[str] = Query(None),
    learning_engine: FeedbackLearningEngine = Depends(get_feedback_learning_engine)
):
    """Récupérer les suggestions d'amélioration de modèle"""
    try:
        suggestions = learning_engine.get_model_suggestions(status_filter)
        return {"suggestions": suggestions}
        
    except Exception as e:
        log.error(f"Failed to get model suggestions: {e}")
        raise HTTPException(500, f"model_suggestions_failed: {str(e)}")

@router.post("/learning/generate-improvements")
async def generate_model_improvements(
    learning_engine: FeedbackLearningEngine = Depends(get_feedback_learning_engine)
):
    """Générer des suggestions d'amélioration de modèle"""
    try:
        suggestions = await learning_engine.generate_model_improvements()
        return {
            "suggestions_generated": len(suggestions),
            "suggestions": [s.__dict__ for s in suggestions]
        }
        
    except Exception as e:
        log.error(f"Failed to generate model improvements: {e}")
        raise HTTPException(500, f"improvement_generation_failed: {str(e)}")

@router.get("/learning/metrics")
async def get_learning_metrics(
    learning_engine: FeedbackLearningEngine = Depends(get_feedback_learning_engine)
):
    """Métriques d'apprentissage"""
    try:
        metrics = learning_engine.get_learning_metrics()
        return metrics
        
    except Exception as e:
        log.error(f"Failed to get learning metrics: {e}")
        raise HTTPException(500, f"learning_metrics_failed: {str(e)}")

@router.get("/learning/performance-trends")
async def get_performance_trends(
    learning_engine: FeedbackLearningEngine = Depends(get_feedback_learning_engine)
):
    """Tendances de performance"""
    try:
        trends = learning_engine.get_performance_trends()
        return trends
        
    except Exception as e:
        log.error(f"Failed to get performance trends: {e}")
        raise HTTPException(500, f"performance_trends_failed: {str(e)}")

@router.get("/learning/feature-status")
async def get_feature_learning_status(
    learning_engine: FeedbackLearningEngine = Depends(get_feedback_learning_engine)
):
    """Status d'apprentissage par feature"""
    try:
        status = learning_engine.get_feature_learning_status()
        return {"features": status}
        
    except Exception as e:
        log.error(f"Failed to get feature learning status: {e}")
        raise HTTPException(500, f"feature_status_failed: {str(e)}")

# System Status Endpoints
@router.get("/status")
async def get_intelligence_status(
    xai_engine: ExplainableAIEngine = Depends(get_explainable_ai_engine),
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine),
    learning_engine: FeedbackLearningEngine = Depends(get_feedback_learning_engine)
):
    """Status global du système d'intelligence hybride"""
    try:
        return {
            "system_status": "operational",
            "components": {
                "explainable_ai": {
                    "status": "active",
                    "metrics": xai_engine.get_metrics()
                },
                "human_in_the_loop": {
                    "status": "active" if human_engine.running else "inactive",
                    "metrics": human_engine.get_metrics()
                },
                "feedback_learning": {
                    "status": "active" if learning_engine.running else "inactive", 
                    "metrics": learning_engine.get_metrics()
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        log.error(f"Failed to get intelligence status: {e}")
        raise HTTPException(500, f"status_failed: {str(e)}")

@router.post("/system/start")
async def start_intelligence_system(
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine),
    learning_engine: FeedbackLearningEngine = Depends(get_feedback_learning_engine)
):
    """Démarrer le système d'intelligence hybride"""
    try:
        # Démarrer les composants
        if not human_engine.running:
            await human_engine.start()
        
        if not learning_engine.running:
            await learning_engine.start()
        
        return {"success": True, "message": "Intelligence system started"}
        
    except Exception as e:
        log.error(f"Failed to start intelligence system: {e}")
        raise HTTPException(500, f"system_start_failed: {str(e)}")

@router.post("/system/stop")
async def stop_intelligence_system(
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine),
    learning_engine: FeedbackLearningEngine = Depends(get_feedback_learning_engine)
):
    """Arrêter le système d'intelligence hybride"""
    try:
        # Arrêter les composants
        if human_engine.running:
            await human_engine.stop()
        
        if learning_engine.running:
            await learning_engine.stop()
        
        return {"success": True, "message": "Intelligence system stopped"}
        
    except Exception as e:
        log.error(f"Failed to stop intelligence system: {e}")
        raise HTTPException(500, f"system_stop_failed: {str(e)}")

# Demo/Test Endpoints
@router.post("/demo/simulate-decision-flow")
async def simulate_decision_flow(
    decision_type: str = Body("risk_assessment"),
    risk_level: float = Body(0.7),
    xai_engine: ExplainableAIEngine = Depends(get_explainable_ai_engine),
    human_engine: HumanInTheLoopEngine = Depends(get_human_loop_engine)
):
    """Simuler un flux complet de décision avec explication et intervention humaine"""
    try:
        # Simuler des features
        features = {
            "volatility_btc": risk_level * 0.05,
            "correlation_btc_eth": 0.6 + risk_level * 0.3,
            "sentiment_score": 0.5 - risk_level * 0.2,
            "var_95": risk_level * 10000,
            "decision_confidence": 0.8 - risk_level * 0.3
        }
        
        # Prédiction simulée
        prediction = risk_level
        
        # Générer explication
        explanation = await xai_engine.explain_decision(
            model_name=decision_type,
            prediction=prediction,
            features=features,
            model_data={"simulation": True}
        )
        
        # Créer demande d'intervention humaine si nécessaire
        human_request = None
        if risk_level > 0.6:  # Intervention requise pour risque élevé
            human_request = await human_engine.request_human_decision(
                decision_type=decision_type,
                original_decision={"action": "reduce_exposure", "percentage": risk_level * 20},
                explanation=explanation,
                context={"simulation": True, "risk_level": risk_level}
            )
        
        return {
            "simulation_complete": True,
            "explanation": explanation.to_dict(),
            "human_intervention_required": human_request is not None,
            "human_request": human_request.to_dict() if human_request else None
        }
        
    except Exception as e:
        log.error(f"Failed to simulate decision flow: {e}")
        raise HTTPException(500, f"simulation_failed: {str(e)}")