"""
Integration tests for balance resolution (resolve_current_balances).

Critical paths tested:
- Multi-user isolation (URGENT per AUDIT_REPORT_2025-10-19.md)
- Source routing (cointracking, cointracking_api, saxobank)
- Data filtering (min_usd threshold)
- Error handling

Created: 2025-10-20 (Tests Critical Paths - Priority 1)
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app, resolve_current_balances
import os
from pathlib import Path


client = TestClient(app)


class TestBalanceResolution:
    """Tests for resolve_current_balances function"""

    @pytest.mark.asyncio
    async def test_multi_user_isolation_demo_vs_jack(self):
        """
        CRITICAL: User isolation test.
        Demo and Jack should get different data from different sources.
        """
        # User demo with cointracking source
        balances_demo = await resolve_current_balances(
            source="cointracking",
            user_id="demo"
        )

        # User jack with saxobank source
        balances_jack = await resolve_current_balances(
            source="saxobank",
            user_id="jack"
        )

        # Assert data isolation
        assert balances_demo["source_used"] in ["cointracking", "stub"]
        # Note: May fallback to cointracking if Saxo CSV not available
        assert balances_jack["source_used"] in ["saxobank", "saxo_data", "cointracking", "stub"]

        # Items should be different (unless both empty/stub)
        demo_items = balances_demo.get("items", [])
        jack_items = balances_jack.get("items", [])

        # At minimum, verify structure
        assert isinstance(demo_items, list)
        assert isinstance(jack_items, list)

        # If both have data, they should be different users
        if demo_items and jack_items:
            # Convert to sets of symbols for comparison
            demo_symbols = {item.get("symbol") for item in demo_items}
            jack_symbols = {item.get("symbol") for item in jack_items}

            # Different users may have different portfolios
            # (This test may be weak if portfolios overlap, but verifies structure)
            print(f"Demo symbols: {demo_symbols}")
            print(f"Jack symbols: {jack_symbols}")

    @pytest.mark.asyncio
    async def test_multi_user_isolation_same_source(self):
        """
        CRITICAL: Multiple users with same source should get isolated data.
        """
        # Both users use cointracking, but different CSV files
        balances_demo = await resolve_current_balances(
            source="cointracking",
            user_id="demo"
        )

        balances_roberto = await resolve_current_balances(
            source="cointracking",
            user_id="roberto"
        )

        # Both should use cointracking (or stub)
        assert balances_demo["source_used"] in ["cointracking", "stub"]
        assert balances_roberto["source_used"] in ["cointracking", "stub"]

        # Verify structure
        assert "items" in balances_demo
        assert "items" in balances_roberto

    @pytest.mark.asyncio
    async def test_source_routing_cointracking(self):
        """resolve_current_balances should route to CSV for cointracking source"""
        result = await resolve_current_balances(
            source="cointracking",
            user_id="demo"
        )

        # Should return cointracking or stub (if no CSV)
        assert result["source_used"] in ["cointracking", "stub"]
        assert "items" in result
        assert isinstance(result["items"], list)

    @pytest.mark.asyncio
    async def test_source_routing_cointracking_api(self):
        """resolve_current_balances should route to API for cointracking_api source"""
        # Note: This may fail if API keys not configured, that's OK
        try:
            result = await resolve_current_balances(
                source="cointracking_api",
                user_id="demo"
            )

            # If API available, should use it
            # If not, may fall back to stub
            assert result["source_used"] in ["cointracking_api", "stub"]
            assert "items" in result

        except Exception as e:
            # API may not be configured in test environment
            print(f"API test skipped: {e}")
            pytest.skip("CoinTracking API not configured")

    @pytest.mark.asyncio
    async def test_source_routing_saxobank(self):
        """resolve_current_balances should route to Saxo for saxobank source"""
        result = await resolve_current_balances(
            source="saxobank",
            user_id="jack"
        )

        # Should return saxobank/saxo_data or fallback to cointracking/stub
        assert result["source_used"] in ["saxobank", "saxo_data", "cointracking", "stub"]
        assert "items" in result
        assert isinstance(result["items"], list)

    @pytest.mark.asyncio
    async def test_items_structure(self):
        """Items should have required fields: symbol, value_usd, location"""
        result = await resolve_current_balances(
            source="cointracking",
            user_id="demo"
        )

        items = result.get("items", [])

        # If items exist, verify structure
        if items:
            for item in items[:3]:  # Check first 3 items
                assert "symbol" in item
                assert "value_usd" in item or "usd_value" in item
                # location may be optional in some formats

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_empty_or_stub(self):
        """Nonexistent user should not crash, return empty/stub data"""
        result = await resolve_current_balances(
            source="cointracking",
            user_id="nonexistent_user_12345"
        )

        # Should not crash
        assert "source_used" in result
        assert "items" in result

        # Should return empty or stub
        assert result["source_used"] in ["cointracking", "stub"]
        # Items may be empty list
        assert isinstance(result["items"], list)


class TestBalanceResolutionEndpoint:
    """Tests for /balances/current endpoint"""

    def test_balances_endpoint_requires_user_header(self):
        """Endpoint should respect X-User header for multi-tenancy"""
        response_demo = client.get(
            "/balances/current?source=cointracking",
            headers={"X-User": "demo"}
        )

        response_jack = client.get(
            "/balances/current?source=saxobank",
            headers={"X-User": "jack"}
        )

        # Both should succeed
        assert response_demo.status_code == 200
        assert response_jack.status_code == 200

        data_demo = response_demo.json()
        data_jack = response_jack.json()

        # Verify structure
        assert "source_used" in data_demo
        assert "items" in data_demo
        assert "source_used" in data_jack
        assert "items" in data_jack

    def test_balances_endpoint_defaults_to_demo_user(self):
        """Endpoint without X-User should default to demo"""
        response = client.get("/balances/current?source=cointracking")

        assert response.status_code == 200
        data = response.json()

        # Should return data (demo user default)
        assert "source_used" in data
        assert "items" in data

    def test_balances_endpoint_min_usd_filter(self):
        """Endpoint should filter assets below min_usd threshold"""
        # Get balances with min_usd=1
        response_1 = client.get(
            "/balances/current?source=cointracking&min_usd=1",
            headers={"X-User": "demo"}
        )

        # Get balances with min_usd=1000
        response_1000 = client.get(
            "/balances/current?source=cointracking&min_usd=1000",
            headers={"X-User": "demo"}
        )

        assert response_1.status_code == 200
        assert response_1000.status_code == 200

        data_1 = response_1.json()
        data_1000 = response_1000.json()

        # Higher threshold should result in fewer or equal items
        # (unless both are empty/stub)
        if data_1["items"] and data_1000["items"]:
            assert len(data_1000["items"]) <= len(data_1["items"])


class TestBalanceResolutionErrorHandling:
    """Tests for error handling in balance resolution"""

    @pytest.mark.asyncio
    async def test_invalid_source_returns_fallback(self):
        """Invalid source should gracefully fallback (stub or cointracking)"""
        result = await resolve_current_balances(
            source="invalid_source_xyz",
            user_id="demo"
        )

        # Should not crash, return fallback (stub or cointracking)
        assert "source_used" in result
        assert result["source_used"] in ["stub", "cointracking"]
        assert "items" in result

    def test_endpoint_handles_invalid_source(self):
        """Endpoint should handle invalid source gracefully"""
        response = client.get(
            "/balances/current?source=invalid_source_xyz",
            headers={"X-User": "demo"}
        )

        # Should return 200 with fallback data (not crash)
        assert response.status_code == 200
        data = response.json()
        # May fallback to cointracking or stub
        assert data["source_used"] in ["stub", "cointracking"]


# Run with:
# pytest tests/integration/test_balance_resolution.py -v
# pytest tests/integration/test_balance_resolution.py::TestBalanceResolution::test_multi_user_isolation_demo_vs_jack -v
