# api/taxonomy_endpoints.py
from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter, Body, Query

from api.taxonomy import Taxonomy
from connectors.cointracking import get_current_balances

router = APIRouter()

@router.get("")
async def get_taxonomy() -> Dict[str, Any]:
    tx = Taxonomy.load()
    return tx.to_dict()

@router.get("/unknown_aliases")
async def unknown_aliases(
    source: str = Query("cointracking"),
    min_usd: float = Query(100.0, ge=0.0),
) -> Dict[str, Any]:
    res = await get_current_balances(source=source)
    rows = res.get("items", []) if isinstance(res, dict) else (res or [])
    tx = Taxonomy.load()
    items = tx.unknown_aliases_from_rows(rows, min_usd=min_usd)
    return {"count": len(items), "items": items, "min_usd": min_usd}

@router.post("/aliases")
async def upsert_aliases(
    payload: Dict[str, Dict[str, str]] = Body(..., example={
        "aliases": { "TBTC": "BTC", "WSTETH": "ETH" }
    })
) -> Dict[str, Any]:
    """
    Body:
    {
      "aliases": {
        "ALIAS1": "GROUP",
        "ALIAS2": "GROUP"
      }
    }
    """
    tx = Taxonomy.load()
    aliases = (payload or {}).get("aliases") or {}
    for a, g in aliases.items():
        if not a or not g:
            continue
        tx.add_mapping(a, g)
    tx.save()
    return {"ok": True, "aliases": tx.aliases}
