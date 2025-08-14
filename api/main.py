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

import os, re

# Pricing (services.pricing -> fallback pricing.py -> fallback no-op)
try:
    from services.pricing import get_prices_usd
except Exception:
    try:
        from pricing import get_prices_usd
    except Exception:
        def get_prices_usd(symbols):  # fallback si aucun provider dispo
            return {}

app = FastAPI(title="Crypto Rebal Starter")

# CORS (config via .env si besoin)
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
      {symbol, alias?, value_usd, price_usd?, amount?, location?}
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

        # >>> NOUVEAU : price_usd + amount si présents
        price_usd = r.get("price_usd")
        try:
            price_usd = float(price_usd) if price_usd is not None else None
        except Exception:
            price_usd = None

        amount = r.get("amount")
        try:
            amount = float(amount) if amount is not None else None
        except Exception:
            amount = None

        out.append({
            "symbol": symbol,
            "alias": (r.get("alias") or r.get("name") or symbol).strip(),
            "value_usd": value_usd,
            "price_usd": price_usd,
            "amount": amount,
            "location": r.get("location"),
        })
    return out


def _parse_min_usd(s: str | None, default: float = 0.0) -> float:
    if not s: return default
    try:
        return float(str(s).replace(",", "."))
    except Exception:
        return default
    
def _enrich_actions_with_prices(plan: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Remplit price_used et est_quantity pour chaque action.
    Ordre des sources de prix :
      1) Stables (USD/USDT/USDC = 1)
      2) Prix issus de CoinTracking (price_usd ou value_usd/amount déduits du portefeuille 'rows')
      3) Provider externe get_prices_usd (stub éventuel)
      4) Alias BTC/ETH/SOL (TBTC/WBTC -> BTC; WETH/STETH/WSTETH/RETH -> ETH; JUPSOL/JITOSOL -> SOL)
      5) Strip suffixes numériques (ATOM2 -> ATOM, SOL2 -> SOL, ...)
    """
    actions = plan.get("actions") or []
    if not actions:
        return plan

    import re
    FIAT_STABLE_FIXED = {"USD": 1.0, "USDT": 1.0, "USDC": 1.0}
    PRICE_SYMBOL_ALIAS = {
        "TBTC": "BTC", "WBTC": "BTC",
        "WETH": "ETH", "STETH": "ETH", "WSTETH": "ETH", "RETH": "ETH",
        "JUPSOL": "SOL", "JITOSOL": "SOL",
    }

    # --- (2) Carte de prix issue de CoinTracking (rows)
    portfolio_price: Dict[str, float] = {}
    for it in rows or []:
        s = (it.get("symbol") or "").upper()
        if not s:
            continue
        amt = it.get("amount")
        val = it.get("value_usd")
        p  = it.get("price_usd")
        # calcule si besoin
        if p is None and amt and val and float(amt) > 0:
            try:
                p = float(val) / float(amt)
            except Exception:
                p = None
        if p and float(p) > 0:
            portfolio_price[s] = float(p)
            # alias et strip suffix
            base = PRICE_SYMBOL_ALIAS.get(s)
            if base and base not in portfolio_price:
                portfolio_price[base] = float(p)
            s_nosuf = re.sub(r"\d+$", "", s)
            if s_nosuf and s_nosuf != s and s_nosuf not in portfolio_price:
                portfolio_price[s_nosuf] = float(p)

    # --- (3) Provider externe (stub possible)
    syms = set()
    for a in actions:
        s = (a.get("symbol") or "").upper()
        if s:
            syms.add(s)
            base = PRICE_SYMBOL_ALIAS.get(s)
            if base: syms.add(base)
            s_nosuf = re.sub(r"\d+$", "", s)
            if s_nosuf and s_nosuf != s: syms.add(s_nosuf)
    price_map = get_prices_usd(list(syms)) or {}

    def _resolve(sym: str) -> float | None:
        s = (sym or "").upper()
        if not s:
            return None
        # 1) stables
        if s in FIAT_STABLE_FIXED:
            return FIAT_STABLE_FIXED[s]
        # 2) CoinTracking (direct / alias / sans suffixe)
        p = portfolio_price.get(s)
        if p: return p
        base = PRICE_SYMBOL_ALIAS.get(s)
        if base:
            pb = portfolio_price.get(base)
            if pb: return pb
        s_nosuf = re.sub(r"\d+$", "", s)
        if s_nosuf and s_nosuf != s:
            p2 = portfolio_price.get(s_nosuf)
            if p2: return p2
            base2 = PRICE_SYMBOL_ALIAS.get(s_nosuf)
            if base2:
                pb2 = portfolio_price.get(base2)
                if pb2: return pb2
        # 3) Provider (direct / alias / sans suffixe)
        p = price_map.get(s)
        if p and float(p) > 0: return float(p)
        if base:
            pb = price_map.get(base)
            if pb and float(pb) > 0: return float(pb)
        if s_nosuf and s_nosuf != s:
            p2 = price_map.get(s_nosuf)
            if p2 and float(p2) > 0: return float(p2)
            if base2:
                pb2 = price_map.get(base2)
                if pb2 and float(pb2) > 0: return float(pb2)
        return None

    for a in actions:
        p = _resolve(a.get("symbol"))
        if p and p > 0:
            a["price_used"] = float(p)
            a["est_quantity"] = round(abs(float(a.get("usd") or 0.0)) / float(p), 8)
        else:
            a["price_used"] = None
            a["est_quantity"] = None

    return plan

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
    plan = _enrich_actions_with_prices(plan, rows)
    try:
        plan.setdefault("meta", {})["source_used"] = res.get("source_used")
    except Exception:
        pass
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
