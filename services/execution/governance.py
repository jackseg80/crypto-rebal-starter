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
    cooldown_hours: int = Field(default=24, ge=1, le=168, description="Cooldown entre plans [1-168h]")
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
    
    # Contenu du plan
    targets: List[Target] = Field(..., description="Cibles d'allocation")
    governance_mode: GovernanceMode = Field(..., description="Mode de gouvernance")
    
    # Constraints et validation
    total_weight: float = Field(default=1.0, description="Somme des poids (doit = 1.0)")
    risk_budget: Optional[float] = Field(default=None, description="Budget de risque")
    non_removable: List[str] = Field(default_factory=list, description="Assets non supprimables")
    
    # Metadata
    created_by: str = Field(default="system", description="Créateur du plan")
    approved_by: Optional[str] = Field(default=None, description="Approbateur")
    notes: Optional[str] = Field(default=None, description="Notes du plan")

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
        self._last_signals_fetch = datetime.min
        self._signals_cache_ttl = 300  # 5 minutes
        
        logger.info("GovernanceEngine initialized")
    
    async def get_current_state(self) -> DecisionState:
        """
        Retourne l'état actuel du Decision Engine
        Agrège : store local + signaux ML + policy dérivée
        """
        try:
            # Refresh signals si nécessaire
            if (datetime.now() - self._last_signals_fetch).seconds > self._signals_cache_ttl:
                await self._refresh_ml_signals()
            
            # Dérive la policy depuis les signaux
            self.current_state.execution_policy = self._derive_execution_policy()
            self.current_state.last_update = datetime.now()
            
            logger.debug(f"Current governance state: mode={self.current_state.governance_mode}, "
                        f"contradiction={self.current_state.signals.contradiction_index:.3f}")
            
            return self.current_state
            
        except Exception as e:
            logger.error(f"Error getting current state: {e}")
            # Fallback : état par défaut safe
            return DecisionState(
                governance_mode="manual",
                execution_policy=Policy(mode="Freeze", cap_daily=0.01),
                system_status="error"
            )
    
    async def _refresh_ml_signals(self) -> None:
        """Refresh les signaux ML depuis les endpoints unifiés"""
        try:
            async with httpx.AsyncClient() as client:
                # Appel aux endpoints ML existants
                signals_response = await client.get(f"{self.api_base_url}/api/ml/status")
                if signals_response.status_code == 200:
                    ml_status = signals_response.json()
                    
                    # Extraire les signaux pertinents
                    self.current_state.signals = MLSignals(
                        as_of=datetime.now(),
                        volatility=self._extract_volatility_signals(ml_status),
                        regime=self._extract_regime_signals(ml_status),
                        correlation=self._extract_correlation_signals(ml_status),
                        sentiment=self._extract_sentiment_signals(ml_status),
                        decision_score=0.6,  # À calculer depuis les signaux
                        confidence=0.75,     # À calculer depuis les signaux
                        contradiction_index=self._compute_contradiction_index(ml_status),
                        sources_used=["volatility", "regime", "correlation", "sentiment"]
                    )
                    
                    self._last_signals_fetch = datetime.now()
                    logger.debug("ML signals refreshed successfully")
                    
        except Exception as e:
            logger.warning(f"Failed to refresh ML signals: {e}")
            # Garder les signaux précédents
    
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
                
            policy = Policy(
                mode=mode,
                cap_daily=cap,
                ramp_hours=ramp_hours,
                min_trade=100.0,
                slippage_limit_bps=50,
                cooldown_hours=24,
                notes=f"Derived from ML signals: contradiction={contradiction:.2f}, confidence={confidence:.2f}"
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

# Instance globale pour réutilisation
governance_engine = GovernanceEngine()