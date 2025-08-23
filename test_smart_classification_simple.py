#!/usr/bin/env python3
"""
Test simple du système de classification intelligente - Version sans emojis pour Windows
"""

import asyncio
import logging
from typing import List, Dict, Any
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_basic_classification():
    """Test de classification de base"""
    print("\n" + "="*60)
    print("TEST 1: Classification de base")
    print("="*60)
    
    from services.smart_classification import smart_classification_service
    
    # Tokens de test
    test_symbols = [
        "WBTC", "STETH", "WETH", "JUPSOL",  # Dérivés
        "USDC", "USDT", "DOGE", "PEPE",     # Patterns évidents
        "UNI", "AAVE", "RENDER",            # Tokens spécifiques
        "UNKNOWN_TEST_TOKEN"                # Token inconnu
    ]
    
    print(f"Classification de {len(test_symbols)} tokens...")
    results = {}
    
    for symbol in test_symbols:
        try:
            result = await smart_classification_service.classify_symbol(symbol)
            results[symbol] = result
            
            base_info = f" (derivé de {result.base_symbol})" if result.base_symbol else ""
            print(f"  {symbol:<20} -> {result.suggested_group:<15} "
                  f"({result.confidence_score:>5.1f}% via {result.method}){base_info}")
                
        except Exception as e:
            print(f"  ERREUR {symbol}: {e}")
    
    print(f"\nClassification terminée: {len(results)}/{len(test_symbols)} réussies")
    return results

async def test_duplicate_detection():
    """Test de détection des duplicatas"""
    print("\n" + "="*60)
    print("TEST 2: Détection de duplicatas")
    print("="*60)
    
    from services.smart_classification import smart_classification_service
    
    # Portfolio avec duplicatas intentionnels
    test_portfolio = [
        "BTC", "WBTC", "TBTC",           # Bitcoin et dérivés
        "ETH", "STETH", "WETH", "RETH",   # Ethereum et dérivés
        "SOL", "JUPSOL", "JITOSOL",       # Solana et dérivés
        "USDC", "USDT",                   # Pas de duplicatas pour stables
        "UNI", "DOGE"                     # Autres tokens uniques
    ]
    
    print(f"Analyse d'un portfolio de {len(test_portfolio)} tokens...")
    
    duplicates = smart_classification_service.detect_duplicates_in_portfolio(test_portfolio)
    
    print(f"\nDuplicatas détectés:")
    for base_symbol, derivatives in duplicates.items():
        print(f"  {base_symbol}:")
        for deriv in derivatives:
            print(f"    - {deriv['symbol']} ({deriv['type']}, confiance: {deriv['confidence']}%)")
            print(f"      {deriv['description']}")
    
    if not duplicates:
        print("  Aucun duplicata détecté")
    
    return duplicates

async def test_patterns():
    """Test des patterns avancés"""
    print("\n" + "="*60)
    print("TEST 3: Patterns avancés")
    print("="*60)
    
    from services.smart_classification import smart_classification_service
    
    # Test tokens pour chaque catégorie
    pattern_tests = {
        "Stablecoins": ["BUSD", "TUSD", "FRAX", "GUSD", "DAI"],
        "L2/Scaling": ["ARB", "OP", "MATIC", "STRK", "IMX"],
        "Memecoins": ["BONK", "WIF", "FLOKI", "BABYDOGE"],
        "AI/Data": ["FET", "RENDER", "TAO", "OCEAN", "GRT"],
        "DeFi": ["UNI", "AAVE", "COMP", "MKR", "SNX"]
    }
    
    total_correct = 0
    total_tested = 0
    
    for expected_group, symbols in pattern_tests.items():
        print(f"\nTest patterns pour {expected_group}:")
        correct_count = 0
        
        for symbol in symbols:
            try:
                result = await smart_classification_service.classify_symbol(symbol)
                correct = result.suggested_group == expected_group
                status = "OK" if correct else "FAIL"
                
                print(f"  {status} {symbol:<12} -> {result.suggested_group:<15} "
                      f"({result.confidence_score:>5.1f}%)")
                
                if correct:
                    correct_count += 1
                total_tested += 1
                    
            except Exception as e:
                print(f"  ERREUR {symbol}: {e}")
        
        success_rate = correct_count / len(symbols) * 100
        total_correct += correct_count
        print(f"  Taux de réussite: {correct_count}/{len(symbols)} ({success_rate:.1f}%)")
    
    overall_rate = total_correct / total_tested * 100 if total_tested > 0 else 0
    print(f"\nTaux de réussite global: {total_correct}/{total_tested} ({overall_rate:.1f}%)")
    
    return overall_rate

