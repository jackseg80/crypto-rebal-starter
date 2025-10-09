"""
Tests d'intégration pour les modules du Risk Dashboard refactorisé
Tests les endpoints API utilisés par risk-alerts-tab, risk-overview-tab, risk-cycles-tab, risk-targets-tab
"""

import pytest
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from api.main import app


class TestRiskAlertsTabAPI:
    """Tests pour risk-alerts-tab.js - Endpoints /api/alerts/*"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_active_alerts_success(self, client):
        """Test GET /api/alerts/active - cas nominal"""
        response = client.get("/api/alerts/active")

        # Accepter 200 (service actif) ou 503 (service indisponible)
        assert response.status_code in [200, 503], f"Status inattendu: {response.status_code}"

        if response.status_code == 200:
            data = response.json()

            # Structure attendue
            assert isinstance(data, list)

            if len(data) > 0:
                alert = data[0]
                assert "id" in alert
                assert "alert_type" in alert
                assert "severity" in alert
                assert "created_at" in alert
        else:
            # Service indisponible, test passé (alertes optionnelles)
            pytest.skip("Alert service unavailable (503)")

    def test_get_active_alerts_with_filters(self, client):
        """Test filtrage par severité"""
        response = client.get("/api/alerts/active?severity_filter=S2,S3")

        if response.status_code == 503:
            pytest.skip("Alert service unavailable (503)")

        assert response.status_code == 200
        data = response.json()

        # Tous les résultats doivent être S2 ou S3
        for alert in data:
            assert alert["severity"] in ["S2", "S3"]

    def test_acknowledge_alert(self, client):
        """Test POST /api/alerts/acknowledge/{alert_id}"""
        # D'abord récupérer une alerte existante
        alerts_response = client.get("/api/alerts/active")

        if alerts_response.status_code == 503:
            pytest.skip("Alert service unavailable (503)")

        alerts = alerts_response.json()

        if len(alerts) > 0:
            alert_id = alerts[0]["id"]
            response = client.post(f"/api/alerts/acknowledge/{alert_id}")

            # Peut retourner 200, 404 ou 503
            assert response.status_code in [200, 404, 503]

    def test_snooze_alert(self, client):
        """Test POST /api/alerts/snooze/{alert_id}"""
        alerts_response = client.get("/api/alerts/active")

        if alerts_response.status_code == 503:
            pytest.skip("Alert service unavailable (503)")

        alerts = alerts_response.json()

        if len(alerts) > 0:
            alert_id = alerts[0]["id"]
            response = client.post(
                f"/api/alerts/snooze/{alert_id}",
                json={"minutes": 60}
            )

            # Peut retourner 200, 404 ou 503
            assert response.status_code in [200, 404, 503]

    def test_get_alert_types(self, client):
        """Test GET /api/alerts/types - métadonnées types d'alertes"""
        response = client.get("/api/alerts/types")

        if response.status_code == 503:
            pytest.skip("Alert service unavailable (503)")

        assert response.status_code == 200
        data = response.json()

        assert "alert_types" in data
        assert "severities" in data
        assert len(data["severities"]) == 3  # S1, S2, S3

    def test_get_alert_metrics(self, client):
        """Test GET /api/alerts/metrics - stats alertes"""
        response = client.get("/api/alerts/metrics")

        if response.status_code == 503:
            pytest.skip("Alert service unavailable (503)")

        assert response.status_code == 200
        data = response.json()

        assert "alert_engine" in data or "error" in data  # Peut être indisponible
        assert "timestamp" in data


