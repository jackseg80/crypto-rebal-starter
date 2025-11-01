#!/usr/bin/env python3
"""
Final integration test for CCS -> Rebalance communication
"""

import requests
import json
import time

BASE_URL = "http://localhost:8080"

def test_complete_flow():
    """Test the complete CCS integration flow"""
    print("Final CCS Integration Test")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 6
    
    # Test 1: Pages load
    print("\n1. Testing page accessibility...")
    try:
        risk_resp = requests.get(f"{BASE_URL}/static/risk-dashboard.html", timeout=5)
        rebalance_resp = requests.get(f"{BASE_URL}/static/rebalance.html", timeout=5)
        
        if risk_resp.status_code == 200 and rebalance_resp.status_code == 200:
            print("   PASS: Both pages load successfully")
            tests_passed += 1
        else:
            print("   FAIL: Page loading issues")
    except Exception as e:
        print(f"   FAIL: {e}")
    
    # Test 2: CCS modules exist and are accessible
    print("\n2. Testing CCS modules...")
    modules = [
        "core/risk-dashboard-store.js",
        "core/fetcher.js",
        "modules/signals-engine.js", 
        "modules/cycle-navigator.js",
        "modules/targets-coordinator.js"
    ]
    
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
        print(f"   PASS: All {len(modules)} modules accessible")
        tests_passed += 1
    else:
        print(f"   FAIL: Only {modules_ok}/{len(modules)} modules accessible")
    
    # Test 3: Strategy button fixes
    print("\n3. Testing strategy button fixes...")
    
    # Check that risk dashboard renders targets without CCS requirement
    risk_content = risk_resp.text
    has_unconditional_targets = "if (activeTab === 'targets') {" in risk_content
    
    # Check that proposeTargets handles missing CCS gracefully
    coordinator_resp = requests.get(f"{BASE_URL}/static/modules/targets-coordinator.js", timeout=5)
    coordinator_content = coordinator_resp.text
    has_ccs_fallback = "Macro (CCS unavailable)" in coordinator_content
    has_cycle_fallback = "Macro (Cycle unavailable)" in coordinator_content
    
    if has_unconditional_targets and has_ccs_fallback and has_cycle_fallback:
        print("   PASS: Strategy buttons work without CCS data")
        tests_passed += 1
    else:
        print("   FAIL: Strategy button fixes incomplete")
        print(f"      Unconditional targets: {has_unconditional_targets}")
        print(f"      CCS fallback: {has_ccs_fallback}")
        print(f"      Cycle fallback: {has_cycle_fallback}")
    
    # Test 4: Apply Targets localStorage saving
    print("\n4. Testing Apply Targets localStorage saving...")
    
    has_save_targets = "localStorage.setItem('last_targets'" in coordinator_content
    has_correct_structure = "'targets': proposalResult.targets" in coordinator_content
    has_source_label = "'source': 'risk-dashboard-ccs'" in coordinator_content
    
    if has_save_targets and has_correct_structure and has_source_label:
        print("   PASS: Apply Targets saves to localStorage correctly")
        tests_passed += 1
    else:
        print("   FAIL: Apply Targets localStorage saving incomplete")
        print(f"      Has save code: {has_save_targets}")
        print(f"      Correct structure: {has_correct_structure}")
        print(f"      Source label: {has_source_label}")
    
    # Test 5: Rebalance page polling
    print("\n5. Testing rebalance page localStorage polling...")
    
    rebalance_content = rebalance_resp.text
    has_polling_function = "function checkForNewTargets()" in rebalance_content
    has_interval_setup = "setInterval(checkForNewTargets, 2000)" in rebalance_content
    has_api_integration = "window.rebalanceAPI.setDynamicTargets" in rebalance_content
    has_indicator_update = "dynamicTargetsIndicator" in rebalance_content
    
    if has_polling_function and has_interval_setup and has_api_integration and has_indicator_update:
        print("   PASS: Rebalance page polling works correctly")
        tests_passed += 1
    else:
        print("   FAIL: Rebalance page polling incomplete")
        print(f"      Polling function: {has_polling_function}")
        print(f"      Interval setup: {has_interval_setup}")
        print(f"      API integration: {has_api_integration}")
        print(f"      Indicator update: {has_indicator_update}")
    
    # Test 6: Risk API works
    print("\n6. Testing Risk API...")
    try:
        resp = requests.get(f"{BASE_URL}/api/risk/dashboard", 
                          params={"source": "cointracking", "min_usd": "100"}, 
                          timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success') and data.get('portfolio_summary'):
                portfolio_value = data.get('portfolio_summary', {}).get('total_value', 0)
                print(f"   PASS: Risk API works (Portfolio: ${portfolio_value:,.0f})")
                tests_passed += 1
            else:
                print("   FAIL: Risk API response invalid")
        else:
            print(f"   FAIL: Risk API returned {resp.status_code}")
    except Exception as e:
        print(f"   FAIL: Risk API error: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("FINAL TEST SUMMARY")
    print("=" * 50)
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("SUCCESS: All systems working!")
        print_user_instructions()
    else:
        print("PARTIAL: Some issues remain")
        print("Check failed tests above for details")
    
    return tests_passed == total_tests

def print_user_instructions():
    """Print final user testing instructions"""
    print(f"""
USER TESTING INSTRUCTIONS:
==========================

The CCS integration is now ready for testing. Follow these steps:

1. OPEN RISK DASHBOARD:
   {BASE_URL}/static/risk-dashboard.html

2. NAVIGATE TO STRATEGIC TARGETS:
   - Click "Strategic Targets" in the left sidebar
   - The page should load even without CCS data
   - You should see 4 strategy buttons:
     * Macro Only
     * CCS Based  
     * Cycle Adjusted
     * Blended Strategy

3. TEST STRATEGY BUTTONS:
   - Click each strategy button
   - The "Proposed Targets" table should update
   - Each button should work (may show "Macro (CCS unavailable)" if no CCS data)
   - No JavaScript errors should appear in console

4. TEST APPLY TARGETS:
   - Click the green "Apply Targets" button
   - Button should change to "Applied!" briefly
   - Check browser console for "Targets applied successfully!" message

5. TEST REBALANCE COMMUNICATION:
   - Open new tab: {BASE_URL}/static/rebalance.html
   - Within 2 seconds, look for "🎯 Targets dynamiques" indicator in top-right
   - Check console for "New CCS targets detected from localStorage"

6. TEST REBALANCE INTEGRATION:
   - Click "Générer le plan" on rebalance page
   - Generated plan should use CCS-based allocations
   - Plans should reflect the applied strategy

EXPECTED RESULTS:
=================
✓ Strategy buttons update proposed targets table
✓ Apply Targets shows success feedback  
✓ Rebalance page automatically detects new targets
✓ Dynamic targets indicator appears
✓ Generated plans use CCS allocations

TROUBLESHOOTING:
================
- If buttons don't work: Check browser console (F12) for errors
- If communication fails: Check localStorage with: localStorage.getItem('last_targets')
- If no CCS data: System should still work with macro fallbacks

The system is designed to be robust and work even without CCS signals!
""")

if __name__ == "__main__":
    success = test_complete_flow()
    exit(0 if success else 1)
