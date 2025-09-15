"""
Crypto-specific feature engineering for ML models
Advanced technical indicators and crypto market features
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CryptoFeatureEngineer:
    """
    Advanced feature engineering for cryptocurrency data
    Focuses on crypto-specific patterns and market microstructure
    """
    
    def __init__(self):
        self.feature_cache = {}
        
    def engineer_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer price-based technical features
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with price features
        """
        result = df.copy()
        
        # Basic price features
        result['returns'] = result['close'].pct_change()
        result['log_returns'] = np.log(result['close'] / result['close'].shift(1))
        
        # Price momentum features (minimal windows for maximum data compatibility)
        for window in [3, 5, 10]:  # Further reduced windows
            result[f'momentum_{window}'] = result['close'] / result['close'].shift(window) - 1
            result[f'ma_{window}'] = result['close'].rolling(window=window).mean()
        
        # Moving average ratios (using available MAs only)
        result['ma_ratio_5_10'] = result['ma_5'] / result['ma_10']  # Use shorter windows
        
        # Price position relative to moving averages
        result['price_vs_ma10'] = (result['close'] - result['ma_10']) / result['ma_10']
        result['price_vs_ma5'] = (result['close'] - result['ma_5']) / result['ma_5']
        
        return result
    
    def engineer_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer volatility-based features
        
        Args:
            df: DataFrame with returns
            
        Returns:
            DataFrame with volatility features
        """
        result = df.copy()
        
        # Realized volatility at different time horizons (reduced windows)
        for window in [5, 10]:  # Minimal windows for compatibility
            result[f'vol_{window}'] = result['returns'].rolling(window=window).std() * np.sqrt(365)
        
        # Volatility ratios and spreads (using available windows)
        result['vol_ratio_5_10'] = result['vol_5'] / result['vol_10']
        result['vol_spread_5_10'] = result['vol_5'] - result['vol_10']
        
        # GARCH-like features (using shorter windows)
        result['vol_persistence'] = result['vol_10'].rolling(window=5).std()
        result['vol_mean_reversion'] = (result['vol_5'] - result['vol_10'].rolling(window=5).mean()) / result['vol_10'].rolling(window=5).std()
        
        # High-frequency volatility proxies
        result['hl_ratio'] = (result['high'] - result['low']) / result['close']
        result['oc_ratio'] = abs(result['open'] - result['close']) / result['close']
        result['garman_klass_vol'] = np.sqrt(
            np.log(result['high'] / result['low']) * np.log(result['high'] / result['low']) * 0.5 -
            (2 * np.log(2) - 1) * np.log(result['close'] / result['open']) * np.log(result['close'] / result['open'])
        ) * np.sqrt(365)
        
        return result
    
    def engineer_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer volume-based features
        
        Args:
            df: DataFrame with volume data
            
        Returns:
            DataFrame with volume features
        """
        result = df.copy()
        
        # Volume moving averages
        for window in [5, 10]:  # Reduced windows for better compatibility
            result[f'volume_ma_{window}'] = result['volume'].rolling(window=window).mean()
        
        # Volume ratios
        result['volume_ratio_current'] = result['volume'] / result['volume_ma_10']  # Use ma_10 instead
        result['volume_ratio_5_10'] = result['volume_ma_5'] / result['volume_ma_10']  # Use ma_10 instead
        
        # Volume momentum
        for window in [3, 5, 10]:
            result[f'volume_momentum_{window}'] = result['volume'] / result['volume'].shift(window) - 1
        
        # Price-Volume relationship
        result['price_volume_trend'] = (result['close'] - result['close'].shift(1)) * result['volume']
        result['volume_price_ratio'] = result['volume'] / result['close']
        
        # On-Balance Volume (OBV)
        result['obv'] = (np.sign(result['returns']) * result['volume']).cumsum()
        result['obv_ma'] = result['obv'].rolling(window=20).mean()
        result['obv_divergence'] = result['obv'] - result['obv_ma']
        
        return result
    
    def engineer_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer technical analysis indicators
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with technical indicators
        """
        result = df.copy()
        
        # RSI (Relative Strength Index)
        result['rsi'] = self._calculate_rsi(result['close'])
        result['rsi_overbought'] = (result['rsi'] > 70).astype(int)
        result['rsi_oversold'] = (result['rsi'] < 30).astype(int)
        
        # MACD
        result['macd'], result['macd_signal'], result['macd_histogram'] = self._calculate_macd(result['close'])
        
        # Bollinger Bands
        result['bb_upper'], result['bb_middle'], result['bb_lower'] = self._calculate_bollinger_bands(result['close'])
        result['bb_position'] = (result['close'] - result['bb_lower']) / (result['bb_upper'] - result['bb_lower'])
        result['bb_squeeze'] = (result['bb_upper'] - result['bb_lower']) / result['bb_middle']
        
        # Williams %R
        result['williams_r'] = self._calculate_williams_r(result['high'], result['low'], result['close'])
        
        # Commodity Channel Index (CCI)
        result['cci'] = self._calculate_cci(result['high'], result['low'], result['close'])
        
        # Average True Range (ATR)
        result['atr'] = self._calculate_atr(result['high'], result['low'], result['close'])
        result['atr_ratio'] = result['atr'] / result['close']
        
        return result
    
    def engineer_crypto_specific_features(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Engineer crypto-specific market features
        
        Args:
            df: DataFrame with price data
            symbol: Crypto symbol
            
        Returns:
            DataFrame with crypto-specific features
        """
        result = df.copy()
        
        # Time-based features (crypto markets are 24/7)
        result['hour'] = result.index.hour
        result['day_of_week'] = result.index.dayofweek
        result['is_weekend'] = (result['day_of_week'] >= 5).astype(int)
        result['is_asian_hours'] = ((result['hour'] >= 0) & (result['hour'] < 8)).astype(int)
        result['is_us_hours'] = ((result['hour'] >= 13) & (result['hour'] < 21)).astype(int)
        result['is_european_hours'] = ((result['hour'] >= 7) & (result['hour'] < 16)).astype(int)
        
        # Crypto market cap tiers (approximation based on symbol)
        large_cap = ['BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'AVAX']
        mid_cap = ['MATIC', 'LINK', 'UNI', 'LTC', 'BCH', 'ATOM', 'ALGO', 'NEAR']
        
        if symbol in large_cap:
            result['market_cap_tier'] = 0  # Large cap
        elif symbol in mid_cap:
            result['market_cap_tier'] = 1  # Mid cap
        else:
            result['market_cap_tier'] = 2  # Small cap / Alt coin
        
        # Drawdown features
        result['peak'] = result['close'].expanding().max()
        result['drawdown'] = (result['close'] - result['peak']) / result['peak']
        result['drawdown_duration'] = self._calculate_drawdown_duration(result['drawdown'])
        
        # Pump and dump detection features
        result['price_acceleration'] = result['returns'] - result['returns'].shift(1)
        result['volume_spike'] = (result['volume'] > result['volume'].rolling(window=20).mean() * 3).astype(int)
        result['pump_signal'] = ((result['returns'] > 0.1) & (result['volume_spike'] == 1)).astype(int)
        
        # Correlation with Bitcoin (if not BTC)
        if symbol != 'BTC' and 'btc_price' in result.columns:
            result['btc_correlation'] = result['returns'].rolling(window=30).corr(result['btc_price'].pct_change())
            result['beta_to_btc'] = self._calculate_beta(result['returns'], result['btc_price'].pct_change())
        
        return result
    
    def engineer_sentiment_features(self, df: pd.DataFrame, sentiment_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Engineer sentiment-based features
        
        Args:
            df: DataFrame with price data
            sentiment_data: Optional sentiment data
            
        Returns:
            DataFrame with sentiment features
        """
        result = df.copy()
        
        # Fear and Greed Index approximation (based on volatility and momentum)
        result['fear_greed_proxy'] = self._calculate_fear_greed_proxy(result)
        
        # Market structure indicators
        result['trend_strength'] = abs(result['ma_5'] - result['ma_10']) / result['close']  # Use ma_10
        result['market_regime'] = self._classify_market_regime(result)
        
        # Add actual sentiment data if provided
        if sentiment_data is not None:
            result = result.merge(sentiment_data, left_index=True, right_index=True, how='left')
            result['sentiment_score'] = result['sentiment_score'].fillna(0)
            result['sentiment_momentum'] = result['sentiment_score'] - result['sentiment_score'].shift(1)
        
        return result
    
    def _calculate_rsi(self, prices: pd.Series, window: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD"""
        exp1 = prices.ewm(span=fast).mean()
        exp2 = prices.ewm(span=slow).mean()
        macd = exp1 - exp2
        macd_signal = macd.ewm(span=signal).mean()
        macd_histogram = macd - macd_signal
        return macd, macd_signal, macd_histogram
    
    def _calculate_bollinger_bands(self, prices: pd.Series, window: int = 20, num_std: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        ma = prices.rolling(window=window).mean()
        std = prices.rolling(window=window).std()
        upper = ma + (std * num_std)
        lower = ma - (std * num_std)
        return upper, ma, lower
    
    def _calculate_williams_r(self, high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """Calculate Williams %R"""
        highest_high = high.rolling(window=window).max()
        lowest_low = low.rolling(window=window).min()
        williams_r = -100 * (highest_high - close) / (highest_high - lowest_low)
        return williams_r
    
    def _calculate_cci(self, high: pd.Series, low: pd.Series, close: pd.Series, window: int = 20) -> pd.Series:
        """Calculate Commodity Channel Index"""
        typical_price = (high + low + close) / 3
        ma = typical_price.rolling(window=window).mean()
        mean_deviation = typical_price.rolling(window=window).apply(lambda x: np.abs(x - x.mean()).mean())
        cci = (typical_price - ma) / (0.015 * mean_deviation)
        return cci
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = high - low
        high_close_prev = np.abs(high - close.shift())
        low_close_prev = np.abs(low - close.shift())
        true_range = np.maximum(high_low, np.maximum(high_close_prev, low_close_prev))
        atr = true_range.rolling(window=window).mean()
        return atr
    
    def _calculate_drawdown_duration(self, drawdown: pd.Series) -> pd.Series:
        """Calculate drawdown duration"""
        duration = pd.Series(index=drawdown.index, dtype=float)
        current_duration = 0
        
        for i in range(len(drawdown)):
            if drawdown.iloc[i] < 0:
                current_duration += 1
            else:
                current_duration = 0
            duration.iloc[i] = current_duration
        
        return duration
    
    def _calculate_beta(self, asset_returns: pd.Series, market_returns: pd.Series, window: int = 60) -> pd.Series:
        """Calculate rolling beta"""
        def beta_calc(x, y):
            if len(x) < 10:  # Need minimum observations
                return np.nan
            covariance = np.cov(x, y)[0, 1]
            variance = np.var(y)
            return covariance / variance if variance != 0 else np.nan
        
        beta = pd.Series(index=asset_returns.index, dtype=float)
        for i in range(window, len(asset_returns)):
            asset_window = asset_returns.iloc[i-window:i]
            market_window = market_returns.iloc[i-window:i]
            beta.iloc[i] = beta_calc(asset_window.dropna(), market_window.dropna())
        
        return beta
    
    def _calculate_fear_greed_proxy(self, df: pd.DataFrame) -> pd.Series:
        """Calculate a proxy for Fear & Greed Index"""
        # Combine momentum, volatility, and volume signals
        momentum_signal = df['momentum_10'].rolling(window=10).mean()  # Use momentum_10
        vol_signal = 1 - (df['vol_10'] / df['vol_10'].rolling(window=15).max())  # Use vol_10 and reduced window
        volume_signal = df['volume_ratio_current'].rolling(window=10).mean()  # Reduced window
        
        # Normalize signals to 0-1 range (minimal windows)
        momentum_norm = (momentum_signal - momentum_signal.rolling(window=20).min()) / \
                       (momentum_signal.rolling(window=20).max() - momentum_signal.rolling(window=20).min())
        vol_norm = vol_signal
        volume_norm = (volume_signal - volume_signal.rolling(window=20).min()) / \
                     (volume_signal.rolling(window=20).max() - volume_signal.rolling(window=20).min())
        
        # Weighted combination (scaled to 0-100)
        fear_greed_proxy = (momentum_norm * 0.4 + vol_norm * 0.4 + volume_norm * 0.2) * 100
        
        return fear_greed_proxy.fillna(50)  # Neutral default
    
    def _classify_market_regime(self, df: pd.DataFrame) -> pd.Series:
        """Classify market regime (0: Bear, 1: Neutral, 2: Bull)"""
        # Use multiple indicators to classify regime
        ma_signal = (df['close'] > df['ma_10']).astype(int)  # Use ma_10
        momentum_signal = (df['momentum_10'] > 0).astype(int)  # Use momentum_10
        trend_signal = (df['ma_5'] > df['ma_10']).astype(int)  # Use ma_10
        
        regime_score = ma_signal + momentum_signal + trend_signal
        
        # Convert to regime classification
        regime = pd.Series(index=df.index, dtype=int)
        regime[regime_score == 0] = 0  # Bear
        regime[regime_score == 1] = 1  # Neutral
        regime[regime_score >= 2] = 2  # Bull
        
        return regime
    
    def create_feature_set(self, df: pd.DataFrame, symbol: str, 
                          sentiment_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Create comprehensive feature set for ML models
        
        Args:
            df: Raw OHLCV data
            symbol: Asset symbol
            sentiment_data: Optional sentiment data
            
        Returns:
            DataFrame with all engineered features
        """
        logger.info(f"Engineering features for {symbol}")
        
        # Ultra-simplified feature engineering for debugging
        result = df.copy()
        
        # Only absolute basics - no rolling windows > 5
        result['returns'] = result['close'].pct_change()
        result['ma_3'] = result['close'].rolling(3).mean()
        result['ma_5'] = result['close'].rolling(5).mean()
        result['vol_3'] = result['returns'].rolling(3).std() * np.sqrt(365)
        result['vol_5'] = result['returns'].rolling(5).std() * np.sqrt(365)
        
        # Skip ALL complex methods that might have large windows
        
        # Drop rows with NaN values
        initial_length = len(result)
        result = result.dropna()
        final_length = len(result)
        
        logger.info(f"Feature engineering complete for {symbol}: "
                   f"{initial_length} -> {final_length} samples, "
                   f"{len(result.columns)} features")
        
        return result