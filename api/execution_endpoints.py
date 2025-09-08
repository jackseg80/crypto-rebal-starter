"""
API Endpoints pour le système d'exécution

Ces endpoints gèrent la validation, l'exécution et le monitoring 
des plans de rebalancement.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

from services.execution.execution_engine import execution_engine
from services.execution.exchange_adapter import exchange_registry
from services.execution.governance import governance_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execution", tags=["execution"])

# Models pour les requêtes/réponses
class ExecutionRequest(BaseModel):
    """Requête d'exécution d'un plan"""
    rebalance_actions: List[Dict[str, Any]] = Field(..., description="Actions de rebalancement")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Métadonnées (CCS, etc.)")
    dry_run: bool = Field(default=True, description="Mode simulation")
    max_parallel: int = Field(default=3, description="Ordres en parallèle max")

class ValidationResponse(BaseModel):
    """Réponse de validation"""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    plan_id: str
    total_orders: int
    total_volume: float
    large_orders_count: int

class ExecutionResponse(BaseModel):
    """Réponse d'exécution"""
    success: bool
    plan_id: str
    execution_id: str
    message: str
    estimated_duration_seconds: Optional[float] = None

class ExecutionStatus(BaseModel):
    """Statut d'exécution"""
    plan_id: str
    status: str
    is_active: bool
    total_orders: int
    completed_orders: int
    failed_orders: int
    success_rate: float
    volume_planned: float
    volume_executed: float
    total_fees: float
    execution_time: float
    completion_percentage: float
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class GovernanceStateResponse(BaseModel):
    """État du système de gouvernance"""
    current_state: str
    mode: str
    last_decision_id: Optional[str] = None
    contradiction_index: float
    ml_signals_timestamp: Optional[str] = None
    active_policy: Optional[Dict[str, Any]] = None
    pending_approvals: int
    next_update_time: Optional[str] = None

class ApprovalRequest(BaseModel):
    """Requête d'approbation d'une décision"""
    decision_id: str
    approved: bool
    reason: Optional[str] = None

class FreezeRequest(BaseModel):
    """Requête de gel du système"""
    reason: str
    duration_minutes: Optional[int] = None

# Instance locale du gestionnaire d'ordres pour les endpoints
order_manager = execution_engine.order_manager

@router.post("/validate-plan", response_model=ValidationResponse)
async def validate_execution_plan(request: ExecutionRequest):
    """
    Valider un plan d'exécution avant lancement
    
    Vérifie:
    - Équilibrage des montants
    - Cohérence des données
    - Disponibilité des pairs de trading
    - Limites de taille d'ordre
    """
    try:
        # Créer le plan d'exécution
        plan = order_manager.create_execution_plan(
            rebalance_actions=request.rebalance_actions,
            metadata=request.metadata
        )
        
        # Valider le plan
        validation = order_manager.validate_plan(plan.id)
        
        return ValidationResponse(
            valid=validation["valid"],
            errors=validation["errors"],
            warnings=validation["warnings"],
            plan_id=plan.id,
            total_orders=validation["total_orders"],
            total_volume=validation["total_volume"],
            large_orders_count=validation["large_orders_count"]
        )
        
    except Exception as e:
        logger.error(f"Error validating plan: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/execute-plan", response_model=ExecutionResponse)
