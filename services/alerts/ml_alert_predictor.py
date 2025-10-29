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

                # Déduire assets concernés depuis features
                affected_assets = self._deduce_affected_assets(features_array, alert_type)

                return AlertPrediction(
                    alert_type=alert_type,
                    probability=ensemble_prob,
                    confidence=confidence,
                    horizon=horizon,
                    assets=affected_assets,
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
        except Exception as e:
            logger.debug(f"Failed to get correlation for {asset1}/{asset2}: {e}")
            pass
        return 0.0
    
    def _calculate_large_alt_spread(self, correlation_data: Dict) -> float:
        """Calcule spread performance entre large caps (BTC/ETH) et altcoins"""
        from services.price_history import get_cached_history

        try:
            # Large caps: BTC + ETH
            large_cap_returns = []
            for symbol in ["BTC", "ETH"]:
                history = get_cached_history(symbol, days=30)
                if history and len(history) >= 30:
                    prices = np.array([p for _, p in history])
                    # Return sur 30 jours
                    ret_30d = np.log(prices[-1] / prices[0])
                    large_cap_returns.append(ret_30d)

            # Altcoins représentatifs (large cap alts)
            alt_symbols = ["SOL", "ADA", "DOT", "AVAX", "LINK"]
            alt_returns = []
            for symbol in alt_symbols:
                history = get_cached_history(symbol, days=30)
                if history and len(history) >= 30:
                    prices = np.array([p for _, p in history])
                    ret_30d = np.log(prices[-1] / prices[0])
                    alt_returns.append(ret_30d)

            # Spread = moyenne alts - moyenne large caps
            # Positif = alts surperforment (altseason signal)
            # Négatif = BTC/ETH dominent (risk-off)
            if large_cap_returns and alt_returns:
                avg_large = np.mean(large_cap_returns)
                avg_alt = np.mean(alt_returns)
                spread = avg_alt - avg_large
                return float(spread)
            else:
                return 0.0

        except Exception as e:
            logger.warning(f"Large alt spread calculation error: {e}")
            return 0.0
    
    def _calculate_cluster_stability(self, correlation_data: Dict) -> float:
        """Mesure stabilité des clusters de corrélation (0=instable, 1=stable)"""
        try:
            # Stratégie: comparer la variance des corrélations récentes
            # Une corrélation stable = peu de changement dans le temps

            # Extraire matrices de corrélation temporelles si disponibles
            matrices = correlation_data.get("correlation_matrices", {})
            matrix_1h = matrices.get("1h", np.array([]))
            matrix_4h = matrices.get("4h", np.array([]))
            matrix_1d = matrices.get("1d", np.array([]))

            # Calculer moyennes des corrélations pour chaque fenêtre
            corr_values = []
            for matrix in [matrix_1h, matrix_4h, matrix_1d]:
                if matrix.size > 0:
                    # Upper triangle uniquement (pas de diagonale)
                    triu_indices = np.triu_indices_from(matrix, k=1)
                    corr_subset = matrix[triu_indices]
                    if len(corr_subset) > 0:
                        corr_values.append(np.mean(corr_subset))

            # Stabilité = faible variance entre fenêtres temporelles
            # Variance faible → corrélations constantes → stabilité élevée
            if len(corr_values) >= 2:
                variance = np.var(corr_values)
                # Transformer variance [0, ~0.1] vers stabilité [1, 0]
                # variance < 0.01 → très stable (1.0)
                # variance > 0.1 → instable (0.0)
                stability = np.exp(-10 * variance)  # Décroissance exponentielle
                return float(np.clip(stability, 0.0, 1.0))

            # Fallback: utiliser les clusters si disponibles
            clusters = correlation_data.get("concentration", {}).get("clusters", [])
            if not clusters:
                return 1.0  # Stable si pas de clusters (corrélations faibles partout)

            # Nombre de clusters élevé = fragmentation = instabilité
            # 1-2 clusters = stable, 5+ clusters = instable
            num_clusters = len(clusters)
            if num_clusters <= 2:
                return 0.9
            elif num_clusters <= 4:
                return 0.6
            else:
                return 0.3

        except Exception as e:
            logger.warning(f"Cluster stability calculation error: {e}")
            return 0.7  # Neutre en cas d'erreur
    
    def _extract_volatility_features(self, price_data: Dict) -> Dict[str, float]:
        """Extrait features de volatilité depuis données de prix réelles"""
        from services.price_history import get_cached_history

        try:
            # Récupérer prix historiques pour assets principaux
            all_vols_1h = []
            all_vols_4h = []

            # Assets clés pour vol aggregée (BTC, ETH, SOL comme proxy marché)
            key_assets = ["BTC", "ETH", "SOL"]

            for symbol in key_assets:
                history = get_cached_history(symbol, days=7)  # 7 jours = 168h
                if not history or len(history) < 10:
                    continue

                prices = [p for _, p in history]

                # Volatilité 1h (dernières 24 heures = derniers 24 points)
                if len(prices) >= 24:
                    returns_1h = np.diff(np.log(prices[-24:]))
                    vol_1h = np.std(returns_1h) * np.sqrt(24 * 365)  # Annualisé
                    all_vols_1h.append(vol_1h)

                # Volatilité 4h (dernières 96 heures = 4 jours)
                if len(prices) >= 96:
                    returns_4h = np.diff(np.log(prices[-96:]))
                    vol_4h = np.std(returns_4h) * np.sqrt(6 * 365)  # 6 periods per day
                    all_vols_4h.append(vol_4h)

            # Aggreger les volatilités
            avg_vol_1h = np.mean(all_vols_1h) if all_vols_1h else 0.02
            avg_vol_4h = np.mean(all_vols_4h) if all_vols_4h else 0.04

            # Vol of vol: volatilité des volatilités rolling (instabilité)
            if len(all_vols_1h) >= 2:
                vol_of_vol = np.std(all_vols_1h)
            else:
                vol_of_vol = 0.001

            # Vol skew: asymétrie entre hausse/baisse (upside vs downside vol)
            btc_history = get_cached_history("BTC", days=30)
            if btc_history and len(btc_history) >= 30:
                prices = np.array([p for _, p in btc_history])
                returns = np.diff(np.log(prices))

                # Séparer returns positifs/négatifs
                up_returns = returns[returns > 0]
                down_returns = returns[returns < 0]

                if len(up_returns) > 2 and len(down_returns) > 2:
                    up_vol = np.std(up_returns)
                    down_vol = np.std(down_returns)
                    vol_skew = (down_vol - up_vol) / (down_vol + up_vol + 1e-10)  # -1 à +1
                else:
                    vol_skew = 0.0
            else:
                vol_skew = 0.0

            return {
                "vol_1h": float(avg_vol_1h),
                "vol_4h": float(avg_vol_4h),
                "vol_of_vol": float(vol_of_vol),
                "vol_skew": float(vol_skew)
            }

        except Exception as e:
            logger.warning(f"Volatility features extraction error: {e}")
            # Fallback to safe defaults
            return {
                "vol_1h": 0.02,
                "vol_4h": 0.04,
                "vol_of_vol": 0.001,
                "vol_skew": 0.0
            }
    
    def _extract_momentum_features(self, price_data: Dict) -> Dict[str, float]:
        """Extrait features de momentum depuis données de prix réelles"""
        from services.price_history import get_cached_history

        try:
            # Récupérer prix BTC comme proxy marché principal
            btc_history = get_cached_history("BTC", days=30)
            if not btc_history or len(btc_history) < 30:
                # Fallback to defaults
                return {
                    "momentum_1h": 0.01,
                    "momentum_4h": 0.02,
                    "volume_momentum": 0.0
                }

            prices = np.array([p for _, p in btc_history])

            # Momentum 1h: return moyen des dernières 24h
            if len(prices) >= 25:
                returns_24h = np.diff(np.log(prices[-25:]))
                momentum_1h = np.mean(returns_24h)
            else:
                momentum_1h = 0.0

            # Momentum 4h: return moyen des derniers 4 jours (96h)
            if len(prices) >= 5:
                # Comparer prix actuel vs 4 jours avant
                momentum_4h = np.log(prices[-1] / prices[-5]) / 4  # Return quotidien moyen
            else:
                momentum_4h = 0.0

            # Volume momentum: RSI-14 comme proxy de momentum de volume
            # (Simplified RSI: ratio gains/pertes sur 14 périodes)
            if len(prices) >= 15:
                returns = np.diff(np.log(prices[-15:]))
                gains = returns[returns > 0]
                losses = -returns[returns < 0]

                avg_gain = np.mean(gains) if len(gains) > 0 else 0.0
                avg_loss = np.mean(losses) if len(losses) > 0 else 0.0

                if avg_loss == 0:
                    rsi = 100.0
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))

                # Normaliser RSI 0-100 vers -1 à +1 (50 = neutre)
                volume_momentum = (rsi - 50) / 50.0
            else:
                volume_momentum = 0.0

            return {
                "momentum_1h": float(momentum_1h),
                "momentum_4h": float(momentum_4h),
                "volume_momentum": float(np.clip(volume_momentum, -1, 1))
            }

        except Exception as e:
            logger.warning(f"Momentum features extraction error: {e}")
            # Fallback to safe defaults
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

    def _deduce_affected_assets(self, features_array: np.ndarray, alert_type: PredictiveAlertType) -> List[str]:
        """Déduit les assets concernés depuis features et type d'alerte"""
        try:
            features_dict = self._array_to_features_dict(features_array)

            # Logique de déduction selon type d'alerte
            if alert_type == PredictiveAlertType.VOLATILITY_SPIKE_IMMINENT:
                # Volatilité spike: impacte large caps d'abord (BTC/ETH)
                # Si vol élevée, ajouter alts également
                vol_1h = features_dict.get("realized_vol_1h", 0)
                if vol_1h > 0.6:  # Très haute volatilité
                    return ["BTC", "ETH", "SOL", "AVAX"]
                else:
                    return ["BTC", "ETH"]

            elif alert_type == PredictiveAlertType.REGIME_CHANGE_PENDING:
                # Changement régime: impacte tout le marché
                return ["BTC", "ETH", "SOL", "ADA", "DOT"]

            elif alert_type == PredictiveAlertType.CORRELATION_BREAKDOWN:
                # Décorrélation: impacte surtout les alts (perdent corrélation à BTC)
                spread = features_dict.get("large_alt_spread", 0)
                if spread > 0.05:  # Alts surperforment
                    return ["SOL", "ADA", "AVAX", "LINK"]
                else:
                    return ["BTC", "ETH", "SOL"]

            elif alert_type == PredictiveAlertType.SPIKE_LIKELY:
                # Spike corrélation: impacte les pairs corrélés
                btc_eth_corr = features_dict.get("btc_eth_correlation", 0)
                if btc_eth_corr > 0.8:  # Haute corrélation BTC/ETH
                    return ["BTC", "ETH"]
                else:
                    return ["BTC", "ETH", "SOL"]

            # Fallback: BTC + ETH comme défaut
            return ["BTC", "ETH"]

        except Exception as e:
            logger.warning(f"Asset deduction error: {e}")
            return ["BTC", "ETH"]  # Fallback sûr
    
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