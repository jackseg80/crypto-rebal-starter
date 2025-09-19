# api/taxonomy_endpoints.py
from __future__ import annotations
import os
import json
from typing import Dict, Any, List, Optional
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

# Cache des unknown aliases du dernier plan généré
_LAST_UNKNOWN_ALIASES: List[str] = []

def update_unknown_aliases_cache(unknown_aliases: List[str]) -> None:
    """Met à jour le cache des unknown aliases pour les suggestions automatiques."""
    global _LAST_UNKNOWN_ALIASES
    _LAST_UNKNOWN_ALIASES = list(unknown_aliases) if unknown_aliases else []

def get_cached_unknown_aliases() -> List[str]:
    """Récupère les unknown aliases du cache."""
    return list(_LAST_UNKNOWN_ALIASES)

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
    # source autoritaire = services.taxonomy.DEFAULT_GROUPS_ORDER
    try:
        from services.taxonomy import DEFAULT_GROUPS_ORDER
        return list(DEFAULT_GROUPS_ORDER)
    except Exception:
        # Fallback avec tous les nouveaux groupes
        return ["BTC","ETH","Stablecoins","SOL","L1/L0 majors","L2/Scaling","DeFi","AI/Data","Gaming/NFT","Memecoins","Others"]

def _base_aliases() -> Dict[str, str]:
    try:
        from services.taxonomy import DEFAULT_ALIASES
        return {str(k).upper(): str(v) for k, v in DEFAULT_ALIASES.items()}
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

@router.get("/suggestions")
def get_auto_classification_suggestions_get(sample_symbols: str = Query("", description="Symboles séparés par virgule pour test")) -> Dict[str, Any]:
    """
    Retourne des suggestions de classification automatique pour les symboles inconnus (GET).
    Si sample_symbols est fourni, les utilise comme exemples.
    Sinon utilise les unknown aliases du dernier plan généré.
    """
    return _get_suggestions_logic(sample_symbols)