async def execute_plan(
    plan_id: str = Query(..., description="ID du plan à exécuter"),
    dry_run: bool = Query(default=True, description="Mode simulation"),
    max_parallel: int = Query(default=3, description="Ordres en parallèle max"),
    background_tasks: BackgroundTasks = None
):
    """
    Exécuter un plan de rebalancement
    
    L'exécution se fait en arrière-plan. Utilisez /execution/status/{plan_id}
    pour suivre le progrès.
    """
    try:
        # Vérifier que le plan existe
        if plan_id not in order_manager.execution_plans:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        plan = order_manager.execution_plans[plan_id]
        
        # Estimer la durée d'exécution
        estimated_duration = len(plan.orders) * 2.0  # 2 secondes par ordre environ
        
        # Lancer l'exécution en arrière-plan
        async def execute_in_background():
            try:
                stats = await execution_engine.execute_plan(
                    plan_id=plan_id,
                    dry_run=dry_run,
                    max_parallel=max_parallel
                )
                logger.info(f"Plan {plan_id} execution completed with {stats.success_rate:.1f}% success rate")
            except Exception as e:
                logger.error(f"Background execution failed for plan {plan_id}: {e}")
        
        background_tasks.add_task(execute_in_background)
        
        return ExecutionResponse(
            success=True,
            plan_id=plan_id,
            execution_id=plan_id,  # Pour l'instant, utiliser le même ID
            message=f"Execution started for {len(plan.orders)} orders",
            estimated_duration_seconds=estimated_duration
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{plan_id}", response_model=ExecutionStatus)
async def get_execution_status(plan_id: str):
    """
    Obtenir le statut d'exécution d'un plan
    
    Retourne le progrès en temps réel, les statistiques d'exécution,
    et le statut de chaque ordre.
    """
    try:
        progress = execution_engine.get_execution_progress(plan_id)
        
        if "error" in progress:
            raise HTTPException(status_code=404, detail=progress["error"])
        
        return ExecutionStatus(**progress)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cancel/{plan_id}")
async def cancel_execution(plan_id: str):
    """
    Annuler l'exécution d'un plan
    
    Les ordres déjà en cours vont se terminer, mais aucun nouvel ordre
    ne sera lancé.
    """
    try:
        success = await execution_engine.cancel_execution(plan_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Execution not found or not active")
        
        return {
            "success": True,
            "message": f"Execution {plan_id} cancelled successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/plans")
async def list_execution_plans(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Lister les plans d'exécution
    
    Retourne la liste des plans avec leur statut actuel.
    """
    try:
        plans_data = []
        
        # Obtenir tous les plans du gestionnaire d'ordres
        all_plans = list(order_manager.execution_plans.values())
        
        # Pagination
        paginated_plans = all_plans[offset:offset + limit]
        
        for plan in paginated_plans:
            plan_status = order_manager.get_plan_status(plan.id)
            plans_data.append(plan_status)
        
        return {
            "plans": plans_data,
            "total": len(all_plans),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error listing plans: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exchanges")
async def list_exchanges():
    """
    Lister les exchanges disponibles
    
    Retourne la liste des adaptateurs d'exchange configurés
    et leur statut de connexion.
    """
    try:
        exchanges = []
        
        for name in exchange_registry.list_exchanges():
            adapter = exchange_registry.get_adapter(name)
            if adapter:
                exchanges.append({
                    "name": name,
                    "type": adapter.type.value,
                    "connected": adapter.connected,
                    "config": {
                        "fee_rate": adapter.config.fee_rate,
                        "min_order_size": adapter.config.min_order_size,
                        "sandbox": adapter.config.sandbox
                    }
                })
        
        return {"exchanges": exchanges}
        
    except Exception as e:
        logger.error(f"Error listing exchanges: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/exchanges/connect")
async def connect_exchanges():
    """
    Connecter tous les exchanges configurés
    
    Tente de se connecter à tous les adaptateurs d'exchange.
    Utile pour initialiser les connexions avant exécution.
    """
    try:
        results = await exchange_registry.connect_all()
        
        success_count = sum(1 for connected in results.values() if connected)
        total_count = len(results)
        
        return {
            "success": True,
            "message": f"Connected to {success_count}/{total_count} exchanges",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error connecting exchanges: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders/{plan_id}")
async def get_plan_orders(plan_id: str):
    """
    Obtenir la liste détaillée des ordres d'un plan
    
    Retourne tous les ordres avec leur statut, résultats d'exécution,
    et détails techniques.
    """
    try:
        if plan_id not in order_manager.execution_plans:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        plan = order_manager.execution_plans[plan_id]
        
        orders_data = []
        for order in plan.orders:
            order_data = {
                "id": order.id,
                "symbol": order.symbol,
                "alias": order.alias,
                "group": order.group,
                "action": order.action,
                "quantity": order.quantity,
                "usd_amount": order.usd_amount,
                "target_price": order.target_price,
                "platform": order.platform,
                "exec_hint": order.exec_hint,
                "priority": order.priority,
                "status": order.status.value,
                "order_type": order.order_type.value,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
                
                # Résultats d'exécution
                "filled_quantity": order.filled_quantity,
                "filled_usd": order.filled_usd,
                "avg_fill_price": order.avg_fill_price,
                "fees": order.fees,
                "error_message": order.error_message
            }
            orders_data.append(order_data)
        
        return {
            "plan_id": plan_id,
            "orders": orders_data,
            "total_orders": len(orders_data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plan orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pipeline-status")
async def get_pipeline_status():
    """
    Obtenir le statut global du pipeline d'exécution
    
    Vue d'ensemble de tous les plans actifs, statistiques globales,
    et santé des exchanges.
    """
    try:
        # Plans actifs
        active_plans = [
            plan_id for plan_id, is_active in execution_engine.active_executions.items()
            if is_active
        ]
        
        # Statistiques globales
        all_plans = order_manager.execution_plans
        total_plans = len(all_plans)
        
        completed_plans = sum(1 for plan in all_plans.values() if plan.status == "completed")
        failed_plans = sum(1 for plan in all_plans.values() if plan.status == "failed")
        
        # Santé des exchanges
        exchange_health = []
        for name in exchange_registry.list_exchanges():
            adapter = exchange_registry.get_adapter(name)
            if adapter:
                exchange_health.append({
                    "name": name,
                    "connected": adapter.connected,
                    "type": adapter.type.value
                })
        
        return {
            "pipeline_status": "active" if active_plans else "idle",
            "active_executions": len(active_plans),
            "active_plan_ids": active_plans,
            "statistics": {
                "total_plans": total_plans,
                "completed_plans": completed_plans,
                "failed_plans": failed_plans,
                "success_rate": (completed_plans / max(total_plans, 1)) * 100
            },
            "exchange_health": exchange_health,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints de Gouvernance
@router.get("/governance/state", response_model=GovernanceStateResponse)
async def get_governance_state():
    """
    Obtenir l'état actuel du système de gouvernance
    
    Retourne le mode actuel (manual/ai_assisted/full_ai), l'état de la machine à états,
    les signaux ML, et les décisions en attente.
    """
    try:
        state = await governance_engine.get_current_state()
        
        # Derive current state from available data
        current_state = "IDLE"
        if state.proposed_plan:
            current_state = "DRAFT"
        elif state.current_plan:
            current_state = "ACTIVE"
        
        return GovernanceStateResponse(
            current_state=current_state,
            mode=state.governance_mode.value if hasattr(state.governance_mode, 'value') else state.governance_mode,
            last_decision_id=state.current_plan.plan_id if state.current_plan else None,
            contradiction_index=state.signals.contradiction_index if state.signals else 0.0,
            ml_signals_timestamp=state.signals.timestamp.isoformat() if state.signals and hasattr(state.signals, 'timestamp') and state.signals.timestamp else None,
            active_policy=state.execution_policy.dict() if state.execution_policy else None,
            pending_approvals=0,  # TODO: Implement decision tracking
            next_update_time=state.last_update.isoformat() if state.last_update else None
        )
        
    except Exception as e:
        logger.error(f"Error getting governance state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/governance/approve")
async def approve_decision(request: ApprovalRequest):
    """
    Approuver ou rejeter une décision en attente
    
    En mode manuel ou ai_assisted, les décisions doivent être approuvées
    avant d'être exécutées.
    """
    try:
        success = await governance_engine.approve_decision(
            decision_id=request.decision_id,
            approved=request.approved,
            reason=request.reason
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Decision not found or not in approvalable state")
        
        return {
            "success": True,
            "message": f"Decision {request.decision_id} {'approved' if request.approved else 'rejected'}",
            "decision_id": request.decision_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/governance/freeze")
async def freeze_system(request: FreezeRequest):
    """
    Geler le système de gouvernance
    
    Stoppe toutes les décisions automatiques et passe en mode manuel.
    Utilisé en cas d'urgence ou de conditions de marché exceptionnelles.
    """
    try:
        success = await governance_engine.freeze_system(
            reason=request.reason,
            duration_minutes=request.duration_minutes
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="System is already frozen or cannot be frozen")
        
        return {
            "success": True,
            "message": f"System frozen: {request.reason}",
            "duration_minutes": request.duration_minutes,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error freezing system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/governance/unfreeze")
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

@router.get("/governance/signals")
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
        
        return {
            "signals": {
                "volatility": signals.volatility,
                "regime": signals.regime,
                "correlation": signals.correlation,  
                "sentiment": signals.sentiment,
                "decision_score": signals.decision_score,
                "confidence": signals.confidence,
                "contradiction_index": signals.contradiction_index,
                "sources_used": signals.sources_used,
                "timestamp": signals.timestamp.isoformat() if hasattr(signals, 'timestamp') and signals.timestamp else None
            },
            "derived_policy": None,  # TODO: Implement derived policy in MLSignals
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting ML signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/governance/decisions")
async def list_decisions(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    state_filter: Optional[str] = Query(default=None)
):
    """
    Lister les décisions de gouvernance
    
    Retourne l'historique des décisions avec leur état, métadonnées,
    et résultats d'exécution.
    """
    try:
        decisions_data = []
        
        # Filtrer et paginer les décisions
        all_decisions = list(governance_engine.decisions.values())
        
        if state_filter:
            all_decisions = [d for d in all_decisions if d.state.state.value == state_filter.upper()]
        
        paginated_decisions = all_decisions[offset:offset + limit]
        
        for decision in paginated_decisions:
            decision_data = {
                "id": decision.id,
                "plan_id": decision.plan_id,
                "state": decision.state.state.value,
                "mode": decision.state.mode.value,
                "contradiction_index": decision.state.contradiction_index,
                "created_at": decision.created_at.isoformat(),
                "approved_at": decision.approved_at.isoformat() if decision.approved_at else None,
                "executed_at": decision.executed_at.isoformat() if decision.executed_at else None,
                "targets": [target.dict() for target in decision.targets],
                "active_policy": decision.state.active_policy.dict() if decision.state.active_policy else None,
                "approval_reason": decision.approval_reason,
                "execution_stats": decision.execution_stats
            }
            decisions_data.append(decision_data)
        
        return {
            "decisions": decisions_data,
            "total": len(all_decisions),
            "limit": limit,
            "offset": offset,
            "state_filter": state_filter
        }
        
    except Exception as e:
        logger.error(f"Error listing decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))