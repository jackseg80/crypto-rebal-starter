"""
Tests d'intégration pour l'hystérésis anti-yo-yo du GovernanceEngine

Phase 4: Vérifier que les seuils d'activation/désactivation distincts
empêchent les oscillations dans les caps VaR et stale.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from services.execution.governance import GovernanceEngine


class MockSignals:
    """Mock pour les signaux ML avec timestamps configurables"""
    def __init__(self, blended_score: float, as_of: datetime = None):
        self.blended_score = blended_score
        self.as_of = as_of or datetime.now()
        self.volatility = {"BTC": 0.08, "ETH": 0.12, "SOL": 0.15}
        self.risk_score = 70  # Default safe


@pytest.fixture
def governance_engine():
    """Fixture avec GovernanceEngine configuré pour tests hystérésis"""
    engine = GovernanceEngine()
    # Configuration test avec seuils serrés pour validation rapide
    engine._hysteresis_config.update({
        "var_activate_threshold": 75,
        "var_deactivate_threshold": 65,  # Gap 10pts anti-yo-yo
        "stale_activate_seconds": 1800,   # 30min
        "stale_deactivate_seconds": 900,  # 15min (gap 15min)
        "history_window": 3,              # Fenêtre réduite pour tests
        "trend_stability_required": 2     # 2 points pour confirmation
    })
    return engine


class TestVaRHysteresis:
    """Test l'hystérésis VaR avec seuils d'activation/désactivation distincts"""

    def test_var_activation_requires_sustained_high_score(self, governance_engine):
        """VaR hystérésis s'active seulement si score élevé soutenu"""
        engine = governance_engine

        # Scores oscillants autour du seuil -> pas d'activation
        engine._update_hysteresis_state(MockSignals(74), 0)  # Sous seuil
        engine._update_hysteresis_state(MockSignals(76), 0)  # Au-dessus 1x
        engine._update_hysteresis_state(MockSignals(73), 0)  # Retombe

        var_state, _ = engine._update_hysteresis_state(MockSignals(74), 0)
        assert var_state == "normal", "Oscillations ne doivent pas activer"

        # Scores soutenus au-dessus du seuil -> activation
        engine._update_hysteresis_state(MockSignals(76), 0)  # Au-dessus
        var_state, _ = engine._update_hysteresis_state(MockSignals(78), 0)  # Soutenu
        assert var_state == "prudent", "Score élevé soutenu doit activer"

    def test_var_deactivation_gap_prevents_yoyo(self, governance_engine):
        """Gap entre activation (75) et désactivation (65) empêche yo-yo"""
        engine = governance_engine

        # Activer hystérésis VaR
        engine._update_hysteresis_state(MockSignals(76), 0)
        engine._update_hysteresis_state(MockSignals(78), 0)
        var_state, _ = engine._update_hysteresis_state(MockSignals(77), 0)
        assert var_state == "prudent"

        # Score redescend mais reste au-dessus de désactivation (65)
        engine._update_hysteresis_state(MockSignals(70), 0)  # Baisse
        engine._update_hysteresis_state(MockSignals(68), 0)  # Encore baisse
        var_state, _ = engine._update_hysteresis_state(MockSignals(67), 0)  # Au-dessus 65
        assert var_state == "prudent", "Doit rester prudent au-dessus seuil déactivation"

        # Seulement sous 65 de façon soutenue -> désactivation
        engine._update_hysteresis_state(MockSignals(63), 0)
        var_state, _ = engine._update_hysteresis_state(MockSignals(62), 0)  # Soutenu sous 65
        assert var_state == "normal", "Sous seuil désactivation soutenu doit désactiver"


