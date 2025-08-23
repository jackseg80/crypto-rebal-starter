#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Simulator - Simulation avancée d'exécution d'ordres

Ce module fournit une simulation d'ordre réaliste avec prix de marché en temps réel,
slippage, frais variables, latence de réseau et conditions de marché simulées.
"""

import asyncio
import logging
import time
import random
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

# aiohttp will be imported when needed

from .exchange_adapter import ExchangeAdapter, OrderResult, TradingPair
from .order_manager import Order, OrderStatus

logger = logging.getLogger(__name__)

@dataclass
class MarketCondition:
    """Conditions de marché pour la simulation"""
    volatility: float  # Volatilité actuelle (0.0-1.0)
    liquidity: float   # Liquidité du marché (0.0-1.0)  
    trend: str        # "bull", "bear", "sideways"
    volume_multiplier: float  # Multiplicateur de volume
    active_hours: bool  # Heures de marché actives

@dataclass
class SimulationReport:
    """Rapport détaillé d'une simulation"""
    order_id: str
    symbol: str
    action: str
    requested_quantity: float
    requested_usd: float
    
    # Exécution
    filled_quantity: float
    filled_usd: float
    avg_price: float
    execution_price: float
    market_price: float
    
    # Coûts et slippage
    fees: float
    slippage_bps: float
    slippage_usd: float
    
    # Timing
    latency_ms: int
    execution_time: datetime
    
    # Conditions marché
    market_conditions: MarketCondition
    
    # Statut
    success: bool
    error_message: Optional[str] = None

