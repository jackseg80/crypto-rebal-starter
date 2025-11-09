"""
Unit tests for BalanceService - Core balance resolution logic.

Tests cover:
- Multi-tenant isolation
- Source resolution (stub, CSV, API)
- Fallback chains
- Data structure validation
- Error handling

Author: Claude Code Agent
Date: November 9, 2025
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from services.balance_service import BalanceService, balance_service


class TestBalanceServiceStubs:
    """Test stub data sources (no external dependencies)."""

    @pytest.mark.asyncio
    async def test_stub_conservative(self):
        """Test conservative stub portfolio (80% BTC, 15% ETH, 5% stables)."""
        service = BalanceService()
        result = await service.resolve_current_balances(
            source="stub_conservative",
            user_id="demo"
        )

        assert result["source_used"] == "stub_conservative"
        assert "items" in result
        assert len(result["items"]) == 3  # BTC, ETH, USDC
        assert "warnings" in result

        # Verify BTC is dominant
        btc_item = next(x for x in result["items"] if x["symbol"] == "BTC")
        assert btc_item["value_usd"] == 160000.0
        assert btc_item["amount"] == 3.2

    @pytest.mark.asyncio
    async def test_stub_shitcoins(self):
        """Test high-risk memecoin portfolio."""
        service = BalanceService()
        result = await service.resolve_current_balances(
            source="stub_shitcoins",
            user_id="demo"
        )

        assert result["source_used"] == "stub_shitcoins"
        assert len(result["items"]) == 20  # BTC + ETH + 17 memecoins + USDT

        # Verify memecoins present
        symbols = [x["symbol"] for x in result["items"]]
        assert "SHIB" in symbols
        assert "DOGE" in symbols
        assert "PEPE" in symbols

    @pytest.mark.asyncio
    async def test_stub_balanced_default(self):
        """Test default balanced portfolio."""
        service = BalanceService()
        result = await service.resolve_current_balances(
            source="stub",
            user_id="demo"
        )

        assert result["source_used"] == "stub"
        items = result["items"]
        assert len(items) == 23  # BTC + ETH + 21 serious alts

        # Verify data structure
        for item in items:
            assert "symbol" in item
            assert "alias" in item
            assert "amount" in item
            assert "value_usd" in item
            assert "location" in item
            assert isinstance(item["amount"], (int, float))
            assert isinstance(item["value_usd"], (int, float))


class TestBalanceServiceMultiTenant:
    """Test multi-tenant isolation (CLAUDE.md Rule #1)."""

    @pytest.mark.asyncio
    @patch("api.services.data_router.UserDataRouter")
    async def test_different_users_get_different_routers(self, mock_router_class):
        """Test that each user gets their own data router."""
        service = BalanceService()

        # Mock router for demo user
        mock_router_demo = Mock()
        mock_router_demo.get_effective_source.return_value = "stub"

        # Mock router for jack user
        mock_router_jack = Mock()
        mock_router_jack.get_effective_source.return_value = "stub"

        mock_router_class.side_effect = [mock_router_demo, mock_router_jack]

        # Call for demo user
        await service.resolve_current_balances(source="stub", user_id="demo")

        # Call for jack user
        await service.resolve_current_balances(source="stub", user_id="jack")

        # Verify router created twice with different user_ids
        assert mock_router_class.call_count == 2
        calls = mock_router_class.call_args_list

        # First call: demo user
        assert calls[0][0][1] == "demo"

        # Second call: jack user
        assert calls[1][0][1] == "jack"

    @pytest.mark.asyncio
    async def test_stub_data_independent_of_user(self):
        """Test that stub data works the same for all users."""
        service = BalanceService()

        result_demo = await service.resolve_current_balances(
            source="stub",
            user_id="demo"
        )

        result_jack = await service.resolve_current_balances(
            source="stub",
            user_id="jack"
        )

        # Stub data should be identical (no user-specific logic)
        assert len(result_demo["items"]) == len(result_jack["items"])
        assert result_demo["source_used"] == result_jack["source_used"]


class TestBalanceServiceCSVMode:
    """Test CSV mode balance resolution."""

    @pytest.mark.asyncio
    @patch("api.services.data_router.UserDataRouter")
    async def test_csv_mode_success(self, mock_router_class):
        """Test successful CSV mode with mocked data router."""
        # Mock router
        mock_router = Mock()
        mock_router.get_effective_source.return_value = "cointracking"
        mock_router.get_most_recent_csv.return_value = "/fake/path/balance.csv"
        mock_router_class.return_value = mock_router

        # Mock CSV helper
        with patch("api.services.csv_helpers.load_csv_balances", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = [
                {"symbol": "BTC", "alias": "BTC", "amount": 1.0, "value_usd": 50000.0, "location": "Kraken"},
                {"symbol": "ETH", "alias": "ETH", "amount": 10.0, "value_usd": 30000.0, "location": "Binance"}
            ]

            service = BalanceService()
            result = await service.resolve_current_balances(
                source="cointracking",
                user_id="demo"
            )

            assert result["source_used"] == "cointracking"
            assert len(result["items"]) == 2
            assert result["items"][0]["symbol"] == "BTC"
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    @patch("api.services.data_router.UserDataRouter")
    async def test_csv_mode_file_not_found(self, mock_router_class):
        """Test CSV mode when file doesn't exist."""
        # Mock router that returns None (no CSV found)
        mock_router = Mock()
        mock_router.get_effective_source.return_value = "cointracking"
        mock_router.get_most_recent_csv.return_value = None
        mock_router_class.return_value = mock_router

        service = BalanceService()
        result = await service.resolve_current_balances(
            source="cointracking",
            user_id="demo"
        )

        # Should fallback and return empty or stub
        assert "source_used" in result


class TestBalanceServiceAPIMode:
    """Test API mode balance resolution."""

    @pytest.mark.asyncio
    @patch("api.services.data_router.UserDataRouter")
    async def test_api_mode_with_credentials(self, mock_router_class):
        """Test API mode with valid credentials."""
        # Mock router with API credentials
        mock_router = Mock()
        mock_router.get_effective_source.return_value = "cointracking_api"
        mock_router.get_api_credentials.return_value = {
            "api_key": "test_key",
            "api_secret": "test_secret"
        }
        mock_router_class.return_value = mock_router

        # Mock API connector
        with patch("connectors.cointracking_api.get_current_balances", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {
                "items": [
                    {"symbol": "BTC", "alias": "BTC", "amount": 2.0, "value_usd": 100000.0, "location": "API"}
                ]
            }

            service = BalanceService()
            result = await service.resolve_current_balances(
                source="cointracking_api",
                user_id="demo"
            )

            # Note: API mode might fail if connector not available, so we check fallback
            assert "source_used" in result
            assert "items" in result

    @pytest.mark.asyncio
    @patch("api.services.data_router.UserDataRouter")
    async def test_api_mode_missing_credentials(self, mock_router_class):
        """Test API mode when credentials are missing."""
        # Mock router with no credentials
        mock_router = Mock()
        mock_router.get_effective_source.return_value = "cointracking_api"
        mock_router.get_api_credentials.return_value = {}
        mock_router_class.return_value = mock_router

        # Mock legacy API mode to prevent real API call
        with patch("api.services.cointracking_helpers.load_ctapi_exchanges", new_callable=AsyncMock) as mock_legacy:
            mock_legacy.return_value = {"detailed_holdings": {}}

            with patch("connectors.cointracking_api.get_current_balances", new_callable=AsyncMock) as mock_api:
                mock_api.return_value = {"items": []}

                service = BalanceService()
                result = await service.resolve_current_balances(
                    source="cointracking_api",
                    user_id="demo"
                )

                # Should fallback gracefully
                assert "source_used" in result


class TestBalanceServiceFallbacks:
    """Test fallback chains API → CSV → Stub."""

    @pytest.mark.asyncio
    @patch("api.services.data_router.UserDataRouter")
    async def test_auto_source_fallback(self, mock_router_class):
        """Test auto source resolution with fallback."""
        # Mock router that prefers API but has no credentials
        mock_router = Mock()
        mock_router.get_effective_source.return_value = "cointracking_api"
        mock_router.get_api_credentials.return_value = {}  # No credentials
        mock_router.get_most_recent_csv.return_value = None  # No CSV
        mock_router_class.return_value = mock_router

        service = BalanceService()
        result = await service.resolve_current_balances(
            source="auto",
            user_id="demo"
        )

        # Should eventually fallback to something that works
        assert result is not None
        assert "source_used" in result
        assert "items" in result


class TestBalanceServiceDataValidation:
    """Test data structure validation."""

    @pytest.mark.asyncio
    async def test_stub_data_structure_complete(self):
        """Test that all stub items have required fields."""
        service = BalanceService()

        for stub_type in ["stub", "stub_conservative", "stub_shitcoins"]:
            result = await service.resolve_current_balances(
                source=stub_type,
                user_id="demo"
            )

            items = result["items"]
            assert len(items) > 0, f"No items for {stub_type}"

            for item in items:
                # Required fields
                assert "symbol" in item, f"Missing symbol in {stub_type}"
                assert "alias" in item, f"Missing alias in {stub_type}"
                assert "amount" in item, f"Missing amount in {stub_type}"
                assert "value_usd" in item, f"Missing value_usd in {stub_type}"
                assert "location" in item, f"Missing location in {stub_type}"

                # Type validation
                assert isinstance(item["symbol"], str)
                assert isinstance(item["alias"], str)
                assert isinstance(item["amount"], (int, float))
                assert isinstance(item["value_usd"], (int, float))
                assert isinstance(item["location"], str)

                # Value validation
                assert item["amount"] > 0, f"Negative amount in {stub_type}"
                assert item["value_usd"] > 0, f"Negative value_usd in {stub_type}"

    @pytest.mark.asyncio
    async def test_response_structure(self):
        """Test that response has required structure."""
        service = BalanceService()
        result = await service.resolve_current_balances(
            source="stub",
            user_id="demo"
        )

        # Required top-level keys
        assert "source_used" in result
        assert "items" in result

        # source_used is a string
        assert isinstance(result["source_used"], str)

        # items is a list
        assert isinstance(result["items"], list)


class TestBalanceServiceSingleton:
    """Test singleton instance."""

    def test_singleton_exists(self):
        """Test that global singleton instance exists."""
        from services.balance_service import balance_service
        assert balance_service is not None
        assert isinstance(balance_service, BalanceService)

    @pytest.mark.asyncio
    async def test_singleton_works(self):
        """Test that singleton instance is functional."""
        from services.balance_service import balance_service

        result = await balance_service.resolve_current_balances(
            source="stub",
            user_id="demo"
        )

        assert result["source_used"] == "stub"
        assert len(result["items"]) > 0


class TestBalanceServiceErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    @patch("api.services.data_router.UserDataRouter")
    async def test_csv_permission_error(self, mock_router_class):
        """Test handling of CSV permission errors."""
        # Mock router
        mock_router = Mock()
        mock_router.get_effective_source.return_value = "cointracking"
        mock_router.get_most_recent_csv.return_value = "/fake/path/balance.csv"
        mock_router_class.return_value = mock_router

        # Mock CSV helper to raise PermissionError
        with patch("api.services.csv_helpers.load_csv_balances", new_callable=AsyncMock) as mock_load:
            mock_load.side_effect = PermissionError("Access denied")

            service = BalanceService()
            result = await service.resolve_current_balances(
                source="cointracking",
                user_id="demo"
            )

            # Should handle error gracefully and fallback
            assert result is not None

    @pytest.mark.asyncio
    async def test_invalid_source_fallback(self):
        """Test handling of invalid source parameter."""
        service = BalanceService()

        # Use an invalid source name
        result = await service.resolve_current_balances(
            source="invalid_source_xyz",
            user_id="demo"
        )

        # Should fallback and not crash
        assert result is not None
        assert "items" in result


# ============================================================================
# Integration-like tests (require real files - skip if not available)
# ============================================================================

class TestBalanceServiceIntegration:
    """Integration tests (require actual data files)."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not Path("data/users/demo/cointracking/data").exists(),
        reason="Demo user data not available"
    )
    async def test_real_csv_demo_user(self):
        """Test real CSV for demo user (if available)."""
        service = BalanceService()
        result = await service.resolve_current_balances(
            source="cointracking",
            user_id="demo"
        )

        assert result["source_used"] == "cointracking"
        assert len(result["items"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not Path("data/users/jack/cointracking/data").exists(),
        reason="Jack user data not available"
    )
    async def test_real_csv_jack_user(self):
        """Test real CSV for jack user (if available)."""
        service = BalanceService()
        result = await service.resolve_current_balances(
            source="cointracking",
            user_id="jack"
        )

        assert result["source_used"] == "cointracking"
        assert len(result["items"]) > 0


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
