"""
General utility functions for API operations.

Extracted from api/main.py (lines 440-475) as part of Phase 3 refactoring.
Handles data normalization, parsing, and transformation.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def parse_min_usd(raw: str | None, default: float = 1.0) -> float:
    """
    Parse minimum USD threshold parameter with fallback.

    Args:
        raw: Raw string value from query parameter
        default: Default value if parsing fails (default: 1.0)

    Returns:
        Parsed float value or default

    Notes:
        - Returns default if raw is None
        - Logs debug message on parsing failure
        - Used for filtering dust assets across endpoints
    """
    try:
        return float(raw) if raw is not None else default
    except Exception as e:
        logger.debug(f"Failed to parse min_usd value '{raw}', using default {default}: {e}")
        return default


def to_rows(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize connector output to standardized row format.

    Handles multiple input formats from different connectors
    (CoinTracking CSV, CoinTracking API, Saxo, etc.)

    Args:
        raw: List of balance dicts from connector with varying key names

    Returns:
        List of normalized dicts with keys:
        - symbol: str (token/asset symbol)
        - alias: str (display name)
        - value_usd: float (USD value)
        - amount: float or None (quantity)
        - location: str (exchange/wallet)

    Key normalization:
        - symbol: Accepts "symbol", "coin", "name"
        - alias: Falls back to "name" or "symbol"
        - value_usd: Accepts "value_usd", "value"
        - location: Accepts "location", "exchange" (default: "Unknown")

    Notes:
        - Filters out rows without symbol
        - Converts all values to appropriate types
        - Amount can be None if not provided by connector
    """
    out: List[Dict[str, Any]] = []
    for r in raw or []:
        symbol = r.get("symbol") or r.get("coin") or r.get("name")
        if not symbol:
            continue
        out.append({
            "symbol": str(symbol),
            "alias": (r.get("alias") or r.get("name") or r.get("symbol")),
            "value_usd": float(r.get("value_usd") or r.get("value") or 0.0),
            "amount": float(r.get("amount") or 0.0) if r.get("amount") else None,
            "location": r.get("location") or r.get("exchange") or "Unknown",
        })
    return out


def norm_primary_symbols(x: Any) -> Dict[str, List[str]]:
    """
    Normalize primary symbol grouping configuration.

    Accepts two formats:
    1. Dict with comma-separated strings: {"BTC": "BTC,TBTC,WBTC"}
    2. Dict with lists: {"BTC": ["BTC", "TBTC", "WBTC"]}

    Args:
        x: Configuration dict in either format, or None

    Returns:
        Normalized dict mapping primary symbol -> list of aliases
        Example: {"BTC": ["BTC", "TBTC", "WBTC"], "ETH": ["ETH", "WETH"]}

    Used for:
        - Grouping wrapped tokens with primary tokens
        - Rebalancing calculations across token variants
        - Display aggregation in UI

    Notes:
        - Empty strings are filtered out
        - Whitespace is stripped from all symbols
        - Returns empty dict if input is not a dict
    """
    out: Dict[str, List[str]] = {}
    if isinstance(x, dict):
        for g, v in x.items():
            if isinstance(v, str):
                # Split comma-separated string
                out[g] = [s.strip() for s in v.split(",") if s.strip()]
            elif isinstance(v, list):
                # Convert list to strings
                out[g] = [str(s).strip() for s in v if str(s).strip()]
    return out
