#!/usr/bin/env python3
"""
Test complet du système de classification intelligente des cryptomonnaies

Tests inclus :
- Classification avec scoring de confiance
- Détection de duplicatas et dérivés (WBTC/BTC, STETH/ETH)
- Patterns avancés et auto-classification
- API d'apprentissage avec feedback humain
- Performance et cache
"""

import asyncio
import logging
from typing import List, Dict, Any
import time
from datetime import datetime

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_basic_classification():
    """Test de classification de base avec différents types de tokens"""
    print("\n" + "="*60)
    print("🧪 TEST 1: Classification de base")
    print("="*60)
    
    from services.smart_classification import smart_classification_service
    
    # Tokens de test représentant différents cas
    test_symbols = [
        # Dérivés connus
        "WBTC", "STETH", "WETH", "JUPSOL", "JITOSOL",
        # Patterns évidents
        "USDC", "USDT", "DOGE", "PEPE", 
        # Tokens spécifiques
        "UNI", "AAVE", "RENDER",
        # Token inconnu
        "UNKNOWN_TEST_TOKEN"
    ]
    
    print(f"📝 Classification de {len(test_symbols)} tokens...")
    results = {}
    
    for symbol in test_symbols:
        try:
            result = await smart_classification_service.classify_symbol(symbol)
            results[symbol] = result
            
            print(f"  • {symbol:<20} → {result.suggested_group:<15} "
                  f"({result.confidence_score:>5.1f}% via {result.method})")
            if result.base_symbol:
                print(f"    └─ Dérivé de {result.base_symbol}")
                
        except Exception as e:
            print(f"  ❌ Erreur {symbol}: {e}")
    
    print(f"\n✅ Classification terminée: {len(results)}/{len(test_symbols)} réussies")
    return results

async def test_duplicate_detection():
    """Test de détection des duplicatas dans un portfolio"""
    print("\n" + "="*60)
    print("🔍 TEST 2: Détection de duplicatas")
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
    
    print(f"📊 Analyse d'un portfolio de {len(test_portfolio)} tokens...")
    
    duplicates = smart_classification_service.detect_duplicates_in_portfolio(test_portfolio)
    
    print(f"\n🎯 Duplicatas détectés:")
    for base_symbol, derivatives in duplicates.items():
        print(f"  📈 {base_symbol}:")
        for deriv in derivatives:
            print(f"    ├─ {deriv['symbol']} ({deriv['type']}, confiance: {deriv['confidence']}%)")
            print(f"    │  └─ {deriv['description']}")
    
    if not duplicates:
        print("  ℹ️  Aucun duplicata détecté")
    
    # Calcul de statistiques
    total_base_assets = len(set(test_portfolio) - set().union(*[
        [d["symbol"] for d in derivs] 
        for derivs in duplicates.values()
    ]))
    complexity = (len(test_portfolio) - total_base_assets) / len(test_portfolio) * 100
    
    print(f"\n📊 Analyse du portfolio:")
    print(f"  • Total tokens: {len(test_portfolio)}")
    print(f"  • Assets uniques: {total_base_assets}")
    print(f"  • Score de complexité: {complexity:.1f}%")
    
    return duplicates

async def test_advanced_patterns():
    """Test des patterns avancés pour auto-classification"""
    print("\n" + "="*60)
    print("🎯 TEST 3: Patterns avancés")
    print("="*60)
    
    from services.smart_classification import smart_classification_service
    
    # Test tokens pour chaque catégorie de pattern
    pattern_tests = {
        "Stablecoins": ["BUSD", "TUSD", "FRAX", "GUSD", "DAI"],
        "L2/Scaling": ["ARB", "OP", "MATIC", "STRK", "IMX"],
        "Memecoins": ["BONK", "WIF", "FLOKI", "BABYDOGE", "SAFEMOON"],
        "AI/Data": ["FET", "RENDER", "TAO", "OCEAN", "GRT"],
        "Gaming/NFT": ["AXS", "SAND", "MANA", "ENJ", "GALA"],
        "DeFi": ["UNI", "AAVE", "COMP", "MKR", "SNX"]
    }
    
    pattern_results = {}
    
    for expected_group, symbols in pattern_tests.items():
        print(f"\n🧪 Test patterns pour {expected_group}:")
        group_results = {}
        
        for symbol in symbols:
            try:
                result = await smart_classification_service.classify_symbol(symbol)
                group_results[symbol] = result
                
                # Vérifier si la classification correspond
                correct = result.suggested_group == expected_group
                status = "✅" if correct else "❌"
                
                print(f"  {status} {symbol:<12} → {result.suggested_group:<15} "
                      f"({result.confidence_score:>5.1f}%)")
                
                if not correct:
                    print(f"    └─ Attendu: {expected_group}")
                    
            except Exception as e:
                print(f"  ❌ {symbol}: Erreur {e}")
        
        pattern_results[expected_group] = group_results
        
        # Calcul du taux de réussite pour ce groupe
        correct_count = sum(1 for r in group_results.values() 
                          if r.suggested_group == expected_group)
        success_rate = correct_count / len(group_results) * 100 if group_results else 0
        print(f"  📊 Taux de réussite: {correct_count}/{len(group_results)} ({success_rate:.1f}%)")
    
    return pattern_results

