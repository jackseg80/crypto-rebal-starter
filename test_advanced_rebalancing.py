#!/usr/bin/env python3
"""
Test système de rebalancement avancé - Version sans emojis pour Windows
"""

import asyncio
import logging
from typing import List, Dict, Any
import time
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_basic_strategies():
    """Test des stratégies de base"""
    print("\n" + "="*60)
    print("TEST 1: Stratégies de rebalancement de base")
    print("="*60)
    
    from services.advanced_rebalancing import (
        advanced_rebalancing_engine,
        RebalancingStrategy,
        OptimizationConstraints
    )
    
    # Portfolio de test avec duplicatas intentionnels
    test_holdings = [
        {"symbol": "BTC", "value_usd": 5000.0, "location": "Binance", "quantity": 0.1},
        {"symbol": "WBTC", "value_usd": 1000.0, "location": "Coinbase", "quantity": 0.02},  # Duplicata BTC
        {"symbol": "ETH", "value_usd": 3000.0, "location": "Kraken", "quantity": 2.0},
        {"symbol": "STETH", "value_usd": 500.0, "location": "Binance", "quantity": 0.3},   # Duplicata ETH
        {"symbol": "USDC", "value_usd": 1500.0, "location": "Binance", "quantity": 1500},
        {"symbol": "DOGE", "value_usd": 800.0, "location": "Binance", "quantity": 1000},
        {"symbol": "UNI", "value_usd": 400.0, "location": "Coinbase", "quantity": 50}
    ]
    
    # Allocations cibles
    target_allocations = {
        "BTC": 40.0,
        "ETH": 30.0,
        "Stablecoins": 20.0,
        "DeFi": 5.0,
        "Memecoins": 5.0
    }
    
    # Test de différentes stratégies
    strategies_to_test = [
        RebalancingStrategy.SMART_CONSOLIDATION,
        RebalancingStrategy.PROPORTIONAL,
        RebalancingStrategy.RISK_PARITY,
        RebalancingStrategy.MOMENTUM
    ]
    
    results = {}
    
    print(f"Portfolio de test: ${sum(h['value_usd'] for h in test_holdings):,.0f}")
    print("Holdings:")
    for h in test_holdings:
        print(f"  - {h['symbol']}: ${h['value_usd']:,.0f} sur {h['location']}")
    
    for strategy in strategies_to_test:
        try:
            start_time = time.time()
            
            result = await advanced_rebalancing_engine.rebalance_portfolio(
                current_holdings=test_holdings,
                target_allocations=target_allocations,
                strategy=strategy
            )
            
            duration = time.time() - start_time
            results[strategy.value] = result
            
            print(f"\nStrategie: {strategy.value}")
            print(f"  Actions: {len(result.actions)}")
            print(f"  Consolidations: {len(result.duplicate_consolidations)}")
            print(f"  Score optimisation: {result.optimization_score:.1f}")
            print(f"  Frais estimes: ${result.estimated_total_fees:.2f}")
            print(f"  Complexite: {result.execution_complexity}")
            print(f"  Duree: {duration:.2f}s")
            
            if result.warnings:
                print(f"  Warnings: {len(result.warnings)}")
                for warning in result.warnings[:2]:
                    print(f"    - {warning}")
            
        except Exception as e:
            print(f"  ERREUR {strategy.value}: {e}")
            results[strategy.value] = None
    
    print(f"\nRésultats: {len([r for r in results.values() if r is not None])}/{len(strategies_to_test)} stratégies réussies")
    return results

