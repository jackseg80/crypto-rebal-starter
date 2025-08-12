from fastapi import FastAPI, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from engine.plan import build_plan
from connectors.cointracking import ct_raw, get_current_balances
from services.rebalance import snapshot_groups, plan_rebalance
from api.taxonomy import Taxonomy

STABLES = {"USDT","USDC","FDUSD","TUSD","DAI","EURT","USDCE","USDBC","BUSD","FDUSD","EUR","USD","UST","USTC"}

def _normalize_targets(raw: Union[Dict[str, float], List[Dict[str, Any]], None]) -> Dict[str, float]:
    """
    Accepte:
      - dict: {"BTC":35, "ETH":25, ...}
      - list: [{"group":"BTC","weight_pct":35}, {"group":"ETH","pct":25}, ...]
    Retourne toujours: dict[str, float]
    """
    if raw is None:
        return {}

    if isinstance(raw, dict):
        return {str(k): float(v) for k, v in raw.items()}

    out: Dict[str, float] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("group") or item.get("name")
        val = (item.get("weight_pct") or item.get("pct") or item.get("percent") or item.get("value"))
        if name is not None and val is not None:
            out[str(name)] = float(val)
    return out

def _to_taxonomy_rows(rows):
    norm = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        symbol = (r.get("symbol") or r.get("coin") or r.get("ticker") or "").upper()
        value_usd = (
            r.get("value_usd")
            if r.get("value_usd") is not None
            else r.get("usd_value")  # <-- ton format actuel
        )
        # fallback éventuel
        if value_usd is None:
            value_usd = r.get("value_fiat")

        amount = r.get("amount") or r.get("qty") or 0
        alias = r.get("alias")

        norm.append({
            "symbol": symbol,
            "value_usd": float(value_usd or 0),
            "amount": float(amount or 0),
            "alias": alias,
        })
    return norm

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/balances/current")
async def balances_current(
    source: str = Query("stub", pattern="^(stub|csv|cointracking)$"),
    min_usd: float = Query(1.0, ge=0),
    alias: str = Query("safe", pattern="^(none|safe|wrappers|all)$")
):
    data = await get_current_balances(source=source, min_usd=min_usd, alias_mode=alias)
    return {"source": source, "items": data}

@app.post("/balances/current")
async def balances_current_post(body: Dict[str, Any] = Body(...)):
    source = body.get("source", "stub")
    csv_current = body.get("csv_current")
    csv_by_exchange = body.get("csv_by_exchange")
    min_usd = float(body.get("min_usd", 1.0))
    alias = body.get("alias", "safe")  # "none"|"safe"|"wrappers"|"all"
    data = await get_current_balances(source=source,
                                      csv_current=csv_current,
                                      csv_by_exchange=csv_by_exchange,
                                      min_usd=min_usd,
                                      alias_mode=alias)
    return {"source": source, "items": data}

@app.get("/debug/env")
def debug_env():
    import os
    return {
        "ct_key_present": bool(os.getenv("COINTRACKING_KEY")),
        "ct_secret_present": bool(os.getenv("COINTRACKING_SECRET"))
    }

@app.get("/debug/ct/raw")
async def debug_ct_raw(method: str = "getBalance"):
    return await ct_raw(method)

@app.get("/portfolio/summary")
async def portfolio_summary(
    source: str = Query("cointracking", pattern="^(stub|csv|cointracking)$"),
    min_usd: float = Query(1.0, ge=0),
    alias: str = Query("safe", pattern="^(none|safe|wrappers|all)$"),
    top_n: int = Query(10, ge=1, le=100)
):
    items = await get_current_balances(source=source, min_usd=min_usd, alias_mode=alias)
    total = sum(x["usd_value"] for x in items) or 0.0
    out = []
    for x in items:
        w = (x["usd_value"] / total) * 100 if total else 0.0
        out.append({**x, "weight_pct": round(w, 4), "is_stable": x["symbol"] in STABLES})
    out.sort(key=lambda r: r["usd_value"], reverse=True)

    stables_total = sum(x["usd_value"] for x in out if x["is_stable"])
    nonstables_total = total - stables_total

    return {
        "total_usd": round(total, 2),
        "n_positions": len(out),
        "stables_total_usd": round(stables_total, 2),
        "nonstables_total_usd": round(nonstables_total, 2),
        "top": out[:top_n],
        "items": out  # complet si tu veux tout afficher côté front
    }
    
@app.get("/portfolio/groups")
async def portfolio_groups(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
):
    min_usd = 1.0
    if min_usd_raw and min_usd_raw.strip():
        try:
            min_usd = float(min_usd_raw)
        except ValueError:
            pass

    res = await get_current_balances(source=source)
    rows = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_taxonomy_rows(rows)  # <-- normalisation

    return snapshot_groups(rows, min_usd=min_usd)


