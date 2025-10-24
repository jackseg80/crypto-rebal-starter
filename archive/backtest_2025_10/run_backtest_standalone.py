"""
Standalone backtest runner - bypasses services.ml.__init__.py imports

This script directly imports only the needed modules without triggering torch imports
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import directly without going through services.ml.__init__.py
import logging
from datetime import datetime
import json
import numpy as np

# Direct imports (bypass __init__.py)
from services.ml.bourse import stop_loss_backtest
from services.ml.bourse import stop_loss_calculator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_results(results: dict):
    """Pretty print backtest results"""
    print("\n" + "=" * 80)
    print(f"📊 STOP LOSS BACKTEST RESULTS")
    print("=" * 80)

    config = results.get('test_config', {})
    print(f"\n⚙️ Configuration:")
    print(f"  • Market Regime: {config.get('market_regime')}")
    print(f"  • Timeframe: {config.get('timeframe')}")
    print(f"  • Lookback Days: {config.get('lookback_days')}")
    print(f"  • Entry Interval: {config.get('entry_interval_days')} days")

    # Individual results
    print(f"\n📈 Individual Assets:\n")
    for result in results.get('individual_results', []):
        symbol = result['symbol']
        period = result['data_period']
        atr = result['atr_2x']
        fixed = result['fixed_pct']
        comp = result['comparison']

        print(f"  {symbol} ({period['start']} to {period['end']}, {period['days']} days)")
        print(f"  ┌─────────────────┬──────────────┬──────────────┐")
        print(f"  │ Metric          │ ATR 2x       │ Fixed %      │")
        print(f"  ├─────────────────┼──────────────┼──────────────┤")
        print(f"  │ Total Trades    │ {atr['total_trades']:12} │ {fixed['total_trades']:12} │")
        print(f"  │ Win Rate        │ {atr['win_rate']*100:11.1f}% │ {fixed['win_rate']*100:11.1f}% │")
        print(f"  │ Avg P&L %       │ {atr['avg_pnl_pct']*100:+11.2f}% │ {fixed['avg_pnl_pct']*100:+11.2f}% │")
        print(f"  │ Total P&L $     │ ${atr['total_pnl_usd']:11,.0f} │ ${fixed['total_pnl_usd']:11,.0f} │")
        print(f"  │ Stops Hit       │ {atr['stops_hit_pct']*100:11.1f}% │ {fixed['stops_hit_pct']*100:11.1f}% │")
        print(f"  │ Targets Reached │ {atr['targets_reached_pct']*100:11.1f}% │ {fixed['targets_reached_pct']*100:11.1f}% │")
        print(f"  │ Avg Hold Days   │ {atr['avg_holding_days']:11.1f}d │ {fixed['avg_holding_days']:11.1f}d │")
        print(f"  └─────────────────┴──────────────┴──────────────┘")

        print(f"  🏆 Winner: {comp['winner']}")
        print(f"  📝 Verdict: {comp['verdict']}")
        print()

    # Aggregate results
    aggregate = results.get('aggregate', {})
    if aggregate:
        print(f"\n🎯 AGGREGATE RESULTS ({aggregate['assets_tested']} assets):\n")

        atr_agg = aggregate['atr_2x']
        fixed_agg = aggregate['fixed_pct']

        print(f"  ┌─────────────────────┬──────────────┬──────────────┐")
        print(f"  │ Metric              │ ATR 2x       │ Fixed %      │")
        print(f"  ├─────────────────────┼──────────────┼──────────────┤")
        print(f"  │ Total P&L (all)     │ ${atr_agg['total_pnl_usd']:11,.0f} │ ${fixed_agg['total_pnl_usd']:11,.0f} │")
        print(f"  │ Avg Win Rate        │ {atr_agg['avg_win_rate']*100:11.1f}% │ {fixed_agg['avg_win_rate']*100:11.1f}% │")
        print(f"  │ Avg Stops Hit %     │ {atr_agg['avg_stops_hit_pct']*100:11.1f}% │ {fixed_agg['avg_stops_hit_pct']*100:11.1f}% │")
        print(f"  │ Assets Won          │ {atr_agg['assets_won']:12} │ {fixed_agg['assets_won']:12} │")
        print(f"  └─────────────────────┴──────────────┴──────────────┘")

        print(f"\n  🏆 Overall Winner: {aggregate['overall_winner']}")
        print(f"  💰 P&L Difference: ${aggregate['pnl_difference_usd']:,.0f} ({aggregate['pnl_improvement_pct']:+.1f}%)")

    print("\n" + "=" * 80)


def main():
    """Run quick backtest on 3 representative assets"""
    print("\n🚀 Starting Stop Loss Backtesting...")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Test assets (different volatility profiles)
    test_symbols = [
        "AAPL",  # Moderate vol (~25-30%)
        "NVDA",  # High vol (~40-50%)
        "SPY"    # Low vol (~15-20%, ETF)
    ]

    # Initialize backtester
    backtester = stop_loss_backtest.StopLossBacktest(
        cache_dir="data/cache/bourse",
        market_regime="Bull Market",  # Use Bull Market for now (2.5x ATR)
        timeframe="short"  # 1-2 weeks, 5% fixed stop
    )

    # Run backtest
    logger.info(f"Testing {len(test_symbols)} assets: {', '.join(test_symbols)}")

    results = backtester.run_multi_asset_backtest(
        symbols=test_symbols,
        lookback_days=3650,  # 10 years of data (optimal standard)
        entry_interval_days=7  # Enter every week
    )

    # Print results
    print_results(results)

    # Save results to file for later analysis
    output_file = "data/backtest_results.json"

    # Convert numpy types to native Python for JSON serialization
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

    logger.info(f"\n✅ Results saved to {output_file}")

    print(f"\n💡 Next steps:")
    print(f"  1. Review aggregate results above")
    print(f"  2. Generate HTML report: python run_generate_report.py")
    print(f"  3. If ATR performs better, proceed to Phase 2 (Support Detection)")
    print(f"  4. If results are mixed, investigate specific scenarios")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Backtest interrupted by user")
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        print(f"\nDebug info:")
        print(f"  • Check that parquet files exist in data/cache/bourse/")
        print(f"  • Verify yfinance installed: pip install yfinance")
        print(f"  • Check logs for detailed error messages")
