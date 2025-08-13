# api/taxonomy_endpoints.py
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query

from api.taxonomy import Taxonomy, _storage_path
from connectors.cointracking import get_current_balances

router = APIRouter()  # <-- pas de prefix ici

@router.get("/taxonomy")
def get_taxonomy() -> Dict[str, Any]:
    tx = Taxonomy.load()
    return {
        "groups_order": tx.groups_order,
        "aliases": tx.aliases,
        "storage": _storage_path(),
    }

@router.post("/taxonomy/aliases")
def post_aliases(data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Body:
    {
      "aliases": { "WBTC": "BTC", "WSTETH": "ETH", ... }
    }
    """
    if not isinstance(data, dict) or "aliases" not in data:
        raise HTTPException(status_code=400, detail="Body must contain an 'aliases' object.")
    add = data["aliases"]
    if not isinstance(add, dict):
        raise HTTPException(status_code=400, detail="'aliases' must be an object.")

    tx = Taxonomy.load()
    for k, v in add.items():
        k_norm = str(k).upper().strip()
        v_norm = str(v).upper().strip()
        if not k_norm or not v_norm:
            continue
        tx.aliases[k_norm] = v_norm
    tx.save()
    return {"ok": True, "aliases_count": len(tx.aliases)}

@router.get("/taxonomy/unknown_aliases")
async def get_unknown_aliases(
    source: str = Query("cointracking"),
    min_usd: float = Query(100.0),
) -> Dict[str, Any]:
    """
    Liste les symboles non mappés (pas présents dans taxonomy.aliases), avec total >= min_usd.
    """
    tx = Taxonomy.load()
    res = await get_current_balances(source=source)
    rows = res.get("items", []) if isinstance(res, dict) else (res or [])

    totals = defaultdict(float)
    for r in rows:
        sym = str(r.get("symbol", "")).upper()
        usd = float(r.get("usd_value") or r.get("value_usd") or 0.0)
        if sym and sym not in tx.aliases:
            totals[sym] += usd

    items = [{"symbol": s, "total_usd": round(v, 2)}
             for s, v in totals.items() if v >= min_usd]
    items.sort(key=lambda x: x["total_usd"], reverse=True)
    return {"count": len(items), "items": items}