async def test_batch_classification():
    """Test de classification en lot avec performance"""
    print("\n" + "="*60)
    print("⚡ TEST 4: Classification batch et performance")
    print("="*60)
    
    from services.smart_classification import smart_classification_service
    
    # Grande liste de tokens pour test de performance
    batch_symbols = [
        "BTC", "ETH", "SOL", "ADA", "AVAX", "MATIC", "DOT", "UNI", "LINK", "AAVE",
        "WBTC", "STETH", "WETH", "JUPSOL", "USDC", "USDT", "DAI", "BUSD",
        "DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI",
        "RENDER", "FET", "TAO", "OCEAN", "GRT",
        "AXS", "SAND", "MANA", "ENJ", "GALA",
        "ARB", "OP", "STRK", "IMX", "LRC"
    ]
    
    print(f"🚀 Classification batch de {len(batch_symbols)} tokens...")
    
    # Test avec différents seuils de confiance
    confidence_thresholds = [30.0, 50.0, 70.0, 90.0]
    
    for threshold in confidence_thresholds:
        start_time = time.time()
        
        results = await smart_classification_service.classify_symbols_batch(
            batch_symbols, confidence_threshold=threshold
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        classified_count = len(results)
        success_rate = classified_count / len(batch_symbols) * 100
        
        print(f"\n📊 Seuil {threshold}%:")
        print(f"  • Classifiés: {classified_count}/{len(batch_symbols)} ({success_rate:.1f}%)")
        print(f"  • Temps: {duration:.2f}s ({duration/len(batch_symbols)*1000:.1f}ms/token)")
        
        # Distribution par méthode
        method_counts = {}
        confidence_sum = 0
        for result in results.values():
            method_counts[result.method] = method_counts.get(result.method, 0) + 1
            confidence_sum += result.confidence_score
        
        avg_confidence = confidence_sum / len(results) if results else 0
        print(f"  • Confiance moyenne: {avg_confidence:.1f}%")
        print(f"  • Méthodes: {dict(method_counts)}")
    
    return results

async def test_learning_api():
    """Test de l'API d'apprentissage avec feedback humain"""
    print("\n" + "="*60)
    print("🧠 TEST 5: API d'apprentissage")
    print("="*60)
    
    from services.smart_classification import smart_classification_service, ClassificationResult
    from services.taxonomy import Taxonomy
    from datetime import datetime
    
    # Token de test personnalisé
    test_symbol = "CUSTOM_TEST_TOKEN"
    human_classification = "DeFi"
    
    print(f"📚 Test d'apprentissage pour {test_symbol}...")
    
    # 1. Classification initiale (devrait être "Others")
    initial_result = await smart_classification_service.classify_symbol(test_symbol)
    print(f"  📝 Classification initiale: {initial_result.suggested_group} "
          f"({initial_result.confidence_score}% via {initial_result.method})")
    
    # 2. Simulation de feedback humain
    print(f"  🧑‍💻 Feedback humain: {test_symbol} → {human_classification}")
    
    # Mise à jour directe de la taxonomie (simulation de l'API learning)
    taxonomy = Taxonomy.load()
    taxonomy.aliases[test_symbol] = human_classification
    taxonomy.save()
    
    # Invalider le cache
    if test_symbol in smart_classification_service._classification_cache:
        del smart_classification_service._classification_cache[test_symbol]
    
    # 3. Nouvelle classification après apprentissage
    learned_result = await smart_classification_service.classify_symbol(test_symbol)
    print(f"  🎓 Après apprentissage: {learned_result.suggested_group} "
          f"({learned_result.confidence_score}% via {learned_result.method})")
    
    # Vérifier que l'apprentissage a fonctionné
    learning_success = learned_result.suggested_group == human_classification
    print(f"  {'✅' if learning_success else '❌'} Apprentissage: "
          f"{'Réussi' if learning_success else 'Échec'}")
    
    # Nettoyage - retirer le token de test
    if test_symbol in taxonomy.aliases:
        del taxonomy.aliases[test_symbol]
        taxonomy.save()
    
    return learning_success

async def test_system_stats():
    """Test des statistiques du système"""
    print("\n" + "="*60)  
    print("📊 TEST 6: Statistiques système")
    print("="*60)
    
    from services.smart_classification import smart_classification_service
    
    stats = smart_classification_service.get_classification_stats()
    
    print("🔧 Cache et Performance:")
    cache_stats = stats["cache_stats"]
    print(f"  • Symboles en cache: {cache_stats['cached_symbols']}")
    print(f"  • TTL cache: {cache_stats['cache_ttl_hours']:.1f}h")
    
    print("\n🧬 Mappings de dérivés:")
    deriv_stats = stats["derivative_mappings"]
    print(f"  • Total mappings: {deriv_stats['total_mappings']}")
    for base, count in deriv_stats["by_base"].items():
        print(f"  • {base}: {count} dérivés")
    
    print("\n🎯 Performance de classification:")
    perf_stats = stats["classification_performance"]
    print(f"  • Total classifiés: {perf_stats['total_classified']}")
    
    method_counts = perf_stats["method_counts"]
    for method, count in method_counts.items():
        if count > 0:
            print(f"  • Via {method}: {count}")
    
    conf_dist = perf_stats["confidence_distribution"]
    print(f"  • Confiance haute (80%+): {conf_dist['high']}")
    print(f"  • Confiance moyenne (50-80%): {conf_dist['medium']}")
    print(f"  • Confiance faible (<50%): {conf_dist['low']}")
    
    print("\n🔍 Patterns avancés:")
    pattern_stats = stats["advanced_patterns"]
    for group, count in pattern_stats.items():
        print(f"  • {group}: {count} patterns")
    
    return stats

async def run_comprehensive_test():
    """Lance tous les tests du système de classification intelligente"""
    print("🚀 TESTS SYSTÈME DE CLASSIFICATION INTELLIGENTE")
    print("=" * 60)
    
    start_time = time.time()
    test_results = {}
    
    try:
        # Exécuter tous les tests
        tests = [
            ("Classification de base", test_basic_classification),
            ("Détection duplicatas", test_duplicate_detection), 
            ("Patterns avancés", test_advanced_patterns),
            ("Classification batch", test_batch_classification),
            ("API d'apprentissage", test_learning_api),
            ("Statistiques système", test_system_stats)
        ]
        
        for test_name, test_func in tests:
            try:
                print(f"\n🔄 Lancement: {test_name}...")
                result = await test_func()
                test_results[test_name] = {"success": True, "result": result}
                print(f"✅ {test_name} terminé avec succès")
                
            except Exception as e:
                print(f"❌ Erreur dans {test_name}: {e}")
                test_results[test_name] = {"success": False, "error": str(e)}
                logger.error(f"Erreur test {test_name}: {e}", exc_info=True)
        
        # Résumé final
        total_time = time.time() - start_time
        successful_tests = sum(1 for r in test_results.values() if r["success"])
        total_tests = len(test_results)
        
        print("\n" + "="*60)
        print("📋 RÉSUMÉ DES TESTS")
        print("="*60)
        
        for test_name, result in test_results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"{status} - {test_name}")
            if not result["success"]:
                print(f"    └─ Erreur: {result['error']}")
        
        print(f"\n🎯 Résultat global: {successful_tests}/{total_tests} tests réussis")
        print(f"⏱️  Temps d'exécution: {total_time:.2f}s")
        
        if successful_tests == total_tests:
            print("🎉 Tous les tests ont réussi ! Système de classification opérationnel.")
        else:
            print(f"⚠️  {total_tests - successful_tests} test(s) ont échoué.")
        
        return successful_tests == total_tests
        
    except Exception as e:
        logger.error(f"Erreur fatale dans les tests: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(run_comprehensive_test())
        exit_code = 0 if success else 1
        print(f"\n🚪 Sortie avec code: {exit_code}")
        exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n⛔ Tests interrompus par l'utilisateur")
        exit(130)
    except Exception as e:
        logger.error(f"Erreur fatale: {e}", exc_info=True)
        exit(1)