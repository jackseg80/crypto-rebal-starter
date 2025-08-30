#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Execution Dashboard - Endpoints pour le tableau de bord d'exécution

Ce module fournit les endpoints API pour surveiller l'exécution d'ordres,
les connexions aux exchanges et les statistiques en temps réel.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, List, Any, Optional
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from services.execution.exchange_adapter import setup_default_exchanges, exchange_registry
from services.execution.order_manager import Order, OrderStatus
from services.execution.safety_validator import safety_validator
from services.analytics.execution_history import execution_history

logger = logging.getLogger(__name__)

# Router pour les endpoints dashboard
router = APIRouter(prefix="/api/execution", tags=["execution-dashboard"])

# Storage global pour l'état du dashboard (en production, utiliser Redis/DB)
dashboard_state = {
    "connections": {},
    "orders": [],
    "statistics": {
        "total_orders": 0,
        "successful_orders": 0,
        "failed_orders": 0,
        "total_volume_usd": 0.0,
        "total_fees": 0.0,
        "last_updated": None
    },
    "market_data": {},
    "safety_status": {
        "enabled": True,
        "level": "STRICT",
        "daily_volume_used": 0.0,
        "daily_volume_limit": 10000.0
    }
}

@router.get("/status")
async def get_dashboard_status():
    """Statut général du dashboard d'exécution"""
    try:
        # Initialiser si nécessaire
        if not exchange_registry.adapters:
            setup_default_exchanges()
        
        # Statut des connexions
        connections = {}
        for name, adapter in exchange_registry.adapters.items():
            connections[name] = {
                "name": name,
                "type": adapter.config.type.value,
                "connected": adapter.connected,
                "sandbox": getattr(adapter.config, 'sandbox', False),
                "last_check": datetime.now(timezone.utc).isoformat()
            }
        
        dashboard_state["connections"] = connections
        dashboard_state["statistics"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        return JSONResponse({
            "status": "active",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "connections": connections,
            "statistics": dashboard_state["statistics"],
            "safety_status": dashboard_state["safety_status"]
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/connections")
async def get_connections_status():
    """État détaillé des connexions aux exchanges"""
    try:
        if not exchange_registry.adapters:
            setup_default_exchanges()
        
        detailed_connections = {}
        
        for name, adapter in exchange_registry.adapters.items():
            try:
                # Test de connexion
                connection_healthy = adapter.connected
                
                # Obtenir informations supplémentaires
                additional_info = {}
                
                if connection_healthy:
                    try:
                        # Test prix pour vérifier la connectivité
                        if name != "simulator":
                            price = await adapter.get_current_price("BTC/USDT")
                            additional_info["btc_price"] = price
                        
                        # Balance test
                        balance = await adapter.get_balance("USDT")
                        additional_info["usdt_balance"] = balance
                        
                        # Paires de trading
                        pairs = await adapter.get_trading_pairs()
                        additional_info["trading_pairs"] = len(pairs)
                        
                    except Exception as test_error:
                        additional_info["test_error"] = str(test_error)
                
                detailed_connections[name] = {
                    "name": name,
                    "type": adapter.config.type.value,
                    "connected": connection_healthy,
                    "sandbox": getattr(adapter.config, 'sandbox', False),
                    "config": {
                        "fee_rate": adapter.config.fee_rate,
                        "min_order_size": adapter.config.min_order_size,
                        "has_credentials": bool(getattr(adapter.config, 'api_key', None))
                    },
                    "additional_info": additional_info,
                    "last_check": datetime.now(timezone.utc).isoformat()
                }
                
            except Exception as adapter_error:
                detailed_connections[name] = {
                    "name": name,
                    "connected": False,
                    "error": str(adapter_error),
                    "last_check": datetime.now(timezone.utc).isoformat()
                }
        
        return JSONResponse(detailed_connections)
        
    except Exception as e:
        logger.error(f"Error getting connections status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-connection/{exchange_name}")
async def test_exchange_connection(exchange_name: str):
    """Tester la connexion à un exchange spécifique"""
    try:
        if not exchange_registry.adapters:
            setup_default_exchanges()
        
        adapter = exchange_registry.get_adapter(exchange_name)
        if not adapter:
            raise HTTPException(status_code=404, detail=f"Exchange {exchange_name} not found")
        
        # Test de reconnexion
        if adapter.connected:
            await adapter.disconnect()
        
        connection_result = await adapter.connect()
        
        test_results = {
            "exchange": exchange_name,
            "connection_successful": connection_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if connection_result:
            # Tests additionnels
            try:
                price = await adapter.get_current_price("BTC/USDT")
                balance = await adapter.get_balance("USDT")
                
                test_results.update({
                    "btc_price": price,
                    "usdt_balance": balance,
                    "api_functional": True
                })
            except Exception as api_error:
                test_results.update({
                    "api_functional": False,
                    "api_error": str(api_error)
                })
        
        return JSONResponse(test_results)
        
    except Exception as e:
        logger.error(f"Error testing connection to {exchange_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders/recent")
async def get_recent_orders(limit: int = 50):
    """Obtenir les ordres récents avec détails"""
    try:
        # Filtrer les ordres récents (dernières 24h)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_orders = [
            order for order in dashboard_state["orders"]
            if datetime.fromisoformat(order.get("timestamp", "1970-01-01")).replace(tzinfo=timezone.utc) > cutoff_time
        ]
        
        # Trier par timestamp descendant et limiter
        recent_orders.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        limited_orders = recent_orders[:limit]
        
        return JSONResponse({
            "orders": limited_orders,
            "total_count": len(recent_orders),
            "limit": limit,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting recent orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/orders/execute")
async def execute_orders(orders_data: Dict[str, Any], background_tasks: BackgroundTasks):
    """Exécuter des ordres avec monitoring en temps réel"""
    try:
        if not exchange_registry.adapters:
            setup_default_exchanges()
        
        orders_list = orders_data.get("orders", [])
        exchange_name = orders_data.get("exchange", "enhanced_simulator")
        
        if not orders_list:
            raise HTTPException(status_code=400, detail="No orders provided")
        
        # Obtenir l'adaptateur
        adapter = exchange_registry.get_adapter(exchange_name)
        if not adapter:
            raise HTTPException(status_code=404, detail=f"Exchange {exchange_name} not found")
        
        # Créer les objets Order
        orders = []
        for order_data in orders_list:
            order = Order(
                symbol=order_data.get("symbol", ""),
                action=order_data.get("action", ""),
                quantity=float(order_data.get("quantity", 0)),
                usd_amount=float(order_data.get("usd_amount", 0)),
                alias=order_data.get("alias", ""),
                group=order_data.get("group", "")
            )
            orders.append(order)
        
        # Lancer l'exécution en arrière-plan
        background_tasks.add_task(execute_orders_background, orders, adapter)
        
        return JSONResponse({
            "message": f"Execution started for {len(orders)} orders",
            "exchange": exchange_name,
            "orders_count": len(orders),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "estimated_completion": (datetime.now(timezone.utc) + timedelta(seconds=len(orders) * 2)).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error executing orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def execute_orders_background(orders: List[Order], adapter):
    """Exécution d'ordres en arrière-plan avec mise à jour du dashboard"""
    try:
        # Connexion si nécessaire
        if not adapter.connected:
            await adapter.connect()
        
        execution_results = []
        
        for order in orders:
            try:
                # Validation de sécurité
                safety_result = safety_validator.validate_order(order, {"adapter": adapter})
                
                order_record = {
                    "id": order.id,
                    "symbol": order.symbol,
                    "action": order.action,
                    "quantity": order.quantity,
                    "usd_amount": order.usd_amount,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "exchange": adapter.config.name,
                    "safety_validated": safety_result.passed,
                    "safety_score": safety_result.total_score
                }
                
                if safety_result.passed:
                    # Exécuter l'ordre
                    result = await adapter.place_order(order)
                    
                    order_record.update({
                        "status": "success" if result.success else "failed",
                        "filled_quantity": result.filled_quantity if result.success else 0,
                        "filled_usd": result.filled_usd if result.success else 0,
                        "avg_price": result.avg_price if result.success else 0,
                        "fees": result.fees if result.success else 0,
                        "error_message": result.error_message if not result.success else None,
                        "exchange_data": result.exchange_data if result.success else None
                    })
                    
                    # Mettre à jour les statistiques
                    if result.success:
                        dashboard_state["statistics"]["successful_orders"] += 1
                        dashboard_state["statistics"]["total_volume_usd"] += result.filled_usd
                        dashboard_state["statistics"]["total_fees"] += result.fees
                    else:
                        dashboard_state["statistics"]["failed_orders"] += 1
                
                else:
                    order_record.update({
                        "status": "rejected",
                        "error_message": f"Safety validation failed: {'; '.join(safety_result.errors)}",
                        "safety_errors": safety_result.errors
                    })
                    dashboard_state["statistics"]["failed_orders"] += 1
                
                # Ajouter à l'historique
                dashboard_state["orders"].append(order_record)
                dashboard_state["statistics"]["total_orders"] += 1
                
                execution_results.append(order_record)
                
                # Petite pause entre les ordres
                await asyncio.sleep(0.5)
                
            except Exception as order_error:
                logger.error(f"Error executing order {order.id}: {order_error}")
                
                error_record = {
                    "id": order.id,
                    "symbol": order.symbol,
                    "action": order.action,
                    "status": "error",
                    "error_message": str(order_error),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                dashboard_state["orders"].append(error_record)
                dashboard_state["statistics"]["failed_orders"] += 1
                dashboard_state["statistics"]["total_orders"] += 1
        
        # Mise à jour finale
        dashboard_state["statistics"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        # Enregistrer la session d'exécution dans l'historique
        try:
            session_metadata = {
                "total_orders_requested": len(orders),
                "execution_type": "dashboard",
                "timestamp_started": execution_results[0].get("timestamp") if execution_results else datetime.now(timezone.utc).isoformat()
            }
            
            await execution_history.record_execution_session(
                orders=execution_results,
                exchange=adapter.config.name,
                metadata=session_metadata
            )
            
            logger.info(f"Execution session recorded in history")
            
        except Exception as history_error:
            logger.error(f"Error recording execution session in history: {history_error}")
        
        logger.info(f"Background execution completed: {len(execution_results)} orders processed")
        
    except Exception as e:
        logger.error(f"Error in background order execution: {e}")

@router.get("/statistics/summary")
async def get_statistics_summary():
    """Résumé des statistiques d'exécution"""
    try:
        # Calculer des métriques additionnelles
        recent_orders = [
            order for order in dashboard_state["orders"]
            if datetime.fromisoformat(order.get("timestamp", "1970-01-01")).replace(tzinfo=timezone.utc) > 
               datetime.now(timezone.utc) - timedelta(hours=24)
        ]
        
        successful_recent = [o for o in recent_orders if o.get("status") == "success"]
        
        summary = {
            **dashboard_state["statistics"],
            "recent_24h": {
                "total_orders": len(recent_orders),
                "successful_orders": len(successful_recent),
                "success_rate": (len(successful_recent) / len(recent_orders) * 100) if recent_orders else 0,
                "total_volume": sum(o.get("filled_usd", 0) for o in successful_recent),
                "total_fees": sum(o.get("fees", 0) for o in successful_recent)
            },
            "safety_stats": {
                "daily_volume_used": safety_validator.daily_volume_used,
                "daily_volume_limit": safety_validator.max_daily_volume,
                "volume_utilization": (safety_validator.daily_volume_used / safety_validator.max_daily_volume * 100)
            }
        }
        
        return JSONResponse(summary)
        
    except Exception as e:
        logger.error(f"Error getting statistics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/market-data")
async def get_market_data():
    """Données de marché pour les symboles surveillés"""
    try:
        if not exchange_registry.adapters:
            setup_default_exchanges()
        
        # Utiliser le simulateur avancé pour les prix
        enhanced_sim = exchange_registry.get_adapter("enhanced_simulator")
        if not enhanced_sim:
            raise HTTPException(status_code=503, detail="Enhanced simulator not available")
        
        symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "ADA/USDT", "DOT/USDT"]
        market_data = {}
        
        if not enhanced_sim.connected:
            await enhanced_sim.connect()
        
        for symbol in symbols:
            try:
                price = await enhanced_sim.get_current_price(symbol)
                market_data[symbol] = {
                    "price": price,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "enhanced_simulator"
                }
            except Exception as symbol_error:
                logger.warning(f"Error getting price for {symbol}: {symbol_error}")
                market_data[symbol] = {
                    "price": None,
                    "error": str(symbol_error),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
        
        return JSONResponse({
            "market_data": market_data,
            "last_updated": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        raise HTTPException(status_code=500, detail=str(e))