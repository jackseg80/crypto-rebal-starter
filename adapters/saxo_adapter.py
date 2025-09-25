"""Adapter consolidating Saxo data for the Wealth namespace."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from connectors.saxo_import import SaxoImportConnector
from models.wealth import (
    AccountModel,
    InstrumentModel,
    PositionModel,
    PricePoint,
    ProposedTrade,
    TransactionModel,
)
from services.pricing_service import get_prices as pricing_get_prices

logger = logging.getLogger(__name__)

_MODULE = "saxo"
_STORAGE_PATH = Path("data/wealth/saxo_snapshot.json")
_ISIN_MAP = Path("data/mappings/isin_ticker.json")


def _ensure_storage() -> None:
    _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _STORAGE_PATH.exists():
        _STORAGE_PATH.write_text(json.dumps({"portfolios": []}), encoding="utf-8")


def _load_snapshot() -> Dict[str, Any]:
    _ensure_storage()
    try:
        with _STORAGE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if not isinstance(data, dict):  # pragma: no cover - defensive
                return {"portfolios": []}
            data.setdefault("portfolios", [])
            return data
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[wealth][saxo] failed to load snapshot: %s", exc)
        return {"portfolios": []}


def _save_snapshot(snapshot: Dict[str, Any]) -> None:
    _ensure_storage()
    tmp_path = _STORAGE_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(_STORAGE_PATH)


def _load_isin_mapping() -> Dict[str, str]:
    if not _ISIN_MAP.exists():
        try:
            _ISIN_MAP.parent.mkdir(parents=True, exist_ok=True)
            _ISIN_MAP.write_text("{}", encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[wealth][saxo] unable to initialize ISIN mapping: %s", exc)
        return {}
    try:
        with _ISIN_MAP.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return {str(k).upper(): str(v).upper() for k, v in data.items()}
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[wealth][saxo] invalid ISIN mapping content: %s", exc)
    return {}


def _normalize_asset_class(asset_class: str) -> str:
    normalized = str(asset_class or "").lower()
    mapping = {
        "stock": "EQUITY",
        "equity": "EQUITY",
        "etf": "ETF",
        "fund": "ETF",
        "bond": "BOND",
        "cash": "CASH",
        "money market": "CASH",
        "commodity": "COMMODITY",
        "forex": "FX",
        "fx": "FX",
        "reit": "REIT",
    }
    return mapping.get(normalized, "EQUITY")


def _resolve_symbol(position: Dict[str, Any], isin_map: Dict[str, str]) -> str:
    symbol = str(position.get("symbol") or "").upper()
    instrument = str(position.get("instrument") or "")
    if symbol and not symbol.startswith("ISIN:"):
        return symbol
    isin = ""
    if instrument.upper().startswith("ISIN:"):
        isin = instrument.split(":", 1)[-1].strip().upper()
    elif symbol.upper().startswith("ISIN"):
        isin = symbol.split(":", 1)[-1].strip().upper()
    if isin:
        return isin_map.get(isin, isin)
    return symbol or instrument or "UNKNOWN"


def _portfolio_id(name: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    slug = "-".join(filter(None, slug.split("-")))
    return slug or "default"


def ingest_file(file_path: str, portfolio_name: Optional[str] = None) -> Dict[str, Any]:
    connector = SaxoImportConnector()
    parsed = connector.process_saxo_file(file_path)
    positions = parsed.get("positions", []) if isinstance(parsed, dict) else []
    if not positions:
        logger.warning("[wealth][saxo] ingestion produced no positions for %s", file_path)
        return {}

    isin_map = _load_isin_mapping()
    total_value = sum(float(pos.get("market_value") or 0) for pos in positions)
    normalized_positions: List[Dict[str, Any]] = []

    for pos in positions:
        symbol = _resolve_symbol(pos, isin_map)
        normalized_positions.append({
            "symbol": symbol,
            "name": str(pos.get("instrument") or symbol),
            "quantity": float(pos.get("quantity") or 0.0),
            "currency": str(pos.get("currency") or "USD").upper(),
            "market_value": float(pos.get("market_value") or 0.0),
            "asset_class": _normalize_asset_class(pos.get("asset_class") or ""),
            "position_id": str(pos.get("position_id") or symbol),
        })

    portfolio_name = portfolio_name or parsed.get("metadata", {}).get("portfolio_name") or "Saxo Portfolio"
    portfolio = {
        "portfolio_id": _portfolio_id(portfolio_name),
        "name": portfolio_name,
        "positions": normalized_positions,
        "total_value_usd": total_value,
        "updated_at": datetime.utcnow().isoformat(),
    }

    snapshot = _load_snapshot()
    snapshot["portfolios"] = [p for p in snapshot.get("portfolios", []) if p.get("portfolio_id") != portfolio["portfolio_id"]]
    snapshot["portfolios"].append(portfolio)
    _save_snapshot(snapshot)

    logger.info("[wealth][saxo] stored portfolio '%s' with %s positions", portfolio_name, len(normalized_positions))
    return portfolio


def _iter_positions() -> Iterable[Dict[str, Any]]:
    snapshot = _load_snapshot()
    for portfolio in snapshot.get("portfolios", []):
        for position in portfolio.get("positions", []):
            yield position


def _total_value() -> float:
    snapshot = _load_snapshot()
    return sum(float(p.get("total_value_usd") or 0.0) for p in snapshot.get("portfolios", []))


async def list_accounts() -> List[AccountModel]:
    snapshot = _load_snapshot()
    accounts: List[AccountModel] = []
    for portfolio in snapshot.get("portfolios", []):
        accounts.append(
            AccountModel(
                id=f"{_MODULE}:{portfolio.get('portfolio_id')}",
                provider=_MODULE,
                type="portfolio",
                currency="USD",
            )
        )
    if not accounts:
        accounts.append(AccountModel(id=f"{_MODULE}:placeholder", provider=_MODULE, type="portfolio", currency="USD"))
    logger.info("[wealth][saxo] accounts normalized=%s", len(accounts))
    return accounts


async def list_instruments() -> List[InstrumentModel]:
    instruments: Dict[str, InstrumentModel] = {}
    for position in _iter_positions():
        symbol = position.get("symbol")
        if not symbol:
            continue
        instrument_id = symbol
        if instrument_id in instruments:
            continue
        instruments[instrument_id] = InstrumentModel(
            id=instrument_id,
            symbol=symbol,
            isin=symbol if symbol.startswith("ISIN") and len(symbol) > 5 else None,
            name=position.get("name") or symbol,
            asset_class=position.get("asset_class") or "EQUITY",
            sector=None,
            region=None,
        )
    instrument_list = sorted(instruments.values(), key=lambda inst: inst.symbol)
    logger.info("[wealth][saxo] instruments normalized=%s", len(instrument_list))
    return instrument_list


async def list_positions() -> List[PositionModel]:
    total = _total_value() or 1.0
    positions: List[PositionModel] = []
    for position in _iter_positions():
        symbol = position.get("symbol")
        quantity = float(position.get("quantity") or 0.0)
        if not symbol or quantity == 0:
            continue
        market_value = float(position.get("market_value") or 0.0) or None
        weight = (market_value or 0.0) / total if total else None
        tags = [f"asset_class:{position.get('asset_class')}"]
        positions.append(
            PositionModel(
                instrument_id=symbol,
                quantity=quantity,
                avg_price=None,
                currency=position.get("currency") or "USD",
                market_value=market_value,
                pnl=None,
                weight=weight,
                tags=tags,
            )
        )
    logger.info("[wealth][saxo] positions normalized=%s", len(positions))
    return positions


async def list_transactions(start: Optional[str] = None, end: Optional[str] = None) -> List[TransactionModel]:
    logger.info("[wealth][saxo] transactions not mapped yet, returning empty list")
    return []


async def get_prices(instrument_ids: Iterable[str], granularity: str = "daily") -> List[PricePoint]:
    prices = await pricing_get_prices(list(instrument_ids), granularity=granularity)
    logger.debug("[wealth][saxo] price points fetched=%s", len(prices))
    return prices


async def preview_rebalance() -> List[ProposedTrade]:
    logger.info("[wealth][saxo] rebalance preview not implemented, returning empty list")
    return []


async def has_data() -> bool:
    return any(True for _ in _iter_positions())
