import pytest

from services.execution.governance import GovernanceEngine, Policy


@pytest.fixture
def engine():
    engine = GovernanceEngine(api_base_url="http://localhost")
    engine.current_state.governance_mode = "manual"
    engine.current_state.last_applied_policy = None
    engine._last_cap = 0.08
    return engine


def test_manual_policy_override_clamps_and_freezes_last_cap(engine):
    manual_policy = Policy.model_construct(
        mode="Normal",
        cap_daily=0.5,
        ramp_hours=12,
        min_trade=250.0,
        slippage_limit_bps=75,
        signals_ttl_seconds=1200,
        plan_cooldown_hours=6,
        no_trade_threshold_pct=0.4,
        execution_cost_bps=180,
        notes="test override",
    )
    engine.current_state.last_applied_policy = manual_policy

    derived = engine._derive_execution_policy()

    assert pytest.approx(0.20) == derived.cap_daily
    assert pytest.approx(0.10) == derived.no_trade_threshold_pct
    assert derived.execution_cost_bps == 100
    assert pytest.approx(0.20) == engine._last_cap
    assert derived.mode == "Normal"
