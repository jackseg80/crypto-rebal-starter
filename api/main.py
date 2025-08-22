# --- imports (en haut du fichier) ---
from __future__ import annotations
from typing import Any, Dict, List
from time import monotonic
import os, sys, inspect, hashlib, time
from fastapi import FastAPI, Query, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Charger les variables d'environnement depuis .env
load_dotenv()

from connectors import cointracking as ct_file
from connectors.cointracking_api import get_current_balances as ct_api_get_current_balances, _debug_probe

from services.rebalance import plan_rebalance
from services.pricing import get_prices_usd
from services.portfolio import portfolio_analytics
from api.taxonomy_endpoints import router as taxonomy_router
from api.execution_endpoints import router as execution_router
from api.monitoring_endpoints import router as monitoring_router
from api.analytics_endpoints import router as analytics_router

app = FastAPI()
# CORS large pour tests locaux + UI docs/
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],         # important pour POST CSV + preflight
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent     # répertoire du repo (main.py à la racine)
STATIC_DIR = BASE_DIR / "static"               # D:\Python\crypto-rebal-starter\static

if not STATIC_DIR.exists():
    # fallback si l’arbo a changé
    STATIC_DIR = Path.cwd() / "static"

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR), html=True),
    name="static",
)

# petit cache prix optionnel (si tu l’as déjà chez toi, garde le tien)
_PRICE_CACHE: Dict[str, tuple] = {}  # symbol -> (ts, price)
def _cache_get(cache: dict, key: Any, ttl: int):
    if ttl <= 0:
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
    _PRICE_CACHE[key] = (monotonic(), val)
    
    # >>> BEGIN: CT-API helpers (ADD THIS ONCE NEAR THE TOP) >>>
try:
    from connectors import cointracking_api as ct_api
except Exception:
    import cointracking_api as ct_api  # fallback au cas où le package n'est pas packagé "connectors"

FAST_SELL_EXCHANGES = [
    "Kraken", "Binance", "Coinbase", "Bitget", "OKX", "Bybit", "KuCoin", "Bittrex", "Bitstamp", "Gemini"
]
DEFI_HINTS = ["Aave", "Lido", "Rocket Pool", "Curve", "Uniswap", "Sushiswap", "Jupiter", "Osmosis", "Thorchain"]
COLD_HINTS = ["Ledger", "Trezor", "Cold", "Vault", "Hardware"]

def _normalize_loc(label: str) -> str:
    if not label:
        return "Unknown"
    t = label.strip()
    # CoinTracking renvoie souvent “KRaken Balance”, “Kraken Earn Balance”, “COINBASE BALANCE”, …
    t = t.replace("_", " ").replace("-", " ")
    t = t.title()
    # Enlever suffixes fréquents
    for suf in (" Balance", " Wallet", " Account"):
        if t.endswith(suf):
            t = t[: -len(suf)]
    # Ex.: “Kraken Earn Balance” -> “Kraken Earn”
    t = t.replace(" Earn", " Earn")
    return t

def _classify_location(loc: str) -> int:
    L = _normalize_loc(loc)
    if any(L.startswith(x) for x in FAST_SELL_EXCHANGES):
        return 0  # CEX rapide
    if any(h in L for h in DEFI_HINTS):
        return 1  # DeFi
    if any(h in L for h in COLD_HINTS):
        return 2  # Cold/Hardware
    return 3  # reste

def _pick_primary_location_for_symbol(symbol: str, detailed_holdings: dict) -> str:
    # Retourne l’exchange où ce symbole pèse le plus en USD
    best_loc, best_val = "CoinTracking", 0.0
    for loc, assets in (detailed_holdings or {}).items():
        for a in assets or []:
            if a.get("symbol") == symbol:
                v = float(a.get("value_usd") or 0)
                if v > best_val:
                    best_val, best_loc = v, loc
    return best_loc

