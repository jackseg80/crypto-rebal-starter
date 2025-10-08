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

# Logger setup
logger = logging.getLogger(__name__)

# Import real ML orchestrator
try:
    from ..ml.orchestrator import get_orchestrator
    ML_ORCHESTRATOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"ML Orchestrator not available: {e}")
    ML_ORCHESTRATOR_AVAILABLE = False

# Phase 3C: Import Hybrid Intelligence components
try:
    from ..intelligence.explainable_ai import ExplainableAIEngine
    from ..intelligence.human_loop import HumanInTheLoopEngine
    from ..intelligence.feedback_learning import FeedbackLearningEngine
    from ..orchestration.hybrid_orchestrator import HybridOrchestrator
    HYBRID_INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Phase 3C Hybrid Intelligence not available: {e}")
    HYBRID_INTELLIGENCE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Types pour la governance
GovernanceMode = Literal["manual", "ai_assisted", "full_ai", "freeze"]
PlanStatus = Literal["DRAFT", "REVIEWED", "APPROVED", "ACTIVE", "EXECUTED", "CANCELLED"]
ExecMode = Literal["Freeze", "Slow", "Normal", "Aggressive"]

# Phase 1C: Sémantique Freeze claire
class FreezeType:
    """Types de freeze avec sémantique précise"""
    FULL_FREEZE = "full_freeze"       # Tout bloqué (urgence)
    S3_ALERT_FREEZE = "s3_freeze"     # Freeze achats, rotations↓ stables OK, hedge OK
    ERROR_FREEZE = "error_freeze"     # Freeze prudent, réductions risque autorisées

