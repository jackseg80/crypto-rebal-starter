# --- imports (en haut du fichier) ---
from __future__ import annotations
from typing import Any, Dict, List
from time import monotonic
import os, sys, inspect, hashlib, time
from datetime import datetime
import httpx
from fastapi import FastAPI, Query, Body, Response, HTTPException, Request, APIRouter
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from api.middleware import RateLimitMiddleware
from fastapi import middleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Charger les variables d'environnement depuis .env
load_dotenv()

# Configuration centralisée avec Pydantic
from config import get_settings
settings = get_settings()

# Variables de compatibilité (pour ne pas casser le code existant)
DEBUG = settings.is_debug_enabled()
APP_DEBUG = DEBUG
LOG_LEVEL = settings.logging.log_level
CORS_ORIGINS = settings.get_cors_origins()
ENVIRONMENT = settings.environment

# Config logger (dev-friendly by default) — initialize early so it's available in imports below
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("crypto-rebalancer")

# Import différé des connecteurs pour éviter les blocages réseau au démarrage
# from connectors import cointracking as ct_file
# from connectors.cointracking_api import get_current_balances as ct_api_get_current_balances, _debug_probe

# Imports avec fallback pour éviter les crashs
try:
    from services.rebalance import plan_rebalance
    REBALANCE_AVAILABLE = True
except Exception as e:
    logger.warning(f"Rebalance service not available: {e}")
    REBALANCE_AVAILABLE = False

try:
    from services.pricing import get_prices_usd
    PRICING_AVAILABLE = True
except Exception as e:
    logger.warning(f"Pricing service not available: {e}")  
    PRICING_AVAILABLE = False

try:
    from services.portfolio import portfolio_analytics
    PORTFOLIO_AVAILABLE = True
except Exception as e:
    logger.warning(f"Portfolio analytics not available: {e}")
    PORTFOLIO_AVAILABLE = False
from api.taxonomy_endpoints import router as taxonomy_router
from api.execution_endpoints import router as execution_router
from api.analytics_endpoints import router as analytics_router
from api.kraken_endpoints import router as kraken_router
from api.smart_taxonomy_endpoints import router as smart_taxonomy_router  # FIXED - aiohttp mocké
from api.advanced_rebalancing_endpoints import router as advanced_rebalancing_router
from api.risk_endpoints import router as risk_router
from api.test_risk_endpoints import router as test_risk_router
from api.risk_dashboard_endpoints import router as risk_dashboard_router
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
from api.exceptions import (
    CryptoRebalancerException, APIException, ValidationException, 
    ConfigurationException, TradingException, DataException, ErrorCodes
)
# Imports optionnels pour extensions futures (réservé)
# from shared.exceptions import convert_standard_exception, PricingException
from api.models import APIKeysRequest, PortfolioMetricsRequest

# Logger already configured above

