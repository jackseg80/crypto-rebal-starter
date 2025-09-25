"""MVP adapter exposing bank cash holdings for the Wealth namespace."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from models.wealth import AccountModel, InstrumentModel, PositionModel, PricePoint, ProposedTrade, TransactionModel
from services.fx_service import convert as fx_convert

logger = logging.getLogger(__name__)

_MODULE = "banks"
_STORAGE_PATH = Path("data/wealth/banks_snapshot.json")


def _ensure_storage() -> None:
    _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _STORAGE_PATH.exists():
        _STORAGE_PATH.write_text(json.dumps({"accounts": []}), encoding="utf-8")


def _load_snapshot() -> dict:
    _ensure_storage()
    try:
        with _STORAGE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                data.setdefault("accounts", [])
                return data
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[wealth][banks] failed to load snapshot: %s", exc)
    return {"accounts": []}


def _total_usd(accounts: List[dict]) -> float:
    total = 0.0
    for account in accounts:
        balance = float(account.get("balance") or 0.0)
        currency = str(account.get("currency") or "USD").upper()
        total += fx_convert(balance, currency, "USD")
    return total


async def list_accounts() -> List[AccountModel]:
    snapshot = _load_snapshot()
    accounts: List[AccountModel] = []
    for account in snapshot.get("accounts", []):
        accounts.append(
            AccountModel(
                id=f"{_MODULE}:{account.get('id', 'account')}",
                provider=_MODULE,
                type="bank",
                currency=str(account.get("currency") or "USD").upper(),
            )
        )
    if not accounts:
        accounts.append(AccountModel(id=f"{_MODULE}:placeholder", provider=_MODULE, type="bank", currency="USD"))
    logger.info("[wealth][banks] accounts normalized=%s", len(accounts))
    return accounts


async def list_instruments() -> List[InstrumentModel]:
    snapshot = _load_snapshot()
    instruments: dict = {}
    for account in snapshot.get("accounts", []):
        currency = str(account.get("currency") or "USD").upper()
        inst_id = f"CASH:{currency}"
        if inst_id in instruments:
            continue
        instruments[inst_id] = InstrumentModel(
            id=inst_id,
            symbol=currency,
            isin=None,
            name=f"Cash {currency}",
            asset_class="CASH",
            sector="Cash",
            region=None,
        )
    instrument_list = sorted(instruments.values(), key=lambda inst: inst.symbol)
    logger.info("[wealth][banks] instruments normalized=%s", len(instrument_list))
    return instrument_list


async def list_positions() -> List[PositionModel]:
    snapshot = _load_snapshot()
    accounts = snapshot.get("accounts", [])
    total_usd = _total_usd(accounts) or 1.0
    positions: List[PositionModel] = []
    for account in accounts:
        balance = float(account.get("balance") or 0.0)
        if balance == 0:
            continue
        currency = str(account.get("currency") or "USD").upper()
        inst_id = f"CASH:{currency}"
        market_value_usd = fx_convert(balance, currency, "USD")
        weight = market_value_usd / total_usd if total_usd else None
        positions.append(
            PositionModel(
                instrument_id=inst_id,
                quantity=balance,
                avg_price=1.0,
                currency=currency,
                market_value=balance,
                pnl=None,
                weight=weight,
                tags=["asset_class:CASH"],
            )
        )
    logger.info("[wealth][banks] positions normalized=%s", len(positions))
    return positions


async def list_transactions(start: str | None = None, end: str | None = None) -> List[TransactionModel]:
    logger.info("[wealth][banks] transactions not mapped yet, returning empty list")
    return []


async def get_prices(instrument_ids: Iterable[str], granularity: str = "daily") -> List[PricePoint]:
    price_points: List[PricePoint] = []
    timestamp = datetime.utcnow()
    for instrument_id in instrument_ids:
        if instrument_id.startswith("CASH:"):
            currency = instrument_id.split(":", 1)[1]
            price_points.append(
                PricePoint(
                    instrument_id=instrument_id,
                    ts=timestamp,
                    price=fx_convert(1.0, currency, "USD"),
                    currency="USD",
                    source="fx_service",
                )
            )
    return price_points


async def preview_rebalance() -> List[ProposedTrade]:
    logger.info("[wealth][banks] rebalance preview not implemented, returning empty list")
    return []


async def has_data() -> bool:
    snapshot = _load_snapshot()
    return any(float(account.get("balance") or 0.0) > 0 for account in snapshot.get("accounts", []))
