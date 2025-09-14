"""
Machine Learning Models for Crypto Portfolio Management
Basic predictive models for market regime detection and return forecasting
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, mean_squared_error, classification_report
import pickle
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """Market regime classifications"""
    ACCUMULATION = "accumulation"
    EXPANSION = "expansion" 
    EUPHORIA = "euphoria"
    DISTRIBUTION = "distribution"

@dataclass
class RegimePrediction:
    """Market regime prediction result"""
    regime: MarketRegime
    confidence: float
    probabilities: Dict[str, float]
    features_importance: Dict[str, float]
    timestamp: pd.Timestamp

@dataclass
class ReturnForecast:
    """Return forecast result"""
    expected_returns: Dict[str, float]
    confidence_intervals: Dict[str, Tuple[float, float]]
    model_accuracy: float
    forecast_horizon: int  # days
    timestamp: pd.Timestamp

class CryptoMLPredictor:
    """Machine Learning predictor for crypto markets"""
    
    def __init__(self, models_path: str = "data/models"):
        self.models_path = Path(models_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        
        self.regime_model = None
        self.return_models = {}  # Per asset return models
        self.feature_scaler = StandardScaler()
        
        # Model parameters
        self.regime_model_params = {
            'n_estimators': 100,
            'max_depth': 10,
            'min_samples_split': 5,
            'random_state': 42
        }
        
        self.return_model_params = {
            'n_estimators': 50,
            'max_depth': 8,
            'min_samples_split': 10,
            'random_state': 42
        }
        
    def prepare_features(self, price_data: pd.DataFrame, 
                        market_indicators: Optional[Dict] = None) -> pd.DataFrame:
        """
        Prepare ML features from price data and market indicators
        """
        
        features = pd.DataFrame(index=price_data.index)
        
        # Technical indicators features
        for asset in price_data.columns:
            prices = price_data[asset].dropna()
            
            # Returns features
            returns = prices.pct_change()
            features[f'{asset}_return_1d'] = returns
            features[f'{asset}_return_7d'] = returns.rolling(7).sum()
            features[f'{asset}_return_30d'] = returns.rolling(30).sum()
            
            # Volatility features
            features[f'{asset}_vol_7d'] = returns.rolling(7).std()
            features[f'{asset}_vol_30d'] = returns.rolling(30).std()
            features[f'{asset}_vol_ratio'] = features[f'{asset}_vol_7d'] / features[f'{asset}_vol_30d']
            
            # Price momentum features
            features[f'{asset}_ma_20'] = prices.rolling(20).mean()
            features[f'{asset}_ma_50'] = prices.rolling(50).mean()
            features[f'{asset}_price_to_ma20'] = prices / features[f'{asset}_ma_20']
            features[f'{asset}_price_to_ma50'] = prices / features[f'{asset}_ma_50']
            
            # RSI approximation
            gains = returns.where(returns > 0, 0)
            losses = -returns.where(returns < 0, 0)
            avg_gains = gains.rolling(14).mean()
            avg_losses = losses.rolling(14).mean()
            rs = avg_gains / avg_losses
            features[f'{asset}_rsi'] = 100 - (100 / (1 + rs))
            
        # Cross-asset features
        if 'BTC' in price_data.columns and 'ETH' in price_data.columns:
            btc_returns = price_data['BTC'].pct_change()
            eth_returns = price_data['ETH'].pct_change()
            
            # BTC dominance proxy
            features['btc_eth_ratio'] = price_data['BTC'] / price_data['ETH']
            features['btc_eth_corr'] = btc_returns.rolling(30).corr(eth_returns)
            
        # Market-wide features
        if len(price_data.columns) > 1:
            all_returns = price_data.pct_change()
            features['market_vol'] = all_returns.mean(axis=1).rolling(30).std()
            features['market_trend'] = all_returns.mean(axis=1).rolling(7).mean()
            
            # Cross-correlation features
            corr_matrix = all_returns.rolling(30).corr()
            # Average correlation (excluding diagonal)
            features['avg_correlation'] = corr_matrix.groupby(level=0).apply(
                lambda x: x.values[np.triu_indices_from(x.values, k=1)].mean()
            )
        
        # External market indicators (if provided)
        if market_indicators:
            for name, series in market_indicators.items():
                if isinstance(series, pd.Series):
                    features[f'market_{name}'] = series.reindex(features.index)
                elif isinstance(series, (int, float)):
                    features[f'market_{name}'] = series
                    
        return features.fillna(method='ffill').dropna()
    
    def prepare_regime_labels(self, price_data: pd.DataFrame, 
                             primary_asset: str = 'BTC') -> pd.Series:
        """
        Create market regime labels based on price action and volatility
        """
        
        if primary_asset not in price_data.columns:
            primary_asset = price_data.columns[0]
            
        prices = price_data[primary_asset]
        returns = prices.pct_change()
        
        # Rolling metrics for regime classification
        vol_30d = returns.rolling(30).std() * np.sqrt(365)  # Annualized volatility
        return_30d = returns.rolling(30).mean() * 365  # Annualized return
        trend_90d = returns.rolling(90).mean() * 365
        
        # Regime classification logic
        labels = pd.Series(index=prices.index, dtype='object')
        
        for i in range(90, len(prices)):  # Start after 90-day window
            vol = vol_30d.iloc[i]
            ret_30 = return_30d.iloc[i] 
            ret_90 = trend_90d.iloc[i]
            
            # Dynamic thresholds based on historical data
            vol_pct = np.percentile(vol_30d.dropna().iloc[:i], 75)
            
            if ret_90 < -0.2:  # Strong downtrend
                if vol > vol_pct:
                    labels.iloc[i] = MarketRegime.DISTRIBUTION.value
                else:
                    labels.iloc[i] = MarketRegime.ACCUMULATION.value
            elif ret_90 > 0.5:  # Strong uptrend
                if vol > vol_pct:
                    labels.iloc[i] = MarketRegime.EUPHORIA.value
                else:
                    labels.iloc[i] = MarketRegime.EXPANSION.value
            else:  # Neutral trend
                if vol > vol_pct:
                    labels.iloc[i] = MarketRegime.DISTRIBUTION.value
                else:
                    labels.iloc[i] = MarketRegime.EXPANSION.value
                    
        return labels.dropna()
    
    def train_regime_model(self, features: pd.DataFrame, labels: pd.Series) -> Dict:
        """
        Train market regime classification model
        """
        
        # Align features and labels
        common_index = features.index.intersection(labels.index)
        X = features.loc[common_index].fillna(0)
        y = labels.loc[common_index]
        
        if len(X) < 100:
            raise ValueError("Insufficient data for training. Need at least 100 samples.")
        
        # Scale features
        X_scaled = self.feature_scaler.fit_transform(X)
        
        # Train/validation split
        X_train, X_val, y_train, y_val = train_test_split(
            X_scaled, y, test_size=0.3, random_state=42, stratify=y
        )
        
        # Train Random Forest model
        self.regime_model = RandomForestClassifier(**self.regime_model_params)
        self.regime_model.fit(X_train, y_train)
        
        # Validation
        y_pred = self.regime_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        # Cross-validation score
        cv_scores = cross_val_score(self.regime_model, X_scaled, y, cv=5)
        
        # Feature importance
        feature_importance = dict(zip(
            features.columns, 
            self.regime_model.feature_importances_
        ))
        
        training_results = {
            'accuracy': accuracy,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'feature_importance': feature_importance,
            'classification_report': classification_report(y_val, y_pred, output_dict=True),
            'training_samples': len(X_train),
            'validation_samples': len(X_val)
        }
        
        logger.info(f"Regime model trained: Accuracy={accuracy:.3f}, CV={cv_scores.mean():.3f}±{cv_scores.std():.3f}")
        
        return training_results
    
    def train_return_models(self, features: pd.DataFrame, 
                           price_data: pd.DataFrame,
                           forecast_horizon: int = 7) -> Dict:
        """
        Train return forecasting models for each asset
        """
        
        training_results = {}
        
        for asset in price_data.columns:
            try:
                # Prepare target variable (future returns)
                returns = price_data[asset].pct_change()
                future_returns = returns.rolling(forecast_horizon).sum().shift(-forecast_horizon)
                
                # Align data
                common_index = features.index.intersection(future_returns.index)
                X = features.loc[common_index].fillna(0)
                y = future_returns.loc[common_index].dropna()
                
                if len(X) < 50:
                    logger.warning(f"Insufficient data for {asset}, skipping")
                    continue
                
                # Align X and y after dropna
                common_index_final = X.index.intersection(y.index)
                X = X.loc[common_index_final]
                y = y.loc[common_index_final]
                
                # Scale features
                X_scaled = self.feature_scaler.transform(X)
                
                # Train/validation split
                X_train, X_val, y_train, y_val = train_test_split(
                    X_scaled, y, test_size=0.3, random_state=42
                )
                
                # Train model
                model = RandomForestRegressor(**self.return_model_params)
                model.fit(X_train, y_train)
                
                # Validation
                y_pred = model.predict(X_val)
                mse = mean_squared_error(y_val, y_pred)
                
                # Cross-validation
                cv_scores = cross_val_score(model, X_scaled, y, cv=5, scoring='neg_mean_squared_error')
                
                self.return_models[asset] = model
                
                training_results[asset] = {
                    'mse': mse,
                    'rmse': np.sqrt(mse),
                    'cv_mean': -cv_scores.mean(),
                    'cv_std': cv_scores.std(),
                    'training_samples': len(X_train),
                    'validation_samples': len(X_val)
                }
                
                logger.info(f"{asset} return model trained: RMSE={np.sqrt(mse):.4f}")
                
            except Exception as e:
                logger.error(f"Failed to train return model for {asset}: {e}")
                continue
                
        return training_results
    
    def predict_regime(self, features: pd.DataFrame) -> RegimePrediction:
        """
        Predict current market regime
        """
        
        if self.regime_model is None:
            raise ValueError("Regime model not trained")
        
        # Use latest features
        latest_features = features.iloc[-1:].fillna(0)
        X_scaled = self.feature_scaler.transform(latest_features)
        
        # Prediction
        regime_pred = self.regime_model.predict(X_scaled)[0]
        probabilities = self.regime_model.predict_proba(X_scaled)[0]
        
        # Get class names
        classes = self.regime_model.classes_
        prob_dict = dict(zip(classes, probabilities))
        
        # Feature importance for latest prediction
        feature_importance = dict(zip(
            features.columns,
            self.regime_model.feature_importances_
        ))
        
        return RegimePrediction(
            regime=MarketRegime(regime_pred),
            confidence=max(probabilities),
            probabilities=prob_dict,
            features_importance=feature_importance,
            timestamp=features.index[-1]
        )
    
    def predict_returns(self, features: pd.DataFrame,
                       forecast_horizon: int = 7) -> ReturnForecast:
        """
        Predict future returns for all assets
        """
        
        if not self.return_models:
            raise ValueError("Return models not trained")
        
        # Use latest features
        latest_features = features.iloc[-1:].fillna(0)
        X_scaled = self.feature_scaler.transform(latest_features)
        
        expected_returns = {}
        confidence_intervals = {}
        
        for asset, model in self.return_models.items():
            try:
                # Point prediction
                prediction = model.predict(X_scaled)[0]
                
                # Bootstrap confidence intervals (simplified)
                # In practice, you'd use model.predict with uncertainty estimation
                prediction_std = abs(prediction) * 0.2  # Rough estimate
                
                expected_returns[asset] = prediction
                confidence_intervals[asset] = (
                    prediction - 1.96 * prediction_std,
                    prediction + 1.96 * prediction_std
                )
                
            except Exception as e:
                logger.error(f"Failed to predict returns for {asset}: {e}")
                continue
        
        # Calculate overall model accuracy (placeholder)
        model_accuracy = 0.65  # This would be calculated from validation
        
        return ReturnForecast(
            expected_returns=expected_returns,
            confidence_intervals=confidence_intervals,
            model_accuracy=model_accuracy,
            forecast_horizon=forecast_horizon,
            timestamp=features.index[-1]
        )
    
    def save_models(self) -> bool:
        """Save trained models to disk"""
        
        try:
            # Save regime model
            if self.regime_model is not None:
                with open(self.models_path / 'regime_model.pkl', 'wb') as f:
                    pickle.dump(self.regime_model, f)
                    
            # Save return models
            if self.return_models:
                with open(self.models_path / 'return_models.pkl', 'wb') as f:
                    pickle.dump(self.return_models, f)
                    
            # Save scaler
            with open(self.models_path / 'feature_scaler.pkl', 'wb') as f:
                pickle.dump(self.feature_scaler, f)
                
            logger.info(f"Models saved to {self.models_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save models: {e}")
            return False
    
    def load_models(self) -> bool:
        """Load trained models from disk"""
        
        try:
            # Load regime model
            regime_path = self.models_path / 'regime_model.pkl'
            if regime_path.exists():
                with open(regime_path, 'rb') as f:
                    self.regime_model = pickle.load(f)
                    
            # Load return models
            return_path = self.models_path / 'return_models.pkl'
            if return_path.exists():
                with open(return_path, 'rb') as f:
                    self.return_models = pickle.load(f)
                    
            # Load scaler
            scaler_path = self.models_path / 'feature_scaler.pkl'
            if scaler_path.exists():
                with open(scaler_path, 'rb') as f:
                    self.feature_scaler = pickle.load(f)
                    
            logger.info("Models loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            return False

class CryptoMLPipeline:
    """Full ML pipeline for crypto portfolio management"""
    
    def __init__(self):
        self.predictor = CryptoMLPredictor()
        self.is_trained = False
        
    def train_pipeline(self, price_data: pd.DataFrame, 
                      market_indicators: Optional[Dict] = None,
                      save_models: bool = True) -> Dict:
        """
        Train the complete ML pipeline
        """
        
        logger.info("Starting ML pipeline training...")
        
        # Prepare features
        features = self.predictor.prepare_features(price_data, market_indicators)
        logger.info(f"Prepared {len(features.columns)} features from {len(features)} samples")
        
        # Prepare regime labels
        regime_labels = self.predictor.prepare_regime_labels(price_data)
        logger.info(f"Prepared regime labels: {len(regime_labels)} samples")
        
        results = {}
        
        # Train regime model
        try:
            regime_results = self.predictor.train_regime_model(features, regime_labels)
            results['regime_model'] = regime_results
        except Exception as e:
            logger.error(f"Failed to train regime model: {e}")
            results['regime_model'] = {'error': str(e)}
        
        # Train return models
        try:
            return_results = self.predictor.train_return_models(features, price_data)
            results['return_models'] = return_results
        except Exception as e:
            logger.error(f"Failed to train return models: {e}")
            results['return_models'] = {'error': str(e)}
        
        # Save models
        if save_models:
            success = self.predictor.save_models()
            results['models_saved'] = success
            
        self.is_trained = True
        logger.info("ML pipeline training completed")
        
        return results
    
    def get_predictions(self, price_data: pd.DataFrame,
                       market_indicators: Optional[Dict] = None) -> Dict:
        """
        Get current predictions from trained models
        """
        
        if not self.is_trained:
            # Try to load models
            if not self.predictor.load_models():
                raise ValueError("Models not trained and cannot be loaded")
            self.is_trained = True
        
        # Prepare features
        features = self.predictor.prepare_features(price_data, market_indicators)
        
        predictions = {}
        
        # Regime prediction
        try:
            regime_pred = self.predictor.predict_regime(features)
            predictions['regime'] = {
                'regime': regime_pred.regime.value,
                'confidence': regime_pred.confidence,
                'probabilities': regime_pred.probabilities,
                'timestamp': regime_pred.timestamp.isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to predict regime: {e}")
            predictions['regime'] = {'error': str(e)}
        
        # Return predictions
        try:
            return_pred = self.predictor.predict_returns(features)
            predictions['returns'] = {
                'expected_returns': return_pred.expected_returns,
                'confidence_intervals': {
                    k: [float(v[0]), float(v[1])] 
                    for k, v in return_pred.confidence_intervals.items()
                },
                'model_accuracy': return_pred.model_accuracy,
                'forecast_horizon': return_pred.forecast_horizon,
                'timestamp': return_pred.timestamp.isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to predict returns: {e}")
            predictions['returns'] = {'error': str(e)}
        
        return predictions

# Global ML pipeline instance
ml_pipeline = CryptoMLPipeline()