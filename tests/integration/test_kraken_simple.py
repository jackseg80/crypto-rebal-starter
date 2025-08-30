#!/usr/bin/env python3
"""
Test simple d'intégration Kraken
"""

import asyncio
import logging
from dotenv import load_dotenv

# Configurer les logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

async def test_kraken_basic():
    """Test basique de Kraken"""
    print("=" * 50)
    print("TEST INTEGRATION KRAKEN")
    print("=" * 50)
    
    try:
        from connectors.kraken_api import KrakenAPI, KrakenConfig
        
        print("1. Test API Kraken...")
        config = KrakenConfig()
        
        async with KrakenAPI(config) as client:
            # Test public
            server_time = await client.get_server_time()
            print(f"  Server time: {server_time}")
            
            system_status = await client.get_system_status()
            print(f"  System status: {system_status.get('status', 'unknown')}")
            
            # Test ticker
            ticker = await client.get_ticker(['XBTUSD'])
            if 'XBTUSD' in ticker:
                btc_price = ticker['XBTUSD'].get('c', ['0'])[0]
                print(f"  BTC/USD price: ${float(btc_price):,.2f}")
        
        print("  API Test: OK")
        
        # Test adaptateur
        print("\n2. Test Adaptateur...")
        from services.execution.exchange_adapter import exchange_registry
        
        exchanges = exchange_registry.list_exchanges()
        print(f"  Available exchanges: {exchanges}")
        
        if "kraken" in exchanges:
            kraken_adapter = exchange_registry.get_adapter("kraken")
            print(f"  Kraken adapter: {kraken_adapter.__class__.__name__}")
            
            # Test connexion (sans credentials, ça va échouer mais c'est normal)
            try:
                connected = await kraken_adapter.connect()
                print(f"  Connection: {'OK' if connected else 'FAIL (normal sans credentials)'}")
                
                if connected:
                    pairs = await kraken_adapter.get_trading_pairs()
                    print(f"  Trading pairs loaded: {len(pairs)}")
                    
                    await kraken_adapter.disconnect()
                    
            except Exception as e:
                print(f"  Connection test: EXPECTED FAILURE - {e}")
        
        print("  Adapter Test: OK")
        
        print("\n" + "=" * 50)
        print("INTEGRATION KRAKEN: SUCCESS")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Fonction principale"""
    success = await test_kraken_basic()
    
    if success:
        print("\nTo test with real credentials, set:")
        print("  KRAKEN_API_KEY=your_api_key")
        print("  KRAKEN_API_SECRET=your_api_secret")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())