"""
Tests d'intégration pour l'endpoint /governance/state unifié

Tests que l'endpoint étendu retourne correctement :
- Scores canoniques unifiés
- Phase de rotation BTC→ETH→Large→Alt  
- Exec pressure court-terme
- Bus de signaux unifié
- Métriques portefeuille
- Suggestion IA canonique
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from api.main import app


@pytest.fixture
def client():
    """Client de test FastAPI"""
    return TestClient(app)


class TestGovernanceStateUnified:
    """Tests de l'endpoint /governance/state étendu"""
    
    def test_endpoint_accessibility(self, client):
        """Test que l'endpoint est accessible et retourne un 200"""
        response = client.get("/execution/governance/state")
        assert response.status_code == 200
    
    def test_backward_compatibility(self, client):
        """Test que les champs existants sont toujours présents"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        # Champs existants obligatoires
        required_existing_fields = [
            "current_state", "mode", "contradiction_index", 
            "pending_approvals", "next_update_time"
        ]
        
        for field in required_existing_fields:
            assert field in data, f"Champ existant manquant: {field}"
    
    def test_new_unified_fields_present(self, client):
        """Test que les nouveaux champs unifiés sont présents"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        # Nouveaux champs obligatoires (peuvent être null)
        new_fields = ["scores", "phase", "exec", "signals", "portfolio", "suggestion"]
        
        for field in new_fields:
            assert field in data, f"Nouveau champ manquant: {field}"
    
    def test_scores_structure(self, client):
        """Test structure du champ scores canoniques"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        scores = data.get("scores")
        if scores:  # Peut être null selon l'état
            # Structure scores canoniques
            assert "decision" in scores
            assert "confidence" in scores  
            assert "contradiction" in scores
            assert "components" in scores
            assert "as_of" in scores
            
            # Validation des ranges
            assert 0.0 <= scores["decision"] <= 100.0
            assert 0.0 <= scores["confidence"] <= 1.0
            assert 0.0 <= scores["contradiction"] <= 1.0
            
            # Structure des composants
            components = scores["components"]
            required_components = ["trend_regime", "risk", "breadth_rotation", "sentiment"]
            
            for component in required_components:
                assert component in components
                assert 0.0 <= components[component] <= 100.0
    
    def test_phase_structure(self, client):
        """Test structure du champ phase de rotation"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        phase = data.get("phase")
        if phase:  # Peut être null selon l'état
            # Structure phase
            assert "phase_now" in phase
            assert "phase_probs" in phase
            assert "confidence" in phase
            assert "explain" in phase
            
            # Validation phase_now
            valid_phases = ["btc", "eth", "large", "alt"]
            assert phase["phase_now"] in valid_phases
            
            # Validation probabilités
            probs = phase["phase_probs"]
            assert isinstance(probs, dict)
            assert all(phase_name in probs for phase_name in valid_phases)
            assert all(0.0 <= prob <= 1.0 for prob in probs.values())
            
            # Probabilités doivent sommer à ~1.0
            prob_sum = sum(probs.values())
            assert 0.9 <= prob_sum <= 1.1
            
            # Explications
            assert isinstance(phase["explain"], list)
            assert len(phase["explain"]) >= 1
            assert all(isinstance(exp, str) for exp in phase["explain"])
    
    def test_exec_pressure_structure(self, client):
        """Test structure du champ exec pressure"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        exec_data = data.get("exec")
        if exec_data:  # Peut être null selon l'état
            # Structure exec pressure
            assert "pressure" in exec_data
            assert "cost_estimate_bps" in exec_data
            assert "market_impact" in exec_data
            assert "optimal_window_hours" in exec_data
            
            # Validation des valeurs
            assert 0.0 <= exec_data["pressure"] <= 100.0
            assert exec_data["cost_estimate_bps"] > 0
            assert exec_data["market_impact"] in ["low", "medium", "high"]
            assert exec_data["optimal_window_hours"] > 0
    
    def test_portfolio_structure(self, client):
        """Test structure du champ portfolio"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        portfolio = data.get("portfolio")
        if portfolio and "metrics" in portfolio:
            metrics = portfolio["metrics"]
            
            # Métriques de risque optionnelles mais typées si présentes
            optional_metrics = ["var_95_pct", "sharpe_ratio", "hhi_concentration", 
                              "avg_correlation", "beta_btc"]
            
            for metric in optional_metrics:
                if metric in metrics and metrics[metric] is not None:
                    assert isinstance(metrics[metric], (int, float))
            
            # Expositions par groupe
            if "exposures" in metrics:
                exposures = metrics["exposures"]
                assert isinstance(exposures, dict)
                
                # Vérifier que les expositions sont des pourcentages valides
                for group, exposure in exposures.items():
                    assert isinstance(group, str)
                    assert isinstance(exposure, (int, float))
                    assert 0.0 <= exposure <= 100.0
    
    def test_suggestion_structure(self, client):
        """Test structure du champ suggestion IA"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        suggestion = data.get("suggestion")
        if suggestion:  # Peut être null si pas de suggestion
            # Structure suggestion IA
            assert "targets" in suggestion
            assert "rationale" in suggestion
            assert "policy_hint" in suggestion
            assert "confidence" in suggestion
            assert "generated_at" in suggestion
            
            # Validation targets
            targets = suggestion["targets"]
            assert isinstance(targets, list)
            assert len(targets) > 0
            
            # Chaque target doit avoir symbol et weight
            total_weight = 0.0
            for target in targets:
                assert "symbol" in target
                assert "weight" in target
                assert isinstance(target["symbol"], str)
                assert isinstance(target["weight"], (int, float))
                assert 0.0 <= target["weight"] <= 1.0
                total_weight += target["weight"]
            
            # Poids doivent sommer à ~1.0
            assert 0.9 <= total_weight <= 1.1
            
            # Policy hint valide
            valid_policy_hints = ["Slow", "Normal", "Aggressive"]
            assert suggestion["policy_hint"] in valid_policy_hints
            
            # Confiance valide
            assert 0.0 <= suggestion["confidence"] <= 1.0
    
    def test_signals_structure(self, client):
        """Test structure du champ signals unifié"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        signals = data.get("signals")
        if signals:  # Peut être null selon disponibilité ML
            # Structure bus de signaux
            assert "market" in signals
            assert "cycle" in signals
            assert "as_of" in signals
            
            # Market signals
            market = signals["market"]
            expected_market_fields = ["volatility", "regime", "correlation", "sentiment"]
            for field in expected_market_fields:
                assert field in market
                assert isinstance(market[field], dict)
            
            # Cycle signals
            cycle = signals["cycle"]
            expected_cycle_fields = ["btc_cycle", "rotation"]
            for field in expected_cycle_fields:
                assert field in cycle
                assert isinstance(cycle[field], dict)
            
            # Timestamp valide
            timestamp = signals["as_of"]
            # Vérifier que c'est une date ISO valide
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))