async def _load_ctapi_exchanges(min_usd: float = 0.0) -> dict:
    """
    Combine les données correctes de get_current_balances avec les locations de getGroupedBalance
    pour éviter la duplication et obtenir les totaux corrects.
    """
    from connectors.cointracking import get_current_balances
    
    # 1) Données correctes de balances
    balances_data = await get_current_balances("cointracking_api")
    correct_items = balances_data.get("items", [])
    
    # 2) Locations depuis getGroupedBalance (pour mapping symbol -> location)
    location_map: Dict[str, str] = {}
    try:
        import connectors.cointracking_api as ct_api
        p_gb = ct_api._post_api_cached("getGroupedBalance", {"group": "exchange", "exclude_dep_with": "1"}, ttl=60)
        rows_gb = ct_api._extract_rows_from_groupedBalance(p_gb)
        
        # Pour chaque symbole, trouver l'exchange avec la plus grande valeur
        symbol_exchanges: Dict[str, List[Tuple[str, float]]] = {}
        for r in rows_gb:
            sym = str(r.get("symbol", "")).upper()
            loc = str(r.get("location", "")).replace(" Balance", "").strip().title()
            val = float(r.get("value_usd", 0))
            if sym and loc and val > 0:
                symbol_exchanges.setdefault(sym, []).append((loc, val))
        
        # Assign primary location (highest value)
        for sym, exchanges in symbol_exchanges.items():
            if exchanges:
                primary_loc = max(exchanges, key=lambda x: x[1])[0]
                location_map[sym] = primary_loc
    except Exception:
        pass
    
    # 3) Grouper par exchange en utilisant les données correctes
    detailed: Dict[str, List[Dict[str, Any]]] = {}
    
    for item in correct_items:
        sym = str(item.get("symbol", "")).upper()
        val = float(item.get("value_usd", 0))
        
        # Appliquer le filtre min_usd
        if val < min_usd:
            continue
            
        # Determiner la location
        location = location_map.get(sym, "CoinTracking")
        
        # Ajouter à detailed_holdings
        detailed.setdefault(location, []).append({
            "symbol": sym,
            "alias": item.get("alias", sym),
            "amount": item.get("amount", 0),
            "value_usd": val,
            "price_usd": None,  # On peut le calculer si besoin
            "location": location
        })
    
    # 4) Créer les exchanges summary
    exchanges = []
    for loc, assets in detailed.items():
        total_val = sum(float(a.get("value_usd", 0)) for a in assets)
        if total_val >= min_usd:
            exchanges.append({
                "location": loc,
                "total_value_usd": round(total_val, 2),
                "asset_count": len(assets),
                "assets": sorted(assets, key=lambda x: float(x.get("value_usd", 0)), reverse=True)
            })
    
    exchanges.sort(key=lambda x: x["total_value_usd"], reverse=True)
    return {"exchanges": exchanges, "detailed_holdings": detailed}
# <<< END: CT-API helpers <<<

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
        csv_path = os.getenv("COINTRACKING_CSV")
        if not csv_path:
            # Utiliser le même path resolution que dans le connector
            default_cur = "CoinTracking - Current Balance_mini.csv"
            candidates = [os.path.join("data", default_cur), default_cur]
            for candidate in candidates:
                if candidate and os.path.exists(candidate):
                    csv_path = candidate
                    break
        
        if csv_path and os.path.exists(csv_path):
            try:
                mtime = os.path.getmtime(csv_path)
                age_seconds = time.time() - mtime
                return age_seconds / 60.0
            except Exception:
                pass
        # Fallback : considérer les données CSV comme récentes pour utiliser prix locaux
        return 5.0  # 5 minutes par défaut (récent)
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
            "amount": float(r.get("amount") or 0.0) if r.get("amount") else None,
            "location": r.get("location") or r.get("exchange") or "Unknown",
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
# --- REPLACE THIS WHOLE FUNCTION IN main.py ---

