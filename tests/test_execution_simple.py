#!/usr/bin/env python3
"""
Test simple du système d'exécution - Validation complète
"""

import asyncio
import json
import requests
import time

API_BASE = "http://127.0.0.1:8000"

# Plan de test simple
TEST_ACTIONS = [
    {
        "symbol": "BTC",
        "alias": "Bitcoin", 
        "group": "BTC",
        "action": "sell",
        "usd": -1000.0,
        "est_quantity": 0.022,
        "price_used": 45000.0,
        "exec_hint": "Sell on Binance",
        "location": "Binance"
    },
    {
        "symbol": "ETH",
        "alias": "Ethereum",
        "group": "ETH", 
        "action": "buy",
        "usd": 500.0,
        "est_quantity": 0.167,
        "price_used": 3000.0,
        "exec_hint": "Buy on Kraken",
        "location": "Kraken"
    },
    {
        "symbol": "SOL",
        "alias": "Solana",
        "group": "SOL",
        "action": "buy", 
        "usd": 500.0,
        "est_quantity": 5.0,
        "price_used": 100.0,
        "exec_hint": "Buy on Binance",
        "location": "Binance"
    }
]

def test_api_endpoint(method, endpoint, data=None):
    """Test un endpoint API"""
    url = f"{API_BASE}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"Error calling {method} {endpoint}: {e}")
        return None

def main():
    print("Test du Systeme d'Execution")
    print("=" * 50)
    
    # 1. Verifier les exchanges disponibles
    print("\n1. Exchanges disponibles:")
    exchanges = test_api_endpoint("GET", "/execution/exchanges")
    if exchanges:
        for ex in exchanges["exchanges"]:
            status = "CONNECTED" if ex["connected"] else "DISCONNECTED"
            print(f"  {status} {ex['name']} ({ex['type']})")
    
    # 2. Valider un plan d'execution
    print("\n2. Validation du plan:")
    validation_data = {
        "rebalance_actions": TEST_ACTIONS,
        "metadata": {
            "source": "test_script",
            "timestamp": time.time()
        }
    }
    
    validation = test_api_endpoint("POST", "/execution/validate-plan", validation_data)
    if validation:
        if validation["valid"]:
            print(f"  OK Plan valide: {validation['total_orders']} ordres, ${validation['total_volume']:.2f}")
            plan_id = validation["plan_id"]
        else:
            print(f"  ERROR Validation echouee: {validation['errors']}")
            return
    else:
        print("  ERROR Impossible de valider le plan")
        return
    
    # 3. Lancer l'execution en mode simulation
    print(f"\n3. Execution du plan {plan_id} (simulation):")
    execution = test_api_endpoint("POST", f"/execution/execute-plan?plan_id={plan_id}&dry_run=true&max_parallel=2")
    if execution and execution["success"]:
        print(f"  STARTED Execution lancee: {execution['message']}")
        execution_id = execution["execution_id"]
    else:
        print("  ERROR Impossible de lancer l'execution")
        return
    
    # 4. Monitoring du progres
    print(f"\n4. Monitoring de l'execution:")
    for i in range(10):  # Max 20 secondes
        time.sleep(2)
        
        status = test_api_endpoint("GET", f"/execution/status/{plan_id}")
        if status:
            progress = status.get("completion_percentage", 0)
            success_rate = status.get("success_rate", 0)
            is_active = status.get("is_active", False)
            
            print(f"  PROGRESS: {progress:.1f}% | Success: {success_rate:.1f}% | Active: {is_active}")
            
            if not is_active:
                print(f"  FINISHED Execution terminee avec statut: {status.get('status', 'unknown')}")
                break
        else:
            print("  ERROR Impossible de recuperer le statut")
            break
    
    # 5. Details des ordres executes
    print(f"\n5. Details des ordres:")
    orders = test_api_endpoint("GET", f"/execution/orders/{plan_id}")
    if orders:
        for order in orders["orders"]:
            status_text = order["status"].upper()
            
            print(f"  {status_text} {order['alias']}: {order['action']} ${abs(order['usd_amount']):.2f} on {order['platform']}")
            if order["status"] == "filled":
                print(f"      EXECUTED: {order['filled_quantity']:.6f} @ ${order['avg_fill_price']:.2f}")
                print(f"      FEES: ${order['fees']:.2f}")
    
    # 6. Statistiques globales
    print(f"\n6. Statistiques globales:")
    stats = test_api_endpoint("GET", "/execution/pipeline-status")
    if stats:
        print(f"  ACTIVE Plans actifs: {stats['active_executions']}")
        print(f"  SUCCESS Taux de succes global: {stats['statistics']['success_rate']:.1f}%")
    
    print(f"\nOK Test termine avec succes!")

if __name__ == "__main__":
    main()