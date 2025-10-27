from __future__ import annotations
from typing import Any, Dict, List
from time import monotonic
import os, sys, inspect, hashlib, time, json
from datetime import datetime
import httpx
from fastapi import FastAPI, Query, Body, Response, HTTPException, Request, APIRouter, Depends, Header, Path
import logging
from logging.handlers import RotatingFileHandler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from api.middleware import RateLimitMiddleware
from api.middlewares import (
    add_security_headers_middleware,
    request_timing_middleware,
    request_logger_middleware,
    no_cache_dev_middleware,
)
from api.services.location_assigner import assign_locations_to_actions
from api.services.price_enricher import enrich_actions_with_prices, get_data_age_minutes
from api.services.cointracking_helpers import (
    normalize_loc,
    classify_location,
    pick_primary_location_for_symbol,
    load_ctapi_exchanges
)
from api.services.csv_helpers import load_csv_balances, to_csv
from api.services.utils import parse_min_usd, to_rows, norm_primary_symbols
from fastapi import middleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Charger les variables d'environnement depuis .env
load_dotenv()

# Fix joblib/loky Windows encoding issue with Python 3.13
# Set before any scikit-learn imports to avoid wmic auto-detection errors
if not os.getenv('LOKY_MAX_CPU_COUNT'):
    os.environ['LOKY_MAX_CPU_COUNT'] = '4'

# Configuration centralisée avec Pydantic
from config import get_settings
settings = get_settings()

# Variables de compatibilité (pour ne pas casser le code existant)
DEBUG = settings.is_debug_enabled()
APP_DEBUG = DEBUG
LOG_LEVEL = settings.logging.log_level
CORS_ORIGINS = settings.get_cors_origins()
ENVIRONMENT = settings.environment
# Par défaut, on désactive les stubs pour éviter de masquer des erreurs de config.
ALLOW_STUB_SOURCES = (os.getenv("ALLOW_STUB_SOURCES", "false").strip().lower() == "true")
COMPUTE_ON_STUB_SOURCES = (os.getenv("COMPUTE_ON_STUB_SOURCES", "false").strip().lower() == "true")

# Config logger (dev-friendly by default) — initialize early so it's available in imports below
# Créer le dossier logs s'il n'existe pas
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Configuration du logging avec handlers multiples (console + fichier rotatif)
log_level = getattr(logging, LOG_LEVEL, logging.INFO)
log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Configuration avec RotatingFileHandler pour limiter la taille des logs
logging.basicConfig(
    level=log_level,
    format=log_format,
    handlers=[
        # Console (stdout) - pour le terminal
        logging.StreamHandler(),
        # Fichier rotatif - 5 MB par fichier, 3 backups (15 MB total)
        # Adapté pour Claude Code: fichiers de taille raisonnable
        RotatingFileHandler(
            LOG_DIR / "app.log",
            maxBytes=5*1024*1024,  # 5 MB par fichier (facile à lire pour une IA)
            backupCount=3,          # Garder 3 fichiers de backup (15 MB total max)
            encoding="utf-8"
        )
    ]
)
logger = logging.getLogger("crypto-rebalancer")
logger.info(f"📝 Logging initialized: console + file (rotating 5MB x3 backups) -> {LOG_DIR / 'app.log'}")

# Import différé des connecteurs pour éviter les blocages réseau au démarrage
# from connectors import cointracking as ct_file
# from connectors.cointracking_api import get_current_balances as ct_api_get_current_balances, _debug_probe

# Imports avec fallback pour éviter les crashs
try:
    from services.rebalance import plan_rebalance
    REBALANCE_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    logger.warning(f"Rebalance service not available: {e}")
    REBALANCE_AVAILABLE = False

try:
    from services.pricing import get_prices_usd
    PRICING_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    logger.warning(f"Pricing service not available: {e}")
    PRICING_AVAILABLE = False

try:
    from services.portfolio import portfolio_analytics
    PORTFOLIO_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    logger.warning(f"Portfolio analytics not available: {e}")
    PORTFOLIO_AVAILABLE = False

