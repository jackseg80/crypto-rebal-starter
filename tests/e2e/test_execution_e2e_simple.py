#!/usr/bin/env python3
"""
Test E2E Simple du système d'exécution
Version simplifiée sans emojis pour compatibilité Windows
"""

import requests
import time

API_BASE = "http://localhost:8001"

def test_execution_workflow():
    """Test complet du workflow d'exécution"""
    
    print("[TEST] E2E du systeme d'execution")
    print("=" * 50)
    
    # 1. Générer un plan de rebalancement
    print("\n[1] Generation du plan de rebalancement...")
    
    rebalance_payload = {
        "group_targets_pct": {
            "BTC": 40.0,
            "ETH": 25.0,
            "Stablecoins": 25.0,
            "Others": 10.0
        },
        "sub_allocation": "proportional",
        "min_trade_usd": 25.0
    }
    
    response = requests.post(
        f"{API_BASE}/rebalance/plan?source=stub&min_usd=1&pricing=auto",
        json=rebalance_payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Erreur generation plan: {response.text}")
        return False
        
    plan = response.json()
    actions = plan.get("actions", [])
    total_volume = sum(abs(float(a.get("usd", 0))) for a in actions)
    
    print(f"OK Plan genere: {len(actions)} actions, ${total_volume:,.2f} total")
    
    if not actions:
        print("WARN Aucune action generee")
        return True
    
    # 2. Valider le plan
    print("\n[2] Validation du plan d'execution...")
    
    validation_payload = {
        "rebalance_actions": actions,
        "metadata": {"source": "stub", "pricing_mode": "auto"},
        "dry_run": True,
        "max_parallel": 3
    }
    
    response = requests.post(
        f"{API_BASE}/execution/validate-plan",
        json=validation_payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Erreur validation: {response.text}")
        return False
        
    validation = response.json()
    plan_id = validation["plan_id"]
    
    print(f"OK Plan valide: {validation['total_orders']} ordres, ${validation['total_volume']:,.2f} volume")
    if validation.get("warnings"):
        print(f"WARN Avertissements: {validation['warnings']}")
    
    # 3. Exécuter le plan
    print("\n[3] Lancement de l'execution (dry-run)...")
    
    response = requests.post(
        f"{API_BASE}/execution/execute-plan?plan_id={plan_id}&dry_run=true&max_parallel=3"
    )
    
    if response.status_code != 200:
        print(f"Erreur execution: {response.text}")
        return False
        
    execution_result = response.json()
    execution_id = execution_result["execution_id"]
    
    print(f"OK Execution lancee: {execution_result['message']}")
    print(f"TIME Duree estimee: {execution_result.get('estimated_duration_seconds', 0)}s")
    
    # 4. Monitoring du progrès
    print("\n[4] Monitoring du progres...")
    
    max_checks = 10
    for i in range(max_checks):
        time.sleep(2)
        
        response = requests.get(f"{API_BASE}/execution/status/{plan_id}")
        if response.status_code != 200:
            continue
            
        status = response.json()
        
        progress = status.get("progress_pct", 0)
        completed = status.get("orders_completed", 0)  
        total = status.get("total_orders", 1)
        success_rate = status.get("success_rate_pct", 0)
        
        print(f"PROGRESS: {progress:.1f}% - {completed}/{total} ordres - Succes: {success_rate:.1f}%")
        
        if status.get("status") in ["completed", "failed"]:
            final_status = status
            break
    else:
        print("TIMEOUT Monitoring timeout")
        return False
    
    print(f"DONE Execution terminee: {final_status['status']}")
    
    # 5. Résultats finaux
    print("\n[5] Resultats finaux...")
    
    if final_status.get("order_results"):
        orders = final_status["order_results"]
        
        completed = len([o for o in orders if o["status"] == "filled"])
        failed = len([o for o in orders if o["status"] == "failed"])
        total_fees = sum(float(o.get("fees", 0)) for o in orders)
        
        print("RESULTS Resultats detailles:")
        print(f"   OK Completes: {completed}/{len(orders)}")
        print(f"   FAIL Echecs: {failed}/{len(orders)}")
        print(f"   FEES Frais totaux: ${total_fees:.4f}")
        
        # Afficher quelques ordres exemple
        print("\nEXAMPLES Exemples d'ordres:")
        for i, order in enumerate(orders[:3]):
            status_text = "OK" if order["status"] == "filled" else "FAIL" if order["status"] == "failed" else "WAIT"
            avg_price = order.get('avg_fill_price') or 0
            print(f"   {status_text} {order['alias']}: {order['action']} ${abs(order['usd_amount']):.2f} "
                  f"@ ${avg_price:.2f}")
    
    # 6. Test du monitoring système
    print("\n[6] Monitoring systeme...")
    
    response = requests.get(f"{API_BASE}/monitoring/status")
    if response.status_code == 200:
        monitoring = response.json()
        print(f"SYSTEM Status: {monitoring.get('status', 'unknown')}")
        print(f"UPTIME: {monitoring.get('uptime_seconds', 0)}s")
    
    return True

def main():
    """Point d'entrée principal"""
    try:
        success = test_execution_workflow()
        print("\nSUCCESS Tests d'execution E2E termines avec succes!" if success else "\nFAIL Tests echoues!")
        return 0 if success else 1
    except Exception as e:
        print(f"\nERROR Erreur durant les tests: {e}")
        return 1

if __name__ == "__main__":
    exit(main())