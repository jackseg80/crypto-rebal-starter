#!/usr/bin/env python3
"""
Test simple du mode Priority - compatible Windows.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("=== Validation Mode Priority ===")

    # Test 1: Imports
    print("\n1. Test imports...")
    try:
        from connectors.coingecko import CoinGeckoConnector, CoinMeta
        from services.universe import UniverseManager, ScoredCoin, get_universe_cached
        from services.rebalance import plan_rebalance
        print("   OK: Tous les imports reussis")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    # Test 2: Configuration
    print("\n2. Test configuration...")
    import json
    config_files = ["config/universe.json", "data/mkt/aliases.json"]
    for config_file in config_files:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    json.load(f)
                print(f"   OK: {config_file}")
            except Exception as e:
                print(f"   FAIL: {config_file} - {e}")
                return False
        else:
            print(f"   FAIL: {config_file} manquant")
            return False

    # Test 3: Mode proportionnel (non-regression)
    print("\n3. Test mode proportionnel...")
    try:
        rows = [
            {"symbol": "BTC", "alias": "BTC", "value_usd": 3500, "location": "CoinTracking"},
            {"symbol": "ETH", "alias": "ETH", "value_usd": 2000, "location": "CoinTracking"},
        ]
        targets = {"BTC": 60, "ETH": 40}

        plan = plan_rebalance(rows=rows, group_targets_pct=targets, sub_allocation="proportional")
        assert plan["total_usd"] == 5500.0
        assert "actions" in plan
        print("   OK: Mode proportionnel fonctionne")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    # Test 4: Mode priority avec fallback
    print("\n4. Test mode priority...")
    try:
        from unittest.mock import patch

        with patch('services.universe.get_universe_cached', return_value=None):
            plan = plan_rebalance(rows=rows, group_targets_pct=targets, sub_allocation="priority")

        assert plan["total_usd"] == 5500.0
        assert "actions" in plan
        print("   OK: Mode priority avec fallback fonctionne")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    # Test 5: Univers manager
    print("\n5. Test univers manager...")
    try:
        manager = UniverseManager()
        config = manager._load_config()
        assert "features" in config
        assert config["features"]["priority_allocation"] is True
        print("   OK: Univers manager fonctionne")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    print("\n=== RESULTATS ===")
    print("SUCCES: Tous les tests sont passes!")
    print("\nPour utiliser le mode priority:")
    print("1. Demarrer: uvicorn api.main:app --reload --port 8080")
    print("2. Ouvrir: http://localhost:8080/static/rebalance.html")
    print("3. Activer le toggle 'Mode intra-groupe : Priorite'")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
