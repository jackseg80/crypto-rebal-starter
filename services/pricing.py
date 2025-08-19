# services/pricing.py
import json, os, time
from urllib.request import urlopen
from urllib.error import URLError

# --- Configuration via env ---
PRICE_CACHE_TTL = int(os.getenv("PRICE_CACHE_TTL", "120"))
PRICE_FILE      = os.getenv("PRICE_FILE", "data/prices.json")
# ordre des providers, séparés par des virgules
# options disponibles : file, binance, coingecko
PRICE_PROVIDER_ORDER = [p.strip() for p in os.getenv("PRICE_PROVIDER_ORDER", "file,coingecko,binance").split(",") if p.strip()]

# Cache simple en mémoire
_cache = {}  # symbol -> (price, ts)

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
