"""
Contrat prédictif unifié pour les modèles ML
Schémas standardisés pour entrées/sorties ML avec gestion d'incertitude et métadonnées
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union, Literal
from datetime import datetime
from enum import Enum


# === TYPES DE BASE ===

class ModelType(str, Enum):
    """Types de modèles supportés"""
    VOLATILITY = "volatility"
    SENTIMENT = "sentiment"
    REGIME = "regime"
    CORRELATION = "correlation"
    RISK = "risk"
    BLENDED = "blended"


class Horizon(str, Enum):
    """Horizons temporels standardisés"""
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    D7 = "7d"
    D30 = "30d"
    D90 = "90d"


class ConfidenceLevel(str, Enum):
    """Niveaux de confiance pour intervalles"""
    LOW = "80"
    MEDIUM = "90"
    HIGH = "95"
    VERY_HIGH = "99"


# === METADATA ET QUALITE ===

class ModelMetadata(BaseModel):
    """Métadonnées du modèle utilisé"""
    model_config = {"protected_namespaces": ()}

    name: str = Field(description="Nom du modèle")
    version: str = Field(description="Version du modèle (semver)")
    trained_at: Optional[datetime] = Field(None, description="Date d'entraînement")
    features_used: Optional[List[str]] = Field(None, description="Features utilisées")
    model_type: ModelType = Field(description="Type de modèle")
    horizon: Optional[Horizon] = Field(None, description="Horizon prédit")


class UncertaintyMeasures(BaseModel):
    """Mesures d'incertitude standardisées"""
    std: Optional[float] = Field(None, description="Écart-type de prédiction")
    lower_bound: Optional[float] = Field(None, description="Borne inférieure (PI)")
    upper_bound: Optional[float] = Field(None, description="Borne supérieure (PI)")
    confidence_level: Optional[ConfidenceLevel] = Field(None, description="Niveau de confiance")
    calibration_score: Optional[float] = Field(None, ge=0, le=1, description="Score de calibration [0,1]")


class QualityMetrics(BaseModel):
    """Métriques de qualité de prédiction"""
    model_config = {"protected_namespaces": ()}

    confidence: float = Field(ge=0, le=1, description="Confiance globale [0,1]")
    data_freshness: Optional[float] = Field(None, description="Fraîcheur données (heures)")
    feature_coverage: Optional[float] = Field(None, ge=0, le=1, description="Couverture features [0,1]")
    model_health: Optional[float] = Field(None, ge=0, le=1, description="Santé modèle [0,1]")


# === REQUETES UNIFIEES ===

class UnifiedMLRequest(BaseModel):
    """Requête ML unifiée"""
    model_config = {"protected_namespaces": ()}

    assets: List[str] = Field(max_items=50, description="Liste des actifs")
    model_type: ModelType = Field(description="Type de prédiction demandée")
    horizon: Optional[Horizon] = Field(None, description="Horizon temporel")

    # Options de qualité
    include_uncertainty: bool = Field(False, description="Inclure mesures d'incertitude")
    include_metadata: bool = Field(False, description="Inclure métadonnées modèle")
    confidence_threshold: float = Field(0.5, ge=0, le=1, description="Seuil confiance minimum")

    # Paramètres contextuels
    context: Optional[Dict[str, Any]] = Field(None, description="Contexte additionnel")
    cache_ttl: Optional[int] = Field(300, description="TTL cache en secondes")


class BatchMLRequest(BaseModel):
    """Requête ML batch pour multiple modèles/horizons"""
    assets: List[str] = Field(max_items=20, description="Actifs à analyser")
    requests: List[Dict[str, Any]] = Field(max_items=10, description="Requêtes multiples")
    global_options: Optional[Dict[str, Any]] = Field(None, description="Options globales")


# === REPONSES UNIFIEES ===

class UnifiedPrediction(BaseModel):
    """Prédiction unitaire avec incertitude"""
    asset: str = Field(description="Actif concerné")
    value: float = Field(description="Valeur prédite")

    # Incertitude (optionnel)
    uncertainty: Optional[UncertaintyMeasures] = Field(None, description="Mesures d'incertitude")

    # Qualité
    quality: QualityMetrics = Field(description="Métriques de qualité")

    # Métadonnées (optionnel)
    metadata: Optional[ModelMetadata] = Field(None, description="Info modèle utilisé")


