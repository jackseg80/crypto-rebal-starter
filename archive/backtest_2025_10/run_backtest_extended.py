"""
Extended backtest with 10 assets over 5 years

Tests ATR 2x vs Fixed % on diverse portfolio:
- 3 Tech stocks (high vol)
- 3 Blue chips (moderate vol)
- 2 Defensive (low vol)
- 2 ETFs (market baseline)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
from datetime import datetime
import json
import numpy as np

from services.ml.bourse import stop_loss_backtest

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_results(results: dict):
    """Pretty print backtest results"""
    print("\n" + "=" * 80)
    print(f"STOP LOSS BACKTEST RESULTS - EXTENDED (10 YEARS)")
    print("=" * 80)

    config = results.get('test_config', {})
    print(f"\nConfiguration:")
    print(f"  - Market Regime: {config.get('market_regime')}")
    print(f"  - Timeframe: {config.get('timeframe')}")
    print(f"  - Lookback Period: 10 years ({config.get('lookback_days')} days)")
    print(f"  - Entry Interval: {config.get('entry_interval_days')} days")
    print(f"  - Assets Tested: {len(config.get('symbols', []))}")

    # Individual results (summary table)
    print(f"\nIndividual Assets Summary:\n")
    print(f"  {'Asset':<8} {'Type':<12} {'ATR P&L':<12} {'Fixed P&L':<12} {'Winner':<10} {'Trades':<8}")
    print(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*12} {'-'*10} {'-'*8}")

    for result in results.get('individual_results', []):
        symbol = result['symbol']
        atr = result['atr_2x']
        fixed = result['fixed_pct']
        comp = result['comparison']

        # Determine asset type
        if symbol in ['SPY', 'QQQ', 'IWM']:
            asset_type = "ETF"
        elif symbol in ['NVDA', 'TSLA', 'AMD']:
            asset_type = "Tech (High)"
        elif symbol in ['KO', 'PG', 'JNJ']:
            asset_type = "Defensive"
        else:
            asset_type = "Blue Chip"

        winner = "[ATR]" if comp['winner'] == 'ATR 2x' else "[Fixed]"

        print(f"  {symbol:<8} {asset_type:<12} ${atr['total_pnl_usd']:>10,.0f} ${fixed['total_pnl_usd']:>10,.0f} {winner:<10} {atr['total_trades']:>6}")

    # Aggregate results
    aggregate = results.get('aggregate', {})
    if aggregate:
        print(f"\n{'='*80}")
        print(f"AGGREGATE RESULTS ({aggregate['assets_tested']} assets):")
        print(f"{'='*80}\n")

        atr_agg = aggregate['atr_2x']
        fixed_agg = aggregate['fixed_pct']

        print(f"  ┌─────────────────────┬──────────────┬──────────────┐")
        print(f"  │ Metric              │ ATR 2x       │ Fixed %      │")
        print(f"  ├─────────────────────┼──────────────┼──────────────┤")
        print(f"  │ Total P&L (all)     │ ${atr_agg['total_pnl_usd']:>11,.0f} │ ${fixed_agg['total_pnl_usd']:>11,.0f} │")
        print(f"  │ Avg Win Rate        │ {atr_agg['avg_win_rate']*100:>11.1f}% │ {fixed_agg['avg_win_rate']*100:>11.1f}% │")
        print(f"  │ Avg Stops Hit %     │ {atr_agg['avg_stops_hit_pct']*100:>11.1f}% │ {fixed_agg['avg_stops_hit_pct']*100:>11.1f}% │")
        print(f"  │ Assets Won          │ {atr_agg['assets_won']:>12} │ {fixed_agg['assets_won']:>12} │")
        print(f"  └─────────────────────┴──────────────┴──────────────┘")

        print(f"\n  Overall Winner: {aggregate['overall_winner']}")
        print(f"  P&L Difference: ${aggregate['pnl_difference_usd']:,.0f} ({aggregate['pnl_improvement_pct']:+.1f}%)")

        # Verdict
        pnl_imp = aggregate['pnl_improvement_pct']
        if pnl_imp > 10:
            verdict = f"[OK] ATR 2x significantly outperforms (+{pnl_imp:.1f}%) - VALIDATED for production"
        elif pnl_imp > 0:
            verdict = f"[WARN] ATR 2x slightly better (+{pnl_imp:.1f}%) - Investigate by asset type"
        elif pnl_imp > -10:
            verdict = f"[WARN] Fixed % slightly better ({pnl_imp:.1f}%) - No clear winner"
        else:
            verdict = f"[FAIL] Fixed % significantly better ({pnl_imp:.1f}%) - ATR needs adjustment"

        print(f"\n  Verdict: {verdict}")

    print("\n" + "=" * 80)


def main():
    """Run extended backtest on 10 diverse assets"""
    print("\nStarting Extended Stop Loss Backtesting (10 YEARS)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Extended asset list (diverse volatility profiles)
    test_symbols = [
        # Tech (High Volatility 40-60%)
        "NVDA",   # NVIDIA
        "TSLA",   # Tesla
        "AMD",    # AMD

        # Blue Chips (Moderate Volatility 20-35%)
        "AAPL",   # Apple
        "MSFT",   # Microsoft
        "GOOGL",  # Alphabet

        # Defensive (Low Volatility 15-25%)
        "KO",     # Coca-Cola
        "PG",     # Procter & Gamble

        # ETFs (Market Baseline 15-20%)
        "SPY",    # S&P 500
        "QQQ"     # Nasdaq 100
    ]

    print(f"\nAssets: {len(test_symbols)} total")
    print(f"  - Tech (High Vol): NVDA, TSLA, AMD")
    print(f"  - Blue Chips: AAPL, MSFT, GOOGL")
    print(f"  - Defensive: KO, PG")
    print(f"  - ETFs: SPY, QQQ\n")

    # Initialize backtester
    backtester = stop_loss_backtest.StopLossBacktest(
        cache_dir="data/cache/bourse",
        market_regime="Bull Market",  # Use Bull Market (2.5x ATR)
        timeframe="short"  # 1-2 weeks, 5% fixed stop
    )

    # Run backtest
    logger.info(f"Testing {len(test_symbols)} assets over 10 years")

    results = backtester.run_multi_asset_backtest(
        symbols=test_symbols,
        lookback_days=3650,  # 10 years (Oct 2015 - Oct 2025)
        entry_interval_days=7  # Enter every week (~520 trades per asset)
    )

    # Print results
    print_results(results)

    # Save results
    output_file = "data/backtest_results_extended.json"

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

    print(f"\nNext steps:")
    print(f"  1. Review aggregate results above")
    print(f"  2. Generate HTML report: python services/ml/bourse/generate_backtest_report.py")
    print(f"  3. If ATR wins by >10%, proceed to Phase 2 (Support Detection)")
    print(f"  4. If mixed results, analyze by asset type (tech vs defensive)")
    print(f"\nExpected runtime: ~5-10 minutes for 5200+ trade simulations")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBacktest interrupted by user")
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        print(f"\nError: {e}")