@router.post("/suggestions") 
def get_auto_classification_suggestions_post(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """
    Retourne des suggestions de classification automatique pour les symboles inconnus (POST).
    Body peut contenir: {"sample_symbols": "DOGE,PEPE,ARBUSDT"} pour tester.
    """
    sample_symbols = payload.get("sample_symbols", "")
    return _get_suggestions_logic(sample_symbols)

def _get_suggestions_logic(sample_symbols: str) -> Dict[str, Any]:
    """Logique commune pour les suggestions de classification."""
    from services.taxonomy import get_classification_suggestions
    
    if sample_symbols:
        # Mode test avec symboles fournis
        unknown_aliases = [s.strip().upper() for s in sample_symbols.split(",") if s.strip()]
        source = "sample_symbols"
    else:
        # Récupérer les unknown aliases du cache du dernier plan
        unknown_aliases = get_cached_unknown_aliases()
        source = "last_plan_cache"
    
    suggestions = get_classification_suggestions(unknown_aliases)
    
    return {
        "suggestions": suggestions,
        "auto_classified_count": len(suggestions),
        "unknown_count": len(unknown_aliases),
        "coverage": len(suggestions) / len(unknown_aliases) if unknown_aliases else 0,
        "source": source,
        "cached_unknowns": unknown_aliases,
        "note": "Générez un plan de rebalancement pour mettre à jour les unknown aliases" if not sample_symbols and not unknown_aliases else None
    }

@router.post("/auto-classify")
def auto_classify_unknowns(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """
    Applique automatiquement la classification suggérée aux symboles inconnus.
    Body peut contenir: {"sample_symbols": "DOGE,PEPE,ARBUSDT"} pour tester.
    Sinon utilise les unknown aliases du dernier plan généré.
    """
    from services.taxonomy import get_classification_suggestions
    
    sample_symbols = payload.get("sample_symbols", "")
    
    if sample_symbols:
        # Mode test avec symboles fournis
        unknown_aliases = [s.strip().upper() for s in sample_symbols.split(",") if s.strip()]
        source = "sample_symbols"
    else:
        # Récupérer les unknown aliases du cache du dernier plan
        unknown_aliases = get_cached_unknown_aliases()
        source = "last_plan_cache"
        
        if not unknown_aliases:
            return {"ok": False, "message": "Aucun unknown alias trouvé. Générez d'abord un plan de rebalancement ou utilisez le paramètre sample_symbols pour tester", "classified": 0}
    
    if not unknown_aliases:
        return {"ok": True, "message": "Aucun alias inconnu à classifier", "classified": 0}
    
    # Générer suggestions
    suggestions = get_classification_suggestions(unknown_aliases)
    
    if not suggestions:
        return {"ok": True, "message": f"Aucune suggestion automatique trouvée pour les {len(unknown_aliases)} aliases: {', '.join(unknown_aliases[:5])}", "classified": 0}
    
    # Appliquer les suggestions via l'endpoint existant
    result = upsert_aliases({"aliases": suggestions})
    
    return {
        "ok": True, 
        "message": f"{len(suggestions)} aliases classifiés automatiquement",
        "classified": len(suggestions),
        "suggestions_applied": suggestions,
        "source": source,
        "upsert_result": result
    }

# Nouveaux endpoints pour l'enrichissement CoinGecko

@router.post("/suggestions-enhanced")
async def suggestions_enhanced(payload: Dict[str, Any] = Body({})):
    """
    Version améliorée des suggestions avec support CoinGecko
    """
    from services.taxonomy import get_classification_suggestions_enhanced
    
    sample_symbols = payload.get("sample_symbols", "")
    if sample_symbols:
        # Utiliser les symboles fournis pour test
        symbols_list = [s.strip().upper() for s in sample_symbols.split(",") if s.strip()]
        source = "sample_symbols"
    else:
        # Récupérer les unknown aliases du cache du dernier plan
        symbols_list = get_cached_unknown_aliases()
        source = "last_plan_cache"
        
        if not symbols_list:
            return {
                "source": source,
                "unknown_count": 0,
                "auto_classified_count": 0,
                "coverage": 0.0,
                "suggestions": {},
                "note": "Aucun unknown alias trouvé. Générez d'abord un plan de rebalancement ou utilisez sample_symbols pour tester"
            }
    
    if not symbols_list:
        return {
            "source": source,
            "unknown_count": 0,
            "auto_classified_count": 0,
            "coverage": 0.0,
            "suggestions": {}
        }
    
    # Générer suggestions avec CoinGecko
    suggestions = await get_classification_suggestions_enhanced(symbols_list, use_coingecko=True)
    
    return {
        "source": source,
        "unknown_count": len(symbols_list),
        "auto_classified_count": len(suggestions),
        "coverage": len(suggestions) / len(symbols_list) if symbols_list else 0.0,
        "suggestions": suggestions,
        "enhanced": True,
        "coingecko_enabled": True
    }

@router.post("/auto-classify-enhanced")
async def auto_classify_enhanced(payload: Dict[str, Any] = Body({})):
    """
    Version améliorée de l'auto-classification avec support CoinGecko
    """
    from services.taxonomy import get_classification_suggestions_enhanced
    
    sample_symbols = payload.get("sample_symbols", "")
    if sample_symbols:
        # Utiliser les symboles fournis pour test
        unknown_aliases = [s.strip().upper() for s in sample_symbols.split(",") if s.strip()]
        source = "sample_symbols"
    else:
        # Récupérer les unknown aliases du cache du dernier plan
        unknown_aliases = get_cached_unknown_aliases()
        source = "last_plan_cache"
        
        if not unknown_aliases:
            return {"ok": False, "message": "Aucun unknown alias trouvé. Générez d'abord un plan de rebalancement ou utilisez le paramètre sample_symbols pour tester", "classified": 0}
    
    if not unknown_aliases:
        return {"ok": True, "message": "Aucun alias inconnu à classifier", "classified": 0}
    
    # Générer suggestions avec CoinGecko
    suggestions = await get_classification_suggestions_enhanced(unknown_aliases, use_coingecko=True)
    
    if not suggestions:
        return {"ok": True, "message": f"Aucune suggestion automatique trouvée pour les {len(unknown_aliases)} aliases: {', '.join(unknown_aliases[:5])}", "classified": 0}
    
    # Appliquer les suggestions via l'endpoint existant
    result = upsert_aliases({"aliases": suggestions})
    
    return {
        "ok": True, 
        "message": f"{len(suggestions)} aliases classifiés automatiquement (avec CoinGecko)",
        "classified": len(suggestions),
        "suggestions_applied": suggestions,
        "source": source,
        "enhanced": True,
        "coingecko_enabled": True,
        "upsert_result": result
    }

@router.get("/coingecko-stats")
async def coingecko_stats():
    """
    Statistiques sur le service CoinGecko
    """
    try:
        from services.coingecko import coingecko_service
        stats = await coingecko_service.get_enrichment_stats()
        return {"ok": True, "stats": stats}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/enrich-from-coingecko")
async def enrich_from_coingecko(payload: Dict[str, Any] = Body({})):
    """
    Enrichit directement des symboles via CoinGecko sans les patterns regex
    """
    sample_symbols = payload.get("sample_symbols", "")
    if not sample_symbols:
        return {"ok": False, "message": "Le paramètre sample_symbols est requis"}
    
    symbols_list = [s.strip().upper() for s in sample_symbols.split(",") if s.strip()]
    
    if not symbols_list:
        return {"ok": False, "message": "Aucun symbole fourni"}
    
    try:
        from services.coingecko import coingecko_service
        results = await coingecko_service.classify_symbols_batch(symbols_list)
        
        # Filtrer les résultats non-null
        classifications = {k: v for k, v in results.items() if v is not None}
        
        return {
            "ok": True,
            "message": f"{len(classifications)} symboles classifiés via CoinGecko sur {len(symbols_list)} demandés",
            "total_requested": len(symbols_list),
            "coingecko_classified": len(classifications),
            "coverage": len(classifications) / len(symbols_list) if symbols_list else 0.0,
            "classifications": classifications,
            "unclassified": [k for k, v in results.items() if v is None]
        }
        
    except Exception as e:
        return {"ok": False, "error": str(e), "message": "Erreur lors de l'enrichissement CoinGecko"}

@router.get("/test-coingecko-api")
async def test_coingecko_api(api_key: str = None):
    """
    Test direct de l'API CoinGecko avec une clé fournie.
    Usage: GET /taxonomy/test-coingecko-api?api_key=YOUR_KEY
    """
    if not api_key:
        return {"ok": False, "error": "API key required as query parameter"}

    import aiohttp
    import asyncio

    # Test direct de l'API CoinGecko
    url = "https://api.coingecko.com/api/v3/ping"
    headers = {
        'accept': 'application/json',
        'User-Agent': 'crypto-rebal-starter/1.0'
    }
    params = {'x_cg_demo_api_key': api_key}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "ok": True,
                        "status": response.status,
                        "response": data,
                        "message": "API CoinGecko accessible avec cette clé"
                    }
                elif response.status == 401:
                    return {
                        "ok": False,
                        "status": response.status,
                        "error": "Unauthorized - clé API invalide",
                        "message": "La clé API CoinGecko est invalide ou expirée"
                    }
                elif response.status == 429:
                    return {
                        "ok": False,
                        "status": response.status,
                        "error": "Rate limited",
                        "message": "Limite de taux API atteinte - essayez plus tard"
                    }
                else:
                    error_text = await response.text()
                    return {
                        "ok": False,
                        "status": response.status,
                        "error": error_text,
                        "message": f"Erreur API CoinGecko: {response.status}"
                    }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "Erreur de connexion à l'API CoinGecko"
        }