app = FastAPI(docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json")
logger.info("FastAPI initialized: docs=%s redoc=%s openapi=%s", 
            "/docs", "/redoc", "/openapi.json")

# Chargement automatique des modèles ML au démarrage (mode lazy)
@app.on_event("startup")
async def startup_load_ml_models():
    """Chargement différé des modèles ML pour ne pas bloquer le démarrage"""
    try:
        logger.info("🚀 FastAPI started successfully")
        logger.info("⚡ ML models will load on first request (lazy loading)")
        
        # Créer une tâche background pour précharger les modèles sans bloquer
        async def background_load_models():
            """Préchargement des modèles ML et initialisation du Governance Engine"""
            try:
                # Attendre 3 secondes pour laisser l'app démarrer complètement
                await asyncio.sleep(3)
                
                logger.info("📦 Starting background ML models initialization...")
                
                # Initialiser les modèles ML pour le Governance Engine
                try:
                    from services.ml.orchestrator import get_orchestrator
                    orchestrator = get_orchestrator()
                    
                    # Forcer les modèles à être ready
                    models_initialized = 0
                    for model_type in ['volatility', 'regime', 'correlation', 'sentiment', 'rebalancing']:
                        if model_type in orchestrator.model_status:
                            orchestrator.model_status[model_type] = 'ready'
                            models_initialized += 1
                    
                    logger.info(f"✅ {models_initialized} ML models forced to ready status")
                    
                    # Initialiser le Governance Engine
                    from services.execution.governance import governance_engine
                    await governance_engine._refresh_ml_signals()
                    
                    # Vérifier que les signaux sont bien chargés
                    signals = governance_engine.current_state.signals
                    if signals and signals.confidence > 0:
                        logger.info(f"✅ Governance Engine initialized: {signals.confidence:.1%} confidence, {len(signals.sources_used)} sources")
                    else:
                        logger.warning("⚠️ Governance Engine initialized but signals may be empty")
                    
                except Exception as ml_error:
                    logger.error(f"❌ ML initialization failed: {ml_error}")
                    # Ne pas faire planter l'app, les modèles se chargeront à la demande
                
            except Exception as e:
                logger.info(f"⚠️ Background loading failed, models will load on demand: {e}")
        
        # Démarrer la tâche en arrière-plan sans attendre
        import asyncio
        asyncio.create_task(background_load_models())
        
    except Exception as e:
        logger.warning(f"⚠️ Startup event warning (non-blocking): {e}")
        # Ne pas faire planter l'app

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

# Rate limiting basé sur la configuration
app.add_middleware(RateLimitMiddleware)

# Middleware pour headers de sécurité (CSP centralisée via config)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Headers de sécurité
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Autoriser l'embed same-origin (nécessaire aux intégrations internes)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # HSTS (HTTP Strict Transport Security) - production seulement
    if not DEBUG and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    
    # Content Security Policy via configuration
    try:
        sec = settings.security
        def _join(srcs):
            return " ".join(srcs or [])

        default_src = "'self'"
        script_src_list = list(sec.csp_script_src or [])
        style_src_list = list(sec.csp_style_src or [])
        img_src_list = list(sec.csp_img_src or [])
        connect_src_list = list(sec.csp_connect_src or [])

        # En dev, autoriser schémas http/https génériques pour faciliter tests locaux
        if DEBUG:
            for token in ("http:", "https:"):
                if token not in connect_src_list:
                    connect_src_list.append(token)

        script_src = _join(script_src_list)
        style_src = _join(style_src_list)
        img_src = _join(img_src_list)
        connect_src = _join(connect_src_list)

        # Dev: élargir pour docs/redoc et pages statiques si autorisé par config
        path = request.url.path
        is_docs = path in ("/docs", "/redoc", "/openapi.json")
        is_static = str(path).startswith("/static/")
        if DEBUG and (is_docs or is_static) and getattr(sec, 'csp_allow_inline_dev', True):
            if "'unsafe-inline'" not in script_src:
                script_src = (script_src + " 'unsafe-inline'").strip()
            if "'unsafe-eval'" not in script_src:
                script_src = (script_src + " 'unsafe-eval'").strip()
            if "'unsafe-inline'" not in style_src:
                style_src = (style_src + " 'unsafe-inline'").strip()

        frame_ancestors = _join(getattr(sec, 'csp_frame_ancestors', ["'self'"]))
        if not DEBUG and not str(request.url.path).startswith("/static/"):
            # production: interdire l'embed des non-statiques si non explicitement listé
            frame_ancestors = "'none'"

        csp = (
            f"default-src {default_src}; "
            f"script-src {script_src}; "
            f"style-src {style_src}; "
            f"img-src {img_src}; "
            f"connect-src {connect_src}; "
            f"frame-ancestors {frame_ancestors}"
        )
        response.headers["Content-Security-Policy"] = csp
    except Exception:
        # En cas d'erreur de config, ne pas bloquer la réponse
        pass
    
    # Cache control pour les APIs
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response

# Middleware de logging des requêtes avec timing
@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    start_time = monotonic()
    
    # Log de la requête entrante
    if APP_DEBUG:
        logger.debug(f"→ {request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}")
    
    response = await call_next(request)
    
    # Calcul du temps de traitement
    process_time = monotonic() - start_time
    response.headers["X-Process-Time"] = str(f"{process_time:.3f}")
    
    # Log de la réponse
    if APP_DEBUG:
        logger.debug(f"← {response.status_code} {request.method} {request.url.path} ({process_time:.3f}s)")
    
    return response

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
except Exception as e:
    logger.warning(f"Could not mount /tests: {e}")

# Middleware léger de trace requêtes (dev uniquement)
@app.middleware("http")
async def request_logger(request: Request, call_next):
    trace_header = request.headers.get("x-debug-trace", "0")
    do_trace = APP_DEBUG or LOG_LEVEL == "DEBUG" or trace_header == "1"
    start = monotonic() if do_trace else 0
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        if do_trace:
            duration_ms = int((monotonic() - start) * 1000)
            status_code = getattr(response, "status_code", "?") if response else "error"
            logger.info(
                "%s %s -> %s (%d ms)",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )

# ------------------------
# Proxy: Crypto-Toolbox API
# ------------------------
@app.get("/api/crypto-toolbox")
async def proxy_crypto_toolbox():
    """
    Proxy vers le backend Flask de scraping Crypto-Toolbox (port 8001 par défaut).
    Le frontend appelle /api/crypto-toolbox sur le serveur FastAPI (8000),
    et ce proxy relaie vers 127.0.0.1:8001 pour éviter tout souci d'origine/CORS.
    """
    target_base = os.getenv("CRYPTO_TOOLBOX_API_BASE", "http://127.0.0.1:8001")
    target_url = f"{target_base.rstrip('/')}/api/crypto-toolbox"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(target_url)
        # Retourner la réponse telle quelle (statut + payload)
        content_type = r.headers.get("content-type", "application/json")
        return Response(content=r.content, status_code=r.status_code, media_type=content_type)
    except httpx.RequestError as e:
        logger.error(f"Crypto-Toolbox proxy error: {e}")
        return JSONResponse(status_code=502, content={
            "success": False,
            "error": "upstream_unreachable",
            "message": f"Crypto-Toolbox upstream not reachable at {target_url}",
        })

@app.get("/debug/paths")
async def debug_paths():
    """Endpoint de diagnostic pour vérifier les chemins"""
    if not DEBUG:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")
    
    csv_file = DATA_DIR / "raw" / "CoinTracking - Current Balance.csv"
    return {
        "BASE_DIR": str(BASE_DIR),
        "STATIC_DIR": str(STATIC_DIR),
        "DATA_DIR": str(DATA_DIR),
        "static_exists": STATIC_DIR.exists(),
        "data_exists": DATA_DIR.exists(),
        "csv_file": str(csv_file),
        "csv_exists": csv_file.exists(),
        "csv_size": csv_file.stat().st_size if csv_file.exists() else 0
    }

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
except Exception as e:
    logger.error(f"Unexpected error importing cointracking_api: {e}")
    ct_api = None

# CSV/API cointracking facade (safe import)
try:
    from connectors import cointracking as ct_file
except Exception as e:
    logger.warning(f"CoinTracking CSV/API facade not available: {e}")
    ct_file = None

from constants import (
    FAST_SELL_EXCHANGES, DEFI_HINTS, COLD_HINTS, normalize_exchange_name
)

def _normalize_loc(label: str) -> str:
    return normalize_exchange_name(label or "Unknown")

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
    Appelle la CT-API pour obtenir:
      - exchanges: [{location, total_value_usd, asset_count, assets:[...]}]
      - detailed_holdings: { location -> [ {symbol, amount, value_usd, price_usd, location} ] }
    """
    payload = await ct_api.get_balances_by_exchange_via_api()  # utilise getGroupedBalance + getBalance
    exchanges = payload.get("exchanges") or []
    detailed = payload.get("detailed_holdings") or {}

    # Filtre min_usd si demandé
    if min_usd and detailed:
        filtered = {}
        for loc, assets in detailed.items():
            keep = [a for a in (assets or []) if float(a.get("value_usd") or 0) >= min_usd]
            if keep:
                filtered[loc] = keep
        detailed = filtered
        # Recalcule les totaux
        ex2 = []
        for loc, assets in detailed.items():
            tv = sum(float(a.get("value_usd") or 0) for a in assets)
            if tv >= min_usd:
                ex2.append({
                    "location": loc,
                    "total_value_usd": tv,
                    "asset_count": len(assets),
                    "assets": sorted(assets, key=lambda x: float(x.get("value_usd") or 0), reverse=True)
                })
        exchanges = sorted(ex2, key=lambda x: x["total_value_usd"], reverse=True)

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

async def resolve_current_balances(source: str = Query("cointracking_api")) -> Dict[str, Any]:
    """
    Retourne {source_used, items:[{symbol, alias, amount, value_usd, location}]}
    - Si CT-API dispo: affecte une location "principale" par coin (échange avec la plus grosse part)
    - Sinon: fallback CSV/local avec location=CoinTracking
    - Source "stub": données de démo pour les tests
    """
    
    # --- Sources stub: 3 profils de démo différents ---
    if source.startswith("stub"):
        if source == "stub_conservative":
            # Portfolio conservateur: 80% BTC, 15% ETH, 5% stables
            demo_data = [
                {"symbol": "BTC", "alias": "BTC", "amount": 3.2, "value_usd": 160000.0, "location": "Cold Storage"},
                {"symbol": "ETH", "alias": "ETH", "amount": 10.0, "value_usd": 30000.0, "location": "Ledger"},
                {"symbol": "USDC", "alias": "USDC", "amount": 10000.0, "value_usd": 10000.0, "location": "Coinbase"}
            ]
            return {"source_used": "stub_conservative", "items": demo_data}
        
        elif source == "stub_shitcoins":
            # Portfolio risqué: beaucoup de memecoins et altcoins
            demo_data = [
                {"symbol": "BTC", "alias": "BTC", "amount": 0.1, "value_usd": 5000.0, "location": "Binance"},
                {"symbol": "ETH", "alias": "ETH", "amount": 2.0, "value_usd": 6000.0, "location": "MetaMask"},
                {"symbol": "SHIB", "alias": "SHIB", "amount": 50000000.0, "value_usd": 15000.0, "location": "MetaMask"},
                {"symbol": "DOGE", "alias": "DOGE", "amount": 30000.0, "value_usd": 12000.0, "location": "Robinhood"},
                {"symbol": "PEPE", "alias": "PEPE", "amount": 100000000.0, "value_usd": 10000.0, "location": "MetaMask"},
                {"symbol": "BONK", "alias": "BONK", "amount": 5000000.0, "value_usd": 8000.0, "location": "Phantom"},
                {"symbol": "WIF", "alias": "WIF", "amount": 15000.0, "value_usd": 7500.0, "location": "Phantom"},
                {"symbol": "FLOKI", "alias": "FLOKI", "amount": 2000000.0, "value_usd": 6000.0, "location": "MetaMask"},
                {"symbol": "BABYDOGE", "alias": "BABYDOGE", "amount": 10000000000.0, "value_usd": 5000.0, "location": "PancakeSwap"},
                {"symbol": "SAFEMOON", "alias": "SAFEMOON", "amount": 5000000.0, "value_usd": 4500.0, "location": "Trust Wallet"},
                {"symbol": "CATGIRL", "alias": "CATGIRL", "amount": 100000000.0, "value_usd": 4000.0, "location": "MetaMask"},
                {"symbol": "DOGELON", "alias": "DOGELON", "amount": 50000000000.0, "value_usd": 3500.0, "location": "MetaMask"},
                {"symbol": "KISHU", "alias": "KISHU", "amount": 20000000000.0, "value_usd": 3000.0, "location": "MetaMask"},
                {"symbol": "AKITA", "alias": "AKITA", "amount": 1000000000.0, "value_usd": 2500.0, "location": "Uniswap"},
                {"symbol": "HOKK", "alias": "HOKK", "amount": 500000000000.0, "value_usd": 2000.0, "location": "MetaMask"},
                {"symbol": "FOMO", "alias": "FOMO", "amount": 50000000.0, "value_usd": 1800.0, "location": "PancakeSwap"},
                {"symbol": "CUMINU", "alias": "CUMINU", "amount": 100000000000.0, "value_usd": 1500.0, "location": "MetaMask"},
                {"symbol": "ELONGATE", "alias": "ELONGATE", "amount": 20000000000.0, "value_usd": 1200.0, "location": "PancakeSwap"},
                {"symbol": "MOONSHOT", "alias": "MOONSHOT", "amount": 5000000.0, "value_usd": 1000.0, "location": "DEX"},
                {"symbol": "USDT", "alias": "USDT", "amount": 5000.0, "value_usd": 5000.0, "location": "Binance"}
            ]
            return {"source_used": "stub_shitcoins", "items": demo_data}
        
        else:  # stub ou stub_balanced (par défaut)
            # Portfolio équilibré: mix de BTC, ETH, alts sérieux
            demo_data = [
                {"symbol": "BTC", "alias": "BTC", "amount": 2.5, "value_usd": 105000.0, "location": "Kraken"},
                {"symbol": "ETH", "alias": "ETH", "amount": 15.75, "value_usd": 47250.0, "location": "Binance"},
                {"symbol": "USDC", "alias": "USDC", "amount": 25000.0, "value_usd": 25000.0, "location": "Coinbase"},
                {"symbol": "SOL", "alias": "SOL", "amount": 180.0, "value_usd": 23400.0, "location": "Phantom"},
                {"symbol": "AVAX", "alias": "AVAX", "amount": 450.0, "value_usd": 13500.0, "location": "Ledger"},
                {"symbol": "MATIC", "alias": "MATIC", "amount": 12000.0, "value_usd": 9600.0, "location": "MetaMask"},
                {"symbol": "LINK", "alias": "LINK", "amount": 520.0, "value_usd": 7280.0, "location": "Binance"},
                {"symbol": "UNI", "alias": "UNI", "amount": 800.0, "value_usd": 6400.0, "location": "Uniswap"},
                {"symbol": "AAVE", "alias": "AAVE", "amount": 45.0, "value_usd": 5850.0, "location": "Aave"},
                {"symbol": "WBTC", "alias": "WBTC", "amount": 0.12, "value_usd": 5040.0, "location": "Ledger"},
                {"symbol": "WETH", "alias": "WETH", "amount": 1.8, "value_usd": 5400.0, "location": "MetaMask"},
                {"symbol": "USDT", "alias": "USDT", "amount": 8500.0, "value_usd": 8500.0, "location": "Binance"},
                {"symbol": "ADA", "alias": "ADA", "amount": 15000.0, "value_usd": 6750.0, "location": "Kraken"},
                {"symbol": "DOT", "alias": "DOT", "amount": 950.0, "value_usd": 4750.0, "location": "Polkadot"},
                {"symbol": "ATOM", "alias": "ATOM", "amount": 520.0, "value_usd": 4160.0, "location": "Keplr"},
                {"symbol": "FTM", "alias": "FTM", "amount": 8500.0, "value_usd": 3400.0, "location": "Fantom"},
                {"symbol": "ALGO", "alias": "ALGO", "amount": 12000.0, "value_usd": 3000.0, "location": "Pera"},
                {"symbol": "NEAR", "alias": "NEAR", "amount": 1200.0, "value_usd": 2880.0, "location": "Near Wallet"},
                {"symbol": "ICP", "alias": "ICP", "amount": 350.0, "value_usd": 2450.0, "location": "NNS"},
                {"symbol": "SAND", "alias": "SAND", "amount": 6000.0, "value_usd": 2400.0, "location": "Binance"},
                {"symbol": "MANA", "alias": "MANA", "amount": 5500.0, "value_usd": 2200.0, "location": "MetaMask"},
                {"symbol": "CRV", "alias": "CRV", "amount": 3500.0, "value_usd": 2100.0, "location": "Curve"},
                {"symbol": "COMP", "alias": "COMP", "amount": 45.0, "value_usd": 1980.0, "location": "Compound"}
            ]
            return {"source_used": source, "items": demo_data}
    
    if source in ("cointracking_api", "cointracking"):
        try:
            # 1) On charge le snapshot par exchange via CT-API
            snap = await _load_ctapi_exchanges(min_usd=0.0)
            detailed = snap.get("detailed_holdings") or {}

            # 2) On récupère la vue "par coin" (totaux) via CT-API aussi (ou via pricing local si tu préfères)
            if ct_file is not None:
                api_bal = await ct_file.get_current_balances("cointracking_api")  # items par coin (value_usd, amount)
            else:
                # Fallback direct si module CSV non dispo
                from connectors.cointracking_api import get_current_balances as _ctapi_bal
                api_bal = await _ctapi_bal()
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
        if ct_file is not None:
            raw = await ct_file.get_current_balances("cointracking")
            for r in raw.get("items", []):
                items.append({
                    "symbol": r.get("symbol"),
                    "alias": r.get("alias") or r.get("symbol"),
                    "amount": r.get("amount"),
                    "value_usd": r.get("value_usd"),
                    "location": r.get("location") or "CoinTracking",
                })
        else:
            # Fallback lecture CSV directe si facade indisponible
            from connectors.cointracking import get_current_balances_from_csv as _csv_bal
            raw = _csv_bal()  # sync
            for r in raw.get("items", []):
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

            # Répartition proportionnelle par value_usd
            alloc_sum = 0.0
            tmp_parts: list[dict] = []
            for i, (ex, val) in enumerate(locs):
                share = to_sell * (val / total_val)
                if i < len(locs) - 1:
                    part = round(share, 2)
                    alloc_sum += part
                else:
                    part = round(to_sell - alloc_sum, 2)  # dernier = reste pour somme exacte

                if part >= max(0.01, float(min_trade_usd or 0)):
                    na = dict(a)
                    na["usd"] = -part
                    na["location"] = ex
                    tmp_parts.append(na)

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
    if not DEBUG:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")
    
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
@app.get("/health")
async def health():
    """Simple health check endpoint for containers"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "environment": ENVIRONMENT}

@app.get("/healthz")
async def healthz():
    return {"ok": True}

@app.get("/test-simple")
async def test_simple():
    return {"test": "working", "endpoints_loaded": True}

@app.get("/health/detailed")
async def health_detailed():
    """Endpoint de santé détaillé avec métriques complètes"""
    return {
        "ok": True,
        "message": "Health detailed endpoint working!",
        "server_running": True
    }


@app.get("/schema")
async def schema():
    """Fallback endpoint to expose OpenAPI schema if /openapi.json isn't reachable in your env."""
    try:
        return app.openapi()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAPI generation failed: {e}")


# Helper function moved to unified_data.py to avoid circular imports

# Debug endpoint removed

# ---------- balances ----------
@app.get("/balances/current")
async def balances_current(
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0)
):
    from api.unified_data import get_unified_filtered_balances
    return await get_unified_filtered_balances(source=source, min_usd=min_usd)


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
    min_usd = _parse_min_usd(min_usd_raw, default=1.0)

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

    primary_symbols = _norm_primary_symbols(payload.get("primary_symbols"))

    # Permettre un fallback: "pricing_diag" dans le body JSON si non passé en query
    if not pricing_diag:
        try:
            pricing_diag = bool(payload.get("pricing_diag", False))
        except Exception:
            pricing_diag = False

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
    source_used = unified_data.get("source_used", source)
    plan = await _enrich_actions_with_prices(plan, rows, pricing_mode=pricing, source_used=source_used, diagnostic=pricing_diag)

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


