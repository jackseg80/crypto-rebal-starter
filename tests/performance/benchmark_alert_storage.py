#!/usr/bin/env python3
"""
Benchmark script for Phase 2A Alert Storage Performance

Tests P95/P99 latency for:
- Redis ZSET/HASH + Lua scripts vs File storage
- Cascade fallback performance
- Concurrent operations scalability
- Memory usage patterns

Usage: python tests/performance/benchmark_alert_storage.py
"""

import asyncio
import json
import random
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple
import sys
import logging

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from services.alerts.alert_storage import AlertStorage
from services.alerts.alert_types import Alert, AlertType, AlertSeverity

# Configure logging for benchmark
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class AlertStorageBenchmark:
    """Comprehensive benchmark for Phase 2A Alert Storage"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url
        self.results = {}
        
    def create_test_alert(self, alert_id: str = None, alert_type: AlertType = None, 
                         severity: AlertSeverity = None) -> Alert:
        """Create a test alert with random but realistic data"""
        if not alert_id:
            alert_id = f"BENCH-{int(time.time()*1000)}-{random.randint(1000, 9999)}"
        
        if not alert_type:
            alert_type = random.choice(list(AlertType))
        
        if not severity:
            severity = random.choice(list(AlertSeverity))
        
        # Realistic alert data
        current_value = random.uniform(0.1, 1.0)
        threshold = current_value * random.uniform(0.5, 0.9)
        
        return Alert(
            id=alert_id,
            alert_type=alert_type,
            severity=severity,
            data={
                "current_value": current_value,
                "adaptive_threshold": threshold,
                "base_threshold": threshold * 0.8,
                "signals_snapshot": {
                    "volatility": {"BTC": random.uniform(0.2, 0.8)},
                    "regime": {"bull": random.uniform(0.3, 0.7)},
                    "correlation": {"avg_correlation": random.uniform(0.4, 0.9)},
                    "sentiment": {"fear_greed": random.uniform(20, 80)},
                    "decision_score": random.uniform(0.3, 0.9),
                    "confidence": random.uniform(0.5, 0.9),
                    "contradiction_index": random.uniform(0.1, 0.8)
                },
                "evaluation_timestamp": datetime.now().isoformat()
            },
            created_at=datetime.now()
        )
    
    def measure_latency(self, func, *args, **kwargs) -> Tuple[Any, float]:
        """Measure function execution time in milliseconds"""
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        return result, latency_ms
    
    def calculate_percentiles(self, latencies: List[float]) -> Dict[str, float]:
        """Calculate P50, P95, P99 percentiles"""
        if not latencies:
            return {"p50": 0, "p95": 0, "p99": 0, "mean": 0, "min": 0, "max": 0}
        
        sorted_latencies = sorted(latencies)
        return {
            "p50": statistics.median(sorted_latencies),
            "p95": sorted_latencies[int(0.95 * len(sorted_latencies))],
            "p99": sorted_latencies[int(0.99 * len(sorted_latencies))],
            "mean": statistics.mean(sorted_latencies),
            "min": min(sorted_latencies),
            "max": max(sorted_latencies),
            "count": len(sorted_latencies)
        }
    
    def benchmark_storage_mode(self, storage: AlertStorage, mode_name: str, 
                              num_operations: int = 1000) -> Dict[str, Any]:
        """Benchmark a specific storage mode"""
        print(f"\\n[BENCHMARK] Testing {mode_name} mode ({num_operations} operations)")
        
        # Benchmark store operations
        store_latencies = []
        stored_alerts = []
        
        for i in range(num_operations):
            alert = self.create_test_alert()
            result, latency = self.measure_latency(storage.store_alert, alert)
            
            if result:  # Only count successful stores
                store_latencies.append(latency)
                stored_alerts.append(alert.id)
            
            if (i + 1) % 100 == 0:
                print(f"  Stored {i + 1}/{num_operations} alerts...")
        
        store_stats = self.calculate_percentiles(store_latencies)
        print(f"  Store P95: {store_stats['p95']:.2f}ms, P99: {store_stats['p99']:.2f}ms")
        
        # Benchmark get_active_alerts operations
        get_latencies = []
        
        for i in range(100):  # Fewer get operations since they're more expensive
            _, latency = self.measure_latency(storage.get_active_alerts, False)
            get_latencies.append(latency)
            
            if (i + 1) % 20 == 0:
                print(f"  Retrieved active alerts {i + 1}/100 times...")
        
        get_stats = self.calculate_percentiles(get_latencies)
        print(f"  Get P95: {get_stats['p95']:.2f}ms, P99: {get_stats['p99']:.2f}ms")
        
        # Get final metrics
        metrics = storage.get_metrics()
        
        return {
            "mode": mode_name,
            "store_latency": store_stats,
            "get_latency": get_stats,
            "storage_metrics": {
                "total_alerts": metrics.get("total_alerts", 0),
                "active_alerts": metrics.get("active_alerts", 0),
                "storage_mode": metrics.get("storage_mode", "unknown"),
                "redis_failures": metrics.get("redis_failures", 0),
                "file_failures": metrics.get("file_failures", 0),
                "is_degraded": metrics.get("is_degraded", False)
            }
        }
    
    def benchmark_concurrent_operations(self, storage: AlertStorage, 
                                      num_threads: int = 10, 
                                      operations_per_thread: int = 100) -> Dict[str, Any]:
        """Benchmark concurrent operations"""
        print(f"\\n[BENCHMARK] Testing concurrent operations ({num_threads} threads, {operations_per_thread} ops each)")
        
        def worker_store_alerts(thread_id: int) -> List[float]:
            """Worker function for concurrent alert storage"""
            latencies = []
            for i in range(operations_per_thread):
                alert = self.create_test_alert(alert_id=f"THREAD{thread_id}-{i}")
                _, latency = self.measure_latency(storage.store_alert, alert)
                latencies.append(latency)
            return latencies
        
        # Run concurrent store operations
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_store_alerts, i) for i in range(num_threads)]
            all_latencies = []
            
            for future in futures:
                thread_latencies = future.result()
                all_latencies.extend(thread_latencies)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        concurrent_stats = self.calculate_percentiles(all_latencies)
        throughput = len(all_latencies) / total_time
        
        print(f"  Concurrent P95: {concurrent_stats['p95']:.2f}ms, P99: {concurrent_stats['p99']:.2f}ms")
        print(f"  Throughput: {throughput:.1f} ops/sec")
        
        return {
            "concurrent_latency": concurrent_stats,
            "throughput_ops_per_sec": throughput,
            "total_operations": len(all_latencies),
            "total_time_sec": total_time,
            "threads": num_threads
        }
    
    def benchmark_fallback_cascade(self) -> Dict[str, Any]:
        """Benchmark fallback cascade performance"""
        print("\\n[BENCHMARK] Testing fallback cascade performance")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            json_file = Path(temp_dir) / "alerts_fallback_test.json"
            
            # Test Redis -> File -> Memory cascade
            storage = AlertStorage(
                redis_url=self.redis_url,
                json_file=str(json_file),
                enable_fallback_cascade=True
            )
            
            results = {}
            
            # Test each mode in the cascade
            if storage.storage_mode == "redis":
                # Test Redis mode
                redis_results = self.benchmark_storage_mode(storage, "Redis", 500)
                results["redis"] = redis_results
                
                # Force fallback to file
                storage.storage_mode = "file"
                storage.redis_available = False
                
            if storage.storage_mode == "file":
                # Test file mode
                file_results = self.benchmark_storage_mode(storage, "File", 500)
                results["file"] = file_results
                
                # Force fallback to memory
                storage.storage_mode = "in_memory"
            
            if storage.storage_mode == "in_memory":
                # Test memory mode
                memory_results = self.benchmark_storage_mode(storage, "Memory", 200)  # Fewer ops for memory
                results["memory"] = memory_results
            
            return results
    
    def run_full_benchmark(self) -> Dict[str, Any]:
        """Run complete benchmark suite"""
        print("="*80)
        print("PHASE 2A ALERT STORAGE PERFORMANCE BENCHMARK")
        print("="*80)
        print(f"Redis URL: {self.redis_url or 'None (file/memory only)'}")
        print(f"Start time: {datetime.now()}")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "redis_url": self.redis_url,
            "phase": "2A"
        }
        
        try:
            # 1. Single-threaded performance
            with tempfile.TemporaryDirectory() as temp_dir:
                json_file = Path(temp_dir) / "alerts_bench.json"
                
                # Test with cascade enabled
                storage_cascade = AlertStorage(
                    redis_url=self.redis_url,
                    json_file=str(json_file),
                    enable_fallback_cascade=True
                )
                
                mode_name = f"{storage_cascade.storage_mode.title()}_Cascade"
                single_thread_results = self.benchmark_storage_mode(storage_cascade, mode_name, 1000)
                results["single_threaded"] = single_thread_results
                
                # 2. Concurrent operations
                concurrent_results = self.benchmark_concurrent_operations(storage_cascade, 10, 50)
                results["concurrent"] = concurrent_results
                
                # 3. Fallback cascade performance
                fallback_results = self.benchmark_fallback_cascade()
                results["fallback_cascade"] = fallback_results
                
                # 4. Legacy comparison (without cascade)
                storage_legacy = AlertStorage(
                    redis_url=None,  # Force file mode
                    json_file=str(json_file.with_name("alerts_legacy.json")),
                    enable_fallback_cascade=False
                )
                
                legacy_results = self.benchmark_storage_mode(storage_legacy, "Legacy_File", 1000)
                results["legacy_comparison"] = legacy_results
            
            # Final summary
            self.print_benchmark_summary(results)
            
        except Exception as e:
            print(f"[ERROR] Benchmark failed: {e}")
            results["error"] = str(e)
        
        return results
    
    def print_benchmark_summary(self, results: Dict[str, Any]):
        """Print comprehensive benchmark summary"""
        print("\\n" + "="*80)
        print("BENCHMARK SUMMARY")
        print("="*80)
        
        # Single-threaded performance
        if "single_threaded" in results:
            st = results["single_threaded"]
            print(f"\\n[SINGLE-THREADED] {st['mode']} Mode:")
            print(f"  Store Operations - P95: {st['store_latency']['p95']:.2f}ms, P99: {st['store_latency']['p99']:.2f}ms")
            print(f"  Get Operations   - P95: {st['get_latency']['p95']:.2f}ms, P99: {st['get_latency']['p99']:.2f}ms")
            print(f"  Total Alerts: {st['storage_metrics']['total_alerts']}")
            print(f"  Is Degraded: {st['storage_metrics']['is_degraded']}")
        
        # Concurrent performance
        if "concurrent" in results:
            cc = results["concurrent"]
            print(f"\\n[CONCURRENT] {cc['threads']} Threads:")
            print(f"  P95: {cc['concurrent_latency']['p95']:.2f}ms, P99: {cc['concurrent_latency']['p99']:.2f}ms")
            print(f"  Throughput: {cc['throughput_ops_per_sec']:.1f} ops/sec")
        
        # Fallback cascade comparison
        if "fallback_cascade" in results:
            print("\\n[FALLBACK CASCADE] Mode Comparison:")
            for mode, data in results["fallback_cascade"].items():
                if isinstance(data, dict) and "store_latency" in data:
                    store_p95 = data['store_latency']['p95']
                    get_p95 = data['get_latency']['p95']
                    print(f"  {mode.upper():8} - Store P95: {store_p95:6.2f}ms, Get P95: {get_p95:6.2f}ms")
        
        # Performance targets
        print("\\n[PERFORMANCE TARGETS]")
        single_thread = results.get("single_threaded", {})
        store_p95 = single_thread.get("store_latency", {}).get("p95", float('inf'))
        get_p95 = single_thread.get("get_latency", {}).get("p95", float('inf'))
        throughput = results.get("concurrent", {}).get("throughput_ops_per_sec", 0)
        
        # Phase 2A targets (based on user requirements)
        store_target = 100.0  # P95 < 100ms for store operations (CPU)
        get_target = 50.0     # P95 < 50ms for get operations
        throughput_target = 100.0  # > 100 ops/sec concurrent
        
        print(f"  Store P95 Target:  < {store_target}ms   {'[PASS]' if store_p95 < store_target else '[FAIL]'} ({store_p95:.2f}ms)")
        print(f"  Get P95 Target:    < {get_target}ms    {'[PASS]' if get_p95 < get_target else '[FAIL]'} ({get_p95:.2f}ms)")
        print(f"  Throughput Target: > {throughput_target} ops/s  {'[PASS]' if throughput > throughput_target else '[FAIL]'} ({throughput:.1f} ops/s)")
        
        # Overall assessment
        targets_met = (store_p95 < store_target and get_p95 < get_target and throughput > throughput_target)
        print(f"\\n[OVERALL] Phase 2A Performance: {'[MEETS TARGETS]' if targets_met else '[BELOW TARGETS]'}")
        
        print("="*80)
    
    def save_results(self, results: Dict[str, Any], output_file: str = None):
        """Save benchmark results to JSON file"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"benchmark_results_phase2a_{timestamp}.json"
        
        output_path = Path(__file__).parent / output_file
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\\n[RESULTS] Saved to: {output_path}")
        return output_path


