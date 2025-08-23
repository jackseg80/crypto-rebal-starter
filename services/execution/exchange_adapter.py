"""
Exchange Adapter System - Adaptateurs pour différents exchanges

Ce module fournit une interface unifiée pour interagir avec différents
exchanges (CEX et DEX) de manière standardisée.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import logging
import asyncio
import time
import random
from datetime import datetime, timezone

from .order_manager import Order, OrderStatus
from .safety_validator import safety_validator, SafetyResult

logger = logging.getLogger(__name__)

# Error handling and retry utilities
class RetryableError(Exception):
    """Exception raised for errors that can be retried"""
    pass

class RateLimitError(RetryableError):
    """Exception raised when rate limit is exceeded"""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds" if retry_after else "Rate limit exceeded")

def calculate_backoff_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate exponential backoff delay with jitter"""
    delay = min(base_delay * (2 ** attempt), max_delay)
    # Add jitter (±25%)
    jitter = delay * 0.25 * (random.random() * 2 - 1)
    return max(0.1, delay + jitter)

def retry_on_error(max_attempts: int = 3, base_delay: float = 1.0, 
                   retryable_errors: tuple = (RetryableError, ConnectionError, TimeoutError)):
    """Decorator to retry async functions on specific errors"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_errors as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts")
                        break
                    
                    # Handle rate limit with specific delay
                    if isinstance(e, RateLimitError) and e.retry_after:
                        delay = e.retry_after
                        logger.warning(f"Rate limit hit, waiting {delay}s before retry {attempt + 1}")
                    else:
                        delay = calculate_backoff_delay(attempt, base_delay)
                        logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.1f}s: {e}")
                    
                    await asyncio.sleep(delay)
                except Exception as e:
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise
            
            raise last_exception
        return wrapper
    return decorator

class ExchangeType(Enum):
    """Types d'exchanges supportés"""
    CEX = "centralized"
    DEX = "decentralized"
    SIMULATOR = "simulator"

@dataclass
class ExchangeConfig:
    """Configuration pour un exchange"""
    name: str
    type: ExchangeType
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    sandbox: bool = True
    rate_limit: int = 10  # Requêtes par seconde
    
    # Paramètres spécifiques
    base_url: Optional[str] = None
    fee_rate: float = 0.001  # 0.1% par défaut
    min_order_size: float = 10.0  # USD minimum
    
@dataclass
class TradingPair:
    """Information sur une paire de trading"""
    symbol: str           # "BTC/USD"
    base_asset: str       # "BTC"
    quote_asset: str      # "USD"
    available: bool = True
    min_order_size: Optional[float] = None
    price_precision: int = 8
    quantity_precision: int = 8

@dataclass  
class OrderResult:
    """Résultat d'exécution d'un ordre"""
    success: bool
    order_id: str
    exchange_order_id: Optional[str] = None
    
    # Détails d'exécution
    filled_quantity: float = 0.0
    filled_usd: float = 0.0
    avg_price: Optional[float] = None
    fees: float = 0.0
    
    # Statut et erreurs
    status: OrderStatus = OrderStatus.PENDING
    error_message: Optional[str] = None
    
    # Métadonnées
    executed_at: Optional[datetime] = None
    exchange_data: Optional[Dict[str, Any]] = None

class ExchangeAdapter(ABC):
    """Interface abstraite pour tous les adaptateurs d'exchange"""
    
    def __init__(self, config: ExchangeConfig):
        self.config = config
        self.name = config.name
        self.type = config.type
        self.connected = False
        
    @abstractmethod
    async def connect(self) -> bool:
        """Se connecter à l'exchange"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Se déconnecter de l'exchange"""
        pass
    
    @abstractmethod
    async def get_trading_pairs(self) -> List[TradingPair]:
        """Obtenir la liste des paires de trading disponibles"""
        pass
    
    @abstractmethod
    async def get_balance(self, asset: str) -> float:
        """Obtenir le solde d'un actif"""
        pass
    
    @abstractmethod
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Obtenir le prix actuel d'un symbole"""
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> OrderResult:
        """Placer un ordre sur l'exchange"""
        pass
    
    @abstractmethod
    async def cancel_order(self, exchange_order_id: str) -> bool:
        """Annuler un ordre"""
        pass
    
    @abstractmethod
    async def get_order_status(self, exchange_order_id: str) -> OrderResult:
        """Obtenir le statut d'un ordre"""
        pass
    
    def validate_order(self, order: Order) -> List[str]:
        """Valider un ordre avant placement"""
        errors = []
        
        # Vérifications de base
        if not order.symbol:
            errors.append("Symbol is required")
        
        if order.quantity <= 0:
            errors.append("Quantity must be positive")
        
        if abs(order.usd_amount) < self.config.min_order_size:
            errors.append(f"Order size below minimum: ${self.config.min_order_size}")
        
        return errors

