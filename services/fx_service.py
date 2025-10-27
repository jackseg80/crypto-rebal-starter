"""Thin FX conversion layer shared by Wealth adapters."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Fallback reference rates (1 unit of currency -> USD) - used if API fetch fails
# Last updated: Oct 2025
_FALLBACK_RATES_TO_USD = {
    "USD": 1.0,
    "EUR": 1.087,   # 1 EUR = 1.087 USD (Oct 2025)
    "CHF": 1.136,   # 1 CHF = 1.136 USD (Oct 2025)
    "GBP": 1.30,    # 1 GBP = 1.30 USD
    "DKK": 0.146,   # 1 DKK = 0.146 USD
    "SEK": 0.096,   # 1 SEK = 0.096 USD
    "NOK": 0.093,   # 1 NOK = 0.093 USD
    "JPY": 0.0066,  # 1 JPY = 0.0066 USD
    "CAD": 0.72,    # 1 CAD = 0.72 USD
    "AUD": 0.65,    # 1 AUD = 0.65 USD
    "SGD": 0.75,    # 1 SGD = 0.75 USD
}

# Live rates cache (fetched from external API)
_RATES_TO_USD = {**_FALLBACK_RATES_TO_USD}  # Start with fallback
_RATES_CACHE_TIMESTAMP = 0
_RATES_CACHE_TTL = 14400  # 4 hours in seconds


def _fetch_live_rates() -> bool:
    """
    Fetch live FX rates from external API and update cache.

    Returns:
        True if fetch succeeded, False otherwise
    """
    global _RATES_TO_USD, _RATES_CACHE_TIMESTAMP

    try:
        import httpx

        # Use exchangerate-api.com (free, no API key required, 1500 requests/month)
        # Fetches rates with USD as base
        url = "https://open.exchangerate-api.com/v6/latest/USD"

        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)

            if response.status_code != 200:
                logger.warning(f"[wealth][fx] API returned status {response.status_code}, using fallback rates")
                return False

            data = response.json()

            if data.get("result") != "success":
                logger.warning(f"[wealth][fx] API result not success, using fallback rates")
                return False

            fetched_rates = data.get("rates", {})

            if not fetched_rates:
                logger.warning(f"[wealth][fx] No rates in API response, using fallback rates")
                return False

            # Convert rates: API gives USD -> XXX, we need XXX -> USD
            # Example: API says USD->EUR = 0.92, we need EUR->USD = 1/0.92 = 1.087
            updated_rates = {}
            for currency, rate_from_usd in fetched_rates.items():
                currency = currency.upper()
                if currency == "USD":
                    updated_rates[currency] = 1.0
                elif rate_from_usd > 0:
                    # Invert: if 1 USD = 0.92 EUR, then 1 EUR = 1/0.92 USD
                    updated_rates[currency] = 1.0 / rate_from_usd
                else:
                    # Keep fallback if invalid rate
                    updated_rates[currency] = _FALLBACK_RATES_TO_USD.get(currency, 1.0)

            # Update cache
            _RATES_TO_USD.update(updated_rates)
            _RATES_CACHE_TIMESTAMP = time.time()

            logger.info(f"[wealth][fx] ✅ Fetched {len(updated_rates)} live rates from API")
            return True

    except Exception as e:
        logger.warning(f"[wealth][fx] Failed to fetch live rates: {e}, using fallback rates")
        return False


def _ensure_rates_fresh():
    """Ensure rates cache is fresh, fetch if expired."""
    global _RATES_CACHE_TIMESTAMP

    now = time.time()
    age = now - _RATES_CACHE_TIMESTAMP

    if age > _RATES_CACHE_TTL:
        logger.debug(f"[wealth][fx] Cache expired (age: {age:.0f}s), fetching live rates...")
        _fetch_live_rates()


def _resolve_rate(currency: str) -> float:
    """Get rate for currency, using cache with fallback."""
    _ensure_rates_fresh()  # Refresh if needed

    currency = currency.upper()
    rate = _RATES_TO_USD.get(currency)

    if rate is None:
        logger.debug("[wealth][fx] missing FX rate for %s, defaulting to parity", currency)
        rate = 1.0

    return rate


def convert(amount: float, from_ccy: str, to_ccy: str, asof: Optional[datetime] = None) -> float:
    """Convert amount between currencies using cached indicative rates."""

    if from_ccy is None or to_ccy is None:
        raise ValueError("from_ccy and to_ccy must be provided")

    from_ccy = from_ccy.upper()
    to_ccy = to_ccy.upper()

    if from_ccy == to_ccy:
        return float(amount)

    from_rate = _resolve_rate(from_ccy)
    to_rate = _resolve_rate(to_ccy)

    usd_amount = float(amount) * from_rate
    result = usd_amount / to_rate if to_rate else usd_amount
    logger.debug(
        "[wealth][fx] convert %.2f %s -> %.2f %s (asof=%s)",
        amount,
        from_ccy,
        result,
        to_ccy,
        asof.isoformat() if asof else "latest",
    )
    return result


def get_rates(base_currency: str = "USD") -> dict:
    """
    Get FX rates for all supported currencies.

    Args:
        base_currency: Base currency for rates (default: USD)

    Returns:
        Dictionary of currency -> rate (e.g., {"EUR": 0.92} means 1 USD = 0.92 EUR)
    """
    _ensure_rates_fresh()  # Refresh cache if needed

    base_currency = base_currency.upper()

    if base_currency == "USD":
        # Return inverted rates: 1 USD = X foreign currency
        # Frontend expects: 1 USD = 0.92 EUR (so EUR/USD rate is inverted)
        rates = {}
        for currency, rate_to_usd in _RATES_TO_USD.items():
            if currency == "USD":
                rates[currency] = 1.0
            else:
                # Invert: if 1 EUR = 1.087 USD, then 1 USD = 1/1.087 = 0.920 EUR
                rates[currency] = 1.0 / rate_to_usd if rate_to_usd > 0 else 1.0
        return rates
    else:
        # For other base currencies, convert through USD
        base_rate = _resolve_rate(base_currency)
        rates = {}
        for currency, rate_to_usd in _RATES_TO_USD.items():
            if currency == base_currency:
                rates[currency] = 1.0
            else:
                # Convert: base -> USD -> target
                rates[currency] = rate_to_usd / base_rate if base_rate > 0 else 1.0
        return rates


def get_supported_currencies() -> list:
    """Get list of supported currency codes."""
    _ensure_rates_fresh()  # Refresh cache if needed
    return list(_RATES_TO_USD.keys())


def initialize_rates():
    """
    Initialize FX rates on application startup.
    Fetches live rates immediately to avoid delay on first request.
    """
    logger.info("[wealth][fx] Initializing FX rates on startup...")
    success = _fetch_live_rates()
    if success:
        logger.info("[wealth][fx] ✅ FX rates initialized with live data")
    else:
        logger.warning("[wealth][fx] ⚠️ FX rates initialized with fallback data")


def get_cache_info() -> dict:
    """
    Get information about the rates cache.

    Returns:
        Dictionary with cache metadata
    """
    now = time.time()
    age = now - _RATES_CACHE_TIMESTAMP if _RATES_CACHE_TIMESTAMP > 0 else None

    return {
        "cached_currencies": len(_RATES_TO_USD),
        "cache_age_seconds": age,
        "cache_ttl_seconds": _RATES_CACHE_TTL,
        "cache_fresh": age < _RATES_CACHE_TTL if age is not None else False,
        "last_update": datetime.fromtimestamp(_RATES_CACHE_TIMESTAMP).isoformat() if _RATES_CACHE_TIMESTAMP > 0 else None
    }
