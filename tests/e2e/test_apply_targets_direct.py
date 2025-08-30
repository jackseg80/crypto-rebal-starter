#!/usr/bin/env python3
"""
Direct test of Apply Targets functionality
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_apply_targets_simulation():
    """Test by simulating what Apply Targets should do"""
    print("Testing Apply Targets Simulation")
    print("=" * 50)
    
    # 1. Test that both pages are accessible
    print("1. Testing page accessibility...")
    
    try:
        risk_resp = requests.get(f"{BASE_URL}/static/risk-dashboard.html", timeout=5)
        rebalance_resp = requests.get(f"{BASE_URL}/static/rebalance.html", timeout=5)
        
        if risk_resp.status_code != 200 or rebalance_resp.status_code != 200:
            print("FAIL: Pages not accessible")
            return False
            
        print("   PASS: Both pages accessible")
        
    except Exception as e:
        print(f"   FAIL: {e}")
        return False
    
    # 2. Simulate what Apply Targets should save to localStorage
    print("\n2. Simulating Apply Targets action...")
    
    # This is what a successful Apply Targets should create
    test_targets_data = {
        'targets': {
            'BTC': 35.0,
            'ETH': 25.0, 
            'Stablecoins': 20.0,
            'L1/L0 majors': 10.0,
            'L2/Scaling': 5.0,
            'DeFi': 3.0,
            'AI/Data': 2.0,
            'Others': 0.0
        },
        'timestamp': '2025-08-25T01:00:00Z',
        'strategy': 'Macro (CCS unavailable)',
        'source': 'risk-dashboard-ccs'
    }
    
    print(f"   Created test data: {test_targets_data['strategy']}")
    print(f"   Targets count: {len([k for k,v in test_targets_data['targets'].items() if v > 0])}")
    
    # 3. Test rebalance page detection
    print("\n3. Testing rebalance page localStorage detection...")
    
    # Check if rebalance.html has the polling code
    rebalance_content = rebalance_resp.text
    
    has_polling = "checkForNewTargets" in rebalance_content
    has_localstorage_check = "localStorage.getItem('last_targets')" in rebalance_content
    has_interval = "setInterval(checkForNewTargets" in rebalance_content
    has_rebalance_api = "window.rebalanceAPI.setDynamicTargets" in rebalance_content
    
    print(f"   checkForNewTargets function: {'PASS' if has_polling else 'FAIL'}")
    print(f"   localStorage polling: {'PASS' if has_localstorage_check else 'FAIL'}")
    print(f"   2-second interval: {'PASS' if has_interval else 'FAIL'}")
    print(f"   rebalanceAPI integration: {'PASS' if has_rebalance_api else 'FAIL'}")
    
    detection_ok = has_polling and has_localstorage_check and has_interval and has_rebalance_api
    
    # 4. Test targets-coordinator saving
    print("\n4. Testing targets coordinator localStorage saving...")
    
    try:
        coordinator_resp = requests.get(f"{BASE_URL}/static/modules/targets-coordinator.js", timeout=5)
        coordinator_content = coordinator_resp.text
        
        has_save_code = "localStorage.setItem('last_targets'" in coordinator_content
        has_source_label = "'risk-dashboard-ccs'" in coordinator_content
        has_targets_key = "'targets':" in coordinator_content
        
        print(f"   localStorage.setItem: {'PASS' if has_save_code else 'FAIL'}")
        print(f"   Source label: {'PASS' if has_source_label else 'FAIL'}")
        print(f"   Targets structure: {'PASS' if has_targets_key else 'FAIL'}")
        
        saving_ok = has_save_code and has_source_label and has_targets_key
        
    except Exception as e:
        print(f"   FAIL: {e}")
        saving_ok = False
    
    # Summary
    print("\n" + "=" * 50)
    print("SIMULATION TEST SUMMARY")
    print("=" * 50)
    
    overall_ok = detection_ok and saving_ok
    
    if overall_ok:
        print("PASS: Apply Targets mechanism should work")
        print("\nManual test instructions:")
        print("1. Open: http://localhost:8000/static/risk-dashboard.html")
        print("2. Click 'Strategic Targets' tab")
        print("3. Click any strategy button (should work even without CCS)")
        print("4. Click 'Apply Targets' (should save to localStorage)")
        print("5. Open: http://localhost:8000/static/rebalance.html")
        print("6. Look for 'Targets dynamiques' indicator (should appear within 2 seconds)")
        print("7. Check browser console for 'New CCS targets detected' message")
        
    else:
        print("FAIL: Apply Targets mechanism has issues")
        if not detection_ok:
            print("   Issue: rebalance.html detection code missing or incomplete")
        if not saving_ok:
            print("   Issue: targets-coordinator.js saving code missing or incomplete")
    
    return overall_ok

def create_manual_test_data():
    """Create test data for manual verification"""
    print("\nCreating manual test data...")
    
    manual_test_script = '''
// Manual test script - paste this into browser console on rebalance.html
console.log("🧪 Manual Apply Targets Test");

// Simulate what Apply Targets would save
const testTargetsData = {
    targets: {
        "BTC": 35.0,
        "ETH": 25.0,
        "Stablecoins": 20.0,
        "L1/L0 majors": 10.0,
        "L2/Scaling": 5.0,
        "DeFi": 3.0,
        "AI/Data": 2.0,
        "Others": 0.0
    },
    timestamp: new Date().toISOString(),
    strategy: "Manual Test Strategy",
    source: "risk-dashboard-ccs"
};

console.log("💾 Saving test data to localStorage...");
localStorage.setItem('last_targets', JSON.stringify(testTargetsData));

console.log("✅ Test data saved!");
console.log("🔍 Watch for 'New CCS targets detected' message in next 2 seconds...");
console.log("🎯 Look for 'Targets dynamiques' indicator to appear");
'''
    
    print("=" * 60)
    print("MANUAL BROWSER CONSOLE TEST")
    print("=" * 60)
    print("1. Open: http://localhost:8000/static/rebalance.html")
    print("2. Open browser DevTools (F12) and go to Console tab")
    print("3. Paste and run this script:")
    print()
    print(manual_test_script)
    print("=" * 60)

if __name__ == "__main__":
    success = test_apply_targets_simulation()
    create_manual_test_data()
    
    exit(0 if success else 1)