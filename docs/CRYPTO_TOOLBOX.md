# Crypto-Toolbox API Integration

## Overview

This module scrapes cryptocurrency market indicators from [crypto-toolbox.vercel.app](https://crypto-toolbox.vercel.app/signaux) using Playwright and exposes them via FastAPI REST endpoints.

**Purpose**: Provide real-time risk indicators (BMO, MVRV, Puell Multiple, etc.) for decision-making in the portfolio management system.

---

## Architecture

### Technology Stack
- **FastAPI** (async REST API)
- **Playwright** (browser automation, async_api)
- **Chromium** (headless browser)

### Design Principles
- **Single browser instance**: Shared across all requests (launched at startup)
- **Concurrency control**: Semaphore(2) limits simultaneous scrapes
- **Cache-first**: 30-minute TTL to reduce upstream load
- **Graceful degradation**: Browser auto-recovery if crashed

---

## API Endpoints

### `GET /api/crypto-toolbox`

Get crypto-toolbox indicators (cached or fresh).

**Query Parameters**:
- `force` (bool, optional): Force refresh bypassing cache (default: `false`)

**Response** (200 OK):
```json
{
    "success": true,
    "indicators": [
        {
            "name": "MVRV Z-Score",
            "value": "2.34",
            "value_numeric": 2.34,
            "threshold": ">=7",
            "threshold_numeric": 7.0,
            "threshold_operator": ">=",
            "in_critical_zone": false,
            "raw_value": "2.34",
            "raw_threshold": ">=7 (euphoria)"
        }
    ],
    "total_count": 15,
    "critical_count": 3,
    "scraped_at": "2025-10-02T12:34:56.789",
    "source": "crypto-toolbox.vercel.app",
    "cached": true,
    "cache_age_seconds": 456
}
```

**Error Response** (502 Bad Gateway):
```json
{
    "detail": "Upstream scraping error: timeout"
}
```

---

### `POST /api/crypto-toolbox/refresh`

Force refresh data (bypass cache).

**Response**: Same as `GET` with `cached: false`

---

### `GET /api/crypto-toolbox/health`

Health check endpoint.

**Response** (200 OK):
```json
{
    "status": "healthy",
    "browser_connected": true,
    "cache_status": "active",
    "cache_age_seconds": 456,
    "timestamp": "2025-10-02T12:34:56.789"
}
```

---

### `POST /api/crypto-toolbox/cache/clear`

Clear cache (admin/debug).

**Response** (200 OK):
```json
{
    "message": "Cache cleared successfully"
}
```

---

## Configuration

### Environment Variables
- `CRYPTO_TOOLBOX_URL` (optional): Target URL (default: `https://crypto-toolbox.vercel.app/signaux`)
- `CRYPTO_TOOLBOX_CACHE_TTL` (optional): Cache TTL in seconds (default: `1800`)

### Cache Settings
- **TTL**: 30 minutes (1800 seconds)
- **Strategy**: In-memory (no Redis in dev)
- **Lock**: asyncio.Lock prevents thundering herd

### Concurrency
- **Browser**: 1 shared instance (re-launched if crashed)
- **Pages**: Max 2 concurrent (Semaphore)
- **Workers**: **Single-worker Uvicorn only** (Playwright state is not multi-process safe)

---

## Dependencies

### Python Packages
```txt
playwright==1.46.0
fastapi>=0.104.0
uvicorn>=0.24.0
```

### System Requirements
**Chromium browser** must be installed:
```bash
# After pip install playwright
playwright install chromium
```

**Docker**: Use Playwright official image or install deps:
```dockerfile
RUN playwright install chromium --with-deps
```

---

## Lifecycle Management

### Startup Sequence
1. **FastAPI app starts** (`api/main.py`)
2. **ML models initialize** (3s delay, background task)
3. **Governance Engine** initialized
4. **Alert Engine** scheduler started
5. **Playwright browser** initialized (optional, non-blocking)
   - Only if `api/crypto_toolbox_endpoints` successfully imported
   - If fails → logs warning, browser lazy-launched on first request
   - Memory footprint: ~200 MB (Chromium process)

**Order of initialization** (in `api/startup.py`):
```python
models_count = await initialize_ml_models()           # 1st
governance_ok = await initialize_governance_engine()  # 2nd
alerts_ok = await initialize_alert_engine()           # 3rd
playwright_ok = await initialize_playwright_browser() # 4th (optional)
```

**Memory impact**:
- Baseline (FastAPI + ML): ~300-400 MB
- With Playwright browser: ~500-600 MB
- Per request overhead: ~1-2 MB (page context)

### Shutdown Sequence
1. **FastAPI shutdown event** triggered (SIGTERM/SIGINT)
2. **Alert Engine** scheduler stopped gracefully
3. **Playwright browser** closed (if initialized)
   - All pages closed
   - Browser process terminated
   - Playwright instance stopped
4. **Cleanup complete** (logs confirmation)

### Recovery & Resilience
- **Browser crash**: Auto re-launch on next request
  - `_ensure_browser()` checks `browser.is_connected()`
  - New browser spawned if disconnected
  - Request retried automatically
- **Import failure**: Graceful degradation
  - Startup continues even if Playwright fails
  - Logs warning, endpoints return 502 until browser available
- **Page timeout**: 15-second limit per scrape
  - Request fails with HTTPException 502
  - Cache serves stale data if available

---

## Special Cases

### BMO (par Prof. Chaîne)
This indicator has **multiple sub-indicators** with different thresholds:
- Each sub-indicator gets a separate entry
- Format: `"BMO (par Prof. Chaîne) (Label)"`
- Example: `"BMO (par Prof. Chaîne) (Short-Term)"`

### Threshold Operators
Supported comparison operators:
- `>=` : Greater than or equal
- `<=` : Less than or equal
- `>` : Greater than
- `<` : Less than

### Parsing Edge Cases
- Comma decimal separators → normalized to periods
- Newlines in raw values → stripped
- Missing thresholds → skipped (not included in response)

---

## Memory & Performance

### Memory Footprint
- **Browser process**: ~150-200 MB (Chromium headless)
- **Cache**: ~10-50 KB (JSON in-memory)
- **Total**: ~200 MB per worker

### Latency
- **Cache hit**: <5 ms
- **Cache miss (scrape)**: 3-5 seconds
- **Timeout**: 15 seconds (page load)

### Scaling
- **Vertical**: Single worker, handles ~50 req/s (mostly cached)
- **Horizontal**: Multiple containers (1 worker each) behind load balancer
- ⚠️ **Do NOT use `--workers > 1`** with Playwright (shared browser state issue)

---

## Development

### Local Testing
```bash
# Start dev server
uvicorn api.main:app --reload --port 8000

# Test endpoint
curl http://localhost:8000/api/crypto-toolbox

# Force refresh
curl http://localhost:8000/api/crypto-toolbox?force=true

# Health check
curl http://localhost:8000/api/crypto-toolbox/health
```

### Debug Logs
```python
import logging
logging.getLogger("api.crypto_toolbox_endpoints").setLevel(logging.DEBUG)
```

---

## Production Deployment

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install Playwright + Chromium
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium --with-deps

COPY . .
EXPOSE 8000

# Single worker (Playwright requirement)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### systemd (Linux)
```ini
[Unit]
Description=Crypto Rebal API
After=network.target

[Service]
WorkingDirectory=/opt/crypto-rebal
ExecStart=/opt/crypto-rebal/.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Migration Status

### Current State
- ✅ Router skeleton created (`api/crypto_toolbox_endpoints.py`)
- ✅ Contract documented (JSON schema, invariants)
- ✅ Lifecycle hooks integrated (`api/startup.py`)
- ✅ **Parsing logic ported from Flask** (100% parity)
  - `_parse_comparison()` function (regex-based)
  - BMO special handling (multiple sub-indicators)
  - Operator evaluation (>=, <=, >, <)
  - Async Playwright calls (sync → async migration)
- ⏳ Integration in `api/main.py` (Commit 4, behind feature flag)
- ⏳ A/B testing & validation (Commit 6)
- ⏳ Legacy Flask removal (Commit 8, after A/B validation)

### Parsing Parity

**Validated** against `crypto_toolbox_api.py`:
- ✅ Regex patterns identical
- ✅ BMO multi-indicator logic identical
- ✅ Numeric extraction identical
- ✅ Threshold parsing identical
- ✅ JSON structure identical

**See**: `docs/CRYPTO_TOOLBOX_PARITY.md` for detailed checklist

### Rollback Strategy
- **Before Commit 4**: No impact (router not included)
- **Commit 4-7**: Feature flag `CRYPTO_TOOLBOX_NEW=0` reverts to Flask
- **After Commit 8**: Revert commit to restore Flask proxy

---

## References

- **Original Flask implementation**: `crypto_toolbox_api.py` (to be removed in Commit 8)
- **Proxy endpoint**: `api/main.py:432-447` (to be removed in Commit 8)
- **Parity validation**: `docs/CRYPTO_TOOLBOX_PARITY.md`
- **Target site**: https://crypto-toolbox.vercel.app/signaux

---

**Last updated**: 2025-10-02
**Status**: Phase 3 - Parsing Logic Ported (Commit 3)
