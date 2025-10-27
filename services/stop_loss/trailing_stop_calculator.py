"""
Trailing Stop Calculator - Generic Implementation

Can be used for stocks, crypto, commodities, or any asset class.
Calculates trailing stop loss based on unrealized gains to protect winners.

Key Features:
- Adaptive trailing percentage based on gain tiers
- ATH (All-Time High) estimation from price history
- Applicable only to positions with significant unrealized gains
- Designed for long-term positions (legacy holdings)

Author: AI System
Date: October 2025
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class TrailingStopCalculator:
    """
    Calculate trailing stop loss based on unrealized gains.

    Philosophy:
    - Let winners run: Use wider stops for profitable positions
    - Protect capital: Standard stops for recent positions
    - Legacy positions: Special treatment for high-gain holdings

    Gain Tiers (configurable):
    - 0-20%: Use standard stop (not applicable)
    - 20-50%: Trailing 15% from ATH
    - 50-100%: Trailing 20% from ATH
    - 100-500%: Trailing 25% from ATH
    - >500%: Trailing 30% from ATH (legacy positions)
    """

    # Trailing percentages by gain tier (min_gain, max_gain) -> trail_pct
    # None means "not applicable" - use standard stop instead
    TRAILING_TIERS = {
        (0.0, 0.20): None,           # 0-20%: Use standard stop
        (0.20, 0.50): 0.15,          # 20-50%: -15% from ATH
        (0.50, 1.00): 0.20,          # 50-100%: -20% from ATH
        (1.00, 5.00): 0.25,          # 100-500%: -25% from ATH
        (5.00, float('inf')): 0.30   # >500%: -30% from ATH (legacy)
    }

    # Minimum gain threshold for trailing stop to be applicable
    MIN_GAIN_PCT = 0.20  # 20%

    # Lookback period for ATH estimation (days)
    DEFAULT_ATH_LOOKBACK = 365  # 1 year

    def __init__(
        self,
        custom_tiers: Optional[Dict[Tuple[float, float], Optional[float]]] = None,
        min_gain_threshold: float = 0.20,
        ath_lookback_days: int = 365
    ):
        """
        Initialize trailing stop calculator

        Args:
            custom_tiers: Optional custom gain tiers (overrides defaults)
            min_gain_threshold: Minimum unrealized gain (%) to apply trailing stop
            ath_lookback_days: Days to look back for ATH estimation
        """
        self.tiers = custom_tiers if custom_tiers else self.TRAILING_TIERS
        self.min_gain_threshold = min_gain_threshold
        self.ath_lookback_days = ath_lookback_days

    def calculate_trailing_stop(
        self,
        current_price: float,
        avg_price: Optional[float],
        ath: Optional[float] = None,
        price_history: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Calculate trailing stop based on unrealized gains

        Args:
            current_price: Current market price
            avg_price: Average acquisition price (cost basis)
            ath: All-Time High (if known), otherwise estimated from price_history
            price_history: OHLC DataFrame for ATH estimation (columns: 'high', 'close')

        Returns:
            Dict with trailing stop details:
            {
                'applicable': bool,           # Whether trailing stop applies
                'stop_loss': float,           # Stop loss price
                'distance_pct': float,        # Distance from current price (%)
                'unrealized_gain_pct': float, # Current unrealized gain (%)
                'ath': float,                 # All-Time High used
                'ath_estimated': bool,        # Whether ATH was estimated
                'trail_pct': float,           # Trailing percentage from ATH
                'tier': tuple,                # Gain tier applied
                'reasoning': str              # Human-readable explanation
            }

            Returns None if not applicable (no avg_price or insufficient gain)
        """
        # Validate inputs
        if not avg_price or avg_price <= 0:
            logger.debug("Trailing stop not applicable: no avg_price provided")
            return None

        if current_price <= 0:
            logger.warning(f"Invalid current_price: {current_price}")
            return None

        # Calculate unrealized gain
        unrealized_gain_pct = (current_price / avg_price - 1.0) * 100

        # Check if gain is sufficient for trailing stop
        if unrealized_gain_pct < self.min_gain_threshold * 100:
            logger.debug(f"Trailing stop not applicable: gain {unrealized_gain_pct:.1f}% < {self.min_gain_threshold*100}%")
            return {
                'applicable': False,
                'unrealized_gain_pct': unrealized_gain_pct,
                'min_threshold': self.min_gain_threshold * 100,
                'reasoning': f"Gain {unrealized_gain_pct:.1f}% is below {self.min_gain_threshold*100}% threshold"
            }

        # Determine ATH
        ath_estimated = False
        if ath is None or ath <= 0:
            if price_history is not None and len(price_history) > 0:
                ath = self._estimate_ath(price_history, current_price)
                ath_estimated = True
                logger.debug(f"Estimated ATH: ${ath:.2f}")
            else:
                # Fallback: use current price as ATH
                ath = current_price
                ath_estimated = True
                logger.debug("No price history, using current price as ATH")

        # Ensure ATH is at least current price
        ath = max(ath, current_price)

        # Find applicable tier
        tier, trail_pct = self._find_tier(unrealized_gain_pct / 100)

        if trail_pct is None:
            logger.debug(f"Trailing stop not applicable for tier {tier}")
            return {
                'applicable': False,
                'unrealized_gain_pct': unrealized_gain_pct,
                'tier': tier,
                'reasoning': f"Gain {unrealized_gain_pct:.1f}% is in tier that uses standard stop"
            }

        # Calculate trailing stop
        stop_loss = ath * (1 - trail_pct)
        distance_pct = (stop_loss / current_price - 1) * 100

        # Build reasoning message
        tier_desc = self._get_tier_description(tier, trail_pct)
        reasoning = (
            f"Legacy position with +{unrealized_gain_pct:.0f}% gain. "
            f"{tier_desc}. "
            f"ATH: ${ath:.2f} {'(estimated)' if ath_estimated else '(provided)'}. "
            f"Stop loss: ${stop_loss:.2f} ({trail_pct*100:.0f}% trailing from ATH)"
        )

        logger.info(f"Trailing stop calculated: {reasoning}")

        return {
            'applicable': True,
            'stop_loss': round(stop_loss, 2),
            'distance_pct': round(distance_pct, 1),
            'unrealized_gain_pct': round(unrealized_gain_pct, 1),
            'ath': round(ath, 2),
            'ath_estimated': ath_estimated,
            'trail_pct': trail_pct,
            'tier': tier,
            'reasoning': reasoning
        }

    def _estimate_ath(
        self,
        price_history: pd.DataFrame,
        current_price: float
    ) -> float:
        """
        Estimate All-Time High from price history

        Uses rolling maximum over lookback period.
        Default 1 year to balance recency vs historical maximum.

        Args:
            price_history: OHLC DataFrame (expected columns: 'high', 'close')
            current_price: Current price

        Returns:
            Estimated ATH
        """
        try:
            if price_history is None or len(price_history) == 0:
                return current_price

            # Use 'high' column if available (more accurate for ATH)
            if 'high' in price_history.columns:
                price_col = 'high'
            elif 'close' in price_history.columns:
                price_col = 'close'
            else:
                logger.warning("Price history missing 'high' and 'close' columns")
                return current_price

            # Get recent history (lookback period)
            recent_history = price_history.tail(self.ath_lookback_days)

            if len(recent_history) == 0:
                return current_price

            # Calculate ATH from recent history
            ath = float(recent_history[price_col].max())

            # Ensure ATH is at least current price (can't be lower)
            ath = max(ath, current_price)

            logger.debug(f"ATH estimated from {len(recent_history)} days: ${ath:.2f}")
            return ath

        except Exception as e:
            logger.error(f"Error estimating ATH: {e}")
            return current_price

    def _find_tier(
        self,
        gain_ratio: float
    ) -> Tuple[Tuple[float, float], Optional[float]]:
        """
        Find the applicable gain tier for a given gain ratio

        Args:
            gain_ratio: Unrealized gain as ratio (e.g., 2.40 for +240%)

        Returns:
            Tuple of (tier_bounds, trail_pct)
        """
        for tier_bounds, trail_pct in self.tiers.items():
            min_gain, max_gain = tier_bounds
            if min_gain <= gain_ratio < max_gain:
                return tier_bounds, trail_pct

        # Fallback: use highest tier
        max_tier = max(self.tiers.keys(), key=lambda t: t[0])
        return max_tier, self.tiers[max_tier]

    def _get_tier_description(
        self,
        tier: Tuple[float, float],
        trail_pct: float
    ) -> str:
        """
        Get human-readable description of a tier

        Args:
            tier: Tier bounds (min, max)
            trail_pct: Trailing percentage

        Returns:
            Description string
        """
        min_gain, max_gain = tier

        if max_gain == float('inf'):
            tier_name = f">{min_gain*100:.0f}% (Legacy)"
        else:
            tier_name = f"{min_gain*100:.0f}-{max_gain*100:.0f}%"

        return f"Tier: {tier_name}, Trailing {trail_pct*100:.0f}% from ATH"

    def is_legacy_position(
        self,
        current_price: float,
        avg_price: Optional[float],
        legacy_threshold: float = 1.0  # 100% gain
    ) -> bool:
        """
        Determine if a position is a "legacy" (long-term winner)

        Args:
            current_price: Current market price
            avg_price: Average acquisition price
            legacy_threshold: Gain ratio threshold (default 1.0 = 100%)

        Returns:
            True if position is a legacy holding
        """
        if not avg_price or avg_price <= 0:
            return False

        gain_ratio = current_price / avg_price - 1.0
        return gain_ratio >= legacy_threshold