class TestStaleHysteresis:
    """Test l'hystérésis staleness avec seuils temporels distincts"""

    def test_stale_activation_requires_sustained_staleness(self, governance_engine):
        """Stale hystérésis s'active seulement si staleness soutenue"""
        engine = governance_engine
        base_time = datetime.now()

        # Signaux oscillants autour du seuil stale (1800s)
        old_signals = MockSignals(70, base_time - timedelta(seconds=1700))  # Pas encore stale
        engine._update_hysteresis_state(old_signals, 1700)

        stale_signals = MockSignals(70, base_time - timedelta(seconds=1900))  # Stale
        engine._update_hysteresis_state(stale_signals, 1900)

        fresh_signals = MockSignals(70, base_time - timedelta(seconds=1600))  # Fresh again
        _, stale_state = engine._update_hysteresis_state(fresh_signals, 1600)
        assert stale_state == "normal", "Oscillations staleness ne doivent pas activer"

        # Staleness soutenue -> activation
        stale1 = MockSignals(70, base_time - timedelta(seconds=1900))
        engine._update_hysteresis_state(stale1, 1900)
        stale2 = MockSignals(70, base_time - timedelta(seconds=2000))
        _, stale_state = engine._update_hysteresis_state(stale2, 2000)
        assert stale_state == "stale", "Staleness soutenue doit activer"

    def test_stale_deactivation_gap_prevents_yoyo(self, governance_engine):
        """Gap entre activation (1800s) et désactivation (900s) empêche yo-yo"""
        engine = governance_engine
        base_time = datetime.now()

        # Activer staleness
        stale1 = MockSignals(70, base_time - timedelta(seconds=1900))
        engine._update_hysteresis_state(stale1, 1900)
        stale2 = MockSignals(70, base_time - timedelta(seconds=2000))
        _, stale_state = engine._update_hysteresis_state(stale2, 2000)
        assert stale_state == "stale"

        # Signaux redeviennent plus frais mais au-dessus seuil désactivation (900s)
        semi_fresh = MockSignals(70, base_time - timedelta(seconds=1200))  # 1200s > 900s
        engine._update_hysteresis_state(semi_fresh, 1200)
        semi_fresh2 = MockSignals(70, base_time - timedelta(seconds=1100))
        _, stale_state = engine._update_hysteresis_state(semi_fresh2, 1100)
        assert stale_state == "stale", "Doit rester stale au-dessus seuil désactivation"

        # Signaux vraiment frais (< 900s) de façon soutenue
        fresh1 = MockSignals(70, base_time - timedelta(seconds=800))
        engine._update_hysteresis_state(fresh1, 800)
        fresh2 = MockSignals(70, base_time - timedelta(seconds=700))
        _, stale_state = engine._update_hysteresis_state(fresh2, 700)
        assert stale_state == "normal", "Signaux frais soutenus doivent désactiver"


class TestHysteresisIntegration:
    """Test intégration hystérésis dans dérivation des policies"""

    def test_hysteresis_affects_policy_caps_and_mode(self, governance_engine):
        """Hystérésis influence caps et mode dans derive_execution_policy"""
        engine = governance_engine
        base_time = datetime.now()

        # Signaux normaux -> policy normale
        normal_signals = MockSignals(70, base_time)
        policy1 = engine.derive_execution_policy(normal_signals)
        assert "VAR_HYSTERESIS" not in str(policy1), "Pas d'hystérésis sur signaux normaux"

        # Activer VaR hysteresis
        high_signals = MockSignals(76, base_time)
        engine._update_hysteresis_state(high_signals, 100)
        high_signals2 = MockSignals(78, base_time)

        policy2 = engine.derive_execution_policy(high_signals2)
        # Le mode Aggressive devrait être downgraded en Normal
        assert policy2.mode in ["Normal", "Slow"], "VaR hystérésis doit réduire agressivité"
        assert policy2.cap_daily <= 0.08, "VaR hystérésis doit plafonner cap"

    def test_stale_hysteresis_reduces_caps(self, governance_engine):
        """Hystérésis stale réduit caps de façon stable"""
        engine = governance_engine
        base_time = datetime.now()

        # Activer stale hysteresis
        old_signals1 = MockSignals(70, base_time - timedelta(seconds=1900))
        engine._update_hysteresis_state(old_signals1, 1900)
        old_signals2 = MockSignals(70, base_time - timedelta(seconds=2000))

        policy = engine.derive_execution_policy(old_signals2)
        assert policy.cap_daily <= 0.08, "Stale hystérésis doit réduire cap à 8%"
        assert "STALE_HYSTERESIS" in str(policy), "Policy doit indiquer stale hystérésis"

    def test_hysteresis_logging(self, governance_engine, caplog):
        """Hystérésis log les transitions d'état"""
        engine = governance_engine

        # Activation VaR
        high1 = MockSignals(76, datetime.now())
        engine._update_hysteresis_state(high1, 100)
        high2 = MockSignals(78, datetime.now())
        engine._update_hysteresis_state(high2, 100)

        # Vérifier logs d'activation
        assert "VaR hysteresis activated: prudent mode" in caplog.text

        caplog.clear()

        # Désactivation
        low1 = MockSignals(63, datetime.now())
        engine._update_hysteresis_state(low1, 100)
        low2 = MockSignals(62, datetime.now())
        engine._update_hysteresis_state(low2, 100)

        # Vérifier logs de désactivation
        assert "VaR hysteresis deactivated: normal mode" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])