"""
Endpoints API pour l'intégration Kraken
Expose les fonctionnalités Kraken via FastAPI
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kraken", tags=["kraken"])

@router.get("/status")
async def kraken_status():
    """Obtenir le statut de l'intégration Kraken"""
    try:
        from services.execution.exchange_adapter import exchange_registry
        from connectors.kraken_api import KrakenAPI, KrakenConfig
        
        # Vérifier si Kraken est enregistré
        kraken_adapter = exchange_registry.get_adapter("kraken")
        if not kraken_adapter:
            return {
                "available": False,
                "error": "Kraken adapter not registered"
            }
        
        # Test de connectivité basique (API publique)
        config = KrakenConfig()
        async with KrakenAPI(config) as client:
            server_time = await client.get_server_time()
            system_status = await client.get_system_status()
            
            return {
                "available": True,
                "adapter_registered": True,
                "api_accessible": True,
                "server_time": server_time,
                "system_status": system_status.get("status", "unknown"),
                "has_credentials": bool(config.api_key and config.api_secret)
            }
            
    except Exception as e:
        logger.error(f"Error checking Kraken status: {e}")
        return {
            "available": False,
            "error": str(e)
        }

@router.get("/pairs")
async def get_kraken_trading_pairs():
    """Obtenir les paires de trading Kraken disponibles"""
    try:
        from services.execution.exchange_adapter import exchange_registry
        
        kraken_adapter = exchange_registry.get_adapter("kraken")
        if not kraken_adapter:
            raise HTTPException(status_code=404, detail="Kraken adapter not found")
        
        # Tentative de connexion
        connected = await kraken_adapter.connect()
        if not connected:
            # Même sans credentials, on peut récupérer les paires publiques
            from connectors.kraken_api import KrakenAPI, KrakenConfig
            config = KrakenConfig()
            async with KrakenAPI(config) as client:
                pairs_info = await client.get_tradable_asset_pairs()
                
                pairs = []
                for pair_name, pair_info in pairs_info.items():
                    if pair_info.get('status') == 'online':
                        base_asset = client.normalize_asset(pair_info['base'])
                        quote_asset = client.normalize_asset(pair_info['quote'])
                        
                        if quote_asset in ['USD', 'EUR', 'USDT', 'USDC']:
                            pairs.append({
                                "symbol": f"{base_asset}/{quote_asset}",
                                "kraken_pair": pair_name,
                                "base_asset": base_asset,
                                "quote_asset": quote_asset,
                                "min_order_size": float(pair_info.get('ordermin', '0.0001')),
                                "price_precision": int(pair_info.get('pair_decimals', 8)),
                                "quantity_precision": int(pair_info.get('lot_decimals', 8))
                            })
                
                return {
                    "pairs": pairs,
                    "total_count": len(pairs),
                    "source": "public_api"
                }
        else:
            pairs = await kraken_adapter.get_trading_pairs()
            await kraken_adapter.disconnect()
            
            return {
                "pairs": [
                    {
                        "symbol": pair.symbol,
                        "base_asset": pair.base_asset,
                        "quote_asset": pair.quote_asset,
                        "min_order_size": pair.min_order_size,
                        "price_precision": pair.price_precision,
                        "quantity_precision": pair.quantity_precision
                    }
                    for pair in pairs
                ],
                "total_count": len(pairs),
                "source": "adapter"
            }
            
    except Exception as e:
        logger.error(f"Error getting Kraken pairs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/prices")
async def get_kraken_prices(symbols: Optional[str] = None):
    """Obtenir les prix Kraken pour des symboles spécifiques"""
    try:
        from connectors.kraken_api import KrakenAPI, KrakenConfig
        
        config = KrakenConfig()
        async with KrakenAPI(config) as client:
            if symbols:
                # Symboles spécifiques
                symbol_list = symbols.split(',')
                kraken_pairs = []
                
                for symbol in symbol_list:
                    symbol = symbol.strip().upper()
                    if '/' in symbol:
                        base, quote = symbol.split('/')
                        kraken_base = client.kraken_asset(base)
                        kraken_quote = client.kraken_asset(quote)
                        kraken_pairs.append(f"{kraken_base}{kraken_quote}")
                    else:
                        # Assumons USD par défaut
                        kraken_base = client.kraken_asset(symbol)
                        kraken_pairs.append(f"{kraken_base}USD")
                
                ticker = await client.get_ticker(kraken_pairs)
            else:
                # Prix principaux par défaut
                ticker = await client.get_ticker(['XBTUSD', 'ETHUSD', 'SOLUSD'])
            
            prices = {}
            for pair, data in ticker.items():
                if 'c' in data:  # Last price
                    last_price = float(data['c'][0])
                    prices[pair] = {
                        "price": last_price,
                        "bid": float(data.get('b', ['0'])[0]),
                        "ask": float(data.get('a', ['0'])[0]),
                        "volume": float(data.get('v', ['0'])[0])
                    }
            
            return {
                "prices": prices,
                "timestamp": await client.get_server_time()
            }
            
    except Exception as e:
        logger.error(f"Error getting Kraken prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/balance")
async def get_kraken_balance():
    """Obtenir les soldes du compte Kraken (nécessite credentials)"""
    try:
        from services.execution.exchange_adapter import exchange_registry
        
        kraken_adapter = exchange_registry.get_adapter("kraken")
        if not kraken_adapter:
            raise HTTPException(status_code=404, detail="Kraken adapter not found")
        
        connected = await kraken_adapter.connect()
        if not connected:
            raise HTTPException(
                status_code=401, 
                detail="Could not connect to Kraken - check API credentials"
            )
        
        try:
            # Obtenir les soldes via l'adaptateur
            balance_dict = await kraken_adapter.kraken_client.get_account_balance()
            
            balances = []
            for asset, amount in balance_dict.items():
                if amount > 0:
                    balances.append({
                        "asset": asset,
                        "balance": amount,
                        "balance_str": f"{amount:,.8f}"
                    })
            
            # Trier par montant décroissant
            balances.sort(key=lambda x: x['balance'], reverse=True)
            
            return {
                "balances": balances,
                "total_assets": len(balances),
                "timestamp": await kraken_adapter.kraken_client.get_server_time()
            }
            
        finally:
            await kraken_adapter.disconnect()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Kraken balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate-order")