class UnifiedMLResponse(BaseModel):
    """Réponse ML unifiée"""
    model_config = {"protected_namespaces": ()}

    success: bool = Field(True, description="Statut de succès")
    model_type: ModelType = Field(description="Type de modèle utilisé")
    horizon: Optional[Horizon] = Field(None, description="Horizon prédit")

    # Données principales
    predictions: List[UnifiedPrediction] = Field(description="Prédictions par actif")

    # Agrégations (optionnel)
    aggregated: Optional[Dict[str, float]] = Field(None, description="Métriques agrégées")

    # Contexte global
    processed_at: datetime = Field(default_factory=datetime.now, description="Timestamp traitement")
    cache_hit: bool = Field(False, description="Résultat depuis cache")
    processing_time_ms: Optional[float] = Field(None, description="Temps de traitement")

    # Gestion d'erreurs
    warnings: List[str] = Field(default_factory=list, description="Avertissements")
    failed_assets: List[str] = Field(default_factory=list, description="Actifs en échec")


class BatchMLResponse(BaseModel):
    """Réponse ML batch"""
    success: bool = Field(True, description="Succès global")
    responses: Dict[str, UnifiedMLResponse] = Field(description="Réponses par requête")
    global_metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées globales")
    total_processing_time_ms: Optional[float] = Field(None, description="Temps total")


# === SCHEMAS SPECIFIQUES ===

class VolatilityPrediction(UnifiedPrediction):
    """Prédiction de volatilité avec spécificités"""
    annualized_vol: Optional[float] = Field(None, description="Volatilité annualisée")
    regime_context: Optional[str] = Field(None, description="Contexte de régime")


class SentimentPrediction(UnifiedPrediction):
    """Prédiction de sentiment avec détails"""
    sentiment_breakdown: Optional[Dict[str, float]] = Field(None, description="Détail par source")
    fear_greed_index: Optional[float] = Field(None, ge=0, le=100, description="Indice Fear & Greed")


class RiskScorePrediction(UnifiedPrediction):
    """Score de risque avec composantes"""
    components: Optional[Dict[str, float]] = Field(None, description="Composantes du score")
    risk_category: Optional[str] = Field(None, description="Catégorie de risque")


# === SCHEMAS DE MONITORING ===

class ModelHealth(BaseModel):
    """Santé d'un modèle"""
    model_config = {"protected_namespaces": ()}

    model_name: str = Field(description="Nom du modèle")
    version: str = Field(description="Version")
    is_healthy: bool = Field(description="État de santé")
    last_prediction: Optional[datetime] = Field(None, description="Dernière prédiction")
    error_rate_24h: Optional[float] = Field(None, description="Taux d'erreur 24h")
    avg_confidence: Optional[float] = Field(None, description="Confiance moyenne")
    drift_score: Optional[float] = Field(None, description="Score de drift")


class MLSystemHealth(BaseModel):
    """Santé globale du système ML"""
    overall_health: float = Field(ge=0, le=1, description="Santé globale [0,1]")
    models_status: List[ModelHealth] = Field(description="Statut par modèle")
    system_metrics: Dict[str, Any] = Field(default_factory=dict, description="Métriques système")
    last_check: datetime = Field(default_factory=datetime.now, description="Dernière vérification")


# === UTILITY FUNCTIONS ===

def create_fallback_response(
    model_type: ModelType,
    assets: List[str],
    error_msg: str = "Model unavailable"
) -> UnifiedMLResponse:
    """Créer une réponse de fallback avec confiance faible"""
    predictions = [
        UnifiedPrediction(
            asset=asset,
            value=0.0,
            quality=QualityMetrics(confidence=0.1),
            uncertainty=UncertaintyMeasures(std=999.0)
        )
        for asset in assets
    ]

    return UnifiedMLResponse(
        success=False,
        model_type=model_type,
        predictions=predictions,
        warnings=[error_msg],
        failed_assets=assets
    )


def validate_prediction_quality(prediction: UnifiedPrediction, min_confidence: float = 0.3) -> bool:
    """Valider la qualité d'une prédiction"""
    return prediction.quality.confidence >= min_confidence