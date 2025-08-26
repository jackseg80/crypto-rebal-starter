#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test du Safety Validator - Validation complète des mécanismes de sécurité

Ce script teste toutes les règles de sécurité pour s'assurer qu'elles
fonctionnent correctement et protègent contre les erreurs dangereuses.
"""

import asyncio
import logging
import os
from services.execution.safety_validator import SafetyValidator, SafetyLevel
from services.execution.order_manager import Order
from services.execution.exchange_adapter import ExchangeConfig, ExchangeType, BinanceAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_safety_rules():
    """Test de toutes les règles de sécurité"""
    print("\n=== Test des Règles de Sécurité ===")
    
    validator = SafetyValidator(SafetyLevel.STRICT)
    results = []
    
    # Test 1: Ordre normal (devrait passer)
    normal_order = Order(
        id="test_normal",
        symbol="BTC/USDT", 
        action="buy",
        quantity=0.001,
        usd_amount=50.0
    )
    
    result = validator.validate_order(normal_order)
    results.append(("Ordre Normal", result.passed, f"Score: {result.total_score:.1f}"))
    
    # Test 2: Montant trop élevé (devrait échouer)
    high_amount_order = Order(
        id="test_high_amount",
        symbol="BTC/USDT",
        action="buy", 
        quantity=1.0,
        usd_amount=5000.0  # Dépasse la limite par défaut
    )
    
    result = validator.validate_order(high_amount_order)
    results.append(("Montant Élevé", not result.passed, f"Erreurs: {len(result.errors)}"))
    
    # Test 3: Symbole non autorisé (devrait donner un avertissement)
    unknown_symbol_order = Order(
        id="test_unknown_symbol",
        symbol="DOGE/USDT",  # Pas dans la whitelist
        action="sell",
        quantity=1000.0,
        usd_amount=100.0
    )
    
    result = validator.validate_order(unknown_symbol_order)
    results.append(("Symbole Inconnu", len(result.warnings) > 0, f"Avertissements: {len(result.warnings)}"))
    
    # Test 4: Quantité suspecte (devrait donner un avertissement)
    suspicious_quantity_order = Order(
        id="test_suspicious", 
        symbol="BTC/USDT",
        action="buy",
        quantity=10000.0,  # Quantité énorme
        usd_amount=500.0
    )
    
    result = validator.validate_order(suspicious_quantity_order)
    results.append(("Quantité Suspecte", len(result.warnings) > 0, f"Avertissements: {len(result.warnings)}"))
    
    # Test 5: Montant négatif (devrait échouer)
    negative_amount_order = Order(
        id="test_negative",
        symbol="ETH/USDT",
        action="sell", 
        quantity=1.0,
        usd_amount=-100.0  # Montant négatif
    )
    
    result = validator.validate_order(negative_amount_order)
    results.append(("Montant Négatif", not result.passed, f"Erreurs: {len(result.errors)}"))
    
    # Afficher les résultats
    for test_name, expected_result, details in results:
        status = "[PASS]" if expected_result else "[FAIL]"
        print(f"{status} {test_name}: {details}")
    
    return all(result[1] for result in results)

async def test_volume_limits():
    """Test des limites de volume quotidien"""
    print("\n=== Test des Limites de Volume ===")
    
    validator = SafetyValidator(SafetyLevel.STRICT)
    orders = []
    
    # Créer plusieurs ordres qui dépassent ensemble la limite quotidienne
    for i in range(15):  # 15 ordres de $800 = $12,000 (> $10,000 limite par défaut)
        order = Order(
            id=f"volume_test_{i}",
            symbol="BTC/USDT",
            action="buy" if i % 2 == 0 else "sell",
            quantity=0.02,
            usd_amount=800.0
        )
        orders.append(order)
    
    results = validator.validate_orders(orders)
    
    passed_orders = sum(1 for r in results.values() if r.passed)
    failed_orders = len(orders) - passed_orders
    
    print(f"[INFO] Ordres validés: {passed_orders}/{len(orders)}")
    print(f"[INFO] Ordres rejetés: {failed_orders}")
    print(f"[INFO] Volume utilisé: ${validator.daily_volume_used:.2f}")
    
    # Vérifier qu'au moins certains ordres sont rejetés pour dépassement de volume
    volume_rejections = sum(1 for r in results.values() 
                           if not r.passed and any('daily_volume_limit' in err for err in r.errors))
    
    success = volume_rejections > 0
    status = "[PASS]" if success else "[FAIL]"
    print(f"{status} Limitation de volume: {volume_rejections} rejets pour volume")
    
    return success

async def test_testnet_detection():
    """Test de détection du mode testnet"""
    print("\n=== Test Détection Testnet ===")
    
    validator = SafetyValidator(SafetyLevel.STRICT)
    
    # Créer un adaptateur Binance en mode sandbox
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
    
    test_order = Order(
        id="testnet_check",
        symbol="BTC/USDT",
        action="buy",
        quantity=0.001,
        usd_amount=50.0
    )
    
    # Test avec adaptateur sandbox
    result = validator.validate_order(test_order, {"adapter": adapter})
    testnet_passed = result.passed and any('Mode testnet confirmé' in info for info in result.info_messages)
    
    status = "[PASS]" if testnet_passed else "[FAIL]"
    print(f"{status} Détection testnet: {testnet_passed}")
    
    return testnet_passed

async def test_integration_with_binance_adapter():
    """Test d'intégration avec BinanceAdapter"""
    print("\n=== Test Intégration BinanceAdapter ===")
    
    # Créer un adaptateur avec validation de sécurité intégrée
    config = ExchangeConfig(
        name="binance_safety_test",
        type=ExchangeType.CEX,
        api_key="test_key",
        api_secret="test_secret",
        sandbox=True,
        fee_rate=0.001,
        min_order_size=10.0
    )
    
    adapter = BinanceAdapter(config)
    
    # Test 1: Ordre normal (devrait être accepté par la validation mais échouer à la connexion)
    normal_order = Order(
        id="integration_normal",
        symbol="BTC/USDT",
        action="buy",
        quantity=0.001, 
        usd_amount=50.0
    )
    
    result = await adapter.place_order(normal_order)
    
    # L'ordre devrait échouer à la connexion, pas à la validation de sécurité
    normal_test_passed = (not result.success and 
                         "Failed to connect" in result.error_message and
                         "sécurité" not in result.error_message)
    
    # Test 2: Ordre dangereux (devrait être rejeté par la validation de sécurité)
    dangerous_order = Order(
        id="integration_dangerous",
        symbol="BTC/USDT", 
        action="buy",
        quantity=1.0,
        usd_amount=10000.0  # Montant trop élevé
    )
    
    result = await adapter.place_order(dangerous_order)
    
    # L'ordre devrait être rejeté par la validation de sécurité
    dangerous_test_passed = (not result.success and 
                            "sécurité" in result.error_message)
    
    status1 = "[PASS]" if normal_test_passed else "[FAIL]"  
    status2 = "[PASS]" if dangerous_test_passed else "[FAIL]"
    
    print(f"{status1} Ordre normal: Validation passée, connexion échouée")
    print(f"{status2} Ordre dangereux: Rejeté par validation de sécurité")
    
    return normal_test_passed and dangerous_test_passed

