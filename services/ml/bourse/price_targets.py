"""
Price Targets Calculator for Portfolio Recommendations

Calculates:
- Entry zones (for BUY signals)
- Stop-loss levels (multi-method: ATR, Technical, Volatility, Fixed)
- Take-profit targets (TP1, TP2)
- Risk/Reward ratios
"""

from typing import Dict, Any, Optional, Tuple
import logging
import pandas as pd
from services.ml.bourse.stop_loss_calculator import StopLossCalculator

logger = logging.getLogger(__name__)


class PriceTargets:
    """Calculate price targets based on technical levels and timeframe"""

    # Target percentages by timeframe
    TARGETS = {
        "short": {  # 1-2 weeks
            "entry_buffer": 0.02,  # 2% above current for entry zone
            "stop_loss": 0.05,     # 5% below support
            "tp1": 0.05,           # 5% above current
            "tp2": 0.10            # 10% above current
        },
        "medium": {  # 1 month
            "entry_buffer": 0.03,  # 3%
            "stop_loss": 0.08,     # 8%
            "tp1": 0.08,           # 8%
            "tp2": 0.15            # 15%
        },
        "long": {  # 3-6 months
            "entry_buffer": 0.05,  # 5%
            "stop_loss": 0.12,     # 12%
            "tp1": 0.12,           # 12%
            "tp2": 0.25            # 25%
        }
    }

    def __init__(self, timeframe: str = "medium", market_regime: str = "Bull Market"):
        """
        Initialize price targets calculator

        Args:
            timeframe: "short", "medium", or "long"
            market_regime: Current market regime for stop loss adaptation
        """
        if timeframe not in self.TARGETS:
            logger.warning(f"Invalid timeframe '{timeframe}', defaulting to 'medium'")
            timeframe = "medium"

        self.timeframe = timeframe
        self.market_regime = market_regime
        self.params = self.TARGETS[timeframe]

        # Initialize stop loss calculator
        self.stop_loss_calc = StopLossCalculator(
            timeframe=timeframe,
            market_regime=market_regime
        )

    def calculate_targets(
        self,
        current_price: float,
        action: str,
        support_resistance: Optional[Dict[str, float]] = None,
        volatility: Optional[float] = None,
        price_data: Optional[pd.DataFrame] = None,
        avg_price: Optional[float] = None,
        leverage: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate all price targets

        Args:
            current_price: Current market price
            action: Recommendation action (STRONG BUY, BUY, HOLD, etc.)
            support_resistance: Optional S/R levels from technical analysis
            volatility: Optional volatility for adaptive sizing
            price_data: Optional historical OHLC data for advanced stop loss calculation
            avg_price: Average entry price (cost basis) for trailing stop calculation
            leverage: Optional leverage multiplier for CFD/leveraged products (P0 Enhancement)

        Returns:
            Dict with entry zone, stop-loss, take-profits, and risk/reward
        """
        if action in ["STRONG BUY", "BUY"]:
            return self._calculate_buy_targets(
                current_price,
                support_resistance,
                volatility,
                price_data,
                avg_price,
                leverage
            )
        elif action in ["STRONG SELL", "SELL"]:
            return self._calculate_sell_targets(
                current_price,
                support_resistance,
                volatility,
                price_data,
                avg_price
            )
        else:  # HOLD
            return self._calculate_hold_targets(current_price, price_data, avg_price)

    def _calculate_buy_targets(
        self,
        current_price: float,
        sr_levels: Optional[Dict[str, float]],
        volatility: Optional[float],
        price_data: Optional[pd.DataFrame] = None,
        avg_price: Optional[float] = None,
        leverage: Optional[float] = None
    ) -> Dict[str, Any]:
        """Calculate targets for BUY recommendations"""

        # Entry zone: between support and slight premium
        entry_low = current_price * (1 - self.params["entry_buffer"] / 2)
        entry_high = current_price * (1 + self.params["entry_buffer"])

        # Adjust entry zone with support if available
        if sr_levels and "support1" in sr_levels:
            support = sr_levels["support1"]
            if support < current_price:
                entry_low = max(entry_low, support)

        # Calculate stop loss using multi-method approach
        stop_loss_analysis = self.stop_loss_calc.calculate_all_methods(
            current_price=current_price,
            price_data=price_data,
            volatility=volatility,
            avg_price=avg_price  # Pass avg_price for trailing stop calculation
        )

        # Use recommended stop loss for main calculation
        recommended_method = stop_loss_analysis["recommended_method"]
        stop_loss = stop_loss_analysis["stop_loss_levels"][recommended_method]["price"]

        # CFD/Leverage adjustment (P0 Enhancement - Oct 2025)
        # For leveraged products, use much tighter stops (divide distance by leverage)
        if leverage and leverage > 1.0:
            logger.info(f"Adjusting stop loss for leverage {leverage:.1f}x")
            stop_distance = current_price - stop_loss
            adjusted_distance = stop_distance / leverage  # Tighter stop for leverage
            stop_loss = current_price - adjusted_distance
            logger.info(f"Stop loss adjusted: {stop_loss:.2f} (original distance reduced by {leverage:.1f}x)")

        # Get volatility bucket from stop loss analysis (for adaptive TP calculation)
        vol_bucket = stop_loss_analysis["stop_loss_levels"][recommended_method].get("volatility_bucket", "moderate")

        # TP multipliers based on volatility (Option C - Adaptive)
        # Low vol: aim further (predictable, can hold longer)
        # High vol: take profits earlier (erratic, quick reversals)
        TP_MULTIPLIERS = {
            "low": {"tp1": 2.0, "tp2": 3.0},      # Low vol: viser plus loin
            "moderate": {"tp1": 1.5, "tp2": 2.5},  # Moderate: équilibré
            "high": {"tp1": 1.2, "tp2": 2.0}       # High vol: prendre profits plus tôt
        }

        multipliers = TP_MULTIPLIERS.get(vol_bucket, {"tp1": 1.5, "tp2": 2.5})

        # Calculate risk
        risk = current_price - stop_loss

        # Calculate TP based on risk multiples (volatility-adaptive)
        tp1_calculated = current_price + (risk * multipliers["tp1"])
        tp2_calculated = current_price + (risk * multipliers["tp2"])

        # Override with technical resistance if better
        if sr_levels and "resistance1" in sr_levels:
            tp1 = max(tp1_calculated, sr_levels["resistance1"])
        else:
            tp1 = tp1_calculated

        if sr_levels and "resistance2" in sr_levels:
            tp2 = max(tp2_calculated, sr_levels["resistance2"])
        else:
            tp2 = tp2_calculated

        # Risk/Reward calculation
        risk = current_price - stop_loss
        reward_tp1 = tp1 - current_price
        reward_tp2 = tp2 - current_price

        rr_tp1 = reward_tp1 / risk if risk > 0 else 0
        rr_tp2 = reward_tp2 / risk if risk > 0 else 0

        return {
            "current_price": round(current_price, 2),
            "entry_zone": {
                "low": round(entry_low, 2),
                "high": round(entry_high, 2)
            },
            "stop_loss": round(stop_loss, 2),
            "stop_loss_pct": round((stop_loss / current_price - 1) * 100, 1),
            "take_profit_1": round(tp1, 2),
            "take_profit_1_pct": round((tp1 / current_price - 1) * 100, 1),
            "take_profit_2": round(tp2, 2),
            "take_profit_2_pct": round((tp2 / current_price - 1) * 100, 1),
            "risk_reward_tp1": round(rr_tp1, 2),
            "risk_reward_tp2": round(rr_tp2, 2),
            "position_sizing": "50% at TP1, 50% at TP2",
            "timeframe": self.timeframe,
            # Add multi-method stop loss analysis
            "stop_loss_analysis": stop_loss_analysis
        }

    def _calculate_sell_targets(
        self,
        current_price: float,
        sr_levels: Optional[Dict[str, float]],
        volatility: Optional[float],
        price_data: Optional[pd.DataFrame] = None,
        avg_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Calculate targets for SELL recommendations"""

        # For SELL, we want to exit at good price
        # Exit zone: between current and slight discount
        exit_low = current_price * (1 - self.params["entry_buffer"])
        exit_high = current_price * (1 + self.params["entry_buffer"] / 2)

        # Adjust exit zone with resistance if available
        if sr_levels and "resistance1" in sr_levels:
            resistance = sr_levels["resistance1"]
            if resistance > current_price:
                exit_high = min(exit_high, resistance)

        # For sells, we don't have traditional SL/TP
        # But we can suggest "stop-buy" if price recovers strongly
        stop_buy = current_price * (1 + self.params["stop_loss"])  # Re-entry if wrong

        return {
            "current_price": round(current_price, 2),
            "exit_zone": {
                "low": round(exit_low, 2),
                "high": round(exit_high, 2)
            },
            "target_exit": round(exit_high, 2),  # Exit near resistance
            "stop_buy": round(stop_buy, 2),  # Re-enter if price recovers
            "stop_buy_pct": round((stop_buy / current_price - 1) * 100, 1),
            "position_sizing": "Reduce 50-75% on rallies",
            "timeframe": self.timeframe
        }

    def _calculate_hold_targets(
        self,
        current_price: float,
        price_data: Optional[pd.DataFrame] = None,
        avg_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Calculate monitoring levels for HOLD positions"""

        # Calculate stop loss using multi-method approach (useful for monitoring)
        stop_loss_analysis = self.stop_loss_calc.calculate_all_methods(
            current_price=current_price,
            price_data=price_data,
            volatility=None,
            avg_price=avg_price  # Pass avg_price for trailing stop calculation
        )

        # Get volatility bucket and stop loss
        recommended_method = stop_loss_analysis["recommended_method"]
        lower_watch = stop_loss_analysis["stop_loss_levels"][recommended_method]["price"]
        vol_bucket = stop_loss_analysis["stop_loss_levels"][recommended_method].get("volatility_bucket", "moderate")

        # Use same TP multipliers as BUY (for consistency)
        TP_MULTIPLIERS = {
            "low": {"tp1": 2.0, "tp2": 3.0},
            "moderate": {"tp1": 1.5, "tp2": 2.5},
            "high": {"tp1": 1.2, "tp2": 2.0}
        }

        multipliers = TP_MULTIPLIERS.get(vol_bucket, {"tp1": 1.5, "tp2": 2.5})

        # Calculate risk and upper watch (using tp1 multiple)
        risk = current_price - lower_watch
        upper_watch = current_price + (risk * multipliers["tp1"])

        return {
            "current_price": round(current_price, 2),
            "action": "HOLD - Monitor position",
            "upper_watch": round(upper_watch, 2),
            "upper_watch_pct": round((upper_watch / current_price - 1) * 100, 1),
            "lower_watch": round(lower_watch, 2),
            "lower_watch_pct": round((lower_watch / current_price - 1) * 100, 1),
            "guidance": f"Re-evaluate if price breaks above ${upper_watch:.2f} (upgrade to BUY) or below ${lower_watch:.2f} (downgrade to SELL)",
            "timeframe": self.timeframe,
            # Add multi-method stop loss analysis
            "stop_loss_analysis": stop_loss_analysis
        }

    def calculate_position_size(
        self,
        action: str,
        confidence: float,
        portfolio_value: float,
        current_allocation: float,
        sector_weight: float,
        max_position_pct: float = 0.05,  # 5% default max
        max_sector_pct: float = 0.40     # 40% default max sector
    ) -> Dict[str, Any]:
        """
        Calculate suggested position size

        Args:
            action: Recommendation action
            confidence: Confidence level (0-1)
            portfolio_value: Total portfolio value
            current_allocation: Current position size (as % of portfolio)
            sector_weight: Current sector weight
            max_position_pct: Max single position size
            max_sector_pct: Max sector concentration

        Returns:
            Dict with position sizing guidance
        """
        if action in ["STRONG BUY", "BUY"]:
            # Base allocation on confidence
            if action == "STRONG BUY" and confidence > 0.75:
                target_pct = 0.05  # 5% for strong conviction
            elif action == "STRONG BUY":
                target_pct = 0.04  # 4%
            elif confidence > 0.65:
                target_pct = 0.03  # 3%
            else:
                target_pct = 0.02  # 2%

            # Limit by max position size
            target_pct = min(target_pct, max_position_pct)

            # Limit by sector concentration
            sector_remaining = max_sector_pct - sector_weight
            if sector_remaining < target_pct:
                target_pct = max(0, sector_remaining)

            # Calculate dollar amount
            increment_pct = target_pct - current_allocation
            increment_dollars = portfolio_value * increment_pct

            return {
                "action": "ADD",
                "current_allocation_pct": round(current_allocation * 100, 1),
                "target_allocation_pct": round(target_pct * 100, 1),
                "increment_pct": round(increment_pct * 100, 1),
                "increment_dollars": round(increment_dollars, 0),
                "sector_weight": round(sector_weight * 100, 1),
                "sector_limit": round(max_sector_pct * 100, 1),
                "guidance": f"Add ${increment_dollars:.0f} ({increment_pct*100:.1f}% of portfolio)" if increment_dollars > 0 else "Sector limit reached, no room to add"
            }

        elif action in ["STRONG SELL", "SELL"]:
            # Reduce position
            if action == "STRONG SELL":
                reduction_pct = 0.75  # Reduce 75%
            else:
                reduction_pct = 0.50  # Reduce 50%

            reduction_dollars = portfolio_value * current_allocation * reduction_pct

            return {
                "action": "REDUCE",
                "current_allocation_pct": round(current_allocation * 100, 1),
                "reduction_pct": round(reduction_pct * 100, 0),
                "reduction_dollars": round(reduction_dollars, 0),
                "remaining_pct": round(current_allocation * (1 - reduction_pct) * 100, 1),
                "guidance": f"Reduce by ${reduction_dollars:.0f} ({reduction_pct*100:.0f}% of position)"
            }

        else:  # HOLD
            return {
                "action": "HOLD",
                "current_allocation_pct": round(current_allocation * 100, 1),
                "guidance": "Maintain current position size"
            }
