"""
Advanced Risk Analytics for Bourse Portfolio

Provides sophisticated risk analysis tools:
- Position-level VaR (marginal & component VaR)
- Correlation matrix & clustering
- Stress testing scenarios
- FX exposure analysis
- Liquidity metrics
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


class AdvancedRiskAnalytics:
    """
    Advanced risk analytics for portfolio management

    Features:
    - Position-level VaR decomposition
    - Correlation analysis with clustering
    - Stress testing (market crash, rate changes, etc.)
    - FX exposure and hedging analysis
    - Liquidity scoring
    """

    def __init__(self):
        self.cache = {}

    # ==================== Position-Level VaR ====================

    def calculate_position_var(
        self,
        positions_returns: Dict[str, pd.Series],
        portfolio_weights: Dict[str, float],
        confidence_level: float = 0.95,
        method: str = "historical"
    ) -> Dict[str, Any]:
        """
        Calculate VaR contribution for each position

        Args:
            positions_returns: Dict of {ticker: returns_series}
            portfolio_weights: Dict of {ticker: weight} (sum = 1.0)
            confidence_level: VaR confidence level
            method: VaR calculation method

        Returns:
            Dict with position-level VaR metrics:
            {
                'position_var': {ticker: var_value},
                'marginal_var': {ticker: marginal_contribution},
                'component_var': {ticker: component_contribution},
                'total_portfolio_var': float,
                'diversification_benefit': float
            }
        """
        try:
            # Align all returns to common dates
            returns_df = pd.DataFrame(positions_returns)
            returns_df = returns_df.dropna()

            if len(returns_df) < 30:
                raise ValueError(f"Insufficient data: only {len(returns_df)} days available")

            # Calculate portfolio returns
            weights_array = np.array([portfolio_weights.get(ticker, 0) for ticker in returns_df.columns])
            portfolio_returns = (returns_df.values @ weights_array)

            # Portfolio VaR
            alpha = 1 - confidence_level
            portfolio_var = np.percentile(portfolio_returns, alpha * 100)

            # Position-level VaR (standalone)
            position_var = {}
            for ticker in returns_df.columns:
                pos_returns = returns_df[ticker].values
                pos_var = np.percentile(pos_returns, alpha * 100)
                position_var[ticker] = float(pos_var * portfolio_weights.get(ticker, 0))

            # Marginal VaR (change in portfolio VaR for small change in position)
            marginal_var = {}
            epsilon = 0.01  # 1% change

            for ticker in returns_df.columns:
                # Increase weight slightly
                weights_modified = weights_array.copy()
                ticker_idx = list(returns_df.columns).index(ticker)
                weights_modified[ticker_idx] += epsilon
                weights_modified = weights_modified / weights_modified.sum()  # Renormalize

                # Calculate new portfolio VaR
                portfolio_returns_modified = (returns_df.values @ weights_modified)
                var_modified = np.percentile(portfolio_returns_modified, alpha * 100)

                # Marginal VaR
                marginal_var[ticker] = float((var_modified - portfolio_var) / epsilon)

            # Component VaR (weight * marginal VaR)
            component_var = {
                ticker: float(portfolio_weights.get(ticker, 0) * marginal_var[ticker])
                for ticker in returns_df.columns
            }

            # Diversification benefit
            sum_standalone_var = sum(abs(v) for v in position_var.values())
            diversification_benefit = sum_standalone_var - abs(portfolio_var)

            result = {
                'position_var': position_var,
                'marginal_var': marginal_var,
                'component_var': component_var,
                'total_portfolio_var': float(portfolio_var),
                'diversification_benefit': float(diversification_benefit),
                'sum_components': float(sum(component_var.values())),
                'method': method,
                'confidence_level': confidence_level,
                'num_positions': len(returns_df.columns),
                'observation_days': len(returns_df)
            }

            logger.info(f"Position-level VaR calculated for {len(returns_df.columns)} positions")
            return result

        except Exception as e:
            logger.error(f"Error calculating position-level VaR: {e}")
            raise

    # ==================== Correlation Analysis ====================

    def calculate_correlation_matrix(
        self,
        positions_returns: Dict[str, pd.Series],
        method: str = "pearson",
        rolling_window: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate correlation matrix between positions

        Args:
            positions_returns: Dict of {ticker: returns_series}
            method: Correlation method ('pearson', 'spearman', 'kendall')
            rolling_window: Optional rolling window for dynamic correlation

        Returns:
            Dict with correlation metrics:
            {
                'correlation_matrix': Dict[ticker, Dict[ticker, correlation]],
                'avg_correlation': float,
                'max_correlation': float,
                'min_correlation': float,
                'clustering': Dict with hierarchical clustering results,
                'timestamp': str
            }
        """
        try:
            # Align returns
            returns_df = pd.DataFrame(positions_returns)
            returns_df = returns_df.dropna()

            if len(returns_df) < 30:
                raise ValueError(f"Insufficient data for correlation: {len(returns_df)} days")

            # Calculate correlation matrix
            if rolling_window:
                corr_matrix = returns_df.rolling(rolling_window).corr().iloc[-len(returns_df.columns):]
            else:
                corr_matrix = returns_df.corr(method=method)

            # Extract upper triangle (exclude diagonal)
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
            upper_triangle = corr_matrix.where(mask)

            # Stats
            correlations = upper_triangle.values[mask]
            avg_corr = float(np.mean(correlations))
            max_corr = float(np.max(correlations))
            min_corr = float(np.min(correlations))

            # Hierarchical clustering
            distance_matrix = 1 - corr_matrix.abs()  # Convert correlation to distance
            linkage_matrix = linkage(squareform(distance_matrix.values), method='ward')

            # Convert to JSON-serializable format
            corr_dict = corr_matrix.to_dict()

            result = {
                'correlation_matrix': corr_dict,
                'avg_correlation': avg_corr,
                'max_correlation': max_corr,
                'min_correlation': min_corr,
                'max_pair': self._find_max_correlation_pair(corr_matrix),
                'min_pair': self._find_min_correlation_pair(corr_matrix),
                'clustering': {
                    'linkage_matrix': linkage_matrix.tolist(),
                    'labels': list(corr_matrix.columns),
                    'method': 'ward'
                },
                'method': method,
                'num_positions': len(returns_df.columns),
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Correlation matrix calculated: avg={avg_corr:.3f}, range=[{min_corr:.3f}, {max_corr:.3f}]")
            return result

        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}")
            raise

    def _find_max_correlation_pair(self, corr_matrix: pd.DataFrame) -> Dict[str, Any]:
        """Find pair with maximum correlation"""
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
        upper_triangle = corr_matrix.where(mask)

        max_val = upper_triangle.max().max()
        for col in upper_triangle.columns:
            if upper_triangle[col].max() == max_val:
                row = upper_triangle[col].idxmax()
                return {
                    'pair': [row, col],
                    'correlation': float(max_val)
                }
        return {'pair': [], 'correlation': 0.0}

    def _find_min_correlation_pair(self, corr_matrix: pd.DataFrame) -> Dict[str, Any]:
        """Find pair with minimum correlation"""
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
        upper_triangle = corr_matrix.where(mask)

        min_val = upper_triangle.min().min()
        for col in upper_triangle.columns:
            if upper_triangle[col].min() == min_val:
                row = upper_triangle[col].idxmin()
                return {
                    'pair': [row, col],
                    'correlation': float(min_val)
                }
        return {'pair': [], 'correlation': 0.0}

    # ==================== Stress Testing ====================

    def run_stress_test(
        self,
        positions_data: Dict[str, Dict[str, float]],  # {ticker: {'current_price': x, 'quantity': y}}
        scenario: str = "market_crash",
        custom_shocks: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Run stress test scenario on portfolio

        Args:
            positions_data: Dict with position details
            scenario: Predefined scenario name or 'custom'
            custom_shocks: Custom price shocks {ticker: shock_pct}

        Returns:
            Dict with stress test results:
            {
                'scenario': str,
                'total_pnl': float,
                'pnl_pct': float,
                'position_impacts': {ticker: {'pnl': x, 'pnl_pct': y}},
                'worst_position': str,
                'best_position': str
            }
        """
        try:
            # Predefined scenarios (generic + historical)
            scenarios = {
                # Generic scenarios
                'market_crash': -0.10,      # -10% across all positions
                'market_rally': 0.10,       # +10% across all positions
                'moderate_selloff': -0.05,  # -5% selloff
                'rate_hike': -0.03,         # -3% (typical rate hike impact)

                # Historical crisis scenarios
                'covid_crash': -0.34,       # COVID-19 Crash (Mars 2020): -34% S&P500
                'financial_crisis_2008': -0.57,  # 2008 Financial Crisis: -57% peak-to-trough
                'dotcom_bubble': -0.78,     # Dot-com Bubble (2000-2002): -78% NASDAQ
                'black_monday_1987': -0.22, # Black Monday (Oct 1987): -22% in 1 day
                'flash_crash_2010': -0.09,  # Flash Crash (May 2010): -9% in minutes
                'brexit_2016': -0.12,       # Brexit Vote (June 2016): -12% FTSE
            }

            # Determine shocks
            if scenario == 'custom' and custom_shocks:
                shocks = custom_shocks
            elif scenario in scenarios:
                shock_pct = scenarios[scenario]
                shocks = {ticker: shock_pct for ticker in positions_data.keys()}
            else:
                raise ValueError(f"Unknown scenario: {scenario}")

            # Calculate impacts
            position_impacts = {}
            total_pnl = 0.0
            total_value_before = 0.0

            for ticker, data in positions_data.items():
                current_price = data.get('current_price', 0)
                quantity = data.get('quantity', 0)
                shock = shocks.get(ticker, 0)

                value_before = current_price * quantity
                value_after = current_price * (1 + shock) * quantity
                pnl = value_after - value_before
                pnl_pct = shock  # Shock is already in percentage

                position_impacts[ticker] = {
                    'pnl': float(pnl),
                    'pnl_pct': float(pnl_pct * 100),  # Convert to percentage
                    'value_before': float(value_before),
                    'value_after': float(value_after),
                    'shock_applied': float(shock)
                }

                total_pnl += pnl
                total_value_before += value_before

            pnl_pct = (total_pnl / total_value_before * 100) if total_value_before > 0 else 0

            # Find worst/best positions
            sorted_positions = sorted(
                position_impacts.items(),
                key=lambda x: x[1]['pnl']
            )
            worst_position = sorted_positions[0][0] if sorted_positions else None
            best_position = sorted_positions[-1][0] if sorted_positions else None

            result = {
                'scenario': scenario,
                'total_pnl': float(total_pnl),
                'pnl_pct': float(pnl_pct),
                'total_value_before': float(total_value_before),
                'total_value_after': float(total_value_before + total_pnl),
                'position_impacts': position_impacts,
                'worst_position': worst_position,
                'best_position': best_position,
                'num_positions': len(positions_data),
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Stress test '{scenario}': Total P&L = ${total_pnl:,.2f} ({pnl_pct:.2f}%)")
            return result

        except Exception as e:
            logger.error(f"Error running stress test: {e}")
            raise

    # ==================== FX Exposure ====================

    def analyze_fx_exposure(
        self,
        positions: List[Dict[str, Any]],
        base_currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Analyze currency exposure in portfolio

        Args:
            positions: List of positions with currency info
            base_currency: Base currency for reporting

        Returns:
            Dict with FX exposure metrics:
            {
                'exposures_by_currency': {currency: {'value': x, 'pct': y, 'num_positions': z}},
                'total_exposure': float,
                'dominant_currency': str,
                'diversification_score': float (0-100),
                'hedging_suggestions': List[str]
            }
        """
        try:
            exposures = {}
            total_value = sum(pos.get('market_value_usd', 0) for pos in positions)

            for pos in positions:
                currency = pos.get('currency', base_currency)
                value = pos.get('market_value_usd', 0)

                if currency not in exposures:
                    exposures[currency] = {
                        'value': 0.0,
                        'pct': 0.0,
                        'num_positions': 0
                    }

                exposures[currency]['value'] += value
                exposures[currency]['num_positions'] += 1

            # Calculate percentages
            for currency in exposures:
                exposures[currency]['pct'] = (exposures[currency]['value'] / total_value * 100) if total_value > 0 else 0

            # Find dominant currency
            dominant = max(exposures.items(), key=lambda x: x[1]['value']) if exposures else (base_currency, {'value': 0, 'pct': 0})
            dominant_currency = dominant[0]
            dominant_pct = dominant[1]['pct']

            # Diversification score (Herfindahl index inverted)
            hhi = sum((exp['pct'] / 100) ** 2 for exp in exposures.values())
            diversification_score = (1 - hhi) * 100  # 0 = concentrated, 100 = diversified

            # Hedging suggestions
            suggestions = []
            for currency, data in exposures.items():
                if currency != base_currency and data['pct'] > 20:
                    suggestions.append(f"Consider hedging {currency} exposure ({data['pct']:.1f}%)")

            if dominant_pct > 50:
                suggestions.append(f"High concentration in {dominant_currency} ({dominant_pct:.1f}%) - diversify or hedge")

            result = {
                'exposures_by_currency': exposures,
                'total_exposure': float(total_value),
                'dominant_currency': dominant_currency,
                'dominant_pct': float(dominant_pct),
                'diversification_score': float(diversification_score),
                'num_currencies': len(exposures),
                'hedging_suggestions': suggestions,
                'base_currency': base_currency,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"FX exposure analyzed: {len(exposures)} currencies, dominant={dominant_currency} ({dominant_pct:.1f}%)")
            return result

        except Exception as e:
            logger.error(f"Error analyzing FX exposure: {e}")
            raise
