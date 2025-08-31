#!/usr/bin/env python3
"""Test multi-period optimization"""

import pandas as pd
import numpy as np
from services.portfolio_optimization import PortfolioOptimizer, OptimizationConstraints

def test_multi_period():
    # Create simple test data
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
    assets = ['BTC', 'ETH', 'SOL']
    
    # Generate mock price data
    np.random.seed(42)
    price_data = pd.DataFrame(
        index=dates,
        columns=assets,
        data=np.cumsum(np.random.randn(len(dates), len(assets)) * 0.02, axis=0) + 100
    )
    
    print("Price data shape:", price_data.shape)
    
    # Setup constraints
    constraints = OptimizationConstraints(
        min_weight=0.1,
        max_weight=0.6,
        rebalance_periods=[30, 90, 180],
        period_weights=[0.5, 0.3, 0.2]
    )
    
    # Initialize optimizer
    optimizer = PortfolioOptimizer()
    
    try:
        result = optimizer.optimize_multi_period(price_data, constraints)
        print("Multi-period optimization successful!")
        print(f"Weights: {result.weights}")
        print(f"Expected return: {result.expected_return:.3f}")
        print(f"Volatility: {result.volatility:.3f}")
        print(f"Sharpe ratio: {result.sharpe_ratio:.3f}")
        
    except Exception as e:
        print(f"Multi-period optimization failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_multi_period()