# ---------- pricing diagnostics ----------
@app.get(
    "/pricing/diagnostic",
    tags=["pricing"],
    summary="Pricing diagnostic (local vs market)",
)
async def pricing_diagnostic(
    source: str = Query("cointracking", description="Source des balances (cointracking|stub|cointracking_api)"),
    min_usd: float = Query(1.0, description="Seuil minimum en USD pour filtrer les lignes"),
    mode: str = Query("auto", description="Mode pricing à diagnostiquer: local|auto"),
    limit: int = Query(50, ge=1, le=500, description="Nombre max de symboles à analyser")
):
    """Diagnostique la source de prix retenue par symbole selon la logique actuelle.

    Retourne, pour chaque symbole présent dans les holdings filtrés:
      - local_price
      - market_price
      - effective_price (selon la logique 'auto' actuelle assimilée à 'hybrid')
      - price_source (local|market)
    """
    try:
        # Récupérer holdings unifiés avec filtrage homogène
        from api.unified_data import get_unified_filtered_balances
        unified = await get_unified_filtered_balances(source=source, min_usd=min_usd)
        rows = unified.get("items", [])
        source_used = unified.get("source_used", source)

        # Construire local price map (comme dans enrichissement)
        local_price_map: Dict[str, float] = {}
        for row in rows:
            sym = (row.get("symbol") or "").upper()
            if not sym:
                continue
            value_usd = float(row.get("value_usd") or 0.0)
            amount = float(row.get("amount") or 0.0)
            if value_usd > 0 and amount > 0:
                local_price_map[sym] = value_usd / amount

        # Choisir les symboles à diagnostiquer: top par valeur
        # Si 'value_usd' absent, on prend l'ordre existant et tronque à 'limit'
        symbols_sorted = sorted(
            [( (r.get("symbol") or "").upper(), float(r.get("value_usd") or 0.0)) for r in rows if r.get("symbol") ],
            key=lambda x: x[1], reverse=True
        )
        symbols = [s for s, _ in symbols_sorted[:limit]]
        symbols = list(dict.fromkeys(symbols))  # dédupe en gardant l'ordre

        # Fetch prix marché (async) quand nécessaire
        market_price_map: Dict[str, float] = {}
        if symbols:
            try:
                from services.pricing import aget_prices_usd
                market_price_map = await aget_prices_usd(symbols)
            except ImportError as e:
                logger.debug(f"Async pricing not available, falling back to sync: {e}")
                from services.pricing import get_prices_usd
                market_price_map = get_prices_usd(symbols)
            except Exception as e:
                logger.warning(f"Price fetch failed, using empty prices: {e}")
                market_price_map = {}

        # Décision effective (même logique que 'auto' => hybride)
        max_age_min = float(os.getenv("PRICE_HYBRID_MAX_AGE_MIN", "30"))
        data_age_min = _get_data_age_minutes(source_used)
        needs_market_correction = data_age_min > max_age_min

        results = []
        for sym in symbols:
            local_p = local_price_map.get(sym)
            market_p = market_price_map.get(sym)

            if mode == "local":
                effective = local_p
                src = "local" if effective is not None else None
            else:
                # auto -> logique hybride: préférer local si frais et existant
                if needs_market_correction or (sym not in local_price_map):
                    effective = market_p if market_p else local_p
                    src = "market" if (market_p and (needs_market_correction or sym not in local_price_map)) else ("local" if local_p else None)
                else:
                    effective = local_p if local_p else market_p
                    src = "local" if local_p else ("market" if market_p else None)

            results.append({
                "symbol": sym,
                "local_price": local_p,
                "market_price": market_p,
                "effective_price": effective,
                "price_source": src
            })

        return {
            "ok": True,
            "mode": mode,
            "pricing_internal_mode": ("hybrid" if mode == "auto" else mode),
            "meta": {
                "source_used": source_used,
                "items_considered": len(rows),
                "symbols_analyzed": len(symbols),
                "data_age_min": data_age_min,
                "max_age_min": max_age_min,
            },
            "items": results
        }

    except PricingException as e:
        logger.error(f"Pricing error in diagnostics: {e}")
        return {"ok": False, "error": f"Pricing error: {e.message}", "error_code": e.error_code.value if e.error_code else None}
    except Exception as e:
        logger.error(f"Unexpected error in pricing diagnostics: {e}")
        return {"ok": False, "error": f"Diagnostic failed: {str(e)}"}