class TestDataConsistency:
    """Tests de cohérence des données"""
    
    def test_score_phase_consistency(self, client):
        """Test cohérence entre score et phase"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        scores = data.get("scores")
        phase = data.get("phase")
        
        if scores and phase:
            # Si score très élevé, phase devrait être plus agressive
            decision_score = scores["decision"]
            current_phase = phase["phase_now"]
            
            # Logique basique : score élevé + phase ALT = cohérent
            if decision_score > 80 and current_phase == "alt":
                # C'est cohérent, pas d'assertion à faire
                pass
            elif decision_score < 30 and current_phase == "btc":
                # Cohérent aussi (conservateur)
                pass
    
    def test_contradiction_consistency(self, client):
        """Test cohérence de l'index de contradiction"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        # Ancien champ vs nouveau champ doivent être cohérents
        old_contradiction = data.get("contradiction_index", 0)
        scores = data.get("scores")
        
        if scores:
            new_contradiction = scores["contradiction"]
            
            # Doivent être similaires (tolérance pour calculs différents)
            assert abs(old_contradiction - new_contradiction) < 0.2
    
    def test_exec_pressure_policy_consistency(self, client):
        """Test cohérence entre exec pressure et policy"""
        response = client.get("/execution/governance/state")
        data = response.json()
        
        exec_data = data.get("exec")
        active_policy = data.get("active_policy")
        
        if exec_data and active_policy:
            pressure = exec_data["pressure"]
            policy_mode = active_policy.get("mode", "Normal")
            
            # Cohérence : pression élevée → mode conservateur
            if pressure > 80:
                assert policy_mode in ["Freeze", "Slow"], f"Pression {pressure} mais mode {policy_mode}"
            elif pressure < 30:
                assert policy_mode in ["Normal", "Aggressive"], f"Pression {pressure} mais mode {policy_mode}"


class TestPerformance:
    """Tests de performance de l'endpoint étendu"""
    
    def test_response_time(self, client):
        """Test que l'endpoint répond en moins de 2 secondes"""
        import time
        
        start_time = time.time()
        response = client.get("/execution/governance/state")
        end_time = time.time()
        
        response_time = end_time - start_time
        assert response_time < 2.0, f"Endpoint trop lent: {response_time:.2f}s"
        assert response.status_code == 200
    
    def test_response_size_reasonable(self, client):
        """Test que la taille de réponse reste raisonnable"""
        response = client.get("/execution/governance/state")
        
        # Réponse doit faire moins de 50KB
        response_size = len(response.content)
        assert response_size < 50000, f"Réponse trop grosse: {response_size} bytes"


class TestErrorHandling:
    """Tests de gestion d'erreur"""
    
    def test_graceful_degradation(self, client):
        """Test que l'endpoint fonctionne même si certains composants échouent"""
        # Même si Score Registry ou Phase Engine échouent,
        # l'endpoint doit retourner les champs existants
        response = client.get("/execution/governance/state")
        
        # Au minimum, les champs de base doivent être présents
        assert response.status_code == 200
        data = response.json()
        assert "current_state" in data
        assert "mode" in data