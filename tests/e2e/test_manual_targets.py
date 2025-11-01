#!/usr/bin/env python3
"""
Manual test for CCS targets communication
Simple validation of the integration components
"""

import requests
import json

BASE_URL = "http://localhost:8080"

def test_pages_load():
    """Test that both pages load correctly"""
    print("Testing page accessibility...")
    
    # Test risk dashboard
    try:
        resp = requests.get(f"{BASE_URL}/static/risk-dashboard.html", timeout=5)
        risk_ok = resp.status_code == 200 and "Strategic Targets" in resp.text
        print(f"   Risk Dashboard: {'✅' if risk_ok else '❌'} (HTTP {resp.status_code})")
    except Exception as e:
        print(f"   Risk Dashboard: ❌ Error - {e}")
        risk_ok = False
    
    # Test rebalance page
    try:
        resp = requests.get(f"{BASE_URL}/static/rebalance.html", timeout=5)
        rebalance_ok = resp.status_code == 200 and "dynamicTargetsIndicator" in resp.text
        print(f"   Rebalance Page: {'✅' if rebalance_ok else '❌'} (HTTP {resp.status_code})")
    except Exception as e:
        print(f"   Rebalance Page: ❌ Error - {e}")
        rebalance_ok = False
    
    return risk_ok and rebalance_ok

def test_modules_exist():
    """Test that CCS modules are accessible"""
    print("\n🧪 Testing CCS modules accessibility...")
    
    modules = [
        "core/risk-dashboard-store.js",
        "core/fetcher.js", 
        "modules/signals-engine.js",
        "modules/cycle-navigator.js",
        "modules/targets-coordinator.js"
    ]
    
    all_ok = True
    for module in modules:
        try:
            resp = requests.get(f"{BASE_URL}/static/{module}", timeout=5)
            module_ok = resp.status_code == 200
            print(f"   {module}: {'✅' if module_ok else '❌'} (HTTP {resp.status_code})")
            all_ok = all_ok and module_ok
        except Exception as e:
            print(f"   {module}: ❌ Error - {e}")
            all_ok = False
    
    return all_ok

