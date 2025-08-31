"""
Multi-Asset Portfolio Management API Endpoints
Supports crypto, stocks, bonds, commodities, and REITs
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, List, Optional, Union
import logging
from datetime import datetime
import asyncio

from services.multi_asset_manager import multi_asset_manager, AssetClass, Asset, AssetAllocation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/multi-asset", tags=["Multi-Asset Portfolio"])

@router.get("/asset-classes")
async def get_asset_classes():
    """Get all supported asset classes"""
    
    return {
        "success": True,
        "asset_classes": [
            {
                "code": asset_class.value,
                "name": asset_class.name.title(),
                "description": {
                    AssetClass.CRYPTO: "Cryptocurrencies and digital assets",
                    AssetClass.STOCK: "Individual stocks and equity securities",
                    AssetClass.BOND: "Government and corporate bonds",
                    AssetClass.COMMODITY: "Physical commodities and commodity funds",
                    AssetClass.REIT: "Real Estate Investment Trusts",
                    AssetClass.FOREX: "Foreign exchange currency pairs",
                    AssetClass.ETF: "Exchange-Traded Funds"
                }[asset_class]
            }
            for asset_class in AssetClass
        ]
    }

@router.get("/assets")
async def get_assets(
    asset_class: Optional[str] = Query(None, description="Filter by asset class"),
    region: Optional[str] = Query(None, description="Filter by region"),
    sector: Optional[str] = Query(None, description="Filter by sector")
):
    """Get available assets, optionally filtered by class, region, or sector"""
    
    assets = list(multi_asset_manager.assets.values())
    
    # Apply filters
    if asset_class:
        try:
            filter_class = AssetClass(asset_class)
            assets = [a for a in assets if a.asset_class == filter_class]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid asset class: {asset_class}")
    
    if region:
        assets = [a for a in assets if a.region and a.region.lower() == region.lower()]
    
    if sector:
        assets = [a for a in assets if a.sector and sector.lower() in a.sector.lower()]
    
    # Convert to response format
    asset_data = []
    for asset in assets:
        asset_data.append({
            "symbol": asset.symbol,
            "name": asset.name,
            "asset_class": asset.asset_class.value,
            "sector": asset.sector,
            "region": asset.region,
            "currency": asset.currency,
            "market_cap": asset.market_cap,
            "expense_ratio": asset.expense_ratio,
            "yield_rate": asset.yield_rate,
            "beta": asset.beta
        })
    
    return {
        "success": True,
        "count": len(asset_data),
        "assets": asset_data,
        "filters_applied": {
            "asset_class": asset_class,
            "region": region,
            "sector": sector
        }
    }

@router.post("/assets")
async def add_asset(asset_data: dict = Body(...)):
    """Add a new asset to the universe"""
    
    try:
        # Validate required fields
        required_fields = ["symbol", "name", "asset_class"]
        for field in required_fields:
            if field not in asset_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Create asset object
        asset = Asset(
            symbol=asset_data["symbol"],
            name=asset_data["name"],
            asset_class=AssetClass(asset_data["asset_class"]),
            sector=asset_data.get("sector"),
            region=asset_data.get("region"),
            currency=asset_data.get("currency", "USD"),
            market_cap=asset_data.get("market_cap"),
            expense_ratio=asset_data.get("expense_ratio"),
            yield_rate=asset_data.get("yield_rate"),
            beta=asset_data.get("beta")
        )
        
        # Add to manager
        multi_asset_manager.add_asset(asset)
        
        return {
            "success": True,
            "message": f"Asset {asset.symbol} added successfully",
            "asset": {
                "symbol": asset.symbol,
                "name": asset.name,
                "asset_class": asset.asset_class.value,
                "sector": asset.sector,
                "region": asset.region
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid asset class: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to add asset: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add asset: {str(e)}")

@router.get("/prices")
async def get_multi_asset_prices(
    symbols: str = Query(..., description="Comma-separated list of symbols"),
    period: str = Query("1y", description="Price period (1d, 1mo, 3mo, 6mo, 1y, 2y, 5y)"),
    include_volume: bool = Query(False, description="Include volume data")
):
    """Get price data for multiple assets across different classes"""
    
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        
        # Validate symbols
        invalid_symbols = [s for s in symbol_list if s not in multi_asset_manager.assets]
        if invalid_symbols:
            logger.warning(f"Unknown symbols: {invalid_symbols}")
        
        valid_symbols = [s for s in symbol_list if s in multi_asset_manager.assets]
        if not valid_symbols:
            raise HTTPException(status_code=400, detail="No valid symbols provided")
        
        # Fetch price data
        price_data = await multi_asset_manager.fetch_prices(valid_symbols, period)
        
        # Format response
        formatted_data = {}
        for symbol, df in price_data.items():
            if df is not None and not df.empty:
                asset = multi_asset_manager.assets[symbol]
                
                prices = df['close'].dropna()
                response_data = {
                    "asset_class": asset.asset_class.value,
                    "name": asset.name,
                    "currency": asset.currency,
                    "prices": [
                        {
                            "timestamp": ts.isoformat(),
                            "price": float(price)
                        }
                        for ts, price in prices.items()
                    ]
                }
                
                if include_volume and 'volume' in df.columns:
                    volumes = df['volume'].dropna()
                    volume_data = [
                        {
                            "timestamp": ts.isoformat(),
                            "volume": float(volume)
                        }
                        for ts, volume in volumes.items()
                        if ts in prices.index
                    ]
                    response_data["volumes"] = volume_data
                
                formatted_data[symbol] = response_data
        
        return {
            "success": True,
            "period": period,
            "symbols_requested": symbol_list,
            "symbols_found": list(formatted_data.keys()),
            "symbols_missing": [s for s in symbol_list if s not in formatted_data],
            "data": formatted_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch multi-asset prices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch prices: {str(e)}")

@router.get("/correlation")
async def get_multi_asset_correlation(
    symbols: str = Query(..., description="Comma-separated list of symbols"),
    period: str = Query("1y", description="Analysis period"),
    include_class_correlation: bool = Query(True, description="Include asset class correlation analysis")
):
    """Calculate correlation matrix across multiple asset classes"""
    
    try:
        # Validate input symbols
        if not symbols.strip():
            raise HTTPException(status_code=400, detail="Symbols parameter cannot be empty")
        
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        
        # Validate symbol count
        if len(symbol_list) < 2:
            raise HTTPException(status_code=400, detail="At least 2 symbols required for correlation analysis")
        
        if len(symbol_list) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 symbols allowed for correlation analysis")
        
        # Validate period
        valid_periods = ["7d", "30d", "90d", "1y", "2y", "5y"]
        if period not in valid_periods:
            raise HTTPException(
                status_code=400, 
                detail=f"Period must be one of: {', '.join(valid_periods)}"
            )
        
        # Fetch price data
        try:
            price_data = await multi_asset_manager.fetch_prices(symbol_list, period)
        except Exception as e:
            logger.error(f"Failed to fetch price data: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to fetch price data: {str(e)}"
            )
        
        if len(price_data) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 assets for correlation analysis")
        
        # Calculate correlations
        correlation_matrix, class_correlations = multi_asset_manager.calculate_multi_asset_correlation(price_data)
        
        # Format correlation matrix
        correlation_data = {}
        for symbol1 in correlation_matrix.index:
            correlation_data[symbol1] = {}
            for symbol2 in correlation_matrix.columns:
                correlation_data[symbol1][symbol2] = float(correlation_matrix.loc[symbol1, symbol2])
        
        response = {
            "success": True,
            "period": period,
            "symbols": list(correlation_matrix.index),
            "correlation_matrix": correlation_data,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        # Add class correlation analysis if requested
        if include_class_correlation and class_correlations:
            class_corr_formatted = {}
            for class1, correlations in class_correlations.items():
                class_corr_formatted[class1.value] = {
                    class2.value: float(corr) for class2, corr in correlations.items()
                }
            response["asset_class_correlations"] = class_corr_formatted
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to calculate correlations: {e}")
        raise HTTPException(status_code=500, detail=f"Correlation analysis failed: {str(e)}")

@router.get("/performance-analysis")
async def get_performance_analysis(
    symbols: str = Query(..., description="Comma-separated list of symbols"),
    period: str = Query("1y", description="Analysis period"),
    benchmark: Optional[str] = Query("SPY", description="Benchmark symbol for comparison")
):
    """Analyze performance metrics by asset class"""
    
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        
        # Add benchmark if provided and not in list
        if benchmark and benchmark.upper() not in symbol_list:
            symbol_list.append(benchmark.upper())
        
        # Fetch price data
        price_data = await multi_asset_manager.fetch_prices(symbol_list, period)
        
        if not price_data:
            raise HTTPException(status_code=400, detail="No price data available for analysis")
        
        # Calculate period days for metrics
        period_days = multi_asset_manager._period_to_days(period)
        
        # Analyze performance by asset class
        performance_by_class = multi_asset_manager.analyze_asset_class_performance(price_data, period_days)
        
        # Individual asset analysis
        individual_analysis = {}
        for symbol, df in price_data.items():
            if symbol not in multi_asset_manager.assets or df.empty:
                continue
                
            asset = multi_asset_manager.assets[symbol]
            prices = df['close'].dropna()
            returns = prices.pct_change().dropna()
            
            if len(returns) < 30:
                continue
            
            # Calculate individual metrics
            total_return = (prices.iloc[-1] / prices.iloc[0] - 1) * 100
            volatility = returns.std() * (252 ** 0.5) * 100
            
            # Sharpe ratio
            risk_free_rate = 0.02
            excess_returns = returns.mean() * 252 - risk_free_rate
            sharpe_ratio = excess_returns / (returns.std() * (252 ** 0.5)) if returns.std() > 0 else 0
            
            # Maximum drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = abs(drawdown.min()) * 100
            
            # Beta calculation (if benchmark available)
            beta = None
            if benchmark and benchmark.upper() in price_data and benchmark.upper() != symbol:
                benchmark_df = price_data[benchmark.upper()]
                if not benchmark_df.empty:
                    benchmark_returns = benchmark_df['close'].pct_change().dropna()
                    
                    # Align returns
                    aligned_returns = returns.align(benchmark_returns, join='inner')[0]
                    aligned_benchmark = returns.align(benchmark_returns, join='inner')[1]
                    
                    if len(aligned_returns) > 30:
                        covariance = aligned_returns.cov(aligned_benchmark)
                        benchmark_variance = aligned_benchmark.var()
                        if benchmark_variance > 0:
                            beta = covariance / benchmark_variance
            
            individual_analysis[symbol] = {
                "asset_class": asset.asset_class.value,
                "name": asset.name,
                "total_return_pct": round(total_return, 2),
                "annualized_volatility_pct": round(volatility, 2),
                "sharpe_ratio": round(sharpe_ratio, 3),
                "max_drawdown_pct": round(max_drawdown, 2),
                "beta": round(beta, 3) if beta is not None else None,
                "current_price": float(prices.iloc[-1]),
                "data_points": len(prices)
            }
        
        # Format class analysis
        class_analysis_formatted = {}
        for asset_class, metrics in performance_by_class.items():
            class_analysis_formatted[asset_class.value] = {
                "average_return_pct": round(metrics["avg_return"], 2),
                "average_volatility_pct": round(metrics["avg_volatility"], 2),
                "average_sharpe_ratio": round(metrics["avg_sharpe"], 3),
                "average_max_drawdown_pct": round(metrics["avg_max_drawdown"], 2),
                "asset_count": metrics["count"],
                "symbols": metrics["symbols"]
            }
        
        return {
            "success": True,
            "analysis_period": period,
            "benchmark": benchmark,
            "individual_analysis": individual_analysis,
            "asset_class_analysis": class_analysis_formatted,
            "analysis_timestamp": datetime.now().isoformat(),
            "summary": {
                "total_assets_analyzed": len(individual_analysis),
                "asset_classes_covered": len(class_analysis_formatted),
                "period_days": period_days
            }
        }
        
    except Exception as e:
        logger.error(f"Performance analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Performance analysis failed: {str(e)}")

@router.post("/allocation/suggest")
async def suggest_allocation(
    risk_profile: str = Query("moderate", description="Risk profile: conservative, moderate, aggressive"),
    investment_horizon: str = Query("medium", description="Investment horizon: short, medium, long"),
    total_portfolio_value: float = Query(100000, description="Total portfolio value in USD"),
    exclude_asset_classes: Optional[str] = Query(None, description="Comma-separated asset classes to exclude")
):
    """Get suggested asset allocation based on risk profile and investment horizon"""
    
    try:
        # Get base allocation suggestion
        suggested_allocation = multi_asset_manager.suggest_multi_asset_allocation(
            risk_profile=risk_profile,
            investment_horizon=investment_horizon,
            total_portfolio_value=total_portfolio_value
        )
        
        # Apply exclusions if specified
        if exclude_asset_classes:
            excluded_classes = [AssetClass(cls.strip()) for cls in exclude_asset_classes.split(",")]
            
            # Remove excluded classes and redistribute
            total_excluded = sum(suggested_allocation.get(cls, 0) for cls in excluded_classes)
            for cls in excluded_classes:
                suggested_allocation.pop(cls, None)
            
            # Redistribute excluded allocation proportionally
            if total_excluded > 0 and suggested_allocation:
                remaining_total = sum(suggested_allocation.values())
                for cls in suggested_allocation:
                    suggested_allocation[cls] += (suggested_allocation[cls] / remaining_total) * total_excluded
        
        # Calculate dollar amounts
        allocation_details = {}
        for asset_class, percentage in suggested_allocation.items():
            dollar_amount = total_portfolio_value * percentage
            
            # Get available assets in this class
            class_assets = multi_asset_manager.get_assets_by_class(asset_class)
            
            allocation_details[asset_class.value] = {
                "percentage": round(percentage * 100, 2),
                "dollar_amount": round(dollar_amount, 2),
                "available_assets": len(class_assets),
                "recommended_assets": [
                    {
                        "symbol": asset.symbol,
                        "name": asset.name,
                        "sector": asset.sector
                    }
                    for asset in class_assets[:5]  # Top 5 recommendations
                ]
            }
        
        return {
            "success": True,
            "allocation_strategy": {
                "risk_profile": risk_profile,
                "investment_horizon": investment_horizon,
                "total_portfolio_value": total_portfolio_value,
                "excluded_asset_classes": exclude_asset_classes.split(",") if exclude_asset_classes else []
            },
            "suggested_allocation": allocation_details,
            "diversification_score": len(allocation_details) * 20,  # Simple score based on class count
            "rebalancing_notes": [
                f"Review allocation quarterly for {risk_profile} risk profile",
                f"Consider rebalancing when any asset class drifts >5% from target",
                f"Adjust allocation as investment horizon changes",
                "Monitor correlation changes between asset classes"
            ],
            "generated_at": datetime.now().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {str(e)}")
    except Exception as e:
        logger.error(f"Allocation suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Allocation suggestion failed: {str(e)}")

@router.get("/diversification-score")
async def calculate_diversification_score(
    symbols: str = Query(..., description="Comma-separated list of current portfolio symbols"),
    weights: Optional[str] = Query(None, description="Comma-separated weights (if not provided, assumes equal weight)")
):
    """Calculate portfolio diversification score across asset classes"""
    
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        
        # Parse weights if provided
        if weights:
            weight_list = [float(w.strip()) for w in weights.split(",")]
            if len(weight_list) != len(symbol_list):
                raise HTTPException(status_code=400, detail="Number of weights must match number of symbols")
            
            # Normalize weights
            total_weight = sum(weight_list)
            weight_list = [w / total_weight for w in weight_list]
        else:
            # Equal weights
            weight_list = [1.0 / len(symbol_list)] * len(symbol_list)
        
        # Analyze current allocation by asset class
        class_allocation = {}
        unknown_symbols = []
        
        for symbol, weight in zip(symbol_list, weight_list):
            if symbol not in multi_asset_manager.assets:
                unknown_symbols.append(symbol)
                continue
                
            asset = multi_asset_manager.assets[symbol]
            if asset.asset_class not in class_allocation:
                class_allocation[asset.asset_class] = 0
            class_allocation[asset.asset_class] += weight
        
        # Calculate diversification metrics
        total_classes = len(AssetClass)
        used_classes = len(class_allocation)
        class_coverage = used_classes / total_classes
        
        # Calculate concentration (Herfindahl-Hirschman Index)
        hhi = sum(weight ** 2 for weight in class_allocation.values())
        concentration_score = 1 - hhi  # Higher is better (less concentrated)
        
        # Calculate balance score (how evenly distributed across classes)
        if used_classes > 1:
            ideal_weight = 1.0 / used_classes
            balance_score = 1 - sum(abs(weight - ideal_weight) for weight in class_allocation.values()) / 2
        else:
            balance_score = 0
        
        # Overall diversification score (0-100)
        diversification_score = (class_coverage * 0.4 + concentration_score * 0.4 + balance_score * 0.2) * 100
        
        # Recommendations
        recommendations = []
        if diversification_score < 30:
            recommendations.append("Very low diversification - consider adding assets from different classes")
        elif diversification_score < 50:
            recommendations.append("Low diversification - expand into additional asset classes")
        elif diversification_score < 70:
            recommendations.append("Moderate diversification - consider rebalancing weights")
        else:
            recommendations.append("Good diversification across asset classes")
        
        # Missing asset classes
        missing_classes = [cls.value for cls in AssetClass if cls not in class_allocation]
        if missing_classes:
            recommendations.append(f"Consider adding exposure to: {', '.join(missing_classes)}")
        
        # Over-concentrated classes
        over_concentrated = [cls.value for cls, weight in class_allocation.items() if weight > 0.6]
        if over_concentrated:
            recommendations.append(f"Consider reducing concentration in: {', '.join(over_concentrated)}")
        
        return {
            "success": True,
            "portfolio_analysis": {
                "total_assets": len(symbol_list),
                "recognized_assets": len(symbol_list) - len(unknown_symbols),
                "unknown_symbols": unknown_symbols
            },
            "diversification_metrics": {
                "overall_score": round(diversification_score, 1),
                "class_coverage_score": round(class_coverage * 100, 1),
                "concentration_score": round(concentration_score * 100, 1),
                "balance_score": round(balance_score * 100, 1)
            },
            "asset_class_breakdown": {
                cls.value: {
                    "percentage": round(weight * 100, 2),
                    "symbols": [s for s, w in zip(symbol_list, weight_list) 
                              if s in multi_asset_manager.assets and 
                              multi_asset_manager.assets[s].asset_class == cls]
                }
                for cls, weight in class_allocation.items()
            },
            "recommendations": recommendations,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        logger.error(f"Diversification analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")