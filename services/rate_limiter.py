"""
Token Bucket Rate Limiter with Adaptive Caching
Implements sophisticated rate limiting with burst handling and cache optimization
"""

import time
import asyncio
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging

log = logging.getLogger(__name__)

@dataclass
class TokenBucket:
    """Token bucket for rate limiting with burst support"""
    capacity: float
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float

    def consume(self, tokens: int = 1) -> bool:
        """Attempt to consume tokens from bucket"""
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        """Refill bucket based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def available_tokens(self) -> int:
        """Get current available tokens"""
        self._refill()
        return int(self.tokens)

    def time_until_available(self, tokens: int = 1) -> float:
        """Time in seconds until specified tokens available"""
        self._refill()
        if self.tokens >= tokens:
            return 0.0

        needed_tokens = tokens - self.tokens
        return needed_tokens / self.refill_rate

class AdaptiveRateLimiter:
    """Advanced rate limiter with token bucket and adaptive caching"""

    def __init__(self, refill_rate: float = 6.0, burst_size: int = 12):
        self.refill_rate = refill_rate
        self.burst_size = burst_size
        self.buckets: Dict[str, TokenBucket] = {}
        self.cache_stats: Dict[str, dict] = defaultdict(lambda: {
            'hits': 0, 'misses': 0, 'last_access': time.time()
        })
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

        log.info(f"🪣 Token bucket rate limiter initialized: {refill_rate} req/s burst {burst_size}")

    def _get_bucket(self, client_id: str) -> TokenBucket:
        """Get or create token bucket for client"""
        now = time.time()

        if client_id not in self.buckets:
            self.buckets[client_id] = TokenBucket(
                capacity=self.burst_size,
                tokens=self.burst_size,  # Start with full bucket
                refill_rate=self.refill_rate,
                last_refill=now
            )

        return self.buckets[client_id]

    async def check_rate_limit(self, client_id: str, endpoint: str = "",
                              tokens: int = 1) -> Tuple[bool, Dict]:
        """
        Check if request is allowed under rate limit
        Returns: (allowed, metadata)
        """
        self._maybe_cleanup()

        bucket = self._get_bucket(client_id)
        allowed = bucket.consume(tokens)

        # Update cache stats
        cache_key = f"{client_id}:{endpoint}"
        stats = self.cache_stats[cache_key]
        stats['last_access'] = time.time()

        if allowed:
            stats['hits'] += 1
        else:
            stats['misses'] += 1

        metadata = {
            'allowed': allowed,
            'available_tokens': bucket.available_tokens(),
            'refill_rate': self.refill_rate,
            'burst_size': self.burst_size,
            'time_until_available': bucket.time_until_available(tokens),
            'cache_hit_ratio': self._get_cache_hit_ratio(cache_key)
        }

        if not allowed:
            log.warning(f"🚫 Rate limit exceeded for {client_id}:{endpoint} "
                       f"(next available in {metadata['time_until_available']:.1f}s)")

        return allowed, metadata

    def _get_cache_hit_ratio(self, cache_key: str) -> float:
        """Calculate cache hit ratio for adaptive caching"""
        stats = self.cache_stats[cache_key]
        total = stats['hits'] + stats['misses']
        return stats['hits'] / total if total > 0 else 0.0

    def get_adaptive_cache_ttl(self, client_id: str, endpoint: str) -> int:
        """
        Calculate adaptive cache TTL based on usage patterns
        High hit ratio = longer cache, frequent misses = shorter cache
        """
        cache_key = f"{client_id}:{endpoint}"
        hit_ratio = self._get_cache_hit_ratio(cache_key)
        stats = self.cache_stats[cache_key]

        # Base TTL: 30 seconds
        base_ttl = 30

        # Adjust based on hit ratio
        if hit_ratio > 0.8:  # High cache efficiency
            multiplier = 2.0
        elif hit_ratio > 0.5:  # Medium efficiency
            multiplier = 1.5
        else:  # Low efficiency, shorter cache
            multiplier = 0.8

        # Factor in recency of access
        time_since_access = time.time() - stats['last_access']
        if time_since_access < 60:  # Recent access
            multiplier *= 1.2

        adaptive_ttl = int(base_ttl * multiplier)
        return max(10, min(300, adaptive_ttl))  # Clamp between 10s and 5min

    def _maybe_cleanup(self):
        """Periodic cleanup of old buckets and stats"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        # Remove stale buckets (no activity for 1 hour)
        stale_threshold = now - 3600
        stale_clients = [
            client_id for client_id, bucket in self.buckets.items()
            if bucket.last_refill < stale_threshold
        ]

        for client_id in stale_clients:
            del self.buckets[client_id]

        # Remove stale cache stats
        stale_cache_keys = [
            key for key, stats in self.cache_stats.items()
            if stats['last_access'] < stale_threshold
        ]

        for key in stale_cache_keys:
            del self.cache_stats[key]

        if stale_clients or stale_cache_keys:
            log.info(f"🧹 Cleanup: removed {len(stale_clients)} buckets, "
                    f"{len(stale_cache_keys)} cache entries")

        self._last_cleanup = now

    def get_status(self) -> Dict:
        """Get rate limiter status for monitoring"""
        total_requests = sum(
            stats['hits'] + stats['misses']
            for stats in self.cache_stats.values()
        )

        return {
            'active_buckets': len(self.buckets),
            'cache_entries': len(self.cache_stats),
            'total_requests': total_requests,
            'refill_rate': self.refill_rate,
            'burst_size': self.burst_size,
            'uptime': time.time() - self._last_cleanup
        }

# Global instance
_rate_limiter: Optional[AdaptiveRateLimiter] = None

def get_rate_limiter() -> AdaptiveRateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        from config.settings import get_settings
        settings = get_settings()

        # Only enable if rate limiting is configured
        if settings.security.rate_limit_requests > 0:
            _rate_limiter = AdaptiveRateLimiter(
                refill_rate=settings.security.rate_limit_refill_rate,
                burst_size=settings.security.rate_limit_burst_size
            )
        else:
            # Disabled rate limiter (allows everything)
            _rate_limiter = DisabledRateLimiter()

    return _rate_limiter

class DisabledRateLimiter:
    """No-op rate limiter for when rate limiting is disabled"""

    async def check_rate_limit(self, client_id: str, endpoint: str = "",
                              tokens: int = 1) -> Tuple[bool, Dict]:
        return True, {
            'allowed': True,
            'available_tokens': float('inf'),
            'disabled': True
        }

    def get_adaptive_cache_ttl(self, client_id: str, endpoint: str) -> int:
        return 60  # Default 1 minute cache

    def get_status(self) -> Dict:
        return {'disabled': True}