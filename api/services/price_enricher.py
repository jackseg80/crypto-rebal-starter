"""
Price enrichment service for rebalancing actions.

Extracted from api/main.py (lines 1050-1215, 445-473) as part of refactoring effort.
Handles enrichment of trading actions with prices from local balances, external APIs,
or hybrid approach with intelligent fallback.
"""

import os
import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def get_data_age_minutes(source_used: str) -> float:
    """
    Get approximate data age in minutes based on source type.

    Args:
        source_used: Data source identifier (cointracking, cointracking_api, etc.)

    Returns:
        Age in minutes (float)

    Logic:
        - cointracking (CSV): File modification time
        - cointracking_api: Fresh data (1 min, 60s cache)
        - stub/other: 0 minutes (always fresh)
    """
    if source_used == "cointracking":
        # For local CSV, check file modification time
        csv_path = os.getenv("COINTRACKING_CSV")
        if not csv_path:
            # Use same path resolution as connector
            default_cur = "CoinTracking - Current Balance_mini.csv"
            candidates = [os.path.join("data", default_cur), default_cur]
            for candidate in candidates:
                if candidate and os.path.exists(candidate):
                    csv_path = candidate
                    break

        if csv_path and os.path.exists(csv_path):
            try:
                mtime = os.path.getmtime(csv_path)
                age_seconds = time.time() - mtime
                return age_seconds / 60.0
            except Exception as e:
                logger.warning(f"Failed to get mtime for CSV file {csv_path}: {e}")

        # Fallback: Consider CSV data as recent to use local prices
        return 5.0  # 5 minutes default (recent)

    elif source_used == "cointracking_api":
        # API data is fresh (60s cache)
        return 1.0
    else:
        # Stub or other sources
        return 0.0


