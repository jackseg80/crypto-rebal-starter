# --- imports (en haut du fichier) ---
from __future__ import annotations
from typing import Any, Dict, List
from time import monotonic
from fastapi import FastAPI, Query, Body, Response
from fastapi.middleware.cors import CORSMiddleware

from connectors import cointracking as ct_file
from connectors.cointracking_api import get_current_balances as ct_api_get_current_balances, _debug_probe

from services.rebalance import plan_rebalance
from services.taxonomy import Taxonomy
from api.taxonomy_endpoints import router as taxonomy_router, _merged_aliases, _all_groups

app = FastAPI()
# CORS large pour tests locaux + UI docs/
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],         # important pour POST CSV + preflight
    allow_headers=["*"],
)

# petit cache prix optionnel (si tu l’as déjà chez toi, garde le tien)
_PRICE_CACHE: Dict[str, tuple] = {}  # symbol -> (ts, price)
def _cache_get(cache: dict, key: Any, ttl: int):
    if ttl <= 0: return None
    ent = cache.get(key)
    if not ent: return None
    ts, val = ent
    if monotonic() - ts > ttl:
        cache.pop(key, None)
        return None
    return val
def _cache_set(cache: dict, key: Any, val: Any):
    _PRICE_CACHE[key] = (monotonic(), val)


# ---------- utils ----------
def _parse_min_usd(raw: str | None, default: float = 1.0) -> float:
    try:
        return float(raw) if raw is not None else default
    except Exception:
        return default

