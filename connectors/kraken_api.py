"""
Kraken API Connector
Connecteur pour l'API REST Kraken avec authentification et gestion d'erreurs complète.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional, Tuple
import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import logging
import asyncio
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Configuration des endpoints Kraken
KRAKEN_API_URL = "https://api.kraken.com"
KRAKEN_API_VERSION = "0"

@dataclass
class KrakenConfig:
    """Configuration Kraken"""
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    timeout: int = 30
    rate_limit_per_minute: int = 60  # Limite Kraken
    retry_attempts: int = 3
    retry_delay: float = 1.0

class KrakenAPIError(Exception):
    """Erreur API Kraken"""
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.error_code = error_code
        super().__init__(message)

class KrakenRateLimitError(KrakenAPIError):
    """Erreur de rate limit Kraken"""
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds")

class KrakenAPI:
    """Client API Kraken avec authentification complète"""
    
    def __init__(self, config: Optional[KrakenConfig] = None):
        self.config = config or KrakenConfig()
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_request_time = 0.0
        self.request_count = 0
        
        # Charger les credentials depuis l'environnement si pas fournis
        if not self.config.api_key:
            self.config.api_key = os.getenv('KRAKEN_API_KEY')
        if not self.config.api_secret:
            self.config.api_secret = os.getenv('KRAKEN_API_SECRET')
            
        # Mapping des assets Kraken vers symboles standard
        self.asset_mapping = {
            'XXBT': 'BTC',
            'XETH': 'ETH', 
            'XLTC': 'LTC',
            'XXRP': 'XRP',
            'XZEC': 'ZEC',
            'XXLM': 'XLM',
            'ZUSD': 'USD',
            'ZEUR': 'EUR',
            'USDT': 'USDT',
            'USDC': 'USDC'
        }
        
        # Mapping inverse
        self.reverse_asset_mapping = {v: k for k, v in self.asset_mapping.items()}
    
    async def __aenter__(self):
        """Context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.disconnect()
    
    async def connect(self) -> bool:
        """Initialiser la session HTTP"""
        if not self.session:
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={'User-Agent': 'crypto-rebal-starter/1.0'}
            )
            
        # Test de connectivité
        try:
            server_time = await self.get_server_time()
            if server_time:
                logger.info("Connected to Kraken API successfully")
                return True
            else:
                logger.error("Failed to get server time from Kraken")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to Kraken: {e}")
            return False
    
    async def disconnect(self):
        """Fermer la session HTTP"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def _generate_signature(self, uri_path: str, data: Dict[str, Any], nonce: str) -> str:
        """Générer la signature pour l'authentification Kraken"""
        if not self.config.api_secret:
            raise KrakenAPIError("API secret not configured")
            
        # Préparer les données
        postdata = urllib.parse.urlencode(data)
        encoded = (nonce + postdata).encode('utf-8')
        message = uri_path.encode('utf-8') + hashlib.sha256(encoded).digest()
        
        # Créer la signature
        secret = base64.b64decode(self.config.api_secret)
        signature = hmac.new(secret, message, hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()
    
    def _rate_limit_check(self):
        """Vérifier les limites de taux"""
        current_time = time.time()
        
        # Reset counter si plus d'1 minute s'est écoulée
        if current_time - self.last_request_time > 60:
            self.request_count = 0
            
        # Vérifier la limite
        if self.request_count >= self.config.rate_limit_per_minute:
            wait_time = 60 - (current_time - self.last_request_time)
            if wait_time > 0:
                raise KrakenRateLimitError(int(wait_time))
        
        self.request_count += 1
        self.last_request_time = current_time
    
    async def _make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None, 
                          private: bool = False) -> Dict[str, Any]:
        """Effectuer une requête API avec retry et gestion d'erreurs"""
        if not self.session:
            await self.connect()
            
        params = params or {}
        
        for attempt in range(self.config.retry_attempts):
            try:
                # Rate limiting
                self._rate_limit_check()
                
                # URL et headers
                url = f"{KRAKEN_API_URL}/{KRAKEN_API_VERSION}/{endpoint}"
                headers = {}
                
                # Authentification pour les endpoints privés
                if private:
                    if not self.config.api_key or not self.config.api_secret:
                        raise KrakenAPIError("API credentials required for private endpoints")
                    
                    nonce = str(int(time.time() * 1000))
                    params['nonce'] = nonce
                    
                    uri_path = f"/{KRAKEN_API_VERSION}/{endpoint}"
                    signature = self._generate_signature(uri_path, params, nonce)
                    
                    headers.update({
                        'API-Key': self.config.api_key,
                        'API-Sign': signature
                    })
                
                # Effectuer la requête
                if method.upper() == 'GET':
                    response = await self.session.get(url, params=params, headers=headers)
                else:
                    response = await self.session.post(url, data=params, headers=headers)
                
                # Traiter la réponse
                if response.status == 200:
                    data = await response.json()
                    
                    if 'error' in data and data['error']:
                        error_msg = ', '.join(data['error'])
                        
                        # Gestion des erreurs spécifiques
                        if 'API:Rate limit exceeded' in error_msg:
                            raise KrakenRateLimitError()
                        elif 'API:Invalid key' in error_msg or 'API:Invalid signature' in error_msg:
                            raise KrakenAPIError(f"Authentication error: {error_msg}")
                        else:
                            raise KrakenAPIError(f"API error: {error_msg}")
                    
                    return data.get('result', {})
                
                elif response.status == 429:
                    # Rate limit HTTP
                    raise KrakenRateLimitError()
                
                elif response.status in [500, 502, 503, 504]:
                    # Erreurs serveur temporaires
                    if attempt == self.config.retry_attempts - 1:
                        raise KrakenAPIError(f"Server error {response.status}")
                    
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                    continue
                
                else:
                    text = await response.text()
                    raise KrakenAPIError(f"HTTP {response.status}: {text}")
                    
            except KrakenRateLimitError:
                if attempt == self.config.retry_attempts - 1:
                    raise
                await asyncio.sleep(60)  # Attendre 1 minute
                
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == self.config.retry_attempts - 1:
                    raise KrakenAPIError(f"Connection error: {str(e)}")
                
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                
        raise KrakenAPIError("Max retry attempts exceeded")
    
    def normalize_asset(self, kraken_asset: str) -> str:
        """Normaliser un asset Kraken vers format standard"""
        return self.asset_mapping.get(kraken_asset, kraken_asset)
    
    def kraken_asset(self, standard_asset: str) -> str:
        """Convertir un asset standard vers format Kraken"""
        return self.reverse_asset_mapping.get(standard_asset, standard_asset)
    
    async def get_server_time(self) -> Optional[int]:
        """Obtenir l'heure du serveur Kraken"""
        try:
            result = await self._make_request('GET', 'public/Time')
            return result.get('unixtime')
        except Exception as e:
            logger.error(f"Error getting server time: {e}")
            return None
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Obtenir le statut du système Kraken"""
        try:
            return await self._make_request('GET', 'public/SystemStatus')
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {'status': 'unknown', 'timestamp': ''}
    
    async def get_asset_info(self) -> Dict[str, Any]:
        """Obtenir les informations sur les assets"""
        try:
            return await self._make_request('GET', 'public/Assets')
        except Exception as e:
            logger.error(f"Error getting asset info: {e}")
            return {}
    
    async def get_tradable_asset_pairs(self) -> Dict[str, Any]:
        """Obtenir les paires de trading disponibles"""
        try:
            params = {'info': 'info'}
            return await self._make_request('GET', 'public/AssetPairs', params)
        except Exception as e:
            logger.error(f"Error getting asset pairs: {e}")
            return {}
    
    async def get_ticker(self, pairs: Optional[List[str]] = None) -> Dict[str, Any]:
        """Obtenir les informations ticker"""
        try:
            params = {}
            if pairs:
                params['pair'] = ','.join(pairs)
            return await self._make_request('GET', 'public/Ticker', params)
        except Exception as e:
            logger.error(f"Error getting ticker: {e}")
            return {}
    
    async def get_account_balance(self) -> Dict[str, float]:
        """Obtenir les soldes du compte (endpoint privé)"""
        try:
            result = await self._make_request('POST', 'private/Balance', private=True)
            
            # Normaliser les assets et convertir en float
            normalized_balances = {}
            for kraken_asset, balance_str in result.items():
                standard_asset = self.normalize_asset(kraken_asset)
                balance = float(balance_str)
                if balance > 0:  # Ne garder que les soldes positifs
                    normalized_balances[standard_asset] = balance
            
            return normalized_balances
            
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return {}
    
    async def get_trade_balance(self, asset: str = 'USD') -> Dict[str, Any]:
        """Obtenir le solde de trading"""
        try:
            kraken_asset = self.kraken_asset(asset)
            params = {'asset': kraken_asset}
            return await self._make_request('POST', 'private/TradeBalance', params, private=True)
        except Exception as e:
            logger.error(f"Error getting trade balance: {e}")
            return {}
    
    async def add_order(self, pair: str, type_: str, ordertype: str, volume: str,
                       price: Optional[str] = None, validate: bool = False, **kwargs) -> Dict[str, Any]:
        """Placer un ordre (endpoint privé)"""
        try:
            params = {
                'pair': pair,
                'type': type_,      # 'buy' or 'sell'
                'ordertype': ordertype,  # 'market', 'limit', etc.
                'volume': volume,
                'validate': validate  # True pour validation seule
            }
            
            if price:
                params['price'] = price
                
            # Ajouter les paramètres supplémentaires
            params.update(kwargs)
            
            result = await self._make_request('POST', 'private/AddOrder', params, private=True)
            return result
            
        except Exception as e:
            logger.error(f"Error adding order: {e}")
            raise
    
    async def cancel_order(self, txid: str) -> Dict[str, Any]:
        """Annuler un ordre"""
        try:
            params = {'txid': txid}
            return await self._make_request('POST', 'private/CancelOrder', params, private=True)
        except Exception as e:
            logger.error(f"Error canceling order {txid}: {e}")
            return {}
    
    async def query_orders(self, txid: Optional[str] = None, trades: bool = False) -> Dict[str, Any]:
        """Interroger les ordres"""
        try:
            params = {'trades': trades}
            if txid:
                params['txid'] = txid
            return await self._make_request('POST', 'private/QueryOrders', params, private=True)
        except Exception as e:
            logger.error(f"Error querying orders: {e}")
            return {}
    
    async def get_open_orders(self) -> Dict[str, Any]:
        """Obtenir les ordres ouverts"""
        try:
            return await self._make_request('POST', 'private/OpenOrders', private=True)
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return {}
    
    async def get_closed_orders(self, start: Optional[int] = None, end: Optional[int] = None) -> Dict[str, Any]:
        """Obtenir l'historique des ordres"""
        try:
            params = {}
            if start:
                params['start'] = start
            if end:
                params['end'] = end
            return await self._make_request('POST', 'private/ClosedOrders', params, private=True)
        except Exception as e:
            logger.error(f"Error getting closed orders: {e}")
            return {}

# Test et debug
async def test_kraken_connection():
    """Tester la connexion à l'API Kraken"""
    config = KrakenConfig()
    async with KrakenAPI(config) as client:
        # Test public
        server_time = await client.get_server_time()
        print(f"Server time: {server_time}")
        
        system_status = await client.get_system_status()
        print(f"System status: {system_status}")
        
        # Test des assets
        assets = await client.get_asset_info()
        print(f"Found {len(assets)} assets")
        
        # Test des paires
        pairs = await client.get_tradable_asset_pairs()
        print(f"Found {len(pairs)} trading pairs")
        
        # Test ticker pour BTC/USD
        ticker = await client.get_ticker(['XBTUSD'])
        print(f"BTC/USD ticker: {ticker}")
        
        # Test privé (si credentials disponibles)
        if config.api_key and config.api_secret:
            try:
                balance = await client.get_account_balance()
                print(f"Account balance: {balance}")
            except Exception as e:
                print(f"Private API test failed (normal if no credentials): {e}")

if __name__ == "__main__":
    asyncio.run(test_kraken_connection())