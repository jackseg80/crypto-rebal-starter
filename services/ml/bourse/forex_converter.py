"""
Forex Currency Converter for Multi-Currency Portfolios
Convertit les prix entre devises avec cache intelligent

⚠️ DEPRECATED: This module now uses the unified fx_service internally.
For new code, import directly from services.fx_service instead.

Migration: This wrapper maintains backward compatibility (async API)
while using the unified fx_service backend.
"""

import logging
from typing import Dict, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class ForexConverter:
    """
    Service de conversion de devises (wrapper vers fx_service unifié).

    ⚠️ DEPRECATED: Utilise maintenant fx_service en backend.
    Pour nouveau code, importer directement depuis services.fx_service.

    Maintient la compatibilité async pour code existant.
    """

    def __init__(self, cache_ttl_hours: int = 12):
        """
        Initialize forex converter.

        Args:
            cache_ttl_hours: Ignored (fx_service gère son propre cache)
        """
        # Note: cache_ttl_hours ignoré, fx_service utilise 4h TTL
        logger.debug("ForexConverter initialized (wrapper vers fx_service unifié)")

    async def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        date: Optional[datetime] = None
    ) -> float:
        """
        Obtient le taux de change entre deux devises (via fx_service unifié).

        Args:
            from_currency: Devise source (ex: "CHF", "EUR", "PLN")
            to_currency: Devise cible (ex: "USD")
            date: Date pour taux historique (⚠️ IGNORÉ - fx_service ne supporte pas les taux historiques)

        Returns:
            Taux de change (ex: 1.15 pour CHF→USD)
        """
        from services.fx_service import convert

        # Cas trivial: même devise
        if from_currency == to_currency:
            return 1.0

        if date:
            logger.warning(f"Historical rates not supported by fx_service, using current rate for {from_currency}→{to_currency}")

        # Convertir 1 unité pour obtenir le taux
        rate = convert(1.0, from_currency, to_currency)
        return rate

    async def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        date: Optional[datetime] = None
    ) -> float:
        """
        Convertit un montant d'une devise à une autre (via fx_service unifié).

        Args:
            amount: Montant à convertir
            from_currency: Devise source
            to_currency: Devise cible
            date: Date pour taux historique (⚠️ IGNORÉ)

        Returns:
            Montant converti dans la devise cible
        """
        from services.fx_service import convert as fx_convert

        if date:
            logger.warning(f"Historical rates not supported, using current rate")

        return fx_convert(amount, from_currency, to_currency)

    async def get_multiple_rates(
        self,
        from_currency: str,
        to_currencies: list
    ) -> Dict[str, float]:
        """
        Obtient plusieurs taux de change (via fx_service unifié).

        Args:
            from_currency: Devise source
            to_currencies: Liste des devises cibles

        Returns:
            Dict {devise: taux}
        """
        from services.fx_service import convert

        results = {}
        for to_curr in to_currencies:
            # Convertir 1 unité pour obtenir le taux
            rate = convert(1.0, from_currency, to_curr)
            results[to_curr] = rate

        logger.debug(f"Fetched {len(results)} rates from {from_currency} via fx_service")
        return results

    def clear_cache(self):
        """
        Vide le cache des taux de change.

        ⚠️ Note: fx_service gère son propre cache (4h TTL), cette méthode est no-op.
        """
        logger.debug("clear_cache() called but fx_service manages its own cache")

    def get_supported_currencies(self) -> list:
        """
        Retourne la liste des devises supportées (via fx_service unifié).

        Note: fx_service supporte 165+ devises (vs 30 devises Frankfurter).
        """
        from services.fx_service import get_supported_currencies
        return get_supported_currencies()

    async def normalize_to_usd(
        self,
        prices_dict: Dict[str, float],
        currencies_dict: Dict[str, str]
    ) -> Dict[str, float]:
        """
        Normalise tous les prix en USD pour comparaison uniforme (via fx_service unifié).

        Args:
            prices_dict: {symbol: price_in_native_currency}
            currencies_dict: {symbol: native_currency}

        Returns:
            {symbol: price_in_usd}

        Example:
            prices = {'ROG': 271.2, 'AAPL': 262.82}
            currencies = {'ROG': 'CHF', 'AAPL': 'USD'}
            → {'ROG': 312.0, 'AAPL': 262.82}
        """
        from services.fx_service import convert

        normalized = {}

        for symbol, price in prices_dict.items():
            currency = currencies_dict.get(symbol, 'USD')

            if currency == 'USD':
                normalized[symbol] = price
            else:
                try:
                    # Convert to USD via fx_service (synchrone)
                    usd_price = convert(price, currency, 'USD')
                    normalized[symbol] = usd_price
                except Exception as e:
                    logger.error(f"Failed to convert {symbol} from {currency} to USD: {e}")
                    # Keep original price as fallback
                    normalized[symbol] = price

        return normalized
