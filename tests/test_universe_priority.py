# tests/test_universe_priority.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

# Test des imports sans erreur
def test_imports():
    """Test que tous les modules se chargent sans erreur."""
    from connectors.coingecko import CoinGeckoConnector, CoinMeta
    from services.universe import UniverseManager, ScoredCoin, get_universe_cached
    from services.rebalance import plan_rebalance

    assert CoinGeckoConnector is not None
    assert CoinMeta is not None
    assert UniverseManager is not None
    assert ScoredCoin is not None
    assert get_universe_cached is not None
    assert plan_rebalance is not None


class TestCoinGeckoConnector:
    """Tests pour le connecteur CoinGecko."""

    def test_coingecko_resolve_mapping(self):
        """Test de résolution des aliases vers coingecko_id."""
        from connectors.coingecko import CoinGeckoConnector

        # Mock du fichier aliases.json
        mock_aliases = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "UNKNOWN": "unknown-coin"
        }

        with patch('connectors.coingecko.os.path.exists', return_value=True), \
             patch('connectors.coingecko.open') as mock_open:

            mock_file = Mock()
            mock_file.read.return_value = json.dumps({"mappings": mock_aliases})
            mock_open.return_value.__enter__.return_value = mock_file

            connector = CoinGeckoConnector()

            assert connector._resolve_coingecko_id("BTC") == "bitcoin"
            assert connector._resolve_coingecko_id("ETH") == "ethereum"
            assert connector._resolve_coingecko_id("nonexistent") == "nonexistent"

    def test_coingecko_market_snapshot_mock(self):
        """Test du market snapshot avec données mockées."""
        from connectors.coingecko import CoinGeckoConnector, CoinMeta

        connector = CoinGeckoConnector()

        # Mock de la réponse API
        mock_response = {
            "bitcoin": {
                "usd": 45000,
                "usd_market_cap": 900000000000,
                "usd_24h_vol": 25000000000,
                "usd_30d_change": 5.2,
                "usd_90d_change": -10.1
            }
        }

        with patch.object(connector, '_make_request', return_value=mock_response), \
             patch.object(connector, '_resolve_coingecko_id', return_value="bitcoin"):

            result = connector.get_market_snapshot(["BTC"])

            assert len(result) == 1
            assert "BTC" in result

            coin = result["BTC"]
            assert isinstance(coin, CoinMeta)
            assert coin.symbol == "BTC"
            assert coin.coingecko_id == "bitcoin"
            assert coin.market_cap_rank is not None
            assert coin.volume_24h == 25000000000
            assert coin.price_change_30d == 5.2
            assert coin.liquidity_proxy is not None


class TestUniverseManager:
    """Tests pour le gestionnaire d'univers."""

    def test_universe_config_loading(self):
        """Test du chargement de configuration."""
        from services.universe import UniverseManager

        manager = UniverseManager()
        config = manager._load_config()

        # Config par défaut doit être chargée
        assert "features" in config
        assert "scoring" in config
        assert "allocation" in config
        assert config["features"]["priority_allocation"] is True

    def test_score_calculation(self):
        """Test du calcul de scores."""
        from services.universe import UniverseManager
        from connectors.coingecko import CoinMeta

        manager = UniverseManager()

        # Coin avec bonnes métriques
        good_coin = CoinMeta(
            symbol="BTC",
            alias="BTC",
            coingecko_id="bitcoin",
            market_cap_rank=1,
            volume_24h=25000000000,
            price_change_30d=5.0,
            price_change_90d=10.0,
            liquidity_proxy=0.1,
            risk_flags=[]
        )

        # Coin avec mauvaises métriques
        bad_coin = CoinMeta(
            symbol="UNKNOWN",
            alias="UNKNOWN",
            coingecko_id="unknown",
            market_cap_rank=1000,
            volume_24h=10000,
            price_change_30d=-30.0,
            price_change_90d=-50.0,
            liquidity_proxy=0.001,
            risk_flags=["small_cap", "low_volume"]
        )

        universe = {"TEST": [good_coin, bad_coin]}
        scored = manager.score_group_universe(universe)

        assert "TEST" in scored
        assert len(scored["TEST"]) == 2

        # Le bon coin doit avoir un meilleur score
        scores = [coin.score for coin in scored["TEST"]]
        assert scores[0] > scores[1]  # Triés par score décroissant


