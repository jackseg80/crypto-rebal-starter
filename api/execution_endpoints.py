"""
API Endpoints pour le système d'exécution

Ces endpoints gèrent la validation, l'exécution et le monitoring 
des plans de rebalancement.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Header, Depends
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

from services.execution.execution_engine import execution_engine
from services.execution.exchange_adapter import exchange_registry
from services.execution.governance import Policy, governance_engine
from services.execution.score_registry import get_score_registry
from services.execution.phase_engine import get_phase_engine

# Import RBAC from alerts (shared dependency)
try:
    from api.alerts_endpoints import User, get_current_user, require_role
except ImportError:
    # Fallback si alerts_endpoints pas encore disponible
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

# Nouveaux modèles pour l'unification score/phase
class ScoreComponents(BaseModel):
    """Sous-scores explicatifs du score de décision"""
    trend_regime: float = Field(..., ge=0.0, le=100.0, description="Tendance et régime")
    risk: float = Field(..., ge=0.0, le=100.0, description="Métriques de risque")
    breadth_rotation: float = Field(..., ge=0.0, le=100.0, description="Largeur de marché et rotation")
    sentiment: float = Field(..., ge=0.0, le=100.0, description="Sentiment de marché")

class CanonicalScores(BaseModel):
    """Scores canoniques unifiés"""
    decision: float = Field(..., ge=0.0, le=100.0, description="Score décisionnel principal 0-100")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiance dans la décision")
    contradiction: float = Field(..., ge=0.0, le=1.0, description="Index de contradiction")
    components: ScoreComponents = Field(..., description="Sous-scores explicatifs")
    as_of: str = Field(..., description="Timestamp de calcul")

class PhaseInfo(BaseModel):
    """Information sur la phase de rotation"""
    phase_now: str = Field(..., description="Phase actuelle (btc/eth/large/alt)")
    phase_probs: Dict[str, float] = Field(..., description="Probabilités de chaque phase")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiance dans la détection")
    explain: List[str] = Field(..., description="2-3 explications principales")
    next_likely: Optional[str] = Field(None, description="Phase suivante probable")

class ExecutionPressure(BaseModel):
    """Pression d'exécution court-terme"""
    pressure: float = Field(..., ge=0.0, le=100.0, description="Pression d'exécution 0-100")
    cost_estimate_bps: float = Field(..., description="Coût d'exécution estimé en bps")
    market_impact: str = Field(..., description="Impact marché estimé (low/medium/high)")
    optimal_window_hours: int = Field(..., description="Fenêtre optimale d'exécution")

class MarketSignals(BaseModel):
    """Signaux de marché agrégés"""
    volatility: Dict[str, float] = Field(default_factory=dict, description="Volatilité par asset")
    regime: Dict[str, float] = Field(default_factory=dict, description="Probabilités de régime")
    correlation: Dict[str, float] = Field(default_factory=dict, description="Corrélations clés")
    sentiment: Dict[str, float] = Field(default_factory=dict, description="Sentiment indicators")

class CycleSignals(BaseModel):
    """Signaux de cycle et rotation"""
    btc_cycle: Dict[str, float] = Field(default_factory=dict, description="Position cycle BTC")
    rotation: Dict[str, float] = Field(default_factory=dict, description="Signaux de rotation")

class UnifiedSignals(BaseModel):
    """Bus de signaux unifié"""
    market: MarketSignals = Field(default_factory=MarketSignals, description="Signaux de marché")
    cycle: CycleSignals = Field(default_factory=CycleSignals, description="Signaux de cycle")
    as_of: str = Field(..., description="Timestamp des signaux")

class PortfolioMetrics(BaseModel):
    """Métriques de portefeuille actuelles"""
    var_95_pct: Optional[float] = Field(None, description="VaR 95% en %")
    sharpe_ratio: Optional[float] = Field(None, description="Ratio de Sharpe")
    hhi_concentration: Optional[float] = Field(None, description="Index HHI de concentration")
    avg_correlation: Optional[float] = Field(None, description="Corrélation moyenne pondérée")
    beta_btc: Optional[float] = Field(None, description="Bêta vs BTC")
    exposures: Dict[str, float] = Field(default_factory=dict, description="Expositions par groupe")

class SuggestionIA(BaseModel):
    """Proposition IA canonique (lecture seule)"""
    targets: List[Dict[str, Any]] = Field(..., description="Cibles suggérées")
    rationale: str = Field(..., description="Logique de la suggestion")
    policy_hint: str = Field(..., description="Suggestion de policy (Slow/Normal/Aggressive)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiance dans la suggestion")
    generated_at: str = Field(..., description="Timestamp de génération")

