
from __future__ import annotations
import os
import csv
from typing import Any, Dict, List, Optional

# Optional API connector (not used for 'csv'/'stub' paths here but left for completeness)
try:
    from .cointracking_api import get_balances_via_api  # type: ignore
except Exception:
    get_balances_via_api = None  # type: ignore

# ---------------- Demo data ----------------
_DEMO_ITEMS: List[Dict[str, Any]] = [
    {"symbol": "BTC", "amount": 1.2345, "value_usd": 75000.0, "location": "Demo"},
    {"symbol": "ETH", "amount": 20.0,   "value_usd": 60000.0, "location": "Demo"},
    {"symbol": "USDT","amount": 5000.0, "value_usd": 5000.0,  "location": "Demo"},
    {"symbol": "USDC","amount": 3000.0, "value_usd": 3000.0,  "location": "Demo"},
    {"symbol": "SOL", "amount": 250.0,  "value_usd": 17500.0, "location": "Demo"},
    {"symbol": "ADA", "amount": 5000.0, "value_usd": 1500.0,  "location": "Demo"},
    {"symbol": "LINK","amount": 800.0,  "value_usd": 12000.0, "location": "Demo"},
    {"symbol": "AAVE","amount": 120.0,  "value_usd": 12000.0, "location": "Demo"},
    {"symbol": "DOGE","amount": 300000, "value_usd": 6000.0,  "location": "Demo"},
]

def get_demo_balances() -> Dict[str, Any]:
    return {"source_used": "stub", "items": list(_DEMO_ITEMS)}

# ---------------- CSV helpers ----------------
def _norm_float(s: Any) -> float:
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    txt = str(s).strip().replace("\xa0", "").replace(" ", "")
    txt = txt.replace("'", "")  # thousands separator in some locales
    # Handle "1,234.56" and "1234,56"
    if "," in txt and "." not in txt:
        txt = txt.replace(",", ".")
    if "," in txt and "." in txt:
        txt = txt.replace(",", "")
    try:
        return float(txt)
    except Exception:
        return 0.0

def _read_csv_safe(path: Optional[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path or not os.path.exists(path):
        return rows
    # Keep file open while consuming DictReader
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        except Exception:
            class _D:
                delimiter = ","
            dialect = _D()
        reader = csv.DictReader(f, dialect=dialect)
        for row in reader:
            norm = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v) for k,v in row.items() }
            rows.append(norm)
    return rows

# Accept various header names exported by CoinTracking
_SYMBOL_KEYS = (
    "Ticker", "Currency", "Coin", "Symbol", "Asset",
    "ticker", "currency", "coin", "symbol", "asset"
)
_AMOUNT_KEYS = ("Amount", "amount", "Qty", "Quantity", "quantity")
_VALUE_USD_KEYS = (
    "Value in USD", "Value (USD)", "USD Value",
    "Current Value (USD)", "Total Value (USD)",
    "value_usd", "Value", "value"
)
_PRICE_USD_KEYS = ("Price (USD)", "price_usd", "Price", "price")

def _get_first(row: Dict[str, Any], keys) -> Optional[str]:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None

def _guess_symbol(row: Dict[str, Any]) -> Optional[str]:
    val = _get_first(row, _SYMBOL_KEYS)
    return str(val).strip().upper() if val is not None else None

def _guess_amount(row: Dict[str, Any]) -> float:
    val = _get_first(row, _AMOUNT_KEYS)
    return _norm_float(val) if val is not None else 0.0

def _guess_value_usd(row: Dict[str, Any]) -> float:
    val = _get_first(row, _VALUE_USD_KEYS)
    if val is not None:
        return _norm_float(val)
    amt = _guess_amount(row)
    price = _get_first(row, _PRICE_USD_KEYS)
    if price is not None:
        return _norm_float(price) * amt
    return 0.0

def _aggregate_by_symbol(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    agg: Dict[str, Dict[str, float]] = {}
    for r in rows:
        sym = _guess_symbol(r)
        if not sym:
            continue
        amt = _guess_amount(r)
        val = _guess_value_usd(r)
        if sym not in agg:
            agg[sym] = {"amount": 0.0, "value_usd": 0.0}
        agg[sym]["amount"] += amt
        agg[sym]["value_usd"] += val
    out = [ {"symbol": s, "amount": round(v["amount"], 12), "value_usd": round(v["value_usd"], 8), "location": "CoinTracking"} for s, v in agg.items() ]
    out.sort(key=lambda x: x.get("value_usd", 0.0), reverse=True)
    return out

def _resolve_csv_path(candidates):
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

def get_current_balances_from_csv() -> Dict[str, Any]:
    env_cur = os.getenv("COINTRACKING_CSV")
    default_cur = "CoinTracking - Current Balance_mini.csv"
    candidates_cur = [env_cur, os.path.join("data", default_cur), default_cur]
    p_cur = _resolve_csv_path([c for c in candidates_cur if c])
    rows_cur = _read_csv_safe(p_cur)
    items = _aggregate_by_symbol(rows_cur)
    return {"source_used": "cointracking", "items": items}

# ---------------- Dispatcher ----------------
async def get_current_balances(source: str = "cointracking") -> Dict[str, Any]:
    s = (source or "").lower()

    if s in ("stub", "demo"):
        return get_demo_balances()

    if s == "cointracking":
        return get_current_balances_from_csv()

    if s == "cointracking_api":
        if get_balances_via_api is None:
            return {"source_used": "cointracking_api", "items": []}
        res = await get_balances_via_api()
        return res or {"source_used": "cointracking_api", "items": []}

    # fallback to CSV
    return get_current_balances_from_csv()
