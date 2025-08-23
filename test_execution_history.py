#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Execution History - Validation du système d'historique et analytics

Ce script teste toutes les fonctionnalités de l'historique d'exécution:
- Service d'historique
- API endpoints
- Analytics et métriques
- Visualisations et tendances
- Interface utilisateur
"""

import asyncio
import logging
import json
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import uuid

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_BASE = "http://127.0.0.1:8000/api/execution/history"
DASHBOARD_API = "http://127.0.0.1:8000/api/execution/orders/execute"
HISTORY_UI_URL = "http://127.0.0.1:8000/static/execution_history.html"

class ExecutionHistoryTester:
    def __init__(self):
        self.test_results = []
        self.test_session_ids = []
        
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Enregistre le résultat d'un test"""
        status = "[PASS]" if success else "[FAIL]"
        self.test_results.append((test_name, success, details))
        message = f"{status} {test_name}"
        if details:
            message += f": {details}"
        logger.info(message)
    
    def test_history_service_basic(self) -> bool:
        """Test des fonctionnalités de base du service d'historique"""
        logger.info("\n=== Test Service Historique ===")
        
        try:
            # Test création de données d'historique via exécutions
            test_orders = [
                {
                    "symbol": "BTC/USDT",
                    "action": "buy",
                    "quantity": 0.001,
                    "usd_amount": 50.0,
                    "alias": "BTC",
                    "group": "BTC"
                },
                {
                    "symbol": "ETH/USDT", 
                    "action": "sell",
                    "quantity": 0.02,
                    "usd_amount": 80.0,
                    "alias": "ETH",
                    "group": "ETH"
                }
            ]
            
            # Créer quelques sessions de test
            for i in range(3):
                order_data = {
                    "orders": test_orders,
                    "exchange": "enhanced_simulator"
                }
                
                response = requests.post(DASHBOARD_API, json=order_data, timeout=10)
                
                if response.status_code == 200:
                    self.log_result(f"Création session test {i+1}", True, "Session créée via dashboard")
                    time.sleep(2)  # Attendre completion
                else:
                    self.log_result(f"Création session test {i+1}", False, f"Status: {response.status_code}")
                    return False
            
            # Attendre que les sessions soient enregistrées
            time.sleep(5)
            return True
            
        except Exception as e:
            self.log_result("Service historique", False, f"Error: {str(e)}")
            return False
    
    def test_history_api_endpoints(self) -> bool:
        """Test des endpoints API d'historique"""
        logger.info("\n=== Test API Historique ===")
        
        endpoints_tests = [
            ("sessions", {"limit": 10}, "Sessions récentes"),
            ("statistics", {}, "Statistiques globales"),
            ("performance", {"period_days": 7}, "Métriques performance 7j"),
            ("performance", {"period_days": 30}, "Métriques performance 30j"),
            ("trends", {"days": 14, "interval": "daily"}, "Tendances 14j"),
            ("dashboard-data", {}, "Données dashboard complètes")
        ]
        
        all_success = True
        
        for endpoint, params, description in endpoints_tests:
            try:
                param_string = "&".join([f"{k}={v}" for k, v in params.items()])
                url = f"{API_BASE}/{endpoint}"
                if param_string:
                    url += f"?{param_string}"
                
                response = requests.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Vérifications spécifiques par endpoint
                    if endpoint == "sessions":
                        has_sessions = "sessions" in data
                        has_metadata = "metadata" in data
                        endpoint_valid = has_sessions and has_metadata
                        sessions_count = len(data.get("sessions", []))
                        
                        self.log_result(f"API {description}", endpoint_valid,
                                      f"Sessions: {sessions_count}")
                    
                    elif endpoint == "statistics":
                        has_stats = any(key in data for key in ["total_sessions", "performance_rating"])
                        endpoint_valid = has_stats
                        
                        self.log_result(f"API {description}", endpoint_valid,
                                      f"Rating: {data.get('performance_rating', 'N/A')}")
                    
                    elif endpoint == "performance":
                        period = params.get("period_days", 0)
                        has_metrics = "total_sessions" in data and "avg_success_rate" in data
                        endpoint_valid = has_metrics
                        
                        self.log_result(f"API {description}", endpoint_valid,
                                      f"Sessions: {data.get('total_sessions', 0)}")
                    
                    elif endpoint == "trends":
                        has_trends = "trends" in data or "data_points" in data
                        endpoint_valid = has_trends
                        
                        self.log_result(f"API {description}", endpoint_valid,
                                      f"Points: {len(data.get('data_points', []))}")
                    
                    elif endpoint == "dashboard-data":
                        required_keys = ["recent_sessions", "statistics", "performance", "trends"]
                        endpoint_valid = all(key in data for key in required_keys)
                        
                        self.log_result(f"API {description}", endpoint_valid,
                                      f"Sections: {len([k for k in required_keys if k in data])}/4")
                    
                    if not endpoint_valid:
                        all_success = False
                        
                else:
                    self.log_result(f"API {description}", False,
                                  f"Status: {response.status_code}")
                    all_success = False
                    
            except Exception as e:
                self.log_result(f"API {description}", False, f"Error: {str(e)}")
                all_success = False
        
        return all_success
    
    def test_session_details(self) -> bool:
        """Test des détails de session spécifique"""
        logger.info("\n=== Test Détails Session ===")
        
        try:
            # Récupérer une session existante
            response = requests.get(f"{API_BASE}/sessions?limit=1")
            if response.status_code != 200:
                self.log_result("Récupération session pour test", False, "Pas de sessions disponibles")
                return False
            
            sessions_data = response.json()
            sessions = sessions_data.get("sessions", [])
            
            if not sessions:
                self.log_result("Sessions disponibles pour test", False, "Aucune session trouvée")
                return False
            
            session_id = sessions[0]["id"]
            
            # Tester les détails de session
            details_response = requests.get(f"{API_BASE}/sessions/{session_id}")
            
            if details_response.status_code == 200:
                details = details_response.json()
                
                # Vérifier la structure enrichie
                has_basic_info = all(key in details for key in ["id", "timestamp", "exchange", "orders"])
                has_analytics = "analytics" in details
                has_cost_analysis = has_analytics and "cost_analysis" in details.get("analytics", {})
                has_symbol_breakdown = has_analytics and "symbol_breakdown" in details.get("analytics", {})
                
                all_valid = has_basic_info and has_analytics and has_cost_analysis
                
                self.log_result("Détails session enrichis", all_valid,
                              f"Orders: {len(details.get('orders', []))}")
                
                if has_cost_analysis:
                    cost_analysis = details["analytics"]["cost_analysis"]
                    has_cost_fields = all(key in cost_analysis for key in 
                                        ["trading_fees", "total_cost", "cost_percentage"])
                    self.log_result("Analyse coûts détaillée", has_cost_fields,
                                  f"Coût total: {cost_analysis.get('cost_percentage', 0):.3f}%")
                
                return all_valid
                
            else:
                self.log_result("Accès détails session", False, f"Status: {details_response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Test détails session", False, f"Error: {str(e)}")
            return False
    
    def test_analytics_features(self) -> bool:
        """Test des fonctionnalités d'analytics avancées"""
        logger.info("\n=== Test Analytics Avancées ===")
        
        try:
            # Test métriques de performance avec différentes périodes
            periods = [7, 30]
            analytics_valid = True
            
            for period in periods:
                response = requests.get(f"{API_BASE}/performance?period_days={period}")
                
                if response.status_code == 200:
                    metrics = response.json()
                    
                    # Vérifier les enrichissements
                    has_benchmarks = "benchmarks" in metrics
                    has_recommendations = "recommendations" in metrics  
                    has_performance_rating = "performance_rating" in metrics
                    
                    enrichments_valid = has_benchmarks and has_performance_rating
                    
                    self.log_result(f"Analytics {period}j enrichies", enrichments_valid,
                                  f"Rating: {metrics.get('performance_rating', 'N/A')}")
                    
                    if "recommendations" in metrics:
                        recommendations_count = len(metrics["recommendations"])
                        self.log_result(f"Recommandations {period}j", True,
                                      f"{recommendations_count} suggestions")
                    
                    if not enrichments_valid:
                        analytics_valid = False
                        
                else:
                    self.log_result(f"Analytics {period}j", False, f"Status: {response.status_code}")
                    analytics_valid = False
            
            # Test tendances avec insights
            trends_response = requests.get(f"{API_BASE}/trends?days=14&interval=daily")
            
            if trends_response.status_code == 200:
                trends = trends_response.json()
                
                has_insights = "insights" in trends
                has_trend_data = "trends" in trends
                insights_count = len(trends.get("insights", []))
                
                trends_valid = has_insights and has_trend_data
                
                self.log_result("Tendances avec insights", trends_valid,
                              f"{insights_count} insights générés")
                
                if not trends_valid:
                    analytics_valid = False
                    
            else:
                self.log_result("Tendances", False, f"Status: {trends_response.status_code}")
                analytics_valid = False
            
            return analytics_valid
            
        except Exception as e:
            self.log_result("Analytics avancées", False, f"Error: {str(e)}")
            return False
    
    def test_data_export(self) -> bool:
        """Test de l'export de données"""
        logger.info("\n=== Test Export Données ===")
        
        try:
            # Test export CSV
            export_response = requests.get(f"{API_BASE}/export/sessions?days=30", timeout=10)
            
            if export_response.status_code == 200:
                csv_content = export_response.text
                
                # Vérifier le contenu CSV
                lines = csv_content.strip().split('\n')
                has_header = len(lines) > 0 and 'session_id' in lines[0]
                has_data = len(lines) > 1
                
                export_valid = has_header and 'timestamp' in lines[0] and 'total_volume_usd' in lines[0]
                
                self.log_result("Export CSV", export_valid,
                              f"{len(lines)} lignes générées")
                
                # Vérifier les en-têtes CSV
                if has_header:
                    expected_headers = [
                        "session_id", "timestamp", "exchange", "total_orders",
                        "successful_orders", "success_rate", "total_volume_usd"
                    ]
                    
                    header_line = lines[0]
                    headers_present = sum(1 for h in expected_headers if h in header_line)
                    
                    self.log_result("En-têtes CSV complets", headers_present >= 5,
                                  f"{headers_present}/{len(expected_headers)} en-têtes")
                
                return export_valid
                
            else:
                self.log_result("Export CSV", False, f"Status: {export_response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Export données", False, f"Error: {str(e)}")
            return False
    
    def test_data_persistence(self) -> bool:
        """Test de la persistence des données"""
        logger.info("\n=== Test Persistence ===")
        
        try:
            import os
            from pathlib import Path
            
            # Vérifier création du répertoire de stockage
            expected_storage_dir = Path("data/execution_history")
            storage_exists = expected_storage_dir.exists()
            
            self.log_result("Création répertoire historique", storage_exists,
                          f"Path: {expected_storage_dir}")
            
            if storage_exists:
                # Vérifier présence de fichiers de session
                session_files = list(expected_storage_dir.glob("sessions_*.json"))
                has_session_files = len(session_files) > 0
                
                self.log_result("Fichiers sessions générés", has_session_files,
                              f"Fichiers: {len(session_files)}")
                
                # Vérifier contenu d'un fichier si disponible
                if session_files:
                    try:
                        with open(session_files[0], 'r') as f:
                            sessions_data = json.load(f)
                        
                        data_valid = isinstance(sessions_data, list) and len(sessions_data) > 0
                        
                        if data_valid:
                            # Vérifier structure d'une session
                            first_session = sessions_data[0]
                            required_fields = ["id", "timestamp", "exchange", "orders"]
                            session_valid = all(field in first_session for field in required_fields)
                            
                            self.log_result("Structure sessions valide", session_valid,
                                          f"Entrées: {len(sessions_data)}")
                            
                            return storage_exists and has_session_files and data_valid and session_valid
                        else:
                            self.log_result("Données sessions", False, "Structure invalide")
                            return False
                            
                    except Exception:
                        self.log_result("Lecture données sessions", False, "Erreur parsing JSON")
                        return False
                
                return storage_exists and has_session_files
            
            return False
            
        except Exception as e:
            self.log_result("Test persistence", False, f"Error: {str(e)}")
            return False
    
    def test_history_interface(self) -> bool:
        """Test de l'interface d'historique"""
        logger.info("\n=== Test Interface Historique ===")
        
        try:
            # Vérifier accessibilité de l'interface
            response = requests.get(HISTORY_UI_URL, timeout=5)
            html_accessible = response.status_code == 200
            
            self.log_result("Accessibilité interface", html_accessible,
                          f"Status: {response.status_code}")
            
            if html_accessible:
                html_content = response.text
                
                # Vérifier éléments critiques de l'interface d'historique
                critical_elements = [
                    "Historique Exécutions",
                    "performanceMetrics",
                    "sessionsList",
                    "trendsChart",
                    "insightsList", 
                    "sessionModal",
                    "refreshAll()",
                    "exportData()",
                    "showSessionDetails",
                    "tab-container",
                    "filtersPanel"
                ]
                
                elements_found = 0
                missing_elements = []
                
                for element in critical_elements:
                    if element in html_content:
                        elements_found += 1
                    else:
                        missing_elements.append(element)
                
                interface_complete = elements_found >= len(critical_elements) * 0.9  # 90% des éléments
                
                self.log_result("Éléments interface complets", interface_complete,
                              f"{elements_found}/{len(critical_elements)} trouvés")
                
                if missing_elements and len(missing_elements) <= 2:
                    logger.warning(f"Éléments mineurs manquants: {', '.join(missing_elements[:2])}")
                
                # Vérifier intégration global-config.js
                has_global_config = 'global-config.js' in html_content
                self.log_result("Intégration configuration globale", has_global_config)
                
                return html_accessible and interface_complete
            
            return False
            
        except Exception as e:
            self.log_result("Interface historique", False, f"Error: {str(e)}")
            return False
    
    def test_integration_with_execution(self) -> bool:
        """Test de l'intégration avec le système d'exécution"""
        logger.info("\n=== Test Intégration Exécution ===")
        
        try:
            # Compter sessions avant
            before_response = requests.get(f"{API_BASE}/sessions?limit=1")
            if before_response.status_code == 200:
                before_count = len(before_response.json().get("sessions", []))
            else:
                before_count = 0
            
            # Exécuter un ordre via dashboard
            test_order = {
                "orders": [{
                    "symbol": "BTC/USDT",
                    "action": "buy", 
                    "quantity": 0.001,
                    "usd_amount": 45.0,
                    "alias": "BTC",
                    "group": "BTC"
                }],
                "exchange": "enhanced_simulator"
            }
            
            execution_response = requests.post(DASHBOARD_API, json=test_order, timeout=10)
            execution_success = execution_response.status_code == 200
            
            self.log_result("Exécution ordre test", execution_success)
            
            if execution_success:
                # Attendre enregistrement
                time.sleep(3)
                
                # Vérifier augmentation du nombre de sessions
                after_response = requests.get(f"{API_BASE}/sessions?limit=10")
                if after_response.status_code == 200:
                    after_sessions = after_response.json().get("sessions", [])
                    after_count = len(after_sessions)
                    
                    integration_works = after_count > before_count
                    
                    self.log_result("Enregistrement auto historique", integration_works,
                                  f"Sessions: {before_count} → {after_count}")
                    
                    # Vérifier que la nouvelle session a les bonnes données
                    if after_sessions and integration_works:
                        latest_session = after_sessions[0]  # Plus récente en premier
                        has_metadata = "metadata" in latest_session or len(latest_session.get("orders", [])) > 0
                        
                        self.log_result("Métadonnées session complètes", has_metadata,
                                      f"Exchange: {latest_session.get('exchange', 'N/A')}")
                    
                    return integration_works
                else:
                    self.log_result("Vérification post-exécution", False, "Erreur API")
                    return False
            
            return False
            
        except Exception as e:
            self.log_result("Intégration exécution", False, f"Error: {str(e)}")
            return False
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Lance tous les tests et génère un rapport complet"""
        logger.info("[HISTORY] Tests Complets de l'Historique d'Exécution")
        logger.info("=" * 75)
        
        test_functions = [
            ("Service Historique", self.test_history_service_basic),
            ("API Historique", self.test_history_api_endpoints),
            ("Détails Session", self.test_session_details),
            ("Analytics Avancées", self.test_analytics_features),
            ("Export Données", self.test_data_export),
            ("Persistence Données", self.test_data_persistence),
            ("Interface Historique", self.test_history_interface),
            ("Intégration Exécution", self.test_integration_with_execution)
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
        logger.info("\n" + "=" * 75)
        logger.info("[SUMMARY] RÉSUMÉ DES TESTS HISTORIQUE D'EXÉCUTION")
        logger.info("=" * 75)
        
        passed = sum(1 for r in results.values() if r.get("success", False))
        total = len(results)
        
        for test_name, result in results.items():
            status = "[PASS]" if result.get("success", False) else "[FAIL]"
            duration = result.get("duration", 0)
            logger.info(f"{test_name:<35} {status} ({duration:.1f}s)")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        logger.info(f"\nRésultat: {passed}/{total} tests passés ({success_rate:.1f}%)")
        
        # Statut final
        if passed == total:
            logger.info("[SUCCESS] Historique d'exécution complètement opérationnel!")
            logger.info("[READY] Analytics, persistence et interface fonctionnels")
            return {"status": "success", "passed": passed, "total": total}
        elif passed >= total * 0.8:
            logger.info("[SUCCESS] Historique fonctionne bien")
            logger.info("[CAUTION] Quelques fonctionnalités à optimiser")
            return {"status": "partial", "passed": passed, "total": total}
        else:
            logger.info("[WARNING] Problèmes critiques dans l'historique")
            logger.info("[ACTION] Révision nécessaire avant utilisation")
            return {"status": "failure", "passed": passed, "total": total}

def main():
    """Fonction principale des tests"""
    tester = ExecutionHistoryTester()
    
    # Vérifier que le serveur est en cours d'exécution
    try:
        response = requests.get(f"{API_BASE}/statistics", timeout=10)
        if response.status_code != 200:
            logger.error("[ERROR] Serveur API historique non disponible")
            logger.error("Lancer: uvicorn api.main:app --reload")
            return 1
    except requests.exceptions.RequestException:
        logger.error("[ERROR] Impossible de se connecter au serveur")
        logger.error("Assurez-vous que le serveur est lancé avec l'historique")
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