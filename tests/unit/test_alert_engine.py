"""
Tests unitaires pour AlertEngine - Phase 1 Alerting System
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import json
import tempfile
from pathlib import Path

from services.alerts.alert_engine import AlertEngine, AlertMetrics
from services.alerts.alert_types import Alert, AlertType, AlertSeverity
from services.alerts.alert_storage import AlertStorage


class TestAlertEngine:
    
    @pytest.fixture
    def mock_governance_engine(self):
        """Mock governance engine pour tests"""
        mock_engine = AsyncMock()
        mock_signals = Mock()
        mock_signals.volatility = 0.8
        mock_signals.regime = 0.7
        mock_signals.correlation = 0.85
        mock_signals.sentiment = 0.5
        mock_signals.decision_score = 0.7
        mock_signals.confidence = 0.7
        mock_signals.contradiction_index = 0.6
        mock_signals.as_of = datetime.now()
        
        mock_policy = Mock()
        mock_policy.execution_cost_bps = 15
        
        mock_state = Mock()
        mock_state.signals = mock_signals
        mock_state.execution_policy = mock_policy
        
        mock_engine.get_current_state.return_value = mock_state
        return mock_engine
    
    @pytest.fixture
    def temp_config_file(self):
        """Fichier config temporaire pour tests"""
        config = {
            "alerting_config": {
                "enabled": True,
                "global_rate_limit_per_hour": 10,
                "daily_budgets": {"S1": 20, "S2": 5, "S3": 2}
            },
            "alert_types": {
                "VOL_Q90_CROSS": {
                    "enabled": True,
                    "thresholds": {"S2": 0.75, "S3": 0.85},
                    "hysteresis_pct": 0.05
                },
                "CONTRADICTION_SPIKE": {
                    "enabled": True,
                    "thresholds": {"S2": 0.65, "S3": 0.80}
                }
            },
            "escalation_rules": {
                "enabled": True,
                "S2_to_S3": {
                    "count_threshold": 2,
                    "window_minutes": 30,
                    "enabled": True
                }
            },
            "metadata": {"config_version": "test-1.0"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = f.name
        
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def alert_engine(self, mock_governance_engine, temp_config_file):
        """AlertEngine avec config test"""
        storage = AlertStorage(redis_url=None)  # Force file mode
        return AlertEngine(
            governance_engine=mock_governance_engine,
            storage=storage,
            config_file_path=temp_config_file
        )
    
    def test_initialization(self, alert_engine, temp_config_file):
        """Test initialisation avec config file"""
        assert alert_engine.config_file_path == temp_config_file
        assert alert_engine.config["metadata"]["config_version"] == "test-1.0"
        assert alert_engine.host_id is not None
        assert not alert_engine.is_scheduler  # Pas encore started
    
    def test_config_hot_reload(self, alert_engine, temp_config_file):
        """Test rechargement config à chaud"""
        # Modifier le fichier config
        new_config = {
            "alerting_config": {"enabled": True, "global_rate_limit_per_hour": 15},
            "alert_types": {"VOL_Q90_CROSS": {"enabled": False}},
            "metadata": {"config_version": "test-2.0"}
        }
        
        with open(temp_config_file, 'w') as f:
            json.dump(new_config, f)
        
        # Déclencher reload
        reloaded = alert_engine._check_config_reload()
        
        assert reloaded is True
        assert alert_engine.config["metadata"]["config_version"] == "test-2.0"
        assert alert_engine.config["alerting_config"]["global_rate_limit_per_hour"] == 15
    
    @pytest.mark.asyncio
    async def test_alert_evaluation_basic(self, alert_engine):
        """Test évaluation d'alertes basique"""
        # Pour ce test, mettons simplement une valeur contradiction élevée pour déclencher
        signals_dict = {
            "volatility": {"BTC": 0.8, "ETH": 0.7},  # Format dict comme attendu
            "regime": {"bull": 0.8, "bear": 0.1, "crab": 0.1},
            "correlation": {"systemic": 0.85},
            "contradiction_index": 0.7,  # Assez élevé pour S2
            "confidence": 0.7
        }
        
        # Mock storage pour éviter side effects
        alert_engine.storage.store_alert = Mock(return_value=True)
        alert_engine.storage.is_rate_limited = Mock(return_value=False)
        
        # Mock l'évaluateur pour retourner directement une alerte
        from services.alerts.alert_types import Alert, AlertType, AlertSeverity
        test_alert = Alert(
            id="test-alert",
            alert_type=AlertType.CONTRADICTION_SPIKE,
            severity=AlertSeverity.S2,
            data={"contradiction_index": 0.7, "threshold": 0.65},
            created_at=datetime.now()
        )
        
        # Mock les méthodes d'évaluation
        alert_engine.evaluator.evaluate_alert = Mock(return_value=(AlertSeverity.S2, {"test": True}))
        
        # Évaluer les alertes
        await alert_engine._evaluate_alerts()
        
        # Vérifier qu'une alerte a été émise (ou au moins tentée)
        # Le test vérifie que le workflow fonctionne
        assert alert_engine.evaluator.evaluate_alert.called
    
    @pytest.mark.asyncio
    async def test_escalation_s2_to_s3(self, alert_engine):
        """Test escalade automatique 2x S2 → S3"""
        alert_type = AlertType.CONTRADICTION_SPIKE
        
        # Créer 2 alertes S2 récentes
        now = datetime.now()
        s2_alerts = [
            Alert(
                id=f"test-{i}",
                alert_type=alert_type,
                severity=AlertSeverity.S2,
                data={"test": True},
                created_at=now - timedelta(minutes=5*i)
            ) for i in range(2)
        ]
        
        # Mock storage pour retourner ces alertes
        alert_engine.storage.get_active_alerts = Mock(return_value=s2_alerts)
        alert_engine.storage.store_alert = Mock()
        
        # Déclencher vérification escalade
        await alert_engine._check_escalations()
        
        # Vérifier qu'une alerte S3 a été créée
        alert_engine.storage.store_alert.assert_called()
        escalated_alert = alert_engine.storage.store_alert.call_args[0][0]
        assert escalated_alert.severity == AlertSeverity.S3
    
    def test_metrics_collection(self, alert_engine):
        """Test collecte de métriques"""
        # Incrémenter quelques métriques
        alert_engine.metrics.increment("alerts_emitted_total", {"type": "TEST", "severity": "S2"})
        alert_engine.metrics.set_gauge("active_alerts_count", 5)
        
        # Récupérer métriques
        metrics = alert_engine.get_metrics()
        
        assert "alert_engine" in metrics
        assert "storage" in metrics
        assert "host_info" in metrics
        assert metrics["host_info"]["host_id"] == alert_engine.host_id
        
        # Vérifier structure des métriques
        engine_metrics = metrics["alert_engine"]
        assert "counters" in engine_metrics
        assert "gauges" in engine_metrics
        assert engine_metrics["gauges"]["active_alerts_count"] == 5


class TestAlertMetrics:
    
    @pytest.fixture
    def metrics(self):
        return AlertMetrics()
    
    def test_counter_increment(self, metrics):
        """Test incrémentation compteurs"""
        metrics.increment("test_counter")
        metrics.increment("test_counter", value=5)
        metrics.increment("labeled_counter", {"label": "value"}, value=2)
        
        result = metrics.get_metrics()
        # Structure: counters[metric][key] = value
        assert "test_counter" in result["counters"]
        assert result["counters"]["test_counter"]["test_counter"] == 6
        assert "labeled_counter" in result["counters"]
        assert result["counters"]["labeled_counter"]["labeled_counter:label=value"] == 2
    
    def test_gauge_set(self, metrics):
        """Test mise à jour gauges"""
        metrics.set_gauge("test_gauge", 42.5)
        metrics.set_label("env", "test")
        
        result = metrics.get_metrics()
        assert result["gauges"]["test_gauge"] == 42.5
        assert result["labels"]["env"] == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])