# Import BalanceService singleton for resolving balances
from services.balance_service import balance_service
from api.taxonomy_endpoints import router as taxonomy_router
# Execution endpoints - modular routers (Phase 2.1)
from api.execution import (
    validation_router,
    execution_router,
    monitoring_router,
    governance_router,
    signals_router
)
from api.analytics_endpoints import router as analytics_router
from api.kraken_endpoints import router as kraken_router
from api.smart_taxonomy_endpoints import router as smart_taxonomy_router  # FIXED - aiohttp mocké
from api.advanced_rebalancing_endpoints import router as advanced_rebalancing_router
from api.risk_endpoints import router as risk_router
from api.risk_dashboard_endpoints import router as risk_dashboard_router
from api.risk_bourse_endpoints import router as risk_bourse_router
from api.ml_bourse_endpoints import router as ml_bourse_router
from api.ml_crypto_endpoints import router as ml_crypto_router
from api.execution_history import router as execution_history_router
from api.monitoring_advanced import router as monitoring_advanced_router
from api.portfolio_monitoring import router as portfolio_monitoring_router
from api.csv_endpoints import router as csv_router
from api.portfolio_optimization_endpoints import router as portfolio_optimization_router
from api.advanced_analytics_endpoints import router as advanced_analytics_router
from api.performance_endpoints import router as performance_router
from api.unified_ml_endpoints import router as ml_router
from api.multi_asset_endpoints import router as multi_asset_router
from api.backtesting_endpoints import router as backtesting_router
from api.alerts_endpoints import router as alerts_router
from api.strategy_endpoints import router as strategy_router
from api.saxo_endpoints import router as saxo_router
from api.advanced_risk_endpoints import router as advanced_risk_router
from api.realtime_endpoints import router as realtime_router
from api.intelligence_endpoints import router as intelligence_router
from api.user_settings_endpoints import router as user_settings_router
from api.wealth_endpoints import router as wealth_router
from api.sources_endpoints import router as sources_router
from api.fx_endpoints import router as fx_router
from api.debug_router import router as debug_router
from api.health_router import router as health_router
from api.coingecko_proxy_router import router as coingecko_proxy_router
from api.pricing_router import router as pricing_router
from api.rebalancing_strategy_router import router as rebalancing_strategy_router
from api.config_router import router as config_router
## NOTE: market_endpoints est désactivé tant que le client prix n'est pas réimplémenté
from api.market_endpoints import router as market_router
from api.exceptions import (
    CryptoRebalancerException, APIException, ValidationException,
    ConfigurationException, TradingException, DataException, ErrorCodes
)
from api.deps import get_active_user
# Imports optionnels pour extensions futures (réservé)
from api.models import APIKeysRequest, PortfolioMetricsRequest

# Logger already configured above

app = FastAPI(docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json")
logger.info("FastAPI initialized: docs=%s redoc=%s openapi=%s",
            "/docs", "/redoc", "/openapi.json")

# /metrics Prometheus (activable en prod via variable d'environnement)
if os.getenv("ENABLE_METRICS", "0") == "1":
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app, include_in_schema=False)
    except (ImportError, ModuleNotFoundError) as e:
        logging.getLogger(__name__).warning("Prometheus non activé: %s", e)

# Startup handlers (refactored to api/startup.py)
from api.startup import get_startup_handler, get_shutdown_handler

@app.on_event("startup")
async def startup():
    """Application startup - initialize ML, Governance, Alerts"""
    handler = get_startup_handler()
    await handler()

@app.on_event("shutdown")
async def shutdown():
    """Application shutdown - cleanup resources"""
    handler = get_shutdown_handler()
    await handler()

