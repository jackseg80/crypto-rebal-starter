"""Adapter exposing crypto holdings through Wealth models."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, List, Tuple

from models.wealth import (
    AccountModel,
    InstrumentModel,
    PositionModel,
    TransactionModel,
    PricePoint,
    ProposedTrade,
)
from services.taxonomy import Taxonomy
from services.pricing_service import get_prices as pricing_get_prices

logger = logging.getLogger(__name__)

_MODULE = "crypto"
_DEFAULT_SOURCE = "auto"
_DEFAULT_USER = "demo"


def _instrument_id(symbol: str) -> str:
    return symbol.upper()


async def _fetch_balances(user_id: str, source: str) -> Dict[str, Any]:
    from api.main import resolve_current_balances

    resolved = await resolve_current_balances(source=source, user_id=user_id)
    items = resolved.get("items", []) if isinstance(resolved, dict) else []
    logger.debug("[wealth][crypto] fetched %s raw balance rows", len(items))
    return {"source_used": resolved.get("source_used", _MODULE), "items": items}


def _group_for(symbol: str, taxonomy: Taxonomy) -> str:
    try:
        return taxonomy.group_for_alias(symbol)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.debug("[wealth][crypto] taxonomy lookup failed for %s: %s", symbol, exc)
        return "Others"


def _account_type(location: str) -> str:
    normalized = (location or "").lower()
    if any(keyword in normalized for keyword in ("wallet", "ledger", "vault")):
        return "wallet"
    if any(keyword in normalized for keyword in ("defi", "pool", "dex")):
        return "defi"
    return "exchange"


async def list_accounts(user_id: str = _DEFAULT_USER, source: str = _DEFAULT_SOURCE) -> List[AccountModel]:
    balances = await _fetch_balances(user_id=user_id, source=source)
    locations: Dict[str, str] = {}
    for item in balances.get("items", []):
        location = str(item.get("location") or "Portfolio")
        locations.setdefault(location, _account_type(location))
    if not locations:
        locations["Portfolio"] = "exchange"
    accounts = [
        AccountModel(id=f"{_MODULE}:{name.lower().replace(' ', '_')}", provider=_MODULE, type=acct_type, currency="USD")
        for name, acct_type in sorted(locations.items())
    ]
    logger.info("[wealth][crypto] accounts normalized=%s", len(accounts))
    return accounts


async def list_instruments(user_id: str = _DEFAULT_USER, source: str = _DEFAULT_SOURCE) -> List[InstrumentModel]:
    balances = await _fetch_balances(user_id=user_id, source=source)
    taxonomy = Taxonomy.load()
    instruments: Dict[str, InstrumentModel] = {}
    for item in balances.get("items", []):
        symbol = str(item.get("symbol") or item.get("alias") or "").upper()
        if not symbol:
            continue
        inst_id = _instrument_id(symbol)
        if inst_id in instruments:
            continue
        group = _group_for(symbol, taxonomy)
        instruments[inst_id] = InstrumentModel(
            id=inst_id,
            symbol=symbol,
            isin=None,
            name=symbol,
            asset_class="CRYPTO",
            sector=group,
            region=None,
        )
    instrument_list = sorted(instruments.values(), key=lambda inst: inst.symbol)
    logger.info("[wealth][crypto] instruments normalized=%s", len(instrument_list))
    return instrument_list


def _compute_weights(rows: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for row in rows:
        symbol = str(row.get("symbol") or row.get("alias") or "").upper()
        val = float(row.get("value_usd") or 0)
        if not symbol or val <= 0:
            continue
        totals[symbol] = totals.get(symbol, 0.0) + val
    portfolio_total = sum(totals.values()) or 1.0
    return {sym: val / portfolio_total for sym, val in totals.items()}


async def list_positions(user_id: str = _DEFAULT_USER, source: str = _DEFAULT_SOURCE) -> List[PositionModel]:
    balances = await _fetch_balances(user_id=user_id, source=source)
    taxonomy = Taxonomy.load()
    items = balances.get("items", [])
    weights = _compute_weights(items)
    positions: List[PositionModel] = []
    for item in items:
        symbol = str(item.get("symbol") or item.get("alias") or "").upper()
        if not symbol:
            continue
        quantity = float(item.get("amount") or item.get("quantity") or 0.0)
        if quantity == 0:
            continue
        market_value = float(item.get("value_usd") or 0.0) or None
        group = _group_for(symbol, taxonomy)
        location = str(item.get("location") or "Portfolio")
        tags = [f"group:{group}"]
        if location:
            tags.append(f"location:{location}")
        positions.append(
            PositionModel(
                instrument_id=_instrument_id(symbol),
                quantity=quantity,
                avg_price=None,
                currency="USD",
                market_value=market_value,
                pnl=None,
                weight=weights.get(symbol),
                tags=tags,
            )
        )
    logger.info("[wealth][crypto] positions normalized=%s", len(positions))
    return positions


async def list_transactions(
    user_id: str = _DEFAULT_USER, source: str = _DEFAULT_SOURCE, start: str | None = None, end: str | None = None
) -> List[TransactionModel]:
    logger.info("[wealth][crypto] transactions not yet mapped, returning empty list")
    return []


async def get_prices(
    instrument_ids: Iterable[str],
    granularity: str = "daily",
) -> List[PricePoint]:
    price_points = await pricing_get_prices(list(instrument_ids), granularity=granularity)
    logger.debug("[wealth][crypto] price points fetched=%s", len(price_points))
    return price_points


async def preview_rebalance(
    user_id: str = _DEFAULT_USER,
    source: str = _DEFAULT_SOURCE,
) -> List[ProposedTrade]:
    logger.info("[wealth][crypto] rebalance preview not implemented, returning empty list")
    return []


async def has_data(user_id: str = _DEFAULT_USER, source: str = _DEFAULT_SOURCE) -> bool:
    balances = await _fetch_balances(user_id=user_id, source=source)
    return any(float(item.get("value_usd") or 0) > 0 for item in balances.get("items", []))
