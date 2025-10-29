"""
Score Registry Centralisé pour Decision Engine Unifié

Ce module centralise la configuration et le calcul du score canonique :
- Poids configurables avec hot-reload
- Score canonique 0-100 + 4 sous-scores explicatifs  
- Gestion de la contradiction avec pénalité bornée
- Fallback dégradé si config indisponible
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel, Field
import asyncio

logger = logging.getLogger(__name__)

class ScoreComponents(BaseModel):
    """Composants du score décisionnel"""
    trend_regime: float = Field(default=50.0, ge=0.0, le=100.0, description="Tendance et régime")
    risk: float = Field(default=50.0, ge=0.0, le=100.0, description="Métriques de risque")
    breadth_rotation: float = Field(default=50.0, ge=0.0, le=100.0, description="Largeur de marché et rotation")
    sentiment: float = Field(default=50.0, ge=0.0, le=100.0, description="Sentiment de marché")

class CanonicalScores(BaseModel):
    """Score canonique avec sous-scores explicatifs"""
    decision: float = Field(..., ge=0.0, le=100.0, description="Score décisionnel principal 0-100")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiance dans la décision")
    contradiction: float = Field(..., ge=0.0, le=1.0, description="Index de contradiction")
    components: ScoreComponents = Field(..., description="Sous-scores explicatifs")
    as_of: datetime = Field(default_factory=datetime.now, description="Timestamp de calcul")

class ScoreWeights(BaseModel):
    """Poids configurables pour le calcul du score"""
    trend_regime: float = Field(default=0.35, ge=0.0, le=1.0)
    risk: float = Field(default=0.25, ge=0.0, le=1.0) 
    breadth_rotation: float = Field(default=0.25, ge=0.0, le=1.0)
    sentiment: float = Field(default=0.15, ge=0.0, le=1.0)
    
    def __post_init__(self):
        total = self.trend_regime + self.risk + self.breadth_rotation + self.sentiment
        if abs(total - 1.0) > 0.001:
            logger.warning(f"Score weights don't sum to 1.0: {total:.3f}")

class ScoreConfig(BaseModel):
    """Configuration complète du Score Registry"""
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    contradiction_penalty_cap: float = Field(default=0.30, ge=0.0, le=0.5, description="Cap de pénalité contradiction")
    volatility_window_days: int = Field(default=30, ge=7, le=90, description="Fenêtre volatilité")
    correlation_window_days: int = Field(default=90, ge=30, le=180, description="Fenêtre corrélation")
    sentiment_smoothing_days: int = Field(default=7, ge=1, le=30, description="Lissage sentiment")
    
    # Bandes avec hystérésis
    bands: Dict[str, Tuple[float, float]] = Field(
        default={
            "conservative": (0, 39),
            "moderate": (40, 59), 
            "aggressive": (60, 79),
            "high_conviction": (80, 100)
        },
        description="Bandes décisionnelles"
    )
    band_hysteresis: float = Field(default=3.0, ge=1.0, le=10.0, description="Delta min pour changer de bande")
    
    # Facteurs de phase pour alertes
    phase_factors: Dict[str, Dict[str, float]] = Field(
        default={
            "volatility": {"btc": 1.0, "eth": 1.1, "large": 1.2, "alt": 1.3},
            "correlation": {"btc": 1.0, "eth": 1.0, "large": 1.1, "alt": 1.2},
            "regime_flip": {"btc": 1.0, "eth": 1.1, "large": 1.2, "alt": 1.3}
        },
        description="Facteurs multiplicateurs par phase pour alertes"
    )
    
    version: str = Field(default="1.0", description="Version de la configuration")
    last_updated: datetime = Field(default_factory=datetime.now)

class ScoreRegistry:
    """
    Registry centralisé pour la configuration et calcul des scores
    
    Fonctionnalités :
    - Hot-reload de la config depuis fichier JSON
    - Calcul score canonique avec pénalité contradiction bornée
    - Fallback dégradé si config indisponible
    - Cache intelligent avec TTL
    """
    
    def __init__(self, config_path: str = "config/score_registry.json"):
        self.config_path = Path(config_path)
        self.config: Optional[ScoreConfig] = None
        self.config_loaded_at: Optional[datetime] = None
        self.fallback_config = ScoreConfig()  # Config par défaut embarquée
        
        # Cache des derniers scores avec TTL
        self._score_cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        logger.info(f"ScoreRegistry initialized with config path: {self.config_path}")
    
    async def load_config(self) -> bool:
        """
        Charge la configuration depuis le fichier JSON
        Retourne True si succès, False si fallback utilisé
        """
        try:
            if not self.config_path.exists():
                logger.warning(f"Score config not found at {self.config_path}, creating default")
                await self._create_default_config()
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            self.config = ScoreConfig(**config_data)
            self.config_loaded_at = datetime.now()
            
            logger.info(f"Score config loaded successfully (version: {self.config.version})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load score config: {e}")
            logger.warning("Using fallback embedded config")
            
            self.config = self.fallback_config
            self.config_loaded_at = datetime.now()
            return False
    
    async def _create_default_config(self):
        """Crée un fichier de configuration par défaut"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            default_config = ScoreConfig()
            config_dict = default_config.dict()
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, default=str)
                
            logger.info(f"Default score config created at {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to create default config: {e}")
    
    async def get_config(self) -> ScoreConfig:
        """Retourne la config actuelle, charge si nécessaire"""
        if self.config is None:
            await self.load_config()
        return self.config
    
    async def calculate_canonical_score(
        self, 
        trend_regime: float = 50.0,
        risk: float = 50.0, 
        breadth_rotation: float = 50.0,
        sentiment: float = 50.0,
        contradiction_index: float = 0.0,
        confidence: float = 0.75
    ) -> CanonicalScores:
        """
        Calcul du score canonique avec ordre documenté :
        1. Composants → clamp [0-100]
        2. Score pondéré 
        3. Pénalité contradiction → bornée
        4. Clamp final [0-100]
        """
        try:
            config = await self.get_config()
            
            # 1. Clamp des composants [0-100]
            components = ScoreComponents(
                trend_regime=max(0.0, min(100.0, trend_regime)),
                risk=max(0.0, min(100.0, risk)),
                breadth_rotation=max(0.0, min(100.0, breadth_rotation)),
                sentiment=max(0.0, min(100.0, sentiment))
            )
            
            # 2. Score pondéré
            weights = config.weights
            raw_score = (
                components.trend_regime * weights.trend_regime +
                components.risk * weights.risk +
                components.breadth_rotation * weights.breadth_rotation + 
                components.sentiment * weights.sentiment
            )
            
            # 3. Pénalité contradiction bornée
            contradiction_clamped = max(0.0, min(1.0, contradiction_index))
            max_penalty = config.contradiction_penalty_cap * raw_score  # Ex: max 30% du score
            actual_penalty = contradiction_clamped * max_penalty
            
            penalized_score = raw_score - actual_penalty
            
            # 4. Clamp final [0-100]
            final_score = max(0.0, min(100.0, penalized_score))
            
            logger.debug(
                f"Score calculation: raw={raw_score:.1f}, "
                f"contradiction={contradiction_clamped:.3f}, "
                f"penalty={actual_penalty:.1f}, final={final_score:.1f}"
            )
            
            return CanonicalScores(
                decision=final_score,
                confidence=max(0.0, min(1.0, confidence)),
                contradiction=contradiction_clamped,
                components=components,
                as_of=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error calculating canonical score: {e}")
            
            # Fallback score conservateur
            return CanonicalScores(
                decision=50.0,  # Score neutre
                confidence=0.1,  # Confiance très faible
                contradiction=0.5,  # Contradiction moyenne
                components=ScoreComponents(),  # Composants par défaut
                as_of=datetime.now()
            )
    
    def get_band_for_score(self, score: float, previous_band: Optional[str] = None) -> str:
        """
        Retourne la bande décisionnelle avec hystérésis
        """
        try:
            config = self.config or self.fallback_config
            bands = config.bands
            hysteresis = config.band_hysteresis
            
            # Déterminer la nouvelle bande sans hystérésis
            new_band = None
            for band_name, (min_val, max_val) in bands.items():
                if min_val <= score <= max_val:
                    new_band = band_name
                    break
            
            if new_band is None:
                new_band = "moderate"  # Fallback
            
            # Appliquer hystérésis si on a une bande précédente
            if previous_band and previous_band != new_band:
                # Vérifier si le changement dépasse le seuil d'hystérésis
                prev_range = bands.get(previous_band, (40, 59))
                prev_center = (prev_range[0] + prev_range[1]) / 2
                
                if abs(score - prev_center) < hysteresis:
                    logger.debug(f"Hysteresis: keeping {previous_band} (score={score:.1f}, delta={abs(score-prev_center):.1f})")
                    return previous_band
            
            logger.debug(f"Band for score {score:.1f}: {new_band}" + (f" (was {previous_band})" if previous_band else ""))
            return new_band
            
        except Exception as e:
            logger.error(f"Error getting band for score: {e}")
            return "moderate"
    
    def get_phase_factor(self, alert_type: str, phase: str) -> float:
        """Retourne le facteur multiplicateur pour une phase donnée"""
        try:
            config = self.config or self.fallback_config
            return config.phase_factors.get(alert_type, {}).get(phase, 1.0)
        except Exception as e:
            logger.warning(f"Failed to get phase factor for {alert_type}/{phase}: {e}, using default")
            return 1.0
    
    async def health_check(self) -> Dict[str, Any]:
        """Vérification de santé du registry"""
        try:
            config_age_minutes = 0
            config_status = "unknown"
            
            if self.config_loaded_at:
                config_age_minutes = (datetime.now() - self.config_loaded_at).total_seconds() / 60
                config_status = "loaded" if self.config_path.exists() else "fallback"
            
            return {
                "status": "healthy" if self.config else "degraded",
                "config_status": config_status,
                "config_version": self.config.version if self.config else "fallback",
                "config_age_minutes": round(config_age_minutes, 1),
                "config_path": str(self.config_path),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# Instance globale singleton
_score_registry: Optional[ScoreRegistry] = None

def get_score_registry() -> ScoreRegistry:
    """Retourne l'instance singleton du ScoreRegistry"""
    global _score_registry
    if _score_registry is None:
        _score_registry = ScoreRegistry()
    return _score_registry

# Hot-reload automatique en arrière-plan
async def start_config_watcher():
    """Démarre le watcher pour hot-reload de la config"""
    registry = get_score_registry()
    
    while True:
        try:
            if registry.config_path.exists():
                stat = registry.config_path.stat()
                if (registry.config_loaded_at is None or 
                    stat.st_mtime > registry.config_loaded_at.timestamp()):
                    
                    logger.info("Score config file changed, reloading...")
                    success = await registry.load_config()
                    status = "success" if success else "fallback"
                    logger.info(f"Score config reload: {status}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Config watcher error: {e}")
            await asyncio.sleep(60)  # Wait longer on error