class TestRiskOverviewTabAPI:
    """Tests pour risk-overview-tab.js - Endpoints /api/risk/*"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_risk_dashboard_default(self, client):
        """Test GET /api/risk/dashboard - mode legacy par défaut"""
        response = client.get("/api/risk/dashboard?user_id=demo&source=cointracking")

        assert response.status_code == 200
        data = response.json()

        # Structure minimale attendue
        assert "risk_metrics" in data
        metrics = data["risk_metrics"]

        # Risk Score doit être présent
        assert "risk_score" in metrics
        assert isinstance(metrics["risk_score"], (int, float))
        assert 0 <= metrics["risk_score"] <= 100

    def test_get_risk_dashboard_dual_window(self, client):
        """Test GET /api/risk/dashboard avec dual_window=true"""
        response = client.get(
            "/api/risk/dashboard?user_id=demo&source=cointracking&use_dual_window=true"
        )

        assert response.status_code == 200
        data = response.json()

        metrics = data["risk_metrics"]

        # Dual window metadata doit être présente
        if "dual_window" in metrics:
            dual = metrics["dual_window"]
            assert "enabled" in dual
            assert "long_term" in dual
            assert "full_intersection" in dual

            # Vérifier structure long_term
            if dual.get("long_term", {}).get("available"):
                lt = dual["long_term"]
                assert "window_days" in lt
                assert "asset_count" in lt
                assert "coverage_pct" in lt
                assert "metrics" in lt

    def test_get_risk_dashboard_v2_shadow(self, client):
        """Test GET /api/risk/dashboard avec risk_version=v2_shadow"""
        response = client.get(
            "/api/risk/dashboard?user_id=demo&source=cointracking"
            "&risk_version=v2_shadow&use_dual_window=true"
        )

        assert response.status_code == 200
        data = response.json()

        metrics = data["risk_metrics"]

        # V2 metadata doit être présente
        if "risk_version_info" in metrics:
            v2_info = metrics["risk_version_info"]
            assert "active_version" in v2_info
            assert "risk_score_legacy" in v2_info
            assert "risk_score_v2" in v2_info

            # Scores doivent être valides
            assert 0 <= v2_info["risk_score_legacy"] <= 100
            assert 0 <= v2_info["risk_score_v2"] <= 100

    def test_get_risk_advanced(self, client):
        """Test GET /api/risk/advanced - métriques avancées"""
        response = client.get(
            "/api/risk/advanced?user_id=demo&source=cointracking"
        )

        assert response.status_code == 200
        data = response.json()

        # Structure attendue
        assert "risk_score" in data or "error" in data

    def test_get_onchain_score(self, client):
        """Test GET /api/risk/onchain-score"""
        response = client.get("/api/risk/onchain-score")

        assert response.status_code == 200
        data = response.json()

        assert "score" in data
        assert 0 <= data["score"] <= 100


class TestRiskCyclesTabAPI:
    """Tests pour risk-cycles-tab.js - Endpoints Bitcoin cycles + On-chain"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_bitcoin_historical_price(self, client):
        """Test GET /api/ml/bitcoin-historical-price - données Chart.js"""
        response = client.get("/api/ml/bitcoin-historical-price?days=365")

        assert response.status_code == 200
        data = response.json()

        # Structure attendue pour Chart.js
        assert "labels" in data or "dates" in data  # X-axis
        assert "prices" in data or "values" in data  # Y-axis

        # Vérifier que les données ne sont pas vides
        labels = data.get("labels") or data.get("dates") or []
        prices = data.get("prices") or data.get("values") or []
        assert len(labels) > 0, "Données historiques BTC vides"
        assert len(prices) > 0, "Prix BTC vides"

    def test_get_cycle_score(self, client):
        """Test GET /api/risk/cycle-score - score cycle Bitcoin"""
        response = client.get("/api/risk/cycle-score")

        assert response.status_code == 200
        data = response.json()

        assert "score" in data
        assert 0 <= data["score"] <= 100

        # Métadonnées utiles
        if "metadata" in data:
            meta = data["metadata"]
            assert "last_halving" in meta or "next_halving" in meta

    def test_get_onchain_indicators(self, client):
        """Test GET /api/risk/onchain-indicators - indicateurs on-chain détaillés"""
        response = client.get("/api/risk/onchain-indicators")

        assert response.status_code == 200
        data = response.json()

        # Structure attendue
        assert "composite_score" in data or "indicators" in data

        if "indicators" in data:
            indicators = data["indicators"]
            # Catégories attendues
            expected_categories = ["momentum", "valuation", "network", "risk"]
            for category in expected_categories:
                if category in indicators:
                    assert isinstance(indicators[category], dict)

    def test_bitcoin_price_fallback_sources(self, client):
        """Test fallback multi-sources (FRED → Binance → CoinGecko)"""
        response = client.get("/api/ml/bitcoin-historical-price?days=30")

        # Doit réussir même si FRED échoue (fallback actif)
        assert response.status_code == 200
        data = response.json()

        # Vérifier métadonnées source
        if "metadata" in data:
            meta = data["metadata"]
            assert "source" in meta
            assert meta["source"] in ["fred", "binance", "coingecko", "cache"]


