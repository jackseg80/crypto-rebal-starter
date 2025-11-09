"""
Performance Management API Endpoints
Cache management, optimization metrics, and system performance monitoring
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Request, Response
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional
import logging
from datetime import datetime
import time
from hashlib import sha256
import json

from api.deps import get_active_user
from services.performance_optimizer import performance_optimizer
from api.dependencies.dev_guards import require_dev_mode

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

@router.post("/cache/clear", dependencies=[Depends(require_dev_mode)])
async def clear_cache(
    older_than_days: int = Query(7, description="Clear cache files older than N days"),
    clear_memory: bool = Query(True, description="Also clear memory cache")
):
    """Clear optimization cache (DEV ONLY - disabled in production)"""
    
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

@router.get("/optimization/benchmark", dependencies=[Depends(require_dev_mode)])
async def benchmark_optimization_methods(
    n_assets: int = Query(100, description="Number of assets to benchmark"),
    n_periods: int = Query(252, description="Number of time periods"),
    seed: int = Query(42, description="Random seed for reproducibility")
):
    """Benchmark different optimization methods (DEV ONLY - heavy computation)"""
    
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

@router.post("/optimization/precompute", dependencies=[Depends(require_dev_mode)])
async def precompute_matrices(
    n_assets: int = Query(100, description="Number of top assets to precompute"),
    source: str = Query("cointracking", description="Data source")
):
    """Precompute optimization matrices (DEV ONLY - disabled in production)"""
    
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

@router.get("/summary")
async def get_performance_summary(
    request: Request,
    anchor: str = Query(default="prev_close", description="Point de référence temporel (prev_close, midnight, session)"),
    user: str = Depends(get_active_user),
    source: str = Query(default="cointracking", description="Data source")
):
    """
    P&L Summary endpoint pour performance tracking intraday

    Calcule le P&L (Profit & Loss) depuis un point d'ancrage temporel.
    Intègre avec les snapshots portfolio pour calculs réels.

    Supporte ETag et If-None-Match pour optimisation cache HTTP.

    Anchor points supportés:
    - "prev_close": Début du jour actuel (midnight pour crypto 24/7)
    - "midnight": Début du jour actuel à 00:00 (même comportement)
    - "session": Dernier snapshot disponible (alias pour prev_snapshot)
    """
    try:
        from api.unified_data import get_unified_filtered_balances
        from services.portfolio import portfolio_analytics

        # Récupérer les données actuelles du portfolio
        balances = await get_unified_filtered_balances(
            source=source,
            user_id=user
        )

        # Calculer métriques actuelles
        if isinstance(balances, dict):
            current_metrics = portfolio_analytics.calculate_portfolio_metrics(balances)
        else:
            # Fallback si balances est déjà une liste
            current_metrics = portfolio_analytics.calculate_portfolio_metrics({"items": balances})

        current_value_usd = current_metrics.get("total_value_usd", 0.0)

        # Mapper l'anchor vers la convention du service portfolio
        # prev_close/midnight → midnight, session → prev_snapshot
        portfolio_anchor = "midnight" if anchor in ["prev_close", "midnight"] else "prev_snapshot"

        # Calculer la performance vs anchor point
        perf_metrics = portfolio_analytics.calculate_performance_metrics(
            current_data=current_metrics,
            user_id=user,
            source=source,
            anchor=portfolio_anchor,
            window="24h"
        )

        # Extraire les valeurs de P&L (avec fallback si pas de données historiques)
        if perf_metrics.get("performance_available", False):
            absolute_change_usd = perf_metrics.get("absolute_change_usd", 0.0)
            percent_change = perf_metrics.get("percentage_change", 0.0)
            comparison_info = perf_metrics.get("comparison", {})
            base_snapshot_at = comparison_info.get("base_snapshot_at")
        else:
            # Pas de données historiques → P&L à 0
            absolute_change_usd = 0.0
            percent_change = 0.0
            base_snapshot_at = None
            logger.warning(f"No historical data for P&L calculation (user={user}, source={source}, anchor={anchor})")

        # Structure de réponse compatible avec les tests
        response_data = {
            "ok": True,
            "performance": {
                "as_of": datetime.now().isoformat(),
                "anchor": anchor,
                "base_snapshot_at": base_snapshot_at,
                "total": {
                    "current_value_usd": round(current_value_usd, 2),
                    "absolute_change_usd": round(absolute_change_usd, 2),
                    "percent_change": round(percent_change, 4)
                },
                "by_account": {
                    "main": {
                        "current_value_usd": round(current_value_usd, 2),
                        "absolute_change_usd": round(absolute_change_usd, 2),
                        "percent_change": round(percent_change, 4)
                    }
                },
                "by_source": {
                    source: {
                        "current_value_usd": round(current_value_usd, 2),
                        "absolute_change_usd": round(absolute_change_usd, 2),
                        "percent_change": round(percent_change, 4)
                    }
                }
            }
        }

        # Générer ETag basé sur le contenu (exclure timestamp pour stabilité cache)
        # Le timestamp change à chaque appel mais les données peuvent être identiques
        etag_data = {
            "total": response_data["performance"]["total"],
            "by_account": response_data["performance"]["by_account"],
            "by_source": response_data["performance"]["by_source"],
            "anchor": response_data["performance"]["anchor"]
        }
        content_str = json.dumps(etag_data, sort_keys=True)
        etag = f'"{sha256(content_str.encode()).hexdigest()}"'

        # Vérifier If-None-Match header pour cache validation
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match == etag:
            # Le client a la version à jour, retourner 304 Not Modified
            return Response(status_code=304, headers={"etag": etag})

        # Retourner une Response avec headers ETag
        return JSONResponse(
            content=response_data,
            headers={
                "etag": etag,
                "cache-control": "private, max-age=60"  # Cache 60s pour perfs
            }
        )

    except Exception as e:
        logger.error(f"Error calculating performance summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Performance summary failed: {str(e)}")