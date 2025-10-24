"""
Stop Loss Backtest V2 - Fair Comparison

Compares:
1. ATR 2x (adapts to volatility)
2. Fixed 5% (same for all - UNFAIR)
3. Fixed Variable (adapts to volatility - FAIR comparison)

This is the proper test we should have done from the start.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path
import logging

from services.ml.bourse.stop_loss_backtest import StopLossBacktest

logger = logging.getLogger(__name__)


class StopLossBacktestV2(StopLossBacktest):
    """
    Enhanced backtest that includes Fixed Variable method
    """

    # Fixed stops by VOLATILITY (not timeframe)
    FIXED_BY_VOLATILITY = {
        "high": 0.08,      # 8% for vol > 40%
        "moderate": 0.06,  # 6% for vol 25-40%
        "low": 0.04        # 4% for vol < 25%
    }

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
            logger.warning(f"Failed to calculate volatility: {e}")
            return "moderate"  # Default

    def simulate_trades_fixed_variable(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        entry_interval_days: int = 7,
        holding_period_days: int = 30,
        target_gain_pct: float = 0.08
    ) -> List[Dict]:
        """
        Simulate trades with Fixed Variable stop (adapts to volatility)

        Args:
            symbol: Stock ticker
            price_data: OHLC DataFrame
            entry_interval_days: Days between entries
            holding_period_days: Max days to hold
            target_gain_pct: Target profit

        Returns:
            List of trade results
        """
        trades = []

        # Determine volatility bucket
        vol_bucket = self.get_volatility_bucket(price_data)
        fixed_pct = self.FIXED_BY_VOLATILITY[vol_bucket]

        logger.info(f"{symbol} volatility bucket: {vol_bucket} → Fixed stop: {fixed_pct*100:.0f}%")

        # Generate entry points
        entry_dates = price_data.index[::entry_interval_days]

        for entry_date in entry_dates:
            try:
                entry_price = price_data.loc[entry_date, 'close']
                stop_loss_price = entry_price * (1 - fixed_pct)
                target_price = entry_price * (1 + target_gain_pct)

                # Simulate holding period
                from datetime import timedelta
                exit_date = entry_date + timedelta(days=holding_period_days)
                holding_data = price_data[
                    (price_data.index > entry_date) &
                    (price_data.index <= exit_date)
                ]

                if holding_data.empty:
                    continue

                # Check for stop/target
                exit_reason = "holding_expired"
                exit_price = holding_data.iloc[-1]['close']
                exit_actual_date = holding_data.index[-1]

                for date, row in holding_data.iterrows():
                    if row['low'] <= stop_loss_price:
                        exit_reason = "stop_loss"
                        exit_price = stop_loss_price
                        exit_actual_date = date
                        break

                    if row['high'] >= target_price:
                        exit_reason = "target_reached"
                        exit_price = target_price
                        exit_actual_date = date
                        break

                # Calculate P&L
                pnl_pct = (exit_price - entry_price) / entry_price
                pnl_usd = (exit_price - entry_price) * 100

                trades.append({
                    "symbol": symbol,
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "stop_loss_price": stop_loss_price,
                    "target_price": target_price,
                    "exit_date": exit_actual_date,
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "pnl_pct": pnl_pct,
                    "pnl_usd": pnl_usd,
                    "holding_days": (exit_actual_date - entry_date).days,
                    "method": f"fixed_var_{vol_bucket}",
                    "stop_pct": fixed_pct
                })

            except Exception as e:
                logger.warning(f"Failed to simulate trade on {entry_date}: {e}")
                continue

        logger.info(f"Simulated {len(trades)} trades for {symbol} using fixed_variable")
        return trades

    def compare_three_methods(
        self,
        symbol: str,
        lookback_days: int = 180,
        entry_interval_days: int = 7,
        holding_period_days: int = 30
    ) -> Dict:
        """
        Compare ATR 2x vs Fixed 5% vs Fixed Variable

        Args:
            symbol: Stock ticker
            lookback_days: Days of historical data
            entry_interval_days: Days between entries
            holding_period_days: Max holding period

        Returns:
            Dict with 3-way comparison
        """
        logger.info(f"=== Backtesting {symbol} (3 methods) ===")

        # Load data
        price_data = self.load_cached_data(symbol, lookback_days)
        if price_data is None or len(price_data) < 30:
            logger.error(f"Insufficient data for {symbol}")
            return None

        # Method 1: ATR 2x
        atr_trades = self.simulate_trades(
            symbol, price_data,
            entry_interval_days=entry_interval_days,
            holding_period_days=holding_period_days,
            stop_method="atr_2x"
        )

        # Method 2: Fixed 5% (unfair)
        fixed_trades = self.simulate_trades(
            symbol, price_data,
            entry_interval_days=entry_interval_days,
            holding_period_days=holding_period_days,
            stop_method="fixed_pct"
        )

        # Method 3: Fixed Variable (fair comparison)
        fixed_var_trades = self.simulate_trades_fixed_variable(
            symbol, price_data,
            entry_interval_days=entry_interval_days,
            holding_period_days=holding_period_days
        )

        # Calculate metrics
        atr_metrics = self._calculate_metrics(atr_trades)
        fixed_metrics = self._calculate_metrics(fixed_trades)
        fixed_var_metrics = self._calculate_metrics(fixed_var_trades)

        return {
            "symbol": symbol,
            "data_period": {
                "start": price_data.index[0].strftime("%Y-%m-%d"),
                "end": price_data.index[-1].strftime("%Y-%m-%d"),
                "days": len(price_data)
            },
            "atr_2x": atr_metrics,
            "fixed_5pct": fixed_metrics,
            "fixed_variable": fixed_var_metrics,
            "comparison": self._compare_three(atr_metrics, fixed_metrics, fixed_var_metrics)
        }

    def _compare_three(self, atr: Dict, fixed: Dict, fixed_var: Dict) -> Dict:
        """Compare 3 methods"""
        if atr['total_trades'] == 0:
            return {"winner": "N/A", "reason": "Insufficient trades"}

        pnls = {
            "ATR 2x": atr['total_pnl_usd'],
            "Fixed 5%": fixed['total_pnl_usd'],
            "Fixed Variable": fixed_var['total_pnl_usd']
        }

        winner = max(pnls, key=pnls.get)
        winner_pnl = pnls[winner]

        return {
            "winner": winner,
            "pnl_atr": atr['total_pnl_usd'],
            "pnl_fixed": fixed['total_pnl_usd'],
            "pnl_fixed_var": fixed_var['total_pnl_usd'],
            "best_pnl": winner_pnl,
            "verdict": self._generate_three_way_verdict(pnls)
        }

    def _generate_three_way_verdict(self, pnls: Dict) -> str:
        """Generate verdict for 3-way comparison"""
        sorted_methods = sorted(pnls.items(), key=lambda x: x[1], reverse=True)

        best = sorted_methods[0]
        second = sorted_methods[1]
        worst = sorted_methods[2]

        improvement_vs_worst = ((best[1] - worst[1]) / abs(worst[1]) * 100) if worst[1] != 0 else 0

        verdict = f"{best[0]} wins with ${best[1]:,.0f}"
        verdict += f" (+{improvement_vs_worst:.1f}% vs worst)"

        return verdict
