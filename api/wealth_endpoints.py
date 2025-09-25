"""Wealth namespace endpoints unifying holdings across providers."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from adapters import banks_adapter, crypto_adapter, saxo_adapter
from models.wealth import (
    AccountModel,
    InstrumentModel,
    PositionModel,
    TransactionModel,
    PricePoint,
    ProposedTrade,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wealth", tags=["Wealth"])
_SUPPORTED_MODULES = {"crypto", "saxo", "banks"}


async def _module_available(module: str) -> bool:
    try:
        if module == "crypto":
            return await crypto_adapter.has_data()
        if module == "saxo":
            return await saxo_adapter.has_data()
        if module == "banks":
            return await banks_adapter.has_data()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[wealth] availability probe failed for %s: %s", module, exc)
        return False
    return False


def _ensure_module(module: str) -> None:
    if module not in _SUPPORTED_MODULES:
        raise HTTPException(status_code=404, detail="unknown_module")


@router.get("/modules", response_model=List[str])
async def list_modules() -> List[str]:
    discovered = []
    for module in _SUPPORTED_MODULES:
        if await _module_available(module):
            discovered.append(module)
    if not discovered:
        discovered = sorted(_SUPPORTED_MODULES)
    logger.info("[wealth] modules_available=%s", discovered)
    return discovered


@router.get("/{module}/accounts", response_model=List[AccountModel])
async def get_accounts(
    module: str,
    user_id: str = Query("demo", description="User identifier for crypto sources"),
    source: str = Query("auto", description="Crypto source resolver"),
) -> List[AccountModel]:
    _ensure_module(module)
    if module == "crypto":
        accounts = await crypto_adapter.list_accounts(user_id=user_id, source=source)
    elif module == "saxo":
        accounts = await saxo_adapter.list_accounts()
    else:
        accounts = await banks_adapter.list_accounts()
    logger.info("[wealth] served %s accounts for module=%s", len(accounts), module)
    return accounts


@router.get("/{module}/instruments", response_model=List[InstrumentModel])
async def get_instruments(
    module: str,
    user_id: str = Query("demo"),
    source: str = Query("auto"),
) -> List[InstrumentModel]:
    _ensure_module(module)
    if module == "crypto":
        instruments = await crypto_adapter.list_instruments(user_id=user_id, source=source)
    elif module == "saxo":
        instruments = await saxo_adapter.list_instruments()
    else:
        instruments = await banks_adapter.list_instruments()
    logger.info("[wealth] served %s instruments for module=%s", len(instruments), module)
    return instruments


@router.get("/{module}/positions", response_model=List[PositionModel])
async def get_positions(
    module: str,
    user_id: str = Query("demo"),
    source: str = Query("auto"),
    asof: Optional[str] = Query(None, description="Date override (yyyy-mm-dd)")
) -> List[PositionModel]:
    _ensure_module(module)
    if module == "crypto":
        positions = await crypto_adapter.list_positions(user_id=user_id, source=source)
    elif module == "saxo":
        positions = await saxo_adapter.list_positions()
    else:
        positions = await banks_adapter.list_positions()
    logger.info("[wealth] served %s positions for module=%s asof=%s", len(positions), module, asof or "latest")
    return positions


@router.get("/{module}/transactions", response_model=List[TransactionModel])
async def get_transactions(
    module: str,
    user_id: str = Query("demo"),
    source: str = Query("auto"),
    start: Optional[str] = Query(None, alias="from"),
    end: Optional[str] = Query(None, alias="to"),
) -> List[TransactionModel]:
    _ensure_module(module)
    if module == "crypto":
        transactions = await crypto_adapter.list_transactions(user_id=user_id, source=source, start=start, end=end)
    elif module == "saxo":
        transactions = await saxo_adapter.list_transactions(start=start, end=end)
    else:
        transactions = await banks_adapter.list_transactions(start=start, end=end)
    logger.info(
        "[wealth] served %s transactions for module=%s window=%s/%s",
        len(transactions),
        module,
        start or "*",
        end or "*",
    )
    return transactions


@router.get("/{module}/prices", response_model=List[PricePoint])
async def get_prices(
    module: str,
    ids: List[str] = Query(..., description="Instrument identifiers"),
    granularity: str = Query("daily", regex="^(daily|intraday)$"),
    user_id: str = Query("demo"),
    source: str = Query("auto"),
) -> List[PricePoint]:
    _ensure_module(module)
    if not ids:
        raise HTTPException(status_code=400, detail="missing_ids")
    if module == "crypto":
        prices = await crypto_adapter.get_prices(ids, granularity=granularity)
    elif module == "saxo":
        prices = await saxo_adapter.get_prices(ids, granularity=granularity)
    else:
        prices = await banks_adapter.get_prices(ids, granularity=granularity)
    logger.info("[wealth] served %s price points for module=%s", len(prices), module)
    return prices


@router.post("/{module}/rebalance/preview", response_model=List[ProposedTrade])
async def preview_rebalance(
    module: str,
    payload: Optional[dict] = Body(default=None, description="Module-specific preview payload"),
    user_id: str = Query("demo"),
    source: str = Query("auto"),
) -> List[ProposedTrade]:
    _ensure_module(module)
    if module == "crypto":
        trades = await crypto_adapter.preview_rebalance(user_id=user_id, source=source)
    elif module == "saxo":
        trades = await saxo_adapter.preview_rebalance()
    else:
        trades = await banks_adapter.preview_rebalance()
    logger.info(
        "[wealth] rebalance preview module=%s payload_keys=%s returned=%s",
        module,
        sorted(list(payload.keys())) if payload else [],
        len(trades),
    )
    return trades
