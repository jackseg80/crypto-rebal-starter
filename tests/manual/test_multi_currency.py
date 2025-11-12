"""
Test script for multi-currency stock data fetching
Validates that CurrencyExchangeDetector and ForexConverter work correctly
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta

from services.ml.bourse.data_sources import StocksDataSource
from services.ml.bourse.currency_detector import CurrencyExchangeDetector
from services.ml.bourse.forex_converter import ForexConverter


async def test_currency_detector():
    """Test CurrencyExchangeDetector with various symbols"""
    print("\n" + "="*80)
    print("TEST 1: Currency & Exchange Detection")
    print("="*80)

    detector = CurrencyExchangeDetector()

    # Test symbols from Jack's portfolio
    test_symbols = [
        # Swiss stocks
        ('ROG', 'CH0012032048', 'VX'),  # Roche
        ('SLHn', 'CH0014852781', 'VX'),  # Swiss Life
        ('UBSG', 'CH0244767585', 'VX'),  # UBS
        ('UHRN', 'CH0012255144', 'SWX'),  # Swatch

        # German stocks
        ('IFX', 'DE0006231004', 'FSE'),  # Infineon

        # Polish stocks
        ('CDR', 'PLOPTTC00011', 'WSE'),  # CD Projekt

        # US stocks
        ('AAPL', 'US0378331005', 'NASDAQ'),
        ('GOOGL', 'US02079K3059', 'NASDAQ'),
        ('TSLA', 'US88160R1014', 'NASDAQ'),

        # ETFs
        ('IWDA', 'IE00B4L5Y983', 'AMS'),  # iShares MSCI World
        ('ITEK', 'IE00BDDRF700', 'PAR'),  # HAN-GINS Tech
        ('WORLD', 'IE000N6LBS91', 'SWX_ETF'),  # UBS MSCI World
    ]

    results = []
    for symbol, isin, exchange in test_symbols:
        yf_symbol, currency, exchange_name = detector.detect_currency_and_exchange(
            symbol=symbol,
            isin=isin,
            exchange_hint=exchange
        )

        results.append({
            'Symbol': symbol,
            'YF Symbol': yf_symbol,
            'Currency': currency,
            'Exchange': exchange_name,
            'ISIN': isin[:7] + '...'
        })

        status = "OK" if currency != 'USD' or exchange_name == 'US Exchange' else "WARN"
        print(f"[{status}] {symbol:8s} -> {yf_symbol:15s} ({currency:3s} on {exchange_name})")

    # Print summary table
    df = pd.DataFrame(results)
    print("\n" + df.to_string(index=False))


async def test_forex_converter():
    """Test ForexConverter with various currency pairs"""
    print("\n" + "="*80)
    print("TEST 2: Forex Currency Conversion")
    print("="*80)

    converter = ForexConverter()

    # Test conversions
    test_conversions = [
        (100, 'CHF', 'USD'),  # Swiss Franc to USD
        (100, 'EUR', 'USD'),  # Euro to USD
        (100, 'PLN', 'USD'),  # Polish Zloty to USD
        (100, 'GBP', 'USD'),  # British Pound to USD
        (271.2, 'CHF', 'USD'),  # Roche stock price
        (33.495, 'EUR', 'USD'),  # Infineon stock price
    ]

    for amount, from_curr, to_curr in test_conversions:
        try:
            converted = await converter.convert(amount, from_curr, to_curr)
            rate = converted / amount
            print(f"{amount:10.2f} {from_curr} -> {converted:10.2f} {to_curr} (rate: {rate:.4f})")
        except Exception as e:
            print(f"ERROR converting {amount} {from_curr} -> {to_curr}: {e}")


async def test_stock_data_fetching():
    """Test fetching actual stock data with multi-currency support"""
    print("\n" + "="*80)
    print("TEST 3: Stock Data Fetching (5 days)")
    print("="*80)

    data_source = StocksDataSource()

    # Test a few symbols from different exchanges
    test_stocks = [
        ('ROG', 'CH0012032048', 'VX', 'Roche (CHF)'),
        ('IFX', 'DE0006231004', 'FSE', 'Infineon (EUR)'),
        ('AAPL', 'US0378331005', 'NASDAQ', 'Apple (USD)'),
        ('WORLD', 'IE000N6LBS91', 'SWX_ETF', 'UBS MSCI World ETF (CHF)'),
    ]

    for symbol, isin, exchange, name in test_stocks:
        print(f"\nFetching {name}...")
        try:
            df = await data_source.get_ohlcv_data(
                symbol=symbol,
                lookback_days=5,
                isin=isin,
                exchange_hint=exchange
            )

            if df is not None and len(df) > 0:
                last_close = df['close'].iloc[-1]
                native_currency = df.attrs.get('native_currency', 'N/A')
                exchange_name = df.attrs.get('exchange', 'N/A')

                print(f"  OK - {len(df)} days fetched")
                print(f"  Last close: {last_close:.2f} {native_currency}")
                print(f"  Exchange: {exchange_name}")
                print(f"  Date range: {df.index[0].date()} to {df.index[-1].date()}")
            else:
                print(f"  WARNING - No data returned")

        except Exception as e:
            print(f"  ERROR - {e}")


async def test_price_comparison():
    """Compare fetched prices with expected prices from Jack's portfolio"""
    print("\n" + "="*80)
    print("TEST 4: Price Validation vs Jack's Portfolio (25 Oct 2025)")
    print("="*80)

    # Expected prices from Jack's CSV (25 Oct 2025, 10:37)
    expected_prices = {
        'AAPL': 262.82,  # USD
        'GOOGL': 259.92,  # USD
        'MSFT': 523.55,  # USD
        'TSLA': 433.62,  # USD
        'ROG': 271.2,  # CHF (should be ~312 USD after conversion)
        'IFX': 33.495,  # EUR (should be ~36.5 USD after conversion)
        'SLHn': 871.2,  # CHF (should be ~1000 USD after conversion)
    }

    data_source = StocksDataSource()
    converter = ForexConverter()

    results = []
    for symbol, expected_price_native in expected_prices.items():
        try:
            # Fetch latest price
            df = await data_source.get_ohlcv_data(symbol=symbol, lookback_days=5)

            if df is not None and len(df) > 0:
                fetched_price_native = df['close'].iloc[-1]
                native_currency = df.attrs.get('native_currency', 'USD')

                # Convert to USD for comparison
                if native_currency != 'USD':
                    fetched_price_usd = await converter.convert(
                        fetched_price_native,
                        native_currency,
                        'USD'
                    )
                    expected_price_usd = await converter.convert(
                        expected_price_native,
                        native_currency,
                        'USD'
                    )
                else:
                    fetched_price_usd = fetched_price_native
                    expected_price_usd = expected_price_native

                # Calculate difference
                diff_pct = abs((fetched_price_usd - expected_price_usd) / expected_price_usd) * 100

                status = "OK" if diff_pct < 5.0 else "WARN"

                results.append({
                    'Symbol': symbol,
                    'Expected': f"{expected_price_native:.2f} {native_currency}",
                    'Fetched': f"{fetched_price_native:.2f} {native_currency}",
                    'Diff %': f"{diff_pct:.2f}%",
                    'Status': status
                })

                print(f"[{status}] {symbol:8s} Expected: {expected_price_native:8.2f} {native_currency}, "
                      f"Fetched: {fetched_price_native:8.2f} {native_currency}, "
                      f"Diff: {diff_pct:5.2f}%")
            else:
                print(f"[ERR ] {symbol:8s} No data fetched")

        except Exception as e:
            print(f"[ERR ] {symbol:8s} Error: {e}")

    # Print summary
    if results:
        df = pd.DataFrame(results)
        print("\n" + df.to_string(index=False))


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("MULTI-CURRENCY STOCK DATA FETCHING TESTS")
    print("="*80)

    try:
        await test_currency_detector()
        await test_forex_converter()
        await test_stock_data_fetching()
        await test_price_comparison()

        print("\n" + "="*80)
        print("[OK] ALL TESTS COMPLETED")
        print("="*80)

    except Exception as e:
        print(f"\n[ERROR] TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
