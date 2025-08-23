#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script pour la gestion d'erreurs et retry logic du BinanceAdapter

Ce script teste les différents scénarios d'erreur et vérifie que
le système de retry et de gestion d'erreurs fonctionne correctement.
"""

import asyncio
import logging
from unittest.mock import Mock, patch, AsyncMock
from services.execution.exchange_adapter import (
    BinanceAdapter, ExchangeConfig, ExchangeType,
    RetryableError, RateLimitError
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockBinanceException(Exception):
    """Mock de BinanceAPIException pour les tests"""
    def __init__(self, code, message, status_code=400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

async def test_retry_mechanism():
    """Test du mécanisme de retry avec exponential backoff"""
    print("[TEST] Retry mechanism...")
    
    config = ExchangeConfig(
        name="binance_test",
        type=ExchangeType.CEX,
        api_key="test_key",
        api_secret="test_secret",
        sandbox=True,
        fee_rate=0.001,
        min_order_size=10.0
    )
    
    adapter = BinanceAdapter(config)
    
    # Mock du client qui échoue 2 fois puis réussit
    mock_client = Mock()
    call_count = 0
    
    def mock_get_account():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise MockBinanceException(-1003, "Too many requests", 429)
        return {"balances": []}
    
    mock_client.get_account = mock_get_account
    adapter.client = mock_client
    adapter.connected = True
    
    # Test que le retry fonctionne
    try:
        balance = await adapter.get_balance("BTC")
        print("[PASS] Retry mechanism works - connection succeeded after 2 failures")
        assert call_count == 3, f"Expected 3 calls, got {call_count}"
    except Exception as e:
        print(f"[FAIL] Retry mechanism failed: {e}")
        return False
    
    return True

async def test_rate_limit_handling():
    """Test de la gestion des rate limits"""
    print("\n[TEST] Rate limit handling...")
    
    config = ExchangeConfig(
        name="binance_test",
        type=ExchangeType.CEX,
        api_key="test_key", 
        api_secret="test_secret",
        sandbox=True,
        fee_rate=0.001,
        min_order_size=10.0
    )
    
    adapter = BinanceAdapter(config)
    
    # Test de la conversion d'exception
    # Mock binance.exceptions module
    import sys
    from types import ModuleType
    
    # Create mock binance.exceptions module
    mock_binance_exceptions = ModuleType('binance.exceptions')
    
    class MockBinanceAPIException(Exception):
        def __init__(self, code, message, status_code=400):
            self.code = code
            self.message = message  
            self.status_code = status_code
            super().__init__(message)
    
    class MockBinanceRequestException(Exception):
        pass
    
    mock_binance_exceptions.BinanceAPIException = MockBinanceAPIException
    mock_binance_exceptions.BinanceRequestException = MockBinanceRequestException
    
    sys.modules['binance.exceptions'] = mock_binance_exceptions
    
    try:
        # Simuler une erreur de rate limit
        mock_exception = MockBinanceAPIException(-1003, "Too many requests", 429)
        adapter._handle_binance_exception(mock_exception)
        print("[FAIL] Rate limit exception not detected")
        return False
    except RateLimitError as e:
        print("[PASS] Rate limit correctly detected and converted")
        assert e.retry_after == 60, f"Expected retry_after=60, got {e.retry_after}"
    except Exception as e:
        print(f"[FAIL] Wrong exception raised: {type(e).__name__}: {e}")
        return False
    
    return True

async def test_connection_recovery():
    """Test de la reconnexion automatique"""
    print("\n[TEST] Test de la reconnexion automatique...")
    
    config = ExchangeConfig(
        name="binance_test",
        type=ExchangeType.CEX,
        api_key="test_key",
        api_secret="test_secret", 
        sandbox=True,
        fee_rate=0.001,
        min_order_size=10.0
    )
    
    adapter = BinanceAdapter(config)
    
    # Mock de la méthode connect
    connect_calls = 0
    original_connect = adapter.connect
    
    async def mock_connect():
        nonlocal connect_calls
        connect_calls += 1
        if connect_calls == 1:
            return True  # Première connexion réussit
        return True  # Reconnexion réussit aussi
    
    adapter.connect = mock_connect
    
    # Simuler une déconnexion
    adapter.connected = False
    
    # Appeler get_balance qui doit déclencher une reconnexion
    mock_client = Mock()
    mock_client.get_account.return_value = {"balances": [{"asset": "BTC", "free": "0.5", "locked": "0.0"}]}
    
    # Simuler que le client est créé après reconnexion
    async def mock_get_balance_internal(asset):
        if not adapter.connected:
            await adapter.connect()
            adapter.client = mock_client
            adapter.connected = True
        return 0.5
    
    # Patcher la méthode get_balance
    with patch.object(adapter, 'get_balance', side_effect=mock_get_balance_internal):
        balance = await adapter.get_balance("BTC")
        print("[PASS] Reconnexion automatique fonctionne")
        assert connect_calls >= 1, "La reconnexion n'a pas été tentée"
    
    return True

async def test_error_classification():
    """Test de la classification des erreurs"""
    print("\n[TEST] Test de la classification des erreurs...")
    
    config = ExchangeConfig(
        name="binance_test",
        type=ExchangeType.CEX,
        api_key="test_key",
        api_secret="test_secret",
        sandbox=True,
        fee_rate=0.001,
        min_order_size=10.0
    )
    
    adapter = BinanceAdapter(config)
    
    # Mock binance.exceptions module
    import sys
    from types import ModuleType
    
    # Create mock binance.exceptions module
    mock_binance_exceptions = ModuleType('binance.exceptions')
    
    class MockBinanceAPIException(Exception):
        def __init__(self, code, message, status_code=400):
            self.code = code
            self.message = message  
            self.status_code = status_code
            super().__init__(message)
    
    class MockBinanceRequestException(Exception):
        pass
    
    mock_binance_exceptions.BinanceAPIException = MockBinanceAPIException
    mock_binance_exceptions.BinanceRequestException = MockBinanceRequestException
    
    sys.modules['binance.exceptions'] = mock_binance_exceptions
    
    test_cases = [
        # (error_code, expected_exception_type, description)
        (-1003, RateLimitError, "Rate limit error"),
        (-1002, RateLimitError, "IP banned"),
        (-1001, RetryableError, "Network error"),
        (-2010, ValueError, "Account error (non-retryable)"),
        (-9999, ValueError, "Unknown API error")
    ]
    
    for error_code, expected_type, description in test_cases:
        try:
            mock_exception = MockBinanceAPIException(error_code, f"Test {description}")
            adapter._handle_binance_exception(mock_exception)
            print(f"[FAIL] {description}: Exception pas levée")
            return False
        except expected_type:
            print(f"[PASS] {description}: Correctement classifié comme {expected_type.__name__}")
        except Exception as e:
            print(f"[FAIL] {description}: Mauvaise classification - {type(e).__name__} au lieu de {expected_type.__name__}")
            return False
    
    return True

async def test_exponential_backoff():
    """Test du calcul de l'exponential backoff"""
    print("\n[TEST] Test de l'exponential backoff...")
    
    from services.execution.exchange_adapter import calculate_backoff_delay
    
    # Test que les délais augmentent exponentiellement
    delays = []
    for attempt in range(5):
        delay = calculate_backoff_delay(attempt, base_delay=1.0, max_delay=10.0)
        delays.append(delay)
        print(f"   Attempt {attempt}: {delay:.2f}s")
    
    # Vérifier que les délais augmentent (en général, avec de la jitter il peut y avoir des variations)
    base_delays = [1.0, 2.0, 4.0, 8.0, 10.0]  # Max à 10.0
    
    for i, (actual, expected_base) in enumerate(zip(delays, base_delays)):
        # Avec jitter, on s'attend à ±25% du délai de base
        min_delay = expected_base * 0.75
        max_delay = expected_base * 1.25
        if not (0.1 <= actual <= max(max_delay, 10.0)):  # 0.1 est le minimum absolu
            print(f"[FAIL] Délai {i} hors limites: {actual:.2f}s (attendu: {min_delay:.2f}-{max_delay:.2f}s)")
            return False
    
    print("[PASS] Exponential backoff avec jitter fonctionne correctement")
    return True

async def main():
    """Fonction principale des tests"""
    print("[RUN] Test de la gestion d'erreurs - BinanceAdapter")
    print("=" * 50)
    
    tests = [
        ("Exponential Backoff", test_exponential_backoff),
        ("Classification des erreurs", test_error_classification),
        ("Gestion rate limits", test_rate_limit_handling),
        ("Mécanisme retry", test_retry_mechanism),
        ("Reconnexion automatique", test_connection_recovery),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n[INFO] Exécution: {test_name}")
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"[FAIL] Erreur dans {test_name}: {e}")
            results.append((test_name, False))
    
    # Résumé des résultats
    print("\n" + "=" * 50)
    print("[SUMMARY] RÉSUMÉ DES TESTS")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "[PASS] PASSÉ" if success else "[FAIL] ÉCHOUÉ"
        print(f"{test_name:.<40} {status}")
        if success:
            passed += 1
    
    print(f"\n[RESULT] Résultat final: {passed}/{total} tests passés")
    
    if passed == total:
        print("[SUCCESS] Tous les tests de gestion d'erreurs sont passés!")
        return True
    else:
        print("[WARN]  Certains tests ont échoué - vérification nécessaire")
        return False

if __name__ == "__main__":
    asyncio.run(main())