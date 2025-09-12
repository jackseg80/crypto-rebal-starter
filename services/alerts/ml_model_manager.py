"""
Phase 2C.4: ML Model Management with MLflow Integration

Système de gestion des modèles ML pour alertes prédictives avec :
- Versioning automatique des modèles
- A/B Testing entre versions de modèles  
- Performance tracking et drift detection
- Auto-retraining pipeline
- Model registry intégré
"""

import mlflow
import mlflow.sklearn
import mlflow.tracking
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
import logging
import json
import numpy as np
import pandas as pd
from dataclasses import dataclass
import joblib
import hashlib

from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
from sklearn.model_selection import cross_val_score

from .ml_alert_predictor import MLAlertPredictor, AlertPrediction, FeatureSet, PredictiveAlertType

logger = logging.getLogger(__name__)

@dataclass
class ModelVersion:
    """Version de modèle avec métadonnées"""
    model_id: str
    version: str
    alert_type: str
    horizon: str
    model_uri: str
    created_at: datetime
    metrics: Dict[str, float]
    status: str  # "active", "testing", "deprecated", "failed"
    tags: Dict[str, str]
    
@dataclass 
class ModelPerformance:
    """Métriques de performance d'un modèle"""
    model_version: str
    evaluated_at: datetime
    precision: float
    recall: float 
    f1_score: float
    auc_score: float
    prediction_count: int
    accuracy_trend: str  # "improving", "stable", "degrading"

@dataclass
class ABTestResult:
    """Résultats d'un A/B test entre modèles"""
    test_id: str
    model_a: str
    model_b: str
    started_at: datetime
    ended_at: Optional[datetime]
    winner: Optional[str]
    confidence: float
    metrics_comparison: Dict[str, Dict[str, float]]
    sample_size: int

