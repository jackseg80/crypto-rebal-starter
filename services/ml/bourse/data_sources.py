"""
Data source adapter for stock ML models.
Wraps BourseDataFetcher to provide ML-specific data formatting.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

from services.risk.bourse.data_fetcher import BourseDataFetcher

logger = logging.getLogger(__name__)


class StocksDataSource:
    """
    ML-friendly wrapper around BourseDataFetcher.
    Provides data in the format expected by ML models (same as crypto models).
    """

    def __init__(self):
        self.fetcher = BourseDataFetcher()

    async def get_ohlcv_data(
        self,
        symbol: str,
        lookback_days: int = 365,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Get OHLCV data formatted for ML models.

        Args:
            symbol: Stock ticker (e.g., "AAPL", "MSFT")
            lookback_days: Number of days of history
            end_date: End date (default: now)

        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: DatetimeIndex
        """
        if end_date is None:
            end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        df = await self.fetcher.fetch_historical_prices(
            ticker=symbol,
            start_date=start_date,
            end_date=end_date,
            source="yahoo"
        )

        # ML models expect lowercase column names
        df.columns = [col.lower() for col in df.columns]

        return df

    async def get_multi_asset_data(
        self,
        symbols: List[str],
        lookback_days: int = 365,
        end_date: Optional[datetime] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Get OHLCV data for multiple stocks.

        Args:
            symbols: List of stock tickers
            lookback_days: Number of days of history
            end_date: End date (default: now)

        Returns:
            Dict mapping symbol -> OHLCV DataFrame
        """
        result = {}
        for symbol in symbols:
            try:
                df = await self.get_ohlcv_data(symbol, lookback_days, end_date)
                result[symbol] = df
            except Exception as e:
                logger.error(f"Failed to fetch data for {symbol}: {e}")
                # Continue with other symbols

        return result

    async def get_benchmark_data(
        self,
        benchmark: str = "SPY",
        lookback_days: int = 365,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Get benchmark index data (for market regime detection).

        Args:
            benchmark: Benchmark ticker (default: SPY for S&P500)
            lookback_days: Number of days of history
            end_date: End date

        Returns:
            OHLCV DataFrame for benchmark
        """
        return await self.get_ohlcv_data(benchmark, lookback_days, end_date)

    def calculate_returns(
        self,
        ohlcv_data: pd.DataFrame,
        column: str = 'close'
    ) -> pd.Series:
        """
        Calculate returns from OHLCV data.

        Args:
            ohlcv_data: OHLCV DataFrame
            column: Price column to use

        Returns:
            Series of returns (indexed by date)
        """
        return ohlcv_data[column].pct_change().dropna()

    def get_multi_asset_returns(
        self,
        multi_asset_data: Dict[str, pd.DataFrame],
        column: str = 'close'
    ) -> pd.DataFrame:
        """
        Calculate returns for multiple assets and align dates.

        Args:
            multi_asset_data: Dict of symbol -> OHLCV DataFrame
            column: Price column to use

        Returns:
            DataFrame with columns = symbols, rows = dates, values = returns
        """
        returns_dict = {}
        for symbol, ohlcv in multi_asset_data.items():
            returns_dict[symbol] = self.calculate_returns(ohlcv, column)

        # Align all returns to common dates
        returns_df = pd.DataFrame(returns_dict)
        returns_df = returns_df.dropna()  # Remove rows with missing data

        return returns_df

    def clear_cache(self):
        """Clear data cache."""
        self.fetcher.clear_cache()
        logger.info("StocksDataSource cache cleared")
