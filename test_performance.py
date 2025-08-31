#!/usr/bin/env python3
"""Test performance optimizations for large portfolios"""

import pandas as pd
import numpy as np
import time
from services.portfolio_optimization import PortfolioOptimizer, OptimizationConstraints, OptimizationObjective
from services.performance_optimizer import performance_optimizer

def test_performance_comparison():
    """Compare standard vs optimized performance"""
    
    print("=== Portfolio Optimization Performance Test ===")
    
    # Test different portfolio sizes
    test_sizes = [50, 100, 200, 500]
    
    for n_assets in test_sizes:
        print(f"\n[*] Testing with {n_assets} assets:")
        
        # Generate synthetic data
        np.random.seed(42)
        dates = pd.date_range('2020-01-01', periods=365, freq='D')
        assets = [f"ASSET_{i:03d}" for i in range(n_assets)]
        
        # Realistic crypto return structure
        returns = np.random.multivariate_normal(
            mean=np.zeros(n_assets) + 0.0005,  # Slight positive drift
            cov=0.001 * np.eye(n_assets) + 0.0002 * np.ones((n_assets, n_assets)),
            size=365
        )
        
        prices = pd.DataFrame(100 * np.exp(np.cumsum(returns, axis=0)), 
                             index=dates, columns=assets)
        
        # Setup optimizer
        optimizer = PortfolioOptimizer()
        constraints = OptimizationConstraints(min_weight=0.005, max_weight=0.1)
        
        # Test standard optimization
        print("   Standard optimization...", end=" ", flush=True)
        start_time = time.time()
        
        try:
            cov_matrix, _ = optimizer.calculate_risk_model(prices)
            expected_returns = optimizer.calculate_expected_returns(prices, method="historical")
            
            result_standard = optimizer.optimize_portfolio(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                constraints=constraints,
                objective=OptimizationObjective.MAX_SHARPE
            )
            
            standard_time = time.time() - start_time
            n_standard_assets = len([w for w in result_standard.weights.values() if w > 0.001])
            print(f"[OK] {standard_time:.2f}s ({n_standard_assets} assets with weights)")
            
        except Exception as e:
            standard_time = time.time() - start_time
            print(f"❌ Failed in {standard_time:.2f}s: {str(e)[:50]}")
            continue
        
        # Test optimized version for large portfolios
        if n_assets > 100:
            print("   Large portfolio optimization...", end=" ", flush=True)
            start_time = time.time()
            
            try:
                result_large = optimizer.optimize_large_portfolio(
                    price_history=prices,
                    constraints=constraints,
                    objective=OptimizationObjective.MAX_SHARPE,
                    max_assets=150  # Limit for performance
                )
                
                large_time = time.time() - start_time
                n_large_assets = len([w for w in result_large.weights.values() if w > 0.001])
                speedup = standard_time / large_time if large_time > 0 else float('inf')
                
                print(f"[OK] {large_time:.2f}s ({n_large_assets} assets, {speedup:.1f}x speedup)")
                
            except Exception as e:
                large_time = time.time() - start_time
                print(f"[FAIL] Failed in {large_time:.2f}s: {str(e)[:50]}")

def test_caching_performance():
    """Test matrix caching performance"""
    
    print("\n=== Matrix Caching Performance Test ===")
    
    # Generate test data
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=252, freq='D')
    assets = [f"CRYPTO_{i:03d}" for i in range(100)]
    
    returns_data = np.random.multivariate_normal(
        mean=np.zeros(100),
        cov=0.001 * np.eye(100) + 0.0001 * np.ones((100, 100)),
        size=252
    )
    
    returns = pd.DataFrame(returns_data, index=dates, columns=assets)
    
    print("[*] First covariance calculation (no cache)...", end=" ")
    start_time = time.time()
    cov1 = performance_optimizer.optimized_covariance_matrix(returns)
    first_time = time.time() - start_time
    print(f"{first_time:.3f}s")
    
    print("[*] Second covariance calculation (with cache)...", end=" ")
    start_time = time.time()
    cov2 = performance_optimizer.optimized_covariance_matrix(returns)
    second_time = time.time() - start_time
    print(f"{second_time:.3f}s")
    
    if second_time > 0:
        speedup = first_time / second_time
        print(f"[CACHE] Cache speedup: {speedup:.1f}x")
    
    # Check cache stats
    cache_size = len(performance_optimizer.memory_cache)
    print(f"[INFO] Memory cache entries: {cache_size}")
    
    # Verify results are identical
    if np.allclose(cov1, cov2):
        print("[OK] Cached results identical to fresh calculation")
    else:
        print("[FAIL] Cache integrity issue detected")

def test_memory_usage():
    """Test memory efficiency"""
    
    print("\n=== Memory Usage Test ===")
    
    try:
        import psutil
        process = psutil.Process()
        
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        print(f"[INFO] Initial memory usage: {initial_memory:.1f} MB")
        
        # Generate large dataset
        n_assets = 300
        dates = pd.date_range('2020-01-01', periods=500, freq='D')
        assets = [f"LARGE_{i:03d}" for i in range(n_assets)]
        
        print(f"[DATA] Generating {n_assets} assets x {len(dates)} days dataset...")
        
        np.random.seed(42)
        returns_data = np.random.multivariate_normal(
            mean=np.zeros(n_assets) * 0.0005,
            cov=0.0008 * np.eye(n_assets) + 0.0001 * np.ones((n_assets, n_assets)),
            size=len(dates)
        )
        
        prices = pd.DataFrame(100 * np.exp(np.cumsum(returns_data, axis=0)), 
                             index=dates, columns=assets)
        
        after_data_memory = process.memory_info().rss / 1024 / 1024
        print(f"[MEM] After data creation: {after_data_memory:.1f} MB (+{after_data_memory-initial_memory:.1f} MB)")
        
        # Run optimization
        optimizer = PortfolioOptimizer()
        constraints = OptimizationConstraints(min_weight=0.003, max_weight=0.05)
        
        result = optimizer.optimize_large_portfolio(
            price_history=prices,
            constraints=constraints,
            max_assets=200
        )
        
        final_memory = process.memory_info().rss / 1024 / 1024
        print(f"[OPT] After optimization: {final_memory:.1f} MB (+{final_memory-after_data_memory:.1f} MB)")
        
        n_optimized = len([w for w in result.weights.values() if w > 0.001])
        print(f"[OK] Optimized {n_optimized} assets successfully")
        
        # Clear cache and check memory
        performance_optimizer.clear_cache()
        performance_optimizer.memory_cache.clear()
        
        cleared_memory = process.memory_info().rss / 1024 / 1024
        print(f"[CLEAN] After cache clear: {cleared_memory:.1f} MB (-{final_memory-cleared_memory:.1f} MB)")
        
    except ImportError:
        print("[WARN] psutil not available - install with 'pip install psutil' for memory monitoring")

if __name__ == "__main__":
    test_performance_comparison()
    test_caching_performance()
    test_memory_usage()
    
    print("\n[DONE] Performance testing completed!")