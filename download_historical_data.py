"""
Download full historical data for backtesting

This script downloads 12 months of OHLCV data for test assets
and saves to cache for backtesting.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import logging
from datetime import datetime, timedelta

from services.risk.bourse.data_fetcher import BourseDataFetcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def download_asset_data(symbol: str, days: int = 3650):
    """
    Download historical data for a symbol

    Args:
        symbol: Stock ticker
        days: Days of history (default 3650 = 10 years)
    """
    fetcher = BourseDataFetcher(cache_dir="data/cache/bourse")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    logger.info(f"Downloading {symbol} data from {start_date.date()} to {end_date.date()}")

    try:
        df = await fetcher.fetch_historical_prices(
            ticker=symbol,
            start_date=start_date,
            end_date=end_date,
            source="yahoo"
        )

        logger.info(f"✅ {symbol}: Downloaded {len(df)} days of data")
        return symbol, len(df), True

    except Exception as e:
        logger.error(f"❌ {symbol}: Failed to download - {e}")
        return symbol, 0, False


async def main():
    """Download data for all test assets"""
    print("\n📥 Downloading Historical Data for Backtesting")
    print("=" * 60)

    # Assets to download (can expand later)
    test_assets = [
        "AAPL",   # Apple
        "NVDA",   # NVIDIA
        "SPY",    # S&P 500 ETF
        "MSFT",   # Microsoft (bonus)
        "TSLA",   # Tesla (bonus volatile asset)
        "KO"      # Coca-Cola (bonus stable asset)
    ]

    print(f"Assets: {', '.join(test_assets)}")
    print(f"Period: 10 years (3650 days)")
    print(f"Source: Yahoo Finance\n")

    # Download concurrently
    tasks = [download_asset_data(symbol, days=3650) for symbol in test_assets]
    results = await asyncio.gather(*tasks)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Download Summary:")
    print("=" * 60)

    success = 0
    failed = 0

    for symbol, days, status in results:
        if status:
            print(f"  ✅ {symbol:6s} : {days:3d} days downloaded")
            success += 1
        else:
            print(f"  ❌ {symbol:6s} : Download failed")
            failed += 1

    print("\n" + "=" * 60)
    print(f"✅ Success: {success}/{len(test_assets)}")
    if failed > 0:
        print(f"❌ Failed: {failed}/{len(test_assets)}")

    print("\n💡 Next step:")
    print("  python run_backtest_standalone.py")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
