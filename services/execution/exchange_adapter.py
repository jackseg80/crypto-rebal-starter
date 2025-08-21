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
from datetime import datetime, timezone

from .order_manager import Order, OrderStatus

logger = logging.getLogger(__name__)

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
    """Adaptateur pour Binance (implémentation de base)"""
    
    def __init__(self, config: ExchangeConfig):
        super().__init__(config)
        # TODO: Initialiser client Binance
        
    async def connect(self) -> bool:
        """Connexion à Binance"""
        # TODO: Implémenter connexion réelle Binance
        logger.warning("Binance adapter not fully implemented - using simulator mode")
        self.connected = True
        return True
    
    async def disconnect(self) -> None:
        self.connected = False
    
    async def get_trading_pairs(self) -> List[TradingPair]:
        # TODO: Récupérer vraies paires Binance
        return []
    
    async def get_balance(self, asset: str) -> float:
        # TODO: Vraie balance Binance  
        return 0.0
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        # TODO: Vrai prix Binance
        return None
    
    async def place_order(self, order: Order) -> OrderResult:
        # TODO: Vrai placement d'ordre Binance
        return OrderResult(
            success=False,
            order_id=order.id,
            error_message="Binance adapter not implemented"
        )
    
    async def cancel_order(self, exchange_order_id: str) -> bool:
        return False
    
    async def get_order_status(self, exchange_order_id: str) -> OrderResult:
        return OrderResult(success=False, order_id="", error_message="Not implemented")

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
    """Configuration par défaut des exchanges"""
    
    # Simulateur (toujours disponible)
    simulator_config = ExchangeConfig(
        name="simulator",
        type=ExchangeType.SIMULATOR,
        fee_rate=0.001,
        min_order_size=10.0
    )
    exchange_registry.register_exchange(simulator_config)
    
    # Binance (nécessite clés API)
    binance_config = ExchangeConfig(
        name="binance",
        type=ExchangeType.CEX,
        fee_rate=0.001,
        min_order_size=10.0,
        sandbox=True  # Mode sandbox par défaut
    )
    exchange_registry.register_exchange(binance_config)
    
    logger.info("Default exchanges configured")

# Configuration automatique au chargement du module
setup_default_exchanges()