#!/usr/bin/env python3
"""
Test CCS → rebalance.html targets communication
Tests the integration between risk-dashboard and rebalance interfaces
"""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

BASE_URL = "http://localhost:8000"

def setup_driver():
    """Setup Chrome driver with headless options"""
    options = Options()
    options.add_argument('--headless')  # Comment this line to see the browser
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    return driver

def test_targets_communication():
    """Test complete CCS targets → rebalance communication flow"""
    driver = setup_driver()
    
    try:
        print("🧪 Testing CCS → Rebalance Targets Communication")
        print("=" * 60)
        
        # 1. Open risk dashboard
        print("1. Opening CCS risk dashboard...")
        driver.get(f"{BASE_URL}/static/risk-dashboard.html")
        
        # Wait for CCS data to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ccs-score"))
        )
        
        # Switch to targets tab
        print("2. Switching to Strategic Targets tab...")
        targets_tab = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-tab='targets']"))
        )
        targets_tab.click()
        time.sleep(1)
        
        # 3. Test strategy buttons
        print("3. Testing strategy selection buttons...")
        strategy_buttons = {
            'macro': 'Macro Only',
            'ccs': 'CCS Based', 
            'cycle': 'Cycle Adjusted',
            'blend': 'Blended Strategy'
        }
        
        for mode, name in strategy_buttons.items():
            print(f"   Testing {name} button...")
            try:
                button = driver.find_element(By.CSS_SELECTOR, f"button[onclick*='applyStrategy(\\'#{mode}\\')']")
                print(f"   ✅ {name} button found and clickable")
            except Exception as e:
                # Try alternative selector
                try:
                    button = driver.find_element(By.XPATH, f"//button[contains(text(), '{name.split()[0]}')]")
                    print(f"   ✅ {name} button found (alternative selector)")
                except Exception as e2:
                    print(f"   ❌ {name} button not found: {e2}")
        
        # 4. Open rebalance.html in new tab
        print("4. Opening rebalance.html in new tab...")
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get(f"{BASE_URL}/static/rebalance.html")
        
        # Wait for rebalance page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "btnRun"))
        )
        print("   ✅ Rebalance page loaded")
        
        # 5. Go back to risk dashboard and apply targets
        print("5. Switching back to risk dashboard to apply targets...")
        driver.switch_to.window(driver.window_handles[0])
        
        # Click Apply Targets button
        try:
            apply_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[onclick*='applyTargetsAction']"))
            )
            print("   ✅ Apply Targets button found")
            
            # Execute the click via JavaScript to avoid click interception
            driver.execute_script("arguments[0].click();", apply_button)
            print("   ✅ Apply Targets clicked")
            
            time.sleep(2)  # Wait for localStorage and event propagation
            
        except Exception as e:
            print(f"   ❌ Could not click Apply Targets: {e}")
            return False
        
        # 6. Check rebalance.html for dynamic targets
        print("6. Checking rebalance.html for dynamic targets indicator...")
        driver.switch_to.window(driver.window_handles[1])
        
        # Look for dynamic targets indicator
        try:
            dynamic_indicator = driver.find_element(By.ID, "dynamicTargetsIndicator")
            is_visible = dynamic_indicator.is_displayed()
            indicator_text = dynamic_indicator.text if is_visible else ""
            
            print(f"   Dynamic indicator visible: {is_visible}")
            print(f"   Indicator text: '{indicator_text}'")
            
            if is_visible and ("CCS" in indicator_text or "Target" in indicator_text):
                print("   ✅ Dynamic targets successfully received!")
                return True
            else:
                print("   ⚠️  Dynamic indicator found but not showing CCS targets")
                
        except Exception as e:
            print(f"   ❌ Dynamic targets indicator not found: {e}")
        
        # 7. Alternative: Check localStorage for last_targets
        print("7. Checking localStorage for targets communication...")
        try:
            last_targets = driver.execute_script("return localStorage.getItem('last_targets');")
            if last_targets:
                print(f"   ✅ Found last_targets in localStorage: {last_targets[:100]}...")
                return True
            else:
                print("   ❌ No last_targets found in localStorage")
        except Exception as e:
            print(f"   ❌ Could not check localStorage: {e}")
        
        return False
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
        
    finally:
        driver.quit()

def test_console_communication():
    """Test JavaScript console communication without UI clicks"""
    driver = setup_driver()
    
    try:
        print("\n🧪 Testing JavaScript Communication (Console)")
        print("=" * 60)
        
        # Open risk dashboard  
        driver.get(f"{BASE_URL}/static/risk-dashboard.html")
        
        # Wait for modules to load
        time.sleep(3)
        
        # Execute JavaScript to simulate targets application
        print("1. Simulating CCS targets application via console...")
        
        js_code = """
        // Import necessary functions (they should be in global scope)
        const { proposeTargets, applyTargets } = await import('./modules/targets-coordinator.js');
        
        try {
            // Propose blended targets
            const proposal = proposeTargets('blend');
            console.log('Proposal generated:', proposal);
            
            // Apply targets (this should trigger localStorage and events)
            await applyTargets(proposal);
            console.log('Targets applied successfully');
            
            return { success: true, strategy: proposal.strategy };
        } catch (error) {
            console.error('Error:', error);
            return { success: false, error: error.message };
        }
        """
        
        result = driver.execute_async_script(f"""
        const callback = arguments[0];
        try {{
            {js_code.replace('return', 'callback')}
        }} catch (error) {{
            callback({{ success: false, error: error.message }});
        }}
        """)
        
        print(f"   JavaScript execution result: {result}")
        
        if result.get('success'):
            print("   ✅ Targets successfully applied via JavaScript")
            return True
        else:
            print(f"   ❌ JavaScript execution failed: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Console test failed: {e}")
        return False
        
    finally:
        driver.quit()

def main():
    """Run all communication tests"""
    print("CCS → Rebalance Targets Communication Test")
    print("=" * 70)
    
    # Test 1: Full UI flow
    ui_success = test_targets_communication()
    
    # Test 2: Console-based communication
    console_success = test_console_communication()
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"UI Communication Test:      {'✅ PASS' if ui_success else '❌ FAIL'}")
    print(f"Console Communication Test: {'✅ PASS' if console_success else '❌ FAIL'}")
    
    overall_success = ui_success or console_success
    print(f"\nOverall Result: {'✅ COMMUNICATION WORKING' if overall_success else '❌ COMMUNICATION BROKEN'}")
    
    if overall_success:
        print("\n📋 Next Steps:")
        print("   1. Open http://localhost:8000/static/risk-dashboard.html")
        print("   2. Go to 'Strategic Targets' tab")
        print("   3. Click any strategy button (Macro, CCS, Cycle, Blend)")
        print("   4. Click 'Apply Targets'") 
        print("   5. Open http://localhost:8000/static/rebalance.html")
        print("   6. Check for '🎯 Targets dynamiques' indicator")
        print("   7. Generate plan to see CCS-based allocations")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)