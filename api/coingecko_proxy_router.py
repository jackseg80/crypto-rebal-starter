"""
CoinGecko Proxy Router
Provides a backend proxy for CoinGecko API to avoid CORS and rate limiting issues.

Features:
- Caching (5 minutes default) to reduce API calls
- CORS-free (backend-to-backend)
- Automatic fallback to cached data on API failures
- Rate limit handling
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
import httpx
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger("crypto-rebalancer")

router = APIRouter(prefix="/api/coingecko-proxy", tags=["coingecko-proxy"])

# Simple in-memory cache
# Format: {cache_key: {"data": {...}, "timestamp": datetime, "ttl": int}}
_cache: Dict[str, Dict[str, Any]] = {}

def get_cached_data(cache_key: str, ttl_seconds: int = 300) -> Optional[Dict[str, Any]]:
    """
    Get cached data if available and not expired.

    Args:
        cache_key: Unique key for the cached data
        ttl_seconds: Time-to-live in seconds (default 5 minutes)

    Returns:
        Cached data or None if expired/not found
    """
    if cache_key not in _cache:
        return None

    cached = _cache[cache_key]
    age = (datetime.now() - cached["timestamp"]).total_seconds()

    if age > ttl_seconds:
        logger.debug(f"Cache expired for {cache_key} (age: {age:.1f}s, ttl: {ttl_seconds}s)")
        del _cache[cache_key]
        return None

    logger.debug(f"Cache hit for {cache_key} (age: {age:.1f}s)")
    return cached["data"]

def set_cached_data(cache_key: str, data: Dict[str, Any], ttl_seconds: int = 300):
    """
    Store data in cache with timestamp.

    Args:
        cache_key: Unique key for the cached data
        data: Data to cache
        ttl_seconds: Time-to-live in seconds
    """
    _cache[cache_key] = {
        "data": data,
        "timestamp": datetime.now(),
        "ttl": ttl_seconds
    }
    logger.debug(f"Cached data for {cache_key} (ttl: {ttl_seconds}s)")

async def _fetch_with_cache_and_fallback(
    url: str,
    cache_key: str,
    cache_ttl: int,
    params: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Helper function to fetch from CoinGecko with caching and stale fallback.

    Args:
        url: CoinGecko API URL
        cache_key: Unique cache key
        cache_ttl: Cache TTL in seconds
        params: Optional query parameters

    Returns:
        Response dict with data, cached status, etc.
    """
    # Try cache first
    cached = get_cached_data(cache_key, cache_ttl)
    if cached:
        return {
            "data": cached,
            "cached": True,
            "timestamp": datetime.now().isoformat()
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.debug(f"Fetching from CoinGecko: {url}")
            response = await client.get(url, params=params)

            if response.status_code == 429:
                logger.warning("CoinGecko rate limit reached (429)")
                # Try to use stale cache if available
                if cache_key in _cache:
                    stale_data = _cache[cache_key]["data"]
                    age = (datetime.now() - _cache[cache_key]["timestamp"]).total_seconds()
                    logger.info(f"Using stale cache (age: {age:.1f}s) due to rate limit")
                    return {
                        "data": stale_data,
                        "cached": True,
                        "stale": True,
                        "age_seconds": age,
                        "timestamp": datetime.now().isoformat(),
                        "warning": "CoinGecko API rate limited, using stale cache"
                    }
                raise HTTPException(status_code=429, detail="CoinGecko API rate limit exceeded and no cache available")

            response.raise_for_status()
            data = response.json()

            # Cache the response
            set_cached_data(cache_key, data, cache_ttl)

            logger.info(f"Successfully fetched data from CoinGecko: {url}")
            return {
                "data": data,
                "cached": False,
                "timestamp": datetime.now().isoformat()
            }

    except httpx.TimeoutException:
        logger.error("CoinGecko API timeout")
        # Try to use stale cache
        if cache_key in _cache:
            stale_data = _cache[cache_key]["data"]
            age = (datetime.now() - _cache[cache_key]["timestamp"]).total_seconds()
            logger.info(f"Using stale cache (age: {age:.1f}s) due to timeout")
            return {
                "data": stale_data,
                "cached": True,
                "stale": True,
                "age_seconds": age,
                "timestamp": datetime.now().isoformat(),
                "warning": "CoinGecko API timeout, using stale cache"
            }
        raise HTTPException(status_code=504, detail="CoinGecko API timeout and no cache available")

    except httpx.HTTPStatusError as e:
        logger.error(f"CoinGecko API error: {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail=f"CoinGecko API error: {e.response.text}")

    except Exception as e:
        logger.error(f"Unexpected error fetching CoinGecko data: {e}")
        # Try to use stale cache
        if cache_key in _cache:
            stale_data = _cache[cache_key]["data"]
            age = (datetime.now() - _cache[cache_key]["timestamp"]).total_seconds()
            logger.info(f"Using stale cache (age: {age:.1f}s) due to error")
            return {
                "data": stale_data,
                "cached": True,
                "stale": True,
                "age_seconds": age,
                "timestamp": datetime.now().isoformat(),
                "warning": f"CoinGecko API error: {str(e)}, using stale cache"
            }
        raise HTTPException(status_code=500, detail=f"Failed to fetch CoinGecko data: {str(e)}")

@router.get("/bitcoin")
async def get_bitcoin_data(
    localization: bool = Query(False, description="Include localization data"),
    tickers: bool = Query(False, description="Include tickers data"),
    market_data: bool = Query(True, description="Include market data"),
    community_data: bool = Query(False, description="Include community data"),
    developer_data: bool = Query(False, description="Include developer data"),
    sparkline: bool = Query(False, description="Include sparkline data"),
    cache_ttl: int = Query(300, description="Cache TTL in seconds", ge=60, le=3600)
):
    """
    Proxy endpoint for CoinGecko Bitcoin data.

    This endpoint caches responses to avoid rate limiting and provides
    graceful degradation when CoinGecko API is unavailable.

    Example:
        GET /api/coingecko-proxy/bitcoin?market_data=true

    Returns:
        Bitcoin market data from CoinGecko API (or cached data)
    """
    # Build cache key from parameters
    cache_key = f"bitcoin_{localization}_{tickers}_{market_data}_{community_data}_{developer_data}_{sparkline}"

    # Build CoinGecko URL and params
    url = "https://api.coingecko.com/api/v3/coins/bitcoin"
    params = {
        "localization": str(localization).lower(),
        "tickers": str(tickers).lower(),
        "market_data": str(market_data).lower(),
        "community_data": str(community_data).lower(),
        "developer_data": str(developer_data).lower(),
        "sparkline": str(sparkline).lower()
    }

    return await _fetch_with_cache_and_fallback(url, cache_key, cache_ttl, params)

@router.get("/global")
async def get_global_data(
    cache_ttl: int = Query(300, description="Cache TTL in seconds", ge=60, le=3600)
):
    """
    Proxy endpoint for CoinGecko global cryptocurrency market data.
    Used for BTC dominance and market cap data.

    Example:
        GET /api/coingecko-proxy/global

    Returns:
        Global market data from CoinGecko API (or cached data)
    """
    cache_key = "global"
    url = "https://api.coingecko.com/api/v3/global"

    return await _fetch_with_cache_and_fallback(url, cache_key, cache_ttl)

@router.get("/simple/price")
async def get_simple_price(
    ids: str = Query(..., description="Comma-separated coin IDs (e.g., bitcoin,ethereum)"),
    vs_currencies: str = Query("usd", description="Comma-separated fiat currencies"),
    cache_ttl: int = Query(300, description="Cache TTL in seconds", ge=60, le=3600)
):
    """
    Proxy endpoint for CoinGecko simple price endpoint.
    Used for getting current prices of multiple coins.

    Example:
        GET /api/coingecko-proxy/simple/price?ids=bitcoin,ethereum&vs_currencies=usd

    Returns:
        Simple price data from CoinGecko API (or cached data)
    """
    cache_key = f"simple_price_{ids}_{vs_currencies}"
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ids,
        "vs_currencies": vs_currencies
    }

    return await _fetch_with_cache_and_fallback(url, cache_key, cache_ttl, params)

@router.get("/market_chart")
async def get_market_chart(
    coin_id: str = Query("bitcoin", description="Coin ID (e.g., bitcoin)"),
    vs_currency: str = Query("usd", description="Fiat currency"),
    days: int = Query(7, description="Number of days", ge=1, le=365),
    interval: str = Query("daily", description="Data interval"),
    cache_ttl: int = Query(300, description="Cache TTL in seconds", ge=60, le=3600)
):
    """
    Proxy endpoint for CoinGecko market chart endpoint.
    Used for historical price data and volatility calculations.

    Example:
        GET /api/coingecko-proxy/market_chart?coin_id=bitcoin&vs_currency=usd&days=7&interval=daily

    Returns:
        Market chart data from CoinGecko API (or cached data)
    """
    cache_key = f"market_chart_{coin_id}_{vs_currency}_{days}_{interval}"
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": vs_currency,
        "days": str(days),
        "interval": interval
    }

    return await _fetch_with_cache_and_fallback(url, cache_key, cache_ttl, params)

@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics (useful for debugging).

    Returns:
        Cache size, keys, and ages
    """
    now = datetime.now()
    stats = {
        "cache_size": len(_cache),
        "entries": []
    }

    for key, value in _cache.items():
        age = (now - value["timestamp"]).total_seconds()
        stats["entries"].append({
            "key": key,
            "age_seconds": age,
            "ttl_seconds": value["ttl"],
            "expired": age > value["ttl"]
        })

    return stats

@router.delete("/cache/clear")
async def clear_cache():
    """
    Clear the entire cache (useful for debugging/testing).

    Returns:
        Number of entries cleared
    """
    global _cache
    count = len(_cache)
    _cache = {}
    logger.info(f"Cleared {count} cache entries")
    return {"cleared": count, "message": f"Cleared {count} cache entries"}