class EnhancedSimulator(ExchangeAdapter):
    """Simulateur avancé avec conditions de marché réalistes"""
    
    def __init__(self, config):
        super().__init__(config)
        self.market_data_cache = {}
        self.last_price_update = None
        self.simulation_reports = []
        self.total_fees_collected = 0.0
        self.total_slippage_cost = 0.0
        
        # Configuration de simulation
        self.base_latency_ms = 50  # Latence de base
        self.slippage_base_bps = 5  # Slippage de base en basis points
        self.market_hours_active = True  # Crypto 24/7 par défaut
        
    async def connect(self) -> bool:
        """Simulation de connexion"""
        # Simuler latence de connexion
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        self.connected = True
        logger.info("Connected to Enhanced Simulator")
        
        # Charger les données de marché initiales
        await self._update_market_data()
        return True
    
    async def disconnect(self) -> None:
        """Simulation de déconnexion"""
        self.connected = False
        logger.info("Disconnected from Enhanced Simulator")
    
    async def _update_market_data(self) -> None:
        """Mettre à jour les données de marché réelles"""
        if (self.last_price_update and 
            datetime.now() - self.last_price_update < timedelta(minutes=1)):
            return  # Cache valide
        
        try:
            # Essayer d'obtenir des prix réels via CoinGecko
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {
                    'ids': 'bitcoin,ethereum,binancecoin,cardano,polkadot',
                    'vs_currencies': 'usd',
                    'include_24hr_change': 'true',
                    'include_24hr_vol': 'true'
                }
                
                async with session.get(url, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Mapper les données
                        self.market_data_cache = {
                            'BTC': {
                                'price': data.get('bitcoin', {}).get('usd', 45000),
                                'change_24h': data.get('bitcoin', {}).get('usd_24h_change', 0),
                                'volume_24h': data.get('bitcoin', {}).get('usd_24h_vol', 1000000000)
                            },
                            'ETH': {
                                'price': data.get('ethereum', {}).get('usd', 2800), 
                                'change_24h': data.get('ethereum', {}).get('usd_24h_change', 0),
                                'volume_24h': data.get('ethereum', {}).get('usd_24h_vol', 500000000)
                            },
                            'BNB': {
                                'price': data.get('binancecoin', {}).get('usd', 300),
                                'change_24h': data.get('binancecoin', {}).get('usd_24h_change', 0), 
                                'volume_24h': data.get('binancecoin', {}).get('usd_24h_vol', 100000000)
                            },
                            'ADA': {
                                'price': data.get('cardano', {}).get('usd', 0.5),
                                'change_24h': data.get('cardano', {}).get('usd_24h_change', 0),
                                'volume_24h': data.get('cardano', {}).get('usd_24h_vol', 50000000)
                            },
                            'DOT': {
                                'price': data.get('polkadot', {}).get('usd', 6.0),
                                'change_24h': data.get('polkadot', {}).get('usd_24h_change', 0),
                                'volume_24h': data.get('polkadot', {}).get('usd_24h_vol', 30000000)
                            }
                        }
                        
                        self.last_price_update = datetime.now()
                        logger.info("Updated market data from CoinGecko")
                    else:
                        logger.warning(f"CoinGecko API returned {response.status}")
                        
        except Exception as e:
            logger.warning(f"Failed to fetch real market data: {e}")
            # Utiliser des prix par défaut
            if not self.market_data_cache:
                self._set_default_prices()
    
    def _set_default_prices(self):
        """Prix par défaut si l'API échoue"""
        self.market_data_cache = {
            'BTC': {'price': 45000, 'change_24h': 2.5, 'volume_24h': 1000000000},
            'ETH': {'price': 2800, 'change_24h': 1.8, 'volume_24h': 500000000},
            'BNB': {'price': 300, 'change_24h': 0.5, 'volume_24h': 100000000},
            'ADA': {'price': 0.5, 'change_24h': -0.8, 'volume_24h': 50000000},
            'DOT': {'price': 6.0, 'change_24h': 1.2, 'volume_24h': 30000000}
        }
        logger.info("Using default market prices")
    
    async def _get_market_conditions(self, symbol: str) -> MarketCondition:
        """Déterminer les conditions de marché"""
        await self._update_market_data()
        
        base_symbol = symbol.split('/')[0] if '/' in symbol else symbol.replace('USDT', '')
        market_data = self.market_data_cache.get(base_symbol, {})
        
        change_24h = market_data.get('change_24h', 0)
        volume_24h = market_data.get('volume_24h', 100000000)
        
        # Volatilité basée sur le changement 24h
        volatility = min(abs(change_24h) / 10.0, 1.0)  # 10% change = volatility 1.0
        
        # Liquidité basée sur le volume
        liquidity = min(volume_24h / 1000000000, 1.0)  # 1B volume = liquidité 1.0
        
        # Tendance basée sur le changement 24h
        if change_24h > 3:
            trend = "bull"
        elif change_24h < -3:
            trend = "bear"
        else:
            trend = "sideways"
            
        # Volume multiplier basé sur la volatilité
        volume_multiplier = 1.0 + (volatility * 0.5)
        
        return MarketCondition(
            volatility=volatility,
            liquidity=liquidity,
            trend=trend,
            volume_multiplier=volume_multiplier,
            active_hours=self.market_hours_active
        )
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Prix de marché en temps réel avec micro-fluctuations"""
        base_symbol = symbol.split('/')[0] if '/' in symbol else symbol.replace('USDT', '')
        
        await self._update_market_data()
        
        market_data = self.market_data_cache.get(base_symbol)
        if not market_data:
            return None
            
        base_price = market_data['price']
        
        # Ajouter des micro-fluctuations réalistes (±0.1%)
        micro_change = random.uniform(-0.001, 0.001)
        current_price = base_price * (1 + micro_change)
        
        return current_price
    
    def _calculate_slippage(self, order: Order, market_conditions: MarketCondition) -> Tuple[float, float]:
        """Calculer le slippage réaliste"""
        # Slippage de base
        base_slippage_bps = self.slippage_base_bps
        
        # Ajustements basés sur les conditions de marché
        volatility_multiplier = 1 + (market_conditions.volatility * 2)
        liquidity_multiplier = 2 - market_conditions.liquidity  # Moins de liquidité = plus de slippage
        size_multiplier = 1 + (order.usd_amount / 100000)  # Plus gros ordres = plus de slippage
        
        # Différentiel buy/sell
        direction_multiplier = 1.2 if order.action == "buy" else 0.8
        
        # Heures de marché (crypto 24/7 mais weekends plus volatils)  
        import datetime
        now = datetime.datetime.now()
        weekend_multiplier = 1.3 if now.weekday() >= 5 else 1.0
        
        total_slippage_bps = (base_slippage_bps * 
                             volatility_multiplier * 
                             liquidity_multiplier * 
                             size_multiplier * 
                             direction_multiplier * 
                             weekend_multiplier)
        
        # Limiter le slippage à des valeurs réalistes (max 100 bps = 1%)
        total_slippage_bps = min(total_slippage_bps, 100)
        
        slippage_factor = total_slippage_bps / 10000  # Convertir bps en facteur
        return total_slippage_bps, slippage_factor
    
    def _calculate_fees(self, order: Order, market_conditions: MarketCondition) -> float:
        """Calculer les frais variables selon les conditions"""
        base_fee_rate = self.config.fee_rate
        
        # Frais réduits pendant les heures calmes
        if market_conditions.volatility < 0.2:
            fee_multiplier = 0.8
        else:
            fee_multiplier = 1.0
            
        # Frais majorés pour les gros ordres
        if order.usd_amount > 50000:
            fee_multiplier *= 1.2
        
        return base_fee_rate * fee_multiplier
    
    async def _simulate_network_latency(self, market_conditions: MarketCondition) -> int:
        """Simuler la latence réseau variable"""
        base_latency = self.base_latency_ms
        
        # Latence augmentée pendant haute volatilité (congestion réseau)
        volatility_latency = base_latency * (1 + market_conditions.volatility)
        
        # Ajouter jitter aléatoire
        jitter = random.uniform(0.5, 1.5)
        
        total_latency = int(volatility_latency * jitter)
        
        # Simuler latence réelle
        await asyncio.sleep(total_latency / 1000.0)
        
        return total_latency
    
    async def place_order(self, order: Order) -> OrderResult:
        """Simulation d'ordre avancée avec conditions de marché réelles"""
        start_time = time.time()
        
        # Obtenir les conditions de marché
        market_conditions = await self._get_market_conditions(order.symbol)
        
        # Simuler latence réseau
        latency_ms = await self._simulate_network_latency(market_conditions)
        
        # Prix de marché actuel
        market_price = await self.get_current_price(order.symbol)
        if not market_price:
            return OrderResult(
                success=False,
                order_id=order.id,
                error_message=f"No market data available for {order.symbol}",
                status=OrderStatus.FAILED
            )
        
        # Calculer slippage et prix d'exécution
        slippage_bps, slippage_factor = self._calculate_slippage(order, market_conditions)
        
        if order.action == "buy":
            execution_price = market_price * (1 + slippage_factor)  # Prix plus élevé pour achats
        else:
            execution_price = market_price * (1 - slippage_factor)  # Prix plus bas pour ventes
        
        # Calculer quantités
        if order.action == "buy":
            filled_quantity = abs(order.usd_amount) / execution_price
        else:
            filled_quantity = abs(order.quantity) if order.quantity != 0 else abs(order.usd_amount) / execution_price
        
        filled_usd = filled_quantity * execution_price
        
        # Calculer frais
        fee_rate = self._calculate_fees(order, market_conditions)
        fees = filled_usd * fee_rate
        
        # Calculer coût de slippage
        slippage_usd = abs(filled_usd - (filled_quantity * market_price))
        
        # Simulation d'échec basée sur les conditions de marché
        failure_rate = 0.02 + (market_conditions.volatility * 0.03)  # 2-5% d'échec
        success = random.random() > failure_rate
        
        if success:
            status = OrderStatus.FILLED
            error_message = None
            
            # Mise à jour des totaux
            self.total_fees_collected += fees
            self.total_slippage_cost += slippage_usd
            
        else:
            status = OrderStatus.FAILED
            error_message = f"Order failed due to market conditions (volatility: {market_conditions.volatility:.2f})"
            filled_quantity = 0.0
            filled_usd = 0.0
            fees = 0.0
            slippage_usd = 0.0
        
        # Créer rapport de simulation
        report = SimulationReport(
            order_id=order.id,
            symbol=order.symbol,
            action=order.action,
            requested_quantity=order.quantity,
            requested_usd=order.usd_amount,
            filled_quantity=filled_quantity,
            filled_usd=filled_usd,
            avg_price=execution_price,
            execution_price=execution_price,
            market_price=market_price,
            fees=fees,
            slippage_bps=slippage_bps,
            slippage_usd=slippage_usd,
            latency_ms=latency_ms,
            execution_time=datetime.now(timezone.utc),
            market_conditions=market_conditions,
            success=success,
            error_message=error_message
        )
        
        self.simulation_reports.append(report)
        
        # Créer résultat d'ordre
        result = OrderResult(
            success=success,
            order_id=order.id,
            exchange_order_id=f"sim_{int(time.time() * 1000)}",
            filled_quantity=filled_quantity,
            filled_usd=filled_usd,
            avg_price=execution_price,
            fees=fees,
            status=status,
            error_message=error_message,
            executed_at=datetime.now(timezone.utc),
            exchange_data={
                "simulated": True,
                "market_price": market_price,
                "slippage_bps": slippage_bps,
                "slippage_usd": slippage_usd,
                "latency_ms": latency_ms,
                "market_conditions": asdict(market_conditions)
            }
        )
        
        if success:
            logger.info(f"✓ Simulated {order.action}: {filled_quantity:.6f} {order.symbol.split('/')[0]} @ ${execution_price:.2f} "
                       f"(slippage: {slippage_bps:.1f}bps, fees: ${fees:.4f})")
        else:
            logger.warning(f"✗ Simulation failed: {error_message}")
        
        return result
    
    async def get_balance(self, asset: str) -> float:
        """Simulation de balance avec historique"""
        # Balances par défaut généreuses pour les tests
        default_balances = {
            'BTC': 1.0,
            'ETH': 10.0,
            'BNB': 100.0,
            'ADA': 1000.0,
            'DOT': 100.0,
            'USDT': 50000.0,
            'USD': 50000.0
        }
        
        balance = default_balances.get(asset.upper(), 0.0)
        
        # Ajouter petite variation aléatoire
        variation = random.uniform(0.95, 1.05)
        return balance * variation
    
    async def get_trading_pairs(self) -> List[TradingPair]:
        """Paires de trading supportées par le simulateur"""
        pairs = []
        symbols = ['BTC', 'ETH', 'BNB', 'ADA', 'DOT']
        
        for symbol in symbols:
            pairs.append(TradingPair(
                symbol=f"{symbol}/USDT",
                base_asset=symbol,
                quote_asset="USDT",
                available=True,
                min_order_size=10.0
            ))
        
        return pairs
    
    def get_simulation_summary(self) -> Dict[str, Any]:
        """Résumé complet de toutes les simulations"""
        if not self.simulation_reports:
            return {"message": "No simulations executed yet"}
        
        successful_orders = [r for r in self.simulation_reports if r.success]
        failed_orders = [r for r in self.simulation_reports if not r.success]
        
        total_volume = sum(r.filled_usd for r in successful_orders)
        avg_slippage = sum(r.slippage_bps for r in successful_orders) / len(successful_orders) if successful_orders else 0
        avg_latency = sum(r.latency_ms for r in self.simulation_reports) / len(self.simulation_reports)
        
        return {
            "total_orders": len(self.simulation_reports),
            "successful_orders": len(successful_orders),
            "failed_orders": len(failed_orders),
            "success_rate": len(successful_orders) / len(self.simulation_reports) * 100,
            "total_volume_usd": total_volume,
            "total_fees_paid": self.total_fees_collected,
            "total_slippage_cost": self.total_slippage_cost,
            "average_slippage_bps": avg_slippage,
            "average_latency_ms": avg_latency,
            "orders_by_symbol": {
                symbol: len([r for r in self.simulation_reports if r.symbol.startswith(symbol)])
                for symbol in ['BTC', 'ETH', 'BNB', 'ADA', 'DOT']
            }
        }
    
    async def cancel_order(self, exchange_order_id: str) -> bool:
        """Simulation d'annulation avec latence"""
        await asyncio.sleep(random.uniform(0.05, 0.2))
        # 95% de succès d'annulation
        success = random.random() < 0.95
        logger.info(f"Simulated cancel order {exchange_order_id}: {'success' if success else 'failed'}")
        return success
    
    async def get_order_status(self, exchange_order_id: str) -> OrderResult:
        """Statut d'ordre avec délai réaliste"""
        await asyncio.sleep(random.uniform(0.05, 0.15))
        
        return OrderResult(
            success=True,
            order_id=exchange_order_id,
            status=OrderStatus.FILLED,
            exchange_order_id=exchange_order_id
        )