class SimulatorAdapter(ExchangeAdapter):
    """Adaptateur simulateur pour tests et dry-run"""
    
    def __init__(self, config: ExchangeConfig):
        super().__init__(config)
        self.simulated_balances: Dict[str, float] = {}
        self.simulated_prices: Dict[str, float] = {}
        self.order_counter = 0
        
        # Prices simulés par défaut
        self.simulated_prices.update({
            "BTC": 45000.0,
            "ETH": 3000.0,
            "SOL": 100.0,
            "USDT": 1.0,
            "USDC": 1.0
        })
    
    async def connect(self) -> bool:
        """Simulation de connexion"""
        await asyncio.sleep(0.1)  # Simule latence
        self.connected = True
        logger.info(f"Connected to {self.name} (simulator)")
        return True
    
    async def disconnect(self) -> None:
        """Simulation de déconnexion"""
        self.connected = False
        logger.info(f"Disconnected from {self.name}")
    
    async def get_trading_pairs(self) -> List[TradingPair]:
        """Paires simulées"""
        pairs = []
        for base in ["BTC", "ETH", "SOL"]:
            for quote in ["USD", "USDT", "USDC"]:
                pairs.append(TradingPair(
                    symbol=f"{base}/{quote}",
                    base_asset=base,
                    quote_asset=quote,
                    min_order_size=10.0
                ))
        return pairs
    
    async def get_balance(self, asset: str) -> float:
        """Solde simulé"""
        return self.simulated_balances.get(asset, 1000.0)  # $1000 par défaut
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Prix simulé"""
        # Extraire l'actif de base
        base_asset = symbol.split('/')[0] if '/' in symbol else symbol
        return self.simulated_prices.get(base_asset)
    
    async def place_order(self, order: Order) -> OrderResult:
        """Simulation de placement d'ordre"""
        await asyncio.sleep(0.2)  # Simule latence
        
        self.order_counter += 1
        exchange_order_id = f"SIM_{self.order_counter:06d}"
        
        # Simulation du prix d'exécution
        base_asset = order.symbol.split('/')[0] if '/' in order.symbol else order.symbol
        current_price = await self.get_current_price(base_asset)
        
        if not current_price:
            return OrderResult(
                success=False,
                order_id=order.id,
                error_message=f"No price available for {order.symbol}",
                status=OrderStatus.FAILED
            )
        
        # Simule un slippage léger
        slippage = 0.001  # 0.1%
        execution_price = current_price * (1 + slippage if order.action == "buy" else 1 - slippage)
        
        # Calcul des quantités
        if order.action == "buy":
            filled_quantity = abs(order.usd_amount) / execution_price
        else:
            filled_quantity = abs(order.quantity) if order.quantity != 0 else abs(order.usd_amount) / execution_price
        
        filled_usd = filled_quantity * execution_price
        fees = filled_usd * self.config.fee_rate
        
        # Simulation réussie par défaut (95% de succès)
        import random
        if random.random() < 0.95:
            status = OrderStatus.FILLED
            success = True
            error_message = None
        else:
            status = OrderStatus.FAILED  
            success = False
            error_message = "Simulated execution failure"
            filled_quantity = 0.0
            filled_usd = 0.0
            fees = 0.0
        
        result = OrderResult(
            success=success,
            order_id=order.id,
            exchange_order_id=exchange_order_id,
            filled_quantity=filled_quantity,
            filled_usd=filled_usd,
            avg_price=execution_price,
            fees=fees,
            status=status,
            error_message=error_message,
            executed_at=datetime.now(timezone.utc),
            exchange_data={"simulated": True, "slippage": slippage}
        )
        
        logger.info(f"Simulated order {order.alias}: {order.action} {filled_quantity:.6f} @ ${execution_price:.2f}")
        return result
    
    async def cancel_order(self, exchange_order_id: str) -> bool:
        """Simulation d'annulation"""
        await asyncio.sleep(0.1)
        logger.info(f"Simulated cancel order {exchange_order_id}")
        return True
    
    async def get_order_status(self, exchange_order_id: str) -> OrderResult:
        """Statut simulé"""
        return OrderResult(
            success=True,
            order_id="",
            exchange_order_id=exchange_order_id,
            status=OrderStatus.FILLED
        )

