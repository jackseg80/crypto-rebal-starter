"""
Bourse Risk Calculator - Orchestrates all risk calculations
Main entry point for risk analytics on stock portfolios
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from .metrics import (
    calculate_var_historical,
    calculate_var_parametric,
    calculate_var_montecarlo,
    calculate_volatility,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_beta,
    calculate_risk_score,
    calculate_calmar_ratio
)
from .data_fetcher import BourseDataFetcher

logger = logging.getLogger(__name__)


class BourseRiskCalculator:
    """
    Orchestrates risk calculations for bourse portfolios
    Combines multiple risk metrics into comprehensive risk assessment
    """

    def __init__(self, data_source: str = "yahoo"):
        self.data_fetcher = BourseDataFetcher()
        self.data_source = data_source
        self.cache = {}

    async def calculate_portfolio_risk(
        self,
        positions: List[Dict[str, Any]],
        benchmark: str = "SPY",
        lookback_days: int = 252,
        risk_free_rate: float = 0.03,
        var_method: str = "historical"
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive risk metrics for a portfolio

        Args:
            positions: List of portfolio positions with ticker, quantity, market_value
            benchmark: Benchmark ticker (default SPY for S&P500)
            lookback_days: Historical lookback period
            risk_free_rate: Annual risk-free rate
            var_method: VaR calculation method ("historical", "parametric", "montecarlo")

        Returns:
            Dictionary with comprehensive risk metrics
        """
        logger.info(f"Calculating portfolio risk for {len(positions)} positions")

        try:
            # Calculate total portfolio value
            portfolio_value = sum(pos.get('market_value_usd', 0) for pos in positions)

            if portfolio_value == 0:
                raise ValueError("Portfolio value is zero")

            # Fetch historical data for all positions
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days + 30)  # Extra buffer

            position_data = {}
            for pos in positions:
                ticker = pos.get('ticker') or pos.get('symbol')
                if not ticker:
                    logger.warning(f"Position missing ticker: {pos}")
                    continue

                try:
                    prices = await self.data_fetcher.fetch_historical_prices(
                        ticker,
                        start_date,
                        end_date,
                        source=self.data_source
                    )
                    position_data[ticker] = {
                        'prices': prices,
                        'weight': pos['market_value_usd'] / portfolio_value,
                        'position': pos
                    }
                except Exception as e:
                    logger.error(f"Failed to fetch data for {ticker}: {e}")

            if not position_data:
                raise ValueError("No valid position data fetched")

            # Calculate weighted portfolio returns
            portfolio_returns = self._calculate_portfolio_returns(position_data)

            # Fetch benchmark data
            try:
                benchmark_prices = await self.data_fetcher.fetch_benchmark_prices(
                    benchmark,
                    start_date,
                    end_date
                )
                benchmark_returns = self.data_fetcher.calculate_returns(benchmark_prices)
            except Exception as e:
                logger.warning(f"Failed to fetch benchmark {benchmark}: {e}")
                benchmark_returns = np.zeros(len(portfolio_returns))

            # Calculate risk metrics
            risk_metrics = self._calculate_all_metrics(
                portfolio_returns,
                benchmark_returns,
                portfolio_value,
                risk_free_rate,
                var_method
            )

            # Add metadata
            risk_metrics['metadata'] = {
                'timestamp': datetime.now().isoformat(),
                'portfolio_value': portfolio_value,
                'positions_count': len(positions),
                'lookback_days': lookback_days,
                'risk_free_rate': risk_free_rate,
                'benchmark': benchmark,
                'var_method': var_method
            }

            logger.info(f"Portfolio risk calculated: Score={risk_metrics['risk_score']['risk_score']}")
            return risk_metrics

        except Exception as e:
            logger.error(f"Error calculating portfolio risk: {e}")
            raise

    def _calculate_portfolio_returns(
        self,
        position_data: Dict[str, Dict]
    ) -> np.ndarray:
        """
        Calculate weighted portfolio returns

        Args:
            position_data: Dictionary of position data with prices and weights

        Returns:
            Array of portfolio returns
        """
        # Get common dates across all positions
        all_dates = None
        for ticker, data in position_data.items():
            if all_dates is None:
                all_dates = data['prices'].index
            else:
                all_dates = all_dates.intersection(data['prices'].index)

        if len(all_dates) == 0:
            raise ValueError("No common dates found across positions")

        # Calculate weighted returns
        portfolio_returns = np.zeros(len(all_dates) - 1)  # -1 for pct_change

        for ticker, data in position_data.items():
            prices = data['prices'].loc[all_dates, 'close']
            returns = prices.pct_change().dropna().values
            weight = data['weight']

            portfolio_returns += returns * weight

        return portfolio_returns

    def _calculate_all_metrics(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
        portfolio_value: float,
        risk_free_rate: float,
        var_method: str
    ) -> Dict[str, Any]:
        """
        Calculate all risk metrics

        Args:
            returns: Portfolio returns
            benchmark_returns: Benchmark returns
            portfolio_value: Total portfolio value
            risk_free_rate: Risk-free rate
            var_method: VaR calculation method

        Returns:
            Dictionary with all metrics
        """
        # VaR calculation
        if var_method == "historical":
            var_result = calculate_var_historical(returns, 0.95, portfolio_value)
        elif var_method == "parametric":
            var_result = calculate_var_parametric(returns, 0.95, portfolio_value)
        elif var_method == "montecarlo":
            var_result = calculate_var_montecarlo(returns, 0.95, portfolio_value)
        else:
            raise ValueError(f"Unknown VaR method: {var_method}")

        # Volatility calculations
        vol_30d = calculate_volatility(returns, window=30, annualize=True)
        vol_90d = calculate_volatility(returns, window=90, annualize=True)
        vol_252d = calculate_volatility(returns, window=None, annualize=True)

        # Risk-adjusted returns
        sharpe = calculate_sharpe_ratio(returns, risk_free_rate)
        sortino = calculate_sortino_ratio(returns, risk_free_rate)

        # Reconstruct prices from returns for drawdown
        prices = (1 + returns).cumprod() * 100  # Start at 100

        # Max drawdown
        dd_metrics = calculate_max_drawdown(prices)

        # Beta
        beta = calculate_beta(returns, benchmark_returns)

        # Calmar ratio
        calmar = calculate_calmar_ratio(returns, prices)

        # Composite risk score
        risk_score_result = calculate_risk_score(
            var_result['var_percentage'],
            vol_252d,
            sharpe,
            dd_metrics['max_drawdown'],
            beta
        )

        # Compile results
        return {
            'risk_score': risk_score_result,
            'traditional_risk': {
                'var_95_1d': var_result['var_percentage'],
                'var_monetary': var_result.get('var_monetary', 0),
                'var_method': var_result['method'],
                'volatility_30d': vol_30d,
                'volatility_90d': vol_90d,
                'volatility_252d': vol_252d,
                'sharpe_ratio': sharpe,
                'sortino_ratio': sortino,
                'calmar_ratio': calmar,
                'max_drawdown': dd_metrics['max_drawdown'],
                'max_drawdown_pct': dd_metrics['max_drawdown_pct'],
                'drawdown_days': dd_metrics['drawdown_days'],
                'beta_portfolio': beta
            },
            'concentration': self._calculate_concentration_metrics(returns),
            'alerts': self._generate_alerts(risk_score_result, var_result, vol_30d, dd_metrics)
        }

    def _calculate_concentration_metrics(self, returns: np.ndarray) -> Dict[str, Any]:
        """
        Calculate portfolio concentration metrics

        Note: This is a simplified version. Full implementation would analyze
        actual position weights, sectors, geography, etc.
        """
        # Placeholder for now
        return {
            'top5_pct': 0.0,  # To be calculated from actual positions
            'sector_max_pct': 0.0,
            'geography_us_pct': 0.0
        }

    def _generate_alerts(
        self,
        risk_score: Dict[str, Any],
        var_result: Dict[str, float],
        volatility: float,
        dd_metrics: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Generate risk alerts based on thresholds

        Args:
            risk_score: Risk score result
            var_result: VaR calculation result
            volatility: Current volatility
            dd_metrics: Drawdown metrics

        Returns:
            List of alert dictionaries
        """
        alerts = []

        # High risk score alert
        if risk_score['risk_score'] < 30:
            alerts.append({
                'severity': 'critical',
                'type': 'risk_score',
                'message': f"Critical risk level: Score {risk_score['risk_score']}/100"
            })
        elif risk_score['risk_score'] < 50:
            alerts.append({
                'severity': 'warning',
                'type': 'risk_score',
                'message': f"High risk level: Score {risk_score['risk_score']}/100"
            })

        # High VaR alert
        if var_result['var_percentage'] < -0.03:  # VaR > 3%
            alerts.append({
                'severity': 'warning',
                'type': 'var',
                'message': f"High Value at Risk: {var_result['var_percentage']*100:.2f}% daily loss possible"
            })

        # High volatility alert
        if volatility > 0.30:  # >30% annualized
            alerts.append({
                'severity': 'warning',
                'type': 'volatility',
                'message': f"High volatility: {volatility*100:.1f}% annualized"
            })

        # Deep drawdown alert
        if dd_metrics['max_drawdown'] < -0.20:  # >20% drawdown
            alerts.append({
                'severity': 'warning',
                'type': 'drawdown',
                'message': f"Significant drawdown: {dd_metrics['max_drawdown_pct']:.1f}%"
            })

        return alerts

    async def calculate_position_level_var(
        self,
        positions: List[Dict[str, Any]],
        lookback_days: int = 252
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate VaR contribution for each position

        Args:
            positions: List of positions
            lookback_days: Historical lookback period

        Returns:
            Dictionary mapping ticker to VaR metrics
        """
        position_vars = {}

        for pos in positions:
            ticker = pos.get('ticker') or pos.get('symbol')
            if not ticker:
                continue

            try:
                # Fetch prices
                end_date = datetime.now()
                start_date = end_date - timedelta(days=lookback_days + 30)

                prices = await self.data_fetcher.fetch_historical_prices(
                    ticker,
                    start_date,
                    end_date,
                    source=self.data_source
                )

                # Calculate returns
                returns = self.data_fetcher.calculate_returns(prices)

                # Calculate VaR
                var_result = calculate_var_historical(
                    returns,
                    confidence_level=0.95,
                    portfolio_value=pos['market_value_usd']
                )

                position_vars[ticker] = {
                    'var_percentage': var_result['var_percentage'],
                    'var_monetary': var_result['var_monetary'],
                    'position_value': pos['market_value_usd']
                }

            except Exception as e:
                logger.error(f"Failed to calculate VaR for {ticker}: {e}")

        return position_vars
