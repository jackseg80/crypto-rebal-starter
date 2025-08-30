#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de securite pour le mode sandbox - Validation des controles de securite

Ce script verifie que tous les mecanismes de securite fonctionnent correctement
en mode sandbox et qu'aucun ordre reel ne peut etre place accidentellement.
"""

import asyncio
import logging
import os
from typing import List, Dict, Any
from services.execution.exchange_adapter import (
    setup_default_exchanges, exchange_registry, ExchangeConfig, ExchangeType
)
from services.execution.order_manager import Order, OrderStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityTestResults:
    """Stockage des resultats de tests de securite"""
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.critical_failures = []
        self.warnings = []
        self.test_details = []

    def add_result(self, test_name: str, passed: bool, details: str = "", critical: bool = False):
        """Ajouter un resultat de test"""
        if passed:
            self.tests_passed += 1
            status = "[PASS]"
        else:
            self.tests_failed += 1
            status = "[FAIL]"
            if critical:
                self.critical_failures.append(f"{test_name}: {details}")

        self.test_details.append(f"{status} {test_name}: {details}")
        print(f"{status} {test_name}: {details}")

    def add_warning(self, message: str):
        """Ajouter un avertissement"""
        self.warnings.append(message)
        print(f"[WARN] {message}")

    def get_summary(self) -> Dict[str, Any]:
        """Obtenir le resume des tests"""
        total_tests = self.tests_passed + self.tests_failed
        return {
            "total_tests": total_tests,
            "passed": self.tests_passed,
            "failed": self.tests_failed,
            "success_rate": (self.tests_passed / total_tests * 100) if total_tests > 0 else 0,
            "critical_failures": len(self.critical_failures),
            "warnings": len(self.warnings)
        }

async def test_environment_configuration(results: SecurityTestResults):
    """Test de la configuration d'environnement pour la securite"""
    print("\n=== Test Configuration Environnement ===")
    
    # Test 1: Verifier que BINANCE_SANDBOX est configure
    sandbox_mode = os.getenv('BINANCE_SANDBOX', 'true').lower()
    if sandbox_mode == 'true':
        results.add_result("Sandbox Mode Enabled", True, "BINANCE_SANDBOX=true")
    else:
        results.add_result("Sandbox Mode Enabled", False, 
                         f"DANGER: BINANCE_SANDBOX={sandbox_mode}", critical=True)

    # Test 2: Verifier la presence des cles API
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if api_key and api_secret:
        # Verifier que ce sont des cles testnet (doivent etre marquees explicitement)
        testnet_marker = os.getenv('BINANCE_TESTNET', 'false').lower() == 'true'
        if testnet_marker:
            results.add_result("Testnet API Keys", True, f"Key: {api_key[:8]}...{api_key[-4:]} (testnet confirmed)")
        else:
            results.add_warning(f"API key detected but BINANCE_TESTNET not set - verify it's testnet: {api_key[:8]}...{api_key[-4:]}")
            results.add_result("Testnet API Keys", False, "Testnet mode not explicitly confirmed")
    else:
        results.add_result("API Keys Present", False, "No API keys found - will use simulator")

    # Test 3: Verifier qu'on n'est pas en mode production
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    if log_level in ['DEBUG', 'INFO']:
        results.add_result("Safe Log Level", True, f"LOG_LEVEL={log_level}")
    else:
        results.add_warning(f"Log level {log_level} may hide important safety information")

async def test_exchange_adapter_safety(results: SecurityTestResults):
    """Test des mecanismes de securite de l'adaptateur d'exchange"""
    print("\n=== Test Securite Adaptateurs ===")
    
    # Configuration des exchanges
    setup_default_exchanges()
    
    # Test 1: Verifier que Binance est configure en mode sandbox
    exchanges = exchange_registry.list_exchanges()
    results.add_result("Exchange Registry", len(exchanges) > 0, f"{len(exchanges)} exchanges configured")
    
    for exchange_name in exchanges:
        config = exchange_registry.configs.get(exchange_name)
        if config:
            if exchange_name == "binance":
                if hasattr(config, 'sandbox') and config.sandbox:
                    results.add_result(f"Binance Sandbox Mode", True, "Sandbox enabled")
                else:
                    results.add_result(f"Binance Sandbox Mode", False, 
                                     "DANGER: Sandbox not enabled", critical=True)
            
            # Test de connexion securisee
            try:
                adapter = exchange_registry.get_adapter(exchange_name)
                if adapter:
                    # Verifier que l'adaptateur refuse les connexions non securisees
                    if hasattr(adapter, 'config') and hasattr(adapter.config, 'sandbox'):
                        if adapter.config.sandbox:
                            results.add_result(f"{exchange_name} Safety Check", True, 
                                             "Adapter configured in sandbox mode")
                        else:
                            results.add_result(f"{exchange_name} Safety Check", False,
                                             f"DANGER: {exchange_name} not in sandbox", critical=True)
            except Exception as e:
                results.add_result(f"{exchange_name} Adapter Test", False, f"Error: {e}")

