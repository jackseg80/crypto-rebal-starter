"""
Location assignment service for rebalancing actions.

Extracted from api/main.py (lines 821-902) as part of refactoring effort.
Handles assignment of exchange locations to trading actions, with special
logic for SELL actions (split by holdings across exchanges).
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def assign_locations_to_actions(
    plan: Dict[str, Any],
    rows: List[Dict[str, Any]],
    min_trade_usd: float = 25.0
) -> Dict[str, Any]:
    """
    Add location (exchange) information to trading actions.

    For SELL actions, splits the action across multiple exchanges proportionally
    to the actual holdings (value_usd) on each exchange.

    Args:
        plan: Rebalancing plan containing actions
        rows: Current balance rows with symbol, location, value_usd
        min_trade_usd: Minimum trade size in USD (default: 25.0)

    Returns:
        Updated plan with locations assigned to actions

    Logic:
        - If action already has a specific location (not Unknown/CoinTracking), keep it
        - For SELL actions: Split across exchanges proportionally to holdings
        - For BUY actions: Leave as-is (UI will choose exchange)
        - If split results in trades < min_trade_usd, consolidate to biggest exchange
    """
    logger.info(
        f"🔧 assign_locations_to_actions called with "
        f"{len(rows)} rows, {len(plan.get('actions', []))} actions"
    )

    # Build holdings map: holdings[symbol][location] -> total value_usd
    holdings: Dict[str, Dict[str, float]] = {}
    locations_seen = set()

    for r in rows or []:
        sym = (r.get("symbol") or "").upper()
        loc = r.get("location") or "Unknown"
        locations_seen.add(loc)
        val = float(r.get("value_usd") or 0.0)

        if sym and val > 0:
            holdings.setdefault(sym, {}).setdefault(loc, 0.0)
            holdings[sym][loc] += val

    logger.info(
        f"📍 assign_locations_to_actions: "
        f"{len(locations_seen)} locations found: {sorted(locations_seen)}"
    )
    logger.info(f"📍 Sample holdings: {dict(list(holdings.items())[:3])}")

    actions = plan.get("actions") or []
    out_actions: List[Dict[str, Any]] = []

    for a in actions:
        sym = (a.get("symbol") or "").upper()
        usd = float(a.get("usd") or 0.0)
        loc = a.get("location")

        # If location already defined (and not generic), keep it
        if loc and loc not in ["Unknown", "CoinTracking", "Cointracking"]:
            out_actions.append(a)
            continue

        # SELL: Split across exchanges where coin is held
        if usd < 0 and sym in holdings and holdings[sym]:
            to_sell = -usd
            locs = [(ex, v) for ex, v in holdings[sym].items() if v > 0]
            total_val = sum(v for _, v in locs)

            # No holdings detected -> leave as 'Unknown'
            if total_val <= 0:
                a["location"] = "Unknown"
                out_actions.append(a)
                continue

            # Proportional allocation by value_usd
            alloc_sum = 0.0
            tmp_parts: List[Dict[str, Any]] = []

            for i, (ex, val) in enumerate(locs):
                share = to_sell * (val / total_val)

                if i < len(locs) - 1:
                    part = round(share, 2)
                    alloc_sum += part
                else:
                    # Last part = remainder for exact sum
                    part = round(to_sell - alloc_sum, 2)

                # Only create action if above minimum threshold
                if part >= max(0.01, float(min_trade_usd or 0)):
                    na = dict(a)
                    na["usd"] = -part
                    na["location"] = ex
                    tmp_parts.append(na)

            # If all parts below min_trade_usd, consolidate to biggest exchange
            if not tmp_parts:
                ex_big = max(locs, key=lambda t: t[1])[0]
                na = dict(a)
                na["location"] = ex_big
                tmp_parts.append(na)

            out_actions.extend(tmp_parts)
        else:
            # BUY or unknown symbol: leave as-is (UI will choose exchange)
            out_actions.append(a)

    plan["actions"] = out_actions
    return plan
