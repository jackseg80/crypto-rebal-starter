"""
Volatility Prediction Model using LSTM/GRU for crypto assets
Predicts volatility across multiple time horizons with confidence intervals
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import logging
import joblib
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

from ..feature_engineering import CryptoFeatureEngineer
from ..data_pipeline import MLDataPipeline

logger = logging.getLogger(__name__)

class VolatilityLSTM(nn.Module):
    """
    LSTM Neural Network for volatility prediction
    Architecture: Multi-layer LSTM + Attention + Dense layers
    """
    
    def __init__(self, input_size: int, hidden_size: int = 128, num_layers: int = 3, 
                 dropout: float = 0.2, output_horizons: int = 3):
        super(VolatilityLSTM, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_horizons = output_horizons
        
        # LSTM layers with dropout
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=False
        )
        
        # Attention mechanism
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_size,
            num_heads=8,
            dropout=dropout,
            batch_first=True
        )
        
        # Dense layers for prediction
        self.dense = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, hidden_size // 4),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 4, output_horizons * 2)  # mean + std for each horizon
        )
        
        # Initialize weights
        self.apply(self._init_weights)
    
    def _init_weights(self, m):
        """Initialize weights with Xavier uniform"""
        if isinstance(m, nn.Linear):
            torch.nn.init.xavier_uniform_(m.weight)
            m.bias.data.fill_(0.01)
        elif isinstance(m, nn.LSTM):
            for name, param in m.named_parameters():
                if 'weight_ih' in name:
                    torch.nn.init.xavier_uniform_(param.data)
                elif 'weight_hh' in name:
                    torch.nn.init.orthogonal_(param.data)
                elif 'bias' in name:
                    param.data.fill_(0)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the network
        Args:
            x: Input tensor [batch_size, sequence_length, input_size]
        Returns:
            predictions: [batch_size, output_horizons * 2] (mean + std for each horizon)
        """
        batch_size = x.size(0)
        
        # LSTM forward pass
        lstm_out, (hidden, cell) = self.lstm(x)
        
        # Attention mechanism
        attended_out, attention_weights = self.attention(
            lstm_out, lstm_out, lstm_out
        )
        
        # Use last timestep after attention
        final_hidden = attended_out[:, -1, :]
        
        # Dense layers for prediction
        predictions = self.dense(final_hidden)
        
        return predictions

