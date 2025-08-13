# api/main.py
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware

from connectors.cointracking import get_current_balances
from services.rebalance import plan_rebalance
from services.taxonomy import Taxonomy
from api.taxonomy_endpoints import router as taxonomy_router


app = FastAPI(title="Crypto Rebal Starter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Le router Taxonomy a un prefix="/taxonomy"
app.include_router(taxonomy_router)


# --- Helpers ---------------------------------------------------------------

def _to_rows(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalise les lignes renvoyées par connecteurs (CoinTracking) vers :
    { symbol: str, alias: Optional[str], value_usd: float, location: Optional[str] }
    """
    out: List[Dict[str, Any]] = []
    for r in raw or []:
        symbol = r.get("symbol") or r.get("coin") or r.get("name")
        if not symbol:
            continue

        # valeur en USD (différents noms possibles selon la source)
        v = (
            r.get("value_usd", None)
            if isinstance(r, dict)
            else None
        )
        if v is None:
            v = r.get("usd_value")
        if v is None:
            v = r.get("usd")
        if v is None:
            v = r.get("value")

        try:
            value_usd = float(v)
        except (TypeError, ValueError):
            value_usd = 0.0

        out.append({
            "symbol": str(symbol),
            "alias": r.get("alias") or None,   # l'alias sera (re)calculé côté Taxonomy si absent
            "value_usd": value_usd,
            "location": r.get("location"),
        })
    return out


def _parse_min_usd(min_usd_raw: str | None, default: float = 0.0) -> float:
    if min_usd_raw and min_usd_raw.strip():
        try:
            return float(min_usd_raw)
        except ValueError:
            return default
    return default


# --- Endpoints -------------------------------------------------------------

@app.get("/balances/current")
async def balances_current(
    source: str = Query("cointracking"),
    min_usd: float = Query(0.0),
):
    res = await get_current_balances(source=source)
    raw = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_rows(raw)
    rows = [r for r in rows if float(r.get("value_usd") or 0.0) >= min_usd]
    return {"items": rows}


@app.get("/portfolio/groups")
async def portfolio_groups(
    source: str = Query("cointracking"),
    min_usd: float = Query(0.0),
):
    tx = Taxonomy.load()

    # 1) Récup data brute
    res = await get_current_balances(source=source)
    raw = res.get("items", []) if isinstance(res, dict) else (res or [])

    # 2) Normalisation lignes
    rows: List[Dict[str, Any]] = []
    for it in raw:
        symbol = (it.get("symbol") or it.get("name") or it.get("coin") or "").strip()
        alias = (it.get("alias") or it.get("name") or symbol or "").strip()
        val = it.get("value_usd")
        if val is None:
            val = it.get("usd_value")
        value_usd = float(val or 0.0)
        rows.append({
            "symbol": symbol,
            "alias": alias,
            "value_usd": value_usd,
            "location": it.get("location"),
        })

    # 3) Filtre & total
    items = [r for r in rows if float(r.get("value_usd") or 0.0) >= float(min_usd or 0.0)]
    total_usd = sum(r["value_usd"] for r in items) or 0.0

    # 4) Prépare les groupes + fallback
    groups_order = list(tx.groups_order or [])
    if not groups_order:
        groups_order = ["BTC", "ETH", "Stablecoins", "SOL", "L1/L0 majors", "Others"]
    by_group: Dict[str, List[Dict[str, Any]]] = {g: [] for g in groups_order}
    fallback = "Others" if "Others" in by_group else groups_order[0]

    def pick_group_for_alias(a: str) -> str:
        g = tx.group_for_alias(a)
        # g peut être une liste, un tuple, une string, ou None
        if isinstance(g, (list, tuple)):
            # on prend le 1er candidat connu
            for cand in g:
                if isinstance(cand, str) and cand in by_group:
                    return cand
            # sinon le 1er string dispo
            for cand in g:
                if isinstance(cand, str):
                    return cand
            return fallback
        if isinstance(g, str):
            return g if g in by_group else fallback
        return fallback

    # 5) Répartition par groupe
    for r in items:
        alias = (r.get("alias") or r.get("symbol") or "").strip()
        g = pick_group_for_alias(alias)
        by_group[g].append({
            "symbol": r["symbol"],
            "alias": alias or r["symbol"],
            "amount": 0.0,
            "value_usd": r["value_usd"],
            "location": r.get("location") or "unknown",
        })

    groups = []
    for g in groups_order:
        g_items = by_group[g]
        g_total = sum(x["value_usd"] for x in g_items)
        groups.append({
            "group": g,
            "total_usd": round(g_total, 2),
            "items": g_items,
            "weight_pct": round(100.0 * g_total / total_usd, 6) if total_usd else 0.0,
        })

    # 6) alias_summary + unknown_aliases
    alias_sum: Dict[str, Dict[str, Any]] = {}
    known_aliases = set(tx.aliases.keys())
    unknown_aliases_acc: Dict[str, float] = {}

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
            "group": pick_group_for_alias(a),
        })
        if a not in known_aliases:
            unknown_aliases_acc[a] = unknown_aliases_acc.get(a, 0.0) + v

    alias_summary_sorted = sorted(alias_sum.values(), key=lambda x: -x["total_usd"])
    unknown_aliases_sorted = sorted(unknown_aliases_acc.keys())

    return {
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
    # parse min_usd (filtre sur les lignes d'entrée)
    min_usd = _parse_min_usd(min_usd_raw, default=1.0)

    # portefeuille courant
    res = await get_current_balances(source=source)
    raw = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_rows(raw)
    rows = [r for r in rows if float(r.get("value_usd") or 0.0) >= min_usd]

    # compat : "group_targets_pct" ou "targets"
    targets_raw = payload.get("group_targets_pct")
    if targets_raw is None:
        targets_raw = payload.get("targets")

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