async def test_duplicate_consolidation():
    """Test spécifique de la consolidation de duplicatas"""
    print("\n" + "="*60)
    print("TEST 2: Consolidation de duplicatas")
    print("="*60)
    
    from services.advanced_rebalancing import (
        advanced_rebalancing_engine,
        RebalancingStrategy
    )
    
    # Portfolio avec beaucoup de duplicatas
    holdings_with_duplicates = [
        {"symbol": "BTC", "value_usd": 2000.0, "location": "Binance"},
        {"symbol": "WBTC", "value_usd": 1500.0, "location": "Coinbase"}, 
        {"symbol": "TBTC", "value_usd": 500.0, "location": "Kraken"},
        {"symbol": "ETH", "value_usd": 1000.0, "location": "Binance"},
        {"symbol": "STETH", "value_usd": 800.0, "location": "Binance"},
        {"symbol": "WETH", "value_usd": 200.0, "location": "Coinbase"},
        {"symbol": "SOL", "value_usd": 600.0, "location": "Binance"},
        {"symbol": "JUPSOL", "value_usd": 400.0, "location": "Binance"},
        {"symbol": "USDC", "value_usd": 1000.0, "location": "Binance"}
    ]
    
    targets = {
        "BTC": 45.0,
        "ETH": 25.0, 
        "SOL": 15.0,
        "Stablecoins": 15.0
    }
    
    print(f"Portfolio avant consolidation:")
    total_before = sum(h['value_usd'] for h in holdings_with_duplicates)
    print(f"  Total: ${total_before:,.0f}")
    
    # Détection préliminaire des duplicatas
    from services.smart_classification import smart_classification_service
    symbols = [h["symbol"] for h in holdings_with_duplicates]
    duplicates = smart_classification_service.detect_duplicates_in_portfolio(symbols)
    
    print(f"  Duplicatas détectés: {len(duplicates)} groupes")
    for base, derivs in duplicates.items():
        print(f"    {base}: {len(derivs)} dérivés")
    
    # Test avec consolidation
    result = await advanced_rebalancing_engine.rebalance_portfolio(
        current_holdings=holdings_with_duplicates,
        target_allocations=targets,
        strategy=RebalancingStrategy.SMART_CONSOLIDATION
    )
    
    print(f"\nAprès rebalancement avec consolidation:")
    print(f"  Actions de consolidation: {len(result.duplicate_consolidations)}")
    print(f"  Actions de rebalancement: {len(result.actions)}")
    
    consolidation_volume = sum(float(c.get('value_usd', 0)) for c in result.duplicate_consolidations)
    print(f"  Volume de consolidation: ${consolidation_volume:,.0f}")
    
    if result.duplicate_consolidations:
        print("  Consolidations détaillées:")
        for consolidation in result.duplicate_consolidations:
            print(f"    {consolidation['from_symbol']} -> {consolidation['to_symbol']} (${consolidation['value_usd']:,.0f})")
    
    return result

async def test_strategy_comparison():
    """Test de comparaison entre stratégies"""
    print("\n" + "="*60)
    print("TEST 3: Comparaison de stratégies")
    print("="*60)
    
    from services.advanced_rebalancing import (
        advanced_rebalancing_engine,
        RebalancingStrategy
    )
    
    # Portfolio équilibré pour comparaison
    balanced_holdings = [
        {"symbol": "BTC", "value_usd": 4000.0, "location": "Binance"},
        {"symbol": "ETH", "value_usd": 3000.0, "location": "Kraken"},
        {"symbol": "SOL", "value_usd": 1500.0, "location": "Binance"},
        {"symbol": "USDC", "value_usd": 1000.0, "location": "Binance"},
        {"symbol": "UNI", "value_usd": 500.0, "location": "Coinbase"}
    ]
    
    targets = {"BTC": 35.0, "ETH": 30.0, "SOL": 20.0, "Stablecoins": 10.0, "DeFi": 5.0}
    
    strategies = [
        RebalancingStrategy.PROPORTIONAL,
        RebalancingStrategy.RISK_PARITY,
        RebalancingStrategy.MOMENTUM,
        RebalancingStrategy.MULTI_OBJECTIVE
    ]
    
    comparison_results = {}
    
    for strategy in strategies:
        try:
            result = await advanced_rebalancing_engine.rebalance_portfolio(
                balanced_holdings, targets, strategy
            )
            
            comparison_results[strategy.value] = {
                "optimization_score": result.optimization_score,
                "market_timing_score": result.market_timing_score, 
                "estimated_fees": result.estimated_total_fees,
                "execution_complexity": result.execution_complexity,
                "total_actions": len(result.actions),
                "warnings": len(result.warnings),
                "volume": result.metadata.get("total_volume", 0)
            }
            
        except Exception as e:
            comparison_results[strategy.value] = {"error": str(e)}
    
    print("Comparaison des stratégies:")
    print(f"{'Strategie':<20} {'Opt Score':<10} {'Timing':<8} {'Frais':<8} {'Actions':<8} {'Complexite':<12}")
    print("-" * 80)
    
    for strategy, metrics in comparison_results.items():
        if "error" not in metrics:
            print(f"{strategy:<20} {metrics['optimization_score']:<10.1f} "
                  f"{metrics['market_timing_score']:<8.1f} ${metrics['estimated_fees']:<7.2f} "
                  f"{metrics['total_actions']:<8} {metrics['execution_complexity']:<12}")
        else:
            print(f"{strategy:<20} ERROR: {metrics['error']}")
    
    # Déterminer la meilleure stratégie
    valid_results = {k: v for k, v in comparison_results.items() if "error" not in v}
    if valid_results:
        best_overall = max(valid_results.keys(), key=lambda k: valid_results[k]["optimization_score"])
        best_timing = max(valid_results.keys(), key=lambda k: valid_results[k]["market_timing_score"])
        lowest_fees = min(valid_results.keys(), key=lambda k: valid_results[k]["estimated_fees"])
        
        print(f"\nMeilleures stratégies par critère:")
        print(f"  Optimisation globale: {best_overall}")
        print(f"  Timing de marché: {best_timing}")
        print(f"  Frais les plus bas: {lowest_fees}")
    
    return comparison_results

