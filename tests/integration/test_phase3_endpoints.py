"""
Tests d'intégration pour les endpoints Phase 3A/B/C

Vérifie que tous les endpoints Phase 3 renvoient 200 OK au lieu de 404
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_phase3_status_endpoint():
    """Test que l'endpoint status fonctionne"""
    response = client.get("/api/phase3/status")
    assert response.status_code == 200
    
    data = response.json()
    assert "phase_3a_advanced_risk" in data
    assert "phase_3b_realtime_streaming" in data
    assert "phase_3c_hybrid_intelligence" in data
    assert "unified_orchestration" in data
    assert "system_health" in data

def test_phase3_health_comprehensive():
    """Test que l'endpoint health comprehensive fonctionne"""
    response = client.get("/api/phase3/health/comprehensive")
    assert response.status_code == 200
    
    data = response.json()
    assert "overall_status" in data
    assert "components" in data
    assert "summary" in data
    # Vérifier que nous avons des composants healthy
    assert data["summary"]["healthy_components"] >= 3

def test_phase3_streaming_connections():
    """Test que l'endpoint streaming fonctionne"""
    response = client.get("/api/phase3/streaming/active-connections")
    assert response.status_code == 200
    
    data = response.json()
    assert "active_websocket_connections" in data
    assert "redis_streams_active" in data

def test_phase3_intelligence_human_decisions():
    """Test que l'endpoint human decisions fonctionne"""
    response = client.get("/api/phase3/intelligence/human-decisions")
    assert response.status_code == 200
    
    data = response.json()
    assert "pending_decisions" in data
    assert "decision_queue_depth" in data

def test_phase3_learning_insights():
    """Test que l'endpoint learning insights fonctionne"""
    response = client.get("/api/phase3/learning/insights")
    assert response.status_code == 200
    
    data = response.json()
    assert "learning_insights" in data
    assert "active_patterns" in data

def test_phase3_health_alerts():
    """Test que l'endpoint health alerts fonctionne"""
    response = client.get("/api/phase3/health/alerts")
    assert response.status_code == 200
    
    data = response.json()
    assert "active_alerts" in data
    assert "alert_summary" in data

def test_phase3_risk_comprehensive_analysis():
    """Test que l'endpoint risk analysis fonctionne avec des données de test"""
    test_request = {
        "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
        "portfolio_value": 10000,
        "analysis_types": ["var_parametric", "stress_test"],
        "confidence_levels": [0.95],
        "horizons": ["1d"]
    }
    
    response = client.post("/api/phase3/risk/comprehensive-analysis", json=test_request)
    assert response.status_code == 200
    
    data = response.json()
    assert "var_analysis" in data
    assert "stress_tests" in data
    assert "risk_summary" in data

def test_phase3_not_found_endpoints():
    """Test que les endpoints qui n'existent pas renvoient 404"""
    response = client.get("/api/phase3/nonexistent")
    assert response.status_code == 404

# Test de performance basique
def test_phase3_status_performance():
    """Test que l'endpoint status répond rapidement"""
    import time
    start = time.time()
    
    response = client.get("/api/phase3/status")
    
    elapsed = time.time() - start
    assert response.status_code == 200
    assert elapsed < 2.0  # Moins de 2 secondes