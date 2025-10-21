"""
Bitcoin Market Regime Detection using Hybrid Rule-Based + HMM System

Adapté du système bourse avec thresholds crypto:
- Bear Market: Drawdown ≤ -50% (vs -20% bourse), sustained 30 days (vs 60)
- Expansion: Recovery +30%/month (vs +15% bourse)
- Bull Market: DD > -20%, vol <60% (vs DD > -5%, vol <20%)

Résout le problème de temporal blindness du HMM seul (0% recall sur bear markets).
"""

import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import logging
from pathlib import Path
from hmmlearn import hmm
from sklearn.preprocessing import StandardScaler
import joblib

from services.price_history import price_history

logger = logging.getLogger(__name__)


class BTCRegimeDetector:
    """
    Bitcoin Regime Detection using Hybrid approach:
    - Rule-based detection for clear cases (bear >50% DD, bull stable)
    - HMM for nuanced cases (corrections 10-50%, consolidations)
    - Fusion with confidence threshold 85%

    Detects 4 regimes:
    - 0: Bear Market (violent crashes -50% to -85%)
    - 1: Correction (pullbacks -10% to -50%, or high volatility)
    - 2: Bull Market (stable uptrend, low drawdown)
    - 3: Expansion (post-crash recovery +30%/month)
    """

    def __init__(self, num_regimes: int = 4):
        self.num_regimes = num_regimes
        self.regime_names = ['Bear Market', 'Correction', 'Bull Market', 'Expansion']
        self.regime_descriptions = {
            0: 'Violent market crash with sustained drawdown >50%',
            1: 'Market pullback or high volatility period (10-50% drawdown)',
            2: 'Stable uptrend with low drawdown and moderate volatility',
            3: 'Strong post-crash recovery at +30%/month or higher'
        }

        # HMM model (trained on features)
        self.hmm_model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.training_metadata = {}

        # Models directory
        self.models_dir = Path("models/regime")
        self.models_dir.mkdir(parents=True, exist_ok=True)

    async def prepare_regime_features(
        self,
        symbol: str = 'BTC',
        lookback_days: int = 3650,
        include_contextual: bool = True
    ) -> pd.DataFrame:
        """
        Prepare features for Bitcoin regime detection.

        Args:
            symbol: Crypto symbol (default: BTC)
            lookback_days: Historical window (default: 10 years)
            include_contextual: Add drawdown/temporal features (required for hybrid)

        Returns:
            DataFrame with regime features
        """
        logger.info(f"Preparing regime features for {symbol} ({lookback_days} days)...")

        # Get historical data from price_history cache
        history = price_history.get_cached_history(symbol, days=lookback_days)

        if history is None or len(history) == 0:
            raise ValueError(f"No historical data available for {symbol}. Run: python scripts/init_price_history.py --symbols {symbol} --days {lookback_days}")

        # Convert to DataFrame (history is List[Tuple[timestamp_seconds, close_price]])
        data = pd.DataFrame(history, columns=['timestamp', 'close'])
        data['timestamp'] = pd.to_datetime(data['timestamp'], unit='s')  # Seconds, not ms
        data.set_index('timestamp', inplace=True)

        # For regime detection, we only have close prices (no OHLCV)
        # We'll synthesize volume as constant for features that need it
        data['volume'] = 1.0  # Constant volume (not used for regime detection)

        logger.info(f"Loaded {len(data)} days of {symbol} data")

        # Calculate basic features
        features_df = pd.DataFrame(index=data.index)

        # Returns
        features_df['returns'] = data['close'].pct_change()

        # Realized volatility (20-day rolling std, annualized)
        features_df['realized_vol'] = features_df['returns'].rolling(20).std() * np.sqrt(365)

        # Volume features
        if 'volume' in data.columns:
            vol_ma = data['volume'].rolling(20).mean()
            features_df['volume_ratio'] = data['volume'] / vol_ma
        else:
            features_df['volume_ratio'] = 1.0

        # RSI (14-period)
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        features_df['rsi'] = 100 - (100 / (1 + rs))

        # Price momentum (20-day change)
        features_df['price_momentum_20'] = data['close'].pct_change(20)

        # Market-wide features (single asset, so market = asset)
        features_df['market_return'] = features_df['returns']
        features_df['market_volatility'] = features_df['realized_vol']
        features_df['market_volume_ratio'] = features_df['volume_ratio']
        features_df['market_rsi'] = features_df['rsi']
        features_df['market_momentum'] = features_df['price_momentum_20']

        # Fear & Greed proxy
        features_df['fear_greed_proxy'] = self._calculate_fear_greed_proxy(
            features_df['market_rsi'],
            features_df['market_volatility'],
            features_df['market_momentum']
        )

        # Trend strength
        features_df['trend_strength'] = features_df['market_momentum'].abs()
        features_df['volume_trend'] = (features_df['market_volume_ratio'] - 1).clip(lower=0)

        # Rolling features
        for window in [5, 20, 60]:
            features_df[f'volatility_ma_{window}'] = features_df['market_volatility'].rolling(window).mean()
            features_df[f'return_ma_{window}'] = features_df['market_return'].rolling(window).mean()
            features_df[f'momentum_ma_{window}'] = features_df['market_momentum'].rolling(window).mean()

        # CONTEXTUAL FEATURES (required for hybrid system to overcome HMM temporal blindness)
        if include_contextual:
            # Drawdown from peak (cumulative context)
            cummax = data['close'].cummax()
            drawdown = (data['close'] - cummax) / cummax
            features_df['drawdown_from_peak'] = drawdown

            # Days since peak (temporal context)
            days_since_peak = pd.Series(0, index=data.index, dtype=int)
            peak_idx = 0
            for i in range(len(data)):
                if data['close'].iloc[i] >= data['close'].iloc[:i+1].max():
                    peak_idx = i
                    days_since_peak.iloc[i] = 0
                else:
                    days_since_peak.iloc[i] = i - peak_idx
            features_df['days_since_peak'] = days_since_peak

            # 30-day trend (directional context)
            features_df['trend_30d'] = data['close'].pct_change(30)

            logger.info("Added contextual features: drawdown_from_peak, days_since_peak, trend_30d")

        # Remove NaN rows
        features_df = features_df.dropna()

        # Store feature columns
        self.feature_columns = list(features_df.columns)

        logger.info(f"Regime features prepared: {len(features_df)} samples, {len(self.feature_columns)} features")
        return features_df

    def _calculate_fear_greed_proxy(
        self,
        rsi: pd.Series,
        volatility: pd.Series,
        momentum: pd.Series
    ) -> pd.Series:
        """Calculate Fear & Greed proxy from market indicators"""
        # Normalize RSI (50 = neutral)
        rsi_score = (rsi - 50) / 50  # -1 to 1

        # Volatility score (lower volatility = less fear)
        vol_score = (1 - volatility * 2).clip(0, 1)  # Crypto vol baseline ~50%

        # Momentum score
        momentum_score = np.tanh(momentum * 10)  # -1 to 1

        # Combine scores (0-100 scale)
        fear_greed = (rsi_score * 0.4 + vol_score * 0.3 + momentum_score * 0.3) * 50 + 50
        return fear_greed.clip(0, 100)

    async def train_hmm(self, symbol: str = 'BTC', lookback_days: int = 3650):
        """
        Train HMM model on Bitcoin historical data.

        Args:
            symbol: Crypto symbol
            lookback_days: Training window
        """
        logger.info(f"Training HMM for {symbol} regime detection...")

        # Prepare features
        features_df = await self.prepare_regime_features(symbol, lookback_days)

        # Normalize features
        features_scaled = self.scaler.fit_transform(features_df[self.feature_columns])

        # Train HMM with multiple random starts for stability
        best_score = -np.inf
        best_model = None

        for seed in range(5):  # 5 random initializations
            model = hmm.GaussianHMM(
                n_components=self.num_regimes,
                covariance_type='full',
                n_iter=100,
                random_state=42 + seed
            )

            try:
                model.fit(features_scaled)
                score = model.score(features_scaled)

                if score > best_score:
                    best_score = score
                    best_model = model

                logger.info(f"HMM seed {seed}: score={score:.2f}")

            except Exception as e:
                logger.warning(f"HMM seed {seed} failed: {e}")

        if best_model is None:
            raise ValueError("HMM training failed for all seeds")

        self.hmm_model = best_model
        self.training_metadata = {
            'trained_at': datetime.now().isoformat(),
            'symbol': symbol,
            'lookback_days': lookback_days,
            'num_samples': len(features_df),
            'hmm_score': best_score
        }

        logger.info(f"HMM trained successfully (score={best_score:.2f})")

        # Save model
        self.save_model(f"btc_regime_hmm.pkl")

    def save_model(self, filename: str):
        """Save HMM model and scaler"""
        model_path = self.models_dir / filename
        joblib.dump({
            'hmm_model': self.hmm_model,
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'regime_names': self.regime_names,
            'training_metadata': self.training_metadata
        }, model_path)
        logger.info(f"Model saved to {model_path}")

    def load_model(self, filename: str):
        """Load HMM model and scaler"""
        model_path = self.models_dir / filename
        if not model_path.exists():
            logger.warning(f"Model file not found: {model_path}")
            return False

        data = joblib.load(model_path)
        self.hmm_model = data['hmm_model']
        self.scaler = data['scaler']
        self.feature_columns = data['feature_columns']
        self.regime_names = data['regime_names']
        self.training_metadata = data.get('training_metadata', {})

        logger.info(f"Model loaded from {model_path}")
        return True

    async def predict_regime(
        self,
        symbol: str = 'BTC',
        lookback_days: int = 3650,
        return_probabilities: bool = True
    ) -> Dict[str, Any]:
        """
        Predict current Bitcoin market regime using HYBRID system.

        Args:
            symbol: Crypto symbol
            lookback_days: Historical window for features
            return_probabilities: Include regime probabilities

        Returns:
            Dict with regime prediction, confidence, and method (rule_based or hmm)
        """
        logger.info(f"Predicting regime for {symbol}...")

        # Prepare features
        features_df = await self.prepare_regime_features(symbol, lookback_days)

        if len(features_df) == 0:
            raise ValueError("No features available for prediction")

        # Load or train HMM if needed
        if self.hmm_model is None:
            model_loaded = self.load_model("btc_regime_hmm.pkl")
            if not model_loaded:
                logger.info("No trained model found, training HMM...")
                await self.train_hmm(symbol, lookback_days)

        # Normalize features
        features_scaled = self.scaler.transform(features_df[self.feature_columns])

        # HMM prediction (baseline)
        regime_sequence = self.hmm_model.predict(features_scaled)
        regime_id = int(regime_sequence[-1])
        regime_name = self.regime_names[regime_id]

        # Get regime probabilities
        probabilities = self.hmm_model.predict_proba(features_scaled)
        regime_confidence = float(probabilities[-1, regime_id])

        regime_info = self.regime_descriptions[regime_id]

        # Baseline HMM result
        hmm_result = {
            'predicted_regime': regime_id,
            'regime_name': regime_name,
            'confidence': regime_confidence,
            'regime_info': regime_info,
            'prediction_date': datetime.now().isoformat(),
            'model_metadata': {
                'trained_at': self.training_metadata.get('trained_at'),
                'features_used': len(self.feature_columns)
            }
        }

        # HYBRID SYSTEM: Try rule-based detection first
        rule_based_result = self._detect_regime_rule_based(features_df)

        # Fuse predictions
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
            result['rule_reason'] = None

        if return_probabilities:
            result['regime_probabilities'] = {
                self.regime_names[i]: float(probabilities[-1, i])
                for i in range(self.num_regimes)
            }

        logger.info(f"Regime: {result['regime_name']} (confidence={result['confidence']:.3f}, method={result['detection_method']})")

        return result

    def _detect_regime_rule_based(self, features: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Detect regime using CRYPTO-ADAPTED rule-based criteria.

        Bitcoin thresholds (vs bourse):
        - Bear: DD ≤ -50% (vs -20%), sustained 30 days (vs 60)
        - Expansion: +30%/month (vs +15%)
        - Bull: DD > -20%, vol <60% (vs DD > -5%, vol <20%)

        Only returns result if confidence ≥ 85%.

        Returns:
            Dict with regime + confidence if clear, else None
        """
        if 'drawdown_from_peak' not in features.columns:
            return None  # Need contextual features

        latest = features.iloc[-1]
        drawdown = latest['drawdown_from_peak']
        days_since_peak = latest['days_since_peak']
        trend_30d = latest.get('trend_30d', 0)
        volatility = latest['market_volatility']

        # Rule 1: BEAR MARKET (highest priority)
        # Crypto: DD ≤ -50%, sustained 30 days (vs bourse: -20%, 60 days)
        if drawdown <= -0.50 and days_since_peak >= 30:
            return {
                'regime_id': 0,
                'regime_name': 'Bear Market',
                'confidence': min(0.95, 0.85 + abs(drawdown) * 0.2),  # More DD = more confident
                'method': 'rule_based',
                'reason': f'Drawdown {drawdown:.1%} sustained {int(days_since_peak)} days'
            }

        # Rule 2: EXPANSION (post-crash recovery)
        # Crypto: +30%/month (vs bourse: +15%/month)
        if drawdown >= -0.20 and days_since_peak >= 30:  # Recovered
            # Check if there was recent deep drawdown
            lookback_dd = features.tail(180)['drawdown_from_peak'].min()  # Last 6 months
            if lookback_dd <= -0.50 and trend_30d >= 0.30:  # Was -50%+ deep + strong recovery
                return {
                    'regime_id': 3,
                    'regime_name': 'Expansion',
                    'confidence': 0.90,
                    'method': 'rule_based',
                    'reason': f'Recovery from {lookback_dd:.1%} at +{trend_30d:.1%}/30d'
                }

        # Rule 3: BULL MARKET (clear uptrend)
        # Crypto: DD > -20%, vol <60% (vs bourse: DD > -5%, vol <20%)
        if drawdown >= -0.20 and volatility < 0.60 and trend_30d > 0.10:
            return {
                'regime_id': 2,
                'regime_name': 'Bull Market',
                'confidence': 0.88,
                'method': 'rule_based',
                'reason': f'Stable uptrend: DD={drawdown:.1%}, vol={volatility:.1%}'
            }

        # Rule 4: CORRECTION (fallback before HMM)
        # Moderate drawdown (-50% < DD < -5%) OR elevated volatility (>40%)
        # Prevents HMM from incorrectly labeling corrections as "Bear Market"
        if (-0.50 < drawdown < -0.05) or (volatility > 0.40):
            confidence = 0.85
            # Higher confidence for deeper corrections
            if drawdown < -0.30:
                confidence = 0.90

            reason_parts = []
            if -0.50 < drawdown < -0.05:
                reason_parts.append(f'Moderate drawdown {drawdown:.1%}')
            if volatility > 0.40:
                reason_parts.append(f'Elevated volatility {volatility:.1%}')

            return {
                'regime_id': 1,
                'regime_name': 'Correction',
                'confidence': confidence,
                'method': 'rule_based',
                'reason': ' + '.join(reason_parts)
            }

        # No clear rule-based detection → defer to HMM
        return None

    def _fuse_predictions(self, rule_based: Optional[Dict], hmm_result: Dict) -> Dict[str, Any]:
        """
        Fuse rule-based and HMM predictions.

        FUSION LOGIC:
        - If rule_based confidence ≥ 85% → Use rule-based
        - Else → Use HMM

        Args:
            rule_based: Rule-based prediction (or None)
            hmm_result: HMM prediction

        Returns:
            Fused prediction with method indicator
        """
        if rule_based and rule_based['confidence'] >= 0.85:
            # High confidence rule-based → override HMM
            return rule_based
        else:
            # Use HMM for nuanced cases
            return {
                'regime_id': hmm_result['predicted_regime'],
                'regime_name': hmm_result['regime_name'],
                'confidence': hmm_result['confidence'],
                'method': 'hmm'
            }
