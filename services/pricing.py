# services/pricing.py
import json
import os
import time
import asyncio
import logging
from urllib.request import urlopen
from urllib.error import URLError
import httpx

# --- Configuration via env ---
PRICE_CACHE_TTL = int(os.getenv("PRICE_CACHE_TTL", "120"))
PRICE_FILE      = os.getenv("PRICE_FILE", "data/prices.json")
# ordre des providers, séparés par des virgules
# options disponibles : file, binance, coingecko
PRICE_PROVIDER_ORDER = [p.strip() for p in os.getenv("PRICE_PROVIDER_ORDER", "file,coingecko,binance").split(",") if p.strip()]

# Cache amélioré en mémoire avec persistance
_cache = {}  # symbol -> (price, ts)
_cache_file = "data/pricing_cache.json"
logger = logging.getLogger(__name__)

def _load_cache_from_disk():
    """Charger le cache depuis le disque au démarrage"""
    global _cache
    try:
        if os.path.exists(_cache_file):
            with open(_cache_file, 'r', encoding='utf-8') as f:
                disk_cache = json.load(f)
                # Filtrer les entrées expirées
                now = _now()
                for symbol, (price, ts) in disk_cache.items():
                    if now - ts <= PRICE_CACHE_TTL:
                        _cache[symbol] = (price, ts)
                logger.debug(f"Cache chargé depuis le disque: {len(_cache)} entrées")
    except Exception as e:
        logger.debug(f"Erreur chargement cache: {e}")

def _save_cache_to_disk():
    """Sauvegarder le cache sur disque"""
    try:
        os.makedirs(os.path.dirname(_cache_file), exist_ok=True)
        with open(_cache_file, 'w', encoding='utf-8') as f:
            json.dump(_cache, f, indent=2)
    except Exception as e:
        logger.debug(f"Erreur sauvegarde cache: {e}")

# Charger le cache au démarrage du module
_load_cache_from_disk()

# Mapping minimal pour CoinGecko (élargissable au besoin)
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "TBTC": "tbtc",
    "WBTC": "wrapped-bitcoin",

    "ETH": "ethereum",
    "WETH": "weth",
    "STETH": "lido-staked-ether",
    "WSTETH": "wrapped-steth",
    "RETH": "rocket-pool-eth",

    "SOL": "solana",
    "JITOSOL": "jito-staked-sol",
    "JUPSOL": "jupiter-staked-sol",

    "AAVE": "aave",
    "LINK": "chainlink",
    "DOGE": "dogecoin",

    "USDT": "tether",
    "USDC": "usd-coin",
}

FIAT_STABLE_FIXED = {"USD": 1.0, "USDT": 1.0, "USDC": 1.0}

# Alias de prix (on utilise le prix du "base symbol")
SYMBOL_ALIAS = {
    "TBTC": "BTC",
    "WBTC": "BTC",
    "WETH": "ETH",
    "STETH": "ETH",
    "WSTETH": "ETH",
    "RETH": "ETH",
    "JITOSOL": "SOL",
    "JUPSOL": "SOL",
}

def get_price_usd(symbol: str):
    if not symbol:
        return None
    symbol = symbol.upper()
    base = SYMBOL_ALIAS.get(symbol, symbol)

    # 1) fiat/stables fixes
    if base in FIAT_STABLE_FIXED:
        return FIAT_STABLE_FIXED[base]

    # 2) cache mémoire
    p = _get_from_cache(base)
    if p:
        return p

    # 3) providers (dans l'ordre)
    for name in PRICE_PROVIDER_ORDER:
        fn = _PROVIDERS.get(name)
        if not fn:
            continue
        p = fn(base)
        if p and p > 0:
            _set_cache(base, p)
            return p

    return None

def _now() -> float:
    return time.time()

def _get_from_cache(symbol: str):
    key = symbol.upper()
    if key in _cache:
        price, ts = _cache[key]
        if _now() - ts <= PRICE_CACHE_TTL:
            return price
    return None

def _set_cache(symbol: str, price: float):
    if price and price > 0:
        _cache[symbol.upper()] = (float(price), _now())
        # Sauvegarder périodiquement sur disque (tous les 10 ajouts)
        if len(_cache) % 10 == 0:
            _save_cache_to_disk()

