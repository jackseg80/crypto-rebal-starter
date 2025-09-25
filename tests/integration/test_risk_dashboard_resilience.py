import datetime
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_history(start: datetime.datetime, days: int, missing_every: int = 0) -> List[List[float]]:
    history: List[List[float]] = []
    for i in range(days):
        if missing_every and i % missing_every == 0:
            continue
        ts = int((start + datetime.timedelta(days=i)).timestamp())
        price = 100 + i
        history.append([ts, price])
    return history


def test_risk_dashboard_returns_ok_quality(monkeypatch, client: TestClient):
    start = datetime.datetime(2023, 1, 1)
    histories = {
        "BTC": _make_history(start, 120, missing_every=6),
        "ETH": _make_history(start, 120, missing_every=8),
    }

    async def fake_resolve_current_balances(*_args, **_kwargs) -> Dict[str, Any]:
        return {"items": [
            {"symbol": "BTC", "value_usd": 10000, "amount": 0.5},
            {"symbol": "ETH", "value_usd": 2500, "amount": 5},
        ]}

    def fake_to_rows(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return items

    def fake_get_cached_history(symbol: str, days: int = None):  # noqa: ANN001
        return histories.get(symbol.upper(), [])

    monkeypatch.setattr("api.main.resolve_current_balances", fake_resolve_current_balances)
    monkeypatch.setattr("api.main._to_rows", fake_to_rows)
    monkeypatch.setattr("services.price_history.get_cached_history", fake_get_cached_history)

    response = client.get(
        "/api/risk/dashboard",
        params={"source": "test", "min_usd": 1.0, "price_history_days": 365},
        headers={"X-User": "demo"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["quality"] == "ok"
    assert set(data["data_quality"]["filtered_symbols"]) == {"BTC", "ETH"}
    assert data["risk_metrics"]["data_points"] >= 30


def test_risk_dashboard_degraded_quality(monkeypatch, client: TestClient):
    start = datetime.datetime(2024, 1, 1)
    short_histories = {
        "BTC": _make_history(start, 20),
        "ETH": _make_history(start, 18),
    }

    async def fake_resolve_current_balances(*_args, **_kwargs) -> Dict[str, Any]:
        return {"items": [
            {"symbol": "BTC", "value_usd": 4000, "amount": 0.2},
            {"symbol": "ETH", "value_usd": 1500, "amount": 3},
        ]}

    def fake_to_rows(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return items

    def fake_get_cached_history(symbol: str, days: int = None):  # noqa: ANN001
        return short_histories.get(symbol.upper(), [])

    async def fake_risk_metrics(*_args, **_kwargs):
        now = datetime.datetime.utcnow()
        return SimpleNamespace(
            var_95_1d=0.05,
            var_99_1d=0.08,
            cvar_95_1d=0.06,
            cvar_99_1d=0.09,
            volatility_annualized=0.2,
            sharpe_ratio=0.5,
            sortino_ratio=0.6,
            calmar_ratio=0.7,
            max_drawdown=-0.1,
            max_drawdown_duration_days=5,
            current_drawdown=-0.05,
            ulcer_index=0.01,
            skewness=0.0,
            kurtosis=0.0,
            overall_risk_level=SimpleNamespace(value="medium"),
            risk_score=0.0,
            calculation_date=now,
            data_points=10,
            confidence_level=0.95,
        )

    async def fake_correlation_matrix(*_args, **_kwargs):
        return SimpleNamespace(
            diversification_ratio=0.5,
            effective_assets=1.5,
            correlations={}
        )

    monkeypatch.setattr("api.main.resolve_current_balances", fake_resolve_current_balances)
    monkeypatch.setattr("api.main._to_rows", fake_to_rows)
    monkeypatch.setattr("services.price_history.get_cached_history", fake_get_cached_history)
    monkeypatch.setattr("services.risk_management.risk_manager.calculate_portfolio_risk_metrics", fake_risk_metrics)
    monkeypatch.setattr("services.risk_management.risk_manager.calculate_correlation_matrix", fake_correlation_matrix)

    response = client.get(
        "/api/risk/dashboard",
        params={"source": "test", "min_usd": 1.0, "price_history_days": 90},
        headers={"X-User": "demo"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["quality"] == "low"
    assert "warning" in data
    assert data["data_quality"].get("reason") in {"no_symbol_meets_threshold", "not_enough_points", "no_holdings_after_filter"}