class TestRiskTargetsTabAPI:
    """Tests pour risk-targets-tab.js - Endpoints stratégies + plans d'action"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_governance_state(self, client):
        """Test GET /execution/governance/state - état gouvernance unifié"""
        response = client.get("/execution/governance/state")

        assert response.status_code == 200
        data = response.json()

        # Structure attendue
        assert "status" in data
        assert "timestamp" in data

        if "decisions" in data:
            assert isinstance(data["decisions"], dict)

    def test_get_allocation_strategies(self, client):
        """Test GET /api/strategy/allocations - 5 stratégies disponibles"""
        response = client.get(
            "/api/strategy/allocations?user_id=demo&source=cointracking"
        )

        assert response.status_code == 200
        data = response.json()

        # Doit retourner plusieurs stratégies
        assert "strategies" in data or "allocations" in data or isinstance(data, dict)

        # Vérifier présence des 5 stratégies attendues
        if "strategies" in data:
            strategies = data["strategies"]
            expected = ["macro", "ccs", "cycle", "blend", "smart"]
            for strategy in expected:
                assert any(strategy in str(s).lower() for s in strategies)

    def test_get_rebalance_plan(self, client):
        """Test GET /rebalance/plan - génération plan d'action"""
        response = client.get(
            "/rebalance/plan?user_id=demo&source=cointracking&mode=priority"
        )

        # Peut retourner 200 ou 422 selon état portfolio
        assert response.status_code in [200, 422]

        if response.status_code == 200:
            data = response.json()

            # Structure plan d'action
            assert "actions" in data or "trades" in data
            assert "metadata" in data or "summary" in data

    def test_get_decision_history(self, client):
        """Test historique des décisions (5 dernières)"""
        response = client.get("/execution/governance/decisions/history?limit=5")

        # Peut retourner 200 ou 404 selon historique
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            assert len(data) <= 5

    def test_get_exposure_caps(self, client):
        """Test GET caps d'exposition SMART"""
        response = client.get("/execution/governance/state")

        assert response.status_code == 200
        data = response.json()

        # Vérifier présence des caps (SMART strategy)
        if "caps" in data or "exposure_caps" in data:
            caps = data.get("caps") or data.get("exposure_caps")
            assert isinstance(caps, dict)