class GovernanceStateResponse(BaseModel):
    """État du système de gouvernance étendu"""
    # Champs existants (compatibilité)
    current_state: str
    mode: str
    last_decision_id: Optional[str] = None
    contradiction_index: float
    ml_signals_timestamp: Optional[str] = None
    active_policy: Optional[Dict[str, Any]] = None
    pending_approvals: int
    next_update_time: Optional[str] = None
    etag: Optional[str] = None  # ETag pour concurrency control
    auto_unfreeze_at: Optional[str] = None  # TTL auto-unfreeze timestamp
    
    # NOUVEAUX CHAMPS - Unification
    scores: Optional[CanonicalScores] = Field(None, description="Scores canoniques unifiés")
    phase: Optional[PhaseInfo] = Field(None, description="Phase de rotation actuelle")
    exec: Optional[ExecutionPressure] = Field(None, description="Pression d'exécution")
    signals: Optional[UnifiedSignals] = Field(None, description="Bus de signaux unifié")
    portfolio: Optional[Dict[str, Any]] = Field(None, description="État du portefeuille")
    suggestion: Optional[SuggestionIA] = Field(None, description="Suggestion IA canonique")

class ApprovalRequest(BaseModel):
    """Requête d'approbation d'une décision"""
    decision_id: str
    approved: bool
    reason: Optional[str] = None

class UnifiedApprovalRequest(BaseModel):
    """Requête d'approbation unifiée pour décisions et plans"""
    resource_type: str = Field(..., pattern="^(decision|plan)$", description="Type: decision ou plan")
    approved: bool = Field(..., description="Approuver (true) ou rejeter (false)")
    approved_by: str = Field(default="system", description="Identifiant de l'approbateur")
    reason: Optional[str] = Field(None, max_length=500, description="Raison de l'approbation/rejet")
    notes: Optional[str] = Field(None, max_length=500, description="Notes additionnelles")

class FreezeRequest(BaseModel):
    """Requête de gel du système avec TTL"""
    reason: str = Field(..., max_length=140, description="Raison du freeze")
    ttl_minutes: int = Field(default=360, ge=15, le=1440, description="TTL auto-unfreeze [15min-24h]")
    source_alert_id: Optional[str] = Field(None, description="ID alerte source si applicable")

