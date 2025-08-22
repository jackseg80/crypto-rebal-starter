
from __future__ import annotations
import os
import csv
from typing import Any, Dict, List, Optional

# Optional API connector (not used for 'csv'/'stub' paths here but left for completeness)
try:
    from .cointracking_api import get_balances_via_api, get_balances_by_exchange_via_api  # type: ignore
except Exception:
    get_balances_via_api = None  # type: ignore
    get_balances_by_exchange_via_api = None  # type: ignore

# ---------------- Demo data ----------------
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

# ---------------- CSV helpers ----------------
def _norm_float(s: Any) -> float:
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    txt = str(s).strip().replace("\xa0", "").replace(" ", "")
    txt = txt.replace("'", "")  # thousands separator in some locales
    # Handle "1,234.56" and "1234,56"
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
    # Keep file open while consuming DictReader
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

# Accept various header names exported by CoinTracking
_SYMBOL_KEYS = (
    "Ticker", "Currency", "Coin", "Symbol", "Asset",
    "ticker", "currency", "coin", "symbol", "asset"
)
_AMOUNT_KEYS = ("Amount", "amount", "Qty", "Quantity", "quantity")
_VALUE_USD_KEYS = (
    "Value in USD", "Value (USD)", "USD Value",
    "Current Value (USD)", "Total Value (USD)",
    "Current value in USD", "value_usd", "Value", "value"
)
_PRICE_USD_KEYS = ("Price (USD)", "price_usd", "Price", "price")
_EXCHANGE_KEYS = ("Exchange", "exchange", "Location", "location", "Wallet", "wallet")

def _get_first(row: Dict[str, Any], keys) -> Optional[str]:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None

def _guess_symbol(row: Dict[str, Any]) -> Optional[str]:
    val = _get_first(row, _SYMBOL_KEYS)
    return str(val).strip().upper() if val is not None else None

def _guess_amount(row: Dict[str, Any]) -> float:
    val = _get_first(row, _AMOUNT_KEYS)
    return _norm_float(val) if val is not None else 0.0

def _guess_value_usd(row: Dict[str, Any]) -> float:
    val = _get_first(row, _VALUE_USD_KEYS)
    if val is not None:
        return _norm_float(val)
    amt = _guess_amount(row)
    price = _get_first(row, _PRICE_USD_KEYS)
    if price is not None:
        return _norm_float(price) * amt
    return 0.0

def _guess_exchange(row: Dict[str, Any]) -> str:
    val = _get_first(row, _EXCHANGE_KEYS)
    return str(val).strip() if val is not None else "Unknown"

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
    out = [ {"symbol": s, "amount": round(v["amount"], 12), "value_usd": round(v["value_usd"], 8), "location": "CoinTracking"} for s, v in agg.items() ]
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
        if amt > 0:  # Only count assets with positive amounts
            agg[exchange]["asset_count"] += 1
    
    out = []
    for exchange, data in agg.items():
        if data["total_value_usd"] > 0:  # Only include exchanges with positive value
            out.append({
                "location": exchange,
                "total_value_usd": round(data["total_value_usd"], 2),
                "asset_count": data["asset_count"]
            })
    
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
        
        if amt <= 0:  # Skip zero or negative amounts
            continue
            
        if exchange not in holdings:
            holdings[exchange] = []
        
        holdings[exchange].append({
            "symbol": sym,
            "amount": round(amt, 12),
            "value_usd": round(val, 8),
            "location": exchange
        })
    
    # Sort holdings within each exchange by value
    for exchange in holdings:
        holdings[exchange].sort(key=lambda x: x.get("value_usd", 0.0), reverse=True)
    
    return holdings

def _resolve_csv_path(candidates):
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

