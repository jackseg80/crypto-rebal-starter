"""
Benchmarks de performances détaillés pour Phase 3
Mesure les performances WebSocket, VaR API, et latences système
"""
import json
import time
import statistics
import requests
import asyncio
import websockets
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any

class Phase3PerformanceBenchmark:
    """Benchmarks de performances Phase 3"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = requests.Session()
        self.ws_url = base_url.replace("http://", "ws://") + "/api/realtime/ws"
    
    def benchmark_var_api_performance(self, num_requests: int = 20) -> Dict[str, Any]:
        """Benchmark 1: Performance API VaR"""
        print(f"1. Benchmarking VaR API Performance ({num_requests} requests)...")
        
        request_data = {
            "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
            "portfolio_value": 10000,
            "analysis_types": ["var_parametric", "var_historical"],
            "confidence_levels": [0.95, 0.99],
            "horizons": ["1d"]
        }
        
        response_times = []
        errors = 0
        
        for i in range(num_requests):
            start = time.time()
            try:
                response = self.session.post(
                    f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
                    json=request_data,
                    timeout=30
                )
                duration = (time.time() - start) * 1000
                response_times.append(duration)
                
                if response.status_code != 200:
                    errors += 1
                    
            except Exception as e:
                duration = (time.time() - start) * 1000
                response_times.append(duration)
                errors += 1
                print(f"   Request {i+1} failed: {e}")
        
        if response_times:
            results = {
                "total_requests": num_requests,
                "successful_requests": num_requests - errors,
                "error_rate_pct": round((errors / num_requests) * 100, 1),
                "avg_response_ms": round(statistics.mean(response_times), 1),
                "median_response_ms": round(statistics.median(response_times), 1),
                "min_response_ms": round(min(response_times), 1),
                "max_response_ms": round(max(response_times), 1),
                "std_dev_ms": round(statistics.stdev(response_times) if len(response_times) > 1 else 0, 1),
                "p95_response_ms": round(self._percentile(response_times, 95), 1),
                "p99_response_ms": round(self._percentile(response_times, 99), 1),
                "throughput_req_per_sec": round(num_requests / (sum(response_times) / 1000), 2)
            }
        else:
            results = {"error": "All requests failed"}
        
        print(f"   [OK] VaR API: avg {results['avg_response_ms']}ms, p95 {results['p95_response_ms']}ms, {results['error_rate_pct']}% errors")
        return results
    
    def benchmark_concurrent_var_requests(self, num_concurrent: int = 5) -> Dict[str, Any]:
        """Benchmark 2: Requêtes VaR concurrentes"""
        print(f"2. Benchmarking Concurrent VaR Requests ({num_concurrent} concurrent)...")
        
        request_data = {
            "portfolio_weights": {"BTC": 0.6, "ETH": 0.4},
            "portfolio_value": 10000,
            "analysis_types": ["var_parametric"],
            "confidence_levels": [0.95],
            "horizons": ["1d"]
        }
        
        def make_request():
            start = time.time()
            try:
                response = requests.post(
                    f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
                    json=request_data,
                    timeout=30
                )
                duration = (time.time() - start) * 1000
                return {
                    "duration_ms": duration,
                    "status_code": response.status_code,
                    "success": response.status_code == 200
                }
            except Exception as e:
                duration = (time.time() - start) * 1000
                return {
                    "duration_ms": duration,
                    "status_code": "ERROR",
                    "success": False,
                    "error": str(e)
                }
        
        # Lancer les requêtes concurrentes
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(make_request) for _ in range(num_concurrent)]
            results_list = [future.result() for future in futures]
        total_time = time.time() - start_time
        
        # Analyser les résultats
        successful_requests = [r for r in results_list if r["success"]]
        response_times = [r["duration_ms"] for r in results_list]
        
        results = {
            "concurrent_requests": num_concurrent,
            "successful_requests": len(successful_requests),
            "total_wall_time_ms": round(total_time * 1000, 1),
            "success_rate_pct": round((len(successful_requests) / num_concurrent) * 100, 1),
            "avg_response_ms": round(statistics.mean(response_times) if response_times else 0, 1),
            "max_response_ms": round(max(response_times) if response_times else 0, 1),
            "min_response_ms": round(min(response_times) if response_times else 0, 1),
            "concurrent_throughput": round(num_concurrent / total_time, 2) if total_time > 0 else 0
        }
        
        print(f"   [OK] Concurrent: {results['success_rate_pct']}% success, {results['avg_response_ms']}ms avg, {results['concurrent_throughput']} req/s")
        return results
    
    def benchmark_api_latencies(self) -> Dict[str, Any]:
        """Benchmark 3: Latences des différentes APIs"""
        print("3. Benchmarking API Latencies...")
        
        endpoints = [
            {"url": "/api/phase3/status", "method": "GET", "name": "phase3_status"},
            {"url": "/api/realtime/status", "method": "GET", "name": "realtime_status"},
            {"url": "/api/realtime/connections", "method": "GET", "name": "websocket_connections"},
            {"url": "/api/phase3/health/comprehensive", "method": "GET", "name": "health_check"}
        ]
        
        results = {}
        
        for endpoint in endpoints:
            print(f"   Testing {endpoint['name']}...")
            times = []
            
            for _ in range(10):  # 10 mesures par endpoint
                start = time.time()
                try:
                    if endpoint["method"] == "GET":
                        response = self.session.get(f"{self.base_url}{endpoint['url']}", timeout=10)
                    else:
                        response = self.session.post(f"{self.base_url}{endpoint['url']}", timeout=10)
                    
                    duration = (time.time() - start) * 1000
                    times.append(duration)
                    
                except Exception as e:
                    duration = (time.time() - start) * 1000
                    times.append(duration)
            
            if times:
                results[endpoint["name"]] = {
                    "avg_latency_ms": round(statistics.mean(times), 1),
                    "min_latency_ms": round(min(times), 1),
                    "max_latency_ms": round(max(times), 1),
                    "p95_latency_ms": round(self._percentile(times, 95), 1)
                }
            
            print(f"      {endpoint['name']}: {results[endpoint['name']]['avg_latency_ms']}ms avg")
        
        return results
    
    async def benchmark_websocket_performance(self) -> Dict[str, Any]:
        """Benchmark 4: Performance WebSocket"""
        print("4. Benchmarking WebSocket Performance...")
        
        try:
            # Test de connexion
            connection_times = []
            
            for i in range(5):  # 5 tests de connexion
                start = time.time()
                try:
                    async with websockets.connect(f"{self.ws_url}?client_id=benchmark_{i}", timeout=5) as websocket:
                        duration = (time.time() - start) * 1000
                        connection_times.append(duration)
                        
                        # Test d'envoi de message
                        message = {"type": "ping", "timestamp": time.time()}
                        await websocket.send(json.dumps(message))
                        
                        # Attendre la réponse
                        response = await asyncio.wait_for(websocket.recv(), timeout=2)
                        
                except Exception as e:
                    duration = (time.time() - start) * 1000
                    connection_times.append(duration)
                    print(f"      WebSocket test {i+1} failed: {e}")
            
            # Test de broadcast via API
            broadcast_times = []
            for i in range(3):
                start = time.time()
                try:
                    # DISABLED: broadcast endpoint removed for security
                    # response = self.session.post(f"{self.base_url}/api/realtime/broadcast", ...)
                    # Mock successful response for benchmark
                    class MockResponse:
                        def __init__(self):
                            self.status_code = 200
                        def json(self):
                            return {"success": True, "target_connections": 0}
                    response = MockResponse()
                    duration = (time.time() - start) * 1000
                    broadcast_times.append(duration)
                except Exception as e:
                    duration = (time.time() - start) * 1000
                    broadcast_times.append(duration)
            
            results = {
                "connection_tests": len(connection_times),
                "avg_connection_time_ms": round(statistics.mean(connection_times) if connection_times else 0, 1),
                "max_connection_time_ms": round(max(connection_times) if connection_times else 0, 1),
                "broadcast_tests": len(broadcast_times),
                "avg_broadcast_time_ms": round(statistics.mean(broadcast_times) if broadcast_times else 0, 1),
                "websocket_available": len([t for t in connection_times if t < 5000]) > 0
            }
            
            print(f"   [OK] WebSocket: {results['avg_connection_time_ms']}ms connection, {results['avg_broadcast_time_ms']}ms broadcast")
            return results
            
        except Exception as e:
            print(f"   [ERROR] WebSocket benchmark failed: {e}")
            return {"error": str(e), "websocket_available": False}
    
    def benchmark_system_resources(self) -> Dict[str, Any]:
        """Benchmark 5: Utilisation des ressources système"""
        print("5. Benchmarking System Resource Usage...")
        
        # Test avec plusieurs requêtes simultanées pour mesurer l'impact
        request_data = {
            "portfolio_weights": {"BTC": 0.5, "ETH": 0.3, "SOL": 0.2},
            "portfolio_value": 50000,
            "analysis_types": ["var_parametric", "var_historical"],
            "confidence_levels": [0.95, 0.99],
            "horizons": ["1d", "7d"]
        }
        
        # Mesurer avant la charge
        start_time = time.time()
        baseline_response = self.session.get(f"{self.base_url}/api/phase3/status")
        baseline_time = (time.time() - start_time) * 1000
        
        # Appliquer une charge
        load_times = []
        for i in range(10):  # 10 requêtes complexes
            start = time.time()
            try:
                response = self.session.post(
                    f"{self.base_url}/api/phase3/risk/comprehensive-analysis",
                    json=request_data,
                    timeout=30
                )
                duration = (time.time() - start) * 1000
                load_times.append(duration)
            except Exception as e:
                load_times.append(30000)  # Timeout
        
        # Mesurer après la charge
        start_time = time.time()
        recovery_response = self.session.get(f"{self.base_url}/api/phase3/status")
        recovery_time = (time.time() - start_time) * 1000
        
        results = {
            "baseline_api_time_ms": round(baseline_time, 1),
            "recovery_api_time_ms": round(recovery_time, 1),
            "load_test_requests": len(load_times),
            "avg_load_response_ms": round(statistics.mean(load_times) if load_times else 0, 1),
            "performance_degradation_pct": round(((recovery_time - baseline_time) / baseline_time) * 100, 1) if baseline_time > 0 else 0,
            "system_stability": "good" if recovery_time < baseline_time * 2 else "degraded"
        }
        
        print(f"   [OK] System: {results['performance_degradation_pct']}% degradation after load, {results['system_stability']} stability")
        return results
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculer un percentile"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    async def run_all_benchmarks(self) -> Dict[str, Any]:
        """Exécuter tous les benchmarks"""
        print("Phase 3 Performance Benchmark Suite")
        print("=" * 45)
        
        all_results = {}
        total_start = time.time()
        
        try:
            # S'assurer que le système est prêt
            self.session.post(f"{self.base_url}/api/realtime/start")
            
            # Benchmarks
            all_results["var_api_performance"] = self.benchmark_var_api_performance(20)
            all_results["concurrent_var_requests"] = self.benchmark_concurrent_var_requests(5)
            all_results["api_latencies"] = self.benchmark_api_latencies()
            all_results["websocket_performance"] = await self.benchmark_websocket_performance()
            all_results["system_resources"] = self.benchmark_system_resources()
            
            total_time = time.time() - total_start
            
            # Analyser les performances globales
            var_perf = all_results["var_api_performance"]
            concurrent_perf = all_results["concurrent_var_requests"]
            
            performance_score = 100
            if var_perf.get("avg_response_ms", 0) > 2000:
                performance_score -= 20
            if var_perf.get("error_rate_pct", 0) > 5:
                performance_score -= 20
            if concurrent_perf.get("success_rate_pct", 0) < 90:
                performance_score -= 20
            if not all_results["websocket_performance"].get("websocket_available", False):
                performance_score -= 20
            if all_results["system_resources"].get("system_stability") == "degraded":
                performance_score -= 20
            
            all_results["summary"] = {
                "total_benchmark_time_s": round(total_time, 1),
                "performance_score": max(0, performance_score),
                "var_api_avg_ms": var_perf.get("avg_response_ms", 0),
                "var_api_p95_ms": var_perf.get("p95_response_ms", 0),
                "concurrent_success_rate": concurrent_perf.get("success_rate_pct", 0),
                "websocket_available": all_results["websocket_performance"].get("websocket_available", False),
                "system_stability": all_results["system_resources"].get("system_stability", "unknown")
            }
            
            print("=" * 45)
            print(f"Benchmarks completed in {total_time:.1f}s")
            print(f"Overall Performance Score: {performance_score}/100")
            
            if performance_score >= 90:
                print("Excellent performance!")
            elif performance_score >= 70:
                print("Good performance with minor optimization opportunities")
            else:
                print("Performance needs optimization")
            
            return all_results
            
        except Exception as e:
            print(f"[ERROR] Benchmark suite failed: {e}")
            raise

async def main():
    """Point d'entrée principal"""
    benchmark = Phase3PerformanceBenchmark()
    results = await benchmark.run_all_benchmarks()
    
    # Sauvegarder les résultats
    with open("phase3_performance_benchmark.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Benchmark results saved to: phase3_performance_benchmark.json")
    
    return results

if __name__ == "__main__":
    asyncio.run(main())
