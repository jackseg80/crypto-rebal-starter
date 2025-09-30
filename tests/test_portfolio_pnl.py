"""
Tests unitaires pour le système P&L portfolio avec ancres et détection de flux.
"""

import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from services.portfolio import (
    PortfolioAnalytics,
    _compute_anchor_ts,
    _upsert_daily_snapshot,
    _atomic_json_dump,
    TZ
)


@pytest.fixture
def temp_history_file():
    """Fichier temporaire pour portfolio_history.json"""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def portfolio_analytics(temp_history_file):
    """Instance PortfolioAnalytics avec fichier temporaire"""
    analytics = PortfolioAnalytics()
    analytics.historical_data_file = temp_history_file
    return analytics


@pytest.fixture
def sample_balances():
    """Données de balance sample pour tests"""
    return {
        "source_used": "cointracking",
        "items": [
            {"symbol": "BTC", "value_usd": 50000, "amount": 1.0},
            {"symbol": "ETH", "value_usd": 30000, "amount": 10.0},
            {"symbol": "USDT", "value_usd": 20000, "amount": 20000}
        ]
    }


class TestAtomicWrite:
    """Tests pour l'écriture atomique JSON"""

    def test_atomic_write_creates_file(self, temp_history_file):
        """Vérifie que l'écriture atomique crée le fichier"""
        data = {"test": "value"}
        _atomic_json_dump(data, temp_history_file)

        assert os.path.exists(temp_history_file)
        with open(temp_history_file, 'r') as f:
            loaded = json.load(f)
        assert loaded == data

    def test_atomic_write_overwrites_safely(self, temp_history_file):
        """Vérifie que l'écrasement est atomique"""
        # Écriture initiale
        data1 = {"version": 1}
        _atomic_json_dump(data1, temp_history_file)

        # Écrasement
        data2 = {"version": 2}
        _atomic_json_dump(data2, temp_history_file)

        with open(temp_history_file, 'r') as f:
            loaded = json.load(f)
        assert loaded == data2

    def test_atomic_write_no_temp_files_left(self, temp_history_file):
        """Vérifie qu'aucun fichier temporaire ne reste après écriture"""
        temp_dir = os.path.dirname(temp_history_file)
        basename = os.path.basename(temp_history_file)

        # Compter les fichiers .tmp AVANT
        before_files = [f for f in os.listdir(temp_dir) if f.startswith(f".{basename}.") and f.endswith('.tmp')]

        data = {"test": "cleanup"}
        _atomic_json_dump(data, temp_history_file)

        # Compter les fichiers .tmp APRÈS
        after_files = [f for f in os.listdir(temp_dir) if f.startswith(f".{basename}.") and f.endswith('.tmp')]

        # Vérifier qu'on n'a pas laissé de fichiers temporaires NOTRE opération
        assert len(after_files) == len(before_files)


class TestAnchorComputation:
    """Tests pour le calcul des ancres temporelles"""

    def test_anchor_midnight(self):
        """Vérifie ancre midnight = début du jour actuel"""
        now = datetime(2025, 9, 30, 14, 30, 0, tzinfo=TZ)
        anchor_ts, window_ts = _compute_anchor_ts(anchor="midnight", window="24h", now=now)

        assert anchor_ts is not None
        assert anchor_ts.hour == 0
        assert anchor_ts.minute == 0
        assert anchor_ts.second == 0
        assert anchor_ts.date() == now.date()

    def test_anchor_prev_snapshot(self):
        """Vérifie prev_snapshot retourne None (snapshot choisi par logique)"""
        anchor_ts, window_ts = _compute_anchor_ts(anchor="prev_snapshot", window="24h")

        assert anchor_ts is None
        assert window_ts is not None

    def test_window_24h(self):
        """Vérifie window 24h = now - 1 jour"""
        now = datetime(2025, 9, 30, 12, 0, 0, tzinfo=TZ)
        anchor_ts, window_ts = _compute_anchor_ts(anchor="prev_snapshot", window="24h", now=now)

        expected = now - timedelta(days=1)
        assert abs((window_ts - expected).total_seconds()) < 1

    def test_window_7d(self):
        """Vérifie window 7d = now - 7 jours"""
        now = datetime(2025, 9, 30, 12, 0, 0, tzinfo=TZ)
        anchor_ts, window_ts = _compute_anchor_ts(anchor="prev_snapshot", window="7d", now=now)

        expected = now - timedelta(days=7)
        assert abs((window_ts - expected).total_seconds()) < 1

    def test_window_ytd(self):
        """Vérifie window ytd = début d'année"""
        now = datetime(2025, 9, 30, 12, 0, 0, tzinfo=TZ)
        anchor_ts, window_ts = _compute_anchor_ts(anchor="prev_snapshot", window="ytd", now=now)

        assert window_ts.year == 2025
        assert window_ts.month == 1
        assert window_ts.day == 1
        assert window_ts.hour == 0


