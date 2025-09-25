"""Legacy Saxo endpoints delegating to Wealth namespace for compatibility."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile

from adapters.saxo_adapter import ingest_file
from api.wealth_endpoints import (
    get_accounts as wealth_get_accounts,
    get_instruments as wealth_get_instruments,
    get_positions as wealth_get_positions,
    get_transactions as wealth_get_transactions,
    get_prices as wealth_get_prices,
    preview_rebalance as wealth_preview_rebalance,
)
from models.wealth import AccountModel, InstrumentModel, PositionModel, PricePoint, ProposedTrade, TransactionModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/saxo", tags=["Saxo Bank"])

_MODULE = "saxo"


def _legacy_log(path: str) -> None:
    logger.info("[legacy-compat] %s -> /api/wealth/%s%s", path, _MODULE, path)


@router.post("/import")
async def import_portfolio(
    file: UploadFile = File(..., description="Saxo export file"),
    portfolio_name: str = Form("Saxo Portfolio"),
) -> dict:
    """Import Saxo CSV/XLSX and persist through the wealth adapter."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing_file")

    suffix = Path(file.filename).suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)
    try:
        portfolio = ingest_file(str(tmp_path), portfolio_name=portfolio_name)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not portfolio:
        raise HTTPException(status_code=422, detail="import_failed")

    _legacy_log("/import")
    return {"portfolio": portfolio, "delegated": True}


@router.get("/accounts", response_model=List[AccountModel])
async def list_accounts() -> List[AccountModel]:
    _legacy_log("/accounts")
    return await wealth_get_accounts(module=_MODULE)


@router.get("/instruments", response_model=List[InstrumentModel])
async def list_instruments() -> List[InstrumentModel]:
    _legacy_log("/instruments")
    return await wealth_get_instruments(module=_MODULE)


@router.get("/positions")
async def list_positions(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    _legacy_log("/positions")
    wealth_positions = await wealth_get_positions(module=_MODULE)
    # wealth endpoint returns pydantic models; convert to plain dicts
    normalized = [p.model_dump() if isinstance(p, PositionModel) else p for p in wealth_positions]
    total = len(normalized)
    window = normalized[offset : offset + limit]
    return {
        "positions": window,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        },
    }


@router.get("/transactions", response_model=List[TransactionModel])
async def list_transactions(
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> List[TransactionModel]:
    _legacy_log("/transactions")
    return await wealth_get_transactions(module=_MODULE, start=start, end=end)


@router.get("/prices", response_model=List[PricePoint])
async def list_prices(ids: List[str], granularity: str = "daily") -> List[PricePoint]:
    if not ids:
        raise HTTPException(status_code=400, detail="missing_ids")
    _legacy_log("/prices")
    return await wealth_get_prices(module=_MODULE, ids=ids, granularity=granularity)


@router.post("/rebalance/preview", response_model=List[ProposedTrade])
async def preview_rebalance(payload: Optional[dict] = Body(default=None)) -> List[ProposedTrade]:
    _legacy_log("/rebalance/preview")
    return await wealth_preview_rebalance(module=_MODULE, payload=payload)
