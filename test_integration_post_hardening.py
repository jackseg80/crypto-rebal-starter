#!/usr/bin/env python3
"""
Test d'intégration post-durcissement
Vérifie que tous les modules critiques fonctionnent après les changements
"""
import asyncio
import httpx
import json
from pathlib import Path

async def test_api_endpoints():
    """Test des endpoints API critiques"""
    base_url = "http://127.0.0.1:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        tests = []
        
        # Test 1: Health check
        try:
            response = await client.get(f"{base_url}/healthz")
            tests.append(("Health check", response.status_code == 200))
        except Exception as e:
            tests.append(("Health check", False, str(e)))
        
        # Test 2: Balances endpoint
        try:
            response = await client.get(f"{base_url}/balances/current?source=cointracking&min_usd=1")
            tests.append(("Balances API", response.status_code == 200))
        except Exception as e:
            tests.append(("Balances API", False, str(e)))
        
        # Test 3: Pricing diagnostic
        try:
            response = await client.get(f"{base_url}/pricing/diagnostic?limit=5")
            tests.append(("Pricing diagnostic", response.status_code == 200))
        except Exception as e:
            tests.append(("Pricing diagnostic", False, str(e)))
        
        # Test 4: Rebalance plan
        try:
            payload = {
                "BTC": 0.6,
                "ETH": 0.4
            }
            response = await client.post(
                f"{base_url}/rebalance/plan?source=cointracking&min_usd=25", 
                json=payload
            )
            tests.append(("Rebalance plan", response.status_code == 200))
        except Exception as e:
            tests.append(("Rebalance plan", False, str(e)))
        
        return tests

def test_security_headers():
    """Test des headers de sécurité"""
    import requests
    
    try:
        response = requests.get("http://127.0.0.1:8000/healthz", timeout=10)
        headers = response.headers
        
        security_checks = [
            ("X-Content-Type-Options", "nosniff" in headers.get("X-Content-Type-Options", "")),
            ("X-Frame-Options", headers.get("X-Frame-Options") == "DENY"),
            ("X-XSS-Protection", "1; mode=block" in headers.get("X-XSS-Protection", "")),
            ("Content-Security-Policy", "default-src" in headers.get("Content-Security-Policy", "")),
            ("X-Process-Time", "X-Process-Time" in headers)
        ]
        
        return security_checks
    except Exception as e:
        return [("Security headers", False, str(e))]

def test_cache_performance():
    """Test des performances du cache pricing"""
    from services.pricing import get_price_usd, get_cache_stats
    import time
    
    # Test 1: Premier appel (miss)
    start = time.time()
    price1 = get_price_usd("BTC")
    time1 = time.time() - start
    
    # Test 2: Deuxième appel (hit)
    start = time.time() 
    price2 = get_price_usd("BTC")
    time2 = time.time() - start
    
    cache_stats = get_cache_stats()
    
    return [
        ("Cache miss time", time1 < 5.0, f"{time1:.3f}s"),
        ("Cache hit time", time2 < 0.1, f"{time2:.3f}s"), 
        ("Cache speedup", time1 > time2 * 2, f"{time1/time2:.1f}x faster"),
        ("Cache entries", cache_stats["valid_entries"] > 0, f"{cache_stats['valid_entries']} entries")
    ]

async def run_all_tests():
    """Exécute tous les tests d'intégration"""
    print("TESTS D'INTEGRATION POST-DURCISSEMENT")
    print("=" * 50)
    
    # Test des modules de base
    print("\nModules de base:")
    try:
        from constants import EXCHANGE_PRIORITIES, MIN_TRADE_USD
        from services.pricing import get_cache_stats
        from api.main import app
        
        print(f"OK Constants: {len(EXCHANGE_PRIORITIES)} exchanges, min_trade={MIN_TRADE_USD}")
        print(f"OK Pricing cache: TTL={get_cache_stats()['cache_ttl']}s")
        print("OK FastAPI app: initialized")
    except Exception as e:
        print(f"ERROR Module imports failed: {e}")
        return
    
    # Test des performances du cache
    print("\nPerformance du cache:")
    cache_tests = test_cache_performance()
    for test_name, passed, details in cache_tests:
        status = "OK" if passed else "FAIL"
        print(f"{status} {test_name}: {details}")
    
    # Test des headers de sécurité
    print("\nHeaders de securite:")
    print("Demarrage du serveur requis pour ces tests...")
    print("Lancez: uvicorn api.main:app --host 127.0.0.1 --port 8000")
    print("Puis executez separement les tests API")
    
    print(f"\nRESULTAT: Modules core valides OK")

if __name__ == "__main__":
    asyncio.run(run_all_tests())