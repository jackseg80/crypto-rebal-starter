"""
ML Gating System avec calibration et gestion d'incertitude
Système de validation et contrôle qualité pour prédictions ML
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from scipy.stats import norm

from api.schemas.ml_contract import (
    UnifiedPrediction, QualityMetrics, UncertaintyMeasures,
    ModelType, ConfidenceLevel
)

logger = logging.getLogger(__name__)


# === DATACLASSES DE CONFIGURATION ===

@dataclass
class GatingConfig:
    """Configuration du système de gating"""
    min_confidence: float = 0.3
    max_uncertainty: float = 2.0
    drift_threshold: float = 0.15
    error_rate_threshold: float = 0.2
    staleness_threshold_hours: float = 24.0
    enable_calibration: bool = True
    fallback_confidence: float = 0.1


@dataclass
class CalibrationMetrics:
    """Métriques de calibration d'un modèle"""
    reliability: float  # ECE - Expected Calibration Error
    sharpness: float    # Moyenne de la variance des prédictions
    mae: float         # Mean Absolute Error
    coverage_80: float # Couverture à 80%
    coverage_95: float # Couverture à 95%
    last_updated: datetime


# === CALIBRATEUR UNIFIE ===

class UnifiedCalibrator:
    """Calibrateur unifié pour différents types de prédictions"""

    def __init__(self, method: str = "platt"):
        """
        Initialiser le calibrateur

        Args:
            method: "platt" (sigmoid) ou "isotonic"
        """
        self.method = method
        self.calibrators: Dict[str, Any] = {}
        self.is_fitted: Dict[str, bool] = {}

    def fit(self, model_key: str, predictions: np.ndarray, true_values: np.ndarray):
        """
        Entraîner le calibrateur pour un modèle donné

        Args:
            model_key: Identifiant du modèle
            predictions: Prédictions brutes
            true_values: Valeurs réelles
        """
        try:
            if self.method == "platt":
                # Calibration Platt (sigmoid) - utiliser LogisticRegression directement
                calibrator = LogisticRegression()
                # Normaliser pour classification binaire
                binary_targets = (true_values > np.median(true_values)).astype(int)
                calibrator.fit(predictions.reshape(-1, 1), binary_targets)
            else:
                # Calibration isotonique
                calibrator = IsotonicRegression(out_of_bounds='clip')
                calibrator.fit(predictions, true_values)

            self.calibrators[model_key] = calibrator
            self.is_fitted[model_key] = True

            logger.info(f"Calibrator fitted for model {model_key} using {self.method}")

        except Exception as e:
            logger.error(f"Failed to fit calibrator for {model_key}: {e}")
            self.is_fitted[model_key] = False

    def calibrate_prediction(self, model_key: str, raw_prediction: float) -> Tuple[float, float]:
        """
        Calibrer une prédiction

        Returns:
            Tuple (prediction_calibrée, confiance_calibrée)
        """
        if model_key not in self.calibrators or not self.is_fitted.get(model_key, False):
            # Pas de calibration disponible
            return raw_prediction, 0.5

        try:
            calibrator = self.calibrators[model_key]

            if self.method == "platt":
                # Proba de classe positive comme confiance
                confidence = calibrator.predict_proba([[raw_prediction]])[0][1]
                return raw_prediction, float(confidence)
            else:
                # Isotonic regression
                calibrated = calibrator.predict([raw_prediction])[0]
                # Confiance basée sur la distance à la médiane historique
                confidence = max(0.1, min(0.9, 1.0 - abs(calibrated - raw_prediction)))
                return float(calibrated), float(confidence)

        except Exception as e:
            logger.error(f"Calibration failed for {model_key}: {e}")
            return raw_prediction, 0.3


# === SYSTEME DE GATING ===