class BinanceAdapter(ExchangeAdapter):
    """Adaptateur pour Binance avec API réelle et gestion d'erreurs robuste"""
    
    def __init__(self, config: ExchangeConfig):
        super().__init__(config)
        self.client = None
        self._trading_pairs_cache = None
        self._last_pairs_update = None
        self._connection_attempts = 0
        self._last_connection_attempt = None
        self._rate_limit_reset_time = None
    
    def _handle_binance_exception(self, e) -> None:
        """Convert Binance API exceptions to our custom error types"""
        try:
            from binance.exceptions import BinanceAPIException, BinanceRequestException
            
            if isinstance(e, BinanceAPIException):
                error_code = e.code
                error_msg = e.message
                
                # Rate limit errors (HTTP 429)
                if error_code == -1003 or "Too many requests" in error_msg or e.status_code == 429:
                    # Extract retry-after from headers if available
                    retry_after = getattr(e, 'retry_after', None) or 60
                    raise RateLimitError(retry_after)
                
                # IP banned (usually temporary)
                elif error_code == -1002:
                    raise RateLimitError(300)  # Wait 5 minutes for IP ban
                
                # Connection/network errors that can be retried
                elif error_code in [-1001, -1006, -1007, -1014, -1015]:
                    raise RetryableError(f"Binance connection error: {error_msg}")
                
                # Account/permission issues (not retryable)
                elif error_code in [-2010, -2011, -2013, -2014, -2015]:
                    raise ValueError(f"Binance account error: {error_msg}")
                
                # Generic API error (not retryable)
                else:
                    raise ValueError(f"Binance API error {error_code}: {error_msg}")
            
            elif isinstance(e, BinanceRequestException):
                # Network/connection errors that can be retried
                raise RetryableError(f"Binance request error: {str(e)}")
            
        except ImportError:
            # python-binance not available, treat as generic error
            pass
        
        # Fallback for unknown exceptions
        if "timeout" in str(e).lower() or "connection" in str(e).lower():
            raise RetryableError(str(e))
        else:
            raise e
        
    @retry_on_error(max_attempts=3, base_delay=2.0)
    async def connect(self) -> bool:
        """Connexion à Binance avec validation des credentials et retry automatique"""
        self._connection_attempts += 1
        self._last_connection_attempt = time.time()
        
        try:
            # Import dynamique pour éviter les erreurs si le package n'est pas installé
            from binance.client import Client
            
            if not self.config.api_key or not self.config.api_secret:
                logger.error("Binance API key/secret not provided")
                return False
            
            # Créer le client Binance
            self.client = Client(
                api_key=self.config.api_key,
                api_secret=self.config.api_secret,
                testnet=self.config.sandbox  # Utilise testnet si sandbox=True
            )
            
            # Test de connexion
            account_info = self.client.get_account()
            
            if account_info:
                self.connected = True
                self._connection_attempts = 0  # Reset counter on success
                mode = "TESTNET" if self.config.sandbox else "MAINNET"
                logger.info(f"Connected to Binance {mode} successfully (attempt {self._connection_attempts})")
                return True
            else:
                logger.error("Failed to get account info from Binance")
                return False
                
        except ImportError:
            logger.error("python-binance package not installed. Run: pip install python-binance")
            return False
        except Exception as e:
            # Convert to our custom error types for retry handling
            try:
                self._handle_binance_exception(e)
            except (RetryableError, RateLimitError):
                # Let the retry decorator handle these
                raise
            except Exception as converted_e:
                logger.error(f"Non-retryable error connecting to Binance: {converted_e}")
                return False
            
        return False
    
    async def disconnect(self) -> None:
        """Déconnexion propre"""
        if self.client:
            # Pas de méthode close() spécifique pour python-binance
            self.client = None
        self.connected = False
        logger.info("Disconnected from Binance")
    
    @retry_on_error(max_attempts=2, base_delay=2.0)
    async def get_trading_pairs(self) -> List[TradingPair]:
        """Récupérer les paires de trading Binance avec cache et retry"""
        if not self.connected or not self.client:
            logger.warning("Not connected to Binance, attempting reconnection...")
            if not await self.connect():
                return []
            
        try:
            from datetime import datetime, timedelta
            
            # Cache pendant 1 heure
            if (self._trading_pairs_cache and self._last_pairs_update and 
                datetime.now() - self._last_pairs_update < timedelta(hours=1)):
                return self._trading_pairs_cache
            
            # Récupérer info sur les paires depuis Binance
            exchange_info = self.client.get_exchange_info()
            pairs = []
            
            for symbol_info in exchange_info['symbols']:
                if symbol_info['status'] == 'TRADING':
                    # Conversion format Binance → format standard
                    base_asset = symbol_info['baseAsset']
                    quote_asset = symbol_info['quoteAsset']
                    symbol = f"{base_asset}/{quote_asset}"
                    
                    # Filtrer les paires USDT principales
                    if quote_asset in ['USDT', 'BUSD', 'USD']:
                        min_qty = None
                        for filter in symbol_info.get('filters', []):
                            if filter['filterType'] == 'MIN_NOTIONAL':
                                min_qty = float(filter.get('minNotional', 10.0))
                                break
                        
                        pairs.append(TradingPair(
                            symbol=symbol,
                            base_asset=base_asset,
                            quote_asset=quote_asset,
                            available=True,
                            min_order_size=min_qty
                        ))
            
            self._trading_pairs_cache = pairs
            self._last_pairs_update = datetime.now()
            
            logger.info(f"Loaded {len(pairs)} trading pairs from Binance")
            return pairs
            
        except Exception as e:
            try:
                self._handle_binance_exception(e)
            except (RetryableError, RateLimitError):
                # Let the retry decorator handle these
                raise
            except Exception as converted_e:
                logger.error(f"Non-retryable error getting trading pairs: {converted_e}")
                return []
    
    @retry_on_error(max_attempts=3, base_delay=1.0)
    async def get_balance(self, asset: str) -> float:
        """Récupérer balance réelle d'un asset avec retry automatique"""
        if not self.connected or not self.client:
            logger.warning("Not connected to Binance, attempting reconnection...")
            if not await self.connect():
                return 0.0
            
        try:
            account = self.client.get_account()
            
            for balance in account['balances']:
                if balance['asset'] == asset.upper():
                    free_balance = float(balance['free'])
                    locked_balance = float(balance['locked'])
                    total_balance = free_balance + locked_balance
                    
                    logger.debug(f"Balance {asset}: {total_balance} (free: {free_balance}, locked: {locked_balance})")
                    return total_balance
            
            return 0.0
            
        except Exception as e:
            try:
                self._handle_binance_exception(e)
            except (RetryableError, RateLimitError):
                # Let the retry decorator handle these
                raise
            except Exception as converted_e:
                logger.error(f"Non-retryable error getting balance for {asset}: {converted_e}")
                return 0.0
    
    @retry_on_error(max_attempts=3, base_delay=0.5)
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Récupérer prix actuel depuis Binance avec retry automatique"""
        if not self.connected or not self.client:
            logger.warning("Not connected to Binance, attempting reconnection...")
            if not await self.connect():
                return None
            
        try:
            # Conversion format standard → format Binance
            binance_symbol = symbol.replace('/', '').replace('USD', 'USDT')
            
            ticker = self.client.get_symbol_ticker(symbol=binance_symbol)
            price = float(ticker['price'])
            
            logger.debug(f"Price for {symbol} ({binance_symbol}): ${price}")
            return price
            
        except Exception as e:
            try:
                self._handle_binance_exception(e)
            except (RetryableError, RateLimitError):
                # Let the retry decorator handle these
                raise
            except Exception as converted_e:
                logger.error(f"Non-retryable error getting price for {symbol}: {converted_e}")
                return None
    
    @retry_on_error(max_attempts=2, base_delay=1.0)
    async def place_order(self, order: Order) -> OrderResult:
        """Placer un ordre réel sur Binance avec gestion d'erreurs robuste et validation de sécurité"""
        
        # ÉTAPE 1: Validation de sécurité AVANT toute connexion
        logger.info(f"Validation de sécurité pour ordre {order.id}")
        safety_result = safety_validator.validate_order(order, {"adapter": self})
        
        if not safety_result.passed:
            error_msg = f"Ordre rejeté par validation de sécurité: {'; '.join(safety_result.errors)}"
            logger.error(error_msg)
            return OrderResult(
                success=False,
                order_id=order.id,
                error_message=error_msg,
                status=OrderStatus.FAILED
            )
        
        # Log des avertissements de sécurité
        for warning in safety_result.warnings:
            logger.warning(f"Avertissement sécurité ordre {order.id}: {warning}")
        
        logger.info(f"✓ Ordre {order.id} validé par sécurité (score: {safety_result.total_score:.1f}/100)")
        
        # ÉTAPE 2: Vérification de connexion
        if not self.connected or not self.client:
            logger.warning("Not connected to Binance for order placement, attempting reconnection...")
            if not await self.connect():
                return OrderResult(
                    success=False,
                    order_id=order.id,
                    error_message="Failed to connect to Binance for order placement",
                    status=OrderStatus.FAILED
                )
        
        try:
            from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
            
            # Préparation des paramètres
            binance_symbol = order.symbol.replace('/', '').replace('USD', 'USDT')
            side = SIDE_BUY if order.action == 'buy' else SIDE_SELL
            
            # Log de l'ordre avant placement (pour debugging)
            logger.info(f"Placing {order.action} order: {order.quantity} {order.symbol} (~${order.usd_amount})")
            
            # Déterminer la quantité
            if order.action == 'buy':
                # Pour acheter, utiliser quoteOrderQty (montant en USDT)
                quote_qty = abs(order.usd_amount)
                result = self.client.order_market_buy(
                    symbol=binance_symbol,
                    quoteOrderQty=quote_qty
                )
            else:
                # Pour vendre, utiliser quantity (quantité de l'asset)
                if order.quantity > 0:
                    quantity = order.quantity
                else:
                    # Calculer quantité à partir du montant USD
                    current_price = await self.get_current_price(order.symbol)
                    if not current_price:
                        return OrderResult(
                            success=False,
                            order_id=order.id,
                            error_message=f"Could not get current price for {order.symbol}",
                            status=OrderStatus.FAILED
                        )
                    quantity = abs(order.usd_amount) / current_price
                
                result = self.client.order_market_sell(
                    symbol=binance_symbol,
                    quantity=quantity
                )
            
            # Traitement du résultat
            if result and result['status'] == 'FILLED':
                filled_qty = float(result['executedQty'])
                cumulative_quote = float(result['cummulativeQuoteQty'])
                avg_price = cumulative_quote / filled_qty if filled_qty > 0 else 0
                
                # Calcul des frais
                total_fee = 0.0
                for fill in result.get('fills', []):
                    total_fee += float(fill['commission'])
                
                logger.info(f"Order filled: {filled_qty} @ ${avg_price:.2f} (fees: ${total_fee:.4f})")
                
                return OrderResult(
                    success=True,
                    order_id=order.id,
                    exchange_order_id=str(result['orderId']),
                    filled_quantity=filled_qty,
                    filled_usd=cumulative_quote,
                    avg_price=avg_price,
                    fees=total_fee,
                    status=OrderStatus.FILLED,
                    executed_at=datetime.now(timezone.utc),
                    exchange_data=result
                )
            else:
                error_msg = f"Order not filled. Status: {result.get('status', 'unknown')}"
                logger.warning(error_msg)
                return OrderResult(
                    success=False,
                    order_id=order.id,
                    error_message=error_msg,
                    status=OrderStatus.FAILED
                )
                
        except Exception as e:
            try:
                self._handle_binance_exception(e)
            except (RetryableError, RateLimitError):
                # Let the retry decorator handle these
                raise
            except Exception as converted_e:
                logger.error(f"Non-retryable error placing order: {converted_e}")
                return OrderResult(
                    success=False,
                    order_id=order.id,
                    error_message=str(converted_e),
                    status=OrderStatus.FAILED
                )
    
    async def cancel_order(self, exchange_order_id: str) -> bool:
        """Annuler un ordre sur Binance"""
        if not self.connected or not self.client:
            return False
            
        try:
            # TODO: Implémenter l'annulation d'ordre
            # Nécessite de stocker le symbol avec l'ordre
            logger.warning("Order cancellation not fully implemented")
            return False
        except Exception as e:
            logger.error(f"Error canceling order {exchange_order_id}: {e}")
            return False
    
    async def get_order_status(self, exchange_order_id: str) -> OrderResult:
        """Récupérer le statut d'un ordre"""
        if not self.connected or not self.client:
            return OrderResult(success=False, order_id="", error_message="Not connected")
            
        try:
            # TODO: Implémenter la récupération de statut
            # Nécessite de stocker le symbol avec l'ordre
            logger.warning("Order status check not fully implemented")
            return OrderResult(success=False, order_id="", error_message="Not implemented")
        except Exception as e:
            logger.error(f"Error getting order status {exchange_order_id}: {e}")
            return OrderResult(success=False, order_id="", error_message=str(e))

