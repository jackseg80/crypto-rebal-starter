#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Monitoring Avancé - Validation du système de surveillance sophistiqué

Ce script teste toutes les fonctionnalités du monitoring avancé:
- Service de monitoring des connexions
- API endpoints avancés
- Système d'alertes
- Analytics et tendances
- Interface utilisateur
"""

import asyncio
import logging
import json
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_BASE = "http://127.0.0.1:8080/api/monitoring"
MONITORING_UI_URL = "http://127.0.0.1:8080/static/monitoring_advanced.html"

class AdvancedMonitoringTester:
    def __init__(self):
        self.test_results = []
        
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Enregistre le résultat d'un test"""
        status = "[PASS]" if success else "[FAIL]"
        self.test_results.append((test_name, success, details))
        message = f"{status} {test_name}"
        if details:
            message += f": {details}"
        logger.info(message)
    
    def test_monitoring_service_startup(self) -> bool:
        """Test du démarrage automatique du service de monitoring"""
        logger.info("\n=== Test Service Monitoring ===")
        
        try:
            # Le monitoring devrait démarrer automatiquement avec l'API
            response = requests.get(f"{API_BASE}/health", timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                monitoring_active = health_data.get("monitoring_active", False)
                
                self.log_result("Démarrage automatique monitoring", monitoring_active,
                              f"Active: {monitoring_active}")
                
                if monitoring_active:
                    # Vérifier que les métriques commencent à être collectées
                    time.sleep(5)  # Attendre un cycle de collecte
                    
                    config_response = requests.get(f"{API_BASE}/monitoring/config")
                    if config_response.status_code == 200:
                        config_data = config_response.json()
                        interval = config_data.get("check_interval_seconds", 0)
                        self.log_result("Configuration monitoring", interval > 0,
                                      f"Intervalle: {interval}s")
                        return True
                        
            return False
            
        except Exception as e:
            self.log_result("Service monitoring", False, f"Error: {str(e)}")
            return False
    
    def test_health_monitoring_api(self) -> bool:
        """Test des endpoints de monitoring de santé"""
        logger.info("\n=== Test API Monitoring Santé ===")
        
        endpoints_tests = [
            ("health", "GET", None, "Santé système globale"),
            ("status/detailed", "GET", None, "Statut détaillé exchanges"),
            ("monitoring/config", "GET", None, "Configuration monitoring"),
        ]
        
        all_success = True
        
        for endpoint, method, payload, description in endpoints_tests:
            try:
                url = f"{API_BASE}/{endpoint}"
                if method == "GET":
                    response = requests.get(url, timeout=10)
                else:
                    response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Vérifications spécifiques par endpoint
                    if endpoint == "health":
                        has_status = "global_status" in data
                        has_summary = "summary" in data
                        has_exchanges = "exchanges" in data
                        endpoint_valid = has_status and has_summary and has_exchanges
                        
                        self.log_result(f"API {description}", endpoint_valid,
                                      f"Status: {data.get('global_status', 'N/A')}")
                    
                    elif endpoint == "status/detailed":
                        has_exchanges = "exchanges" in data
                        exchanges_count = len(data.get("exchanges", {}))
                        endpoint_valid = has_exchanges and exchanges_count > 0
                        
                        self.log_result(f"API {description}", endpoint_valid,
                                      f"Exchanges: {exchanges_count}")
                    
                    elif endpoint == "monitoring/config":
                        has_interval = "check_interval_seconds" in data
                        has_active = "monitoring_active" in data
                        endpoint_valid = has_interval and has_active
                        
                        self.log_result(f"API {description}", endpoint_valid,
                                      f"Active: {data.get('monitoring_active', False)}")
                    
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
    
    def test_alerts_system(self) -> bool:
        """Test du système d'alertes"""
        logger.info("\n=== Test Système Alertes ===")
        
        try:
            # Récupérer les alertes existantes
            response = requests.get(f"{API_BASE}/alerts?limit=10")
            
            if response.status_code == 200:
                alerts_data = response.json()
                alerts = alerts_data.get("alerts", [])
                pagination = alerts_data.get("pagination", {})
                
                # Vérifier la structure des alertes
                alerts_valid = True
                if alerts:
                    first_alert = alerts[0]
                    required_fields = ["id", "exchange", "level", "message", "timestamp"]
                    alerts_valid = all(field in first_alert for field in required_fields)
                
                self.log_result("Récupération alertes", True,
                              f"{len(alerts)} alertes, Structure: {alerts_valid}")
                
                # Test filtres alertes
                filter_tests = [
                    ("level=warning", "Filtre par niveau"),
                    ("resolved=false", "Filtre non résolues"),
                    ("limit=5", "Limite résultats")
                ]
                
                for filter_param, description in filter_tests:
                    filter_response = requests.get(f"{API_BASE}/alerts?{filter_param}")
                    filter_success = filter_response.status_code == 200
                    self.log_result(f"Alertes {description}", filter_success)
                    
                    if not filter_success:
                        alerts_valid = False
                
                # Test résolution d'alerte (si disponible)
                if alerts and not alerts[0].get("resolved", True):
                    alert_id = alerts[0]["id"]
                    resolve_response = requests.post(f"{API_BASE}/alerts/{alert_id}/resolve")
                    resolve_success = resolve_response.status_code == 200
                    self.log_result("Résolution alerte", resolve_success)
                    
                    if not resolve_success:
                        alerts_valid = False
                
                return alerts_valid
                
            else:
                self.log_result("Système alertes", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Système alertes", False, f"Error: {str(e)}")
            return False
    
    def test_analytics_endpoints(self) -> bool:
        """Test des endpoints d'analytics"""
        logger.info("\n=== Test Analytics ===")
        
        analytics_tests = [
            ("analytics/performance", {"period_hours": 24}, "Performance globale"),
            ("analytics/trends", {"hours": 24}, "Analyse tendances"),
            ("metrics/enhanced_simulator", {"hours": 1}, "Métriques exchange spécifique"),
        ]
        
        all_success = True
        
        for endpoint, params, description in analytics_tests:
            try:
                # Construire URL avec paramètres
                param_string = "&".join([f"{k}={v}" for k, v in params.items()])
                url = f"{API_BASE}/{endpoint}?{param_string}"
                
                response = requests.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Vérifications spécifiques
                    if "performance" in endpoint:
                        has_global = "global_stats" in data
                        has_exchanges = "exchanges" in data
                        valid = has_global and has_exchanges
                        
                        self.log_result(f"Analytics {description}", valid,
                                      f"Exchanges analysés: {len(data.get('exchanges', {}))}")
                    
                    elif "trends" in endpoint:
                        has_trends = "trends" in data
                        trends_count = len(data.get("trends", {}))
                        valid = has_trends and trends_count >= 0
                        
                        self.log_result(f"Analytics {description}", valid,
                                      f"Tendances: {trends_count}")
                    
                    elif "metrics" in endpoint:
                        has_summary = "summary" in data
                        has_metrics = "metrics" in data
                        valid = has_summary and has_metrics
                        
                        self.log_result(f"Analytics {description}", valid,
                                      f"Points de données: {len(data.get('metrics', []))}")
                    
                    if not valid:
                        all_success = False
                        
                elif response.status_code == 404 and "metrics" in endpoint:
                    # Normal si pas encore de données pour cet exchange
                    self.log_result(f"Analytics {description}", True,
                                  "Pas de données (normal au démarrage)")
                else:
                    self.log_result(f"Analytics {description}", False,
                                  f"Status: {response.status_code}")
                    all_success = False
                    
            except Exception as e:
                self.log_result(f"Analytics {description}", False, f"Error: {str(e)}")
                all_success = False
        
        return all_success
    
    def test_monitoring_lifecycle(self) -> bool:
        """Test du cycle de vie du monitoring (redémarrage)"""
        logger.info("\n=== Test Cycle Vie Monitoring ===")
        
        try:
            # Obtenir l'état initial
            initial_response = requests.get(f"{API_BASE}/health")
            if initial_response.status_code != 200:
                self.log_result("État initial monitoring", False, "API inaccessible")
                return False
            
            initial_data = initial_response.json()
            initially_active = initial_data.get("monitoring_active", False)
            
            # Redémarrer le monitoring
            restart_response = requests.post(f"{API_BASE}/monitoring/restart")
            restart_success = restart_response.status_code == 200
            
            self.log_result("Redémarrage monitoring", restart_success)
            
            if restart_success:
                # Attendre un peu pour que le redémarrage prenne effet
                time.sleep(3)
                
                # Vérifier que le monitoring est toujours actif
                post_restart_response = requests.get(f"{API_BASE}/health")
                if post_restart_response.status_code == 200:
                    post_restart_data = post_restart_response.json()
                    still_active = post_restart_data.get("monitoring_active", False)
                    
                    self.log_result("Monitoring actif après redémarrage", still_active)
                    return still_active
                else:
                    self.log_result("Vérification post-redémarrage", False, 
                                  "API inaccessible après redémarrage")
                    return False
            
            return restart_success
            
        except Exception as e:
            self.log_result("Cycle vie monitoring", False, f"Error: {str(e)}")
            return False
    
    def test_monitoring_interface(self) -> bool:
        """Test de l'interface de monitoring avancé"""
        logger.info("\n=== Test Interface Monitoring ===")
        
        try:
            # Vérifier accessibilité de l'interface
            response = requests.get(MONITORING_UI_URL, timeout=5)
            html_accessible = response.status_code == 200
            
            self.log_result("Accessibilité interface", html_accessible,
                          f"Status: {response.status_code}")
            
            if html_accessible:
                html_content = response.text
                
                # Vérifier éléments critiques de l'interface avancée
                critical_elements = [
                    "Monitoring Avancé",
                    "globalStatus",
                    "exchangeStatus", 
                    "alertsList",
                    "analyticsContent",
                    "trendsContent",
                    "refreshAll()",
                    "restartMonitoring()",
                    "tab-container",
                    "auto-refresh"
                ]
                
                elements_found = 0
                missing_elements = []
                
                for element in critical_elements:
                    if element in html_content:
                        elements_found += 1
                    else:
                        missing_elements.append(element)
                
                interface_complete = elements_found == len(critical_elements)
                
                self.log_result("Éléments interface complets", interface_complete,
                              f"{elements_found}/{len(critical_elements)} trouvés")
                
                if missing_elements:
                    logger.warning(f"Éléments manquants: {', '.join(missing_elements)}")
                
                return html_accessible and interface_complete
            
            return False
            
        except Exception as e:
            self.log_result("Interface monitoring", False, f"Error: {str(e)}")
            return False
    
    def test_data_persistence(self) -> bool:
        """Test de la persistence des données"""
        logger.info("\n=== Test Persistence Données ===")
        
        try:
            import os
            from pathlib import Path
            
            # Vérifier création du répertoire de stockage
            expected_storage_dir = Path("data/monitoring")
            storage_exists = expected_storage_dir.exists()
            
            self.log_result("Création répertoire stockage", storage_exists,
                          f"Path: {expected_storage_dir}")
            
            if storage_exists:
                # Attendre un peu pour que des données soient générées
                time.sleep(10)
                
                # Vérifier présence de fichiers de métriques
                metric_files = list(expected_storage_dir.glob("metrics_*.json"))
                alert_files = list(expected_storage_dir.glob("alerts.json"))
                
                has_metric_files = len(metric_files) > 0
                has_alert_files = len(alert_files) > 0
                
                self.log_result("Fichiers métriques générés", has_metric_files,
                              f"Fichiers: {len(metric_files)}")
                
                self.log_result("Fichier alertes créé", has_alert_files,
                              f"Présent: {has_alert_files}")
                
                # Vérifier contenu d'un fichier de métriques si disponible
                if metric_files:
                    try:
                        with open(metric_files[0], 'r') as f:
                            metrics_data = json.load(f)
                        
                        data_valid = isinstance(metrics_data, list) and len(metrics_data) > 0
                        self.log_result("Données métriques valides", data_valid,
                                      f"Entrées: {len(metrics_data) if data_valid else 0}")
                        
                        return storage_exists and has_metric_files and data_valid
                    except Exception:
                        self.log_result("Lecture données métriques", False, "Erreur parsing JSON")
                        return False
                
                return storage_exists
            
            return False
            
        except Exception as e:
            self.log_result("Persistence données", False, f"Error: {str(e)}")
            return False
    
    def test_performance_impact(self) -> bool:
        """Test de l'impact sur les performances"""
        logger.info("\n=== Test Impact Performance ===")
        
        try:
            # Mesurer temps de réponse avec monitoring actif
            start_time = time.time()
            response_times = []
            
            for i in range(5):
                test_start = time.time()
                response = requests.get(f"{API_BASE}/health")
                test_end = time.time()
                
                if response.status_code == 200:
                    response_times.append((test_end - test_start) * 1000)  # ms
                
                time.sleep(1)  # Pause entre tests
            
            total_time = time.time() - start_time
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                max_response_time = max(response_times)
                
                # Les réponses doivent rester rapides même avec monitoring actif
                performance_acceptable = avg_response_time < 200 and max_response_time < 500
                
                self.log_result("Performance API acceptable", performance_acceptable,
                              f"Moy: {avg_response_time:.1f}ms, Max: {max_response_time:.1f}ms")
                
                # Vérifier que le monitoring ne bloque pas l'API
                api_responsive = len(response_times) == 5
                self.log_result("API responsive sous monitoring", api_responsive,
                              f"Réponses: {len(response_times)}/5")
                
                return performance_acceptable and api_responsive
            
            return False
            
        except Exception as e:
            self.log_result("Impact performance", False, f"Error: {str(e)}")
            return False
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Lance tous les tests et génère un rapport complet"""
        logger.info("[MONITORING] Tests Complets du Monitoring Avancé")
        logger.info("=" * 70)
        
        test_functions = [
            ("Service Monitoring", self.test_monitoring_service_startup),
            ("API Monitoring Santé", self.test_health_monitoring_api), 
            ("Système Alertes", self.test_alerts_system),
            ("Analytics", self.test_analytics_endpoints),
            ("Cycle Vie Monitoring", self.test_monitoring_lifecycle),
            ("Interface Monitoring", self.test_monitoring_interface),
            ("Persistence Données", self.test_data_persistence),
            ("Impact Performance", self.test_performance_impact)
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
        logger.info("\n" + "=" * 70)
        logger.info("[SUMMARY] RÉSUMÉ DES TESTS MONITORING AVANCÉ")
        logger.info("=" * 70)
        
        passed = sum(1 for r in results.values() if r.get("success", False))
        total = len(results)
        
        for test_name, result in results.items():
            status = "[PASS]" if result.get("success", False) else "[FAIL]"
            duration = result.get("duration", 0)
            logger.info(f"{test_name:<30} {status} ({duration:.1f}s)")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        logger.info(f"\nRésultat: {passed}/{total} tests passés ({success_rate:.1f}%)")
        
        # Statut final
        if passed == total:
            logger.info("[SUCCESS] Monitoring avancé opérationnel!")
            logger.info("[READY] Système de surveillance sophistiqué prêt")
            return {"status": "success", "passed": passed, "total": total}
        elif passed >= total * 0.8:
            logger.info("[SUCCESS] Monitoring fonctionne bien")
            logger.info("[CAUTION] Quelques fonctionnalités à optimiser")
            return {"status": "partial", "passed": passed, "total": total}
        else:
            logger.info("[WARNING] Problèmes critiques dans le monitoring")
            logger.info("[ACTION] Révision nécessaire avant utilisation")
            return {"status": "failure", "passed": passed, "total": total}

def main():
    """Fonction principale des tests"""
    tester = AdvancedMonitoringTester()
    
    # Vérifier que le serveur est en cours d'exécution
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code != 200:
            logger.error("[ERROR] Serveur API non disponible")
            logger.error("Lancer: uvicorn api.main:app --reload")
            return 1
    except requests.exceptions.RequestException:
        logger.error("[ERROR] Impossible de se connecter au serveur")
        logger.error("Assurez-vous que le serveur est lancé avec le monitoring")
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
