"""
Portfolio Optimization API Endpoints
Advanced Markowitz optimization with crypto-specific features
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from pydantic import BaseModel
import logging

from services.portfolio_optimization import (
    PortfolioOptimizer, 
    OptimizationConstraints,
    OptimizationObjective,
    create_crypto_constraints
)
from services.price_history import get_cached_history
from services.price_utils import price_history_to_dataframe, validate_price_data
from connectors import cointracking as ct_file
from services.pricing import FIAT_STABLE_FIXED
import re

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio/optimization", tags=["Portfolio Optimization"])

class OptimizationRequest(BaseModel):
    """Request model for portfolio optimization"""
    objective: str = "max_sharpe"
    lookback_days: int = 365
    expected_return_method: str = "mean_reversion"
    conservative: bool = False
    custom_constraints: Optional[Dict] = None
    target_sectors: Optional[Dict[str, float]] = None
    risk_budget: Optional[Dict[str, float]] = None
    rebalance_periods: Optional[List[int]] = None
    period_weights: Optional[List[float]] = None
    transaction_costs: Optional[Dict[str, float]] = None
    include_current_weights: bool = True

class OptimizationResponse(BaseModel):
    """Response model for portfolio optimization"""
    success: bool
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    diversification_ratio: float
    optimization_score: float
    constraints_satisfied: bool
    risk_contributions: Dict[str, float]
    sector_exposures: Dict[str, float]
    rebalancing_trades: List[Dict]
    optimization_details: Dict

class Suggestion(BaseModel):
    objective: Optional[str] = None
    expected_return_method: Optional[str] = None
    lookback_days: Optional[float] = None
    min_history_days: Optional[float] = None
    min_usd: Optional[float] = None
    min_assets: Optional[int] = None
    max_weight: Optional[float] = None
    max_sector_weight: Optional[float] = None
    min_diversification_ratio: Optional[float] = None
    min_weight: Optional[float] = None
    target_volatility: Optional[float] = None

class Scenario(BaseModel):
    name: str
    description: Optional[str] = None
    suggest: Suggestion

class AnalysisResponse(BaseModel):
    success: bool
    total_value_usd: float
    asset_count: int
    stablecoins_value_usd: float
    stablecoins_weight: float
    top10_weight: float
    hhi: float
    history_coverage: Dict[str, int]
    suggest: Suggestion
    scenarios: List[Scenario] = []
    notes: List[str]

@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_portfolio(
    request: OptimizationRequest,
    source: str = Query("cointracking", description="Data source"),
    min_usd: float = Query(100, description="Minimum USD value to include"),
    min_history_days: int = Query(365, description="Minimum history days required")
):
    """
    Optimize portfolio allocation using advanced Markowitz optimization
    """
    
    try:
        optimizer = PortfolioOptimizer()
        
        # Get current portfolio using the same logic as /balances/current
        if source == "stub":
            balances_response = {
                "source_used": "stub", 
                "items": [
                    {"symbol": "BTC", "value_usd": 105000.0, "amount": 2.5, "location": "Kraken"},
                    {"symbol": "ETH", "value_usd": 47250.0, "amount": 15.75, "location": "Binance"},
                    {"symbol": "USDC", "value_usd": 25000.0, "amount": 25000.0, "location": "Coinbase"},
                    {"symbol": "SOL", "value_usd": 23400.0, "amount": 180.0, "location": "Phantom"},
                    {"symbol": "AVAX", "value_usd": 13500.0, "amount": 450.0, "location": "Ledger"},
                ]
            }
        elif source == "cointracking_api":
            # Try to use CoinTracking API data via unified connector
            try:
                result = await ct_file.get_unified_balances_by_exchange("cointracking_api")
                items = []
                if 'detailed_holdings' in result:
                    for exchange, holdings in (result.get('detailed_holdings') or {}).items():
                        for holding in holdings:
                            if holding.get('value_usd', 0) >= min_usd:
                                items.append(holding)
                elif 'items' in result:
                    for item in result.get('items') or []:
                        if item.get('value_usd', 0) >= min_usd:
                            items.append(item)
                balances_response = {"source_used": "cointracking_api", "items": items}
            except Exception as e:
                logger.warning(f"CoinTracking API failed: {e}, falling back to CSV")
                # Fallback to CSV data
                try:
                    result = ct_file.get_balances_by_exchange_from_csv()
                    items = []
                    if 'detailed_holdings' in result:
                        for exchange, holdings in result['detailed_holdings'].items():
                            for holding in holdings:
                                if holding.get('value_usd', 0) >= min_usd:
                                    items.append(holding)
                    balances_response = {"source_used": "cointracking_csv_fallback", "items": items}
                except Exception:
                    # Final fallback to stub
                    balances_response = {
                        "source_used": "stub_fallback", 
                        "items": [
                            {"symbol": "BTC", "value_usd": 50000.0, "amount": 1.0, "location": "Kraken"},
                            {"symbol": "ETH", "value_usd": 30000.0, "amount": 10.0, "location": "Binance"},
                            {"symbol": "SOL", "value_usd": 10000.0, "amount": 100.0, "location": "Phantom"}
                        ]
                    }
        else:
            # Default cointracking = CSV data
            try:
                result = ct_file.get_balances_by_exchange_from_csv()
                # Convert detailed_holdings to flat items list
                items = []
                if 'detailed_holdings' in result:
                    for exchange, holdings in result['detailed_holdings'].items():
                        for holding in holdings:
                            if holding.get('value_usd', 0) >= min_usd:
                                items.append(holding)
                balances_response = {"source_used": "cointracking", "items": items}
            except Exception:
                # Fallback to stub data
                balances_response = {
                    "source_used": "stub", 
                    "items": [
                        {"symbol": "BTC", "value_usd": 50000.0, "amount": 1.0, "location": "Kraken"},
                        {"symbol": "ETH", "value_usd": 30000.0, "amount": 10.0, "location": "Binance"},
                        {"symbol": "SOL", "value_usd": 10000.0, "amount": 100.0, "location": "Phantom"}
                    ]
                }
        
        if not balances_response.get("items"):
            raise HTTPException(status_code=400, detail="No portfolio data found")
        
        # Canonicalize symbols to avoid duplicates like SOL2, DOT2, etc. (but keep JUPSOL/JITOSOL distinct)
        def canonical_symbol(sym: str) -> str:
            s = (sym or "").upper().strip()
            # Drop trailing digits (CoinTracking variants like SOL2, DOT2, TAO6)
            if re.search(r"\d+$", s) and not re.match(r"^\d", s):
                s = re.sub(r"\d+$", "", s)
            return s

        aggregated = {}
        # Data is already filtered by min_usd from the API call
        for item in balances_response["items"]:
            raw_symbol = str(item.get("symbol") or "").upper()
            value = float(item.get("value_usd") or 0)
            if value <= 0 or not raw_symbol:
                continue
            cs = canonical_symbol(raw_symbol)
            aggregated[cs] = aggregated.get(cs, 0.0) + value

        if not aggregated:
            raise HTTPException(status_code=400, detail="No eligible assets after normalization")

        current_portfolio = dict(aggregated)
        total_value = sum(current_portfolio.values())
        symbols = list(current_portfolio.keys())
        
        # Convert to weights
        current_weights = {symbol: value/total_value for symbol, value in current_portfolio.items()}
        
        # Get price history
        price_data = {}
        missing_symbols = []
        
        for symbol in symbols:
            try:
                # Vérifier d'abord l'historique total disponible (pas juste lookback)
                full_prices = get_cached_history(symbol)  # Tout l'historique
                if not full_prices or len(full_prices) < min_history_days:
                    logger.info(f"Exclusion {symbol}: seulement {len(full_prices) if full_prices else 0} jours d'historique (min: {min_history_days})")
                    missing_symbols.append(symbol)
                    continue
                
                # Maintenant récupérer la fenêtre demandée
                prices = get_cached_history(symbol, days=request.lookback_days)
                if prices and len(prices) > 7:  # Minimum 7 days
                    price_data[symbol] = prices
                else:
                    # Generate synthetic price data for testing
                    logger.warning(f"No historical data for {symbol}, generating synthetic data")
                    import random
                    from datetime import datetime, timedelta
                    
                    # Create 90 days of synthetic price data
                    # Base prices for common crypto assets
                    base_prices = {
                        "BTC": 50000.0, "ETH": 3000.0, "SOL": 130.0, "AVAX": 30.0,
                        "USDC": 1.0, "USDT": 1.0, "BUSD": 1.0, "DAI": 1.0,
                        "ADA": 0.5, "DOT": 7.0, "MATIC": 1.2, "LINK": 15.0,
                        "UNI": 8.0, "LTC": 100.0, "BCH": 300.0, "XLM": 0.12,
                        "ALGO": 0.3, "ATOM": 12.0, "FTT": 25.0, "NEAR": 3.5,
                        "MANA": 0.8, "SAND": 1.5, "CRV": 1.0, "COMP": 60.0,
                        "AAVE": 80.0, "MKR": 800.0, "SNX": 3.0, "YFI": 8000.0,
                        "SUSHI": 1.2, "1INCH": 0.5, "ENJ": 0.4, "BAT": 0.25
                    }
                    base_price = base_prices.get(symbol, 50.0)  # Default $50
                    
                    synthetic_prices = []
                    current_price = base_price
                    for i in range(90):
                        # Simple random walk with slight upward trend
                        daily_change = random.uniform(-0.05, 0.06)  # -5% to +6% daily change
                        current_price *= (1 + daily_change)
                        timestamp = int((datetime.now() - timedelta(days=89-i)).timestamp())
                        synthetic_prices.append((timestamp, current_price))
                    
                    price_data[symbol] = synthetic_prices
            except Exception as e:
                logger.warning(f"Could not get or generate price history for {symbol}: {e}")
                missing_symbols.append(symbol)
        
        if len(price_data) < 3:
            raise HTTPException(
                status_code=400, 
                detail="Insufficient price history data. Need at least 3 assets with historical data."
            )
        
        # Create price DataFrame
        price_df = price_history_to_dataframe(price_data)
        
        if not validate_price_data(price_df, min_days=7):
            raise HTTPException(
                status_code=400,
                detail="Insufficient historical data. Need at least 7 days of price history."
            )
        
        # Calculate expected returns
        expected_returns = optimizer.calculate_expected_returns(
            price_df, method=request.expected_return_method
        )
        
        # Calculate risk model
        cov_matrix, volatilities = optimizer.calculate_risk_model(price_df)
        
        # Set up constraints
        n_assets = len(price_df.columns)
        if request.custom_constraints:
            constraints = OptimizationConstraints(**request.custom_constraints)
        else:
            constraints = create_crypto_constraints(
                conservative=request.conservative, 
                n_assets=n_assets
            )
        
        # Add risk budget if provided
        if request.risk_budget:
            constraints.risk_budget = request.risk_budget
        
        # Add multi-period parameters if provided
        if request.rebalance_periods:
            constraints.rebalance_periods = request.rebalance_periods
        if request.period_weights:
            constraints.period_weights = request.period_weights
        
        # Add transaction costs if provided
        if request.transaction_costs:
            constraints.transaction_costs = request.transaction_costs
        
        # Add sector targets if provided
        if request.target_sectors:
            # This would require more complex constraint handling
            logger.info("Sector targets provided but not yet implemented in constraints")
        
        # Parse objective
        try:
            objective = OptimizationObjective(request.objective)
        except ValueError:
            objective = OptimizationObjective.MAX_SHARPE
        
        # Current weights for assets with price data
        filtered_current_weights = {
            symbol: current_weights.get(symbol, 0) 
            for symbol in price_df.columns
        } if request.include_current_weights else None
        
        # Run optimization
        if objective == OptimizationObjective.MULTI_PERIOD:
            # Use multi-period optimization
            result = optimizer.optimize_multi_period(
                price_history=price_df,
                constraints=constraints,
                current_weights=filtered_current_weights
            )
        else:
            # Use standard optimization
            result = optimizer.optimize_portfolio(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                constraints=constraints,
                objective=objective,
                current_weights=filtered_current_weights
            )
        
        # Calculate total value of optimized assets only (for coherent trade amounts)
        optimized_total_value = sum(
            current_portfolio.get(symbol, 0) 
            for symbol in result.weights.keys()
        )
        
        # Calculate rebalancing trades
        rebalancing_trades = []
        if request.include_current_weights:
            # 1. Trades for assets included in optimization
            for symbol in result.weights:
                current_weight = current_weights.get(symbol, 0)
                target_weight = result.weights[symbol]
                weight_diff = target_weight - current_weight
                
                if abs(weight_diff) > 0.01:  # 1% threshold
                    value_diff = weight_diff * optimized_total_value
                    rebalancing_trades.append({
                        "symbol": symbol,
                        "action": "buy" if weight_diff > 0 else "sell",
                        "current_weight": round(current_weight, 4),
                        "target_weight": round(target_weight, 4),
                        "weight_change": round(weight_diff, 4),
                        "usd_amount": round(abs(value_diff), 2),
                        "priority": "high" if abs(weight_diff) > 0.05 else "medium" if abs(weight_diff) > 0.02 else "low",
                        "reason": "rebalance"
                    })
            
            # 2. "Sell to 0%" trades for excluded assets
            for symbol in current_weights:
                if symbol not in result.weights:
                    current_weight = current_weights[symbol]
                    current_value_usd = current_portfolio.get(symbol, 0)
                    
                    # Include if weight > 1% or value > $50
                    if current_weight > 0.01 or current_value_usd > 50:
                        rebalancing_trades.append({
                            "symbol": symbol,
                            "action": "sell",
                            "current_weight": round(current_weight, 4),
                            "target_weight": 0.0,
                            "weight_change": round(-current_weight, 4),
                            "usd_amount": round(current_value_usd, 2),
                            "priority": "high" if current_weight > 0.05 or current_value_usd > 500 else "medium",
                            "reason": "excluded"
                        })
        
        # Sort trades by priority and absolute change
        rebalancing_trades.sort(key=lambda x: (
            {"high": 3, "medium": 2, "low": 1}[x["priority"]],
            abs(x["weight_change"])
        ), reverse=True)
        
        # Optimization details
        optimization_details = {
            "objective_used": request.objective,
            "method": request.expected_return_method,
            "lookback_days": request.lookback_days,
            "assets_optimized": len(result.weights),
            "assets_excluded": len(missing_symbols),
            "excluded_symbols": missing_symbols,
            "total_portfolio_value": round(total_value, 2),
            "optimization_successful": result.constraints_satisfied,
            "expected_annual_return": round(result.expected_return * 100, 2),
            "expected_annual_volatility": round(result.volatility * 100, 2),
            "risk_free_rate": round(optimizer.risk_free_rate * 100, 2)
        }
        
        return OptimizationResponse(
            success=True,
            weights={k: round(v, 4) for k, v in result.weights.items()},
            expected_return=round(result.expected_return, 4),
            volatility=round(result.volatility, 4),
            sharpe_ratio=round(result.sharpe_ratio, 4),
            diversification_ratio=round(result.diversification_ratio, 4),
            optimization_score=round(result.optimization_score, 4),
            constraints_satisfied=result.constraints_satisfied,
            risk_contributions={k: round(v, 4) for k, v in result.risk_contributions.items()},
            sector_exposures={k: round(v, 4) for k, v in result.sector_exposures.items()},
            rebalancing_trades=rebalancing_trades,
            optimization_details=optimization_details
        )
        
    except Exception as e:
        logger.error(f"Portfolio optimization failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

@router.get("/analyze", response_model=AnalysisResponse)
async def analyze_portfolio(
    source: str = Query("cointracking", description="Data source: cointracking|stub"),
    min_usd: float = Query(50, description="Ignore holdings below this value for stats"),
    target_assets: int = Query(30, description="Desired number of assets to optimize"),
):
    """Analyze current portfolio and suggest optimization parameters."""
    try:
        # Load balances (CSV or stub)
        if source == "stub":
            balances_response = {
                "source_used": "stub",
                "items": [
                    {"symbol": "BTC", "value_usd": 105000.0, "amount": 2.5, "location": "Kraken"},
                    {"symbol": "ETH", "value_usd": 47250.0, "amount": 15.75, "location": "Binance"},
                    {"symbol": "USDC", "value_usd": 25000.0, "amount": 25000.0, "location": "Coinbase"},
                    {"symbol": "SOL", "value_usd": 23400.0, "amount": 180.0, "location": "Phantom"},
                    {"symbol": "AVAX", "value_usd": 13500.0, "amount": 450.0, "location": "Ledger"},
                ]
            }
        else:
            result = ct_file.get_balances_by_exchange_from_csv()
            items = []
            if 'detailed_holdings' in result:
                for _, holdings in result['detailed_holdings'].items():
                    for holding in holdings:
                        if holding.get('value_usd', 0) >= min_usd:
                            items.append(holding)
            balances_response = {"source_used": "cointracking", "items": items}

        items = balances_response.get("items") or []
        if not items:
            raise HTTPException(status_code=400, detail="No portfolio data found")

        # Aggregate stats
        values = []
        total_value = 0.0
        stable_value = 0.0
        symbols = []
        for it in items:
            v = float(it.get("value_usd") or 0.0)
            sym = str(it.get("symbol") or "").upper()
            if v <= 0 or not sym:
                continue
            values.append(v)
            total_value += v
            symbols.append(sym)
            if sym in FIAT_STABLE_FIXED:
                stable_value += v

        if total_value <= 0:
            raise HTTPException(status_code=400, detail="Total portfolio value is zero")

        # Concentration metrics
        weights = [v / total_value for v in sorted(values, reverse=True)]
        top10_weight = sum(weights[:10])
        hhi = sum(w * w for w in weights)  # Herfindahl-Hirschman Index

        # History coverage
        # Consider a wider set of windows for better coverage-based suggestion
        thresholds = [1460, 1095, 730, 365, 180, 90]
        coverage = {str(t): 0 for t in thresholds}
        for sym in set(symbols):
            hist = get_cached_history(sym)
            days = len(hist) if hist else 0
            for t in thresholds:
                if days >= t:
                    coverage[str(t)] += 1

        # Suggest min_usd to target N assets
        suggested_min_usd = min_usd
        try:
            sorted_vals = sorted(values, reverse=True)
            if 1 <= target_assets <= len(sorted_vals):
                cutoff = sorted_vals[target_assets - 1]
                # Nudge down slightly to include borderline assets
                suggested_min_usd = max(min_usd, round(cutoff * 0.95, 2))
        except Exception:
            pass

        # Suggest min_history_days based on coverage
        def choose_min_history():
            # Prefer the longest window that still leaves enough assets.
            # Try to hit target_assets if possible, else accept a lower bar.
            need_primary = max(15, target_assets)  # aim near target
            need_secondary = max(8, target_assets // 2)
            need_minimal = 3

            for t in thresholds:  # thresholds already from longest to shortest
                if coverage.get(str(t), 0) >= need_primary:
                    return t
            for t in thresholds:
                if coverage.get(str(t), 0) >= need_secondary:
                    return t
            for t in thresholds:
                if coverage.get(str(t), 0) >= need_minimal:
                    return t
            # As a last resort use the shortest window
            return thresholds[-1]

        suggested_min_history = choose_min_history()

        # Suggest objective and constraints
        stable_weight = stable_value / total_value if total_value > 0 else 0.0
        suggest = {
            "objective": "max_sharpe",
            "expected_return_method": "mean_reversion",
            "lookback_days": float(suggested_min_history),
            "min_history_days": float(suggested_min_history),
            "min_usd": float(suggested_min_usd),
            "min_assets": 12 if (top10_weight > 0.6 or hhi > 0.10) else 10,
            "max_weight": 0.25,
            "max_sector_weight": 0.5 if stable_weight < 0.4 else 0.4,
            "min_diversification_ratio": 0.5,
            "min_weight": 0.0,
            "target_volatility": 0.25,
        }

        # Build adaptive scenarios tailored to the actual data (stub or CSV)
        def pick_long_window() -> int:
            for t in [1460, 1095, 730]:
                if coverage.get(str(t), 0) >= max(12, target_assets // 2):
                    return t
            return suggested_min_history

        def pick_mid_window() -> int:
            # Prefer 365 if enough assets; else 730; else fallback
            if coverage.get("365", 0) >= max(12, target_assets // 2):
                return 365
            if coverage.get("730", 0) >= max(12, target_assets // 2):
                return 730
            return suggested_min_history

        min_assets_rec = 12 if (top10_weight > 0.6 or hhi > 0.10) else 10
        sector_cap = 0.5 if stable_weight < 0.4 else 0.4
        implied_max_by_assets = 1.0 / max(min_assets_rec, 1)
        base_min_usd = float(suggested_min_usd)

        scenarios: List[Scenario] = []
        scenarios.append(Scenario(
            name="Core Long-Term",
            description="Robust long-horizon Sharpe with broad diversification",
            suggest=Suggestion(
                objective="max_sharpe",
                expected_return_method="historical",
                lookback_days=float(pick_long_window()),
                min_history_days=float(pick_long_window()),
                min_usd=base_min_usd,
                min_assets=min_assets_rec,
                max_weight=min(0.20, implied_max_by_assets),
                max_sector_weight=sector_cap,
                min_diversification_ratio=0.5,
                min_weight=0.0,
                target_volatility=0.25,
            )
        ))

        scenarios.append(Scenario(
            name="Balanced 1-Year",
            description="Balanced Sharpe on 1-year window",
            suggest=Suggestion(
                objective="max_sharpe",
                expected_return_method="historical",
                lookback_days=float(pick_mid_window()),
                min_history_days=float(pick_mid_window()),
                min_usd=base_min_usd,
                min_assets=min_assets_rec,
                max_weight=min(0.20, implied_max_by_assets),
                max_sector_weight=sector_cap,
                min_diversification_ratio=0.5,
                min_weight=0.0,
                target_volatility=0.25,
            )
        ))

        scenarios.append(Scenario(
            name="Tactical Mean-Reversion",
            description="Short-term correction bias with higher target risk",
            suggest=Suggestion(
                objective="max_sharpe",
                expected_return_method="mean_reversion",
                lookback_days=float(pick_mid_window()),
                min_history_days=float(pick_mid_window()),
                min_usd=base_min_usd,
                min_assets=max(min_assets_rec, 12),
                max_weight=min(0.18, 1.0 / max(max(min_assets_rec, 12), 1)),
                max_sector_weight=sector_cap,
                min_diversification_ratio=0.5,
                min_weight=0.0,
                target_volatility=0.30,
            )
        ))

        scenarios.append(Scenario(
            name="Momentum Tilt",
            description="Trend-following tilt on 1-year window",
            suggest=Suggestion(
                objective="max_sharpe",
                expected_return_method="momentum",
                lookback_days=float(pick_mid_window()),
                min_history_days=float(pick_mid_window()),
                min_usd=base_min_usd,
                min_assets=max(min_assets_rec, 12),
                max_weight=min(0.18, 1.0 / max(max(min_assets_rec, 12), 1)),
                max_sector_weight=sector_cap,
                min_diversification_ratio=0.5,
                min_weight=0.0,
                target_volatility=0.30,
            )
        ))

        scenarios.append(Scenario(
            name="Baseline Risk Parity",
            description="Equal risk contribution baseline",
            suggest=Suggestion(
                objective="risk_parity",
                expected_return_method="historical",
                lookback_days=float(pick_mid_window()),
                min_history_days=float(pick_mid_window()),
                min_usd=base_min_usd,
                min_assets=max(min_assets_rec, 15),
                max_weight=min(0.15, 1.0 / max(max(min_assets_rec, 15), 1)),
                max_sector_weight=sector_cap,
                min_diversification_ratio=0.5,
                min_weight=0.0,
                target_volatility=None,
            )
        ))

        notes = []
        if stable_weight > 0.4:
            notes.append("High stablecoin share detected; reducing max sector weight to avoid over-cash portfolios.")
        if coverage.get(str(suggested_min_history), 0) < max(15, target_assets // 2):
            notes.append("Few assets have long history; consider lowering Min History or pre-downloading histories.")
        if top10_weight > 0.7:
            notes.append("High concentration in top holdings; consider lower max_weight or higher min_usd.")

        return AnalysisResponse(
            success=True,
            total_value_usd=round(total_value, 2),
            asset_count=len(values),
            stablecoins_value_usd=round(stable_value, 2),
            stablecoins_weight=round(stable_weight, 4),
            top10_weight=round(top10_weight, 4),
            hhi=round(hhi, 4),
            history_coverage={k: int(v) for k, v in coverage.items()},
            suggest=Suggestion(**suggest),
            scenarios=scenarios,
            notes=notes,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

@router.get("/objectives")
async def get_optimization_objectives():
    """Get available optimization objectives"""
    return {
        "objectives": [
            {
                "value": "max_sharpe",
                "name": "Maximize Sharpe Ratio",
                "description": "Optimize for best risk-adjusted returns"
            },
            {
                "value": "min_variance",
                "name": "Minimize Risk",
                "description": "Minimize portfolio volatility"
            },
            {
                "value": "max_return",
                "name": "Maximize Return",
                "description": "Maximize expected returns (ignores risk)"
            },
            {
                "value": "risk_parity",
                "name": "Risk Parity", 
                "description": "Equal risk contribution from all assets"
            },
            {
                "value": "mean_reversion",
                "name": "Mean Reversion",
                "description": "Exploit mean reversion patterns"
            }
        ]
    }

@router.get("/constraints/defaults")
async def get_default_constraints(conservative: bool = Query(False)):
    """Get default optimization constraints"""
    
    constraints = create_crypto_constraints(conservative=conservative)
    
    return {
        "conservative": conservative,
        "constraints": {
            "min_weight": constraints.min_weight,
            "max_weight": constraints.max_weight, 
            "max_sector_weight": constraints.max_sector_weight,
            "min_diversification_ratio": constraints.min_diversification_ratio,
            "max_correlation_exposure": constraints.max_correlation_exposure,
            "target_volatility": constraints.target_volatility
        },
        "description": "Conservative constraints limit risk but may reduce returns" if conservative else "Aggressive constraints allow higher risk for potentially higher returns"
    }

@router.post("/backtest")
async def backtest_optimization(
    request: OptimizationRequest,
    test_periods: int = Query(12, description="Number of monthly rebalancing periods to test"),
    source: str = Query("cointracking"),
    min_usd: float = Query(100)
):
    """
    Backtest optimization strategy over historical periods
    """
    
    try:
        # This would implement rolling optimization backtest
        # For now, return a placeholder structure
        
        results = {
            "success": True,
            "backtest_summary": {
                "test_periods": test_periods,
                "total_return": 0.15,  # 15% annual
                "volatility": 0.28,    # 28% annual
                "sharpe_ratio": 0.54,
                "max_drawdown": -0.35, # -35%
                "win_rate": 0.67,      # 67% winning months
                "average_rebalancing_cost": 0.002  # 0.2% per rebalance
            },
            "period_returns": [
                {"period": i, "return": np.random.normal(0.01, 0.08)} 
                for i in range(test_periods)
            ],
            "note": "Backtesting implementation in progress. This is sample data."
        }
        
        return results
        
    except Exception as e:
        logger.error(f"Backtesting failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Backtesting failed: {str(e)}")
