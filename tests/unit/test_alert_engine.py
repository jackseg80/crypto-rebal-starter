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

from services.alerts.alert_engine import AlertEngine, AlertMetrics, PhaseSnapshot, PhaseAwareContext
from services.alerts.alert_types import Alert, AlertType, AlertSeverity
from services.alerts.alert_storage import AlertStorage
from services.execution.phase_engine import Phase, PhaseEngine
from prometheus_client import CollectorRegistry


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
        """Fichier config temporaire pour tests Phase 2A"""
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
            "phase_aware": {
                "enabled": True,
                "phase_lag_minutes": 15,
                "phase_persistence_ticks": 3,
                "contradiction_neutralize_threshold": 0.70,
                "phase_factors": {
                    "VOL_Q90_CROSS": {"btc": 1.0, "eth": 1.1, "large": 1.2, "alt": 1.3},
                    "CONTRADICTION_SPIKE": {"btc": 1.0, "eth": 1.0, "large": 1.1, "alt": 1.2}
                },
                "gating_matrix": {
                    "btc": {
                        "VOL_Q90_CROSS": "enabled",
                        "CONTRADICTION_SPIKE": "enabled"
                    },
                    "eth": {
                        "VOL_Q90_CROSS": "enabled", 
                        "CONTRADICTION_SPIKE": "attenuated"
                    },
                    "large": {
                        "VOL_Q90_CROSS": "attenuated",
                        "CONTRADICTION_SPIKE": "attenuated"
                    },
                    "alt": {
                        "VOL_Q90_CROSS": "disabled",
                        "CONTRADICTION_SPIKE": "disabled"
                    }
                }
            },
            "metadata": {"config_version": "test-2A.0"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = f.name
        
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture(scope="function")
    def prometheus_registry(self):
        """Fresh Prometheus registry for each test"""
        return CollectorRegistry()
    
    @pytest.fixture
    def alert_engine(self, mock_governance_engine, temp_config_file, prometheus_registry):
        """AlertEngine avec config test"""
        storage = AlertStorage(redis_url=None)  # Force file mode
        
        # Mock prometheus metrics to avoid registry conflicts
        with patch('services.alerts.alert_engine.get_alert_metrics') as mock_metrics:
            mock_metrics.return_value = Mock()
            return AlertEngine(
                governance_engine=mock_governance_engine,
                storage=storage,
                config_file_path=temp_config_file,
                prometheus_registry=prometheus_registry
            )
    
    def test_initialization(self, alert_engine, temp_config_file):
        """Test initialisation avec config file"""
        assert alert_engine.config_file_path == temp_config_file
        assert alert_engine.config["metadata"]["config_version"] == "test-2A.0"
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
    
    @pytest.mark.skip(reason="Test needs to properly inject signals into alert engine - format mismatch")
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
    
    # ===== PHASE 2A TESTS =====
    
    @pytest.fixture
    def mock_phase_engine(self):
        """Mock phase engine pour tests Phase 2A"""
        mock_engine = Mock()
        mock_engine.get_current_phase.return_value = Phase.BTC
        mock_engine.get_phase_confidence.return_value = 0.8
        return mock_engine
    
    def test_phase_aware_initialization(self, alert_engine, temp_config_file):
        """Test initialisation system Phase 2A avec phase-aware config"""
        assert alert_engine.config["metadata"]["config_version"] == "test-2A.0"
        assert alert_engine.config["phase_aware"]["enabled"] is True
        assert alert_engine.config["phase_aware"]["phase_lag_minutes"] == 15
        assert alert_engine.config["phase_aware"]["phase_persistence_ticks"] == 3
        assert alert_engine.config["phase_aware"]["contradiction_neutralize_threshold"] == 0.70
    
    def test_phase_snapshot_creation(self):
        """Test création PhaseSnapshot"""
        snapshot = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=2,
            captured_at=datetime.now(),
            contradiction_index=0.3
        )
        
        assert snapshot.phase == Phase.BTC
        assert snapshot.confidence == 0.8
        assert snapshot.persistence_count == 2
        assert snapshot.contradiction_index == 0.3
    
    def test_phase_aware_context_initialization(self, mock_phase_engine):
        """Test initialisation PhaseAwareContext"""
        context = PhaseAwareContext(lag_minutes=15, persistence_ticks=3)
        
        assert context.lag_minutes == 15
        assert context.persistence_ticks == 3
        assert context.current_lagged_phase is None
        assert len(context.phase_history) == 0
    
    def test_phase_lagging_mechanism(self, mock_phase_engine):
        """Test mécanisme de phase lagging (15 minutes)"""
        context = PhaseAwareContext(lag_minutes=15, persistence_ticks=3)
        
        # Simuler des updates de phase avec timestamps différents
        now = datetime.utcnow()
        
        # Phase ancienne (plus de 15 min) - devrait être utilisée
        old_phase_state = Mock()
        old_phase_state.phase = Phase.BTC
        old_phase_state.confidence = 0.8
        
        # Phase récente (moins de 15 min) - devrait être ignorée  
        recent_phase_state = Mock()
        recent_phase_state.phase = Phase.ETH
        recent_phase_state.confidence = 0.9
        
        # Manually add to history avec timestamps appropriés
        old_snapshot = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=now - timedelta(minutes=20),  # Plus de 15 min
            contradiction_index=0.2
        )
        
        recent_snapshot = PhaseSnapshot(
            phase=Phase.ETH,
            confidence=0.9,
            persistence_count=1, 
            captured_at=now - timedelta(minutes=10),  # Moins de 15 min
            contradiction_index=0.1
        )
        
        context.phase_history.extend([old_snapshot, recent_snapshot])
        
        # get_lagged_phase devrait retourner une phase suffisamment ancienne
        lagged = context.get_lagged_phase()
        assert lagged is not None
        assert lagged.phase == Phase.BTC  # Phase ancienne
    
    def test_phase_persistence_check(self, mock_phase_engine):
        """Test vérification persistance de phase (3 ticks minimum)"""
        config = {
            "phase_lag_minutes": 15,
            "phase_persistence_ticks": 3,
            "contradiction_neutralize_threshold": 0.70
        }
        
        context = PhaseAwareContext(phase_engine=mock_phase_engine, config=config)
        
        # Créer snapshots avec persistance insuffisante
        snapshots = []
        for i in range(2):  # Seulement 2 ticks (< 3)
            snapshot = PhaseSnapshot(
                phase=Phase.BTC,
                confidence=0.8,
                persistence_count=i + 1,
                captured_at=datetime.now() - timedelta(minutes=20 + i),
                contradiction_index=0.2
            )
            snapshots.append(snapshot)
        
        context.snapshot_history = snapshots
        context.current_snapshot = snapshots[-1]
        
        # Pas assez de persistance
        assert not context.has_sufficient_persistence(Phase.BTC)
        
        # Ajouter un 3ème tick
        third_snapshot = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=datetime.now() - timedelta(minutes=18),
            contradiction_index=0.2
        )
        context.snapshot_history.append(third_snapshot)
        context.current_snapshot = third_snapshot
        
        # Maintenant suffisant
        assert context.has_sufficient_persistence(Phase.BTC)
    
    def test_contradiction_neutralization(self, mock_phase_engine):
        """Test neutralisation si contradiction_index > 0.70"""
        config = {
            "phase_lag_minutes": 15,
            "phase_persistence_ticks": 3,
            "contradiction_neutralize_threshold": 0.70
        }
        
        context = PhaseAwareContext(phase_engine=mock_phase_engine, config=config)
        
        # Contradiction élevée (> 0.70) - devrait neutraliser
        high_contradiction = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=datetime.now() - timedelta(minutes=20),
            contradiction_index=0.80  # > 0.70
        )
        
        context.current_snapshot = high_contradiction
        assert context.should_neutralize_alerts()
        
        # Contradiction faible (< 0.70) - ne devrait pas neutraliser
        low_contradiction = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=datetime.now() - timedelta(minutes=20),
            contradiction_index=0.60  # < 0.70
        )
        
        context.current_snapshot = low_contradiction
        assert not context.should_neutralize_alerts()
    
    def test_gating_matrix_application(self, alert_engine):
        """Test application de la gating matrix par phase"""
        # Mock phase context pour retourner différentes phases
        with patch.object(alert_engine, 'phase_context') as mock_context:
            # Test phase BTC - VOL_Q90_CROSS enabled
            mock_context.get_lagged_phase.return_value = Phase.BTC
            mock_context.should_neutralize_alerts.return_value = False
            mock_context.has_sufficient_persistence.return_value = True
            
            gating = alert_engine._get_alert_gating(AlertType.VOL_Q90_CROSS)
            assert gating == "enabled"
            
            # Test phase ALT - VOL_Q90_CROSS disabled
            mock_context.get_lagged_phase.return_value = Phase.ALT
            
            gating = alert_engine._get_alert_gating(AlertType.VOL_Q90_CROSS)
            assert gating == "disabled"
            
            # Test phase ETH - CONTRADICTION_SPIKE attenuated
            mock_context.get_lagged_phase.return_value = Phase.ETH
            
            gating = alert_engine._get_alert_gating(AlertType.CONTRADICTION_SPIKE)
            assert gating == "attenuated"
    
    def test_adaptive_threshold_calculation(self, alert_engine):
        """Test calcul des seuils adaptatifs avec phase factors"""
        base_threshold = 0.75
        alert_type = AlertType.VOL_Q90_CROSS
        
        # Mock phase context pour phase ETH (factor 1.1)
        with patch.object(alert_engine, 'phase_context') as mock_context:
            mock_context.get_lagged_phase.return_value = Phase.ETH
            mock_context.should_neutralize_alerts.return_value = False
            
            adaptive = alert_engine._calculate_adaptive_threshold(base_threshold, alert_type)
            expected = base_threshold * 1.1  # ETH factor from config
            assert adaptive == expected
            
            # Test phase ALT (factor 1.3)
            mock_context.get_lagged_phase.return_value = Phase.ALT
            
            adaptive = alert_engine._calculate_adaptive_threshold(base_threshold, alert_type)
            expected = base_threshold * 1.3  # ALT factor from config
            assert adaptive == expected
    
    @pytest.mark.asyncio
    async def test_anti_circularite_guards(self, alert_engine):
        """Test guards anti-circularité: lag + persistance + contradiction"""
        # Mock storage et evaluator
        alert_engine.storage.store_alert = Mock(return_value=True)
        alert_engine.storage.is_rate_limited = Mock(return_value=False)
        
        # Test 1: Phase lag insufficient (récent changement)
        with patch.object(alert_engine, 'phase_context') as mock_context:
            mock_context.get_lagged_phase.return_value = None  # Pas de phase laggée
            mock_context.should_neutralize_alerts.return_value = False
            mock_context.has_sufficient_persistence.return_value = True
            
            await alert_engine._evaluate_alerts()
            # Aucune alerte ne devrait être générée
            alert_engine.storage.store_alert.assert_not_called()
        
        # Test 2: Persistance insuffisante
        alert_engine.storage.store_alert.reset_mock()
        with patch.object(alert_engine, 'phase_context') as mock_context:
            mock_context.get_lagged_phase.return_value = Phase.BTC
            mock_context.should_neutralize_alerts.return_value = False
            mock_context.has_sufficient_persistence.return_value = False  # Insuffisant
            
            await alert_engine._evaluate_alerts()
            alert_engine.storage.store_alert.assert_not_called()
        
        # Test 3: Contradiction élevée (neutralisation)
        alert_engine.storage.store_alert.reset_mock()
        with patch.object(alert_engine, 'phase_context') as mock_context:
            mock_context.get_lagged_phase.return_value = Phase.BTC
            mock_context.should_neutralize_alerts.return_value = True  # Neutralisation
            mock_context.has_sufficient_persistence.return_value = True
            
            await alert_engine._evaluate_alerts()
            alert_engine.storage.store_alert.assert_not_called()


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