async def resolve_current_balances(source: str = Query("cointracking")) -> Dict[str, Any]:
    """
    Retourne {source_used, items:[{symbol, alias, amount, value_usd, location}]}
    - Si CT-API dispo: affecte une location “principale” par coin (échange avec la plus grosse part)
    - Sinon: fallback CSV/local avec location=CoinTracking
    """
    if source in ("cointracking_api", "cointracking"):
        try:
            # 1) On charge le snapshot par exchange via CT-API
            snap = await _load_ctapi_exchanges(min_usd=0.0)
            detailed = snap.get("detailed_holdings") or {}

            # 2) On récupère la vue “par coin” (totaux) via CT-API aussi (ou via pricing local si tu préfères)
            api_bal = await ct_api.get_current_balances()  # items par coin (value_usd, amount)
            items = api_bal.get("items") or []

            # 3) Pour CHAQUE coin, on met la location = exchange principal (max value_usd)
            out = []
            for it in items:
                sym = it.get("symbol")
                loc = _pick_primary_location_for_symbol(sym, detailed)
                o = {
                    "symbol": sym,
                    "alias": it.get("alias") or sym,
                    "amount": it.get("amount"),
                    "value_usd": it.get("value_usd"),
                    "location": loc or "CoinTracking",
                }
                out.append(o)

            return {"source_used": "cointracking_api", "items": out}
        except Exception:
            # Fallback silencieux CSV/local
            pass

    # --- Fallback CSV/local (ancienne logique) ---
    items = []
    try:
        raw = await ct_file.get_current_balances()
        for r in raw or []:
            items.append({
                "symbol": r.get("symbol"),
                "alias": r.get("alias") or r.get("symbol"),
                "amount": r.get("amount"),
                "value_usd": r.get("value_usd"),
                "location": r.get("location") or "CoinTracking",
            })
    except Exception:
        pass

    return {"source_used": "cointracking", "items": items}



def _assign_locations_to_actions(plan: dict, rows: list[dict], min_trade_usd: float = 25.0) -> dict:
    """
    Ajoute la location aux actions. Pour les SELL, répartit par exchange
    au prorata des avoirs réels (value_usd) sur chaque exchange.
    """
    # holdings[symbol][location] -> total value_usd
    holdings: dict[str, dict[str, float]] = {}
    locations_seen = set()
    for r in rows or []:
        sym = (r.get("symbol") or "").upper()
        loc = r.get("location") or "Unknown"
        locations_seen.add(loc)
        val = float(r.get("value_usd") or 0.0)
        if sym and val > 0:
            holdings.setdefault(sym, {}).setdefault(loc, 0.0)
            holdings[sym][loc] += val
    

    actions = plan.get("actions") or []
    out_actions: list[dict] = []

    for a in actions:
        sym = (a.get("symbol") or "").upper()
        usd = float(a.get("usd") or 0.0)
        loc = a.get("location")

        # Si la location est déjà définie (ex. imposée par UI), on garde.
        if loc and loc != "Unknown":
            out_actions.append(a)
            continue

        # SELL: on découpe par exchanges où le coin est détenu
        if usd < 0 and sym in holdings and holdings[sym]:
            to_sell = -usd
            locs = [(ex, v) for ex, v in holdings[sym].items() if v > 0]
            total_val = sum(v for _, v in locs)

            # Pas d’avoirs détectés -> laisser 'Unknown'
            if total_val <= 0:
                a["location"] = "Unknown"
                out_actions.append(a)
                continue

            # Tri par priorité CEX → DeFi → Cold, puis par valeur décroissante  
            def get_exchange_priority(exchange_name: str) -> int:
                priorities = {
                    # CEX rapides (priorité 1-15)
                    "Binance": 1, "Kraken": 2, "Coinbase": 3, "Bitget": 4, "Bybit": 5, "OKX": 6,
                    "Huobi": 7, "KuCoin": 8, "Poloniex": 9, "Kraken Earn": 10, "Coinbase Pro": 11,
                    "Bittrex": 12, "Ftx": 13, "Swissborg": 14,
                    # Wallets software (priorité 20-29)
                    "MetaMask": 20, "Phantom": 21, "Rabby": 22, "TrustWallet": 23,
                    # DeFi (priorité 30-39)  
                    "DeFi": 30, "Uniswap": 31, "PancakeSwap": 32, "SushiSwap": 33, "Curve": 34,
                    # Hardware/Cold (priorité 40+)
                    "Ledger": 40, "Trezor": 41, "Cold Storage": 42, "Ledger Wallets": 40,
                    "Portfolio": 50, "CoinTracking": 51, "Demo Wallet": 52, "Unknown": 60
                }
                # Normalisation pour matcher les noms CoinTracking
                clean_name = exchange_name.replace(" Balance", "").replace(" Wallets", "").strip()
                for prefix in ["Metamask", "Solana", "Ron", "Siacoin", "Vsync"]:
                    if clean_name.startswith(prefix):
                        return 25  # Wallets spécialisés
                return priorities.get(clean_name, 99)

            # Tri par priorité, puis par valeur décroissante pour les mêmes priorités
            locs_sorted = sorted(locs, key=lambda x: (get_exchange_priority(x[0]), -x[1]))
            
            # Répartition avec priorité intelligente
            alloc_sum = 0.0
            tmp_parts: list[dict] = []
            remaining_to_sell = to_sell
            
            for i, (ex, available_val) in enumerate(locs_sorted):
                if remaining_to_sell <= 0.01:
                    break
                    
                # Prendre min(ce qui reste à vendre, ce qui est disponible)
                can_sell = min(remaining_to_sell, available_val)
                
                # Respecter le min_trade_usd sauf si c'est le dernier exchange
                if can_sell >= max(0.01, float(min_trade_usd or 0)) or i == len(locs_sorted) - 1:
                    part = round(can_sell, 2)
                    if part > 0.01:
                        na = dict(a)
                        na["usd"] = -part
                        na["location"] = ex
                        tmp_parts.append(na)
                        remaining_to_sell -= part

            # Si tout est sous le min_trade_usd, on regroupe sur le plus gros exchange
            if not tmp_parts:
                ex_big = max(locs, key=lambda t: t[1])[0]
                na = dict(a)
                na["location"] = ex_big
                tmp_parts.append(na)

            out_actions.extend(tmp_parts)
        else:
            # BUY ou symbole inconnu: on laisse tel quel (UI choisira l’exchange)
            out_actions.append(a)

    plan["actions"] = out_actions
    
    return plan