class TestPlanRebalanceIntegration:
    """Tests d'intégration pour plan_rebalance avec mode priority."""

    def test_plan_rebalance_proportional_unchanged(self):
        """Test de non-régression : mode proportional identique."""
        from services.rebalance import plan_rebalance

        # Portfolio test
        rows = [
            {"symbol": "BTC", "alias": "BTC", "value_usd": 3500, "location": "CoinTracking"},
            {"symbol": "ETH", "alias": "ETH", "value_usd": 2000, "location": "CoinTracking"},
            {"symbol": "USDC", "alias": "USDC", "value_usd": 500, "location": "CoinTracking"},
        ]

        targets = {"BTC": 50, "ETH": 30, "Stablecoins": 20}

        # Mode proportional (défaut)
        plan_proportional = plan_rebalance(
            rows=rows,
            group_targets_pct=targets,
            sub_allocation="proportional",
            min_trade_usd=25.0
        )

        # Mode absent (défaut)
        plan_default = plan_rebalance(
            rows=rows,
            group_targets_pct=targets,
            # sub_allocation non spécifié
            min_trade_usd=25.0
        )

        # Les résultats doivent être identiques
        assert plan_proportional["total_usd"] == plan_default["total_usd"]
        assert plan_proportional["current_by_group"] == plan_default["current_by_group"]
        assert len(plan_proportional["actions"]) == len(plan_default["actions"])

        # Pas de métadonnées priority
        assert "priority_meta" not in plan_proportional
        assert "priority_meta" not in plan_default

    def test_plan_rebalance_priority_mode_fallback(self):
        """Test du mode priority avec fallback vers proportional."""
        from services.rebalance import plan_rebalance

        rows = [
            {"symbol": "BTC", "alias": "BTC", "value_usd": 3500, "location": "CoinTracking"},
            {"symbol": "ETH", "alias": "ETH", "value_usd": 2000, "location": "CoinTracking"},
        ]

        targets = {"BTC": 50, "ETH": 50}

        # Mock l'univers pour qu'il soit indisponible
        with patch('services.universe.get_universe_cached', return_value=None):
            plan = plan_rebalance(
                rows=rows,
                group_targets_pct=targets,
                sub_allocation="priority",
                min_trade_usd=25.0
            )

        # Plan doit exister (fallback vers proportional)
        assert plan["total_usd"] > 0
        assert "actions" in plan

        # Pas de crash, comportement de fallback
        assert isinstance(plan["actions"], list)

    def test_plan_rebalance_priority_mode_with_universe(self):
        """Test du mode priority avec univers disponible."""
        from services.rebalance import plan_rebalance
        from services.universe import ScoredCoin
        from connectors.coingecko import CoinMeta

        # Portfolio test
        rows = [
            {"symbol": "BTC", "alias": "BTC", "value_usd": 1000, "location": "CoinTracking"},
            {"symbol": "ETH", "alias": "ETH", "value_usd": 1000, "location": "CoinTracking"},
            {"symbol": "LINK", "alias": "LINK", "value_usd": 1000, "location": "CoinTracking"},
        ]

        targets = {"BTC": 40, "ETH": 40, "L1/L0 majors": 20}

        # Mock univers avec scores
        btc_coin = ScoredCoin(
            meta=CoinMeta("BTC", "BTC", "bitcoin", market_cap_rank=1),
            score=0.9,
            reasons={"cap_rank_inv": 0.3, "liquidity": 0.3, "momentum": 0.3}
        )

        eth_coin = ScoredCoin(
            meta=CoinMeta("ETH", "ETH", "ethereum", market_cap_rank=2),
            score=0.8,
            reasons={"cap_rank_inv": 0.25, "liquidity": 0.3, "momentum": 0.25}
        )

        link_coin = ScoredCoin(
            meta=CoinMeta("LINK", "LINK", "chainlink", market_cap_rank=20),
            score=0.6,
            reasons={"cap_rank_inv": 0.2, "liquidity": 0.2, "momentum": 0.2}
        )

        mock_universe = {
            "BTC": [btc_coin],
            "ETH": [eth_coin],
            "L1/L0 majors": [link_coin]
        }

        with patch('services.universe.get_universe_cached', return_value=mock_universe):
            plan = plan_rebalance(
                rows=rows,
                group_targets_pct=targets,
                sub_allocation="priority",
                min_trade_usd=25.0
            )

        # Plan doit contenir des métadonnées priority
        assert "priority_meta" in plan
        assert plan["priority_meta"]["mode"] == "priority"
        assert plan["priority_meta"]["universe_available"] is True
        assert "groups_details" in plan["priority_meta"]


class TestConfigAndFiles:
    """Tests des fichiers de configuration et structure."""

    def test_universe_config_exists_and_valid(self):
        """Test que config/universe.json existe et est valide."""
        config_path = "config/universe.json"
        assert os.path.exists(config_path), f"Config file missing: {config_path}"

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Structure requise
        assert "features" in config
        assert "scoring" in config
        assert "allocation" in config
        assert "guardrails" in config
        assert "lists" in config
        assert "cache" in config

        # Features
        assert "priority_allocation" in config["features"]

        # Scoring weights
        weights = config["scoring"]["weights"]
        assert "w_cap_rank_inv" in weights
        assert "w_liquidity" in weights
        assert "w_momentum" in weights
        assert "w_internal" in weights
        assert "w_risk" in weights

    def test_aliases_mapping_exists_and_valid(self):
        """Test que data/mkt/aliases.json existe et est valide."""
        aliases_path = "data/mkt/aliases.json"
        assert os.path.exists(aliases_path), f"Aliases file missing: {aliases_path}"

        with open(aliases_path, 'r', encoding='utf-8') as f:
            aliases_data = json.load(f)

        assert "mappings" in aliases_data
        assert "categories" in aliases_data

        mappings = aliases_data["mappings"]

        # Mapping essentiels
        assert "BTC" in mappings
        assert "ETH" in mappings
        assert "SOL" in mappings
        assert mappings["BTC"] == "bitcoin"
        assert mappings["ETH"] == "ethereum"

    def test_cache_directory_structure(self):
        """Test que la structure de cache est créée."""
        cache_dir = "data/cache"
        assert os.path.exists(cache_dir), f"Cache directory missing: {cache_dir}"
        assert os.path.isdir(cache_dir), f"Cache path is not a directory: {cache_dir}"


if __name__ == "__main__":
    # Exécution simple des tests
    test_imports()
    print("Imports tests passed")

    # Tests de configuration
    config_test = TestConfigAndFiles()
    config_test.test_universe_config_exists_and_valid()
    config_test.test_aliases_mapping_exists_and_valid()
    config_test.test_cache_directory_structure()
    print("Configuration tests passed")

    print("All basic tests passed! Run 'pytest tests/test_universe_priority.py' for full test suite.")