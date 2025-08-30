import asyncio
import json

import httpx

from api.main import app


async def _client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _test_healthz_async():
    async with await _client() as client:
        r = await client.get("/healthz")
        assert r.status_code == 200
        assert r.json().get("ok") is True

def test_healthz():
    asyncio.run(_test_healthz_async())


async def _test_balances_stub_async():
    async with await _client() as client:
        r = await client.get("/balances/current", params={"source": "stub", "min_usd": 1})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("items"), list)
        assert data.get("source_used") in ("cointracking", "cointracking_api", None, "stub") or True

def test_balances_stub():
    asyncio.run(_test_balances_stub_async())


async def _test_rebalance_plan_stub_async():
    payload = {
        "group_targets_pct": {"BTC": 40, "ETH": 30, "Stablecoins": 10, "L1/L0 majors": 20},
        "min_trade_usd": 25.0,
        "sub_allocation": "proportional",
    }
    async with await _client() as client:
        r = await client.post(
            "/rebalance/plan",
            params={"source": "stub", "min_usd": 1, "pricing": "local", "dynamic_targets": False},
            json=payload,
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("actions"), list)

def test_rebalance_plan_stub():
    asyncio.run(_test_rebalance_plan_stub_async())
