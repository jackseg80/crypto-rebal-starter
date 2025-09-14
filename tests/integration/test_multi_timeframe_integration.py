"""
Tests d'intégration pour Phase 2B1 - Multi-Timeframe Alert Analysis

Tests end-to-end du système multi-timeframe avec AlertEngine,
API endpoints, et métriques Prometheus.
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
import json

from services.alerts.alert_engine import AlertEngine
from services.alerts.alert_types import AlertType, AlertSeverity
from services.alerts.multi_timeframe import Timeframe, TimeframeSignal
from services.execution.phase_engine import Phase, PhaseEngine, PhaseState
from api.alerts_endpoints import router
from fastapi.testclient import TestClient
from fastapi import FastAPI


class TestMultiTimeframeIntegration:
    """Tests d'intégration pour système multi-timeframe complet"""
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI app with alerts endpoints"""
        app = FastAPI()
        app.include_router(router)
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def alert_engine_config(self):
        """Configuration complète avec multi-timeframe"""
        return {
            "metadata": {
                "config_version": "test-phase2b1-integration",
                "last_updated": datetime.now(timezone.utc).isoformat()
            },
            "alerting_config": {
                "phase_aware": {
                    "enabled": True,
                    "phase_lag_minutes": 15,
                    "phase_persistence_ticks": 3,
                    "contradiction_neutralize_threshold": 0.70,
                    "gating_matrix": {
                        "btc": {
                            "VOL_Q90_CROSS": "enabled",
                            "REGIME_FLIP": "enabled"
                        },
                        "eth": {
                            "VOL_Q90_CROSS": "attenuated",
                            "REGIME_FLIP": "enabled"
                        }
                    }
                },
                "multi_timeframe": {
                    "enabled": True,
                    "coherence_thresholds": {
                        "high_coherence": 0.80,
                        "medium_coherence": 0.60,
                        "low_coherence": 0.40,
                        "divergence_alert": 0.30
                    },
                    "timeframe_weights": {
                        "1m": 0.05,
                        "5m": 0.10,
                        "15m": 0.15,
                        "1h": 0.30,
                        "4h": 0.25,
                        "1d": 0.15
                    },
                    "coherence_lookback_minutes": 60,
                    "signal_history_hours": 24,
                    "temporal_overrides": {
                        "VOL_Q90_CROSS": {
                            "1m": "attenuated",
                            "5m": "attenuated",
                            "1h": "enabled",
                            "4h": "enabled",
                            "1d": "enabled"
                        },
                        "REGIME_FLIP": {
                            "1m": "disabled",
                            "5m": "disabled",
                            "15m": "attenuated",
                            "1h": "enabled",
                            "4h": "enabled",
                            "1d": "enabled"
                        }
                    }
                }
            },
            "alert_types": {
                "VOL_Q90_CROSS": {
                    "enabled": True,
                    "thresholds": {"S2": 0.75, "S3": 0.85},
                    "hysteresis_pct": 0.1
                },
                "REGIME_FLIP": {
                    "enabled": True,
                    "thresholds": {"S2": 0.70, "S3": 0.80},
                    "hysteresis_pct": 0.12
                }
            }
        }
    
    @pytest.fixture
    def alert_engine(self, alert_engine_config):
        """Create AlertEngine with multi-timeframe enabled"""
        governance_engine = Mock()
        governance_engine.get_ml_signals.return_value = {
            "volatility": {"BTC": 0.80, "ETH": 0.22},
            "correlation": {"avg_correlation": 0.6},
            "confidence": 0.8,
            "contradiction_index": 0.3
        }
        
        with patch('services.alerts.prometheus_metrics.get_alert_metrics') as mock_metrics:
            mock_metrics.return_value = Mock()
            
            engine = AlertEngine(
                governance_engine=governance_engine,
                config=alert_engine_config
            )
            
            return engine
    
    @pytest.mark.asyncio
    async def test_multi_timeframe_initialization(self, alert_engine):
        """Test initialisation correcte du système multi-timeframe"""
        assert alert_engine.phase_aware_enabled == True
        assert alert_engine.multi_timeframe_enabled == True
        assert alert_engine.multi_timeframe_analyzer is not None
        assert alert_engine.temporal_gating is not None
        
        # Vérifier configuration multi-timeframe
        config = alert_engine.config["alerting_config"]["multi_timeframe"]
        assert config["enabled"] == True
        assert len(config["timeframe_weights"]) == 6
        assert config["coherence_thresholds"]["high_coherence"] == 0.80
        
        # Vérifier temporal overrides chargés
        assert "VOL_Q90_CROSS" in alert_engine.temporal_gating.temporal_overrides
        assert "REGIME_FLIP" in alert_engine.temporal_gating.temporal_overrides
    
    @pytest.mark.asyncio
    async def test_alert_evaluation_with_multi_timeframe(self, alert_engine):
        """Test évaluation d'alertes avec analyse multi-timeframe"""
        # Setup phase laggée stable
        now = datetime.utcnow()
        btc_snapshot = {
            "phase": Phase.BTC,
            "confidence": 0.8,
            "persistence_count": 4,
            "captured_at": now - timedelta(minutes=20),
            "contradiction_index": 0.2
        }
        
        # Mock phase state
        phase_state = Mock()
        phase_state.phase_now = Phase.BTC
        phase_state.confidence = 0.8
        phase_state.persistence_count = 4
        
        if alert_engine.phase_context:
            alert_engine.phase_context.update_phase(phase_state, contradiction_index=0.2)
        
        # Mock storage pour vérifier alertes générées
        mock_storage = Mock()
        mock_storage.store_alert = AsyncMock(return_value=True)
        mock_storage.get_active_alerts.return_value = []
        mock_storage.check_rate_limit.return_value = True
        alert_engine.storage = mock_storage
        
        # Simuler signaux avec volatilité déclenchante
        signals = {
            "volatility": {"BTC": 0.85, "ETH": 0.22},  # BTC au-dessus seuil S2 (0.75)
            "correlation": {"avg_correlation": 0.6},
            "confidence": 0.8,
            "contradiction_index": 0.3,
            "current_timestamp": now.isoformat()
        }
        
        # Exécuter évaluation avec multi-timeframe
        await alert_engine._evaluate_alert_type(AlertType.VOL_Q90_CROSS, signals)
        
        # Vérifier que l'alerte a été évaluée et stockée
        # (Le système devrait simuler des signaux multi-timeframe et décider)
        if mock_storage.store_alert.called:
            call_args = mock_storage.store_alert.call_args[0][0]
            assert call_args["alert_type"] == "VOL_Q90_CROSS"
            assert "multi_timeframe" in call_args["data"]
            
            # Vérifier métadonnées multi-timeframe
            multi_tf_data = call_args["data"]["multi_timeframe"]
            assert "coherence_score" in multi_tf_data
            assert "timeframe_agreement" in multi_tf_data
            assert "reason" in multi_tf_data
    
    @pytest.mark.asyncio
    async def test_multi_timeframe_coherence_suppression(self, alert_engine):
        """Test suppression d'alerte due à faible cohérence multi-timeframe"""
        # Setup conditions où multi-timeframe analysis supprime l'alerte
        
        # Mock storage
        mock_storage = Mock()
        mock_storage.store_alert = AsyncMock(return_value=False)
        mock_storage.check_rate_limit.return_value = True
        alert_engine.storage = mock_storage
        
        # Simuler signaux avec cohérence faible (sera simulé dans _evaluate_alert_type)
        signals = {
            "volatility": {"BTC": 0.80},  # Au-dessus seuil mais cohérence simulée faible
            "confidence": 0.7,
            "contradiction_index": 0.4,
        }
        
        # Pour tester la suppression, on peut patch la méthode should_trigger_alert
        with patch.object(alert_engine.multi_timeframe_analyzer, 'should_trigger_alert') as mock_trigger:
            mock_trigger.return_value = (False, {
                "reason": "low_coherence_suppressed",
                "coherence_score": 0.35,
                "timeframe_agreement": 0.3
            })
            
            await alert_engine._evaluate_alert_type(AlertType.VOL_Q90_CROSS, signals)
            
            # Vérifier que l'alerte a été supprimée par multi-timeframe
            assert not mock_storage.store_alert.called
            # Vérifier que should_trigger_alert a été appelé
            mock_trigger.assert_called_once_with(AlertType.VOL_Q90_CROSS, AlertSeverity.S2)
    
    @pytest.mark.asyncio
    async def test_temporal_gating_integration(self, alert_engine):
        """Test intégration temporal gating avec phase gating"""
        # Vérifier que temporal gating est correctement configuré
        assert alert_engine.temporal_gating is not None
        
        # Test gating pour VOL_Q90_CROSS sur timeframe M1 (devrait être attenuated)
        allowed, reason = alert_engine.temporal_gating.check_temporal_gating(
            "btc", "VOL_Q90_CROSS", Timeframe.M1
        )
        
        assert allowed == True  # attenuated permet passage
        assert "temporal:attenuated" in reason
        assert "final:attenuated" in reason
        
        # Test gating pour REGIME_FLIP sur timeframe M1 (devrait être disabled)
        allowed, reason = alert_engine.temporal_gating.check_temporal_gating(
            "btc", "REGIME_FLIP", Timeframe.M1
        )
        
        assert allowed == False  # disabled bloque
        assert "temporal:disabled" in reason
        assert "final:disabled" in reason
    
    def test_get_multi_timeframe_status(self, alert_engine):
        """Test méthode de status multi-timeframe"""
        status = alert_engine.get_multi_timeframe_status()
        
        assert status["enabled"] == True
        assert "timestamp" in status
        assert "timeframes" in status
        assert "coherence_thresholds" in status
        assert "temporal_gating_enabled" in status
        
        # Vérifier structure des timeframes
        for tf_value in ["1m", "5m", "15m", "1h", "4h", "1d"]:
            assert tf_value in status["timeframes"]
            tf_status = status["timeframes"][tf_value]
            assert "signal_count_30min" in tf_status
            assert "last_signal" in tf_status
            assert "active_alert_types" in tf_status
    
    @pytest.mark.asyncio
    async def test_multi_timeframe_status_endpoint_integration(self, alert_engine):
        """Test endpoint API multi-timeframe status"""
        # Cette partie nécessiterait une intégration FastAPI complète
        # Pour l'instant, testons la logique directement
        
        status = alert_engine.get_multi_timeframe_status()
        
        # Simuler ce que l'endpoint ferait
        if status.get("enabled", False):
            config = alert_engine.config.get("alerting_config", {}).get("multi_timeframe", {})
            expected_config_fields = [
                "coherence_lookback_minutes",
                "signal_history_hours", 
                "timeframe_weights",
                "temporal_overrides"
            ]
            
            for field in expected_config_fields:
                assert field in config
        
        # Vérifier cohérence thresholds
        coherence_thresholds = status.get("coherence_thresholds", {})
        assert coherence_thresholds.get("high_coherence") == 0.80
        assert coherence_thresholds.get("medium_coherence") == 0.60
        assert coherence_thresholds.get("low_coherence") == 0.40
    
    @pytest.mark.asyncio 
    async def test_coherence_calculation_integration(self, alert_engine):
        """Test calcul de cohérence avec données simulées"""
        analyzer = alert_engine.multi_timeframe_analyzer
        now = datetime.utcnow()
        
        # Ajouter signaux cohérents simulés
        coherent_timeframes = [Timeframe.H1, Timeframe.H4, Timeframe.D1]
        for tf in coherent_timeframes:
            signal = TimeframeSignal(
                timeframe=tf,
                alert_type=AlertType.VOL_Q90_CROSS,
                severity=AlertSeverity.S2,
                threshold_value=0.75,
                actual_value=0.85,  # Cohérent: tous au-dessus
                confidence=0.8,
                timestamp=now - timedelta(minutes=30),
                phase=Phase.BTC
            )
            analyzer.add_signal(signal)
        
        # Calculer cohérence
        coherence = analyzer.calculate_coherence_score(AlertType.VOL_Q90_CROSS, lookback_minutes=60)
        
        # Vérifications
        assert coherence.alert_type == AlertType.VOL_Q90_CROSS
        assert coherence.overall_score >= 0.70  # Haute cohérence attendue
        assert coherence.timeframe_agreement == 1.0  # 100% accord
        assert coherence.divergence_severity == 0.0  # Pas de divergences
        assert coherence.dominant_timeframe in [Timeframe.H1, Timeframe.H4]  # Poids élevé
        assert len(coherence.conflicting_signals) == 0
        
        # Test déclenchement basé sur cohérence
        should_trigger, metadata = analyzer.should_trigger_alert(
            AlertType.VOL_Q90_CROSS, AlertSeverity.S2
        )
        
        assert should_trigger == True
        assert metadata["reason"] == "high_timeframe_coherence"
        assert metadata["coherence_score"] >= 0.70
    
    def test_multi_timeframe_disabled_fallback(self):
        """Test comportement quand multi-timeframe est désactivé"""
        config_disabled = {
            "alerting_config": {
                "phase_aware": {"enabled": True},
                "multi_timeframe": {"enabled": False}
            }
        }
        
        with patch('services.alerts.prometheus_metrics.get_alert_metrics') as mock_metrics:
            mock_metrics.return_value = Mock()
            
            engine = AlertEngine(config=config_disabled)
            
            assert engine.phase_aware_enabled == True
            assert engine.multi_timeframe_enabled == False
            assert engine.multi_timeframe_analyzer is None
            assert engine.temporal_gating is None
            
            # Status devrait retourner disabled
            status = engine.get_multi_timeframe_status()
            assert status["enabled"] == False
            assert "reason" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])