def _to_rows(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalise les lignes connecteurs -> {symbol, alias, value_usd, location}"""
    out: List[Dict[str, Any]] = []
    for r in raw or []:
        symbol = r.get("symbol") or r.get("coin") or r.get("name")
        if not symbol:
            continue
        out.append({
            "symbol": str(symbol),
            "alias": (r.get("alias") or r.get("name") or r.get("symbol")),
            "value_usd": float(r.get("value_usd") or r.get("value") or 0.0),
            "location": r.get("location") or r.get("exchange") or "",
        })
    return out

def _norm_primary_symbols(x: Any) -> Dict[str, List[str]]:
    # accepte { BTC: "BTC,TBTC,WBTC" } ou { BTC: ["BTC","TBTC","WBTC"] }
    out: Dict[str, List[str]] = {}
    if isinstance(x, dict):
        for g, v in x.items():
            if isinstance(v, str):
                out[g] = [s.strip() for s in v.split(",") if s.strip()]
            elif isinstance(v, list):
                out[g] = [str(s).strip() for s in v if str(s).strip()]
    return out


# ---------- source resolver ----------
async def resolve_current_balances(source: str) -> Dict[str, Any]:
    """
    Retourne {source_used, items:[{symbol, value_usd, ...}]}
    """
    if source == "stub":
        # mini portefeuille de démo
        items = [
            {"symbol": "BTC", "value_usd": 117000.0},
            {"symbol": "ETH", "value_usd": 60000.0},
            {"symbol": "USDT", "value_usd": 5000.0},
            {"symbol": "USDC", "value_usd": 900.0},
            {"symbol": "SOL",  "value_usd": 3000.0},
            {"symbol": "LINK", "value_usd": 7000.0},
            {"symbol": "AAVE", "value_usd": 4500.0},
            {"symbol": "DOGE", "value_usd": 5000.0},
            {"symbol": "EUR",  "value_usd": 120.0},
        ]
        return {"source_used": "stub", "items": items}

    if source == "cointracking":
        res = await ct_file.get_current_balances(source="cointracking")
        return {"source_used": "cointracking", "items": res.get("items", []) if isinstance(res, dict) else (res or [])}

    if source == "cointracking_api":
        res = await ct_api_get_current_balances()
        return {"source_used": "cointracking_api", "items": res.get("items", []) if isinstance(res, dict) else (res or [])}

    # fallback: cointracking (CSV)
    res = await ct_file.get_current_balances(source="cointracking")
    return {"source_used": "cointracking", "items": res.get("items", []) if isinstance(res, dict) else (res or [])}


# ---------- health ----------
@app.get("/healthz")
async def healthz():
    return {"ok": True}


# ---------- balances ----------
@app.get("/balances/current")
async def balances_current(
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0)
):
    res = await resolve_current_balances(source=source)
    rows = [r for r in _to_rows(res.get("items", [])) if float(r.get("value_usd") or 0.0) >= float(min_usd)]
    return {"source_used": res.get("source_used"), "items": rows}


# ---------- rebalance (JSON) ----------
@app.post("/rebalance/plan")
async def rebalance_plan(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
    pricing: str = Query("local"),   # local | auto
    payload: Dict[str, Any] = Body(...)
):
    min_usd = _parse_min_usd(min_usd_raw, default=1.0)

    # portefeuille
    res = await resolve_current_balances(source=source)
    rows = [r for r in _to_rows(res.get("items", [])) if float(r.get("value_usd") or 0.0) >= min_usd]

    # targets
    targets_raw = payload.get("group_targets_pct") or payload.get("targets") or {}
    group_targets_pct: Dict[str, float] = {}
    if isinstance(targets_raw, dict):
        group_targets_pct = {str(k): float(v) for k, v in targets_raw.items()}
    elif isinstance(targets_raw, list):
        for it in targets_raw:
            g = str(it.get("group"))
            p = float(it.get("weight_pct", 0.0))
            if g: group_targets_pct[g] = p

    primary_symbols = _norm_primary_symbols(payload.get("primary_symbols"))

    plan = plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=payload.get("sub_allocation", "proportional"),
        primary_symbols=primary_symbols,
        min_trade_usd=float(payload.get("min_trade_usd", 25.0)),
    )

    # enrichissement prix (selon "pricing")
    plan = _enrich_actions_with_prices(plan, rows, pricing_mode=pricing)

    # meta pour UI
    plan["meta"] = {
        "source_used": res.get("source_used"),
        "items_count": len(rows)
    }
    return plan


# ---------- rebalance (CSV) ----------
@app.options("/rebalance/plan.csv")
async def rebalance_plan_csv_preflight():
    # pour laisser passer les preflight CORS
    return Response(status_code=200)

@app.post("/rebalance/plan.csv")
async def rebalance_plan_csv(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
    pricing: str = Query("local"),
    payload: Dict[str, Any] = Body(...)
):
    # réutilise le JSON pour construire le CSV
    plan = await rebalance_plan(source=source, min_usd_raw=min_usd_raw, pricing=pricing, payload=payload)
    actions = plan.get("actions") or []
    csv_text = _to_csv(actions)
    headers = {"Content-Disposition": 'attachment; filename="rebalance-actions.csv"'}
    return Response(content=csv_text, media_type="text/csv", headers=headers)


# ---------- helpers prix + csv ----------
def _enrich_actions_with_prices(plan: Dict[str, Any], rows: List[Dict[str, Any]], pricing_mode: str = "local") -> Dict[str, Any]:
    """
    Si pricing_mode = "local", on dérive des prix simples à partir de rows (ou via cache local).
    Si "auto", garde ton mécanisme existant (ex: pricing.py externe). Ici on met juste un placeholder local.
    """
    # mini map symbol->price (local) = total_usd / amount (si dispo); sinon laisse None
    price_map: Dict[str, float] = {}
    # si tu as un fichier services/pricing.py avec get_prices, tu peux l'appeler ici selon pricing_mode

    # enrichit plan.actions
    for a in plan.get("actions", []) or []:
        sym = a.get("symbol")
        if sym and a.get("usd") and not a.get("price_used"):
            price = price_map.get(sym)
            if price:
                a["price_used"] = float(price)
                try:
                    a["est_quantity"] = round(float(a["usd"]) / float(price), 8)
                except Exception:
                    pass
    return plan

def _to_csv(actions: List[Dict[str, Any]]) -> str:
    lines = ["group,alias,symbol,action,usd,est_quantity,price_used"]
    for a in actions or []:
        lines.append("{},{},{},{},{:.2f},{}{}".format(
            a.get("group",""),
            a.get("alias",""),
            a.get("symbol",""),
            a.get("action",""),
            float(a.get("usd") or 0.0),
            ("" if a.get("est_quantity") is None else f"{a.get('est_quantity')}"),
            ("" if a.get("price_used")   is None else f",{a.get('price_used')}")
        ))
    return "\n".join(lines)

# inclure les routes taxonomie
app.include_router(taxonomy_router)
