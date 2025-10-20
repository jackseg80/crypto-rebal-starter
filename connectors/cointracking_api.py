# connectors/cointracking_api.py
from __future__ import annotations

import os, time, hmac, hashlib, json, re, asyncio
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from dotenv import load_dotenv
from collections import defaultdict
from functools import partial

import logging
logger = logging.getLogger(__name__)
logger.debug("CT-API parser version: %s", "2025-08-22-1")

# Charger .env au début pour que les variables soient disponibles
load_dotenv()

# --- Config (.env) -----------------------------------------------------------
# Supporter plusieurs variantes de noms d'ENV pour être tolérant aux configs:
# - CT_API_* (historique)
# - COINTRACKING_API_* (clair)
# - API_COINTRACKING_API_* (pydantic settings API_ prefix)
API_BASE = (
    os.getenv("CT_API_BASE")
    or os.getenv("COINTRACKING_API_BASE")
    or os.getenv("API_COINTRACKING_API_BASE")
    or "https://cointracking.info/api/v1/"
)
API_KEY = (
    os.getenv("CT_API_KEY")
    or os.getenv("COINTRACKING_API_KEY")
    or os.getenv("API_COINTRACKING_API_KEY")
    or ""
).strip()
API_SECRET = (
    os.getenv("CT_API_SECRET")
    or os.getenv("COINTRACKING_API_SECRET")
    or os.getenv("API_COINTRACKING_API_SECRET")
    or ""
).strip()

# Optionnel : exclure certains exchanges (ex: "FTX,Cryptopia") pour l'affichage
# EXCLUDE_EXCHANGES = set(s.strip() for s in (os.getenv("CT_EXCLUDE_EXCHANGES") or "").split(",") if s.strip()

_EX_ALIAS_FIXES = {
    # normalisations / alias -> label que tu veux voir dans l’UI
    "COINBASE BALANCE": "Coinbase",
    "COINBASE PRO BALANCE": "Coinbase Pro",
    "POLONIEX BALANCE": "Poloniex",
    "BITTREX BALANCE": "Bittrex",
    "BINANCE BALANCE": "Binance",
    "KRAKEN BALANCE": "Kraken",
    "KRAKEN EARN BALANCE": "Kraken Earn",
    "FTX BALANCE": "FTX",
    "LEDGER BALANCE": "Ledger",
    "LEDGER LIVE BALANCE": "Ledger",
    # ... complète au besoin (regarde ce qui remonte chez toi)
}

# --- Bounded in-memory cache (anti-spam API) ------------------------------------
_CACHE: dict[tuple, tuple[float, dict]] = {}  # key -> (ts, payload)
_MAX_CACHE_SIZE = 1000  # Limite de 1000 entrées
_CACHE_CLEANUP_THRESHOLD = 1200  # Nettoyer quand on dépasse ce seuil

def _cleanup_cache() -> None:
    """Nettoie le cache en gardant seulement les entrées les plus récentes"""
    import time
    if len(_CACHE) <= _MAX_CACHE_SIZE:
        return
    
    # Trier par timestamp et garder les plus récents
    sorted_items = sorted(_CACHE.items(), key=lambda x: x[1][0], reverse=True)
    _CACHE.clear()
    for key, value in sorted_items[:_MAX_CACHE_SIZE]:
        _CACHE[key] = value

def _cache_get(key: tuple, ttl: int) -> dict | None:
    import time
    item = _CACHE.get(key)
    if not item:
        return None
    ts, payload = item
    if time.time() - ts > ttl:
        _CACHE.pop(key, None)
        return None
    return payload

def _cache_set(key: tuple, payload: dict) -> None:
    import time
    _CACHE[key] = (time.time(), payload)
    
    # Nettoyer si nécessaire
    if len(_CACHE) > _CACHE_CLEANUP_THRESHOLD:
        _cleanup_cache()

async def _post_api_cached_async(method: str, params: Optional[Dict[str, Any]] = None, ttl: int = 60,
                                api_key: Optional[str] = None, api_secret: Optional[str] = None) -> Dict[str, Any]:
    """Version async de _post_api_cached utilisant un executor pour éviter le blocking I/O"""
    # Inclure les clés API dans la clé de cache pour éviter les collisions entre utilisateurs
    cache_key_parts = [method, json.dumps(params or {}, sort_keys=True)]
    if api_key:
        cache_key_parts.append(f"key_{api_key[:8]}")
    key = tuple(cache_key_parts)

    hit = _cache_get(key, ttl)
    if hit is not None:
        return hit

    # Utiliser un executor pour ne pas bloquer la boucle d'événements
    loop = asyncio.get_running_loop()
    payload = await loop.run_in_executor(None, partial(_post_api, method, params, api_key, api_secret))
    
    if isinstance(payload, dict):
        _cache_set(key, payload)
    return payload