async def enrich_actions_with_prices(
    plan: Dict[str, Any],
    rows: List[Dict[str, Any]],
    pricing_mode: str = "local",
    source_used: str = "",
    diagnostic: bool = False
) -> Dict[str, Any]:
    """
    Enrich trading actions with prices using 3 modes.

    Pricing modes:
        - "local": Use only prices derived from balance data
        - "auto": Use only external API prices
        - "hybrid": Start with local, correct with market if data is stale or has large deviation

    Args:
        plan: Rebalancing plan containing actions
        rows: Current balance rows with symbol, amount, value_usd
        pricing_mode: Pricing strategy ("local", "auto", "hybrid")
        source_used: Data source identifier (for age calculation)
        diagnostic: If True, include detailed pricing information in response

    Returns:
        Updated plan with price_used, price_source, est_quantity added to actions

    Hybrid Logic:
        - If data age > max_age_min (default: 30 min): Prefer market prices
        - If data is fresh: Prefer local prices, fallback to market if missing
        - If local price unavailable: Use market price as fallback
    """
    # Hybrid configuration
    max_age_min = float(os.getenv("PRICE_HYBRID_MAX_AGE_MIN", "30"))
    max_deviation_pct = float(os.getenv("PRICE_HYBRID_DEVIATION_PCT", "5.0"))

    # Calculate local prices (always needed for hybrid)
    local_price_map: Dict[str, float] = {}
    for row in rows or []:
        sym = row.get("symbol")
        if not sym:
            continue
        value_usd = float(row.get("value_usd") or 0.0)
        amount = float(row.get("amount") or 0.0)
        if value_usd > 0 and amount > 0:
            local_price_map[sym.upper()] = value_usd / amount

    # Prepare prices based on mode
    price_map: Dict[str, float] = {}
    market_price_map: Dict[str, float] = {}

    original_mode = pricing_mode

    if pricing_mode == "local":
        price_map = local_price_map.copy()

    elif pricing_mode == "auto":
        # Auto behaves like hybrid: prefer local when fresh, else market
        price_map = local_price_map.copy()

        symbols = set()
        for a in plan.get("actions", []) or []:
            sym = a.get("symbol")
            if sym:
                symbols.add(sym.upper())

        data_age_min = get_data_age_minutes(source_used)
        needs_market_correction = data_age_min > max_age_min
        missing_local_prices = symbols - set(local_price_map.keys())

        if (needs_market_correction or missing_local_prices) and symbols:
            try:
                from services.pricing import aget_prices_usd
                market_price_map = await aget_prices_usd(list(symbols))
            except Exception as e:
                logger.debug(f"Async pricing failed, falling back to sync: {e}")
                from services.pricing import get_prices_usd
                market_price_map = get_prices_usd(list(symbols))
            market_price_map = {k: v for k, v in market_price_map.items() if v is not None}

        # Force hybrid selection logic for next step
        pricing_mode = "hybrid"

    elif pricing_mode == "hybrid":
        # Start with local prices
        price_map = local_price_map.copy()

        # Determine if correction is needed
        data_age_min = get_data_age_minutes(source_used)
        needs_market_correction = data_age_min > max_age_min

        # Get required symbols
        symbols = set()
        for a in plan.get("actions", []) or []:
            sym = a.get("symbol")
            if sym:
                symbols.add(sym.upper())

        # Check if local prices are available for needed symbols
        missing_local_prices = symbols - set(local_price_map.keys())
        needs_market_fallback = bool(missing_local_prices)

        # Fetch market prices if data is stale OR local prices missing
        if (needs_market_correction or needs_market_fallback) and symbols:
            try:
                from services.pricing import aget_prices_usd
                market_price_map = await aget_prices_usd(list(symbols))
            except Exception as e:
                logger.debug(f"Async pricing failed, falling back to sync: {e}")
                from services.pricing import get_prices_usd
                market_price_map = get_prices_usd(list(symbols))
            market_price_map = {k: v for k, v in market_price_map.items() if v is not None}

    # Enrich actions
    pricing_details = [] if diagnostic else None
    for a in plan.get("actions", []) or []:
        sym = a.get("symbol")
        if not sym or a.get("usd") is None or a.get("price_used"):
            continue

        sym_upper = sym.upper()
        local_price = local_price_map.get(sym_upper)
        market_price = market_price_map.get(sym_upper)

        # Determine final price and source
        final_price = None
        price_source = "local"

        if pricing_mode == "local":
            if local_price:
                final_price = local_price
                price_source = "local"
            # No fallback in pure local mode

        elif pricing_mode == "auto":
            if market_price:
                final_price = market_price
                price_source = "market"

        elif pricing_mode == "hybrid":
            # Hybrid logic with intelligent fallback
            data_age_min = get_data_age_minutes(source_used)

            if data_age_min > max_age_min:
                # Stale data -> prefer market prices
                if market_price:
                    final_price = market_price
                    price_source = "market"
                elif local_price:
                    final_price = local_price
                    price_source = "local"
            else:
                # Fresh data -> prefer local prices, fallback to market
                if local_price:
                    final_price = local_price
                    price_source = "local"
                elif market_price:
                    final_price = market_price
                    price_source = "market"

        # Apply final price
        if final_price and final_price > 0:
            a["price_used"] = float(final_price)
            a["price_source"] = price_source
            try:
                a["est_quantity"] = round(float(a["usd"]) / float(final_price), 8)
            except Exception as e:
                logger.warning(
                    f"Failed to calculate est_quantity for action {a.get('symbol')}: {e}"
                )

        if diagnostic:
            pricing_details.append({
                "symbol": sym_upper,
                "local_price": local_price,
                "market_price": market_price,
                "effective_price": final_price,
                "price_source": price_source
            })

    # Add pricing metadata
    if not plan.get("meta"):
        plan["meta"] = {}

    # Report external mode (UI) and internal strategy
    plan["meta"]["pricing_mode"] = original_mode
    plan["meta"]["pricing_internal_mode"] = pricing_mode
    if pricing_mode == "hybrid":
        plan["meta"]["pricing_hybrid"] = {
            "max_age_min": max_age_min,
            "max_deviation_pct": max_deviation_pct,
            "data_age_min": get_data_age_minutes(source_used)
        }
    if diagnostic and pricing_details is not None:
        plan["meta"]["pricing_details"] = pricing_details

    return plan