class TestDailyDeduplication:
    """Tests pour la déduplication des snapshots journaliers"""

    def test_upsert_new_snapshot(self):
        """Vérifie qu'un nouveau snapshot est ajouté"""
        entries = []
        now = datetime.now(TZ)
        snap = {
            "date": now.isoformat(),
            "user_id": "jack",
            "source": "cointracking",
            "total_value_usd": 100000
        }

        _upsert_daily_snapshot(entries, snap, "jack", "cointracking")

        assert len(entries) == 1
        assert entries[0]["total_value_usd"] == 100000

    def test_upsert_same_day_replaces(self):
        """Vérifie qu'un snapshot le même jour est remplacé"""
        now = datetime.now(TZ)
        snap1 = {
            "date": now.replace(hour=8).isoformat(),
            "user_id": "jack",
            "source": "cointracking",
            "total_value_usd": 100000
        }
        snap2 = {
            "date": now.replace(hour=16).isoformat(),
            "user_id": "jack",
            "source": "cointracking",
            "total_value_usd": 105000
        }

        entries = [snap1]
        _upsert_daily_snapshot(entries, snap2, "jack", "cointracking")

        assert len(entries) == 1
        assert entries[0]["total_value_usd"] == 105000

    def test_upsert_different_day_adds(self):
        """Vérifie que des snapshots de jours différents coexistent"""
        yesterday = datetime.now(TZ) - timedelta(days=1)
        today = datetime.now(TZ)

        snap1 = {
            "date": yesterday.isoformat(),
            "user_id": "jack",
            "source": "cointracking",
            "total_value_usd": 100000
        }
        snap2 = {
            "date": today.isoformat(),
            "user_id": "jack",
            "source": "cointracking",
            "total_value_usd": 105000
        }

        entries = [snap1]
        _upsert_daily_snapshot(entries, snap2, "jack", "cointracking")

        assert len(entries) == 2

    def test_upsert_different_user_not_replaced(self):
        """Vérifie que des users différents ne se remplacent pas"""
        now = datetime.now(TZ)
        snap1 = {
            "date": now.isoformat(),
            "user_id": "jack",
            "source": "cointracking",
            "total_value_usd": 100000
        }
        snap2 = {
            "date": now.isoformat(),
            "user_id": "demo",
            "source": "cointracking",
            "total_value_usd": 50000
        }

        entries = [snap1]
        _upsert_daily_snapshot(entries, snap2, "demo", "cointracking")

        assert len(entries) == 2