class ExchangeRegistry:
    """Registre des adaptateurs d'exchange disponibles"""
    
    def __init__(self):
        self.adapters: Dict[str, ExchangeAdapter] = {}
        self.configs: Dict[str, ExchangeConfig] = {}
        
    def register_exchange(self, config: ExchangeConfig) -> None:
        """Enregistrer un exchange"""
        self.configs[config.name] = config
        
        # Créer l'adaptateur approprié
        if config.name == "simulator":
            adapter = SimulatorAdapter(config)
        elif config.name == "binance":
            adapter = BinanceAdapter(config)
        else:
            raise ValueError(f"Unknown exchange: {config.name}")
        
        self.adapters[config.name] = adapter
        logger.info(f"Registered exchange: {config.name} ({config.type.value})")
    
    def get_adapter(self, exchange_name: str) -> Optional[ExchangeAdapter]:
        """Obtenir un adaptateur d'exchange"""
        return self.adapters.get(exchange_name)
    
    def list_exchanges(self) -> List[str]:
        """Lister les exchanges disponibles"""
        return list(self.adapters.keys())
    
    async def connect_all(self) -> Dict[str, bool]:
        """Connecter tous les exchanges"""
        results = {}
        for name, adapter in self.adapters.items():
            try:
                results[name] = await adapter.connect()
            except Exception as e:
                logger.error(f"Failed to connect to {name}: {e}")
                results[name] = False
        return results
    
    async def disconnect_all(self) -> None:
        """Déconnecter tous les exchanges"""
        for adapter in self.adapters.values():
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

