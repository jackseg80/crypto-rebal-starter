"""
ML module for traditional stock market (bourse) analytics.

This module reuses the existing crypto ML infrastructure by adapting it for stocks.
Main components:
- StocksMLAdapter: Wrapper to reuse VolatilityPredictor, RegimeDetector, etc.
- StocksDataSource: yfinance adapter to standard OHLCV format
"""

from .stocks_adapter import StocksMLAdapter
from .data_sources import StocksDataSource

__all__ = ['StocksMLAdapter', 'StocksDataSource']
