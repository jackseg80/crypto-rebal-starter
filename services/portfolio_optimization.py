"""
Advanced Portfolio Optimization Module
Implements Markowitz optimization with crypto-specific constraints
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass
from enum import Enum
from .performance_optimizer import performance_optimizer

logger = logging.getLogger(__name__)

class OptimizationObjective(Enum):
    """Portfolio optimization objectives"""
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_RETURN = "max_return"
    RISK_PARITY = "risk_parity"
    RISK_BUDGETING = "risk_budgeting"
    MEAN_REVERSION = "mean_reversion"
    MULTI_PERIOD = "multi_period"
    BLACK_LITTERMAN = "black_litterman"
    MAX_DIVERSIFICATION = "max_diversification"
    CVAR_OPTIMIZATION = "cvar_optimization"
    EFFICIENT_FRONTIER = "efficient_frontier"

@dataclass
class OptimizationConstraints:
    """Portfolio optimization constraints"""
    min_weight: float = 0.0
    max_weight: float = 1.0
    max_sector_weight: float = 0.5
    min_diversification_ratio: float = 0.3
    max_correlation_exposure: float = 0.7
    target_volatility: Optional[float] = None
    min_expected_return: Optional[float] = None
    risk_budget: Optional[Dict[str, float]] = None
    rebalance_periods: Optional[List[int]] = None  # [30, 90, 180] days for multi-period
    period_weights: Optional[List[float]] = None   # [0.5, 0.3, 0.2] weights for each period
    transaction_costs: Optional[Dict[str, float]] = None  # {"maker_fee": 0.001, "taker_fee": 0.0015, "spread": 0.005}
    
@dataclass
class OptimizationResult:
    """Portfolio optimization result"""
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    diversification_ratio: float
    optimization_score: float
    constraints_satisfied: bool
    risk_contributions: Dict[str, float]
    sector_exposures: Dict[str, float]

class PortfolioOptimizer:
    """Advanced portfolio optimization with crypto-specific features"""
    
    def __init__(self):
        self.risk_free_rate = 0.02  # 2% annual risk-free rate
        self.crypto_sectors = {
            'BTC': ['BTC', 'TBTC', 'WBTC'],
            'ETH': ['ETH', 'WETH', 'STETH', 'WSTETH', 'RETH'],
            'Stablecoins': ['USDT', 'USDC', 'DAI', 'BUSD', 'FRAX'],
            'SOL': ['SOL', 'JUPSOL', 'JITOSOL'],
            'L1/L0 majors': ['ADA', 'AVAX', 'DOT', 'ATOM', 'NEAR', 'FTM', 'ALGO'],
            'L2/Scaling': ['ARB', 'OP', 'MATIC', 'STRK', 'IMX'],
            'DeFi': ['UNI', 'AAVE', 'COMP', 'SNX', 'MKR', 'YFI', 'CRV'],
            'AI/Data': ['FET', 'RENDER', 'OCEAN', 'GRT', 'TAO'],
            'Gaming/NFT': ['SAND', 'MANA', 'AXS', 'GALA', 'ENJ'],
            'Memecoins': ['DOGE', 'SHIB', 'PEPE', 'BONK', 'WIF'],
            'Others': []
        }
        
    def calculate_expected_returns(self, price_history: pd.DataFrame, 
                                 method: str = "mean_reversion") -> pd.Series:
        """Calculate expected returns using various methods"""
        
        if method == "historical":
            # Simple historical mean
            returns = price_history.pct_change().dropna()
            return returns.mean() * 252  # Annualized
            
        elif method == "mean_reversion":
            # Mean reversion model
            returns = price_history.pct_change().dropna()
            current_returns = returns.tail(30).mean() * 252
            long_term_returns = returns.mean() * 252
            
            # Mean reversion factor (stronger reversion for crypto)
            reversion_factor = 0.4
            expected_returns = (1 - reversion_factor) * current_returns + \
                              reversion_factor * long_term_returns
            return expected_returns
            
        elif method == "momentum":
            # Momentum-based expected returns
            returns = price_history.pct_change().dropna()
            short_momentum = returns.tail(30).mean()
            long_momentum = returns.tail(90).mean()
            
            momentum_signal = (short_momentum - long_momentum) * 2
            base_return = returns.mean()
            
            return (base_return + momentum_signal) * 252
            
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def calculate_risk_model(self, price_history: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Calculate covariance matrix and volatilities with crypto adjustments"""
        
        returns = price_history.pct_change().dropna()
        n_assets = price_history.shape[1]
        
        # Use performance optimizer for large portfolios
        if n_assets > 100:
            logger.info(f"Using optimized covariance calculation for {n_assets} assets")
            cov_matrix = performance_optimizer.optimized_covariance_matrix(
                returns, exponential_weight=True, shrinkage=0.2
            )
            volatilities = np.sqrt(np.diag(cov_matrix))
        else:
            # Standard calculation for smaller portfolios
            # Exponential weighting for more recent data
            weights = np.exp(np.linspace(-1, 0, len(returns)))
            weights = weights / weights.sum()
            
            # Weighted covariance matrix
            weighted_returns = returns * np.sqrt(weights[:, np.newaxis])
            cov_matrix = np.cov(weighted_returns.T) * 252  # Annualized
            
            # Volatility adjustment for crypto (higher volatility regime detection)
            volatilities = np.sqrt(np.diag(cov_matrix))
            
            # Correlation matrix with stability adjustments
            corr_matrix = cov_matrix / np.outer(volatilities, volatilities)
            
            # Shrinkage to improve stability
            shrinkage_factor = 0.2
            identity = np.eye(len(corr_matrix))
            stable_corr = (1 - shrinkage_factor) * corr_matrix + shrinkage_factor * identity
            
            # Reconstruct covariance matrix
            cov_matrix = stable_corr * np.outer(volatilities, volatilities)
        
        return pd.DataFrame(cov_matrix, index=returns.columns, columns=returns.columns), \
               pd.Series(volatilities, index=returns.columns)
    
    def optimize_portfolio(self, 
                          expected_returns: pd.Series,
                          cov_matrix: pd.DataFrame,
                          constraints: OptimizationConstraints,
                          objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE,
                          current_weights: Optional[Dict[str, float]] = None) -> OptimizationResult:
        """
        Optimize portfolio with advanced constraints and objectives
        """
        
        assets = expected_returns.index.tolist()
        n_assets = len(assets)
        
        # Initial weights (equal weight or current portfolio)
        if current_weights:
            x0 = np.array([current_weights.get(asset, 1/n_assets) for asset in assets])
        else:
            x0 = np.ones(n_assets) / n_assets
            
        # Bounds for individual weights
        bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n_assets)]
        
        # Constraint functions
        constraint_list = []
        
        # Weights sum to 1
        constraint_list.append({
            'type': 'eq',
            'fun': lambda x: np.sum(x) - 1.0
        })
        
        # Sector constraints
        for sector, symbols in self.crypto_sectors.items():
            sector_indices = [i for i, asset in enumerate(assets) if asset in symbols]
            if sector_indices:
                constraint_list.append({
                    'type': 'ineq', 
                    'fun': lambda x, indices=sector_indices: constraints.max_sector_weight - np.sum(x[indices])
                })
        
        # Diversification constraint
        if constraints.min_diversification_ratio > 0:
            constraint_list.append({
                'type': 'ineq',
                'fun': lambda x: self._calculate_diversification_ratio(x, cov_matrix.values) - constraints.min_diversification_ratio
            })
        
        # Target volatility constraint
        if constraints.target_volatility:
            constraint_list.append({
                'type': 'eq',
                'fun': lambda x: np.sqrt(np.dot(x, np.dot(cov_matrix.values, x))) - constraints.target_volatility
            })
        
        # Minimum expected return constraint  
        if constraints.min_expected_return:
            constraint_list.append({
                'type': 'ineq',
                'fun': lambda x: np.dot(x, expected_returns.values) - constraints.min_expected_return
            })
            
        # Maximum correlation exposure constraint
        if constraints.max_correlation_exposure and constraints.max_correlation_exposure < 1.0:
            corr_matrix = self._calculate_correlation_matrix(cov_matrix)
            constraint_list.append({
                'type': 'ineq',
                'fun': lambda x: constraints.max_correlation_exposure - self._calculate_correlation_exposure(x, corr_matrix)
            })
        
        # Objective function with numerical robustness
        def objective_function(x):
            portfolio_return = np.dot(x, expected_returns.values)
            portfolio_variance = np.dot(x, np.dot(cov_matrix.values, x))
            portfolio_volatility = np.sqrt(max(portfolio_variance, 1e-12))  # Avoid sqrt(0)
            
            # Base objective value
            base_objective = 0.0
            
            if objective == OptimizationObjective.MAX_SHARPE:
                # Robust Sharpe ratio calculation
                if portfolio_volatility <= 1e-12:
                    base_objective = 1e6  # Penalize zero volatility
                else:
                    base_objective = -(portfolio_return - self.risk_free_rate) / portfolio_volatility
            elif objective == OptimizationObjective.MIN_VARIANCE:
                base_objective = portfolio_variance
            elif objective == OptimizationObjective.MAX_RETURN:
                base_objective = -portfolio_return
            elif objective == OptimizationObjective.RISK_PARITY:
                base_objective = self._risk_parity_objective(x, cov_matrix.values)
            elif objective == OptimizationObjective.RISK_BUDGETING:
                # Default risk budget if none provided
                default_risk_budget = {'BTC': 0.4, 'ETH': 0.3, 'SOL': 0.1, 'Stablecoins': 0.05, 'L1/L0 majors': 0.1, 'Others': 0.05}
                risk_budget = getattr(constraints, 'risk_budget', None) or default_risk_budget
                base_objective = self._risk_budgeting_objective(x, cov_matrix.values, risk_budget, assets)
            elif objective == OptimizationObjective.MEAN_REVERSION:
                base_objective = self._mean_reversion_objective(x, expected_returns.values, cov_matrix.values)
            elif objective == OptimizationObjective.BLACK_LITTERMAN:
                # For Black-Litterman, the expected returns are already adjusted, so use max Sharpe
                if portfolio_volatility <= 1e-12:
                    base_objective = 1e6
                else:
                    base_objective = -(portfolio_return - self.risk_free_rate) / portfolio_volatility
            elif objective == OptimizationObjective.MAX_DIVERSIFICATION:
                # Maximize diversification ratio: weighted individual vols / portfolio vol
                individual_vols = np.sqrt(np.diag(cov_matrix.values))
                weighted_vol = np.dot(x, individual_vols)
                base_objective = -weighted_vol / portfolio_volatility if portfolio_volatility > 1e-12 else 1e6
            elif objective == OptimizationObjective.CVAR_OPTIMIZATION:
                # Minimize Conditional Value at Risk (simplified approximation)
                # CVaR ≈ -1.645 * σ for normal distribution at 95% confidence
                cvar_estimate = 1.645 * portfolio_volatility
                base_objective = cvar_estimate + 0.1 * portfolio_variance
            
            # Add transaction cost penalty if current weights provided and transaction costs enabled
            transaction_penalty = 0.0
            if (current_weights and 
                constraints.transaction_costs and 
                len(current_weights) == len(x)):
                
                current_weights_array = np.array([current_weights.get(asset, 0) for asset in assets])
                transaction_penalty = self._calculate_transaction_cost_penalty(
                    x, current_weights_array, constraints.transaction_costs
                )
            
            return base_objective + transaction_penalty
        
        # Optimization
        result = minimize(
            objective_function,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraint_list,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )
        
        if not result.success:
            logger.warning(f"Optimization failed: {result.message}")
            # Intelligent fallback instead of equal weights
            if current_weights:
                # Normalize current weights if available
                current_weights_array = np.array([current_weights.get(asset, 0) for asset in assets])
                if np.sum(current_weights_array) > 0:
                    optimal_weights = current_weights_array / np.sum(current_weights_array)
                else:
                    optimal_weights = self._create_smart_fallback_weights(expected_returns.values)
            else:
                # Weight assets proportionally to positive expected returns
                optimal_weights = self._create_smart_fallback_weights(expected_returns.values)
        else:
            optimal_weights = result.x
            
        # Calculate result metrics
        weights_dict = {asset: weight for asset, weight in zip(assets, optimal_weights)}
        
        portfolio_return = np.dot(optimal_weights, expected_returns.values)
        portfolio_variance = np.dot(optimal_weights, np.dot(cov_matrix.values, optimal_weights))
        portfolio_volatility = np.sqrt(max(portfolio_variance, 1e-12))  # Numerical stability
        
        # Robust Sharpe ratio calculation
        if portfolio_volatility <= 1e-12:
            sharpe_ratio = 0.0  # Force zero for degenerate portfolios
        else:
            sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_volatility
        
        # Risk contributions
        risk_contributions = {}
        for i, asset in enumerate(assets):
            marginal_risk = np.dot(cov_matrix.values[i], optimal_weights)
            risk_contributions[asset] = optimal_weights[i] * marginal_risk / portfolio_variance
        
        # Sector exposures
        sector_exposures = {}
        for sector, symbols in self.crypto_sectors.items():
            sector_weight = sum(weights_dict.get(symbol, 0) for symbol in symbols)
            if sector_weight > 0:
                sector_exposures[sector] = sector_weight
        
        # Constraints satisfaction check
        constraints_satisfied = self._check_constraints_satisfaction(
            optimal_weights, constraints, assets
        )
        
        diversification_ratio = self._calculate_diversification_ratio(
            optimal_weights, cov_matrix.values
        )
        
        return OptimizationResult(
            weights=weights_dict,
            expected_return=portfolio_return,
            volatility=portfolio_volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=0.0,  # Would need historical simulation
            diversification_ratio=diversification_ratio,
            optimization_score=sharpe_ratio * diversification_ratio,
            constraints_satisfied=constraints_satisfied,
            risk_contributions=risk_contributions,
            sector_exposures=sector_exposures
        )
    
    def _calculate_diversification_ratio(self, weights: np.ndarray, cov_matrix: np.ndarray) -> float:
        """Calculate diversification ratio"""
        individual_vols = np.sqrt(np.diag(cov_matrix))
        weighted_vol = np.dot(weights, individual_vols)
        portfolio_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
        
        return weighted_vol / portfolio_vol if portfolio_vol > 0 else 0.0
    
    def _calculate_risk_contributions(self, weights: np.ndarray, cov_matrix: np.ndarray, assets: List[str] = None) -> Dict[str, float]:
        """Calculate risk contributions for each asset"""
        portfolio_variance = np.dot(weights, np.dot(cov_matrix, weights))
        
        if portfolio_variance == 0:
            return {}
            
        marginal_risks = np.dot(cov_matrix, weights)
        risk_contributions = {}
        
        for i in range(len(weights)):
            asset_name = assets[i] if assets and i < len(assets) else f"asset_{i}"
            risk_contributions[asset_name] = weights[i] * marginal_risks[i] / portfolio_variance
        
        return risk_contributions
    
    def _calculate_transaction_cost_penalty(self, target_weights: np.ndarray, 
                                          current_weights: np.ndarray,
                                          transaction_costs: Dict[str, float],
                                          portfolio_value: float = 100000) -> float:
        """Calculate transaction cost penalty for rebalancing"""
        
        # Default transaction costs
        maker_fee = transaction_costs.get('maker_fee', 0.001)  # 0.1%
        taker_fee = transaction_costs.get('taker_fee', 0.0015)  # 0.15%
        spread_cost = transaction_costs.get('spread', 0.005)  # 0.5% bid-ask spread impact
        
        total_cost = 0.0
        
        for i in range(len(target_weights)):
            weight_change = abs(target_weights[i] - current_weights[i])
            
            if weight_change > 0.001:  # Only count significant changes (>0.1%)
                # Trade amount in USD
                trade_amount = weight_change * portfolio_value
                
                # Trading fee (average of maker/taker)
                avg_fee = (maker_fee + taker_fee) / 2
                
                # Total cost = fee + spread impact
                trade_cost = trade_amount * (avg_fee + spread_cost)
                total_cost += trade_cost
        
        # Normalize cost as percentage of portfolio
        normalized_cost = total_cost / portfolio_value
        
        # Scale penalty (costs reduce returns)
        return normalized_cost * 10  # Amplify impact for optimization
    
    def _risk_parity_objective(self, weights: np.ndarray, cov_matrix: np.ndarray) -> float:
        """Risk parity objective function"""
        portfolio_variance = np.dot(weights, np.dot(cov_matrix, weights))
        
        if portfolio_variance == 0:
            return 1e6
            
        marginal_risks = np.dot(cov_matrix, weights)
        risk_contributions = weights * marginal_risks / portfolio_variance
        
        # Minimize variance of risk contributions
        target_risk_contrib = 1.0 / len(weights)
        return np.sum((risk_contributions - target_risk_contrib) ** 2)
    
    def _mean_reversion_objective(self, weights: np.ndarray, 
                                expected_returns: np.ndarray, 
                                cov_matrix: np.ndarray) -> float:
        """Mean reversion objective with risk penalty"""
        portfolio_return = np.dot(weights, expected_returns)
        portfolio_variance = np.dot(weights, np.dot(cov_matrix, weights))
        
        # Higher penalty for concentrated positions (mean reversion works better diversified)
        concentration_penalty = np.sum(weights ** 2) * 0.1
        
        return -(portfolio_return - 0.5 * portfolio_variance) + concentration_penalty
    
    def _risk_budgeting_objective(self, weights: np.ndarray, 
                                cov_matrix: np.ndarray,
                                risk_budget: Dict[str, float],
                                assets: List[str]) -> float:
        """Risk budgeting objective with custom sector allocations"""
        portfolio_variance = np.dot(weights, np.dot(cov_matrix, weights))
        
        if portfolio_variance == 0:
            return 1e6
            
        # Calculate risk contributions
        marginal_risks = np.dot(cov_matrix, weights)
        risk_contributions = weights * marginal_risks / portfolio_variance
        
        # Map assets to risk budget categories
        asset_risk_budgets = np.ones(len(assets)) / len(assets)  # Default equal budget
        
        for i, asset in enumerate(assets):
            # Sector mapping for crypto assets
            if asset in ['BTC', 'TBTC', 'WBTC']:
                asset_risk_budgets[i] = risk_budget.get('BTC', 0.4)
            elif asset in ['ETH', 'WSTETH', 'STETH', 'RETH', 'WETH']:
                asset_risk_budgets[i] = risk_budget.get('ETH', 0.3)
            elif asset in ['SOL', 'JUPSOL', 'JITOSOL']:
                asset_risk_budgets[i] = risk_budget.get('SOL', 0.1)
            elif asset in ['USDT', 'USDC', 'DAI', 'USD', 'EUR']:
                asset_risk_budgets[i] = risk_budget.get('Stablecoins', 0.05)
            elif asset in ['ADA', 'ATOM', 'DOT', 'AVAX', 'NEAR', 'TAO']:
                asset_risk_budgets[i] = risk_budget.get('L1/L0 majors', 0.1)
            else:
                asset_risk_budgets[i] = risk_budget.get('Others', 0.05)
        
        # Normalize budgets to sum to 1
        asset_risk_budgets = asset_risk_budgets / np.sum(asset_risk_budgets)
        
        # Minimize squared deviations from target risk budgets
        return np.sum((risk_contributions - asset_risk_budgets) ** 2)
    
    def _multi_period_objective(self, weights: np.ndarray, 
                              expected_returns_dict: Dict[str, np.ndarray], 
                              cov_matrices_dict: Dict[str, np.ndarray],
                              period_weights: List[float]) -> float:
        """Multi-period optimization combining multiple time horizons"""
        
        total_objective = 0.0
        
        for i, (period, period_weight) in enumerate(zip(expected_returns_dict.keys(), period_weights)):
            expected_returns = expected_returns_dict[period]
            cov_matrix = cov_matrices_dict[period]
            
            # Calculate period-specific metrics
            portfolio_return = np.dot(weights, expected_returns)
            portfolio_variance = np.dot(weights, np.dot(cov_matrix, weights))
            portfolio_volatility = np.sqrt(max(portfolio_variance, 1e-12))
            
            # Sharpe ratio for this period (negative because we minimize)
            if portfolio_volatility <= 1e-12:
                period_sharpe = -1e6  # Penalize zero volatility
            else:
                period_sharpe = -(portfolio_return - self.risk_free_rate) / portfolio_volatility
            
            # Weight by period importance
            total_objective += period_weight * period_sharpe
        
        # Add stability penalty for extreme allocations
        concentration_penalty = np.sum(weights ** 2) * 0.05
        
        return total_objective + concentration_penalty
    
    def optimize_large_portfolio(self, price_history: pd.DataFrame,
                               constraints: OptimizationConstraints,
                               objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE,
                               current_weights: Optional[Dict[str, float]] = None,
                               max_assets: int = 200) -> OptimizationResult:
        """Optimized portfolio optimization for large portfolios (500+ assets)"""
        
        logger.info(f"Starting large portfolio optimization with {price_history.shape[1]} assets")
        
        # Preprocess and filter assets for performance
        preprocessed = performance_optimizer.batch_optimization_preprocessing(
            price_history, max_assets=max_assets
        )
        
        # Use optimized covariance calculation
        expected_returns = pd.Series(
            preprocessed['expected_returns'], 
            index=preprocessed['assets']
        )
        cov_matrix = pd.DataFrame(
            preprocessed['cov_matrix'],
            index=preprocessed['assets'],
            columns=preprocessed['assets']
        )
        
        logger.info(f"Filtered to {len(preprocessed['assets'])} assets for optimization")
        
        # Filter current weights to match selected assets
        if current_weights:
            filtered_current_weights = {
                asset: current_weights.get(asset, 0) 
                for asset in preprocessed['assets']
            }
        else:
            filtered_current_weights = None
        
        # Run standard optimization on filtered data
        result = self.optimize_portfolio(
            expected_returns=expected_returns,
            cov_matrix=cov_matrix,
            constraints=constraints,
            objective=objective,
            current_weights=filtered_current_weights
        )
        
        # Extend result to include all original assets (zero weights for excluded)
        all_assets = price_history.columns.tolist()
        extended_weights = {}
        
        for asset in all_assets:
            if asset in result.weights:
                extended_weights[asset] = result.weights[asset]
            else:
                extended_weights[asset] = 0.0
        
        # Update result with extended weights
        result.weights = extended_weights
        
        logger.info(f"Large portfolio optimization completed: {len([w for w in extended_weights.values() if w > 0.001])} assets with meaningful weights")
        
        return result
    
    def optimize_multi_period(self, price_history: pd.DataFrame, 
                            constraints: OptimizationConstraints,
                            current_weights: Optional[Dict[str, float]] = None) -> OptimizationResult:
        """Multi-period portfolio optimization"""
        
        # Default periods and weights if not specified
        periods = constraints.rebalance_periods or [30, 90, 180]  # Short, medium, long-term
        period_weights = constraints.period_weights or [0.5, 0.3, 0.2]  # Recent bias
        
        if len(periods) != len(period_weights):
            period_weights = [1.0 / len(periods)] * len(periods)  # Equal weights fallback
        
        # Calculate expected returns and covariance for each period
        expected_returns_dict = {}
        cov_matrices_dict = {}
        
        for period in periods:
            # Use last N days for this period
            period_data = price_history.tail(period) if len(price_history) > period else price_history
            
            # Calculate returns for this period
            returns = period_data.pct_change().dropna()
            expected_returns_dict[str(period)] = returns.mean() * 252  # Annualized
            
            # Calculate covariance matrix for this period
            cov_matrices_dict[str(period)] = returns.cov() * 252  # Annualized
        
        # Setup optimization
        assets = price_history.columns.tolist()
        n_assets = len(assets)
        x0 = np.ones(n_assets) / n_assets  # Equal weight initial guess
        
        # Bounds
        bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n_assets)]
        
        # Constraint: weights sum to 1
        constraint_list = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}]
        
        # Objective function
        def multi_period_objective(x):
            return self._multi_period_objective(x, expected_returns_dict, cov_matrices_dict, period_weights)
        
        # Optimization
        result = minimize(
            multi_period_objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraint_list,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )
        
        if not result.success:
            logger.warning(f"Multi-period optimization failed: {result.message}")
            # Fallback to equal weights
            optimal_weights = np.ones(n_assets) / n_assets
        else:
            optimal_weights = result.x
        
        # Calculate final metrics using combined approach (weighted average)
        combined_returns = np.zeros(n_assets)
        combined_cov = np.zeros((n_assets, n_assets))
        
        for i, period in enumerate(periods):
            weight = period_weights[i]
            combined_returns += weight * expected_returns_dict[str(period)]
            combined_cov += weight * cov_matrices_dict[str(period)]
        
        # Build result
        weights_dict = {asset: weight for asset, weight in zip(assets, optimal_weights)}
        portfolio_return = np.dot(optimal_weights, combined_returns)
        portfolio_variance = np.dot(optimal_weights, np.dot(combined_cov, optimal_weights))
        portfolio_volatility = np.sqrt(portfolio_variance)
        
        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_volatility if portfolio_volatility > 0 else 0
        
        # Calculate risk contributions inline
        risk_contributions = {}
        if portfolio_variance > 0:
            combined_cov_values = combined_cov.values if hasattr(combined_cov, 'values') else combined_cov
            for i, asset in enumerate(assets):
                marginal_risk = np.dot(combined_cov_values[i], optimal_weights)
                risk_contributions[asset] = optimal_weights[i] * marginal_risk / portfolio_variance
        
        # Calculate sector exposures
        sector_exposures = {}
        for sector, symbols in self.crypto_sectors.items():
            sector_weight = sum(weights_dict.get(symbol, 0) for symbol in symbols)
            if sector_weight > 0:
                sector_exposures[sector] = sector_weight
        
        # Calculate optimization score (simplified)
        optimization_score = sharpe_ratio * self._calculate_diversification_ratio(optimal_weights, combined_cov)
        
        return OptimizationResult(
            weights=weights_dict,
            expected_return=portfolio_return,
            volatility=portfolio_volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=0.0,  # Would need historical simulation
            diversification_ratio=self._calculate_diversification_ratio(optimal_weights, combined_cov),
            optimization_score=optimization_score,
            risk_contributions=risk_contributions,
            sector_exposures=sector_exposures,
            constraints_satisfied=self._check_constraints_satisfaction(optimal_weights, constraints, assets)
        )
    
    def _check_constraints_satisfaction(self, weights: np.ndarray, 
                                      constraints: OptimizationConstraints,
                                      assets: List[str]) -> bool:
        """Check if all constraints are satisfied"""
        
        # Weight bounds
        if np.any(weights < constraints.min_weight - 1e-6) or \
           np.any(weights > constraints.max_weight + 1e-6):
            return False
            
        # Weights sum to 1
        if abs(np.sum(weights) - 1.0) > 1e-6:
            return False
            
        # Sector constraints
        for sector, symbols in self.crypto_sectors.items():
            sector_weight = sum(weights[i] for i, asset in enumerate(assets) 
                              if asset in symbols)
            if sector_weight > constraints.max_sector_weight + 1e-6:
                return False
                
        return True
        
    def _calculate_correlation_matrix(self, cov_matrix: pd.DataFrame) -> np.ndarray:
        """Calculate correlation matrix from covariance matrix"""
        
        volatilities = np.sqrt(np.diag(cov_matrix.values))
        # Avoid division by zero
        vol_matrix = np.outer(volatilities, volatilities)
        vol_matrix = np.where(vol_matrix == 0, 1e-8, vol_matrix)
        
        corr_matrix = cov_matrix.values / vol_matrix
        return corr_matrix
    
    def _calculate_correlation_exposure(self, weights: np.ndarray, corr_matrix: np.ndarray) -> float:
        """
        Calculate portfolio correlation exposure as weighted sum of absolute correlations
        Formula: exposure = sum_{i<j} |corr_ij| * x_i * x_j / (1 - sum x_i^2 + eps)
        """
        
        n = len(weights)
        exposure = 0.0
        
        # Sum of pairwise correlation contributions
        for i in range(n):
            for j in range(i + 1, n):
                correlation = abs(corr_matrix[i, j])
                exposure += correlation * weights[i] * weights[j]
        
        # Normalize by portfolio concentration (1 - HHI)
        herfindahl_index = np.sum(weights ** 2)
        normalization = max(1 - herfindahl_index, 1e-6)  # Avoid division by zero
        
        return exposure / normalization
    
    def _create_smart_fallback_weights(self, expected_returns: np.ndarray) -> np.ndarray:
        """Create intelligent fallback weights when optimization fails"""
        
        # Weight assets proportionally to positive expected returns
        positive_returns = np.maximum(expected_returns, 0)
        
        if np.sum(positive_returns) > 0:
            weights = positive_returns / np.sum(positive_returns)
        else:
            # If all returns are negative, use equal weights
            weights = np.ones(len(expected_returns)) / len(expected_returns)
        
        return weights

    def optimize_black_litterman(
        self,
        price_history: pd.DataFrame,
        market_views: Dict[str, float],
        view_confidence: Dict[str, float],
        constraints: OptimizationConstraints,
        current_weights: Optional[Dict[str, float]] = None
    ) -> OptimizationResult:
        """
        Black-Litterman optimization with investor views

        Args:
            price_history: Historical price data
            market_views: Dict of asset -> expected return views (e.g., {"BTC": 0.15, "ETH": 0.12})
            view_confidence: Dict of asset -> confidence level 0-1 (e.g., {"BTC": 0.8, "ETH": 0.6})
            constraints: Portfolio constraints
            current_weights: Current portfolio weights (used as market equilibrium)
        """
        # Calculate basic inputs
        returns = price_history.pct_change().dropna()
        assets = returns.columns.tolist()

        # Market equilibrium weights (current portfolio or equal weights)
        if current_weights:
            w_market = np.array([current_weights.get(asset, 0) for asset in assets])
            w_market = w_market / w_market.sum() if w_market.sum() > 0 else np.ones(len(assets)) / len(assets)
        else:
            w_market = np.ones(len(assets)) / len(assets)

        # Risk aversion parameter (typical range 2-10)
        risk_aversion = 3.5

        # Covariance matrix
        cov_matrix = returns.cov().values * 252  # Annualized

        # Implied equilibrium returns (reverse optimization)
        pi = risk_aversion * cov_matrix @ w_market

        # Prepare views
        view_assets = [asset for asset in market_views.keys() if asset in assets]
        if not view_assets:
            raise ValueError("No valid assets found in market views")

        k = len(view_assets)
        n = len(assets)

        # Picking matrix P (which assets have views)
        P = np.zeros((k, n))
        Q = np.zeros(k)  # View returns

        for i, asset in enumerate(view_assets):
            asset_idx = assets.index(asset)
            P[i, asset_idx] = 1.0
            Q[i] = market_views[asset]

        # Uncertainty matrix Omega (diagonal)
        omega = np.eye(k)
        for i, asset in enumerate(view_assets):
            confidence = view_confidence.get(asset, 0.5)
            # Higher confidence = lower uncertainty
            # tau * variance of the view
            asset_idx = assets.index(asset)
            asset_variance = cov_matrix[asset_idx, asset_idx]
            omega[i, i] = (1 - confidence) * 0.05 * asset_variance

        # Tau parameter (uncertainty of prior)
        tau = 0.05

        # Black-Litterman formula
        M1 = np.linalg.inv(tau * cov_matrix)
        M2 = P.T @ np.linalg.inv(omega) @ P
        M3 = M1 @ pi + P.T @ np.linalg.inv(omega) @ Q

        # New expected returns
        mu_bl = np.linalg.inv(M1 + M2) @ M3

        # New covariance matrix
        sigma_bl = np.linalg.inv(M1 + M2)

        # Convert to pandas for optimization
        expected_returns = pd.Series(mu_bl, index=assets)
        cov_df = pd.DataFrame(sigma_bl, index=assets, columns=assets)

        # Optimize using max Sharpe with BL inputs
        return self.optimize_portfolio(
            expected_returns=expected_returns,
            cov_matrix=cov_df,
            constraints=constraints,
            objective=OptimizationObjective.MAX_SHARPE,
            current_weights=current_weights
        )

    def calculate_efficient_frontier(
        self,
        price_history: pd.DataFrame,
        constraints: OptimizationConstraints,
        n_points: int = 50
    ) -> Dict[str, Any]:
        """
        Calculate the efficient frontier

        Returns:
            Dict with risks, returns, weights, and sharpe ratios for each point
        """
        returns = price_history.pct_change().dropna()
        expected_returns = self.calculate_expected_returns(price_history, "mean_reversion")
        cov_matrix, _ = self.calculate_risk_model(price_history)

        assets = expected_returns.index.tolist()

        # Range of target returns
        min_ret = expected_returns.min()
        max_ret = expected_returns.max()
        target_returns = np.linspace(min_ret, max_ret, n_points)

        efficient_weights = []
        efficient_risks = []
        efficient_returns = []
        efficient_sharpes = []

        for target_ret in target_returns:
            try:
                # Set target return constraint
                temp_constraints = OptimizationConstraints(
                    min_weight=constraints.min_weight,
                    max_weight=constraints.max_weight,
                    max_sector_weight=constraints.max_sector_weight,
                    min_expected_return=target_ret
                )

                # Optimize for minimum variance at this return level
                result = self.optimize_portfolio(
                    expected_returns=expected_returns,
                    cov_matrix=cov_matrix,
                    constraints=temp_constraints,
                    objective=OptimizationObjective.MIN_VARIANCE
                )

                if result.constraints_satisfied:
                    efficient_weights.append(result.weights)
                    efficient_risks.append(result.volatility)
                    efficient_returns.append(result.expected_return)
                    efficient_sharpes.append(result.sharpe_ratio)

            except Exception as e:
                logger.warning(f"Failed to optimize for target return {target_ret:.3f}: {e}")
                continue

        return {
            "risks": efficient_risks,
            "returns": efficient_returns,
            "weights": efficient_weights,
            "sharpe_ratios": efficient_sharpes,
            "n_points": len(efficient_risks)
        }

