"""
Correlation Forecaster using Transformer architecture
Advanced multi-asset correlation prediction for portfolio optimization
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
from datetime import datetime, timedelta
from pathlib import Path
import joblib
import json
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class MultiAssetTransformer(nn.Module):
    """
    Transformer architecture for multi-asset correlation forecasting
    Uses self-attention to capture complex temporal relationships
    """
    
    def __init__(self, 
                 n_assets: int,
                 d_model: int = 256,
                 n_heads: int = 8,
                 n_layers: int = 6,
                 d_ff: int = 1024,
                 dropout: float = 0.1,
                 sequence_length: int = 60):
        super(MultiAssetTransformer, self).__init__()
        
        self.n_assets = n_assets
        self.d_model = d_model
        self.sequence_length = sequence_length
        
        # Input embedding for multi-asset features
        self.input_projection = nn.Linear(n_assets * 4, d_model)  # 4 features per asset (OHLC returns)
        
        # Positional encoding
        self.positional_encoding = nn.Parameter(
            torch.randn(sequence_length, d_model) * 0.02
        )
        
        # Transformer encoder layers
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_ff,
            dropout=dropout,
            activation='gelu',
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        
        # Asset-specific attention for correlation matrix construction
        self.asset_attention = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=n_heads,
            dropout=dropout,
            batch_first=True
        )
        
        # Output layers for correlation prediction
        n_correlations = n_assets * (n_assets - 1) // 2  # Upper triangular matrix
        self.correlation_head = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, n_correlations),
            nn.Tanh()  # Correlations are bounded [-1, 1]
        )
        
        # Volatility prediction head (auxiliary task)
        self.volatility_head = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, d_model // 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 4, n_assets),
            nn.Softplus()  # Volatility is positive
        )
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize transformer weights"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.LayerNorm):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)
    
    def forward(self, x: torch.Tensor, return_attention: bool = False):
        """
        Forward pass
        
        Args:
            x: Input tensor of shape (batch_size, sequence_length, n_assets * 4)
            return_attention: Whether to return attention weights
            
        Returns:
            Dictionary with correlation and volatility predictions
        """
        batch_size, seq_len, _ = x.shape
        
        # Input projection
        x = self.input_projection(x)
        
        # Add positional encoding
        x = x + self.positional_encoding[:seq_len].unsqueeze(0)
        
        # Transformer encoding
        encoded = self.transformer_encoder(x)
        
        # Asset-specific attention pooling
        pooled, attention_weights = self.asset_attention(
            encoded, encoded, encoded
        )
        
        # Global average pooling for final representation
        pooled = pooled.mean(dim=1)  # (batch_size, d_model)
        
        # Predict correlations and volatilities
        correlations = self.correlation_head(pooled)
        volatilities = self.volatility_head(pooled)
        
        output = {
            'correlations': correlations,
            'volatilities': volatilities
        }
        
        if return_attention:
            output['attention_weights'] = attention_weights
        
        return output
    
    def correlations_to_matrix(self, correlations: torch.Tensor) -> torch.Tensor:
        """
        Convert correlation vector to full correlation matrix
        
        Args:
            correlations: Upper triangular correlations (batch_size, n_correlations)
            
        Returns:
            Full correlation matrices (batch_size, n_assets, n_assets)
        """
        batch_size = correlations.shape[0]
        n_assets = self.n_assets
        
        # Create correlation matrices
        corr_matrices = torch.zeros(batch_size, n_assets, n_assets, device=correlations.device)
        
        # Fill diagonal with ones
        for i in range(n_assets):
            corr_matrices[:, i, i] = 1.0
        
        # Fill upper triangular
        idx = 0
        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                corr_matrices[:, i, j] = correlations[:, idx]
                corr_matrices[:, j, i] = correlations[:, idx]  # Symmetric
                idx += 1
        
        return corr_matrices


class CorrelationForecaster:
    """
    Main class for correlation forecasting using Transformer architecture
    """
    
    def __init__(self, model_dir: str = "models/correlation_forecaster"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Model configuration
        self.config = {
            'd_model': 256,
            'n_heads': 8,
            'n_layers': 6,
            'd_ff': 1024,
            'dropout': 0.1,
            'sequence_length': 60,
            'prediction_horizons': [1, 7, 30]  # days
        }
        
        # Training configuration
        self.learning_rate = 1e-4
        self.batch_size = 32
        self.epochs = 50
        self.early_stopping_patience = 10
        
        # Data preprocessing
        self.scalers = {}
        self.asset_symbols = []
        
        # Models for different horizons
        self.models = {}
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        logger.info(f"CorrelationForecaster initialized with device: {self.device}")
    
    def prepare_multi_asset_features(self, 
                                   price_data: Dict[str, pd.DataFrame],
                                   lookback_days: int = 365) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare multi-asset feature matrices
        
        Args:
            price_data: Dictionary mapping symbols to price DataFrames
            lookback_days: Number of days to use for features
            
        Returns:
            Feature matrices, correlation targets, asset symbols
        """
        # Filter assets with sufficient data
        valid_assets = {}
        for symbol, df in price_data.items():
            if len(df) >= lookback_days + 30:  # Minimum data requirement
                valid_assets[symbol] = df
        
        if len(valid_assets) < 2:
            raise ValueError("Need at least 2 assets with sufficient data")
        
        self.asset_symbols = sorted(valid_assets.keys())
        logger.info(f"Preparing features for {len(self.asset_symbols)} assets")
        
        # Align data on common dates
        aligned_data = {}
        common_dates = None
        
        for symbol in self.asset_symbols:
            df = valid_assets[symbol].copy()
            df = df.sort_index()
            
            if common_dates is None:
                common_dates = df.index
            else:
                common_dates = common_dates.intersection(df.index)
            
            aligned_data[symbol] = df
        
        # Filter to common dates and recent period
        common_dates = common_dates.sort_values()[-lookback_days:]
        
        # Calculate features for each asset
        feature_matrices = []
        returns_data = {}
        
        for symbol in self.asset_symbols:
            df = aligned_data[symbol].loc[common_dates]
            
            # Calculate returns and volatility features
            returns = df['close'].pct_change()
            
            features = pd.DataFrame(index=df.index)
            features['returns'] = returns
            features['log_returns'] = np.log(1 + returns).replace([np.inf, -np.inf], 0)
            features['volatility'] = returns.rolling(window=20).std()
            features['momentum'] = df['close'].pct_change(5)
            
            features = features.fillna(0)
            feature_matrices.append(features.values)
            returns_data[symbol] = returns.fillna(0)
        
        # Stack features: (n_samples, n_assets * n_features)
        features_3d = np.stack(feature_matrices, axis=2)  # (n_samples, n_features, n_assets)
        features_2d = features_3d.reshape(features_3d.shape[0], -1)  # Flatten
        
        # Calculate rolling correlation matrices as targets
        returns_df = pd.DataFrame(returns_data)
        correlation_targets = []
        
        correlation_window = 30
        for i in range(correlation_window, len(returns_df)):
            window_returns = returns_df.iloc[i-correlation_window:i]
            corr_matrix = window_returns.corr().fillna(0)
            
            # Extract upper triangular correlations
            n_assets = len(self.asset_symbols)
            corr_vector = []
            for j in range(n_assets):
                for k in range(j + 1, n_assets):
                    corr_vector.append(corr_matrix.iloc[j, k])
            
            correlation_targets.append(corr_vector)
        
        # Align features with correlation targets
        features_aligned = features_2d[correlation_window:]
        correlation_targets = np.array(correlation_targets)
        
        logger.info(f"Features shape: {features_aligned.shape}")
        logger.info(f"Targets shape: {correlation_targets.shape}")
        
        return features_aligned, correlation_targets, self.asset_symbols
    
    def create_sequences(self, features: np.ndarray, targets: np.ndarray, 
                        horizon: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sequential data for transformer training
        
        Args:
            features: Feature matrix
            targets: Target correlations
            horizon: Prediction horizon in days
            
        Returns:
            Sequential features and targets
        """
        sequence_length = self.config['sequence_length']
        
        X_sequences = []
        y_sequences = []
        
        for i in range(sequence_length, len(features) - horizon):
            # Input sequence
            X_seq = features[i-sequence_length:i]
            # Target at horizon
            y_seq = targets[i + horizon - 1]
            
            X_sequences.append(X_seq)
            y_sequences.append(y_seq)
        
        return np.array(X_sequences), np.array(y_sequences)
    
    def train_model(self, price_data: Dict[str, pd.DataFrame], 
                   validation_split: float = 0.2) -> Dict[str, Any]:
        """
        Train correlation forecasting models for different horizons
        
        Args:
            price_data: Multi-asset price data
            validation_split: Fraction of data for validation
            
        Returns:
            Training metadata
        """
        logger.info("Starting correlation forecaster training")
        
        # Prepare features
        features, targets, asset_symbols = self.prepare_multi_asset_features(price_data)
        
        # Scale features
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features.reshape(-1, features.shape[-1])).reshape(features.shape)
        self.scalers['features'] = scaler
        
        # Save asset configuration
        self.config['n_assets'] = len(asset_symbols)
        self.config['asset_symbols'] = asset_symbols
        
        training_results = {}
        
        # Train models for different horizons
        for horizon in self.config['prediction_horizons']:
            logger.info(f"Training model for {horizon}-day horizon")
            
            # Create sequences
            X_seq, y_seq = self.create_sequences(features_scaled, targets, horizon)
            
            if len(X_seq) < 100:  # Minimum training samples
                logger.warning(f"Insufficient data for {horizon}-day horizon: {len(X_seq)} samples")
                continue
            
            # Split data
            split_idx = int(len(X_seq) * (1 - validation_split))
            X_train, X_val = X_seq[:split_idx], X_seq[split_idx:]
            y_train, y_val = y_seq[:split_idx], y_seq[split_idx:]
            
            # Initialize model
            model = MultiAssetTransformer(
                n_assets=self.config['n_assets'],
                d_model=self.config['d_model'],
                n_heads=self.config['n_heads'],
                n_layers=self.config['n_layers'],
                d_ff=self.config['d_ff'],
                dropout=self.config['dropout'],
                sequence_length=self.config['sequence_length']
            ).to(self.device)
            
            # Training setup
            optimizer = optim.AdamW(model.parameters(), lr=self.learning_rate, weight_decay=1e-5)
            scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
            
            # Loss function combining correlation and volatility prediction
            def correlation_loss(pred_corr, true_corr, pred_vol=None, true_vol=None):
                corr_loss = nn.MSELoss()(pred_corr, true_corr)
                
                # Add volatility loss if available
                if pred_vol is not None and true_vol is not None:
                    vol_loss = nn.MSELoss()(pred_vol, true_vol)
                    return corr_loss + 0.1 * vol_loss
                
                return corr_loss
            
            # Training loop
            best_val_loss = float('inf')
            patience_counter = 0
            train_losses = []
            val_losses = []
            
            for epoch in range(self.epochs):
                model.train()
                train_loss = 0
                n_batches = 0
                
                # Training batches
                for i in range(0, len(X_train), self.batch_size):
                    batch_X = torch.FloatTensor(X_train[i:i+self.batch_size]).to(self.device)
                    batch_y = torch.FloatTensor(y_train[i:i+self.batch_size]).to(self.device)
                    
                    optimizer.zero_grad()
                    
                    outputs = model(batch_X)
                    loss = correlation_loss(outputs['correlations'], batch_y)
                    
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    optimizer.step()
                    
                    train_loss += loss.item()
                    n_batches += 1
                
                avg_train_loss = train_loss / n_batches
                
                # Validation
                model.eval()
                val_loss = 0
                n_val_batches = 0
                
                with torch.no_grad():
                    for i in range(0, len(X_val), self.batch_size):
                        batch_X = torch.FloatTensor(X_val[i:i+self.batch_size]).to(self.device)
                        batch_y = torch.FloatTensor(y_val[i:i+self.batch_size]).to(self.device)
                        
                        outputs = model(batch_X)
                        loss = correlation_loss(outputs['correlations'], batch_y)
                        
                        val_loss += loss.item()
                        n_val_batches += 1
                
                avg_val_loss = val_loss / n_val_batches
                scheduler.step(avg_val_loss)
                
                train_losses.append(avg_train_loss)
                val_losses.append(avg_val_loss)
                
                # Early stopping
                if avg_val_loss < best_val_loss:
                    best_val_loss = avg_val_loss
                    patience_counter = 0
                    
                    # Save best model
                    torch.save({
                        'model_state_dict': model.state_dict(),
                        'config': self.config,
                        'training_metadata': {
                            'horizon': horizon,
                            'train_samples': len(X_train),
                            'val_samples': len(X_val),
                            'best_val_loss': best_val_loss,
                            'epoch': epoch
                        }
                    }, self.model_dir / f"correlation_model_{horizon}d.pth")
                    
                else:
                    patience_counter += 1
                
                if epoch % 10 == 0:
                    logger.info(f"Epoch {epoch}, Train Loss: {avg_train_loss:.6f}, "
                              f"Val Loss: {avg_val_loss:.6f}")
                
                if patience_counter >= self.early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break
            
            # Store model and results
            self.models[horizon] = model
            training_results[horizon] = {
                'train_samples': len(X_train),
                'val_samples': len(X_val),
                'best_val_loss': best_val_loss,
                'train_losses': train_losses,
                'val_losses': val_losses
            }
            
            logger.info(f"Training completed for {horizon}-day horizon. Best val loss: {best_val_loss:.6f}")
        
        # Save scalers and configuration
        joblib.dump(self.scalers, self.model_dir / "scalers.pkl")
        
        with open(self.model_dir / "config.json", 'w') as f:
            json.dump(self.config, f, indent=2)
        
        logger.info("Correlation forecaster training completed")
        return training_results
    
    def load_models(self) -> bool:
        """
        Load trained models
        
        Returns:
            Success status
        """
        try:
            # Load configuration
            config_file = self.model_dir / "config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    self.config = json.load(f)
            
            # Load scalers
            scalers_file = self.model_dir / "scalers.pkl"
            if scalers_file.exists():
                self.scalers = joblib.load(scalers_file)
            
            # Load models for each horizon
            models_loaded = 0
            for horizon in self.config['prediction_horizons']:
                model_file = self.model_dir / f"correlation_model_{horizon}d.pth"
                
                if model_file.exists():
                    checkpoint = torch.load(model_file, map_location=self.device, weights_only=False)
                    
                    model = MultiAssetTransformer(
                        n_assets=self.config['n_assets'],
                        d_model=self.config['d_model'],
                        n_heads=self.config['n_heads'],
                        n_layers=self.config['n_layers'],
                        d_ff=self.config['d_ff'],
                        dropout=self.config['dropout'],
                        sequence_length=self.config['sequence_length']
                    ).to(self.device)
                    
                    model.load_state_dict(checkpoint['model_state_dict'])
                    model.eval()
                    
                    self.models[horizon] = model
                    models_loaded += 1
                    
                    logger.info(f"Loaded {horizon}-day correlation model")
            
            if models_loaded > 0:
                self.asset_symbols = self.config.get('asset_symbols', [])
                logger.info(f"Loaded {models_loaded} correlation models")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error loading correlation models: {str(e)}")
            return False
    
    def predict_correlations(self, price_data: Dict[str, pd.DataFrame], 
                           horizons: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Predict future correlations
        
        Args:
            price_data: Recent multi-asset price data
            horizons: Prediction horizons (uses all trained if None)
            
        Returns:
            Correlation predictions for each horizon
        """
        if not self.models:
            if not self.load_models():
                raise RuntimeError("No trained correlation models available")
        
        if horizons is None:
            horizons = list(self.models.keys())
        
        logger.info(f"Predicting correlations for horizons: {horizons}")
        
        # Prepare recent features
        try:
            features, _, _ = self.prepare_multi_asset_features(
                price_data, lookback_days=self.config['sequence_length'] + 60
            )
            
            # Scale features
            if 'features' in self.scalers:
                features_scaled = self.scalers['features'].transform(
                    features.reshape(-1, features.shape[-1])
                ).reshape(features.shape)
            else:
                features_scaled = features
            
            # Use most recent sequence
            recent_sequence = features_scaled[-self.config['sequence_length']:]
            input_tensor = torch.FloatTensor(recent_sequence).unsqueeze(0).to(self.device)
            
        except Exception as e:
            logger.error(f"Error preparing prediction data: {str(e)}")
            return {'error': str(e)}
        
        predictions = {}
        
        # Generate predictions for each horizon
        for horizon in horizons:
            if horizon not in self.models:
                continue
            
            model = self.models[horizon]
            
            with torch.no_grad():
                outputs = model(input_tensor, return_attention=True)
                
                # Extract predictions
                corr_predictions = outputs['correlations'].cpu().numpy()[0]
                vol_predictions = outputs['volatilities'].cpu().numpy()[0]
                
                # Convert to correlation matrix
                corr_matrix_tensor = model.correlations_to_matrix(
                    torch.FloatTensor(corr_predictions).unsqueeze(0)
                )
                corr_matrix = corr_matrix_tensor.cpu().numpy()[0]
                
                # Create readable correlation matrix
                corr_df = pd.DataFrame(
                    corr_matrix,
                    index=self.asset_symbols,
                    columns=self.asset_symbols
                )
                
                predictions[f"{horizon}d"] = {
                    'correlation_matrix': corr_df.to_dict(),
                    'predicted_volatilities': dict(zip(self.asset_symbols, vol_predictions)),
                    'correlation_vector': corr_predictions.tolist(),
                    'timestamp': datetime.now().isoformat(),
                    'confidence_score': self._calculate_prediction_confidence(outputs)
                }
        
        return {
            'predictions': predictions,
            'asset_symbols': self.asset_symbols,
            'model_status': 'active',
            'last_updated': datetime.now().isoformat()
        }
    
    def _calculate_prediction_confidence(self, outputs: Dict[str, torch.Tensor]) -> float:
        """
        Calculate confidence score for predictions
        
        Args:
            outputs: Model outputs
            
        Returns:
            Confidence score [0, 1]
        """
        try:
            # Use attention entropy as a measure of confidence
            if 'attention_weights' in outputs:
                attention = outputs['attention_weights']
                # Lower entropy = higher confidence
                attention_entropy = -(attention * torch.log(attention + 1e-8)).sum(dim=-1).mean()
                confidence = 1 / (1 + attention_entropy.item())
                return min(max(confidence, 0.0), 1.0)
            
            # Fallback: use prediction magnitude
            correlations = outputs['correlations']
            magnitude = torch.abs(correlations).mean().item()
            return min(magnitude, 1.0)
            
        except Exception:
            return 0.5  # Default confidence
    
    def analyze_correlation_changes(self, 
                                  current_data: Dict[str, pd.DataFrame],
                                  lookback_days: int = 90) -> Dict[str, Any]:
        """
        Analyze recent correlation changes and patterns
        
        Args:
            current_data: Current price data
            lookback_days: Days to analyze
            
        Returns:
            Correlation analysis results
        """
        try:
            # Get recent correlation predictions
            predictions = self.predict_correlations(current_data)
            
            if 'error' in predictions:
                return predictions
            
            # Calculate historical correlations for comparison
            features, targets, symbols = self.prepare_multi_asset_features(
                current_data, lookback_days=lookback_days
            )
            
            # Get recent historical correlations
            recent_correlations = targets[-30:]  # Last 30 correlation observations
            
            analysis = {
                'correlation_trends': {},
                'volatility_clustering': {},
                'regime_changes': {},
                'risk_insights': {}
            }
            
            # Analyze correlation trends
            for i, symbol1 in enumerate(symbols):
                for j, symbol2 in enumerate(symbols):
                    if i >= j:
                        continue
                    
                    # Find correlation index
                    pair_key = f"{symbol1}_{symbol2}"
                    corr_idx = 0
                    for k in range(len(symbols)):
                        for l in range(k + 1, len(symbols)):
                            if (symbols[k] == symbol1 and symbols[l] == symbol2) or \
                               (symbols[k] == symbol2 and symbols[l] == symbol1):
                                break
                            corr_idx += 1
                    
                    # Extract correlation time series
                    if corr_idx < recent_correlations.shape[1]:
                        pair_correlations = recent_correlations[:, corr_idx]
                        
                        # Trend analysis
                        trend_slope = np.polyfit(range(len(pair_correlations)), pair_correlations, 1)[0]
                        volatility = np.std(pair_correlations)
                        
                        analysis['correlation_trends'][pair_key] = {
                            'trend_slope': float(trend_slope),
                            'volatility': float(volatility),
                            'current_level': float(pair_correlations[-1]),
                            'trend_direction': 'increasing' if trend_slope > 0.01 else 'decreasing' if trend_slope < -0.01 else 'stable'
                        }
            
            # Overall market analysis
            avg_correlations = np.mean(recent_correlations, axis=1)
            analysis['market_correlation_level'] = {
                'current': float(np.mean(avg_correlations[-5:])),
                'trend': 'increasing' if np.mean(avg_correlations[-5:]) > np.mean(avg_correlations[-15:-5]) else 'decreasing',
                'regime': 'high_correlation' if np.mean(avg_correlations[-5:]) > 0.5 else 'low_correlation'
            }
            
            # Risk insights
            analysis['risk_insights'] = {
                'diversification_benefit': 'low' if np.mean(avg_correlations[-5:]) > 0.7 else 'high',
                'market_stress_indicator': 'stressed' if np.mean(avg_correlations[-5:]) > 0.8 else 'normal',
                'portfolio_risk_level': 'elevated' if np.std(avg_correlations[-10:]) > 0.1 else 'normal'
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in correlation analysis: {str(e)}")
            return {'error': str(e)}
    
    def get_model_status(self) -> Dict[str, Any]:
        """
        Get correlation forecaster status
        
        Returns:
            Model status information
        """
        return {
            'models_loaded': len(self.models),
            'available_horizons': list(self.models.keys()),
            'asset_symbols': getattr(self, 'asset_symbols', []),
            'device': str(self.device),
            'config': self.config,
            'model_files': [str(f) for f in self.model_dir.glob("*.pth")]
        }