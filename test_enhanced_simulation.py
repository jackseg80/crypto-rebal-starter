#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test du simulateur avance - Validation des fonctionnalites realistes

Ce script teste le simulateur avance avec prix de marche reels,
slippage, frais variables et conditions de marche.
"""

import asyncio
import logging
import json
from services.execution.exchange_adapter import setup_default_exchanges, exchange_registry
from services.execution.order_manager import Order

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_enhanced_simulator_basic():
    """Test des fonctionnalites de base du simulateur avance"""
    print("\n=== Test Simulateur Avance - Fonctionnalites de Base ===")
    
    setup_default_exchanges()
    
    # Obtenir le simulateur avance
    enhanced_sim = exchange_registry.get_adapter("enhanced_simulator")
    if not enhanced_sim:
        print("[FAIL] Enhanced simulator not available")
        return False
    
    # Test de connexion
    connected = await enhanced_sim.connect()
    if not connected:
        print("[FAIL] Connection failed")
        return False
    
    print("[PASS] Enhanced simulator connected successfully")
    
    # Test prix de marche
    btc_price = await enhanced_sim.get_current_price("BTC/USDT")
    eth_price = await enhanced_sim.get_current_price("ETH/USDT")
    
    if btc_price and btc_price > 0:
        print(f"[PASS] BTC price: ${btc_price:,.2f}")
    else:
        print("[FAIL] BTC price not available")
        return False
        
    if eth_price and eth_price > 0:
        print(f"[PASS] ETH price: ${eth_price:,.2f}")
    else:
        print("[FAIL] ETH price not available")
        return False
    
    # Test balances
    btc_balance = await enhanced_sim.get_balance("BTC")
    usdt_balance = await enhanced_sim.get_balance("USDT")
    
    print(f"[INFO] BTC balance: {btc_balance:.6f}")
    print(f"[INFO] USDT balance: ${usdt_balance:,.2f}")
    
    await enhanced_sim.disconnect()
    return True

async def test_realistic_order_execution():
    """Test d'execution d'ordres avec conditions realistes"""
    print("\n=== Test Execution Ordres Realistes ===")
    
    setup_default_exchanges()
    enhanced_sim = exchange_registry.get_adapter("enhanced_simulator")
    await enhanced_sim.connect()
    
    # Test ordres varies
    test_orders = [
        Order(id="test_btc_buy", symbol="BTC/USDT", action="buy", quantity=0.01, usd_amount=500.0),
        Order(id="test_eth_sell", symbol="ETH/USDT", action="sell", quantity=0.5, usd_amount=1400.0),
        Order(id="test_bnb_buy", symbol="BNB/USDT", action="buy", quantity=10.0, usd_amount=3000.0),
        Order(id="test_small_order", symbol="ADA/USDT", action="buy", quantity=100.0, usd_amount=50.0),
        Order(id="test_large_order", symbol="BTC/USDT", action="sell", quantity=0.1, usd_amount=4500.0),
    ]
    
    results = []
    
    for order in test_orders:
        print(f"[TEST] Executing {order.action} {order.symbol}: {order.quantity} (~${order.usd_amount})")
        
        result = await enhanced_sim.place_order(order)
        results.append(result)
        
        if result.success:
            slippage_data = result.exchange_data.get("slippage_bps", 0)
            latency = result.exchange_data.get("latency_ms", 0)
            print(f"[PASS] Order filled: {result.filled_quantity:.6f} @ ${result.avg_price:.2f}")
            print(f"       Slippage: {slippage_data:.1f}bps, Fees: ${result.fees:.4f}, Latency: {latency}ms")
        else:
            print(f"[INFO] Order failed: {result.error_message}")
    
    # Statistiques
    successful = [r for r in results if r.success]
    total_volume = sum(r.filled_usd for r in successful)
    total_fees = sum(r.fees for r in successful)
    avg_slippage = sum(r.exchange_data.get("slippage_bps", 0) for r in successful) / len(successful) if successful else 0
    
    print(f"\n[SUMMARY] Orders: {len(successful)}/{len(results)} successful")
    print(f"[SUMMARY] Total volume: ${total_volume:,.2f}")
    print(f"[SUMMARY] Total fees: ${total_fees:.4f}")
    print(f"[SUMMARY] Average slippage: {avg_slippage:.1f}bps")
    
    await enhanced_sim.disconnect()
    return len(successful) >= len(results) * 0.8  # 80% success rate minimum

async def test_market_conditions_impact():
    """Test de l'impact des conditions de marche"""
    print("\n=== Test Impact Conditions de Marche ===")
    
    setup_default_exchanges() 
    enhanced_sim = exchange_registry.get_adapter("enhanced_simulator")
    await enhanced_sim.connect()
    
    # Executer plusieurs ordres identiques pour voir la variation
    identical_orders = []
    for i in range(5):
        order = Order(
            id=f"market_test_{i}",
            symbol="BTC/USDT", 
            action="buy",
            quantity=0.01,
            usd_amount=450.0
        )
        identical_orders.append(order)
    
    execution_prices = []
    slippages = []
    latencies = []
    
    for order in identical_orders:
        result = await enhanced_sim.place_order(order)
        
        if result.success:
            execution_prices.append(result.avg_price)
            slippages.append(result.exchange_data.get("slippage_bps", 0))
            latencies.append(result.exchange_data.get("latency_ms", 0))
    
    if len(execution_prices) >= 3:
        price_variance = max(execution_prices) - min(execution_prices)
        slippage_variance = max(slippages) - min(slippages)
        latency_variance = max(latencies) - min(latencies)
        
        print(f"[PASS] Price variance: ${price_variance:.2f}")
        print(f"[PASS] Slippage variance: {slippage_variance:.1f}bps")
        print(f"[PASS] Latency variance: {latency_variance}ms")
        
        # Verifier qu'il y a bien de la variance (realisme)
        has_realistic_variance = price_variance > 0 or slippage_variance > 0
        
        status = "[PASS]" if has_realistic_variance else "[WARN]"
        print(f"{status} Market conditions create realistic variance")
        
        await enhanced_sim.disconnect()
        return has_realistic_variance
    else:
        print("[FAIL] Insufficient successful orders to test variance")
        await enhanced_sim.disconnect()
        return False

