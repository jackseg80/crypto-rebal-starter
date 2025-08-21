#!/usr/bin/env python3
"""
Test simple du système d'exécution
"""

import requests
import time

API_BASE = "http://localhost:8001"

def test_execution_workflow():
    print("[TEST] E2E du systeme d'execution")
    print("=" * 50)
    
    # 1. Génération plan de rebalancement
    print("\n[1] Generation du plan de rebalancement...")
    
    rebalance_payload = {
        "primary_symbols": {
            "BTC": ["BTC"],
            "ETH": ["ETH"]
        },
        "sub_allocation": "proportional",
        "min_trade_usd": 25,
        "dynamic_targets_pct": {
            "BTC": 50,
            "ETH": 30,
            "Others": 20
        }
    }
    
    response = requests.post(
        f"{API_BASE}/rebalance/plan?source=coingecko&min_usd=1&pricing=auto&dynamic_targets=true",
        json=rebalance_payload
    )
    
    if response.status_code != 200:
        print(f"[ERROR] Generation plan: {response.status_code}")
        return False
    
    rebalance_plan = response.json()
    actions = rebalance_plan.get("actions", [])
    
    print(f"[OK] Plan genere: {len(actions)} actions")
    
    # 2. Validation du plan d'exécution
    print("\n[2] Validation du plan d'execution...")
    
    validation_payload = {
        "rebalance_actions": actions,
        "metadata": {
            "dynamic_targets_used": True,
            "ccs_score": 45
        },
        "dry_run": True,
        "max_parallel": 2
    }
    
    response = requests.post(
        f"{API_BASE}/execution/validate-plan",
        json=validation_payload
    )
    
    if response.status_code != 200:
        print(f"[ERROR] Validation: {response.status_code}")
        return False
    
    validation = response.json()
    plan_id = validation["plan_id"]
    
    print(f"[OK] Plan valide: {validation['total_orders']} ordres")
    print(f"[INFO] Volume: ${validation['total_volume']:.2f}")
    
    # 3. Lancer l'exécution
    print("\n[3] Lancement execution (dry-run)...")
    
    response = requests.post(
        f"{API_BASE}/execution/execute-plan?plan_id={plan_id}&dry_run=true&max_parallel=2"
    )
    
    if response.status_code != 200:
        print(f"[ERROR] Execution: {response.status_code}")
        return False
    
    execution = response.json()
    print(f"[OK] Execution lancee: {execution['message']}")
    
    # 4. Monitoring
    print("\n[4] Monitoring du progres...")
    
    for i in range(10):  # Max 10 checks
        response = requests.get(f"{API_BASE}/execution/status/{plan_id}")
        
        if response.status_code == 200:
            status = response.json()
            
            print(f"[PROGRESS] {status['completion_percentage']:.1f}% - "
                  f"{status['completed_orders']}/{status['total_orders']} ordres")
            
            if not status['is_active']:
                print(f"[DONE] Execution terminee: {status['status']}")
                break
        
        time.sleep(1)
    
    # 5. Résultats
    print("\n[5] Resultats...")
    
    response = requests.get(f"{API_BASE}/execution/orders/{plan_id}")
    if response.status_code == 200:
        orders_detail = response.json()
        orders = orders_detail["orders"]
        
        completed = sum(1 for o in orders if o["status"] == "filled")
        failed = sum(1 for o in orders if o["status"] == "failed")
        
        print(f"[RESULTS] Completes: {completed}/{len(orders)}")
        print(f"[RESULTS] Echecs: {failed}/{len(orders)}")
    
    print("\n[SUCCESS] Test E2E termine!")
    return True

if __name__ == "__main__":
    try:
        success = test_execution_workflow()
        if success:
            print("\n[OK] Tous les tests passes!")
        else:
            print("\n[FAIL] Tests echoues!")
    except Exception as e:
        print(f"\n[ERROR] Exception: {e}")
        import traceback
        traceback.print_exc()