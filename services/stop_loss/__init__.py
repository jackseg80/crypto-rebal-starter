"""
Stop Loss utilities module

Contains generic stop loss calculators that can be used across different asset classes:
- Trailing stop calculator
- Additional stop loss strategies
"""

from .trailing_stop_calculator import TrailingStopCalculator

__all__ = ['TrailingStopCalculator']