def get_current_balances_from_csv() -> Dict[str, Any]:
    env_cur = os.getenv("COINTRACKING_CSV")
    # Noms d'exports CoinTracking courants (mini + full) :
    default_names = [
        "CoinTracking - Current Balance_mini.csv",
        "CoinTracking - Balance by Exchange_mini.csv",
        "CoinTracking - Current Balance.csv",
        "CoinTracking - Balance by Exchange.csv",
    ]
    candidates_cur = []
    # 1) priorité à la variable d'env explicite
    if env_cur:
        candidates_cur.append(env_cur)
    # 2) chercher dans data/ puis dans cwd pour chaque nom connu
    for name in default_names:
        candidates_cur.append(os.path.join("data", name))
        candidates_cur.append(name)
    # 3) choisir le plus récent parmi ceux qui existent
    p_cur = _resolve_csv_path([c for c in candidates_cur if c])
    rows_cur = _read_csv_safe(p_cur)
    items = _aggregate_by_symbol(rows_cur)
    return {"source_used": "cointracking", "items": items}

def get_balances_by_exchange_from_csv() -> Dict[str, Any]:
    env_cur = os.getenv("COINTRACKING_CSV")
    # Prioriser UNIQUEMENT les fichiers "Balance by Exchange" pour avoir les infos d'exchange
    exchange_names = [
        "CoinTracking - Balance by Exchange_mini.csv",
        "CoinTracking - Balance by Exchange.csv",
    ]
    fallback_names = [
        "CoinTracking - Current Balance_mini.csv",
        "CoinTracking - Current Balance.csv",
    ]
    
    candidates_cur = []
    
    # Seulement utiliser la variable d'env si c'est un fichier "Balance by Exchange"
    if env_cur and "Balance by Exchange" in env_cur:
        candidates_cur.append(env_cur)
    
    # Prioriser les fichiers Exchange, puis fallback sur les autres
    for name in exchange_names + fallback_names:
        # Chercher d'abord dans data/raw puis data puis racine
        candidates_cur.append(os.path.join("data", "raw", name))
        candidates_cur.append(os.path.join("data", name))
        candidates_cur.append(name)
    
    p_cur = _resolve_csv_path([c for c in candidates_cur if c])
    rows_cur = _read_csv_safe(p_cur)
    
    # Retourner les données agrégées par exchange
    exchange_summary = _aggregate_by_exchange(rows_cur)
    detailed_holdings = _get_detailed_holdings_by_exchange(rows_cur)
    
    return {
        "source_used": "cointracking", 
        "exchanges": exchange_summary,
        "detailed_holdings": detailed_holdings
    }

def get_combined_balances_with_locations() -> Dict[str, Any]:
    """
    Combine les données du Current Balance (portfolio complet) avec les informations
    d'exchange du Balance by Exchange pour avoir toutes les positions avec leurs locations.
    """
    # 1. Récupérer le portfolio complet
    current_balance = get_current_balances_from_csv()
    current_items = current_balance.get("items", [])
    
    # 2. Récupérer les données d'exchange
    exchange_data = get_balances_by_exchange_from_csv()
    detailed_holdings = exchange_data.get("detailed_holdings", {})
    
    # 3. Créer un mapping symbol -> location basé sur les données d'exchange
    symbol_to_location = {}
    for exchange, holdings in detailed_holdings.items():
        for holding in holdings:
            symbol = holding.get("symbol", "").upper()
            if symbol:
                symbol_to_location[symbol] = exchange
    
    # 4. Enrichir les données du portfolio complet avec les informations de location
    enriched_items = []
    for item in current_items:
        symbol = str(item.get("symbol", "")).upper()
        # Chercher la location dans les données d'exchange
        location = symbol_to_location.get(symbol, "Portfolio")  # Default fallback location
        
        # Créer une copie enrichie de l'item
        enriched_item = dict(item)
        enriched_item["location"] = location
        enriched_items.append(enriched_item)
    
    return {
        "source_used": "cointracking_combined",
        "items": enriched_items,
        "exchange_mapping_count": len(symbol_to_location)
    }

