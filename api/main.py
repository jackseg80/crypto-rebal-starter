# --- imports (en haut du fichier) ---
from __future__ import annotations
from typing import Any, Dict, List
from time import monotonic
import os
import time
from fastapi import FastAPI, Query, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

from connectors import cointracking as ct_file
from connectors.cointracking_api import get_current_balances as ct_api_get_current_balances, _debug_probe

from services.rebalance import plan_rebalance
from services.taxonomy import Taxonomy
from services.pricing import get_prices_usd
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

def _get_data_age_minutes(source_used: str) -> float:
    """Retourne l'âge approximatif des données en minutes selon la source"""
    if source_used == "cointracking":
        # Pour CSV local, vérifier la date de modification du fichier
        csv_path = os.getenv("COINTRACKING_CSV", "./data/cointracking_balances.csv")
        try:
            if os.path.exists(csv_path):
                mtime = os.path.getmtime(csv_path)
                age_seconds = time.time() - mtime
                return age_seconds / 60.0
        except Exception:
            pass
        # Fallback : considérer les données CSV comme potentiellement anciennes
        return 60.0  # 1 heure par défaut
    elif source_used == "cointracking_api":
        # API données fraîches (cache 60s)
        return 1.0
    else:
        # Stub ou autres sources
        return 0.0

def _calculate_price_deviation(local_price: float, market_price: float) -> float:
    """Calcule l'écart en pourcentage entre prix local et marché"""
    if market_price <= 0:
        return 0.0
    return abs(local_price - market_price) / market_price * 100.0

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
    source_used = res.get("source_used")
    plan = _enrich_actions_with_prices(plan, rows, pricing_mode=pricing, source_used=source_used)

    # meta pour UI - fusionner avec les métadonnées pricing existantes
    if not plan.get("meta"):
        plan["meta"] = {}
    plan["meta"].update({
        "source_used": source_used,
        "items_count": len(rows)
    })
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
def _enrich_actions_with_prices(plan: Dict[str, Any], rows: List[Dict[str, Any]], pricing_mode: str = "local", source_used: str = "") -> Dict[str, Any]:
    """
    Enrichit les actions avec les prix selon 3 modes :
    - "local" : utilise uniquement les prix dérivés des balances
    - "auto" : utilise uniquement les prix d'API externes
    - "hybrid" : commence par local, corrige avec marché si données anciennes ou écart important
    """
    # Configuration hybride
    max_age_min = float(os.getenv("PRICE_HYBRID_MAX_AGE_MIN", "30"))
    max_deviation_pct = float(os.getenv("PRICE_HYBRID_DEVIATION_PCT", "5.0"))
    
    # Calculer les prix locaux (toujours nécessaire pour hybrid)
    local_price_map: Dict[str, float] = {}
    for row in rows or []:
        sym = row.get("symbol")
        if not sym:
            continue
        value_usd = float(row.get("value_usd") or 0.0)
        amount = float(row.get("amount") or 0.0)
        if value_usd > 0 and amount > 0:
            local_price_map[sym.upper()] = value_usd / amount

    # Préparer les prix selon le mode
    price_map: Dict[str, float] = {}
    market_price_map: Dict[str, float] = {}
    
    if pricing_mode == "local":
        price_map = local_price_map.copy()
    elif pricing_mode == "auto":
        # Récupérer tous les prix via API
        symbols = set()
        for a in plan.get("actions", []) or []:
            sym = a.get("symbol")
            if sym:
                symbols.add(sym.upper())
        
        if symbols:
            market_price_map = get_prices_usd(list(symbols))
            price_map = {k: v for k, v in market_price_map.items() if v is not None}
    elif pricing_mode == "hybrid":
        # Commencer par prix locaux
        price_map = local_price_map.copy()
        
        # Déterminer si correction nécessaire  
        data_age_min = _get_data_age_minutes(source_used)
        needs_market_correction = data_age_min > max_age_min
        
        # Récupérer les symboles nécessaires
        symbols = set()
        for a in plan.get("actions", []) or []:
            sym = a.get("symbol")
            if sym:
                symbols.add(sym.upper())
        
        # Vérifier si on a des prix locaux pour les symboles nécessaires
        missing_local_prices = symbols - set(local_price_map.keys())
        needs_market_fallback = bool(missing_local_prices)
        
        # Récupérer prix marché si données anciennes OU si prix locaux manquants
        if (needs_market_correction or needs_market_fallback) and symbols:
            market_price_map = get_prices_usd(list(symbols))
            market_price_map = {k: v for k, v in market_price_map.items() if v is not None}

    # Enrichir les actions
    for a in plan.get("actions", []) or []:
        sym = a.get("symbol")
        if not sym or not a.get("usd") or a.get("price_used"):
            continue
            
        sym_upper = sym.upper()
        local_price = local_price_map.get(sym_upper)
        market_price = market_price_map.get(sym_upper)
        
        # Déterminer le prix final et la source
        final_price = None
        price_source = "local"
        
        if pricing_mode == "local":
            final_price = local_price
            price_source = "local"
        elif pricing_mode == "auto":
            final_price = market_price
            price_source = "market"
        elif pricing_mode == "hybrid":
            # Logique hybride avec fallback intelligent
            data_age_min = _get_data_age_minutes(source_used)
            
            if data_age_min > max_age_min:
                # Données anciennes -> privilégier prix marché
                if market_price:
                    final_price = market_price
                    price_source = "market"
                elif local_price:
                    final_price = local_price
                    price_source = "local"
            else:
                # Données fraîches -> privilégier prix local, fallback marché
                if local_price:
                    final_price = local_price
                    price_source = "local"
                elif market_price:
                    final_price = market_price
                    price_source = "market"
        
        # Appliquer le prix final
        if final_price and final_price > 0:
            a["price_used"] = float(final_price)
            a["price_source"] = price_source
            try:
                a["est_quantity"] = round(float(a["usd"]) / float(final_price), 8)
            except Exception:
                pass
    
    # Ajouter métadonnées sur le pricing
    if not plan.get("meta"):
        plan["meta"] = {}
    
    plan["meta"]["pricing_mode"] = pricing_mode
    if pricing_mode == "hybrid":
        plan["meta"]["pricing_hybrid"] = {
            "max_age_min": max_age_min,
            "max_deviation_pct": max_deviation_pct,
            "data_age_min": _get_data_age_minutes(source_used)
        }
    
    return plan

def _to_csv(actions: List[Dict[str, Any]]) -> str:
    lines = ["group,alias,symbol,action,usd,est_quantity,price_used"]
    for a in actions or []:
        lines.append("{},{},{},{},{:.2f},{},{}".format(
            a.get("group",""),
            a.get("alias",""),
            a.get("symbol",""),
            a.get("action",""),
            float(a.get("usd") or 0.0),
            ("" if a.get("est_quantity") is None else f"{a.get('est_quantity')}"),
            ("" if a.get("price_used")   is None else f"{a.get('price_used')}")
        ))
    return "\n".join(lines)

# ---------- debug ----------
@app.get("/debug/ctapi")
async def debug_ctapi():
    """Endpoint de debug pour CoinTracking API"""
    return _debug_probe()

# inclure les routes taxonomie
app.include_router(taxonomy_router)
