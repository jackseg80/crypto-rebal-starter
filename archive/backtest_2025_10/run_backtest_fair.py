"""
Fair Backtest - 3-Way Comparison

Compares:
1. ATR 2x (adapts to volatility automatically)
2. Fixed 5% (same for all - current unfair baseline)
3. Fixed Variable (4-6-8% based on volatility - fair baseline)

This answers: "Should we use ATR or Fixed for stop losses?"
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
from datetime import datetime
import json
import numpy as np

from services.ml.bourse.stop_loss_backtest_v2 import StopLossBacktestV2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_results(results: dict):
    """Pretty print 3-way comparison"""
    print("\n" + "=" * 80)
    print("FAIR STOP LOSS COMPARISON (3 Methods)")
    print("=" * 80)

    config = results.get('test_config', {})
    print(f"\nConfiguration:")
    print(f"  - Lookback: {config.get('lookback_days')} days")
    print(f"  - Entry Interval: {config.get('entry_interval_days')} days")
    print(f"  - Market Regime: {config.get('market_regime')}")

    print(f"\nAssets Tested: {len(results.get('individual_results', []))}")
    print("\n" + "-" * 80)

    # Individual results
    for result in results.get('individual_results', []):
        symbol = result['symbol']
        period = result['data_period']
        atr = result['atr_2x']
        fixed = result['fixed_5pct']
        fixed_var = result['fixed_variable']
        comp = result['comparison']

        print(f"\n{symbol} ({period['days']} days: {period['start']} to {period['end']})")
        print(f"  +----------+----------+--------------+--------------+")
        print(f"  | Metric   | ATR 2x   | Fixed 5%     | Fixed Var    |")
        print(f"  +----------+----------+--------------+--------------+")
        print(f"  | Trades   | {atr['total_trades']:8} | {fixed['total_trades']:12} | {fixed_var['total_trades']:12} |")
        print(f"  | Win Rate | {atr['win_rate']*100:7.1f}% | {fixed['win_rate']*100:11.1f}% | {fixed_var['win_rate']*100:11.1f}% |")
        print(f"  | Total P&L| ${atr['total_pnl_usd']:7,.0f} | ${fixed['total_pnl_usd']:10,.0f} | ${fixed_var['total_pnl_usd']:10,.0f} |")
        print(f"  | Stops Hit| {atr['stops_hit_pct']*100:7.1f}% | {fixed['stops_hit_pct']*100:11.1f}% | {fixed_var['stops_hit_pct']*100:11.1f}% |")
        print(f"  +----------+----------+--------------+--------------+")
        print(f"  Winner: {comp['winner']} - {comp['verdict']}")

    print("\n" + "=" * 80)


def main():
    """Run fair 3-way backtest"""
    print("\nStarting Fair Stop Loss Backtest")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Test assets (must have data)
    test_symbols = ["AAPL", "NVDA", "TSLA", "MSFT", "KO", "SPY"]

    print(f"Assets: {', '.join(test_symbols)}")
    print(f"\nMethods:")
    print(f"  1. ATR 2x        - Adapts to volatility (2.5x ATR)")
    print(f"  2. Fixed 5%      - Same 5% for all assets (UNFAIR)")
    print(f"  3. Fixed Variable- 4% (low vol), 6% (med vol), 8% (high vol) (FAIR)\n")

    # Initialize backtester
    backtester = StopLossBacktestV2(
        cache_dir="data/cache/bourse",
        market_regime="Bull Market",
        timeframe="short"
    )

    # Run backtest
    results = {"individual_results": [], "test_config": {
        "lookback_days": 365,
        "entry_interval_days": 7,
        "market_regime": "Bull Market"
    }}

    for symbol in test_symbols:
        result = backtester.compare_three_methods(
            symbol,
            lookback_days=365,
            entry_interval_days=7
        )
        if result:
            results["individual_results"].append(result)

    # Print results
    print_results(results)

    # Aggregate
    if results['individual_results']:
        atr_total = sum(r['atr_2x']['total_pnl_usd'] for r in results['individual_results'])
        fixed_total = sum(r['fixed_5pct']['total_pnl_usd'] for r in results['individual_results'])
        fixed_var_total = sum(r['fixed_variable']['total_pnl_usd'] for r in results['individual_results'])

        print("\nAGGREGATE RESULTS:")
        print(f"  ATR 2x:        ${atr_total:>10,.0f}")
        print(f"  Fixed 5%:      ${fixed_total:>10,.0f}")
        print(f"  Fixed Variable:${fixed_var_total:>10,.0f}")

        if atr_total > max(fixed_total, fixed_var_total):
            print(f"\n  Winner: ATR 2x (adapts to volatility automatically)")
        elif fixed_var_total > max(atr_total, fixed_total):
            print(f"\n  Winner: Fixed Variable (fair baseline)")
        else:
            print(f"\n  Winner: Fixed 5% (surprisingly...)")

    print("\n" + "=" * 80)

    # Save
    output_file = "data/backtest_results_fair.json"

    def convert_numpy(obj):
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convert_numpy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy(item) for item in obj]
        return obj

    with open(output_file, 'w') as f:
        json.dump(convert_numpy(results), f, indent=2, default=str)

    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBacktest interrupted by user")
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        print(f"\nError: {e}")