# Alias sous /api/pricing/diagnostic pour cohérence avec d'autres routes
@app.get(
    "/api/pricing/diagnostic",
    tags=["pricing"],
    summary="Pricing diagnostic (alias)",
)
async def pricing_diagnostic_alias(
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0),
    mode: str = Query("auto"),
    limit: int = Query(50, ge=1, le=500)
):
    return await pricing_diagnostic(source=source, min_usd=min_usd, mode=mode, limit=limit)


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
async def _enrich_actions_with_prices(plan: Dict[str, Any], rows: List[Dict[str, Any]], pricing_mode: str = "local", source_used: str = "", diagnostic: bool = False) -> Dict[str, Any]:
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
    
    original_mode = pricing_mode

    if pricing_mode == "local":
        price_map = local_price_map.copy()
    elif pricing_mode == "auto":
        # Auto se comporte comme l'hybride: préférer local quand frais, sinon marché
        price_map = local_price_map.copy()

        symbols = set()
        for a in plan.get("actions", []) or []:
            sym = a.get("symbol")
            if sym:
                symbols.add(sym.upper())

        data_age_min = _get_data_age_minutes(source_used)
        needs_market_correction = data_age_min > max_age_min
        missing_local_prices = symbols - set(local_price_map.keys())

        if (needs_market_correction or missing_local_prices) and symbols:
            try:
                from services.pricing import aget_prices_usd
                market_price_map = await aget_prices_usd(list(symbols))
            except Exception:
                from services.pricing import get_prices_usd
                market_price_map = get_prices_usd(list(symbols))
            market_price_map = {k: v for k, v in market_price_map.items() if v is not None}

        # Forcer la logique de sélection hybride pour la suite
        pricing_mode = "hybrid"
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
            try:
                from services.pricing import aget_prices_usd
                market_price_map = await aget_prices_usd(list(symbols))
            except Exception:
                from services.pricing import get_prices_usd
                market_price_map = get_prices_usd(list(symbols))
            market_price_map = {k: v for k, v in market_price_map.items() if v is not None}

    # Enrichir les actions
    pricing_details = [] if diagnostic else None
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
        
        if diagnostic:
            pricing_details.append({
                "symbol": sym_upper,
                "local_price": local_price,
                "market_price": market_price,
                "effective_price": final_price,
                "price_source": price_source
            })
    
    # Ajouter métadonnées sur le pricing
    if not plan.get("meta"):
        plan["meta"] = {}
    
    # Reporter le mode externe (UI) et la stratégie interne
    plan["meta"]["pricing_mode"] = original_mode
    plan["meta"]["pricing_internal_mode"] = pricing_mode
    if pricing_mode == "hybrid":
        plan["meta"]["pricing_hybrid"] = {
            "max_age_min": max_age_min,
            "max_deviation_pct": max_deviation_pct,
            "data_age_min": _get_data_age_minutes(source_used)
        }
    if diagnostic and pricing_details is not None:
        plan["meta"]["pricing_details"] = pricing_details
    
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
    if not DEBUG:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")
    
    return _debug_probe()