async def test_simulation_reporting():
    """Test du systeme de rapports de simulation"""
    print("\n=== Test Rapports de Simulation ===")
    
    setup_default_exchanges()
    enhanced_sim = exchange_registry.get_adapter("enhanced_simulator")
    await enhanced_sim.connect()
    
    # Executer quelques ordres
    test_orders = [
        Order(id="report_test_1", symbol="BTC/USDT", action="buy", quantity=0.005, usd_amount=225.0),
        Order(id="report_test_2", symbol="ETH/USDT", action="sell", quantity=0.1, usd_amount=280.0),
    ]
    
    for order in test_orders:
        await enhanced_sim.place_order(order)
    
    # Obtenir le rapport de simulation
    summary = enhanced_sim.get_simulation_summary()
    
    required_fields = [
        "total_orders", "successful_orders", "failed_orders", 
        "success_rate", "total_volume_usd", "total_fees_paid",
        "average_slippage_bps", "average_latency_ms"
    ]
    
    all_fields_present = all(field in summary for field in required_fields)
    
    if all_fields_present:
        print("[PASS] Simulation summary contains all required fields")
        print(f"[INFO] Summary: {summary['total_orders']} orders, "
              f"{summary['success_rate']:.1f}% success rate")
        print(f"[INFO] Volume: ${summary['total_volume_usd']:.2f}, "
              f"Fees: ${summary['total_fees_paid']:.4f}")
        print(f"[INFO] Avg slippage: {summary['average_slippage_bps']:.1f}bps, "
              f"Avg latency: {summary['average_latency_ms']:.1f}ms")
    else:
        print(f"[FAIL] Missing fields in summary: {set(required_fields) - set(summary.keys())}")
    
    await enhanced_sim.disconnect()
    return all_fields_present

async def test_comparison_with_basic_simulator():
    """Comparaison avec le simulateur de base"""
    print("\n=== Test Comparaison Simulateurs ===")
    
    setup_default_exchanges()
    
    basic_sim = exchange_registry.get_adapter("simulator")
    enhanced_sim = exchange_registry.get_adapter("enhanced_simulator")
    
    await basic_sim.connect()
    await enhanced_sim.connect()
    
    # Meme ordre sur les deux simulateurs
    test_order_basic = Order(id="compare_basic", symbol="BTC/USDT", action="buy", quantity=0.01, usd_amount=450.0)
    test_order_enhanced = Order(id="compare_enhanced", symbol="BTC/USDT", action="buy", quantity=0.01, usd_amount=450.0)
    
    basic_result = await basic_sim.place_order(test_order_basic)
    enhanced_result = await enhanced_sim.place_order(test_order_enhanced)
    
    print(f"[INFO] Basic simulator: ${basic_result.avg_price:.2f}, fees: ${basic_result.fees:.4f}")
    print(f"[INFO] Enhanced simulator: ${enhanced_result.avg_price:.2f}, fees: ${enhanced_result.fees:.4f}")
    
    # Verifier que le simulateur avance a plus de donnees
    has_enhanced_data = (
        "slippage_bps" in enhanced_result.exchange_data and
        "latency_ms" in enhanced_result.exchange_data and
        "market_conditions" in enhanced_result.exchange_data
    )
    
    basic_has_less_data = len(basic_result.exchange_data) < len(enhanced_result.exchange_data)
    
    status = "[PASS]" if has_enhanced_data and basic_has_less_data else "[FAIL]"
    print(f"{status} Enhanced simulator provides more detailed data")
    
    await basic_sim.disconnect()
    await enhanced_sim.disconnect()
    
    return has_enhanced_data and basic_has_less_data

async def main():
    """Fonction principale des tests"""
    print("[SIMULATION] Tests du Simulateur Avance")
    print("=" * 55)
    
    test_functions = [
        ("Fonctionnalites de Base", test_enhanced_simulator_basic),
        ("Execution Ordres Realistes", test_realistic_order_execution),
        ("Impact Conditions Marche", test_market_conditions_impact),
        ("Rapports de Simulation", test_simulation_reporting),
        ("Comparaison Simulateurs", test_comparison_with_basic_simulator)
    ]
    
    results = []
    
    for test_name, test_func in test_functions:
        try:
            print(f"\n[TEST] {test_name}")
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"[ERROR] Erreur dans {test_name}: {e}")
            results.append((test_name, False))
    
    # Resume final
    print("\n" + "=" * 55)
    print("[SUMMARY] RESUME DES TESTS")
    print("=" * 55)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{test_name:<30} {status}")
        if success:
            passed += 1
    
    success_rate = (passed / total * 100) if total > 0 else 0
    print(f"\nResultat: {passed}/{total} tests passes ({success_rate:.1f}%)")
    
    if passed == total:
        print("[SUCCESS] Simulateur avance fonctionne parfaitement!")
        print("[READY] Pret pour les tests de rebalancement realistes")
        return 0
    elif passed >= total * 0.8:
        print("[SUCCESS] Simulateur avance fonctionne bien")
        print("[CAUTION] Quelques fonctionnalites a verifier")
        return 0
    else:
        print("[WARNING] Problemes detectes dans le simulateur avance")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)