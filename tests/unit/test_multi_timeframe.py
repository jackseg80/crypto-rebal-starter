"""
Tests unitaires pour le système Multi-Timeframe Analysis (Phase 2B1)

Tests complets pour la cohérence multi-timeframe, temporal gating,
et performance des algorithmes de détection de divergences.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from services.alerts.multi_timeframe import (
    MultiTimeframeAnalyzer, TemporalGatingMatrix, Timeframe, 
    TimeframeSignal, CoherenceScore
)
from services.alerts.alert_types import AlertType, AlertSeverity
from services.execution.phase_engine import Phase


class TestMultiTimeframeAnalyzer:
    """Tests pour l'analyseur multi-timeframe"""
    
    @pytest.fixture
    def analyzer_config(self):
        return {
            "coherence_thresholds": {
                "high_coherence": 0.80,
                "medium_coherence": 0.60,
                "low_coherence": 0.40,
                "divergence_alert": 0.30
            },
            "coherence_lookback_minutes": 60,
            "signal_history_hours": 24
        }
    
    @pytest.fixture
    def analyzer(self, analyzer_config):
        return MultiTimeframeAnalyzer(analyzer_config)
    
    def test_analyzer_initialization(self, analyzer):
        """Test initialisation correcte de l'analyseur"""
        assert analyzer.config is not None
        assert len(analyzer.timeframes) == 6
        assert Timeframe.H1 in analyzer.timeframes
        assert analyzer.timeframe_weights[Timeframe.H1] == 0.30  # Timeframe dominant
        assert analyzer.coherence_thresholds["high_coherence"] == 0.80
    
    def test_add_signal(self, analyzer):
        """Test ajout de signaux avec nettoyage automatique"""
        now = datetime.utcnow()
        
        # Ajouter signal récent
        signal1 = TimeframeSignal(
            timeframe=Timeframe.H1,
            alert_type=AlertType.VOL_Q90_CROSS,
            severity=AlertSeverity.S2,
            threshold_value=0.75,
            actual_value=0.85,
            confidence=0.8,
            timestamp=now,
            phase=Phase.BTC
        )
        
        analyzer.add_signal(signal1)
        assert len(analyzer.signal_history[Timeframe.H1]) == 1
        
        # Ajouter signal ancien (sera nettoyé)
        signal_old = TimeframeSignal(
            timeframe=Timeframe.H1,
            alert_type=AlertType.VOL_Q90_CROSS,
            severity=AlertSeverity.S2,
            threshold_value=0.75,
            actual_value=0.85,
            confidence=0.8,
            timestamp=now - timedelta(hours=25),  # > 24h
            phase=Phase.BTC
        )
        
        analyzer.add_signal(signal_old)
        # Signal ancien devrait être nettoyé
        assert len(analyzer.signal_history[Timeframe.H1]) == 1
        assert analyzer.signal_history[Timeframe.H1][0].timestamp == now
    
    def test_coherence_calculation_high(self, analyzer):
        """Test calcul cohérence élevée (signaux alignés)"""
        now = datetime.utcnow()
        
        # Ajouter signaux cohérents sur plusieurs timeframes
        timeframes = [Timeframe.M15, Timeframe.H1, Timeframe.H4]
        for tf in timeframes:
            signal = TimeframeSignal(
                timeframe=tf,
                alert_type=AlertType.VOL_Q90_CROSS,
                severity=AlertSeverity.S2,
                threshold_value=0.75,
                actual_value=0.85,  # Tous au-dessus du seuil (direction positive)
                confidence=0.8,
                timestamp=now - timedelta(minutes=30),
                phase=Phase.BTC
            )
            analyzer.add_signal(signal)
        
        coherence = analyzer.calculate_coherence_score(AlertType.VOL_Q90_CROSS)
        
        assert coherence.alert_type == AlertType.VOL_Q90_CROSS
        assert coherence.timeframe_agreement == 1.0  # 100% accord
        assert coherence.overall_score >= 0.80  # High coherence
        assert coherence.divergence_severity == 0.0  # Pas de divergences
        assert coherence.dominant_timeframe == Timeframe.H1  # Plus haut poids
        assert len(coherence.conflicting_signals) == 0
    
    def test_coherence_calculation_divergent(self, analyzer):
        """Test calcul cohérence avec divergences"""
        now = datetime.utcnow()
        
        # H1: signal positif (au-dessus seuil)
        signal_h1 = TimeframeSignal(
            timeframe=Timeframe.H1,
            alert_type=AlertType.VOL_Q90_CROSS,
            severity=AlertSeverity.S2,
            threshold_value=0.75,
            actual_value=0.85,  # Positif
            confidence=0.8,
            timestamp=now - timedelta(minutes=30),
        )
        
        # H4: signal négatif (en-dessous seuil)
        signal_h4 = TimeframeSignal(
            timeframe=Timeframe.H4,
            alert_type=AlertType.VOL_Q90_CROSS,
            severity=AlertSeverity.S2,
            threshold_value=0.75,
            actual_value=0.65,  # Négatif
            confidence=0.8,
            timestamp=now - timedelta(minutes=30),
        )
        
        analyzer.add_signal(signal_h1)
        analyzer.add_signal(signal_h4)
        
        coherence = analyzer.calculate_coherence_score(AlertType.VOL_Q90_CROSS)
        
        assert coherence.timeframe_agreement == 0.5  # 50% accord seulement
        assert coherence.overall_score < 0.60  # Low coherence
        assert coherence.divergence_severity > 0.0  # Divergences détectées
        assert len(coherence.conflicting_signals) > 0
        
        # Vérifier que le conflit H1-H4 est détecté
        conflict_pairs = [(tf1.value, tf2.value) for tf1, tf2 in coherence.conflicting_signals]
        assert ("1h", "4h") in conflict_pairs or ("4h", "1h") in conflict_pairs
    
    def test_should_trigger_alert_high_coherence(self, analyzer):
        """Test déclenchement avec haute cohérence"""
        now = datetime.utcnow()
        
        # Simuler signaux cohérents
        for tf in [Timeframe.H1, Timeframe.H4, Timeframe.D1]:
            signal = TimeframeSignal(
                timeframe=tf,
                alert_type=AlertType.VOL_Q90_CROSS,
                severity=AlertSeverity.S2,
                threshold_value=0.75,
                actual_value=0.90,
                confidence=0.8,
                timestamp=now - timedelta(minutes=30)
            )
            analyzer.add_signal(signal)
        
        should_trigger, metadata = analyzer.should_trigger_alert(
            AlertType.VOL_Q90_CROSS, AlertSeverity.S2
        )
        
        assert should_trigger == True
        assert metadata["reason"] == "high_timeframe_coherence"
        assert metadata["confidence_boost"] == 0.2
        assert metadata["coherence_score"] >= 0.80
    
    def test_should_trigger_alert_low_coherence(self, analyzer):
        """Test suppression avec faible cohérence"""
        now = datetime.utcnow()
        
        # Simuler signaux divergents
        signal_pos = TimeframeSignal(
            timeframe=Timeframe.H1,
            alert_type=AlertType.VOL_Q90_CROSS,
            severity=AlertSeverity.S2,
            threshold_value=0.75,
            actual_value=0.85,  # Positif
            confidence=0.8,
            timestamp=now - timedelta(minutes=30)
        )
        
        signal_neg = TimeframeSignal(
            timeframe=Timeframe.H4,
            alert_type=AlertType.VOL_Q90_CROSS,
            severity=AlertSeverity.S2,
            threshold_value=0.75,
            actual_value=0.45,  # Négatif
            confidence=0.8,
            timestamp=now - timedelta(minutes=30)
        )
        
        analyzer.add_signal(signal_pos)
        analyzer.add_signal(signal_neg)
        
        should_trigger, metadata = analyzer.should_trigger_alert(
            AlertType.VOL_Q90_CROSS, AlertSeverity.S2
        )
        
        assert should_trigger == False
        assert "low_coherence" in metadata["reason"] or "divergence" in metadata["reason"]
        assert metadata["coherence_score"] < 0.60
    
    def test_should_trigger_alert_critical_override(self, analyzer):
        """Test override pour alertes critiques même en cas de divergence"""
        now = datetime.utcnow()
        
        # Simuler divergence modérée avec alerte S3 (critique)
        signal_pos = TimeframeSignal(
            timeframe=Timeframe.H1,
            alert_type=AlertType.VOL_Q90_CROSS,
            severity=AlertSeverity.S3,
            threshold_value=0.75,
            actual_value=0.95,
            confidence=0.8,
            timestamp=now - timedelta(minutes=30)
        )
        
        signal_neg = TimeframeSignal(
            timeframe=Timeframe.H4,
            alert_type=AlertType.VOL_Q90_CROSS,
            severity=AlertSeverity.S3,
            threshold_value=0.75,
            actual_value=0.65,
            confidence=0.8,
            timestamp=now - timedelta(minutes=30)
        )
        
        analyzer.add_signal(signal_pos)
        analyzer.add_signal(signal_neg)
        
        should_trigger, metadata = analyzer.should_trigger_alert(
            AlertType.VOL_Q90_CROSS, AlertSeverity.S3
        )
        
        # Les alertes critiques doivent passer même avec divergence modérée
        if metadata.get("divergence_severity", 0) < 0.8:
            assert should_trigger == True
            assert "critical" in metadata["reason"]
            assert metadata.get("confidence_penalty") < 0  # Penalty présente mais variable
    
    def test_get_timeframe_status(self, analyzer):
        """Test statut des timeframes"""
        now = datetime.utcnow()
        
        # Ajouter quelques signaux récents
        signal1 = TimeframeSignal(
            timeframe=Timeframe.H1,
            alert_type=AlertType.VOL_Q90_CROSS,
            severity=AlertSeverity.S2,
            threshold_value=0.75,
            actual_value=0.85,
            confidence=0.8,
            timestamp=now - timedelta(minutes=15)
        )
        
        signal2 = TimeframeSignal(
            timeframe=Timeframe.H1,
            alert_type=AlertType.REGIME_FLIP,
            severity=AlertSeverity.S3,
            threshold_value=0.80,
            actual_value=0.95,
            confidence=0.9,
            timestamp=now - timedelta(minutes=10)
        )
        
        analyzer.add_signal(signal1)
        analyzer.add_signal(signal2)
        
        status = analyzer.get_timeframe_status()
        
        assert "timestamp" in status
        assert "timeframes" in status
        assert "overall_health" in status
        
        # Vérifier status H1 (a des signaux)
        h1_status = status["timeframes"]["1h"]
        assert h1_status["signal_count_30min"] == 2
        assert h1_status["last_signal"] is not None
        assert "VOL_Q90_CROSS" in h1_status["active_alert_types"]
        assert "REGIME_FLIP" in h1_status["active_alert_types"]
        
        # Vérifier status M1 (pas de signaux)
        m1_status = status["timeframes"]["1m"]
        assert m1_status["signal_count_30min"] == 0
        assert m1_status["last_signal"] is None


