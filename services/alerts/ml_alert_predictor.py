"""
Phase 2C: ML Alert Predictions Engine

Système de prédiction d'alertes utilisant ML pour anticiper les événements
de marché 24-48h à l'avance. Intégration complète avec AlertEngine existant
et CrossAssetCorrelationAnalyzer.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging
import joblib
from pathlib import Path
import json

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

logger = logging.getLogger(__name__)

class PredictionHorizon(str, Enum):
    """Horizons de prédiction disponibles"""
    H4 = "4h"        # 4 heures à l'avance
    H12 = "12h"      # 12 heures à l'avance  
    H24 = "24h"      # 24 heures à l'avance
    H48 = "48h"      # 48 heures à l'avance

class PredictiveAlertType(str, Enum):
    """Types d'alertes prédictives"""
    SPIKE_LIKELY = "SPIKE_LIKELY"                     # Spike corrélation probable
    REGIME_CHANGE_PENDING = "REGIME_CHANGE_PENDING"   # Changement régime attendu
    CORRELATION_BREAKDOWN = "CORRELATION_BREAKDOWN"   # Décorrélation majeure
    VOLATILITY_SPIKE_IMMINENT = "VOLATILITY_SPIKE_IMMINENT"  # Spike volatilité

@dataclass
class AlertPrediction:
    """Prédiction d'alerte ML"""
    alert_type: PredictiveAlertType
    probability: float              # 0-1, probabilité de l'event
    confidence: float              # 0-1, confiance du modèle
    horizon: PredictionHorizon     # Horizon temporel
    assets: List[str]              # Assets concernés
    features: Dict[str, float]     # Features utilisées pour prédiction
    model_version: str             # Version du modèle utilisé
    predicted_at: datetime         # Timestamp de prédiction
    target_time: datetime          # Moment prédit de l'event
    severity_estimate: str         # "S1", "S2", "S3" prédit

@dataclass  
class FeatureSet:
    """Set de features pour ML alert prediction"""
    # Features corrélation
    avg_correlation_1h: float
    avg_correlation_4h: float  
    avg_correlation_1d: float
    correlation_volatility: float
    correlation_trend: float
    
    # Features cross-asset
    btc_eth_correlation: float
    large_alt_spread: float
    concentration_score: float
    cluster_stability: float
    
    # Features volatilité
    realized_vol_1h: float
    realized_vol_4h: float
    vol_of_vol: float
    vol_skew: float
    
    # Features momentum
    price_momentum_1h: float
    price_momentum_4h: float
    volume_momentum: float
    
    # Features macro
    market_stress: float
    funding_rates_avg: float
    
    timestamp: datetime

