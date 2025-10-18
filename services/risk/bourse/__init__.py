"""
Bourse (Stock Market) Risk Analytics Module
Provides risk metrics and analytics for traditional assets (stocks, ETFs, CFDs, bonds)
"""

from .metrics import (
    calculate_var_historical,
    calculate_var_parametric,
    calculate_var_montecarlo,
    calculate_volatility,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_beta,
    calculate_risk_score
)

from .data_fetcher import BourseDataFetcher
from .calculator import BourseRiskCalculator

__all__ = [
    'calculate_var_historical',
    'calculate_var_parametric',
    'calculate_var_montecarlo',
    'calculate_volatility',
    'calculate_sharpe_ratio',
    'calculate_sortino_ratio',
    'calculate_max_drawdown',
    'calculate_beta',
    'calculate_risk_score',
    'BourseDataFetcher',
    'BourseRiskCalculator'
]