async def test_batch_classification():
    """Test de classification batch"""
    print("\n" + "="*60)
    print("TEST 4: Classification batch")
    print("="*60)
    
    from services.smart_classification import smart_classification_service
    
    batch_symbols = [
        "BTC", "ETH", "SOL", "ADA", "AVAX", "MATIC", "DOT", "UNI", "LINK", "AAVE",
        "WBTC", "STETH", "WETH", "JUPSOL", "USDC", "USDT", "DAI", "BUSD",
        "DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI",
        "RENDER", "FET", "TAO", "OCEAN", "GRT"
    ]
    
    print(f"Classification batch de {len(batch_symbols)} tokens...")
    
    start_time = time.time()
    results = await smart_classification_service.classify_symbols_batch(
        batch_symbols, confidence_threshold=50.0
    )
    end_time = time.time()
    
    duration = end_time - start_time
    classified_count = len(results)
    success_rate = classified_count / len(batch_symbols) * 100
    
    print(f"Résultats:")
    print(f"  Classifiés: {classified_count}/{len(batch_symbols)} ({success_rate:.1f}%)")
    print(f"  Temps: {duration:.2f}s ({duration/len(batch_symbols)*1000:.1f}ms/token)")
    
    # Distribution par méthode
    method_counts = {}
    confidence_sum = 0
    for result in results.values():
        method_counts[result.method] = method_counts.get(result.method, 0) + 1
        confidence_sum += result.confidence_score
    
    avg_confidence = confidence_sum / len(results) if results else 0
    print(f"  Confiance moyenne: {avg_confidence:.1f}%")
    print(f"  Méthodes: {dict(method_counts)}")
    
    return results

async def test_system_stats():
    """Test des statistiques système"""
    print("\n" + "="*60)
    print("TEST 5: Statistiques système")
    print("="*60)
    
    from services.smart_classification import smart_classification_service
    
    stats = smart_classification_service.get_classification_stats()
    
    print("Cache et Performance:")
    cache_stats = stats["cache_stats"]
    print(f"  Symboles en cache: {cache_stats['cached_symbols']}")
    print(f"  TTL cache: {cache_stats['cache_ttl_hours']:.1f}h")
    
    print("\nMappings de dérivés:")
    deriv_stats = stats["derivative_mappings"]
    print(f"  Total mappings: {deriv_stats['total_mappings']}")
    for base, count in deriv_stats["by_base"].items():
        print(f"  {base}: {count} dérivés")
    
    print("\nPerformance de classification:")
    perf_stats = stats["classification_performance"]
    print(f"  Total classifiés: {perf_stats['total_classified']}")
    
    method_counts = perf_stats["method_counts"]
    for method, count in method_counts.items():
        if count > 0:
            print(f"  Via {method}: {count}")
    
    return stats

async def run_all_tests():
    """Lance tous les tests"""
    print("TESTS SYSTÈME DE CLASSIFICATION INTELLIGENTE")
    print("=" * 60)
    
    start_time = time.time()
    test_results = {}
    
    tests = [
        ("Classification de base", test_basic_classification),
        ("Détection duplicatas", test_duplicate_detection), 
        ("Patterns avancés", test_patterns),
        ("Classification batch", test_batch_classification),
        ("Statistiques système", test_system_stats)
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
        print("Tous les tests ont réussi ! Système opérationnel.")
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