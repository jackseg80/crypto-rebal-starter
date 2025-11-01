#!/usr/bin/env python3
"""
Simple validation test for CCS targets communication
"""

import requests
import json

BASE_URL = "http://localhost:8080"

def test_all():
    """Test all components"""
    print("CCS -> Rebalance Communication Validation")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 5
    
    # Test 1: Risk dashboard loads
    try:
        resp = requests.get(f"{BASE_URL}/static/risk-dashboard.html", timeout=5)
        if resp.status_code == 200 and "Strategic Targets" in resp.text:
            print("1. Risk Dashboard: PASS")
            tests_passed += 1
        else:
            print("1. Risk Dashboard: FAIL")
    except Exception as e:
        print(f"1. Risk Dashboard: ERROR - {e}")
    
    # Test 2: Rebalance page loads
    try:
        resp = requests.get(f"{BASE_URL}/static/rebalance.html", timeout=5)
        if resp.status_code == 200 and "dynamicTargetsIndicator" in resp.text:
            print("2. Rebalance Page: PASS")
            tests_passed += 1
        else:
            print("2. Rebalance Page: FAIL")
    except Exception as e:
        print(f"2. Rebalance Page: ERROR - {e}")
    
    # Test 3: CCS modules exist
    modules = ["modules/targets-coordinator.js", "modules/signals-engine.js"]
    modules_ok = 0
    for module in modules:
        try:
            resp = requests.get(f"{BASE_URL}/static/{module}", timeout=5)
            if resp.status_code == 200:
                modules_ok += 1
        except Exception as e:
            print(f"  Warning: Failed to load module {module}: {e}")
            pass
    
    if modules_ok == len(modules):
        print("3. CCS Modules: PASS")
        tests_passed += 1
    else:
        print(f"3. CCS Modules: FAIL ({modules_ok}/{len(modules)})")
    
    # Test 4: Risk API works
    try:
        resp = requests.get(f"{BASE_URL}/api/risk/dashboard", 
                          params={"source": "cointracking", "min_usd": "100"}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'):
                print("4. Risk API: PASS")
                tests_passed += 1
            else:
                print("4. Risk API: FAIL")
        else:
            print(f"4. Risk API: FAIL (HTTP {resp.status_code})")
    except Exception as e:
        print(f"4. Risk API: ERROR - {e}")
    
    # Test 5: Communication setup
    try:
        # Check rebalance.html has event listener
        resp = requests.get(f"{BASE_URL}/static/rebalance.html", timeout=5)
        rebalance_content = resp.text
        has_listener = "addEventListener('targetsUpdated'" in rebalance_content
        
        # Check targets-coordinator has event dispatch
        resp2 = requests.get(f"{BASE_URL}/static/modules/targets-coordinator.js", timeout=5)
        coordinator_content = resp2.text
        has_dispatch = "dispatchEvent(new CustomEvent('targetsUpdated'" in coordinator_content
        
        if has_listener and has_dispatch:
            print("5. Event Communication: PASS")
            tests_passed += 1
        else:
            print("5. Event Communication: FAIL")
    except Exception as e:
        print(f"5. Event Communication: ERROR - {e}")
    
    # Summary
    print("=" * 50)
    print(f"RESULT: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("\nSUCCESS! Ready for manual testing.")
        print_manual_steps()
    else:
        print("\nFAILED! Some components need fixing.")
    
    return tests_passed == total_tests

def print_manual_steps():
    """Print manual testing steps"""
    print("\nMANUAL TEST STEPS:")
    print("1. Open: http://localhost:8080/static/risk-dashboard.html")
    print("2. Go to 'Strategic Targets' tab")
    print("3. Click any strategy button (Macro, CCS, Cycle, Blend)")
    print("4. Click 'Apply Targets' button")
    print("5. Open: http://localhost:8080/static/rebalance.html")
    print("6. Look for 'Targets dynamiques' indicator")
    print("7. Generate plan - should use CCS allocations")

if __name__ == "__main__":
    success = test_all()
    exit(0 if success else 1)