class VolatilityPredictor:
    """
    Advanced Volatility Predictor for crypto assets using LSTM with attention
    Provides predictions for multiple time horizons with confidence intervals
    """
    
    def __init__(self, model_dir: str = "models/volatility"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Model hyperparameters
        self.sequence_length = 60  # 60 days lookback
        self.hidden_size = 128
        self.num_layers = 3
        self.dropout = 0.2
        self.learning_rate = 0.001
        self.batch_size = 32
        self.epochs = 100
        self.early_stopping_patience = 15
        
        # Prediction horizons (days)
        self.horizons = [1, 7, 30]  # 1 day, 1 week, 1 month
        
        # Initialize components
        self.feature_engineer = CryptoFeatureEngineer()
        self.data_pipeline = MLDataPipeline()
        
        # Model storage
        self.models = {}  # symbol -> model
        self.scalers = {}  # symbol -> scaler
        self.metadata = {}  # symbol -> training metadata
        
        # Device selection
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")
    
    def prepare_features(self, price_data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Prepare crypto-specific features for volatility prediction
        
        Args:
            price_data: DataFrame with OHLCV data
            symbol: Asset symbol
            
        Returns:
            DataFrame with engineered features
        """
        logger.info(f"Preparing features for {symbol}")
        
        # Ensure we have required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in price_data.columns for col in required_cols):
            raise ValueError(f"Missing required columns. Need: {required_cols}")
        
        features_df = price_data.copy()
        
        # Basic price features
        features_df['returns'] = features_df['close'].pct_change()
        features_df['log_returns'] = np.log(features_df['close'] / features_df['close'].shift(1))
        features_df['realized_vol'] = features_df['returns'].rolling(window=20).std() * np.sqrt(365)
        
        # Price-based features
        features_df['price_momentum_5'] = features_df['close'] / features_df['close'].shift(5) - 1
        features_df['price_momentum_20'] = features_df['close'] / features_df['close'].shift(20) - 1
        features_df['rsi'] = self._calculate_rsi(features_df['close'], window=14)
        features_df['bollinger_position'] = self._calculate_bollinger_position(features_df['close'])
        
        # Volume features
        features_df['volume_sma'] = features_df['volume'].rolling(window=20).mean()
        features_df['volume_ratio'] = features_df['volume'] / features_df['volume_sma']
        features_df['volume_momentum'] = features_df['volume'] / features_df['volume'].shift(5) - 1
        
        # Volatility features  
        features_df['vol_5'] = features_df['returns'].rolling(window=5).std() * np.sqrt(365)
        features_df['vol_20'] = features_df['returns'].rolling(window=20).std() * np.sqrt(365)
        features_df['vol_60'] = features_df['returns'].rolling(window=60).std() * np.sqrt(365)
        features_df['vol_ratio'] = features_df['vol_5'] / features_df['vol_20']
        
        # High-low spread features
        features_df['hl_ratio'] = (features_df['high'] - features_df['low']) / features_df['close']
        features_df['oc_ratio'] = (features_df['open'] - features_df['close']) / features_df['close']
        
        # Moving averages and trends
        features_df['ma_5'] = features_df['close'].rolling(window=5).mean()
        features_df['ma_20'] = features_df['close'].rolling(window=20).mean()
        features_df['ma_50'] = features_df['close'].rolling(window=50).mean()
        features_df['ma_ratio_5_20'] = features_df['ma_5'] / features_df['ma_20']
        features_df['ma_ratio_20_50'] = features_df['ma_20'] / features_df['ma_50']
        
        # Crypto-specific: Weekend effects, time-based features
        features_df['day_of_week'] = features_df.index.dayofweek
        features_df['is_weekend'] = (features_df['day_of_week'] >= 5).astype(int)
        features_df['month'] = features_df.index.month
        
        # Target variables (future volatility)
        for horizon in self.horizons:
            features_df[f'target_vol_{horizon}d'] = (
                features_df['returns'].rolling(window=horizon).std().shift(-horizon) * np.sqrt(365)
            )
        
        # Select final feature columns
        feature_columns = [
            'returns', 'log_returns', 'realized_vol',
            'price_momentum_5', 'price_momentum_20', 'rsi', 'bollinger_position',
            'volume_ratio', 'volume_momentum',
            'vol_5', 'vol_20', 'vol_60', 'vol_ratio',
            'hl_ratio', 'oc_ratio',
            'ma_ratio_5_20', 'ma_ratio_20_50',
            'is_weekend', 'day_of_week', 'month'
        ]
        
        # Add target columns
        target_columns = [f'target_vol_{h}d' for h in self.horizons]
        final_columns = feature_columns + target_columns
        
        # Filter and clean data
        result_df = features_df[final_columns].copy()
        result_df = result_df.dropna()
        
        logger.info(f"Features prepared for {symbol}: {len(result_df)} samples, {len(feature_columns)} features")
        return result_df
    
    def _calculate_rsi(self, prices: pd.Series, window: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_bollinger_position(self, prices: pd.Series, window: int = 20, num_std: float = 2) -> pd.Series:
        """Calculate position within Bollinger Bands"""
        ma = prices.rolling(window=window).mean()
        std = prices.rolling(window=window).std()
        upper_band = ma + (std * num_std)
        lower_band = ma - (std * num_std)
        position = (prices - lower_band) / (upper_band - lower_band)
        return position
    
    def create_sequences(self, features: pd.DataFrame, symbol: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sequence data for LSTM training
        
        Args:
            features: Feature DataFrame
            symbol: Asset symbol
            
        Returns:
            X: Input sequences [samples, sequence_length, features]
            y: Target sequences [samples, horizons * 2] (mean + std)
        """
        # Feature columns (excluding targets)
        feature_cols = [col for col in features.columns if not col.startswith('target_vol')]
        target_cols = [f'target_vol_{h}d' for h in self.horizons]
        
        # Normalize features
        from sklearn.preprocessing import RobustScaler
        scaler = RobustScaler()
        features_scaled = scaler.fit_transform(features[feature_cols])
        
        # Store scaler
        self.scalers[symbol] = scaler
        
        # Create sequences
        X, y = [], []
        
        for i in range(self.sequence_length, len(features_scaled)):
            # Input sequence
            X.append(features_scaled[i-self.sequence_length:i])
            
            # Target (volatility for each horizon)
            targets = []
            for target_col in target_cols:
                vol_value = features.iloc[i][target_col]
                if pd.isna(vol_value):
                    vol_value = features[target_col].median()  # Fallback
                targets.extend([vol_value, vol_value * 0.1])  # mean, std approximation
            
            y.append(targets)
        
        X = np.array(X)
        y = np.array(y)
        
        logger.info(f"Created sequences for {symbol}: X shape {X.shape}, y shape {y.shape}")
        return X, y
    
    def train_model(self, symbol: str, price_data: pd.DataFrame, 
                   validation_split: float = 0.2) -> Dict[str, Any]:
        """
        Train volatility prediction model for a specific asset
        
        Args:
            symbol: Asset symbol
            price_data: Historical price data
            validation_split: Fraction for validation
            
        Returns:
            Training results and metadata
        """
        logger.info(f"Training volatility model for {symbol}")
        
        try:
            # Prepare features
            features_df = self.prepare_features(price_data, symbol)
            if len(features_df) < self.sequence_length + 30:
                raise ValueError(f"Insufficient data for {symbol}: {len(features_df)} samples")
            
            # Create sequences
            X, y = self.create_sequences(features_df, symbol)
            
            # Train-validation split
            split_idx = int(len(X) * (1 - validation_split))
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]
            
            # Convert to tensors
            X_train = torch.FloatTensor(X_train).to(self.device)
            y_train = torch.FloatTensor(y_train).to(self.device)
            X_val = torch.FloatTensor(X_val).to(self.device)
            y_val = torch.FloatTensor(y_val).to(self.device)
            
            # Initialize model
            input_size = X.shape[2]
            model = VolatilityLSTM(
                input_size=input_size,
                hidden_size=self.hidden_size,
                num_layers=self.num_layers,
                dropout=self.dropout,
                output_horizons=len(self.horizons)
            ).to(self.device)
            
            # Loss and optimizer
            criterion = nn.MSELoss()
            optimizer = optim.Adam(model.parameters(), lr=self.learning_rate, weight_decay=1e-5)
            scheduler = optim.lr_scheduler.ReduceLROnPlateau(
                optimizer, mode='min', factor=0.5, patience=10, verbose=True
            )
            
            # Training loop
            best_val_loss = float('inf')
            patience_counter = 0
            training_history = {'train_loss': [], 'val_loss': []}
            
            for epoch in range(self.epochs):
                model.train()
                
                # Training
                optimizer.zero_grad()
                y_pred = model(X_train)
                train_loss = criterion(y_pred, y_train)
                train_loss.backward()
                
                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                
                # Validation
                model.eval()
                with torch.no_grad():
                    y_val_pred = model(X_val)
                    val_loss = criterion(y_val_pred, y_val)
                
                # Learning rate scheduling
                scheduler.step(val_loss)
                
                # Record history
                training_history['train_loss'].append(train_loss.item())
                training_history['val_loss'].append(val_loss.item())
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss.item()
                    patience_counter = 0
                    # Save best model
                    torch.save(model.state_dict(), self.model_dir / f'{symbol}_volatility_best.pth')
                else:
                    patience_counter += 1
                
                if epoch % 10 == 0:
                    logger.info(f"Epoch {epoch}: Train Loss {train_loss:.6f}, Val Loss {val_loss:.6f}")
                
                if patience_counter >= self.early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break
            
            # Load best model
            model.load_state_dict(torch.load(self.model_dir / f'{symbol}_volatility_best.pth'))
            self.models[symbol] = model
            
            # Training metadata
            metadata = {
                'symbol': symbol,
                'trained_at': datetime.now().isoformat(),
                'input_size': input_size,
                'sequence_length': self.sequence_length,
                'horizons': self.horizons,
                'train_samples': len(X_train),
                'val_samples': len(X_val),
                'best_val_loss': best_val_loss,
                'final_epoch': epoch,
                'training_history': training_history
            }
            
            self.metadata[symbol] = metadata
            
            # Save metadata
            joblib.dump(metadata, self.model_dir / f'{symbol}_metadata.pkl')
            joblib.dump(self.scalers[symbol], self.model_dir / f'{symbol}_scaler.pkl')
            
            logger.info(f"Model training completed for {symbol}. Best val loss: {best_val_loss:.6f}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error training model for {symbol}: {str(e)}")
            raise
    
    def predict_volatility(self, symbol: str, recent_data: pd.DataFrame, 
                          confidence_level: float = 0.95) -> Dict[str, Any]:
        """
        Predict volatility for multiple horizons with confidence intervals
        
        Args:
            symbol: Asset symbol
            recent_data: Recent price data for prediction
            confidence_level: Confidence level for intervals
            
        Returns:
            Prediction results with confidence intervals
        """
        if symbol not in self.models:
            raise ValueError(f"No trained model found for {symbol}")
        
        try:
            model = self.models[symbol]
            scaler = self.scalers[symbol]
            model.eval()
            
            # Prepare features
            features_df = self.prepare_features(recent_data, symbol)
            feature_cols = [col for col in features_df.columns if not col.startswith('target_vol')]
            
            # Get last sequence
            features_scaled = scaler.transform(features_df[feature_cols].iloc[-self.sequence_length:])
            X = torch.FloatTensor(features_scaled).unsqueeze(0).to(self.device)  # Add batch dimension
            
            # Predict
            with torch.no_grad():
                predictions = model(X).cpu().numpy()[0]  # Remove batch dimension
            
            # Parse predictions (mean, std for each horizon)
            results = {}
            z_score = 1.96 if confidence_level == 0.95 else 2.576 if confidence_level == 0.99 else 1.645
            
            for i, horizon in enumerate(self.horizons):
                mean_vol = predictions[i * 2]
                std_vol = max(predictions[i * 2 + 1], mean_vol * 0.05)  # Minimum std
                
                # Ensure positive volatility
                mean_vol = max(mean_vol, 0.01)
                
                # Confidence intervals
                lower_bound = max(mean_vol - z_score * std_vol, 0.01)
                upper_bound = mean_vol + z_score * std_vol
                
                results[f'{horizon}d'] = {
                    'predicted_volatility': round(mean_vol, 4),
                    'confidence_interval': {
                        'lower': round(lower_bound, 4),
                        'upper': round(upper_bound, 4),
                        'confidence_level': confidence_level
                    },
                    'uncertainty': round(std_vol, 4),
                    'horizon_days': horizon
                }
            
            # Add current realized volatility for comparison
            current_vol = recent_data['close'].pct_change().rolling(window=20).std().iloc[-1] * np.sqrt(365)
            
            prediction_result = {
                'symbol': symbol,
                'prediction_date': datetime.now().isoformat(),
                'current_realized_volatility': round(current_vol, 4),
                'predictions': results,
                'model_metadata': {
                    'trained_at': self.metadata[symbol]['trained_at'],
                    'sequence_length': self.sequence_length,
                    'confidence_level': confidence_level
                }
            }
            
            logger.info(f"Volatility prediction completed for {symbol}")
            return prediction_result
            
        except Exception as e:
            logger.error(f"Error predicting volatility for {symbol}: {str(e)}")
            raise
    
    def load_model(self, symbol: str) -> bool:
        """Load trained model and metadata"""
        try:
            model_path = self.model_dir / f'{symbol}_volatility_best.pth'
            metadata_path = self.model_dir / f'{symbol}_metadata.pkl'
            scaler_path = self.model_dir / f'{symbol}_scaler.pkl'
            
            if not all(p.exists() for p in [model_path, metadata_path, scaler_path]):
                return False
            
            # Load metadata and scaler
            metadata = joblib.load(metadata_path)
            scaler = joblib.load(scaler_path)
            
            # Initialize and load model
            model = VolatilityLSTM(
                input_size=metadata['input_size'],
                hidden_size=self.hidden_size,
                num_layers=self.num_layers,
                dropout=self.dropout,
                output_horizons=len(self.horizons)
            ).to(self.device)
            
            model.load_state_dict(torch.load(model_path, map_location=self.device))
            
            # Store in memory
            self.models[symbol] = model
            self.metadata[symbol] = metadata
            self.scalers[symbol] = scaler
            
            logger.info(f"Model loaded for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model for {symbol}: {str(e)}")
            return False
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all loaded models"""
        status = {
            'device': str(self.device),
            'models_loaded': len(self.models),
            'symbols': list(self.models.keys()),
            'models_detail': {}
        }
        
        for symbol, metadata in self.metadata.items():
            status['models_detail'][symbol] = {
                'trained_at': metadata['trained_at'],
                'train_samples': metadata['train_samples'],
                'best_val_loss': metadata['best_val_loss'],
                'horizons': metadata['horizons']
            }
        
        return status