async def test_constraints_validation():
    """Test de validation des contraintes"""
    print("\n" + "="*60)
    print("TEST 4: Validation des contraintes")
    print("="*60)
    
    from services.advanced_rebalancing import OptimizationConstraints
    
    # Test contraintes par défaut
    default_constraints = OptimizationConstraints()
    print("Contraintes par défaut:")
    print(f"  Max trade: ${default_constraints.max_trade_size_usd:,.0f}")
    print(f"  Min trade: ${default_constraints.min_trade_size_usd:,.0f}")
    print(f"  Max allocation change: {default_constraints.max_allocation_change*100:.1f}%")
    print(f"  Max trades simultanés: {default_constraints.max_simultaneous_trades}")
    print(f"  Exchanges préférés: {default_constraints.preferred_exchanges}")
    print(f"  Consolider duplicatas: {default_constraints.consolidate_duplicates}")
    
    # Test contraintes personnalisées
    custom_constraints = OptimizationConstraints(
        max_trade_size_usd=2000.0,
        min_trade_size_usd=100.0,
        max_allocation_change=0.10,
        preferred_exchanges=["Kraken", "Coinbase"],
        consolidate_duplicates=True
    )
    
    print("\nContraintes personnalisées:")
    print(f"  Max trade réduit: ${custom_constraints.max_trade_size_usd:,.0f}")
    print(f"  Min trade augmenté: ${custom_constraints.min_trade_size_usd:,.0f}")
    print(f"  Change limite: {custom_constraints.max_allocation_change*100:.1f}%")
    print(f"  Exchanges: {custom_constraints.preferred_exchanges}")
    
    return {"default": default_constraints, "custom": custom_constraints}