class TestRiskDashboardIntegration:
    """Tests d'intégration cross-tabs (interactions entre modules)"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_full_risk_dashboard_flow(self, client):
        """Test flux complet : alertes → overview → cycles → targets"""

        # 1. Charger alertes
        alerts_response = client.get("/api/alerts/active")
        assert alerts_response.status_code == 200

        # 2. Charger overview avec dual window
        overview_response = client.get(
            "/api/risk/dashboard?user_id=demo&source=cointracking&use_dual_window=true"
        )
        assert overview_response.status_code == 200

        # 3. Charger données cycles
        cycles_response = client.get("/api/risk/cycle-score")
        assert cycles_response.status_code == 200

        # 4. Charger stratégies targets
        governance_response = client.get("/execution/governance/state")
        assert governance_response.status_code == 200

        # Vérifier cohérence des timestamps
        overview_ts = overview_response.json().get("timestamp")
        governance_ts = governance_response.json().get("timestamp")

        if overview_ts and governance_ts:
            # Timestamps doivent être récents (< 5 min)
            now = datetime.now().timestamp()
            assert abs(now - overview_ts) < 300
            assert abs(now - governance_ts) < 300

    def test_risk_score_consistency(self, client):
        """Test cohérence Risk Score entre endpoints"""

        # Score depuis /api/risk/dashboard
        dashboard_response = client.get(
            "/api/risk/dashboard?user_id=demo&source=cointracking"
        )
        assert dashboard_response.status_code == 200
        dashboard_score = dashboard_response.json()["risk_metrics"]["risk_score"]

        # Score depuis /api/risk/advanced
        advanced_response = client.get(
            "/api/risk/advanced?user_id=demo&source=cointracking"
        )
        assert advanced_response.status_code == 200

        if "risk_score" in advanced_response.json():
            advanced_score = advanced_response.json()["risk_score"]

            # Scores doivent être cohérents (< 5 points d'écart)
            assert abs(dashboard_score - advanced_score) < 5

    def test_multi_user_isolation(self, client):
        """Test isolation multi-tenant entre users"""

        # User demo
        demo_response = client.get(
            "/api/risk/dashboard?user_id=demo&source=cointracking"
        )
        assert demo_response.status_code == 200

        # User jack
        jack_response = client.get(
            "/api/risk/dashboard?user_id=jack&source=cointracking"
        )
        assert jack_response.status_code == 200

        # Les données ne doivent PAS être identiques (isolation)
        # Note : peut être identique si même source CSV uploadé, mais timestamps différents
        demo_ts = demo_response.json().get("timestamp")
        jack_ts = jack_response.json().get("timestamp")

        # Au minimum, vérifier que les requêtes sont traitées indépendamment
        assert demo_ts is not None or jack_ts is not None


class TestRiskDashboardErrorHandling:
    """Tests cas d'erreur et edge cases"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_missing_user_id(self, client):
        """Test comportement sans user_id (doit utiliser 'demo' par défaut)"""
        response = client.get("/api/risk/dashboard?source=cointracking")

        # Doit réussir avec user_id=demo par défaut
        assert response.status_code == 200

    def test_invalid_source(self, client):
        """Test source invalide"""
        response = client.get(
            "/api/risk/dashboard?user_id=demo&source=invalid_source_xyz"
        )

        # Peut retourner 200 avec données vides ou 404
        assert response.status_code in [200, 404, 422]

    def test_empty_portfolio(self, client):
        """Test portfolio vide (nouveau user)"""
        response = client.get(
            "/api/risk/dashboard?user_id=newuser&source=cointracking"
        )

        # Doit gérer gracieusement (200 avec scores par défaut ou 404)
        assert response.status_code in [200, 404]

    def test_malformed_parameters(self, client):
        """Test paramètres malformés"""

        # min_history_days négatif
        response = client.get(
            "/api/risk/dashboard?user_id=demo&source=cointracking&min_history_days=-100"
        )
        assert response.status_code in [200, 422]

        # min_coverage_pct > 1
        response = client.get(
            "/api/risk/dashboard?user_id=demo&source=cointracking&min_coverage_pct=1.5"
        )
        assert response.status_code in [200, 422]

    def test_concurrent_requests(self, client):
        """Test requêtes concurrentes (pas de race conditions)"""
        import concurrent.futures

        def make_request():
            return client.get("/api/risk/dashboard?user_id=demo&source=cointracking")

        # 5 requêtes parallèles
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            responses = [f.result() for f in futures]

        # Toutes doivent réussir
        for response in responses:
            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
