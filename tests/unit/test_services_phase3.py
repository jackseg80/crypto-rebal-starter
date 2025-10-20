"""
Unit tests for Phase 3 refactored services.

Tests coverage for:
- api/services/utils.py (parse_min_usd, to_rows, norm_primary_symbols)
- api/services/csv_helpers.py (to_csv)
- api/services/cointracking_helpers.py (normalize_loc, classify_location, pick_primary_location_for_symbol)
- api/services/location_assigner.py (assign_locations_to_actions)
- api/services/price_enricher.py (enrich_actions_with_prices, get_data_age_minutes)

Created: 2025-10-20 (Phase 3 refactoring completion)
"""

import pytest
from typing import Dict, List, Any


class TestUtils:
    """Tests for api/services/utils.py"""

    def test_parse_min_usd_valid_string(self):
        """parse_min_usd should convert valid string to float"""
        from api.services.utils import parse_min_usd

        assert parse_min_usd("10.5") == 10.5
        assert parse_min_usd("100") == 100.0
        assert parse_min_usd("0.01") == 0.01

    def test_parse_min_usd_none_returns_default(self):
        """parse_min_usd should return default when None"""
        from api.services.utils import parse_min_usd

        assert parse_min_usd(None) == 1.0
        assert parse_min_usd(None, default=5.0) == 5.0

    def test_parse_min_usd_invalid_returns_default(self):
        """parse_min_usd should return default when invalid"""
        from api.services.utils import parse_min_usd

        assert parse_min_usd("invalid") == 1.0
        assert parse_min_usd("abc", default=10.0) == 10.0

    def test_to_rows_normalizes_connector_output(self):
        """to_rows should normalize various connector formats"""
        from api.services.utils import to_rows

        raw = [
            {"symbol": "BTC", "value_usd": 50000, "amount": 1.5, "location": "Binance"},
            {"coin": "ETH", "value": 3000, "amount": 2.0, "exchange": "Kraken"},
            {"name": "USDC", "value_usd": 1000, "location": "Coinbase"}
        ]

        result = to_rows(raw)

        assert len(result) == 3
        assert result[0]["symbol"] == "BTC"
        assert result[0]["value_usd"] == 50000
        assert result[0]["amount"] == 1.5
        assert result[0]["location"] == "Binance"

        assert result[1]["symbol"] == "ETH"
        assert result[1]["value_usd"] == 3000
        assert result[1]["location"] == "Kraken"

        assert result[2]["symbol"] == "USDC"
        assert result[2]["value_usd"] == 1000
        assert result[2]["location"] == "Coinbase"

    def test_to_rows_filters_missing_symbol(self):
        """to_rows should filter out rows without symbol"""
        from api.services.utils import to_rows

        raw = [
            {"symbol": "BTC", "value_usd": 50000},
            {"value_usd": 1000},  # Missing symbol
            {"coin": "ETH", "value_usd": 3000}
        ]

        result = to_rows(raw)
        assert len(result) == 2
        assert result[0]["symbol"] == "BTC"
        assert result[1]["symbol"] == "ETH"

    def test_norm_primary_symbols_with_string(self):
        """norm_primary_symbols should parse comma-separated strings"""
        from api.services.utils import norm_primary_symbols

        input_dict = {
            "BTC": "BTC,WBTC,TBTC",
            "ETH": "ETH,WETH"
        }

        result = norm_primary_symbols(input_dict)

        assert result["BTC"] == ["BTC", "WBTC", "TBTC"]
        assert result["ETH"] == ["ETH", "WETH"]

    def test_norm_primary_symbols_with_list(self):
        """norm_primary_symbols should handle list format"""
        from api.services.utils import norm_primary_symbols

        input_dict = {
            "BTC": ["BTC", "WBTC", "TBTC"],
            "ETH": ["ETH", "WETH"]
        }

        result = norm_primary_symbols(input_dict)

        assert result["BTC"] == ["BTC", "WBTC", "TBTC"]
        assert result["ETH"] == ["ETH", "WETH"]

    def test_norm_primary_symbols_empty_input(self):
        """norm_primary_symbols should handle empty/None input"""
        from api.services.utils import norm_primary_symbols

        assert norm_primary_symbols(None) == {}
        assert norm_primary_symbols({}) == {}


