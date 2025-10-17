"""
Endpoints de gouvernance

Ces endpoints gerent l'etat de gouvernance, les modes, les plans et les politiques d'execution.
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, timedelta

from services.execution.governance import Policy, governance_engine
from services.execution.score_registry import get_score_registry
from services.execution.phase_engine import get_phase_engine
from .models import (
    GovernanceStateResponse, ScoreComponents, CanonicalScores,
    PhaseInfo, ExecutionPressure, MarketSignals, CycleSignals,
    UnifiedSignals, PortfolioMetrics, SuggestionIA,
    UnifiedApprovalRequest, FreezeRequest, ApplyPolicyRequest
)

# Import RBAC from alerts (shared dependency)
try:
    from api.alerts_endpoints import User, get_current_user, require_role
except ImportError:
    class User:
        def __init__(self, username: str = "system", roles: List[str] = None):
            self.username = username
            self.roles = roles or ["approver"]
    
    def get_current_user() -> User:
        return User("system_user", ["approver", "viewer"])
    
    def require_role(required_role: str):
        def dependency(current_user: User = Depends(get_current_user)):
            return current_user
        return dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execution/governance", tags=["governance"])

@router.get("/state", response_model=GovernanceStateResponse)
async def get_governance_state():
    """
    Obtenir l'état actuel du système de gouvernance - VERSION UNIFIÉE
    
    Retourne maintenant :
    - Champs existants (compatibilité) 
    - Scores canoniques unifiés
    - Phase de rotation BTC→ETH→Large→Alt
    - Exec pressure court-terme
    - Bus de signaux unifié (market/cycle)
    - Métriques portefeuille
    - Suggestion IA canonique
    """
    try:
        # 1. État governance existant
        state = await governance_engine.get_current_state()
        
        # Derive current state from available data
        current_state = "IDLE"
        if state.proposed_plan:
            current_state = "DRAFT"
        elif state.current_plan:
            current_state = "ACTIVE"
        
        # Get current plan ETag for concurrency control
        current_etag = None
        if state.current_plan:
            current_etag = state.current_plan.etag
        elif state.proposed_plan:
            current_etag = state.proposed_plan.etag
        
        # 2. NOUVEAUX CHAMPS - Score canonique
        canonical_scores = None
        try:
            score_registry = get_score_registry()
            
            # Extraire les composants depuis les signaux ML existants
            ml_signals = state.signals if state.signals else None
            
            if ml_signals:
                # Mapping des signaux ML vers composants de score
                trend_regime = 50.0  # CCS Mixte via trend_regime uniquement 
                if hasattr(ml_signals, 'regime') and ml_signals.regime:
                    # Convertir regime probabilities en score 0-100
                    bull_prob = ml_signals.regime.get('bull', 0.33)
                    trend_regime = min(100.0, max(0.0, bull_prob * 100 + 25))
                
                risk_component = 50.0
                if hasattr(ml_signals, 'volatility') and ml_signals.volatility:
                    # Volatilité inversée (high vol = low score)
                    avg_vol = sum(ml_signals.volatility.values()) / len(ml_signals.volatility)
                    risk_component = min(100.0, max(0.0, 100 - (avg_vol * 500)))
                
                breadth_rotation = 50.0  # Phase engine alimentera ceci
                
                sentiment_component = 50.0
                if hasattr(ml_signals, 'sentiment') and ml_signals.sentiment:
                    # Sentiment fear/greed → score 0-100
                    fear_greed = ml_signals.sentiment.get('fear_greed', 50)
                    sentiment_component = min(100.0, max(0.0, fear_greed))
                
                # Calculer score canonique
                raw_scores = await score_registry.calculate_canonical_score(
                    trend_regime=trend_regime,
                    risk=risk_component, 
                    breadth_rotation=breadth_rotation,
                    sentiment=sentiment_component,
                    contradiction_index=ml_signals.contradiction_index,
                    confidence=ml_signals.confidence
                )
                
                # Convertir en format compatible avec notre modèle d'endpoint
                canonical_scores = CanonicalScores(
                    decision=raw_scores.decision,
                    confidence=raw_scores.confidence,
                    contradiction=raw_scores.contradiction,
                    components=ScoreComponents(
                        trend_regime=raw_scores.components.trend_regime,
                        risk=raw_scores.components.risk,
                        breadth_rotation=raw_scores.components.breadth_rotation,
                        sentiment=raw_scores.components.sentiment
                    ),
                    as_of=raw_scores.as_of.isoformat()
                )
                
        except Exception as e:
            logger.warning(f"Error calculating canonical scores: {e}")
        
        # 3. Phase de rotation
        phase_info = None
        try:
            phase_engine = get_phase_engine()
            phase_state = await phase_engine.get_current_phase()
            
            phase_info = PhaseInfo(
                phase_now=phase_state.phase_now.value,
                phase_probs=phase_state.phase_probs,
                confidence=phase_state.confidence,
                explain=phase_state.explain,
                next_likely=phase_state.next_likely.value if phase_state.next_likely else None
            )
            
        except Exception as e:
            logger.warning(f"Error getting phase info: {e}")
        
        # 4. Exec pressure court-terme
        exec_pressure = None
        try:
            # Calculer pression d'exécution depuis policy et signaux
            policy = state.execution_policy
            if policy:
                # Pression basée sur cap et mode
                mode_pressure_map = {"Freeze": 90, "Slow": 70, "Normal": 40, "Aggressive": 20}
                base_pressure = mode_pressure_map.get(policy.mode, 50)
                
                # Ajustements selon coûts
                cost_multiplier = min(2.0, policy.execution_cost_bps / 20)  # 20 bps = baseline
                final_pressure = min(100.0, base_pressure * cost_multiplier)
                
                exec_pressure = ExecutionPressure(
                    pressure=final_pressure,
                    cost_estimate_bps=policy.execution_cost_bps,
                    market_impact="high" if final_pressure > 70 else "medium" if final_pressure > 40 else "low",
                    optimal_window_hours=policy.ramp_hours
                )
        except Exception as e:
            logger.warning(f"Error calculating exec pressure: {e}")
        
        # 5. Bus de signaux unifié
        unified_signals = None
        try:
            if state.signals:
                market_signals = MarketSignals(
                    volatility=state.signals.volatility if hasattr(state.signals, 'volatility') else {},
                    regime=state.signals.regime if hasattr(state.signals, 'regime') else {},
                    correlation=state.signals.correlation if hasattr(state.signals, 'correlation') else {},
                    sentiment=state.signals.sentiment if hasattr(state.signals, 'sentiment') else {}
                )
                
                # Cycle signals enrichis par Phase Engine
                # Map cycle position string to float (0-1 scale)
                position_map = {
                    'early_cycle': 0.25,
                    'mid_cycle': 0.50,
                    'late_cycle': 0.75,
                    'peak': 1.0
                }
                cycle_signals = CycleSignals(
                    btc_cycle={
                        "position": position_map.get('mid_cycle', 0.5),  # Float 0-1 (Pydantic expects float)
                        "confidence": 0.7
                    },
                    rotation={}
                )
                
                if phase_info:
                    cycle_signals.rotation = {
                        "current_phase": phase_info.phase_now,
                        "phase_strength": max(phase_info.phase_probs.values()),
                        "rotation_signal": phase_info.confidence
                    }
                
                unified_signals = UnifiedSignals(
                    market=market_signals,
                    cycle=cycle_signals,
                    as_of=state.signals.as_of.isoformat() if hasattr(state.signals, 'as_of') and state.signals.as_of else datetime.now().isoformat()
                )
                
        except Exception as e:
            logger.warning(f"Error building unified signals: {e}")
        
        # 6. Portfolio metrics (simulation pour l'instant)
        portfolio_metrics = {
            "metrics": PortfolioMetrics(
                var_95_pct=2.5,  # Simulé
                sharpe_ratio=1.2, 
                hhi_concentration=0.35,
                avg_correlation=0.65,
                beta_btc=0.85,
                exposures={"BTC": 45.0, "ETH": 25.0, "Large": 20.0, "Alt": 10.0}
            ).dict()
        }
        
        # 7. Suggestion IA canonique (lecture seule)
        suggestion_ia = None
        try:
            if canonical_scores and phase_info:
                # Générer suggestion basée sur score et phase
                confidence_level = canonical_scores.confidence
                decision_score = canonical_scores.decision
                current_phase = phase_info.phase_now
                
                # Logique de suggestion selon phase et score
                if current_phase == "btc" and decision_score > 60:
                    targets = [{"symbol": "BTC", "weight": 0.6}, {"symbol": "ETH", "weight": 0.25}, {"symbol": "SOL", "weight": 0.15}]
                    rationale = f"Phase BTC forte (score {decision_score:.0f}) : privilégier BTC"
                elif current_phase == "eth" and decision_score > 50:
                    targets = [{"symbol": "BTC", "weight": 0.4}, {"symbol": "ETH", "weight": 0.4}, {"symbol": "SOL", "weight": 0.2}]
                    rationale = f"Phase ETH (score {decision_score:.0f}) : équilibrer BTC/ETH"
                elif current_phase in ["large", "alt"] and decision_score > 55:
                    targets = [{"symbol": "BTC", "weight": 0.35}, {"symbol": "ETH", "weight": 0.25}, {"symbol": "SOL", "weight": 0.25}, {"symbol": "Others", "weight": 0.15}]
                    rationale = f"Phase {current_phase.upper()} (score {decision_score:.0f}) : diversifier vers alts"
                else:
                    # Conservative fallback
                    targets = [{"symbol": "BTC", "weight": 0.5}, {"symbol": "ETH", "weight": 0.3}, {"symbol": "SOL", "weight": 0.2}]
                    rationale = f"Mode conservateur (score {decision_score:.0f}, phase {current_phase})"
                
                # Policy hint basée sur contradiction et confiance
                contradiction = canonical_scores.contradiction
                if contradiction > 0.7 or confidence_level < 0.4:
                    policy_hint = "Slow"
                elif contradiction < 0.3 and confidence_level > 0.8:
                    policy_hint = "Aggressive"
                else:
                    policy_hint = "Normal"
                
                suggestion_ia = SuggestionIA(
                    targets=targets,
                    rationale=rationale,
                    policy_hint=policy_hint,
                    confidence=confidence_level,
                    generated_at=datetime.now().isoformat()
                )
                
        except Exception as e:
            logger.warning(f"Error generating IA suggestion: {e}")
        
        # CONSTRUCTION DE LA RÉPONSE UNIFIÉE
        # Count pending approvals (plans in DRAFT or REVIEWED state)
        pending_approvals = 0
        if state.proposed_plan and state.proposed_plan.status in ["DRAFT", "REVIEWED"]:
            pending_approvals = 1

        return GovernanceStateResponse(
            # Champs existants (compatibilité)
            current_state=current_state,
            mode=state.governance_mode.value if hasattr(state.governance_mode, 'value') else state.governance_mode,
            last_decision_id=state.current_plan.plan_id if state.current_plan else None,
            contradiction_index=state.signals.contradiction_index if state.signals else 0.0,
            ml_signals_timestamp=state.signals.timestamp.isoformat() if state.signals and hasattr(state.signals, 'timestamp') and state.signals.timestamp else (state.last_update.isoformat() if state.last_update else datetime.now().isoformat()),
            active_policy=state.execution_policy.dict() if state.execution_policy else None,
            pending_approvals=pending_approvals,
            next_update_time=state.last_update.isoformat() if state.last_update else None,
            etag=current_etag,
            auto_unfreeze_at=state.auto_unfreeze_at.isoformat() if state.auto_unfreeze_at else None,
            
            # NOUVEAUX CHAMPS UNIFIÉS
            scores=canonical_scores,
            phase=phase_info,
            exec=exec_pressure,
            signals=unified_signals,
            portfolio=portfolio_metrics,
            suggestion=suggestion_ia
        )
        
    except Exception as e:
        logger.error(f"Error getting governance state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# REMOVED: Old /governance/approve endpoint - replaced by unified /governance/approve/{resource_id}
# Former functionality available with resource_type="decision"

@router.post("/init-ml")
async def init_ml_models():
    """
    Force l'initialisation des modèles ML pour la gouvernance
    
    Utile pour résoudre les problèmes de modèles non initialisés.
    """
    try:
        # Force ML models ready status
        from services.ml.orchestrator import get_orchestrator
        orchestrator = get_orchestrator()
        
        models_initialized = 0
        for model_type in ['volatility', 'regime', 'correlation', 'sentiment', 'rebalancing']:
            if model_type in orchestrator.model_status:
                orchestrator.model_status[model_type] = 'ready'
                models_initialized += 1
        
        # Force refresh ML signals in governance
        await governance_engine._refresh_ml_signals()
        
        # Get current state to verify
        state = await governance_engine.get_current_state()
        signals = state.signals
        
        return {
            "success": True,
            "models_initialized": models_initialized,
            "current_signals": {
                "decision_score": signals.decision_score,
                "confidence": signals.confidence,
                "sources_used": signals.sources_used,
                "timestamp": signals.as_of.isoformat() if signals.as_of else None
            },
            "message": "ML models initialized and signals refreshed",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error initializing ML models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/unfreeze")
async def unfreeze_system():
    """
    Dégeler le système de gouvernance
    
    Remet le système en fonctionnement normal selon le mode configuré.
    """
    try:
        success = await governance_engine.unfreeze_system()
        
        if not success:
            raise HTTPException(status_code=400, detail="System is not frozen")
        
        return {
            "success": True,
            "message": "System unfrozen and resumed normal operations",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error unfreezing system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/signals")
async def get_ml_signals():
    """
    Obtenir les signaux ML actuels
    
    Retourne les derniers signaux des 4 modèles (volatilité, régime, corrélation, sentiment)
    avec leur indice de contradiction et la politique dérivée.
    """
    try:
        signals = await governance_engine.get_current_ml_signals()
        
        if not signals:
            return {
                "signals": None,
                "message": "No ML signals available",
                "timestamp": datetime.now().isoformat()
            }
        
        # Derive policy recommendation from ML signals
        derived_policy = None
        try:
            logger.debug(f"Deriving policy from signals: contradiction={signals.contradiction_index}, confidence={signals.confidence}")
            contradiction = signals.contradiction_index
            confidence = signals.confidence

            # Determine mode based on contradiction and confidence
            if contradiction > 0.7 or confidence < 0.4:
                mode = "Slow"
                cap_daily = 0.03  # 3% cap for high uncertainty
            elif contradiction < 0.3 and confidence > 0.8:
                mode = "Aggressive"
                cap_daily = 0.15  # 15% cap for high confidence
            else:
                mode = "Normal"
                cap_daily = 0.08  # 8% cap default

            # Adjust cap based on volatility if available
            if hasattr(signals, 'volatility') and signals.volatility and len(signals.volatility) > 0:
                avg_vol = sum(signals.volatility.values()) / len(signals.volatility)
                if avg_vol > 0.15:  # High volatility
                    cap_daily = max(0.02, cap_daily * 0.5)  # Reduce cap by 50%

            derived_policy = {
                "mode": mode,
                "cap_daily": cap_daily,
                "ramp_hours": 48 if mode == "Slow" else 24 if mode == "Normal" else 12,
                "rationale": f"Derived from contradiction={contradiction:.2f}, confidence={confidence:.2f}",
                "confidence": confidence
            }
            logger.info(f"Derived policy successfully: mode={mode}, cap={cap_daily:.2%}")
        except Exception as e:
            logger.warning(f"Error deriving policy: {e}", exc_info=True)

        return {
            "signals": {
                "volatility": signals.volatility,
                "regime": signals.regime,
                "correlation": signals.correlation,
                "sentiment": signals.sentiment,
                "decision_score": signals.decision_score,
                "confidence": signals.confidence,
                "contradiction_index": signals.contradiction_index,
                "blended_score": getattr(signals, 'blended_score', None),
                "sources_used": signals.sources_used,
                "timestamp": signals.as_of.isoformat() if hasattr(signals, 'as_of') and signals.as_of else None
            },
            "derived_policy": derived_policy,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting ML signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mode")
async def set_governance_mode(request: dict):
    """
    Changer le mode de gouvernance
    
    Modes disponibles:
    - manual: Décisions entièrement manuelles
    - ai_assisted: IA propose, humain approuve
    - full_ai: IA décide automatiquement (seuil de confiance)
    - freeze: Arrêt d'urgence
    """
    try:
        mode = request.get("mode", "").lower()
        reason = request.get("reason", "Mode change via UI")
        
        if mode not in ["manual", "ai_assisted", "full_ai", "freeze"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid mode '{mode}'. Valid modes: manual, ai_assisted, full_ai, freeze"
            )
        
        # Update governance mode
        success = await governance_engine.set_governance_mode(mode, reason)
        
        if success:
            return {
                "success": True,
                "message": f"Governance mode changed to '{mode}'",
                "mode": mode,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to change governance mode")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing governance mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/propose")
async def propose_decision(request: dict):
    """
    Proposer une nouvelle décision avec respect du cooldown
    
    Crée un plan DRAFT en respectant le cooldown entre publications.
    Utilise force_override_cooldown=true pour bypasser en urgence.
    """
    try:
        targets = request.get("targets", [
            {"symbol": "BTC", "weight": 0.6},
            {"symbol": "ETH", "weight": 0.3}, 
            {"symbol": "SOL", "weight": 0.1}
        ])
        reason = request.get("reason", "Test proposal from UI")
        force_override = request.get("force_override_cooldown", False)
        
        # Create a proposed plan (nouvelle signature avec tuple return)
        success, message = await governance_engine.create_proposed_plan(targets, reason, force_override)
        
        if success:
            plan_obj = getattr(governance_engine.current_state, 'proposed_plan', None)
            plan_id = getattr(plan_obj, 'plan_id', None)
            return {
                "success": True,
                "message": message,
                "state": "DRAFT",
                "plan_id": plan_id,
                "targets": targets,
                "reason": reason,
                "force_override_used": force_override,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=429, detail=message)  # 429 Too Many Requests pour cooldown
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proposing decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/review/{plan_id}")
async def review_plan(plan_id: str, request: dict, if_match: Optional[str] = Header(None)):
    """
    Review un plan DRAFT → REVIEWED with ETag-based concurrency control
    
    Transition obligatoire avant approbation en mode governance stricte.
    Utilise l'header If-Match pour le contrôle de concurrence optimiste.
    """
    try:
        reviewed_by = request.get("reviewed_by", "system")
        notes = request.get("notes", "Reviewed via API")
        
        success = await governance_engine.review_plan(plan_id, reviewed_by, notes, if_match)
        
        if success:
            # Get updated plan for new ETag
            state = await governance_engine.get_current_state()
            plan = governance_engine._find_plan_by_id(plan_id)
            new_etag = plan.etag if plan else None
            
            return {
                "success": True,
                "message": f"Plan {plan_id} reviewed by {reviewed_by}",
                "plan_id": plan_id,
                "new_state": "REVIEWED",
                "reviewed_by": reviewed_by,
                "etag": new_etag,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Check if it's an ETag mismatch vs other error
            if if_match:
                raise HTTPException(status_code=412, detail="Precondition Failed: ETag mismatch or plan state changed")
            else:
                raise HTTPException(status_code=400, detail="Plan not found or not in reviewable state")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reviewing plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/approve/{resource_id}")
async def unified_approval_endpoint(resource_id: str, request: UnifiedApprovalRequest):
    """
    Endpoint unifié pour approuver/rejeter des décisions ou des plans
    
    Remplace les anciens endpoints séparés /governance/approve et /governance/approve/{plan_id}
    """
    try:
        if request.resource_type == "decision":
            # Approbation de décision (ancien comportement /governance/approve)
            success = await governance_engine.approve_decision(
                decision_id=resource_id,
                approved=request.approved,
                reason=request.reason
            )
            
            if not success:
                raise HTTPException(status_code=404, detail="Decision not found or not in approvable state")
            
            return {
                "success": True,
                "resource_type": "decision",
                "resource_id": resource_id,
                "action": "approved" if request.approved else "rejected",
                "message": f"Decision {resource_id} {'approved' if request.approved else 'rejected'}",
                "approved_by": request.approved_by,
                "timestamp": datetime.now().isoformat()
            }
        
        elif request.resource_type == "plan":
            # Approbation ou rejet de plan (ancien comportement /governance/approve/{plan_id})
            if not request.approved:
                # Rejet de plan
                success = await governance_engine.reject_plan(
                    resource_id,
                    request.approved_by,  # renamed to rejected_by internally
                    request.notes or request.reason or "Rejected via API"
                )

                if not success:
                    raise HTTPException(status_code=404, detail="Plan not found or not in rejectable state (must be DRAFT or REVIEWED)")

                return {
                    "success": True,
                    "resource_type": "plan",
                    "resource_id": resource_id,
                    "action": "rejected",
                    "message": f"Plan {resource_id} rejected",
                    "rejected_by": request.approved_by,
                    "timestamp": datetime.now().isoformat()
                }
            
            success = await governance_engine.approve_plan(
                resource_id, 
                request.approved_by, 
                request.notes or request.reason or "Approved via API"
            )
            
            if success:
                return {
                    "success": True,
                    "resource_type": "plan",
                    "resource_id": resource_id,
                    "action": "approved",
                    "message": f"Plan {resource_id} approved by {request.approved_by}",
                    "new_state": "APPROVED",
                    "approved_by": request.approved_by,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                raise HTTPException(status_code=400, detail="Plan not found or not in approvable state")
        
        else:
            raise HTTPException(status_code=400, detail="Invalid resource_type. Must be 'decision' or 'plan'")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in unified approval for {request.resource_type} {resource_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/activate/{plan_id}")
async def activate_plan_endpoint(plan_id: str):
    """
    Activer un plan APPROVED → ACTIVE
    
    Rend le plan actif pour execution. Un seul plan peut être ACTIVE à la fois.
    """
    try:
        success = await governance_engine.activate_plan(plan_id)
        
        if success:
            return {
                "success": True,
                "message": f"Plan {plan_id} activated",
                "plan_id": plan_id,
                "new_state": "ACTIVE",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=400, detail="Plan not found or not in activatable state")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute/{plan_id}")
async def execute_plan_endpoint(plan_id: str):
    """
    Marquer un plan comme exécuté ACTIVE → EXECUTED
    
    Transition finale après execution réussie
    """
    try:
        success = await governance_engine.execute_plan(plan_id)
        
        if success:
            return {
                "success": True,
                "message": f"Plan {plan_id} marked as executed",
                "plan_id": plan_id,
                "new_state": "EXECUTED",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=400, detail="Plan not found or not in executable state")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking plan as executed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cancel/{plan_id}")
async def cancel_plan_endpoint(plan_id: str, request: dict):
    """
    Annuler un plan ANY_STATE → CANCELLED
    
    Peut annuler un plan depuis n'importe quel état (sauf EXECUTED/CANCELLED)
    """
    try:
        cancelled_by = request.get("cancelled_by", "system")
        reason = request.get("reason", "Cancelled via API")
        
        success = await governance_engine.cancel_plan(plan_id, cancelled_by, reason)
        
        if success:
            return {
                "success": True,
                "message": f"Plan {plan_id} cancelled by {cancelled_by}",
                "plan_id": plan_id,
                "new_state": "CANCELLED",
                "cancelled_by": cancelled_by,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=400, detail="Plan not found or not in cancellable state")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cooldown-status")
async def get_cooldown_status():
    """
    Vérifier le statut du cooldown de publication des plans
    
    Indique si on peut publier un nouveau plan et le temps restant.
    """
    try:
        can_publish, reason = governance_engine.can_publish_new_plan()
        
        # Get current policy for detailed info
        state = await governance_engine.get_current_state()
        policy = state.execution_policy if state else None
        
        return {
            "can_publish": can_publish,
            "reason": reason,
            "cooldown_hours": policy.plan_cooldown_hours if policy else None,
            "signals_ttl_seconds": policy.signals_ttl_seconds if policy else None,
            "current_policy_mode": policy.mode if policy else None,
            "no_trade_threshold_pct": policy.no_trade_threshold_pct if policy else None,
            "execution_cost_bps": policy.execution_cost_bps if policy else None,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting cooldown status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/apply_policy")
async def apply_policy_from_alert(
    request: ApplyPolicyRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", description="Cle idempotency UUID"),
    current_user: User = Depends(require_role("approver"))
):
    """
    Applique une policy sans creer de plan (respecte cooldown) - NOUVEAU

    Endpoint dedie pour actions suggerees par alertes.
    Necessite role 'approver' et cle d'idempotency.
    """
    from services.alerts.idempotency import get_idempotency_manager

    def _clamp_float(value, lower, upper, default):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = default
        return max(lower, min(upper, numeric))

    def _clamp_int(value, lower, upper, default):
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = default
        return max(lower, min(upper, numeric))

    try:
        state = await governance_engine.get_current_state()
        if state and state.execution_policy:
            logger.debug("Policy cooldown check - implementation simplified")

        cap_daily = _clamp_float(request.cap_daily, 0.01, 0.20, 0.08)
        no_trade_threshold = _clamp_float(request.no_trade_threshold_pct, 0.0, 0.10, 0.02)
        execution_cost_bps = _clamp_int(request.execution_cost_bps, 0, 100, 15)

        policy_notes = request.notes or f"Manual apply: {request.reason} (by {current_user.username})"
        policy_payload = {
            "mode": request.mode,
            "cap_daily": cap_daily,
            "ramp_hours": request.ramp_hours,
            "min_trade": request.min_trade,
            "slippage_limit_bps": request.slippage_limit_bps,
            "signals_ttl_seconds": request.signals_ttl_seconds,
            "plan_cooldown_hours": request.plan_cooldown_hours,
            "no_trade_threshold_pct": no_trade_threshold,
            "execution_cost_bps": execution_cost_bps,
            "notes": policy_notes,
        }
        policy = Policy(**policy_payload)
        policy_dict = policy.dict()

        response_data = {
            "success": True,
            "message": f"Policy applied & activated: {policy.mode}",
            "policy": policy_dict,
            "applied_by": current_user.username,
            "source_alert_id": request.source_alert_id,
            "reason": request.reason,
            "timestamp": datetime.now().isoformat(),
        }

        idem_manager = get_idempotency_manager()
        existing_response = idem_manager.check_and_store(idempotency_key, response_data)
        if existing_response:
            logger.info("Idempotent request detected for policy change: %s", idempotency_key)
            return existing_response

        applied_at = datetime.now()
        governance_engine.current_state.execution_policy = policy
        governance_engine.current_state.last_applied_policy = policy.model_copy(deep=True)
        governance_engine.current_state.last_manual_policy_update = applied_at
        governance_engine.current_state.last_update = applied_at
        governance_engine._last_cap = policy.cap_daily

        logger.info(
            "Policy applied & activated by %s (reason=%s): mode=%s, cap=%.2f%%",
            current_user.username,
            request.reason,
            policy.mode,
            policy.cap_daily * 100,
        )

        if request.source_alert_id:
            try:
                from api.alerts_endpoints import alert_engine
                if alert_engine:
                    await alert_engine.mark_alert_applied(request.source_alert_id, current_user.username)
            except Exception as alert_error:
                logger.warning("Could not mark alert as applied: %s", alert_error)

        return response_data

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error applying policy from alert: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
@router.post("/freeze")
async def freeze_system_with_ttl(
    request: FreezeRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", description="Clé idempotency UUID"),
    current_user: User = Depends(require_role("approver"))
):
    """
    Freeze le système avec TTL et auto-restore - ÉTENDU
    
    Version étoffée avec TTL automatique et traçabilité alerte.
    """
    from services.alerts.idempotency import get_idempotency_manager
    
    try:
        # Préparer réponse pour idempotency  
        response_data = {
            "success": True,
            "message": f"System frozen: {request.reason}",
            "freeze_ttl_minutes": request.ttl_minutes,
            "source_alert_id": request.source_alert_id,
            "frozen_by": current_user.username,
            "auto_unfreeze_at": (datetime.now() + timedelta(minutes=request.ttl_minutes)).isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Vérifier idempotency
        idem_manager = get_idempotency_manager()
        existing_response = idem_manager.check_and_store(idempotency_key, response_data)
        
        if existing_response:
            logger.info(f"Idempotent freeze request detected: {idempotency_key}")
            return existing_response
        
        # Appeler freeze avec TTL
        success = await governance_engine.freeze_system(
            reason=f"{request.reason} (by {current_user.username})",
            duration_minutes=request.ttl_minutes
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="System is already frozen or cannot be frozen")
        
        logger.info(f"System frozen by {current_user.username} for {request.ttl_minutes} minutes with auto-unfreeze")
        
        # Marquer l'alerte comme appliquée si ID fourni
        if request.source_alert_id:
            try:
                from api.alerts_endpoints import alert_engine
                if alert_engine:
                    await alert_engine.mark_alert_applied(request.source_alert_id, current_user.username)
            except Exception as e:
                logger.warning(f"Could not mark alert as applied: {e}")
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error freezing system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate-allocation")
async def validate_allocation_change(request: dict):
    """
    Valide un changement d'allocation avant exécution
    
    Vérifie no-trade zone et estime les coûts d'exécution
    """
    try:
        current_weights = request.get("current_weights", {})
        target_weights = request.get("target_weights", {})
        portfolio_usd = request.get("portfolio_usd", 100000)
        
        # Vérifier no-trade zone
        within_zone, changes = governance_engine.is_change_within_no_trade_zone(current_weights, target_weights)
        
        # Estimer coûts d'exécution
        cost_estimate = governance_engine.estimate_execution_cost(target_weights, portfolio_usd)
        
        # Recommandation basée sur l'analyse
        recommendation = "approve"
        if not within_zone:
            recommendation = "review"  # Changements significatifs
        if not cost_estimate.get('cost_efficient', True):
            recommendation = "reject"  # Coûts trop élevés
        
        return {
            "valid": within_zone,
            "recommendation": recommendation,
            "no_trade_analysis": {
                "within_zone": within_zone,
                "changes": changes
            },
            "cost_analysis": cost_estimate,
            "summary": {
                "total_changes": len([c for c in changes.values() if not c['within_zone']]),
                "largest_change_pct": max([c['change'] for c in changes.values()]) * 100 if changes else 0,
                "estimated_cost_pct": cost_estimate.get('cost_percentage', 0),
                "cost_efficient": cost_estimate.get('cost_efficient', True)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error validating allocation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
