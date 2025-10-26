"""
CoinGecko Proxy Router
Provides a backend proxy for CoinGecko API to avoid CORS and rate limiting issues.

Features:
- Caching (15 minutes default - optimized Oct 2025) to reduce API calls
- CORS-free (backend-to-backend)
- Automatic fallback to cached data on API failures
- Rate limit handling
- Multi-tenant: uses user's CoinGecko API key from config.json
"""
from fastapi import APIRouter, HTTPException, Query, Header
from typing import Dict, Any, Optional
import httpx
import logging
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

logger = logging.getLogger("crypto-rebalancer")

def get_user_coingecko_key(user_id: str) -> Optional[str]:
    """
    Load CoinGecko API key from user's config.json.
    Falls back to .env if user config doesn't exist.

    Args:
        user_id: User ID

    Returns:
        CoinGecko API key or None
    """
    try:
        config_path = Path(f"data/users/{user_id}/config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                key = config.get("coingecko_api_key", "")
                if key:
                    logger.debug(f"Using CoinGecko key from user {user_id} config")
                    return key
    except Exception as e:
        logger.warning(f"Failed to load user config for {user_id}: {e}")

    # Fallback to .env
    env_key = os.getenv("COINGECKO_API_KEY", "")
    if env_key:
        logger.debug("Using CoinGecko key from .env (fallback)")
        return env_key

    logger.debug("No CoinGecko API key found (user config or .env)")
    return None

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
    params: Optional[Dict[str, str]] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Helper function to fetch from CoinGecko with caching and stale fallback.

    Args:
        url: CoinGecko API URL
        cache_key: Unique cache key
        cache_ttl: Cache TTL in seconds
        params: Optional query parameters
        api_key: CoinGecko API key (from user config)

    Returns:
        Response dict with data, cached status, etc.
    """
    # Try cache first
    cached = get_cached_data(cache_key, cache_ttl)
    if cached:
        # Return data directly (frontend expects raw CoinGecko response)
        return cached

    try:
        # Add API key to params if available (for Pro/Demo API)
        if api_key:
            if params is None:
                params = {}
            params["x_cg_demo_api_key"] = api_key
            logger.debug("Using CoinGecko API key from user config")

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
                    # Return data directly (frontend expects raw CoinGecko response)
                    return stale_data
                raise HTTPException(status_code=429, detail="CoinGecko API rate limit exceeded and no cache available")

            response.raise_for_status()
            data = response.json()

            # Cache the response
            set_cached_data(cache_key, data, cache_ttl)

            logger.info(f"Successfully fetched data from CoinGecko: {url}")
            # Return data directly (frontend expects raw CoinGecko response)
            return data

    except httpx.TimeoutException:
        logger.error("CoinGecko API timeout")
        # Try to use stale cache
        if cache_key in _cache:
            stale_data = _cache[cache_key]["data"]
            age = (datetime.now() - _cache[cache_key]["timestamp"]).total_seconds()
            logger.info(f"Using stale cache (age: {age:.1f}s) due to timeout")
            # Return data directly (frontend expects raw CoinGecko response)
            return stale_data
        raise HTTPException(status_code=504, detail="CoinGecko API timeout and no cache available")

    except httpx.HTTPStatusError as e:
        logger.error(f"CoinGecko API error: {e.response.status_code}")
        # Try to use stale cache instead of raising error
        if cache_key in _cache:
            stale_data = _cache[cache_key]["data"]
            age = (datetime.now() - _cache[cache_key]["timestamp"]).total_seconds()
            logger.info(f"Using stale cache (age: {age:.1f}s) due to API error {e.response.status_code}")
            # Return data directly (frontend expects raw CoinGecko response)
            return stale_data
        # Only raise if no cache available
        raise HTTPException(status_code=e.response.status_code, detail=f"CoinGecko API error and no cache available")

    except Exception as e:
        logger.error(f"Unexpected error fetching CoinGecko data: {e}")
        # ALWAYS try to use stale cache before raising error
        if cache_key in _cache:
            stale_data = _cache[cache_key]["data"]
            age = (datetime.now() - _cache[cache_key]["timestamp"]).total_seconds()
            logger.info(f"Using stale cache (age: {age:.1f}s) due to unexpected error")
            # Return data directly (frontend expects raw CoinGecko response)
            return stale_data
        # Last resort: return empty object (frontend expects raw CoinGecko response)
        logger.warning(f"No cache available for {cache_key}, returning empty fallback")
        return {}

@router.get("/bitcoin")
async def get_bitcoin_data(
    localization: bool = Query(False, description="Include localization data"),
    tickers: bool = Query(False, description="Include tickers data"),
    market_data: bool = Query(True, description="Include market data"),
    community_data: bool = Query(False, description="Include community data"),
    developer_data: bool = Query(False, description="Include developer data"),
    sparkline: bool = Query(False, description="Include sparkline data"),
    cache_ttl: int = Query(900, description="Cache TTL in seconds (default 15min)", ge=60, le=7200),
    x_user: Optional[str] = Header(None, alias="X-User")
):
    """
    Proxy endpoint for CoinGecko Bitcoin data (multi-tenant).

    This endpoint caches responses to avoid rate limiting and provides
    graceful degradation when CoinGecko API is unavailable.

    Uses the CoinGecko API key from the user's config.json.

    Example:
        GET /api/coingecko-proxy/bitcoin?market_data=true

    Headers:
        X-User: Optional user ID (defaults to "demo")

    Returns:
        Bitcoin market data from CoinGecko API (or cached data)
    """
    # Get user (fallback to demo if not provided)
    user = x_user or "demo"

    # Build cache key from parameters (include user for multi-tenant cache)
    cache_key = f"bitcoin_{user}_{localization}_{tickers}_{market_data}_{community_data}_{developer_data}_{sparkline}"

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

    # Get user's CoinGecko API key
    api_key = get_user_coingecko_key(user)

    return await _fetch_with_cache_and_fallback(url, cache_key, cache_ttl, params, api_key)

@router.get("/global")
async def get_global_data(
    cache_ttl: int = Query(900, description="Cache TTL in seconds (default 15min)", ge=60, le=7200),
    x_user: Optional[str] = Header(None, alias="X-User")
):
    """
    Proxy endpoint for CoinGecko global cryptocurrency market data (multi-tenant).
    Used for BTC dominance and market cap data.

    Example:
        GET /api/coingecko-proxy/global

    Headers:
        X-User: Optional user ID (defaults to "demo")

    Returns:
        Global market data from CoinGecko API (or cached data)
    """
    user = x_user or "demo"
    cache_key = f"global_{user}"
    url = "https://api.coingecko.com/api/v3/global"

    # Get user's CoinGecko API key
    api_key = get_user_coingecko_key(user)

    return await _fetch_with_cache_and_fallback(url, cache_key, cache_ttl, None, api_key)

@router.get("/simple/price")
async def get_simple_price(
    ids: str = Query(..., description="Comma-separated coin IDs (e.g., bitcoin,ethereum)"),
    vs_currencies: str = Query("usd", description="Comma-separated fiat currencies"),
    cache_ttl: int = Query(180, description="Cache TTL in seconds (default 3min for prices)", ge=60, le=7200),
    x_user: Optional[str] = Header(None, alias="X-User")
):
    """
    Proxy endpoint for CoinGecko simple price endpoint (multi-tenant).
    Used for getting current prices of multiple coins.

    Example:
        GET /api/coingecko-proxy/simple/price?ids=bitcoin,ethereum&vs_currencies=usd

    Headers:
        X-User: Optional user ID (defaults to "demo")

    Returns:
        Simple price data from CoinGecko API (or cached data)
    """
    user = x_user or "demo"
    cache_key = f"simple_price_{user}_{ids}_{vs_currencies}"
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ids,
        "vs_currencies": vs_currencies
    }

    # Get user's CoinGecko API key
    api_key = get_user_coingecko_key(user)

    return await _fetch_with_cache_and_fallback(url, cache_key, cache_ttl, params, api_key)

@router.get("/market_chart")
async def get_market_chart(
    coin_id: str = Query("bitcoin", description="Coin ID (e.g., bitcoin)"),
    vs_currency: str = Query("usd", description="Fiat currency"),
    days: int = Query(7, description="Number of days", ge=1, le=365),
    interval: str = Query("daily", description="Data interval"),
    cache_ttl: int = Query(900, description="Cache TTL in seconds (default 15min)", ge=60, le=7200),
    x_user: Optional[str] = Header(None, alias="X-User")
):
    """
    Proxy endpoint for CoinGecko market chart endpoint (multi-tenant).
    Used for historical price data and volatility calculations.

    Example:
        GET /api/coingecko-proxy/market_chart?coin_id=bitcoin&vs_currency=usd&days=7&interval=daily

    Headers:
        X-User: Optional user ID (defaults to "demo")

    Returns:
        Market chart data from CoinGecko API (or cached data)
    """
    user = x_user or "demo"
    cache_key = f"market_chart_{user}_{coin_id}_{vs_currency}_{days}_{interval}"
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": vs_currency,
        "days": str(days),
        "interval": interval
    }

    # Get user's CoinGecko API key
    api_key = get_user_coingecko_key(user)

    return await _fetch_with_cache_and_fallback(url, cache_key, cache_ttl, params, api_key)

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