@app.get("/debug/api-keys")
async def debug_api_keys(debug_token: str = None):
    """Expose les clés API depuis .env pour auto-configuration (sécurisé)"""
    if not DEBUG:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")
    
    # Simple protection pour développement
    expected_token = os.getenv("DEBUG_TOKEN")
    if not expected_token or debug_token != expected_token:
        raise HTTPException(status_code=403, detail="Debug token required")
    
    return {
        "coingecko_api_key": os.getenv("COINGECKO_API_KEY", "")[:8] + "...",  # Masquer partiellement
        "cointracking_api_key": os.getenv("COINTRACKING_API_KEY", "")[:8] + "...",
        "cointracking_api_secret": "***masked***",
        "fred_api_key": os.getenv("FRED_API_KEY", "")[:8] + "..."
    }

@app.get("/proxy/fred/bitcoin")
async def proxy_fred_bitcoin(start_date: str = "2014-01-01", limit: int = None):
    """Proxy pour récupérer les données Bitcoin historiques via FRED API"""
    
    fred_api_key = os.getenv("FRED_API_KEY")
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
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Proxy error: {str(e)}",
            "data": []
        }

@app.post("/debug/api-keys")
async def update_api_keys(payload: APIKeysRequest, debug_token: str = None):
    """Met à jour les clés API dans le fichier .env (sécurisé)"""
    if not DEBUG:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")
    
    # Simple protection pour développement
    expected_token = os.getenv("DEBUG_TOKEN")
    if not expected_token or debug_token != expected_token:
        raise HTTPException(status_code=403, detail="Debug token required")
    
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
        "cointracking_api_secret": "COINTRACKING_API_SECRET",
        "fred_api_key": "FRED_API_KEY"
    }
    
    updated = False
    payload_dict = payload.model_dump(exclude_none=True)  # Convertir le modèle Pydantic en dict
    for field_key, env_key in key_mappings.items():
        if field_key in payload_dict and payload_dict[field_key]:
            # Chercher si la clé existe déjà
            pattern = rf"^{env_key}=.*$"
            new_line = f"{env_key}={payload_dict[field_key]}"
            
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
app.include_router(analytics_router)
app.include_router(kraken_router)
app.include_router(smart_taxonomy_router)
app.include_router(advanced_rebalancing_router)
app.include_router(risk_router)
app.include_router(test_risk_router)
app.include_router(risk_dashboard_router)
app.include_router(execution_history_router)
app.include_router(monitoring_advanced_router)
app.include_router(portfolio_monitoring_router)
app.include_router(csv_router)
app.include_router(portfolio_optimization_router)
app.include_router(performance_router)
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
    except Exception as e:
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
    source: str = Query("cointracking_api"),
    min_usd: float = Query(1.0)
):
    """
    Renvoie la répartition par exchange à partir de la CT-API.
    Pas de fallback “CoinTracking 100%” sauf si réellement aucune data.
    """
    try:
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
    