async def validate_kraken_order(order_data: Dict[str, Any] = Body(...)):
    """Valider un ordre Kraken sans l'exécuter"""
    try:
        from connectors.kraken_api import KrakenAPI, KrakenConfig
        
        # Extraire les paramètres de l'ordre
        pair = order_data.get('pair', 'XBTUSD')
        order_type = order_data.get('type', 'buy')
        ordertype = order_data.get('ordertype', 'market')
        volume = str(order_data.get('volume', '0.001'))
        price = order_data.get('price')
        
        config = KrakenConfig()
        if not config.api_key or not config.api_secret:
            raise HTTPException(
                status_code=401,
                detail="API credentials required for order validation"
            )
        
        async with KrakenAPI(config) as client:
            # Validation d'ordre (validate=True)
            params = {
                'pair': pair,
                'type': order_type,
                'ordertype': ordertype,
                'volume': volume,
                'validate': True  # MODE VALIDATION SEULEMENT
            }
            
            if price:
                params['price'] = str(price)
            
            result = await client.add_order(**params)
            
            return {
                "valid": True,
                "validation_result": result,
                "order_params": params
            }
            
    except Exception as e:
        logger.error(f"Error validating Kraken order: {e}")
        # La validation peut échouer pour diverses raisons (solde insuffisant, etc.)
        # mais cela nous donne des informations utiles
        return {
            "valid": False,
            "error": str(e),
            "order_params": order_data
        }

@router.get("/system-info")
async def get_kraken_system_info():
    """Obtenir les informations système Kraken"""
    try:
        from connectors.kraken_api import KrakenAPI, KrakenConfig
        
        config = KrakenConfig()
        async with KrakenAPI(config) as client:
            system_status = await client.get_system_status()
            server_time = await client.get_server_time()
            
            # Obtenir quelques assets de base
            assets = await client.get_asset_info()
            major_assets = {k: v for k, v in list(assets.items())[:10]}
            
            return {
                "system_status": system_status,
                "server_time": server_time,
                "server_time_iso": f"Timestamp: {server_time}",
                "api_accessible": True,
                "major_assets": major_assets,
                "integration_version": "1.0.0",
                "features": {
                    "public_data": True,
                    "private_trading": bool(config.api_key and config.api_secret),
                    "order_validation": bool(config.api_key and config.api_secret),
                    "balance_check": bool(config.api_key and config.api_secret)
                }
            }
            
    except Exception as e:
        logger.error(f"Error getting Kraken system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-connection")
async def test_kraken_connection():
    """Test de connexion Kraken complet"""
    try:
        from services.execution.exchange_adapter import exchange_registry
        from connectors.kraken_api import KrakenAPI, KrakenConfig
        
        results = {
            "adapter_available": False,
            "api_accessible": False,
            "credentials_valid": False,
            "trading_pairs_loaded": False,
            "prices_accessible": False,
            "details": {}
        }
        
        # 1. Test adaptateur
        kraken_adapter = exchange_registry.get_adapter("kraken")
        if kraken_adapter:
            results["adapter_available"] = True
            results["details"]["adapter"] = "KrakenAdapter registered"
        else:
            results["details"]["adapter"] = "KrakenAdapter not found"
            return results
        
        # 2. Test API publique
        config = KrakenConfig()
        try:
            async with KrakenAPI(config) as client:
                server_time = await client.get_server_time()
                if server_time:
                    results["api_accessible"] = True
                    results["details"]["api"] = f"Server time: {server_time}"
                
                # Test prix
                ticker = await client.get_ticker(['XBTUSD'])
                if 'XBTUSD' in ticker:
                    btc_price = ticker['XBTUSD'].get('c', ['0'])[0]
                    results["prices_accessible"] = True
                    results["details"]["prices"] = f"BTC/USD: ${float(btc_price):,.2f}"
        except Exception as e:
            results["details"]["api_error"] = str(e)
        
        # 3. Test credentials (si disponibles)
        if config.api_key and config.api_secret:
            try:
                connected = await kraken_adapter.connect()
                if connected:
                    results["credentials_valid"] = True
                    results["details"]["credentials"] = "Valid credentials"
                    
                    # Test paires de trading
                    pairs = await kraken_adapter.get_trading_pairs()
                    if pairs:
                        results["trading_pairs_loaded"] = True
                        results["details"]["trading_pairs"] = f"{len(pairs)} pairs loaded"
                    
                    await kraken_adapter.disconnect()
                else:
                    results["details"]["credentials"] = "Connection failed"
            except Exception as e:
                results["details"]["credentials_error"] = str(e)
        else:
            results["details"]["credentials"] = "No API credentials provided"
        
        # Score global
        score = sum([
            results["adapter_available"],
            results["api_accessible"], 
            results["credentials_valid"],
            results["trading_pairs_loaded"],
            results["prices_accessible"]
        ])
        
        results["integration_score"] = f"{score}/5"
        results["ready_for_trading"] = results["credentials_valid"] and results["trading_pairs_loaded"]
        
        return results
        
    except Exception as e:
        logger.error(f"Error in Kraken connection test: {e}")
        raise HTTPException(status_code=500, detail=str(e))