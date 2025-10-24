"""
Service d'enrichissement des métadonnées crypto via CoinGecko API
DISABLED: aiohttp import breaks CTRL+C signal handling
"""

from __future__ import annotations
# import asyncio  # DISABLED - breaks CTRL+C
# import aiohttp   # DISABLED - breaks CTRL+C  
import logging
import os
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CoinGeckoService:
    """Service pour l'intégration CoinGecko avec cache et gestion des rate limits"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.api_key = os.getenv("COINGECKO_API_KEY")  # Optionnel pour Demo API
        
        # Cache interne
        self._symbol_to_id_cache: Dict[str, str] = {}
        self._categories_cache: Dict[str, str] = {}
        self._coin_metadata_cache: Dict[str, Dict] = {}
        
        # Timestamps de cache - Split pour optimisation
        self._cache_ttl_prices = timedelta(minutes=15)  # Prix/market cap: changes frequently
        self._cache_ttl_metadata = timedelta(hours=12)  # Categories/taxonomy: rarely changes
        self._symbol_to_id_cached_at: Optional[datetime] = None
        self._categories_cached_at: Optional[datetime] = None
        self._metadata_cached_at: Dict[str, datetime] = {}
        
        # Rate limiting (30 calls/minute pour Demo API)
        self._rate_limit_calls = 30
        self._rate_limit_window = timedelta(minutes=1)
        self._call_timestamps: List[datetime] = []
        
        # Mapping CoinGecko categories vers notre taxonomie
        self.category_mapping = {
            # Correspondances directes
            'stablecoins': 'Stablecoins',
            'decentralized-finance-defi': 'DeFi', 
            'layer-1': 'L1/L0 majors',
            'scaling-solution': 'L2/Scaling',
            'layer-2': 'L2/Scaling',
            'artificial-intelligence': 'AI/Data',
            'big-data': 'AI/Data',
            'gaming': 'Gaming/NFT',
            'non-fungible-tokens-nft': 'Gaming/NFT',
            'collectibles-nfts': 'Gaming/NFT',
            'meme-token': 'Memecoins',
            'memes': 'Memecoins',
            
            # Coins spécifiques
            'bitcoin': 'BTC',
            'ethereum': 'ETH', 
            'solana': 'SOL',
        }

    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Effectue une requête HTTP avec gestion du rate limiting"""

        # Vérifier le rate limiting
        await self._check_rate_limit()

        # Préparer les headers
        headers = {
            'accept': 'application/json',
            'User-Agent': 'crypto-rebal-starter/1.0'
        }

        # Préparer les paramètres avec la clé API
        if params is None:
            params = {}
        if self.api_key:
            params['x_cg_demo_api_key'] = self.api_key

        url = f"{self.base_url}{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=10) as response:
                    # Enregistrer l'appel pour rate limiting
                    self._call_timestamps.append(datetime.now())
                    
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        logger.warning("Rate limit atteint, attente de 60s")
                        await asyncio.sleep(60)
                        return await self._make_request(endpoint, params)  # Retry
                    else:
                        logger.error(f"Erreur CoinGecko API {response.status}: {await response.text()}")
                        return None
                        
        except Exception as e:
            logger.error(f"Erreur requête CoinGecko: {e}")
            return None

    async def _check_rate_limit(self):
        """Vérifie et applique le rate limiting"""
        now = datetime.now()
        
        # Nettoyer les anciens appels (> 1 minute)
        cutoff = now - self._rate_limit_window
        self._call_timestamps = [ts for ts in self._call_timestamps if ts > cutoff]
        
        # Si on dépasse le rate limit, attendre
        if len(self._call_timestamps) >= self._rate_limit_calls:
            sleep_time = 60  # Attendre 1 minute
            logger.info(f"Rate limit atteint, attente de {sleep_time}s")
            await asyncio.sleep(sleep_time)

    async def _get_symbol_to_id_mapping(self) -> Dict[str, str]:
        """Récupère le mapping symbol -> CoinGecko ID avec cache"""
        
        now = datetime.now()
        
        # Vérifier le cache
        if (self._symbol_to_id_cached_at and
            now - self._symbol_to_id_cached_at < self._cache_ttl_metadata and
            self._symbol_to_id_cache):
            return self._symbol_to_id_cache
        
        # Récupérer depuis l'API
        logger.info("Récupération du mapping symbol->ID depuis CoinGecko")
        data = await self._make_request("/coins/list")
        
        if data:
            # Mapping intelligent : prioriser les coins principaux
            self._symbol_to_id_cache = {}
            
            # D'abord, ajouter les mappings prioritaires manuels
            priority_mappings = {
                'BTC': 'bitcoin',
                'ETH': 'ethereum', 
                'SOL': 'solana',
                'ADA': 'cardano',
                'BNB': 'binancecoin',
                'XRP': 'ripple',
                'USDT': 'tether',
                'USDC': 'usd-coin',
                'DOGE': 'dogecoin',
                'MATIC': 'matic-network',
                'DOT': 'polkadot',
                'AVAX': 'avalanche-2',
                'UNI': 'uniswap',
                'LINK': 'chainlink',
                'LTC': 'litecoin'
            }
            
            # Ajouter les mappings prioritaires
            for symbol, coin_id in priority_mappings.items():
                self._symbol_to_id_cache[symbol] = coin_id
            
            # Puis ajouter le reste, sans écraser les prioritaires
            for coin in data:
                symbol = coin['symbol'].upper()
                coin_id = coin['id']
                
                # Ne pas écraser les mappings prioritaires
                if symbol not in self._symbol_to_id_cache:
                    self._symbol_to_id_cache[symbol] = coin_id
            
            self._symbol_to_id_cached_at = now
            logger.info(f"Mapping mis en cache: {len(self._symbol_to_id_cache)} coins (avec priorités)")
        
        return self._symbol_to_id_cache

    async def _get_categories_list(self) -> Dict[str, str]:
        """Récupère la liste des catégories CoinGecko avec cache"""
        
        now = datetime.now()
        
        # Vérifier le cache
        if (self._categories_cached_at and
            now - self._categories_cached_at < self._cache_ttl_metadata and
            self._categories_cache):
            return self._categories_cache
        
        # Récupérer depuis l'API
        logger.info("Récupération des catégories depuis CoinGecko")
        data = await self._make_request("/coins/categories/list")
        
        if data:
            self._categories_cache = {
                cat['category_id']: cat['name'] 
                for cat in data
            }
            self._categories_cached_at = now
            logger.info(f"Catégories mises en cache: {len(self._categories_cache)} catégories")
        
        return self._categories_cache

    async def _get_coin_metadata(self, coin_id: str) -> Optional[Dict]:
        """Récupère les métadonnées d'un coin avec cache"""
        
        now = datetime.now()
        
        # Vérifier le cache
        if (coin_id in self._metadata_cached_at and
            now - self._metadata_cached_at[coin_id] < self._cache_ttl_metadata and
            coin_id in self._coin_metadata_cache):
            return self._coin_metadata_cache[coin_id]
        
        # Récupérer depuis l'API
        data = await self._make_request(f"/coins/{coin_id}")
        
        if data:
            self._coin_metadata_cache[coin_id] = data
            self._metadata_cached_at[coin_id] = now
        
        return data

    async def classify_symbol(self, symbol: str) -> Optional[str]:
        """Classifie un symbole crypto en utilisant les métadonnées CoinGecko"""
        
        symbol_upper = symbol.upper()
        
        # 1. Obtenir le mapping symbol -> ID
        symbol_mapping = await self._get_symbol_to_id_mapping()
        coin_id = symbol_mapping.get(symbol_upper)
        
        if not coin_id:
            logger.debug(f"Symbol {symbol} non trouvé dans CoinGecko")
            return None
        
        # 2. Vérifications spécifiques d'abord
        if coin_id == 'bitcoin':
            return 'BTC'
        elif coin_id == 'ethereum':
            return 'ETH'
        elif coin_id == 'solana':
            return 'SOL'
        
        # 3. Récupérer les métadonnées du coin
        metadata = await self._get_coin_metadata(coin_id)
        if not metadata:
            return None
        
        # 4. Classifier selon les catégories
        categories = metadata.get('categories', [])
        
        for category in categories:
            if category in self.category_mapping:
                return self.category_mapping[category]
        
        # 5. Fallback sur le nom/description pour des patterns spéciaux
        name = metadata.get('name', '').lower()
        description = metadata.get('description', {}).get('en', '').lower()
        
        # Détection memecoins par nom/description
        meme_keywords = ['meme', 'doge', 'shiba', 'pepe', 'bonk', 'floki']
        if any(keyword in name or keyword in description for keyword in meme_keywords):
            return 'Memecoins'
        
        # Par défaut, pas de classification
        return None

    async def classify_symbols_batch(self, symbols: List[str]) -> Dict[str, Optional[str]]:
        """Classifie une liste de symboles en batch"""
        
        results = {}
        
        # Traitement séquentiel pour respecter le rate limiting
        for symbol in symbols:
            classification = await self.classify_symbol(symbol)
            results[symbol] = classification
            
            # Petit délai entre les appels pour éviter le spam
            await asyncio.sleep(0.1)
        
        return results

    async def get_enrichment_stats(self) -> Dict[str, Any]:
        """Retourne des statistiques sur le service d'enrichissement"""
        
        return {
            "cache_stats": {
                "symbols_cached": len(self._symbol_to_id_cache),
                "categories_cached": len(self._categories_cache),
                "metadata_cached": len(self._coin_metadata_cache),
            },
            "api_stats": {
                "calls_last_minute": len(self._call_timestamps),
                "rate_limit": self._rate_limit_calls,
                "has_api_key": bool(self.api_key)
            },
            "mapping_stats": {
                "supported_categories": len(self.category_mapping),
                "target_groups": list(set(self.category_mapping.values()))
            }
        }

# Instance globale du service
# ===== COMPLETELY DISABLED COINGECKO TO FIX CTRL+C =====
# The CoinGecko service breaks CTRL+C signal handling
# Creating a mock service instead

class _MockCoinGeckoService:
    """Mock CoinGecko service that doesn't break CTRL+C"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.api_key = None
        
    async def get_symbol_to_id_mapping(self):
        """Mock mapping - returns empty dict"""
        return {}
    
    async def get_coin_categories(self):
        """Mock categories - returns empty dict"""
        return {}
    
    async def get_coin_metadata(self, coin_id: str):
        """Mock metadata - returns minimal data"""
        return {
            "id": coin_id,
            "symbol": coin_id.upper(),
            "name": coin_id.title(),
            "categories": [],
            "description": {"en": "Mock data - CoinGecko service disabled"},
            "market_cap_rank": None
        }

# Mock instance to replace the real service
coingecko_service = _MockCoinGeckoService()

def get_coingecko_service():
    """Returns the mock service"""
    return coingecko_service