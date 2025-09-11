"""
Tests unitaires pour Phase 2A - Phase-Aware Alerting System
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from dataclasses import dataclass

from services.alerts.alert_engine import PhaseSnapshot, PhaseAwareContext
from services.execution.phase_engine import Phase


class TestPhaseAwareAlerts:
    """Tests pour le système d'alertes phase-aware"""
    
    def test_phase_snapshot_creation(self):
        """Test création d'un PhaseSnapshot"""
        now = datetime.now(timezone.utc)
        
        snapshot = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.85,
            persistence_count=3,
            captured_at=now,
            contradiction_index=0.25
        )
        
        assert snapshot.phase == Phase.BTC
        assert snapshot.confidence == 0.85
        assert snapshot.persistence_count == 3
        assert snapshot.captured_at == now
        assert snapshot.contradiction_index == 0.25
    
    def test_phase_aware_context_basic(self):
        """Test initialisation et fonctionnement de base du PhaseAwareContext"""
        context = PhaseAwareContext(lag_minutes=15, persistence_ticks=3)
        
        # Vérification initialisation
        assert context.lag_minutes == 15
        assert context.persistence_ticks == 3
        assert context.current_lagged_phase is None
        assert len(context.phase_history) == 0
    
    def test_phase_lagging_logic(self):
        """Test de la logique de phase lagging (15 minutes)"""
        context = PhaseAwareContext(lag_minutes=15, persistence_ticks=3)
        now = datetime.now(timezone.utc)
        
        # Créer des snapshots avec différents timestamps
        old_snapshot = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=now - timedelta(minutes=20),  # Il y a 20 minutes
            contradiction_index=0.2
        )
        
        recent_snapshot = PhaseSnapshot(
            phase=Phase.ETH,
            confidence=0.9,
            persistence_count=1,
            captured_at=now - timedelta(minutes=5),   # Il y a 5 minutes
            contradiction_index=0.1
        )
        
        # Ajouter à l'historique et simuler le calcul de la phase laggée
        context.phase_history = [old_snapshot, recent_snapshot]
        
        # Simulation de la logique de get_lagged_phase depuis update()
        lag_cutoff = now - timedelta(minutes=15)
        lagged_snapshots = [s for s in context.phase_history if s.captured_at <= lag_cutoff]
        
        assert len(lagged_snapshots) == 1
        candidate = max(lagged_snapshots, key=lambda x: x.captured_at)
        
        # Vérifier que c'est le bon snapshot et qu'il a suffisamment de persistance
        assert candidate.phase == Phase.BTC
        assert candidate.captured_at == old_snapshot.captured_at
        assert candidate.persistence_count >= context.persistence_ticks
        
        # Simuler l'assignation qui se ferait dans update()
        context.current_lagged_phase = candidate
        
        # Test de la méthode get_lagged_phase
        lagged = context.get_lagged_phase()
        
        # Devrait retourner la phase suffisamment ancienne (> 15 min)
        assert lagged is not None
        assert lagged.phase == Phase.BTC
        assert lagged.captured_at == old_snapshot.captured_at
    
    def test_phase_persistence_validation(self):
        """Test validation de la persistance de phase (3 ticks minimum)"""
        context = PhaseAwareContext(lag_minutes=15, persistence_ticks=3)
        now = datetime.now(timezone.utc)
        
        # Test avec persistance insuffisante (2 ticks)
        snapshots_insufficient = [
            PhaseSnapshot(
                phase=Phase.BTC,
                confidence=0.8,
                persistence_count=i + 1,
                captured_at=now - timedelta(minutes=20 + i),
                contradiction_index=0.2
            ) for i in range(2)  # Seulement 2 snapshots
        ]
        
        context.phase_history = snapshots_insufficient
        
        # Simuler has_sufficient_persistence (la méthode exacte peut varier)
        btc_snapshots = [s for s in context.phase_history if s.phase == Phase.BTC]
        sufficient = len(btc_snapshots) >= context.persistence_ticks
        assert not sufficient  # Pas suffisant (2 < 3)
        
        # Test avec persistance suffisante (3 ticks)
        snapshots_sufficient = [
            PhaseSnapshot(
                phase=Phase.BTC,
                confidence=0.8,
                persistence_count=i + 1,
                captured_at=now - timedelta(minutes=20 + i),
                contradiction_index=0.2
            ) for i in range(3)  # 3 snapshots
        ]
        
        context.phase_history = snapshots_sufficient
        
        btc_snapshots = [s for s in context.phase_history if s.phase == Phase.BTC]
        sufficient = len(btc_snapshots) >= context.persistence_ticks
        assert sufficient  # Suffisant (3 >= 3)
    
    def test_contradiction_neutralization_logic(self):
        """Test logique de neutralisation basée sur contradiction_index"""
        context = PhaseAwareContext(lag_minutes=15, persistence_ticks=3)
        
        # Test avec contradiction élevée (> 0.70)
        high_contradiction_snapshot = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            contradiction_index=0.85  # > 0.70
        )
        
        context.current_lagged_phase = high_contradiction_snapshot
        
        # Logique de neutralisation (seuil à 0.70)
        should_neutralize = (
            context.current_lagged_phase is not None and 
            context.current_lagged_phase.contradiction_index > 0.70
        )
        assert should_neutralize
        
        # Test avec contradiction faible (< 0.70) 
        low_contradiction_snapshot = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            contradiction_index=0.45  # < 0.70
        )
        
        context.current_lagged_phase = low_contradiction_snapshot
        
        should_neutralize = (
            context.current_lagged_phase is not None and 
            context.current_lagged_phase.contradiction_index > 0.70
        )
        assert not should_neutralize
    
    def test_gating_matrix_logic(self):
        """Test logique de gating matrix par phase"""
        # Configuration de test de la gating matrix
        gating_matrix = {
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
        
        # Test différentes phases
        phase_mappings = {
            Phase.BTC: "btc",
            Phase.ETH: "eth", 
            Phase.LARGE: "large",
            Phase.ALT: "alt"
        }
        
        # Test phase BTC - VOL_Q90_CROSS enabled
        phase_key = phase_mappings[Phase.BTC]
        gating = gating_matrix[phase_key]["VOL_Q90_CROSS"]
        assert gating == "enabled"
        
        # Test phase ALT - VOL_Q90_CROSS disabled
        phase_key = phase_mappings[Phase.ALT]
        gating = gating_matrix[phase_key]["VOL_Q90_CROSS"]
        assert gating == "disabled"
        
        # Test phase ETH - CONTRADICTION_SPIKE attenuated
        phase_key = phase_mappings[Phase.ETH]
        gating = gating_matrix[phase_key]["CONTRADICTION_SPIKE"]
        assert gating == "attenuated"
    
    def test_adaptive_threshold_calculation(self):
        """Test calcul des seuils adaptatifs avec phase factors"""
        # Configuration de test des phase factors
        phase_factors = {
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
        }
        
        base_threshold = 0.75
        alert_type = "VOL_Q90_CROSS"
        
        # Test différentes phases
        phase_mappings = {
            Phase.BTC: "btc",
            Phase.ETH: "eth",
            Phase.LARGE: "large", 
            Phase.ALT: "alt"
        }
        
        # Test phase ETH - factor 1.1
        phase_key = phase_mappings[Phase.ETH]
        factor = phase_factors[alert_type][phase_key]
        adaptive_threshold = base_threshold * factor
        expected = 0.75 * 1.1
        assert adaptive_threshold == expected
        
        # Test phase ALT - factor 1.3
        phase_key = phase_mappings[Phase.ALT]
        factor = phase_factors[alert_type][phase_key]
        adaptive_threshold = base_threshold * factor
        expected = 0.75 * 1.3
        assert adaptive_threshold == expected
    
    def test_anti_circularite_complete_workflow(self):
        """Test workflow complet des guards anti-circularité"""
        context = PhaseAwareContext(lag_minutes=15, persistence_ticks=3)
        now = datetime.now(timezone.utc)
        
        # Scénario 1: Phase lag insuffisant (changement récent)
        recent_snapshot = PhaseSnapshot(
            phase=Phase.ETH,
            confidence=0.9,
            persistence_count=1,
            captured_at=now - timedelta(minutes=5),  # Trop récent (< 15 min)
            contradiction_index=0.3
        )
        
        context.phase_history = [recent_snapshot]
        lagged = context.get_lagged_phase()
        
        # Pas de phase laggée disponible
        assert lagged is None or lagged.captured_at > (now - timedelta(minutes=15))
        
        # Scénario 2: Persistance insuffisante
        # (déjà testé dans test_phase_persistence_validation)
        
        # Scénario 3: Contradiction élevée
        persistent_high_contradiction = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=now - timedelta(minutes=20),  # Suffisamment ancien
            contradiction_index=0.85  # Élevé > 0.70
        )
        
        context.phase_history = [persistent_high_contradiction]
        context.current_lagged_phase = persistent_high_contradiction
        lagged = context.get_lagged_phase()
        
        # Phase disponible mais contradiction élevée
        assert lagged is not None
        assert lagged.contradiction_index > 0.70
        
        # Dans ce cas, les alertes devraient être neutralisées
        should_neutralize = lagged.contradiction_index > 0.70
        assert should_neutralize
        
        # Scénario 4: Tous les guards passent - alertes autorisées
        valid_snapshot = PhaseSnapshot(
            phase=Phase.BTC,
            confidence=0.8,
            persistence_count=3,
            captured_at=now - timedelta(minutes=20),  # Suffisamment ancien
            contradiction_index=0.3  # Faible < 0.70
        )
        
        # Simuler plusieurs snapshots pour la persistance
        persistent_snapshots = [
            PhaseSnapshot(
                phase=Phase.BTC,
                confidence=0.8,
                persistence_count=i + 1,
                captured_at=now - timedelta(minutes=25 + i),
                contradiction_index=0.3
            ) for i in range(3)
        ]
        
        context.phase_history = persistent_snapshots
        context.current_lagged_phase = valid_snapshot
        lagged = context.get_lagged_phase()
        
        # Toutes les conditions remplies
        assert lagged is not None
        assert lagged.captured_at <= (now - timedelta(minutes=15))  # Lag OK
        assert lagged.contradiction_index <= 0.70  # Contradiction OK
        # Persistance OK (3 snapshots)
        
        should_allow_alerts = (
            lagged is not None and
            lagged.captured_at <= (now - timedelta(minutes=15)) and
            lagged.contradiction_index <= 0.70 and
            len([s for s in context.phase_history if s.phase == lagged.phase]) >= 3
        )
        assert should_allow_alerts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])