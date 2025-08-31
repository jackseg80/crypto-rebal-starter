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

logger = logging.getLogger(__name__)

class OptimizationObjective(Enum):
    """Portfolio optimization objectives"""
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance" 
    MAX_RETURN = "max_return"
    RISK_PARITY = "risk_parity"
    MEAN_REVERSION = "mean_reversion"

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
        stable_cov = stable_corr * np.outer(volatilities, volatilities)
        
        return pd.DataFrame(stable_cov, index=returns.columns, columns=returns.columns), \
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
        
        # Objective function
        def objective_function(x):
            portfolio_return = np.dot(x, expected_returns.values)
            portfolio_variance = np.dot(x, np.dot(cov_matrix.values, x))
            portfolio_volatility = np.sqrt(portfolio_variance)
            
            if objective == OptimizationObjective.MAX_SHARPE:
                return -(portfolio_return - self.risk_free_rate) / portfolio_volatility
            elif objective == OptimizationObjective.MIN_VARIANCE:
                return portfolio_variance
            elif objective == OptimizationObjective.MAX_RETURN:
                return -portfolio_return
            elif objective == OptimizationObjective.RISK_PARITY:
                return self._risk_parity_objective(x, cov_matrix.values)
            elif objective == OptimizationObjective.MEAN_REVERSION:
                return self._mean_reversion_objective(x, expected_returns.values, cov_matrix.values)
        
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
            # Fallback to equal weights
            optimal_weights = np.ones(n_assets) / n_assets
        else:
            optimal_weights = result.x
            
        # Calculate result metrics
        weights_dict = {asset: weight for asset, weight in zip(assets, optimal_weights)}
        
        portfolio_return = np.dot(optimal_weights, expected_returns.values)
        portfolio_variance = np.dot(optimal_weights, np.dot(cov_matrix.values, optimal_weights))
        portfolio_volatility = np.sqrt(portfolio_variance)
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

def create_crypto_constraints(conservative: bool = False) -> OptimizationConstraints:
    """Create crypto-specific optimization constraints"""
    
    if conservative:
        return OptimizationConstraints(
            min_weight=0.01,   # 1% minimum pour éviter trop de dispersion
            max_weight=0.25,   # 25% max pour forcer diversification
            max_sector_weight=0.4,
            min_diversification_ratio=0.5,  # Forte diversification
            max_correlation_exposure=0.6,   # Moins de corrélation
            target_volatility=0.20  # 20% volatilité target
        )
    else:
        return OptimizationConstraints(
            min_weight=0.0,     
            max_weight=0.35,    # 35% max au lieu de 60% pour plus de diversité
            max_sector_weight=0.6,
            min_diversification_ratio=0.25,  # Diversification minimum
            max_correlation_exposure=0.75    
        )