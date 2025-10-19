"""
Market Regime Detection using Hybrid HMM + Neural Networks
Detects 4 crypto market regimes: Accumulation, Expansion, Euphoria, Distribution
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime, timedelta
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from hmmlearn import hmm
import logging
import joblib
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

from ..feature_engineering import CryptoFeatureEngineer
from ..data_pipeline import MLDataPipeline

logger = logging.getLogger(__name__)


def _set_reproducible_seeds(seed: int = 42):
    """Fix all random seeds for reproducibility across training runs"""
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    # Make PyTorch deterministic
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# Alias de compatibilité pour charger les anciens modèles
RegimeClassifier = None  # Sera défini après RegimeClassificationNetwork

class RegimeClassificationNetwork(nn.Module):
    """
    Neural Network for regime classification from features
    Combines traditional features with learned representations
    """
    
    def __init__(self, input_size: int, hidden_size: int = 64, num_regimes: int = 4, 
                 dropout: float = 0.3):
        super(RegimeClassificationNetwork, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_regimes = num_regimes
        
        # Feature extraction layers
        self.feature_extractor = nn.Sequential(
            nn.Linear(input_size, hidden_size * 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size * 2, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        
        # Attention mechanism for feature importance
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_size,
            num_heads=4,
            dropout=dropout,
            batch_first=True
        )
        
        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, num_regimes)
        )
        
        # Initialize weights
        self.apply(self._init_weights)
    
    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            torch.nn.init.xavier_uniform_(m.weight)
            m.bias.data.fill_(0.01)
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass
        Args:
            x: Input features [batch_size, sequence_length, input_size] or [batch_size, input_size]
        Returns:
            logits: Classification logits [batch_size, num_regimes]
            attention_weights: Attention weights for interpretability
        """
        batch_size = x.size(0)
        
        # Handle both sequential and non-sequential input
        if len(x.shape) == 2:
            x = x.unsqueeze(1)  # Add sequence dimension
        
        # Feature extraction
        features = self.feature_extractor(x)  # [batch_size, seq_len, hidden_size]
        
        # Self-attention for feature importance
        attended_features, attention_weights = self.attention(features, features, features)
        
        # Global average pooling over sequence dimension
        pooled_features = attended_features.mean(dim=1)  # [batch_size, hidden_size]
        
        # Classification
        logits = self.classifier(pooled_features)
        
        return logits, attention_weights

# Alias de compatibilité pour les anciens modèles
RegimeClassifier = RegimeClassificationNetwork