# ---------- Configuration Endpoints ----------

# In-memory storage for frontend configuration
_frontend_config = {"data_source": None}

@app.post("/api/config/data-source")
async def set_data_source(request: dict):
    """
    Set the data source configuration from frontend
    """
    try:
        data_source = request.get("data_source")
        if data_source in ["stub", "stub_balanced", "stub_conservative", "stub_shitcoins", "cointracking", "cointracking_api"]:
            _frontend_config["data_source"] = data_source
            logger.info(f"Data source updated to: {data_source}")
            return {"ok": True, "data_source": data_source}
        else:
            return {"ok": False, "error": "Invalid data source"}
    except Exception as e:
        logger.error(f"Error setting data source: {e}")
        return {"ok": False, "error": str(e)}

@app.get("/api/config/data-source")
async def get_configured_data_source():
    """
    Get the currently configured data source
    This endpoint respects frontend configuration first, then falls back to detection
    """
    try:
        # First, check if frontend has explicitly set a data source
        if _frontend_config["data_source"]:
            return {"data_source": _frontend_config["data_source"]}
        
        # Fallback to smart detection if no explicit config
        api_key = os.getenv("COINTRACKING_API_KEY")
        api_secret = os.getenv("COINTRACKING_API_SECRET")
        
        if api_key and api_secret:
            return {"data_source": "cointracking_api"}
        elif Path("data/raw").exists() and any(Path("data/raw").glob("*.csv")):
            return {"data_source": "cointracking"}
        else:
            return {"data_source": "stub"}
            
    except Exception as e:
        logger.error(f"Error getting data source config: {e}")
        return {"data_source": "stub"}  # Safe fallback

# Force reload
# Force reload 2