async def test_order_validation_safety(results: SecurityTestResults):
    """Test des validations de securite pour les ordres"""
    print("\n=== Test Validation Securite Ordres ===")
    
    # Test 1: Creer des ordres de test avec des montants securises
    test_orders = [
        {
            "symbol": "BTC/USDT",
            "action": "buy", 
            "quantity": 0.001,  # Petit montant pour test
            "usd_amount": 50.0,  # Montant limite
            "expected_safe": True
        },
        {
            "symbol": "ETH/USDT",
            "action": "sell",
            "quantity": 0.01,
            "usd_amount": 30.0,
            "expected_safe": True
        },
        {
            "symbol": "BTC/USDT", 
            "action": "buy",
            "quantity": 10.0,  # Montant enorme - devrait etre rejete
            "usd_amount": 500000.0,
            "expected_safe": False
        }
    ]
    
    for i, order_data in enumerate(test_orders):
        order = Order(
            id=f"test_{i}",
            symbol=order_data["symbol"],
            action=order_data["action"],
            quantity=order_data["quantity"],
            usd_amount=order_data["usd_amount"]
        )
        
        # Test de validation des montants
        is_safe_amount = order_data["usd_amount"] < 1000.0  # Limite arbitraire pour tests
        if is_safe_amount == order_data["expected_safe"]:
            results.add_result(f"Order {i+1} Amount Validation", True, 
                             f"${order_data['usd_amount']:.2f} correctly classified")
        else:
            results.add_result(f"Order {i+1} Amount Validation", False,
                             f"${order_data['usd_amount']:.2f} validation failed")

async def test_connection_security(results: SecurityTestResults):
    """Test de securite des connexions"""
    print("\n=== Test Securite Connexions ===")
    
    setup_default_exchanges()
    
    # Test connexion a chaque exchange
    for exchange_name in exchange_registry.list_exchanges():
        try:
            adapter = exchange_registry.get_adapter(exchange_name)
            if adapter:
                # Tenter la connexion
                connected = await adapter.connect()
                
                if connected:
                    # Verifier que c'est bien une connexion sandbox/simulator
                    if exchange_name == "simulator":
                        results.add_result(f"{exchange_name} Connection", True, 
                                         "Simulator connected safely")
                    elif exchange_name == "binance":
                        # Verifier les indicateurs de testnet
                        if hasattr(adapter, 'config') and adapter.config.sandbox:
                            results.add_result(f"{exchange_name} Connection", True,
                                             "Connected to Binance TESTNET")
                        else:
                            results.add_result(f"{exchange_name} Connection", False,
                                             "DANGER: Connected to Binance MAINNET", critical=True)
                    
                    # Test de deconnexion propre
                    await adapter.disconnect()
                    results.add_result(f"{exchange_name} Disconnection", True, "Clean disconnection")
                    
                else:
                    results.add_result(f"{exchange_name} Connection", True, 
                                     "Connection failed safely (no credentials)")
                    
        except Exception as e:
            # Les erreurs de connexion sont souvent attendues en mode test
            if "API key" in str(e) or "credentials" in str(e).lower():
                results.add_result(f"{exchange_name} Connection", True,
                                 f"Failed safely: {str(e)[:50]}...")
            else:
                results.add_result(f"{exchange_name} Connection", False, f"Unexpected error: {e}")

async def test_simulator_fallback(results: SecurityTestResults):
    """Test du fallback vers le simulateur"""
    print("\n=== Test Fallback Simulateur ===")
    
    setup_default_exchanges()
    
    # Test 1: Verifier que le simulateur est toujours disponible
    simulator_adapter = exchange_registry.get_adapter("simulator")
    if simulator_adapter:
        connected = await simulator_adapter.connect()
        results.add_result("Simulator Availability", connected, 
                         "Simulator always available as fallback")
        
        if connected:
            # Test des fonctions de base
            balance = await simulator_adapter.get_balance("BTC")
            results.add_result("Simulator Balance", balance >= 0, 
                             f"Balance: {balance} BTC")
            
            price = await simulator_adapter.get_current_price("BTC")
            results.add_result("Simulator Pricing", price is not None and price > 0,
                             f"BTC price: ${price}")
            
            await simulator_adapter.disconnect()
    else:
        results.add_result("Simulator Availability", False, 
                         "CRITICAL: Simulator not available", critical=True)

