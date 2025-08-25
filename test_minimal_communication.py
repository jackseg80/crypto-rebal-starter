#!/usr/bin/env python3
"""
Minimal test of localStorage communication
"""

import requests
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def test_with_browser():
    """Test using a real browser to see JavaScript errors"""
    print("🧪 Testing CCS communication with real browser")
    
    # Setup headless Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        
        print("1. Opening risk dashboard...")
        driver.get("http://localhost:8000/static/risk-dashboard.html")
        
        # Wait for page load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "sidebar"))
        )
        
        # Check for JavaScript errors
        logs = driver.get_log('browser')
        errors = [log for log in logs if log['level'] == 'SEVERE']
        
        if errors:
            print("❌ JavaScript errors found:")
            for error in errors:
                print(f"   {error['message']}")
            return False
        else:
            print("✅ No JavaScript errors found")
        
        # Try clicking Strategic Targets tab
        print("2. Clicking Strategic Targets tab...")
        targets_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'Strategic Targets')]")
        targets_tab.click()
        
        # Wait for content to load
        time.sleep(2)
        
        # Check for strategy buttons
        strategy_buttons = driver.find_elements(By.XPATH, "//button[contains(@onclick, 'applyStrategy')]")
        print(f"   Found {len(strategy_buttons)} strategy buttons")
        
        if len(strategy_buttons) > 0:
            print("3. Testing strategy button click...")
            # Try clicking the blend strategy
            blend_button = None
            for btn in strategy_buttons:
                if "blend" in btn.get_attribute("onclick"):
                    blend_button = btn
                    break
            
            if blend_button:
                blend_button.click()
                time.sleep(1)
                
                # Check for new errors after click
                new_logs = driver.get_log('browser')
                new_errors = [log for log in new_logs if log['level'] == 'SEVERE' and log not in logs]
                
                if new_errors:
                    print("❌ Errors after strategy click:")
                    for error in new_errors:
                        print(f"   {error['message']}")
                else:
                    print("✅ Strategy button clicked without errors")
        
        # Check localStorage
        print("4. Checking localStorage...")
        last_targets = driver.execute_script("return localStorage.getItem('last_targets');")
        if last_targets:
            print("✅ Found data in localStorage")
            try:
                data = json.loads(last_targets)
                print(f"   Strategy: {data.get('strategy', 'N/A')}")
                print(f"   Source: {data.get('source', 'N/A')}")
                print(f"   Targets count: {len(data.get('targets', {}))}")
            except:
                print("❌ Invalid JSON in localStorage")
        else:
            print("❌ No data in localStorage")
        
        return True
        
    except Exception as e:
        print(f"❌ Browser test failed: {e}")
        return False
    
    finally:
        if 'driver' in locals():
            driver.quit()

def test_manual_localStorage():
    """Test by manually setting localStorage data"""
    print("\n🧪 Testing manual localStorage communication")
    
    # Create test targets data
    test_targets = {
        'targets': {
            'BTC': 40.0,
            'ETH': 30.0,
            'Stablecoins': 15.0,
            'L1/L0 majors': 10.0,
            'Others': 5.0
        },
        'strategy': 'Test CCS 75',
        'source': 'risk-dashboard-ccs',
        'timestamp': '2025-08-25T00:45:00Z'
    }
    
    print(f"Test data: {json.dumps(test_targets, indent=2)}")
    
    # Simulate the flow by checking if rebalance page can detect this
    print("✅ Manual test data created")
    print("📋 To test manually:")
    print("1. Open browser console on: http://localhost:8000/static/rebalance.html")
    print("2. Run: localStorage.setItem('last_targets', JSON.stringify(" + json.dumps(test_targets) + "))")
    print("3. Wait 2-3 seconds for polling to detect the change")
    print("4. Look for 'New CCS targets detected' message in console")
    print("5. Check if '🎯 Targets dynamiques' indicator appears")
    
    return True

if __name__ == "__main__":
    print("CCS Communication Debug Test")
    print("=" * 50)
    
    # Test 1: Basic connectivity
    try:
        resp = requests.get("http://localhost:8000/static/risk-dashboard.html", timeout=5)
        if resp.status_code != 200:
            print("❌ Server not accessible")
            exit(1)
        print("✅ Server is accessible")
    except:
        print("❌ Cannot reach server")
        exit(1)
    
    # Test 2: Try browser test (requires Chrome)
    try:
        success = test_with_browser()
    except ImportError:
        print("⚠️ Selenium not available, skipping browser test")
        success = True
    except Exception as e:
        print(f"⚠️ Browser test failed: {e}")
        success = True
    
    # Test 3: Manual test instructions
    test_manual_localStorage()
    
    print("\n" + "=" * 50)
    print("🎯 RECOMMENDATION:")
    print("Open browser DevTools (F12) and check Console tab for JavaScript errors")
    print("Navigate to http://localhost:8000/static/risk-dashboard.html")
    print("Click Strategic Targets tab and look for error messages")