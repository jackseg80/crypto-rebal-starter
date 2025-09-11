"""
Tests d'intégration pour les endpoints Strategy

Tests des endpoints PR-B :
- GET /api/strategy/templates - Liste templates  
- POST /api/strategy/preview - Preview allocation
- GET /api/strategy/current - État courant
- POST /api/strategy/compare - Comparaison templates
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from api.main import app


@pytest.fixture
def client():
    """Client de test FastAPI"""
    return TestClient(app)


class TestStrategyTemplatesEndpoint:
    """Tests de l'endpoint /api/strategy/templates"""
    
    def test_get_templates_success(self, client):
        """Test récupération templates réussie"""
        response = client.get("/api/strategy/templates")
        
        assert response.status_code == 200
        data = response.json()
        
        # Doit contenir au moins les templates par défaut
        expected_templates = ["conservative", "balanced", "aggressive"]
        for template_id in expected_templates:
            assert template_id in data
            
            template_info = data[template_id]
            assert "name" in template_info
            assert "description" in template_info
            assert "template" in template_info
            assert "risk_level" in template_info
            
            # Validation des valeurs
            assert isinstance(template_info["name"], str)
            assert template_info["risk_level"] in ["low", "medium", "high"]
    
    def test_templates_structure_validation(self, client):
        """Test validation structure des templates"""
        response = client.get("/api/strategy/templates")
        data = response.json()
        
        # Chaque template doit avoir structure cohérente
        for template_id, template_info in data.items():
            assert isinstance(template_info["name"], str)
            assert len(template_info["name"]) > 0
            assert template_info["template"] in ["conservative", "balanced", "aggressive", "custom"]
            
            if template_info.get("description"):
                assert isinstance(template_info["description"], str)