def test_api_integration():
    """Test that the risk API is working"""
    print("\n🧪 Testing API integration...")
    
    try:
        resp = requests.get(f"{BASE_URL}/api/risk/dashboard", 
                          params={"source": "cointracking", "min_usd": "100"}, 
                          timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            api_ok = data.get('success') is True
            print(f"   Risk API: {'✅' if api_ok else '❌'} (success: {data.get('success')})")
            
            if api_ok:
                portfolio_value = data.get('portfolio_summary', {}).get('total_value', 0)
                print(f"   Portfolio Value: ${portfolio_value:,.0f}")
                return True
        else:
            print(f"   Risk API: ❌ HTTP {resp.status_code}")
            
    except Exception as e:
        print(f"   Risk API: ❌ Error - {e}")
    
    return False

def check_communication_setup():
    """Check if communication setup is correct"""
    print("\n🧪 Checking communication setup...")
    
    # Check if rebalance.html has targetsUpdated listener
    try:
        resp = requests.get(f"{BASE_URL}/static/rebalance.html", timeout=5)
        rebalance_content = resp.text
        
        has_listener = "addEventListener('targetsUpdated'" in rebalance_content
        has_rebalance_api = "window.rebalanceAPI" in rebalance_content
        has_dynamic_indicator = "dynamicTargetsIndicator" in rebalance_content
        
        print(f"   targetsUpdated listener: {'✅' if has_listener else '❌'}")
        print(f"   rebalanceAPI interface: {'✅' if has_rebalance_api else '❌'}")
        print(f"   Dynamic indicator element: {'✅' if has_dynamic_indicator else '❌'}")
        
        comm_ok = has_listener and has_rebalance_api and has_dynamic_indicator
        
    except Exception as e:
        print(f"   Communication check: ❌ Error - {e}")
        comm_ok = False
    
    # Check if targets-coordinator has event dispatch
    try:
        resp = requests.get(f"{BASE_URL}/static/modules/targets-coordinator.js", timeout=5)
        coordinator_content = resp.text
        
        has_event_dispatch = "dispatchEvent(new CustomEvent('targetsUpdated'" in coordinator_content
        has_localstorage = "localStorage.setItem('last_targets'" in coordinator_content
        
        print(f"   Event dispatch: {'✅' if has_event_dispatch else '❌'}")
        print(f"   localStorage targets: {'✅' if has_localstorage else '❌'}")
        
        coord_ok = has_event_dispatch and has_localstorage
        
    except Exception as e:
        print(f"   Coordinator check: ❌ Error - {e}")
        coord_ok = False
    
    return comm_ok and coord_ok

def print_manual_test_steps():
    """Print manual testing steps"""
    print("\n" + "=" * 70)
    print("📋 MANUAL TEST INSTRUCTIONS")
    print("=" * 70)
    print("Follow these steps to test the CCS -> Rebalance communication:")
    print()
    print("1. 🔗 Open risk dashboard:")
    print(f"   {BASE_URL}/static/risk-dashboard.html")
    print()
    print("2. 📊 Navigate to Strategic Targets:")
    print("   - Click the 'Strategic Targets' tab")
    print("   - Wait for CCS data to load")
    print()
    print("3. 🎯 Test strategy buttons:")
    print("   - Try clicking: 'Macro Only', 'CCS Based', 'Cycle Adjusted', 'Blended Strategy'")
    print("   - Each should update the 'Proposed Targets' table")
    print("   - Check console (F12) for any JavaScript errors")
    print()
    print("4. ✅ Apply targets:")
    print("   - Click the green 'Apply Targets' button")
    print("   - Should see success feedback")
    print("   - Check console for 'Targets applied successfully' message")
    print()
    print("5. 🔄 Open rebalance page:")
    print(f"   {BASE_URL}/static/rebalance.html")
    print()
    print("6. 🎯 Check for dynamic targets:")
    print("   - Look for '🎯 Targets dynamiques' indicator in top-right")
    print("   - Should show CCS score if communication worked")
    print("   - Generate a plan to see CCS-based allocations")
    print()
    print("7. 🔍 Alternative verification:")
    print("   - Open browser DevTools (F12)")
    print("   - Check localStorage: localStorage.getItem('last_targets')")
    print("   - Should contain JSON with targets and strategy info")
    print()
    print("Expected behavior:")
    print("  ✅ Strategy buttons change the proposed targets")
    print("  ✅ Apply Targets shows success feedback")
    print("  ✅ Rebalance page shows '🎯 Targets dynamiques' indicator")
    print("  ✅ Generated plan uses CCS-based allocations instead of defaults")

def main():
    """Run all validation tests"""
    print("CCS -> Rebalance Targets Communication Validation")
    print("=" * 70)
    
    pages_ok = test_pages_load()
    modules_ok = test_modules_exist() 
    api_ok = test_api_integration()
    comm_ok = check_communication_setup()
    
    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Pages Load:           {'✅ PASS' if pages_ok else '❌ FAIL'}")
    print(f"CCS Modules:          {'✅ PASS' if modules_ok else '❌ FAIL'}")
    print(f"API Integration:      {'✅ PASS' if api_ok else '❌ FAIL'}")
    print(f"Communication Setup:  {'✅ PASS' if comm_ok else '❌ FAIL'}")
    
    overall_ok = pages_ok and modules_ok and api_ok and comm_ok
    print(f"\nOverall Status: {'✅ READY FOR TESTING' if overall_ok else '❌ NEEDS FIXES'}")
    
    if overall_ok:
        print_manual_test_steps()
    else:
        print("\n❌ Some components are not working. Check the failed items above.")
    
    return overall_ok

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
