"""
Dev Guards - Protection des endpoints de développement et debug

Ce module fournit des dépendances FastAPI pour protéger automatiquement
les endpoints qui ne doivent être accessibles qu'en développement.

Usage:
    from api.dependencies.dev_guards import require_dev_mode, dev_only

    @router.get("/debug/info", dependencies=[Depends(require_dev_mode)])
    async def debug_info():
        return {"info": "Debug data"}
"""

from fastapi import HTTPException, status
from typing import Callable
import os
import logging

from config.settings import get_settings

log = logging.getLogger(__name__)

def require_dev_mode() -> None:
    """
    Dépendance FastAPI qui bloque l'accès si pas en mode développement.

    Raises:
        HTTPException: 403 Forbidden si environment != 'development'

    Example:
        @router.get("/cache/clear", dependencies=[Depends(require_dev_mode)])
        async def clear_cache():
            ...
    """
    settings = get_settings()

    if settings.environment != "development":
        log.warning(
            f"Access denied to dev-only endpoint from {settings.environment} environment"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "endpoint_disabled_in_production",
                "message": "This endpoint is only available in development mode",
                "environment": settings.environment
            }
        )

def require_debug_enabled() -> None:
    """
    Dépendance FastAPI qui bloque l'accès si DEBUG != true.

    Plus strict que require_dev_mode : vérifie explicitement le flag DEBUG.

    Raises:
        HTTPException: 403 Forbidden si DEBUG=false

    Example:
        @router.post("/test/simulate", dependencies=[Depends(require_debug_enabled)])
        async def simulate_event():
            ...
    """
    settings = get_settings()

    if not settings.debug:
        log.warning(
            "Access denied to debug endpoint - DEBUG flag is disabled"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "debug_disabled",
                "message": "This endpoint requires DEBUG=true",
                "hint": "Enable DEBUG in .env or use development environment"
            }
        )

def require_flag(flag_name: str, env_var: str = None) -> Callable:
    """
    Génère une dépendance qui vérifie une variable d'environnement spécifique.

    Args:
        flag_name: Nom descriptif du flag (pour messages d'erreur)
        env_var: Nom de la variable d'environnement à vérifier

    Returns:
        Fonction de dépendance FastAPI

    Example:
        require_simulation = require_flag("simulation", "DEBUG_SIMULATION")

        @router.post("/simulate", dependencies=[Depends(require_simulation)])
        async def simulate():
            ...
    """
    def dependency() -> None:
        value = os.getenv(env_var or flag_name.upper(), "false").lower()

        if value not in ["true", "1", "yes"]:
            log.warning(
                f"Access denied: {flag_name} flag is disabled ({env_var}={value})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": f"{flag_name}_disabled",
                    "message": f"This endpoint requires {env_var or flag_name.upper()}=true",
                    "current_value": value
                }
            )

    return dependency

def dev_only():
    """
    Decorator convenience pour marquer un endpoint comme dev-only.

    Note: Utiliser plutôt dependencies=[Depends(require_dev_mode)] directement
    dans le décorateur de route pour profiter du mécanisme FastAPI standard.

    Cette fonction existe pour compatibilité/clarté dans le code existant.

    Example:
        # Méthode recommandée (FastAPI standard)
        @router.get("/debug", dependencies=[Depends(require_dev_mode)])
        async def debug_endpoint():
            ...

        # Méthode alternative (si besoin de logique custom)
        @dev_only()
        @router.get("/debug")
        async def debug_endpoint():
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            require_dev_mode()  # Check avant d'appeler la fonction
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Dépendances pré-configurées pour cas courants

# Pour endpoints de simulation (bloque TOUJOURS en prod, même avec flag activé)
def _require_simulation_dev_only():
    """
    Dépendance pour endpoints de simulation.
    Bloque en production peu importe le flag (sécurité stricte).
    Vérifie DEBUG_SIMULATION en dev/staging uniquement.
    """
    settings = get_settings()

    # TOUJOURS bloquer en production, même si DEBUG_SIMULATION=true
    if settings.environment == "production":
        log.warning("Simulation endpoint blocked in production environment")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "simulation_disabled_in_production",
                "message": "Simulation endpoints are never allowed in production",
                "environment": "production"
            }
        )

    # En dev/staging, vérifier le flag
    value = os.getenv("DEBUG_SIMULATION", "false").lower()
    if value not in ["true", "1", "yes"]:
        log.warning(f"Simulation endpoint blocked: DEBUG_SIMULATION={value}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "simulation_disabled",
                "message": "This endpoint requires DEBUG_SIMULATION=true",
                "current_value": value
            }
        )

require_simulation = _require_simulation_dev_only

# Pour endpoints de test alerts
require_alerts_test = require_flag("alerts_test", "ENABLE_ALERTS_TEST_ENDPOINTS")

def validate_websocket_token(token: str = None) -> bool:
    """
    Valide un token WebSocket optionnel.

    Args:
        token: Token passé en query parameter (?token=xxx)

    Returns:
        True si le token est valide ou si l'auth est optionnelle,
        False si le token est invalide

    Example:
        @router.websocket("/ws")
        async def websocket_endpoint(
            websocket: WebSocket,
            token: Optional[str] = Query(None)
        ):
            if not validate_websocket_token(token):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            # ... reste du code
    """
    settings = get_settings()

    # En développement, accepter sans token
    if settings.environment == "development":
        return True

    # En production, valider le token si fourni
    if token:
        # TODO: Implémenter validation JWT ou autre mécanisme
        # Pour l'instant, comparer avec un token simple
        expected_token = settings.security.debug_token
        return token == expected_token

    # En production sans token, refuser
    if settings.is_production():
        log.warning("WebSocket connection rejected: no token provided in production")
        return False

    return True

# Export des dépendances communes
__all__ = [
    "require_dev_mode",
    "require_debug_enabled",
    "require_flag",
    "require_simulation",
    "require_alerts_test",
    "dev_only",
    "validate_websocket_token",
]