class TestTemporalGatingMatrix:
    """Tests pour la gating matrix temporelle"""
    
    @pytest.fixture
    def base_gating_matrix(self):
        return {
            "btc": {
                "VOL_Q90_CROSS": "enabled",
                "REGIME_FLIP": "enabled"
            },
            "eth": {
                "VOL_Q90_CROSS": "attenuated",
                "REGIME_FLIP": "enabled"
            }
        }
    
    @pytest.fixture
    def temporal_gating(self, base_gating_matrix):
        return TemporalGatingMatrix(base_gating_matrix)
    
    def test_temporal_gating_initialization(self, temporal_gating):
        """Test initialisation avec temporal overrides"""
        assert temporal_gating.base_matrix is not None
        assert "VOL_Q90_CROSS" in temporal_gating.temporal_overrides
        assert "REGIME_FLIP" in temporal_gating.temporal_overrides
        
        # Vérifier règles pour VOL_Q90_CROSS
        vol_rules = temporal_gating.temporal_overrides["VOL_Q90_CROSS"]
        assert vol_rules[Timeframe.M1] == "attenuated"  # Timeframes courts atténués
        assert vol_rules[Timeframe.H1] == "enabled"     # Timeframe de référence
        assert vol_rules[Timeframe.D1] == "enabled"     # Timeframe fort
        
        # Vérifier règles pour REGIME_FLIP
        regime_rules = temporal_gating.temporal_overrides["REGIME_FLIP"]
        assert regime_rules[Timeframe.M1] == "disabled"   # Trop de bruit
        assert regime_rules[Timeframe.D1] == "enabled"    # Signal le plus fiable
    
    def test_temporal_gating_base_rule_only(self, temporal_gating):
        """Test gating avec seulement règle de base (pas d'override temporel)"""
        # CONTRADICTION_SPIKE n'a pas d'override temporel
        allowed, reason = temporal_gating.check_temporal_gating(
            "btc", "CONTRADICTION_SPIKE", Timeframe.H1
        )
        
        assert allowed == True
        assert "phase:btc" in reason
        assert "timeframe:1h" in reason
        assert "base:enabled" in reason
        assert "final:enabled" in reason
        assert "temporal:" not in reason  # Pas d'override temporel
    
    def test_temporal_gating_with_override(self, temporal_gating):
        """Test gating avec override temporel"""
        # VOL_Q90_CROSS avec M1 (override: attenuated)
        allowed, reason = temporal_gating.check_temporal_gating(
            "btc", "VOL_Q90_CROSS", Timeframe.M1
        )
        
        assert allowed == True  # attenuated permet passage
        assert "phase:btc" in reason
        assert "timeframe:1m" in reason
        assert "base:enabled" in reason
        assert "temporal:attenuated" in reason
        assert "final:attenuated" in reason
    
    def test_temporal_gating_most_restrictive_wins(self, temporal_gating):
        """Test que la règle la plus restrictive gagne"""
        # ETH + VOL_Q90_CROSS: base=attenuated, temporal(M1)=attenuated → final=attenuated
        allowed1, reason1 = temporal_gating.check_temporal_gating(
            "eth", "VOL_Q90_CROSS", Timeframe.M1
        )
        assert allowed1 == True
        assert "final:attenuated" in reason1
        
        # Test avec disabled override
        # REGIME_FLIP avec M1: base=enabled, temporal(M1)=disabled → final=disabled
        allowed2, reason2 = temporal_gating.check_temporal_gating(
            "btc", "REGIME_FLIP", Timeframe.M1
        )
        assert allowed2 == False
        assert "final:disabled" in reason2
    
    def test_temporal_gating_enabled_priority(self, temporal_gating):
        """Test priorité des timeframes principaux (H1, H4)"""
        # H1 et H4 sont des timeframes de référence pour VOL_Q90_CROSS
        for tf in [Timeframe.H1, Timeframe.H4]:
            allowed, reason = temporal_gating.check_temporal_gating(
                "btc", "VOL_Q90_CROSS", tf
            )
            assert allowed == True
            assert "final:enabled" in reason
    
    def test_temporal_gating_disabled_timeframes(self, temporal_gating):
        """Test timeframes désactivés pour certains types"""
        # REGIME_FLIP disabled sur M1 et M5 (trop de bruit)
        for tf in [Timeframe.M1, Timeframe.M5]:
            allowed, reason = temporal_gating.check_temporal_gating(
                "btc", "REGIME_FLIP", tf
            )
            assert allowed == False
            assert "final:disabled" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])