# Gestionnaires d'exceptions globaux
@app.exception_handler(CryptoRebalancerException)
async def crypto_exception_handler(request: Request, exc: CryptoRebalancerException):
    """Gestionnaire pour toutes les exceptions personnalisées"""
    status_code = 400
    if isinstance(exc, APIException):
        status_code = exc.status_code or 500
    elif isinstance(exc, ValidationException):
        status_code = ErrorCodes.INVALID_INPUT
    elif isinstance(exc, ConfigurationException):
        status_code = ErrorCodes.INVALID_CONFIG
    elif isinstance(exc, TradingException):
        status_code = ErrorCodes.INSUFFICIENT_BALANCE
    elif isinstance(exc, DataException):
        status_code = ErrorCodes.DATA_NOT_FOUND
    
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
            "path": request.url.path
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Gestionnaire pour toutes les autres exceptions"""
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "details": str(exc) if app.debug else None,
            "path": request.url.path
        }
    )

# CORS sécurisé avec configuration dynamique
default_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
    "file://",  # Pour les fichiers HTML statiques (certains navigateurs envoient Origin: null)
    "null",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=(CORS_ORIGINS or default_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Middleware de sécurité
if not DEBUG:
    # HTTPS redirect en production seulement
    app.add_middleware(HTTPSRedirectMiddleware)

# TrustedHost config selon l'environnement
if DEBUG:
    # En développement, plus permissif pour les tests
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Permet tous les hosts en dev
    )
else:
    # En production, strict
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.localhost"],
    )

# Compression GZip pour améliorer les performances
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ========== Middleware Registration (Modular) ==========
# Extracted to api/middlewares/ for maintainability
# See: api/middlewares/{security,timing,logging,cache}.py

# Rate limiting (production only)
if ENVIRONMENT == "production" or not DEBUG:
    app.add_middleware(RateLimitMiddleware)
    logger.info("Rate limiting middleware enabled (production mode)")
else:
    logger.info("Rate limiting middleware disabled (development mode)")

# Security headers (CSP, HSTS, etc.)
app.middleware("http")(add_security_headers_middleware)

# Request timing and structured logging
app.middleware("http")(request_timing_middleware)

# Request logger (debug mode)
app.middleware("http")(request_logger_middleware)

# No-cache for static files (development only)
app.middleware("http")(no_cache_dev_middleware)

BASE_DIR = Path(__file__).resolve().parent.parent  # répertoire du repo (niveau au-dessus d'api/)
STATIC_DIR = BASE_DIR / "static"                    # D:\Python\crypto-rebal-starter\static
DATA_DIR = BASE_DIR / "data"                        # D:\Python\crypto-rebal-starter\data

logger.debug(f"BASE_DIR = {BASE_DIR}")
logger.debug(f"STATIC_DIR = {STATIC_DIR}, exists = {STATIC_DIR.exists()}")
logger.debug(f"DATA_DIR = {DATA_DIR}, exists = {DATA_DIR.exists()}")

if not STATIC_DIR.exists():
    logger.warning("STATIC_DIR not found, using fallback")
    # fallback si l'arbo a changé
    STATIC_DIR = Path.cwd() / "static"
    
if not DATA_DIR.exists():
    logger.warning("DATA_DIR not found, using fallback")
    DATA_DIR = Path.cwd() / "data"
    
logger.debug(f"Final STATIC_DIR = {STATIC_DIR}")
logger.debug(f"Final DATA_DIR = {DATA_DIR}")

# Vérifier le fichier CSV spécifiquement
csv_file = DATA_DIR / "raw" / "CoinTracking - Current Balance.csv"
logger.debug(f"CSV file = {csv_file}, exists = {csv_file.exists()}")

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR), html=True),
    name="static",
)

# Mount data directory for CSV access (nécessaire en production pour les dashboards)
app.mount(
    "/data",
    StaticFiles(directory=str(DATA_DIR)),
    name="data",
)

# Mount config directory for users.json access
CONFIG_DIR = BASE_DIR / "config"
if CONFIG_DIR.exists():
    app.mount(
        "/config",
        StaticFiles(directory=str(CONFIG_DIR)),
        name="config",
    )

# Optionnel: exposer les pages de test HTML en local (sécurisé par DEBUG)
try:
    TESTS_DIR = BASE_DIR / "tests"
    if DEBUG and TESTS_DIR.exists():
        logger.debug(f"Mounting TESTS_DIR at /tests -> {TESTS_DIR}")
        app.mount(
            "/tests",
            StaticFiles(directory=str(TESTS_DIR), html=True),
            name="tests",
        )
except (OSError, RuntimeError) as e:
    logger.warning(f"Could not mount /tests: {e}")

# Cache prix unifié utilisant le système centralisé
_PRICE_CACHE: Dict[str, tuple] = {}  # symbol -> (ts, price)
from api.utils.cache import cache_get as _cache_get, cache_set as _cache_set
 
# >>> BEGIN: CT-API helpers (centralized constants) >>>
try:
    from connectors import cointracking_api as ct_api
except ImportError as e:
    logger.warning(f"Could not import from connectors package: {e}")
    try:
        import cointracking_api as ct_api  # fallback au cas où le package n'est pas packagé "connectors"
        logger.info("Using fallback import for cointracking_api")
    except ImportError as fallback_error:
        logger.error(f"Could not import cointracking_api at all: {fallback_error}")
        ct_api = None
    else:
        # Fallback OK: ne pas écraser ct_api
        pass
except (SyntaxError, AttributeError, RuntimeError, TypeError, ValueError) as e:
    logger.error(f"Error importing cointracking_api: {e}", exc_info=True)
    ct_api = None

# CSV/API cointracking facade (safe import)
try:
    from connectors import cointracking as ct_file
except (ImportError, ModuleNotFoundError) as e:
    logger.warning(f"CoinTracking CSV/API facade not available: {e}")
    ct_file = None

# CoinTracking helpers moved to api/services/cointracking_helpers.py
# - normalize_loc
# - classify_location
# - pick_primary_location_for_symbol
# - load_ctapi_exchanges

# ---------- utils ----------
# Utility functions moved to api/services/utils.py
# - parse_min_usd
# - to_rows
# - norm_primary_symbols

# _get_data_age_minutes moved to api/services/price_enricher.py
# _calculate_price_deviation removed (dead code, never called)


# ---------- source resolver ----------
# CSV helper moved to api/services/csv_helpers.py
# - load_csv_balances

async def resolve_current_balances(source: str = Query("cointracking_api"), user_id: str = "demo") -> Dict[str, Any]:
    """
    Retourne {source_used, items:[{symbol, alias, amount, value_usd, location}]}
    Utilise UserDataRouter pour router les données par utilisateur.

    NOTE: This function now delegates to services.balance_service.BalanceService
    for better separation of concerns and to break circular dependencies.

    The actual implementation is in services/balance_service.py
    """
    # Delegate to BalanceService to break circular dependencies
    return await balance_service.resolve_current_balances(source=source, user_id=user_id)


# Legacy implementation moved to services/balance_service.py for better separation
# This eliminates circular dependencies with AlertEngine and other modules

# _assign_locations_to_actions moved to api/services/location_assigner.py

# Helper function moved to unified_data.py to avoid circular imports

# Debug endpoint removed

# ---------- balances ----------
@app.get("/balances/current")
async def balances_current(
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0),
    user: str = Depends(get_active_user)
):
    from api.unified_data import get_unified_filtered_balances
    return await get_unified_filtered_balances(source=source, min_usd=min_usd, user_id=user)


# ---------- rebalance (JSON) ----------
@app.post("/rebalance/plan")
async def rebalance_plan(
    source: str = Query("cointracking"),
    min_usd_raw: str | None = Query(None, alias="min_usd"),
    pricing: str = Query("local"),   # local | auto
    dynamic_targets: bool = Query(False, description="Use dynamic targets from CCS/cycle module"),
    payload: Dict[str, Any] = Body(...),
    pricing_diag: bool = Query(False, description="Include pricing diagnostic details in response meta")
):
    min_usd = parse_min_usd(min_usd_raw, default=1.0)

    # portefeuille - utiliser la fonction helper unifiée
    from api.unified_data import get_unified_filtered_balances
    unified_data = await get_unified_filtered_balances(source=source, min_usd=min_usd)
    rows = unified_data.get("items", [])

    # targets - support for dynamic CCS-based targets
    if dynamic_targets and payload.get("dynamic_targets_pct"):
        # CCS/cycle module provides pre-calculated targets
        targets_raw = payload.get("dynamic_targets_pct", {})
        group_targets_pct = {str(k): float(v) for k, v in targets_raw.items()}
    else:
        # Standard targets from user input
        targets_raw = payload.get("group_targets_pct") or payload.get("targets") or payload.get("target_allocations") or {}
        group_targets_pct: Dict[str, float] = {}
        if isinstance(targets_raw, dict):
            group_targets_pct = {str(k): float(v) for k, v in targets_raw.items()}
        elif isinstance(targets_raw, list):
            for it in targets_raw:
                g = str(it.get("group"))
                p = float(it.get("weight_pct", 0.0))
                if g:
                    group_targets_pct[g] = p

    primary_symbols = norm_primary_symbols(payload.get("primary_symbols"))

    # Permettre un fallback: "pricing_diag" dans le body JSON si non passé en query
    if not pricing_diag:
        try:
            pricing_diag = bool(payload.get("pricing_diag", False))
        except (ValueError, TypeError, KeyError):
            pricing_diag = False

    plan = plan_rebalance(
        rows=rows,
        group_targets_pct=group_targets_pct,
        min_usd=min_usd,
        sub_allocation=payload.get("sub_allocation", "proportional"),
        primary_symbols=primary_symbols,
        min_trade_usd=float(payload.get("min_trade_usd", 25.0)),
    )

    logger.debug(f"🔧 BEFORE assign_locations_to_actions: plan has {len(plan.get('actions', []))} actions")
    plan = assign_locations_to_actions(plan, rows, min_trade_usd=float(payload.get("min_trade_usd", 25.0)))
    logger.debug(f"🔧 AFTER assign_locations_to_actions: plan has {len(plan.get('actions', []))} actions")

    # enrichissement prix (selon "pricing")
    source_used = unified_data.get("source_used", source)
    plan = await enrich_actions_with_prices(plan, rows, pricing_mode=pricing, source_used=source_used, diagnostic=pricing_diag)

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
    csv_text = to_csv(actions)
    headers = {"Content-Disposition": 'attachment; filename="rebalance-actions.csv"'}
    return Response(content=csv_text, media_type="text/csv", headers=headers)


# ---------- helpers prix + csv ----------
# _enrich_actions_with_prices moved to api/services/price_enricher.py
# to_csv moved to api/services/csv_helpers.py

@app.get("/proxy/fred/bitcoin")
async def proxy_fred_bitcoin(start_date: str = "2014-01-01", limit: int = None, user: str = Depends(get_active_user)):
    """Proxy pour récupérer les données Bitcoin historiques via FRED API (user-scoped)"""
    from api.services.user_fs import UserScopedFS
    from pathlib import Path

    # Lire la clé FRED depuis les user settings
    project_root = str(Path(__file__).parent.parent)
    user_fs = UserScopedFS(project_root, user)
    settings = user_fs.read_json("config.json") if user_fs.exists("config.json") else {}
    fred_api_key = settings.get("fred_api_key") or os.getenv("FRED_API_KEY")

    if not fred_api_key:
        raise HTTPException(status_code=503, detail="FRED API key not configured")
    
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": "CBBTCUSD",
            "api_key": fred_api_key,
            "file_type": "json",
            "observation_start": start_date
        }
        if limit:
            params["limit"] = limit
            
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            
        if response.status_code == 200:
            data = response.json()
            if "observations" in data:
                # Transformer les données au format attendu par le frontend
                bitcoin_data = []
                for obs in data["observations"]:
                    if obs["value"] != "." and obs["value"] is not None:
                        try:
                            price = float(obs["value"])
                            timestamp = int(datetime.fromisoformat(obs["date"]).timestamp() * 1000)
                            bitcoin_data.append({
                                "time": timestamp,
                                "price": price,
                                "date": obs["date"]
                            })
                        except (ValueError, TypeError):
                            continue
                
                return {
                    "success": True,
                    "source": "FRED (CBBTCUSD)",
                    "data": bitcoin_data,
                    "count": len(bitcoin_data),
                    "raw_count": data.get("count", 0)
                }
        
        return {
            "success": False,
            "error": f"FRED API error: HTTP {response.status_code}",
            "data": []
        }

    except httpx.HTTPError as e:
        logger.error(f"HTTP error in FRED proxy: {e}")
        return {
            "success": False,
            "error": f"HTTP error: {str(e)}",
            "data": []
        }
    except httpx.TimeoutException as e:
        logger.error(f"Timeout in FRED proxy: {e}")
        return {
            "success": False,
            "error": f"Timeout: {str(e)}",
            "data": []
        }
    except (ValueError, KeyError) as e:
        logger.warning(f"Data parsing error in FRED proxy: {e}")
        return {
            "success": False,
            "error": f"Parsing error: {str(e)}",
            "data": []
        }

# inclure les routes taxonomie, execution, monitoring et analytics
app.include_router(taxonomy_router)
# Execution routers - modular structure (Phase 2.1)
app.include_router(validation_router)
app.include_router(execution_router)
app.include_router(monitoring_router)
app.include_router(governance_router)
app.include_router(signals_router)
# Analytics router monté une seule fois avec prefix=/api/analytics
app.include_router(analytics_router, prefix="/api")
app.include_router(market_router)
app.include_router(kraken_router)
app.include_router(smart_taxonomy_router)
app.include_router(advanced_rebalancing_router)
app.include_router(risk_router)
# app.include_router(risk_dashboard_router)  # ⛔️ DÉSACTIVÉ - Conflit route /api/risk/dashboard avec risk_router (Shadow Mode V2)
app.include_router(execution_history_router)
app.include_router(monitoring_advanced_router)
app.include_router(portfolio_monitoring_router)
app.include_router(csv_router)
app.include_router(saxo_router)
app.include_router(risk_bourse_router)  # Risk management pour Bourse/Saxo
app.include_router(ml_bourse_router)  # ML predictions pour Bourse/Saxo
app.include_router(ml_crypto_router, prefix="/api/ml/crypto", tags=["ML Crypto"])  # ML regime detection pour Bitcoin
app.include_router(portfolio_optimization_router)
app.include_router(performance_router)
app.include_router(alerts_router)
# ML endpoints avec chargement ultra-lazy (pas d'import au démarrage)
ml_router_lazy = APIRouter(prefix="/api/ml", tags=["ML (lazy)"])

@ml_router_lazy.get("/status")
async def get_ml_status_lazy():
    """Status ML avec chargement à la demande"""
    try:
        # Import seulement quand cette route est appelée
        from services.ml_pipeline_manager_optimized import optimized_pipeline_manager as pipeline_manager
        status = pipeline_manager.get_pipeline_status()
        return {
            "pipeline_status": status,
            "timestamp": datetime.now().isoformat(),
            "loading_mode": "lazy"
        }
    except (ImportError, ModuleNotFoundError, RuntimeError, AttributeError) as e:
        return {
            "error": "ML system not ready",
            "details": str(e),
            "status": "loading",
            "loading_mode": "lazy"
        }

@ml_router_lazy.get("/health")  
async def ml_health_lazy():
    """Health check ML minimal sans imports lourds"""
    return {
        "status": "available", 
        "message": "ML system ready for lazy loading",
        "timestamp": datetime.now().isoformat()
    }

app.include_router(ml_router_lazy)
# Test simple endpoint pour debugging
@app.get("/api/ml/pipeline/test")
async def test_pipeline():
    return {"message": "Pipeline API is working!"}
app.include_router(ml_router)
app.include_router(multi_asset_router)
app.include_router(backtesting_router)
app.include_router(advanced_analytics_router)
app.include_router(rebalancing_strategy_router)
app.include_router(strategy_router)
app.include_router(advanced_risk_router)
app.include_router(realtime_router)
app.include_router(intelligence_router)
app.include_router(user_settings_router)
app.include_router(sources_router)
app.include_router(wealth_router)
app.include_router(fx_router)
app.include_router(debug_router)
app.include_router(health_router)
app.include_router(coingecko_proxy_router)  # CoinGecko CORS proxy with caching
app.include_router(pricing_router)
app.include_router(config_router)
# Phase 3 Unified Orchestration
from api.unified_phase3_endpoints import router as unified_phase3_router
app.include_router(unified_phase3_router)

# Portfolio Analytics (refactored endpoints)
from api.portfolio_endpoints import router as portfolio_router
app.include_router(portfolio_router)

# Crypto-Toolbox router (native FastAPI with Playwright)
try:
    from api.crypto_toolbox_endpoints import router as crypto_toolbox_router
    app.include_router(crypto_toolbox_router)
    logger.info("🎭 Crypto-Toolbox: FastAPI native scraper enabled")
except (ImportError, ModuleNotFoundError) as e:
    logger.error(f"❌ Failed to load crypto_toolbox router: {e}")
    logger.warning("⚠️ Crypto-toolbox endpoints will not be available")

# ---------- Legacy Portfolio Endpoints Removed ----------
# Migrated to api/portfolio_endpoints.py:
# - GET /portfolio/metrics
# - POST /portfolio/snapshot
# - GET /portfolio/trend
# - GET /portfolio/alerts

@app.get("/portfolio/breakdown-locations")
async def portfolio_breakdown_locations(
    source: str = Query("cointracking_api"),
    min_usd: float = Query(1.0)
):
    """
    Renvoie la répartition par exchange à partir de la CT-API.
    Pas de fallback “CoinTracking 100%” sauf si réellement aucune data.
    """
    try:
        snap = await load_ctapi_exchanges(min_usd=min_usd)
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
    except httpx.HTTPError as e:
        logger.error(f"HTTP error loading CoinTracking API exchanges: {e}")
    except httpx.TimeoutException as e:
        logger.error(f"Timeout loading CoinTracking API exchanges: {e}")
    except (ValueError, KeyError) as e:
        logger.error(f"Data parsing error loading CoinTracking API exchanges: {e}")

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

# /portfolio/alerts migrated to api/portfolio_endpoints.py
# /api/config/* endpoints migrated to api/config_router.py