# Garde la version synchrone pour compatibilité
def _post_api_cached(method: str, params: Optional[Dict[str, Any]] = None, ttl: int = 60,
                     api_key: Optional[str] = None, api_secret: Optional[str] = None) -> Dict[str, Any]:
    # Inclure les clés API dans la clé de cache pour éviter les collisions entre utilisateurs
    cache_key_parts = [method, json.dumps(params or {}, sort_keys=True)]
    if api_key:
        cache_key_parts.append(f"key_{api_key[:8]}")  # Juste les 8 premiers caractères pour l'unicité
    key = tuple(cache_key_parts)

    hit = _cache_get(key, ttl)
    if hit is not None:
        return hit
    payload = _post_api(method, params, api_key, api_secret)
    if isinstance(payload, dict):
        _cache_set(key, payload)
    return payload

def _now_ms() -> int:
    return int(time.time() * 1000)

def _clean_exchange_name(name: str) -> str:
    if not name: return "Unknown"
    n = str(name).strip()
    # CoinTracking renvoie souvent "Kraken Balance" etc.
    if n.endswith(" Balance"):
        n = n[:-8].strip()
    if n.endswith(" BALANCE"):
        n = n[:-8].strip()
    # Normaliser la casse (première lettre majuscule)
    if n:
        n = n.lower().capitalize()
    return n or "Unknown"

def _dig_details_map(payload: dict) -> dict:
    """
    Retourne la map des exchanges -> coins pour getGroupedBalance(group='exchange').
    Gère: payload['details'] OU payload['result']['details'].
    Normalise les cas où chaque exchange est encore wrappé sous un sous-champ 'details'.
    """
    if not isinstance(payload, dict):
        return {}
    details = payload.get("details")
    if not isinstance(details, dict):
        res = payload.get("result")
        if isinstance(res, dict):
            details = res.get("details")
    if not isinstance(details, dict):
        return {}

    out = {}
    for ex_name, ex_block in details.items():
        if isinstance(ex_block, dict) and isinstance(ex_block.get("details"), dict):
            # CoinTracking renvoie parfois: "<EX>": {"details": { "BTC": {...}, ...}}
            out[ex_name] = ex_block["details"]
        elif isinstance(ex_block, dict):
            out[ex_name] = ex_block
        else:
            out[ex_name] = {}
    return out

