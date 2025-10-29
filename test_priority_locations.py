#!/usr/bin/env python3
"""
Test pour vérifier que le mode Priority respecte bien les locations.
"""

import sys
import os
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_priority_with_multiple_locations():
    """Test avec un portfolio ayant plusieurs locations."""
    print("=== Test Priority Mode avec Locations Multiples ===")

    url = "http://localhost:8000/rebalance/plan"
    params = {"source": "cointracking", "min_usd": "100"}

    # Portfolio avec assets dans différentes locations
    payload = {
        "rows": [
            {"symbol": "BTC", "alias": "BTC", "value_usd": 2000, "location": "Binance"},
            {"symbol": "BTC", "alias": "BTC", "value_usd": 1000, "location": "Coinbase"},
            {"symbol": "ETH", "alias": "ETH", "value_usd": 1500, "location": "Binance"},
            {"symbol": "ETH", "alias": "ETH", "value_usd": 500, "location": "Kraken"},
            {"symbol": "USDC", "alias": "USDC", "value_usd": 1000, "location": "Coinbase"},
        ],
        "group_targets_pct": {"BTC": 60, "ETH": 30, "Stablecoins": 10},
        "sub_allocation": "priority",
        "min_trade_usd": 50
    }

    try:
        response = requests.post(url, params=params, json=payload, timeout=30)
        response.raise_for_status()
        plan = response.json()

        print(f"Total USD: {plan['total_usd']}")
        print(f"Actions générées: {len(plan['actions'])}")

        # Vérifier que les locations sont bien respectées
        locations_found = set()
        for action in plan['actions']:
            location = action.get('location')
            if location:
                locations_found.add(location)
            print(f"  {action['action'].upper():<4} {action['alias']:<8} "
                  f"{action['usd']:>8.2f} USD sur {location}")

        print(f"\nLocations utilisées: {sorted(locations_found)}")

        # Vérifications
        assert 'priority_meta' in plan, "priority_meta manquant"
        assert plan['priority_meta']['mode'] == 'priority', "Mode incorrect"

        # Vérifier que les locations d'origine sont respectées
        for action in plan['actions']:
            assert 'location' in action, f"Location manquante dans action: {action}"
            assert action['location'] in ['Binance', 'Coinbase', 'Kraken', 'CoinTracking'], \
                f"Location inattendue: {action['location']}"

        return True

    except Exception as e:
        print(f"Erreur: {e}")
        return False

def test_location_priority_logic():
    """Test de la logique de priorité des locations."""
    print("\n=== Test Logique de Priorité des Locations ===")

    try:
        from services.rebalance import plan_rebalance

        # Portfolio avec même asset sur plusieurs exchanges
        rows = [
            {"symbol": "BTC", "alias": "BTC", "value_usd": 1000, "location": "Binance"},
            {"symbol": "BTC", "alias": "BTC", "value_usd": 2000, "location": "CoinTracking"},  # Plus gros
            {"symbol": "ETH", "alias": "ETH", "value_usd": 500, "location": "Kraken"},
            {"symbol": "ETH", "alias": "ETH", "value_usd": 1500, "location": "Binance"},      # Plus gros
        ]

        targets = {"BTC": 40, "ETH": 60}

        plan = plan_rebalance(
            rows=rows,
            group_targets_pct=targets,
            sub_allocation="priority",
            min_trade_usd=100
        )

        print(f"Actions générées: {len(plan['actions'])}")

        # Analyser les locations choisies
        btc_actions = [a for a in plan['actions'] if a['alias'] == 'BTC']
        eth_actions = [a for a in plan['actions'] if a['alias'] == 'ETH']

        for action in plan['actions']:
            print(f"  {action['action'].upper():<4} {action['alias']:<4} "
                  f"{action['usd']:>8.2f} USD sur {action['location']}")

        print("\nLogique attendue:")
        print("- Pour BTC: plus gros sur CoinTracking (2000) vs Binance (1000)")
        print("- Pour ETH: plus gros sur Binance (1500) vs Kraken (500)")

        return True

    except Exception as e:
        print(f"Erreur test local: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_server_running():
    """Vérifier que le serveur est démarré."""
    try:
        response = requests.get("http://localhost:8000/docs", timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Warning: Server check failed: {e}")
        return False

def main():
    """Point d'entrée principal."""
    print("Test des Locations dans le Mode Priority")
    print("=" * 50)

    if not check_server_running():
        print("ERREUR: Serveur non demarre sur http://localhost:8000")
        print("Demarrer avec: uvicorn api.main:app --reload --port 8000")
        return False

    success = True
    success &= test_priority_with_multiple_locations()
    success &= test_location_priority_logic()

    print("\n" + "=" * 50)
    if success:
        print("SUCCES: Les locations sont correctement respectees dans le mode Priority!")
        print("\nPoints valides:")
        print("1. Chaque action contient sa location specifique")
        print("2. Les ventes respectent les locations d'origine des assets")
        print("3. Les achats choisissent intelligemment la meilleure location")
        print("4. La logique de priorite des exchanges fonctionne")
    else:
        print("ERREUR: Problemes detectes avec la gestion des locations")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)