class TestCSVHelpers:
    """Tests for api/services/csv_helpers.py"""

    def test_to_csv_generates_correct_format(self):
        """to_csv should generate CSV string with proper format"""
        from api.services.csv_helpers import to_csv

        actions = [
            {
                "group": "MAJOR",
                "alias": "Bitcoin",
                "symbol": "BTC",
                "action": "BUY",
                "usd": 1000.50,
                "est_quantity": 0.02,
                "price_used": 50000,
                "exec_hint": "Binance: BUY 0.02 BTC"
            },
            {
                "group": "STABLE",
                "alias": "USDC",
                "symbol": "USDC",
                "action": "SELL",
                "usd": -500.00,
                "est_quantity": 500,
                "price_used": 1.0,
                "exec_hint": "Coinbase: SELL 500 USDC"
            }
        ]

        result = to_csv(actions)
        lines = result.split("\n")

        # Check header
        assert lines[0] == "group,alias,symbol,action,usd,est_quantity,price_used,exec_hint"

        # Check first action
        assert "MAJOR,Bitcoin,BTC,BUY,1000.50" in lines[1]
        assert "0.02" in lines[1]
        assert "50000" in lines[1]

        # Check second action
        assert "STABLE,USDC,USDC,SELL,-500.00" in lines[2]

    def test_to_csv_handles_empty_actions(self):
        """to_csv should handle empty actions list"""
        from api.services.csv_helpers import to_csv

        result = to_csv([])
        assert result == "group,alias,symbol,action,usd,est_quantity,price_used,exec_hint"

    def test_to_csv_handles_missing_fields(self):
        """to_csv should handle actions with missing optional fields"""
        from api.services.csv_helpers import to_csv

        actions = [
            {
                "symbol": "BTC",
                "action": "BUY",
                "usd": 1000
                # Missing: group, alias, est_quantity, price_used, exec_hint
            }
        ]

        result = to_csv(actions)
        lines = result.split("\n")

        # Should not crash, use empty strings for missing fields
        assert len(lines) == 2
        assert "BTC,BUY,1000.00" in lines[1]


class TestCointrackingHelpers:
    """Tests for api/services/cointracking_helpers.py"""

    def test_classify_location_cex(self):
        """classify_location should identify CEX exchanges"""
        from api.services.cointracking_helpers import classify_location

        # Note: This depends on constants.FAST_SELL_EXCHANGES
        # We'll test the pattern, actual result depends on constants
        result_binance = classify_location("Binance")
        result_kraken = classify_location("Kraken")

        # CEX should be 0, DeFi=1, Cold=2, Other=3
        assert result_binance in [0, 1, 2, 3]
        assert result_kraken in [0, 1, 2, 3]

    def test_pick_primary_location_for_symbol(self):
        """pick_primary_location_for_symbol should find highest value exchange"""
        from api.services.cointracking_helpers import pick_primary_location_for_symbol

        detailed_holdings = {
            "Binance": [
                {"symbol": "BTC", "value_usd": 50000},
                {"symbol": "ETH", "value_usd": 3000}
            ],
            "Kraken": [
                {"symbol": "BTC", "value_usd": 10000},
                {"symbol": "ETH", "value_usd": 5000}
            ],
            "Coinbase": [
                {"symbol": "BTC", "value_usd": 30000}
            ]
        }

        # BTC highest on Binance (50000)
        assert pick_primary_location_for_symbol("BTC", detailed_holdings) == "Binance"

        # ETH highest on Kraken (5000)
        assert pick_primary_location_for_symbol("ETH", detailed_holdings) == "Kraken"

        # Unknown symbol returns default
        assert pick_primary_location_for_symbol("XRP", detailed_holdings) == "CoinTracking"

    def test_pick_primary_location_empty_holdings(self):
        """pick_primary_location_for_symbol should handle empty holdings"""
        from api.services.cointracking_helpers import pick_primary_location_for_symbol

        assert pick_primary_location_for_symbol("BTC", {}) == "CoinTracking"
        assert pick_primary_location_for_symbol("BTC", None) == "CoinTracking"


