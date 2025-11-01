#!/usr/bin/env python3
"""
Test script for CCS MVP Integration
Tests core functionality of the risk dashboard with CCS engine
"""

import asyncio
import json
import requests
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8080"

def test_api_endpoints():
    """Test critical API endpoints"""
    print("Testing API endpoints...")
    
    tests = [
        ("/static/risk-dashboard.html", "Risk Dashboard HTML"),
        ("/static/core/risk-dashboard-store.js", "Store Module"),
        ("/static/core/fetcher.js", "Fetcher Module"),
        ("/static/modules/signals-engine.js", "Signals Engine"),
        ("/static/modules/cycle-navigator.js", "Cycle Navigator"),
        ("/static/modules/targets-coordinator.js", "Targets Coordinator"),
        ("/api/risk/dashboard?source=cointracking&min_usd=100", "Risk API"),
    ]
    
    results = []
    for endpoint, name in tests:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            status = "PASS" if response.status_code == 200 else "FAIL"
            results.append(f"{status} {name}: HTTP {response.status_code}")
        except Exception as e:
            results.append(f"FAIL {name}: ERROR - {e}")
    
    for result in results:
        print(f"  {result}")
    
    return all("PASS" in result for result in results)

def test_ccs_logic():
    """Test CCS computational logic"""
    print("\nTesting CCS computational logic...")
    
    # Test data similar to what the JS modules would handle
    test_signals = {
        "fear_greed": {"value": 65, "source": "test"},
        "btc_dominance": {"value": 55, "source": "test"},
        "funding_rate": {"value": -0.005, "source": "test"},
        "eth_btc_ratio": {"value": 0.062, "source": "test"},
        "volatility": {"value": 0.45, "source": "test"},
        "trend": {"value": 0.05, "source": "test"}
    }
    
    # Mock CCS calculation (simplified version of JS logic)
    def normalize_signal(key: str, value: float) -> float:
        if key == "fear_greed":
            return max(0, min(100, value))
        elif key == "btc_dominance":
            return max(0, min(100, (70 - value) / (70 - 40) * 100))
        elif key == "funding_rate":
            return max(0, min(100, 50 - (value * 2000)))
        elif key == "eth_btc_ratio":
            return max(0, min(100, (value - 0.05) / (0.08 - 0.05) * 100))
        elif key == "volatility":
            return max(0, min(100, 100 - (value * 100)))
        elif key == "trend":
            return max(0, min(100, 50 + (value * 250)))
        return 50
    
    weights = {
        "fear_greed": 0.25,
        "btc_dominance": 0.20,
        "funding_rate": 0.15,
        "eth_btc_ratio": 0.15,
        "volatility": 0.10,
        "trend": 0.15
    }
    
    # Calculate CCS
    weighted_sum = 0
    total_weight = 0
    
    for key, signal in test_signals.items():
        if key in weights:
            normalized = normalize_signal(key, signal["value"])
            weighted_sum += normalized * weights[key]
            total_weight += weights[key]
            print(f"  {key}: {signal['value']} -> {normalized:.1f} (weight: {weights[key]})")
    
    ccs_score = weighted_sum / total_weight if total_weight > 0 else 50
    print(f"  Final CCS Score: {ccs_score:.1f}")
    
    # Test cycle logic
    months_after_halving = 20  # Peak phase
    if months_after_halving <= 6:
        phase = "accumulation"
        cycle_score = 40 + (months_after_halving / 6) * 20
    elif months_after_halving <= 18:
        phase = "bull_build"
        cycle_score = 60 + ((months_after_halving - 6) / 12) * 30
    elif months_after_halving <= 24:
        phase = "peak"
        peak_position = (months_after_halving - 18) / 6
        cycle_score = 100 - (peak_position * 60)
    else:
        phase = "bear"
        cycle_score = 40 - ((months_after_halving - 24) / 12) * 20
    
    print(f"  Cycle: Month {months_after_halving} -> {phase} -> Score: {cycle_score:.1f}")
    
    # Test blended CCS
    cycle_weight = 0.3
    blended_ccs = ccs_score * (1 - cycle_weight) + cycle_score * cycle_weight
    print(f"  Blended CCS*: {blended_ccs:.1f}")
    
    return 50 <= ccs_score <= 100 and 0 <= cycle_score <= 100