# DEBUG: introspection rapide de la répartition par exchange (cointracking_api)
@app.get("/debug/exchanges-snapshot")
async def debug_exchanges_snapshot(source: str = "cointracking_api"):
    from connectors.cointracking import get_unified_balances_by_exchange
    data = await get_unified_balances_by_exchange(source=source)
    return {
        "has_exchanges": bool(data.get("exchanges")),
        "exchanges_count": len(data.get("exchanges") or []),
        "sample_exchanges": [e.get("location") for e in (data.get("exchanges") or [])[:5]],
        "has_holdings": bool(data.get("detailed_holdings")),
        "holdings_keys": list((data.get("detailed_holdings") or {}).keys())[:5]
    }

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
    dynamic_targets: bool = Query(False, description="Use dynamic targets from CCS/cycle module"),
    payload: Dict[str, Any] = Body(...)
):
    min_usd = _parse_min_usd(min_usd_raw, default=1.0)

    # portefeuille - utiliser les données enrichies avec locations
    try:
        from connectors.cointracking import get_unified_balances_by_exchange
        exchange_data = await get_unified_balances_by_exchange(source=source)
        
        # Extraire tous les items avec leurs locations des detailed_holdings
        items_with_location = []
        detailed_holdings = exchange_data.get("detailed_holdings", {})
        
        for location, assets in detailed_holdings.items():
            for asset in assets:
                # Ensure location is set on the asset
                if "location" not in asset or not asset["location"]:
                    asset["location"] = location
                items_with_location.append(asset)  # asset contient déjà symbol, value_usd, location, amount
        
        rows = [r for r in _to_rows(items_with_location) if float(r.get("value_usd") or 0.0) >= min_usd]
        
    except Exception as e:
        # Fallback sur la méthode originale en cas d'erreur
        res = await resolve_current_balances(source=source)
        rows = [r for r in _to_rows(res.get("items", [])) if float(r.get("value_usd") or 0.0) >= min_usd]

    # targets - support for dynamic CCS-based targets
    if dynamic_targets and payload.get("dynamic_targets_pct"):
        # CCS/cycle module provides pre-calculated targets
        targets_raw = payload.get("dynamic_targets_pct", {})
        group_targets_pct = {str(k): float(v) for k, v in targets_raw.items()}
    else:
        # Standard targets from user input
        targets_raw = payload.get("group_targets_pct") or payload.get("targets") or {}
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

    plan = _assign_locations_to_actions(plan, rows, min_trade_usd=float(payload.get("min_trade_usd", 25.0)))

    # enrichissement prix (selon "pricing")
    source_used = exchange_data.get("source_used") if 'exchange_data' in locals() else "unknown"
    plan = _enrich_actions_with_prices(plan, rows, pricing_mode=pricing, source_used=source_used)

    # Mettre à jour les exec_hints basés sur les locations assignées (après enrichissement prix)
    from services.rebalance import _format_hint_for_location, _get_exec_hint
    
    # Créer un index des holdings par groupe pour les actions sans location
    holdings_by_group = {}
    for row in rows:
        group = row.get("group")
        if not group:
            continue
        if group not in holdings_by_group:
            holdings_by_group[group] = []
        holdings_by_group[group].append(row)
    
    for action in plan.get("actions", []):
        location = action.get("location")
        action_type = action.get("action", "")
        
        if location and location not in ["Unknown", ""]:
            # Action avec location spécifique - utiliser la nouvelle logique
            action["exec_hint"] = _format_hint_for_location(location, action_type)
        else:
            # Action sans location spécifique - utiliser l'ancienne logique comme fallback
            group = action.get("group", "")
            group_items = holdings_by_group.get(group, [])
            action["exec_hint"] = _get_exec_hint(action, {group: group_items})

    # meta pour UI - fusionner avec les métadonnées pricing existantes
    if not plan.get("meta"):
        plan["meta"] = {}
    # Préserver les métadonnées existantes et ajouter les nouvelles
    meta_update = {
        "source_used": source_used,
        "items_count": len(rows)
    }
    plan["meta"].update(meta_update)
    
    # Mettre à jour le cache des unknown aliases pour les suggestions automatiques
    unknown_aliases = plan.get("unknown_aliases", [])
    if unknown_aliases:
        try:
            from api.taxonomy_endpoints import update_unknown_aliases_cache
            update_unknown_aliases_cache(unknown_aliases)
        except ImportError:
            pass  # Ignore si pas disponible
    
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
    dynamic_targets: bool = Query(False, description="Use dynamic targets from CCS/cycle module"),
    payload: Dict[str, Any] = Body(...)
):
    # réutilise le JSON pour construire le CSV
    plan = await rebalance_plan(source=source, min_usd_raw=min_usd_raw, pricing=pricing, dynamic_targets=dynamic_targets, payload=payload)
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
        if not sym or a.get("usd") is None or a.get("price_used"):
            continue
            
        sym_upper = sym.upper()
        local_price = local_price_map.get(sym_upper)
        market_price = market_price_map.get(sym_upper)
        
        # Déterminer le prix final et la source
        final_price = None
        price_source = "local"
        
        if pricing_mode == "local":
            if local_price:
                final_price = local_price
                price_source = "local"
            # Pas de fallback en mode local pur
        elif pricing_mode == "auto":
            if market_price:
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
    lines = ["group,alias,symbol,action,usd,est_quantity,price_used,exec_hint"]
    for a in actions or []:
        lines.append("{},{},{},{},{:.2f},{},{},{}".format(
            a.get("group",""),
            a.get("alias",""),
            a.get("symbol",""),
            a.get("action",""),
            float(a.get("usd") or 0.0),
            ("" if a.get("est_quantity") is None else f"{a.get('est_quantity')}"),
            ("" if a.get("price_used")   is None else f"{a.get('price_used')}"),
            a.get("exec_hint", "")
        ))
    return "\n".join(lines)