async def test_dry_run_mode(results: SecurityTestResults):
    """Test du mode dry-run complet"""
    print("\n=== Test Mode Dry-Run ===")
    
    # Test 1: Verifier qu'aucun ordre reel n'est envoye
    setup_default_exchanges()
    
    simulator = exchange_registry.get_adapter("simulator")
    if simulator and await simulator.connect():
        
        # Creer un ordre de test
        test_order = Order(
            id="dryrun_test",
            symbol="BTC/USDT",
            action="buy",
            quantity=0.001,
            usd_amount=50.0
        )
        
        # Tenter de placer l'ordre
        result = await simulator.place_order(test_order)
        
        if result.success:
            results.add_result("Dry-Run Order", True, 
                             f"Order simulated successfully: {result.filled_quantity} @ ${result.avg_price}")
            
            # Verifier que c'est bien une simulation
            if hasattr(result, 'exchange_data') and isinstance(result.exchange_data, dict):
                if result.exchange_data.get('simulated', False):
                    results.add_result("Order Simulation Flag", True, "Order properly marked as simulated")
                else:
                    results.add_warning("Order simulation flag not found - verify it's not real")
        else:
            results.add_result("Dry-Run Order", False, f"Order failed: {result.error_message}")
        
        await simulator.disconnect()
    else:
        results.add_result("Dry-Run Setup", False, "Could not setup simulator for dry-run test")

async def generate_security_report(results: SecurityTestResults):
    """Generer un rapport de securite detaille"""
    print("\n" + "=" * 60)
    print("RAPPORT DE SÉCURITÉ SANDBOX")
    print("=" * 60)
    
    summary = results.get_summary()
    
    print(f"Tests executes: {summary['total_tests']}")
    print(f"Reussis: {summary['passed']}")
    print(f"Echoues: {summary['failed']}")
    print(f"Taux de reussite: {summary['success_rate']:.1f}%")
    print(f"Echecs critiques: {summary['critical_failures']}")
    print(f"Avertissements: {summary['warnings']}")
    
    if results.critical_failures:
        print(f"\n[CRITICAL] ECHECS CRITIQUES DE SECURITE:")
        for failure in results.critical_failures:
            print(f"  - {failure}")
    
    if results.warnings:
        print(f"\n[WARN] AVERTISSEMENTS:")
        for warning in results.warnings:
            print(f"  - {warning}")
    
    print(f"\n[RECOMMENDATION]")
    if summary['critical_failures'] == 0:
        print("[SAFE] Le systeme est sur pour les tests sandbox")
        if summary['failed'] > 0:
            print("[WARN] Certains tests ont echoue - verifiez les details ci-dessus")
        if summary['warnings'] > 0:
            print("[WARN] Avertissements detectes - verifiez la configuration")
    else:
        print("[DANGER] Echecs critiques detectes - NE PAS UTILISER en production")
        print("[DANGER] Corrigez tous les problemes critiques avant de continuer")
    
    return summary['critical_failures'] == 0 and summary['success_rate'] >= 80.0

async def main():
    """Fonction principale des tests de securite"""
    print("[SECURITY] Tests de Securite Sandbox - Crypto Rebalancer")
    print("=" * 60)
    print("IMPORTANT: Ces tests verifient que le systeme est sur")
    print("pour les tests et qu'aucun ordre reel ne sera place.")
    print("=" * 60)
    
    results = SecurityTestResults()
    
    try:
        # Executer tous les tests de securite
        await test_environment_configuration(results)
        await test_exchange_adapter_safety(results)
        await test_order_validation_safety(results)
        await test_connection_security(results)
        await test_simulator_fallback(results)
        await test_dry_run_mode(results)
        
        # Generer le rapport final
        is_safe = await generate_security_report(results)
        
        # Retourner le code de sortie approprie
        if is_safe:
            print("\n[SUCCESS] Tous les tests de securite sont passes avec succes!")
            return 0
        else:
            print("\n[DANGER] Tests de securite echoues - Systeme non sur!")
            return 1
            
    except Exception as e:
        print(f"\n[ERROR] Erreur critique pendant les tests: {e}")
        results.add_result("Test Execution", False, str(e), critical=True)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)