# connectors/coingecko.py
from __future__ import annotations

import json
import os
import time
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

import httpx

log = logging.getLogger(__name__)

@dataclass
class CoinMeta:
    """Métadonnées d'un coin pour scoring universe."""
    symbol: str
    alias: str  # symbole normalisé utilisé dans le portefeuille
    coingecko_id: str
    market_cap_rank: Optional[int] = None
    volume_24h: Optional[float] = None
    price_change_30d: Optional[float] = None
    price_change_90d: Optional[float] = None
    liquidity_proxy: Optional[float] = None  # approximation basée sur volume/mcap
    risk_flags: List[str] = None

    def __post_init__(self):
        if self.risk_flags is None:
            self.risk_flags = []


class CoinGeckoConnector:
    """Connecteur CoinGecko pour récupération données marché."""

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout
        self.session = httpx.Client(timeout=timeout)
        self._aliases_map: Optional[Dict[str, str]] = None
        self._last_request_time = 0.0
        self._rate_limit_delay = 1.1  # Délai entre requêtes (free tier: ~10-50/min)

    def _load_aliases_map(self) -> Dict[str, str]:
        """Charge le mapping symbol/alias -> coingecko_id depuis data/mkt/aliases.json."""
        if self._aliases_map is not None:
            return self._aliases_map

        aliases_path = os.path.join("data", "mkt", "aliases.json")
        try:
            if os.path.exists(aliases_path):
                with open(aliases_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._aliases_map = data.get("mappings", {})
                    log.debug(f"Loaded {len(self._aliases_map)} alias mappings from {aliases_path}")
            else:
                log.warning(f"Aliases file not found: {aliases_path}")
                self._aliases_map = {}
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in aliases file {aliases_path}: {e}")
            self._aliases_map = {}
        except OSError as e:
            log.error(f"Failed to read aliases file {aliases_path}: {e}")
            self._aliases_map = {}
        except KeyError as e:
            log.warning(f"Missing 'mappings' key in aliases file {aliases_path}: {e}")
            self._aliases_map = {}

        return self._aliases_map

    def _rate_limit(self):
        """Simple rate limiting pour éviter les erreurs 429."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit_delay:
            sleep_time = self._rate_limit_delay - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _resolve_coingecko_id(self, symbol_or_alias: str) -> Optional[str]:
        """Résout un symbol/alias vers coingecko_id."""
        aliases_map = self._load_aliases_map()

        # Tentatives de résolution par ordre de priorité
        symbol_upper = symbol_or_alias.upper().strip()

        # 1. Mapping direct
        if symbol_upper in aliases_map:
            return aliases_map[symbol_upper]

        # 2. Heuristiques simples
        symbol_lower = symbol_or_alias.lower().strip()

        # Cas particuliers fréquents
        heuristics = {
            "bitcoin": "bitcoin",
            "ethereum": "ethereum",
            "solana": "solana",
            "cardano": "cardano",
            "polkadot": "polkadot",
            "chainlink": "chainlink",
            "uniswap": "uniswap"
        }

        if symbol_lower in heuristics:
            return heuristics[symbol_lower]

        # 3. Par défaut, assumer que le symbol en lowercase = coingecko_id
        # (pas toujours vrai, mais permet d'essayer)
        log.debug(f"No mapping found for {symbol_or_alias}, trying lowercase: {symbol_lower}")
        return symbol_lower

    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Effectue une requête vers l'API CoinGecko avec gestion d'erreur."""
        self._rate_limit()

        url = f"{self.BASE_URL}{endpoint}"
        headers = {}

        if self.api_key:
            headers["x-cg-demo-api-key"] = self.api_key

        if params is None:
            params = {}

        try:
            log.debug(f"CoinGecko request: {endpoint} with params: {params}")
            response = self.session.get(url, params=params, headers=headers)
            response.raise_for_status()

            return response.json()

        except httpx.TimeoutException:
            log.error(f"CoinGecko API timeout for {endpoint}")
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                log.warning(f"CoinGecko rate limit hit, status: {e.response.status_code}")
                # Augmenter le délai pour les prochaines requêtes
                self._rate_limit_delay = min(self._rate_limit_delay * 1.5, 10.0)
            else:
                log.error(f"CoinGecko API error {e.response.status_code} for {endpoint}: {e}")
            return None
        except httpx.ConnectError as e:
            log.error(f"Connection failed to CoinGecko API for {endpoint}: {e}")
            return None
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON response from CoinGecko for {endpoint}: {e}")
            return None

    def get_market_snapshot(self, symbols_or_aliases: List[str]) -> Dict[str, CoinMeta]:
        """
        Récupère un snapshot marché pour une liste de symbols/aliases.

        Returns:
            Dict[symbol, CoinMeta] - Seuls les coins trouvés sont inclus
        """
        if not symbols_or_aliases:
            return {}

        result: Dict[str, CoinMeta] = {}
        unresolved: List[str] = []

        # 1. Résoudre les symbols vers coingecko_ids
        symbol_to_id: Dict[str, str] = {}
        for symbol in symbols_or_aliases:
            coingecko_id = self._resolve_coingecko_id(symbol)
            if coingecko_id:
                symbol_to_id[symbol] = coingecko_id
            else:
                unresolved.append(symbol)

        if unresolved:
            log.warning(f"Could not resolve coingecko_id for: {unresolved}")

        if not symbol_to_id:
            log.warning("No symbols could be resolved to coingecko_ids")
            return {}

        # 2. Requête API (batch jusqu'à 100 coins)
        ids_list = list(symbol_to_id.values())
        ids_param = ",".join(ids_list[:100])  # Limite CoinGecko

        params = {
            "ids": ids_param,
            "vs_currencies": "usd",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_24hr_change": "true",
            "price_change_percentage": "30d,90d"
        }

        data = self._make_request("/simple/price", params)
        if not data:
            log.error("Failed to fetch market data from CoinGecko")
            return {}

        # 3. Parser la réponse et construire CoinMeta
        for symbol, coingecko_id in symbol_to_id.items():
            coin_data = data.get(coingecko_id)
            if not coin_data:
                log.debug(f"No data returned for {symbol} (id: {coingecko_id})")
                continue

            # Extraction des données avec fallbacks
            usd_price = coin_data.get("usd", 0.0)
            market_cap = coin_data.get("usd_market_cap")
            volume_24h = coin_data.get("usd_24h_vol")
            price_change_30d = coin_data.get("usd_30d_change")
            price_change_90d = coin_data.get("usd_90d_change")

            # Calcul liquidity_proxy (volume_24h / market_cap si disponible)
            liquidity_proxy = None
            if volume_24h and market_cap and market_cap > 0:
                liquidity_proxy = volume_24h / market_cap

            # Détection risk_flags basiques
            risk_flags = []
            if market_cap and market_cap < 10_000_000:  # < 10M mcap
                risk_flags.append("small_cap")
            if volume_24h and volume_24h < 100_000:  # < 100k volume/24h
                risk_flags.append("low_volume")
            if not market_cap or not volume_24h:
                risk_flags.append("incomplete_data")

            # Détection rank depuis market_cap (approximatif)
            market_cap_rank = None
            if market_cap:
                # Heuristique simple basée sur des seuils
                if market_cap > 500_000_000_000:  # >500B
                    market_cap_rank = 1
                elif market_cap > 100_000_000_000:  # >100B
                    market_cap_rank = 2
                elif market_cap > 50_000_000_000:   # >50B
                    market_cap_rank = 5
                elif market_cap > 10_000_000_000:   # >10B
                    market_cap_rank = 10
                elif market_cap > 1_000_000_000:    # >1B
                    market_cap_rank = 50
                elif market_cap > 100_000_000:      # >100M
                    market_cap_rank = 200
                else:
                    market_cap_rank = 500

            coin_meta = CoinMeta(
                symbol=symbol.upper(),
                alias=symbol.upper(),
                coingecko_id=coingecko_id,
                market_cap_rank=market_cap_rank,
                volume_24h=volume_24h,
                price_change_30d=price_change_30d,
                price_change_90d=price_change_90d,
                liquidity_proxy=liquidity_proxy,
                risk_flags=risk_flags
            )

            result[symbol.upper()] = coin_meta

        log.info(f"Retrieved market data for {len(result)}/{len(symbols_or_aliases)} symbols")
        return result

    def get_category_top(self, category: str, n: int = 20) -> List[CoinMeta]:
        """
        Récupère le top N des coins d'une catégorie CoinGecko.
        Utile pour élargir l'univers au-delà du portefeuille courant.
        """
        if n <= 0:
            return []

        # Mapping de nos catégories vers les catégories CoinGecko
        category_map = {
            "layer-1": "layer-1",
            "layer-2": "layer-2",
            "defi": "decentralized-finance-defi",
            "memecoins": "meme-token",
            "ai-data": "artificial-intelligence",
            "gaming-nft": "gaming",
            "storage": "storage"
        }

        cg_category = category_map.get(category, category)

        params = {
            "category": cg_category,
            "order": "market_cap_desc",
            "per_page": min(n, 100),
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "30d,90d"
        }

        data = self._make_request("/coins/markets", params)
        if not data or not isinstance(data, list):
            log.error(f"Failed to fetch category {category} top coins")
            return []

        result: List[CoinMeta] = []

        for item in data[:n]:
            symbol = item.get("symbol", "").upper()
            coingecko_id = item.get("id", "")
            market_cap_rank = item.get("market_cap_rank")
            volume_24h = item.get("total_volume")
            price_change_30d = item.get("price_change_percentage_30d_in_currency")
            price_change_90d = item.get("price_change_percentage_90d_in_currency")
            market_cap = item.get("market_cap")

            # Calcul liquidity_proxy
            liquidity_proxy = None
            if volume_24h and market_cap and market_cap > 0:
                liquidity_proxy = volume_24h / market_cap

            # Risk flags
            risk_flags = []
            if market_cap and market_cap < 10_000_000:
                risk_flags.append("small_cap")
            if volume_24h and volume_24h < 100_000:
                risk_flags.append("low_volume")

            coin_meta = CoinMeta(
                symbol=symbol,
                alias=symbol,
                coingecko_id=coingecko_id,
                market_cap_rank=market_cap_rank,
                volume_24h=volume_24h,
                price_change_30d=price_change_30d,
                price_change_90d=price_change_90d,
                liquidity_proxy=liquidity_proxy,
                risk_flags=risk_flags
            )

            result.append(coin_meta)

        log.info(f"Retrieved {len(result)} coins from category {category}")
        return result

    def close(self):
        """Ferme la session HTTP."""
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Instance globale réutilisable
_global_connector: Optional[CoinGeckoConnector] = None

def get_connector(user_id: str = None, api_key: str = None) -> CoinGeckoConnector:
    """
    Retourne l'instance globale du connecteur CoinGecko.

    Args:
        user_id: ID utilisateur pour récupérer la clé API depuis secrets.json
        api_key: Clé API explicite (override user_id)

    Returns:
        Instance de CoinGeckoConnector
    """
    global _global_connector

    # Si une api_key est fournie explicitement, créer nouveau connecteur
    if api_key:
        return CoinGeckoConnector(api_key=api_key)

    # Lazy init avec user_id ou fallback .env
    if _global_connector is None:
        if user_id:
            from services.user_secrets import get_coingecko_api_key
            api_key = get_coingecko_api_key(user_id)
        else:
            api_key = os.getenv("COINGECKO_API_KEY", "")

        _global_connector = CoinGeckoConnector(api_key=api_key)

    return _global_connector