# Instance globale du registre
exchange_registry = ExchangeRegistry()

def setup_default_exchanges():
    """Configuration par défaut des exchanges avec support des variables d'environnement"""
    import os
    
    # Simulateur (toujours disponible)
    simulator_config = ExchangeConfig(
        name="simulator",
        type=ExchangeType.SIMULATOR,
        fee_rate=0.001,
        min_order_size=10.0,
        sandbox=True
    )
    exchange_registry.register_exchange(simulator_config)
    
    # Binance (avec credentials depuis environnement)
    binance_api_key = os.getenv('BINANCE_API_KEY')
    binance_api_secret = os.getenv('BINANCE_API_SECRET')
    binance_sandbox = os.getenv('BINANCE_SANDBOX', 'true').lower() == 'true'
    
    binance_config = ExchangeConfig(
        name="binance",
        type=ExchangeType.CEX,
        api_key=binance_api_key,
        api_secret=binance_api_secret,
        sandbox=binance_sandbox,
        fee_rate=0.001,
        min_order_size=10.0
    )
    
    # Log de la configuration sans exposer les secrets
    if binance_api_key:
        masked_key = binance_api_key[:8] + "..." + binance_api_key[-4:] if len(binance_api_key) > 12 else "***"
        mode = "TESTNET" if binance_sandbox else "MAINNET"
        logger.info(f"Binance configured with API key {masked_key} in {mode} mode")
    else:
        logger.warning("Binance API key not found in environment - will use simulator mode")
    exchange_registry.register_exchange(binance_config)
    
    logger.info("Default exchanges configured")

# Configuration automatique au chargement du module
setup_default_exchanges()