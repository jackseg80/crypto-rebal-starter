"""
Debug Router - Development Endpoints
Extracted from api/main.py for better organization
"""
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import Response

from api.models import APIKeysRequest
from api.deps import get_active_user

# Import debug flag and paths from config
from config import get_settings
settings = get_settings()
DEBUG = settings.is_debug_enabled()

# Directory paths (from main.py)
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/paths")
async def debug_paths():
    """Endpoint de diagnostic pour vérifier les chemins"""
    if not DEBUG:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")

    csv_file = DATA_DIR / "raw" / "CoinTracking - Current Balance.csv"
    return {
        "BASE_DIR": str(BASE_DIR),
        "STATIC_DIR": str(STATIC_DIR),
        "DATA_DIR": str(DATA_DIR),
        "static_exists": STATIC_DIR.exists(),
        "data_exists": DATA_DIR.exists(),
        "csv_file": str(csv_file),
        "csv_exists": csv_file.exists(),
        "csv_size": csv_file.stat().st_size if csv_file.exists() else 0
    }


@router.get("/exchanges-snapshot")
async def debug_exchanges_snapshot(source: str = Query("cointracking_api")):
    """DEBUG: introspection rapide de la répartition par exchange (cointracking_api)"""
    if not DEBUG:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")

    from connectors.cointracking import get_unified_balances_by_exchange
    data = await get_unified_balances_by_exchange(source=source)
    return {
        "has_exchanges": bool(data.get("exchanges")),
        "exchanges_count": len(data.get("exchanges") or []),
        "sample_exchanges": [e.get("location") for e in (data.get("exchanges") or [])[:5]],
        "has_holdings": bool(data.get("detailed_holdings")),
        "holdings_keys": list((data.get("detailed_holdings") or {}).keys())[:5]
    }


@router.get("/ctapi")
async def debug_ctapi():
    """Endpoint de debug pour CoinTracking API"""
    if not DEBUG:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")

    # Import dynamique pour éviter crash au démarrage si module manquant
    try:
        from connectors import cointracking_api as ct_api
    except ImportError:
        try:
            import cointracking_api as ct_api
        except ImportError:
            ct_api = None

    if ct_api is None:
        raise HTTPException(status_code=503, detail="cointracking_api module not available")

    try:
        return ct_api._debug_probe()
    except Exception as e:
        # Encapsuler proprement les erreurs pour le frontend de test
        return {
            "ok": False,
            "error": str(e),
            "env": {
                "has_key": bool(
                    os.getenv("COINTRACKING_API_KEY") or
                    os.getenv("CT_API_KEY") or
                    os.getenv("API_COINTRACKING_API_KEY")
                ),
                "has_secret": bool(
                    os.getenv("COINTRACKING_API_SECRET") or
                    os.getenv("CT_API_SECRET") or
                    os.getenv("API_COINTRACKING_API_SECRET")
                ),
            }
        }


@router.get("/api-keys")
async def debug_api_keys(debug_token: Optional[str] = Query(None), user_id: str = Query("demo")):
    """
    Expose les clés API pour auto-configuration (DEBUG ONLY).

    SECURITY WARNING: Cet endpoint est désactivé en production (DEBUG=False).
    Les clés API doivent être stockées dans data/users/{user_id}/secrets.json.
    """
    if not DEBUG:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")

    # Simple protection pour développement
    expected_token = os.getenv("DEBUG_TOKEN")
    if not expected_token or debug_token != expected_token:
        raise HTTPException(status_code=403, detail="Debug token required")

    # Lire depuis secrets.json (recommandé) avec fallback .env
    from services.user_secrets import get_coingecko_api_key

    cg_key = get_coingecko_api_key(user_id) or os.getenv("COINGECKO_API_KEY", "")

    return {
        "coingecko_api_key": cg_key[:8] + "..." if cg_key else "",
        "cointracking_api_key": os.getenv("COINTRACKING_API_KEY", "")[:8] + "...",
        "cointracking_api_secret": "***masked***",
        "fred_api_key": os.getenv("FRED_API_KEY", "")[:8] + "...",
        "_note": "CoinGecko key loaded from secrets.json (user: {})".format(user_id)
    }


@router.post("/api-keys")
async def update_api_keys(payload: APIKeysRequest, debug_token: Optional[str] = Query(None)):
    """Met à jour les clés API dans le fichier .env (sécurisé)"""
    if not DEBUG:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")

    # Simple protection pour développement
    expected_token = os.getenv("DEBUG_TOKEN")
    if not expected_token or debug_token != expected_token:
        raise HTTPException(status_code=403, detail="Debug token required")

    env_file = Path(".env")
    if not env_file.exists():
        # Créer le fichier .env s'il n'existe pas
        env_file.write_text("# Clés API générées automatiquement\n")

    content = env_file.read_text()

    # Définir les mappings clé -> nom dans .env
    key_mappings = {
        "coingecko_api_key": "COINGECKO_API_KEY",
        "cointracking_api_key": "COINTRACKING_API_KEY",
        "cointracking_api_secret": "COINTRACKING_API_SECRET",
        "fred_api_key": "FRED_API_KEY"
    }

    updated = False
    payload_dict = payload.model_dump(exclude_none=True)  # Convertir le modèle Pydantic en dict
    for field_key, env_key in key_mappings.items():
        if field_key in payload_dict and payload_dict[field_key]:
            # Chercher si la clé existe déjà
            pattern = rf"^{env_key}=.*$"
            new_line = f"{env_key}={payload_dict[field_key]}"

            if re.search(pattern, content, re.MULTILINE):
                # Remplacer la ligne existante
                content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
            else:
                # Ajouter la nouvelle clé
                content += f"\n{new_line}"
            updated = True

    if updated:
        env_file.write_text(content)
        # Recharger les variables d'environnement dans le process courant
        for field_key, env_key in key_mappings.items():
            val = payload_dict.get(field_key)
            if val:
                os.environ[env_key] = val

    return {"success": True, "updated": updated}
