"""
Dépendances FastAPI réutilisables.
Gestion des utilisateurs avec header X-User.
Redis client pour caching et persistence.
"""
from __future__ import annotations
from typing import Optional
from fastapi import Header, HTTPException, status
import logging
import os

from api.config.users import (
    get_default_user,
    is_allowed_user,
    validate_user_id,
    get_user_info
)

logger = logging.getLogger(__name__)

# Redis client singleton
_redis_client = None

def get_active_user(x_user: Optional[str] = Header(None)) -> str:
    """
    Dépendance FastAPI pour récupérer l'utilisateur actuel.

    Args:
        x_user: Header X-User optionnel

    Returns:
        str: ID utilisateur validé

    Raises:
        HTTPException: 403 si utilisateur inconnu
    """
    # Fallback vers utilisateur par défaut si pas de header
    if not x_user:
        default_user = get_default_user()
        logger.debug(f"No X-User header, using default: {default_user}")
        return default_user

    try:
        # Validation et normalisation
        normalized_user = validate_user_id(x_user)

        # Mode développement : bypass de l'autorisation si DEV_OPEN_API=1
        dev_mode = os.getenv("DEV_OPEN_API", "0") == "1"
        if dev_mode:
            logger.info(f"DEV MODE: Bypassing authorization for user: {normalized_user}")
            return normalized_user

        # Vérification autorisation normale
        if not is_allowed_user(normalized_user):
            logger.warning(f"Unknown user attempted access: {x_user}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown user: {x_user}"
            )

        # Log pour audit
        logger.info(f"Active user: {normalized_user}")
        return normalized_user

    except ValueError as e:
        logger.warning(f"Invalid user ID format: {x_user} - {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user ID format: {e}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_active_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def get_active_user_info(current_user: str = None) -> dict:
    """
    Récupère les informations complètes de l'utilisateur actuel.

    Args:
        current_user: ID utilisateur (optionnel, utilise get_active_user si None)

    Returns:
        dict: Informations utilisateur
    """
    if current_user is None:
        current_user = get_active_user()

    user_info = get_user_info(current_user)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User info not found: {current_user}"
        )

    return user_info


def get_redis_client() -> Optional[any]:
    """
    Dépendance FastAPI pour obtenir le client Redis.

    Retourne un client Redis singleton partagé entre toutes les requêtes.
    Si Redis n'est pas disponible, retourne None (graceful degradation).

    Returns:
        Redis client ou None si indisponible

    Usage:
        @app.get("/endpoint")
        async def endpoint(redis = Depends(get_redis_client)):
            if redis:
                # Utiliser Redis
                redis.set(key, value)
    """
    global _redis_client

    # Return existing client if available
    if _redis_client is not None:
        try:
            # Test connection
            _redis_client.ping()
            return _redis_client
        except Exception as e:
            logger.warning(f"Redis client lost connection: {e}")
            _redis_client = None

    # Try to create new client
    try:
        from redis import Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = Redis.from_url(redis_url, decode_responses=False)

        # Test connection
        _redis_client.ping()
        logger.info(f"Redis client connected: {redis_url}")
        return _redis_client

    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        return None