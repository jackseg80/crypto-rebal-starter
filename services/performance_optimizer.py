"""
Performance optimization utilities for large portfolios
Handles caching, matrix operations acceleration, and memory optimization
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from functools import lru_cache
import hashlib
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class PortfolioPerformanceOptimizer:
    """Performance optimizations for large portfolio operations"""
    
    def __init__(self, cache_dir: str = "cache/portfolio_optimization"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.memory_cache = {}
        self.max_cache_size = 100  # Maximum cached items
    
    def get_cache_key(self, data: Any, prefix: str = "") -> str:
        """Generate cache key from data"""
        if isinstance(data, pd.DataFrame):
            # Use shape, columns, and sample of data for DataFrame hash
            key_data = f"{data.shape}_{list(data.columns)}_{data.iloc[0:5].sum().sum() if len(data) > 0 else 0}"
        elif isinstance(data, dict):
            key_data = json.dumps(data, sort_keys=True)
        else:
            key_data = str(data)
        
        return f"{prefix}_{hashlib.md5(key_data.encode()).hexdigest()[:16]}"
    
    def cache_matrix_operation(self, key: str, operation: callable, *args, **kwargs) -> Any:
        """Cache expensive matrix operations"""
        cache_file = self.cache_dir / f"{key}.json"
        
        # Check memory cache first
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # Check disk cache
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                    if isinstance(cached_data, dict) and 'data' in cached_data:
                        result = np.array(cached_data['data']) if 'shape' in cached_data else cached_data['data']
                        self.memory_cache[key] = result
                        return result
            except Exception as e:
                logger.warning(f"Failed to load cache {key}: {e}")
        
        # Compute and cache
        result = operation(*args, **kwargs)
        
        # Cache in memory
        self.memory_cache[key] = result
        if len(self.memory_cache) > self.max_cache_size:
            # Remove oldest entries
            oldest_key = next(iter(self.memory_cache))
            del self.memory_cache[oldest_key]
        
        # Cache to disk
        try:
            cache_data = {
                'data': result.tolist() if hasattr(result, 'tolist') else result,
                'timestamp': datetime.now().isoformat(),
                'shape': result.shape if hasattr(result, 'shape') else None
            }
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.warning(f"Failed to cache {key}: {e}")
        
        return result
    
    def optimized_covariance_matrix(self, returns: pd.DataFrame, 
                                  exponential_weight: bool = True,
                                  shrinkage: float = 0.2) -> np.ndarray:
        """Optimized covariance matrix calculation for large portfolios"""
        
        cache_key = self.get_cache_key(returns, f"cov_ew{exponential_weight}_shr{shrinkage}")
        
        def compute_cov():
            n_assets = returns.shape[1]
            n_periods = returns.shape[0]
            
            # For very large portfolios, use sample covariance with regularization
            if n_assets > 500:
                logger.info(f"Using regularized covariance for {n_assets} assets")
                
                # Simple sample covariance for speed
                sample_cov = returns.cov().values * 252  # Annualized
                
                # Shrinkage toward identity matrix for stability
                identity = np.eye(n_assets) * np.mean(np.diag(sample_cov))
                regularized_cov = (1 - shrinkage) * sample_cov + shrinkage * identity
                
                return regularized_cov
            
            # Standard exponentially weighted covariance for smaller portfolios
            if exponential_weight and n_periods > 30:
                weights = np.exp(np.linspace(-1, 0, n_periods))
                weights = weights / weights.sum()
                
                # Weighted covariance
                weighted_returns = returns * np.sqrt(weights[:, np.newaxis])
                cov_matrix = np.cov(weighted_returns.T) * 252
            else:
                # Simple covariance
                cov_matrix = returns.cov().values * 252
            
            # Shrinkage for stability
            if shrinkage > 0:
                n_assets = cov_matrix.shape[0]
                identity = np.eye(n_assets) * np.mean(np.diag(cov_matrix))
                cov_matrix = (1 - shrinkage) * cov_matrix + shrinkage * identity
            
            return cov_matrix
        
        return self.cache_matrix_operation(cache_key, compute_cov)
    
    def fast_correlation_matrix(self, cov_matrix: np.ndarray) -> np.ndarray:
        """Fast correlation matrix calculation"""
        
        cache_key = f"corr_{hashlib.md5(cov_matrix.tobytes()).hexdigest()[:16]}"
        
        def compute_corr():
            volatilities = np.sqrt(np.diag(cov_matrix))
            # Avoid division by zero
            vol_outer = np.outer(volatilities, volatilities)
            vol_outer[vol_outer == 0] = 1e-8
            return cov_matrix / vol_outer
        
        return self.cache_matrix_operation(cache_key, compute_corr)
    
    def efficient_portfolio_metrics(self, weights: np.ndarray, 
                                  expected_returns: np.ndarray,
                                  cov_matrix: np.ndarray) -> Dict[str, float]:
        """Efficient calculation of portfolio metrics"""
        
        portfolio_return = np.dot(weights, expected_returns)
        portfolio_variance = np.dot(weights, np.dot(cov_matrix, weights))
        portfolio_volatility = np.sqrt(max(portfolio_variance, 1e-12))
        
        # Fast risk contributions using vectorized operations
        marginal_risks = np.dot(cov_matrix, weights)
        risk_contributions = weights * marginal_risks / max(portfolio_variance, 1e-12)
        
        # Diversification ratio
        individual_vols = np.sqrt(np.diag(cov_matrix))
        weighted_vol = np.dot(weights, individual_vols)
        diversification_ratio = weighted_vol / portfolio_volatility if portfolio_volatility > 0 else 0
        
        return {
            'expected_return': portfolio_return,
            'volatility': portfolio_volatility,
            'variance': portfolio_variance,
            'diversification_ratio': diversification_ratio,
            'risk_contributions': risk_contributions,
            'concentration': np.sum(weights ** 2)  # Herfindahl index
        }
    
    def batch_optimization_preprocessing(self, price_data: pd.DataFrame,
                                       min_assets: int = 50,
                                       max_assets: int = 200) -> Dict[str, Any]:
        """Preprocess data for batch optimization of large portfolios"""
        
        n_total_assets = price_data.shape[1]
        logger.info(f"Preprocessing {n_total_assets} assets for optimization")
        
        # Calculate basic statistics
        returns = price_data.pct_change().dropna()
        
        # Asset filtering for performance
        if n_total_assets > max_assets:
            logger.info(f"Filtering from {n_total_assets} to {max_assets} assets")
            
            # Keep assets with:
            # 1. Sufficient data (>90% non-null)
            # 2. Reasonable volatility (not too stable/volatile)
            # 3. Recent activity
            
            data_completeness = returns.count() / len(returns)
            volatilities = returns.std() * np.sqrt(252)  # Annualized
            recent_activity = returns.tail(30).std()  # Recent volatility
            
            # Scoring system
            completeness_score = (data_completeness - 0.5) / 0.5  # 0.5-1.0 -> 0-1
            vol_score = 1 - np.abs(volatilities - volatilities.median()) / volatilities.std()
            activity_score = recent_activity / recent_activity.median()
            
            combined_score = (completeness_score + vol_score + activity_score) / 3
            
            # Select top assets
            top_assets = combined_score.nlargest(max_assets).index
            filtered_data = price_data[top_assets]
            
            logger.info(f"Selected {len(top_assets)} assets for optimization")
        else:
            filtered_data = price_data
        
        # Precompute matrices
        filtered_returns = filtered_data.pct_change().dropna()
        expected_returns = self.calculate_expected_returns(filtered_returns)
        cov_matrix = self.optimized_covariance_matrix(filtered_returns)
        corr_matrix = self.fast_correlation_matrix(cov_matrix)
        
        return {
            'price_data': filtered_data,
            'returns': filtered_returns,
            'expected_returns': expected_returns,
            'cov_matrix': cov_matrix,
            'corr_matrix': corr_matrix,
            'n_assets': filtered_data.shape[1],
            'assets': list(filtered_data.columns)
        }
    
    def calculate_expected_returns(self, returns: pd.DataFrame,
                                 method: str = "robust_mean") -> np.ndarray:
        """Calculate expected returns with robust estimation"""
        
        if method == "robust_mean":
            # Winsorized mean to handle outliers
            def winsorized_mean(series, lower=0.05, upper=0.95):
                lower_bound = series.quantile(lower)
                upper_bound = series.quantile(upper)
                clipped = series.clip(lower_bound, upper_bound)
                return clipped.mean()
            
            expected_returns = returns.apply(winsorized_mean) * 252
            
        elif method == "shrinkage":
            # Shrink toward cross-sectional mean
            sample_means = returns.mean() * 252
            cross_sectional_mean = sample_means.mean()
            shrinkage_factor = 0.3
            
            expected_returns = (1 - shrinkage_factor) * sample_means + shrinkage_factor * cross_sectional_mean
            
        else:
            # Simple historical mean
            expected_returns = returns.mean() * 252
        
        return expected_returns.values
    
    def clear_cache(self, older_than_days: int = 7):
        """Clear old cache files"""
        cutoff_time = datetime.now() - timedelta(days=older_than_days)
        
        cleared = 0
        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file.stat().st_mtime < cutoff_time.timestamp():
                cache_file.unlink()
                cleared += 1
        
        logger.info(f"Cleared {cleared} old cache files")
        
        # Clear memory cache
        self.memory_cache.clear()

# Global instance
performance_optimizer = PortfolioPerformanceOptimizer()