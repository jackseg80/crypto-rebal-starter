"""Centralized pricing facade for Wealth adapters with disk caching."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from models.wealth import PricePoint
from services.taxonomy import Taxonomy

logger = logging.getLogger(__name__)

_CACHE_DIR = Path("cache/prices")
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_PRICES_FILE = Path("data/prices.json")

_CRYPTO_SYMBOLS = set(Taxonomy.load().aliases.keys())

_TTL_CRYPTO = 60
_TTL_DEFAULT = 1800


def _cache_path(instrument_id: str, granularity: str) -> Path:
    safe_id = instrument_id.replace(":", "_")
    return _CACHE_DIR / f"{safe_id}_{granularity}.json"


def _ttl_for(instrument_id: str) -> int:
    if instrument_id.upper() in _CRYPTO_SYMBOLS:
        return _TTL_CRYPTO
    return _TTL_DEFAULT


def _load_cached(instrument_id: str, granularity: str, ttl: int) -> Optional[PricePoint]:
    path = _cache_path(instrument_id, granularity)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        fetched_at = float(data.get("fetched_at") or 0)
        if fetched_at == 0 or time.time() - fetched_at > ttl:
            return None
        ts = datetime.fromisoformat(data["ts"])
        return PricePoint(
            instrument_id=data["instrument_id"],
            ts=ts,
            price=float(data["price"]),
            currency=data["currency"],
            source=data.get("source", "pricing_service"),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("[wealth][pricing] cache read failed for %s: %s", instrument_id, exc)
        return None


def _store_cache(point: PricePoint, granularity: str) -> None:
    payload = {
        "instrument_id": point.instrument_id,
        "ts": point.ts.isoformat(),
        "price": point.price,
        "currency": point.currency,
        "source": point.source,
        "fetched_at": time.time(),
        "granularity": granularity,
    }
    path = _cache_path(point.instrument_id, granularity)
    tmp_path = path.with_suffix(".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        tmp_path.replace(path)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("[wealth][pricing] cache write failed for %s: %s", point.instrument_id, exc)


async def _fetch_price(instrument_id: str) -> Optional[PricePoint]:
    # Cash instruments are derived from FX service
    if instrument_id.upper().startswith("CASH:"):
        try:
            from services.fx_service import convert as fx_convert
        except Exception as exc:  # pragma: no cover
            logger.warning("[wealth][pricing] fx_service unavailable: %s", exc)
            return None
        currency = instrument_id.split(":", 1)[1].upper()
        price = fx_convert(1.0, currency, "USD")
        return PricePoint(
            instrument_id=instrument_id,
            ts=datetime.now(timezone.utc),
            price=price,
            currency="USD",
            source="fx_service",
        )

    try:
        from services.pricing import aget_price_usd
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[wealth][pricing] base pricing service unavailable: %s", exc)
        return None

    price = await aget_price_usd(instrument_id)
    if price is None:
        fallback = _price_from_static_file(instrument_id)
        if fallback:
            return fallback
        logger.debug("[wealth][pricing] no price for %s", instrument_id)
        return None
    return PricePoint(
        instrument_id=instrument_id,
        ts=datetime.now(timezone.utc),
        price=float(price),
        currency="USD",
        source="pricing_service",
    )


def _price_from_static_file(instrument_id: str) -> Optional[PricePoint]:
    if not _PRICES_FILE.exists():
        return None
    try:
        data = json.loads(_PRICES_FILE.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("[wealth][pricing] failed to read %s: %s", _PRICES_FILE, exc)
        return None

    raw = data.get(instrument_id.upper())
    if raw is None:
        return None

    if isinstance(raw, dict):
        price = raw.get("price")
    elif isinstance(raw, (int, float)):
        price = float(raw)
    else:
        price = None

    if price is None:
        return None

    return PricePoint(
        instrument_id=instrument_id,
        ts=datetime.now(timezone.utc),
        price=float(price),
        currency="USD",
        source="pricing_file",
    )


async def get_prices(instrument_ids: Iterable[str], granularity: str = "daily") -> List[PricePoint]:
    results: Dict[str, PricePoint] = {}
    to_fetch: List[str] = []

    for instrument_id in {inst.upper() for inst in instrument_ids if inst}:
        ttl = _ttl_for(instrument_id)
        cached = _load_cached(instrument_id, granularity, ttl)
        if cached:
            results[instrument_id] = cached
        else:
            to_fetch.append(instrument_id)

    if to_fetch:
        fetch_tasks = [_fetch_price(inst) for inst in to_fetch]
        fetched = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        for instrument_id, outcome in zip(to_fetch, fetched):
            if isinstance(outcome, Exception):  # pragma: no cover - defensive
                logger.debug("[wealth][pricing] fetch failed for %s: %s", instrument_id, outcome)
                continue
            if outcome:
                results[instrument_id] = outcome
                _store_cache(outcome, granularity)

    ordered = [results[key] for key in sorted(results.keys())]
    logger.info("[wealth][pricing] delivered %s price points (granularity=%s)", len(ordered), granularity)
    return ordered