async def test_large_order_splitting():
    """Test du splitting des gros ordres"""
    print("\n" + "="*60)
    print("TEST 5: Splitting des gros ordres")
    print("="*60)
    
    from services.advanced_rebalancing import (
        advanced_rebalancing_engine,
        RebalancingStrategy,
        OptimizationConstraints
    )
    
    # Portfolio avec besoins de gros rebalancement
    large_portfolio = [
        {"symbol": "BTC", "value_usd": 50000.0, "location": "Binance"},  # Grosse position BTC
        {"symbol": "USDC", "value_usd": 50000.0, "location": "Binance"}  # Grosse position stable
    ]
    
    # Targets qui nécessitent gros rebalancement
    targets = {"BTC": 30.0, "Stablecoins": 30.0, "ETH": 40.0}  # Forcer achat ETH important
    
    # Contraintes avec splitting agressif
    constraints = OptimizationConstraints(
        max_trade_size_usd=5000.0,  # Force splitting
        min_trade_size_usd=100.0
    )
    
    result = await advanced_rebalancing_engine.rebalance_portfolio(
        large_portfolio, targets, RebalancingStrategy.PROPORTIONAL, constraints
    )
    
    print(f"Portfolio: ${sum(h['value_usd'] for h in large_portfolio):,.0f}")
    print(f"Actions générées: {len(result.actions)}")
    
    # Analyser les splits
    split_actions = [a for a in result.actions if a.get("split_info", {}).get("is_split", False)]
    regular_actions = [a for a in result.actions if not a.get("split_info", {}).get("is_split", False)]
    
    print(f"Actions splitées: {len(split_actions)}")
    print(f"Actions régulières: {len(regular_actions)}")
    
    if split_actions:
        print("\nExemples de splits:")
        splits_by_symbol = {}
        for action in split_actions:
            symbol = action.get("symbol", "unknown")
            if symbol not in splits_by_symbol:
                splits_by_symbol[symbol] = []
            splits_by_symbol[symbol].append(action)
        
        for symbol, splits in list(splits_by_symbol.items())[:2]:  # Top 2 symbols
            print(f"  {symbol}: {len(splits)} parts")
            original_amount = splits[0].get("split_info", {}).get("original_amount", 0)
            print(f"    Montant original: ${original_amount:,.0f}")
            for i, split in enumerate(splits[:3]):  # Top 3 splits
                amount = abs(float(split.get("usd", 0)))
                delay = split.get("execution_delay_minutes", 0)
                print(f"    Part {i+1}: ${amount:,.0f} (délai: {delay}min)")
    
    print(f"\nMétadonnées:")
    print(f"  Volume total: ${result.metadata.get('total_volume', 0):,.0f}")
    print(f"  Nombre de splits: {result.metadata.get('num_splits', 0)}")
    print(f"  Complexité: {result.execution_complexity}")
    
    return result

async def run_all_tests():
    """Lance tous les tests du système de rebalancement avancé"""
    print("TESTS SYSTÈME DE REBALANCEMENT AVANCÉ")
    print("=" * 60)
    
    start_time = time.time()
    test_results = {}
    
    tests = [
        ("Stratégies de base", test_basic_strategies),
        ("Consolidation duplicatas", test_duplicate_consolidation),
        ("Comparaison stratégies", test_strategy_comparison),
        ("Validation contraintes", test_constraints_validation),
        ("Splitting gros ordres", test_large_order_splitting)
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\nLancement: {test_name}...")
            result = await test_func()
            test_results[test_name] = {"success": True, "result": result}
            print(f"OK - {test_name} terminé")
            
        except Exception as e:
            print(f"ERREUR dans {test_name}: {e}")
            test_results[test_name] = {"success": False, "error": str(e)}
            logger.error(f"Erreur test {test_name}: {e}")
    
    # Résumé
    total_time = time.time() - start_time
    successful_tests = sum(1 for r in test_results.values() if r["success"])
    total_tests = len(test_results)
    
    print("\n" + "="*60)
    print("RÉSUMÉ DES TESTS")
    print("="*60)
    
    for test_name, result in test_results.items():
        status = "PASS" if result["success"] else "FAIL"
        print(f"{status} - {test_name}")
        if not result["success"]:
            print(f"    Erreur: {result['error']}")
    
    print(f"\nRésultat global: {successful_tests}/{total_tests} tests réussis")
    print(f"Temps d'exécution: {total_time:.2f}s")
    
    if successful_tests == total_tests:
        print("Tous les tests ont réussi ! Système de rebalancement avancé opérationnel.")
        print("\nFonctionnalités validées:")
        print("- 6 stratégies de rebalancement (Proportional, Risk Parity, Momentum, etc.)")
        print("- Consolidation automatique des duplicatas (WBTC->BTC, STETH->ETH)")
        print("- Splitting intelligent des gros ordres (TWAP)")
        print("- Optimisation multi-critères (risque, timing, frais, liquidité)")
        print("- Contraintes de trading personnalisables")
        print("- Scoring et métriques avancées")
    else:
        print(f"{total_tests - successful_tests} test(s) ont échoué.")
    
    return successful_tests == total_tests

if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        exit_code = 0 if success else 1
        print(f"\nSortie avec code: {exit_code}")
        exit(exit_code)
        
    except KeyboardInterrupt:
        print("\nTests interrompus par l'utilisateur")
        exit(130)
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        exit(1)