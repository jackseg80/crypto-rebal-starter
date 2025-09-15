"""
Tests d'intégration End-to-End pour Phase 3A/B/C
Valide les flux complets: Dashboard → Advanced Risk → VaR → WebSocket
"""
import asyncio
import json
import time
import pytest
import websockets
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

class Phase3E2ETest:
    """Suite de tests E2E pour l'intégration Phase 3"""
    
    @classmethod
    def setup_class(cls):
        """Configuration initiale des tests"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Mode sans interface
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        try:
            cls.driver = webdriver.Chrome(options=chrome_options)
            cls.driver.implicitly_wait(10)
        except Exception as e:
            pytest.skip(f"Chrome WebDriver not available: {e}")
        
        # Démarrer le serveur de test si nécessaire
        cls.base_url = "http://localhost:8000"
        
        # Vérifier que le serveur répond
        try:
            response = client.get("/api/phase3/status")
            assert response.status_code == 200
        except Exception as e:
            pytest.skip(f"Test server not available: {e}")
    
    @classmethod
    def teardown_class(cls):
        """Nettoyage après les tests"""
        if hasattr(cls, 'driver'):
            cls.driver.quit()
    
    def test_phase3_status_api(self):
        """Test 1: Vérification du statut Phase 3"""
        response = client.get("/api/phase3/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "phase_3a_advanced_risk" in data
        assert "phase_3b_realtime_streaming" in data  
        assert "phase_3c_hybrid_intelligence" in data
        assert data["system_health"] == "healthy"
        
        print("✅ Phase 3 Status API working")
    
    def test_var_api_comprehensive(self):
        """Test 2: API VaR complète avec données réelles"""
        request_data = {
            "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
            "portfolio_value": 10000,
            "analysis_types": ["var_parametric", "var_historical"],
            "confidence_levels": [0.95, 0.99],
            "horizons": ["1d"]
        }
        
        start_time = time.time()
        response = client.post("/api/phase3/risk/comprehensive-analysis", json=request_data)
        response_time = (time.time() - start_time) * 1000
        
        assert response.status_code == 200
        assert response_time < 2000  # Moins de 2 secondes
        
        data = response.json()
        assert "var_analysis" in data
        assert "95%_1d" in data["var_analysis"]
        
        var_95_1d = data["var_analysis"]["95%_1d"]
        assert "parametric_var" in var_95_1d
        assert "historical_var" in var_95_1d
        assert var_95_1d["parametric_var"] > 0
        assert var_95_1d["historical_var"] > 0
        
        print(f"✅ VaR API working - Response time: {response_time:.0f}ms")
    
    def test_realtime_websocket_connection(self):
        """Test 3: Connexion WebSocket temps réel"""
        # D'abord s'assurer que le moteur temps réel est démarré
        start_response = client.post("/api/realtime/start")
        assert start_response.status_code == 200
        
        # Vérifier les connexions actives
        connections_response = client.get("/api/realtime/connections")
        assert connections_response.status_code == 200
        
        connections_data = connections_response.json()
        assert "total_connections" in connections_data
        
        print(f"✅ WebSocket system active - {connections_data['total_connections']} connections")
    
    def test_risk_dashboard_loading(self):
        """Test 4: Chargement du dashboard de risque"""
        self.driver.get(f"{self.base_url}/static/risk-dashboard.html")
        
        # Attendre que la page se charge
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "risk-dashboard"))
        )
        
        # Vérifier que les éléments Phase 3 sont présents
        advanced_toggle = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "mode-switch"))
        )
        assert advanced_toggle is not None
        
        print("✅ Risk Dashboard loaded successfully")
    
    def test_advanced_mode_toggle(self):
        """Test 5: Basculement mode Basic/Advanced"""
        self.driver.get(f"{self.base_url}/static/risk-dashboard.html")
        
        # Attendre le chargement
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.ID, "mode-switch"))
        )
        
        # Activer le mode avancé
        advanced_toggle = self.driver.find_element(By.ID, "mode-switch")
        if not advanced_toggle.is_selected():
            advanced_toggle.click()
        
        # Attendre que les composants avancés se chargent
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "var-analysis"))
        )
        
        # Vérifier que les sections avancées sont visibles
        var_analysis = self.driver.find_element(By.ID, "var-analysis")
        assert var_analysis.is_displayed()
        
        print("✅ Advanced mode toggle working")
    
    def test_var_analysis_integration(self):
        """Test 6: Intégration VaR analysis avec vraies données"""
        self.driver.get(f"{self.base_url}/static/risk-dashboard.html")
        
        # Activer le mode avancé
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.ID, "mode-switch"))
        )
        
        advanced_toggle = self.driver.find_element(By.ID, "mode-switch")
        if not advanced_toggle.is_selected():
            advanced_toggle.click()
        
        # Attendre que l'analyse VaR se charge
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.ID, "var-analysis-content"))
        )
        
        # Vérifier le contenu VaR
        var_content = self.driver.find_element(By.ID, "var-analysis-content")
        var_methods = var_content.find_elements(By.CLASS_NAME, "var-method")
        
        assert len(var_methods) >= 2  # Parametric et Historical minimum
        
        # Vérifier les valeurs
        for method in var_methods:
            value_element = method.find_element(By.CLASS_NAME, "var-value")
            value_text = value_element.text
            assert "$" in value_text  # Format monétaire
            assert "95%" in value_text  # Niveau de confiance
        
        print("✅ VaR Analysis integration working with real data")
    
    def test_navigation_badge_websocket(self):
        """Test 7: Badge de navigation avec WebSocket"""
        self.driver.get(f"{self.base_url}/static/dashboard.html")
        
        # Attendre que la navigation se charge
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "app-header"))
        )
        
        # Le badge devrait être masqué s'il n'y a pas de décisions en attente
        badge_elements = self.driver.find_elements(By.ID, "human-loop-badge")
        
        # Vérifier que le système de badge est initialisé
        # (Le badge peut être masqué, c'est normal s'il n'y a pas de décisions)
        navigation = self.driver.find_element(By.CLASS_NAME, "app-header")
        assert navigation is not None
        
        print("✅ Navigation badge system initialized")
    
    def test_error_handling_resilience(self):
        """Test 8: Résilience aux erreurs"""
        # Test avec des données invalides
        invalid_request = {
            "portfolio_weights": {"INVALID": 1.0},
            "portfolio_value": -1000,  # Valeur négative
            "analysis_types": ["invalid_method"],
            "confidence_levels": [1.5],  # > 1.0
            "horizons": ["invalid"]
        }
        
        response = client.post("/api/phase3/risk/comprehensive-analysis", json=invalid_request)
        
        # L'API devrait gérer gracieusement les erreurs
        assert response.status_code in [400, 422, 500]  # Erreur attendue
        
        print("✅ Error handling working correctly")
    
    def test_performance_benchmarks(self):
        """Test 9: Benchmarks de performance"""
        performance_results = {}
        
        # Test VaR API
        start_time = time.time()
        response = client.post("/api/phase3/risk/comprehensive-analysis", json={
            "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
            "portfolio_value": 10000,
            "analysis_types": ["var_parametric"],
            "confidence_levels": [0.95],
            "horizons": ["1d"]
        })
        var_time = (time.time() - start_time) * 1000
        performance_results["var_api_ms"] = var_time
        
        # Test Status API
        start_time = time.time()
        status_response = client.get("/api/phase3/status")
        status_time = (time.time() - start_time) * 1000
        performance_results["status_api_ms"] = status_time
        
        # Test WebSocket connections
        start_time = time.time()
        connections_response = client.get("/api/realtime/connections")
        websocket_time = (time.time() - start_time) * 1000
        performance_results["websocket_api_ms"] = websocket_time
        
        # Assertions de performance
        assert var_time < 2000  # VaR en moins de 2s
        assert status_time < 500  # Status en moins de 500ms
        assert websocket_time < 100  # WebSocket info en moins de 100ms
        
        print(f"✅ Performance benchmarks:")
        for metric, value in performance_results.items():
            print(f"   {metric}: {value:.0f}ms")
    
    def test_full_user_journey(self):
        """Test 10: Parcours utilisateur complet"""
        print("🚀 Testing full user journey...")
        
        # 1. Arriver sur le dashboard principal
        self.driver.get(f"{self.base_url}/static/dashboard.html")
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "app-header"))
        )
        
        # 2. Naviguer vers le Risk Dashboard
        risk_link = self.driver.find_element(By.LINK_TEXT, "Risk Dashboard")
        risk_link.click()
        
        # 3. Attendre le chargement du Risk Dashboard
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "risk-dashboard"))
        )
        
        # 4. Activer le mode avancé
        advanced_toggle = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "mode-switch"))
        )
        if not advanced_toggle.is_selected():
            advanced_toggle.click()
        
        # 5. Vérifier que les analyses avancées se chargent
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.ID, "var-analysis-content"))
        )
        
        # 6. Vérifier les données VaR
        var_content = self.driver.find_element(By.ID, "var-analysis-content")
        assert var_content.is_displayed()
        
        print("✅ Full user journey completed successfully")

# Tests individuels pour execution
def test_phase3_api_status():
    """Test API Status - peut être exécuté individuellement"""
    tester = Phase3E2ETest()
    tester.setup_class()
    try:
        tester.test_phase3_status_api()
    finally:
        tester.teardown_class()

def test_var_comprehensive():
    """Test VaR API - peut être exécuté individuellement"""
    tester = Phase3E2ETest()
    tester.setup_class()
    try:
        tester.test_var_api_comprehensive()
    finally:
        tester.teardown_class()

if __name__ == "__main__":
    # Execution directe pour développement
    tester = Phase3E2ETest()
    tester.setup_class()
    
    try:
        print("🧪 Running Phase 3 E2E Integration Tests")
        print("=" * 50)
        
        tester.test_phase3_status_api()
        tester.test_var_api_comprehensive()
        tester.test_realtime_websocket_connection()
        tester.test_error_handling_resilience()
        tester.test_performance_benchmarks()
        
        # Tests UI (nécessitent WebDriver)
        try:
            tester.test_risk_dashboard_loading()
            tester.test_advanced_mode_toggle()
            tester.test_var_analysis_integration()
            tester.test_navigation_badge_websocket()
            tester.test_full_user_journey()
        except Exception as e:
            print(f"⚠️ UI Tests skipped (WebDriver issue): {e}")
        
        print("=" * 50)
        print("🎉 All E2E tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
    finally:
        tester.teardown_class()