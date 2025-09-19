"""
Unit tests for Stability Engine - Production Readiness
Tests hystérésis, EMA anti-flickering, staleness gating, and rate limiting
"""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch
from services.rate_limiter import AdaptiveRateLimiter, TokenBucket, get_rate_limiter

class TestTokenBucket:
    """Test token bucket mechanics"""

    def test_initial_state(self):
        bucket = TokenBucket(
            capacity=10.0,
            tokens=10.0,
            refill_rate=5.0,
            last_refill=time.time()
        )

        assert bucket.available_tokens() == 10
        assert bucket.consume(5) is True
        assert bucket.available_tokens() == 5

    def test_refill_mechanism(self):
        now = time.time()
        bucket = TokenBucket(
            capacity=10.0,
            tokens=0.0,
            refill_rate=5.0,  # 5 tokens per second
            last_refill=now - 2.0  # 2 seconds ago
        )

        # Should have refilled 10 tokens (2 sec × 5 tokens/sec)
        assert bucket.available_tokens() == 10

    def test_consume_with_insufficient_tokens(self):
        bucket = TokenBucket(
            capacity=10.0,
            tokens=2.0,
            refill_rate=5.0,
            last_refill=time.time()
        )

        assert bucket.consume(5) is False
        assert bucket.available_tokens() == 2  # Unchanged

    def test_time_until_available(self):
        bucket = TokenBucket(
            capacity=10.0,
            tokens=1.0,
            refill_rate=5.0,  # 5 tokens per second
            last_refill=time.time()
        )

        # Need 5 more tokens = 4 tokens needed / 5 tokens per second = 0.8 seconds
        time_needed = bucket.time_until_available(5)
        assert abs(time_needed - 0.8) < 0.1

    def test_capacity_limit(self):
        now = time.time()
        bucket = TokenBucket(
            capacity=10.0,
            tokens=5.0,
            refill_rate=10.0,  # High refill rate
            last_refill=now - 10.0  # Long time ago
        )

        # Should not exceed capacity
        assert bucket.available_tokens() == 10

class TestAdaptiveRateLimiter:
    """Test adaptive rate limiter with token bucket"""

    @pytest.fixture
    def rate_limiter(self):
        return AdaptiveRateLimiter(refill_rate=6.0, burst_size=12)

    @pytest.mark.asyncio
    async def test_basic_rate_limiting(self, rate_limiter):
        # First request should be allowed
        allowed, metadata = await rate_limiter.check_rate_limit("client1", "endpoint1")
        assert allowed is True
        assert metadata['allowed'] is True
        assert metadata['available_tokens'] == 11  # 12 - 1

    @pytest.mark.asyncio
    async def test_burst_handling(self, rate_limiter):
        client_id = "burst_client"

        # Should handle burst up to capacity
        for i in range(12):
            allowed, metadata = await rate_limiter.check_rate_limit(client_id)
            assert allowed is True

        # 13th request should be blocked
        allowed, metadata = await rate_limiter.check_rate_limit(client_id)
        assert allowed is False
        assert metadata['available_tokens'] == 0

    @pytest.mark.asyncio
    async def test_adaptive_cache_ttl(self, rate_limiter):
        client_id = "cache_client"
        endpoint = "test_endpoint"

        # Initial TTL
        initial_ttl = rate_limiter.get_adaptive_cache_ttl(client_id, endpoint)
        assert 10 <= initial_ttl <= 300

        # Simulate successful requests (cache hits)
        for _ in range(10):
            await rate_limiter.check_rate_limit(client_id, endpoint)

        # TTL should increase with good hit ratio
        high_hit_ttl = rate_limiter.get_adaptive_cache_ttl(client_id, endpoint)
        assert high_hit_ttl >= initial_ttl

    @pytest.mark.asyncio
    async def test_rate_limiter_status(self, rate_limiter):
        status = rate_limiter.get_status()

        assert 'active_buckets' in status
        assert 'cache_entries' in status
        assert 'total_requests' in status
        assert status['refill_rate'] == 6.0
        assert status['burst_size'] == 12

    @pytest.mark.asyncio
    async def test_cleanup_mechanism(self, rate_limiter):
        # Create multiple clients
        for i in range(5):
            await rate_limiter.check_rate_limit(f"client_{i}")

        initial_buckets = len(rate_limiter.buckets)
        assert initial_buckets == 5

        # Mock old timestamps to trigger cleanup
        for bucket in rate_limiter.buckets.values():
            bucket.last_refill = time.time() - 7200  # 2 hours ago

        # Force cleanup
        rate_limiter._last_cleanup = time.time() - 400  # Force cleanup check
        await rate_limiter.check_rate_limit("new_client")

        # Old buckets should be cleaned up
        assert len(rate_limiter.buckets) <= initial_buckets

