"""
Dépendances FastAPI réutilisables.
Gestion des utilisateurs avec header X-User.
Redis client pour caching et persistence.
Common dependency factories for endpoints.
"""
from __future__ import annotations
from typing import Optional, Tuple
from fastapi import Header, HTTPException, status, Query
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


# ============================================================================
# Common Dependency Factories
# ============================================================================

def get_user_and_source(
    user: str = Header(None, alias="X-User"),
    source: str = Query("auto", description="Data source (auto, cointracking, saxobank)")
) -> Tuple[str, str]:
    """
    Dependency factory for endpoints that need both user_id and source.

    This consolidates the common pattern of extracting user from header
    and source from query parameters.

    Args:
        user: User ID from X-User header (optional, defaults to 'demo')
        source: Data source from query parameter (default: 'auto')

    Returns:
        Tuple[str, str]: (user_id, source)

    Usage:
        from api.deps import get_user_and_source
        from fastapi import Depends

        @app.get("/endpoint")
        async def endpoint(
            user_source: Tuple[str, str] = Depends(get_user_and_source)
        ):
            user_id, source = user_source
            # ... use user_id and source

        # Or with unpacking (Python 3.10+)
        @app.get("/endpoint")
        async def endpoint(
            user_id: str = Depends(lambda x=Depends(get_user_and_source): x[0]),
            source: str = Depends(lambda x=Depends(get_user_and_source): x[1])
        ):
            # ... use user_id and source

        # Or simplest (extract from dict):
        @app.get("/endpoint")
        async def endpoint(params: dict = Depends(get_user_and_source_dict)):
            user_id = params["user_id"]
            source = params["source"]
    """
    # Use get_active_user logic for user extraction
    if not user:
        user_id = get_default_user()
        logger.debug(f"No X-User header, using default: {user_id}")
    else:
        try:
            user_id = validate_user_id(user)

            # Dev mode bypass
            dev_mode = os.getenv("DEV_OPEN_API", "0") == "1"
            if dev_mode:
                logger.info(f"DEV MODE: Bypassing authorization for user: {user_id}")
            elif not is_allowed_user(user_id):
                logger.warning(f"Unknown user attempted access: {user}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Unknown user: {user}"
                )

            logger.info(f"Active user: {user_id}")

        except ValueError as e:
            logger.warning(f"Invalid user ID format: {user} - {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid user ID format: {e}"
            )

    return user_id, source


def get_user_and_source_dict(
    user_source: Tuple[str, str] = None
) -> dict:
    """
    Alternative dependency that returns user and source as a dict.

    This is a convenience wrapper around get_user_and_source that returns
    a dict instead of a tuple for easier unpacking.

    Returns:
        dict: {"user_id": str, "source": str}

    Usage:
        @app.get("/endpoint")
        async def endpoint(params: dict = Depends(get_user_and_source_dict)):
            user_id = params["user_id"]
            source = params["source"]
    """
    if user_source is None:
        # This should not happen if used as a dependency
        user_id, source = get_default_user(), "auto"
    else:
        user_id, source = user_source

    return {"user_id": user_id, "source": source}