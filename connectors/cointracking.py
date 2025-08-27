from __future__ import annotations
import os
import csv
from typing import Any, Dict, List, Optional

try:
    # API (si présent)
    from .cointracking_api import (  # type: ignore
        get_current_balances as get_balances_via_api,
        get_balances_by_exchange_via_api,
    )
except Exception:
    get_balances_via_api = None  # type: ignore
    get_balances_by_exchange_via_api = None  # type: ignore


# ---------- Demo ----------
_DEMO_ITEMS: List[Dict[str, Any]] = [
    {"symbol": "BTC", "amount": 1.2345, "value_usd": 75000.0, "location": "Demo"},
    {"symbol": "ETH", "amount": 20.0,   "value_usd": 60000.0, "location": "Demo"},
    {"symbol": "USDT","amount": 5000.0, "value_usd": 5000.0,  "location": "Demo"},
    {"symbol": "USDC","amount": 3000.0, "value_usd": 3000.0,  "location": "Demo"},
    {"symbol": "SOL", "amount": 250.0,  "value_usd": 17500.0, "location": "Demo"},
    {"symbol": "ADA", "amount": 5000.0, "value_usd": 1500.0,  "location": "Demo"},
    {"symbol": "LINK","amount": 800.0,  "value_usd": 12000.0, "location": "Demo"},
    {"symbol": "AAVE","amount": 120.0,  "value_usd": 12000.0, "location": "Demo"},
    {"symbol": "DOGE","amount": 300000, "value_usd": 6000.0,  "location": "Demo"},
]

def get_demo_balances() -> Dict[str, Any]:
    return {"source_used": "stub", "items": list(_DEMO_ITEMS)}


# ---------- CSV helpers ----------
def _norm_float(s: Any) -> float:
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    txt = str(s).strip().replace("\xa0", "").replace(" ", "")
    txt = txt.replace("'", "")
    if "," in txt and "." not in txt:
        txt = txt.replace(",", ".")
    if "," in txt and "." in txt:
        txt = txt.replace(",", "")
    try:
        return float(txt)
    except Exception:
        return 0.0


def _read_csv_safe(path: Optional[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path or not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        except Exception:
            class _D:
                delimiter = ","
            dialect = _D()
        reader = csv.DictReader(f, dialect=dialect)
        for row in reader:
            norm = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v) for k,v in row.items() }
            rows.append(norm)
    return rows


_SYMBOL_KEYS = ("Ticker", "Currency", "Coin", "Symbol", "Asset",
                "ticker", "currency", "coin", "symbol", "asset")
_AMOUNT_KEYS = ("Amount", "amount", "Qty", "Quantity", "quantity")
_VALUE_USD_KEYS = ("Value in USD", "Value (USD)", "USD Value",
                   "Current Value (USD)", "Total Value (USD)",
                   "Current value in USD", "value_usd", "Value", "value")
_PRICE_USD_KEYS = ("Price (USD)", "price_usd", "Price", "price")
_EXCHANGE_KEYS = ("Exchange", "exchange", "Location", "location", "Wallet", "wallet")


def _get_first(row: Dict[str, Any], keys) -> Optional[str]:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _guess_symbol(row: Dict[str, Any]) -> Optional[str]:
    v = _get_first(row, _SYMBOL_KEYS)
    return str(v).strip().upper() if v is not None else None


def _guess_amount(row: Dict[str, Any]) -> float:
    v = _get_first(row, _AMOUNT_KEYS)
    return _norm_float(v) if v is not None else 0.0


def _guess_value_usd(row: Dict[str, Any]) -> float:
    v = _get_first(row, _VALUE_USD_KEYS)
    if v is not None:
        return _norm_float(v)
    amt = _guess_amount(row)
    price = _get_first(row, _PRICE_USD_KEYS)
    if price is not None:
        return _norm_float(price) * amt
    return 0.0


def _guess_exchange(row: Dict[str, Any]) -> str:
    v = _get_first(row, _EXCHANGE_KEYS)
    return str(v).strip() if v is not None else "Unknown"