def create_crypto_constraints(conservative: bool = False, n_assets: int = None) -> OptimizationConstraints:
    """Create crypto-specific optimization constraints with dynamic min_weight"""
    
    # Calculate dynamic min_weight based on number of assets
    dynamic_min_weight = 0.0
    if n_assets and n_assets > 0:
        # For many assets, use smaller min_weight to avoid infeasibility
        # Rule: min(0.01, 1/(2*n_assets)) but never below 0.001
        dynamic_min_weight = max(0.001, min(0.01, 1.0 / (2 * n_assets)))
    
    if conservative:
        return OptimizationConstraints(
            min_weight=dynamic_min_weight,  # Dynamic minimum
            max_weight=0.25,   # 25% max pour forcer diversification
            max_sector_weight=0.4,
            min_diversification_ratio=0.5,  # Forte diversification
            max_correlation_exposure=0.6,   # Moins de corrélation
            target_volatility=0.20  # 20% volatilité target
        )
    else:
        return OptimizationConstraints(
            min_weight=0.0,     # No minimum for aggressive
            max_weight=0.35,    # 35% max au lieu de 60% pour plus de diversité
            max_sector_weight=0.6,
            min_diversification_ratio=0.25,  # Diversification minimum
            max_correlation_exposure=0.75    
        )