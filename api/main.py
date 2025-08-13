# api/main.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

# Dépendances projet
# - ct_raw / get_current_balances : connecteur CoinTracking
# - snapshot_groups / plan_rebalance : logique de regroupement et de plan
# - Taxonomy : mapping des alias -> groupes
from connectors.cointracking import ct_raw, get_current_balances
from services.rebalance import snapshot_groups, plan_rebalance
from api.taxonomy import Taxonomy
from api.taxonomy_endpoints import router as taxonomy_router

app = FastAPI(title="Crypto Rebal Starter", version="1.0.0")

app.include_router(taxonomy_router, prefix="/taxonomy", tags=["taxonomy"])

# CORS : autorise localhost / file:// via navigateur
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tu peux restreindre à ["http://127.0.0.1:5500", "http://localhost:5500"] si tu veux
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Helpers ----------

def _safe_float(val: Optional[str], default: float = 1.0) -> float:
    if val is None:
        return default
    s = val.strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _to_taxonomy_rows(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transforme les lignes brutes en lignes normalisées utilisées par la logique de regroupement.
    Attend au minimum: symbol, usd_value (ou value_usd), et éventuellement alias/name/location.
    """
    out: List[Dict[str, Any]] = []
    for r in items:
        symbol = r.get("symbol") or r.get("coin") or r.get("ticker")
        if not symbol:
            continue

        # value / amount (on ne force pas amount ici)
        value = r.get("value_usd", r.get("usd_value", r.get("usd", 0.0)))
        try:
            value_usd = float(value)
        except Exception:
            value_usd = 0.0

        alias = r.get("alias") or symbol  # si l’alias n’est pas déjà posé par le connecteur
        name = r.get("name") or r.get("label") or symbol
        location = r.get("location") or r.get("exchange") or r.get("account")

        out.append(
            {
                "symbol": symbol,
                "alias": alias,
                "value_usd": value_usd,
                "name": name,
                "location": location,
            }
        )
    return out


def _normalize_targets(targets_raw: Any) -> Dict[str, float]:
    """
    Accepte plusieurs formes :
      - dict : {"BTC": 35, "ETH": 25, ...}
      - list de dicts : [{"group":"BTC","weight_pct":35}, ...] ou [{"group":"BTC","weight":35}, ...]
      - list de tuples : [["BTC", 35], ["ETH", 25], ...]
    Retourne {group: float(weight)}
    """
    if not targets_raw:
        return {}

    # Déjà un dict
    if isinstance(targets_raw, dict):
        out = {}
        for k, v in targets_raw.items():
            try:
                out[str(k)] = float(v)
            except Exception:
                continue
        return out

    # Listes
    if isinstance(targets_raw, list):
        out: Dict[str, float] = {}
        for x in targets_raw:
            if isinstance(x, dict):
                g = x.get("group") or x.get("name")
                w = x.get("weight_pct", x.get("weight"))
                if g is None or w is None:
                    continue
                try:
                    out[str(g)] = float(w)
                except Exception:
                    pass
            elif isinstance(x, (list, tuple)) and len(x) >= 2:
                g, w = x[0], x[1]
                try:
                    out[str(g)] = float(w)
                except Exception:
                    pass
        return out

    # Sinon, rien
    return {}


# ---------- Endpoints ----------

@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/balances/current")
async def balances_current(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
):
    """
    Renvoie les balances brutes normalisées (pour debug/compat).
    """
    min_usd = _safe_float(min_usd_raw, 0.0)
    res = await get_current_balances(source=source)
    # Certains connecteurs renvoient {"items":[...]} ; d’autres une liste simple
    items = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_taxonomy_rows(items)
    if min_usd > 0:
        rows = [r for r in rows if r.get("value_usd", 0.0) >= min_usd]
    total = sum(r.get("value_usd", 0.0) for r in rows)
    return {"total_usd": total, "items": rows}


@app.get("/portfolio/groups")
async def portfolio_groups(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
):
    """
    Vue agrégée par groupes (BTC, ETH, Stablecoins, SOL, L1/L0 majors, Others).
    Utilisée par l’UI pour l’affichage simplifié.
    """
    min_usd = _safe_float(min_usd_raw, 1.0)
    res = await get_current_balances(source=source)
    items = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_taxonomy_rows(items)

    # Agrégation
    data = snapshot_groups(rows=rows, min_usd=min_usd)
    return data


@app.post("/rebalance/plan")
async def rebalance_plan(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
    payload: Dict[str, Any] = Body(...),
):
    """
    Calcule le plan de rebalancing détaillé.
    Body attendu (au choix) :
      - group_targets_pct : { "BTC": 35, "ETH": 25, "SOL": 10, "L1/L0 majors": 10, "Stablecoins": 10, "Others": 10 }
      - targets : mêmes données mais format alternatif (dict ou liste)

    Options :
      - sub_allocation : "proportional" (par défaut) — la logique d’achat interne gère la
                         préférence "primary_symbols" côté services.rebalance
      - primary_symbols : { "BTC": ["BTC","TBTC","WBTC"], "ETH": ["ETH","WSTETH","STETH","RETH","WETH"], ... }
      - min_trade_usd : float (25 par défaut)
    """
    min_usd = _safe_float(min_usd_raw, 1.0)

    # 1) portefeuille courant
    res = await get_current_balances(source=source)
    rows = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_taxonomy_rows(rows)

    # 2) normalisation des cibles
    targets_raw = payload.get("group_targets_pct")
    if targets_raw is None:
        targets_raw = payload.get("targets")
    group_targets_pct = _normalize_targets(targets_raw)

    # 3) calcul du plan
    plan = plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=payload.get("sub_allocation", "proportional"),
        primary_symbols=payload.get("primary_symbols"),
        min_trade_usd=float(payload.get("min_trade_usd", 25.0)),
    )
    return plan


@app.post("/rebalance/plan.csv", response_class=PlainTextResponse)
async def rebalance_plan_csv(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
    payload: Dict[str, Any] = Body(...),
):
    """
    Même calcul que /rebalance/plan mais retourne un CSV (colonnes principales).
    """
    min_usd = _safe_float(min_usd_raw, 1.0)

    res = await get_current_balances(source=source)
    rows = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_taxonomy_rows(rows)

    targets_raw = payload.get("group_targets_pct")
    if targets_raw is None:
        targets_raw = payload.get("targets")
    group_targets_pct = _normalize_targets(targets_raw)

    plan = plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=payload.get("sub_allocation", "proportional"),
        primary_symbols=payload.get("primary_symbols"),
        min_trade_usd=float(payload.get("min_trade_usd", 25.0)),
    )

    # Construction CSV (UTF-8)
    lines = ["group,alias,symbol,action,usd"]
    for a in plan.get("actions", []):
        g = a.get("group", "")
        alias = a.get("alias", "")
        sym = a.get("symbol", "")
        act = a.get("action", "")
        usd = a.get("usd", 0)
        # protège la virgule décimale éventuelle
        lines.append(f'{g},{alias},{sym},{act},{usd}')
    csv = "\n".join(lines)
    return PlainTextResponse(content=csv, media_type="text/csv; charset=utf-8")


@app.get("/debug/snapshot")
async def debug_snapshot(
    source: str = Query("cointracking"),
    alias: str = Query("all"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
):
    """
    Petit endpoint de debug pour voir la forme des données brutes et la 1ère ligne.
    """
    _ = _safe_float(min_usd_raw, 1.0)  # conservé si tu veux filtrer à l’avenir
    res = await get_current_balances(source=source)

    # Retourne une pré-visualisation utile
    if isinstance(res, dict):
        items = res.get("items", [])
        first = items[0] if items else None
        return {
            "top_level_type": "dict",
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
