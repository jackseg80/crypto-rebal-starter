#!/usr/bin/env python3
"""
Tests manuels interactifs pour le système d'alertes - Phase 1

Usage: python tests/manual/test_alerting_workflows.py
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests
from typing import Dict, Any

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).parent.parent.parent))

BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

class AlertingWorkflowTester:
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def print_section(self, title: str):
        """Afficher section de test"""
        print(f"\n{'='*60}")
        print(f"[TEST] {title}")
        print(f"{'='*60}")
    
    def print_result(self, test_name: str, success: bool, details: str = ""):
        """Afficher résultat de test"""
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} {test_name}")
        if details:
            print(f"   -> {details}")
    
    def test_api_health(self) -> bool:
        """Test 1: Vérifier santé des APIs"""
        self.print_section("1. Tests de Santé des APIs")
        
        try:
            # Test API principale
            response = self.session.get(f"{self.base_url}/docs")
            api_healthy = response.status_code == 200
            self.print_result("API FastAPI", api_healthy, f"Status: {response.status_code}")
            
            # Test endpoint alerts health
            response = self.session.get(f"{self.base_url}/api/alerts/health")
            alerts_healthy = response.status_code == 200
            if alerts_healthy:
                health_data = response.json()
                overall_status = health_data.get("status", "unknown")
                self.print_result("Alerts Health Check", overall_status == "healthy", 
                                f"Status: {overall_status}")
                
                # Détails des composants
                components = health_data.get("components", {})
                for comp_name, comp_data in components.items():
                    comp_status = comp_data.get("status", "unknown")
                    self.print_result(f"  Component {comp_name}", comp_status == "healthy",
                                    f"Status: {comp_status}")
            else:
                self.print_result("Alerts Health Check", False, f"HTTP {response.status_code}")
            
            return api_healthy and alerts_healthy
            
        except Exception as e:
            self.print_result("API Health", False, f"Error: {e}")
            return False
    
    def test_governance_endpoints(self) -> bool:
        """Test 2: Endpoints de gouvernance étendus"""
        self.print_section("2. Tests Endpoints Gouvernance")
        
        try:
            # Test état gouvernance
            response = self.session.get(f"{self.base_url}/api/governance/state")
            gov_state_ok = response.status_code == 200
            
            if gov_state_ok:
                state_data = response.json()
                has_auto_unfreeze = "auto_unfreeze_at" in state_data
                self.print_result("Governance State", True, 
                                f"Mode: {state_data.get('mode')}, Auto-unfreeze field: {has_auto_unfreeze}")
            else:
                self.print_result("Governance State", False, f"HTTP {response.status_code}")
            
            # Test freeze avec TTL (nécessite headers idempotency)
            freeze_payload = {
                "reason": "Test manuel freeze avec TTL",
                "ttl_minutes": 5,
                "source_alert_id": None
            }
            
            headers_with_idem = HEADERS.copy()
            headers_with_idem["Idempotency-Key"] = f"test-{int(time.time())}"
            
            response = self.session.post(
                f"{self.base_url}/api/governance/freeze",
                json=freeze_payload,
                headers=headers_with_idem
            )
            
            freeze_ok = response.status_code in [200, 401, 403]  # 401/403 = RBAC (attendu)
            if response.status_code == 200:
                freeze_data = response.json()
                self.print_result("Freeze with TTL", True, 
                                f"TTL: {freeze_data.get('freeze_ttl_minutes')}min")
            elif response.status_code in [401, 403]:
                self.print_result("Freeze with TTL", True, "RBAC protection active (expected)")
            else:
                self.print_result("Freeze with TTL", False, f"HTTP {response.status_code}")
            
            return gov_state_ok and freeze_ok
            
        except Exception as e:
            self.print_result("Governance Endpoints", False, f"Error: {e}")
            return False
    
    def test_alerts_endpoints(self) -> bool:
        """Test 3: Endpoints d'alertes"""
        self.print_section("3. Tests Endpoints Alertes")
        
        try:
            # Test liste des alertes actives
            response = self.session.get(f"{self.base_url}/api/alerts/active")
            active_alerts_ok = response.status_code == 200
            
            if active_alerts_ok:
                alerts_data = response.json()
                alert_count = len(alerts_data)
                self.print_result("Active Alerts", True, f"Count: {alert_count}")
                
                # Test avec filtres
                response = self.session.get(f"{self.base_url}/api/alerts/active?severity_filter=S2")
                filter_ok = response.status_code == 200
                self.print_result("Active Alerts with Filter", filter_ok)
            else:
                self.print_result("Active Alerts", False, f"HTTP {response.status_code}")
            
            # Test types d'alertes
            response = self.session.get(f"{self.base_url}/api/alerts/types")
            types_ok = response.status_code == 200
            
            if types_ok:
                types_data = response.json()
                alert_types_count = len(types_data.get("alert_types", []))
                severities_count = len(types_data.get("severities", []))
                self.print_result("Alert Types", alert_types_count == 6 and severities_count == 3,
                                f"Types: {alert_types_count}, Severities: {severities_count}")
            else:
                self.print_result("Alert Types", False, f"HTTP {response.status_code}")
            
            # Test métriques
            response = self.session.get(f"{self.base_url}/api/alerts/metrics")
            metrics_ok = response.status_code in [200, 401, 403]  # RBAC peut bloquer
            
            if response.status_code == 200:
                metrics_data = response.json()
                has_required_fields = all(key in metrics_data for key in 
                                        ["alert_engine", "storage", "host_info"])
                self.print_result("Metrics Endpoint", has_required_fields,
                                f"Required fields present: {has_required_fields}")
            elif response.status_code in [401, 403]:
                self.print_result("Metrics Endpoint", True, "RBAC protection active")
            else:
                self.print_result("Metrics Endpoint", False, f"HTTP {response.status_code}")
            
            return active_alerts_ok and types_ok and metrics_ok
            
        except Exception as e:
            self.print_result("Alerts Endpoints", False, f"Error: {e}")
            return False
    
    def test_config_management(self) -> bool:
        """Test 4: Gestion de configuration"""
        self.print_section("4. Tests Gestion Configuration")
        
        try:
            # Test lecture config actuelle
            response = self.session.get(f"{self.base_url}/api/alerts/config/current")
            current_config_ok = response.status_code in [200, 401, 403]
            
            if response.status_code == 200:
                config_data = response.json()
                has_config_fields = all(key in config_data for key in 
                                      ["config", "config_file_path", "last_modified"])
                self.print_result("Current Config", has_config_fields,
                                f"Config path: {config_data.get('config_file_path', 'N/A')}")
            elif response.status_code in [401, 403]:
                self.print_result("Current Config", True, "RBAC protection active")
            else:
                self.print_result("Current Config", False, f"HTTP {response.status_code}")
            
            # Test hot-reload (nécessite RBAC)
            response = self.session.post(f"{self.base_url}/api/alerts/config/reload")
            reload_ok = response.status_code in [200, 401, 403]
            
            if response.status_code == 200:
                reload_data = response.json()
                self.print_result("Config Reload", True, 
                                f"Success: {reload_data.get('success')}")
            elif response.status_code in [401, 403]:
                self.print_result("Config Reload", True, "RBAC protection active")
            else:
                self.print_result("Config Reload", False, f"HTTP {response.status_code}")
            
            return current_config_ok and reload_ok
            
        except Exception as e:
            self.print_result("Config Management", False, f"Error: {e}")
            return False
    
    def test_monitoring_endpoints(self) -> bool:
        """Test 5: Endpoints de monitoring"""
        self.print_section("5. Tests Endpoints Monitoring")
        
        try:
            # Test Prometheus metrics
            response = self.session.get(f"{self.base_url}/api/alerts/metrics/prometheus")
            prometheus_ok = response.status_code in [200, 401, 403]
            
            if response.status_code == 200:
                prometheus_text = response.text
                has_prometheus_format = (
                    "# HELP" in prometheus_text and 
                    "# TYPE" in prometheus_text and
                    "crypto_rebal_" in prometheus_text
                )
                self.print_result("Prometheus Metrics", has_prometheus_format,
                                f"Format valid: {has_prometheus_format}")
            elif response.status_code in [401, 403]:
                self.print_result("Prometheus Metrics", True, "RBAC protection active")
            else:
                self.print_result("Prometheus Metrics", False, f"HTTP {response.status_code}")
            
            # Test historique des alertes
            response = self.session.get(f"{self.base_url}/api/alerts/history?limit=10")
            history_ok = response.status_code == 200
            
            if history_ok:
                history_data = response.json()
                has_pagination = "pagination" in history_data and "alerts" in history_data
                self.print_result("Alert History", has_pagination,
                                f"Pagination present: {has_pagination}")
            else:
                self.print_result("Alert History", False, f"HTTP {response.status_code}")
            
            return prometheus_ok and history_ok
            
        except Exception as e:
            self.print_result("Monitoring Endpoints", False, f"Error: {e}")
            return False
    
    def test_config_file_structure(self) -> bool:
        """Test 6: Structure du fichier de configuration"""
        self.print_section("6. Tests Structure Configuration")
        
        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "alerts_rules.json"
            
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                
                # Vérifier structure requise
                required_sections = ["alerting_config", "alert_types", "suggested_actions", "metadata"]
                sections_present = all(section in config_data for section in required_sections)
                self.print_result("Config File Exists", True, f"Path: {config_path}")
                self.print_result("Required Sections", sections_present, 
                                f"Sections: {list(config_data.keys())}")
                
                # Vérifier les 6 types d'alertes
                alert_types = config_data.get("alert_types", {})
                expected_types = [
                    "VOL_Q90_CROSS", "REGIME_FLIP", "CORR_HIGH", 
                    "CONTRADICTION_SPIKE", "DECISION_DROP", "EXEC_COST_SPIKE"
                ]
                types_complete = all(atype in alert_types for atype in expected_types)
                self.print_result("Alert Types Complete", types_complete,
                                f"Types: {list(alert_types.keys())}")
                
                return sections_present and types_complete
            else:
                self.print_result("Config File Exists", False, f"Not found: {config_path}")
                return False
                
        except Exception as e:
            self.print_result("Config File Structure", False, f"Error: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Exécuter tous les tests"""
        print("[START] Demarrage des tests manuels - Phase 1 Alerting System")
        print(f"Base URL: {self.base_url}")
        
        results = {
            "api_health": self.test_api_health(),
            "governance_endpoints": self.test_governance_endpoints(),
            "alerts_endpoints": self.test_alerts_endpoints(),
            "config_management": self.test_config_management(),
            "monitoring_endpoints": self.test_monitoring_endpoints(),
            "config_file_structure": self.test_config_file_structure()
        }
        
        # Résumé
        self.print_section("RÉSUMÉ DES TESTS")
        passed = sum(results.values())
        total = len(results)
        
        for test_name, result in results.items():
            status = "[PASS]" if result else "[FAIL]"
            print(f"{status} {test_name.replace('_', ' ').title()}")
        
        print(f"\n[SUMMARY] Resultat global: {passed}/{total} tests passes")
        
        if passed == total:
            print("[SUCCESS] Tous les tests sont passes ! Le systeme d'alertes Phase 1 est operationnel.")
        else:
            print("[WARNING] Certains tests ont echoue. Verifiez les details ci-dessus.")
            print("[INFO] Note: Les echecs RBAC (401/403) sont normaux si l'authentification n'est pas configuree.")
        
        return results


if __name__ == "__main__":
    tester = AlertingWorkflowTester()
    results = tester.run_all_tests()
    
    # Exit code basé sur les résultats
    exit_code = 0 if all(results.values()) else 1
    sys.exit(exit_code)