"""
Dépendances FastAPI réutilisables.
Gestion des utilisateurs avec header X-User.
"""
from __future__ import annotations
from typing import Optional
from fastapi import Header, HTTPException, status
import logging

from api.config.users import (
    get_default_user,
    is_allowed_user,
    validate_user_id,
    get_user_info
)

logger = logging.getLogger(__name__)

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

        # Vérification autorisation
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