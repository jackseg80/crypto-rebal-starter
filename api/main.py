# api/main.py
from __future__ import annotations

from typing import Any, Dict, List
from time import monotonic
from fastapi import FastAPI, Query, Body, Response
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

app.include_router(taxonomy_router)

# ====== TTL CACHES (balances + prix) ======
BALANCES_TTL_SEC = int(os.getenv("BALANCES_TTL_SEC", "60"))
PRICES_TTL_SEC   = int(os.getenv("PRICES_TTL_SEC",   "120"))

_BAL_CACHE: Dict[tuple, tuple] = {}   # (ts, value) par clé (source,)
_PRICE_CACHE: Dict[str, tuple] = {}   # symbol -> (ts, price)

def _cache_get(cache: dict, key: Any, ttl: int):
    if ttl <= 0:  # TTL=0 => désactivé
        return None
    ent = cache.get(key)
    if not ent:
        return None
    ts, val = ent
    if monotonic() - ts > ttl:
        cache.pop(key, None)
        return None
    return val

def _cache_set(cache: dict, key: Any, val: Any):
    cache[key] = (monotonic(), val)
    

# --- Résolveur de source -----------------------------------------------------
async def resolve_current_balances(source: str = "cointracking") -> Dict[str, Any]:
    s = (source or "").strip().lower()
    key = (s,)

    # 1) cache
    cached = _cache_get(_BAL_CACHE, key, BALANCES_TTL_SEC)
    if cached is not None:
        # s'assurer d'avoir un dict comme l’API attend
        if isinstance(cached, dict):
            return cached
        return {"source_used": s, "items": cached or []}

    # 2) fetch réel
    if s in ("cointracking_api", "ctapi", "ct_api"):
        res = await ct_api_get_current_balances()
        out = res if isinstance(res, dict) else {"source_used": "cointracking_api", "items": res or []}
    else:
        res = await ct_file.get_current_balances(source=s)
        out = res if isinstance(res, dict) else {"source_used": s or "cointracking", "items": res or []}

    # 3) cache + retour
    _cache_set(_BAL_CACHE, key, out)
    return out


# --- Utils -------------------------------------------------------------------
def _norm_primary_symbols(raw: Dict[str, Any] | None) -> Dict[str, list[str]]:
    out: Dict[str, list[str]] = {}
    if not isinstance(raw, dict):
        return out
    for g, v in raw.items():
        if isinstance(v, str):
            parts = [s.strip().upper() for s in v.split(",") if str(s).strip()]
        elif isinstance(v, list):
            parts = [str(s).strip().upper() for s in v if str(s).strip()]
        else:
            parts = []
        out[str(g)] = parts
    return out

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
    
def _build_implied_prices_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    for r in rows or []:
        sym = str(r.get("symbol") or "").upper()
        try:
            amt = float(r.get("amount") or 0.0)
            val = float(r.get("value_usd") or 0.0)
        except Exception:
            continue
        if sym and amt > 0.0 and val > 0.0:
            prices.setdefault(sym, val / amt)
    for s in ("USD", "USDT", "USDC"):
        prices.setdefault(s, 1.0)
    return prices


def _price_cache_get(sym: str) -> float | None:
    ent = _PRICE_CACHE.get(sym)
    if not ent:
        return None
    ts, price = ent
    if monotonic() - ts > PRICES_TTL_SEC:
        _PRICE_CACHE.pop(sym, None)
        return None
    return float(price)


def _price_cache_set(sym: str, price: float):
    _PRICE_CACHE[sym] = (monotonic(), float(price))


def _try_fetch_prices(symbols: List[str]) -> Dict[str, float]:
    """
    Essaie d'utiliser pricing.py si présent.
    - Utilise get_prices([...]) si dispo, sinon get_price(sym) par sym.
    - Retourne {} si pas de module ou erreur (fail-silent).
    """
    out: Dict[str, float] = {}
    if not symbols:
        return out
    try:
        import pricing  # type: ignore
    except Exception:
        return out

    # API facultative: get_prices([...])
    if hasattr(pricing, "get_prices"):
        try:
            got = pricing.get_prices(symbols)  # attendu dict {sym:price}
            if isinstance(got, dict):
                for k, v in got.items():
                    try:
                        if float(v) > 0:
                            out[str(k).upper()] = float(v)
                    except Exception:
                        pass
                return out
        except Exception:
            pass

    # Fallback: get_price(sym) un par un
    if hasattr(pricing, "get_price"):
        for s in symbols:
            try:
                p = pricing.get_price(s)
                if p and float(p) > 0:
                    out[s.upper()] = float(p)
            except Exception:
                continue
    return out