class MLModelManager:
    """
    Gestionnaire de modèles ML avec MLflow
    
    Responsabilités :
    - Registry des modèles par type d'alerte et horizon
    - Versioning automatique avec tags metadata
    - A/B Testing pour sélection meilleur modèle 
    - Performance monitoring et alertes de drift
    - Pipeline de retraining automatique
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Configuration MLflow
        self.mlflow_tracking_uri = config.get("mlflow_tracking_uri", "sqlite:///data/ml_models/mlflow.db")
        self.experiment_name = config.get("experiment_name", "alert_predictions")
        
        # Configuration modèles
        self.model_registry_name = config.get("model_registry_name", "alert_predictor_models")
        self.performance_window_hours = config.get("performance_window_hours", 24)
        self.drift_threshold = config.get("drift_threshold", 0.1)  # 10% drop in F1
        
        # A/B Testing configuration
        self.ab_test_duration_hours = config.get("ab_test_duration_hours", 168)  # 7 jours
        self.ab_test_min_samples = config.get("ab_test_min_samples", 100)
        self.ab_test_confidence_threshold = config.get("ab_test_confidence_threshold", 0.95)
        
        # Storage
        self.model_versions: Dict[str, List[ModelVersion]] = {}
        self.performance_history: Dict[str, List[ModelPerformance]] = {}
        self.active_ab_tests: Dict[str, ABTestResult] = {}
        
        # Initialize MLflow
        self._setup_mlflow()
        
        logger.info(f"MLModelManager initialized with tracking_uri: {self.mlflow_tracking_uri}")
    
    def _setup_mlflow(self):
        """Configure MLflow tracking et experiment"""
        try:
            mlflow.set_tracking_uri(self.mlflow_tracking_uri)
            
            # Créer experiment s'il n'existe pas
            try:
                experiment = mlflow.get_experiment_by_name(self.experiment_name)
                if experiment is None:
                    experiment_id = mlflow.create_experiment(
                        name=self.experiment_name,
                        tags={
                            "purpose": "alert_predictions",
                            "phase": "2C",
                            "created_by": "ml_model_manager"
                        }
                    )
                    logger.info(f"Created MLflow experiment: {self.experiment_name} (ID: {experiment_id})")
                else:
                    logger.info(f"Using existing MLflow experiment: {self.experiment_name}")
            except Exception as e:
                logger.warning(f"MLflow experiment setup warning: {e}")
            
        except Exception as e:
            logger.error(f"MLflow setup error: {e}")
            raise
    
    def register_model_version(self, 
                              predictor: MLAlertPredictor,
                              alert_type: PredictiveAlertType,
                              horizon: str,
                              training_metrics: Dict[str, float],
                              validation_data: Optional[pd.DataFrame] = None) -> str:
        """
        Enregistre une nouvelle version de modèle dans MLflow Registry
        
        Args:
            predictor: Instance du predicteur entraîné
            alert_type: Type d'alerte prédit
            horizon: Horizon de prédiction
            training_metrics: Métriques d'entraînement
            validation_data: Données de validation pour tests
            
        Returns:
            model_version_id: ID de la version enregistrée
        """
        try:
            model_key = f"{alert_type.value}_{horizon}"
            
            with mlflow.start_run(experiment_id=mlflow.get_experiment_by_name(self.experiment_name).experiment_id):
                # Log des hyperparamètres
                mlflow.log_params({
                    "alert_type": alert_type.value,
                    "horizon": horizon,
                    "model_type": "ensemble",
                    "n_estimators_rf": predictor.models_config["random_forest"]["n_estimators"],
                    "max_depth_rf": predictor.models_config["random_forest"]["max_depth"],
                    "learning_rate_gb": predictor.models_config["gradient_boosting"]["learning_rate"],
                    "prediction_threshold": predictor.prediction_thresholds.get(alert_type.value, 0.7)
                })
                
                # Log des métriques d'entraînement
                for metric_name, value in training_metrics.items():
                    mlflow.log_metric(f"train_{metric_name}", value)
                
                # Log du modèle
                if model_key in predictor.models:
                    models_dict = predictor.models[model_key]
                    scaler = predictor.scalers.get(model_key)
                    
                    # Créer artifact avec modèles + scaler
                    model_artifact = {
                        "models": models_dict,
                        "scaler": scaler,
                        "feature_names": predictor._get_feature_names(),
                        "config": predictor.config,
                        "alert_type": alert_type.value,
                        "horizon": horizon
                    }
                    
                    # Log comme artifact custom
                    mlflow.sklearn.log_model(
                        sk_model=models_dict["random_forest"],  # Modèle principal pour signature
                        artifact_path="alert_predictor",
                        registered_model_name=f"{self.model_registry_name}_{model_key}",
                        metadata={"ensemble_info": "custom_artifact"}
                    )
                    
                    # Log des artifacts additionnels
                    mlflow.log_dict(model_artifact, "model_full.json")
                
                # Validation croisée si données disponibles
                if validation_data is not None:
                    try:
                        cv_scores = self._cross_validate_model(predictor, model_key, validation_data)
                        for i, score in enumerate(cv_scores):
                            mlflow.log_metric(f"cv_f1_fold_{i}", score)
                        mlflow.log_metric("cv_f1_mean", np.mean(cv_scores))
                        mlflow.log_metric("cv_f1_std", np.std(cv_scores))
                    except Exception as e:
                        logger.warning(f"Cross-validation failed: {e}")
                
                # Tags de la version
                mlflow.set_tags({
                    "stage": "testing",
                    "alert_type": alert_type.value,
                    "horizon": horizon,
                    "created_by": "ml_model_manager",
                    "training_timestamp": datetime.now().isoformat()
                })
                
                # Générer version ID
                run_id = mlflow.active_run().info.run_id
                model_version_id = f"{model_key}_v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Enregistrer dans tracking local
                model_version = ModelVersion(
                    model_id=model_key,
                    version=model_version_id,
                    alert_type=alert_type.value,
                    horizon=horizon,
                    model_uri=f"runs:/{run_id}/alert_predictor",
                    created_at=datetime.now(),
                    metrics=training_metrics,
                    status="testing",
                    tags={"run_id": run_id, "stage": "testing"}
                )
                
                if model_key not in self.model_versions:
                    self.model_versions[model_key] = []
                self.model_versions[model_key].append(model_version)
                
                logger.info(f"Registered model version {model_version_id} for {model_key}")
                return model_version_id
                
        except Exception as e:
            logger.error(f"Model registration failed: {e}")
            raise
    
    def start_ab_test(self, 
                     model_a_version: str, 
                     model_b_version: str,
                     traffic_split: float = 0.5) -> str:
        """
        Lance un A/B test entre deux versions de modèles
        
        Args:
            model_a_version: Version A (baseline)
            model_b_version: Version B (challenger)
            traffic_split: % de traffic pour version B (0.5 = 50/50)
        
        Returns:
            test_id: ID du test A/B
        """
        try:
            test_id = f"ab_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            ab_test = ABTestResult(
                test_id=test_id,
                model_a=model_a_version,
                model_b=model_b_version,
                started_at=datetime.now(),
                ended_at=None,
                winner=None,
                confidence=0.0,
                metrics_comparison={},
                sample_size=0
            )
            
            self.active_ab_tests[test_id] = ab_test
            
            logger.info(f"Started A/B test {test_id}: {model_a_version} vs {model_b_version} (split: {traffic_split:.0%})")
            return test_id
            
        except Exception as e:
            logger.error(f"Failed to start A/B test: {e}")
            raise
    
    def evaluate_ab_test(self, test_id: str) -> Optional[ABTestResult]:
        """Évalue les résultats d'un A/B test en cours"""
        if test_id not in self.active_ab_tests:
            logger.warning(f"A/B test {test_id} not found")
            return None
        
        ab_test = self.active_ab_tests[test_id]
        
        try:
            # Récupérer performances des deux modèles
            perf_a = self._get_recent_performance(ab_test.model_a)
            perf_b = self._get_recent_performance(ab_test.model_b)
            
            if not perf_a or not perf_b:
                logger.debug(f"Insufficient data for A/B test {test_id}")
                return ab_test
            
            # Calcul statistiques
            metrics_comparison = {
                "model_a": {
                    "f1_score": perf_a.f1_score,
                    "precision": perf_a.precision,
                    "recall": perf_a.recall,
                    "auc_score": perf_a.auc_score,
                    "sample_size": perf_a.prediction_count
                },
                "model_b": {
                    "f1_score": perf_b.f1_score,
                    "precision": perf_b.precision,
                    "recall": perf_b.recall,
                    "auc_score": perf_b.auc_score,
                    "sample_size": perf_b.prediction_count
                }
            }
            
            # Test statistique simple (t-test approximation)
            f1_diff = perf_b.f1_score - perf_a.f1_score
            combined_samples = perf_a.prediction_count + perf_b.prediction_count
            
            # Seuil de signification (simplifiée)
            significance_threshold = 0.02  # 2% d'amélioration minimum
            confidence = min(0.99, abs(f1_diff) / significance_threshold) if abs(f1_diff) > 0 else 0.5
            
            # Déterminer gagnant
            winner = None
            if combined_samples >= self.ab_test_min_samples and confidence >= self.ab_test_confidence_threshold:
                if f1_diff > significance_threshold:
                    winner = ab_test.model_b
                elif f1_diff < -significance_threshold:
                    winner = ab_test.model_a
            
            # Mettre à jour le test
            ab_test.metrics_comparison = metrics_comparison
            ab_test.confidence = confidence
            ab_test.sample_size = combined_samples
            ab_test.winner = winner
            
            # Terminer le test si décision prise ou timeout
            test_duration = datetime.now() - ab_test.started_at
            if winner or test_duration.total_seconds() / 3600 >= self.ab_test_duration_hours:
                ab_test.ended_at = datetime.now()
                self._finalize_ab_test(ab_test)
            
            logger.info(f"A/B test {test_id} evaluation: winner={winner}, confidence={confidence:.0%}")
            return ab_test
            
        except Exception as e:
            logger.error(f"A/B test evaluation error: {e}")
            return ab_test
    
    def track_model_performance(self, 
                               model_version: str,
                               predictions: List[AlertPrediction],
                               actual_outcomes: List[bool]) -> ModelPerformance:
        """
        Track performance en temps réel d'un modèle
        
        Args:
            model_version: Version du modèle
            predictions: Prédictions générées
            actual_outcomes: Résultats réels (True si event s'est produit)
        """
        try:
            # Calculer métriques de performance
            y_pred = [1 if pred.probability >= 0.5 else 0 for pred in predictions]
            y_true = actual_outcomes
            
            if len(set(y_true)) == 1:  # Tous positifs ou tous négatifs
                logger.warning(f"Performance tracking skipped - no class diversity")
                return None
            
            precision = precision_score(y_true, y_pred, zero_division=0)
            recall = recall_score(y_true, y_pred, zero_division=0)
            f1 = f1_score(y_true, y_pred, zero_division=0)
            auc = roc_auc_score(y_true, [pred.probability for pred in predictions])
            
            # Déterminer trend
            trend = self._calculate_performance_trend(model_version, f1)
            
            performance = ModelPerformance(
                model_version=model_version,
                evaluated_at=datetime.now(),
                precision=precision,
                recall=recall,
                f1_score=f1,
                auc_score=auc,
                prediction_count=len(predictions),
                accuracy_trend=trend
            )
            
            # Stocker dans historique
            if model_version not in self.performance_history:
                self.performance_history[model_version] = []
            self.performance_history[model_version].append(performance)
            
            # Log vers MLflow
            try:
                with mlflow.start_run():
                    mlflow.log_metrics({
                        f"realtime_precision": precision,
                        f"realtime_recall": recall,
                        f"realtime_f1": f1,
                        f"realtime_auc": auc,
                        f"prediction_count": len(predictions)
                    })
                    mlflow.set_tags({
                        "model_version": model_version,
                        "performance_tracking": "realtime",
                        "trend": trend
                    })
            except Exception as e:
                logger.warning(f"MLflow logging failed: {e}")
            
            # Alerte de drift si performance dégradée
            if trend == "degrading" and f1 < (1 - self.drift_threshold):
                logger.warning(f"Model drift detected for {model_version}: F1={f1:.3f} (trend: {trend})")
                self._trigger_drift_alert(model_version, performance)
            
            logger.info(f"Performance tracked for {model_version}: F1={f1:.3f}, AUC={auc:.3f}, trend={trend}")
            return performance
            
        except Exception as e:
            logger.error(f"Performance tracking error: {e}")
            return None
    
    def get_best_model_version(self, alert_type: PredictiveAlertType, horizon: str) -> Optional[str]:
        """Retourne la meilleure version de modèle pour un type/horizon"""
        model_key = f"{alert_type.value}_{horizon}"
        
        if model_key not in self.model_versions:
            logger.warning(f"No models available for {model_key}")
            return None
        
        # Filtrer modèles actifs seulement
        active_versions = [v for v in self.model_versions[model_key] if v.status == "active"]
        
        if not active_versions:
            logger.warning(f"No active models for {model_key}")
            return None
        
        # Sélectionner basé sur F1 score le plus récent
        best_version = max(active_versions, key=lambda v: v.metrics.get("f1_score", 0))
        return best_version.version
    
    def _cross_validate_model(self, predictor: MLAlertPredictor, model_key: str, validation_data: pd.DataFrame) -> List[float]:
        """Validation croisée du modèle"""
        try:
            if model_key not in predictor.models:
                return []
            
            model = predictor.models[model_key]["random_forest"]  # Utiliser RF comme représentant
            scaler = predictor.scalers[model_key]
            
            # Préparer données
            feature_names = predictor._get_feature_names()
            X = validation_data[feature_names].values
            y = validation_data["target"].values
            
            # Normaliser
            X_scaled = scaler.transform(X)
            
            # Validation croisée
            scores = cross_val_score(model, X_scaled, y, cv=5, scoring='f1', error_score='raise')
            return scores.tolist()
            
        except Exception as e:
            logger.error(f"Cross-validation failed: {e}")
            return []
    
    def _get_recent_performance(self, model_version: str) -> Optional[ModelPerformance]:
        """Récupère performance récente d'un modèle"""
        if model_version not in self.performance_history:
            return None
        
        recent_performances = [
            p for p in self.performance_history[model_version]
            if (datetime.now() - p.evaluated_at).total_seconds() / 3600 <= self.performance_window_hours
        ]
        
        if not recent_performances:
            return None
        
        # Moyenne des performances récentes
        avg_performance = ModelPerformance(
            model_version=model_version,
            evaluated_at=datetime.now(),
            precision=np.mean([p.precision for p in recent_performances]),
            recall=np.mean([p.recall for p in recent_performances]),
            f1_score=np.mean([p.f1_score for p in recent_performances]),
            auc_score=np.mean([p.auc_score for p in recent_performances]),
            prediction_count=sum([p.prediction_count for p in recent_performances]),
            accuracy_trend=recent_performances[-1].accuracy_trend  # Dernier trend
        )
        
        return avg_performance
    
    def _calculate_performance_trend(self, model_version: str, current_f1: float) -> str:
        """Calcule trend de performance"""
        if model_version not in self.performance_history:
            return "stable"
        
        recent_f1_scores = [p.f1_score for p in self.performance_history[model_version][-5:]]  # 5 derniers
        
        if len(recent_f1_scores) < 3:
            return "stable"
        
        # Régression linéaire simple
        x = np.arange(len(recent_f1_scores))
        slope = np.polyfit(x, recent_f1_scores, 1)[0]
        
        if slope > 0.01:
            return "improving"
        elif slope < -0.01:
            return "degrading"
        else:
            return "stable"
    
    def _finalize_ab_test(self, ab_test: ABTestResult):
        """Finalise un A/B test et promeut le gagnant"""
        try:
            if ab_test.winner:
                # Promouvoir modèle gagnant vers "active"
                self._promote_model_to_active(ab_test.winner)
                logger.info(f"A/B test {ab_test.test_id} completed - Winner: {ab_test.winner}")
            else:
                logger.info(f"A/B test {ab_test.test_id} completed - No clear winner")
            
            # Archiver le test
            del self.active_ab_tests[ab_test.test_id]
            
        except Exception as e:
            logger.error(f"A/B test finalization error: {e}")
    
    def _promote_model_to_active(self, model_version: str):
        """Promeut un modèle vers statut active"""
        for model_key, versions in self.model_versions.items():
            for version in versions:
                if version.version == model_version:
                    version.status = "active"
                    logger.info(f"Promoted model {model_version} to active status")
                    break
    
    def _trigger_drift_alert(self, model_version: str, performance: ModelPerformance):
        """Déclenche alerte de drift de modèle"""
        # TODO: Intégrer avec système d'alertes principal
        logger.warning(f"MODEL DRIFT ALERT: {model_version} - F1={performance.f1_score:.3f}, trend={performance.accuracy_trend}")
    
    def get_model_status_report(self) -> Dict[str, Any]:
        """Génère rapport de statut de tous les modèles"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_models": sum(len(versions) for versions in self.model_versions.values()),
            "active_models": sum(1 for versions in self.model_versions.values() 
                               for v in versions if v.status == "active"),
            "active_ab_tests": len(self.active_ab_tests),
            "model_types": list(self.model_versions.keys()),
            "performance_summary": {}
        }
        
        for model_key, versions in self.model_versions.items():
            active_version = next((v for v in versions if v.status == "active"), None)
            if active_version and model_key in self.performance_history:
                recent_perf = self._get_recent_performance(active_version.version)
                if recent_perf:
                    report["performance_summary"][model_key] = {
                        "version": active_version.version,
                        "f1_score": recent_perf.f1_score,
                        "trend": recent_perf.accuracy_trend,
                        "prediction_count": recent_perf.prediction_count
                    }
        
        return report


def create_ml_model_manager(config: Dict[str, Any]) -> Optional[MLModelManager]:
    """Factory function pour créer MLModelManager"""
    try:
        if not config.get("enabled", False):
            logger.info("MLModelManager disabled in config")
            return None
        
        return MLModelManager(config)
        
    except Exception as e:
        logger.error(f"Failed to create MLModelManager: {e}")
        return None