class ApplyPolicyRequest(BaseModel):
    """Requete d'application de policy depuis alerte - NOUVEAU"""
    mode: str = Field(..., description="Mode de policy")
    cap_daily: float = Field(..., ge=-1.0, le=1.0, description="Cap quotidien brut (sera clampe +/-20%)")
    ramp_hours: int = Field(..., ge=1, le=72, description="Ramping [1-72h]")
    reason: str = Field(..., max_length=140, description="Raison du changement")
    source_alert_id: Optional[str] = Field(None, description="ID de l'alerte source")
    min_trade: float = Field(default=100.0, ge=10.0, description="Trade minimum en USD")
    slippage_limit_bps: int = Field(default=50, ge=1, le=500, description="Limite slippage [1-500 bps]")
    signals_ttl_seconds: int = Field(default=1800, ge=60, le=7200, description="TTL signaux [60-7200s]")
    plan_cooldown_hours: int = Field(default=24, ge=1, le=168, description="Cooldown plans [1-168h]")
    no_trade_threshold_pct: float = Field(default=0.02, description="No-trade zone brute (sera clampee)")
    execution_cost_bps: int = Field(default=15, ge=-1000, le=1000, description="Cout brut en bps (sera clampe [0-100])")
    notes: Optional[str] = Field(default=None, max_length=280, description="Notes additionnelles")

    @validator('mode')
    def validate_mode(cls, v):
        allowed_modes = ["Slow", "Normal", "Aggressive"]
        if v not in allowed_modes:
            raise ValueError(f"Mode must be one of {allowed_modes}. Use freeze endpoint for Freeze mode.")
        return v

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
        return GovernanceStateResponse(
            # Champs existants (compatibilité)
            current_state=current_state,
            mode=state.governance_mode.value if hasattr(state.governance_mode, 'value') else state.governance_mode,
            last_decision_id=state.current_plan.plan_id if state.current_plan else None,
            contradiction_index=state.signals.contradiction_index if state.signals else 0.0,
            ml_signals_timestamp=state.signals.timestamp.isoformat() if state.signals and hasattr(state.signals, 'timestamp') and state.signals.timestamp else (state.last_update.isoformat() if state.last_update else datetime.now().isoformat()),
            active_policy=state.execution_policy.dict() if state.execution_policy else None,
            pending_approvals=0,  # TODO: Implement decision tracking
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

@router.post("/governance/init-ml")
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
                "blended_score": getattr(signals, 'blended_score', None),
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
        decisions_store = getattr(governance_engine, 'decisions', {}) or {}
        if not isinstance(decisions_store, dict):
            decisions_store = {}

        
        # Filtrer et paginer les décisions
        all_decisions = list(decisions_store.values())
        
        if state_filter:
            all_decisions = [
                d for d in all_decisions
                if getattr(getattr(getattr(d, 'state', None), 'state', None), 'value', '') == state_filter.upper()
            ]
        
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

@router.post("/governance/mode")
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

@router.post("/governance/propose")
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

@router.post("/governance/review/{plan_id}")
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

@router.post("/governance/approve/{resource_id}")
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

@router.post("/governance/activate/{plan_id}")
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

@router.post("/governance/execute/{plan_id}")
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

@router.post("/governance/cancel/{plan_id}")
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

@router.get("/governance/cooldown-status")
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

@router.post("/governance/apply_policy")
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
@router.post("/governance/freeze")
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

@router.post("/governance/validate-allocation")
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

class UpdateSignalsRequest(BaseModel):
    """Payload pour mise à jour partielle des signaux ML (ex: blended score issu du front)"""
    blended_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Blended Decision Score 0-100")

@router.post("/governance/signals/update")
async def update_ml_signals(request: UpdateSignalsRequest):
    """
    Mettre à jour des champs de signaux ML maintenus côté gouvernance.
    Actuellement: accepte `blended_score` (0-100) pour activer les garde-fous backend.
    """
    try:
        # Ensure we have a current state
        state = await governance_engine.get_current_state()
        signals = state.signals

        # Update blended score if provided
        if request.blended_score is not None:
            try:
                # Attach blended score directly to signals model
                setattr(signals, 'blended_score', float(request.blended_score))
            except Exception:
                # Graceful fallback if assignment fails
                pass

        return {
            "success": True,
            "updated": {
                "blended_score": getattr(signals, 'blended_score', None)
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error updating ML signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class RecomputeSignalsRequest(BaseModel):
    """Optionally provide components for blended recomputation.
    If omitted, backend falls back to neutral values.
    """
    ccs_mixte: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    onchain_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)

_LAST_RECOMPUTE_TS = 0.0
_RECOMPUTE_WINDOW = []  # timestamps for burst control (last 10s)
_RECOMPUTE_CACHE = {}   # idempotency cache: key -> {response, ts}

# Phase 2B: Concurrency safety
import asyncio
_RECOMPUTE_LOCK = asyncio.Lock()  # Mutex pour éviter recompute concurrent

@router.post("/governance/signals/recompute")
async def recompute_ml_signals(
    request: RecomputeSignalsRequest,
    current_user: User = Depends(require_role("governance_admin")),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
):
    """
    Recompute blended score server-side from components and attach to governance signals.
    Phase 2B: With concurrency safety mutex
    """
    # Phase 2B: Acquire lock to prevent concurrent recompute
    async with _RECOMPUTE_LOCK:
        try:
            global _LAST_RECOMPUTE_TS, _RECOMPUTE_WINDOW, _RECOMPUTE_CACHE

            # CSRF basic check
            if not x_csrf_token:
                raise HTTPException(status_code=403, detail="missing_csrf_token")

            # Idempotency check
            if idempotency_key and idempotency_key in _RECOMPUTE_CACHE:
                return _RECOMPUTE_CACHE[idempotency_key]["response"]

            # Simple in-process rate-limit: 1 call/sec + burst 5/10s
            now_ts = datetime.now().timestamp()
            user_id = getattr(current_user, 'username', 'unknown')

            if (now_ts - _LAST_RECOMPUTE_TS) < 1.0:
                # Phase 2A: Log rate limit metric
                logger.warning(f"METRICS: recompute_429_total=1 user={user_id} reason=rate_limit")
                raise HTTPException(status_code=429, detail="too_many_requests")
            _LAST_RECOMPUTE_TS = now_ts

            # Burst window
            _RECOMPUTE_WINDOW = [t for t in _RECOMPUTE_WINDOW if (now_ts - t) < 10.0]
            if len(_RECOMPUTE_WINDOW) >= 5:
                # Phase 2A: Log burst limit metric
                logger.warning(f"METRICS: recompute_429_total=1 user={user_id} reason=burst_limit window_size={len(_RECOMPUTE_WINDOW)}")
                raise HTTPException(status_code=429, detail="too_many_requests_burst")
            _RECOMPUTE_WINDOW.append(now_ts)

            state = await governance_engine.get_current_state()
            signals = state.signals

            # Phase 2B: Validate component freshness for 409 NeedsRefresh
            missing_components = []
            if request.ccs_mixte is None:
                missing_components.append("ccs_mixte")
            if request.onchain_score is None:
                missing_components.append("onchain_score")
            if request.risk_score is None:
                missing_components.append("risk_score")

            if missing_components:
                # Phase 2B: 409 si composantes manquantes/non-fraîches
                logger.warning(f"AUDIT_RECOMPUTE_409: user={user_id} missing_components={missing_components}")
                raise HTTPException(
                    status_code=409,
                    detail=f"NeedsRefresh: missing components {missing_components}"
                )

            # Pull components if provided; otherwise fall back to safe neutrals
            ccs_mixte = request.ccs_mixte if request.ccs_mixte is not None else 50.0
            onchain = request.onchain_score if request.onchain_score is not None else 50.0
            risk = request.risk_score if request.risk_score is not None else 50.0

            # Get previous blended score for audit trail
            blended_old = getattr(signals, 'blended_score', None)

            # Strategic blended: 50% CCS Mixte + 30% On-Chain + 20% (100-Risk)
            blended = (ccs_mixte * 0.50) + (onchain * 0.30) + ((100.0 - risk) * 0.20)
            blended = max(0.0, min(100.0, blended))

            try:
                setattr(signals, 'blended_score', float(blended))
                setattr(signals, 'as_of', datetime.now())
            except Exception:
                pass

            # Phase 2A: Enriched structured audit logging with unique calc_timestamp
            policy = state.execution_policy
            backend_status = "ok"  # TODO: derive from actual backend health check
            calc_timestamp = datetime.now()

            try:
                # Check if components are fresh (simulate backend status)
                signals_age = (calc_timestamp - signals.as_of).total_seconds() if signals.as_of else 0
                if signals_age > 3600:  # 1h stale
                    backend_status = "stale"
                if signals_age > 7200:  # 2h error
                    backend_status = "error"
            except:
                pass

            audit_data = {
                "event": "recompute_blended",
                "user": getattr(current_user, 'username', 'unknown'),
                "timestamp": calc_timestamp.isoformat(),
                "calc_timestamp": calc_timestamp.isoformat(),  # Phase 2B: Unique timestamp
                "blended_old": blended_old,
                "blended_new": round(blended, 1),
                "inputs": {
                    "ccs_mixte": ccs_mixte,
                    "onchain": onchain,
                    "risk": risk
                },
                "policy_cap_before": round(policy.cap_daily * 100, 1) if policy else None,
                "policy_cap_after": round(policy.cap_daily * 100, 1) if policy else None,  # Will be updated after policy refresh
                "idempotency_hit": idempotency_key in _RECOMPUTE_CACHE if idempotency_key else False,
                "backend_status": backend_status,
                "rate_limit_window": len(_RECOMPUTE_WINDOW),
                "session_id": idempotency_key[:8] if idempotency_key else "none"
            }

            # Log structured audit entry (JSON for easier parsing)
            logger.info(f"AUDIT_RECOMPUTE: {audit_data}")

            # Also log readable summary
            logger.info(f"recompute_blended user={audit_data['user']} "
                       f"blended={audit_data['blended_old']}→{audit_data['blended_new']} "
                       f"inputs=({ccs_mixte},{onchain},{risk}) "
                       f"backend={backend_status} "
                       f"idempotency={'HIT' if audit_data['idempotency_hit'] else 'NEW'}")

            # Phase 2A: Simple metrics tracking (logs-analytics pattern)
            try:
                # Log metrics for downstream analytics
                logger.info(f"METRICS: recompute_ok_total=1 user={audit_data['user']} backend_status={backend_status}")
                if audit_data['idempotency_hit']:
                    logger.info(f"METRICS: recompute_idempotency_hit_total=1 user={audit_data['user']}")
            except:
                pass

            response_payload = {
                "success": True,
                "blended_score": blended,
                "blended_formula_version": "1.0",
                "timestamp": calc_timestamp.isoformat(),
                "calc_timestamp": calc_timestamp.isoformat()  # Phase 2B: Unique timestamp
            }
            # Idempotency cache
            if idempotency_key:
                try:
                    _RECOMPUTE_CACHE[idempotency_key] = {"response": response_payload, "ts": calc_timestamp.timestamp()}
                except Exception:
                    pass

            return response_payload
        except Exception as e:
            logger.error(f"Error recomputing ML signals: {e}")
            raise HTTPException(status_code=500, detail=str(e))
