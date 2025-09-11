"""
Governance Engine pour Decision Engine Unifié

Ce module centralise la gouvernance des décisions d'allocation :
- Single-writer strict pour les targets
- State machine governance (manual/ai_assisted/full_ai)
- Policy d'exécution unifiée (mode/cap/ramp)
- Centralisation contradiction index depuis composite-score-v2.js
"""

from typing import Dict, List, Any, Optional, Literal, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging
import asyncio
import httpx

# Import real ML orchestrator
try:
    from ..ml.orchestrator import get_orchestrator
    ML_ORCHESTRATOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"ML Orchestrator not available: {e}")
    ML_ORCHESTRATOR_AVAILABLE = False

logger = logging.getLogger(__name__)

# Types pour la governance
GovernanceMode = Literal["manual", "ai_assisted", "full_ai", "freeze"]
PlanStatus = Literal["DRAFT", "REVIEWED", "APPROVED", "ACTIVE", "EXECUTED", "CANCELLED"]
ExecMode = Literal["Freeze", "Slow", "Normal", "Aggressive"]

class Target(BaseModel):
    """Cible d'allocation pour un groupe/asset"""
    symbol: str = Field(..., description="Symbole ou groupe (BTC, ETH, Stablecoins, etc.)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Poids d'allocation [0-1]")
    
class Policy(BaseModel):
    """Politique d'exécution dérivée des signaux ML + gouvernance"""
    mode: ExecMode = Field(default="Normal", description="Mode d'exécution")
    cap_daily: float = Field(default=0.08, ge=0.01, le=0.50, description="Cap quotidien [1-50%]")
    ramp_hours: int = Field(default=12, ge=1, le=72, description="Ramping sur N heures")
    min_trade: float = Field(default=100.0, ge=10.0, description="Trade minimum en USD")
    slippage_limit_bps: int = Field(default=50, ge=1, le=500, description="Limite slippage [1-500 bps]")
    
    # TTL vs Cooldown separation (critique essentielle)
    signals_ttl_seconds: int = Field(default=1800, ge=60, le=7200, description="TTL des signaux ML [1min-2h]")
    plan_cooldown_hours: int = Field(default=24, ge=1, le=168, description="Cooldown publication plans [1-168h]")
    
    # No-trade zone et coûts
    no_trade_threshold_pct: float = Field(default=0.02, ge=0.001, le=0.10, description="Zone no-trade [0.1-10%]")
    execution_cost_bps: int = Field(default=15, ge=1, le=100, description="Coût d'execution estimé [1-100 bps]")
    
    notes: Optional[str] = Field(default=None, description="Notes explicatives")

class MLSignals(BaseModel):
    """Signaux ML agrégés pour la prise de décision"""
    as_of: datetime = Field(default_factory=datetime.now, description="Timestamp des signaux")
    
    # Signaux individuels
    volatility: Dict[str, float] = Field(default_factory=dict, description="Vol forecast par asset")
    regime: Dict[str, float] = Field(default_factory=dict, description="Régime probabilities")
    correlation: Dict[str, Any] = Field(default_factory=dict, description="Corrélation metrics")
    sentiment: Dict[str, float] = Field(default_factory=dict, description="Sentiment indicators")
    
    # Signaux dérivés
    decision_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Score décisionnel global")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confiance dans la décision")
    contradiction_index: float = Field(default=0.0, ge=0.0, le=1.0, description="Index de contradiction")
    
    # Metadata
    ttl_seconds: int = Field(default=1800, ge=60, description="TTL des signaux")
    sources_used: List[str] = Field(default_factory=list, description="Sources ML utilisées")

class DecisionPlan(BaseModel):
    """Plan de décision avec targets et métadonnées"""
    plan_id: str = Field(..., description="ID unique du plan")
    created_at: datetime = Field(default_factory=datetime.now, description="Date de création")
    status: PlanStatus = Field(default="DRAFT", description="Statut du plan")
    version: int = Field(default=1, ge=1, description="Version pour concurrency")
    etag: str = Field(..., description="ETag pour optimistic concurrency")
    
    # State transition timestamps
    reviewed_at: Optional[datetime] = Field(default=None, description="Date de review")
    approved_at: Optional[datetime] = Field(default=None, description="Date d'approbation")
    activated_at: Optional[datetime] = Field(default=None, description="Date d'activation")
    executed_at: Optional[datetime] = Field(default=None, description="Date d'exécution")
    cancelled_at: Optional[datetime] = Field(default=None, description="Date d'annulation")
    
    # Contenu du plan
    targets: List[Target] = Field(..., description="Cibles d'allocation")
    governance_mode: GovernanceMode = Field(..., description="Mode de gouvernance")
    
    # Constraints et validation
    total_weight: float = Field(default=1.0, description="Somme des poids (doit = 1.0)")
    risk_budget: Optional[float] = Field(default=None, description="Budget de risque")
    non_removable: List[str] = Field(default_factory=list, description="Assets non supprimables")
    
    # State transition metadata
    created_by: str = Field(default="system", description="Créateur du plan")
    reviewed_by: Optional[str] = Field(default=None, description="Reviewer du plan")
    approved_by: Optional[str] = Field(default=None, description="Approbateur")
    notes: Optional[str] = Field(default=None, description="Notes du plan")
    review_notes: Optional[str] = Field(default=None, description="Notes de review")
    approval_notes: Optional[str] = Field(default=None, description="Notes d'approbation")