def _aggregate_by_symbol(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    agg: Dict[str, Dict[str, float]] = {}
    for r in rows:
        sym = _guess_symbol(r)
        if not sym:
            continue
        amt = _guess_amount(r)
        val = _guess_value_usd(r)
        if sym not in agg:
            agg[sym] = {"amount": 0.0, "value_usd": 0.0}
        agg[sym]["amount"] += amt
        agg[sym]["value_usd"] += val
    out = [
        {"symbol": s, "amount": round(v["amount"], 12), "value_usd": round(v["value_usd"], 8), "location": "CoinTracking"}
        for s, v in agg.items()
    ]
    out.sort(key=lambda x: x.get("value_usd", 0.0), reverse=True)
    return out


def _aggregate_by_exchange(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    agg: Dict[str, Dict[str, float]] = {}
    for r in rows:
        sym = _guess_symbol(r)
        if not sym:
            continue
        amt = _guess_amount(r)
        val = _guess_value_usd(r)
        exchange = _guess_exchange(r)
        if exchange not in agg:
            agg[exchange] = {"total_value_usd": 0.0, "asset_count": 0}
        agg[exchange]["total_value_usd"] += val
        if amt > 0:
            agg[exchange]["asset_count"] += 1
    out = []
    for ex, data in agg.items():
        if data["total_value_usd"] > 0:
            out.append({"location": ex, "total_value_usd": round(data["total_value_usd"], 2), "asset_count": data["asset_count"]})
    out.sort(key=lambda x: x.get("total_value_usd", 0.0), reverse=True)
    return out


def _get_detailed_holdings_by_exchange(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    holdings: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        sym = _guess_symbol(r)
        if not sym:
            continue
        amt = _guess_amount(r)
        val = _guess_value_usd(r)
        exchange = _guess_exchange(r)
        if amt <= 0:
            continue
        holdings.setdefault(exchange, []).append({
            "symbol": sym, "amount": round(amt, 12), "value_usd": round(val, 8), "location": exchange
        })
    for ex in holdings:
        holdings[ex].sort(key=lambda x: x.get("value_usd", 0.0), reverse=True)
    return holdings


def _resolve_csv_path(cands):
    ex = [c for c in cands if c and os.path.exists(c)]
    if not ex:
        return None
    ex.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return ex[0]


def get_current_balances_from_csv() -> Dict[str, Any]:
    """Charge les données Current Balance depuis CSV avec support dynamique des dates"""
    import glob
    env_cur = os.getenv("COINTRACKING_CSV")
    
    # Recherche dynamique des fichiers "Current Balance" avec dates
    data_raw_dir = os.path.join("data", "raw")
    current_patterns = [
        "CoinTracking - Current Balance - *.csv",  # Avec date quelconque
        "CoinTracking - Current Balance_*.csv",    # Autres variantes
        "CoinTracking - Current Balance.csv"       # Sans date
    ]
    
    # Chercher tous les fichiers correspondants aux patterns
    found_files = []
    if os.path.exists(data_raw_dir):
        for pattern in current_patterns:
            pattern_path = os.path.join(data_raw_dir, pattern)
            found_files.extend(glob.glob(pattern_path))
    
    # Trier par date de modification (plus récent en premier)
    found_files.sort(key=lambda f: os.path.getmtime(f) if os.path.exists(f) else 0, reverse=True)
    
    # Construire la liste des candidats
    cands = []
    if env_cur and "Current Balance" in env_cur:
        cands.append(env_cur)
    
    # Ajouter tous les fichiers trouvés (triés par date)
    cands.extend(found_files)
    
    # Ajouter aussi les anciens noms fixes pour compatibilité
    legacy_names = ["CoinTracking - Current Balance_mini.csv", "CoinTracking - Current Balance.csv"]
    for n in legacy_names:
        cands += [os.path.join("data", "raw", n), os.path.join("data", n), n]
    
    p = _resolve_csv_path([c for c in cands if c])
    rows = _read_csv_safe(p)
    items = _aggregate_by_symbol(rows)
    return {"source_used": "cointracking", "items": items}


def get_coins_by_exchange_from_csv() -> Dict[str, Any]:
    """Charge les données 'Coins by Exchange' depuis CSV avec support dynamique des dates"""
    import glob
    env_cur = os.getenv("COINTRACKING_CSV")
    
    # Recherche dynamique des fichiers "Coins by Exchange" avec dates
    data_raw_dir = os.path.join("data", "raw")
    coins_patterns = [
        "CoinTracking - Coins by Exchange - *.csv",  # Avec date quelconque
        "CoinTracking - Coins by Exchange_*.csv",    # Autres variantes
        "CoinTracking - Coins by Exchange.csv"       # Sans date
    ]
    
    # Chercher tous les fichiers correspondants aux patterns
    found_files = []
    if os.path.exists(data_raw_dir):
        for pattern in coins_patterns:
            pattern_path = os.path.join(data_raw_dir, pattern)
            found_files.extend(glob.glob(pattern_path))
    
    # Trier par date de modification (plus récent en premier)
    found_files.sort(key=lambda f: os.path.getmtime(f) if os.path.exists(f) else 0, reverse=True)
    
    # Fallback vers Current Balance si aucun Coins by Exchange
    fb_names = ["CoinTracking - Current Balance_mini.csv", "CoinTracking - Current Balance.csv"]
    
    # Construire la liste des candidats
    cands = []
    if env_cur and "Coins by Exchange" in env_cur:
        cands.append(env_cur)
    
    # Ajouter tous les fichiers trouvés (triés par date)
    cands.extend(found_files)
    
    # Ajouter aussi les anciens noms fixes pour compatibilité
    legacy_names = [
        "CoinTracking - Coins by Exchange_mini.csv", 
        "CoinTracking - Coins by Exchange.csv"
    ]
    for n in legacy_names:
        cands += [os.path.join("data", "raw", n), os.path.join("data", n), n]
    
    # Fallback vers Current Balance si aucun Coins by Exchange trouvé
    for n in fb_names:
        cands += [os.path.join("data", "raw", n), os.path.join("data", n), n]
    
    p = _resolve_csv_path([c for c in cands if c])
    rows = _read_csv_safe(p)
    items = _build_coins_by_exchange_structure(rows)
    return {"source_used": "cointracking_coins", "items": items}


def _build_coins_by_exchange_structure(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Construit la structure coins par exchange à partir des lignes CSV"""
    # Dictionnaire pour grouper par exchange puis par coin
    exchanges = {}
    
    for row in rows:
        symbol = _guess_symbol(row)
        amount = _guess_amount(row) 
        value_usd = _guess_value_usd(row)
        exchange = _get_first(row, _EXCHANGE_KEYS) or "Unknown"
        
        if not symbol or amount <= 0 or value_usd <= 0:
            continue
            
        # Initialiser exchange si pas encore présent
        if exchange not in exchanges:
            exchanges[exchange] = {}
        
        # Ajouter ou cumuler le coin dans cet exchange
        if symbol in exchanges[exchange]:
            exchanges[exchange][symbol]["amount"] += amount
            exchanges[exchange][symbol]["value_usd"] += value_usd
        else:
            exchanges[exchange][symbol] = {
                "symbol": symbol,
                "amount": amount,
                "value_usd": value_usd
            }
    
    # Convertir en structure de liste pour l'API
    result = []
    for exchange, coins in exchanges.items():
        for symbol, data in coins.items():
            result.append({
                "symbol": symbol,
                "amount": data["amount"],
                "value_usd": data["value_usd"],
                "location": exchange
            })
    
    return result


def get_balances_by_exchange_from_csv() -> Dict[str, Any]:
    import glob
    env_cur = os.getenv("COINTRACKING_CSV")
    
    # Recherche dynamique des fichiers "Balance by Exchange" avec dates
    data_raw_dir = os.path.join("data", "raw")
    balance_patterns = [
        "CoinTracking - Balance by Exchange - *.csv",  # Avec date quelconque
        "CoinTracking - Balance by Exchange_*.csv",    # Autres variantes
        "CoinTracking - Balance by Exchange.csv"       # Sans date
    ]
    
    # Chercher tous les fichiers correspondants aux patterns
    found_files = []
    if os.path.exists(data_raw_dir):
        for pattern in balance_patterns:
            pattern_path = os.path.join(data_raw_dir, pattern)
            found_files.extend(glob.glob(pattern_path))
    
    # Trier par date de modification (plus récent en premier)
    found_files.sort(key=lambda f: os.path.getmtime(f) if os.path.exists(f) else 0, reverse=True)
    
    fb_names = ["CoinTracking - Current Balance_mini.csv", "CoinTracking - Current Balance.csv"]
    
    # Privilégier les fichiers "Balance by Exchange" d'abord
    cands = []
    if env_cur and "Balance by Exchange" in env_cur:
        cands.append(env_cur)
    
    # Ajouter tous les fichiers trouvés (triés par date)
    cands.extend(found_files)
    
    # Ajouter aussi les anciens noms fixes pour compatibilité
    legacy_names = [
        "CoinTracking - Balance by Exchange_mini.csv", 
        "CoinTracking - Balance by Exchange.csv"
    ]
    for n in legacy_names:
        cands += [os.path.join("data", "raw", n), os.path.join("data", n), n]
    
    # Si aucun fichier "Balance by Exchange" trouvé, utiliser Current Balance en fallback
    p = _resolve_csv_path([c for c in cands if c])
    if not p:
        for n in fb_names:
            cands += [os.path.join("data", "raw", n), os.path.join("data", n), n]
        p = _resolve_csv_path([c for c in cands if c])
    
    rows = _read_csv_safe(p)
    return {
        "source_used": "cointracking",
        "exchanges": _aggregate_by_exchange(rows),
        "detailed_holdings": _get_detailed_holdings_by_exchange(rows),
    }


def get_combined_balances_with_locations() -> Dict[str, Any]:
    current_items = get_current_balances_from_csv().get("items", [])
    detailed = get_balances_by_exchange_from_csv().get("detailed_holdings", {})
    sym2loc: Dict[str, str] = {}
    for ex, items in detailed.items():
        for it in items:
            s = str(it.get("symbol", "")).upper()
            if s:
                sym2loc[s] = ex
    enriched = []
    for it in current_items:
        s = str(it.get("symbol", "")).upper()
        loc = sym2loc.get(s, "Portfolio")
        e = dict(it); e["location"] = loc
        enriched.append(e)
    return {"source_used": "cointracking_combined", "items": enriched, "exchange_mapping_count": len(sym2loc)}


# ---------- helpers API exchange parsing ----------
def _clean_exchange_name(x: Any) -> str:
    s = str(x or "").strip().replace("_", " ").replace("-", " ")
    # drop suffixes
    for suf in (" BALANCE", " Balance", " WALLET", " Wallet", " EXCHANGE", " Exchange"):
        if s.upper().endswith(suf.strip().upper()):
            s = s[: -len(suf)].strip()
    s = s.title()
    # fix acronyms
    fixes = {"Okx": "OKX", "Ftx": "FTX", "Mexc": "MEXC", "Btcturk": "BTCTurk"}
    return fixes.get(s, s)


def _exchanges_from_grouped_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        name = r.get("symbol") or r.get("name") or r.get("exchange") or r.get("location")
        loc = _clean_exchange_name(name)
        val = _norm_float(r.get("value_usd") or r.get("usd_value") or r.get("total_value_usd") or r.get("value"))
        amt = _norm_float(r.get("amount") or 0)
        if val <= 0 and amt <= 0:
            continue
        out.append({"location": loc, "total_value_usd": round(val, 2), "asset_count": int(r.get("asset_count") or 0)})
    out.sort(key=lambda x: x["total_value_usd"], reverse=True)
    return out


# ---------- Dispatcher ----------
async def get_unified_balances_by_exchange(source: str = "cointracking") -> Dict[str, Any]:
    s = (source or "").lower()

    if s in ("stub", "demo"):
        return {
            "source_used": "stub",
            "exchanges": [{"location": "Demo Wallet", "total_value_usd": 189000.0, "asset_count": 9}],
            "detailed_holdings": {"Demo Wallet": _DEMO_ITEMS.copy()},
        }

    if s == "cointracking":
        try:
            ex_data = get_balances_by_exchange_from_csv()
            exchanges = ex_data.get("exchanges", [])
            detailed = ex_data.get("detailed_holdings", {})
            cur_items = get_current_balances_from_csv().get("items", [])
            tot_cur = sum(i.get("value_usd", 0) for i in cur_items)
            tot_ex = sum(e.get("total_value_usd", 0) for e in exchanges)
            if not detailed or (tot_cur > 0 and tot_ex < tot_cur * 0.8):
                # enrich à partir des items
                if cur_items:
                    sym2ex: Dict[str, str] = {}
                    for ex, hold in detailed.items():
                        for h in hold:
                            s = str(h.get("symbol", "")).upper()
                            if s:
                                sym2ex[s] = ex
                    buckets: Dict[str, List[Dict[str, Any]]] = {}
                    for it in cur_items:
                        s = str(it.get("symbol", "")).upper()
                        ex = sym2ex.get(s, "Portfolio")
                        it2 = dict(it); it2["location"] = ex
                        buckets.setdefault(ex, []).append(it2)
                    ex_list = []
                    for ex, arr in buckets.items():
                        val = sum(x.get("value_usd", 0) for x in arr)
                        if val > 0:
                            ex_list.append({"location": ex, "total_value_usd": round(val, 2), "asset_count": len(arr)})
                    ex_list.sort(key=lambda x: x["total_value_usd"], reverse=True)
                    return {"source_used": "cointracking", "exchanges": ex_list, "detailed_holdings": buckets}
                return {"source_used": "cointracking", "exchanges": [], "detailed_holdings": {}}
            return ex_data
        except Exception as e:
            return {"source_used": "cointracking", "exchanges": [], "detailed_holdings": {}, "error": str(e)}

    if s == "cointracking_api":
        # 1) tenter l’API “by exchange” si dispo
        if get_balances_by_exchange_via_api is not None:
            try:
                raw = await get_balances_by_exchange_via_api()

                # a) déjà structuré ?
                if isinstance(raw, dict) and isinstance(raw.get("exchanges"), list) and raw["exchanges"]:
                    return {"source_used": "cointracking_api",
                            "exchanges": raw["exchanges"],
                            "detailed_holdings": raw.get("detailed_holdings") or {}}

                # b) liste brute de lignes groupées ?
                rows: Optional[List[Dict[str, Any]]] = None
                if isinstance(raw, list):
                    rows = raw
                elif isinstance(raw, dict):
                    for key in ("rows", "items", "data", "grouped", "grouped_rows", "balances"):
                        v = raw.get(key)
                        if isinstance(v, list) and v:
                            rows = v
                            break
                if rows:
                    ex_list = _exchanges_from_grouped_rows(rows)
                    if ex_list:
                        return {"source_used": "cointracking_api", "exchanges": ex_list, "detailed_holdings": {}}
            except Exception as e:
                # on tombera sur le fallback ci-dessous
                pass

        # 2) fallback: balances simples (un seul “CoinTracking”)
        try:
            if get_balances_via_api is not None:
                cur = await get_balances_via_api()
                items = cur.get("items", [])
                if items:
                    total = sum(float(i.get("value_usd") or 0) for i in items)
                    for it in items:
                        it["location"] = "CoinTracking"
                    return {
                        "source_used": "cointracking_api",
                        "exchanges": [{"location": "CoinTracking", "total_value_usd": round(total, 2), "asset_count": len(items)}],
                        "detailed_holdings": {"CoinTracking": items},
                    }
            return {"source_used": "cointracking_api", "exchanges": [], "detailed_holdings": {}, "error": "API connector not available"}
        except Exception as e:
            return {"source_used": "cointracking_api", "exchanges": [], "detailed_holdings": {}, "error": str(e)}

    # fallback CSV
    return await get_unified_balances_by_exchange("cointracking")


async def get_current_balances(source: str = "cointracking") -> Dict[str, Any]:
    s = (source or "").lower()
    if s in ("stub", "demo"):
        return get_demo_balances()
    if s == "cointracking":
        return get_current_balances_from_csv()
    if s == "cointracking_api":
        if get_balances_via_api is None:
            return {"source_used": "cointracking_api", "items": []}
        res = await get_balances_via_api()
        return res or {"source_used": "cointracking_api", "items": []}
    return get_current_balances_from_csv()
