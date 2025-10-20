"""
CoinTracking-specific helper functions for exchange location management.

Extracted from api/main.py (lines 381-437) as part of Phase 3 refactoring.
Handles exchange classification, location normalization, and CT-API integration.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def normalize_loc(label: str) -> str:
    """
    Normalize exchange location label to standard format.

    Args:
        label: Raw exchange location label

    Returns:
        Normalized exchange name (e.g., "Binance", "Unknown")
    """
    from constants import normalize_exchange_name
    return normalize_exchange_name(label or "Unknown")


def classify_location(loc: str) -> int:
    """
    Classify exchange location into categories for sell priority.

    Args:
        loc: Exchange location label

    Returns:
        Classification code:
        - 0: Fast CEX (Binance, Kraken, Coinbase, etc.)
        - 1: DeFi (Uniswap, Pancakeswap, Metamask, etc.)
        - 2: Cold storage (Ledger, Trezor, hardware wallets)
        - 3: Other (unknown or unclassified)

    Used for determining optimal sell execution path.
    """
    from constants import FAST_SELL_EXCHANGES, DEFI_HINTS, COLD_HINTS

    L = normalize_loc(loc)
    if any(L.startswith(x) for x in FAST_SELL_EXCHANGES):
        return 0  # CEX rapide
    if any(h in L for h in DEFI_HINTS):
        return 1  # DeFi
    if any(h in L for h in COLD_HINTS):
        return 2  # Cold/Hardware
    return 3  # reste


def pick_primary_location_for_symbol(symbol: str, detailed_holdings: dict) -> str:
    """
    Find the exchange where a symbol has the highest USD value.

    Args:
        symbol: Token symbol (e.g., "BTC", "ETH")
        detailed_holdings: Dict mapping location -> list of asset dicts
            Each asset dict should have: symbol, value_usd

    Returns:
        Exchange name with highest value for this symbol (default: "CoinTracking")

    Used for determining primary trading venue for rebalancing actions.
    """
    best_loc, best_val = "CoinTracking", 0.0
    for loc, assets in (detailed_holdings or {}).items():
        for a in assets or []:
            if a.get("symbol") == symbol:
                v = float(a.get("value_usd") or 0)
                if v > best_val:
                    best_val, best_loc = v, loc
    return best_loc


async def load_ctapi_exchanges(min_usd: float = 0.0) -> dict:
    """
    Fetch balance data grouped by exchange via CoinTracking API.

    Calls CT-API getGroupedBalance + getBalance to retrieve:
    - Exchange summary (location, total_value_usd, asset_count, assets)
    - Detailed holdings per exchange (location -> assets)

    Args:
        min_usd: Minimum USD threshold to filter assets and exchanges (default: 0.0)

    Returns:
        Dict with keys:
        - "exchanges": List[Dict] - Exchange summaries sorted by total_value_usd desc
        - "detailed_holdings": Dict[str, List[Dict]] - Location -> asset list

    Exchange summary structure:
        {
            "location": str,
            "total_value_usd": float,
            "asset_count": int,
            "assets": List[Dict] - Sorted by value_usd desc
        }

    Asset structure:
        {
            "symbol": str,
            "amount": float,
            "value_usd": float,
            "price_usd": float,
            "location": str
        }

    Note: If min_usd is specified, filters assets and recalculates exchange totals.
    """
    try:
        from connectors import cointracking_api as ct_api
    except ImportError:
        try:
            import cointracking_api as ct_api
        except ImportError:
            logger.error("CoinTracking API module not available")
            return {"exchanges": [], "detailed_holdings": {}}

    payload = await ct_api.get_balances_by_exchange_via_api()
    exchanges = payload.get("exchanges") or []
    detailed = payload.get("detailed_holdings") or {}

    # Filter by min_usd threshold if specified
    if min_usd and detailed:
        filtered = {}
        for loc, assets in detailed.items():
            keep = [a for a in (assets or []) if float(a.get("value_usd") or 0) >= min_usd]
            if keep:
                filtered[loc] = keep
        detailed = filtered

        # Recalculate exchange totals
        ex2 = []
        for loc, assets in detailed.items():
            tv = sum(float(a.get("value_usd") or 0) for a in assets)
            if tv >= min_usd:
                ex2.append({
                    "location": loc,
                    "total_value_usd": tv,
                    "asset_count": len(assets),
                    "assets": sorted(
                        assets,
                        key=lambda x: float(x.get("value_usd") or 0),
                        reverse=True
                    )
                })
        exchanges = sorted(ex2, key=lambda x: x["total_value_usd"], reverse=True)

    return {"exchanges": exchanges, "detailed_holdings": detailed}