class DecisionState(BaseModel):
    """État global du Decision Engine"""
    # Plan actuel
    current_plan: Optional[DecisionPlan] = Field(default=None, description="Plan actuellement actif")
    proposed_plan: Optional[DecisionPlan] = Field(default=None, description="Plan proposé en attente")
    
    # Governance
    governance_mode: GovernanceMode = Field(default="manual", description="Mode de gouvernance global")
    execution_policy: Policy = Field(default_factory=Policy, description="Politique d'exécution")
    
    # Signaux ML
    signals: MLSignals = Field(default_factory=MLSignals, description="Signaux ML actuels")
    
    # Métadonnées
    last_update: datetime = Field(default_factory=datetime.now, description="Dernière MAJ")
    system_status: str = Field(default="operational", description="Statut système")
    auto_unfreeze_at: Optional[datetime] = Field(default=None, description="Auto-unfreeze programmé")


class GovernanceEngine:
    """
    Moteur de gouvernance centralisé pour les décisions d'allocation
    
    Responsabilités :
    - Centralise la logique de contradiction depuis composite-score-v2.js
    - Extrait la policy logic depuis UnifiedInsights  
    - Gère les transitions d'état DRAFT→ACTIVE
    - Interface unique avec les signaux ML
    """
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url.rstrip("/")
        self.current_state = DecisionState()
        
        # TTL vs Cooldown separation (critique essentielle)
        self._last_signals_fetch = datetime.min
        self._last_plan_publication = datetime.min
        
        # Default policy values - will be overridden by derived policy
        self._signals_ttl_seconds = 1800  # 30 minutes - signaux peuvent être rafraîchis
        self._plan_cooldown_hours = 24     # 24 heures - nouvelles publications limitées
        
        logger.info("GovernanceEngine initialized with TTL/cooldown separation")
    
    async def get_current_state(self) -> DecisionState:
        """
        Retourne l'état actuel du Decision Engine
        Agrège : store local + signaux ML + policy dérivée
        Sépare TTL (signaux) et cooldown (plans)
        """
        try:
            # Check auto-unfreeze TTL
            await self.check_auto_unfreeze()
            
            # Dérive la policy AVANT de vérifier les signaux (pour obtenir TTL/cooldown actualisés)
            self.current_state.execution_policy = self._derive_execution_policy()
            
            # TTL check : Refresh signals si TTL expiré
            signals_expired = (datetime.now() - self._last_signals_fetch).total_seconds() > self.current_state.execution_policy.signals_ttl_seconds
            if signals_expired:
                await self._refresh_ml_signals()
                logger.debug(f"ML signals refreshed (TTL {self.current_state.execution_policy.signals_ttl_seconds}s expired)")
            
            # Cooldown check : Vérifier si on peut publier de nouveaux plans
            plan_cooldown_active = (datetime.now() - self._last_plan_publication).total_seconds() < (self.current_state.execution_policy.plan_cooldown_hours * 3600)
            
            # Actualiser l'état global
            self.current_state.last_update = datetime.now()
            
            logger.debug(f"Current governance state: mode={self.current_state.governance_mode}, "
                        f"contradiction={self.current_state.signals.contradiction_index:.3f}, "
                        f"signals_fresh={(not signals_expired)}, cooldown_active={plan_cooldown_active}")
            
            return self.current_state
            
        except Exception as e:
            logger.error(f"Error getting current state: {e}")
            # Fallback : état par défaut safe avec policy conservatrice
            return DecisionState(
                governance_mode="manual",
                execution_policy=Policy(
                    mode="Freeze", 
                    cap_daily=0.01,
                    signals_ttl_seconds=300,  # TTL court en cas d'erreur
                    plan_cooldown_hours=48    # Cooldown long en cas d'erreur
                ),
                system_status="error"
            )
    
    async def _refresh_ml_signals(self) -> None:
        """Refresh les signaux ML depuis le vrai MLOrchestrator ou fallback vers endpoints"""
        try:
            if ML_ORCHESTRATOR_AVAILABLE:
                # Use real ML orchestrator
                orchestrator = get_orchestrator()
                
                # Get unified predictions from all models
                ml_predictions = await orchestrator.get_unified_predictions(
                    symbols=['BTC', 'ETH', 'SOL'],  # Main portfolio assets
                    horizons=[1, 7, 30]
                )
                
                if 'error' not in ml_predictions:
                    # Extract signals from real ML models
                    self.current_state.signals = MLSignals(
                        as_of=datetime.now(),
                        volatility=self._extract_real_volatility_signals(ml_predictions),
                        regime=self._extract_real_regime_signals(ml_predictions),
                        correlation=self._extract_real_correlation_signals(ml_predictions),
                        sentiment=self._extract_real_sentiment_signals(ml_predictions),
                        decision_score=ml_predictions.get('ensemble', {}).get('confidence_level', 0.6),
                        confidence=self._calculate_real_confidence(ml_predictions),
                        contradiction_index=self._compute_real_contradiction_index(ml_predictions),
                        sources_used=list(ml_predictions.get('models', {}).keys())
                    )
                    
                    self._last_signals_fetch = datetime.now()
                    logger.debug("Real ML signals refreshed successfully")
                    return
                else:
                    logger.warning(f"ML orchestrator error: {ml_predictions.get('error')}")
            
            # Fallback to API endpoint
            async with httpx.AsyncClient() as client:
                signals_response = await client.get(f"{self.api_base_url}/api/ml/status", timeout=5.0)
                if signals_response.status_code == 200:
                    ml_status = signals_response.json()
                    
                    # Fallback to simulated signals
                    self.current_state.signals = MLSignals(
                        as_of=datetime.now(),
                        volatility=self._extract_volatility_signals(ml_status),
                        regime=self._extract_regime_signals(ml_status),
                        correlation=self._extract_correlation_signals(ml_status),
                        sentiment=self._extract_sentiment_signals(ml_status),
                        decision_score=0.6,
                        confidence=0.75,
                        contradiction_index=self._compute_contradiction_index(ml_status),
                        sources_used=["volatility_fallback", "regime_fallback", "correlation_fallback", "sentiment_fallback"]
                    )
                    
                    self._last_signals_fetch = datetime.now()
                    logger.debug("ML signals refreshed via fallback API")
                    
        except Exception as e:
            logger.warning(f"Failed to refresh ML signals: {e}")
            # Keep previous signals or create minimal default
            if not self.current_state.signals:
                self.current_state.signals = MLSignals(
                    as_of=datetime.now(),
                    decision_score=0.5,
                    confidence=0.5,
                    contradiction_index=0.3,
                    sources_used=["fallback"]
                )
    
    def _compute_contradiction_index(self, ml_status: Dict[str, Any]) -> float:
        """
        Centralise le calcul de contradiction depuis composite-score-v2.js
        
        Logique basée sur :
        - Conflits vol/regime (high vol + bull regime = contradiction)
        - Sentiment vs regime (extreme fear + bull = contradiction)
        - Corrélations vs diversification
        """
        try:
            contradictions = 0.0
            total_checks = 0.0
            
            # Check 1: Volatilité vs Régime
            vol_high = any(v > 0.15 for v in self._extract_volatility_signals(ml_status).values())
            regime_bull = self._extract_regime_signals(ml_status).get("bull", 0.0) > 0.6
            
            if vol_high and regime_bull:
                contradictions += 0.3  # High vol + bull regime = contradiction
            total_checks += 1.0
            
            # Check 2: Sentiment vs Régime  
            sentiment_data = self._extract_sentiment_signals(ml_status)
            sentiment_extreme_fear = sentiment_data.get("fear_greed", 50) < 25
            sentiment_extreme_greed = sentiment_data.get("fear_greed", 50) > 75
            
            if (sentiment_extreme_greed and not regime_bull) or (sentiment_extreme_fear and regime_bull):
                contradictions += 0.25
            total_checks += 1.0
            
            # Check 3: Corrélations élevées (risque systémique)
            corr_data = self._extract_correlation_signals(ml_status)
            high_correlation = corr_data.get("avg_correlation", 0.0) > 0.7
            
            if high_correlation:
                contradictions += 0.2  # Faible diversification
            total_checks += 1.0
            
            # Normaliser [0-1]
            contradiction_index = min(1.0, contradictions / max(1.0, total_checks)) if total_checks > 0 else 0.0
            
            logger.debug(f"Contradiction index computed: {contradiction_index:.3f} "
                        f"(vol_high={vol_high}, regime_bull={regime_bull}, high_corr={high_correlation})")
            
            return contradiction_index
            
        except Exception as e:
            logger.warning(f"Error computing contradiction index: {e}")
            return 0.5  # Valeur neutre par défaut
    
    def _derive_execution_policy(self) -> Policy:
        """
        Dérive la politique d'exécution depuis les signaux ML
        Extrait la logique cap/mode depuis UnifiedInsights
        """
        try:
            signals = self.current_state.signals
            contradiction = signals.contradiction_index
            confidence = signals.confidence
            
            # Logique extraite d'UnifiedInsights (cap ±3/7/12%)
            if contradiction > 0.7 or confidence < 0.3:
                # Mode défensif
                mode = "Freeze" if contradiction > 0.8 else "Slow"
                cap = max(0.03, 0.12 - contradiction * 0.09)  # 3-12% inversé
                ramp_hours = 48
                
            elif contradiction > 0.5 or confidence < 0.6:
                # Mode prudent
                mode = "Slow"
                cap = 0.07  # 7% comme dans UnifiedInsights "Rotate"
                ramp_hours = 24
                
            elif confidence > 0.8 and contradiction < 0.2:
                # Mode agressif
                mode = "Aggressive" 
                cap = 0.12  # 12% comme dans UnifiedInsights "Deploy"
                ramp_hours = 6
                
            else:
                # Mode normal
                mode = "Normal"
                cap = 0.08  # 8% baseline
                ramp_hours = 12
            
            # Ajustements selon governance mode
            if self.current_state.governance_mode == "freeze":
                mode = "Freeze"
                cap = 0.01
                
            # Ajuster no-trade zone et coûts selon la volatilité
            vol_signals = signals.volatility
            avg_volatility = sum(vol_signals.values()) / len(vol_signals) if vol_signals else 0.15
            
            # No-trade zone plus large si volatilité élevée (évite le churning)
            no_trade_threshold = min(0.10, 0.02 + avg_volatility * 0.5)  # 2-10% selon volatilité
            
            # Coûts d'exécution estimés (spread + slippage + frais)
            execution_cost = 15 + (avg_volatility * 100)  # 15-30 bps selon volatilité
            
            policy = Policy(
                mode=mode,
                cap_daily=cap,
                ramp_hours=ramp_hours,
                min_trade=100.0,
                slippage_limit_bps=50,
                signals_ttl_seconds=self._signals_ttl_seconds,
                plan_cooldown_hours=self._plan_cooldown_hours,
                no_trade_threshold_pct=no_trade_threshold,
                execution_cost_bps=min(100, int(execution_cost)),  # Cap à 100 bps
                notes=f"Derived from ML signals: contradiction={contradiction:.2f}, confidence={confidence:.2f}, vol={avg_volatility:.3f}"
            )
            
            logger.debug(f"Execution policy derived: mode={mode}, cap={cap:.1%}, "
                        f"contradiction={contradiction:.3f}")
            
            return policy
            
        except Exception as e:
            logger.error(f"Error deriving execution policy: {e}")
            return Policy(mode="Freeze", cap_daily=0.01, notes="Error fallback")
    
    def _extract_volatility_signals(self, ml_status: Dict[str, Any]) -> Dict[str, float]:
        """Extrait les signaux de volatilité depuis le ML status"""
        try:
            pipeline = ml_status.get("pipeline_status", {})
            vol_models = pipeline.get("volatility_models", {})
            
            # Simulation basée sur le nombre de modèles chargés
            loaded_count = vol_models.get("models_loaded", 0)
            if loaded_count > 0:
                return {
                    "BTC": 0.08 + (loaded_count * 0.005),  # Volatilité simulée
                    "ETH": 0.12 + (loaded_count * 0.007),
                    "SOL": 0.15 + (loaded_count * 0.010)
                }
            return {}
            
        except Exception as e:
            logger.warning(f"Error extracting volatility signals: {e}")
            return {}
    
    def _extract_regime_signals(self, ml_status: Dict[str, Any]) -> Dict[str, float]:
        """Extrait les signaux de régime depuis le ML status"""
        try:
            pipeline = ml_status.get("pipeline_status", {})
            regime_models = pipeline.get("regime_models", {})
            
            if regime_models.get("model_loaded", False):
                return {
                    "bull": 0.4,
                    "neutral": 0.35,
                    "bear": 0.25
                }
            return {"neutral": 1.0}
            
        except Exception as e:
            logger.warning(f"Error extracting regime signals: {e}")
            return {"neutral": 1.0}
    
    def _extract_correlation_signals(self, ml_status: Dict[str, Any]) -> Dict[str, Any]:
        """Extrait les signaux de corrélation depuis le ML status"""
        try:
            pipeline = ml_status.get("pipeline_status", {})
            cache_stats = pipeline.get("cache_stats", {})
            
            models_loaded = cache_stats.get("cached_models", 0)
            avg_correlation = min(0.8, 0.4 + (models_loaded * 0.05))
            
            return {
                "avg_correlation": avg_correlation,
                "systemic_risk": "medium" if avg_correlation > 0.6 else "low"
            }
            
        except Exception as e:
            logger.warning(f"Error extracting correlation signals: {e}")
            return {"avg_correlation": 0.5, "systemic_risk": "unknown"}
    
    def _extract_sentiment_signals(self, ml_status: Dict[str, Any]) -> Dict[str, float]:
        """Extrait les signaux de sentiment (Fear & Greed, etc.)"""
        try:
            # Simulation stable basée sur l'heure pour éviter le bruit
            import time
            hour_seed = int(time.time() / 3600) % 100
            
            fear_greed = 45 + (hour_seed % 30)  # 45-75, stable par heure
            
            return {
                "fear_greed": fear_greed,
                "sentiment_score": (fear_greed - 50) / 50  # [-1, 1]
            }
            
        except Exception as e:
            logger.warning(f"Error extracting sentiment signals: {e}")
            return {"fear_greed": 50, "sentiment_score": 0.0}

    async def get_current_ml_signals(self) -> Optional[MLSignals]:
        """Retourne les signaux ML actuels (wrapper pour endpoints)"""
        try:
            state = await self.get_current_state()
            return state.signals if state else None
        except Exception as e:
            logger.error(f"Error getting current ML signals: {e}")
            return None

    async def freeze_system(self, reason: str, duration_minutes: Optional[int] = None) -> bool:
        """Freeze le système (mode d'urgence) avec TTL optionnel"""
        try:
            logger.info(f"Freezing system: {reason} (TTL: {duration_minutes}min)" if duration_minutes else f"Freezing system: {reason}")
            
            # Set governance mode to freeze
            self.current_state.governance_mode = "freeze"
            self.current_state.system_status = "frozen"
            self.current_state.last_update = datetime.now()
            
            # Store auto-unfreeze time if TTL specified
            if duration_minutes:
                self.current_state.auto_unfreeze_at = datetime.now() + timedelta(minutes=duration_minutes)
                logger.info(f"Auto-unfreeze scheduled for: {self.current_state.auto_unfreeze_at}")
            else:
                self.current_state.auto_unfreeze_at = None
            
            # Update execution policy to freeze mode
            self.current_state.execution_policy = Policy(
                mode="Freeze",
                cap_daily=0.01,
                ramp_hours=1,
                cooldown_hours=168,  # 1 week
                notes=f"System frozen: {reason}" + (f" (auto-unfreeze: {duration_minutes}min)" if duration_minutes else "")
            )
            
            logger.info("System successfully frozen")
            return True
            
        except Exception as e:
            logger.error(f"Error freezing system: {e}")
            return False

    async def unfreeze_system(self) -> bool:
        """Unfreeze le système"""
        try:
            logger.info("Unfreezing system")
            
            # Restore normal governance mode
            self.current_state.governance_mode = "manual"
            self.current_state.system_status = "operational"
            self.current_state.last_update = datetime.now()
            self.current_state.auto_unfreeze_at = None  # Clear auto-unfreeze
            
            # Derive normal execution policy
            self.current_state.execution_policy = self._derive_execution_policy()
            
            logger.info("System successfully unfrozen")
            return True
            
        except Exception as e:
            logger.error(f"Error unfreezing system: {e}")
            return False

    async def check_auto_unfreeze(self) -> bool:
        """Vérifie et exécute auto-unfreeze si TTL écoulé"""
        try:
            if (self.current_state.governance_mode == "freeze" and 
                self.current_state.auto_unfreeze_at and 
                datetime.now() >= self.current_state.auto_unfreeze_at):
                
                logger.info("Auto-unfreeze TTL expired, unfreezing system")
                await self.unfreeze_system()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking auto-unfreeze: {e}")
            return False

    async def review_plan(self, plan_id: str, reviewed_by: str, notes: Optional[str] = None, expected_etag: Optional[str] = None) -> bool:
        """Transition DRAFT → REVIEWED with optional ETag validation"""
        try:
            plan = self._find_plan_by_id(plan_id)
            if not plan:
                logger.error(f"Plan {plan_id} not found")
                return False
            
            # ETag validation if provided
            if expected_etag and not self.validate_etag(plan_id, expected_etag):
                logger.error(f"ETag validation failed for plan {plan_id}")
                return False
                
            if plan.status != "DRAFT":
                logger.error(f"Plan {plan_id} is not in DRAFT state (current: {plan.status})")
                return False
            
            # Update plan state
            plan.status = "REVIEWED"
            plan.reviewed_at = datetime.now()
            plan.reviewed_by = reviewed_by
            plan.review_notes = notes
            plan.version += 1
            plan.etag = f"etag_{datetime.now().timestamp()}"
            
            self.current_state.last_update = datetime.now()
            logger.info(f"Plan {plan_id} reviewed by {reviewed_by}")
            return True
            
        except Exception as e:
            logger.error(f"Error reviewing plan {plan_id}: {e}")
            return False

    async def approve_plan(self, plan_id: str, approved_by: str, notes: Optional[str] = None, expected_etag: Optional[str] = None) -> bool:
        """Transition REVIEWED → APPROVED with optional ETag validation"""
        try:
            plan = self._find_plan_by_id(plan_id)
            if not plan:
                logger.error(f"Plan {plan_id} not found")
                return False
            
            # ETag validation if provided
            if expected_etag and not self.validate_etag(plan_id, expected_etag):
                logger.error(f"ETag validation failed for plan {plan_id}")
                return False
                
            if plan.status != "REVIEWED":
                logger.error(f"Plan {plan_id} is not in REVIEWED state (current: {plan.status})")
                return False
            
            # Update plan state
            plan.status = "APPROVED"
            plan.approved_at = datetime.now()
            plan.approved_by = approved_by
            plan.approval_notes = notes
            plan.version += 1
            plan.etag = f"etag_{datetime.now().timestamp()}"
            
            self.current_state.last_update = datetime.now()
            logger.info(f"Plan {plan_id} approved by {approved_by}")
            return True
            
        except Exception as e:
            logger.error(f"Error approving plan {plan_id}: {e}")
            return False

    async def activate_plan(self, plan_id: str, expected_etag: Optional[str] = None) -> bool:
        """Transition APPROVED → ACTIVE with optional ETag validation"""
        try:
            plan = self._find_plan_by_id(plan_id)
            if not plan:
                logger.error(f"Plan {plan_id} not found")
                return False
            
            # ETag validation if provided
            if expected_etag and not self.validate_etag(plan_id, expected_etag):
                logger.error(f"ETag validation failed for plan {plan_id}")
                return False
                
            if plan.status != "APPROVED":
                logger.error(f"Plan {plan_id} is not in APPROVED state (current: {plan.status})")
                return False
            
            # Deactivate current active plan if any
            if self.current_state.current_plan and self.current_state.current_plan.status == "ACTIVE":
                self.current_state.current_plan.status = "EXECUTED"
                self.current_state.current_plan.executed_at = datetime.now()
                logger.info(f"Previous plan {self.current_state.current_plan.plan_id} marked as executed")
            
            # Activate new plan
            plan.status = "ACTIVE"
            plan.activated_at = datetime.now()
            plan.version += 1
            plan.etag = f"etag_{datetime.now().timestamp()}"
            
            # Move to current plan
            self.current_state.current_plan = plan
            if self.current_state.proposed_plan and self.current_state.proposed_plan.plan_id == plan_id:
                self.current_state.proposed_plan = None
            
            self.current_state.last_update = datetime.now()
            logger.info(f"Plan {plan_id} activated")
            return True
            
        except Exception as e:
            logger.error(f"Error activating plan {plan_id}: {e}")
            return False

    async def execute_plan(self, plan_id: str, expected_etag: Optional[str] = None) -> bool:
        """Transition ACTIVE → EXECUTED with optional ETag validation"""
        try:
            plan = self._find_plan_by_id(plan_id)
            if not plan:
                logger.error(f"Plan {plan_id} not found")
                return False
            
            # ETag validation if provided
            if expected_etag and not self.validate_etag(plan_id, expected_etag):
                logger.error(f"ETag validation failed for plan {plan_id}")
                return False
                
            if plan.status != "ACTIVE":
                logger.error(f"Plan {plan_id} is not in ACTIVE state (current: {plan.status})")
                return False
            
            # Update plan state
            plan.status = "EXECUTED"
            plan.executed_at = datetime.now()
            plan.version += 1
            plan.etag = f"etag_{datetime.now().timestamp()}"
            
            self.current_state.last_update = datetime.now()
            logger.info(f"Plan {plan_id} marked as executed")
            return True
            
        except Exception as e:
            logger.error(f"Error executing plan {plan_id}: {e}")
            return False

    async def cancel_plan(self, plan_id: str, cancelled_by: str, reason: Optional[str] = None, expected_etag: Optional[str] = None) -> bool:
        """Cancel plan from any state → CANCELLED with optional ETag validation"""
        try:
            plan = self._find_plan_by_id(plan_id)
            if not plan:
                logger.error(f"Plan {plan_id} not found")
                return False
            
            # ETag validation if provided
            if expected_etag and not self.validate_etag(plan_id, expected_etag):
                logger.error(f"ETag validation failed for plan {plan_id}")
                return False
                
            if plan.status in ["EXECUTED", "CANCELLED"]:
                logger.error(f"Plan {plan_id} cannot be cancelled (current: {plan.status})")
                return False
            
            # Update plan state
            plan.status = "CANCELLED"
            plan.cancelled_at = datetime.now()
            plan.notes = f"{plan.notes or ''} | Cancelled by {cancelled_by}: {reason or 'No reason provided'}"
            plan.version += 1
            plan.etag = f"etag_{datetime.now().timestamp()}"
            
            # Remove from active positions if needed
            if self.current_state.current_plan and self.current_state.current_plan.plan_id == plan_id:
                self.current_state.current_plan = None
            if self.current_state.proposed_plan and self.current_state.proposed_plan.plan_id == plan_id:
                self.current_state.proposed_plan = None
            
            self.current_state.last_update = datetime.now()
            logger.info(f"Plan {plan_id} cancelled by {cancelled_by}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling plan {plan_id}: {e}")
            return False

    def _find_plan_by_id(self, plan_id: str) -> Optional[DecisionPlan]:
        """Helper to find plan by ID in current state"""
        if self.current_state.current_plan and self.current_state.current_plan.plan_id == plan_id:
            return self.current_state.current_plan
        if self.current_state.proposed_plan and self.current_state.proposed_plan.plan_id == plan_id:
            return self.current_state.proposed_plan
        return None

    def validate_etag(self, plan_id: str, provided_etag: str) -> bool:
        """
        Valide l'ETag pour le contrôle de concurrence optimiste
        Retourne True si l'ETag correspond, False sinon
        """
        plan = self._find_plan_by_id(plan_id)
        if not plan:
            logger.warning(f"Plan {plan_id} not found for ETag validation")
            return False
        
        current_etag = plan.etag
        if current_etag != provided_etag:
            logger.warning(f"ETag mismatch for plan {plan_id}: expected {current_etag}, got {provided_etag}")
            return False
        
        logger.debug(f"ETag validation successful for plan {plan_id}")
        return True

    def is_change_within_no_trade_zone(self, current_weights: Dict[str, float], target_weights: Dict[str, float]) -> Tuple[bool, Dict[str, float]]:
        """
        Vérifie si les changements d'allocation respectent la no-trade zone
        Retourne: (within_zone, changes_dict)
        """
        try:
            policy = self.current_state.execution_policy
            no_trade_threshold = policy.no_trade_threshold_pct if policy else 0.02
            
            changes = {}
            all_within_zone = True
            
            # Vérifier tous les assets (union des deux dictionnaires)
            all_symbols = set(current_weights.keys()) | set(target_weights.keys())
            
            for symbol in all_symbols:
                current_weight = current_weights.get(symbol, 0.0)
                target_weight = target_weights.get(symbol, 0.0)
                change = abs(target_weight - current_weight)
                
                changes[symbol] = {
                    'current': current_weight,
                    'target': target_weight,
                    'change': change,
                    'within_zone': change <= no_trade_threshold
                }
                
                if change > no_trade_threshold:
                    all_within_zone = False
            
            logger.debug(f"No-trade zone check: threshold={no_trade_threshold:.1%}, all_within={all_within_zone}")
            return all_within_zone, changes
            
        except Exception as e:
            logger.error(f"Error checking no-trade zone: {e}")
            return False, {}

    def estimate_execution_cost(self, target_weights: Dict[str, float], current_portfolio_usd: float = 100000) -> Dict[str, Any]:
        """
        Estime les coûts d'exécution pour un changement d'allocation
        Retourne: dict avec détails des coûts
        """
        try:
            policy = self.current_state.execution_policy
            execution_cost_bps = policy.execution_cost_bps if policy else 15
            
            # Calcul des volumes de trading nécessaires
            total_volume = 0
            trade_details = {}
            
            for symbol, target_weight in target_weights.items():
                current_weight = 0  # Simplification - dans une vraie implémentation, on lirait le portefeuille actuel
                weight_change = abs(target_weight - current_weight)
                trade_volume_usd = weight_change * current_portfolio_usd
                
                trade_details[symbol] = {
                    'volume_usd': trade_volume_usd,
                    'cost_bps': execution_cost_bps,
                    'estimated_cost_usd': trade_volume_usd * execution_cost_bps / 10000
                }
                
                total_volume += trade_volume_usd
            
            total_cost_usd = total_volume * execution_cost_bps / 10000
            cost_percentage = (total_cost_usd / current_portfolio_usd) * 100
            
            execution_summary = {
                'total_volume_usd': total_volume,
                'total_cost_usd': total_cost_usd,
                'cost_percentage': cost_percentage,
                'cost_bps': execution_cost_bps,
                'trade_details': trade_details,
                'cost_efficient': cost_percentage < 0.5  # Flag si coût < 0.5% du portfolio
            }
            
            logger.debug(f"Execution cost estimate: ${total_cost_usd:.2f} ({cost_percentage:.2f}%)")
            return execution_summary
            
        except Exception as e:
            logger.error(f"Error estimating execution cost: {e}")
            return {'error': str(e)}

    async def approve_decision(self, decision_id: str, approved: bool, reason: Optional[str] = None) -> bool:
        """Legacy method - redirect to approve_plan for compatibility"""
        try:
            logger.info(f"Decision {decision_id}: approved={approved}, reason={reason}")
            
            if approved:
                # Try to find and approve plan
                plan = self._find_plan_by_id(decision_id)
                if plan:
                    if plan.status == "DRAFT":
                        await self.review_plan(decision_id, "system", "Auto-reviewed for approval")
                    if plan.status == "REVIEWED":
                        await self.approve_plan(decision_id, "system", reason)
                    if plan.status == "APPROVED":
                        await self.activate_plan(decision_id)
                    return True
                else:
                    logger.warning("No plan found to approve")
                    return False
            else:
                # Cancel the plan
                return await self.cancel_plan(decision_id, "system", reason)
            
        except Exception as e:
            logger.error(f"Error approving decision: {e}")
            return False

    async def set_governance_mode(self, mode: str, reason: str = "Mode change") -> bool:
        """Change le mode de gouvernance"""
        try:
            logger.info(f"Changing governance mode to '{mode}': {reason}")
            
            # Validate mode
            if mode not in ["manual", "ai_assisted", "full_ai", "freeze"]:
                logger.error(f"Invalid governance mode: {mode}")
                return False
                
            self.current_state.governance_mode = mode
            self.current_state.last_update = datetime.now()
            
            # Special handling for freeze mode
            if mode == "freeze":
                await self.freeze_system(reason)
            elif self.current_state.governance_mode == "freeze" and mode != "freeze":
                # Unfreezing implicitly
                self.current_state.system_status = "operational"
                
            logger.info(f"Governance mode changed to '{mode}'")
            return True
            
        except Exception as e:
            logger.error(f"Error setting governance mode: {e}")
            return False

    def can_publish_new_plan(self) -> Tuple[bool, str]:
        """
        Vérifie si on peut publier un nouveau plan (respecte le cooldown)
        Retourne: (can_publish, reason)
        """
        try:
            policy = self.current_state.execution_policy
            if not policy:
                return False, "No execution policy available"
            
            # Calculer le temps restant du cooldown
            time_since_last = (datetime.now() - self._last_plan_publication).total_seconds()
            cooldown_seconds = policy.plan_cooldown_hours * 3600
            
            if time_since_last < cooldown_seconds:
                remaining_hours = (cooldown_seconds - time_since_last) / 3600
                return False, f"Cooldown active: {remaining_hours:.1f}h remaining"
            
            return True, "Cooldown expired, can publish"
            
        except Exception as e:
            logger.error(f"Error checking cooldown: {e}")
            return False, f"Error checking cooldown: {e}"

    async def create_proposed_plan(self, targets: List[Dict], reason: str = "New proposal", force_override_cooldown: bool = False) -> Tuple[bool, str]:
        """
        Crée un plan proposé en respectant le cooldown
        Retourne: (success, message)
        """
        try:
            logger.info(f"Creating proposed plan: {reason}")
            
            # Vérifier le cooldown (sauf si force override)
            if not force_override_cooldown:
                can_publish, cooldown_reason = self.can_publish_new_plan()
                if not can_publish:
                    logger.warning(f"Plan creation blocked by cooldown: {cooldown_reason}")
                    return False, f"Cannot publish plan: {cooldown_reason}"
            
            # Convert targets to Target objects
            target_objects = []
            total_weight = 0.0
            
            for target in targets:
                symbol = target.get("symbol", "")
                weight = target.get("weight", 0.0)
                
                if not symbol or weight <= 0:
                    error_msg = f"Invalid target: {target}"
                    logger.error(error_msg)
                    return False, error_msg
                    
                target_objects.append(Target(symbol=symbol, weight=weight))
                total_weight += weight
            
            # Normalize weights to sum to 1.0
            if abs(total_weight - 1.0) > 0.001:
                logger.info(f"Normalizing weights from {total_weight:.3f} to 1.0")
                for target_obj in target_objects:
                    target_obj.weight = target_obj.weight / total_weight
            
            # Create proposed plan
            proposed_plan = DecisionPlan(
                plan_id=f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                status="DRAFT",
                targets=target_objects,
                governance_mode=self.current_state.governance_mode,
                etag=f"etag_{datetime.now().timestamp()}",
                created_by="UI_System",
                notes=reason
            )
            
            self.current_state.proposed_plan = proposed_plan
            self.current_state.last_update = datetime.now()
            
            # Marquer le timestamp de publication
            self._last_plan_publication = datetime.now()
            
            success_msg = f"Proposed plan created: {proposed_plan.plan_id}"
            logger.info(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"Error creating proposed plan: {e}"
            logger.error(error_msg)
            return False, error_msg

    def _extract_real_volatility_signals(self, ml_predictions: Dict[str, Any]) -> Dict[str, float]:
        """Extrait les signaux de volatilité depuis les vraies prédictions ML"""
        try:
            volatility_data = ml_predictions.get('models', {}).get('volatility', {})
            if not volatility_data:
                return {}
            
            volatility_signals = {}
            for symbol, predictions in volatility_data.items():
                if isinstance(predictions, dict):
                    # Take average volatility across horizons
                    vol_values = []
                    for horizon_key, horizon_data in predictions.items():
                        if isinstance(horizon_data, dict) and 'volatility_forecast' in horizon_data:
                            vol_values.append(horizon_data['volatility_forecast'])
                    
                    if vol_values:
                        volatility_signals[symbol] = sum(vol_values) / len(vol_values)
            
            logger.debug(f"Extracted real volatility signals: {volatility_signals}")
            return volatility_signals
            
        except Exception as e:
            logger.warning(f"Error extracting real volatility signals: {e}")
            return {}

    def _extract_real_regime_signals(self, ml_predictions: Dict[str, Any]) -> Dict[str, float]:
        """Extrait les signaux de régime depuis les vraies prédictions ML"""
        try:
            regime_data = ml_predictions.get('models', {}).get('regime', {})
            if not regime_data:
                return {"neutral": 1.0}
            
            # Map regime names to probabilities
            current_regime = regime_data.get('current_regime', 'unknown')
            regime_prob = regime_data.get('regime_probability', 0.5)
            
            # Convert regime to our expected format
            regime_mapping = {
                'bull_market': {'bull': 0.8, 'neutral': 0.15, 'bear': 0.05},
                'bear_market': {'bull': 0.05, 'neutral': 0.15, 'bear': 0.8},
                'accumulation': {'bull': 0.6, 'neutral': 0.3, 'bear': 0.1},
                'distribution': {'bull': 0.1, 'neutral': 0.3, 'bear': 0.6},
                'euphoria': {'bull': 0.9, 'neutral': 0.08, 'bear': 0.02},
                'sideways': {'bull': 0.33, 'neutral': 0.34, 'bear': 0.33}
            }
            
            if current_regime in regime_mapping:
                base_probs = regime_mapping[current_regime]
                # Adjust by actual confidence
                regime_signals = {}
                for regime_type, base_prob in base_probs.items():
                    regime_signals[regime_type] = base_prob * regime_prob + (1 - regime_prob) * 0.33
            else:
                regime_signals = {"bull": 0.33, "neutral": 0.34, "bear": 0.33}
            
            logger.debug(f"Extracted real regime signals: {regime_signals}")
            return regime_signals
            
        except Exception as e:
            logger.warning(f"Error extracting real regime signals: {e}")
            return {"neutral": 1.0}

    def _extract_real_correlation_signals(self, ml_predictions: Dict[str, Any]) -> Dict[str, Any]:
        """Extrait les signaux de corrélation depuis les vraies prédictions ML"""
        try:
            correlation_data = ml_predictions.get('models', {}).get('correlation', {})
            if not correlation_data:
                return {"avg_correlation": 0.5, "systemic_risk": "unknown"}
            
            # Extract correlation information
            correlations = []
            for pair, corr_info in correlation_data.items():
                if isinstance(corr_info, dict):
                    current_corr = corr_info.get('current_correlation', 0.5)
                    forecast_corr = corr_info.get('forecast_correlation', current_corr)
                    correlations.append(max(current_corr, forecast_corr))
            
            if correlations:
                avg_correlation = sum(correlations) / len(correlations)
                systemic_risk_level = "high" if avg_correlation > 0.7 else "medium" if avg_correlation > 0.5 else "low"
            else:
                avg_correlation = 0.5
                systemic_risk_level = "unknown"
            
            correlation_signals = {
                "avg_correlation": avg_correlation,
                "systemic_risk": systemic_risk_level
            }
            
            logger.debug(f"Extracted real correlation signals: {correlation_signals}")
            return correlation_signals
            
        except Exception as e:
            logger.warning(f"Error extracting real correlation signals: {e}")
            return {"avg_correlation": 0.5, "systemic_risk": "unknown"}

    def _extract_real_sentiment_signals(self, ml_predictions: Dict[str, Any]) -> Dict[str, float]:
        """Extrait les signaux de sentiment depuis les vraies prédictions ML"""
        try:
            sentiment_data = ml_predictions.get('models', {}).get('sentiment', {})
            if not sentiment_data:
                return {"fear_greed": 50, "sentiment_score": 0.0}
            
            # Extract sentiment scores
            sentiment_scores = []
            fear_greed_values = []
            
            for symbol, sentiment_info in sentiment_data.items():
                if isinstance(sentiment_info, dict):
                    if 'sentiment_score' in sentiment_info:
                        sentiment_scores.append(sentiment_info['sentiment_score'])
                    if 'fear_greed_index' in sentiment_info:
                        fear_greed_values.append(sentiment_info['fear_greed_index'])
            
            # Calculate averages
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
            avg_fear_greed = sum(fear_greed_values) / len(fear_greed_values) if fear_greed_values else 50.0
            
            sentiment_signals = {
                "fear_greed": avg_fear_greed,
                "sentiment_score": avg_sentiment
            }
            
            logger.debug(f"Extracted real sentiment signals: {sentiment_signals}")
            return sentiment_signals
            
        except Exception as e:
            logger.warning(f"Error extracting real sentiment signals: {e}")
            return {"fear_greed": 50, "sentiment_score": 0.0}

    def _calculate_real_confidence(self, ml_predictions: Dict[str, Any]) -> float:
        """Calcule la confiance globale depuis les vraies prédictions ML"""
        try:
            confidence_scores = ml_predictions.get('confidence_scores', {})
            if not confidence_scores:
                return 0.5
            
            # Weight different model confidences
            model_weights = {
                'volatility': 0.25,
                'sentiment': 0.20,
                'regime': 0.30,
                'correlation': 0.25
            }
            
            weighted_confidence = 0.0
            total_weight = 0.0
            
            for model, confidence in confidence_scores.items():
                if model in model_weights and isinstance(confidence, (int, float)):
                    weighted_confidence += confidence * model_weights[model]
                    total_weight += model_weights[model]
            
            if total_weight > 0:
                final_confidence = weighted_confidence / total_weight
            else:
                final_confidence = confidence_scores.get('overall', 0.5)
            
            logger.debug(f"Calculated real confidence: {final_confidence:.3f}")
            return min(1.0, max(0.0, final_confidence))
            
        except Exception as e:
            logger.warning(f"Error calculating real confidence: {e}")
            return 0.5

    def _compute_real_contradiction_index(self, ml_predictions: Dict[str, Any]) -> float:
        """Calcule l'index de contradiction depuis les vraies prédictions ML"""
        try:
            ensemble = ml_predictions.get('ensemble', {})
            if not ensemble:
                return 0.3  # Default moderate contradiction
            
            # Use ensemble conflicting signals
            conflicting_signals = ensemble.get('conflicting_signals', [])
            consensus_strength = ensemble.get('consensus_strength', 0.5)
            
            # Base contradiction from conflicting signals
            base_contradiction = len(conflicting_signals) / 4.0  # Normalize by max models
            
            # Adjust by consensus weakness
            consensus_contradiction = 1.0 - consensus_strength
            
            # Combine both measures
            contradiction_index = (base_contradiction * 0.6) + (consensus_contradiction * 0.4)
            
            # Cap at reasonable levels
            contradiction_index = min(1.0, max(0.0, contradiction_index))
            
            logger.debug(f"Computed real contradiction index: {contradiction_index:.3f} "
                        f"(conflicts: {len(conflicting_signals)}, consensus: {consensus_strength:.2f})")
            
            return contradiction_index
            
        except Exception as e:
            logger.warning(f"Error computing real contradiction index: {e}")
            return 0.3

# Instance globale pour réutilisation
governance_engine = GovernanceEngine()