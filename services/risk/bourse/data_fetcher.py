"""
Data fetcher for bourse (stock market) historical prices
Supports multiple data sources: Saxo API, Yahoo Finance fallback
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class BourseDataFetcher:
    """
    Fetches historical price data for stocks, ETFs, and other traditional assets
    """

    def __init__(self, cache_dir: str = "data/cache/bourse"):
        self.cache_dir = cache_dir
        self.cache = {}  # In-memory cache

    async def fetch_historical_prices(
        self,
        ticker: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        source: str = "yahoo"
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for a ticker

        Args:
            ticker: Stock ticker symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            source: Data source ("saxo", "yahoo", "manual")

        Returns:
            DataFrame with OHLCV data indexed by date
        """
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=365)  # Default 1 year

        cache_key = f"{ticker}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{source}"

        # Check cache
        if cache_key in self.cache:
            logger.debug(f"Using cached data for {ticker}")
            return self.cache[cache_key]

        # Fetch from source
        if source == "yahoo":
            df = await self._fetch_yahoo_finance(ticker, start_date, end_date)
        elif source == "saxo":
            df = await self._fetch_saxo_api(ticker, start_date, end_date)
        elif source == "manual":
            df = self._generate_manual_data(ticker, start_date, end_date)
        else:
            raise ValueError(f"Unknown data source: {source}")

        # Cache result
        self.cache[cache_key] = df

        logger.info(f"Fetched {len(df)} days of data for {ticker} from {source}")
        return df

    async def _fetch_yahoo_finance(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Fetch data from Yahoo Finance API

        Note: This is a simplified implementation. In production, use yfinance library.
        """
        try:
            import yfinance as yf

            # Download data
            data = yf.download(
                ticker,
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                progress=False
            )

            if data.empty:
                raise ValueError(f"No data found for {ticker}")

            # Standardize column names
            df = pd.DataFrame({
                'open': data['Open'],
                'high': data['High'],
                'low': data['Low'],
                'close': data['Close'],
                'volume': data['Volume'],
                'adjusted_close': data['Adj Close']
            })

            return df

        except ImportError:
            logger.warning("yfinance not installed, using manual data")
            return self._generate_manual_data(ticker, start_date, end_date)
        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance data: {e}")
            # Fallback to manual data
            return self._generate_manual_data(ticker, start_date, end_date)

    async def _fetch_saxo_api(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Fetch data from Saxo Bank API

        Note: This requires Saxo API credentials and is currently a placeholder.
        """
        logger.warning("Saxo API not implemented, using manual data fallback")
        return self._generate_manual_data(ticker, start_date, end_date)

    def _generate_manual_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Generate synthetic historical data for testing

        Uses random walk with drift to simulate realistic price movements
        """
        logger.info(f"Generating manual data for {ticker}")

        # Generate date range
        dates = pd.date_range(start=start_date, end=end_date, freq='D')

        # Simulate prices with random walk
        np.random.seed(hash(ticker) % (2**32))  # Consistent seed per ticker

        # Parameters
        initial_price = 100.0
        daily_drift = 0.0005  # ~0.05% daily drift (~13% annual)
        daily_vol = 0.015  # ~1.5% daily vol (~23% annual)

        # Generate returns
        returns = np.random.normal(daily_drift, daily_vol, len(dates))

        # Calculate cumulative prices
        price_levels = initial_price * np.exp(np.cumsum(returns))

        # Generate OHLC from close prices
        opens = price_levels * (1 + np.random.normal(0, 0.002, len(dates)))
        highs = np.maximum(opens, price_levels) * (1 + np.abs(np.random.normal(0, 0.005, len(dates))))
        lows = np.minimum(opens, price_levels) * (1 - np.abs(np.random.normal(0, 0.005, len(dates))))
        closes = price_levels

        # Generate volume
        base_volume = 1000000
        volumes = base_volume * (1 + np.abs(np.random.normal(0, 0.5, len(dates))))

        # Create DataFrame
        df = pd.DataFrame({
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes,
            'adjusted_close': closes  # Simplified: no adjustments
        }, index=dates)

        return df

    async def fetch_benchmark_prices(
        self,
        benchmark: str = "SPY",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch benchmark index prices (e.g., S&P500, NASDAQ)

        Args:
            benchmark: Benchmark ticker (default SPY for S&P500)
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with benchmark prices
        """
        return await self.fetch_historical_prices(benchmark, start_date, end_date)

    def calculate_returns(self, prices: pd.DataFrame, column: str = 'close') -> np.ndarray:
        """
        Calculate simple returns from price series

        Args:
            prices: DataFrame with price data
            column: Column name to use for calculation

        Returns:
            Array of returns
        """
        if column not in prices.columns:
            raise ValueError(f"Column {column} not found in prices DataFrame")

        returns = prices[column].pct_change().dropna().values
        return returns

    def get_last_n_days(self, df: pd.DataFrame, n_days: int) -> pd.DataFrame:
        """
        Get last N days of data

        Args:
            df: Price DataFrame
            n_days: Number of days

        Returns:
            Filtered DataFrame
        """
        return df.tail(n_days)

    def clear_cache(self):
        """Clear the in-memory cache"""
        self.cache.clear()
        logger.info("Cache cleared")
