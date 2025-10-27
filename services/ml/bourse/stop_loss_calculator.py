"""
Stop Loss Calculator - Multi-method approach for optimal stop loss placement

Implements 6 methods:
1. Trailing Stop (NEW) - Adaptive trailing for high-gain positions (legacy holdings)
2. Fixed Variable (RECOMMENDED) - 4%/6%/8% based on volatility (WINNER +8% vs Fixed)
3. ATR-based (2x ATR) - Adapts to volatility, good for hyper-volatile only
4. Technical Support (MA20/MA50) - Uses moving averages as support
5. Volatility-adjusted (2σ) - Based on statistical volatility
6. Fixed percentage - Simple fallback (legacy method)

Backtest Results (Oct 2025):
- Fixed Variable: $105,232 (WINNER)
- Fixed 5%: $97,642 (+8% worse)
- ATR 2x: $41,176 (+156% worse)

Author: AI System
Date: October 2025
Updated: After trailing stop implementation (Oct 2025)
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any

from services.stop_loss.trailing_stop_calculator import TrailingStopCalculator

logger = logging.getLogger(__name__)


class StopLossCalculator:
    """Calculate optimal stop loss using multiple methods"""

    # ATR multipliers by market regime
    ATR_MULTIPLIERS = {
        "Bull Market": 2.5,      # More room in bull markets
        "Expansion": 2.5,
        "Correction": 2.0,       # Neutral
        "Bear Market": 1.5,      # Tighter in bear markets
        "default": 2.0
    }

    # Fixed percentages by timeframe (legacy fallback)
    FIXED_STOPS = {
        "short": 0.05,   # 5% for 1-2 weeks
        "medium": 0.08,  # 8% for 1 month
        "long": 0.12     # 12% for 3-6 months
    }

    # RECOMMENDED: Fixed stops by VOLATILITY (validated by backtest)
    # Winner of 3-way comparison (ATR vs Fixed 5% vs Fixed Variable)
    # Performance: +8% vs Fixed 5%, +156% vs ATR 2x
    FIXED_BY_VOLATILITY = {
        "high": 0.08,      # 8% for vol > 40% (NVDA, TSLA, crypto)
        "moderate": 0.06,  # 6% for vol 25-40% (AAPL, MSFT, most stocks)
        "low": 0.04        # 4% for vol < 25% (KO, SPY, defensive/ETFs)
    }

    def __init__(
        self,
        timeframe: str = "medium",
        market_regime: str = "Bull Market"
    ):
        """
        Initialize stop loss calculator

        Args:
            timeframe: Trading timeframe (short/medium/long)
            market_regime: Current market regime
        """
        self.timeframe = timeframe
        self.market_regime = market_regime
        self.atr_multiplier = self.ATR_MULTIPLIERS.get(
            market_regime,
            self.ATR_MULTIPLIERS["default"]
        )

    def get_volatility_bucket(self, price_data: pd.DataFrame) -> str:
        """
        Determine volatility bucket for an asset

        Args:
            price_data: OHLC DataFrame

        Returns:
            "high", "moderate", or "low"
        """
        try:
            returns = price_data['close'].pct_change().dropna()
            annual_vol = returns.std() * np.sqrt(252)

            if annual_vol > 0.40:
                return "high"
            elif annual_vol > 0.25:
                return "moderate"
            else:
                return "low"

        except Exception as e:
            logger.warning(f"Failed to calculate volatility bucket: {e}")
            return "moderate"  # Default to moderate

    def calculate_atr(
        self,
        price_data: pd.DataFrame,
        period: int = 14
    ) -> float:
        """
        Calculate Average True Range (ATR)

        ATR measures volatility by decomposing the entire range of an asset
        for that period.

        Args:
            price_data: DataFrame with 'high', 'low', 'close' columns
            period: ATR period (default 14 days)

        Returns:
            ATR value
        """
        try:
            if len(price_data) < period + 1:
                logger.warning(f"Insufficient data for ATR calculation ({len(price_data)} < {period + 1})")
                return None

            high = price_data['high']
            low = price_data['low']
            close = price_data['close']

            # True Range = max of:
            # 1. Current High - Current Low
            # 2. Abs(Current High - Previous Close)
            # 3. Abs(Current Low - Previous Close)
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())

            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]

            return float(atr)

        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return None

    def calculate_technical_support(
        self,
        price_data: pd.DataFrame,
        current_price: float
    ) -> Dict[str, Any]:
        """
        Calculate stop loss based on technical support levels (MA20, MA50)

        Args:
            price_data: DataFrame with 'close' column
            current_price: Current market price

        Returns:
            Dict with support level info
        """
        try:
            if len(price_data) < 50:
                logger.warning("Insufficient data for MA50 calculation")
                return None

            close = price_data['close']
            ma20 = close.rolling(20).mean().iloc[-1]
            ma50 = close.rolling(50).mean().iloc[-1]

            # Choose closest support below current price
            supports = []
            if ma20 < current_price:
                supports.append(("MA20", ma20))
            if ma50 < current_price:
                supports.append(("MA50", ma50))

            if not supports:
                # If no support below, use MA20 as fallback
                return {
                    "level": "MA20",
                    "price": ma20,
                    "note": "MA20 above current price (weak setup)"
                }

            # Use the closest support (highest value below current)
            level_name, level_price = max(supports, key=lambda x: x[1])

            return {
                "level": level_name,
                "price": float(level_price),
                "note": f"{level_name} support at ${level_price:.2f}"
            }

        except Exception as e:
            logger.error(f"Error calculating technical support: {e}")
            return None

    def calculate_volatility_stop(
        self,
        price_data: pd.DataFrame,
        current_price: float
    ) -> Optional[float]:
        """
        Calculate stop loss based on 2 standard deviations

        Args:
            price_data: DataFrame with 'close' column
            current_price: Current market price

        Returns:
            Stop loss price
        """
        try:
            if len(price_data) < 30:
                logger.warning("Insufficient data for volatility calculation")
                return None

            # Calculate annualized volatility
            returns = price_data['close'].pct_change().dropna()
            std_dev = returns.std() * np.sqrt(252)  # Annualized

            # Stop loss = current price - (2 × daily volatility in price terms)
            daily_vol = std_dev / np.sqrt(252)
            stop_loss = current_price * (1 - 2 * daily_vol)

            return float(stop_loss)

        except Exception as e:
            logger.error(f"Error calculating volatility stop: {e}")
            return None

    def calculate_all_methods(
        self,
        current_price: float,
        price_data: Optional[pd.DataFrame] = None,
        volatility: Optional[float] = None,
        avg_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate stop loss using all methods and recommend best one

        Args:
            current_price: Current market price
            price_data: Historical OHLC data (optional but recommended)
            volatility: Annualized volatility (optional, calculated if not provided)
            avg_price: Average entry price (cost basis) for trailing stop calculation

        Returns:
            Dict with all stop loss methods and recommendation
        """
        result = {
            "current_price": current_price,
            "timeframe": self.timeframe,
            "market_regime": self.market_regime,
            "recommended_method": "fixed_variable",  # UPDATED: Fixed Variable is winner
            "stop_loss_levels": {}
        }

        # Method 1: Fixed Variable (RECOMMENDED - adapts to volatility)
        if price_data is not None and len(price_data) >= 30:
            vol_bucket = self.get_volatility_bucket(price_data)
            fixed_var_pct = self.FIXED_BY_VOLATILITY[vol_bucket]
            fixed_var_stop = current_price * (1 - fixed_var_pct)

            # Calculate actual volatility for display
            if volatility is None:
                returns = price_data['close'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252)

            result["stop_loss_levels"]["fixed_variable"] = {
                "price": round(fixed_var_stop, 2),
                "distance_pct": round(-fixed_var_pct * 100, 1),
                "percentage": fixed_var_pct,
                "volatility_bucket": vol_bucket,
                "annual_volatility": round(volatility, 2) if volatility else None,
                "reasoning": f"{fixed_var_pct*100:.0f}% stop for {vol_bucket} volatility ({volatility*100:.0f}% annual)",
                "quality": "high"  # Winner of backtest
            }

        # Method 2: ATR-based (requires price data)
        if price_data is not None and len(price_data) >= 15:
            atr = self.calculate_atr(price_data)
            if atr is not None:
                atr_stop = current_price - (atr * self.atr_multiplier)
                result["stop_loss_levels"]["atr_2x"] = {
                    "price": round(atr_stop, 2),
                    "distance_pct": round((atr_stop - current_price) / current_price * 100, 1),
                    "atr_value": round(atr, 2),
                    "multiplier": self.atr_multiplier,
                    "reasoning": f"{self.atr_multiplier}× ATR below current. Adapts to asset volatility.",
                    "quality": "medium"  # DOWNGRADED: Lost to Fixed Variable
                }

        # Method 3: Technical Support (requires price data)
        if price_data is not None and len(price_data) >= 50:
            support = self.calculate_technical_support(price_data, current_price)
            if support is not None:
                result["stop_loss_levels"]["technical_support"] = {
                    "price": round(support["price"], 2),
                    "distance_pct": round((support["price"] - current_price) / current_price * 100, 1),
                    "level": support["level"],
                    "reasoning": support["note"],
                    "quality": "medium"
                }

        # Method 4: Volatility-adjusted (requires price data)
        if price_data is not None and len(price_data) >= 30:
            vol_stop = self.calculate_volatility_stop(price_data, current_price)
            if vol_stop is not None:
                # Calculate actual volatility for display
                if volatility is None:
                    returns = price_data['close'].pct_change().dropna()
                    volatility = returns.std() * np.sqrt(252)

                result["stop_loss_levels"]["volatility_2std"] = {
                    "price": round(vol_stop, 2),
                    "distance_pct": round((vol_stop - current_price) / current_price * 100, 1),
                    "volatility": round(volatility, 2) if volatility else None,
                    "reasoning": f"2 std deviations for {volatility*100:.0f}% annual volatility" if volatility else "2 standard deviations",
                    "quality": "medium"
                }

        # Method 5: Fixed percentage (legacy - always available as fallback)
        fixed_pct = self.FIXED_STOPS.get(self.timeframe, 0.05)
        fixed_stop = current_price * (1 - fixed_pct)
        result["stop_loss_levels"]["fixed_pct"] = {
            "price": round(fixed_stop, 2),
            "distance_pct": round(-fixed_pct * 100, 1),
            "percentage": fixed_pct,
            "reasoning": f"Simple {fixed_pct*100:.0f}% stop for {self.timeframe} timeframe (legacy)",
            "quality": "low"
        }

        # Method 6: Trailing Stop (NEW - for high-gain legacy positions)
        if avg_price and avg_price > 0:
            trailing_calc = TrailingStopCalculator(ath_lookback_days=365)
            trailing_result = trailing_calc.calculate_trailing_stop(
                current_price=current_price,
                avg_price=avg_price,
                ath=None,  # Will be estimated from price_history
                price_history=price_data
            )

            # Only add if trailing stop is applicable (sufficient unrealized gains)
            if trailing_result and trailing_result.get('applicable'):
                result["stop_loss_levels"]["trailing_stop"] = {
                    "price": trailing_result["stop_loss"],
                    "distance_pct": trailing_result["distance_pct"],
                    "gain_pct": trailing_result["unrealized_gain_pct"],
                    "ath": trailing_result["ath"],
                    "ath_estimated": trailing_result["ath_estimated"],
                    "trail_pct": trailing_result["trail_pct"],
                    "tier": trailing_result["tier"],
                    "reasoning": trailing_result["reasoning"],
                    "quality": "high",  # High quality for protecting large gains
                    "is_legacy": True
                }
                logger.info(f"Trailing stop applied: {trailing_result['reasoning']}")

        # Determine recommended method
        result["recommended_method"] = self._determine_best_method(result["stop_loss_levels"])

        # Add recommendation note
        if result["recommended_method"] in result["stop_loss_levels"]:
            result["recommended"] = result["stop_loss_levels"][result["recommended_method"]]

        return result

    def _determine_best_method(self, stop_loss_levels: Dict) -> str:
        """
        Determine which stop loss method to recommend

        Priority (UPDATED with trailing stop Oct 2025):
        1. Trailing Stop (if applicable) - HIGHEST priority for legacy positions
        2. Fixed Variable (if available) - WINNER of backtest (+8% vs Fixed 5%)
        3. ATR-based (if available) - Good for hyper-volatile only
        4. Technical Support (if available)
        5. Fixed percentage (legacy fallback)

        Args:
            stop_loss_levels: Dict of calculated stop loss levels

        Returns:
            Recommended method key
        """
        # Highest priority: Trailing stop for legacy positions with high gains
        if "trailing_stop" in stop_loss_levels:
            return "trailing_stop"
        # Standard methods for recent positions
        elif "fixed_variable" in stop_loss_levels:
            return "fixed_variable"  # Winner of 3-way backtest
        elif "atr_2x" in stop_loss_levels:
            return "atr_2x"
        elif "technical_support" in stop_loss_levels:
            return "technical_support"
        elif "volatility_2std" in stop_loss_levels:
            return "volatility_2std"
        else:
            return "fixed_pct"

    def get_stop_loss_quality_badge(self, method: str) -> str:
        """
        Get quality badge for a stop loss method

        Args:
            method: Method name

        Returns:
            Badge text (high/medium/low)
        """
        quality_map = {
            "trailing_stop": "high",   # NEW: High priority for legacy positions
            "fixed_variable": "high",  # Winner of backtest
            "atr_2x": "medium",        # DOWNGRADED: Lost to Fixed Variable
            "technical_support": "medium",
            "volatility_2std": "medium",
            "fixed_pct": "low"
        }
        return quality_map.get(method, "low")
