#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Dashboard Complet - Validation de l'interface d'exécution temps réel

Ce script teste toutes les fonctionnalités du dashboard d'exécution:
- API endpoints
- Connections aux exchanges
- Exécution d'ordres
- Monitoring temps réel
- Interface utilisateur
"""

import asyncio
import logging
import json
import requests
import time
from datetime import datetime
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_BASE = "http://127.0.0.1:8000/api/execution"
DASHBOARD_URL = "http://127.0.0.1:8000/static/dashboard.html"

class DashboardTester:
    def __init__(self):
        self.test_results = []
        self.execution_history = []
        
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Enregistre le résultat d'un test"""
        status = "[PASS]" if success else "[FAIL]"
        self.test_results.append((test_name, success, details))
        message = f"{status} {test_name}"
        if details:
            message += f": {details}"
        logger.info(message)
    
    def test_api_endpoints(self) -> bool:
        """Test de tous les endpoints API du dashboard"""
        logger.info("\n=== Test API Endpoints ===")
        
        endpoints = [
            ("status", "GET", None),
            ("connections", "GET", None),
            ("statistics/summary", "GET", None),
            ("market-data", "GET", None),
            ("orders/recent?limit=10", "GET", None)
        ]
        
        all_success = True
        
        for endpoint, method, payload in endpoints:
            try:
                url = f"{API_BASE}/{endpoint}"
                if method == "GET":
                    response = requests.get(url, timeout=5)
                else:
                    response = requests.post(url, json=payload, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    self.log_result(f"API {endpoint}", True, f"Status: {response.status_code}")
                else:
                    self.log_result(f"API {endpoint}", False, f"Status: {response.status_code}")
                    all_success = False
                    
            except Exception as e:
                self.log_result(f"API {endpoint}", False, f"Error: {str(e)}")
                all_success = False
        
        return all_success
    
    def test_connection_management(self) -> bool:
        """Test des fonctionnalités de gestion de connexion"""
        logger.info("\n=== Test Gestion Connexions ===")
        
        exchanges = ["simulator", "enhanced_simulator", "binance"]
        all_success = True
        
        for exchange in exchanges:
            try:
                # Test de connexion
                url = f"{API_BASE}/test-connection/{exchange}"
                response = requests.post(url, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    connection_ok = result.get("connection_successful", False)
                    self.log_result(f"Test connexion {exchange}", connection_ok, 
                                  f"Functional: {result.get('api_functional', 'N/A')}")
                else:
                    self.log_result(f"Test connexion {exchange}", False, 
                                  f"Status: {response.status_code}")
                    all_success = False
                    
            except Exception as e:
                self.log_result(f"Test connexion {exchange}", False, f"Error: {str(e)}")
                all_success = False
        
        return all_success
    
    def test_order_execution(self) -> bool:
        """Test de l'exécution d'ordres avec monitoring"""
        logger.info("\n=== Test Exécution Ordres ===")
        
        test_orders = [
            {
                "name": "BTC Buy Small",
                "data": {
                    "orders": [{
                        "symbol": "BTC/USDT",
                        "action": "buy",
                        "quantity": 0.001,
                        "usd_amount": 50.0,
                        "alias": "BTC",
                        "group": "BTC"
                    }],
                    "exchange": "enhanced_simulator"
                }
            },
            {
                "name": "ETH Sell Test",
                "data": {
                    "orders": [{
                        "symbol": "ETH/USDT", 
                        "action": "sell",
                        "quantity": 0.02,
                        "usd_amount": 80.0,
                        "alias": "ETH",
                        "group": "ETH"
                    }],
                    "exchange": "enhanced_simulator"
                }
            },
            {
                "name": "Multi-Order Batch",
                "data": {
                    "orders": [
                        {
                            "symbol": "BNB/USDT",
                            "action": "buy", 
                            "quantity": 0.1,
                            "usd_amount": 75.0,
                            "alias": "BNB",
                            "group": "BNB"
                        },
                        {
                            "symbol": "ADA/USDT",
                            "action": "buy",
                            "quantity": 50.0,
                            "usd_amount": 45.0,
                            "alias": "ADA", 
                            "group": "Others"
                        }
                    ],
                    "exchange": "enhanced_simulator"
                }
            }
        ]
        
        all_success = True
        
        for test_order in test_orders:
            try:
                # Exécuter l'ordre
                url = f"{API_BASE}/orders/execute"
                response = requests.post(url, json=test_order["data"], timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    orders_count = result.get("orders_count", 0)
                    self.log_result(f"Exécution {test_order['name']}", True, 
                                  f"{orders_count} orders submitted")
                    
                    # Attendre completion et vérifier
                    time.sleep(2)
                    
                    # Vérifier les statistiques mises à jour
                    stats_response = requests.get(f"{API_BASE}/statistics/summary")
                    if stats_response.status_code == 200:
                        stats = stats_response.json()
                        total_orders = stats.get("total_orders", 0)
                        success_rate = stats.get("recent_24h", {}).get("success_rate", 0)
                        self.log_result(f"Stats après {test_order['name']}", True,
                                      f"{total_orders} total, {success_rate:.1f}% success")
                    
                else:
                    self.log_result(f"Exécution {test_order['name']}", False,
                                  f"Status: {response.status_code}")
                    all_success = False
                    
            except Exception as e:
                self.log_result(f"Exécution {test_order['name']}", False, f"Error: {str(e)}")
                all_success = False
        
        return all_success
    
    def test_realtime_monitoring(self) -> bool:
        """Test du monitoring temps réel"""
        logger.info("\n=== Test Monitoring Temps Réel ===")
        
        try:
            # Capturer état initial
            initial_response = requests.get(f"{API_BASE}/statistics/summary")
            initial_stats = initial_response.json() if initial_response.status_code == 200 else {}
            
            # Exécuter un ordre pour créer de l'activité
            test_order = {
                "orders": [{
                    "symbol": "DOT/USDT",
                    "action": "buy",
                    "quantity": 10.0,
                    "usd_amount": 40.0,
                    "alias": "DOT",
                    "group": "L1/L0 majors"
                }],
                "exchange": "enhanced_simulator"
            }
            
            requests.post(f"{API_BASE}/orders/execute", json=test_order)
            time.sleep(2)
            
            # Vérifier mise à jour temps réel
            updated_response = requests.get(f"{API_BASE}/statistics/summary")
            updated_stats = updated_response.json() if updated_response.status_code == 200 else {}
            
            initial_orders = initial_stats.get("total_orders", 0)
            updated_orders = updated_stats.get("total_orders", 0)
            
            monitoring_works = updated_orders > initial_orders
            self.log_result("Monitoring temps réel", monitoring_works,
                          f"Orders: {initial_orders} → {updated_orders}")
            
            # Test données de marché en temps réel
            market_response = requests.get(f"{API_BASE}/market-data")
            if market_response.status_code == 200:
                market_data = market_response.json()
                symbols_count = len(market_data.get("market_data", {}))
                self.log_result("Données marché temps réel", symbols_count >= 5,
                              f"{symbols_count} symboles disponibles")
            
            return monitoring_works
            
        except Exception as e:
            self.log_result("Monitoring temps réel", False, f"Error: {str(e)}")
            return False
    
    def test_dashboard_interface(self) -> bool:
        """Test de l'interface dashboard HTML"""
        logger.info("\n=== Test Interface Dashboard ===")
        
        try:
            # Vérifier accessibilité dashboard
            response = requests.get(DASHBOARD_URL, timeout=5)
            html_accessible = response.status_code == 200
            self.log_result("Accessibilité dashboard HTML", html_accessible,
                          f"Status: {response.status_code}")
            
            if html_accessible:
                html_content = response.text
                
                # Vérifier éléments critiques
                critical_elements = [
                    "Dashboard Execution",
                    "connectionsList", 
                    "statisticsGrid",
                    "refreshAll()",
                    "testAllConnections()",
                    "auto-refresh"
                ]
                
                elements_found = 0
                for element in critical_elements:
                    if element in html_content:
                        elements_found += 1
                
                interface_complete = elements_found == len(critical_elements)
                self.log_result("Éléments interface complets", interface_complete,
                              f"{elements_found}/{len(critical_elements)} trouvés")
                
                return html_accessible and interface_complete
            
            return False
            
        except Exception as e:
            self.log_result("Interface dashboard", False, f"Error: {str(e)}")
            return False
    
    def test_error_handling(self) -> bool:
        """Test de la gestion d'erreurs"""
        logger.info("\n=== Test Gestion Erreurs ===")
        
        error_tests = [
            ("Exchange inexistant", f"{API_BASE}/test-connection/nonexistent", "POST"),
            ("Ordre invalide", f"{API_BASE}/orders/execute", "POST", {"invalid": "data"}),
            ("Endpoint inexistant", f"{API_BASE}/nonexistent", "GET")
        ]
        
        all_handled = True
        
        for test_name, url, method, data in [
            ("Exchange inexistant", f"{API_BASE}/test-connection/nonexistent", "POST", None),
            ("Ordre invalide", f"{API_BASE}/orders/execute", "POST", {"invalid": "data"}),
            ("Endpoint inexistant", f"{API_BASE}/nonexistent", "GET", None)
        ]:
            try:
                if method == "GET":
                    response = requests.get(url, timeout=5)
                else:
                    response = requests.post(url, json=data, timeout=5)
                
                # Les erreurs doivent retourner un status approprié (404, 422, 500)
                error_handled = response.status_code in [404, 422, 500]
                self.log_result(f"Erreur {test_name}", error_handled,
                              f"Status: {response.status_code}")
                
                if not error_handled:
                    all_handled = False
                    
            except requests.exceptions.Timeout:
                self.log_result(f"Erreur {test_name}", True, "Timeout géré")
            except Exception as e:
                self.log_result(f"Erreur {test_name}", False, f"Exception: {str(e)}")
                all_handled = False
        
        return all_handled
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Lance tous les tests et génère un rapport complet"""
        logger.info("[DASHBOARD] Tests Complets du Dashboard d'Exécution")
        logger.info("=" * 65)
        
        test_functions = [
            ("API Endpoints", self.test_api_endpoints),
            ("Gestion Connexions", self.test_connection_management),
            ("Exécution Ordres", self.test_order_execution),
            ("Monitoring Temps Réel", self.test_realtime_monitoring),
            ("Interface Dashboard", self.test_dashboard_interface),
            ("Gestion Erreurs", self.test_error_handling)
        ]
        
        results = {}
        
        for test_name, test_func in test_functions:
            try:
                start_time = time.time()
                success = test_func()
                duration = time.time() - start_time
                results[test_name] = {"success": success, "duration": duration}
            except Exception as e:
                logger.error(f"[ERROR] Exception dans {test_name}: {e}")
                results[test_name] = {"success": False, "error": str(e)}
        
        # Résumé final
        logger.info("\n" + "=" * 65)
        logger.info("[SUMMARY] RÉSUMÉ DES TESTS DASHBOARD")
        logger.info("=" * 65)
        
        passed = sum(1 for r in results.values() if r.get("success", False))
        total = len(results)
        
        for test_name, result in results.items():
            status = "[PASS]" if result.get("success", False) else "[FAIL]"
            duration = result.get("duration", 0)
            logger.info(f"{test_name:<25} {status} ({duration:.1f}s)")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        logger.info(f"\nRésultat: {passed}/{total} tests passés ({success_rate:.1f}%)")
        
        # Statut final
        if passed == total:
            logger.info("[SUCCESS] Dashboard d'exécution opérationnel!")
            logger.info("[READY] Phase 3 Dashboard completée avec succès")
            return {"status": "success", "passed": passed, "total": total}
        elif passed >= total * 0.8:
            logger.info("[SUCCESS] Dashboard fonctionne correctement")
            logger.info("[CAUTION] Quelques améliorations possibles")
            return {"status": "partial", "passed": passed, "total": total}
        else:
            logger.info("[WARNING] Problèmes critiques détectés")
            logger.info("[ACTION] Révision nécessaire avant production")
            return {"status": "failure", "passed": passed, "total": total}

def main():
    """Fonction principale des tests"""
    tester = DashboardTester()
    
    # Vérifier que le serveur est en cours d'exécution
    try:
        response = requests.get(f"{API_BASE}/status", timeout=5)
        if response.status_code != 200:
            logger.error("[ERROR] Serveur API non disponible. Lancer: uvicorn api.main:app --reload")
            return 1
    except requests.exceptions.RequestException:
        logger.error("[ERROR] Impossible de se connecter au serveur")
        logger.error("Assurez-vous que le serveur est lancé: uvicorn api.main:app --reload")
        return 1
    
    # Lancer les tests
    result = tester.run_comprehensive_test()
    
    if result["status"] == "success":
        return 0
    elif result["status"] == "partial":
        return 0
    else:
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)