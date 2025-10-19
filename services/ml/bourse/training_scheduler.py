"""
ML Training Scheduler - Contrôle quand réentraîner les modèles.

Règles:
- Regime detection: 1x par semaine (dimanche 3h)
- Volatility forecaster: 1x par jour (minuit)
- Correlation forecaster: 1x par semaine

Évite réentraînement coûteux (60-90s) à chaque appel API.
"""

from datetime import datetime, timedelta
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MLTrainingScheduler:
    """
    Scheduler pour déterminer quand réentraîner les modèles ML.

    Évite les réentraînements inutiles en vérifiant l'âge des modèles
    par rapport à des intervalles configurés.
    """

    TRAINING_INTERVALS = {
        "regime": timedelta(days=7),      # Hebdomadaire
        "volatility": timedelta(days=1),  # Quotidien
        "correlation": timedelta(days=7)  # Hebdomadaire
    }

    @staticmethod
    def should_retrain(model_type: str, model_path: Path) -> bool:
        """
        Vérifie si le modèle doit être réentraîné.

        Args:
            model_type: Type de modèle ('regime', 'volatility', 'correlation')
            model_path: Chemin vers le fichier du modèle

        Returns:
            True si le modèle doit être réentraîné, False sinon
        """
        if not model_path.exists():
            logger.info(f"{model_type} model not found at {model_path}, training required")
            return True  # Pas de modèle = train obligatoire

        # Âge du modèle
        model_age = datetime.now() - datetime.fromtimestamp(
            model_path.stat().st_mtime
        )

        # Intervalle requis pour ce type de modèle
        interval = MLTrainingScheduler.TRAINING_INTERVALS.get(
            model_type,
            timedelta(days=7)  # Default: hebdomadaire
        )

        needs_retrain = model_age > interval

        if needs_retrain:
            logger.info(f"{model_type} model is {model_age.days} days old (>{interval.days} days), retraining needed")
        else:
            logger.debug(f"{model_type} model is fresh ({model_age.total_seconds() / 3600:.1f}h old), using cached version")

        return needs_retrain

    @staticmethod
    def get_model_info(model_path: Path) -> dict:
        """
        Retourne infos sur le modèle (âge, prochaine mise à jour).

        Args:
            model_path: Chemin vers le fichier du modèle

        Returns:
            Dict avec informations sur le modèle
        """
        if not model_path.exists():
            return {
                "exists": False,
                "last_trained": None,
                "age_hours": None,
                "needs_retrain": True
            }

        last_trained = datetime.fromtimestamp(model_path.stat().st_mtime)
        age = datetime.now() - last_trained

        return {
            "exists": True,
            "last_trained": last_trained.isoformat(),
            "age_hours": round(age.total_seconds() / 3600, 2),
            "age_days": round(age.total_seconds() / 86400, 2),
            "needs_retrain": age > timedelta(days=7)  # Conservative default
        }
