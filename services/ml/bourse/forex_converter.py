"""
Forex Currency Converter for Multi-Currency Portfolios
Convertit les prix entre devises avec cache intelligent
"""

import logging
import aiohttp
from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)


class ForexConverter:
    """
    Service de conversion de devises avec cache intelligent.

    Utilise l'API gratuite Frankfurter (European Central Bank data)
    - Pas besoin de clé API
    - Données officielles BCE
    - Taux de change quotidiens
    - Cache TTL 12h (taux changent 1x/jour)
    """

    BASE_URL = "https://api.frankfurter.app"

    def __init__(self, cache_ttl_hours: int = 12):
        """
        Initialize forex converter with cache.

        Args:
            cache_ttl_hours: TTL pour le cache des taux (défaut: 12h)
        """
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

    async def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        date: Optional[datetime] = None
    ) -> float:
        """
        Obtient le taux de change entre deux devises.

        Args:
            from_currency: Devise source (ex: "CHF", "EUR", "PLN")
            to_currency: Devise cible (ex: "USD")
            date: Date pour taux historique (défaut: aujourd'hui)

        Returns:
            Taux de change (ex: 1.15 pour CHF→USD)

        Raises:
            ValueError: Si devise non supportée
            aiohttp.ClientError: Si erreur API
        """
        # Cas trivial: même devise
        if from_currency == to_currency:
            return 1.0

        # Check cache
        cache_key = f"{from_currency}_{to_currency}"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            age = datetime.now() - cached_data['timestamp']
            if age < self.cache_ttl:
                logger.debug(f"Cache hit for {cache_key}: {cached_data['rate']:.4f}")
                return cached_data['rate']

        # Fetch from API
        try:
            if date:
                date_str = date.strftime('%Y-%m-%d')
                url = f"{self.BASE_URL}/{date_str}"
            else:
                url = f"{self.BASE_URL}/latest"

            params = {
                'from': from_currency.upper(),
                'to': to_currency.upper()
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"Forex API error {response.status}: {error_text}")

                    data = await response.json()

                    # Extract rate
                    rate = data['rates'][to_currency.upper()]

                    # Cache result
                    self.cache[cache_key] = {
                        'rate': rate,
                        'timestamp': datetime.now()
                    }

                    logger.info(f"Fetched {from_currency}→{to_currency}: {rate:.4f}")
                    return rate

        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching forex rate {from_currency}→{to_currency}: {e}")
            # Fallback to hardcoded approximations
            return self._get_fallback_rate(from_currency, to_currency)
        except Exception as e:
            logger.error(f"Error fetching forex rate {from_currency}→{to_currency}: {e}")
            return self._get_fallback_rate(from_currency, to_currency)

    async def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        date: Optional[datetime] = None
    ) -> float:
        """
        Convertit un montant d'une devise à une autre.

        Args:
            amount: Montant à convertir
            from_currency: Devise source
            to_currency: Devise cible
            date: Date pour taux historique (optionnel)

        Returns:
            Montant converti dans la devise cible
        """
        rate = await self.get_exchange_rate(from_currency, to_currency, date)
        converted = amount * rate
        logger.debug(f"Converted {amount:.2f} {from_currency} → {converted:.2f} {to_currency} (rate: {rate:.4f})")
        return converted

    async def get_multiple_rates(
        self,
        from_currency: str,
        to_currencies: list
    ) -> Dict[str, float]:
        """
        Obtient plusieurs taux de change en une seule requête.

        Args:
            from_currency: Devise source
            to_currencies: Liste des devises cibles

        Returns:
            Dict {devise: taux}
        """
        # Use Frankfurter batch endpoint
        try:
            url = f"{self.BASE_URL}/latest"
            params = {
                'from': from_currency.upper(),
                'to': ','.join([c.upper() for c in to_currencies])
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        raise ValueError(f"Forex API error {response.status}")

                    data = await response.json()
                    rates = data['rates']

                    # Cache all rates
                    for to_curr, rate in rates.items():
                        cache_key = f"{from_currency}_{to_curr}"
                        self.cache[cache_key] = {
                            'rate': rate,
                            'timestamp': datetime.now()
                        }

                    logger.info(f"Fetched {len(rates)} rates from {from_currency}")
                    return rates

        except Exception as e:
            logger.error(f"Error fetching multiple rates: {e}")
            # Fallback to individual requests
            results = {}
            for to_curr in to_currencies:
                results[to_curr] = await self.get_exchange_rate(from_currency, to_curr)
            return results

    def _get_fallback_rate(self, from_currency: str, to_currency: str) -> float:
        """
        Taux de change approximatifs de fallback si l'API échoue.

        Note: Ces taux sont approximatifs (octobre 2025) et devraient
        être mis à jour régulièrement ou remplacés par une autre source.
        """
        # Approximate rates (October 2025)
        FALLBACK_RATES = {
            # USD as base
            'USD_CHF': 0.87,  # 1 USD = 0.87 CHF
            'USD_EUR': 0.92,  # 1 USD = 0.92 EUR
            'USD_GBP': 0.79,  # 1 USD = 0.79 GBP
            'USD_PLN': 4.05,  # 1 USD = 4.05 PLN
            'USD_JPY': 149.5,

            # CHF conversions
            'CHF_USD': 1.15,  # 1 CHF = 1.15 USD
            'CHF_EUR': 1.06,
            'CHF_GBP': 0.91,
            'CHF_PLN': 4.65,

            # EUR conversions
            'EUR_USD': 1.09,  # 1 EUR = 1.09 USD
            'EUR_CHF': 0.94,
            'EUR_GBP': 0.86,
            'EUR_PLN': 4.40,

            # GBP conversions
            'GBP_USD': 1.27,
            'GBP_EUR': 1.16,
            'GBP_CHF': 1.10,
            'GBP_PLN': 5.10,

            # PLN conversions
            'PLN_USD': 0.247,  # 1 PLN = 0.247 USD
            'PLN_EUR': 0.227,
            'PLN_CHF': 0.215,
            'PLN_GBP': 0.196,
        }

        key = f"{from_currency}_{to_currency}"
        if key in FALLBACK_RATES:
            rate = FALLBACK_RATES[key]
            logger.warning(f"Using fallback rate {from_currency}→{to_currency}: {rate:.4f}")
            return rate

        # Try inverse rate
        inverse_key = f"{to_currency}_{from_currency}"
        if inverse_key in FALLBACK_RATES:
            rate = 1.0 / FALLBACK_RATES[inverse_key]
            logger.warning(f"Using inverse fallback rate {from_currency}→{to_currency}: {rate:.4f}")
            return rate

        # Last resort: assume 1:1 (very bad, but prevents crashes)
        logger.error(f"No fallback rate available for {from_currency}→{to_currency}, assuming 1:1")
        return 1.0

    def clear_cache(self):
        """Vide le cache des taux de change"""
        self.cache.clear()
        logger.info("Forex cache cleared")

    def get_supported_currencies(self) -> list:
        """
        Retourne la liste des devises supportées par l'API Frankfurter.

        Note: L'API Frankfurter supporte ~30 devises principales.
        """
        return [
            'USD', 'EUR', 'CHF', 'GBP', 'JPY', 'CAD', 'AUD', 'NZD',
            'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'RON', 'BGN',
            'TRY', 'ILS', 'CNY', 'HKD', 'SGD', 'KRW', 'INR', 'BRL',
            'MXN', 'ZAR', 'RUB', 'THB', 'MYR', 'IDR', 'PHP'
        ]

    async def normalize_to_usd(
        self,
        prices_dict: Dict[str, float],
        currencies_dict: Dict[str, str]
    ) -> Dict[str, float]:
        """
        Normalise tous les prix en USD pour comparaison uniforme.

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
        normalized = {}

        for symbol, price in prices_dict.items():
            currency = currencies_dict.get(symbol, 'USD')

            if currency == 'USD':
                normalized[symbol] = price
            else:
                try:
                    # Convert to USD
                    usd_price = await self.convert(price, currency, 'USD')
                    normalized[symbol] = usd_price
                except Exception as e:
                    logger.error(f"Failed to convert {symbol} from {currency} to USD: {e}")
                    # Keep original price as fallback
                    normalized[symbol] = price

        return normalized