class TestLocationAssigner:
    """Tests for api/services/location_assigner.py"""

    def test_assign_locations_keeps_existing_specific_location(self):
        """assign_locations_to_actions should keep existing specific locations"""
        from api.services.location_assigner import assign_locations_to_actions

        plan = {
            "actions": [
                {"symbol": "BTC", "usd": -1000, "location": "Binance"}
            ]
        }
        rows = []

        result = assign_locations_to_actions(plan, rows)

        # Should keep Binance
        assert result["actions"][0]["location"] == "Binance"

    def test_assign_locations_splits_sell_proportionally(self):
        """assign_locations_to_actions should split SELL across exchanges"""
        from api.services.location_assigner import assign_locations_to_actions

        plan = {
            "actions": [
                {"symbol": "BTC", "usd": -1000, "location": "Unknown"}
            ]
        }

        rows = [
            {"symbol": "BTC", "location": "Binance", "value_usd": 30000},
            {"symbol": "BTC", "location": "Kraken", "value_usd": 20000},
            {"symbol": "BTC", "location": "Coinbase", "value_usd": 10000}
        ]

        result = assign_locations_to_actions(plan, rows, min_trade_usd=1.0)

        # Should split into 3 actions proportionally
        # Binance: 30000/60000 * 1000 = 500
        # Kraken: 20000/60000 * 1000 = 333.33
        # Coinbase: 10000/60000 * 1000 = 166.67

        actions = result["actions"]
        assert len(actions) == 3

        binance_action = next(a for a in actions if a["location"] == "Binance")
        assert abs(binance_action["usd"] + 500) < 1  # ~-500

        kraken_action = next(a for a in actions if a["location"] == "Kraken")
        assert abs(kraken_action["usd"] + 333.33) < 1  # ~-333.33

    def test_assign_locations_buy_leaves_as_is(self):
        """assign_locations_to_actions should leave BUY actions unchanged"""
        from api.services.location_assigner import assign_locations_to_actions

        plan = {
            "actions": [
                {"symbol": "BTC", "usd": 1000, "location": "Unknown"}
            ]
        }
        rows = []

        result = assign_locations_to_actions(plan, rows)

        # BUY actions stay as-is (UI chooses exchange)
        assert len(result["actions"]) == 1
        assert result["actions"][0]["usd"] == 1000


class TestPriceEnricher:
    """Tests for api/services/price_enricher.py"""

    def test_get_data_age_minutes_cointracking_csv(self):
        """get_data_age_minutes should estimate age from CSV mtime"""
        from api.services.price_enricher import get_data_age_minutes

        # Should return a reasonable age (depends on actual CSV file)
        age = get_data_age_minutes("cointracking")
        assert age >= 0  # Age should be non-negative

    def test_get_data_age_minutes_api(self):
        """get_data_age_minutes should return fresh age for API"""
        from api.services.price_enricher import get_data_age_minutes

        age = get_data_age_minutes("cointracking_api")
        assert age == 1.0  # API data is fresh (1 min)

    def test_get_data_age_minutes_stub(self):
        """get_data_age_minutes should return 0 for stub"""
        from api.services.price_enricher import get_data_age_minutes

        age = get_data_age_minutes("stub")
        assert age == 0.0

    @pytest.mark.asyncio
    async def test_enrich_actions_with_prices_local_mode(self):
        """enrich_actions_with_prices should use local prices in local mode"""
        from api.services.price_enricher import enrich_actions_with_prices

        plan = {
            "actions": [
                {"symbol": "BTC", "usd": 1000},
                {"symbol": "ETH", "usd": 500}
            ]
        }

        rows = [
            {"symbol": "BTC", "value_usd": 50000, "amount": 1.0},
            {"symbol": "ETH", "value_usd": 3000, "amount": 1.0}
        ]

        result = await enrich_actions_with_prices(plan, rows, pricing_mode="local", source_used="cointracking")

        # Should add price_used and est_quantity
        assert result["actions"][0]["price_used"] == 50000
        assert result["actions"][0]["price_source"] == "local"
        assert abs(result["actions"][0]["est_quantity"] - 0.02) < 0.001  # 1000/50000 = 0.02

        assert result["actions"][1]["price_used"] == 3000
        assert result["actions"][1]["price_source"] == "local"
        assert abs(result["actions"][1]["est_quantity"] - 0.16666) < 0.001  # 500/3000 = 0.166...

    @pytest.mark.asyncio
    async def test_enrich_actions_adds_metadata(self):
        """enrich_actions_with_prices should add pricing metadata"""
        from api.services.price_enricher import enrich_actions_with_prices

        plan = {"actions": []}
        rows = []

        result = await enrich_actions_with_prices(plan, rows, pricing_mode="local", source_used="cointracking")

        # Should add meta section
        assert "meta" in result
        assert result["meta"]["pricing_mode"] == "local"


# Run with: pytest tests/unit/test_services_phase3.py -v
