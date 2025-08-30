# Crypto-Toolbox Scraper Service (Port 8001)

This frontend expects a local backend service that scrapes the indicators from https://crypto-toolbox.vercel.app/signaux and exposes them at `http://127.0.0.1:8001/api/crypto-toolbox`.

## Summary
- Purpose: provide ~30 on-chain/technical indicators (percent, threshold, critical flags) to the dashboard.
- Consumer: `static/modules/onchain-indicators.js` calls `GET /api/crypto-toolbox` on port 8001.
- Format: JSON with `indicators: [...]` where each item has `name`, `value_numeric`, `threshold_numeric`, `raw_threshold`, `threshold_operator`, `in_critical_zone`.

## Quickstart
1) Create venv and install deps

```
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install fastapi uvicorn[standard] httpx beautifulsoup4 lxml
# Optional (if you scrape with Playwright)
pip install playwright
playwright install chromium
```

2) Create `crypto_toolbox_api.py` (example minimal implementation)

```
# crypto_toolbox_api.py
from __future__ import annotations
import re, time
import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

URL = "https://crypto-toolbox.vercel.app/signaux"
CACHE = {"ts": 0.0, "data": None}
TTL = 10 * 60  # 10 minutes

# very lightweight scraper (HTML parsing); switch to Playwright if needed
async def scrape_indicators() -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(URL)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    indicators = []
    # Heuristic parsing: find rows/cards with name, value (%), threshold
    # Adapt selectors to the live page structure if needed
    for card in soup.select("[data-indicator], .indicator, .card"):
        name = card.get_text(" ", strip=True)
        m_val = re.search(r"(\d+(?:\.\d+)?)%", name)
        if not m_val:
            continue
        value = float(m_val.group(1))
        in_critical = value >= 80 or value <= 20
        indicators.append({
            "name": name[:80],
            "value": value,
            "value_numeric": value,
            "threshold_numeric": 80.0,
            "raw_threshold": ">= 80% (or <= 20%)",
            "threshold_operator": ">=",
            "in_critical_zone": in_critical,
        })

    return {
        "success": True,
        "indicators": indicators,
        "total_count": len(indicators),
        "critical_count": sum(1 for i in indicators if i.get("in_critical_zone")),
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": URL,
    }

@app.get("/api/crypto-toolbox")
async def api_crypto_toolbox():
    now = time.time()
    if CACHE["data"] and (now - CACHE["ts"]) < TTL:
        return CACHE["data"]
    data = await scrape_indicators()
    CACHE.update(ts=now, data=data)
    return data

@app.get("/healthz")
async def healthz():
    return {"ok": True}
```

3) Run the service on port 8001

```
uvicorn crypto_toolbox_api:app --host 127.0.0.1 --port 8001 --reload
```

4) Verify
- Open http://127.0.0.1:8001/healthz → `{ "ok": true }`
- Open http://127.0.0.1:8001/api/crypto-toolbox → JSON with `indicators`
- Then refresh the dashboard; the On-Chain section will load all indicators.

## Endpoint Contract
Response (success):
```
{
  "success": true,
  "indicators": [
    {
      "name": "MVRV Ratio",
      "value": 62.1,
      "value_numeric": 62.1,
      "threshold_numeric": 80.0,
      "raw_threshold": ">= 80%",
      "threshold_operator": ">=",
      "in_critical_zone": false
    }
  ],
  "total_count": 30,
  "critical_count": 3,
  "scraped_at": "2025-08-25T12:34:56Z",
  "source": "https://crypto-toolbox.vercel.app/signaux"
}
```

Notes:
- `value_numeric` must be a number (0–100). The UI computes categories and the composite score from these.
- `in_critical_zone` is used for highlighting; your logic can be threshold-based per indicator.
- Add/remove fields as needed; unknown fields are ignored by the UI.

## Troubleshooting
- Only Fear & Greed shows up:
  - The dashboard couldn’t reach port 8001. Start the service and retry.
  - Check browser console network tab for `GET http://127.0.0.1:8001/api/crypto-toolbox` errors.
- CORS issues:
  - Ensure `CORSMiddleware` allows your static origin (file:// or http://127.0.0.1:8000/static).
- Structure changes on the source site:
  - Update selectors in `scrape_indicators()` or switch to Playwright for resilient scraping.

## Optional: Use Playwright for Robustness
- Replace the httpx+BeautifulSoup code with Playwright (wait for selectors, handle dynamic rendering).
- Keep a cache (memory or on-disk) to avoid rate-limiting and speed up the UI.

---
This service is decoupled from the main FastAPI app (port 8000). Keeping it separate avoids coupling the UI load path with scraping latency and rate limits.

