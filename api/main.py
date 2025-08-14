# api/main.py
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware

# Connecteurs
from connectors import cointracking as ct_file
from connectors.cointracking_api import get_current_balances as ct_api_get_current_balances, _debug_probe

from services.rebalance import plan_rebalance
from services.taxonomy import Taxonomy
from api.taxonomy_endpoints import router as taxonomy_router

app = FastAPI(title="Crypto Rebal Starter")

# CORS (config via .env si besoin)
import os
CORS_ORIGINS = (os.getenv("CORS_ORIGINS") or "").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(taxonomy_router, prefix="/taxonomy")

# --- Résolveur de source -----------------------------------------------------
async def resolve_current_balances(source: str = "cointracking") -> Dict[str, Any]:
    s = (source or "").strip().lower()
    if s in ("cointracking_api", "ctapi", "ct_api"):
        res = await ct_api_get_current_balances()
        if isinstance(res, dict):
            return res
        return {"source_used": "cointracking_api", "items": res or []}
    else:
        res = await ct_file.get_current_balances(source="cointracking")
        if isinstance(res, dict):
            res.setdefault("source_used", "cointracking")
            return res
        return {"source_used": "cointracking", "items": res or []}

# --- Utils -------------------------------------------------------------------
def _to_rows(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalise les lignes vers:
      {symbol: str, alias?: str, value_usd: float, location?: str}
    """
    out: List[Dict[str, Any]] = []
    for r in raw or []:
        if not isinstance(r, dict):
            continue
        symbol = (r.get("symbol") or r.get("coin") or r.get("name") or "").strip().upper()
        if not symbol:
            continue

        v = r.get("value_usd")
        if v is None: v = r.get("usd_value")
        if v is None: v = r.get("usd")
        if v is None: v = r.get("value")
        try:
            value_usd = float(v or 0.0)
        except Exception:
            value_usd = 0.0

        out.append({
            "symbol": symbol,
            "alias": (r.get("alias") or r.get("name") or symbol).strip(),
            "value_usd": value_usd,
            "location": r.get("location"),
        })
    return out

def _parse_min_usd(s: str | None, default: float = 0.0) -> float:
    if not s: return default
    try:
        return float(str(s).replace(",", "."))
    except Exception:
        return default

# --- Endpoints ---------------------------------------------------------------
@app.get("/healthz")
async def healthz():
    return {"ok": True}

@app.get("/debug/ctapi")
async def debug_ctapi():
    return _debug_probe()

@app.get("/balances/current")
async def balances_current(
    source: str = Query("cointracking"),
    min_usd: float = Query(0.0),
):
    res = await resolve_current_balances(source=source)
    raw = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_rows(raw)
    rows = [r for r in rows if float(r.get("value_usd") or 0.0) >= min_usd]
    return {"source_used": res.get("source_used"), "items": rows}

@app.get("/portfolio/groups")
async def portfolio_groups(
    source: str = Query("cointracking"),
    min_usd: float = Query(0.0),
):
    tx = Taxonomy.load()
    res = await resolve_current_balances(source=source)
    raw = res.get("items", []) if isinstance(res, dict) else (res or [])

    # normalisation
    rows: List[Dict[str, Any]] = []
    for it in raw:
        symbol = (it.get("symbol") or it.get("name") or it.get("coin") or "").strip().upper()
        alias = (it.get("alias") or it.get("name") or symbol or "").strip()
        val = it.get("value_usd")
        if val is None: val = it.get("usd_value")
        value_usd = float(val or 0.0)
        rows.append({"symbol": symbol, "alias": alias, "value_usd": value_usd, "location": it.get("location")})

    # filtre & total
    items = [r for r in rows if float(r.get("value_usd") or 0.0) >= float(min_usd or 0.0)]
    total_usd = sum(r["value_usd"] for r in items) or 0.0

    # groupes + unknowns
    groups = tx.group_aliases(items)
    known_aliases = set(tx.all_aliases())

    unknown_aliases_acc: Dict[str, float] = {}
    alias_sum: Dict[str, Dict[str, Any]] = {}
    for r in items:
        a = (r.get("alias") or r.get("symbol") or "").strip()
        v = float(r.get("value_usd") or 0.0)
        if not a:
            continue
        entry = alias_sum.setdefault(a, {"alias": a, "total_usd": 0.0, "coins": []})
        entry["total_usd"] += v
        entry["coins"].append({
            "symbol": r["symbol"],
            "alias": a,
            "amount": 0.0,
            "value_usd": v,
            "price_usd": None,
            "group": tx.pick_group_for_alias(a),
        })
        if a not in known_aliases:
            unknown_aliases_acc[a] = unknown_aliases_acc.get(a, 0.0) + v

    alias_summary_sorted = sorted(alias_sum.values(), key=lambda x: -x["total_usd"])
    unknown_aliases_sorted = sorted(unknown_aliases_acc.keys())

    return {
        "source_used": res.get("source_used"),
        "total_usd": round(total_usd, 2),
        "groups": groups,
        "alias_summary": alias_summary_sorted,
        "unknown_aliases": unknown_aliases_sorted,
    }

@app.post("/rebalance/plan")
async def rebalance_plan(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
    payload: Dict[str, Any] = Body(...),
):
    # parse filtre
    min_usd = _parse_min_usd(min_usd_raw, default=1.0)

    # portefeuille courant
    res = await resolve_current_balances(source=source)
    raw = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_rows(raw)
    rows = [r for r in rows if float(r.get("value_usd") or 0.0) >= min_usd]

    # compat "group_targets_pct" ou "targets"
    targets_raw = payload.get("group_targets_pct") or payload.get("targets")
    group_targets_pct: Dict[str, float] = {}
    if isinstance(targets_raw, dict):
        group_targets_pct = {str(k): float(v) for k, v in targets_raw.items()}
    elif isinstance(targets_raw, list):
        for it in targets_raw:
            g = str(it.get("group"))
            p = float(it.get("weight_pct", 0.0))
            if g:
                group_targets_pct[g] = p

    plan = plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=payload.get("sub_allocation", "proportional"),
        primary_symbols=payload.get("primary_symbols"),
        min_trade_usd=float(payload.get("min_trade_usd", 25.0)),
    )
    return plan

# CSV
from fastapi.responses import PlainTextResponse
def _to_csv(rows: List[Dict[str, Any]]) -> str:
    cols = ["group","alias","symbol","action","usd","est_quantity","price_used"]
    out = [",".join(cols)]
    for r in rows:
        out.append(",".join([
            str(r.get("group","")),
            str(r.get("alias","")),
            str(r.get("symbol","")),
            str(r.get("action","")),
            f'{float(r.get("usd") or 0.0):.2f}',
            "" if r.get("est_quantity") is None else f'{float(r["est_quantity"]):.8f}',
            "" if r.get("price_used") is None else f'{float(r["price_used"]):.6f}',
        ]))
    return "\n".join(out)

@app.post("/rebalance/plan.csv", response_class=PlainTextResponse)
async def rebalance_plan_csv(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
    payload: Dict[str, Any] = Body(...),
):
    plan = await rebalance_plan(source=source, min_usd_raw=min_usd_raw, payload=payload)
    return _to_csv(plan.get("actions") or [])
