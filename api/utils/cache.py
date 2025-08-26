"""
Cache utilities for API endpoints
"""
from typing import Any, Dict
import time

def cache_get(cache: Dict, key: Any, ttl: int):
    """Get value from cache if not expired"""
    if key in cache:
        val, ts = cache[key]
        if time.time() - ts < ttl:
            return val
    return None

def cache_set(cache: Dict, key: Any, val: Any):
    """Set value in cache with timestamp"""
    cache[key] = (val, time.time())

def cache_clear_expired(cache: Dict, ttl: int):
    """Remove expired entries from cache"""
    now = time.time()
    expired_keys = [
        k for k, (_, ts) in cache.items() 
        if now - ts >= ttl
    ]
    for k in expired_keys:
        del cache[k]