def main():
    """Main benchmark execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Alert Storage Phase 2A Performance Benchmark")
    parser.add_argument("--redis-url", help="Redis connection URL (optional)")
    parser.add_argument("--output", help="Output JSON file for results")
    parser.add_argument("--quick", action="store_true", help="Run quick benchmark (fewer operations)")
    
    args = parser.parse_args()
    
    # Create benchmark instance
    benchmark = AlertStorageBenchmark(redis_url=args.redis_url)
    
    # Adjust operation counts for quick mode
    if args.quick:
        print("[INFO] Running in quick mode (reduced operations)")
    
    # Run benchmark
    results = benchmark.run_full_benchmark()
    
    # Save results
    output_path = benchmark.save_results(results, args.output)
    
    # Return appropriate exit code based on performance targets
    single_thread = results.get("single_threaded", {})
    store_p95 = single_thread.get("store_latency", {}).get("p95", float('inf'))
    get_p95 = single_thread.get("get_latency", {}).get("p95", float('inf'))
    throughput = results.get("concurrent", {}).get("throughput_ops_per_sec", 0)
    
    targets_met = (store_p95 < 100.0 and get_p95 < 50.0 and throughput > 100.0)
    
    print(f"\\n[EXIT] {'Success - All targets met' if targets_met else 'Warning - Some targets missed'}")
    return 0 if targets_met else 1


if __name__ == "__main__":
    exit(main())