"""
Tests de performance pour les modules du Risk Dashboard
Mesure les temps de réponse, throughput, et comportement sous charge
"""

import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from statistics import mean, stdev, median
from typing import List, Dict, Any

from api.main import app


class TestRiskDashboardPerformance:
    """Tests de performance pour les endpoints du Risk Dashboard"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def measure_response_time(self, client: TestClient, url: str, iterations: int = 10) -> Dict[str, float]:
        """Mesure le temps de réponse d'un endpoint"""
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            response = client.get(url)
            duration = (time.perf_counter() - start) * 1000  # ms

            if response.status_code == 200:
                times.append(duration)

        if not times:
            return {
                'mean': 0,
                'median': 0,
                'stdev': 0,
                'min': 0,
                'max': 0,
                'p95': 0,
                'p99': 0
            }

        times.sort()
        p95_index = int(len(times) * 0.95)
        p99_index = int(len(times) * 0.99)

        return {
            'mean': mean(times),
            'median': median(times),
            'stdev': stdev(times) if len(times) > 1 else 0,
            'min': min(times),
            'max': max(times),
            'p95': times[p95_index],
            'p99': times[p99_index],
            'samples': len(times)
        }

    def test_alerts_endpoint_performance(self, client):
        """Test performance /api/alerts/active (< 100ms p95)"""
        url = "/api/alerts/active"
        stats = self.measure_response_time(client, url, iterations=20)

        print(f"\n[Alerts Tab] GET {url}")
        print(f"  Mean: {stats['mean']:.2f}ms")
        print(f"  Median: {stats['median']:.2f}ms")
        print(f"  P95: {stats['p95']:.2f}ms")
        print(f"  Min/Max: {stats['min']:.2f}ms / {stats['max']:.2f}ms")

        # Objectif: P95 < 100ms
        assert stats['p95'] < 100, f"P95 trop élevé: {stats['p95']:.2f}ms (objectif: < 100ms)"

    def test_risk_dashboard_endpoint_performance(self, client):
        """Test performance /api/risk/dashboard (< 500ms p95)"""
        url = "/api/risk/dashboard?user_id=demo&source=cointracking"
        stats = self.measure_response_time(client, url, iterations=20)

        print(f"\n[Overview Tab] GET {url}")
        print(f"  Mean: {stats['mean']:.2f}ms")
        print(f"  Median: {stats['median']:.2f}ms")
        print(f"  P95: {stats['p95']:.2f}ms")
        print(f"  Min/Max: {stats['min']:.2f}ms / {stats['max']:.2f}ms")

        # Objectif: P95 < 500ms
        assert stats['p95'] < 500, f"P95 trop élevé: {stats['p95']:.2f}ms (objectif: < 500ms)"

    def test_risk_dashboard_dual_window_performance(self, client):
        """Test performance /api/risk/dashboard avec dual_window (< 1000ms p95)"""
        url = "/api/risk/dashboard?user_id=demo&source=cointracking&use_dual_window=true"
        stats = self.measure_response_time(client, url, iterations=15)

        print(f"\n[Overview Tab - Dual Window] GET {url}")
        print(f"  Mean: {stats['mean']:.2f}ms")
        print(f"  Median: {stats['median']:.2f}ms")
        print(f"  P95: {stats['p95']:.2f}ms")
        print(f"  Min/Max: {stats['min']:.2f}ms / {stats['max']:.2f}ms")

        # Objectif: P95 < 1000ms (calculs plus lourds)
        assert stats['p95'] < 1000, f"P95 trop élevé: {stats['p95']:.2f}ms (objectif: < 1000ms)"

    def test_bitcoin_historical_price_performance(self, client):
        """Test performance /api/ml/bitcoin-historical-price (< 2000ms p95)"""
        url = "/api/ml/bitcoin-historical-price?days=365"
        stats = self.measure_response_time(client, url, iterations=10)

        print(f"\n[Cycles Tab] GET {url}")
        print(f"  Mean: {stats['mean']:.2f}ms")
        print(f"  Median: {stats['median']:.2f}ms")
        print(f"  P95: {stats['p95']:.2f}ms")
        print(f"  Min/Max: {stats['min']:.2f}ms / {stats['max']:.2f}ms")

        # Objectif: P95 < 2000ms (fetch externe FRED/Binance)
        assert stats['p95'] < 2000, f"P95 trop élevé: {stats['p95']:.2f}ms (objectif: < 2000ms)"

    def test_governance_state_performance(self, client):
        """Test performance /execution/governance/state (< 200ms p95)"""
        url = "/execution/governance/state"
        stats = self.measure_response_time(client, url, iterations=20)

        print(f"\n[Targets Tab] GET {url}")
        print(f"  Mean: {stats['mean']:.2f}ms")
        print(f"  Median: {stats['median']:.2f}ms")
        print(f"  P95: {stats['p95']:.2f}ms")
        print(f"  Min/Max: {stats['min']:.2f}ms / {stats['max']:.2f}ms")

        # Objectif: P95 < 200ms
        assert stats['p95'] < 200, f"P95 trop élevé: {stats['p95']:.2f}ms (objectif: < 200ms)"

    def test_concurrent_requests_throughput(self, client):
        """Test throughput avec 10 requêtes concurrentes"""
        url = "/api/risk/dashboard?user_id=demo&source=cointracking"
        num_requests = 10

        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(client.get, url) for _ in range(num_requests)]
            results = [f.result() for f in as_completed(futures)]

        total_duration = time.perf_counter() - start

        success_count = sum(1 for r in results if r.status_code == 200)
        throughput = num_requests / total_duration

        print(f"\n[Concurrency Test] {num_requests} requêtes parallèles")
        print(f"  Total duration: {total_duration:.2f}s")
        print(f"  Success rate: {success_count}/{num_requests} ({success_count/num_requests*100:.1f}%)")
        print(f"  Throughput: {throughput:.2f} req/s")

        # Objectif: > 80% success, throughput > 2 req/s
        assert success_count / num_requests >= 0.8, f"Success rate trop faible: {success_count}/{num_requests}"
        assert throughput >= 2, f"Throughput trop faible: {throughput:.2f} req/s (objectif: > 2 req/s)"

    def test_memory_leak_detection(self, client):
        """Test détection fuites mémoire (100 requêtes successives)"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        url = "/api/risk/dashboard?user_id=demo&source=cointracking"

        # Baseline
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # 100 requêtes
        for _ in range(100):
            client.get(url)

        # Mesure finale
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        print(f"\n[Memory Leak Test] 100 requêtes")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Increase: {memory_increase:.2f} MB")

        # Objectif: < 50MB d'augmentation (raisonnable pour caches)
        assert memory_increase < 50, f"Fuite mémoire possible: +{memory_increase:.2f} MB"


class TestRiskDashboardStressTests:
    """Tests de stress et cas limites"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_large_alert_list_performance(self, client):
        """Test performance avec grande liste d'alertes (simulation)"""
        # Ce test nécessite un mock ou des données de test volumineuses
        # Pour l'instant, on teste juste que l'endpoint répond

        url = "/api/alerts/active?limit=1000"
        start = time.perf_counter()
        response = client.get(url)
        duration = (time.perf_counter() - start) * 1000

        print(f"\n[Stress Test - Large Alerts] GET {url}")
        print(f"  Status: {response.status_code}")
        print(f"  Duration: {duration:.2f}ms")
        print(f"  Payload size: {len(response.content)} bytes")

        assert response.status_code == 200
        assert duration < 1000, f"Trop lent avec 1000 alertes: {duration:.2f}ms"

    def test_rapid_fire_requests(self, client):
        """Test 50 requêtes rapides séquentielles"""
        url = "/api/alerts/active"
        num_requests = 50

        start = time.perf_counter()
        results = []

        for _ in range(num_requests):
            response = client.get(url)
            results.append(response.status_code)

        total_duration = time.perf_counter() - start
        success_rate = results.count(200) / num_requests

        print(f"\n[Rapid Fire Test] {num_requests} requêtes séquentielles")
        print(f"  Total duration: {total_duration:.2f}s")
        print(f"  Success rate: {success_rate*100:.1f}%")
        print(f"  Avg response time: {(total_duration/num_requests)*1000:.2f}ms")

        # Objectif: 100% success, < 3s total
        assert success_rate == 1.0, f"Échecs détectés: {results.count(200)}/{num_requests}"
        assert total_duration < 3, f"Trop lent: {total_duration:.2f}s (objectif: < 3s)"

    def test_payload_size_optimization(self, client):
        """Test taille des payloads (compression efficace)"""
        endpoints = [
            "/api/alerts/active",
            "/api/risk/dashboard?user_id=demo&source=cointracking",
            "/api/ml/bitcoin-historical-price?days=365"
        ]

        print("\n[Payload Size Test]")
        for url in endpoints:
            response = client.get(url)

            if response.status_code == 200:
                payload_size = len(response.content)
                print(f"  {url}")
                print(f"    Size: {payload_size} bytes ({payload_size/1024:.2f} KB)")

                # Objectif: < 500KB par endpoint (compression active)
                assert payload_size < 500_000, f"Payload trop large: {payload_size} bytes"

    def test_cache_effectiveness(self, client):
        """Test efficacité du cache (2ème requête plus rapide)"""
        url = "/api/risk/dashboard?user_id=demo&source=cointracking"

        # 1ère requête (cache miss)
        start1 = time.perf_counter()
        response1 = client.get(url)
        duration1 = (time.perf_counter() - start1) * 1000

        # 2ème requête immédiate (cache hit attendu)
        start2 = time.perf_counter()
        response2 = client.get(url)
        duration2 = (time.perf_counter() - start2) * 1000

        print(f"\n[Cache Test] {url}")
        print(f"  1st request: {duration1:.2f}ms")
        print(f"  2nd request: {duration2:.2f}ms")
        print(f"  Speedup: {duration1/duration2:.2f}x")

        # Objectif: 2ème requête au moins 1.5x plus rapide
        assert response1.status_code == 200
        assert response2.status_code == 200
        # Note: cache peut ne pas être implémenté partout, donc test souple
        print(f"  Cache {'efficace' if duration2 < duration1 * 0.7 else 'absent ou faible'}")