async def test_safety_levels():
    """Test des différents niveaux de sécurité"""
    print("\n=== Test Niveaux de Sécurité ===")
    
    # Ordre avec avertissement (symbole non whitlisté)
    warning_order = Order(
        id="warning_test",
        symbol="XRP/USDT",  # Pas dans la whitelist
        action="buy",
        quantity=10.0,
        usd_amount=50.0
    )
    
    results = []
    
    # Test en mode STRICT (devrait rejeter)
    strict_validator = SafetyValidator(SafetyLevel.STRICT)
    result = strict_validator.validate_order(warning_order)
    strict_rejects_warnings = not result.passed
    results.append(("Mode STRICT", strict_rejects_warnings))
    
    # Test en mode MODERATE (devrait accepter avec avertissements)
    moderate_validator = SafetyValidator(SafetyLevel.MODERATE)
    result = moderate_validator.validate_order(warning_order)
    moderate_accepts_warnings = result.passed and len(result.warnings) > 0
    results.append(("Mode MODERATE", moderate_accepts_warnings))
    
    # Test en mode PERMISSIVE (devrait accepter)
    permissive_validator = SafetyValidator(SafetyLevel.PERMISSIVE) 
    result = permissive_validator.validate_order(warning_order)
    permissive_accepts = result.passed
    results.append(("Mode PERMISSIVE", permissive_accepts))
    
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}: {passed}")
    
    return all(result[1] for result in results)

async def main():
    """Fonction principale des tests de validation de sécurité"""
    print("[SECURITY] Tests du Safety Validator - Validation de Sécurité")
    print("=" * 65)
    
    test_functions = [
        ("Règles de Sécurité", test_safety_rules),
        ("Limites de Volume", test_volume_limits), 
        ("Détection Testnet", test_testnet_detection),
        ("Intégration BinanceAdapter", test_integration_with_binance_adapter),
        ("Niveaux de Sécurité", test_safety_levels)
    ]
    
    results = []
    
    for test_name, test_func in test_functions:
        try:
            print(f"\n[TEST] {test_name}")
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"[ERROR] Erreur dans {test_name}: {e}")
            results.append((test_name, False))
    
    # Résumé final
    print("\n" + "=" * 65)
    print("[SUMMARY] RÉSUMÉ DES TESTS DE SÉCURITÉ")
    print("=" * 65)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{test_name:<30} {status}")
        if success:
            passed += 1
    
    success_rate = (passed / total * 100) if total > 0 else 0
    print(f"\nRésultat: {passed}/{total} tests passés ({success_rate:.1f}%)")
    
    if passed == total:
        print("[SUCCESS] Tous les tests de sécurité sont passés!")
        print("[SAFE] Le système de validation de sécurité fonctionne correctement")
        return 0
    else:
        print("[WARNING] Certains tests ont échoué")
        print("[CAUTION] Vérifiez les mécanismes de sécurité avant utilisation")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)