class TestPnLCalculation:
    """Tests pour le calcul du P&L avec différentes ancres"""

    def test_pnl_no_historical_data(self, portfolio_analytics, sample_balances):
        """Vérifie comportement sans données historiques"""
        metrics = portfolio_analytics.calculate_portfolio_metrics(sample_balances)
        performance = portfolio_analytics.calculate_performance_metrics(
            metrics,
            user_id="jack",
            source="cointracking"
        )

        assert performance["performance_available"] is False
        assert "Pas de données historiques" in performance["message"]

    def test_pnl_midnight_anchor(self, portfolio_analytics, sample_balances, temp_history_file):
        """Vérifie P&L avec ancre midnight"""
        # Créer un snapshot hier soir
        yesterday = datetime.now(TZ) - timedelta(days=1)
        yesterday_evening = yesterday.replace(hour=23, minute=0, second=0)

        snapshot = {
            "date": yesterday_evening.isoformat(),
            "user_id": "jack",
            "source": "cointracking",
            "total_value_usd": 95000,
            "asset_count": 3,
            "group_count": 1,
            "diversity_score": 1,
            "top_holding_symbol": "BTC",
            "top_holding_percentage": 0.5,
            "group_distribution": {},
            "valuation_currency": "USD",
            "price_source": "cointracking",
            "pricing_timestamp": yesterday_evening.isoformat()
        }

        _atomic_json_dump([snapshot], temp_history_file)

        # Calculer métriques actuelles (100k)
        metrics = portfolio_analytics.calculate_portfolio_metrics(sample_balances)

        # P&L avec anchor=midnight (devrait utiliser snapshot d'hier)
        performance = portfolio_analytics.calculate_performance_metrics(
            metrics,
            user_id="jack",
            source="cointracking",
            anchor="midnight",
            window="24h"
        )

        assert performance["performance_available"] is True
        assert performance["comparison"]["anchor"] == "midnight"
        # Le P&L dépend du moment où le test est exécuté
        # On vérifie juste que les champs existent
        assert "absolute_change_usd" in performance
        assert "suspected_flow" in performance

    def test_pnl_outlier_detection(self, portfolio_analytics, sample_balances, temp_history_file):
        """Vérifie détection d'outlier (flux suspect)"""
        # Snapshot à 100k
        yesterday = datetime.now(TZ) - timedelta(days=1)
        snapshot = {
            "date": yesterday.isoformat(),
            "user_id": "jack",
            "source": "cointracking",
            "total_value_usd": 100000,
            "asset_count": 3,
            "group_count": 1,
            "diversity_score": 1,
            "top_holding_symbol": "BTC",
            "top_holding_percentage": 0.5,
            "group_distribution": {},
            "valuation_currency": "USD",
            "price_source": "cointracking",
            "pricing_timestamp": yesterday.isoformat()
        }

        _atomic_json_dump([snapshot], temp_history_file)

        # Créer balances à 160k (+60% en 1 jour → flux suspect)
        large_balances = {
            "source_used": "cointracking",
            "items": [
                {"symbol": "BTC", "value_usd": 80000, "amount": 1.6},
                {"symbol": "ETH", "value_usd": 50000, "amount": 16.67},
                {"symbol": "USDT", "value_usd": 30000, "amount": 30000}
            ]
        }

        metrics = portfolio_analytics.calculate_portfolio_metrics(large_balances)
        performance = portfolio_analytics.calculate_performance_metrics(
            metrics,
            user_id="jack",
            source="cointracking",
            anchor="prev_snapshot"
        )

        assert performance["performance_available"] is True
        assert performance["suspected_flow"] is True  # >30% change
        assert performance["percentage_change"] > 30

    def test_pnl_window_7d(self, portfolio_analytics, sample_balances, temp_history_file):
        """Vérifie P&L avec fenêtre 7 jours"""
        # Créer snapshots à J-10, J-5, J-1
        now = datetime.now(TZ)
        snapshots = [
            {
                "date": (now - timedelta(days=10)).isoformat(),
                "user_id": "jack",
                "source": "cointracking",
                "total_value_usd": 90000,
                "asset_count": 3,
                "group_count": 1,
                "diversity_score": 1,
                "top_holding_symbol": "BTC",
                "top_holding_percentage": 0.5,
                "group_distribution": {},
                "valuation_currency": "USD",
                "price_source": "cointracking",
                "pricing_timestamp": (now - timedelta(days=10)).isoformat()
            },
            {
                "date": (now - timedelta(days=5)).isoformat(),
                "user_id": "jack",
                "source": "cointracking",
                "total_value_usd": 95000,
                "asset_count": 3,
                "group_count": 1,
                "diversity_score": 1,
                "top_holding_symbol": "BTC",
                "top_holding_percentage": 0.5,
                "group_distribution": {},
                "valuation_currency": "USD",
                "price_source": "cointracking",
                "pricing_timestamp": (now - timedelta(days=5)).isoformat()
            },
            {
                "date": (now - timedelta(days=1)).isoformat(),
                "user_id": "jack",
                "source": "cointracking",
                "total_value_usd": 98000,
                "asset_count": 3,
                "group_count": 1,
                "diversity_score": 1,
                "top_holding_symbol": "BTC",
                "top_holding_percentage": 0.5,
                "group_distribution": {},
                "valuation_currency": "USD",
                "price_source": "cointracking",
                "pricing_timestamp": (now - timedelta(days=1)).isoformat()
            }
        ]

        _atomic_json_dump(snapshots, temp_history_file)

        metrics = portfolio_analytics.calculate_portfolio_metrics(sample_balances)
        performance = portfolio_analytics.calculate_performance_metrics(
            metrics,
            user_id="jack",
            source="cointracking",
            anchor="prev_snapshot",
            window="7d"
        )

        assert performance["performance_available"] is True
        assert performance["comparison"]["window"] == "7d"
        # Devrait utiliser snapshot le plus proche <= now - 7d (donc J-10: 90k)
        assert performance["historical_value_usd"] == 90000


class TestSnapshotSaving:
    """Tests pour la sauvegarde de snapshots"""

    def test_save_snapshot_creates_file(self, portfolio_analytics, sample_balances):
        """Vérifie que save_snapshot crée le fichier"""
        success = portfolio_analytics.save_portfolio_snapshot(
            sample_balances,
            user_id="jack",
            source="cointracking"
        )

        assert success is True
        assert os.path.exists(portfolio_analytics.historical_data_file)

    def test_save_snapshot_metadata(self, portfolio_analytics, sample_balances):
        """Vérifie que les métadonnées de valorisation sont présentes"""
        portfolio_analytics.save_portfolio_snapshot(
            sample_balances,
            user_id="jack",
            source="cointracking"
        )

        with open(portfolio_analytics.historical_data_file, 'r') as f:
            data = json.load(f)

        assert len(data) == 1
        snap = data[0]
        assert "valuation_currency" in snap
        assert snap["valuation_currency"] == "USD"
        assert "price_source" in snap
        assert "pricing_timestamp" in snap

    def test_save_snapshot_isolation(self, portfolio_analytics, sample_balances):
        """Vérifie isolation par (user_id, source)"""
        # Sauvegarder pour jack/cointracking
        portfolio_analytics.save_portfolio_snapshot(
            sample_balances,
            user_id="jack",
            source="cointracking"
        )

        # Sauvegarder pour demo/cointracking
        portfolio_analytics.save_portfolio_snapshot(
            sample_balances,
            user_id="demo",
            source="cointracking"
        )

        with open(portfolio_analytics.historical_data_file, 'r') as f:
            data = json.load(f)

        assert len(data) == 2
        users = {snap["user_id"] for snap in data}
        assert users == {"jack", "demo"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])