"""
Tests d'intégration cross-browser pour Phase 3
Valide le fonctionnement sur différents navigateurs
"""
import json
import time
from typing import Dict, Any, List
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.edge.options import Options as EdgeOptions
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class CrossBrowserTest:
    """Tests cross-browser pour Phase 3"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = {}
    
    def get_browser_configs(self) -> List[Dict[str, Any]]:
        """Configuration des navigateurs à tester"""
        configs = []
        
        # Chrome
        try:
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            configs.append({
                "name": "Chrome",
                "driver_class": webdriver.Chrome,
                "options": chrome_options
            })
        except Exception:
            print("Chrome WebDriver not available")
        
        # Firefox
        try:
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("--headless")
            configs.append({
                "name": "Firefox",
                "driver_class": webdriver.Firefox,
                "options": firefox_options
            })
        except Exception:
            print("Firefox WebDriver not available")
        
        # Edge (si disponible)
        try:
            edge_options = EdgeOptions()
            edge_options.add_argument("--headless")
            configs.append({
                "name": "Edge",
                "driver_class": webdriver.Edge,
                "options": edge_options
            })
        except Exception:
            print("Edge WebDriver not available")
        
        return configs
    
    def test_browser_compatibility(self, browser_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test de compatibilité pour un navigateur"""
        browser_name = browser_config["name"]
        print(f"Testing {browser_name} compatibility...")
        
        try:
            # Initialiser le driver
            driver = browser_config["driver_class"](options=browser_config["options"])
            driver.implicitly_wait(10)
            
            results = {
                "browser": browser_name,
                "tests": {},
                "overall_status": "PASS"
            }
            
            # Test 1: Chargement du Risk Dashboard
            try:
                print(f"   {browser_name}: Testing Risk Dashboard loading...")
                start_time = time.time()
                driver.get(f"{self.base_url}/static/risk-dashboard.html")
                
                # Attendre que la page se charge
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "risk-dashboard"))
                )
                load_time = (time.time() - start_time) * 1000
                
                results["tests"]["dashboard_loading"] = {
                    "status": "PASS",
                    "load_time_ms": round(load_time, 1)
                }
                
            except Exception as e:
                results["tests"]["dashboard_loading"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                results["overall_status"] = "FAIL"
            
            # Test 2: Navigation uniforme
            try:
                print(f"   {browser_name}: Testing navigation...")
                nav_header = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "app-header"))
                )
                
                # Vérifier les liens de navigation
                nav_links = driver.find_elements(By.CSS_SELECTOR, ".app-header nav a")
                
                results["tests"]["navigation"] = {
                    "status": "PASS" if len(nav_links) > 0 else "FAIL",
                    "nav_links_count": len(nav_links)
                }
                
            except Exception as e:
                results["tests"]["navigation"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                results["overall_status"] = "FAIL"
            
            # Test 3: Mode Advanced Toggle
            try:
                print(f"   {browser_name}: Testing advanced mode toggle...")
                
                # Chercher le toggle mode avancé
                mode_switch = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "mode-switch"))
                )
                
                # Activer le mode avancé
                if not mode_switch.is_selected():
                    mode_switch.click()
                
                # Vérifier que les composants avancés apparaissent
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "var-analysis"))
                )
                
                results["tests"]["advanced_mode"] = {
                    "status": "PASS",
                    "toggle_functional": True
                }
                
            except Exception as e:
                results["tests"]["advanced_mode"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                results["overall_status"] = "FAIL"
            
            # Test 4: Responsive Design
            try:
                print(f"   {browser_name}: Testing responsive design...")
                
                # Tester différentes tailles d'écran
                sizes = [
                    {"width": 1920, "height": 1080, "name": "desktop"},
                    {"width": 1024, "height": 768, "name": "tablet"},
                    {"width": 375, "height": 667, "name": "mobile"}
                ]
                
                responsive_results = {}
                for size in sizes:
                    driver.set_window_size(size["width"], size["height"])
                    time.sleep(0.5)  # Laisser le CSS s'adapter
                    
                    # Vérifier que la navigation est toujours visible
                    nav_visible = driver.find_element(By.CLASS_NAME, "app-header").is_displayed()
                    responsive_results[size["name"]] = nav_visible
                
                results["tests"]["responsive_design"] = {
                    "status": "PASS" if all(responsive_results.values()) else "PARTIAL",
                    "sizes_tested": responsive_results
                }
                
            except Exception as e:
                results["tests"]["responsive_design"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                results["overall_status"] = "FAIL"
            
            # Test 5: JavaScript Functionality
            try:
                print(f"   {browser_name}: Testing JavaScript functionality...")
                
                # Vérifier que le JavaScript fonctionne
                js_test = driver.execute_script("return typeof window.initUnifiedNav === 'function';")
                
                # Vérifier localStorage
                storage_test = driver.execute_script("""
                    try {
                        localStorage.setItem('test', 'value');
                        return localStorage.getItem('test') === 'value';
                    } catch (e) {
                        return false;
                    }
                """)
                
                results["tests"]["javascript"] = {
                    "status": "PASS" if js_test and storage_test else "FAIL",
                    "nav_function_available": js_test,
                    "localStorage_functional": storage_test
                }
                
            except Exception as e:
                results["tests"]["javascript"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                results["overall_status"] = "FAIL"
            
            # Fermer le driver
            driver.quit()
            
            # Calculer le score de compatibilité
            passed_tests = len([t for t in results["tests"].values() if t["status"] == "PASS"])
            total_tests = len(results["tests"])
            compatibility_score = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            
            results["compatibility_score"] = round(compatibility_score, 1)
            results["tests_passed"] = f"{passed_tests}/{total_tests}"
            
            print(f"   {browser_name}: {compatibility_score:.1f}% compatibility ({passed_tests}/{total_tests} tests passed)")
            
            return results
            
        except Exception as e:
            return {
                "browser": browser_name,
                "overall_status": "ERROR",
                "error": str(e),
                "compatibility_score": 0
            }
    
    def run_cross_browser_tests(self) -> Dict[str, Any]:
        """Exécuter les tests sur tous les navigateurs"""
        if not SELENIUM_AVAILABLE:
            return {
                "error": "Selenium not available - install with: pip install selenium",
                "browsers_tested": 0,
                "overall_compatibility": 0
            }
        
        print("Phase 3 Cross-Browser Compatibility Tests")
        print("=" * 45)
        
        browser_configs = self.get_browser_configs()
        
        if not browser_configs:
            return {
                "error": "No WebDrivers available - please install Chrome/Firefox/Edge WebDrivers",
                "browsers_tested": 0,
                "overall_compatibility": 0
            }
        
        all_results = {
            "browsers": {},
            "summary": {}
        }
        
        compatibility_scores = []
        
        for config in browser_configs:
            try:
                result = self.test_browser_compatibility(config)
                all_results["browsers"][config["name"]] = result
                
                if "compatibility_score" in result:
                    compatibility_scores.append(result["compatibility_score"])
                    
            except Exception as e:
                all_results["browsers"][config["name"]] = {
                    "browser": config["name"],
                    "overall_status": "ERROR",
                    "error": str(e),
                    "compatibility_score": 0
                }
                compatibility_scores.append(0)
        
        # Calculer la compatibilité globale
        overall_compatibility = sum(compatibility_scores) / len(compatibility_scores) if compatibility_scores else 0
        browsers_passed = len([b for b in all_results["browsers"].values() if b.get("overall_status") == "PASS"])
        
        all_results["summary"] = {
            "browsers_tested": len(browser_configs),
            "browsers_passed": browsers_passed,
            "overall_compatibility_pct": round(overall_compatibility, 1),
            "cross_browser_status": "EXCELLENT" if overall_compatibility >= 90 else 
                                  "GOOD" if overall_compatibility >= 70 else 
                                  "NEEDS_WORK"
        }
        
        print("=" * 45)
        print(f"Cross-Browser Tests Completed")
        print(f"Browsers tested: {len(browser_configs)}")
        print(f"Overall compatibility: {overall_compatibility:.1f}%")
        print(f"Status: {all_results['summary']['cross_browser_status']}")
        
        return all_results

def test_cross_browser_compatibility():
    """Point d'entrée pour les tests cross-browser"""
    tester = CrossBrowserTest()
    results = tester.run_cross_browser_tests()
    
    # Sauvegarder les résultats
    with open("phase3_cross_browser_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Cross-browser results saved to: phase3_cross_browser_results.json")
    
    return results

if __name__ == "__main__":
    test_cross_browser_compatibility()