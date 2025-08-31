#!/usr/bin/env python3
"""Test simple backtesting"""

import pandas as pd
import numpy as np
from services.backtesting_engine import BacktestingEngine, BacktestConfig, TransactionCosts, RebalanceFrequency

def test_simple_backtest():
    # Create simple test data
    dates = pd.date_range('2024-01-01', '2024-01-31', freq='D')
    assets = ['BTC', 'ETH']
    
    # Generate mock price data (upward trend)
    np.random.seed(42)
    price_data = pd.DataFrame(
        index=dates,
        columns=assets,
        data=np.cumsum(np.random.randn(len(dates), len(assets)) * 0.02, axis=0) + 100
    )
    
    print("Price data shape:", price_data.shape)
    print("Price data head:")
    print(price_data.head())
    
    # Setup backtest config
    config = BacktestConfig(
        start_date='2024-01-01',
        end_date='2024-01-31',
        initial_capital=1000.0,
        rebalance_frequency=RebalanceFrequency.WEEKLY,
        transaction_costs=TransactionCosts(
            maker_fee=0.001,
            taker_fee=0.001,
            slippage_bps=5.0,
            min_trade_size=1.0
        )
    )
    
    # Initialize backtest engine
    engine = BacktestingEngine()
    
    print("Available strategies:", list(engine.strategies.keys()))
    
    try:
        result = engine.run_backtest(price_data, 'equal_weight', config)
        print("Backtest successful!")
        print(f"Result attributes: {dir(result)}")
        print(f"Portfolio value type: {type(result.portfolio_value)}")
        if hasattr(result.portfolio_value, 'iloc'):
            print(f"Final value: ${result.portfolio_value.iloc[-1]:.2f}")
        else:
            print(f"Final value: ${result.portfolio_value:.2f}")
        total_return = (result.portfolio_value.iloc[-1] / result.portfolio_value.iloc[0] - 1)
        print(f"Total return: {total_return:.2%}")
        print(f"Metrics available: {result.metrics}")
        print(f"Risk metrics: {result.risk_metrics}")
        if hasattr(result, 'trades_history'):
            print(f"Number of trades: {len(result.trades_history)}")
        
    except Exception as e:
        print(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_backtest()