# ---------- debug ----------
@app.get("/debug/ctapi")
async def debug_ctapi():
    """Endpoint de debug pour CoinTracking API"""
    return _debug_probe()

@app.get("/debug/api-keys")
async def debug_api_keys():
    """Expose les clés API depuis .env pour auto-configuration"""
    return {
        "coingecko_api_key": os.getenv("COINGECKO_API_KEY", ""),
        "cointracking_api_key": os.getenv("COINTRACKING_API_KEY", ""),
        "cointracking_api_secret": os.getenv("COINTRACKING_API_SECRET", "")
    }

@app.post("/debug/api-keys")
async def update_api_keys(payload: dict):
    """Met à jour les clés API dans le fichier .env"""
    import re
    from pathlib import Path
    
    env_file = Path(".env")
    if not env_file.exists():
        # Créer le fichier .env s'il n'existe pas
        env_file.write_text("# Clés API générées automatiquement\n")
    
    content = env_file.read_text()
    
    # Définir les mappings clé -> nom dans .env
    key_mappings = {
        "coingecko_api_key": "COINGECKO_API_KEY",
        "cointracking_api_key": "COINTRACKING_API_KEY", 
        "cointracking_api_secret": "COINTRACKING_API_SECRET"
    }
    
    updated = False
    for field_key, env_key in key_mappings.items():
        if field_key in payload and payload[field_key]:
            # Chercher si la clé existe déjà
            pattern = rf"^{env_key}=.*$"
            new_line = f"{env_key}={payload[field_key]}"
            
            if re.search(pattern, content, re.MULTILINE):
                # Remplacer la ligne existante
                content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
            else:
                # Ajouter la nouvelle clé
                content += f"\n{new_line}"
            updated = True
    
    if updated:
        env_file.write_text(content)
        # Recharger les variables d'environnement
        import os
        for field_key, env_key in key_mappings.items():
            if field_key in payload and payload[field_key]:
                os.environ[env_key] = payload[field_key]
    
    return {"success": True, "updated": updated}

