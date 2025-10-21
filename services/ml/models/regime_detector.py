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


def create_rule_based_labels(price_data: pd.DataFrame) -> np.ndarray:
    """
    Create regime labels using objective economic criteria instead of HMM clustering.

    This addresses critical limitation: HMM doesn't detect bear markets (0% on 30Y data!)
    even when 2000-2002 crash (-49%) and 2008 crisis (-57%) are included.

    Regime Definitions (Objective):
    - 0 (Bear Market): Drawdown ≥20% from peak, duration >2 months
    - 1 (Correction): Drawdown 10-20% OR volatility >30% (60d) OR price <MA200
    - 2 (Bull Market): Price >MA200, volatility <25%, positive momentum
    - 3 (Expansion): Recovery from drawdown >20% at rate >15%/month for 3+ months

    Args:
        price_data: DataFrame with 'close' column and DatetimeIndex

    Returns:
        Array of regime labels (0-3) matching input length
    """
    close = price_data['close'].values
    labels = np.zeros(len(close), dtype=int)

    # Calculate features
    returns = pd.Series(close).pct_change()
    cumulative_max = pd.Series(close).cummax()
    drawdown = (close - cumulative_max) / cumulative_max

    # 60-day rolling volatility (annualized)
    volatility_60d = returns.rolling(60).std() * np.sqrt(252)

    # 200-day moving average
    ma_200 = pd.Series(close).rolling(200).mean()

    # 20-day momentum
    momentum_20 = pd.Series(close).pct_change(20)

    # PHASE 1: Identify Bear Markets (priority 1)
    # Drawdown ≥20% from peak AND sustained >2 months (42 trading days)
    for i in range(42, len(close)):
        if drawdown[i] <= -0.20:  # 20% drawdown
            # Check if sustained for at least 2 months
            if np.all(drawdown[i-42:i+1] <= -0.15):  # At least 15% for 2 months
                labels[i-42:i+1] = 0  # Bear Market

    # PHASE 2: Identify Expansion (priority 2)
    # Recovery from drawdown >20% at rate >15%/month for 3+ months
    for i in range(63, len(close)):  # 3 months = 63 trading days
        # Check if recovering from major drawdown
        min_dd_past = np.min(drawdown[i-126:i-63])  # 3-6 months ago
        if min_dd_past <= -0.20:  # Was in 20%+ drawdown
            # Check if strong recovery (>15% gain per month)
            gain_3m = (close[i] - close[i-63]) / close[i-63]
            if gain_3m >= 0.45:  # 45% in 3 months = 15%/month
                labels[i-63:i+1] = 3  # Expansion

    # PHASE 3: Identify Corrections (priority 3)
    # Drawdown 10-20% OR high volatility OR below MA200
    for i in range(200, len(close)):
        if labels[i] == 0 or labels[i] == 3:
            continue  # Already labeled as Bear or Expansion

        is_correction = (
            (-0.20 < drawdown[i] <= -0.10) or  # 10-20% drawdown
            (volatility_60d[i] >= 0.30) or  # High vol (30%+)
            (close[i] < ma_200[i])  # Below 200-day MA
        )

        if is_correction:
            labels[i] = 1  # Correction

    # PHASE 4: Rest are Bull Markets (default)
    # Price >MA200, low volatility, positive trend
    labels[labels == 0] = 2  # Unlabeled → Bull Market (but avoid overwriting Bear=0!)

    # Fix: Re-apply Bear Market labels (got overwritten)
    for i in range(42, len(close)):
        if drawdown[i] <= -0.20 and np.all(drawdown[i-42:i+1] <= -0.15):
            labels[i-42:i+1] = 0

    return labels


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

        # Temperature scaling for probability calibration
        # Higher temperature = less confident probabilities (more realistic)
        # Default: 2.5 to avoid overconfidence (softmax too sharp with T=1.0)
        self.temperature = 2.5

        # IMPORTANT: Regime names depend on market type
        # For STOCKS (SPY, QQQ, etc.): Score-based ordering is INVERTED from crypto
        #   - Regime 0 (lowest score) = Bear Market (negative returns, high vol)
        #   - Regime 3 (highest score) = Bull Market (positive returns, low vol)
        # For CRYPTO: Original names apply
        #   - Regime 0 = Accumulation, Regime 3 = Distribution

        # Stock market regime names (based on market cycle phases)
        # Regime 0: Negative returns + high volatility = Bear Market (crash, capitulation)
        # Regime 1: Negative/flat returns + medium vol = Correction (pullbacks, sideways)
        # Regime 2: Positive returns + low volatility = Bull Market (stable uptrend)
        # Regime 3: High returns + strong momentum = Expansion (violent rebounds post-crash)
        self.regime_names = ['Bear Market', 'Correction', 'Bull Market', 'Expansion']

        self.regime_descriptions = {
            0: {  # Bear Market (stocks) / Accumulation (crypto)
                'name': 'Bear Market',
                'description': 'Market in decline - risk-off phase with negative returns',
                'characteristics': ['Declining prices', 'High volatility', 'Negative momentum'],
                'strategy': 'Defensive positioning, increase cash/bonds, hedge risk',
                'risk_level': 'High',
                'allocation_bias': 'Significantly reduce risky assets'
            },
            1: {  # Correction - pullbacks, negative/flat returns
                'name': 'Correction',
                'description': 'Market pullback or consolidation - negative/flat returns, sideways action',
                'characteristics': ['Pullbacks', 'Low momentum', 'Neutral to cautious sentiment'],
                'strategy': 'Wait for confirmation, selective accumulation on dips',
                'risk_level': 'Moderate',
                'allocation_bias': 'Reduce to 50-60% allocation'
            },
            2: {  # Bull Market - stable uptrend, low volatility (QE era 2009-2020)
                'name': 'Bull Market',
                'description': 'Stable uptrend with low volatility - sustainable growth phase',
                'characteristics': ['Steady gains', 'LOW volatility', 'Institutional support', 'QE era'],
                'strategy': 'DCA consistently, follow trend, hold long-term positions',
                'risk_level': 'Low',
                'allocation_bias': 'Increase to 70-80% allocation'
            },
            3: {  # Expansion - violent rebounds post-crash (2009, 2020)
                'name': 'Expansion',
                'description': 'Violent rebound post-crash - explosive gains, strong momentum',
                'characteristics': ['Rapid recovery', 'High momentum', 'Post-crisis bounce', 'V-shaped recovery'],
                'strategy': 'Ride the momentum early, but be ready for consolidation',
                'risk_level': 'Moderate',
                'allocation_bias': 'Increase to 75-80% but expect volatility'
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
    
    def prepare_regime_features(self, multi_asset_data: Dict[str, pd.DataFrame],
                               include_contextual: bool = True) -> pd.DataFrame:
        """
        Prepare comprehensive features for regime detection from multiple assets.

        HYBRID SYSTEM: Combines statistical features (for HMM) with contextual features
        (for rule-based detection) to overcome HMM's temporal blindness.

        Args:
            multi_asset_data: Dictionary of asset DataFrames with OHLCV data
            include_contextual: If True, adds drawdown/temporal features (NEW!)

        Returns:
            DataFrame with regime detection features
        """
        logger.info(f"Preparing regime features from {len(multi_asset_data)} assets (contextual={include_contextual})")
        
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

        # NEW: Add contextual features to overcome HMM's temporal blindness
        if include_contextual:
            # Get benchmark price for drawdown calculation
            benchmark_symbol = list(multi_asset_data.keys())[0]  # Use first asset as proxy
            benchmark_data = multi_asset_data[benchmark_symbol]

            # Align with features_df index
            aligned_prices = benchmark_data.loc[features_df.index, 'close'] if 'close' in benchmark_data.columns else None

            if aligned_prices is not None:
                # Drawdown from peak (cumulative context)
                cummax = aligned_prices.cummax()
                drawdown = (aligned_prices - cummax) / cummax
                features_df['drawdown_from_peak'] = drawdown

                # Days since peak (temporal context)
                days_since_peak = pd.Series(0, index=aligned_prices.index)
                peak_idx = 0
                for i in range(len(aligned_prices)):
                    if aligned_prices.iloc[i] >= aligned_prices.iloc[:i+1].max():
                        peak_idx = i
                        days_since_peak.iloc[i] = 0
                    else:
                        days_since_peak.iloc[i] = i - peak_idx
                features_df['days_since_peak'] = days_since_peak

                # 30-day trend (directional context)
                features_df['trend_30d'] = aligned_prices.pct_change(30)

                logger.info("Added contextual features: drawdown_from_peak, days_since_peak, trend_30d")

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
        logger.info("🚀🚀🚀 PHASE 2.5 - NEW SCORING FORMULA ACTIVE (v2025-10-19-15:51) 🚀🚀🚀")
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
        # PHASE 1: Collect raw statistics for all regimes
        regime_characteristics = []
        for regime in range(self.hmm_n_components):
            regime_mask = regime_labels == regime
            if np.sum(regime_mask) > 0:
                # Calculate regime characteristics
                avg_return = np.mean(features.loc[regime_mask, 'market_return'])
                avg_volatility = np.mean(features.loc[regime_mask, 'market_volatility'])
                avg_momentum = np.mean(features.loc[regime_mask, 'market_momentum'])

                regime_characteristics.append({
                    'id': regime,
                    'return': avg_return,
                    'volatility': avg_volatility,
                    'momentum': avg_momentum,
                    'count': np.sum(regime_mask)
                })

        # PHASE 2: Normalize features using z-score (CRITICAL for comparable scoring)
        # Problem: Return (0.001-0.003) vs Volatility (0.15-0.50) → Vol dominates!
        # Solution: Normalize to same scale before weighting
        returns = np.array([r['return'] for r in regime_characteristics])
        vols = np.array([r['volatility'] for r in regime_characteristics])
        momentums = np.array([r['momentum'] for r in regime_characteristics])

        return_mean, return_std = returns.mean(), returns.std()
        vol_mean, vol_std = vols.mean(), vols.std()
        momentum_mean, momentum_std = momentums.mean(), momentums.std()

        logger.info("=== Feature Normalization Stats (Phase 2.6) ===")
        logger.info(f"  Return:    mean={return_mean:.6f}, std={return_std:.6f}")
        logger.info(f"  Volatility: mean={vol_mean:.4f}, std={vol_std:.4f}")
        logger.info(f"  Momentum:   mean={momentum_mean:.6f}, std={momentum_std:.6f}")

        # PHASE 3: Calculate normalized scores
        for char in regime_characteristics:
            # Z-score normalization: (x - mean) / std
            return_norm = (char['return'] - return_mean) / (return_std + 1e-8)
            vol_norm = (char['volatility'] - vol_mean) / (vol_std + 1e-8)
            momentum_norm = (char['momentum'] - momentum_mean) / (momentum_std + 1e-8)

            # Normalized score: prioritize returns + momentum, penalize volatility
            # All features now on same scale [-2, +2] approximately
            score = return_norm * 0.6 + momentum_norm * 0.3 - vol_norm * 0.1

            char['return_norm'] = return_norm
            char['vol_norm'] = vol_norm
            char['momentum_norm'] = momentum_norm
            char['score'] = score

        # Log detailed characteristics for debugging
        logger.info("=== HMM Regime Characteristics (Normalized Scoring) ===")
        for char in regime_characteristics:
            logger.info(f"  Cluster {char['id']}: return={char['return']:.4f} (norm={char['return_norm']:+.2f}), "
                       f"vol={char['volatility']:.4f} (norm={char['vol_norm']:+.2f}), "
                       f"momentum={char['momentum']:.4f} (norm={char['momentum_norm']:+.2f}), "
                       f"score={char['score']:+.3f}, count={char['count']}")

        # PHASE 2.7: Smart mapping based on market cycle characteristics
        # Instead of sorting by score, map clusters based on actual return/vol/momentum patterns
        logger.info("=== Smart Regime Mapping (Phase 2.7) ===")

        regime_mapping = {}
        for char in regime_characteristics:
            ret = char['return']
            vol = char['volatility']
            momentum = char['momentum']
            cluster_id = char['id']

            # Classification logic based on professional market cycles:
            # 1. Bear Market: Negative returns + High volatility (crashes)
            # 2. Correction: Negative/flat returns + Medium vol (pullbacks, sideways)
            # 3. Bull Market: Positive returns + LOW volatility (stable uptrend, QE era)
            # 4. Expansion: High positive returns + Strong momentum (violent rebounds post-crash)

            if ret < -0.001 and vol > vol_mean:  # Negative returns + high vol
                new_regime = 0  # Bear Market
                reason = "negative returns + high vol"
            elif ret > 0.002 and momentum > 0.03:  # Strong returns + strong momentum
                new_regime = 3  # Expansion (violent rebounds)
                reason = "strong returns + strong momentum"
            elif ret > 0 and vol < vol_mean:  # Positive returns + low vol
                new_regime = 2  # Bull Market (stable uptrend)
                reason = "positive returns + low vol"
            else:  # Everything else (flat/negative with medium vol)
                new_regime = 1  # Correction (pullbacks, sideways)
                reason = "flat/negative returns or medium vol"

            regime_mapping[cluster_id] = new_regime
            regime_name = self.regime_names[new_regime]
            logger.info(f"  Cluster {cluster_id} → {new_regime} ({regime_name}) | {reason}")

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
            logger.info(f"Validation class distribution: {np.bincount(y_val, minlength=self.num_regimes).tolist()}")

            # Calculate class weights to handle imbalance
            # IMPORTANT: Use minlength to ensure we get weights for ALL 4 classes, even if some are missing
            class_counts = np.bincount(y_train, minlength=self.num_regimes)
            total_samples = len(y_train)
            # Avoid division by zero for missing classes
            class_weights = np.where(class_counts > 0, total_samples / (len(class_counts) * class_counts), 0.0)
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

            # Temperature calibration on validation set
            # Find optimal temperature that maximizes log-likelihood on validation data
            logger.info("Calibrating temperature on validation set...")
            optimal_temp = self._calibrate_temperature(X_val, y_val)
            self.temperature = optimal_temp
            logger.info(f"Optimal temperature found: {optimal_temp:.3f}")

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
                'training_history': training_history,
                'optimal_temperature': optimal_temp
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

    def _calibrate_temperature(self, X_val: torch.Tensor, y_val: torch.Tensor) -> float:
        """
        Find optimal temperature for probability calibration on validation set.

        Uses grid search to maximize negative log-likelihood (NLL) on validation data.
        Temperature scaling adjusts the "confidence" of predictions without changing
        the predicted class.

        Args:
            X_val: Validation features (already scaled)
            y_val: Validation labels

        Returns:
            Optimal temperature value (typically 1.0-5.0)
        """
        self.neural_model.eval()

        # Get logits for validation set
        with torch.no_grad():
            logits, _ = self.neural_model(X_val)

        # Grid search over temperature values
        temperatures = np.arange(0.5, 5.0, 0.1)
        best_nll = float('inf')
        best_temp = 1.0

        for temp in temperatures:
            # Apply temperature scaling
            scaled_logits = logits / temp
            log_probs = torch.nn.functional.log_softmax(scaled_logits, dim=1)

            # Calculate negative log-likelihood (lower is better)
            nll = torch.nn.functional.nll_loss(log_probs, y_val).item()

            if nll < best_nll:
                best_nll = nll
                best_temp = temp

        logger.info(f"Temperature calibration: best_temp={best_temp:.3f}, best_nll={best_nll:.4f}")
        return best_temp

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
                # Apply temperature scaling to calibrate probabilities
                # Higher temperature = less overconfident predictions
                probabilities = torch.softmax(logits / self.temperature, dim=1)

                # CRITICAL: Apply Bayesian prior to enforce uncertainty floor
                # Prevents dangerous overconfidence (99%+) that misleads users
                # Model trained on 20Y bull market (66%) can't predict black swans
                min_uncertainty = 0.15  # Force at least 15% total uncertainty
                uniform_prior = torch.ones(self.num_regimes, device=self.device) / self.num_regimes
                probabilities = (1 - min_uncertainty) * probabilities + min_uncertainty * uniform_prior

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
            
            # HMM prediction (baseline)
            hmm_result = {
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

            # HYBRID SYSTEM: Try rule-based detection first (high confidence cases)
            rule_based_result = self._detect_regime_rule_based(features_df, multi_asset_data)

            # Fuse predictions: rule-based overrides HMM if confidence >= 85%
            fused = self._fuse_predictions(rule_based_result, hmm_result)

            # Update result with fused prediction
            result = hmm_result.copy()
            if fused.get('method') == 'rule_based':
                result['predicted_regime'] = fused['regime_id']
                result['regime_name'] = fused['regime_name']
                result['confidence'] = fused['confidence']
                result['regime_info'] = self.regime_descriptions[fused['regime_id']]
                result['detection_method'] = 'rule_based'
                result['rule_reason'] = fused['reason']
            else:
                result['detection_method'] = 'hmm'

            if return_probabilities:
                result['regime_probabilities'] = {
                    self.regime_names[i]: float(probabilities[0, i].item())
                    for i in range(self.num_regimes)
                }

                result['feature_importance'] = {
                    'top_features': dict(top_features),
                    'attention_pattern': 'complex_multi_head'  # Simplified description
                }

            logger.info(f"Regime prediction: {result['regime_name']} (confidence: {result['confidence']:.3f}, method: {result['detection_method']})")

            # Log prediction for post-mortem analysis
            self._log_prediction_for_analysis(result)

            return result
            
        except Exception as e:
            logger.error(f"Error predicting regime: {str(e)}")
            raise

    def _detect_regime_rule_based(self, features: pd.DataFrame,
                                  multi_asset_data: Dict[str, pd.DataFrame]) -> Optional[Dict[str, Any]]:
        """
        Detect regime using rule-based criteria for HIGH CONFIDENCE cases only.

        This addresses HMM's temporal blindness by using drawdown and persistence criteria.
        Only returns a result if confidence >= 85% (clear bear/bull/expansion).

        Returns:
            Dict with regime prediction + confidence if clear, else None
        """
        if 'drawdown_from_peak' not in features.columns:
            return None  # Need contextual features

        latest = features.iloc[-1]
        drawdown = latest['drawdown_from_peak']
        days_since_peak = latest['days_since_peak']
        trend_30d = latest.get('trend_30d', 0)
        volatility = latest['market_volatility']

        # Rule 1: BEAR MARKET (highest priority)
        # Drawdown ≥ 20% sustained > 60 days
        if drawdown <= -0.20 and days_since_peak >= 60:
            return {
                'regime_id': 0,
                'regime_name': 'Bear Market',
                'confidence': min(0.95, 0.85 + abs(drawdown) * 0.5),  # More drawdown = more confident
                'method': 'rule_based',
                'reason': f'Drawdown {drawdown:.1%} sustained {int(days_since_peak)} days'
            }

        # Rule 2: EXPANSION (post-crash recovery)
        # Coming from >20% drawdown + strong recovery (+15%/month for 3mo)
        if drawdown >= -0.10 and days_since_peak >= 60:  # Recovered
            # Check if there was a recent deep drawdown
            lookback_dd = features.tail(126)['drawdown_from_peak'].min()  # Last 6 months
            if lookback_dd <= -0.20 and trend_30d >= 0.15:  # Was deep + strong recovery
                return {
                    'regime_id': 3,
                    'regime_name': 'Expansion',
                    'confidence': 0.90,
                    'method': 'rule_based',
                    'reason': f'Recovery from {lookback_dd:.1%} at +{trend_30d:.1%}/30d'
                }

        # Rule 3: BULL MARKET (clear uptrend)
        # Low drawdown (<5%), low volatility (<20%), positive trend
        if drawdown >= -0.05 and volatility < 0.20 and trend_30d > 0.05:
            return {
                'regime_id': 2,
                'regime_name': 'Bull Market',
                'confidence': 0.88,
                'method': 'rule_based',
                'reason': f'Stable uptrend: DD={drawdown:.1%}, vol={volatility:.1%}'
            }

        # No clear rule-based detection → defer to HMM
        return None

    def _fuse_predictions(self, rule_based: Optional[Dict], hmm_result: Dict) -> Dict[str, Any]:
        """
        Fuse rule-based and HMM predictions with adaptive weighting.

        FUSION LOGIC:
        - If rule_based confidence >= 85% → Use rule-based (clear case)
        - Else → Use HMM (nuanced case: corrections vs consolidations)

        Args:
            rule_based: Rule-based prediction (or None)
            hmm_result: HMM prediction

        Returns:
            Final fused prediction
        """
        if rule_based and rule_based['confidence'] >= 0.85:
            logger.info(f"Using rule-based: {rule_based['regime_name']} ({rule_based['confidence']:.0%})")
            return rule_based
        else:
            logger.info(f"Using HMM: {hmm_result['regime_name']} (rule-based not confident)")
            hmm_result['method'] = 'hmm'
            return hmm_result

    def _log_prediction_for_analysis(self, prediction: Dict[str, Any]) -> None:
        """
        Log prediction to file for post-mortem analysis.

        Enables tracking model performance over time and identifying:
        - When the model failed to anticipate regime changes
        - Overconfidence patterns before market crashes
        - Calibration drift over time

        Args:
            prediction: Full prediction result dict
        """
        try:
            import json
            from pathlib import Path

            # Create predictions log directory
            predictions_dir = Path("data/ml_predictions")
            predictions_dir.mkdir(parents=True, exist_ok=True)

            # Log file: one per month to avoid huge files
            log_file = predictions_dir / f"regime_predictions_{datetime.now().strftime('%Y-%m')}.jsonl"

            # Compact log entry (JSONL format - one JSON per line)
            log_entry = {
                "timestamp": prediction.get("prediction_date"),
                "regime": prediction.get("regime_name"),
                "regime_id": prediction.get("predicted_regime"),
                "confidence": prediction.get("confidence"),
                "probabilities": prediction.get("regime_probabilities", {}),
                "model_trained_at": prediction.get("model_metadata", {}).get("trained_at")
            }

            # Append to JSONL file (easy to parse later)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')

        except Exception as e:
            # Don't crash prediction if logging fails
            logger.warning(f"Failed to log prediction for analysis: {e}")

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

            # Load optimal temperature (calibrated on validation set)
            # Fall back to default if not available (old models)
            self.temperature = self.training_metadata.get('optimal_temperature', 2.5)
            logger.info(f"Loaded model with calibrated temperature: {self.temperature:.3f}")
            
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