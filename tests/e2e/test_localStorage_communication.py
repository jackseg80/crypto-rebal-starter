#!/usr/bin/env python3
"""
Test CCS -> Rebalance localStorage communication
Simulates the Apply Targets flow end-to-end
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_localStorage_communication():
    """Test the complete localStorage communication flow"""
    print("Testing CCS -> Rebalance localStorage Communication")
    print("=" * 60)
    
    # Test 1: Verify both pages load
    print("\n1. Testing page accessibility...")
    
    try:
        risk_resp = requests.get(f"{BASE_URL}/static/risk-dashboard.html", timeout=5)
        rebalance_resp = requests.get(f"{BASE_URL}/static/rebalance.html", timeout=5)
        
        risk_ok = risk_resp.status_code == 200 and "Strategic Targets" in risk_resp.text
        rebalance_ok = rebalance_resp.status_code == 200 and "dynamicTargetsIndicator" in rebalance_resp.text
        
        print(f"   Risk Dashboard: {'PASS' if risk_ok else 'FAIL'}")
        print(f"   Rebalance Page: {'PASS' if rebalance_ok else 'FAIL'}")
        
        if not (risk_ok and rebalance_ok):
            return False
            
    except Exception as e:
        print(f"   ERROR: {e}")
        return False
    
    # Test 2: Verify CCS modules exist
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
        except:
            pass
    
    print(f"   CCS Modules: {'PASS' if modules_ok == len(modules) else 'FAIL'} ({modules_ok}/{len(modules)})")
    
    if modules_ok != len(modules):
        return False
    
    # Test 3: Verify API works
    print("\n3. Testing Risk API...")
    
    try:
        resp = requests.get(f"{BASE_URL}/api/risk/dashboard", 
                          params={"source": "cointracking", "min_usd": "100"}, 
                          timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            api_ok = data.get('success') is True
            print(f"   Risk API: {'PASS' if api_ok else 'FAIL'}")
            
            if api_ok:
                portfolio_value = data.get('portfolio_summary', {}).get('total_value', 0)
                print(f"   Portfolio Value: ${portfolio_value:,.0f}")
        else:
            print(f"   Risk API: FAIL (HTTP {resp.status_code})")
            api_ok = False
            
    except Exception as e:
        print(f"   Risk API: ERROR - {e}")
        api_ok = False
    
    if not api_ok:
        return False
    
    # Test 4: Check communication implementation
    print("\n4. Verifying communication setup...")
    
    # Check rebalance.html has localStorage polling
    rebalance_has_polling = ("checkForNewTargets" in rebalance_resp.text and 
                           "localStorage.getItem('last_targets')" in rebalance_resp.text and
                           "setInterval(checkForNewTargets" in rebalance_resp.text)
    
    # Check targets-coordinator has localStorage saving
    try:
        coord_resp = requests.get(f"{BASE_URL}/static/modules/targets-coordinator.js", timeout=5)
        coord_has_save = ("localStorage.setItem('last_targets'" in coord_resp.text and
                         "source: 'risk-dashboard-ccs'" in coord_resp.text)
    except:
        coord_has_save = False
    
    print(f"   localStorage polling: {'PASS' if rebalance_has_polling else 'FAIL'}")
    print(f"   localStorage saving: {'PASS' if coord_has_save else 'FAIL'}")
    
    communication_ok = rebalance_has_polling and coord_has_save
    
    # Summary
    print("\n" + "=" * 60)
    print("COMMUNICATION TEST SUMMARY")
    print("=" * 60)
    
    overall_ok = risk_ok and rebalance_ok and (modules_ok == len(modules)) and api_ok and communication_ok
    
    if overall_ok:
        print("SUCCESS: All systems ready for manual testing!")
        print_manual_test_instructions()
    else:
        print("FAILED: Some components failed. Check above results.")
    
    return overall_ok

def print_manual_test_instructions():
    """Print step-by-step manual test instructions"""
    print(f"""
MANUAL TEST INSTRUCTIONS:
========================

1. Open Risk Dashboard:
   {BASE_URL}/static/risk-dashboard.html

2. Navigate to Strategic Targets tab:
   - Click "Strategic Targets" in the sidebar
   - Wait for CCS data to load (should see score and strategy buttons)

3. Test strategy selection:
   - Click one of: "Macro Only", "CCS Based", "Cycle Adjusted", "Blended Strategy"
   - Check that "Proposed Targets" table updates
   - Open browser DevTools (F12) to monitor console

4. Apply targets:
   - Click the green "Apply Targets" button
   - Should see success feedback: "Targets applied successfully!"
   - Check console for confirmation message

5. Test communication:
   - Open second tab: {BASE_URL}/static/rebalance.html
   - Should automatically see "Targets dynamiques" indicator appear
   - Check console for: "New CCS targets detected from localStorage"

6. Verify rebalance integration:
   - Generate a plan on the rebalance page
   - Should use CCS-based allocations instead of defaults
   - Check that allocations match the applied strategy

Expected Results:
[PASS] Strategy buttons update proposed targets
[PASS] Apply Targets shows success message
[PASS] Dynamic targets indicator appears in rebalance.html
[PASS] Generated plans use CCS allocations
[PASS] Console shows communication messages

If any step fails, check browser DevTools console for errors.
""")

if __name__ == "__main__":
    success = test_localStorage_communication()
    exit(0 if success else 1)