def _enrich_actions_with_prices(
    plan: Dict[str, Any],
    rows: List[Dict[str, Any]],
    pricing_mode: str = "auto",
) -> Dict[str, Any]:
    actions = plan.get("actions") or []
    if not actions:
        return plan

    implied = _build_implied_prices_from_rows(rows)

    # 1) Injecter les prix implicites
    for a in actions:
        sym = str(a.get("symbol") or "").upper()
        if not a.get("price_used"):
            p = implied.get(sym)
            if p:
                a["price_used"] = float(p)

    # 2) Mode local -> pas de réseau
    if str(pricing_mode or "auto").lower() == "local":
        for a in actions:
            price = float(a.get("price_used") or 0.0)
            usd = float(a.get("usd") or 0.0)
            a["est_quantity"] = abs(usd) / price if price > 0 else None
        return plan

    # 3) Mode auto -> compléter avec le cache et (optionnellement) pricing.py
    missing: List[str] = []
    for a in actions:
        sym = str(a.get("symbol") or "").upper()
        if not a.get("price_used"):
            cached = _price_cache_get(sym)
            if cached and cached > 0:
                a["price_used"] = float(cached)
            else:
                missing.append(sym)

    # fetch de groupe (si possible) pour les manquants
    missing = sorted(set([s for s in missing if s]))
    if missing:
        fetched = _try_fetch_prices(missing)
        for s, p in fetched.items():
            _price_cache_set(s, p)
        for a in actions:
            sym = str(a.get("symbol") or "").upper()
            if not a.get("price_used"):
                p = fetched.get(sym)
                if p and p > 0:
                    a["price_used"] = float(p)

    # 4) Calcul des quantités
    for a in actions:
        price = float(a.get("price_used") or 0.0)
        usd = float(a.get("usd") or 0.0)
        a["est_quantity"] = abs(usd) / price if price > 0 else None

    return plan


def _norm_primary_symbols(raw: Dict[str, Any] | None) -> Dict[str, list[str]]:
    out: Dict[str, list[str]] = {}
    if not isinstance(raw, dict):
        return out
    for g, v in raw.items():
        if isinstance(v, str):
            parts = [s.strip().upper() for s in v.split(",") if str(s).strip()]
        elif isinstance(v, list):
            parts = [str(s).strip().upper() for s in v if str(s).strip()]
        else:
            parts = []
        out[str(g)] = parts
    return out

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

def _build_implied_prices_from_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Construit un mapping symbol -> prix déduit (value_usd/amount), sans réseau."""
    prices: dict[str, float] = {}
    for r in rows or []:
        sym = str(r.get("symbol") or "").upper()
        try:
            amt = float(r.get("amount") or 0.0)
            val = float(r.get("value_usd") or 0.0)
        except Exception:
            continue
        if sym and amt > 0.0 and val > 0.0:
            prices.setdefault(sym, val / amt)

    # Stables/fiat par défaut
    for s in ("USD", "USDT", "USDC"):
        prices.setdefault(s, 1.0)

    # EUR : si présent dans rows, on l’a déjà calculé; sinon rien (ou lire EUR_USD depuis l'env si tu veux)
    return prices


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
    pricing: str = Query("auto"),   #  ⬅️  NOUVEAU  (auto | local)
    payload: Dict[str, Any] = Body(...),
):
    min_usd = _parse_min_usd(min_usd_raw, default=1.0)

    res = await resolve_current_balances(source=source)
    raw = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_rows(raw)
    rows = [r for r in rows if float(r.get("value_usd") or 0.0) >= min_usd]

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

    primary_symbols = _norm_primary_symbols(payload.get("primary_symbols"))

    plan = plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=payload.get("sub_allocation", "proportional"),
        primary_symbols=primary_symbols,
        min_trade_usd=float(payload.get("min_trade_usd", 25.0)),
    )

    # ⚠️ Passe bien 'rows' ET le 'pricing'
    plan = _enrich_actions_with_prices(plan, rows, pricing_mode=pricing)

    # total_usd garanti
    if "total_usd" not in plan or plan.get("total_usd") is None:
        plan["total_usd"] = sum(float(r.get("value_usd") or 0.0) for r in rows)

    # méta utile
    plan.setdefault("meta", {})
    plan["meta"]["source_used"] = (res.get("source_used") if isinstance(res, dict) else source) or source
    plan["meta"]["items_count"] = len(rows)

    return plan

@app.post("/rebalance/plan.csv")
async def rebalance_plan_csv(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
    pricing: str = Query("auto"),
    payload: Dict[str, Any] = Body(...),
):
    # ... tu construis "csv_bytes" (bytes) comme aujourd’hui
    headers = {
        "Content-Disposition": 'attachment; filename="rebalance-actions.csv"'
    }
    return Response(content=csv_bytes, media_type="text/csv", headers=headers)




