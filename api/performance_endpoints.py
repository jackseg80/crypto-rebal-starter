"""
Performance Management API Endpoints
Cache management, optimization metrics, and system performance monitoring
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
import logging
from datetime import datetime
import time

from services.performance_optimizer import performance_optimizer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/performance", tags=["Performance"])

@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics and memory usage"""
    
    cache_stats = {
        "memory_cache_size": len(performance_optimizer.memory_cache),
        "max_cache_size": performance_optimizer.max_cache_size,
        "cache_directory": str(performance_optimizer.cache_dir),
        "timestamp": datetime.now().isoformat()
    }
    
    # Count disk cache files
    try:
        disk_files = list(performance_optimizer.cache_dir.glob("*.json"))
        cache_stats["disk_cache_files"] = len(disk_files)
        
        # Calculate total disk usage
        total_size = sum(f.stat().st_size for f in disk_files)
        cache_stats["disk_cache_size_mb"] = round(total_size / (1024 * 1024), 2)
        
    except Exception as e:
        logger.warning(f"Could not calculate disk cache stats: {e}")
        cache_stats["disk_cache_files"] = "unknown"
        cache_stats["disk_cache_size_mb"] = "unknown"
    
    return {
        "success": True,
        "cache_stats": cache_stats
    }

@router.post("/cache/clear")
async def clear_cache(
    older_than_days: int = Query(7, description="Clear cache files older than N days"),
    clear_memory: bool = Query(True, description="Also clear memory cache")
):
    """Clear optimization cache"""
    
    try:
        performance_optimizer.clear_cache(older_than_days=older_than_days)
        
        if clear_memory:
            performance_optimizer.memory_cache.clear()
        
        return {
            "success": True,
            "message": f"Cache cleared successfully (older than {older_than_days} days)",
            "memory_cache_cleared": clear_memory
        }
        
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@router.get("/optimization/benchmark")
async def benchmark_optimization_methods(
    n_assets: int = Query(100, description="Number of assets to benchmark"),
    n_periods: int = Query(252, description="Number of time periods"),
    seed: int = Query(42, description="Random seed for reproducibility")
):
    """Benchmark different optimization methods for performance comparison"""
    
    if n_assets > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 assets for benchmarking")
    
    import numpy as np
    import pandas as pd
    from services.portfolio_optimization import PortfolioOptimizer, OptimizationConstraints
    
    # Generate synthetic data
    np.random.seed(seed)
    dates = pd.date_range('2020-01-01', periods=n_periods, freq='D')
    assets = [f"ASSET_{i:03d}" for i in range(n_assets)]
    
    # Synthetic price data with realistic correlations
    returns = np.random.multivariate_normal(
        mean=np.zeros(n_assets),
        cov=0.0004 * np.eye(n_assets) + 0.0001 * np.ones((n_assets, n_assets)),
        size=n_periods
    )
    
    prices = pd.DataFrame(100 * np.exp(np.cumsum(returns, axis=0)), 
                         index=dates, columns=assets)
    
    # Benchmark different methods
    optimizer = PortfolioOptimizer()
    constraints = OptimizationConstraints(min_weight=0.001, max_weight=0.1)
    
    results = {}
    
    # Standard optimization
    start_time = time.time()
    try:
        cov_matrix, _ = optimizer.calculate_risk_model(prices)
        expected_returns = optimizer.calculate_expected_returns(prices, method="historical")
        
        result_standard = optimizer.optimize_portfolio(
            expected_returns=expected_returns,
            cov_matrix=cov_matrix,
            constraints=constraints
        )
        
        standard_time = time.time() - start_time
        results["standard"] = {
            "duration_seconds": round(standard_time, 3),
            "success": True,
            "n_assets_optimized": len([w for w in result_standard.weights.values() if w > 0.001]),
            "sharpe_ratio": round(result_standard.sharpe_ratio, 3)
        }
    except Exception as e:
        results["standard"] = {
            "duration_seconds": time.time() - start_time,
            "success": False,
            "error": str(e)
        }
    
    # Large portfolio optimization (if applicable)
    if n_assets > 200:
        start_time = time.time()
        try:
            result_large = optimizer.optimize_large_portfolio(
                price_history=prices,
                constraints=constraints,
                max_assets=200
            )
            
            large_time = time.time() - start_time
            results["large_portfolio"] = {
                "duration_seconds": round(large_time, 3),
                "success": True,
                "n_assets_optimized": len([w for w in result_large.weights.values() if w > 0.001]),
                "sharpe_ratio": round(result_large.sharpe_ratio, 3),
                "assets_filtered": n_assets - 200
            }
        except Exception as e:
            results["large_portfolio"] = {
                "duration_seconds": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
    
    # Performance comparison
    performance_summary = {
        "n_assets": n_assets,
        "n_periods": n_periods,
        "benchmark_timestamp": datetime.now().isoformat(),
        "methods_tested": list(results.keys()),
        "recommendation": "standard" if n_assets <= 200 else "large_portfolio"
    }
    
    # Speed comparison
    if len(results) > 1:
        times = [r["duration_seconds"] for r in results.values() if r["success"]]
        if times:
            performance_summary["fastest_method"] = min(results.keys(), 
                key=lambda k: results[k]["duration_seconds"] if results[k]["success"] else float('inf'))
            performance_summary["speed_improvement"] = f"{max(times) / min(times):.1f}x" if len(times) > 1 else "N/A"
    
    return {
        "success": True,
        "benchmark_results": results,
        "performance_summary": performance_summary
    }

@router.get("/system/memory")
async def get_memory_usage():
    """Get current system memory usage"""
    
    try:
        import psutil
        process = psutil.Process()
        
        memory_info = {
            "rss_mb": round(process.memory_info().rss / 1024 / 1024, 2),
            "vms_mb": round(process.memory_info().vms / 1024 / 1024, 2),
            "percent": round(process.memory_percent(), 2),
            "available_system_mb": round(psutil.virtual_memory().available / 1024 / 1024, 2),
            "total_system_mb": round(psutil.virtual_memory().total / 1024 / 1024, 2)
        }
        
        return {
            "success": True,
            "memory_usage": memory_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "psutil not available - install with 'pip install psutil' for memory monitoring"
        }
    except Exception as e:
        logger.error(f"Memory usage check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Memory check failed: {str(e)}")

@router.post("/optimization/precompute")
async def precompute_matrices(
    n_assets: int = Query(100, description="Number of top assets to precompute"),
    source: str = Query("cointracking", description="Data source")
):
    """Precompute optimization matrices for faster subsequent optimizations"""
    
    try:
        from connectors.cointracking_api import get_current_balances
        from services.price_history import get_cached_history
        
        # Get current portfolio
        balances_response = await get_current_balances(source=source)
        if not balances_response.get("items"):
            raise HTTPException(status_code=400, detail="No portfolio data found")
        
        # Get top N assets by value
        sorted_items = sorted(balances_response["items"], 
                            key=lambda x: x["value_usd"], reverse=True)
        top_assets = [item["symbol"] for item in sorted_items[:n_assets]]
        
        logger.info(f"Precomputing matrices for top {len(top_assets)} assets")
        
        # Collect price data
        price_data = {}
        for asset in top_assets:
            try:
                prices = get_cached_history(asset, days=400)
                if prices and len(prices) > 100:
                    price_data[asset] = prices
            except Exception as e:
                logger.warning(f"Failed to get price data for {asset}: {e}")
        
        if len(price_data) < 10:
            raise HTTPException(status_code=400, detail="Insufficient price data for precomputation")
        
        # Create price DataFrame and precompute
        import pandas as pd
        df_data = {}
        for asset, prices in price_data.items():
            timestamps = [pd.to_datetime(p[0], unit='s') for p in prices]
            values = [p[1] for p in prices]
            df_data[asset] = pd.Series(values, index=timestamps)
        
        price_df = pd.DataFrame(df_data).fillna(method='ffill').dropna()
        
        # Trigger matrix precomputation
        preprocessed = performance_optimizer.batch_optimization_preprocessing(
            price_df, max_assets=n_assets
        )
        
        return {
            "success": True,
            "message": f"Precomputed optimization matrices for {len(preprocessed['assets'])} assets",
            "assets_processed": len(preprocessed['assets']),
            "cache_entries_created": len(performance_optimizer.memory_cache),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Matrix precomputation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Precomputation failed: {str(e)}")