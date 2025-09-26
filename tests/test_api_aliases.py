import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_strategies_list_alias():
    r = client.get("/api/strategies/list")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert isinstance(j["strategies"], list)
    assert all("id" in s and "name" in s for s in j["strategies"])

def test_strategy_detail_alias():
    r = client.get("/api/strategies/balanced")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["strategy"]["id"] == "balanced"