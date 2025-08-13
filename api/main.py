# api/main.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from connectors.cointracking import get_current_balances
from api.taxonomy import Taxonomy
from api.taxonomy_endpoints import router as taxonomy_router
from services.rebalance import plan_rebalance, _group_for_alias

app = FastAPI(title="Crypto Rebalancer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# IMPORTANT : le router a des chemins explicites (/taxonomy, /taxonomy/aliases, ...)
# donc on l’inclut sans prefix.
app.include_router(taxonomy_router)

def _to_rows_with_alias(rows: List[Dict[str, Any]], tx: Taxonomy) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        sym = str(r.get("symbol", "")).upper()
        usd = float(r.get("usd_value") or r.get("value_usd") or 0.0)
        alias = tx.aliases.get(sym, sym)
        group = _group_for_alias(alias)
        out.append({
            "symbol": sym, "alias": alias, "group": group, "value_usd": usd
        })
    return out

@app.get("/portfolio/groups")
async def portfolio_groups(
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0),
) -> Dict[str, Any]:
    tx = Taxonomy.load()
    res = await get_current_balances(source=source)
    raw_rows = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_rows_with_alias(raw_rows, tx)
    rows = [r for r in rows if r["value_usd"] >= float(min_usd)]

    total = sum(r["value_usd"] for r in rows)
    by_group: Dict[str, List[Dict[str, Any]]] = {g: [] for g in tx.groups_order}
    for r in rows:
        by_group.setdefault(r["group"], []).append(r)

    groups_out: List[Dict[str, Any]] = []
    for g in tx.groups_order:
        items = by_group.get(g, [])
        g_total = sum(x["value_usd"] for x in items)
        groups_out.append({
            "group": g,
            "total_usd": round(g_total, 2),
            "items": [
                {
                    "symbol": x["symbol"],
                    "alias": x["alias"],
                    "amount": 0.0,
                    "value_usd": round(x["value_usd"], 2),
                    "location": None,
                } for x in items
            ],
            "weight_pct": round(100.0 * g_total / total, 6) if total > 0 else 0.0
        })

    alias_summary: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        a = r["alias"]
        alias_summary.setdefault(a, {"alias": a, "total_usd": 0.0, "coins": []})
        alias_summary[a]["total_usd"] += r["value_usd"]
        alias_summary[a]["coins"].append({
            "symbol": r["symbol"], "alias": r["alias"], "amount": 0.0,
            "value_usd": round(r["value_usd"], 2), "price_usd": None, "group": r["group"]
        })
    for v in alias_summary.values():
        v["total_usd"] = round(v["total_usd"], 2)

    unknown_aliases = sorted({
        r["symbol"] for r in rows if r["symbol"] not in tx.aliases
    })

    return {
        "total_usd": round(total, 2),
        "groups": groups_out,
        "alias_summary": list(alias_summary.values()),
        "unknown_aliases": unknown_aliases,
    }

@app.post("/rebalance/plan")
async def rebalance_plan(
    source: str = Query("cointracking"),
    min_usd_raw: Optional[str] = Query(None, alias="min_usd"),
    payload: Dict[str, Any] = Body(...),
):
    # min_usd robuste
    min_usd = 1.0
    if min_usd_raw and str(min_usd_raw).strip():
        try:
            min_usd = float(min_usd_raw)
        except ValueError:
            pass

    res = await get_current_balances(source=source)
    rows = res.get("items", []) if isinstance(res, dict) else (res or [])

    # compat targets: dict OU list
    targets = payload.get("group_targets_pct", payload.get("targets"))
    if isinstance(targets, dict):
        group_targets_pct = {str(k): float(v) for k, v in targets.items()}
    elif isinstance(targets, list):
        group_targets_pct = {
            str(d.get("group")): float(d.get("weight_pct", 0.0))
            for d in targets if isinstance(d, dict)
        }
    else:
        group_targets_pct = {}

    return plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=payload.get("sub_allocation", "proportional"),
        primary_symbols=payload.get("primary_symbols"),
        min_trade_usd=float(payload.get("min_trade_usd", 25.0)),
    )
