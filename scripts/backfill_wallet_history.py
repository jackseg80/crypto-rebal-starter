"""
Backfill local price history for the currently held symbols.

Usage (PowerShell):
python .\scripts\backfill_wallet_history.py --base-url http://127.0.0.1:8000 --min-usd 5 --days 365
"""

import argparse
import asyncio
import logging
from typing import Any, Dict, List

import httpx

from services.price_history import download_historical_data

logger = logging.getLogger("backfill_wallet_history")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill cached price history for wallet holdings")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--min-usd", type=float, default=5.0, help="Minimum USD value per asset when querying balances")
    parser.add_argument("--days", type=int, default=365, help="Number of days of history to backfill")
    parser.add_argument("--user", default="demo", help="User identifier passed via X-User header")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh even if cache exists")
    parser.add_argument("--concurrency", type=int, default=5, help="Maximum concurrent download tasks")
    return parser.parse_args()


async def fetch_symbols(base_url: str, min_usd: float, user: str) -> List[str]:
    endpoint = f"{base_url.rstrip('/')}/balances/current"
    params = {"min_usd": min_usd}
    headers = {"X-User": user}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(endpoint, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()

    items: List[Dict[str, Any]] = payload.get("items") if isinstance(payload, dict) else payload
    symbols: List[str] = []
    for item in items or []:
        symbol = (item.get("symbol") or "").upper()
        value = float(item.get("value_usd") or 0.0)
        if symbol and value >= min_usd:
            symbols.append(symbol)
    return sorted(set(symbols))


async def backfill_symbol(symbol: str, days: int, force_refresh: bool, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
    async with semaphore:
        try:
            success = await download_historical_data(symbol, days=days, force_refresh=force_refresh)
            return {"symbol": symbol, "success": bool(success)}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Backfill failed for %s", symbol)
            return {"symbol": symbol, "success": False, "error": str(exc)}


async def main_async(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    symbols = await fetch_symbols(args.base_url, args.min_usd, args.user)
    if not symbols:
        logger.warning("No symbols found above the %.2f USD threshold", args.min_usd)
        return 0

    logger.info("Backfilling history for %d symbols (days=%d, force_refresh=%s)", len(symbols), args.days, args.force_refresh)

    semaphore = asyncio.Semaphore(max(1, args.concurrency))
    tasks = [backfill_symbol(symbol, args.days, args.force_refresh, semaphore) for symbol in symbols]
    results = await asyncio.gather(*tasks)

    succeeded = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    logger.info("Completed backfill: %d succeeded, %d failed", len(succeeded), len(failed))
    if failed:
        for entry in failed:
            logger.warning(" - %s: %s", entry["symbol"], entry.get("error", "unknown error"))
    else:
        logger.info("All symbols backfilled successfully")

    return 0 if not failed else 1


def main() -> None:
    args = parse_args()
    exit_code = asyncio.run(main_async(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
