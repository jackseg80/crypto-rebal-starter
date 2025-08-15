# api/taxonomy_endpoints.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Query, HTTPException

from connectors.cointracking import get_current_balances
from services.taxonomy import Taxonomy

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])

def _to_rows(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalise des lignes balances -> {symbol, alias?, value_usd, location?}
    """
    out: List[Dict[str, Any]] = []
    for r in raw or []:
        symbol = r.get("symbol") or r.get("coin") or r.get("name")
        if not symbol:
            continue
        alias = r.get("alias") or r.get("sym") or r.get("short") or None
        value_usd = r.get("value_usd")
        if value_usd is None:
            # CT renvoie parfois amount + price_fiat
            amount = float(r.get("amount") or r.get("qty") or 0.0)
            price = float(r.get("price_usd") or r.get("price_fiat") or 0.0)
            value_usd = amount * price if (amount and price) else float(r.get("value_fiat") or 0.0)
        out.append({
            "symbol": str(symbol).strip(),
            "alias": (str(alias).strip() if alias else None),
            "value_usd": float(value_usd or 0.0),
            "location": r.get("location") or r.get("exchange") or None,
        })
    return out

@router.get("/unknown_aliases")
async def taxonomy_unknown_aliases(
    source: str = Query("cointracking_api"),
    min_usd: float = Query(1.0, alias="min_usd"),
) -> Dict[str, Any]:
    """
    Liste des alias/symbols inconnus (non mappés dans la Taxonomy) avec filtre min_usd.
    """
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

    unknown_aliases = [k for k, _ in sorted(agg.items(), key=lambda kv: -kv[1])]
    return {"unknown_aliases": unknown_aliases}

@router.post("/aliases")
async def taxonomy_upsert_aliases(
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """
    Ajoute/maj des mappings d'alias vers groupe.
    Accepte:
      - { "aliases": { "LINK":"Others", "AAVE":"Others" } }
      - { "LINK":"Others", "AAVE":"Others" }
    """
    mapping = payload.get("aliases") if isinstance(payload, dict) else None
    if not isinstance(mapping, dict):
        if isinstance(payload, dict):
            # format clé->groupe direct
            mapping = payload
    if not isinstance(mapping, dict) or not mapping:
        raise HTTPException(400, "Payload invalide. Attendu {'aliases': {...}} ou {...}.")

    tx = Taxonomy.load()
    added = 0
    for alias, group in mapping.items():
        a = str(alias).strip()
        g = str(group).strip()
        if not a or not g:
            continue
        tx.aliases[a] = g
        added += 1
    Taxonomy.save(tx)

    return {"ok": True, "added": added, "size": len(tx.aliases)}