# ---------- Providers ----------
def _from_file(symbol: str):
    try:
        if not os.path.exists(PRICE_FILE):
            return None
        with open(PRICE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        val = data.get(symbol.upper())
        if val:
            return float(val)
    except Exception:
        return None
    return None

def _from_binance(symbol: str):
    # Appel simple : https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT
    try:
        pair = f"{symbol.upper()}USDT"
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
        with urlopen(url, timeout=5) as r:
            obj = json.loads(r.read().decode("utf-8"))
        p = obj.get("price")
        return float(p) if p else None
    except URLError:
        return None
    except Exception:
        return None

def _from_coingecko(symbol: str):
    try:
        cid = COINGECKO_IDS.get(symbol.upper())
        if not cid:
            return None
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={cid}&vs_currencies=usd"
        with urlopen(url, timeout=6) as r:
            obj = json.loads(r.read().decode("utf-8"))
        p = (obj.get(cid) or {}).get("usd")
        return float(p) if p else None
    except URLError:
        return None
    except Exception:
        return None

_PROVIDERS = {
    "file": _from_file,
    "binance": _from_binance,
    "coingecko": _from_coingecko,
}

def get_prices_usd(symbols):
    out = {}
    for s in set([ (s or "").upper() for s in symbols ]):
        if not s:
            continue
        out[s] = get_price_usd(s)
    return out

# ---------------- Async helpers (non-bloquants) ----------------
async def _from_file_async(symbol: str):
    return await asyncio.to_thread(_from_file, symbol)


async def _from_binance_async(symbol: str):
    try:
        pair = f"{symbol.upper()}USDT"
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            obj = r.json()
            p = obj.get("price")
            return float(p) if p else None
    except Exception as e:
        logger.debug("Binance async provider error for %s: %s", symbol, e)
        return None


async def _from_coingecko_async(symbol: str):
    try:
        cid = COINGECKO_IDS.get(symbol.upper())
        if not cid:
            return None
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={cid}&vs_currencies=usd"
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            obj = r.json()
            p = (obj.get(cid) or {}).get("usd")
            return float(p) if p else None
    except Exception as e:
        logger.debug("Coingecko async provider error for %s: %s", symbol, e)
        return None


async def aget_price_usd(symbol: str):
    if not symbol:
        return None
    symbol = symbol.upper()
    base = SYMBOL_ALIAS.get(symbol, symbol)

    if base in FIAT_STABLE_FIXED:
        return FIAT_STABLE_FIXED[base]

    p = _get_from_cache(base)
    if p:
        return p

    for name in PRICE_PROVIDER_ORDER:
        if name == "file":
            p = await _from_file_async(base)
        elif name == "binance":
            p = await _from_binance_async(base)
        elif name == "coingecko":
            p = await _from_coingecko_async(base)
        else:
            p = None
        if p and p > 0:
            _set_cache(base, p)
            return p
    return None


async def aget_prices_usd(symbols, max_concurrency: int = 6):
    sem = asyncio.Semaphore(max_concurrency)
    results = {}

    async def worker(sym: str):
        async with sem:
            results[sym] = await aget_price_usd(sym)

    tasks = []
    for s in set([(s or "").upper() for s in symbols]):
        if not s:
            continue
        tasks.append(asyncio.create_task(worker(s)))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    return results

# ========== Fonctions de gestion du cache ==========

def get_cache_stats():
    """Obtenir les statistiques du cache"""
    now = _now()
    total_entries = len(_cache)
    valid_entries = sum(1 for _, (_, ts) in _cache.items() if now - ts <= PRICE_CACHE_TTL)
    expired_entries = total_entries - valid_entries
    
    return {
        "total_entries": total_entries,
        "valid_entries": valid_entries,
        "expired_entries": expired_entries,
        "cache_ttl": PRICE_CACHE_TTL,
        "cache_file": _cache_file
    }

def clear_cache(save_to_disk=True):
    """Vider le cache"""
    global _cache
    _cache.clear()
    if save_to_disk:
        _save_cache_to_disk()
    logger.info("Cache pricing vidé")

def cleanup_expired_cache():
    """Nettoyer les entrées expirées du cache"""
    global _cache
    now = _now()
    expired_keys = [key for key, (_, ts) in _cache.items() if now - ts > PRICE_CACHE_TTL]
    
    for key in expired_keys:
        del _cache[key]
    
    if expired_keys:
        _save_cache_to_disk()
        logger.debug(f"Cache nettoyé: {len(expired_keys)} entrées expirées supprimées")
    
    return len(expired_keys)

def force_cache_save():
    """Forcer la sauvegarde du cache sur disque"""
    _save_cache_to_disk()
    logger.debug("Cache forcé sur disque")