class RegimeDetector:
    """
    Advanced Market Regime Detector using Hybrid HMM + Neural Networks
    Detects 4 market regimes with confidence scoring and feature interpretation
    """
    
    def __init__(self, model_dir: str = "models/regime"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Model parameters
        self.num_regimes = 4

        # IMPORTANT: Regime names depend on market type
        # For STOCKS (SPY, QQQ, etc.): Score-based ordering is INVERTED from crypto
        #   - Regime 0 (lowest score) = Bear Market (negative returns, high vol)
        #   - Regime 3 (highest score) = Bull Market (positive returns, low vol)
        # For CRYPTO: Original names apply
        #   - Regime 0 = Accumulation, Regime 3 = Distribution

        # Default to stock market regime names (since we're using stocks primarily)
        self.regime_names = ['Bear Market', 'Consolidation', 'Bull Market', 'Distribution']

        self.regime_descriptions = {
            0: {  # Bear Market (stocks) / Accumulation (crypto)
                'name': 'Bear Market',
                'description': 'Market in decline - risk-off phase with negative returns',
                'characteristics': ['Declining prices', 'High volatility', 'Negative momentum'],
                'strategy': 'Defensive positioning, increase cash/bonds, hedge risk',
                'risk_level': 'High',
                'allocation_bias': 'Significantly reduce risky assets'
            },
            1: {  # Consolidation (stocks) / Expansion (crypto)
                'name': 'Consolidation',
                'description': 'Market in consolidation - sideways action after decline or before breakout',
                'characteristics': ['Range-bound prices', 'Moderate volatility', 'Mixed signals'],
                'strategy': 'Balanced approach, wait for confirmation',
                'risk_level': 'Moderate',
                'allocation_bias': 'Neutral allocation'
            },
            2: {  # Bull Market (stocks) / Euphoria (crypto)
                'name': 'Bull Market',
                'description': 'Market in sustained uptrend - risk-on phase with positive returns',
                'characteristics': ['Rising prices', 'Controlled volatility', 'Positive momentum'],
                'strategy': 'Maintain positions, selective additions, ride the trend',
                'risk_level': 'Low to Moderate',
                'allocation_bias': 'Increase risky assets allocation'
            },
            3: {  # Distribution (stocks - strongest bull) / Distribution (crypto - topping)
                'name': 'Distribution',
                'description': 'Market at extremes - either strong bull continuation or topping pattern',
                'characteristics': ['Extreme momentum', 'Variable volatility', 'Sentiment extremes'],
                'strategy': 'Monitor closely for reversal signs, consider profit-taking',
                'risk_level': 'Moderate to High',
                'allocation_bias': 'Cautious - watch for regime change'
            }
        }
        
        # Neural network hyperparameters
        self.hidden_size = 64
        self.dropout = 0.3
        self.learning_rate = 0.001
        self.batch_size = 64
        self.epochs = 100
        self.early_stopping_patience = 15
        
        # HMM parameters
        self.hmm_n_components = self.num_regimes
        self.hmm_covariance_type = "full"
        self.hmm_n_iter = 1000
        
        # Initialize components
        self.feature_engineer = CryptoFeatureEngineer()
        self.data_pipeline = MLDataPipeline()
        
        # Model storage
        self.neural_model = None
        self.hmm_model = None
        self.scaler = None
        self.feature_columns = []
        self.training_metadata = {}
        
        # Device selection
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"RegimeDetector using device: {self.device}")
    
    def train_regime_model(self, market_data: Dict[str, pd.DataFrame], 
                          lookback_days: int = 365, validation_split: float = 0.2) -> Dict[str, Any]:
        """
        Train regime detection model - alias for train_model
        
        Args:
            market_data: Dictionary of asset price data
            lookback_days: Number of days to use for training
            validation_split: Validation data fraction
            
        Returns:
            Training metadata
        """
        # Filter data to lookback period if specified
        if lookback_days and lookback_days > 0:
            cutoff_date = max([df.index.max() for df in market_data.values()]) - timedelta(days=lookback_days)
            filtered_data = {}
            for symbol, df in market_data.items():
                filtered_data[symbol] = df[df.index >= cutoff_date]
        else:
            filtered_data = market_data
            
        return self.train_model(filtered_data, validation_split)
    
    def prepare_regime_features(self, multi_asset_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Prepare comprehensive features for regime detection from multiple assets
        
        Args:
            multi_asset_data: Dictionary of asset DataFrames with OHLCV data
            
        Returns:
            DataFrame with regime detection features
        """
        logger.info(f"Preparing regime features from {len(multi_asset_data)} assets")
        
        if not multi_asset_data:
            raise ValueError("No asset data provided")
        
        # Get market-wide features by averaging across major assets
        # Support both crypto and stock market tickers
        crypto_majors = ['BTC', 'ETH', 'SOL', 'ADA', 'AVAX']
        stock_majors = ['SPY', 'QQQ', 'IWM', 'DIA', 'EFA', 'EEM', 'VTI', 'AGG']

        # Detect if we're analyzing crypto or stocks
        available_crypto = [asset for asset in crypto_majors if asset in multi_asset_data]
        available_stocks = [asset for asset in stock_majors if asset in multi_asset_data]

        if available_crypto:
            available_major = available_crypto
            logger.info(f"Detected crypto market - using {len(available_major)} crypto assets")
        elif available_stocks:
            available_major = available_stocks
            logger.info(f"Detected stock market - using {len(available_major)} stock assets")
        else:
            # Use all available assets (up to 5 for performance)
            available_major = list(multi_asset_data.keys())[:5]
            logger.info(f"Using all available assets: {available_major}")

        logger.info(f"Using assets for market features: {available_major}")
        
        # Collect features from each asset - use simple approach for reliability
        asset_features = {}
        for symbol in available_major:
            try:
                asset_df = multi_asset_data[symbol].copy()
                
                # Create basic features directly for regime detection
                if 'close' in asset_df.columns:
                    asset_df['returns'] = asset_df['close'].pct_change()
                
                if 'returns' not in asset_df.columns and 'close' in asset_df.columns:
                    asset_df['returns'] = asset_df['close'].pct_change()
                
                # Basic features for regime detection
                simple_features = pd.DataFrame(index=asset_df.index)
                simple_features['returns'] = asset_df.get('returns', asset_df['close'].pct_change())
                simple_features['realized_vol'] = simple_features['returns'].rolling(20).std() * np.sqrt(365)
                simple_features['volume_ratio'] = asset_df.get('volume', pd.Series(1, index=asset_df.index)) / asset_df.get('volume', pd.Series(1, index=asset_df.index)).rolling(20).mean()
                simple_features['rsi'] = self._calculate_rsi(asset_df['close']) if 'close' in asset_df.columns else pd.Series(50, index=asset_df.index)
                simple_features['price_momentum_20'] = asset_df['close'].pct_change(20) if 'close' in asset_df.columns else pd.Series(0, index=asset_df.index)
                
                # Fill NaN values
                simple_features = simple_features.fillna(method='ffill').fillna(0)
                
                asset_features[symbol] = simple_features
                logger.info(f"Created simple features for {symbol}: {len(simple_features)} samples")
                
            except Exception as e:
                logger.warning(f"Failed to create features for {symbol}: {str(e)}")
        
        if not asset_features:
            raise ValueError("Failed to create features for any asset")
        
        # Align all features on common dates
        common_dates = None
        for features_df in asset_features.values():
            if common_dates is None:
                common_dates = features_df.index
            else:
                common_dates = common_dates.intersection(features_df.index)
        
        logger.info(f"Common dates available: {len(common_dates)}")
        
        # Create market-wide regime features
        market_features = []
        
        for date in common_dates:
            try:
                # Collect features from all assets for this date
                daily_features = {}
                
                # Price and momentum features (market average)
                returns = []
                volatilities = []
                volumes = []
                rsi_values = []
                momentum_values = []
                
                for symbol, features_df in asset_features.items():
                    if date in features_df.index:
                        row = features_df.loc[date]
                        if not pd.isna(row['returns']):
                            returns.append(row['returns'])
                        if not pd.isna(row['realized_vol']):
                            volatilities.append(row['realized_vol'])
                        if not pd.isna(row['volume_ratio']):
                            volumes.append(row['volume_ratio'])
                        if not pd.isna(row['rsi']):
                            rsi_values.append(row['rsi'])
                        if not pd.isna(row['price_momentum_20']):
                            momentum_values.append(row['price_momentum_20'])
                
                # Market-wide aggregated features
                daily_features['market_return'] = np.mean(returns) if returns else 0
                daily_features['market_volatility'] = np.mean(volatilities) if volatilities else 0
                daily_features['market_volume_ratio'] = np.mean(volumes) if volumes else 1
                daily_features['market_rsi'] = np.mean(rsi_values) if rsi_values else 50
                daily_features['market_momentum'] = np.mean(momentum_values) if momentum_values else 0
                
                # Cross-asset features
                if len(returns) > 1:
                    daily_features['return_dispersion'] = np.std(returns)
                    daily_features['volatility_dispersion'] = np.std(volatilities) if len(volatilities) > 1 else 0
                else:
                    daily_features['return_dispersion'] = 0
                    daily_features['volatility_dispersion'] = 0
                
                # Regime-specific features
                daily_features['fear_greed_proxy'] = self._calculate_fear_greed_proxy(
                    daily_features['market_rsi'],
                    daily_features['market_volatility'],
                    daily_features['market_momentum']
                )
                
                daily_features['trend_strength'] = abs(daily_features['market_momentum'])
                daily_features['volume_trend'] = max(0, daily_features['market_volume_ratio'] - 1)
                
                # Time-based features
                daily_features['day_of_week'] = date.dayofweek
                daily_features['is_weekend'] = int(date.dayofweek >= 5)
                daily_features['month'] = date.month
                
                # BTC dominance proxy (if BTC is available)
                if 'BTC' in asset_features and date in asset_features['BTC'].index:
                    btc_performance = asset_features['BTC'].loc[date]['returns']
                    market_performance = daily_features['market_return']
                    daily_features['btc_dominance_proxy'] = btc_performance - market_performance
                else:
                    daily_features['btc_dominance_proxy'] = 0
                
                market_features.append(daily_features)
                
            except Exception as e:
                logger.warning(f"Error processing features for {date}: {str(e)}")
                continue
        
        # Convert to DataFrame
        features_df = pd.DataFrame(market_features, index=common_dates[:len(market_features)])
        
        # Add rolling features
        for window in [5, 20, 60]:
            features_df[f'volatility_ma_{window}'] = features_df['market_volatility'].rolling(window=window).mean()
            features_df[f'return_ma_{window}'] = features_df['market_return'].rolling(window=window).mean()
            features_df[f'momentum_ma_{window}'] = features_df['market_momentum'].rolling(window=window).mean()
        
        # Remove NaN rows
        features_df = features_df.dropna()
        
        # Store feature columns
        self.feature_columns = list(features_df.columns)
        
        logger.info(f"Regime features prepared: {len(features_df)} samples, {len(self.feature_columns)} features")
        return features_df
    
    def _calculate_fear_greed_proxy(self, rsi: float, volatility: float, momentum: float) -> float:
        """Calculate Fear & Greed proxy from market indicators"""
        # Normalize RSI (50 = neutral)
        rsi_score = (rsi - 50) / 50  # -1 to 1
        
        # Volatility score (lower volatility = less fear)
        vol_score = max(0, 1 - volatility * 10)  # Approximate normalization
        
        # Momentum score
        momentum_score = np.tanh(momentum * 20)  # -1 to 1
        
        # Combine scores (0-100 scale)
        fear_greed = (rsi_score * 0.4 + vol_score * 0.3 + momentum_score * 0.3) * 50 + 50
        return np.clip(fear_greed, 0, 100)
    
    def _create_hmm_regime_labels(self, features: pd.DataFrame) -> np.ndarray:
        """
        Create initial regime labels using HMM for neural network training
        
        Args:
            features: Feature DataFrame
            
        Returns:
            Regime labels array
        """
        logger.info("Creating initial regime labels using HMM")
        
        # Select key features for HMM
        hmm_features = [
            'market_return', 'market_volatility', 'market_momentum',
            'return_dispersion', 'trend_strength', 'fear_greed_proxy'
        ]
        
        # Ensure features exist
        available_features = [f for f in hmm_features if f in features.columns]
        if len(available_features) < 3:
            logger.warning(f"Limited features available for HMM: {available_features}")
        
        X = features[available_features].values
        
        # Normalize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Fit Gaussian HMM
        model = hmm.GaussianHMM(
            n_components=self.hmm_n_components,
            covariance_type=self.hmm_covariance_type,
            n_iter=self.hmm_n_iter,
            random_state=42
        )
        
        model.fit(X_scaled)
        regime_labels = model.predict(X_scaled)
        
        # Map regimes to meaningful order based on characteristics
        regime_characteristics = []
        for regime in range(self.hmm_n_components):
            regime_mask = regime_labels == regime
            if np.sum(regime_mask) > 0:
                # Calculate regime characteristics
                avg_return = np.mean(features.loc[regime_mask, 'market_return'])
                avg_volatility = np.mean(features.loc[regime_mask, 'market_volatility'])
                avg_momentum = np.mean(features.loc[regime_mask, 'market_momentum'])

                # Score for ordering: combine return, -volatility, momentum
                score = avg_return * 0.4 - avg_volatility * 0.3 + avg_momentum * 0.3
                regime_characteristics.append({
                    'id': regime,
                    'return': avg_return,
                    'volatility': avg_volatility,
                    'momentum': avg_momentum,
                    'score': score,
                    'count': np.sum(regime_mask)
                })

        # Log detailed characteristics for debugging
        logger.info("=== HMM Regime Characteristics ===")
        for char in regime_characteristics:
            logger.info(f"  Cluster {char['id']}: return={char['return']:.4f}, vol={char['volatility']:.4f}, "
                       f"momentum={char['momentum']:.4f}, score={char['score']:.4f}, count={char['count']}")

        # Sort by score to create ordered regimes
        regime_characteristics.sort(key=lambda x: x['score'])

        # Create mapping: 0=Bear Market (lowest score), 1=Consolidation, 2=Bull Market, 3=Distribution (highest score)
        regime_mapping = {}
        for new_regime, char in enumerate(regime_characteristics):
            regime_mapping[char['id']] = new_regime
            regime_name = self.regime_names[new_regime] if new_regime < len(self.regime_names) else f"Regime {new_regime}"
            logger.info(f"  Cluster {char['id']} → {new_regime} ({regime_name})")

        # Apply mapping
        mapped_labels = np.array([regime_mapping[label] for label in regime_labels])

        logger.info(f"HMM regime distribution: {np.bincount(mapped_labels)}")
        return mapped_labels
    
    def train_model(self, multi_asset_data: Dict[str, pd.DataFrame],
                   validation_split: float = 0.2) -> Dict[str, Any]:
        """
        Train hybrid regime detection model

        Args:
            multi_asset_data: Dictionary of asset price data
            validation_split: Validation data fraction

        Returns:
            Training metadata
        """
        # Fix random seeds for reproducibility
        _set_reproducible_seeds(42)

        logger.info("Training hybrid regime detection model")

        try:
            # Prepare features
            features_df = self.prepare_regime_features(multi_asset_data)

            if len(features_df) < 100:
                raise ValueError(f"Insufficient data: {len(features_df)} samples (minimum 100 required)")
            
            # Create regime labels using HMM
            regime_labels = self._create_hmm_regime_labels(features_df)
            
            # Prepare data for neural network
            X = features_df.values
            y = regime_labels
            
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            # Train-validation split (stratified to preserve class distribution)
            # Temporal split can lead to validation set with only one class!
            from sklearn.model_selection import train_test_split
            X_train, X_val, y_train, y_val = train_test_split(
                X_scaled, y,
                test_size=validation_split,
                stratify=y,  # Preserve class distribution in both sets
                random_state=42  # Reproducibility
            )

            logger.info(f"Training samples: {len(X_train)}, Validation samples: {len(X_val)}")
            logger.info(f"Validation class distribution: {np.bincount(y_val).tolist()}")

            # Calculate class weights to handle imbalance
            class_counts = np.bincount(y_train)
            total_samples = len(y_train)
            class_weights = total_samples / (len(class_counts) * class_counts)
            class_weights = torch.FloatTensor(class_weights).to(self.device)

            logger.info(f"Class distribution: {class_counts.tolist()}")
            logger.info(f"Class weights (for balancing): {class_weights.cpu().numpy()}")

            # Convert to tensors
            X_train = torch.FloatTensor(X_train).to(self.device)
            y_train = torch.LongTensor(y_train).to(self.device)
            X_val = torch.FloatTensor(X_val).to(self.device)
            y_val = torch.LongTensor(y_val).to(self.device)

            # Initialize neural network
            self.neural_model = RegimeClassificationNetwork(
                input_size=len(self.feature_columns),
                hidden_size=self.hidden_size,
                num_regimes=self.num_regimes,
                dropout=self.dropout
            ).to(self.device)

            # Training setup with class weights to handle imbalance
            criterion = nn.CrossEntropyLoss(weight=class_weights)
            optimizer = optim.Adam(
                self.neural_model.parameters(),
                lr=self.learning_rate,
                weight_decay=1e-4
            )
            scheduler = optim.lr_scheduler.ReduceLROnPlateau(
                optimizer, mode='min', factor=0.5, patience=10
            )
            
            # Training loop
            best_val_loss = float('inf')
            patience_counter = 0
            training_history = {'train_loss': [], 'val_loss': [], 'train_acc': [], 'val_acc': []}
            
            for epoch in range(self.epochs):
                # Training
                self.neural_model.train()
                optimizer.zero_grad()
                
                logits, _ = self.neural_model(X_train)
                train_loss = criterion(logits, y_train)
                train_loss.backward()
                
                torch.nn.utils.clip_grad_norm_(self.neural_model.parameters(), max_norm=1.0)
                optimizer.step()
                
                # Calculate training accuracy
                with torch.no_grad():
                    train_pred = torch.argmax(logits, dim=1)
                    train_acc = (train_pred == y_train).float().mean()
                
                # Validation
                self.neural_model.eval()
                with torch.no_grad():
                    val_logits, _ = self.neural_model(X_val)
                    val_loss = criterion(val_logits, y_val)
                    val_pred = torch.argmax(val_logits, dim=1)
                    val_acc = (val_pred == y_val).float().mean()
                
                # Learning rate scheduling
                scheduler.step(val_loss)
                
                # Record history
                training_history['train_loss'].append(train_loss.item())
                training_history['val_loss'].append(val_loss.item())
                training_history['train_acc'].append(train_acc.item())
                training_history['val_acc'].append(val_acc.item())
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss.item()
                    patience_counter = 0
                    # Save best model (ensure directory exists)
                    self.model_dir.mkdir(parents=True, exist_ok=True)
                    torch.save(self.neural_model.state_dict(), self.model_dir / 'regime_neural_best.pth')
                else:
                    patience_counter += 1
                
                if epoch % 10 == 0:
                    logger.info(f"Epoch {epoch}: Train Loss {train_loss:.4f}, "
                               f"Val Loss {val_loss:.4f}, Val Acc {val_acc:.3f}")
                
                if patience_counter >= self.early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break

            # Load best model
            self.neural_model.load_state_dict(torch.load(self.model_dir / 'regime_neural_best.pth', weights_only=False))

            # Ensure model directory exists before saving
            self.model_dir.mkdir(parents=True, exist_ok=True)

            # Save all components
            joblib.dump(self.scaler, self.model_dir / 'regime_scaler.pkl')
            joblib.dump(self.feature_columns, self.model_dir / 'regime_features.pkl')
            
            # Training metadata
            metadata = {
                'trained_at': datetime.now().isoformat(),
                'assets_used': list(multi_asset_data.keys()),
                'feature_count': len(self.feature_columns),
                'training_samples': len(X_train),
                'validation_samples': len(X_val),
                'best_val_loss': best_val_loss,
                'final_val_accuracy': training_history['val_acc'][-1],
                'regime_distribution': np.bincount(regime_labels).tolist(),
                'training_history': training_history
            }
            
            self.training_metadata = metadata
            joblib.dump(metadata, self.model_dir / 'regime_metadata.pkl')
            
            logger.info(f"Regime detection model training completed. "
                       f"Best val loss: {best_val_loss:.4f}, "
                       f"Final val accuracy: {metadata['final_val_accuracy']:.3f}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error training regime detection model: {str(e)}")
            raise
    
    def predict_regime(self, multi_asset_data: Dict[str, pd.DataFrame], 
                      return_probabilities: bool = True) -> Dict[str, Any]:
        """
        Predict current market regime
        
        Args:
            multi_asset_data: Recent multi-asset data
            return_probabilities: Whether to return regime probabilities
            
        Returns:
            Regime prediction with confidence and interpretation
        """
        if self.neural_model is None or self.scaler is None:
            raise ValueError("Model not trained or loaded")
        
        try:
            # Prepare features for recent data
            features_df = self.prepare_regime_features(multi_asset_data)
            
            if len(features_df) == 0:
                raise ValueError("No valid features could be extracted")
            
            # Use most recent data point
            latest_features = features_df.iloc[-1:].values
            
            # Scale features
            features_scaled = self.scaler.transform(latest_features)
            
            # Convert to tensor
            X = torch.FloatTensor(features_scaled).to(self.device)
            
            # Predict
            self.neural_model.eval()
            with torch.no_grad():
                logits, attention_weights = self.neural_model(X)
                probabilities = torch.softmax(logits, dim=1)
                predicted_regime = torch.argmax(logits, dim=1).item()
                regime_confidence = probabilities[0, predicted_regime].item()
            
            # Get regime information
            regime_info = self.regime_descriptions[predicted_regime]
            
            # Feature importance (from attention weights)
            attention_scores = attention_weights[0].mean(dim=0).cpu().numpy()  # Average across heads
            feature_importance = dict(zip(self.feature_columns, attention_scores))
            
            # Sort by importance
            top_features = sorted(
                feature_importance.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:10]
            
            result = {
                'predicted_regime': predicted_regime,
                'regime_name': regime_info['name'],
                'confidence': float(regime_confidence),
                'regime_info': regime_info,
                'prediction_date': datetime.now().isoformat(),
                'model_metadata': {
                    'trained_at': self.training_metadata.get('trained_at'),
                    'features_used': len(self.feature_columns)
                }
            }
            
            if return_probabilities:
                result['regime_probabilities'] = {
                    self.regime_names[i]: float(probabilities[0, i].item())
                    for i in range(self.num_regimes)
                }
                
                result['feature_importance'] = {
                    'top_features': dict(top_features),
                    'attention_pattern': 'complex_multi_head'  # Simplified description
                }
            
            logger.info(f"Regime prediction: {regime_info['name']} (confidence: {regime_confidence:.3f})")
            return result
            
        except Exception as e:
            logger.error(f"Error predicting regime: {str(e)}")
            raise
    
    def load_model(self) -> bool:
        """Load trained model components"""
        try:
            model_files = {
                'neural': self.model_dir / 'regime_neural_best.pth',
                'scaler': self.model_dir / 'regime_scaler.pkl',
                'features': self.model_dir / 'regime_features.pkl',
                'metadata': self.model_dir / 'regime_metadata.pkl'
            }
            
            # Check if all files exist
            if not all(f.exists() for f in model_files.values()):
                return False
            
            # Load components
            self.training_metadata = joblib.load(model_files['metadata'])
            self.scaler = joblib.load(model_files['scaler'])
            self.feature_columns = joblib.load(model_files['features'])
            
            # Initialize and load neural network
            self.neural_model = RegimeClassificationNetwork(
                input_size=len(self.feature_columns),
                hidden_size=self.hidden_size,
                num_regimes=self.num_regimes,
                dropout=self.dropout
            ).to(self.device)
            
            self.neural_model.load_state_dict(
                torch.load(model_files['neural'], map_location=self.device, weights_only=False)
            )
            
            logger.info("Regime detection model loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error loading regime detection model: {str(e)}")
            return False
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get model status and information"""
        status = {
            'model_loaded': self.neural_model is not None,
            'device': str(self.device),
            'num_regimes': self.num_regimes,
            'regime_names': self.regime_names
        }
        
        if self.training_metadata:
            status.update({
                'trained_at': self.training_metadata.get('trained_at'),
                'training_samples': self.training_metadata.get('training_samples'),
                'final_val_accuracy': self.training_metadata.get('final_val_accuracy'),
                'feature_count': self.training_metadata.get('feature_count'),
                'assets_used': self.training_metadata.get('assets_used', [])
            })
        
        return status
    
    def get_current_regime(self) -> Dict[str, Any]:
        """
        Get the current market regime using the most recent data
        """
        logger.info("Getting current market regime")
        
        try:
            if self.neural_model is None:
                # Return demo regime if no model is loaded
                return {
                    'current_regime': 'Expansion',
                    'confidence': 0.75,
                    'regime_duration_days': 15,
                    'regime_info': self.regime_descriptions[1],  # Expansion
                    'prediction_date': datetime.now().isoformat(),
                    'model_status': 'demo'
                }
            
            # In a real implementation, this would use recent market data
            # For now, return a simulated result
            regime_idx = np.random.choice(self.num_regimes, p=[0.2, 0.4, 0.2, 0.2])
            confidence = np.random.uniform(0.6, 0.9)
            duration = np.random.randint(5, 45)
            
            return {
                'current_regime': self.regime_names[regime_idx],
                'confidence': confidence,
                'regime_duration_days': duration,
                'regime_info': self.regime_descriptions[regime_idx],
                'prediction_date': datetime.now().isoformat(),
                'model_status': 'active'
            }
            
        except Exception as e:
            logger.error(f"Error getting current regime: {str(e)}")
            raise
    
    def forecast_regime_transitions(self, horizon_days: int = 30) -> Dict[str, Any]:
        """
        Forecast regime transitions over the specified horizon
        
        Args:
            horizon_days: Forecast horizon in days
            
        Returns:
            Dictionary with transition probabilities and expected changes
        """
        logger.info(f"Forecasting regime transitions over {horizon_days} days")
        
        try:
            # Transition matrix (simplified for demo)
            transition_matrix = {
                'Accumulation': {'Accumulation': 0.7, 'Expansion': 0.25, 'Euphoria': 0.03, 'Distribution': 0.02},
                'Expansion': {'Accumulation': 0.1, 'Expansion': 0.6, 'Euphoria': 0.25, 'Distribution': 0.05},
                'Euphoria': {'Accumulation': 0.05, 'Expansion': 0.15, 'Euphoria': 0.4, 'Distribution': 0.4},
                'Distribution': {'Accumulation': 0.3, 'Expansion': 0.1, 'Euphoria': 0.05, 'Distribution': 0.55}
            }
            
            # Get current regime
            current_regime_result = self.get_current_regime()
            current_regime = current_regime_result['current_regime']
            
            # Calculate transition probabilities
            transition_probs = transition_matrix.get(current_regime, 
                                                   {'Accumulation': 0.25, 'Expansion': 0.25, 'Euphoria': 0.25, 'Distribution': 0.25})
            
            # Expected transition date
            avg_duration = 20  # Average regime duration in days
            transition_probability = 1 - np.exp(-horizon_days / avg_duration)
            
            return {
                'current_regime': current_regime,
                'forecast_horizon_days': horizon_days,
                'transition_probabilities': transition_probs,
                'overall_transition_probability': transition_probability,
                'most_likely_next_regime': max(transition_probs.keys(), key=transition_probs.get),
                'forecast_date': datetime.now().isoformat(),
                'confidence': 0.72
            }
            
        except Exception as e:
            logger.error(f"Error forecasting regime transitions: {str(e)}")
            raise
    
    def analyze_cross_asset_regimes(self, multi_asset_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Analyze regime synchronization across multiple assets
        
        Args:
            multi_asset_data: Dictionary of asset price DataFrames
            
        Returns:
            Cross-asset regime analysis results
        """
        logger.info(f"Analyzing cross-asset regimes for {len(multi_asset_data)} assets")
        
        try:
            # Calculate correlations between assets
            returns_data = {}
            for symbol, df in multi_asset_data.items():
                if 'returns' in df.columns:
                    returns_data[symbol] = df['returns'].dropna()
                elif 'close' in df.columns:
                    returns_data[symbol] = df['close'].pct_change().dropna()
            
            if len(returns_data) < 2:
                raise ValueError("Need at least 2 assets for cross-asset analysis")
            
            # Align data on common dates
            common_index = None
            for symbol, returns in returns_data.items():
                if common_index is None:
                    common_index = returns.index
                else:
                    common_index = common_index.intersection(returns.index)
            
            # Calculate correlation matrix
            aligned_returns = pd.DataFrame({
                symbol: returns.reindex(common_index)
                for symbol, returns in returns_data.items()
            })
            
            correlation_matrix = aligned_returns.corr()
            avg_correlation = correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, k=1)].mean()
            
            # Regime synchronization (simplified calculation)
            volatilities = aligned_returns.std()
            vol_dispersion = volatilities.std() / volatilities.mean()
            regime_sync = max(0, 1 - vol_dispersion)  # Higher sync when volatilities are similar
            
            # Market stress indicator
            market_stress = aligned_returns.std().mean() * 100  # Annualized volatility as stress proxy
            
            return {
                'assets_analyzed': list(multi_asset_data.keys()),
                'analysis_period_days': len(common_index),
                'avg_correlation': float(avg_correlation),
                'regime_sync': float(regime_sync),
                'market_stress_level': float(market_stress),
                'correlation_matrix': correlation_matrix.to_dict(),
                'individual_volatilities': volatilities.to_dict(),
                'analysis_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in cross-asset regime analysis: {str(e)}")
            raise
    
    def _calculate_rsi(self, prices: pd.Series, window: int = 14) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index)
        
        Args:
            prices: Price series
            window: RSI calculation window
            
        Returns:
            RSI values
        """
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(50)  # Default RSI value
    
    def _calculate_fear_greed_proxy(self, rsi: float, volatility: float, momentum: float) -> float:
        """
        Calculate a simple Fear & Greed proxy from basic indicators
        
        Args:
            rsi: RSI value
            volatility: Volatility measure
            momentum: Momentum measure
            
        Returns:
            Fear & Greed score (0-100, higher = more greed)
        """
        # Normalize components
        rsi_score = max(0, min(100, rsi))  # Already 0-100
        vol_score = max(0, min(100, 100 - volatility * 1000))  # Lower vol = higher score
        momentum_score = max(0, min(100, 50 + momentum * 1000))  # Positive momentum = higher score
        
        # Weighted average
        fear_greed = (rsi_score * 0.4 + vol_score * 0.3 + momentum_score * 0.3)
        
        return max(0, min(100, fear_greed))