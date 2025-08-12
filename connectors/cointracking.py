import os, hmac, hashlib, time, json
from typing import List, Dict, Optional
import httpx
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

CT_KEY = os.getenv("COINTRACKING_KEY")
CT_SECRET = os.getenv("COINTRACKING_SECRET")

# --- Aliases (ajuste librement) ---
ALIASES_SAFE = {
    "SOL2":"SOL", "DOT2":"DOT", "ATOM2":"ATOM", "EGLD3":"EGLD",
    "IMX2":"IMX", "INJ2":"INJ", "UNI2":"UNI", "THETA2":"THETA",
    "SUI3":"SUI", "TIA3":"TIA", "POL3":"POL", "ICP2":"ICP",
    "XNO2":"XNO", "IOTA2":"IOTA", "MIOTA":"IOTA", "BCHABC":"BCH",
}

ALIASES_WRAPPERS = {
    "WBTC":"BTC", "TBTC":"BTC",
    "WETH":"ETH", "STETH":"ETH", "WSTETH":"ETH", "RETH":"ETH",
}

def _canonical(sym: str, alias_mode: str) -> str:
    s = (sym or "").upper()
    if alias_mode in ("safe", "all"):
        if s in ALIASES_SAFE: s = ALIASES_SAFE[s]
    if alias_mode in ("wrappers", "all"):
        if s in ALIASES_WRAPPERS: s = ALIASES_WRAPPERS[s]
    return s

def _normalize_rows(rows: list[dict], *, min_usd: float = 1.0, alias_mode: str = "safe") -> list[dict]:
    """
    Normalise en [{symbol, name, usd_value}] + agrégation + filtre dust.
    alias_mode: "none" | "safe" | "wrappers" | "all"
    """
    if not rows:
        return []

    norm = []
    for r in rows:
        if not isinstance(r, dict):
            continue

        symbol_raw = str(
            r.get("symbol") or r.get("currency") or r.get("coin") or r.get("ticker") or ""
        ).upper()

        symbol = _canonical(symbol_raw, alias_mode)
        name = str(r.get("name") or r.get("currency") or r.get("coin") or symbol)

        raw = (
            r.get("usd_value") or r.get("value_usd") or r.get("valueUSD")
            or r.get("value_fiat") or r.get("balance_usd") or r.get("fiat_value") or 0
        )
        try:
            usd = float(raw)
        except (TypeError, ValueError):
            s = str(raw).replace(",", "") if raw is not None else "0"
            usd = float(s) if s else 0.0

        norm.append({"symbol": symbol, "name": name, "usd_value": usd})

    if not norm:
        return []

    import pandas as pd
    df = pd.DataFrame(norm).groupby("symbol", as_index=False)["usd_value"].sum()
    df["name"] = df["symbol"]
    if min_usd and min_usd > 0:
        df = df[df["usd_value"].abs() >= float(min_usd)]
    df = df.sort_values("usd_value", ascending=False)
    return df.to_dict(orient="records")


async def _ct_call(method: str, params: Optional[Dict] = None) -> Dict:
    if not (CT_KEY and CT_SECRET):
        raise RuntimeError("Clés CoinTracking manquantes dans .env")
    url = "https://cointracking.info/api/v1/"
    nonce = str(int(time.time()*1000))
    payload_dict = {"method": method, "nonce": nonce}
    if params:
        payload_dict["params"] = json.dumps(params, separators=(",",":"))
    payload = "&".join(f"{k}={v}" for k,v in payload_dict.items())
    sign = hmac.new(CT_SECRET.encode(), payload.encode(), hashlib.sha512).hexdigest()
    headers = {"Key": CT_KEY, "Sign": sign, "Content-Type":"application/x-www-form-urlencoded"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, content=payload)
        r.raise_for_status()
        return r.json()

async def get_current_balances(source: str = "stub",
                               csv_current: Optional[str] = None,
                               csv_by_exchange: Optional[str] = None,
                               *,
                               min_usd: float = 1.0,
                               alias_mode: str = "safe") -> List[Dict]:
    """
    Renvoie une liste [{symbol, name, usd_value}] agrégée.
    """
    if source == "stub":
        rows = [
            {"symbol":"BTC","name":"Bitcoin","usd_value":40000},
            {"symbol":"ETH","name":"Ethereum","usd_value":30000},
            {"symbol":"USDT","name":"Tether","usd_value":30000},
        ]
        return _normalize_rows(rows)

    if source == "csv":
        if not csv_current or not os.path.exists(csv_current):
            raise FileNotFoundError("csv_current introuvable")
        df = pd.read_csv(csv_current)
        # Tente de détecter les colonnes
        currency_col = None
        for c in ["Currency","Ticker","Symbol","Coin"]:
            if c in df.columns: currency_col = c; break
        usd_col = None
        for c in ["Balance (USD)","Value in USD","Current value in USD","USD Value"]:
            if c in df.columns: usd_col = c; break
        if not currency_col or not usd_col:
            raise ValueError("Colonnes attendues non trouvées dans le CSV")
        rows = [{"symbol": str(r[currency_col]).upper(), "name": str(r[currency_col]), "usd_value": float(r[usd_col] or 0)} for _,r in df.iterrows()]
        return _normalize_rows(rows)

    if source == "cointracking":
        j = await _ct_call("getBalance")
        rows = None
        res = j.get("result")
        if isinstance(res, dict):
            rows = res.get("balances") or j.get("balances")
        else:
            rows = j.get("balances")

        if isinstance(rows, dict):
            rows = [{"symbol": k, **(v if isinstance(v, dict) else {"usd_value": v})}
                    for k, v in rows.items()]

        if not rows and "details" in j and isinstance(j["details"], dict):
            rows = []
            for sym, v in j["details"].items():
                coin = (v.get("coin") or sym or "").upper()
                val = v.get("value_fiat") or v.get("valueUSD") or v.get("value_usd")
                rows.append({"symbol": coin, "name": coin, "usd_value": val})

        return _normalize_rows(rows or [], min_usd=min_usd, alias_mode=alias_mode)

    raise ValueError(f"Source inconnue: {source}")

async def ct_raw(method: str, params=None):
    return await _ct_call(method, params)

