import uuid

import pytest
from fastapi.testclient import TestClient

from api.main import app
from services.execution.governance import governance_engine


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def manual_mode_guard():
    state = governance_engine.current_state
    original_mode = state.governance_mode
    original_policy = state.execution_policy.copy(deep=True)
    original_last_policy = state.last_applied_policy.copy(deep=True) if state.last_applied_policy else None
    original_last_update = state.last_manual_policy_update
    original_last_cap = governance_engine._last_cap

    state.governance_mode = "manual"
    state.last_applied_policy = None
    yield

    state.governance_mode = original_mode
    state.execution_policy = original_policy
    state.last_applied_policy = original_last_policy
    state.last_manual_policy_update = original_last_update
    governance_engine._last_cap = original_last_cap


def test_apply_policy_activates_manual_policy(client: TestClient):
    headers = {"Idempotency-Key": str(uuid.uuid4())}
    payload = {
        "mode": "Normal",
        "cap_daily": 0.5,
        "ramp_hours": 6,
        "reason": "manual rotate after risk ok",
        "source_alert_id": "alert-123",
        "min_trade": 150.0,
        "slippage_limit_bps": 60,
        "signals_ttl_seconds": 900,
        "plan_cooldown_hours": 4,
        "no_trade_threshold_pct": 0.25,
        "execution_cost_bps": 250,
        "notes": "integration test manual apply",
    }

    first_response = client.post(
        "/execution/governance/apply_policy",
        json=payload,
        headers=headers,
    )
    assert first_response.status_code == 200
    data = first_response.json()

    assert data["message"] == "Policy applied & activated: Normal"
    applied_policy = data["policy"]
    assert pytest.approx(0.20) == applied_policy["cap_daily"]
    assert pytest.approx(0.10) == applied_policy["no_trade_threshold_pct"]
    assert applied_policy["execution_cost_bps"] == 100
    assert applied_policy["mode"] == "Normal"

    second_response = client.post(
        "/execution/governance/apply_policy",
        json=payload,
        headers=headers,
    )
    assert second_response.status_code == 200
    assert second_response.json() == data

    state_response = client.get("/execution/governance/state")
    assert state_response.status_code == 200
    state_payload = state_response.json()
    active_policy = state_payload.get("active_policy") or {}

    assert pytest.approx(0.20) == active_policy.get("cap_daily")
    assert active_policy.get("mode") == "Normal"
    assert governance_engine.current_state.last_applied_policy.cap_daily == pytest.approx(0.20)