# inclure les routes taxonomie, execution, monitoring et analytics
app.include_router(taxonomy_router)
app.include_router(execution_router)
app.include_router(monitoring_router)
app.include_router(analytics_router)

# ---------- Portfolio Analytics ----------
@app.get("/portfolio/metrics")
async def portfolio_metrics(source: str = Query("cointracking")):
    """Métriques calculées du portfolio"""
    try:
        # Récupérer les données de balance actuelles
        res = await resolve_current_balances(source=source)
        rows = _to_rows(res.get("items", []))
        balances = {"source_used": res.get("source_used"), "items": rows}
        
        # Calculer les métriques
        metrics = portfolio_analytics.calculate_portfolio_metrics(balances)
        performance = portfolio_analytics.calculate_performance_metrics(metrics)
        
        return {
            "ok": True,
            "metrics": metrics,
            "performance": performance
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/portfolio/snapshot")
async def save_portfolio_snapshot(source: str = Query("cointracking")):
    """Sauvegarde un snapshot du portfolio pour suivi historique"""
    try:
        # Récupérer les données actuelles
        res = await resolve_current_balances(source=source)
        rows = _to_rows(res.get("items", []))
        balances = {"source_used": res.get("source_used"), "items": rows}
        
        # Sauvegarder le snapshot
        success = portfolio_analytics.save_portfolio_snapshot(balances)
        
        if success:
            return {"ok": True, "message": "Snapshot sauvegardé"}
        else:
            return {"ok": False, "error": "Erreur lors de la sauvegarde"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/portfolio/trend")
async def portfolio_trend(days: int = Query(30, ge=1, le=365)):
    """Données de tendance du portfolio pour graphiques"""
    try:
        trend_data = portfolio_analytics.get_portfolio_trend(days)
        return {"ok": True, "trend": trend_data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/portfolio/breakdown-locations")
async def portfolio_breakdown_locations(
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0)
):
    """
    Renvoie la répartition par exchange à partir de la CT-API.
    Pas de fallback “CoinTracking 100%” sauf si réellement aucune data.
    """
    try:
        if source == "cointracking":
            # Utiliser CSV comme source
            from connectors.cointracking import get_unified_balances_by_exchange
            snap = await get_unified_balances_by_exchange(source="cointracking")
            
            # Appliquer le filtrage min_usd pour CSV
            if min_usd > 0 and snap.get("detailed_holdings"):
                detailed = snap.get("detailed_holdings", {})
                filtered_detailed = {}
                for loc, assets in detailed.items():
                    filtered_assets = [a for a in assets if float(a.get("value_usd", 0)) >= min_usd]
                    if filtered_assets:
                        filtered_detailed[loc] = filtered_assets
                
                # Recalculer les exchanges
                exchanges = []
                for loc, assets in filtered_detailed.items():
                    total_val = sum(float(a.get("value_usd", 0)) for a in assets)
                    if total_val >= min_usd:
                        exchanges.append({
                            "location": loc,
                            "total_value_usd": round(total_val, 2),
                            "asset_count": len(assets),
                            "assets": sorted(assets, key=lambda x: float(x.get("value_usd", 0)), reverse=True)
                        })
                exchanges.sort(key=lambda x: x["total_value_usd"], reverse=True)
                snap = {"exchanges": exchanges, "detailed_holdings": filtered_detailed}
        else:
            # Utiliser API
            snap = await _load_ctapi_exchanges(min_usd=min_usd)
        exchanges = snap.get("exchanges") or []
        if exchanges:
            total = sum(float(x.get("total_value_usd") or 0) for x in exchanges)
            locs = []
            for e in exchanges:
                tv = float(e.get("total_value_usd") or 0)
                locs.append({
                    "location": e.get("location"),
                    "total_value_usd": tv,
                    "asset_count": int(e.get("asset_count") or len(e.get("assets") or [])),
                    "percentage": (tv / total * 100.0) if total > 0 else 0.0,
                    "assets": e.get("assets") or [],
                })
            return {
                "ok": True,
                "breakdown": {
                    "total_value_usd": total,
                    "location_count": len(locs),
                    "locations": locs,
                },
                "fallback": False,
                "message": "",
            }
    except Exception:
        pass

    # Fallback explicite si VRAIMENT rien
    return {
        "ok": True,
        "breakdown": {
            "total_value_usd": 0.0,
            "location_count": 1,
            "locations": [{
                "location": "CoinTracking",
                "total_value_usd": 0.0,
                "asset_count": 0,
                "percentage": 100.0,
                "assets": []
            }]
        },
        "fallback": True,
        "message": "No location data available, using default location"
    }



# Stratégies de rebalancing prédéfinies
REBALANCING_STRATEGIES = {
    "conservative": {
        "name": "Conservative",
        "description": "Stratégie prudente privilégiant la stabilité",
        "risk_level": "Faible",
        "icon": "🛡️",
        "allocations": {
            "BTC": 40,
            "ETH": 25,
            "Stablecoins": 20,
            "L1/L0 majors": 10,
            "Others": 5
        },
        "characteristics": [
            "Forte allocation en Bitcoin et Ethereum",
            "20% en stablecoins pour la stabilité", 
            "Exposition limitée aux altcoins"
        ]
    },
    "balanced": {
        "name": "Balanced", 
        "description": "Équilibre entre croissance et stabilité",
        "risk_level": "Moyen",
        "icon": "⚖️",
        "allocations": {
            "BTC": 35,
            "ETH": 30,
            "Stablecoins": 10,
            "L1/L0 majors": 15,
            "DeFi": 5,
            "Others": 5
        },
        "characteristics": [
            "Répartition équilibrée majors/altcoins",
            "Exposition modérée aux nouveaux secteurs",
            "Reserve de stabilité réduite"
        ]
    },
    "growth": {
        "name": "Growth",
        "description": "Croissance agressive avec plus d'altcoins", 
        "risk_level": "Élevé",
        "icon": "🚀",
        "allocations": {
            "BTC": 25,
            "ETH": 25,
            "L1/L0 majors": 20,
            "DeFi": 15,
            "AI/Data": 10,
            "Others": 5
        },
        "characteristics": [
            "Réduction de la dominance BTC/ETH",
            "Forte exposition aux secteurs émergents",
            "Potentiel de croissance élevé"
        ]
    },
    "defi_focus": {
        "name": "DeFi Focus",
        "description": "Spécialisé dans l'écosystème DeFi",
        "risk_level": "Élevé", 
        "icon": "🔄",
        "allocations": {
            "ETH": 30,
            "DeFi": 35,
            "L2/Scaling": 15,
            "BTC": 15,
            "Others": 5
        },
        "characteristics": [
            "Forte exposition DeFi et Layer 2",
            "Ethereum comme base principale",
            "Bitcoin comme réserve de valeur"
        ]
    },
    "accumulation": {
        "name": "Accumulation",
        "description": "Accumulation long terme des majors",
        "risk_level": "Faible-Moyen",
        "icon": "📈", 
        "allocations": {
            "BTC": 50,
            "ETH": 35,
            "L1/L0 majors": 10,
            "Stablecoins": 5
        },
        "characteristics": [
            "Très forte dominance BTC/ETH",
            "Vision long terme",
            "Minimum de diversification"
        ]
    }
}

@app.get("/strategies/list")
async def get_rebalancing_strategies():
    """Liste des stratégies de rebalancing prédéfinies"""
    return {
        "ok": True,
        "strategies": REBALANCING_STRATEGIES
    }

@app.get("/strategies/{strategy_id}")
async def get_strategy_details(strategy_id: str):
    """Détails d'une stratégie spécifique"""
    if strategy_id not in REBALANCING_STRATEGIES:
        return {"ok": False, "error": "Stratégie non trouvée"}
    
    return {
        "ok": True,
        "strategy": REBALANCING_STRATEGIES[strategy_id]
    }

@app.get("/portfolio/alerts")
async def get_portfolio_alerts(source: str = Query("cointracking"), drift_threshold: float = Query(10.0)):
    """Calcule les alertes de dérive du portfolio par rapport aux targets"""
    try:
        # Récupérer les données de portfolio
        res = await resolve_current_balances(source=source)
        rows = _to_rows(res.get("items", []))
        balances = {"source_used": res.get("source_used"), "items": rows}
        
        # Calculer les métriques actuelles
        metrics = portfolio_analytics.calculate_portfolio_metrics(balances)
        
        if not metrics.get("ok"):
            return {"ok": False, "error": "Impossible de calculer les métriques"}
        
        current_distribution = metrics["metrics"]["group_distribution"]
        total_value = metrics["metrics"]["total_value_usd"]
        
        # Targets par défaut (peuvent être dynamiques dans le futur)
        default_targets = {
            "BTC": 35,
            "ETH": 25, 
            "Stablecoins": 10,
            "SOL": 10,
            "L1/L0 majors": 10,
            "Others": 10
        }
        
        # Calculer les déviations
        alerts = []
        max_drift = 0
        critical_count = 0
        warning_count = 0
        
        for group, target_pct in default_targets.items():
            current_value = current_distribution.get(group, 0)
            current_pct = (current_value / total_value * 100) if total_value > 0 else 0
            
            drift = abs(current_pct - target_pct)
            drift_direction = "over" if current_pct > target_pct else "under"
            
            # Déterminer le niveau d'alerte
            if drift > drift_threshold * 1.5:  # > 15% par défaut
                level = "critical"
                critical_count += 1
            elif drift > drift_threshold:  # > 10% par défaut
                level = "warning" 
                warning_count += 1
            else:
                level = "ok"
            
            if drift > max_drift:
                max_drift = drift
            
            # Calculer l'action recommandée
            value_diff = (target_pct - current_pct) / 100 * total_value
            action = "buy" if value_diff > 0 else "sell"
            action_amount = abs(value_diff)
            
            alerts.append({
                "group": group,
                "target_pct": target_pct,
                "current_pct": round(current_pct, 2),
                "current_value": current_value,
                "drift": round(drift, 2),
                "drift_direction": drift_direction,
                "level": level,
                "action": action,
                "action_amount_usd": round(action_amount, 2),
                "priority": round(drift, 2)  # Plus la dérive est grande, plus c'est prioritaire
            })
        
        # Trier par priorité (dérive décroissante)
        alerts.sort(key=lambda x: x["priority"], reverse=True)
        
        # Statut global
        if critical_count > 0:
            global_status = "critical"
            global_message = f"{critical_count} groupe(s) en dérive critique"
        elif warning_count > 0:
            global_status = "warning"
            global_message = f"{warning_count} groupe(s) nécessitent attention"
        else:
            global_status = "healthy"
            global_message = "Portfolio équilibré"
        
        return {
            "ok": True,
            "alerts": {
                "global_status": global_status,
                "global_message": global_message,
                "max_drift": round(max_drift, 2),
                "drift_threshold": drift_threshold,
                "total_value_usd": total_value,
                "critical_count": critical_count,
                "warning_count": warning_count,
                "groups": alerts,
                "recommendations": [
                    alert for alert in alerts[:3] 
                    if alert["level"] in ["critical", "warning"]
                ]
            }
        }
        
    except Exception as e:
        return {"ok": False, "error": str(e)}
    