class MLAlertPredictor:
    """
    Moteur de prédiction d'alertes ML
    
    Utilise ensemble de modèles (RandomForest + XGBoost) pour prédire
    différents types d'alertes avec horizons multiples.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)
        
        # Configuration modèles
        self.models_config = config.get("models", {
            "random_forest": {
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 5,
                "random_state": 42
            },
            "gradient_boosting": {
                "n_estimators": 100,
                "learning_rate": 0.1,
                "max_depth": 6,
                "random_state": 42
            }
        })
        
        # Seuils prédiction
        self.prediction_thresholds = config.get("prediction_thresholds", {
            "SPIKE_LIKELY": 0.7,
            "REGIME_CHANGE_PENDING": 0.65,
            "CORRELATION_BREAKDOWN": 0.75,
            "VOLATILITY_SPIKE_IMMINENT": 0.8
        })
        
        # Configuration features
        self.feature_config = config.get("features", {
            "lookback_hours": 168,  # 7 jours de features
            "min_data_points": 50,  # Minimum pour entraînement
            "update_frequency_minutes": 15
        })
        
        # Models storage
        self.models: Dict[str, Dict[str, Any]] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.model_metrics: Dict[str, Dict[str, float]] = {}
        self.feature_importance: Dict[str, Dict[str, float]] = {}
        
        # Cache prédictions
        self.prediction_cache: Dict[str, AlertPrediction] = {}
        self.cache_ttl_minutes = config.get("cache_ttl_minutes", 10)
        
        # Historique features et labels
        self.feature_history: List[FeatureSet] = []
        self.label_history: Dict[str, List[int]] = {}
        
        self.model_path = Path(config.get("model_path", "data/ml_models/alert_predictor"))
        self.model_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"MLAlertPredictor initialized: enabled={self.enabled}, "
                   f"thresholds={self.prediction_thresholds}")
    
    def extract_features(self, 
                        correlation_data: Dict[str, Any], 
                        price_data: Dict[str, Any],
                        market_data: Dict[str, Any]) -> FeatureSet:
        """
        Extraction des features pour prédiction ML
        
        Args:
            correlation_data: Données corrélation du CrossAssetAnalyzer
            price_data: Données prix historiques multi-assets
            market_data: Données macro (funding, sentiment, etc.)
        """
        try:
            # Features corrélation (du système Phase 2B2)
            corr_matrix_1h = correlation_data.get("correlation_matrices", {}).get("1h", np.array([]))
            corr_matrix_4h = correlation_data.get("correlation_matrices", {}).get("4h", np.array([]))  
            corr_matrix_1d = correlation_data.get("correlation_matrices", {}).get("1d", np.array([]))
            
            avg_corr_1h = np.mean(corr_matrix_1h[np.triu_indices_from(corr_matrix_1h, k=1)]) if corr_matrix_1h.size > 0 else 0.0
            avg_corr_4h = np.mean(corr_matrix_4h[np.triu_indices_from(corr_matrix_4h, k=1)]) if corr_matrix_4h.size > 0 else 0.0
            avg_corr_1d = np.mean(corr_matrix_1d[np.triu_indices_from(corr_matrix_1d, k=1)]) if corr_matrix_1d.size > 0 else 0.0
            
            # Volatilité des corrélations
            recent_correlations = correlation_data.get("correlation_history", {})
            corr_volatility = np.std(list(recent_correlations.values())[:50]) if recent_correlations else 0.0
            
            # Trend corrélation (régression linéaire simple sur derniers points)
            corr_trend = self._calculate_correlation_trend(recent_correlations)
            
            # Features cross-asset spécifiques
            btc_eth_corr = self._get_asset_pair_correlation(correlation_data, "BTC", "ETH")
            large_alt_spread = self._calculate_large_alt_spread(correlation_data)
            concentration_score = correlation_data.get("systemic_risk", {}).get("concentration", 0.0)
            cluster_stability = self._calculate_cluster_stability(correlation_data)
            
            # Features volatilité réalisée
            vol_features = self._extract_volatility_features(price_data)
            
            # Features momentum
            momentum_features = self._extract_momentum_features(price_data)
            
            # Features macro
            market_stress = market_data.get("fear_greed_index", 50) / 100.0  # Normaliser 0-1
            funding_rates = market_data.get("funding_rates", {})
            funding_rates_avg = np.mean(list(funding_rates.values())) if funding_rates else 0.0
            
            return FeatureSet(
                # Corrélation features
                avg_correlation_1h=avg_corr_1h,
                avg_correlation_4h=avg_corr_4h,
                avg_correlation_1d=avg_corr_1d,
                correlation_volatility=corr_volatility,
                correlation_trend=corr_trend,
                
                # Cross-asset features  
                btc_eth_correlation=btc_eth_corr,
                large_alt_spread=large_alt_spread,
                concentration_score=concentration_score,
                cluster_stability=cluster_stability,
                
                # Volatilité features
                realized_vol_1h=vol_features["vol_1h"],
                realized_vol_4h=vol_features["vol_4h"],  
                vol_of_vol=vol_features["vol_of_vol"],
                vol_skew=vol_features["vol_skew"],
                
                # Momentum features
                price_momentum_1h=momentum_features["momentum_1h"],
                price_momentum_4h=momentum_features["momentum_4h"],
                volume_momentum=momentum_features["volume_momentum"],
                
                # Macro features
                market_stress=market_stress,
                funding_rates_avg=funding_rates_avg,
                
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            # Return default features in case of error
            return self._get_default_features()
    
    def predict_alerts(self, 
                      features: FeatureSet,
                      horizons: List[PredictionHorizon] = None) -> List[AlertPrediction]:
        """
        Génère prédictions d'alertes pour horizons donnés
        
        Args:
            features: FeatureSet extrait des données actuelles
            horizons: Horizons de prédiction (défaut: [H24])
        """
        if not self.enabled:
            return []
        
        if horizons is None:
            horizons = [PredictionHorizon.H24]
        
        predictions = []
        features_array = self._featureset_to_array(features)
        
        for horizon in horizons:
            for alert_type in PredictiveAlertType:
                try:
                    model_key = f"{alert_type.value}_{horizon.value}"
                    
                    if model_key not in self.models:
                        logger.warning(f"Model {model_key} not trained yet")
                        continue
                    
                    # Prédiction avec ensemble de modèles
                    prediction = self._predict_with_ensemble(
                        features_array, model_key, alert_type, horizon
                    )
                    
                    if prediction and prediction.probability >= self.prediction_thresholds[alert_type.value]:
                        predictions.append(prediction)
                        
                except Exception as e:
                    logger.error(f"Prediction error for {model_key}: {e}")
                    continue
        
        # Cache des prédictions
        cache_key = f"predictions_{features.timestamp.isoformat()}"
        self.prediction_cache[cache_key] = predictions
        
        logger.info(f"Generated {len(predictions)} ML alert predictions")
        return predictions
    
    def train_models(self, 
                    training_data: List[Tuple[FeatureSet, Dict[str, int]]],
                    validation_split: float = 0.2) -> Dict[str, Dict[str, float]]:
        """
        Entraîne les modèles ML sur données historiques
        
        Args:
            training_data: List de (features, labels) où labels = {"SPIKE_LIKELY": 1, ...}
            validation_split: Portion pour validation
            
        Returns:
            Métriques d'évaluation par modèle
        """
        if len(training_data) < self.feature_config["min_data_points"]:
            logger.warning(f"Not enough training data: {len(training_data)} < {self.feature_config['min_data_points']}")
            return {}
        
        results = {}
        
        # Préparer données
        X = np.array([self._featureset_to_array(features) for features, _ in training_data])
        
        for alert_type in PredictiveAlertType:
            for horizon in PredictionHorizon:
                model_key = f"{alert_type.value}_{horizon.value}"
                
                # Extraire labels pour ce type d'alerte
                y = np.array([labels.get(f"{alert_type.value}_{horizon.value}", 0) 
                             for _, labels in training_data])
                
                if np.sum(y) == 0:  # Pas d'événements positifs
                    logger.warning(f"No positive examples for {model_key}")
                    continue
                
                try:
                    # Split train/validation
                    X_train, X_val, y_train, y_val = train_test_split(
                        X, y, test_size=validation_split, random_state=42, stratify=y
                    )
                    
                    # Normalisation features
                    scaler = StandardScaler()
                    X_train_scaled = scaler.fit_transform(X_train)
                    X_val_scaled = scaler.transform(X_val)
                    
                    # Entraînement ensemble de modèles
                    models = self._train_ensemble_models(X_train_scaled, y_train)
                    
                    # Évaluation
                    metrics = self._evaluate_models(models, X_val_scaled, y_val)
                    
                    # Sauvegarde
                    self.models[model_key] = models
                    self.scalers[model_key] = scaler
                    self.model_metrics[model_key] = metrics
                    
                    # Feature importance (du RandomForest)
                    if "random_forest" in models:
                        feature_names = self._get_feature_names()
                        importance = models["random_forest"].feature_importances_
                        self.feature_importance[model_key] = dict(zip(feature_names, importance))
                    
                    results[model_key] = metrics
                    logger.info(f"Trained {model_key}: F1={metrics.get('f1_score', 0):.3f}")
                    
                except Exception as e:
                    logger.error(f"Training error for {model_key}: {e}")
                    continue
        
        # Sauvegarder modèles sur disque
        self._save_models()
        
        return results
    
    def _predict_with_ensemble(self, 
                              features_array: np.ndarray,
                              model_key: str,
                              alert_type: PredictiveAlertType,
                              horizon: PredictionHorizon) -> Optional[AlertPrediction]:
        """Prédiction avec ensemble de modèles"""
        try:
            models = self.models[model_key]
            scaler = self.scalers[model_key]
            
            # Normalisation
            features_scaled = scaler.transform(features_array.reshape(1, -1))
            
            # Prédictions des modèles individuels
            predictions = {}
            probabilities = {}
            
            for model_name, model in models.items():
                pred = model.predict(features_scaled)[0]
                prob = model.predict_proba(features_scaled)[0][1] if hasattr(model, "predict_proba") else pred
                
                predictions[model_name] = pred
                probabilities[model_name] = prob
            
            # Ensemble: moyenne pondérée des probabilités
            weights = {"random_forest": 0.6, "gradient_boosting": 0.4}  # RF plus de poids
            ensemble_prob = sum(probabilities[name] * weights.get(name, 0.5) 
                               for name in probabilities.keys())
            ensemble_prob = np.clip(ensemble_prob, 0, 1)
            
            # Confiance: accord entre modèles
            confidence = 1.0 - np.std(list(probabilities.values()))
            confidence = np.clip(confidence, 0, 1)
            
            # Prédiction finale
            threshold = self.prediction_thresholds[alert_type.value]
            if ensemble_prob >= threshold:
                # Estimer sévérité basée sur probabilité
                severity = "S3" if ensemble_prob >= 0.9 else ("S2" if ensemble_prob >= 0.75 else "S1")
                
                return AlertPrediction(
                    alert_type=alert_type,
                    probability=ensemble_prob,
                    confidence=confidence,
                    horizon=horizon,
                    assets=["BTC", "ETH"],  # TODO: déduire des features
                    features=self._array_to_features_dict(features_array),
                    model_version=f"ensemble_v1.0_{model_key}",
                    predicted_at=datetime.now(),
                    target_time=datetime.now() + timedelta(hours=int(horizon.value[:-1])),
                    severity_estimate=severity
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Ensemble prediction error: {e}")
            return None
    
    def _train_ensemble_models(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict[str, Any]:
        """Entraîne ensemble de modèles"""
        models = {}
        
        # RandomForest
        rf_config = self.models_config["random_forest"]
        rf = RandomForestClassifier(**rf_config)
        rf.fit(X_train, y_train)
        models["random_forest"] = rf
        
        # GradientBoosting
        gb_config = self.models_config["gradient_boosting"]
        gb = GradientBoostingClassifier(**gb_config)
        gb.fit(X_train, y_train)
        models["gradient_boosting"] = gb
        
        return models
    
    def _evaluate_models(self, models: Dict[str, Any], X_val: np.ndarray, y_val: np.ndarray) -> Dict[str, float]:
        """Évalue performance des modèles"""
        metrics = {}
        
        for model_name, model in models.items():
            try:
                y_pred = model.predict(X_val)
                y_prob = model.predict_proba(X_val)[:, 1] if hasattr(model, "predict_proba") else y_pred
                
                metrics[f"{model_name}_precision"] = precision_score(y_val, y_pred, zero_division=0)
                metrics[f"{model_name}_recall"] = recall_score(y_val, y_pred, zero_division=0)
                metrics[f"{model_name}_f1"] = f1_score(y_val, y_pred, zero_division=0)
                metrics[f"{model_name}_auc"] = roc_auc_score(y_val, y_prob) if len(np.unique(y_val)) > 1 else 0
                
            except Exception as e:
                logger.error(f"Evaluation error for {model_name}: {e}")
                continue
        
        # Métriques globales (moyenne des modèles)
        if metrics:
            metrics["precision"] = np.mean([v for k, v in metrics.items() if "precision" in k])
            metrics["recall"] = np.mean([v for k, v in metrics.items() if "recall" in k]) 
            metrics["f1_score"] = np.mean([v for k, v in metrics.items() if "f1" in k])
            metrics["auc_score"] = np.mean([v for k, v in metrics.items() if "auc" in k])
        
        return metrics
    
    # Helper methods
    def _featureset_to_array(self, features: FeatureSet) -> np.ndarray:
        """Convertit FeatureSet en array numpy"""
        return np.array([
            features.avg_correlation_1h,
            features.avg_correlation_4h,
            features.avg_correlation_1d,
            features.correlation_volatility,
            features.correlation_trend,
            features.btc_eth_correlation,
            features.large_alt_spread,
            features.concentration_score,
            features.cluster_stability,
            features.realized_vol_1h,
            features.realized_vol_4h,
            features.vol_of_vol,
            features.vol_skew,
            features.price_momentum_1h,
            features.price_momentum_4h,
            features.volume_momentum,
            features.market_stress,
            features.funding_rates_avg
        ])
    
    def _get_feature_names(self) -> List[str]:
        """Noms des features pour importance"""
        return [
            "avg_correlation_1h", "avg_correlation_4h", "avg_correlation_1d",
            "correlation_volatility", "correlation_trend", "btc_eth_correlation",
            "large_alt_spread", "concentration_score", "cluster_stability",
            "realized_vol_1h", "realized_vol_4h", "vol_of_vol", "vol_skew",
            "price_momentum_1h", "price_momentum_4h", "volume_momentum",
            "market_stress", "funding_rates_avg"
        ]
    
    def _calculate_correlation_trend(self, correlation_history: Dict) -> float:
        """Calcule trend des corrélations récentes"""
        if not correlation_history:
            return 0.0
        
        values = list(correlation_history.values())[-20:]  # 20 derniers points
        if len(values) < 5:
            return 0.0
        
        # Régression linéaire simple
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        return float(slope)
    
    def _get_asset_pair_correlation(self, correlation_data: Dict, asset1: str, asset2: str) -> float:
        """Récupère corrélation spécifique entre deux assets"""
        try:
            matrices = correlation_data.get("correlation_matrices", {})
            matrix_1h = matrices.get("1h", np.array([]))
            assets = correlation_data.get("assets", [])
            
            if asset1 in assets and asset2 in assets and matrix_1h.size > 0:
                idx1 = assets.index(asset1)
                idx2 = assets.index(asset2)
                return float(matrix_1h[idx1, idx2])
        except:
            pass
        return 0.0
    
    def _calculate_large_alt_spread(self, correlation_data: Dict) -> float:
        """Calcule spread corrélation entre large caps et alt coins"""
        # TODO: Implémenter logique spécifique
        return 0.0
    
    def _calculate_cluster_stability(self, correlation_data: Dict) -> float:
        """Mesure stabilité des clusters de corrélation"""
        clusters = correlation_data.get("concentration", {}).get("clusters", [])
        if not clusters:
            return 1.0  # Stable si pas de clusters
        
        # TODO: Implémenter métrique de stabilité
        return 0.5
    
    def _extract_volatility_features(self, price_data: Dict) -> Dict[str, float]:
        """Extrait features de volatilité"""
        # TODO: Implémenter avec données prix réelles
        return {
            "vol_1h": 0.02,
            "vol_4h": 0.04,
            "vol_of_vol": 0.001,
            "vol_skew": 0.0
        }
    
    def _extract_momentum_features(self, price_data: Dict) -> Dict[str, float]:
        """Extrait features de momentum"""
        # TODO: Implémenter avec données prix réelles  
        return {
            "momentum_1h": 0.01,
            "momentum_4h": 0.02,
            "volume_momentum": 0.0
        }
    
    def _get_default_features(self) -> FeatureSet:
        """Features par défaut en cas d'erreur"""
        return FeatureSet(
            avg_correlation_1h=0.0, avg_correlation_4h=0.0, avg_correlation_1d=0.0,
            correlation_volatility=0.0, correlation_trend=0.0, btc_eth_correlation=0.0,
            large_alt_spread=0.0, concentration_score=0.0, cluster_stability=1.0,
            realized_vol_1h=0.02, realized_vol_4h=0.04, vol_of_vol=0.001, vol_skew=0.0,
            price_momentum_1h=0.0, price_momentum_4h=0.0, volume_momentum=0.0,
            market_stress=0.5, funding_rates_avg=0.0, timestamp=datetime.now()
        )
    
    def _array_to_features_dict(self, features_array: np.ndarray) -> Dict[str, float]:
        """Convertit array de features en dict pour storage"""
        feature_names = self._get_feature_names()
        return dict(zip(feature_names, features_array))
    
    def _save_models(self):
        """Sauvegarde modèles sur disque"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            for model_key, models in self.models.items():
                model_file = self.model_path / f"{model_key}_{timestamp}.joblib"
                scaler_file = self.model_path / f"{model_key}_scaler_{timestamp}.joblib"
                
                joblib.dump(models, model_file)
                joblib.dump(self.scalers[model_key], scaler_file)
            
            # Sauvegarder métriques et metadata
            metadata = {
                "timestamp": timestamp,
                "model_metrics": self.model_metrics,
                "feature_importance": self.feature_importance,
                "config": self.config
            }
            
            metadata_file = self.model_path / f"metadata_{timestamp}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            logger.info(f"Models saved to {self.model_path}")
            
        except Exception as e:
            logger.error(f"Model saving error: {e}")

def create_ml_alert_predictor(config: Dict[str, Any]) -> Optional[MLAlertPredictor]:
    """Factory function pour créer MLAlertPredictor"""
    try:
        if not config.get("enabled", False):
            logger.info("MLAlertPredictor disabled in config")
            return None
        
        return MLAlertPredictor(config)
        
    except Exception as e:
        logger.error(f"Failed to create MLAlertPredictor: {e}")
        return None