async def get_unified_balances_by_exchange(source: str = "cointracking") -> Dict[str, Any]:
    """
    Fonction unifiée pour récupérer les balances par exchange selon la source de données.
    Gère les fallbacks en cas de données manquantes.
    """
    s = (source or "").lower()
    
    if s in ("stub", "demo"):
        # Demo data avec locations fictives
        return {
            "source_used": "stub",
            "exchanges": [
                {"location": "Demo Wallet", "total_value_usd": 189000.0, "asset_count": 9}
            ],
            "detailed_holdings": {
                "Demo Wallet": _DEMO_ITEMS.copy()
            }
        }
    
    elif s == "cointracking":
        # Source CSV
        try:
            exchange_data = get_balances_by_exchange_from_csv()
            exchanges = exchange_data.get("exchanges", [])
            detailed_holdings = exchange_data.get("detailed_holdings", {})
            
            # Fallback si pas de données d'exchange dans le CSV
            if not exchanges or not detailed_holdings:
                # Utiliser les balances générales avec une location par défaut
                current_balance = get_current_balances_from_csv()
                current_items = current_balance.get("items", [])
                
                if current_items:
                    total_value = sum(item.get("value_usd", 0) for item in current_items)
                    # Assigner la location par défaut à tous les items
                    for item in current_items:
                        item["location"] = "Portfolio"
                    
                    return {
                        "source_used": "cointracking",
                        "exchanges": [
                            {"location": "Portfolio", "total_value_usd": round(total_value, 2), "asset_count": len(current_items)}
                        ],
                        "detailed_holdings": {
                            "Portfolio": current_items
                        }
                    }
                else:
                    # Pas de données du tout
                    return {
                        "source_used": "cointracking",
                        "exchanges": [],
                        "detailed_holdings": {}
                    }
            
            return exchange_data
            
        except Exception as e:
            # Erreur lors de la lecture CSV - fallback sur location par défaut
            return {
                "source_used": "cointracking",
                "exchanges": [],
                "detailed_holdings": {},
                "error": str(e)
            }
    
    elif s == "cointracking_api":
        # Source API
        if get_balances_by_exchange_via_api is None:
            # API non disponible - fallback sur une location par défaut
            try:
                if get_balances_via_api is not None:
                    # Au moins récupérer les balances générales
                    current_balance = await get_balances_via_api()
                    current_items = current_balance.get("items", [])
                    
                    if current_items:
                        total_value = sum(item.get("value_usd", 0) for item in current_items)
                        # Assigner la location par défaut à tous les items
                        for item in current_items:
                            item["location"] = "CoinTracking"
                        
                        return {
                            "source_used": "cointracking_api",
                            "exchanges": [
                                {"location": "CoinTracking", "total_value_usd": round(total_value, 2), "asset_count": len(current_items)}
                            ],
                            "detailed_holdings": {
                                "CoinTracking": current_items
                            }
                        }
                
                return {
                    "source_used": "cointracking_api",
                    "exchanges": [],
                    "detailed_holdings": {},
                    "error": "API connector not available"
                }
                
            except Exception as e:
                return {
                    "source_used": "cointracking_api",
                    "exchanges": [],
                    "detailed_holdings": {},
                    "error": str(e)
                }
        
        try:
            # Utiliser l'API pour récupérer les données d'exchange
            api_result = await get_balances_by_exchange_via_api()
            exchanges = api_result.get("exchanges", [])
            detailed_holdings = api_result.get("detailed_holdings", {})
            
            # Fallback si l'API ne retourne pas de données d'exchange
            if not exchanges or not detailed_holdings:
                # Essayer de récupérer les balances générales via API
                current_balance = await get_balances_via_api()
                current_items = current_balance.get("items", [])
                
                if current_items:
                    total_value = sum(item.get("value_usd", 0) for item in current_items)
                    # Assigner la location par défaut à tous les items
                    for item in current_items:
                        item["location"] = "CoinTracking"
                    
                    return {
                        "source_used": "cointracking_api",
                        "exchanges": [
                            {"location": "CoinTracking", "total_value_usd": round(total_value, 2), "asset_count": len(current_items)}
                        ],
                        "detailed_holdings": {
                            "CoinTracking": current_items
                        }
                    }
            
            return api_result
            
        except Exception as e:
            return {
                "source_used": "cointracking_api",
                "exchanges": [],
                "detailed_holdings": {},
                "error": str(e)
            }
    
    else:
        # Fallback sur CSV par défaut
        return await get_unified_balances_by_exchange("cointracking")

# ---------------- Dispatcher ----------------
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

    # fallback to CSV
    return get_current_balances_from_csv()