# --- helpers robustes pour parse CT ---
def _to_float(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return 0.0

def _clean_loc(raw: str) -> str:
    s = (raw or "Unknown").strip()
    if s.upper().endswith(" BALANCE"):
        s = s[:-8].strip()
    return s.title()

def _flatten_grouped_exchange(payload: dict, min_usd: float = 0.0):
    """
    Aplati la réponse getGroupedBalance(group='exchange') en lignes:
    { alias, symbol, amount, value_usd, price_usd, location }
    """
    items = []
    details = (payload or {}).get("details") or {}
    for ex_name, coins in details.items():
        loc = _clean_loc(ex_name)
        if not isinstance(coins, dict):
            continue
        for sym, v in coins.items():
            # champs possibles côté CT: amount, value_fiat, price_fiat (parfois value_usd)
            amt = _to_float((v or {}).get("amount"))
            val = _to_float((v or {}).get("value_usd") or (v or {}).get("value_fiat"))
            px  = _to_float((v or {}).get("price_usd") or (v or {}).get("price_fiat"))

            # fallback si value manquante
            if val <= 0 and px > 0 and amt != 0:
                val = amt * px

            if val < float(min_usd or 0.0):
                continue

            items.append({
                "alias": sym, "symbol": sym,
                "amount": amt,
                "value_usd": round(val, 6),
                "price_usd": px if px > 0 else None,
                "location": loc,
            })
    return items

# --- méthode publique à utiliser par l'API ---
async def get_items_by_exchange(client, min_usd: float = 0.0):
    """
    Utilise getGroupedBalance(exchange) et renvoie des lignes déjà localisées.
    'client' est ton objet HTTP (le même que celui qui appelle getBalance).
    """
    # selon ton code existant, adapte l'appel:
    #   data = await client.post("getGroupedBalance", {"group": "exchange"})
    # ou si tu as déjà un wrapper:
    data = await client.get_grouped_balance(group="exchange")  # <-- garde ta signature existante
    return _flatten_grouped_exchange(data, min_usd=min_usd)


# --- HTTP Low-level ----------------------------------------------------------
def _post_api(method: str, params: Optional[Dict[str, Any]] = None,
              api_key: Optional[str] = None, api_secret: Optional[str] = None) -> Dict[str, Any]:
    """
    Appel POST CoinTracking v1 :
      - URL = {API_BASE}/
      - body form-urlencoded: method, nonce, ...extra params
      - headers: Key, Sign (HMAC-SHA512 du body avec SECRET)
    """
    # Utiliser les clés fournies en paramètre ou fallback sur les variables d'environnement
    if api_key and api_secret:
        key = api_key
        sec = api_secret
    else:
        # Rafraîchir dynamiquement les clés si le module a été importé avant l'écriture dans .env
        key = API_KEY or os.getenv("CT_API_KEY") or os.getenv("COINTRACKING_API_KEY") or os.getenv("API_COINTRACKING_API_KEY") or ""
        sec = API_SECRET or os.getenv("CT_API_SECRET") or os.getenv("COINTRACKING_API_SECRET") or os.getenv("API_COINTRACKING_API_SECRET") or ""

    if not key or not sec:
        raise RuntimeError("CT_API_KEY / CT_API_SECRET manquants (ou vides) - fournir en paramètre ou dans l'environnement")

    url = API_BASE.rstrip("/") + "/"
    form: Dict[str, Any] = {"method": method, "nonce": _now_ms()}
    if params:
        form.update(params)

    body = urlencode(form).encode("utf-8")
    sign = hmac.new(sec.encode("utf-8"), body, hashlib.sha512).hexdigest()

    req = Request(
        url,
        data=body,
        headers={
            "Key": key,
            "Sign": sign,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "crypto-rebal-starter/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                raise RuntimeError(f"Réponse non JSON: {raw[:200]}...")
            return payload
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8','replace')}")
    except URLError as e:
        raise RuntimeError(f"URLError: {e}")
    except (OSError, TimeoutError) as e:
        raise RuntimeError(f"Network error: {e}")

# --- Parsing helpers ---------------------------------------------------------
def _num(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        if isinstance(x, str):
            x = x.replace(",", "").strip()
        return float(x)
    except (ValueError, TypeError):
        return None

def _sym(d: Dict[str, Any]) -> Optional[str]:
    for k in ("symbol","coin","currency","ticker","name"):
        v = d.get(k)
        if v:
            return str(v).upper()
    return None

def _location(d: Dict[str, Any]) -> Optional[str]:
    for k in ("exchange","wallet","location","place","group"):
        v = d.get(k)
        if v:
            return str(v)
    return None

def _ensure_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        # certains endpoints renvoient un dict indexé par symbol ou nom
        return list(x.values())
    return [x]

def _extract_rows_from_getBalance(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    getBalance: typiquement:
      - details: [{coin/symbol, amount, value_fiat, price_fiat, ...}, ...]
    On renvoie symbol, amount, value_usd et price_usd (si possible).
    """
    details = payload.get("details")
    if details is None and isinstance(payload.get("result"), dict):
        details = payload["result"].get("details")

    rows = []
    for it in _ensure_list(details):
        if not isinstance(it, dict):
            continue
        sym = _sym(it)
        if not sym:
            continue
        amt = _num(it.get("amount"))
        val_fiat = _num(it.get("value_fiat") or it.get("fiat") or it.get("usd") or it.get("value"))
        # prix direct si exposé, sinon calcule value/amount
        px = _num(it.get("price_fiat") or it.get("fiat_price") or it.get("price_usd") or it.get("price"))
        if px is None and val_fiat is not None and amt is not None and amt > 0:
            px = val_fiat / amt

        rows.append({
            "symbol": sym,
            "amount": amt or 0.0,
            "value_usd": val_fiat or 0.0,         # on suppose le compte en USD
            "price_usd": px if px and px > 0 else None,
            "location": _location(it) or "CoinTracking",
        })
    return rows

def _extract_rows_from_groupedBalance(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    CoinTracking getGroupedBalance(group='exchange') renvoie en pratique:
    {
      "success": 1,
      "result": {
        "details": {
          "Kraken Balance": {
            "details": { "BTC": {...}, "ETH": {...}, "TOTAL": {...} }
          },
          "Binance Balance": { ... }
        }
      }
    }
    Cette fonction retourne une liste de lignes coin/exchange:
    [{symbol, amount, value_usd (peut être 0), location=<exchange>}, ...]
    """
    logger.debug("CT-GB shape: has_result=%s keys_result=%s has_details_at_root=%s",
                 isinstance(payload.get("result"), dict),
                 list((payload.get("result") or {}).keys())[:5],
                 isinstance(payload.get("details"), dict))


    def _num(x):
        try:
            return float(str(x).replace(",", "").strip())
        except (ValueError, TypeError):
            return 0.0

    # 👉 lire au bon niveau
    root = payload.get("result") or payload
    details = root.get("details")
    if not isinstance(details, dict):
        return []

    out: List[Dict[str, Any]] = []

    for ex_name, ex_block in details.items():
        # certains dumps ont un wrap {"details": {...}}
        coins = None
        if isinstance(ex_block, dict) and isinstance(ex_block.get("details"), dict):
            coins = ex_block["details"]
        elif isinstance(ex_block, dict):
            coins = ex_block
        else:
            continue

        for sym, row in coins.items():
            if not isinstance(row, dict):
                continue
            if str(sym).upper() in ("TOTAL", "TOTAL_SUMMARY", "SUMMARY"):
                continue

            amount = _num(row.get("amount") or row.get("balance") or 0)
            fiat   = _num(row.get("fiat") or row.get("value_fiat") or row.get("usd") or row.get("value") or 0)

            if amount > 0:
                out.append({
                    "symbol": str(sym).upper(),
                    "amount": amount,
                    "value_usd": fiat,   # pourra être 0 : on revalorisera avec prices
                    "location": ex_name,
                })

    return out


def _extract_rows_from_api_groupedBalance(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    details = _get_details_dict(payload)
    if not isinstance(details, dict):
        return []

    out: List[Dict[str, Any]] = []
    for exchange_name, coin_map in details.items():
        if not isinstance(coin_map, dict):
            continue
        ex = _clean_exchange_name(exchange_name)
        for coin_symbol, coin_data in coin_map.items():
            if not isinstance(coin_data, dict):
                continue
            if coin_symbol in ("TOTAL_SUMMARY", "TOTAL", "SUMMARY"):
                continue
            amount = _num(coin_data.get("amount")) or 0.0
            fiat   = _num(coin_data.get("fiat") or coin_data.get("value_fiat") or coin_data.get("usd") or coin_data.get("value")) or 0.0
            if amount > 0:
                out.append({
                    "symbol": str(coin_symbol).upper(),
                    "amount": amount,
                    "value_usd": fiat,
                    "location": ex,
                })
    return out


def _extract_active_exchanges_from_grouped_balance(payload: Dict[str, Any]) -> List[str]:
    """
    Extrait la liste des exchanges actifs depuis getGroupedBalance.
    Retourne une liste de noms d'exchanges nettoyés.
    """
    # Structure attendue : payload["details"] contient les exchanges comme clés
    details = payload.get("details")
    if not isinstance(details, dict):
        return []
    
    active_exchanges = []
    for exchange_key, exchange_data in details.items():
        # Nettoyer le nom de l'exchange (enlever "BALANCE", normaliser)
        clean_name = _clean_exchange_name(exchange_key)
        if clean_name and clean_name != "Unknown":
            # Vérifier que l'exchange a des données (pas juste un résumé vide)
            if isinstance(exchange_data, dict) and exchange_data:
                active_exchanges.append(clean_name)
    
    return sorted(set(active_exchanges))  # Enlever les doublons et trier

def _smart_asset_distribution_disabled(assets: List[Dict[str, Any]], active_exchanges: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Distribue intelligemment les assets aux exchanges actifs selon des règles logiques.
    
    Règles de répartition :
    1. Stablecoins (USDT, USDC, etc.) → priorité aux CEX (plus liquides)
    2. Tokens DeFi/L2 → priorité aux wallets software (MetaMask, etc.)
    3. Bitcoin/ETH → répartition sur tous types avec priorité CEX
    4. Autres tokens → répartition proportionnelle
    """
    
    # Classification des exchanges par type
    cex_exchanges = []
    defi_wallets = []
    hardware_wallets = []
    other_exchanges = []
    
    for exchange in active_exchanges:
        exchange_lower = exchange.lower()
        if exchange_lower in ['binance', 'kraken', 'coinbase', 'bitget', 'bybit', 'okx', 'huobi', 'kucoin']:
            cex_exchanges.append(exchange)
        elif exchange_lower in ['metamask', 'phantom', 'rabby', 'trustwallet']:
            defi_wallets.append(exchange)
        elif exchange_lower in ['ledger', 'trezor']:
            hardware_wallets.append(exchange)
        else:
            other_exchanges.append(exchange)
    
    # Classification des assets par type
    def classify_asset(symbol: str) -> str:
        symbol = symbol.upper()
        if symbol in ['USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USD']:
            return 'stablecoin'
        elif symbol in ['BTC', 'TBTC', 'WBTC']:
            return 'bitcoin'
        elif symbol in ['ETH', 'WETH', 'STETH', 'WSTETH', 'RETH']:
            return 'ethereum'
        elif symbol in ['UNI', 'SUSHI', 'AAVE', 'COMP', 'LINK', 'MKR', '1INCH']:
            return 'defi'
        else:
            return 'other'
    
    # Distribution par règles
    distribution: Dict[str, List[Dict[str, Any]]] = {}
    
    for asset in assets:
        symbol = asset.get('symbol', '')
        asset_type = classify_asset(symbol)
        
        # Déterminer les exchanges préférés selon le type d'asset
        if asset_type == 'stablecoin':
            # Stablecoins → priorité CEX (plus liquides)
            preferred_exchanges = cex_exchanges + other_exchanges + defi_wallets + hardware_wallets
        elif asset_type in ['bitcoin', 'ethereum']:
            # BTC/ETH → répartition équilibrée avec priorité CEX
            preferred_exchanges = cex_exchanges + defi_wallets + other_exchanges + hardware_wallets
        elif asset_type == 'defi':
            # Tokens DeFi → priorité wallets
            preferred_exchanges = defi_wallets + cex_exchanges + other_exchanges + hardware_wallets
        else:
            # Autres → répartition proportionnelle
            preferred_exchanges = active_exchanges
        
        # Si aucun exchange préféré disponible, utiliser tous les exchanges actifs
        if not preferred_exchanges:
            preferred_exchanges = active_exchanges
        
        # Implémentation de la répartition proportionnelle
        if preferred_exchanges:
            # Calculer le poids total des exchanges préférés (basé sur leur capacité actuelle)
            exchange_weights = {}
            total_weight = 0
            
            for exchange in preferred_exchanges:
                # Utiliser la capacité actuelle comme poids (exchanges avec plus d'assets ont plus de poids)
                current_capacity = len([a for ex_assets in distribution.values() for a in ex_assets if a.get('location') == exchange])
                weight = max(1, current_capacity + 1)  # Minimum 1 pour éviter division par 0
                exchange_weights[exchange] = weight
                total_weight += weight
            
            # Distribuer l'asset proportionnellement
            asset_value = float(asset.get('value_usd', 0))
            remaining_value = asset_value
            
            for i, exchange in enumerate(preferred_exchanges):
                if i == len(preferred_exchanges) - 1:  # Dernier exchange reçoit le reste
                    allocation_value = remaining_value
                else:
                    proportion = exchange_weights[exchange] / total_weight
                    allocation_value = asset_value * proportion
                    remaining_value -= allocation_value
                
                if allocation_value > 0:
                    asset_copy = dict(asset)
                    asset_copy['location'] = exchange
                    asset_copy['value_usd'] = allocation_value
                    asset_copy['proportional_allocation'] = True
                    
                    if exchange not in distribution:
                        distribution[exchange] = []
                    distribution[exchange].append(asset_copy)
    
    return distribution

def _smart_asset_distribution(assets: List[Dict[str, Any]], active_exchanges: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Version simplifiée pour test"""
    if not active_exchanges:
        active_exchanges = ["Binance"]
    
    distribution = {}
    for asset in assets:
        exchange = active_exchanges[0]  # Assigner au premier exchange pour le test
        asset_copy = dict(asset)
        asset_copy['location'] = exchange
        
        if exchange not in distribution:
            distribution[exchange] = []
        distribution[exchange].append(asset_copy)
    
    return distribution

def _extract_rows_generic(payload: Any) -> List[Dict[str, Any]]:
    """
    Fallback très permissif: accepte
      - liste de dicts avec 'coin'/'currency'/'symbol'
      - dict {SYMBOL: {...}}
    """
    rows: List[Dict[str, Any]] = []
    seq = _ensure_list(payload)
    for it in seq:
        if not isinstance(it, dict):
            continue
        sym = _sym(it)
        if not sym:
            # cas dict {SYMBOL: {...}}
            guess: List[Dict[str, Any]] = []
            for k, v in it.items():
                if isinstance(v, dict):
                    vv = dict(v)
                    vv.setdefault("symbol", k)
                    guess.append(vv)
            if guess:
                seq.extend(guess)
                continue
            else:
                continue
        amt = _num(it.get("amount"))
        val = _num(it.get("value_usd") or it.get("usd_value") or it.get("fiat") or it.get("value"))
        rows.append({
            "symbol": sym,
            "amount": amt or 0.0,
            "value_usd": val or 0.0,
            "location": _location(it) or "CoinTracking",
        })
    return rows

def _get_details_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    CoinTracking met parfois les données sous payload['result']['details'].
    Cette fonction renvoie toujours un dict de 'details' si présent.
    """
    if not isinstance(payload, dict):
        return {}
    details = payload.get("details")
    if isinstance(details, dict):
        return details
    res = payload.get("result")
    if isinstance(res, dict):
        for k in ("details", "balances"):  # parfois CoinTracking met 'balances'
            d = res.get(k)
            if isinstance(d, dict):
                return d
    # dernier recours : si 'payload' lui-même est déjà la map
    return payload if isinstance(payload, dict) else {}

# --- Public API --------------------------------------------------------------
async def get_current_balances(source: str = "cointracking_api",
                               api_key: Optional[str] = None, api_secret: Optional[str] = None) -> dict:
    """
    Préfère getBalance (par coin) ; fallback sur getGroupedBalance (par exchange)
    Ne filtre PAS ici par value_usd (le filtre min_usd est fait par /balances/current).
    """
    # 1) getBalance
    try:
        p = await _post_api_cached_async("getBalance", {}, ttl=60, api_key=api_key, api_secret=api_secret)
        rows = _extract_rows_from_getBalance(p) or []
        if not rows and isinstance(p, dict) and isinstance(p.get("result"), dict):
            rows = _extract_rows_from_getBalance(p["result"]) or []
        # on retourne tel quel (même si value_usd == 0) ; le min_usd est géré par l'API FastAPI
        return {"source_used": "cointracking_api", "items": rows}
    except (RuntimeError, ValueError, KeyError):
        # API call failed or data parsing error, try fallback
        pass

    # 2) fallback: getGroupedBalance + recomposition des valeurs via une price map
    try:
        payload = await _post_api_cached_async("getGroupedBalance", {"group": "exchange"}, ttl=60,
                                              api_key=api_key, api_secret=api_secret)
        items = _extract_rows_from_groupedBalance(payload)  # amount>0, value_usd poss. 0

        # price map depuis getBalance
        price_map: dict[str, float] = {}
        try:
            p2 = await _post_api_cached_async("getBalance", {}, ttl=30, api_key=api_key, api_secret=api_secret)
            details = p2.get("details")
            if details is None and isinstance(p2.get("result"), dict):
                details = p2["result"].get("details")
            for it in _ensure_list(details):
                if isinstance(it, dict):
                    sym = _sym(it)
                    amt = _num(it.get("amount")) or 0.0
                    px  = _num(it.get("price_fiat"))
                    if px is None:
                        val = _num(it.get("value_fiat"))
                        if val and amt:
                            px = val / amt
                    if sym and px and px > 0:
                        price_map[sym] = px
        except (RuntimeError, ValueError, KeyError):
            # Failed to get price map, continue without it
            pass

        # compléter value_usd manquants
        for it in items:
            if not it.get("value_usd"):
                px = price_map.get(str(it.get("symbol") or "").upper())
                if px:
                    it["value_usd"] = float(it.get("amount") or 0.0) * px

        return {"source_used": "cointracking_api", "items": items}
    except (RuntimeError, ValueError, KeyError):
        # Fallback failed, return empty
        pass

    return {"source_used": "cointracking_api", "items": []}

def _get_coin_value_fiat(d: dict) -> float | None:
    # CoinTracking renvoie parfois fiat, parfois value_fiat / usd
    for k in ("fiat", "value_fiat", "usd", "value"):
        v = d.get(k)
        if v is not None:
            try:
                return float(str(v).replace(",", "").strip())
            except (ValueError, TypeError):
                pass
    return None

# cointracking_api.py

async def get_balances_by_exchange_via_api(api_key: Optional[str] = None, api_secret: Optional[str] = None) -> Dict[str, Any]:
    """
    1) getBalance -> récupère un prix par symbole (source de vérité pour la valorisation)
    2) getGroupedBalance(group='exchange', exclude_dep_with=1) -> quantités par exchange
    3) Si value_usd manquant/0, revalorise: value_usd = amount * price
    4) Retourne:
       {
         "exchanges": [{"location": "...", "total_value_usd": ..., "asset_count": ...}, ...],
         "detailed_holdings": {"Kraken": [...], "Binance": [...], ...}
       }
    """
    def _num(x):
        try:
            return float(str(x).replace(",", "").strip())
        except (ValueError, TypeError):
            return 0.0

    # 1) Récupération des données groupées et déduplication intelligente
    p_gb = await _post_api_cached_async("getGroupedBalance", {"group": "exchange", "exclude_dep_with": "1"}, ttl=60,
                                       api_key=api_key, api_secret=api_secret)
    rows_gb = _extract_rows_from_groupedBalance(p_gb)
    
    # 2) Déduplication: pour chaque symbol, aggréger les quantités mais garder la location principale
    symbol_aggregated: Dict[str, Dict[str, Any]] = {}
    location_values: Dict[str, Dict[str, float]] = {}  # symbol -> {location: value}
    
    def _clean_ex(name: str) -> str:
        n = (name or "").replace(" Balance", "").strip()
        return n.title() if n else "Unknown"
    
    for r in rows_gb:
        sym = str(r.get("symbol", "")).upper()
        amt = float(r.get("amount", 0))
        val = float(r.get("value_usd", 0))
        loc = _clean_ex(r.get("location", ""))
        
        if sym and amt > 0 and val > 0:
            # Agréger les quantités par symbole
            if sym not in symbol_aggregated:
                symbol_aggregated[sym] = {
                    "symbol": sym,
                    "total_amount": 0.0,
                    "total_value_usd": 0.0,
                    "price_usd": None
                }
                location_values[sym] = {}
            
            symbol_aggregated[sym]["total_amount"] += amt
            symbol_aggregated[sym]["total_value_usd"] += val
            location_values[sym][loc] = location_values[sym].get(loc, 0.0) + val
            
            # Calculer prix moyen pondéré
            if symbol_aggregated[sym]["total_amount"] > 0:
                symbol_aggregated[sym]["price_usd"] = symbol_aggregated[sym]["total_value_usd"] / symbol_aggregated[sym]["total_amount"]

    # 3) Attribution de la location principale (plus grande valeur) par symbole
    detailed: Dict[str, List[Dict[str, Any]]] = {}
    
    for sym, data in symbol_aggregated.items():
        # Trouver la location avec la plus grande valeur pour ce symbole
        if sym in location_values and location_values[sym]:
            primary_location = max(location_values[sym].items(), key=lambda x: x[1])[0]
        else:
            primary_location = "CoinTracking"
        
        detailed.setdefault(primary_location, []).append({
            "symbol": sym,
            "alias": sym,
            "amount": data["total_amount"],
            "value_usd": round(data["total_value_usd"], 8),
            "price_usd": round(data["price_usd"], 8) if data["price_usd"] else None,
            "location": primary_location
        })

    exchanges: List[Dict[str, Any]] = []
    for ex, items in list(detailed.items()):
        tv = sum(i.get("value_usd", 0.0) for i in items)
        if tv <= 0:
            detailed.pop(ex, None)
            continue
        exchanges.append({"location": ex, "total_value_usd": round(tv, 2), "asset_count": len(items)})

    exchanges.sort(key=lambda e: e["total_value_usd"], reverse=True)
    return {"source_used": "cointracking_api", "exchanges": exchanges, "detailed_holdings": detailed}

def _normalize_exchange_name(raw: str) -> str:
    if not raw:
        return "Unknown"
    s = raw.strip()
    # Beaucoup de lignes arrivent comme 'KRAKEN BALANCE', 'COINBASE BALANCE', etc.
    key = s.upper()
    if key in _EX_ALIAS_FIXES:
        return _EX_ALIAS_FIXES[key]
    # fallback générique: enlève le suffixe ' BALANCE'
    s = re.sub(r"\s*BALANCE\s*$", "", s, flags=re.IGNORECASE).strip()
    # quelques nettoyages courants
    s = s.replace("  ", " ")
    return s or "Unknown"

async def ct_grouped_balance_rows(session=None, exclude_dep_with: str = "1") -> list[dict]:
    """
    Appelle getGroupedBalance(group=exchange) et renvoie la liste brute (rows) telle que l'API la donne.
    """
    params = {"group": "exchange"}
    if exclude_dep_with is not None:
        params["exclude_dep_with"] = str(exclude_dep_with)
    data = await ct_call("getGroupedBalance", params=params, session=session)
    # data['details'] est normalement un mapping exchange->coins OU une liste de lignes selon ton parser.
    # Ton implémentation ct_call() actuelle remonte déjà des 'rows' à plat dans ct debug/previews.
    # Si besoin, adapte ici pour aplatir en lignes {symbol, amount, value_usd, location}
    rows = []
    details = data.get("details") or {}
    if isinstance(details, dict):
        # format 'exchange' -> { 'BTC': {...}, 'ETH': {...}, ... }
        for loc, coins in details.items():
            if not isinstance(coins, dict):
                continue
            for sym, payload in coins.items():
                rows.append({
                    "symbol": sym,
                    "amount": float(payload.get("amount") or 0),
                    "value_usd": float(payload.get("value_fiat") or payload.get("value_usd") or 0),
                    "price_usd": float(payload.get("price_fiat") or payload.get("price_usd") or 0),
                    "location": loc,
                })
    elif isinstance(details, list):
        # déjà à plat (suivant ta version)
        for r in details:
            rows.append({
                "symbol": r.get("symbol"),
                "amount": float(r.get("amount") or 0),
                "value_usd": float(r.get("value_usd") or r.get("value_fiat") or 0),
                "price_usd": float(r.get("price_usd") or r.get("price_fiat") or 0),
                "location": r.get("location") or r.get("exchange") or "",
            })
    return rows

async def get_exchanges_totals(min_usd: float = 0.0) -> list[dict]:
    """
    Totaux par exchange (pour Dashboard). Equiv. 'Balance by Exchange'.
    """
    rows = await ct_grouped_balance_rows()
    agg = defaultdict(lambda: {"location": "", "total_value_usd": 0.0, "asset_count": 0})
    seen_pairs = set()

    for r in rows:
        ex = _normalize_exchange_name(r.get("location", ""))
        val = float(r.get("value_usd") or 0.0)
        sym = (r.get("symbol") or "").upper()
        if val < (min_usd or 0):
            continue
        pair = (ex, sym)
        if pair not in seen_pairs:
            agg[ex]["asset_count"] += 1
            seen_pairs.add(pair)
        agg[ex]["location"] = ex
        agg[ex]["total_value_usd"] += val

    out = sorted(agg.values(), key=lambda x: x["total_value_usd"], reverse=True)
    return out

async def get_coins_by_exchange(min_usd: float = 0.0) -> list[dict]:
    """
    Coins par exchange (pour Rebalance). Equiv. 'Coin by Exchange'.
    Retourne des items: {exchange, alias, amount, value_usd}
    """
    rows = await ct_grouped_balance_rows()
    items = []
    for r in rows:
        ex = _normalize_exchange_name(r.get("location", ""))
        sym = (r.get("symbol") or "").upper()
        val = float(r.get("value_usd") or 0.0)
        amt = float(r.get("amount") or 0.0)
        if val < (min_usd or 0):
            continue
        # on filtre les lignes '0' / poubelles éventuelles
        if not sym or (amt == 0 and val == 0):
            continue
        items.append({
            "exchange": ex,
            "alias": sym,   # même alias que ton pipe “balances/current”
            "amount": amt,
            "value_usd": val
        })
    return items


# --- Petit endpoint de debug (utilisé par /debug/ctapi) ----------------------
def _debug_probe() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "env": {
            "has_key": bool(API_KEY),
            "has_secret": bool(API_SECRET),
            "key_len": len(API_KEY),
            "secret_len": len(API_SECRET),
            "base": API_BASE.rstrip("/"),
        },
        "tries": [],
        "ok": False,
        "first_success": None,
    }

    for method, params, extractor in [
        ("getGroupedBalance", {"group": "exchange"}, _extract_rows_from_groupedBalance),
        ("getBalance", {}, _extract_rows_from_getBalance),
    ]:
        entry: Dict[str, Any] = {"method": method, "params": params, "error": None, "rows_raw": 0, "rows_mapped": 0, "preview": []}
        try:
            payload = _post_api_cached("getGroupedBalance", {"group": "exchange", "exclude_dep_with": "1"}, ttl=60)
            # essayer différentes poches
            raw_candidates: List[Any] = []
            if isinstance(payload, dict):
                raw_candidates.extend([payload.get("balances"), payload.get("result"), payload.get("details"), payload])
            else:
                raw_candidates.append(payload)
            # compter le nb brut (approximatif)
            raw_rows = 0
            for rc in raw_candidates:
                if isinstance(rc, list):
                    raw_rows = max(raw_rows, len(rc))
                elif isinstance(rc, dict):
                    raw_rows = max(raw_rows, len(rc))
            entry["rows_raw"] = raw_rows

            mapped = extractor(payload) or []
            entry["rows_mapped"] = len(mapped)
            entry["preview"] = mapped[:3]
            if not out["ok"] and mapped:
                out["ok"] = True
                out["first_success"] = {"method": method, "rows": len(mapped)}
        except (RuntimeError, ValueError, KeyError) as e:
            entry["error"] = str(e)
        out["tries"].append(entry)

    return out
