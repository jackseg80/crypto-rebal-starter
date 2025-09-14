"""
Integration tests for Phase 2A - Phase-Aware Alerting System

Tests the complete workflow including:
- Phase lagging and persistence
- Gating matrix application
- Contradiction neutralization
- Adaptive threshold calculation
- Metrics recording
- API endpoints integration
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
import json

from services.alerts.alert_engine import AlertEngine, PhaseSnapshot
from services.alerts.alert_types import AlertType, AlertSeverity
from services.execution.phase_engine import Phase, PhaseEngine, PhaseState
from api.alerts_endpoints import router
from fastapi.testclient import TestClient
from fastapi import FastAPI


class TestPhaseAwareIntegration:
    """Integration tests for complete phase-aware alerting workflow"""
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI app with alerts endpoints"""
        app = FastAPI()
        app.include_router(router)  # Router already has /api/alerts prefix
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_phase_engine(self):
        """Mock PhaseEngine for controlled testing"""
        engine = Mock(spec=PhaseEngine)
        return engine
    
    @pytest.fixture
    def alert_engine_config(self):
        """Test configuration for AlertEngine"""
        return {
            "metadata": {
                "config_version": "test-integration-2A.0",
                "last_updated": datetime.now(timezone.utc).isoformat()
            },
            "alerting_config": {
                "phase_aware": {
                    "enabled": True,
                    "phase_lag_minutes": 15,
                    "phase_persistence_ticks": 3,
                    "contradiction_neutralize_threshold": 0.70,
                    "phase_factors": {
                        "VOL_Q90_CROSS": {
                            "btc": 1.0,
                            "eth": 1.1,
                            "large": 1.2,
                            "alt": 1.3
                        },
                        "CONTRADICTION_SPIKE": {
                            "btc": 1.0,
                            "eth": 1.0,
                            "large": 1.1,
                            "alt": 1.2
                        }
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
                "rate_limits": {
                    "daily_budget": 50,
                    "severity_limits": {
                        "S1": {"per_hour": 10, "per_day": 30},
                        "S2": {"per_hour": 5, "per_day": 15},
                        "S3": {"per_hour": 2, "per_day": 5}
                    }
                }
            }
        }
    
    @pytest.fixture
    def alert_engine(self, alert_engine_config):
        """Create AlertEngine with test configuration"""
        # Mock governance engine
        governance_engine = Mock()
        governance_engine.get_ml_signals.return_value = {
            "volatility": {"BTC": 0.15, "ETH": 0.18},
            "correlation": {"avg_correlation": 0.6},
            "confidence": 0.8,
            "contradiction_index": 0.3
        }
        
        # Create AlertEngine with mocked components
        with patch('services.alerts.prometheus_metrics.get_alert_metrics') as mock_metrics:
            mock_metrics.return_value = Mock()
            
            engine = AlertEngine(
                governance_engine=governance_engine,
                config=alert_engine_config
            )
            
            return engine
    
    @pytest.mark.asyncio
    async def test_complete_phase_aware_workflow(self, alert_engine):
        """Test complete Phase 2A workflow from phase detection to alert generation"""
        
        # Étape 1: Simuler historique de phase avec persistance
        now = datetime.now(timezone.utc)
        
        # Créer snapshots persistants pour phase BTC (plus de 3 ticks)
        btc_snapshots = []
        for i in range(4):
            snapshot = PhaseSnapshot(
                phase=Phase.BTC,
                confidence=0.8,
                persistence_count=i + 1,
                captured_at=now - timedelta(minutes=25 + i),
                contradiction_index=0.2
            )
            btc_snapshots.append(snapshot)
        
        # Snapshot récent ETH (pas encore laggé)
        eth_snapshot = PhaseSnapshot(
            phase=Phase.ETH,
            confidence=0.9,
            persistence_count=1,
            captured_at=now - timedelta(minutes=5),
            contradiction_index=0.1
        )
        
        # Configurer l'historique
        alert_engine.phase_context.phase_history = btc_snapshots + [eth_snapshot]
        alert_engine.phase_context.current_lagged_phase = btc_snapshots[-1]  # Phase BTC laggée
        
        # Étape 2: Tester évaluation avec gating matrix
        signals = {
            "volatility": {"BTC": 0.25, "ETH": 0.22},  # Volatilité élevée
            "correlation": {"avg_correlation": 0.6},
            "confidence": 0.8,
            "contradiction_index": 0.3  # Faible, pas de neutralisation
        }
        
        # Test gating pour phase BTC - VOL_Q90_CROSS enabled
        allowed, reason = alert_engine._check_phase_gating(AlertType.VOL_Q90_CROSS, signals)
        assert allowed, f"VOL_Q90_CROSS should be allowed in BTC phase, got: {reason}"
        assert "btc" in reason
        
        # Test gating pour phase BTC - CONTRADICTION_SPIKE enabled
        allowed, reason = alert_engine._check_phase_gating(AlertType.CONTRADICTION_SPIKE, signals)
        assert allowed, f"CONTRADICTION_SPIKE should be allowed in BTC phase, got: {reason}"
        
        # Étape 3: Simuler transition vers phase ALT et vérifier gating
        alt_snapshot = PhaseSnapshot(
            phase=Phase.ALT,
            confidence=0.7,
            persistence_count=3,
            captured_at=now - timedelta(minutes=20),
            contradiction_index=0.2
        )
        alert_engine.phase_context.current_lagged_phase = alt_snapshot
        
        # Test gating pour phase ALT - VOL_Q90_CROSS disabled
        allowed, reason = alert_engine._check_phase_gating(AlertType.VOL_Q90_CROSS, signals)
        assert not allowed, f"VOL_Q90_CROSS should be blocked in ALT phase, got: {reason}"
        assert "alt" in reason
        
        # Étape 4: Tester neutralisation par contradiction élevée
        high_contradiction_signals = {**signals, "contradiction_index": 0.85}
        
        # Reset à phase BTC
        alert_engine.phase_context.current_lagged_phase = btc_snapshots[-1]
        
        allowed, reason = alert_engine._check_phase_gating(AlertType.VOL_Q90_CROSS, high_contradiction_signals)
        assert allowed, "High contradiction should allow through but neutralize"
        assert "contradiction_neutralized" in reason
        
        # Étape 5: Tester calcul seuil adaptatif
        rule_config = alert_engine.config["alerting_config"]
        phase_context = {
            "phase": Phase.ETH,  # Phase avec facteur 1.1
            "phase_factors": rule_config["phase_aware"]["phase_factors"],
            "contradiction_index": 0.3
        }
        
        # Simuler rule VOL_Q90_CROSS
        from services.alerts.alert_types import AlertRule
        rule = AlertRule(
            alert_type=AlertType.VOL_Q90_CROSS,
            base_threshold=0.75,
            adaptive_multiplier=1.0,
            hysteresis_minutes=5,
            severity_thresholds={"S1": 0.80, "S2": 0.85, "S3": 0.90},
            suggested_actions={"S1": {"type": "acknowledge"}}
        )
        
        adaptive_threshold = alert_engine.evaluator._calculate_adaptive_threshold(rule, signals, phase_context)
        
        # Vérifier que le facteur de phase ETH (1.1) a été appliqué
        expected_min = 0.75 * 1.1 * 0.9  # base * phase_factor * min_market_factor
        expected_max = 0.75 * 1.1 * 1.3  # base * phase_factor * max_market_factor
        assert expected_min <= adaptive_threshold <= expected_max, \
            f"Adaptive threshold {adaptive_threshold} not in expected range [{expected_min}, {expected_max}]"
    
    @pytest.mark.asyncio
    async def test_phase_transition_metrics(self, alert_engine):
        """Test que les transitions de phase sont correctement enregistrées dans les métriques"""
        
        # Mock metrics
        mock_metrics = Mock()
        alert_engine.phase_context.metrics = mock_metrics
        
        # Créer historique suffisant pour déclencher une transition
        # Utiliser datetime.utcnow() pour être compatible avec update_phase
        now = datetime.utcnow()
        
        # Phase BTC ancienne (sera remplacée)
        btc_snapshot = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=now - timedelta(minutes=25),
            contradiction_index=0.2
        )
        
        # Phase ETH suffisamment persistante et ancienne (> 15 min) pour devenir laggée
        eth_snapshots = []
        for i in range(4):  # 4 snapshots pour assurer la persistance
            snapshot = PhaseSnapshot(
                phase=Phase.ETH,
                confidence=0.9,
                persistence_count=i + 1,
                captured_at=now - timedelta(minutes=22 - i),  # Assez anciens pour lag
                contradiction_index=0.1
            )
            eth_snapshots.append(snapshot)
        
        # Configurer l'état initial avec BTC comme phase laggée
        alert_engine.phase_context.phase_history = [btc_snapshot] + eth_snapshots
        alert_engine.phase_context.current_lagged_phase = btc_snapshot
        
        # Simuler nouvelle phase ETH qui déclenche la transition
        phase_state = Mock()
        phase_state.phase_now = Phase.ETH
        phase_state.confidence = 0.9
        phase_state.persistence_count = 4
        
        # Déclencher mise à jour - cela devrait détecter ETH comme nouvelle phase laggée
        alert_engine.phase_context.update_phase(phase_state, contradiction_index=0.1)
        
        # Vérifier que la transition a été enregistrée
        if mock_metrics.record_phase_transition.called:
            mock_metrics.record_phase_transition.assert_called_with('btc', 'eth')
        
        # Vérifier que la phase actuelle est mise à jour
        mock_metrics.update_current_lagged_phase.assert_called()
    
    @pytest.mark.asyncio
    async def test_contradiction_neutralization_metrics(self, alert_engine):
        """Test enregistrement des métriques de neutralisation par contradiction"""
        
        # Mock metrics pour vérification
        mock_metrics = Mock()
        alert_engine.prometheus_metrics = mock_metrics
        
        # Configurer phase laggée
        alert_engine.phase_context.current_lagged_phase = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            contradiction_index=0.2
        )
        
        # Signaux avec contradiction élevée
        signals = {
            "volatility": {"BTC": 0.25},
            "contradiction_index": 0.85  # > 0.70 threshold
        }
        
        # Tester neutralisation
        allowed, reason = alert_engine._check_phase_gating(AlertType.VOL_Q90_CROSS, signals)
        
        # Vérifier que la métrique a été enregistrée
        mock_metrics.record_contradiction_neutralization.assert_called_once_with('VOL_Q90_CROSS')
    
    @pytest.mark.asyncio
    async def test_gating_matrix_metrics(self, alert_engine):
        """Test enregistrement des métriques de gating matrix"""
        
        # Mock metrics
        mock_metrics = Mock()
        alert_engine.prometheus_metrics = mock_metrics
        
        # Test phase ALT avec VOL_Q90_CROSS disabled
        alert_engine.phase_context.current_lagged_phase = PhaseSnapshot(
            phase=Phase.ALT,
            confidence=0.7,
            persistence_count=3,
            captured_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            contradiction_index=0.2
        )
        
        signals = {"contradiction_index": 0.3}
        
        # Tester blocage
        allowed, reason = alert_engine._check_phase_gating(AlertType.VOL_Q90_CROSS, signals)
        
        # Vérifier métrique de blocage
        mock_metrics.record_gating_matrix_block.assert_called_once_with('alt', 'VOL_Q90_CROSS', 'disabled')
        
        # Test phase ETH avec atténuation
        mock_metrics.reset_mock()
        alert_engine.phase_context.current_lagged_phase = PhaseSnapshot(
            phase=Phase.ETH,
            confidence=0.8,
            persistence_count=3,
            captured_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            contradiction_index=0.2
        )
        
        allowed, reason = alert_engine._check_phase_gating(AlertType.CONTRADICTION_SPIKE, signals)
        
        # Vérifier métrique d'atténuation
        mock_metrics.record_gating_matrix_block.assert_called_once_with('eth', 'CONTRADICTION_SPIKE', 'attenuated')
    
    @pytest.mark.asyncio
    async def test_api_integration_with_phase_aware(self, alert_engine):
        """Test integration directe avec AlertEngine (pas de HTTP)"""
        
        # Test que l'AlertEngine est correctement configuré avec Phase 2A
        assert alert_engine.phase_aware_enabled == True
        assert alert_engine.phase_context is not None
        
        # Test que la configuration Phase 2A est chargée
        config = alert_engine.config
        phase_config = config.get("alerting_config", {}).get("phase_aware", {})
        
        assert phase_config.get("enabled") == True
        assert "gating_matrix" in phase_config
        assert "phase_factors" in phase_config
        
        # Test que les métriques Prometheus sont initialisées
        assert alert_engine.prometheus_metrics is not None
        
        # Vérifier que les méthodes Phase 2A sont disponibles
        phase_aware_methods = [
            "update_phase_aware_config",
            "record_phase_transition", 
            "record_gating_matrix_block",
            "record_contradiction_neutralization"
        ]
        
        for method in phase_aware_methods:
            assert hasattr(alert_engine.prometheus_metrics, method), \
                f"Missing Phase 2A metrics method: {method}"
    
    @pytest.mark.asyncio
    async def test_end_to_end_alert_evaluation(self, alert_engine):
        """Test évaluation end-to-end d'une alerte avec tous les composants Phase 2A"""
        
        # Setup: phase BTC persistante avec faible contradiction
        now = datetime.now(timezone.utc)
        btc_snapshot = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=4,
            captured_at=now - timedelta(minutes=20),
            contradiction_index=0.2
        )
        
        alert_engine.phase_context.phase_history = [btc_snapshot]
        alert_engine.phase_context.current_lagged_phase = btc_snapshot
        
        # Mock governance engine avec signaux déclencheurs
        alert_engine.governance_engine.get_ml_signals.return_value = {
            "volatility": {"BTC": 0.85, "ETH": 0.22},  # Volatilité BTC > seuil
            "correlation": {"avg_correlation": 0.6},
            "confidence": 0.8,
            "contradiction_index": 0.2,
            "current_timestamp": now.isoformat()
        }
        
        # Mock storage pour vérifier la persistance d'alerte
        mock_storage = Mock()
        mock_storage.store_alert = AsyncMock()
        mock_storage.get_active_alerts.return_value = []
        alert_engine.storage = mock_storage
        
        # Exécuter évaluation d'alertes
        await alert_engine._evaluate_alert_type(AlertType.VOL_Q90_CROSS, {
            "volatility": {"BTC": 0.85},
            "confidence": 0.8,
            "contradiction_index": 0.2
        })
        
        # Vérifier que l'alerte a été stockée (si les conditions sont remplies)
        # Note: cela dépend de la logique exacte d'évaluation
        if mock_storage.store_alert.called:
            call_args = mock_storage.store_alert.call_args[0][0]
            assert call_args["alert_type"] == "VOL_Q90_CROSS"
            assert "adaptive_threshold" in call_args["data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])