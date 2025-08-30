#!/usr/bin/env python3
"""
Test E2E du pipeline complet crypto-rebalancer
Ingestion → Rebalancement → Exécution → Analytics

Ce script démontre le pipeline complet:
1. Ingestion des données portfolio (Balances API)  
2. Génération de plan de rebalancement avec CCS
3. Simulation d'exécution des ordres
4. Tracking analytics et performance
"""

import requests
import time
from datetime import datetime
from typing import Dict, List, Any

# Configuration
BASE_URL = "http://localhost:8001"
HEADERS = {"Content-Type": "application/json", "accept": "application/json"}

class PipelineE2ETester:
    def __init__(self):
        self.session_id = None
        self.portfolio_data = None
        self.rebalance_plan = None
        self.execution_results = []
        
    def log(self, message: str):
        """Log avec timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def test_step_1_ingestion(self) -> Dict[str, Any]:
        """
        Étape 1: Ingestion des données portfolio
        Test de l'endpoint /balances/current
        """
        self.log("=== ÉTAPE 1: INGESTION DES DONNÉES ===")
        
        # Récupérer les balances actuelles
        url = f"{BASE_URL}/balances/current?source=stub&min_usd=1"
        response = requests.get(url)
        
        if response.status_code != 200:
            raise Exception(f"Erreur ingestion: {response.text}")
            
        self.portfolio_data = response.json()
        items = self.portfolio_data.get("items", [])
        total_value = sum(float(item.get("value_usd", 0)) for item in items)
        
        self.log(f"OK Portfolio charge: {len(items)} assets, ${total_value:,.2f}")
        self.log(f"OK Source: {self.portfolio_data.get('source_used')}")
        
        return self.portfolio_data
    
    def test_step_2_rebalance_planning(self) -> Dict[str, Any]:
        """
        Étape 2: Génération du plan de rebalancement avec CCS
        Test de l'endpoint /rebalance/plan avec dynamic_targets
        """
        self.log("=== ÉTAPE 2: PLANIFICATION REBALANCEMENT ===")
        
        # Configuration des targets dynamiques (simulant CCS)
        payload = {
            "dynamic_targets_pct": {
                "BTC": 35.0,      # Réduction BTC (était ~64%)
                "ETH": 35.0,      # Augmentation ETH (était ~33%)  
                "Stablecoins": 20.0,  # Forte augmentation (était ~3%)
                "Others": 10.0    # Augmentation (était ~2%)
            },
            "sub_allocation": "proportional",
            "min_trade_usd": 25.0
        }
        
        url = f"{BASE_URL}/rebalance/plan?source=stub&min_usd=1&pricing=auto&dynamic_targets=true"
        response = requests.post(url, json=payload, headers=HEADERS)
        
        if response.status_code != 200:
            raise Exception(f"Erreur rebalancement: {response.text}")
            
        self.rebalance_plan = response.json()
        actions = self.rebalance_plan.get("actions", [])
        
        # Statistiques du plan
        sells = [a for a in actions if a.get("action") == "SELL"]
        buys = [a for a in actions if a.get("action") == "BUY"]
        total_volume = sum(abs(float(a.get("usd", 0))) for a in actions)
        
        self.log(f"OK Plan genere: {len(actions)} actions ({len(sells)} SELL, {len(buys)} BUY)")
        self.log(f"OK Volume total: ${total_volume:,.2f}")
        self.log(f"OK Pricing mode: {self.rebalance_plan.get('meta', {}).get('pricing_mode')}")
        
        return self.rebalance_plan
    
    def test_step_3_analytics_session(self) -> str:
        """
        Étape 3: Création de session analytics
        Test de l'endpoint /analytics/sessions
        """
        self.log("=== ÉTAPE 3: CRÉATION SESSION ANALYTICS ===")
        
        # Créer une session pour tracker cette opération
        session_payload = {
            "target_allocations": {
                "BTC": 35.0,
                "ETH": 35.0, 
                "Stablecoins": 20.0,
                "Others": 10.0
            },
            "source": "stub",
            "pricing_mode": "auto",
            "dynamic_targets_used": True,
            "ccs_score": 0.78,  # Score CCS simulé
            "min_trade_usd": 25.0,
            "strategy_notes": "Test E2E pipeline complet - CCS dynamic rebalancing"
        }
        
        url = f"{BASE_URL}/analytics/sessions"
        response = requests.post(url, json=session_payload, headers=HEADERS)
        
        if response.status_code != 200:
            raise Exception(f"Erreur création session: {response.text}")
            
        result = response.json()
        self.session_id = result.get("session_id")
        
        self.log(f"OK Session creee: {self.session_id[:8]}...")
        self.log(f"OK CCS Score: {session_payload['ccs_score']}")
        
        return self.session_id
    
    def test_step_4_portfolio_snapshot(self):
        """
        Étape 4: Capture du portfolio avant rebalancement  
        Test de l'endpoint /analytics/sessions/{id}/portfolio-snapshot
        """
        self.log("=== ÉTAPE 4: SNAPSHOT PORTFOLIO INITIAL ===")
        
        # Calculer les allocations actuelles
        items = self.portfolio_data.get("items", [])
        total_value = sum(float(item.get("value_usd", 0)) for item in items)
        
        allocations = {}
        values_usd = {}
        for item in items:
            symbol = item.get("symbol")
            value = float(item.get("value_usd", 0))
            
            # Classifier les symboles 
            if symbol in ["BTC"]:
                group = "BTC"
            elif symbol in ["ETH"]:
                group = "ETH"
            elif symbol in ["USDT", "USDC"]:
                group = "Stablecoins"
            else:
                group = "Others"
            
            allocations[group] = allocations.get(group, 0) + (value / total_value * 100)
            values_usd[group] = values_usd.get(group, 0) + value
        
        snapshot_payload = {
            "total_usd": total_value,
            "allocations": allocations,
            "values_usd": values_usd,
            "performance_24h_pct": 1.8,  # Simulé
            "performance_7d_pct": -2.1,   # Simulé  
            "performance_30d_pct": 12.4,  # Simulé
            "volatility_score": 0.52,     # Simulé
            "diversification_score": 0.68  # Simulé
        }
        
        url = f"{BASE_URL}/analytics/sessions/{self.session_id}/portfolio-snapshot"
        response = requests.post(url, json=snapshot_payload, headers=HEADERS)
        
        if response.status_code != 200:
            raise Exception(f"Erreur snapshot: {response.text}")
        
        self.log(f"OK Snapshot capture: ${total_value:,.2f}")
        for group, alloc in allocations.items():
            self.log(f"  - {group}: {alloc:.1f}%")
    
    def test_step_5_execution_simulation(self) -> List[Dict[str, Any]]:
        """
        Étape 5: Simulation d'exécution des ordres
        Test des endpoints /execution/validate-plan et /execution/execute-plan
        """
        self.log("=== ÉTAPE 5: SIMULATION EXÉCUTION ===")
        
        actions = self.rebalance_plan.get("actions", [])
        if not actions:
            self.log("WARN Aucune action a executer")
            return []
        
        # Étape 5a: Valider le plan d'abord
        validation_payload = {
            "rebalance_actions": actions,
            "metadata": {
                "source": "stub",
                "pricing_mode": "auto",
                "session_id": self.session_id
            },
            "dry_run": True,
            "max_parallel": 3
        }
        
        url = f"{BASE_URL}/execution/validate-plan"
        response = requests.post(url, json=validation_payload, headers=HEADERS)
        
        if response.status_code != 200:
            raise Exception(f"Erreur validation plan: {response.text}")
            
        validation_result = response.json()
        plan_id = validation_result.get("plan_id")
        
        self.log(f"OK Plan valide: {plan_id[:8]}... ({validation_result.get('total_orders')} ordres)")
        
        # Étape 5b: Exécuter le plan validé
        url = f"{BASE_URL}/execution/execute-plan?plan_id={plan_id}&dry_run=true&max_parallel=3"
        response = requests.post(url, headers=HEADERS)
        
        if response.status_code != 200:
            raise Exception(f"Erreur execution: {response.text}")
            
        execution_result = response.json()
        execution_id = execution_result.get("execution_id")
        
        self.log(f"OK Execution lancee: {execution_id[:8]}...")
        
        # Attendre un peu pour l'exécution simulée
        time.sleep(2)
        
        # Étape 5c: Vérifier le statut d'exécution  
        url = f"{BASE_URL}/execution/status/{plan_id}"
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            status = response.json()
            self.log(f"OK Statut: {status.get('status')}")
            self.execution_results = status.get("order_results", [])
            
            # Statistiques d'exécution
            successful = len([r for r in self.execution_results if r.get("status") == "filled"])
            total_volume = sum(float(r.get("executed_amount_usd", 0)) for r in self.execution_results)
            total_fees = sum(float(r.get("fees", 0)) for r in self.execution_results)
            
            self.log(f"OK Ordres executes: {successful}/{len(self.execution_results)}")
            self.log(f"OK Volume execute: ${total_volume:,.2f}")
            self.log(f"OK Frais totaux: ${total_fees:.2f}")
        else:
            self.log(f"WARN Impossible de recuperer le statut: {response.text}")
            self.execution_results = []
        
        return self.execution_results
    
    def test_step_6_execution_tracking(self):
        """
        Étape 6: Enregistrement des résultats d'exécution
        Test de l'endpoint /analytics/sessions/{id}/execution-results  
        """
        self.log("=== ÉTAPE 6: TRACKING EXÉCUTION ===")
        
        if not self.execution_results:
            self.log("WARN Aucun resultat d'execution a tracker")
            return
        
        # Convertir les résultats pour l'analytics
        tracking_payload = {
            "execution_results": []
        }
        
        for result in self.execution_results:
            tracking_result = {
                "symbol": result.get("symbol"),
                "side": result.get("side"),
                "planned_amount_usd": float(result.get("amount_usd", 0)),
                "executed_amount_usd": float(result.get("executed_amount_usd", 0)),
                "executed_quantity": float(result.get("executed_quantity", 0)),
                "average_price": float(result.get("average_price", 0)),
                "fees": float(result.get("fees", 0)),
                "status": result.get("status"),
                "exchange": result.get("exchange", "simulator"),
                "execution_time": result.get("timestamp", datetime.now().isoformat())
            }
            tracking_payload["execution_results"].append(tracking_result)
        
        url = f"{BASE_URL}/analytics/sessions/{self.session_id}/execution-results"
        response = requests.post(url, json=tracking_payload, headers=HEADERS)
        
        if response.status_code != 200:
            raise Exception(f"Erreur tracking exécution: {response.text}")
        
        self.log("OK Resultats d'execution enregistres")
    
    def test_step_7_performance_analysis(self):
        """
        Étape 7: Analyse de performance finale  
        Test des endpoints /analytics/performance/*
        """
        self.log("=== ÉTAPE 7: ANALYSE PERFORMANCE ===")
        
        # Compléter la session
        url = f"{BASE_URL}/analytics/sessions/{self.session_id}/complete"
        response = requests.post(url, headers=HEADERS)
        
        if response.status_code != 200:
            self.log(f"WARN Erreur finalisation session: {response.text}")
        else:
            self.log("OK Session finalisee")
        
        # Obtenir le résumé de performance
        url = f"{BASE_URL}/analytics/performance/summary"
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            summary = response.json()
            self.log("OK Resume de performance obtenu")
            self.log(f"  - Sessions totales: {summary.get('total_sessions', 0)}")
            self.log(f"  - Volume moyen: ${summary.get('avg_volume_per_session', 0):,.2f}")
        else:
            self.log(f"WARN Erreur recuperation performance: {response.text}")
        
        # Obtenir des recommandations  
        url = f"{BASE_URL}/analytics/optimization/recommendations"
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            recommendations = response.json().get("recommendations", [])
            self.log("OK Recommandations obtenues:")
            for rec in recommendations[:3]:  # Top 3
                self.log(f"  • {rec}")
        else:
            self.log(f"WARN Erreur recommandations: {response.text}")
    
    def run_full_pipeline(self):
        """Execute le pipeline E2E complet"""
        self.log(">>> DEBUT DU TEST PIPELINE E2E COMPLET")
        self.log("=" * 60)
        
        try:
            # Pipeline complet
            self.test_step_1_ingestion()
            self.test_step_2_rebalance_planning()  
            self.test_step_3_analytics_session()
            self.test_step_4_portfolio_snapshot()
            self.test_step_5_execution_simulation()
            self.test_step_6_execution_tracking()
            self.test_step_7_performance_analysis()
            
            self.log("=" * 60)
            self.log(">>> PIPELINE E2E TERMINE AVEC SUCCES!")
            self.log(f"Session ID: {self.session_id}")
            
        except Exception as e:
            self.log(f">>> ERREUR PIPELINE: {e}")
            raise

def main():
    """Point d'entrée principal"""
    tester = PipelineE2ETester()
    tester.run_full_pipeline()

if __name__ == "__main__":
    main()