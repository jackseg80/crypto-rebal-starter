"""FX (Foreign Exchange) API endpoints."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query

from api.utils import success_response
from services.fx_service import get_rates, get_supported_currencies, get_cache_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fx", tags=["fx"])


@router.get("/rates")
async def get_fx_rates(
    base: str = Query("USD", description="Base currency (default: USD)")
):
    """
    Get foreign exchange rates for all supported currencies.

    Args:
        base: Base currency (default: USD)

    Returns:
        Dictionary with rates and metadata

    Example response:
        {
            "ok": true,
            "data": {
                "base": "USD",
                "rates": {
                    "USD": 1.0,
                    "EUR": 0.920,
                    "CHF": 0.880,
                    "GBP": 0.769,
                    ...
                }
            },
            "meta": {
                "currencies": 11,
                "updated": "2025-10-27"
            }
        }
    """
    try:
        base = base.upper()
        rates = get_rates(base_currency=base)

        logger.info(f"[fx] Served {len(rates)} rates with base={base}")

        return success_response(
            {
                "base": base,
                "rates": rates
            },
            meta={
                "currencies": len(rates),
                "updated": "2025-10-27"
            }
        )
    except Exception as e:
        logger.error(f"[fx] Failed to get rates: {e}", exc_info=True)
        return success_response(
            {
                "base": "USD",
                "rates": {"USD": 1.0}
            },
            meta={
                "error": str(e),
                "fallback": True
            }
        )


@router.get("/currencies")
async def get_currencies():
    """
    Get list of supported currency codes.

    Returns:
        List of ISO 4217 currency codes

    Example response:
        {
            "ok": true,
            "data": ["USD", "EUR", "CHF", "GBP", ...],
            "meta": {
                "count": 11
            }
        }
    """
    try:
        currencies = get_supported_currencies()
        logger.info(f"[fx] Served {len(currencies)} supported currencies")

        return success_response(
            currencies,
            meta={"count": len(currencies)}
        )
    except Exception as e:
        logger.error(f"[fx] Failed to get currencies: {e}", exc_info=True)
        return success_response(
            ["USD"],
            meta={"error": str(e), "fallback": True}
        )


@router.get("/cache-info")
async def get_fx_cache_info():
    """
    Get information about the FX rates cache.

    Returns:
        Cache metadata including age, TTL, and last update time

    Example response:
        {
            "ok": true,
            "data": {
                "cached_currencies": 160,
                "cache_age_seconds": 3245.2,
                "cache_ttl_seconds": 14400,
                "cache_fresh": true,
                "last_update": "2025-10-27T14:32:10"
            }
        }
    """
    try:
        cache_info = get_cache_info()
        logger.info(f"[fx] Served cache info: {cache_info['cached_currencies']} currencies, fresh={cache_info['cache_fresh']}")

        return success_response(cache_info)
    except Exception as e:
        logger.error(f"[fx] Failed to get cache info: {e}", exc_info=True)
        return success_response(
            {"error": str(e)},
            meta={"fallback": True}
        )
