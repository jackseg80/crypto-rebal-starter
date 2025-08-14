# connectors/cointracking_api.py
from __future__ import annotations

import os
import time
import hmac
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# --- Config (.env) -----------------------------------------------------------
# On supporte les 2 variantes de noms d'env pour être tolérant :
API_BASE = os.getenv("CT_API_BASE") or os.getenv("COINTRACKING_API_BASE") or "https://cointracking.info/api/v1/"
API_KEY = (os.getenv("CT_API_KEY") or os.getenv("COINTRACKING_API_KEY") or "").strip()
API_SECRET = (os.getenv("CT_API_SECRET") or os.getenv("COINTRACKING_API_SECRET") or "").strip()

def _now_ms() -> int:
    return int(time.time() * 1000)

# --- HTTP Low-level ----------------------------------------------------------
def _post_api(method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Appel POST CoinTracking v1 :
      - URL = {API_BASE}/
      - body form-urlencoded: method, nonce, ...extra params
      - headers: Key, Sign (HMAC-SHA512 du body avec SECRET)
    """
    if not API_KEY or not API_SECRET:
        raise RuntimeError("CT_API_KEY / CT_API_SECRET manquants (ou vides)")

    url = API_BASE.rstrip("/") + "/"
    form: Dict[str, Any] = {"method": method, "nonce": _now_ms()}
    if params:
        form.update(params)

    body = urlencode(form).encode("utf-8")
    sign = hmac.new(API_SECRET.encode("utf-8"), body, hashlib.sha512).hexdigest()

    req = Request(
        url,
        data=body,
        headers={
            "Key": API_KEY,
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
    except Exception as e:
        raise RuntimeError(f"Erreur CT: {e}")

# --- Parsing helpers ---------------------------------------------------------
def _num(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        if isinstance(x, str):
            x = x.replace(",", "").strip()
        return float(x)
    except Exception:
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
    getBalance: d'après la doc CT, le résultat contient souvent:
      - account_currency
      - details: liste/dict de monnaies avec {coin, amount, value_fiat, price_fiat, ...}
      - summary: totaux
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
        # 'value_fiat' est la valeur dans la devise du compte (souvent USD)
        val_fiat = _num(it.get("value_fiat") or it.get("fiat") or it.get("usd") or it.get("value"))
        rows.append({
            "symbol": sym,
            "amount": amt or 0.0,
            "value_usd": val_fiat or 0.0,  # on suppose compte en USD
            "location": _location(it) or "CoinTracking",
        })
    return rows

def _extract_rows_from_groupedBalance(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    getGroupedBalance: structure imbriquée par groupe ('exchange' par défaut).
    On a pour chaque groupe un dict {SYMBOL: {amount, fiat, btc}, ..., TOTAL_SUMMARY: {...}}
    """
    # les données peuvent être sous payload['balances'] ou directement dans payload['result']
    container = None
    if isinstance(payload.get("balances"), dict):
        container = payload["balances"]
    elif isinstance(payload.get("result"), dict):
        container = payload["result"]
    elif isinstance(payload, dict):
        container = payload

    if not isinstance(container, dict):
        return []

    out: List[Dict[str, Any]] = []
    for group_name, group_obj in container.items():
        if not isinstance(group_obj, dict):
            continue
        for sym, row in group_obj.items():
            if sym in ("TOTAL_SUMMARY", "TOTAL", "SUMMARY"):
                continue
            if not isinstance(row, dict):
                continue
            amount = _num(row.get("amount"))
            fiat = _num(row.get("fiat") or row.get("value_fiat") or row.get("usd") or row.get("value"))
            out.append({
                "symbol": str(sym).upper(),
                "amount": amount or 0.0,
                "value_usd": fiat or 0.0,   # compte supposé USD
                "location": group_name,
            })
    return out

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

# --- Public API --------------------------------------------------------------
async def get_current_balances(source: str = "cointracking_api") -> Dict[str, Any]:
    """
    Préfère getBalance (valeurs par coin) ; fallback sur getGroupedBalance si besoin.
    Ne retourne que des lignes avec value_usd > 0 (inutile d'envoyer des 0 qui seront filtrés).
    """
    # 1) getBalance (par-coin, avec value_fiat)
    try:
        p = _post_api("getBalance", {})
        rows = _extract_rows_from_getBalance(p)
        # certaines intégrations enveloppent dans 'result'
        if not rows and isinstance(p, dict) and isinstance(p.get("result"), dict):
            rows = _extract_rows_from_getBalance(p["result"])
        rows = [r for r in rows if float(r.get("value_usd") or 0.0) > 0.0]
        if rows:
            return {"source_used": "cointracking_api", "items": rows}
    except Exception:
        pass

    # 2) fallback: getGroupedBalance (par exchange/wallet) -> peut renvoyer des '... BALANCE' à 0
    try:
        p = _post_api("getGroupedBalance", {"group": "exchange"})
        rows = _extract_rows_from_groupedBalance(p)
        # nettoie les placeholders & garde uniquement les valeurs > 0
        cleaned = []
        for r in rows:
            sym = str(r.get("symbol") or "").upper()
            v = float(r.get("value_usd") or 0.0)
            if v <= 0:
                continue
            if sym.endswith(" BALANCE"):
                continue
            cleaned.append(r)
        if cleaned:
            return {"source_used": "cointracking_api", "items": cleaned}
    except Exception:
        pass

    # 3) fallback très permissif
    try:
        rows = _extract_rows_generic(p) if 'p' in locals() else []
        rows = [r for r in rows if float(r.get("value_usd") or 0.0) > 0.0]
        if rows:
            return {"source_used": "cointracking_api", "items": rows}
    except Exception:
        pass

    return {"source_used": "cointracking_api", "items": []}

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
            payload = _post_api(method, params)
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
        except Exception as e:
            entry["error"] = str(e)
        out["tries"].append(entry)

    return out
