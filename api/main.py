# --- imports (en haut du fichier) ---
from __future__ import annotations
from typing import Any, Dict, List
from time import monotonic
import os
import time
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
async def resolve_current_balances(source: str) -> Dict[str, Any]:
    """
    Retourne {source_used, items:[{symbol, value_usd, location, ...}]} avec informations de location
    """
    if source == "stub":
        # mini portefeuille de démo avec locations corrected
        items = [
            {"symbol": "BTC", "value_usd": 117000.0, "location": "Demo Wallet"},
            {"symbol": "ETH", "value_usd": 60000.0, "location": "Demo Wallet"},
            {"symbol": "USDT", "value_usd": 5000.0, "location": "Demo Wallet"},
            {"symbol": "USDC", "value_usd": 900.0, "location": "Demo Wallet"},
            {"symbol": "SOL",  "value_usd": 3000.0, "location": "Demo Wallet"},
            {"symbol": "LINK", "value_usd": 7000.0, "location": "Demo Wallet"},
            {"symbol": "AAVE", "value_usd": 4500.0, "location": "Demo Wallet"},
            {"symbol": "DOGE", "value_usd": 5000.0, "location": "Demo Wallet"},
            {"symbol": "EUR",  "value_usd": 120.0, "location": "Demo Wallet"},
        ]
        return {"source_used": "stub", "items": items}

    # Pour les sources cointracking et cointracking_api, essayer d'abord d'obtenir les données avec locations
    try:
        from connectors.cointracking import get_unified_balances_by_exchange
        exchange_data = await get_unified_balances_by_exchange(source=source)
        
        # Extraire tous les items avec leurs locations des detailed_holdings
        items_with_location = []
        detailed_holdings = exchange_data.get("detailed_holdings", {})
        
        for location, assets in detailed_holdings.items():
            for asset in assets:
                items_with_location.append(asset)  # asset contient déjà symbol, value_usd, location, amount
        
        if items_with_location:
            return {
                "source_used": exchange_data.get("source_used", source),
                "items": items_with_location
            }
    except Exception as e:
        # En cas d'erreur avec la fonction unifiée, fallback sur les anciennes méthodes
        pass

    # Fallback sur les méthodes originales sans location
    if source == "cointracking":
        res = await ct_file.get_current_balances(source="cointracking")
        items = res.get("items", []) if isinstance(res, dict) else (res or [])
        # Ajouter location par défaut
        for item in items:
            if "location" not in item or not item["location"]:
                item["location"] = "Portfolio"
        return {"source_used": "cointracking", "items": items}

    if source == "cointracking_api":
        res = await ct_api_get_current_balances()
        items = res.get("items", []) if isinstance(res, dict) else (res or [])
        # Ajouter location par défaut
        for item in items:
            if "location" not in item or not item["location"]:
                item["location"] = "CoinTracking"
        return {"source_used": "cointracking_api", "items": items}

    # fallback: cointracking (CSV)
    res = await ct_file.get_current_balances(source="cointracking")
    items = res.get("items", []) if isinstance(res, dict) else (res or [])
    # Ajouter location par défaut
    for item in items:
        if "location" not in item or not item["location"]:
            item["location"] = "Portfolio"
    return {"source_used": "cointracking", "items": items}


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

    # portefeuille - utiliser la méthode normale pour l'instant
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

    # enrichissement prix (selon "pricing")
    source_used = res.get("source_used")
    plan = _enrich_actions_with_prices(plan, rows, pricing_mode=pricing, source_used=source_used)

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
async def portfolio_breakdown_locations(source: str = Query("cointracking")):
    """Breakdown du portfolio par exchange/location avec support de toutes les sources de données"""
    try:
        from connectors.cointracking import get_unified_balances_by_exchange
        
        # Utiliser la fonction unifiée qui gère toutes les sources (CSV, API, stub)
        exchange_data = await get_unified_balances_by_exchange(source=source)
        exchanges = exchange_data.get("exchanges", [])
        detailed_holdings = exchange_data.get("detailed_holdings", {})
        
        total_value = sum(ex.get("total_value_usd", 0) for ex in exchanges)
        
        # Si aucune donnée, créer une location par défaut avec 100%
        if not exchanges or total_value == 0:
            # Déterminer la location par défaut selon la source
            default_location = "Portfolio" if source == "cointracking" else "Demo Wallet" if source in ("stub", "demo") else "CoinTracking"
            
            locations = [{
                "location": default_location,
                "total_value_usd": 0.0,
                "asset_count": 0,
                "percentage": 100.0,  # 100% même si valeur est 0
                "assets": []
            }]
            
            return {
                "ok": True,
                "breakdown": {
                    "total_value_usd": 0.0,
                    "location_count": 1,
                    "locations": locations
                },
                "fallback": True,
                "message": "No location data available, using default location"
            }
        
        # Convertir au format attendu par le frontend
        locations = []
        for exchange in exchanges:
            location_name = exchange.get("location", "Portfolio")
            location_value = exchange.get("total_value_usd", 0)
            
            # Récupérer les assets détaillés pour cette location
            assets = detailed_holdings.get(location_name, [])
            
            # Calculer les pourcentages des assets dans cette location
            for asset in assets:
                asset["percentage"] = (asset["value_usd"] / location_value) if location_value > 0 else 0
                asset["alias"] = asset.get("symbol")  # Pour compatibilité frontend
            
            locations.append({
                "location": location_name,
                "total_value_usd": location_value,
                "asset_count": exchange.get("asset_count", 0),
                "percentage": (location_value / total_value) if total_value > 0 else 0,
                "assets": assets
            })
        
        return {
            "ok": True,
            "breakdown": {
                "total_value_usd": total_value,
                "location_count": len(locations),
                "locations": locations
            },
            "source_used": exchange_data.get("source_used", source)
        }
        
    except Exception as e:
        return {"ok": False, "error": str(e)}

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
