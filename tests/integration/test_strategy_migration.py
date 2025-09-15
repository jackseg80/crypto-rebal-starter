"""
Tests d'intégration pour la migration Strategy API (PR-C)

Tests de l'adaptateur strategy-api-adapter.js et de la migration
frontend vers l'API Strategy backend.
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app
import json


@pytest.fixture
def client():
    """Client de test FastAPI"""
    return TestClient(app)


class TestStrategyMigrationIntegration:
    """Tests d'intégration pour la migration Strategy API"""
    
    def test_strategy_api_endpoints_accessible(self, client):
        """Test que tous les endpoints Strategy API sont accessibles"""
        # Templates endpoint
        response = client.get("/api/strategy/templates")
        assert response.status_code == 200
        templates = response.json()
        assert len(templates) >= 3
        assert "balanced" in templates
        
        # Preview endpoint
        preview_request = {
            "template_id": "balanced",
            "force_refresh": True
        }
        response = client.post("/api/strategy/preview", json=preview_request)
        assert response.status_code == 200
        data = response.json()
        
        # Structure compatible avec l'adaptateur frontend
        required_fields = [
            "decision_score", "confidence", "targets", "rationale",
            "policy_hint", "generated_at", "strategy_used"
        ]
        for field in required_fields:
            assert field in data, f"Champ manquant pour adaptateur: {field}"
        
        # Current endpoint
        response = client.get("/api/strategy/current?template_id=balanced")
        assert response.status_code == 200
        current_data = response.json()
        assert "decision_score" in current_data
        
        # Health endpoint
        response = client.get("/api/strategy/health")
        assert response.status_code == 200
        health = response.json()
        assert health["status"] in ["healthy", "degraded"]
    
    def test_strategy_response_format_compatibility(self, client):
        """Test que le format de réponse est compatible avec l'adaptateur frontend"""
        response = client.post("/api/strategy/preview", json={
            "template_id": "balanced", 
            "force_refresh": True
        })
        assert response.status_code == 200
        data = response.json()
        
        # Validation des types pour l'adaptateur JS
        assert isinstance(data["decision_score"], (int, float))
        assert 0 <= data["decision_score"] <= 100
        
        assert isinstance(data["confidence"], (int, float)) 
        assert 0 <= data["confidence"] <= 1
        
        assert isinstance(data["targets"], list)
        assert len(data["targets"]) > 0
        
        # Validation structure targets
        for target in data["targets"]:
            assert "symbol" in target
            assert "weight" in target
            assert isinstance(target["symbol"], str)
            assert isinstance(target["weight"], (int, float))
            assert 0 <= target["weight"] <= 1
        
        # Validation poids normalisés
        total_weight = sum(t["weight"] for t in data["targets"])
        assert abs(total_weight - 1.0) < 0.01, f"Poids non normalisés: {total_weight}"
        
        assert isinstance(data["rationale"], list)
        assert all(isinstance(r, str) for r in data["rationale"])
        
        assert data["policy_hint"] in ["Slow", "Normal", "Aggressive"]
        
        # Timestamp ISO valide
        from datetime import datetime
        datetime.fromisoformat(data["generated_at"])
    
    def test_strategy_templates_completeness(self, client):
        """Test que tous les templates attendus sont disponibles"""
        response = client.get("/api/strategy/templates")
        templates = response.json()
        
        # Templates essentiels pour migration
        essential_templates = ["conservative", "balanced", "aggressive"]
        for template_id in essential_templates:
            assert template_id in templates, f"Template essentiel manquant: {template_id}"
            
            template_info = templates[template_id]
            assert "name" in template_info
            assert "risk_level" in template_info
            assert template_info["risk_level"] in ["low", "medium", "high"]
    
    def test_strategy_custom_weights_support(self, client):
        """Test support des poids custom pour l'adaptateur"""
        custom_weights = {
            "cycle": 0.4,
            "onchain": 0.3,
            "risk_adjusted": 0.2,
            "sentiment": 0.1
        }
        
        response = client.post("/api/strategy/preview", json={
            "template_id": "balanced",
            "custom_weights": custom_weights,
            "force_refresh": True
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Doit fonctionner avec weights custom
        assert isinstance(data["decision_score"], (int, float))
        assert len(data["targets"]) > 0
    
    def test_strategy_comparison_endpoint(self, client):
        """Test endpoint de comparaison pour l'adaptateur"""
        templates_to_compare = ["conservative", "balanced", "aggressive"]
        
        response = client.post("/api/strategy/compare", json=templates_to_compare)
        assert response.status_code == 200
        data = response.json()
        
        assert "comparisons" in data
        assert "generated_at" in data
        
        comparisons = data["comparisons"]
        for template_id in templates_to_compare:
            assert template_id in comparisons
            
            comparison = comparisons[template_id]
            if "error" not in comparison:
                # Structure attendue par l'adaptateur JS
                assert "decision_score" in comparison
                assert "confidence" in comparison 
                assert "policy_hint" in comparison
                assert "targets_count" in comparison
                assert "primary_allocation" in comparison
    
    def test_strategy_error_handling(self, client):
        """Test gestion d'erreurs pour fallback adaptateur"""
        # Template inexistant
        response = client.post("/api/strategy/preview", json={
            "template_id": "inexistant_template"
        })
        assert response.status_code == 400
        
        # Poids invalides
        response = client.post("/api/strategy/preview", json={
            "template_id": "balanced",
            "custom_weights": {
                "cycle": 0.1,
                "onchain": 0.1, 
                "risk_adjusted": 0.1,
                "sentiment": 0.1  # Somme = 0.4 (invalide)
            }
        })
        assert response.status_code == 400
    
    def test_strategy_performance_requirements(self, client):
        """Test exigences de performance pour UX acceptable"""
        import time
        
        # Templates endpoint doit être rapide
        start_time = time.time()
        response = client.get("/api/strategy/templates")
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 1.0, f"Templates endpoint trop lent: {response_time:.2f}s"
        
        # Preview endpoint doit être acceptable
        start_time = time.time()
        response = client.post("/api/strategy/preview", json={
            "template_id": "balanced",
            "force_refresh": True
        })
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 3.0, f"Preview endpoint trop lent: {response_time:.2f}s"


class TestMigrationCompatibility:
    """Tests de compatibilité pour la migration progressive"""
    
    def test_backward_compatibility_maintained(self, client):
        """Test que l'API maintient la compatibilité ascendante"""
        # L'adaptateur s'attend à ces champs dans la réponse
        response = client.post("/api/strategy/preview", json={
            "template_id": "balanced"
        })
        assert response.status_code == 200
        data = response.json()
        
        # Champs legacy qui doivent être présents
        legacy_expected_fields = {
            "decision_score": (int, float),
            "confidence": (int, float),  
            "rationale": list
        }
        
        for field, expected_type in legacy_expected_fields.items():
            assert field in data, f"Champ legacy manquant: {field}"
            assert isinstance(data[field], expected_type), f"Type invalide pour {field}"
    
    def test_new_api_features_available(self, client):
        """Test que les nouvelles fonctionnalités API sont disponibles"""
        response = client.post("/api/strategy/preview", json={
            "template_id": "balanced"
        })
        assert response.status_code == 200
        data = response.json()
        
        # Nouvelles fonctionnalités qui n'existent pas en legacy
        new_features = {
            "targets": list,         # Allocations spécifiques
            "policy_hint": str,      # Hints d'exécution
            "strategy_used": str,    # Template utilisé
            "generated_at": str      # Timestamp
        }
        
        for field, expected_type in new_features.items():
            assert field in data, f"Nouvelle fonctionnalité manquante: {field}"
            assert isinstance(data[field], expected_type), f"Type invalide pour nouvelle fonctionnalité {field}"
    
    def test_migration_rollback_possible(self, client):
        """Test qu'un rollback est possible en cas de problème"""
        # L'API doit toujours être accessible même si Strategy Registry échoue
        response = client.get("/api/strategy/health")
        
        # Même en mode dégradé, l'endpoint doit répondre
        assert response.status_code == 200
        health = response.json()
        assert "status" in health
        assert health["status"] in ["healthy", "degraded"]


class TestMigrationScenarios:
    """Tests de scénarios de migration réels"""
    
    def test_dashboard_migration_scenario(self, client):
        """Test scénario complet de migration d'un dashboard"""
        # 1. Vérifier que l'API Strategy est disponible
        templates_response = client.get("/api/strategy/templates")
        assert templates_response.status_code == 200
        templates = templates_response.json()
        assert "balanced" in templates
        
        # 2. Obtenir une suggestion stratégique (simule l'adaptateur)
        strategy_response = client.post("/api/strategy/preview", json={
            "template_id": "balanced",
            "force_refresh": False  # Utiliser le cache
        })
        assert strategy_response.status_code == 200
        strategy_data = strategy_response.json()
        
        # 3. Vérifier que les données sont utilisables par le dashboard
        assert isinstance(strategy_data["decision_score"], (int, float))
        assert isinstance(strategy_data["targets"], list)
        assert len(strategy_data["targets"]) > 0
        
        # 4. Simuler l'utilisation des targets pour l'affichage
        total_allocation = sum(t["weight"] for t in strategy_data["targets"])
        assert abs(total_allocation - 1.0) < 0.01  # 100% d'allocation
        
        # 5. Vérifier que policy_hint peut guider l'UX
        assert strategy_data["policy_hint"] in ["Slow", "Normal", "Aggressive"]
        
        # 6. Test comparaison (pour validation migration)
        compare_response = client.post("/api/strategy/compare", json=["conservative", "balanced"])
        assert compare_response.status_code == 200
        
        print(f"Migration scenario completed successfully:")
        print(f"   Score: {strategy_data['decision_score']}")
        print(f"   Template: {strategy_data['strategy_used']}")
        print(f"   Policy: {strategy_data['policy_hint']}")
        print(f"   Targets: {len(strategy_data['targets'])}")
    
    def test_gradual_rollout_scenario(self, client):
        """Test scénario de déploiement progressif avec feature flags"""
        # Simuler différents templates pour différents utilisateurs
        user_segments = {
            "conservative_users": "conservative",
            "balanced_users": "balanced", 
            "aggressive_users": "aggressive"
        }
        
        results = {}
        for segment, template in user_segments.items():
            response = client.post("/api/strategy/preview", json={
                "template_id": template
            })
            assert response.status_code == 200
            results[segment] = response.json()
        
        # Vérifier que chaque segment a des recommandations cohérentes
        conservative_score = results["conservative_users"]["decision_score"]
        aggressive_score = results["aggressive_users"]["decision_score"]
        
        # Les templates peuvent donner des scores différents selon les conditions marché
        # On vérifie juste qu'ils sont dans des plages raisonnables
        assert 0 <= conservative_score <= 100
        assert 0 <= aggressive_score <= 100
        
        print(f"Gradual rollout scenario:")
        print(f"   Conservative: {conservative_score}")
        print(f"   Aggressive: {aggressive_score}")
    
    def test_fallback_scenario(self, client):
        """Test scénario de fallback en cas de problème API"""
        # Test avec template inexistant (simule erreur API)
        response = client.post("/api/strategy/preview", json={
            "template_id": "template_inexistant"
        })
        
        # L'API doit retourner une erreur claire pour que l'adaptateur puisse faire le fallback
        assert response.status_code == 400
        error_data = response.json()
        assert "detail" in error_data
        assert "Template inconnu" in error_data["detail"]
        
        # Test avec données corrompues (simule problème backend)
        response = client.post("/api/strategy/preview", json={
            "template_id": "balanced",
            "custom_weights": {
                "invalid": "data"
            }
        })
        
        # Doit retourner une erreur de validation
        assert response.status_code == 422  # Validation error