#!/usr/bin/env python3
"""
Test d'intégration Binance - Version simple
"""

import asyncio
import logging
from services.execution.exchange_adapter import setup_default_exchanges, exchange_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_integration():
    """Test de l'intégration Binance"""
    
    print("Test d'integration Binance")
    print("=" * 40)
    
    # 1. Setup des exchanges par défaut
    print("1. Configuration des exchanges...")
    setup_default_exchanges()
    
    # 2. Lister les exchanges disponibles
    print("\n2. Exchanges configurés:")
    exchanges = exchange_registry.list_exchanges()
    for name in exchanges:
        config = exchange_registry.configs.get(name)
        if config:
            has_credentials = "[OK]" if config.api_key else "[NO]"
            mode = f"({config.type.value}, sandbox={config.sandbox})" if hasattr(config, 'sandbox') else f"({config.type.value})"
            print(f"   • {name}: {has_credentials} {mode}")
    
    # 3. Test de connexion aux exchanges
    print("\n3. Test de connexion...")
    
    for name in exchanges:
        try:
            adapter = exchange_registry.get_adapter(name)
            if adapter:
                print(f"   >> Test connexion {name}...")
                connected = await adapter.connect()
                
                if connected:
                    print(f"   [OK] {name}: Connecte")
                    
                    # Test simple d'une fonction
                    if hasattr(adapter, 'get_current_price'):
                        try:
                            price = await adapter.get_current_price('BTC')
                            if price:
                                print(f"      >> Prix BTC: ${price:,.2f}")
                        except Exception as e:
                            print(f"      [WARN] Prix BTC: {e}")
                    
                    await adapter.disconnect()
                else:
                    print(f"   [ERROR] {name}: Echec de connexion")
                    
        except Exception as e:
            print(f"   [ERROR] {name}: Erreur - {e}")
    
    print("\n[DONE] Test termine")

if __name__ == "__main__":
    asyncio.run(test_integration())