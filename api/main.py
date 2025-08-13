from fastapi import FastAPI, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from engine.plan import build_plan
from connectors.cointracking import ct_raw, get_current_balances
from services.rebalance import snapshot_groups, plan_rebalance
from api.taxonomy import Taxonomy
import io, csv, json


import io, csv

STABLES = {"USDT","USDC","FDUSD","TUSD","DAI","EURT","USDCE","USDBC","BUSD","FDUSD","EUR","USD","UST","USTC"}

def _append_balancing_line(plan: dict, prefer_alias: str = "USD") -> dict:
    """
    Si la somme des 'usd' des actions != 0, ajoute une ligne d'équilibrage
    sur un stable (alias prefer_alias), en 'buy' si net < 0, sinon 'sell'.
    """
    actions = plan.get("actions") or []
    net = sum(a.get("usd", 0.0) for a in actions)
    if abs(net) < 0.01:
        return plan  # déjà équilibré

    bal = {
        "group": "Stablecoins",
        "alias": prefer_alias,
        "symbol": prefer_alias,
        "action": "sell" if net > 0 else "buy",
        "usd": -net,           # contrepartie exacte
        "est_quantity": None,
        "price_used": None,
    }
    actions.append(bal)
    plan["actions"] = actions
    return plan

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
    # 1) parse min_usd (tolérant)
    min_usd = 1.0
    if min_usd_raw and str(min_usd_raw).strip():
        try:
            min_usd = float(min_usd_raw)
        except ValueError:
            pass

    # 2) portefeuille courant
    res = await get_current_balances(source=source)
    rows = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_taxonomy_rows(rows)

    # 3) cibles (dict ou list)
    targets_raw = payload.get("group_targets_pct")
    if targets_raw is None:
        targets_raw = payload.get("targets")
    group_targets_pct = _normalize_targets(targets_raw)

    # 4) primaires (UPPERCASE)
    primary_symbols = payload.get("primary_symbols") or {}
    primary_symbols = {
        (alias or "").upper(): [str(s).upper() for s in (syms or [])]
        for alias, syms in primary_symbols.items()
    }

    # 5) sous-allocation : auto -> primary_first si primaires fournis
    sub_allocation = payload.get("sub_allocation")
    if not sub_allocation or sub_allocation == "auto":
        has_primary = any(primary_symbols.values())
        sub_allocation = "primary_first" if has_primary else "proportional"

    # 6) plan brut
    plan = plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=sub_allocation,
        primary_symbols=primary_symbols,
        min_trade_usd=float(payload.get("min_trade_usd", 25.0)),
    )

    # 7) sécurité : n’ACHETER que des primaires
    plan = _enforce_primary_buys(plan, primary_symbols)

    # 8) équilibrage net à 0 via stable (USD)
    plan = _append_balancing_line(plan, prefer_alias="USD")
    return plan


# --- CSV helper -------------------------------------------------------------
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
    if min_usd_raw and str(min_usd_raw).strip():
        try:
            min_usd = float(min_usd_raw)
        except ValueError:
            pass

    res = await get_current_balances(source=source)
    rows = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_taxonomy_rows(rows)

    targets_raw = payload.get("group_targets_pct") or payload.get("targets")
    group_targets_pct = _normalize_targets(targets_raw)

    # Uppercase des primary pour homogénéité
    primary_symbols = {
        (alias or "").upper(): [str(s).upper() for s in (syms or [])]
        for alias, syms in (payload.get("primary_symbols") or {}).items()
    }

    # Choix de la sous-allocation : si primary fournis => primary_first
    sub_allocation = payload.get("sub_allocation")
    if not sub_allocation or sub_allocation == "auto":
        has_primary = any(primary_symbols.values())
        sub_allocation = "primary_first" if has_primary else "proportional"

    # Plan brut
    plan = plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=sub_allocation,
        primary_symbols=primary_symbols,
        min_trade_usd=float(payload.get("min_trade_usd", 25.0)),
    )

    # IMPORTANT: même post-traitement que l’endpoint JSON
    plan = _enforce_primary_buys(plan, primary_symbols)   # achats = primaires only
    plan = _append_balancing_line(plan, prefer_alias="USD")  # net => 0 via stable

    buf = _actions_to_csv(plan.get("actions", []))
    headers = {"Content-Disposition": 'attachment; filename="rebalance-actions.csv"'}
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers=headers)


def _enforce_primary_buys(plan: Dict[str, Any], primary_symbols: Dict[str, list]) -> Dict[str, Any]:
    """
    Garantit qu'on n'achète QUE des coins listés dans primary_symbols pour chaque alias/groupe.
    Si un buy cible un non-primary, on supprime cette action et on réalloue le montant à un coin primary du même alias.
    """
    if not primary_symbols:
        return plan

    prim = {alias.upper(): set([s.upper() for s in syms]) for alias, syms in primary_symbols.items()}
    actions = plan.get("actions") or []
    if not actions:
        return plan

    new_actions = []
    # montants d'achats non-primary à réallouer par alias
    pending_add: Dict[str, float] = {}
    # index d'une action d'achat primary existante, pour réallouer facilement
    primary_target_index: Dict[str, int] = {}

    for i, a in enumerate(actions):
        act = (a.get("action") or "").lower()
        alias = (a.get("alias") or "").upper()
        symbol = (a.get("symbol") or "").upper()

        # on ne touche qu'aux BUY, et uniquement si on a un set primary pour cet alias
        if act == "buy" and alias in prim:
            if symbol not in prim[alias]:
                # non-primary => on accumule pour réallocation et on drop cette action
                usd = float(a.get("usd") or 0.0)
                if usd > 0:
                    pending_add[alias] = pending_add.get(alias, 0.0) + usd
                # on ne garde pas cette action
                continue
            else:
                # primary : on garde et on mémorise un index pour réaffecter plus tard
                if alias not in primary_target_index:
                    primary_target_index[alias] = len(new_actions)

        new_actions.append(a)

    # Réallocation : si on a du "pending" pour un alias, on l'ajoute à une action primary existante
    for alias, add_usd in pending_add.items():
        if add_usd <= 0:
            continue
        idx = primary_target_index.get(alias)
        if idx is not None:
            new_actions[idx]["usd"] = float(new_actions[idx].get("usd") or 0.0) + add_usd
        else:
            # aucune action d'achat primary existante => on crée une nouvelle action vers le 1er symbole primary
            sym = next(iter(prim[alias]))
            new_actions.append({
                "group": alias,            # même libellé que le groupe/alias
                "alias": alias,
                "symbol": sym,
                "action": "buy",
                "usd": add_usd,
                "est_quantity": None,
                "price_used": None,
            })

    plan["actions"] = new_actions
    return plan



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
