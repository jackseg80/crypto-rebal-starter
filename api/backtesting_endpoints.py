"""
Backtesting API Endpoints
Advanced portfolio strategy backtesting with comprehensive metrics
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Dict, List, Optional, Union
import pandas as pd
from pydantic import BaseModel
import logging
from datetime import datetime, timedelta

from services.backtesting_engine import (
    backtesting_engine, BacktestConfig, TransactionCosts, 
    RebalanceFrequency, BacktestResult
)
from services.price_history import get_cached_history
from connectors.cointracking_api import get_current_balances

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/backtesting", tags=["Backtesting"])

class BacktestRequest(BaseModel):
    """Request model for backtesting"""
    strategy: str
    assets: Optional[List[str]] = None
    start_date: str
    end_date: str
    initial_capital: float = 10000.0
    rebalance_frequency: str = "monthly"
    benchmark: str = "BTC"
    
    # Transaction costs
    maker_fee: float = 0.001
    taker_fee: float = 0.0015
    slippage_bps: float = 5.0
    min_trade_size: float = 10.0
    
    # Risk constraints
    max_position_size: float = 0.5
    risk_free_rate: float = 0.02

class StrategyComparisonRequest(BaseModel):
    """Request for strategy comparison"""
    strategies: List[str]
    assets: Optional[List[str]] = None
    start_date: str
    end_date: str
    initial_capital: float = 10000.0
    rebalance_frequency: str = "monthly"

class BacktestResponse(BaseModel):
    """Response model for backtesting results"""
    success: bool
    strategy_name: str
    summary: Dict
    metrics: Dict[str, float]
    risk_metrics: Dict[str, float]
    monthly_returns: List[Dict]
    attribution: Dict
    benchmark_comparison: Dict
    
@router.get("/strategies")
async def get_available_strategies():
    """Get list of available backtesting strategies"""
    
    strategies = []
    for name, strategy in backtesting_engine.strategies.items():
        strategies.append({
            "key": name,
            "name": strategy.name,
            "description": f"Strategy: {strategy.name}"
        })
    
    return {
        "strategies": strategies,
        "total_count": len(strategies),
        "rebalance_frequencies": [freq.value for freq in RebalanceFrequency]
    }

@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    source: str = Query("cointracking", description="Data source for current portfolio")
):
    """
    Run comprehensive backtest for a single strategy
    """
    
    try:
        # Validate strategy
        if request.strategy not in backtesting_engine.strategies:
            available = list(backtesting_engine.strategies.keys())
            raise HTTPException(
                status_code=400, 
                detail=f"Unknown strategy: {request.strategy}. Available: {available}"
            )
        
        # Get assets to backtest
        assets = request.assets
        if not assets:
            # Get from current portfolio
            balances_response = await get_current_balances(source=source)
            if balances_response.get("items"):
                # Filter by minimum value and take top assets
                filtered_items = [item for item in balances_response["items"] if item["value_usd"] >= 100]
                assets = [item["symbol"] for item in filtered_items[:10]]
            else:
                assets = ["BTC", "ETH", "SOL", "ADA", "DOT"]  # Fallback
        
        # Collect price data
        logger.info(f"Collecting price data for {len(assets)} assets")
        price_data = {}
        
        start_date = pd.to_datetime(request.start_date)
        end_date = pd.to_datetime(request.end_date)
        days_needed = (end_date - start_date).days + 100  # Extra buffer for indicators
        
        for asset in assets:
            try:
                prices = get_cached_history(asset, days=days_needed)
                if prices and len(prices) > 30:
                    price_data[asset] = prices
                else:
                    logger.warning(f"Insufficient data for {asset}")
            except Exception as e:
                logger.warning(f"Failed to get price data for {asset}: {e}")
                continue
        
        if len(price_data) < 2:
            raise HTTPException(
                status_code=400,
                detail="Insufficient price data. Need at least 2 assets with historical data."
            )
        
        # Convert price data to DataFrame format
        df_data = {}
        for asset, prices in price_data.items():
            # Convert list of (timestamp, price) tuples to Series
            if prices and len(prices) > 0:
                timestamps = [pd.to_datetime(p[0], unit='s') for p in prices]
                values = [p[1] for p in prices]
                df_data[asset] = pd.Series(values, index=timestamps)
        
        # Create price DataFrame
        price_df = pd.DataFrame(df_data).fillna(method='ffill').dropna()
        
        # Ensure we have enough data for the backtest period
        if price_df.index[0] > start_date:
            start_date = price_df.index[0]
            logger.warning(f"Adjusted start date to {start_date} due to data availability")
        
        if price_df.index[-1] < end_date:
            end_date = price_df.index[-1]
            logger.warning(f"Adjusted end date to {end_date} due to data availability")
        
        # Create backtest configuration
        try:
            rebal_freq = RebalanceFrequency(request.rebalance_frequency)
        except ValueError:
            rebal_freq = RebalanceFrequency.MONTHLY
            logger.warning(f"Invalid frequency {request.rebalance_frequency}, using monthly")
        
        transaction_costs = TransactionCosts(
            maker_fee=request.maker_fee,
            taker_fee=request.taker_fee,
            slippage_bps=request.slippage_bps,
            min_trade_size=request.min_trade_size
        )
        
        config = BacktestConfig(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            initial_capital=request.initial_capital,
            rebalance_frequency=rebal_freq,
            transaction_costs=transaction_costs,
            benchmark=request.benchmark,
            risk_free_rate=request.risk_free_rate,
            max_position_size=request.max_position_size
        )
        
        # Run backtest
        logger.info(f"Running backtest: {request.strategy} from {start_date} to {end_date}")
        result = backtesting_engine.run_backtest(price_df, request.strategy, config)
        
        # Prepare response
        monthly_returns_list = []
        for date, ret in result.monthly_returns.items():
            monthly_returns_list.append({
                "date": date.strftime('%Y-%m'),
                "return": float(ret),
                "return_pct": float(ret * 100)
            })
        
        # Benchmark comparison
        benchmark_comparison = {}
        if len(result.benchmark_performance) > 0:
            benchmark_total_return = (result.benchmark_performance.iloc[-1] / request.initial_capital) - 1
            portfolio_total_return = result.metrics.get('total_return', 0)
            
            benchmark_comparison = {
                "benchmark_asset": request.benchmark,
                "benchmark_total_return": float(benchmark_total_return),
                "benchmark_return_pct": float(benchmark_total_return * 100),
                "portfolio_total_return": float(portfolio_total_return),
                "portfolio_return_pct": float(portfolio_total_return * 100),
                "excess_return": float(portfolio_total_return - benchmark_total_return),
                "excess_return_pct": float((portfolio_total_return - benchmark_total_return) * 100)
            }
        
        return BacktestResponse(
            success=True,
            strategy_name=result.summary['strategy_name'],
            summary=result.summary,
            metrics={k: float(v) for k, v in result.metrics.items()},
            risk_metrics={k: float(v) for k, v in result.risk_metrics.items()},
            monthly_returns=monthly_returns_list,
            attribution=result.attribution,
            benchmark_comparison=benchmark_comparison
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")

@router.post("/compare")
async def compare_strategies(
    request: StrategyComparisonRequest,
    source: str = Query("cointracking")
):
    """
    Compare multiple strategies side-by-side
    """
    
    try:
        # Validate strategies
        invalid_strategies = [s for s in request.strategies if s not in backtesting_engine.strategies]
        if invalid_strategies:
            available = list(backtesting_engine.strategies.keys())
            raise HTTPException(
                status_code=400,
                detail=f"Unknown strategies: {invalid_strategies}. Available: {available}"
            )
        
        # Get assets
        assets = request.assets
        if not assets:
            balances_response = await get_current_balances(source=source)
            if balances_response.get("items"):
                # Filter by minimum value and take top assets
                filtered_items = [item for item in balances_response["items"] if item["value_usd"] >= 100]
                assets = [item["symbol"] for item in filtered_items[:8]]
            else:
                assets = ["BTC", "ETH", "SOL", "ADA"]
        
        # Collect price data
        price_data = {}
        start_date = pd.to_datetime(request.start_date)
        end_date = pd.to_datetime(request.end_date)
        days_needed = (end_date - start_date).days + 100
        
        for asset in assets:
            try:
                prices = get_cached_history(asset, days=days_needed)
                if prices and len(prices) > 30:
                    price_data[asset] = prices
            except Exception as e:
                logger.warning(f"Failed to get price data for {asset}: {e}")
                continue
        
        if len(price_data) < 2:
            raise HTTPException(status_code=400, detail="Insufficient price data")
        
        price_df = pd.DataFrame(price_data).fillna(method='ffill').dropna()
        
        # Create configuration
        try:
            rebal_freq = RebalanceFrequency(request.rebalance_frequency)
        except ValueError:
            rebal_freq = RebalanceFrequency.MONTHLY
        
        config = BacktestConfig(
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            rebalance_frequency=rebal_freq
        )
        
        # Run comparison
        logger.info(f"Comparing {len(request.strategies)} strategies")
        comparison_df = backtesting_engine.compare_strategies(
            price_df, request.strategies, config
        )
        
        if comparison_df.empty:
            raise HTTPException(status_code=500, detail="Strategy comparison failed")
        
        # Format results
        results = {}
        for strategy in comparison_df.index:
            strategy_data = comparison_df.loc[strategy].to_dict()
            
            # Convert numpy types to native Python types
            formatted_data = {}
            for key, value in strategy_data.items():
                try:
                    formatted_data[key] = float(value) if pd.notna(value) else None
                except (TypeError, ValueError):
                    formatted_data[key] = str(value)
            
            results[strategy] = formatted_data
        
        # Overall comparison summary
        summary = {
            "strategies_compared": len(request.strategies),
            "backtest_period": f"{request.start_date} to {request.end_date}",
            "best_return": comparison_df['annualized_return'].idxmax() if 'annualized_return' in comparison_df else None,
            "best_sharpe": comparison_df['sharpe_ratio'].idxmax() if 'sharpe_ratio' in comparison_df else None,
            "lowest_drawdown": comparison_df['max_drawdown'].idxmax() if 'max_drawdown' in comparison_df else None,  # Least negative
            "metrics_included": list(comparison_df.columns)
        }
        
        return {
            "success": True,
            "summary": summary,
            "comparison_results": results,
            "rankings": {
                "by_return": comparison_df.sort_values('annualized_return', ascending=False).index.tolist() if 'annualized_return' in comparison_df else [],
                "by_sharpe": comparison_df.sort_values('sharpe_ratio', ascending=False).index.tolist() if 'sharpe_ratio' in comparison_df else [],
                "by_calmar": comparison_df.sort_values('calmar_ratio', ascending=False).index.tolist() if 'calmar_ratio' in comparison_df else []
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Strategy comparison failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")

@router.get("/metrics/definitions")
async def get_metrics_definitions():
    """
    Get definitions of all backtesting metrics
    """
    
    return {
        "performance_metrics": {
            "total_return": {
                "name": "Total Return",
                "description": "Total portfolio return over the entire period",
                "unit": "decimal (0.15 = 15%)",
                "interpretation": "Higher is better"
            },
            "annualized_return": {
                "name": "Annualized Return", 
                "description": "Average annual return over the period",
                "unit": "decimal",
                "interpretation": "Higher is better, compare to benchmarks"
            },
            "volatility": {
                "name": "Volatility",
                "description": "Annualized standard deviation of daily returns",
                "unit": "decimal",
                "interpretation": "Lower is generally better (less risk)"
            },
            "sharpe_ratio": {
                "name": "Sharpe Ratio",
                "description": "Risk-adjusted return (excess return / volatility)",
                "unit": "ratio",
                "interpretation": "> 1 is good, > 1.5 is very good, > 2 is excellent"
            },
            "max_drawdown": {
                "name": "Maximum Drawdown",
                "description": "Largest peak-to-trough decline",
                "unit": "decimal (negative)",
                "interpretation": "Smaller magnitude is better (-0.2 better than -0.4)"
            },
            "calmar_ratio": {
                "name": "Calmar Ratio",
                "description": "Annualized return / abs(max drawdown)",
                "unit": "ratio",
                "interpretation": "Higher is better, > 1 is good"
            },
            "sortino_ratio": {
                "name": "Sortino Ratio",
                "description": "Like Sharpe but only considers downside volatility",
                "unit": "ratio", 
                "interpretation": "Higher is better, focuses on harmful volatility"
            },
            "win_rate": {
                "name": "Win Rate",
                "description": "Percentage of positive return days",
                "unit": "decimal (0.6 = 60%)",
                "interpretation": "Higher is generally better"
            }
        },
        "risk_metrics": {
            "var_95": {
                "name": "Value at Risk (95%)",
                "description": "Expected loss on worst 5% of days",
                "unit": "decimal (negative)",
                "interpretation": "Less negative is better"
            },
            "cvar_95": {
                "name": "Conditional VaR (95%)",
                "description": "Expected loss when VaR threshold is exceeded",
                "unit": "decimal (negative)",
                "interpretation": "Less negative is better"
            },
            "beta": {
                "name": "Beta vs Benchmark",
                "description": "Sensitivity to benchmark movements",
                "unit": "ratio",
                "interpretation": "1 = same volatility as benchmark, >1 = higher"
            },
            "tracking_error": {
                "name": "Tracking Error",
                "description": "Standard deviation of excess returns vs benchmark",
                "unit": "decimal",
                "interpretation": "Lower means closer to benchmark performance"
            }
        },
        "strategy_types": {
            "equal_weight": "Equal allocation to all assets, rebalanced periodically",
            "market_cap": "Weight by market cap (price proxy)",
            "momentum_90d": "Weight by 90-day momentum (recent winners get higher weight)",
            "momentum_30d": "Weight by 30-day momentum",
            "mean_reversion": "Higher weight to recent underperformers",
            "risk_parity": "Weight inversely to volatility (equal risk contribution)"
        }
    }

@router.get("/performance/charts/{strategy}")
async def get_performance_charts(
    strategy: str,
    assets: Optional[str] = Query(None, description="Comma-separated asset list"),
    start_date: str = Query(...),
    end_date: str = Query(...),
    source: str = Query("cointracking")
):
    """
    Get chart data for a specific strategy backtest
    """
    
    try:
        # Parse assets
        asset_list = assets.split(',') if assets else None
        
        # Run quick backtest for chart data
        backtest_request = BacktestRequest(
            strategy=strategy,
            assets=asset_list,
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000.0
        )
        
        # This would normally call the full backtest, but for charts we might want optimized version
        # For now, return placeholder structure
        
        return {
            "success": True,
            "strategy": strategy,
            "chart_data": {
                "performance": {
                    "dates": ["2023-01-01", "2023-02-01", "2023-03-01"],
                    "portfolio_values": [10000, 10500, 11200],
                    "benchmark_values": [10000, 10300, 10800]
                },
                "drawdown": {
                    "dates": ["2023-01-01", "2023-02-01", "2023-03-01"],
                    "drawdown_pct": [0, -2.5, -1.2]
                },
                "monthly_returns": {
                    "months": ["2023-01", "2023-02", "2023-03"],
                    "returns_pct": [5.0, 6.7, -1.8]
                }
            },
            "note": "Chart data endpoint - full implementation pending"
        }
        
    except Exception as e:
        logger.error(f"Chart data generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))