class MLGatingSystem:
    """Système de contrôle qualité et validation ML"""

    def __init__(self, config: Optional[GatingConfig] = None):
        self.config = config or GatingConfig()
        self.calibrator = UnifiedCalibrator()
        self.model_metrics: Dict[str, CalibrationMetrics] = {}
        self.prediction_history: Dict[str, List[Dict]] = {}

    def compute_uncertainty_measures(
        self,
        prediction: float,
        model_key: str,
        confidence: float
    ) -> UncertaintyMeasures:
        """
        Calculer les mesures d'incertitude

        Args:
            prediction: Valeur prédite
            model_key: Identifiant du modèle
            confidence: Confiance [0,1]
        """
        try:
            # Calcul de l'écart-type basé sur la confiance
            # Plus la confiance est faible, plus l'incertitude est élevée
            base_std = abs(prediction) * (1 - confidence) * 0.5

            # Ajustement selon l'historique du modèle
            if model_key in self.model_metrics:
                metrics = self.model_metrics[model_key]
                # Ajuster selon la fiabilité historique
                reliability_factor = max(0.5, metrics.reliability)
                base_std = base_std / reliability_factor

            # Intervalles de confiance (approximation normale)
            z_scores = {
                ConfidenceLevel.LOW: 1.28,    # 80%
                ConfidenceLevel.MEDIUM: 1.64, # 90%
                ConfidenceLevel.HIGH: 1.96,   # 95%
                ConfidenceLevel.VERY_HIGH: 2.58 # 99%
            }

            # Utiliser 90% par défaut
            z_score = z_scores[ConfidenceLevel.MEDIUM]
            margin = z_score * base_std

            return UncertaintyMeasures(
                std=base_std,
                lower_bound=prediction - margin,
                upper_bound=prediction + margin,
                confidence_level=ConfidenceLevel.MEDIUM,
                calibration_score=confidence
            )

        except Exception as e:
            logger.error(f"Failed to compute uncertainty for {model_key}: {e}")
            # Fallback avec haute incertitude
            return UncertaintyMeasures(
                std=abs(prediction) * 0.5,
                lower_bound=prediction * 0.5,
                upper_bound=prediction * 1.5,
                confidence_level=ConfidenceLevel.LOW,
                calibration_score=0.3
            )

    def compute_quality_metrics(
        self,
        model_key: str,
        data_age_hours: Optional[float] = None,
        feature_availability: Optional[float] = None
    ) -> QualityMetrics:
        """
        Calculer les métriques de qualité

        Args:
            model_key: Identifiant du modèle
            data_age_hours: Âge des données en heures
            feature_availability: Disponibilité des features [0,1]
        """
        try:
            # Confiance de base selon l'historique du modèle
            base_confidence = 0.5
            if model_key in self.model_metrics:
                metrics = self.model_metrics[model_key]
                base_confidence = max(0.3, min(0.9, metrics.reliability))

            # Pénalité pour données anciennes
            freshness_penalty = 0.0
            if data_age_hours is not None:
                if data_age_hours > self.config.staleness_threshold_hours:
                    freshness_penalty = min(0.3, (data_age_hours - self.config.staleness_threshold_hours) / 100)

            # Pénalité pour features manquantes
            feature_penalty = 0.0
            if feature_availability is not None:
                feature_penalty = (1.0 - feature_availability) * 0.2

            # Confiance ajustée
            final_confidence = max(0.1, base_confidence - freshness_penalty - feature_penalty)

            # Santé du modèle basée sur l'historique récent
            model_health = 0.8
            if model_key in self.prediction_history:
                recent_predictions = self.prediction_history[model_key][-50:]  # 50 dernières
                if recent_predictions:
                    error_count = sum(1 for p in recent_predictions if p.get('error', False))
                    error_rate = error_count / len(recent_predictions)
                    model_health = max(0.3, 1.0 - error_rate)

            return QualityMetrics(
                confidence=final_confidence,
                data_freshness=data_age_hours,
                feature_coverage=feature_availability,
                model_health=model_health
            )

        except Exception as e:
            logger.error(f"Failed to compute quality metrics for {model_key}: {e}")
            return QualityMetrics(confidence=self.config.fallback_confidence)

    def gate_prediction(
        self,
        asset: str,
        raw_prediction: float,
        model_key: str,
        model_type: ModelType,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[UnifiedPrediction, bool]:
        """
        Appliquer le gating sur une prédiction

        Returns:
            Tuple (prédiction_traitée, acceptée)
        """
        try:
            context = context or {}

            # 1. Calibration de la prédiction
            calibrated_pred, confidence = self.calibrator.calibrate_prediction(
                model_key, raw_prediction
            )

            # 2. Calcul des métriques de qualité
            quality = self.compute_quality_metrics(
                model_key=model_key,
                data_age_hours=context.get('data_age_hours'),
                feature_availability=context.get('feature_availability')
            )

            # 3. Calcul des mesures d'incertitude
            uncertainty = self.compute_uncertainty_measures(
                calibrated_pred, model_key, confidence
            )

            # 4. Décision d'acceptation
            accept = self._should_accept_prediction(quality, uncertainty)

            # 5. Construction de la prédiction
            prediction = UnifiedPrediction(
                asset=asset,
                value=calibrated_pred,
                uncertainty=uncertainty,
                quality=quality
            )

            # 6. Mise à jour de l'historique
            self._update_prediction_history(model_key, {
                'prediction': calibrated_pred,
                'confidence': confidence,
                'accepted': accept,
                'timestamp': datetime.now(),
                'error': False
            })

            return prediction, accept

        except Exception as e:
            logger.error(f"Gating failed for {asset} with model {model_key}: {e}")

            # Prédiction de fallback
            fallback_prediction = UnifiedPrediction(
                asset=asset,
                value=0.0,
                uncertainty=UncertaintyMeasures(
                    std=999.0,
                    calibration_score=0.0
                ),
                quality=QualityMetrics(confidence=self.config.fallback_confidence)
            )

            self._update_prediction_history(model_key, {
                'error': True,
                'timestamp': datetime.now()
            })

            return fallback_prediction, False

    def _should_accept_prediction(
        self,
        quality: QualityMetrics,
        uncertainty: UncertaintyMeasures
    ) -> bool:
        """Décider si une prédiction doit être acceptée"""

        # Vérifications de base
        if quality.confidence < self.config.min_confidence:
            return False

        if uncertainty.std and uncertainty.std > self.config.max_uncertainty:
            return False

        if quality.model_health and quality.model_health < 0.5:
            return False

        return True

    def _update_prediction_history(self, model_key: str, record: Dict):
        """Mettre à jour l'historique des prédictions"""
        if model_key not in self.prediction_history:
            self.prediction_history[model_key] = []

        self.prediction_history[model_key].append(record)

        # Garder seulement les 1000 dernières entrées
        if len(self.prediction_history[model_key]) > 1000:
            self.prediction_history[model_key] = self.prediction_history[model_key][-1000:]

    def get_model_health_report(self, model_key: str) -> Dict[str, Any]:
        """Obtenir un rapport de santé pour un modèle"""
        if model_key not in self.prediction_history:
            return {"error": "No history available"}

        history = self.prediction_history[model_key]
        recent_history = [h for h in history if h.get('timestamp') and
                         h['timestamp'] > datetime.now() - timedelta(hours=24)]

        if not recent_history:
            return {"error": "No recent predictions"}

        total_predictions = len(recent_history)
        errors = sum(1 for h in recent_history if h.get('error', False))
        accepted = sum(1 for h in recent_history if h.get('accepted', False))
        avg_confidence = np.mean([h.get('confidence', 0) for h in recent_history])

        return {
            "model_key": model_key,
            "total_predictions_24h": total_predictions,
            "error_rate": errors / total_predictions,
            "acceptance_rate": accepted / total_predictions,
            "avg_confidence": float(avg_confidence),
            "last_prediction": max(h['timestamp'] for h in recent_history),
            "health_score": quality.model_health if model_key in self.model_metrics else 0.5
        }


# === INSTANCE GLOBALE ===

# Instance globale du système de gating
_global_gating_system: Optional[MLGatingSystem] = None


def get_gating_system() -> MLGatingSystem:
    """Obtenir l'instance globale du système de gating"""
    global _global_gating_system
    if _global_gating_system is None:
        _global_gating_system = MLGatingSystem()
    return _global_gating_system


def initialize_gating_system(config: Optional[GatingConfig] = None) -> MLGatingSystem:
    """Initialiser le système de gating avec une configuration"""
    global _global_gating_system
    _global_gating_system = MLGatingSystem(config)
    return _global_gating_system