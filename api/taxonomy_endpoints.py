from fastapi import APIRouter, Body, Query
from typing import Any, Dict, List
from services.taxonomy import Taxonomy
from connectors.cointracking import get_current_balances
from services.rebalance import plan_rebalance

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])

def _to_rows(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalise les lignes renvoyées par connecteurs (CoinTracking) vers :
    { symbol: str, alias: Optional[str], value_usd: float, location: Optional[str] }
    """
    out: List[Dict[str, Any]] = []
    for r in raw or []:
        symbol = r.get("symbol") or r.get("coin") or r.get("name")
        if not symbol:
            continue

        # valeur en USD (différents noms possibles selon la source)
        v = (
            r.get("value_usd", None)
            if isinstance(r, dict)
            else None
        )
        if v is None:
            v = r.get("usd_value")
        if v is None:
            v = r.get("usd")
        if v is None:
            v = r.get("value")

        try:
            value_usd = float(v)
        except (TypeError, ValueError):
            value_usd = 0.0

        out.append({
            "symbol": str(symbol),
            "alias": r.get("alias") or None,   # l'alias sera (re)calculé côté Taxonomy si absent
            "value_usd": value_usd,
            "location": r.get("location"),
        })
    return out

@router.get("")
async def get_taxonomy():
    tx = Taxonomy.load()
    return {"groups_order": tx.groups_order, "aliases": tx.aliases}

@router.post("/aliases")
async def add_aliases(payload: Dict[str, Any] = Body(...)):
    tx = Taxonomy.load()
    aliases = (payload or {}).get("aliases", {})
    if not isinstance(aliases, dict):
        return {"ok": False, "error": "payload.aliases must be a dict"}
    tx.aliases.update({str(k).upper(): str(v) for k, v in aliases.items()})
    tx.save()
    return {"ok": True, "aliases": tx.aliases}

@router.get("/unknown_aliases")
async def unknown_aliases(source: str = Query("cointracking"), min_usd: float = Query(100.0)):
    res = await get_current_balances(source=source)
    raw = res.get("items", []) if isinstance(res, dict) else (res or [])
    rows = _to_rows(raw)
    tx = Taxonomy.load()
    known = set(tx.aliases.keys())

    agg: Dict[str, float] = {}
    for r in rows:
        v = float(r.get("value_usd") or 0.0)
        if v < min_usd: 
            continue
        a = r.get("alias") or r.get("symbol")
        if not a or a in known:
            continue
        agg[a] = agg.get(a, 0.0) + v
    return [{"alias": k, "total_usd": round(v, 2)} for k, v in sorted(agg.items(), key=lambda kv: -kv[1])]
