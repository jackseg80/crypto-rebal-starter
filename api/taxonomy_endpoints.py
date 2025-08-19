# api/taxonomy_endpoints.py
from __future__ import annotations
import os, json
from typing import Dict, Any
from fastapi import APIRouter, Body, HTTPException, Query
try:
    import taxonomy  # DEFAULT_GROUPS, GROUP_ALIASES (mapping par défaut .py)
except Exception:
    # Fallback si pas dispo (évite crash)
    class _T:
        DEFAULT_GROUPS = ["BTC", "ETH", "Stablecoins", "SOL", "L1/L0 majors", "Others"]
        GROUP_ALIASES: Dict[str, str] = {}
    taxonomy = _T()

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])

DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)
ALIASES_JSON = os.path.join(DATA_DIR, os.getenv("TAXONOMY_ALIASES_JSON", "taxonomy_aliases.json"))

# Mémoire process (vivant pendant le run)
_MEM_ALIASES: Dict[str, str] = {}

def _load_disk_aliases() -> Dict[str, str]:
    if not os.path.exists(ALIASES_JSON):
        return {}
    try:
        with open(ALIASES_JSON, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
            if isinstance(data, dict):
                return {str(k).upper(): str(v) for k,v in data.items()}
    except Exception:
        pass
    return {}

def _save_disk_aliases(aliases: Dict[str, str]) -> None:
    tmp = {k.upper(): v for k, v in aliases.items()}
    with open(ALIASES_JSON, "w", encoding="utf-8") as f:
        json.dump(tmp, f, ensure_ascii=False, indent=2)

def _all_groups() -> list[str]:
    # source autoritaire = taxonomy.DEFAULT_GROUPS si dispo
    try:
        return list(taxonomy.DEFAULT_GROUPS)
    except Exception:
        return ["BTC","ETH","Stablecoins","SOL","L1/L0 majors","Others"]

def _base_aliases() -> Dict[str, str]:
    try:
        return {str(k).upper(): str(v) for k, v in getattr(taxonomy, "GROUP_ALIASES", {}).items()}
    except Exception:
        return {}

def _merged_aliases() -> Dict[str, str]:
    # ordre de priorité: overrides mémoire -> JSON -> taxonomy.py (défaut)
    out: Dict[str, str] = {}
    out.update(_base_aliases())
    disk = _load_disk_aliases()
    out.update(disk)
    out.update(_MEM_ALIASES)
    return out

@router.get("")
def get_taxonomy() -> Dict[str, Any]:
    """Retourne les groupes et le mapping alias->groupe (merge défaut + disque + mémoire)."""
    return {
        "groups": _all_groups(),
        "aliases": _merged_aliases(),
        "storage": {
            "file": ALIASES_JSON,
            "in_memory_count": len(_MEM_ALIASES),
        },
    }

@router.post("/aliases")
def upsert_aliases(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Upsert d'aliases (bulk ou unitaire).
    Body attendu: { "aliases": { "LINK": "Others", "AAVE": "Others", ... } }
    """
    aliases = payload.get("aliases") or {}
    if not isinstance(aliases, dict) or not aliases:
        raise HTTPException(status_code=400, detail="Body attendu: { aliases: { ALIAS: GROUP, ... } }")

    groups = set(_all_groups())
    cur = _merged_aliases()

    written = []
    for raw_alias, raw_group in aliases.items():
        if not raw_alias:
            continue
        alias = str(raw_alias).upper().strip()
        group = str(raw_group).strip()
        if group not in groups:
            raise HTTPException(status_code=400, detail=f"Groupe inconnu: {group}")
        cur[alias] = group
        _MEM_ALIASES[alias] = group
        written.append(alias)

    # persist sur disque (JSON)
    _save_disk_aliases({k: cur[k] for k in sorted(cur)})

    return {"ok": True, "written": len(written), "aliases": written}

@router.delete("/aliases/{alias}")
def delete_alias(alias: str) -> Dict[str, Any]:
    if not alias:
        raise HTTPException(status_code=400, detail="Alias manquant")
    alias = alias.upper()
    cur = _merged_aliases()
    if alias not in cur:
        raise HTTPException(status_code=404, detail="Alias introuvable")

    # Supprime en mémoire + disque
    if alias in _MEM_ALIASES:
        _MEM_ALIASES.pop(alias, None)

    cur.pop(alias, None)
    _save_disk_aliases({k: cur[k] for k in sorted(cur)})
    return {"ok": True, "deleted": alias}

# alias bulk explicite (compat)
@router.post("/aliases/bulk")
def bulk_aliases(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    return upsert_aliases(payload)