class FreezeSemantics:
    """
    Définit précisément ce qui est autorisé/bloqué selon le type de freeze
    Phase 1C: Sémantique claire pour éviter confusion opérationnelle
    """

    @staticmethod
    def get_allowed_operations(freeze_type: str) -> Dict[str, bool]:
        """Retourne les opérations autorisées selon le type de freeze"""

        if freeze_type == FreezeType.FULL_FREEZE:
            return {
                "new_purchases": False,     # Pas de nouveaux achats
                "sell_to_stables": False,   # Pas de ventes vers stables
                "asset_rotations": False,   # Pas de rotations BTC→ETH, etc.
                "hedge_operations": False,  # Pas de hedge
                "risk_reductions": False,   # Pas de réductions risque
                "emergency_exits": True,    # Seules sorties d'urgence autorisées
            }
        elif freeze_type == FreezeType.S3_ALERT_FREEZE:
            return {
                "new_purchases": False,     # Pas de nouveaux achats
                "sell_to_stables": True,    # Rotations↓ stables OK
                "asset_rotations": False,   # Pas de rotations entre risky assets
                "hedge_operations": True,   # Hedge autorisé (protection)
                "risk_reductions": True,    # Réductions risque autorisées
                "emergency_exits": True,    # Sorties d'urgence toujours OK
            }
        elif freeze_type == FreezeType.ERROR_FREEZE:
            return {
                "new_purchases": False,     # Pas de nouveaux achats
                "sell_to_stables": True,    # Ventes vers stables OK
                "asset_rotations": False,   # Pas de rotations risquées
                "hedge_operations": True,   # Hedge OK
                "risk_reductions": True,    # Réductions risque prioritaires
                "emergency_exits": True,    # Sorties d'urgence toujours OK
            }
        else:
            # Mode normal : tout autorisé
            return {
                "new_purchases": True,
                "sell_to_stables": True,
                "asset_rotations": True,
                "hedge_operations": True,
                "risk_reductions": True,
                "emergency_exits": True,
            }

    @staticmethod
    def validate_operation(freeze_type: str, operation_type: str) -> Tuple[bool, str]:
        """
        Valide si une opération est autorisée selon le freeze actuel

        Returns:
            (allowed: bool, reason: str)
        """
        allowed_ops = FreezeSemantics.get_allowed_operations(freeze_type)

        if operation_type not in allowed_ops:
            return False, f"Operation type '{operation_type}' not recognized"

        is_allowed = allowed_ops[operation_type]

        if not is_allowed:
            reason = f"{operation_type} blocked by {freeze_type}"
        else:
            reason = f"{operation_type} allowed under {freeze_type}"

        return is_allowed, reason

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
    no_trade_threshold_pct: float = Field(default=0.02, ge=0.0, le=0.10, description="Zone no-trade [0-10%]")
    execution_cost_bps: int = Field(default=15, ge=0, le=100, description="Cout d'execution estime [0-100 bps]")
    
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
    blended_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Blended Decision Score (0-100) si disponible")
    
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
    last_applied_policy: Optional[Policy] = Field(default=None, description="Derniere policy appliquee manuellement")
    last_manual_policy_update: Optional[datetime] = Field(default=None, description="Timestamp derniere activation manuelle")

    
    # Signaux ML
    signals: MLSignals = Field(default_factory=MLSignals, description="Signaux ML actuels")
    
    # Métadonnées
    last_update: datetime = Field(default_factory=datetime.now, description="Dernière MAJ")
    system_status: str = Field(default="operational", description="Statut système")
    auto_unfreeze_at: Optional[datetime] = Field(default=None, description="Auto-unfreeze programmé")

    # Phase 1C: Type de freeze avec sémantique claire
    freeze_type: Optional[str] = Field(default=None, description="Type de freeze actuel (s3_freeze, error_freeze, full_freeze)")


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

        # Phase 1A: Cap stability variables (hystérésis + smoothing)
        self._last_cap = 0.08  # Dernière cap calculée pour smoothing
        self._prudent_mode = False  # État hystérésis prudent/normal
        self._alert_cap_reduction = 0.0  # Réduction cap par AlertEngine
        self._alert_cooldown_until = datetime.min  # Cooldown AlertEngine

        # Phase 4: Hystérésis anti-yo-yo pour VaR et stale detection
        self._var_hysteresis_state = "normal"  # "normal" | "prudent"
        self._stale_hysteresis_state = "normal"  # "normal" | "stale"
        self._var_hysteresis_history = []  # Historique VaR pour trend detection
        self._stale_hysteresis_history = []  # Historique staleness
        self._hysteresis_config = {
            "var_activate_threshold": 75,    # Active hystérésis si VaR > 75
            "var_deactivate_threshold": 65,  # Désactive si VaR < 65 (gap anti-yo-yo)
            "stale_activate_seconds": 3600,  # Active si stale > 1h
            "stale_deactivate_seconds": 1800, # Désactive si fresh < 30min (gap anti-yo-yo)
            "history_window": 5,             # Fenêtre historique pour trend detection
            "trend_stability_required": 3    # Nb points stables requis avant changement
        }
        
        # Phase 3C: Initialize Hybrid Intelligence components
        self.hybrid_intelligence_enabled = HYBRID_INTELLIGENCE_AVAILABLE
        if self.hybrid_intelligence_enabled:
            try:
                self.explainable_ai = ExplainableAIEngine()
                self.human_loop = HumanInTheLoopEngine()
                self.feedback_learning = FeedbackLearningEngine()
                self.hybrid_orchestrator = HybridOrchestrator()
                logger.info("Phase 3C Hybrid Intelligence components initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Phase 3C components: {e}")
                self.hybrid_intelligence_enabled = False
        else:
            self.explainable_ai = None
            self.human_loop = None
            self.feedback_learning = None
            self.hybrid_orchestrator = None
        
        logger.info(f"GovernanceEngine initialized with TTL/cooldown separation, Hybrid Intelligence: {self.hybrid_intelligence_enabled}")

    def _enforce_policy_bounds(self, policy: Policy) -> Policy:
        """Clamp defensif des champs critiques de policy."""
        data = policy.dict()

        def _as_float(value, default):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def _as_int(value, default):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        cap_value = _as_float(data.get("cap_daily", 0.08), 0.08)
        data["cap_daily"] = max(0.01, min(0.20, cap_value))

        no_trade_value = _as_float(data.get("no_trade_threshold_pct", 0.02), 0.02)
        data["no_trade_threshold_pct"] = max(0.0, min(0.10, no_trade_value))

        cost_value = _as_int(data.get("execution_cost_bps", 15), 15)
        data["execution_cost_bps"] = max(0, min(100, cost_value))

        return Policy(**data)

    
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
            # FIX Oct 2025: Fallback safe 8% (not 1% ultra-restrictive)
            return DecisionState(
                governance_mode="manual",
                execution_policy=Policy(
                    mode="Freeze",
                    cap_daily=0.08,  # Safe fallback 8% (aligned with stale/frontend defaults)
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
        Phase 1A: Avec hystérésis + smoothing pour éviter oscillations
        """
        try:
            signals = self.current_state.signals
            contradiction = signals.contradiction_index
            confidence = signals.confidence

            manual_policy = getattr(self.current_state, "last_applied_policy", None)
            control_mode = getattr(self.current_state, "governance_mode", "manual")
            if control_mode == "manual" and manual_policy is not None:
                enforced_policy = self._enforce_policy_bounds(manual_policy)
                self._last_cap = enforced_policy.cap_daily
                logger.info("[governance] manual policy override in effect (mode=%s, cap=%.2f%%)", enforced_policy.mode, enforced_policy.cap_daily * 100)
                return enforced_policy


            # Phase 1A: Hystérésis pour éviter flip-flop mode prudent/normal
            # Prudent si contradiction ≥ 0.45, Normal si contradiction ≤ 0.40
            if contradiction >= 0.45:
                self._prudent_mode = True
            elif contradiction <= 0.40:
                self._prudent_mode = False
            # Entre 0.40-0.45 : conserver l'état précédent (hystérésis)

            # Logique extraite d'UnifiedInsights avec hystérésis appliquée
            if contradiction > 0.7 or confidence < 0.3:
                # Mode défensif
                mode = "Freeze" if contradiction > 0.8 else "Slow"
                cap_raw = max(0.03, 0.12 - contradiction * 0.09)  # 3-12% inversé
                ramp_hours = 48

            elif self._prudent_mode or confidence < 0.6:  # Utilise hystérésis
                # Mode prudent (avec hystérésis)
                mode = "Slow"
                cap_raw = 0.07  # 7% comme dans UnifiedInsights "Rotate"
                ramp_hours = 24

            elif confidence > 0.8 and contradiction < 0.2:
                # Mode agressif
                mode = "Aggressive"
                cap_raw = 0.12  # 12% comme dans UnifiedInsights "Deploy"
                ramp_hours = 6

            else:
                # Mode normal
                mode = "Normal"
                cap_raw = 0.08  # 8% baseline
                ramp_hours = 12

            # Phase 1A: Smoothing cap = 0.7*cap(t-1) + 0.3*cap_raw
            cap_smoothed = 0.7 * self._last_cap + 0.3 * cap_raw

            # Garde-fou : pas de variation > 2 pts entre runs (sauf stale/error)
            max_variation = 0.02  # 2 points de pourcentage
            if abs(cap_smoothed - self._last_cap) > max_variation:
                if cap_smoothed > self._last_cap:
                    cap_smoothed = self._last_cap + max_variation
                else:
                    cap_smoothed = self._last_cap - max_variation

            cap = cap_smoothed
            
            # Garde-fou: ne jamais 'Aggressive' si blended < 70 (si disponible)
            try:
                if mode == "Aggressive":
                    bscore = getattr(self.current_state.signals, 'blended_score', None)
                    if isinstance(bscore, (int, float)) and bscore < 70:
                        mode = "Normal"
                        cap = min(cap, 0.08)
                        ramp_hours = max(ramp_hours, 12)
            except Exception:
                pass

            # Ajustements selon governance mode
            if self.current_state.governance_mode == "freeze":
                mode = "Freeze"
                cap = 0.01

            # Phase 4: Ordre de priorité caps avec hystérésis: error(5%) > stale(8%) > alert > engine
            cap_engine = cap  # Cap calculé par engine
            cap_alert = cap_engine - self._alert_cap_reduction  # Cap réduit par AlertEngine
            cap_stale = None
            cap_error = None

            # Intégrer hystérésis avancée pour éviter oscillations yo-yo
            try:
                as_of = getattr(signals, "as_of", None)
                if isinstance(as_of, datetime):
                    signals_age = (datetime.now() - as_of).total_seconds()
                else:
                    signals_age = 0.0

                var_state, stale_state = self._update_hysteresis_state(signals, signals_age)

                # Appliquer caps basées sur états d'hystérésis (plus stables)
                if stale_state == "stale":
                    cap_stale = 0.08  # 8% stale clamp avec hystérésis

                # Error condition : toujours prioritaire, sans hystérésis (urgence)
                if signals_age > 7200:  # 2h = error critique immédiat
                    cap_error = 0.05  # 5% error clamp

                # Modifier mode selon hystérésis VaR
                if var_state == "prudent" and mode == "Aggressive":
                    mode = "Normal"  # Downgrade si VaR élevé persistant
                    cap = min(cap, 0.08)  # Plafonner cap

            except:
                signals_age = 0
                var_state, stale_state = "normal", "normal"

            # Appliquer la priorité stricte
            original_cap = cap
            if cap_error is not None:
                cap = cap_error
                mode = "Freeze"  # Error force freeze
            elif cap_stale is not None:
                cap = min(cap, cap_stale)
            elif self._alert_cap_reduction > 0:
                cap = cap_alert


            # Ajuster no-trade zone et coûts selon la volatilité
            vol_signals = signals.volatility
            avg_volatility = sum(vol_signals.values()) / len(vol_signals) if vol_signals else 0.15
            
            # No-trade zone plus large si volatilité élevée (évite le churning)
            no_trade_threshold = min(0.10, 0.02 + avg_volatility * 0.5)  # 2-10% selon volatilité
            
            # Coûts d'exécution estimés (spread + slippage + frais)
            execution_cost = 15 + (avg_volatility * 100)  # 15-30 bps selon volatilité
            
            # Enrichir les notes avec les informations de caps et hystérésis
            cap_notes = []
            if cap_error is not None:
                cap_notes.append(f"ERROR_CLAMP(5%)")
            elif cap_stale is not None:
                cap_notes.append(f"STALE_HYSTERESIS(8%)")  # Indication hystérésis
            elif self._alert_cap_reduction > 0:
                cap_notes.append(f"ALERT_REDUCTION(-{self._alert_cap_reduction:.1%})")

            # Phase 4: Notes d'hystérésis avancées
            hysteresis_notes = []
            if var_state == "prudent":
                hysteresis_notes.append("VAR_HYSTERESIS")
            if stale_state == "stale":
                hysteresis_notes.append("STALE_HYSTERESIS")

            if hysteresis_notes:
                cap_notes.extend(hysteresis_notes)

            # Legacy support (pour compatibilité UI)
            if self._prudent_mode:
                cap_notes.append("HYSTERESIS_PRUDENT_LEGACY")

            cap_info = f" [{', '.join(cap_notes)}]" if cap_notes else ""

            cap = max(0.01, min(0.20, cap))
            no_trade_threshold = max(0.0, min(0.10, no_trade_threshold))
            execution_cost_bps = int(max(0, min(100, round(execution_cost))))

            # Mettre a jour _last_cap pour le prochain smoothing (mais seulement si pas stale/error)
            if cap_error is None and cap_stale is None:
                self._last_cap = cap
            # Sinon, garder _last_cap pour revenir au smoothing quand stale/error disparait


            policy = Policy(
                mode=mode,
                cap_daily=cap,
                ramp_hours=ramp_hours,
                min_trade=100.0,
                slippage_limit_bps=50,
                signals_ttl_seconds=self._signals_ttl_seconds,
                plan_cooldown_hours=self._plan_cooldown_hours,
                no_trade_threshold_pct=no_trade_threshold,
                execution_cost_bps=execution_cost_bps,  # Cap à 100 bps
                notes=f"ML: contradiction={contradiction:.2f}, confidence={confidence:.2f}, vol={avg_volatility:.3f}{cap_info}"
            )

            # Logging enrichi Phase 1A
            logger.debug(f"Policy derived: mode={mode}, cap={cap:.1%} (engine={cap_engine:.1%}), "
                        f"contradiction={contradiction:.3f}, prudent_mode={self._prudent_mode}, "
                        f"alert_reduction={self._alert_cap_reduction:.1%}{cap_info}")

            return policy
            
        except Exception as e:
            logger.error(f"Error deriving execution policy: {e}")

            health_state = getattr(self.current_state, "system_status", "unknown")
            normalized_health = "healthy" if health_state == "operational" else health_state

            signals_obj = getattr(self.current_state, "signals", None)
            signals_age = None
            if signals_obj is not None:
                as_of = getattr(signals_obj, "as_of", None)
                if isinstance(as_of, datetime):
                    signals_age = (datetime.now() - as_of).total_seconds()

            current_policy = getattr(self.current_state, "execution_policy", Policy())
            ttl_seconds = getattr(current_policy, "signals_ttl_seconds", self._signals_ttl_seconds)

            logger.warning(
                "Execution policy fallback triggered (health=%s, signals_age=%s, ttl=%s)",
                normalized_health,
                f"{signals_age:.0f}s" if signals_age is not None else "unknown",
                ttl_seconds,
            )

            if normalized_health == "healthy" and signals_age is not None and signals_age < ttl_seconds:
                degraded_policy = current_policy.dict()
                degraded_policy.update({
                    "mode": "Slow",
                    "cap_daily": 0.05,
                    "notes": f"Degraded fallback: {e}"
                })
                logger.info(
                    "Applying degraded Slow fallback after error (cap_daily=5%%)"
                )
                return self._enforce_policy_bounds(Policy(**degraded_policy))

            return self._enforce_policy_bounds(Policy(mode="Freeze", cap_daily=0.08, notes=f"Error fallback: {e}"))  # FIX Oct 2025: 8% safe fallback

    def apply_alert_cap_reduction(self, reduction_percentage: float, alert_id: str, reason: str) -> bool:
        """
        Phase 1B: AlertEngine peut déclencher réduction cap
        Max rule: pas d'empilement, cooldown 60min, remontée progressive

        Args:
            reduction_percentage: Réduction en pourcentage (ex: 0.03 pour -3%)
            alert_id: ID de l'alerte qui déclenche
            reason: Raison (VaR>4%, contradiction>55%, etc.)
        """
        try:
            # Cooldown check: ne pas réduire si déjà en cooldown
            if datetime.now() < self._alert_cooldown_until:
                logger.info(f"Alert cap reduction ignored (cooldown until {self._alert_cooldown_until})")
                return False

            # Max rule: prendre la plus forte réduction, pas additive
            new_reduction = max(self._alert_cap_reduction, reduction_percentage)

            if new_reduction > self._alert_cap_reduction:
                old_reduction = self._alert_cap_reduction
                self._alert_cap_reduction = new_reduction
                # Cooldown 60min après nouvelle réduction
                self._alert_cooldown_until = datetime.now() + timedelta(minutes=60)

                logger.warning(f"Alert cap reduction applied: {old_reduction:.1%} → {new_reduction:.1%} "
                             f"(Alert: {alert_id}, Reason: {reason})")
                return True
            else:
                logger.info(f"Alert cap reduction {reduction_percentage:.1%} ignored "
                          f"(current: {self._alert_cap_reduction:.1%} is higher)")
                return False

        except Exception as e:
            logger.error(f"Error applying alert cap reduction: {e}")
            return False

    def clear_alert_cap_reduction(self, progressive: bool = True) -> bool:
        """
        Phase 1B: Nettoyer réduction cap AlertEngine
        Si progressive=True, remontée +1pt/30min
        """
        try:
            if self._alert_cap_reduction <= 0:
                return True  # Déjà à 0

            if progressive:
                # Remontée progressive +1pt/30min
                step = 0.01  # 1 point de pourcentage
                self._alert_cap_reduction = max(0, self._alert_cap_reduction - step)
                logger.info(f"Alert cap reduction progressive clear: {self._alert_cap_reduction:.1%} remaining")
            else:
                # Clear immédiat
                old_reduction = self._alert_cap_reduction
                self._alert_cap_reduction = 0.0
                self._alert_cooldown_until = datetime.min
                logger.info(f"Alert cap reduction cleared: {old_reduction:.1%} → 0%")

            return True

        except Exception as e:
            logger.error(f"Error clearing alert cap reduction: {e}")
            return False

    def _update_hysteresis_state(self, signals: Any, signals_age: float) -> Tuple[str, str]:
        """
        Phase 4: Hystérésis anti-yo-yo avec seuils d'activation/désactivation distincts

        Returns:
            Tuple[var_state, stale_state] : États d'hystérésis ("normal"/"prudent", "normal"/"stale")
        """
        try:
            # 1. VaR Hysteresis - utilise blended_score comme proxy VaR
            var_proxy_raw = getattr(signals, 'blended_score', None)
            if var_proxy_raw is None:
                var_proxy = 70.0
            else:
                try:
                    var_proxy = float(var_proxy_raw)
                except (TypeError, ValueError):
                    logger.warning(f"Invalid blended_score {var_proxy_raw!r}; falling back to 70.0")
                    var_proxy = 70.0

            try:
                signals_age = float(signals_age)
            except (TypeError, ValueError):
                logger.warning(f"Invalid signals_age {signals_age!r}; defaulting to 0.0")
                signals_age = 0.0

            self._var_hysteresis_history.append(var_proxy)

            # Maintenir fenêtre historique
            if len(self._var_hysteresis_history) > self._hysteresis_config["history_window"]:
                self._var_hysteresis_history.pop(0)

            # Logique d'hystérésis VaR avec gap anti-yo-yo
            if self._var_hysteresis_state == "normal":
                # Condition d'activation prudent : VaR élevé + tendance stable
                if (var_proxy > self._hysteresis_config["var_activate_threshold"] and
                    len(self._var_hysteresis_history) >= self._hysteresis_config["trend_stability_required"]):
                    # Vérifier tendance stable vers le haut
                    recent_values = self._var_hysteresis_history[-self._hysteresis_config["trend_stability_required"]:]
                    if all(v > self._hysteresis_config["var_activate_threshold"] for v in recent_values):
                        self._var_hysteresis_state = "prudent"
                        logger.warning(f"VaR hysteresis activated: prudent mode (score={var_proxy})")
            else:  # "prudent"
                # Condition de désactivation : VaR bas + tendance stable (gap anti-yo-yo)
                if (var_proxy < self._hysteresis_config["var_deactivate_threshold"] and
                    len(self._var_hysteresis_history) >= self._hysteresis_config["trend_stability_required"]):
                    # Vérifier tendance stable vers le bas
                    recent_values = self._var_hysteresis_history[-self._hysteresis_config["trend_stability_required"]:]
                    if all(v < self._hysteresis_config["var_deactivate_threshold"] for v in recent_values):
                        self._var_hysteresis_state = "normal"
                        logger.info(f"VaR hysteresis deactivated: normal mode (score={var_proxy})")

            # 2. Stale Hysteresis - utilise signals_age
            self._stale_hysteresis_history.append(signals_age)

            # Maintenir fenêtre historique
            if len(self._stale_hysteresis_history) > self._hysteresis_config["history_window"]:
                self._stale_hysteresis_history.pop(0)

            # Logique d'hystérésis staleness avec gap anti-yo-yo
            if self._stale_hysteresis_state == "normal":
                # Condition d'activation stale : signaux anciens + tendance stable
                if (signals_age > self._hysteresis_config["stale_activate_seconds"] and
                    len(self._stale_hysteresis_history) >= self._hysteresis_config["trend_stability_required"]):
                    # Vérifier tendance stable vers staleness
                    recent_ages = self._stale_hysteresis_history[-self._hysteresis_config["trend_stability_required"]:]
                    if all(age > self._hysteresis_config["stale_activate_seconds"] for age in recent_ages):
                        self._stale_hysteresis_state = "stale"
                        logger.warning(f"Stale hysteresis activated: stale mode (age={signals_age:.0f}s)")
            else:  # "stale"
                # Condition de désactivation : signaux frais + tendance stable (gap anti-yo-yo)
                if (signals_age < self._hysteresis_config["stale_deactivate_seconds"] and
                    len(self._stale_hysteresis_history) >= self._hysteresis_config["trend_stability_required"]):
                    # Vérifier tendance stable vers freshness
                    recent_ages = self._stale_hysteresis_history[-self._hysteresis_config["trend_stability_required"]:]
                    if all(age < self._hysteresis_config["stale_deactivate_seconds"] for age in recent_ages):
                        self._stale_hysteresis_state = "normal"
                        logger.info(f"Stale hysteresis deactivated: normal mode (age={signals_age:.0f}s)")

            return self._var_hysteresis_state, self._stale_hysteresis_state

        except Exception as e:
            logger.error(f"Error in hysteresis state update: {e}")
            return "normal", "normal"  # Safe fallback

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

    async def freeze_system(self, reason: str, duration_minutes: Optional[int] = None, freeze_type: str = None) -> bool:
        """
        Phase 1C: Freeze système avec sémantique claire

        Args:
            reason: Raison du freeze
            duration_minutes: TTL auto-unfreeze
            freeze_type: Type de freeze (s3_freeze, error_freeze, full_freeze)
        """
        try:
            # Déterminer le type de freeze automatiquement si non spécifié
            if freeze_type is None:
                if "S3" in reason or "alert" in reason.lower():
                    freeze_type = FreezeType.S3_ALERT_FREEZE
                elif "error" in reason.lower() or "backend" in reason.lower():
                    freeze_type = FreezeType.ERROR_FREEZE
                else:
                    freeze_type = FreezeType.FULL_FREEZE

            logger.info(f"Freezing system: {reason} (Type: {freeze_type}, TTL: {duration_minutes}min)"
                       if duration_minutes else f"Freezing system: {reason} (Type: {freeze_type})")

            # Set governance mode to freeze avec type sémantique
            self.current_state.governance_mode = "freeze"
            self.current_state.freeze_type = freeze_type
            self.current_state.system_status = "frozen"
            self.current_state.last_update = datetime.now()

            # Store auto-unfreeze time if TTL specified
            if duration_minutes:
                self.current_state.auto_unfreeze_at = datetime.now() + timedelta(minutes=duration_minutes)
                logger.info(f"Auto-unfreeze scheduled for: {self.current_state.auto_unfreeze_at}")
            else:
                self.current_state.auto_unfreeze_at = None

            # Caps et policy selon le type de freeze
            if freeze_type == FreezeType.FULL_FREEZE:
                cap_daily = 0.01  # Très restrictif
                ramp_hours = 1
            elif freeze_type == FreezeType.S3_ALERT_FREEZE:
                cap_daily = 0.03  # Permet réductions risque
                ramp_hours = 6
            elif freeze_type == FreezeType.ERROR_FREEZE:
                cap_daily = 0.05  # Permet hedge et réductions
                ramp_hours = 12
            else:
                cap_daily = 0.01
                ramp_hours = 1

            # Update execution policy avec sémantique freeze
            allowed_ops = FreezeSemantics.get_allowed_operations(freeze_type)
            ops_summary = [k for k, v in allowed_ops.items() if v]

            self.current_state.execution_policy = Policy(
                mode="Freeze",
                cap_daily=cap_daily,
                ramp_hours=ramp_hours,
                plan_cooldown_hours=168,  # 1 week
                notes=f"Freeze {freeze_type}: {reason}. Allowed: {', '.join(ops_summary)}" +
                      (f" (auto-unfreeze: {duration_minutes}min)" if duration_minutes else "")
            )

            logger.info(f"System frozen with {freeze_type}: allowed operations: {ops_summary}")
            return True

        except Exception as e:
            logger.error(f"Error freezing system: {e}")
            return False

    async def unfreeze_system(self) -> bool:
        """Phase 1C: Unfreeze système avec nettoyage sémantique"""
        try:
            previous_freeze_type = self.current_state.freeze_type
            logger.info(f"Unfreezing system (was: {previous_freeze_type})")

            # Restore normal governance mode
            self.current_state.governance_mode = "manual"
            self.current_state.freeze_type = None  # Clear freeze type
            self.current_state.system_status = "operational"
            self.current_state.last_update = datetime.now()
            self.current_state.auto_unfreeze_at = None  # Clear auto-unfreeze

            # Derive normal execution policy
            self.current_state.execution_policy = self._derive_execution_policy()

            logger.info(f"System successfully unfrozen from {previous_freeze_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error unfreezing system: {e}")
            return False

    def validate_operation(self, operation_type: str) -> Tuple[bool, str]:
        """
        Phase 1C: Valide si une opération est autorisée selon le freeze actuel

        Args:
            operation_type: Type d'opération (new_purchases, sell_to_stables, etc.)

        Returns:
            (allowed: bool, reason: str)
        """
        try:
            current_freeze = self.current_state.freeze_type
            if current_freeze is None:
                return True, "No freeze active - operation allowed"

            return FreezeSemantics.validate_operation(current_freeze, operation_type)

        except Exception as e:
            logger.error(f"Error validating operation {operation_type}: {e}")
            return False, f"Error validating operation: {str(e)}"

    def get_freeze_status(self) -> Dict[str, Any]:
        """
        Phase 1C: Retourne le statut freeze détaillé pour UI

        Returns:
            Dict avec freeze_type, allowed_operations, remaining_time, etc.
        """
        try:
            freeze_type = self.current_state.freeze_type
            auto_unfreeze = self.current_state.auto_unfreeze_at

            if freeze_type is None:
                return {
                    "is_frozen": False,
                    "freeze_type": None,
                    "allowed_operations": FreezeSemantics.get_allowed_operations("normal"),
                    "status_message": "System operational - all operations allowed"
                }

            allowed_ops = FreezeSemantics.get_allowed_operations(freeze_type)
            remaining_minutes = None

            if auto_unfreeze:
                remaining_seconds = (auto_unfreeze - datetime.now()).total_seconds()
                remaining_minutes = max(0, int(remaining_seconds / 60))

            # Message résumé selon le type
            if freeze_type == FreezeType.S3_ALERT_FREEZE:
                status_msg = "S3 Alert Freeze: purchases blocked, risk reductions allowed"
            elif freeze_type == FreezeType.ERROR_FREEZE:
                status_msg = "Error Freeze: purchases blocked, hedge & reductions allowed"
            elif freeze_type == FreezeType.FULL_FREEZE:
                status_msg = "Full Freeze: only emergency exits allowed"
            else:
                status_msg = f"Freeze active: {freeze_type}"

            return {
                "is_frozen": True,
                "freeze_type": freeze_type,
                "allowed_operations": allowed_ops,
                "remaining_minutes": remaining_minutes,
                "auto_unfreeze_at": auto_unfreeze.isoformat() if auto_unfreeze else None,
                "status_message": status_msg
            }

        except Exception as e:
            logger.error(f"Error getting freeze status: {e}")
            return {
                "is_frozen": False,
                "freeze_type": None,
                "error": str(e)
            }

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
            
            # Phase 3C: Check if human-in-the-loop intervention is needed
            if self.hybrid_intelligence_enabled and self.human_loop:
                try:
                    # Assess if this decision needs human oversight
                    risk_assessment = await self._assess_decision_risk(plan)
                    
                    if risk_assessment.get("requires_human_review", False):
                        # Create human decision request
                        human_request = {
                            "plan_id": plan_id,
                            "decision_type": "plan_approval",
                            "risk_level": risk_assessment.get("risk_level", "medium"),
                            "context": {
                                "targets": [{"symbol": t.symbol, "weight": t.weight} for t in plan.targets],
                                "risk_factors": risk_assessment.get("risk_factors", []),
                                "ai_confidence": risk_assessment.get("ai_confidence", 0.5)
                            },
                            "deadline": datetime.now() + timedelta(hours=2),  # 2-hour timeout
                            "fallback_action": "reject"
                        }
                        
                        # Submit to human loop for review
                        human_decision = await self.human_loop.request_human_decision(
                            decision_request=human_request,
                            urgency="high" if risk_assessment.get("risk_level") == "high" else "medium"
                        )
                        
                        # If human intervention is pending, mark plan as requiring human review
                        if human_decision and not human_decision.get("completed", False):
                            plan.status = "PENDING_HUMAN_REVIEW"
                            plan.human_review_requested = datetime.now()
                            plan.human_review_context = risk_assessment
                            logger.info(f"Plan {plan_id} requires human review due to {risk_assessment.get('primary_concern', 'high risk')}")
                            return True  # Plan is in review, not yet approved
                            
                except Exception as e:
                    logger.error(f"Phase 3C human loop assessment failed for plan {plan_id}: {e}")
                    # Continue with normal approval if human loop fails
            
            # Update plan state (normal approval or human loop cleared)
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
            
            # Phase 3C: Add Hybrid Intelligence analysis
            if self.hybrid_intelligence_enabled and self.explainable_ai:
                try:
                    # Generate explainable AI analysis for the proposed plan
                    decision_context = {
                        "plan_id": proposed_plan.plan_id,
                        "targets": [{"symbol": t.symbol, "weight": t.weight} for t in target_objects],
                        "governance_mode": self.current_state.governance_mode,
                        "reason": reason,
                        "ml_signals": self.current_state.raw_signals
                    }
                    
                    # Get decision explanation from XAI
                    explanation = await self.explainable_ai.explain_decision(
                        decision_type="allocation_plan",
                        decision_context=decision_context,
                        model_predictions=self.current_state.raw_signals
                    )
                    
                    # Store explanation in plan notes for transparency
                    if explanation and explanation.explanation_text:
                        proposed_plan.notes += f"\n\nAI Explanation: {explanation.explanation_text}"
                        
                        # Add confidence and feature contributions to context
                        ai_context = {
                            "confidence": explanation.confidence_score,
                            "key_factors": [f.feature_name for f in explanation.feature_contributions[:3]],
                            "explanation_method": explanation.method_used
                        }
                        proposed_plan.context = {**proposed_plan.context, "ai_explanation": ai_context} if hasattr(proposed_plan, 'context') and proposed_plan.context else {"ai_explanation": ai_context}
                    
                    logger.info(f"Phase 3C XAI explanation added to plan {proposed_plan.plan_id}")
                    
                except Exception as e:
                    logger.error(f"Phase 3C XAI analysis failed for plan {proposed_plan.plan_id}: {e}")
            
            self.current_state.proposed_plan = proposed_plan
            self.current_state.last_update = datetime.now()
            
            # Marquer le timestamp de publication
            self._last_plan_publication = datetime.now()
            
            success_msg = f"Proposed plan created with Phase 3C analysis: {proposed_plan.plan_id}"
            logger.info(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"Error creating proposed plan: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def _assess_decision_risk(self, plan: DecisionPlan) -> Dict[str, Any]:
        """Phase 3C: Assess risk level of a decision plan to determine human oversight needs"""
        try:
            risk_factors = []
            risk_score = 0.0
            
            # Check for large allocation changes
            current_allocation = {}  # Would fetch from portfolio service
            for target in plan.targets:
                current_weight = current_allocation.get(target.symbol, 0.0)
                weight_change = abs(target.weight - current_weight)
                
                if weight_change > 0.2:  # >20% change
                    risk_factors.append(f"Large allocation change for {target.symbol}: {weight_change:.1%}")
                    risk_score += 0.3
                elif weight_change > 0.1:  # >10% change
                    risk_factors.append(f"Significant allocation change for {target.symbol}: {weight_change:.1%}")
                    risk_score += 0.15
            
            # Check AI confidence from XAI analysis
            ai_context = getattr(plan, 'context', {}).get("ai_explanation", {})
            ai_confidence = ai_context.get("confidence", 0.5)
            
            if ai_confidence < 0.6:
                risk_factors.append(f"Low AI confidence: {ai_confidence:.2f}")
                risk_score += 0.2
            elif ai_confidence < 0.7:
                risk_factors.append(f"Medium AI confidence: {ai_confidence:.2f}")
                risk_score += 0.1
            
            # Check market volatility from ML signals
            if hasattr(self.current_state, 'raw_signals') and self.current_state.raw_signals:
                volatility_data = self.current_state.raw_signals.get('models', {}).get('volatility', {})
                high_vol_assets = []
                
                for symbol, vol_predictions in volatility_data.items():
                    if isinstance(vol_predictions, dict):
                        for horizon, data in vol_predictions.items():
                            if isinstance(data, dict) and data.get('volatility_forecast', 0) > 0.4:
                                high_vol_assets.append(symbol)
                                break
                
                if high_vol_assets:
                    risk_factors.append(f"High volatility assets: {', '.join(high_vol_assets)}")
                    risk_score += 0.2
            
            # Check governance mode
            if plan.governance_mode in ["full_ai"]:
                risk_factors.append("Full AI mode requires additional oversight")
                risk_score += 0.1
            
            # Determine risk level and human review requirement
            if risk_score >= 0.5:
                risk_level = "high"
                requires_human_review = True
                primary_concern = "Multiple high-risk factors detected"
            elif risk_score >= 0.3:
                risk_level = "medium"
                requires_human_review = True
                primary_concern = "Moderate risk factors present"
            else:
                risk_level = "low"
                requires_human_review = False
                primary_concern = None
            
            return {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "requires_human_review": requires_human_review,
                "risk_factors": risk_factors,
                "primary_concern": primary_concern,
                "ai_confidence": ai_confidence,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error assessing decision risk: {e}")
            return {
                "risk_score": 0.5,
                "risk_level": "medium",
                "requires_human_review": True,
                "risk_factors": ["Risk assessment failed"],
                "primary_concern": "Unable to assess risk",
                "ai_confidence": 0.5,
                "error": str(e)
            }
    
    async def record_plan_outcome(self, plan_id: str, outcome: str, performance_data: Dict[str, Any] = None):
        """Phase 3C: Record plan execution outcome for feedback learning"""
        if not self.hybrid_intelligence_enabled or not self.feedback_learning:
            return
            
        try:
            plan = self._find_plan_by_id(plan_id)
            if not plan:
                logger.warning(f"Cannot record outcome for unknown plan: {plan_id}")
                return
            
            # Create feedback data
            feedback_data = {
                "plan_id": plan_id,
                "outcome": outcome,
                "targets": [{"symbol": t.symbol, "weight": t.weight} for t in plan.targets],
                "governance_mode": plan.governance_mode,
                "ai_explanation": getattr(plan, 'context', {}).get("ai_explanation", {}),
                "risk_assessment": getattr(plan, 'human_review_context', {}),
                "performance_data": performance_data or {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Submit to feedback learning system
            await self.feedback_learning.record_decision_outcome(
                decision_id=plan_id,
                outcome=outcome,
                feedback_data=feedback_data
            )
            
            logger.info(f"Phase 3C: Recorded outcome '{outcome}' for plan {plan_id}")
            
        except Exception as e:
            logger.error(f"Phase 3C: Error recording plan outcome for {plan_id}: {e}")

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
