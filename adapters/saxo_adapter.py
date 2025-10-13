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

def _load_from_sources_fallback(user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Charge les données Saxo depuis le système sources unifié.

    Args:
        user_id: ID utilisateur (None pour mode compatibilité)

    Returns:
        Optional[Dict]: Données normalisées ou None
    """
    if not user_id:
        logger.debug("No user_id provided, using legacy storage")
        return None

    try:
        from api.services.user_fs import UserScopedFS
        from api.services.config_migrator import get_staleness_state
        import os

        project_root = str(Path(__file__).parent.parent)
        user_fs = UserScopedFS(project_root, user_id)

        # 1. Essayer data/ (nouveau système unifié)
        data_files = user_fs.glob_files("saxobank/data/*.csv")
        if data_files:
            # Prendre le plus récent
            latest_data = max(data_files, key=lambda f: os.path.getmtime(f))
            logger.debug(f"Using Saxo data/ for user {user_id}: {latest_data}")
            return _parse_saxo_csv(latest_data, "saxo_data", user_id=user_id)

        logger.debug(f"No Saxo data found for user {user_id}")
        return None

    except Exception as e:
        logger.error(f"Error loading from sources for user {user_id}: {e}")
        return None

def _parse_saxo_csv(csv_path: str, source_type: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Parse un fichier CSV Saxo vers le format portfolio normalisé"""
    try:
        connector = SaxoImportConnector()
        # Utiliser la méthode existante avec user_id pour enrichissement
        result = connector.process_saxo_file(csv_path, user_id=user_id)

        if not result or "positions" not in result:
            return {"portfolios": []}

        positions = result["positions"]
        portfolio_id = f"saxo_{source_type}"

        # Normaliser au format attendu
        normalized_data = {
            "portfolios": [{
                "portfolio_id": portfolio_id,  # Fix: Utiliser 'portfolio_id' pour cohérence
                "name": f"Saxo Portfolio ({source_type})",
                "positions": positions,
                "summary": result.get("summary", {}),
                "last_updated": datetime.now().isoformat(),
                "source": source_type
            }]
        }

        logger.info(f"Parsed Saxo CSV: {len(positions)} positions from {source_type}")
        return normalized_data

    except Exception as e:
        logger.error(f"Failed to parse Saxo CSV {csv_path}: {e}")
        return {"portfolios": []}


def _ensure_storage() -> None:
    _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _STORAGE_PATH.exists():
        _STORAGE_PATH.write_text(json.dumps({"portfolios": []}), encoding="utf-8")


def _load_snapshot(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge le snapshot Saxo avec support du système sources unifié.

    Args:
        user_id: ID utilisateur (None pour mode legacy)

    Returns:
        Dict[str, Any]: Données de snapshot
    """
    # Essayer d'abord le nouveau système sources
    if user_id:
        sources_data = _load_from_sources_fallback(user_id)
        if sources_data:
            return sources_data
        # Si user_id fourni mais pas de données → retourner vide (pas de fallback vers legacy partagé!)
        logger.debug(f"[saxo_adapter] No Saxo data found for user {user_id}, returning empty snapshot")
        return {"portfolios": []}

    # Fallback vers l'ancien système SEULEMENT si user_id est None (mode compatibilité)
    _ensure_storage()
    try:
        with _STORAGE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if not isinstance(data, dict):  # pragma: no cover - defensive
                return {"portfolios": []}
            data.setdefault("portfolios", [])
            return data
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[wealth][saxo] failed to load legacy snapshot: %s", exc)
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
    positions = parsed.get('positions', []) if isinstance(parsed, dict) else []
    errors = parsed.get('errors', []) if isinstance(parsed, dict) else []
    if not positions:
        logger.warning("[wealth][saxo] ingestion produced no positions for %s", file_path)
        return {}

    isin_map = _load_isin_mapping()
    normalized_positions: List[Dict[str, Any]] = []

    for pos in positions:
        symbol = _resolve_symbol(pos, isin_map)
        currency = str(pos.get('currency') or 'USD').upper()
        market_value = float(pos.get('market_value') or 0.0)
        market_value_usd = float(pos.get('market_value_usd') or market_value)
        name = str(pos.get('instrument') or symbol)
        normalized_positions.append({
            'symbol': symbol,
            'instrument': name,
            'name': name,
            'quantity': float(pos.get('quantity') or 0.0),
            'currency': currency,
            'market_value': market_value,
            'market_value_usd': market_value_usd,
            'asset_class': _normalize_asset_class(pos.get('asset_class') or ''),
            'position_id': str(pos.get('position_id') or symbol),
        })

    summary = connector.get_portfolio_summary(normalized_positions)
    total_value_usd = summary.get('total_value_usd', 0.0)
    total_positions = summary.get('total_positions', len(normalized_positions))

    portfolio_name = portfolio_name or parsed.get('metadata', {}).get('portfolio_name') or 'Saxo Portfolio'
    portfolio = {
        'portfolio_id': _portfolio_id(portfolio_name),
        'name': portfolio_name,
        'positions': normalized_positions,
        'total_value_usd': total_value_usd,
        'positions_count': total_positions,
        'summary': summary,
        'updated_at': datetime.utcnow().isoformat(),
    }

    snapshot = _load_snapshot()
    snapshot['portfolios'] = [p for p in snapshot.get('portfolios', []) if p.get('portfolio_id') != portfolio['portfolio_id']]
    snapshot['portfolios'].append(portfolio)
    _save_snapshot(snapshot)

    logger.info("[wealth][saxo] stored portfolio '%s' with %s positions", portfolio_name, len(normalized_positions))
    return {
        'portfolio': portfolio,
        'summary': summary,
        'errors': errors,
    }

def list_portfolios_overview(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return lightweight metadata for stored Saxo portfolios."""
    snapshot = _load_snapshot(user_id)
    portfolios: List[Dict[str, Any]] = []
    connector = None
    mutated = False

    for item in snapshot.get('portfolios', []):
        summary = item.get('summary')
        positions = item.get('positions', [])
        if not summary:
            if connector is None:
                connector = SaxoImportConnector()
            summary = connector.get_portfolio_summary(positions)
            item['summary'] = summary
            item['total_value_usd'] = summary.get('total_value_usd', item.get('total_value_usd', 0.0))
            item['positions_count'] = summary.get('total_positions', len(positions))
            mutated = True

        total_value = summary.get('total_value_usd', item.get('total_value_usd', 0.0))
        positions_count = summary.get('total_positions', item.get('positions_count') or len(positions))

        portfolios.append({
            'portfolio_id': item.get('portfolio_id'),
            'name': item.get('name'),
            'positions_count': positions_count,
            'total_value_usd': total_value,
            'updated_at': item.get('updated_at'),
        })

    if mutated:
        _save_snapshot(snapshot)

    portfolios.sort(key=lambda entry: entry.get('updated_at') or '', reverse=True)
    return portfolios


def get_portfolio_detail(portfolio_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Return full detail for a stored Saxo portfolio."""
    snapshot = _load_snapshot(user_id)
    connector = None
    mutated = False

    for item in snapshot.get('portfolios', []):
        if item.get('portfolio_id') != portfolio_id:
            continue

        summary = item.get('summary')
        positions = item.get('positions', [])
        if not summary:
            if connector is None:
                connector = SaxoImportConnector()
            summary = connector.get_portfolio_summary(positions)
            item['summary'] = summary
            item['total_value_usd'] = summary.get('total_value_usd', item.get('total_value_usd', 0.0))
            item['positions_count'] = summary.get('total_positions', len(positions))
            mutated = True

        result = {
            'portfolio_id': item.get('portfolio_id'),
            'name': item.get('name'),
            'positions': positions,
            'summary': summary,
            'total_value_usd': summary.get('total_value_usd', item.get('total_value_usd', 0.0)),
            'positions_count': summary.get('total_positions', item.get('positions_count') or len(positions)),
            'updated_at': item.get('updated_at'),
        }

        if mutated:
            _save_snapshot(snapshot)
        return result

    if mutated:
        _save_snapshot(snapshot)
    return {}




def _iter_positions(user_id: Optional[str] = None) -> Iterable[Dict[str, Any]]:
    snapshot = _load_snapshot(user_id)
    for portfolio in snapshot.get("portfolios", []):
        for position in portfolio.get("positions", []):
            yield position


def _total_value(user_id: Optional[str] = None) -> float:
    snapshot = _load_snapshot(user_id)
    return sum(float(p.get("total_value_usd") or 0.0) for p in snapshot.get("portfolios", []))


async def list_accounts(user_id: Optional[str] = None) -> List[AccountModel]:
    snapshot = _load_snapshot(user_id)
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


async def list_instruments(user_id: Optional[str] = None) -> List[InstrumentModel]:
    """
    List all instruments with enrichment via registry.

    Args:
        user_id: Optional user ID for per-user catalog lookup

    Returns:
        List of enriched InstrumentModel instances
    """
    from services.instruments_registry import resolve

    instruments: Dict[str, InstrumentModel] = {}
    seen_ids = set()

    for position in _iter_positions(user_id):
        symbol = position.get("symbol")
        instrument_raw = position.get("instrument") or symbol
        if not instrument_raw or instrument_raw in seen_ids:
            continue

        # Enrichissement via registry
        enriched = resolve(instrument_raw, fallback_symbol=symbol, user_id=user_id)

        instrument_id = enriched.get("id") or instrument_raw
        if instrument_id in seen_ids:
            continue

        seen_ids.add(instrument_id)

        # Mapping asset_class pour compatibilité modèle
        asset_class_raw = enriched.get("asset_class") or position.get("asset_class") or "EQUITY"
        asset_class_normalized = _normalize_asset_class(asset_class_raw)

        instruments[instrument_id] = InstrumentModel(
            id=instrument_id,
            symbol=enriched.get("symbol") or symbol,
            isin=enriched.get("isin"),
            name=enriched.get("name") or position.get("name") or symbol,
            asset_class=asset_class_normalized,
            sector=None,  # TODO: Could be enriched from registry later
            region=None,  # TODO: Could be enriched from registry later
        )

    instrument_list = sorted(instruments.values(), key=lambda inst: inst.symbol)
    logger.info("[wealth][saxo] instruments normalized=%s (enriched via registry)", len(instrument_list))
    return instrument_list


async def list_positions(user_id: Optional[str] = None) -> List[PositionModel]:
    total = _total_value(user_id) or 1.0
    positions: List[PositionModel] = []
    for position in _iter_positions(user_id):
        symbol = position.get("symbol")
        quantity = float(position.get("quantity") or 0.0)
        if not symbol or quantity == 0:
            continue
        market_value = float(position.get("market_value") or 0.0) or None
        weight = (market_value or 0.0) / total if total else None
        tags = [f"asset_class:{position.get('asset_class')}"]

        # Fix: Validate currency field - exclude ISINs and other long codes
        raw_currency = position.get("currency")
        currency = "USD"  # Default
        if raw_currency and len(raw_currency) <= 3 and raw_currency.isalpha():
            currency = raw_currency.upper()

        positions.append(
            PositionModel(
                instrument_id=symbol,
                quantity=quantity,
                avg_price=None,
                currency=currency,
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


async def has_data(user_id: Optional[str] = None) -> bool:
    """Vérifie si des données Saxo sont disponibles pour l'utilisateur."""
    return any(True for _ in _iter_positions(user_id))