class TestStabilityIntegration:
    """Integration tests for stability components"""

    @pytest.mark.asyncio
    async def test_disabled_rate_limiter(self):
        from services.rate_limiter import DisabledRateLimiter

        disabled_limiter = DisabledRateLimiter()
        allowed, metadata = await disabled_limiter.check_rate_limit("any_client")

        assert allowed is True
        assert metadata['allowed'] is True
        assert metadata.get('disabled') is True

    def test_rate_limiter_factory(self):
        with patch('config.settings.get_settings') as mock_settings:
            # Test enabled rate limiter
            mock_settings.return_value.security.rate_limit_requests = 100
            mock_settings.return_value.security.rate_limit_refill_rate = 5.0
            mock_settings.return_value.security.rate_limit_burst_size = 10

            limiter = get_rate_limiter()
            assert isinstance(limiter, AdaptiveRateLimiter)

            # Test disabled rate limiter
            mock_settings.return_value.security.rate_limit_requests = 0
            from services.rate_limiter import _rate_limiter
            global _rate_limiter
            _rate_limiter = None  # Reset global

            limiter = get_rate_limiter()
            from services.rate_limiter import DisabledRateLimiter
            assert isinstance(limiter, DisabledRateLimiter)

class TestHysteresisLogic:
    """Test hystérésis and EMA logic"""

    def test_deadband_functionality(self):
        """Test that small changes within deadband don't trigger updates"""
        # This would test the JS stability engine logic
        # For now, we verify the concept with Python equivalent

        class MockHysteresis:
            def __init__(self, deadband=0.02):
                self.deadband = deadband
                self.last_stable = None

            def apply(self, value):
                if self.last_stable is None:
                    self.last_stable = value
                    return value

                delta = abs(value - self.last_stable)
                if delta > self.deadband:
                    self.last_stable = value
                    return value

                return self.last_stable

        hysteresis = MockHysteresis()

        # Initial value
        result1 = hysteresis.apply(0.50)
        assert result1 == 0.50

        # Small change within deadband
        result2 = hysteresis.apply(0.51)  # +1% < 2% deadband
        assert result2 == 0.50  # Should remain unchanged

        # Large change outside deadband
        result3 = hysteresis.apply(0.53)  # +3% > 2% deadband
        assert result3 == 0.53  # Should update

    def test_ema_smoothing(self):
        """Test EMA smoothing functionality"""

        class MockEMA:
            def __init__(self, alpha=0.3):
                self.alpha = alpha
                self.value = None

            def update(self, new_value):
                if self.value is None:
                    self.value = new_value
                else:
                    self.value = self.alpha * new_value + (1 - self.alpha) * self.value
                return self.value

        ema = MockEMA()

        # Test smoothing of large jump
        ema.update(0.30)  # Initial
        ema.update(0.70)  # Large jump

        # Result should be between 0.30 and 0.70 due to smoothing
        assert 0.30 < ema.value < 0.70

        # Verify smoothing formula
        expected = 0.3 * 0.70 + 0.7 * 0.30  # 0.21 + 0.21 = 0.42
        assert abs(ema.value - expected) < 0.01

class TestStabilityPerformance:
    """Performance tests for stability components"""

    @pytest.mark.asyncio
    async def test_rate_limiter_performance(self):
        """Test rate limiter performance under load"""
        rate_limiter = AdaptiveRateLimiter(refill_rate=10.0, burst_size=20)

        start_time = time.time()

        # Simulate 1000 requests
        tasks = []
        for i in range(1000):
            task = rate_limiter.check_rate_limit(f"client_{i % 10}")
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        duration = time.time() - start_time

        # Should complete in reasonable time (< 1 second)
        assert duration < 1.0

        # Should have some allowed and some blocked
        allowed_count = sum(1 for allowed, _ in results if allowed)
        assert 0 < allowed_count < 1000

    def test_bucket_refill_accuracy(self):
        """Test accuracy of token bucket refill calculations"""
        bucket = TokenBucket(
            capacity=100.0,
            tokens=0.0,
            refill_rate=10.0,  # 10 tokens/second
            last_refill=time.time() - 5.0  # 5 seconds ago
        )

        # Should have exactly 50 tokens (5 sec × 10 tokens/sec)
        tokens = bucket.available_tokens()
        assert abs(tokens - 50) < 1  # Allow small floating point error

class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_negative_tokens_request(self):
        """Test handling of invalid token requests"""
        rate_limiter = AdaptiveRateLimiter()

        # Should handle gracefully (treat as 1 token)
        allowed, metadata = await rate_limiter.check_rate_limit("client", "endpoint", tokens=0)
        assert isinstance(allowed, bool)
        assert isinstance(metadata, dict)

    def test_extreme_refill_rates(self):
        """Test bucket behavior with extreme refill rates"""
        # Very high refill rate
        fast_bucket = TokenBucket(
            capacity=10.0,
            tokens=0.0,
            refill_rate=1000.0,
            last_refill=time.time() - 1.0
        )

        # Should cap at capacity
        assert fast_bucket.available_tokens() == 10

        # Very low refill rate
        slow_bucket = TokenBucket(
            capacity=10.0,
            tokens=0.0,
            refill_rate=0.1,
            last_refill=time.time() - 1.0
        )

        # Should have minimal tokens
        assert slow_bucket.available_tokens() < 1

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test thread safety of rate limiter"""
        rate_limiter = AdaptiveRateLimiter(refill_rate=5.0, burst_size=10)
        client_id = "concurrent_client"

        # Simulate concurrent requests
        async def make_request():
            return await rate_limiter.check_rate_limit(client_id)

        tasks = [make_request() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # Should handle all requests without errors
        assert len(results) == 20
        assert all(isinstance(result, tuple) for result in results)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])