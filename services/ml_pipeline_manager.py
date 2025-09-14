# Module de compatibilité pour charger les anciens modèles
"""
Compatibility module for loading old ML models
"""

# Import des classes actuelles
from services.ml.models.regime_detector import RegimeClassificationNetwork as RegimeClassifier
from services.ml.models.volatility_predictor import VolatilityLSTM as VolatilityPredictor

# Exporter pour la compatibilité
__all__ = ['RegimeClassifier', 'VolatilityPredictor']