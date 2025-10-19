"""
Technical Indicators Calculator for Portfolio Recommendations

Calculates technical indicators for individual stock/ETF positions:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Moving Averages (MA20, MA50, MA200)
- Support/Resistance levels
- Volume analysis
- Adaptive thresholds based on market regime
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Calculate technical indicators for stock analysis"""

    def __init__(self, market_regime: str = "Bull Market"):
        """
        Initialize with market regime for adaptive thresholds

        Args:
            market_regime: Current market regime (Bear/Correction/Bull/Expansion)
        """
        self.market_regime = market_regime
        self.rsi_thresholds = self._get_rsi_thresholds()

    def _get_rsi_thresholds(self) -> Dict[str, float]:
        """Get adaptive RSI thresholds based on market regime"""
        thresholds = {
            "Bear Market": {"overbought": 65, "oversold": 35},
            "Correction": {"overbought": 70, "oversold": 30},
            "Bull Market": {"overbought": 70, "oversold": 30},
            "Expansion": {"overbought": 80, "oversold": 40}  # Higher in strong bull
        }
        return thresholds.get(self.market_regime, {"overbought": 70, "oversold": 30})

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index

        Args:
            prices: Price series
            period: RSI period (default 14)

        Returns:
            RSI series
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_macd(
        self,
        prices: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence)

        Args:
            prices: Price series
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line period (default 9)

        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def calculate_moving_averages(
        self,
        prices: pd.Series
    ) -> Dict[str, float]:
        """
        Calculate key moving averages

        Args:
            prices: Price series

        Returns:
            Dict with MA20, MA50, MA200 values
        """
        current_price = prices.iloc[-1]

        ma20 = prices.rolling(window=20).mean().iloc[-1] if len(prices) >= 20 else None
        ma50 = prices.rolling(window=50).mean().iloc[-1] if len(prices) >= 50 else None
        ma200 = prices.rolling(window=200).mean().iloc[-1] if len(prices) >= 200 else None

        return {
            "ma20": ma20,
            "ma50": ma50,
            "ma200": ma200,
            "current_price": current_price,
            "vs_ma20_pct": ((current_price / ma20 - 1) * 100) if ma20 else None,
            "vs_ma50_pct": ((current_price / ma50 - 1) * 100) if ma50 else None,
            "vs_ma200_pct": ((current_price / ma200 - 1) * 100) if ma200 else None,
        }

    def detect_golden_death_cross(
        self,
        prices: pd.Series
    ) -> Optional[str]:
        """
        Detect Golden Cross (bullish) or Death Cross (bearish)

        Args:
            prices: Price series

        Returns:
            "golden_cross", "death_cross", or None
        """
        if len(prices) < 50:
            return None

        ma20 = prices.rolling(window=20).mean()
        ma50 = prices.rolling(window=50).mean()

        # Check last 5 days for crossover
        if len(ma20) >= 5 and len(ma50) >= 5:
            # Golden cross: MA20 crosses above MA50
            if ma20.iloc[-1] > ma50.iloc[-1] and ma20.iloc[-5] <= ma50.iloc[-5]:
                return "golden_cross"
            # Death cross: MA20 crosses below MA50
            elif ma20.iloc[-1] < ma50.iloc[-1] and ma20.iloc[-5] >= ma50.iloc[-5]:
                return "death_cross"

        return None

    def calculate_support_resistance(
        self,
        prices: pd.Series,
        window: int = 20
    ) -> Dict[str, float]:
        """
        Calculate support and resistance levels using pivot points

        Args:
            prices: Price series (must have OHLC if available)
            window: Lookback window for calculation

        Returns:
            Dict with support and resistance levels
        """
        # Simple pivot point calculation
        # In a real implementation, you'd use OHLC data
        recent_prices = prices.iloc[-window:]
        high = recent_prices.max()
        low = recent_prices.min()
        close = recent_prices.iloc[-1]

        pivot = (high + low + close) / 3

        resistance1 = 2 * pivot - low
        support1 = 2 * pivot - high

        resistance2 = pivot + (high - low)
        support2 = pivot - (high - low)

        return {
            "pivot": pivot,
            "resistance1": resistance1,
            "resistance2": resistance2,
            "support1": support1,
            "support2": support2,
            "current_price": close
        }

    def calculate_volume_metrics(
        self,
        volumes: pd.Series,
        period: int = 20
    ) -> Dict[str, Any]:
        """
        Calculate volume metrics

        Args:
            volumes: Volume series
            period: Period for average calculation

        Returns:
            Dict with volume metrics
        """
        if len(volumes) < period:
            return {
                "current_volume": volumes.iloc[-1] if len(volumes) > 0 else 0,
                "avg_volume": None,
                "volume_ratio": None,
                "volume_trend": "neutral"
            }

        current_volume = volumes.iloc[-1]
        avg_volume = volumes.rolling(window=period).mean().iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Volume trend: increasing or decreasing
        recent_avg = volumes.iloc[-5:].mean()
        older_avg = volumes.iloc[-period:-5].mean() if len(volumes) >= period else recent_avg

        volume_trend = "increasing" if recent_avg > older_avg * 1.1 else \
                      "decreasing" if recent_avg < older_avg * 0.9 else "neutral"

        return {
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "volume_ratio": volume_ratio,
            "volume_trend": volume_trend
        }

    def analyze_stock(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Comprehensive technical analysis for a stock

        Args:
            df: DataFrame with at least 'Close' column (optionally 'Volume')
            symbol: Stock symbol

        Returns:
            Dict with all technical indicators and scores
        """
        try:
            prices = df['Close']

            # RSI
            rsi = self.calculate_rsi(prices)
            current_rsi = rsi.iloc[-1] if len(rsi) > 0 and not pd.isna(rsi.iloc[-1]) else 50

            # MACD
            macd_line, signal_line, histogram = self.calculate_macd(prices)
            current_macd = macd_line.iloc[-1] if len(macd_line) > 0 else 0
            current_signal = signal_line.iloc[-1] if len(signal_line) > 0 else 0
            current_histogram = histogram.iloc[-1] if len(histogram) > 0 else 0

            # MACD signal
            macd_signal = "bullish" if current_histogram > 0 else \
                         "bearish" if current_histogram < 0 else "neutral"

            # Moving Averages
            ma_data = self.calculate_moving_averages(prices)

            # Golden/Death Cross
            cross = self.detect_golden_death_cross(prices)

            # Support/Resistance
            sr_levels = self.calculate_support_resistance(prices)

            # Volume (if available)
            volume_metrics = {}
            if 'Volume' in df.columns:
                volume_metrics = self.calculate_volume_metrics(df['Volume'])

            # Technical Score (0-1)
            technical_score = self._calculate_technical_score(
                current_rsi,
                macd_signal,
                ma_data['vs_ma50_pct'],
                cross,
                volume_metrics.get('volume_ratio')
            )

            return {
                "symbol": symbol,
                "rsi_14d": round(current_rsi, 2),
                "rsi_signal": self._get_rsi_signal(current_rsi),
                "macd_value": round(current_macd, 4),
                "macd_signal_value": round(current_signal, 4),
                "macd_histogram": round(current_histogram, 4),
                "macd_signal": macd_signal,
                "ma20": ma_data.get("ma20"),
                "ma50": ma_data.get("ma50"),
                "ma200": ma_data.get("ma200"),
                "vs_ma20_pct": round(ma_data["vs_ma20_pct"], 2) if ma_data["vs_ma20_pct"] else None,
                "vs_ma50_pct": round(ma_data["vs_ma50_pct"], 2) if ma_data["vs_ma50_pct"] else None,
                "vs_ma200_pct": round(ma_data["vs_ma200_pct"], 2) if ma_data["vs_ma200_pct"] else None,
                "cross_signal": cross,
                "support_resistance": sr_levels,
                "volume_metrics": volume_metrics,
                "technical_score": round(technical_score, 3),
                "market_regime": self.market_regime
            }

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return {
                "symbol": symbol,
                "error": str(e),
                "technical_score": 0.5  # Neutral on error
            }

    def _get_rsi_signal(self, rsi: float) -> str:
        """Get RSI signal based on adaptive thresholds"""
        if rsi >= self.rsi_thresholds["overbought"]:
            return "overbought"
        elif rsi <= self.rsi_thresholds["oversold"]:
            return "oversold"
        else:
            return "neutral"

    def _calculate_technical_score(
        self,
        rsi: float,
        macd_signal: str,
        vs_ma50_pct: Optional[float],
        cross: Optional[str],
        volume_ratio: Optional[float]
    ) -> float:
        """
        Calculate aggregated technical score (0-1)

        Components:
        - RSI: 0.3 weight
        - MACD: 0.25 weight
        - MA trend: 0.25 weight
        - Cross signal: 0.1 weight
        - Volume: 0.1 weight
        """
        score = 0.0

        # RSI contribution (30%)
        if rsi <= self.rsi_thresholds["oversold"]:
            rsi_score = 0.8  # Oversold = buy opportunity
        elif rsi >= self.rsi_thresholds["overbought"]:
            rsi_score = 0.2  # Overbought = sell signal
        else:
            # Scale from oversold to overbought
            normalized_rsi = (rsi - self.rsi_thresholds["oversold"]) / \
                           (self.rsi_thresholds["overbought"] - self.rsi_thresholds["oversold"])
            rsi_score = 1 - normalized_rsi  # Invert: lower RSI = higher score
        score += rsi_score * 0.3

        # MACD contribution (25%)
        macd_score = 0.7 if macd_signal == "bullish" else \
                    0.3 if macd_signal == "bearish" else 0.5
        score += macd_score * 0.25

        # MA trend contribution (25%)
        if vs_ma50_pct is not None:
            if vs_ma50_pct > 5:
                ma_score = 0.8  # Strong uptrend
            elif vs_ma50_pct > 0:
                ma_score = 0.6  # Mild uptrend
            elif vs_ma50_pct > -5:
                ma_score = 0.4  # Mild downtrend
            else:
                ma_score = 0.2  # Strong downtrend
        else:
            ma_score = 0.5  # Neutral if no data
        score += ma_score * 0.25

        # Cross signal contribution (10%)
        cross_score = 0.8 if cross == "golden_cross" else \
                     0.2 if cross == "death_cross" else 0.5
        score += cross_score * 0.1

        # Volume contribution (10%)
        if volume_ratio is not None:
            if volume_ratio > 1.5:
                volume_score = 0.7  # High volume = strong signal
            elif volume_ratio > 1.0:
                volume_score = 0.6
            else:
                volume_score = 0.4  # Low volume = weak signal
        else:
            volume_score = 0.5
        score += volume_score * 0.1

        return max(0.0, min(1.0, score))
