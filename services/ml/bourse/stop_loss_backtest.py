"""
Stop Loss Backtesting - Validate ATR vs Fixed methods on historical data

Simple backtest approach:
1. Load cached OHLC data (from data/cache/bourse/*.parquet)
2. Simulate trades with different stop loss methods
3. Compare performance metrics (win rate, avg P&L, stops hit)

Author: AI System
Date: October 2024
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import logging

from services.ml.bourse.stop_loss_calculator import StopLossCalculator

logger = logging.getLogger(__name__)


class StopLossBacktest:
    """
    Backtest stop loss strategies on historical data
    """

    def __init__(
        self,
        cache_dir: str = "data/cache/bourse",
        market_regime: str = "Bull Market",
        timeframe: str = "short"
    ):
        """
        Initialize backtester

        Args:
            cache_dir: Directory containing parquet cache files
            market_regime: Market regime for ATR multipliers
            timeframe: Trading timeframe (short/medium/long)
        """
        self.cache_dir = Path(cache_dir)
        self.market_regime = market_regime
        self.timeframe = timeframe
        self.calculator = StopLossCalculator(
            timeframe=timeframe,
            market_regime=market_regime
        )

    def load_cached_data(
        self,
        symbol: str,
        lookback_days: int = 180
    ) -> Optional[pd.DataFrame]:
        """
        Load cached OHLC data for a symbol

        Args:
            symbol: Stock ticker (e.g., "AAPL")
            lookback_days: Days of history to load

        Returns:
            DataFrame with OHLC data or None if not found
        """
        try:
            # Find most recent cache file for this symbol
            pattern = f"{symbol}_*_yahoo.parquet"
            cache_files = sorted(self.cache_dir.glob(pattern), reverse=True)

            if not cache_files:
                logger.warning(f"No cache file found for {symbol}")
                return None

            # Load the most recent file
            cache_file = cache_files[0]
            logger.debug(f"Loading {cache_file.name}")

            df = pd.read_parquet(cache_file)

            # NO FILTERING - Use all available data in the cache file
            # The cache file should already contain the requested lookback period
            # Filtering here would reduce the data further, which we don't want

            logger.info(f"Loaded {len(df)} days of data for {symbol} (from {df.index[0]} to {df.index[-1]})")
            return df

        except Exception as e:
            logger.error(f"Failed to load cached data for {symbol}: {e}")
            return None

    def simulate_trades(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        entry_interval_days: int = 7,
        holding_period_days: int = 30,
        stop_method: str = "atr_2x",
        target_gain_pct: float = 0.08
    ) -> List[Dict]:
        """
        Simulate trades with a specific stop loss method

        Strategy:
        - Enter every N days (rolling window)
        - Set stop loss using specified method
        - Exit if stop hit OR target reached OR holding period expired
        - Track P&L for each trade

        Args:
            symbol: Stock ticker
            price_data: OHLC DataFrame
            entry_interval_days: Days between entries
            holding_period_days: Max days to hold
            stop_method: "atr_2x" or "fixed_pct"
            target_gain_pct: Target profit (e.g., 0.08 = 8%)

        Returns:
            List of trade results
        """
        trades = []

        # Generate entry points (every entry_interval_days)
        entry_dates = price_data.index[::entry_interval_days]

        for entry_date in entry_dates:
            try:
                # Get entry price
                entry_price = price_data.loc[entry_date, 'close']

                # Calculate stop loss using specified method
                if stop_method == "atr_2x":
                    # Need at least 14 days of data before entry for ATR calculation
                    lookback_start = entry_date - timedelta(days=20)
                    historical_data = price_data[
                        (price_data.index >= lookback_start) &
                        (price_data.index <= entry_date)
                    ]

                    if len(historical_data) < 15:
                        continue  # Skip if insufficient data

                    atr = self.calculator.calculate_atr(historical_data, period=14)
                    if atr is None:
                        continue

                    stop_loss_price = entry_price - (atr * self.calculator.atr_multiplier)

                elif stop_method == "fixed_pct":
                    fixed_pct = self.calculator.FIXED_STOPS.get(self.timeframe, 0.05)
                    stop_loss_price = entry_price * (1 - fixed_pct)

                else:
                    raise ValueError(f"Unknown stop method: {stop_method}")

                # Calculate target price
                target_price = entry_price * (1 + target_gain_pct)

                # Simulate holding period
                exit_date = entry_date + timedelta(days=holding_period_days)
                holding_data = price_data[
                    (price_data.index > entry_date) &
                    (price_data.index <= exit_date)
                ]

                if holding_data.empty:
                    continue  # No data for holding period

                # Check each day for stop loss or target hit
                exit_reason = "holding_expired"
                exit_price = holding_data.iloc[-1]['close']  # Default: exit at end
                exit_actual_date = holding_data.index[-1]

                for date, row in holding_data.iterrows():
                    # Check if stop loss hit (using low of the day)
                    if row['low'] <= stop_loss_price:
                        exit_reason = "stop_loss"
                        exit_price = stop_loss_price  # Assume filled at stop
                        exit_actual_date = date
                        break

                    # Check if target hit (using high of the day)
                    if row['high'] >= target_price:
                        exit_reason = "target_reached"
                        exit_price = target_price  # Assume filled at target
                        exit_actual_date = date
                        break

                # Calculate P&L
                pnl_pct = (exit_price - entry_price) / entry_price
                pnl_usd = (exit_price - entry_price) * 100  # Assume 100 shares

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
                    "method": stop_method
                })

            except Exception as e:
                logger.warning(f"Failed to simulate trade on {entry_date}: {e}")
                continue

        logger.info(f"Simulated {len(trades)} trades for {symbol} using {stop_method}")
        return trades

    def compare_methods(
        self,
        symbol: str,
        lookback_days: int = 180,
        entry_interval_days: int = 7,
        holding_period_days: int = 30
    ) -> Dict:
        """
        Compare ATR 2x vs Fixed % on a single asset

        Args:
            symbol: Stock ticker
            lookback_days: Days of historical data to use
            entry_interval_days: Days between entries
            holding_period_days: Max holding period

        Returns:
            Dict with comparison results
        """
        logger.info(f"=== Backtesting {symbol} ===")

        # Load data
        price_data = self.load_cached_data(symbol, lookback_days)
        if price_data is None or len(price_data) < 30:
            logger.error(f"Insufficient data for {symbol}")
            return None

        # Simulate with ATR 2x
        atr_trades = self.simulate_trades(
            symbol, price_data,
            entry_interval_days=entry_interval_days,
            holding_period_days=holding_period_days,
            stop_method="atr_2x"
        )

        # Simulate with Fixed %
        fixed_trades = self.simulate_trades(
            symbol, price_data,
            entry_interval_days=entry_interval_days,
            holding_period_days=holding_period_days,
            stop_method="fixed_pct"
        )

        # Calculate metrics
        atr_metrics = self._calculate_metrics(atr_trades)
        fixed_metrics = self._calculate_metrics(fixed_trades)

        result = {
            "symbol": symbol,
            "data_period": {
                "start": price_data.index[0].strftime("%Y-%m-%d"),
                "end": price_data.index[-1].strftime("%Y-%m-%d"),
                "days": len(price_data)
            },
            "atr_2x": atr_metrics,
            "fixed_pct": fixed_metrics,
            "comparison": self._compare_metrics(atr_metrics, fixed_metrics)
        }

        return result

    def _calculate_metrics(self, trades: List[Dict]) -> Dict:
        """
        Calculate performance metrics for a list of trades

        Args:
            trades: List of trade results

        Returns:
            Dict with metrics
        """
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "avg_pnl_pct": 0,
                "total_pnl_usd": 0,
                "stops_hit": 0,
                "stops_hit_pct": 0,
                "targets_reached": 0,
                "targets_reached_pct": 0,
                "avg_holding_days": 0
            }

        df = pd.DataFrame(trades)

        wins = df[df['pnl_pct'] > 0]
        losses = df[df['pnl_pct'] <= 0]

        stops_hit = df[df['exit_reason'] == 'stop_loss']
        targets_reached = df[df['exit_reason'] == 'target_reached']

        return {
            "total_trades": len(df),
            "win_rate": len(wins) / len(df) if len(df) > 0 else 0,
            "avg_pnl_pct": df['pnl_pct'].mean(),
            "total_pnl_usd": df['pnl_usd'].sum(),
            "avg_win": wins['pnl_pct'].mean() if len(wins) > 0 else 0,
            "avg_loss": losses['pnl_pct'].mean() if len(losses) > 0 else 0,
            "stops_hit": len(stops_hit),
            "stops_hit_pct": len(stops_hit) / len(df) if len(df) > 0 else 0,
            "targets_reached": len(targets_reached),
            "targets_reached_pct": len(targets_reached) / len(df) if len(df) > 0 else 0,
            "avg_holding_days": df['holding_days'].mean(),
            "best_trade": df['pnl_pct'].max(),
            "worst_trade": df['pnl_pct'].min()
        }

    def _compare_metrics(self, atr: Dict, fixed: Dict) -> Dict:
        """
        Compare ATR vs Fixed metrics

        Args:
            atr: ATR metrics
            fixed: Fixed metrics

        Returns:
            Dict with comparison
        """
        if atr['total_trades'] == 0 or fixed['total_trades'] == 0:
            return {"winner": "N/A", "reason": "Insufficient trades"}

        # Calculate improvement percentages
        win_rate_diff = (atr['win_rate'] - fixed['win_rate']) * 100
        pnl_diff = atr['total_pnl_usd'] - fixed['total_pnl_usd']
        stops_diff = (fixed['stops_hit_pct'] - atr['stops_hit_pct']) * 100  # Fewer stops = better

        # Determine winner based on total P&L
        winner = "ATR 2x" if atr['total_pnl_usd'] > fixed['total_pnl_usd'] else "Fixed %"
        pnl_improvement = (pnl_diff / abs(fixed['total_pnl_usd'])) * 100 if fixed['total_pnl_usd'] != 0 else 0

        return {
            "winner": winner,
            "pnl_difference_usd": pnl_diff,
            "pnl_improvement_pct": pnl_improvement,
            "win_rate_difference": win_rate_diff,
            "stops_reduction": stops_diff,
            "verdict": self._generate_verdict(atr, fixed, pnl_improvement, win_rate_diff, stops_diff)
        }

    def _generate_verdict(
        self,
        atr: Dict,
        fixed: Dict,
        pnl_improvement: float,
        win_rate_diff: float,
        stops_reduction: float
    ) -> str:
        """
        Generate human-readable verdict

        Args:
            atr: ATR metrics
            fixed: Fixed metrics
            pnl_improvement: % improvement in P&L
            win_rate_diff: Difference in win rate (%)
            stops_reduction: Reduction in premature stops (%)

        Returns:
            Verdict string
        """
        if abs(pnl_improvement) < 5:
            return "No significant difference (<5%) - Both methods perform similarly"

        if pnl_improvement > 0:
            verdict = f"ATR 2x outperforms by {pnl_improvement:.1f}%"
            if stops_reduction > 5:
                verdict += f" - Reduces premature stops by {stops_reduction:.1f}%"
            if win_rate_diff > 2:
                verdict += f" - Higher win rate (+{win_rate_diff:.1f}%)"
            return verdict
        else:
            verdict = f"Fixed % outperforms by {abs(pnl_improvement):.1f}%"
            if stops_reduction < -5:
                verdict += f" - ATR has {abs(stops_reduction):.1f}% MORE premature stops"
            return verdict

    def run_multi_asset_backtest(
        self,
        symbols: List[str],
        lookback_days: int = 180,
        entry_interval_days: int = 7
    ) -> Dict:
        """
        Run backtest on multiple assets

        Args:
            symbols: List of tickers to test
            lookback_days: Days of historical data
            entry_interval_days: Days between entries

        Returns:
            Dict with aggregate results
        """
        results = []

        for symbol in symbols:
            try:
                result = self.compare_methods(
                    symbol,
                    lookback_days=lookback_days,
                    entry_interval_days=entry_interval_days
                )
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Failed to backtest {symbol}: {e}")
                continue

        # Aggregate results
        aggregate = self._aggregate_results(results)

        return {
            "individual_results": results,
            "aggregate": aggregate,
            "test_config": {
                "symbols": symbols,
                "lookback_days": lookback_days,
                "entry_interval_days": entry_interval_days,
                "market_regime": self.market_regime,
                "timeframe": self.timeframe
            }
        }

    def _aggregate_results(self, results: List[Dict]) -> Dict:
        """
        Aggregate results from multiple assets

        Args:
            results: List of individual backtest results

        Returns:
            Aggregated metrics
        """
        if not results:
            return {}

        # Sum total P&L across all assets
        atr_total_pnl = sum(r['atr_2x']['total_pnl_usd'] for r in results)
        fixed_total_pnl = sum(r['fixed_pct']['total_pnl_usd'] for r in results)

        # Average win rates
        atr_avg_wr = np.mean([r['atr_2x']['win_rate'] for r in results])
        fixed_avg_wr = np.mean([r['fixed_pct']['win_rate'] for r in results])

        # Average stops hit
        atr_avg_stops = np.mean([r['atr_2x']['stops_hit_pct'] for r in results])
        fixed_avg_stops = np.mean([r['fixed_pct']['stops_hit_pct'] for r in results])

        # Count winners
        atr_wins = sum(1 for r in results if r['comparison']['winner'] == 'ATR 2x')
        fixed_wins = sum(1 for r in results if r['comparison']['winner'] == 'Fixed %')

        return {
            "assets_tested": len(results),
            "atr_2x": {
                "total_pnl_usd": atr_total_pnl,
                "avg_win_rate": atr_avg_wr,
                "avg_stops_hit_pct": atr_avg_stops,
                "assets_won": atr_wins
            },
            "fixed_pct": {
                "total_pnl_usd": fixed_total_pnl,
                "avg_win_rate": fixed_avg_wr,
                "avg_stops_hit_pct": fixed_avg_stops,
                "assets_won": fixed_wins
            },
            "overall_winner": "ATR 2x" if atr_total_pnl > fixed_total_pnl else "Fixed %",
            "pnl_difference_usd": atr_total_pnl - fixed_total_pnl,
            "pnl_improvement_pct": ((atr_total_pnl - fixed_total_pnl) / abs(fixed_total_pnl) * 100) if fixed_total_pnl != 0 else 0
        }
