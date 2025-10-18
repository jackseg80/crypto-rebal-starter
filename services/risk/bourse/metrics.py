"""
Core risk metrics calculations for bourse (stock market) portfolios
Implements VaR, volatility, Sharpe, Sortino, drawdown, beta, and risk scoring
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from scipy import stats
import logging

logger = logging.getLogger(__name__)


def calculate_var_historical(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    portfolio_value: Optional[float] = None
) -> Dict[str, float]:
    """
    Calculate Value at Risk using historical method

    Args:
        returns: Array of historical returns
        confidence_level: Confidence level (default 0.95 for 95%)
        portfolio_value: Optional portfolio value for monetary VaR

    Returns:
        Dictionary with VaR metrics
    """
    if len(returns) == 0:
        raise ValueError("Returns array is empty")

    # Remove NaN values
    returns_clean = returns[~np.isnan(returns)]

    if len(returns_clean) < 10:
        raise ValueError(f"Insufficient data for VaR calculation: {len(returns_clean)} samples")

    # Calculate VaR as the percentile
    alpha = 1 - confidence_level
    var_percentile = np.percentile(returns_clean, alpha * 100)

    result = {
        "method": "historical",
        "confidence_level": confidence_level,
        "var_percentage": float(var_percentile),
        "lookback_days": len(returns_clean)
    }

    if portfolio_value is not None:
        result["var_monetary"] = float(var_percentile * portfolio_value)
        result["portfolio_value"] = float(portfolio_value)

    logger.debug(f"Historical VaR calculated: {var_percentile:.4f} ({confidence_level*100}% confidence)")
    return result


def calculate_var_parametric(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    portfolio_value: Optional[float] = None
) -> Dict[str, float]:
    """
    Calculate Value at Risk using parametric (variance-covariance) method
    Assumes normal distribution of returns

    Args:
        returns: Array of historical returns
        confidence_level: Confidence level (default 0.95)
        portfolio_value: Optional portfolio value for monetary VaR

    Returns:
        Dictionary with VaR metrics
    """
    if len(returns) == 0:
        raise ValueError("Returns array is empty")

    returns_clean = returns[~np.isnan(returns)]

    if len(returns_clean) < 10:
        raise ValueError(f"Insufficient data for parametric VaR: {len(returns_clean)} samples")

    # Calculate mean and std
    mean_return = np.mean(returns_clean)
    std_return = np.std(returns_clean)

    # Z-score for confidence level
    z_score = stats.norm.ppf(1 - confidence_level)

    # VaR = mean + z_score * std (z_score is negative for losses)
    var_parametric = mean_return + z_score * std_return

    result = {
        "method": "parametric",
        "confidence_level": confidence_level,
        "var_percentage": float(var_parametric),
        "mean_return": float(mean_return),
        "std_return": float(std_return),
        "lookback_days": len(returns_clean)
    }

    if portfolio_value is not None:
        result["var_monetary"] = float(var_parametric * portfolio_value)
        result["portfolio_value"] = float(portfolio_value)

    logger.debug(f"Parametric VaR calculated: {var_parametric:.4f}")
    return result


def calculate_var_montecarlo(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    portfolio_value: Optional[float] = None,
    num_simulations: int = 10000,
    random_seed: Optional[int] = 42
) -> Dict[str, float]:
    """
    Calculate Value at Risk using Monte Carlo simulation

    Args:
        returns: Array of historical returns
        confidence_level: Confidence level
        portfolio_value: Optional portfolio value
        num_simulations: Number of Monte Carlo simulations
        random_seed: Random seed for reproducibility (default: 42, None for random)

    Returns:
        Dictionary with VaR metrics
    """
    if len(returns) == 0:
        raise ValueError("Returns array is empty")

    returns_clean = returns[~np.isnan(returns)]

    if len(returns_clean) < 10:
        raise ValueError(f"Insufficient data for Monte Carlo VaR: {len(returns_clean)} samples")

    # Fit distribution parameters
    mean_return = np.mean(returns_clean)
    std_return = np.std(returns_clean)

    # Set random seed for reproducibility
    if random_seed is not None:
        np.random.seed(random_seed)

    # Generate random returns
    simulated_returns = np.random.normal(mean_return, std_return, num_simulations)

    # Calculate VaR from simulations
    alpha = 1 - confidence_level
    var_montecarlo = np.percentile(simulated_returns, alpha * 100)

    result = {
        "method": "montecarlo",
        "confidence_level": confidence_level,
        "var_percentage": float(var_montecarlo),
        "num_simulations": num_simulations,
        "lookback_days": len(returns_clean)
    }

    if portfolio_value is not None:
        result["var_monetary"] = float(var_montecarlo * portfolio_value)
        result["portfolio_value"] = float(portfolio_value)

    logger.debug(f"Monte Carlo VaR calculated: {var_montecarlo:.4f}")
    return result


def calculate_volatility(
    returns: np.ndarray,
    window: Optional[int] = None,
    annualize: bool = True,
    trading_days: int = 252
) -> float:
    """
    Calculate volatility (standard deviation of returns)

    Args:
        returns: Array of returns
        window: Rolling window size (None for entire period)
        annualize: Whether to annualize volatility
        trading_days: Trading days per year (252 for stocks, 365 for crypto)

    Returns:
        Volatility value
    """
    if len(returns) == 0:
        raise ValueError("Returns array is empty")

    returns_clean = returns[~np.isnan(returns)]

    if len(returns_clean) < 2:
        return 0.0

    # Calculate volatility
    if window is not None and window > 0:
        # Rolling volatility - return last value
        if len(returns_clean) < window:
            vol = np.std(returns_clean)
        else:
            vol = np.std(returns_clean[-window:])
    else:
        # Full period volatility
        vol = np.std(returns_clean)

    # Annualize if requested
    if annualize:
        vol = vol * np.sqrt(trading_days)

    return float(vol)


def calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.03,
    annualize: bool = True,
    trading_days: int = 252
) -> float:
    """
    Calculate Sharpe Ratio (risk-adjusted return)

    Args:
        returns: Array of returns
        risk_free_rate: Annual risk-free rate (default 3%)
        annualize: Whether to annualize the ratio
        trading_days: Trading days per year

    Returns:
        Sharpe ratio
    """
    if len(returns) == 0:
        raise ValueError("Returns array is empty")

    returns_clean = returns[~np.isnan(returns)]

    if len(returns_clean) < 2:
        return 0.0

    # Calculate mean return and volatility
    mean_return = np.mean(returns_clean)
    std_return = np.std(returns_clean)

    if std_return == 0:
        return 0.0

    # Convert annual risk-free rate to period rate
    period_rf_rate = risk_free_rate / trading_days

    # Calculate Sharpe ratio
    sharpe = (mean_return - period_rf_rate) / std_return

    # Annualize if requested
    if annualize:
        sharpe = sharpe * np.sqrt(trading_days)

    return float(sharpe)


def calculate_sortino_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.03,
    annualize: bool = True,
    trading_days: int = 252
) -> float:
    """
    Calculate Sortino Ratio (downside risk-adjusted return)

    Args:
        returns: Array of returns
        risk_free_rate: Annual risk-free rate
        annualize: Whether to annualize the ratio
        trading_days: Trading days per year

    Returns:
        Sortino ratio
    """
    if len(returns) == 0:
        raise ValueError("Returns array is empty")

    returns_clean = returns[~np.isnan(returns)]

    if len(returns_clean) < 2:
        return 0.0

    # Calculate mean return
    mean_return = np.mean(returns_clean)

    # Calculate downside deviation (only negative returns)
    downside_returns = returns_clean[returns_clean < 0]

    if len(downside_returns) == 0:
        return 0.0

    downside_std = np.std(downside_returns)

    if downside_std == 0:
        return 0.0

    # Convert annual risk-free rate to period rate
    period_rf_rate = risk_free_rate / trading_days

    # Calculate Sortino ratio
    sortino = (mean_return - period_rf_rate) / downside_std

    # Annualize if requested
    if annualize:
        sortino = sortino * np.sqrt(trading_days)

    return float(sortino)


def calculate_max_drawdown(prices: np.ndarray) -> Dict[str, float]:
    """
    Calculate maximum drawdown from price series

    Args:
        prices: Array of prices

    Returns:
        Dictionary with max drawdown metrics
    """
    if len(prices) == 0:
        raise ValueError("Prices array is empty")

    prices_clean = prices[~np.isnan(prices)]

    if len(prices_clean) < 2:
        return {"max_drawdown": 0.0, "drawdown_days": 0}

    # Calculate running maximum
    running_max = np.maximum.accumulate(prices_clean)

    # Calculate drawdown at each point
    drawdown = (prices_clean - running_max) / running_max

    # Find maximum drawdown
    max_dd = np.min(drawdown)
    max_dd_idx = np.argmin(drawdown)

    # Find peak before max drawdown
    peak_idx = np.argmax(prices_clean[:max_dd_idx+1]) if max_dd_idx > 0 else 0

    # Calculate duration
    drawdown_days = max_dd_idx - peak_idx

    return {
        "max_drawdown": float(max_dd),
        "max_drawdown_pct": float(max_dd * 100),
        "drawdown_days": int(drawdown_days),
        "peak_date_index": int(peak_idx),
        "trough_date_index": int(max_dd_idx)
    }


def calculate_beta(
    asset_returns: np.ndarray,
    benchmark_returns: np.ndarray,
    min_periods: int = 20
) -> float:
    """
    Calculate beta (systematic risk vs benchmark)

    Args:
        asset_returns: Returns of the asset
        benchmark_returns: Returns of the benchmark
        min_periods: Minimum periods required for calculation

    Returns:
        Beta value
    """
    if len(asset_returns) == 0 or len(benchmark_returns) == 0:
        raise ValueError("Returns arrays are empty")

    # Align lengths
    min_len = min(len(asset_returns), len(benchmark_returns))
    asset_clean = asset_returns[:min_len]
    benchmark_clean = benchmark_returns[:min_len]

    # Remove NaN values
    valid_mask = ~(np.isnan(asset_clean) | np.isnan(benchmark_clean))
    asset_clean = asset_clean[valid_mask]
    benchmark_clean = benchmark_clean[valid_mask]

    if len(asset_clean) < min_periods:
        logger.warning(f"Insufficient data for beta calculation: {len(asset_clean)} < {min_periods}")
        return 1.0  # Default to market beta

    # Calculate covariance and variance
    covariance = np.cov(asset_clean, benchmark_clean)[0, 1]
    benchmark_variance = np.var(benchmark_clean)

    if benchmark_variance == 0:
        return 1.0

    beta = covariance / benchmark_variance

    return float(beta)


def calculate_risk_score(
    var_95: float,
    volatility: float,
    sharpe_ratio: float,
    max_drawdown: float,
    beta: float = 1.0
) -> Dict[str, Any]:
    """
    Calculate composite risk score (0-100, higher = lower risk)

    Args:
        var_95: VaR at 95% confidence
        volatility: Annualized volatility
        sharpe_ratio: Sharpe ratio
        max_drawdown: Maximum drawdown (negative value)
        beta: Beta vs benchmark

    Returns:
        Dictionary with risk score and level
    """
    # Normalize components to 0-100 scale (higher = better/safer)

    # VaR score (less negative = better)
    # Typical VaR range: -5% to 0%
    var_score = max(0, min(100, (1 + var_95 / 0.05) * 100))

    # Volatility score (lower = better)
    # Typical vol range: 5% to 50%
    vol_score = max(0, min(100, (1 - volatility / 0.5) * 100))

    # Sharpe score (higher = better)
    # Typical Sharpe range: -1 to 3
    sharpe_score = max(0, min(100, (sharpe_ratio + 1) / 4 * 100))

    # Drawdown score (less negative = better)
    # Typical drawdown range: -50% to 0%
    dd_score = max(0, min(100, (1 + max_drawdown / 0.5) * 100))

    # Beta score (closer to 1 = better, assuming we want market-like risk)
    # Typical beta range: 0 to 2
    beta_score = max(0, min(100, (1 - abs(beta - 1)) * 100))

    # Weighted composite score
    weights = {
        "var": 0.25,
        "volatility": 0.25,
        "sharpe": 0.20,
        "drawdown": 0.20,
        "beta": 0.10
    }

    risk_score = (
        var_score * weights["var"] +
        vol_score * weights["volatility"] +
        sharpe_score * weights["sharpe"] +
        dd_score * weights["drawdown"] +
        beta_score * weights["beta"]
    )

    # Determine risk level
    if risk_score >= 75:
        risk_level = "Low"
    elif risk_score >= 50:
        risk_level = "Moderate"
    elif risk_score >= 25:
        risk_level = "High"
    else:
        risk_level = "Critical"

    return {
        "risk_score": round(risk_score, 1),
        "risk_level": risk_level,
        "component_scores": {
            "var": round(var_score, 1),
            "volatility": round(vol_score, 1),
            "sharpe": round(sharpe_score, 1),
            "drawdown": round(dd_score, 1),
            "beta": round(beta_score, 1)
        },
        "weights": weights
    }


def calculate_calmar_ratio(
    returns: np.ndarray,
    prices: np.ndarray,
    annualize: bool = True,
    trading_days: int = 252
) -> float:
    """
    Calculate Calmar Ratio (annualized return / max drawdown)

    Args:
        returns: Array of returns
        prices: Array of prices
        annualize: Whether to annualize
        trading_days: Trading days per year

    Returns:
        Calmar ratio
    """
    if len(returns) == 0 or len(prices) == 0:
        return 0.0

    returns_clean = returns[~np.isnan(returns)]

    if len(returns_clean) < 2:
        return 0.0

    # Calculate annualized return
    mean_return = np.mean(returns_clean)
    if annualize:
        annualized_return = mean_return * trading_days
    else:
        annualized_return = mean_return

    # Calculate max drawdown
    dd_metrics = calculate_max_drawdown(prices)
    max_dd = abs(dd_metrics["max_drawdown"])

    if max_dd == 0:
        return 0.0

    calmar = annualized_return / max_dd

    return float(calmar)