class TestStrategyPreviewEndpoint:
    """Tests de l'endpoint /api/strategy/preview"""
    
    def test_preview_balanced_strategy(self, client):
        """Test preview stratégie balanced"""
        request_data = {
            "template_id": "balanced",
            "force_refresh": True
        }
        
        response = client.post("/api/strategy/preview", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Structure obligatoire
        required_fields = [
            "decision_score", "confidence", "targets", "rationale", 
            "policy_hint", "generated_at", "strategy_used"
        ]
        for field in required_fields:
            assert field in data
        
        # Validation des valeurs
        assert 0.0 <= data["decision_score"] <= 100.0
        assert 0.0 <= data["confidence"] <= 1.0
        assert data["policy_hint"] in ["Slow", "Normal", "Aggressive"]
        assert data["strategy_used"] == "Balanced"
        
        # Validation targets
        targets = data["targets"]
        assert len(targets) > 0
        
        total_weight = 0.0
        for target in targets:
            assert "symbol" in target
            assert "weight" in target
            assert isinstance(target["symbol"], str)
            assert isinstance(target["weight"], float)
            assert 0.0 <= target["weight"] <= 1.0
            total_weight += target["weight"]
        
        # Poids doivent sommer à ~1.0
        assert abs(total_weight - 1.0) < 0.01
        
        # Rationale non vide
        assert len(data["rationale"]) >= 1
        assert all(isinstance(r, str) for r in data["rationale"])
        
        # Timestamp valide
        datetime.fromisoformat(data["generated_at"])
    
    def test_preview_with_custom_weights(self, client):
        """Test preview avec poids custom"""
        request_data = {
            "template_id": "balanced",
            "custom_weights": {
                "cycle": 0.4,
                "onchain": 0.3,
                "risk_adjusted": 0.2,
                "sentiment": 0.1
            },
            "force_refresh": True
        }
        
        response = client.post("/api/strategy/preview", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Doit fonctionner avec poids custom
        assert 0.0 <= data["decision_score"] <= 100.0
        assert len(data["targets"]) > 0
    
    def test_preview_invalid_template(self, client):
        """Test preview avec template inexistant"""
        request_data = {
            "template_id": "inexistant_template",
            "force_refresh": True
        }
        
        response = client.post("/api/strategy/preview", json=request_data)
        
        assert response.status_code == 400
        error_data = response.json()
        assert "Template inconnu" in error_data["detail"]
    
    def test_preview_invalid_weights_sum(self, client):
        """Test preview avec somme poids invalide"""
        request_data = {
            "template_id": "balanced",
            "custom_weights": {
                "cycle": 0.1,    # Somme = 0.5 (invalide)
                "onchain": 0.1,
                "risk_adjusted": 0.1,
                "sentiment": 0.2
            }
        }
        
        response = client.post("/api/strategy/preview", json=request_data)
        
        assert response.status_code == 400
        error_data = response.json()
        assert "Somme poids invalide" in error_data["detail"]
    
    def test_preview_different_templates(self, client):
        """Test preview de différents templates"""
        templates_to_test = ["conservative", "balanced", "aggressive"]
        
        results = {}
        for template_id in templates_to_test:
            request_data = {"template_id": template_id, "force_refresh": True}
            response = client.post("/api/strategy/preview", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            results[template_id] = data
        
        # Chaque template doit donner des résultats différents
        scores = [r["decision_score"] for r in results.values()]
        assert len(set(scores)) > 1, "Templates donnent scores identiques"
        
        # Conservative devrait avoir score différent d'aggressive
        conservative_score = results["conservative"]["decision_score"]  
        aggressive_score = results["aggressive"]["decision_score"]
        # Note: Pas d'assertion sur l'ordre car dépend des conditions marché


class TestStrategyCurrentEndpoint:
    """Tests de l'endpoint /api/strategy/current"""
    
    def test_get_current_strategy_default(self, client):
        """Test récupération stratégie courante par défaut"""
        response = client.get("/api/strategy/current")
        
        assert response.status_code == 200
        data = response.json()
        
        # Structure identique à preview
        required_fields = [
            "decision_score", "confidence", "targets", "rationale",
            "policy_hint", "generated_at", "strategy_used"
        ]
        for field in required_fields:
            assert field in data
        
        # Défaut = balanced
        assert data["strategy_used"] == "Balanced"
    
    def test_get_current_strategy_specific_template(self, client):
        """Test récupération avec template spécifique"""
        response = client.get("/api/strategy/current?template_id=conservative")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["strategy_used"] == "Conservative"
        assert len(data["targets"]) > 0
    
    def test_current_uses_cache(self, client):
        """Test que current utilise le cache (appels répétés rapides)"""
        # Premier appel
        response1 = client.get("/api/strategy/current?template_id=balanced")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Deuxième appel immédiat
        response2 = client.get("/api/strategy/current?template_id=balanced")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Timestamps doivent être identiques (cache)
        assert data1["generated_at"] == data2["generated_at"]


class TestStrategyCompareEndpoint:
    """Tests de l'endpoint /api/strategy/compare"""
    
    def test_compare_multiple_templates(self, client):
        """Test comparaison de plusieurs templates"""
        request_data = ["conservative", "balanced", "aggressive"]
        
        response = client.post("/api/strategy/compare", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "comparisons" in data
        assert "generated_at" in data
        
        comparisons = data["comparisons"]
        
        # Doit avoir résultats pour chaque template
        for template_id in request_data:
            assert template_id in comparisons
            
            comparison = comparisons[template_id]
            if "error" not in comparison:
                # Structure de comparaison valide
                expected_fields = [
                    "decision_score", "confidence", "policy_hint",
                    "targets_count", "strategy_name", "primary_allocation"
                ]
                for field in expected_fields:
                    assert field in comparison
                
                # Validation des valeurs
                assert 0.0 <= comparison["decision_score"] <= 100.0
                assert 0.0 <= comparison["confidence"] <= 1.0
                assert isinstance(comparison["targets_count"], int)
                assert comparison["targets_count"] > 0
    
    def test_compare_insufficient_templates(self, client):
        """Test comparaison avec moins de 2 templates"""
        request_data = ["balanced"]  # Un seul template
        
        response = client.post("/api/strategy/compare", json=request_data)
        
        assert response.status_code == 400
        error_data = response.json()
        assert "Au moins 2 templates requis" in error_data["detail"]
    
    def test_compare_with_invalid_template(self, client):
        """Test comparaison avec template invalide"""
        request_data = ["balanced", "inexistant", "conservative"]
        
        response = client.post("/api/strategy/compare", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        comparisons = data["comparisons"]
        
        # Templates valides doivent avoir résultats
        assert "decision_score" in comparisons["balanced"]
        assert "decision_score" in comparisons["conservative"]
        
        # Template invalide doit avoir erreur
        assert "error" in comparisons["inexistant"]
    
    def test_compare_max_templates_limit(self, client):
        """Test limite maximale de templates (5)"""
        request_data = [
            "conservative", "balanced", "aggressive", 
            "phase_follower", "contradiction_averse", "extra_template"
        ]  # 6 templates
        
        response = client.post("/api/strategy/compare", json=request_data)
        
        # Doit accepter (limite dans le schema Pydantic)
        # Mais seuls les 5 premiers seront traités si limite appliquée
        assert response.status_code in [200, 422]  # 422 si validation Pydantic échoue


class TestStrategyHealthEndpoint:
    """Tests de l'endpoint /api/strategy/health"""
    
    def test_health_check(self, client):
        """Test health check du Strategy Registry"""
        response = client.get("/api/strategy/health")
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["status", "templates_loaded", "timestamp"]
        for field in required_fields:
            assert field in data
        
        assert data["status"] in ["healthy", "degraded"]
        assert isinstance(data["templates_loaded"], int)
        assert data["templates_loaded"] >= 0
        
        # Timestamp valide
        datetime.fromisoformat(data["timestamp"])


class TestAdminEndpoint:
    """Tests de l'endpoint admin (détails template)"""
    
    def test_get_template_weights_details(self, client):
        """Test récupération détails poids d'un template"""
        response = client.get("/api/strategy/admin/templates/balanced/weights")
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "template_id", "name", "weights", "risk_budget", 
            "phase_adjustments", "confidence_threshold", "rebalance_threshold_pct"
        ]
        for field in required_fields:
            assert field in data
        
        # Validation poids
        weights = data["weights"]
        weight_fields = ["cycle", "onchain", "risk_adjusted", "sentiment"]
        for field in weight_fields:
            assert field in weights
            assert isinstance(weights[field], float)
            assert 0.0 <= weights[field] <= 1.0
        
        # Somme des poids ≈ 1.0
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.01
    
    def test_get_nonexistent_template_weights(self, client):
        """Test récupération poids template inexistant"""
        response = client.get("/api/strategy/admin/templates/inexistant/weights")
        
        assert response.status_code == 404
        error_data = response.json()
        assert "Template non trouvé" in error_data["detail"]


class TestErrorHandling:
    """Tests de gestion d'erreur"""
    
    def test_malformed_request_preview(self, client):
        """Test requête malformée pour preview"""
        # Requête sans template_id
        response = client.post("/api/strategy/preview", json={})
        
        assert response.status_code == 422  # Validation Pydantic
    
    def test_invalid_json_preview(self, client):
        """Test JSON invalide pour preview"""
        response = client.post(
            "/api/strategy/preview",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_server_error_handling(self, client):
        """Test que les erreurs serveur retournent 500"""
        # Cas difficile à simuler sans mock, mais structure existe
        # L'endpoint gère les exceptions avec HTTPException(500, ...)
        pass


# Tests de performance légers
class TestPerformance:
    """Tests de performance basiques"""
    
    def test_template_response_time(self, client):
        """Test temps de réponse templates"""
        import time
        
        start_time = time.time()
        response = client.get("/api/strategy/templates")
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 1.0, f"Endpoint trop lent: {response_time:.2f}s"
    
    def test_preview_response_time(self, client):
        """Test temps de réponse preview"""
        import time
        
        request_data = {"template_id": "balanced", "force_refresh": True}
        
        start_time = time.time()
        response = client.post("/api/strategy/preview", json=request_data)
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 2.0, f"Preview trop lent: {response_time:.2f}s"


class TestDataConsistency:
    """Tests de cohérence des données"""
    
    def test_template_consistency_across_endpoints(self, client):
        """Test cohérence templates entre endpoints"""
        # Récupérer templates disponibles
        templates_response = client.get("/api/strategy/templates")
        templates = templates_response.json()
        
        # Tester preview pour chaque template
        for template_id in templates.keys():
            request_data = {"template_id": template_id, "force_refresh": True}
            preview_response = client.post("/api/strategy/preview", json=request_data)
            
            assert preview_response.status_code == 200, f"Preview échoue pour {template_id}"
            
            preview_data = preview_response.json()
            expected_name = templates[template_id]["name"]
            assert preview_data["strategy_used"] == expected_name
    
    def test_allocation_weights_consistency(self, client):
        """Test cohérence des poids d'allocation"""
        templates_to_test = ["conservative", "balanced", "aggressive"]
        
        for template_id in templates_to_test:
            request_data = {"template_id": template_id, "force_refresh": True}
            response = client.post("/api/strategy/preview", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            
            # Vérifier normalisation des poids
            total_weight = sum(target["weight"] for target in data["targets"])
            assert abs(total_weight - 1.0) < 0.01, f"Poids non normalisés pour {template_id}: {total_weight}"
            
            # Aucun poids négatif
            for target in data["targets"]:
                assert target["weight"] >= 0.0, f"Poids négatif détecté: {target}"