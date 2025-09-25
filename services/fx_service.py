"""Thin FX conversion layer shared by Wealth adapters."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Basic reference rates (1 unit of currency -> USD) refreshed periodically offline.
_RATES_TO_USD = {
    "USD": 1.0,
    "EUR": 1.07,
    "CHF": 1.10,
    "GBP": 1.25,
    "DKK": 0.14,
    "SEK": 0.091,
    "NOK": 0.09,
    "JPY": 0.0068,
    "CAD": 0.74,
    "AUD": 0.66,
    "SGD": 0.74,
}


def _resolve_rate(currency: str) -> float:
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