@app.post("/rebalance/plan")
async def rebalance_plan(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
    payload: Dict[str, Any] = Body(...),
):
    # parse min_usd
    min_usd = 1.0
    if min_usd_raw and min_usd_raw.strip():
        try:
            min_usd = float(min_usd_raw)
        except ValueError:
            pass

    # portefeuille courant
    res = await get_current_balances(source=source)
    rows = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_taxonomy_rows(rows)

    # compat: "group_targets_pct" ou "targets" (dict ou list)
    targets_raw = payload.get("group_targets_pct")
    if targets_raw is None:
        targets_raw = payload.get("targets")
    group_targets_pct = _normalize_targets(targets_raw)

    # on garde min_trade_usd localement (sert aussi au balancer)
    min_trade_usd = float(payload.get("min_trade_usd", 25.0))

    result = plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=payload.get("sub_allocation", "proportional"),
        primary_symbols=payload.get("primary_symbols"),
        min_trade_usd=min_trade_usd,
    )

    # ---- Ajout d'une ligne d'équilibrage pour que Σ(usd) ≈ 0 ----
    actions = result.get("actions", [])
    buy_sum  = sum(a.get("usd", 0) for a in actions if a.get("action") == "buy")
    sell_sum = sum(a.get("usd", 0) for a in actions if a.get("action") == "sell")  # négatif
    net = round(buy_sum + sell_sum, 2)

    # si l'écart est significatif, on compense via un stablecoin (par défaut USD)
    if abs(net) >= max(0.01, min_trade_usd):
        balancer_alias = payload.get("balancer_alias", "USD")  # tu peux mettre "USDT" ou "USDC"
        actions.append({
            "group": "Stablecoins",
            "alias": balancer_alias,
            "symbol": balancer_alias,
            "action": "sell" if net > 0 else "buy",
            "usd": -net,  # ex: net=+441.74 -> on vend -441.74 de USD
            "est_quantity": None,
            "price_used": None,
        })
        result["actions"] = actions

    return result

# --- CSV helper -------------------------------------------------------------
from fastapi.responses import StreamingResponse
import io, csv

def _actions_to_csv(actions: list[dict]) -> io.StringIO:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["group", "alias", "symbol", "action", "usd", "est_quantity", "price_used"])
    for a in actions:
        w.writerow([
            a.get("group"),
            a.get("alias"),
            a.get("symbol"),
            a.get("action"),
            round(float(a.get("usd", 0.0)), 2),
            a.get("est_quantity"),
            a.get("price_used"),
        ])
    buf.seek(0)
    return buf

@app.post("/rebalance/plan.csv")
async def rebalance_plan_csv(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
    payload: Dict[str, Any] = Body(...),
):
    # même parsing que /rebalance/plan
    min_usd = 1.0
    if min_usd_raw and min_usd_raw.strip():
        try:
            min_usd = float(min_usd_raw)
        except ValueError:
            pass

    res = await get_current_balances(source=source)
    rows = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_taxonomy_rows(rows)

    targets_raw = payload.get("group_targets_pct") or payload.get("targets")
    group_targets_pct = _normalize_targets(targets_raw)

    plan = plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=payload.get("sub_allocation", "proportional"),
        primary_symbols=payload.get("primary_symbols"),
        min_trade_usd=float(payload.get("min_trade_usd", 25.0)),
    )

    buf = _actions_to_csv(plan.get("actions", []))
    headers = {"Content-Disposition": 'attachment; filename="rebalance-actions.csv"'}
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers=headers)


# --- DEBUG SNAPSHOT ----------------------------------------------------------
@app.get("/debug/snapshot")
async def debug_snapshot(
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0, ge=0.0),
):
    """
    Retourne l’agrégat par groupes + alias pour inspection.
    """
    rows = await get_current_balances(source=source)
    taxo = Taxonomy()
    snap = taxo.aggregate(rows, min_usd=min_usd)
    return {
        "source": source,
        "min_usd": min_usd,
        **snap
    }
    
# --- Debug: voir la "shape" des données ---
@app.get("/debug/peek")
async def debug_peek(source: str = Query("cointracking")):
    res = await get_current_balances(source=source)
    if isinstance(res, dict):
        items = res.get("items", [])
        first = items[0] if items else None
        return {
            "top_level_type": "dict",
            "top_level_keys": list(res.keys()),
            "items_len": len(items),
            "first_row": first,
            "first_row_keys": list(first.keys()) if isinstance(first, dict) else None,
        }
    elif isinstance(res, list):
        first = res[0] if res else None
        return {
            "top_level_type": "list",
            "items_len": len(res),
            "first_row": first,
            "first_row_keys": list(first.keys()) if isinstance(first, dict) else None,
        }
    else:
        return {"top_level_type": type(res).__name__, "value_preview": str(res)[:200]}