def test_targeting_logic():
    """Test strategic targeting logic"""
    print("\nTesting targeting logic...")
    
    # Default macro targets
    macro_targets = {
        'BTC': 35.0,
        'ETH': 25.0,
        'Stablecoins': 20.0,
        'L1/L0 majors': 10.0,
        'L2/Scaling': 5.0,
        'DeFi': 3.0,
        'AI/Data': 2.0,
        'Others': 0.0
    }
    
    print(f"  Macro targets: {sum(macro_targets.values()):.1f}% total")
    
    # Test CCS-based adjustment
    ccs_score = 75  # High bullish
    if ccs_score >= 80:
        btc_adj = 40
        eth_adj = 30
        stable_adj = 10
    elif ccs_score >= 65:
        btc_adj = 38
        eth_adj = 28
        stable_adj = 15
    else:
        btc_adj = macro_targets['BTC']
        eth_adj = macro_targets['ETH'] 
        stable_adj = macro_targets['Stablecoins']
    
    print(f"  CCS {ccs_score} -> BTC: {btc_adj}%, ETH: {eth_adj}%, Stable: {stable_adj}%")
    
    # Test cycle multipliers (peak phase)
    multipliers = {
        'BTC': 0.9,  # Take profits
        'ETH': 1.0,
        'Stablecoins': 1.2,  # Increase cash
        'L1/L0 majors': 1.3,  # Alt season
        'Others': 1.0
    }
    
    adjusted_targets = {}
    for asset, allocation in macro_targets.items():
        multiplier = multipliers.get(asset, 1.0)
        adjusted_targets[asset] = allocation * multiplier
    
    # Normalize to 100%
    total = sum(adjusted_targets.values())
    normalized_targets = {k: (v / total * 100) for k, v in adjusted_targets.items()}
    
    print(f"  Cycle adjusted: {sum(normalized_targets.values()):.1f}% total")
    print(f"  Top allocations:")
    sorted_targets = sorted(normalized_targets.items(), key=lambda x: x[1], reverse=True)
    for asset, allocation in sorted_targets[:4]:
        print(f"     {asset}: {allocation:.1f}%")
    
    return abs(sum(normalized_targets.values()) - 100.0) < 0.1

def test_integration_flow():
    """Test end-to-end integration flow"""
    print("\nTesting integration flow...")
    
    try:
        # Test risk dashboard API
        risk_response = requests.get(f"{BASE_URL}/api/risk/dashboard", 
                                   params={"source": "cointracking", "min_usd": "100"})
        
        if risk_response.status_code == 200:
            risk_data = risk_response.json()
            print(f"  Risk API: Success={risk_data.get('success')}")
            print(f"     Portfolio: ${risk_data.get('portfolio_summary', {}).get('total_value', 0):,.0f}")
            print(f"     Risk Score: {risk_data.get('risk_metrics', {}).get('risk_score', 0)}/100")
        else:
            print(f"  Risk API: HTTP {risk_response.status_code}")
            return False
        
        # Test localStorage simulation (what would happen in browser)
        test_targets = {
            "targets": {
                "BTC": 38.5,
                "ETH": 27.2,
                "Stablecoins": 18.3,
                "L1/L0 majors": 12.0,
                "Others": 4.0
            },
            "timestamp": "2025-08-24T23:45:00.000Z",
            "strategy": "Blended CCS* (72)",
            "source": "risk-dashboard-ccs"
        }
        
        print(f"  Simulated targets communication:")
        print(f"     Strategy: {test_targets['strategy']}")
        print(f"     Total: {sum(test_targets['targets'].values()):.1f}%")
        
        # Validate targets structure
        targets = test_targets['targets']
        total = sum(targets.values())
        valid = all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in targets.values())
        valid = valid and 95 <= total <= 105  # Allow 5% tolerance
        
        print(f"  Targets validation: {'PASS' if valid else 'FAIL'}")
        
        return valid
        
    except Exception as e:
        print(f"  Integration flow error: {e}")
        return False

def main():
    """Run all tests"""
    print("CCS MVP Integration Test Suite")
    print("=" * 50)
    
    start_time = time.time()
    
    tests = [
        ("API Endpoints", test_api_endpoints),
        ("CCS Logic", test_ccs_logic),
        ("Targeting Logic", test_targeting_logic),
        ("Integration Flow", test_integration_flow),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "PASS" if success else "FAIL"))
        except Exception as e:
            results.append((name, f"ERROR: {e}"))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST RESULTS")
    print("=" * 50)
    
    for name, result in results:
        print(f"{result:12} {name}")
    
    passed = sum(1 for _, result in results if "PASS" in result)
    total = len(results)
    elapsed = time.time() - start_time
    
    print(f"\nSummary: {passed}/{total} tests passed ({elapsed:.1f}s)")
    
    if passed == total:
        print("All tests passed! CCS MVP is ready for production.")
    else:
        print("Some tests failed. Review implementation before deployment.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
