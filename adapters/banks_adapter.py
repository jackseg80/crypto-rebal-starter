"""MVP adapter exposing bank cash holdings for the Wealth namespace - Multi-tenant."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from models.wealth import AccountModel, InstrumentModel, PositionModel, PricePoint, ProposedTrade, TransactionModel
from services.fx_service import convert as fx_convert

logger = logging.getLogger(__name__)

_MODULE = "banks"


def _get_storage_path(user_id: str) -> Path:
    """Return user-specific storage path for banks snapshot."""
    return Path(f"data/users/{user_id}/banks/snapshot.json")


def _ensure_storage(user_id: str) -> None:
    """Ensure storage directory and file exist for user."""
    path = _get_storage_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"accounts": []}), encoding="utf-8")


def _load_snapshot(user_id: str) -> dict:
    """Load banks snapshot for specific user."""
    _ensure_storage(user_id)
    path = _get_storage_path(user_id)
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                data.setdefault("accounts", [])
                return data
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[wealth][banks] failed to load snapshot for user=%s: %s", user_id, exc)
    return {"accounts": []}


def _save_snapshot(data: dict, user_id: str) -> None:
    """Save banks snapshot for specific user (atomic write)."""
    _ensure_storage(user_id)
    path = _get_storage_path(user_id)

    # Atomic write: write to temp file, then rename
    temp_path = path.with_suffix('.tmp')
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        temp_path.replace(path)
        logger.info("[wealth][banks] snapshot saved for user=%s with %s accounts", user_id, len(data.get("accounts", [])))
    except Exception as exc:
        logger.error("[wealth][banks] failed to save snapshot for user=%s: %s", user_id, exc)
        if temp_path.exists():
            temp_path.unlink()
        raise


def _total_usd(accounts: List[dict]) -> float:
    """Calculate total USD value across all accounts."""
    total = 0.0
    for account in accounts:
        balance = float(account.get("balance") or 0.0)
        currency = str(account.get("currency") or "USD").upper()
        total += fx_convert(balance, currency, "USD")
    return total


async def list_accounts(user_id: str) -> List[AccountModel]:
    """List bank accounts for user (Wealth namespace format)."""
    snapshot = _load_snapshot(user_id)
    accounts: List[AccountModel] = []
    for account in snapshot.get("accounts", []):
        # Map bank_name + account_type to AccountModel.type
        bank_name = account.get("bank_name", "Unknown Bank")
        account_type = account.get("account_type", "other")
        display_type = f"{bank_name} ({account_type})"

        accounts.append(
            AccountModel(
                id=f"{_MODULE}:{account.get('id', 'account')}",
                provider=_MODULE,
                type=display_type,
                currency=str(account.get("currency") or "USD").upper(),
            )
        )

    # No placeholder for multi-tenant - empty list is valid
    logger.info("[wealth][banks] accounts normalized=%s for user=%s", len(accounts), user_id)
    return accounts


async def list_instruments(user_id: str) -> List[InstrumentModel]:
    """List unique currencies as instruments for user."""
    snapshot = _load_snapshot(user_id)
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
    logger.info("[wealth][banks] instruments normalized=%s for user=%s", len(instrument_list), user_id)
    return instrument_list


async def list_positions(user_id: str) -> List[PositionModel]:
    """List bank positions aggregated by currency for user."""
    snapshot = _load_snapshot(user_id)
    accounts = snapshot.get("accounts", [])
    total_usd = _total_usd(accounts) or 1.0

    # Aggregate by currency
    positions_by_currency: dict = {}
    for account in accounts:
        balance = float(account.get("balance") or 0.0)
        if balance <= 0:
            continue
        currency = str(account.get("currency") or "USD").upper()

        if currency in positions_by_currency:
            positions_by_currency[currency]["quantity"] += balance
        else:
            positions_by_currency[currency] = {
                "quantity": balance,
                "currency": currency
            }

    # Build PositionModel list
    positions: List[PositionModel] = []
    for currency, data in positions_by_currency.items():
        inst_id = f"CASH:{currency}"
        quantity = data["quantity"]
        market_value_usd = fx_convert(quantity, currency, "USD")
        weight = market_value_usd / total_usd if total_usd else None

        positions.append(
            PositionModel(
                instrument_id=inst_id,
                quantity=quantity,
                avg_price=1.0,
                currency=currency,
                market_value=market_value_usd,  # Market value in USD (converted)
                pnl=None,
                weight=weight,
                tags=["asset_class:CASH"],
            )
        )

    logger.info("[wealth][banks] positions normalized=%s for user=%s", len(positions), user_id)
    return positions


async def list_transactions(start: Optional[str] = None, end: Optional[str] = None, user_id: str = None) -> List[TransactionModel]:
    """List bank transactions for user (not implemented yet)."""
    logger.info("[wealth][banks] transactions not mapped yet for user=%s, returning empty list", user_id)
    return []


async def get_prices(instrument_ids: Iterable[str], granularity: str = "daily", user_id: str = None) -> List[PricePoint]:
    """Get current FX prices for CASH instruments."""
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
    logger.info("[wealth][banks] prices fetched=%s for user=%s", len(price_points), user_id)
    return price_points


async def preview_rebalance(user_id: str) -> List[ProposedTrade]:
    """Preview rebalance for bank accounts (not applicable)."""
    logger.info("[wealth][banks] rebalance preview not implemented for user=%s, returning empty list", user_id)
    return []


async def has_data(user_id: str) -> bool:
    """Check if user has any bank data."""
    snapshot = _load_snapshot(user_id)
    has_accounts = any(float(account.get("balance") or 0.0) > 0 for account in snapshot.get("accounts", []))
    logger.debug("[wealth][banks] has_data=%s for user=%s", has_accounts, user_id)
    return has_accounts


def save_snapshot(data: dict, user_id: str) -> None:
    """Public API for saving banks snapshot (wrapper for _save_snapshot)."""
    _save_snapshot(data, user_id)


def load_snapshot(user_id: str) -> dict:
    """Public API for loading banks snapshot (wrapper for _load_snapshot)."""
    return _load_snapshot(user_id)
