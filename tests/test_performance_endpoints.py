"""
Tests pour les endpoints de performance P&L Today
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_performance_summary_basic():
    """Test basique de l'endpoint /api/performance/summary"""
    response = client.get("/api/performance/summary")
    assert response.status_code == 200
    data = response.json()
    
    # Vérifier la structure de base
    assert data["ok"] is True
    assert "performance" in data
    assert "as_of" in data["performance"]
    assert "total" in data["performance"]
    assert "by_account" in data["performance"]
    assert "by_source" in data["performance"]
    
    # Vérifier les champs du total
    total = data["performance"]["total"]
    assert "current_value_usd" in total
    assert "absolute_change_usd" in total
    assert "percent_change" in total

def test_performance_summary_anchor_parameter():
    """Test du paramètre anchor"""
    for anchor in ["prev_close", "midnight", "session"]:
        response = client.get(f"/api/performance/summary?anchor={anchor}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

def test_performance_summary_etag():
    """Test du fonctionnement ETag"""
    # Premier appel pour obtenir l'ETag
    response1 = client.get("/api/performance/summary")
    assert response1.status_code == 200
    etag = response1.headers.get("etag")
    assert etag is not None
    
    # Deuxième appel avec le bon ETag
    response2 = client.get("/api/performance/summary", headers={"if-none-match": etag})
    assert response2.status_code == 304
    
    # Appel avec mauvais ETag
    response3 = client.get("/api/performance/summary", headers={"if-none-match": "wrong-etag"})
    assert response3.status_code == 200

def test_performance_summary_cache_headers():
    """Test des headers de cache"""
    response = client.get("/api/performance/summary")
    assert response.status_code == 200
    
    # Vérifier les headers de cache
    assert "etag" in response.headers
    assert "cache-control" in response.headers
    # Le cache-control peut varier selon la configuration de sécurité
    # L'important est que l'ETag fonctionne pour la validation de cache
    etag = response.headers["etag"]
    assert len(etag) > 10  # Vérifier que l'ETag est significatif

def test_performance_summary_data_integrity():
    """Test de l'intégrité des données"""
    response = client.get("/api/performance/summary")
    assert response.status_code == 200
    data = response.json()
    
    perf = data["performance"]
    total = perf["total"]
    
    # Vérifier que les valeurs sont cohérentes
    assert isinstance(total["current_value_usd"], (int, float))
    assert isinstance(total["absolute_change_usd"], (int, float))
    assert isinstance(total["percent_change"], (int, float))
    
    # Vérifier que le pourcentage est calculé correctement
    if total["current_value_usd"] - total["absolute_change_usd"] > 0:
        expected_pct = (total["absolute_change_usd"] / 
                       (total["current_value_usd"] - total["absolute_change_usd"])) * 100
        assert abs(total["percent_change"] - expected_pct) < 0.01  # Tolérance de 0.01%

if __name__ == "__main__":
    pytest.main([__file__, "-v"])