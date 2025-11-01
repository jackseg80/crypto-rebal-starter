#!/usr/bin/env python3
"""
Script de validation du mode Priority pour smartfolio.

Vérifie que tous les composants fonctionnent correctement :
- Imports et configuration
- Mode proportionnel (non-régression)
- Mode priority avec fallback
- Interface API

Usage: python validate_priority_mode.py
"""

import sys
import os
import json
import traceback
from typing import Dict, Any, List

# Ajouter le répertoire racine au PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test des imports essentiels."""
    print("Test des imports...")

    try:
        from connectors.coingecko import CoinGeckoConnector, CoinMeta
        from services.universe import UniverseManager, ScoredCoin, get_universe_cached
        from services.rebalance import plan_rebalance
        from services.taxonomy import Taxonomy
        print("Tous les imports reussis")
        return True
    except Exception as e:
        print(f"Erreur d'import: {e}")
        return False

def test_configuration():
    """Test de la configuration."""
    print("\nTest de la configuration...")

    config_files = [
        "config/universe.json",
        "data/mkt/aliases.json"
    ]

    for config_file in config_files:
        if not os.path.exists(config_file):
            print(f"FAIL: Fichier manquant: {config_file}")
            return False

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                json.load(f)
            print(f"OK: {config_file} valide")
        except Exception as e:
            print(f"FAIL: Erreur JSON dans {config_file}: {e}")
            return False

    # Vérifier structure cache
    cache_dir = "data/cache"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        print(f"✅ Répertoire cache créé: {cache_dir}")
    else:
        print(f"✅ Répertoire cache existe: {cache_dir}")

    return True

def test_proportional_mode():
    """Test du mode proportionnel (non-régression)."""
    print("\n🔍 Test mode proportionnel (non-régression)...")

    try:
        from services.rebalance import plan_rebalance

        # Portfolio test
        rows = [
            {"symbol": "BTC", "alias": "BTC", "value_usd": 3500, "location": "CoinTracking"},
            {"symbol": "ETH", "alias": "ETH", "value_usd": 2000, "location": "CoinTracking"},
            {"symbol": "USDC", "alias": "USDC", "value_usd": 500, "location": "CoinTracking"},
        ]

        targets = {"BTC": 50, "ETH": 30, "Stablecoins": 20}

        # Mode par défaut
        plan_default = plan_rebalance(
            rows=rows,
            group_targets_pct=targets,
            min_trade_usd=25.0
        )

        # Mode proportionnel explicite
        plan_proportional = plan_rebalance(
            rows=rows,
            group_targets_pct=targets,
            sub_allocation="proportional",
            min_trade_usd=25.0
        )

        # Vérifications
        assert plan_default["total_usd"] == 6000.0
        assert plan_proportional["total_usd"] == 6000.0
        assert plan_default["total_usd"] == plan_proportional["total_usd"]
        assert "priority_meta" not in plan_default
        assert "priority_meta" not in plan_proportional

        print("✅ Mode proportionnel fonctionne (non-régression OK)")
        return True

    except Exception as e:
        print(f"❌ Erreur mode proportionnel: {e}")
        traceback.print_exc()
        return False

def test_priority_mode_fallback():
    """Test du mode priority avec fallback."""
    print("\n🔍 Test mode priority avec fallback...")

    try:
        from services.rebalance import plan_rebalance
        from unittest.mock import patch

        rows = [
            {"symbol": "BTC", "alias": "BTC", "value_usd": 3500, "location": "CoinTracking"},
            {"symbol": "ETH", "alias": "ETH", "value_usd": 2000, "location": "CoinTracking"},
        ]

        targets = {"BTC": 60, "ETH": 40}

        # Mock l'univers pour qu'il soit indisponible
        with patch('services.universe.get_universe_cached', return_value=None):
            plan = plan_rebalance(
                rows=rows,
                group_targets_pct=targets,
                sub_allocation="priority",
                min_trade_usd=25.0
            )

        # Vérifications
        assert plan["total_usd"] == 5500.0
        assert "actions" in plan
        assert isinstance(plan["actions"], list)

        # Pas de crash = succès du fallback
        print("✅ Mode priority avec fallback fonctionne")
        return True

    except Exception as e:
        print(f"❌ Erreur mode priority: {e}")
        traceback.print_exc()
        return False

def test_universe_manager():
    """Test du gestionnaire d'univers."""
    print("\n🔍 Test gestionnaire d'univers...")

    try:
        from services.universe import UniverseManager

        manager = UniverseManager()
        config = manager._load_config()

        # Vérifications config
        assert "features" in config
        assert "scoring" in config
        assert config["features"]["priority_allocation"] is True

        print("✅ Gestionnaire d'univers fonctionne")
        return True

    except Exception as e:
        print(f"❌ Erreur gestionnaire d'univers: {e}")
        traceback.print_exc()
        return False

def test_coingecko_connector():
    """Test du connecteur CoinGecko (sans API)."""
    print("\n🔍 Test connecteur CoinGecko...")

    try:
        from connectors.coingecko import CoinGeckoConnector, get_connector

        connector = get_connector()

        # Test résolution mapping (sans appel API)
        btc_id = connector._resolve_coingecko_id("BTC")
        eth_id = connector._resolve_coingecko_id("ETH")

        assert btc_id == "bitcoin"
        assert eth_id == "ethereum"

        print("✅ Connecteur CoinGecko fonctionne (mapping)")
        return True

    except Exception as e:
        print(f"❌ Erreur connecteur CoinGecko: {e}")
        traceback.print_exc()
        return False

def generate_summary_report():
    """Génère un rapport de validation."""
    print("\n" + "="*60)
    print("📋 RAPPORT DE VALIDATION - MODE PRIORITY")
    print("="*60)

    tests = [
        ("Imports", test_imports),
        ("Configuration", test_configuration),
        ("Mode proportionnel", test_proportional_mode),
        ("Mode priority (fallback)", test_priority_mode_fallback),
        ("Gestionnaire univers", test_universe_manager),
        ("Connecteur CoinGecko", test_coingecko_connector),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name}: Exception {e}")
            results.append((test_name, False))

    print("\n📊 RÉSULTATS:")
    print("-" * 40)

    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:<25} {status}")
        if success:
            passed += 1

    print("-" * 40)
    print(f"Total: {passed}/{len(results)} tests réussis")

    if passed == len(results):
        print("\n🎉 VALIDATION COMPLÈTE RÉUSSIE!")
        print("\nLe mode priority est prêt à être utilisé :")
        print("1. Démarrer le serveur: uvicorn api.main:app --reload --port 8080")
        print("2. Ouvrir: http://localhost:8080/static/rebalance.html")
        print("3. Activer le toggle 'Mode intra-groupe : Priorité'")
        print("4. Vérifier les métadonnées dans la réponse du plan")
        return True
    else:
        print("\n⚠️  VALIDATION PARTIELLE - Certains tests ont échoué")
        print("Vérifier les erreurs ci-dessus avant utilisation en production.")
        return False

def main():
    """Point d'entrée principal."""
    print("Validation du mode Priority - smartfolio")
    print("=" * 60)

    success = generate_summary_report()

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
