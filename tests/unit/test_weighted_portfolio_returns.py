import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from services.portfolio_metrics import PortfolioMetricsService


@pytest.fixture
def portfolio_service() -> PortfolioMetricsService:
    return PortfolioMetricsService()


def test_weighted_returns_handles_sparse_history(portfolio_service: PortfolioMetricsService):
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    price_data = pd.DataFrame(
        {
            "BTC": [100, 110, 105, 120],
            "ETH": [50, float("nan"), 52, 53],
            "ADA": [20, 22, float("nan"), 24],
        },
        index=index,
    )
    balances = [
        {"symbol": "BTC", "value_usd": 7000},
        {"symbol": "ETH", "value_usd": 2000},
        {"symbol": "ADA", "value_usd": 1000},
    ]

    returns = portfolio_service._calculate_weighted_portfolio_returns(price_data, balances)

    assert not returns.empty
    assert len(returns) == 3
    assert returns.index.is_monotonic_increasing
    assert not returns.isna().any()
    assert returns.iloc[0] == pytest.approx(0.10, rel=1e-6)
    assert returns.iloc[1] == pytest.approx(-0.0454545, rel=1e-6)
    assert returns.iloc[2] == pytest.approx(0.1153846, rel=1e-6)
