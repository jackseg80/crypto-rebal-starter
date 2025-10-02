"""
Crypto-Toolbox API Router (FastAPI Native)

Scrapes crypto-toolbox.vercel.app indicators with Playwright and exposes them via REST API.

## JSON Response Contract

### GET /api/crypto-toolbox
```json
{
    "success": true,
    "indicators": [
        {
            "name": "Indicator Name",
            "value": "123.45",
            "value_numeric": 123.45,
            "threshold": ">=80",
            "threshold_numeric": 80.0,
            "threshold_operator": ">=",
            "in_critical_zone": true,
            "raw_value": "123.45\n(some text)",
            "raw_threshold": ">=80 (critical)"
        }
    ],
    "total_count": 15,
    "critical_count": 3,
    "scraped_at": "2025-10-02T12:34:56.789",
    "source": "crypto-toolbox.vercel.app",
    "cached": false,
    "cache_age_seconds": 0
}
```

### Special Cases
- **BMO (par Prof. Chaîne)**: Multiple sub-indicators with different thresholds
- **Threshold operators**: >=, <=, >, <
- **Cache**: 30 minutes TTL, shared across requests

## Invariants
- `total_count` = len(indicators)
- `critical_count` = count(in_critical_zone == true)
- `value_numeric` and `threshold_numeric` must be floats
- `cached` = true when served from cache
- `cache_age_seconds` = 0 when freshly scraped

## Dependencies
- Playwright (async_api) for browser automation
- Chromium browser installed via `playwright install chromium`

## Lifecycle
- Browser launched at startup (shared across requests)
- Browser closed at shutdown
- Semaphore(2) to limit concurrent scraping

## Cache Strategy
- In-memory cache (no Redis in dev)
- TTL: 1800 seconds (30 minutes)
- asyncio.Lock to prevent thundering herd on refresh
- Force refresh via `force=true` query parameter
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/api/crypto-toolbox", tags=["Crypto Toolbox"])

# Global state (module-level, safe for single-worker Uvicorn)
_browser: Optional[Browser] = None
_playwright_instance = None
_lock_refresh = asyncio.Lock()
_cache: Dict[str, Any] = {"data": None, "timestamp": 0.0}
_concurrency = asyncio.Semaphore(2)  # Max 2 concurrent scrapes

# Configuration
CACHE_TTL = 1800  # 30 minutes
CRYPTO_TOOLBOX_URL = "https://crypto-toolbox.vercel.app/signaux"


# ============================================================================
# Lifecycle Hooks (called from api/startup.py)
# ============================================================================

async def startup_playwright():
    """
    Initialize Playwright and launch browser (called at app startup).

    Notes:
    - Launches Chromium in headless mode
    - Reuses single browser instance across requests
    - Safe for single-worker Uvicorn deployment
    """
    global _browser, _playwright_instance

    if _browser is not None:
        logger.warning("Playwright browser already initialized")
        return

    try:
        logger.info("🎭 Initializing Playwright browser...")
        _playwright_instance = await async_playwright().start()
        _browser = await _playwright_instance.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        logger.info("✅ Playwright browser launched successfully")
    except Exception as e:
        logger.error(f"❌ Failed to launch Playwright browser: {e}")
        raise


async def shutdown_playwright():
    """
    Close browser and cleanup Playwright (called at app shutdown).
    """
    global _browser, _playwright_instance

    if _browser:
        try:
            logger.info("🛑 Closing Playwright browser...")
            await _browser.close()
            logger.info("✅ Playwright browser closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing browser: {e}")
        finally:
            _browser = None

    if _playwright_instance:
        try:
            await _playwright_instance.stop()
        except Exception as e:
            logger.warning(f"⚠️ Error stopping Playwright: {e}")
        finally:
            _playwright_instance = None


async def _ensure_browser() -> Browser:
    """
    Ensure browser is available, re-launch if crashed.

    Returns:
        Browser instance

    Raises:
        RuntimeError: If browser cannot be initialized
    """
    global _browser

    if _browser is None or not _browser.is_connected():
        logger.warning("⚠️ Browser not connected, re-launching...")
        await startup_playwright()

    if _browser is None:
        raise RuntimeError("Failed to initialize Playwright browser")

    return _browser


# ============================================================================
# Scraping Logic (TODO: Port from Flask)
# ============================================================================

async def _scrape_crypto_toolbox() -> Dict[str, Any]:
    """
    Scrape crypto-toolbox.vercel.app indicators.

    Returns:
        Dict with structure defined in module docstring

    Raises:
        Exception: If scraping fails

    TODO:
    - Port parsing logic from crypto_toolbox_api.py
    - Handle BMO special case (multiple sub-indicators)
    - Parse comparison operators (>=, <=, >, <)
    - Extract numeric values and thresholds
    - Calculate in_critical_zone for each indicator
    """
    browser = await _ensure_browser()

    async with _concurrency:
        page: Page = await browser.new_page()
        try:
            logger.info(f"🌐 Loading {CRYPTO_TOOLBOX_URL}")
            await page.goto(CRYPTO_TOOLBOX_URL, timeout=15000)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)  # Extra delay for client-side hydration

            # TODO: Port parsing logic here
            # rows = await page.locator("table tbody tr").all()
            # indicators = []
            # for row in rows:
            #     cells = await row.locator("td").all()
            #     # ... parsing logic ...

            # Placeholder response
            indicators = []

            return {
                "success": True,
                "indicators": indicators,
                "total_count": len(indicators),
                "critical_count": sum(1 for ind in indicators if ind.get("in_critical_zone")),
                "scraped_at": datetime.now().isoformat(),
                "source": "crypto-toolbox.vercel.app"
            }

        finally:
            await page.close()


async def _get_data(force: bool = False) -> Dict[str, Any]:
    """
    Get crypto-toolbox data (cached or fresh).

    Args:
        force: Force refresh bypassing cache

    Returns:
        Data dict with cache metadata
    """
    now = time.time()

    # Check cache (unless force refresh)
    if not force and _cache["data"] and (now - _cache["timestamp"] < CACHE_TTL):
        age = int(now - _cache["timestamp"])
        logger.info(f"💾 Returning cached data (age: {age}s)")
        return {
            **_cache["data"],
            "cached": True,
            "cache_age_seconds": age
        }

    # Prevent thundering herd during refresh
    async with _lock_refresh:
        # Double-check cache after acquiring lock
        now = time.time()
        if not force and _cache["data"] and (now - _cache["timestamp"] < CACHE_TTL):
            age = int(now - _cache["timestamp"])
            return {
                **_cache["data"],
                "cached": True,
                "cache_age_seconds": age
            }

        # Scrape fresh data
        logger.info("🔄 Scraping fresh data...")
        data = await _scrape_crypto_toolbox()

        # Update cache
        _cache["data"] = data
        _cache["timestamp"] = time.time()

        return {
            **data,
            "cached": False,
            "cache_age_seconds": 0
        }


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("")
async def get_crypto_toolbox_data(force: bool = Query(False, description="Force refresh bypassing cache")):
    """
    Get crypto-toolbox indicators.

    Query Parameters:
        force: Force refresh (default: false)

    Returns:
        JSON with indicators and cache metadata

    Raises:
        HTTPException 502: If scraping fails
    """
    try:
        return await _get_data(force=force)
    except Exception as e:
        logger.exception("❌ Crypto-toolbox scraping error")
        raise HTTPException(
            status_code=502,
            detail=f"Upstream scraping error: {str(e)}"
        )


@router.post("/refresh")
async def force_refresh():
    """
    Force refresh crypto-toolbox data (bypass cache).

    Returns:
        Fresh data with cache_age_seconds=0
    """
    return await _get_data(force=True)


@router.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        Status and cache metadata
    """
    cache_age = int(time.time() - _cache["timestamp"]) if _cache["timestamp"] else None
    browser_connected = _browser is not None and _browser.is_connected()

    return {
        "status": "healthy" if browser_connected else "degraded",
        "browser_connected": browser_connected,
        "cache_status": "active" if _cache["data"] else "empty",
        "cache_age_seconds": cache_age,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/cache/clear")
async def clear_cache():
    """
    Clear cache (admin/debug endpoint).

    Returns:
        Success message
    """
    global _cache
    _cache = {"data": None, "timestamp": 0.0}
    logger.info("🧹 Cache cleared")
    return {"message": "Cache cleared successfully"}
