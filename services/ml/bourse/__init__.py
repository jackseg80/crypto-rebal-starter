"""
ML module for traditional stock market (bourse) analytics.

This module reuses the existing crypto ML infrastructure by adapting it for stocks.
Main components:
- StocksMLAdapter: Wrapper to reuse VolatilityPredictor, RegimeDetector, etc.
- StocksDataSource: yfinance adapter to standard OHLCV format
"""

# Optional imports (some require torch)
__all__ = []

try:
    from .stocks_adapter import StocksMLAdapter
    __all__.append('StocksMLAdapter')
except ImportError:
    pass

try:
    from .data_sources import StocksDataSource
    __all__.append('StocksDataSource')
except ImportError:
    pass