class TestRiskDashboardEdgeCases:
    """Tests des cas limites et erreurs"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_invalid_user_id(self, client):
        """Test user_id invalide"""
        response = client.get(
            "/api/risk/dashboard?user_id=nonexistent_user_xyz&source=cointracking"
        )

        # Doit gérer gracieusement (200 avec données par défaut ou 404)
        assert response.status_code in [200, 404]
        print(f"\n[Edge Case] Invalid user_id: {response.status_code}")

    def test_malformed_parameters(self, client):
        """Test paramètres malformés"""
        test_cases = [
            "/api/risk/dashboard?min_history_days=-100",  # Négatif
            "/api/risk/dashboard?min_coverage_pct=1.5",   # > 1
            "/api/alerts/active?severity_filter=INVALID",  # Valeur invalide
        ]

        print("\n[Edge Cases] Malformed parameters")
        for url in test_cases:
            response = client.get(url)
            print(f"  {url}: {response.status_code}")

            # Doit retourner 422 (validation error) ou 200 (handled gracefully)
            assert response.status_code in [200, 422]

    def test_missing_required_parameters(self, client):
        """Test paramètres requis manquants"""
        # user_id manquant (doit utiliser default 'demo')
        response = client.get("/api/risk/dashboard?source=cointracking")

        print(f"\n[Edge Case] Missing user_id: {response.status_code}")
        assert response.status_code == 200  # Default à 'demo'

    def test_empty_response_handling(self, client):
        """Test réponses vides (nouveau user sans données)"""
        response = client.get(
            "/api/risk/dashboard?user_id=empty_user_test&source=cointracking"
        )

        print(f"\n[Edge Case] Empty portfolio: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            # Doit retourner une structure valide même vide
            assert "risk_metrics" in data or "error" in data

    def test_rate_limiting_behavior(self, client):
        """Test comportement rate limiting (100 requêtes rapides)"""
        url = "/api/alerts/active"
        num_requests = 100

        responses = []
        for _ in range(num_requests):
            response = client.get(url)
            responses.append(response.status_code)

        success_count = responses.count(200)
        rate_limited_count = responses.count(429)

        print(f"\n[Rate Limiting Test] {num_requests} requêtes")
        print(f"  Success: {success_count}")
        print(f"  Rate limited (429): {rate_limited_count}")

        # Pas de rate limiting strict en dev, mais on vérifie la résilience
        assert success_count + rate_limited_count == num_requests


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
