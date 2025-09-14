"""
Configuration et validation des utilisateurs multi-tenants.
LRU cache pour performances, validation stricte.
"""
from __future__ import annotations
import json
import os
from functools import lru_cache
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Type hints
UserConfig = Dict[str, Any]
UsersDatabase = Dict[str, Any]

@lru_cache(maxsize=1)
def _load_users_config() -> UsersDatabase:
    """Charge la configuration des utilisateurs avec cache LRU."""
    config_path = Path("config/users.json")

    if not config_path.exists():
        logger.warning(f"Users config not found at {config_path}, using fallback")
        return {
            "default": "demo",
            "users": [{"id": "demo", "label": "Démo", "mode": "csv"}]
        }

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            logger.debug(f"Loaded users config: {len(config.get('users', []))} users")
            return config
    except Exception as e:
        logger.error(f"Failed to load users config: {e}")
        return {
            "default": "demo",
            "users": [{"id": "demo", "label": "Démo", "mode": "csv"}]
        }

def get_default_user() -> str:
    """Retourne l'utilisateur par défaut."""
    config = _load_users_config()
    return config.get("default", "demo")

def get_all_users() -> List[UserConfig]:
    """Retourne la liste de tous les utilisateurs configurés."""
    config = _load_users_config()
    return config.get("users", [])

def is_allowed_user(user_id: str) -> bool:
    """Vérifie si un utilisateur est autorisé."""
    if not user_id or not isinstance(user_id, str):
        return False

    users = get_all_users()
    allowed_ids = {user.get("id") for user in users}
    return user_id in allowed_ids

def get_user_info(user_id: str) -> Optional[UserConfig]:
    """Retourne les informations d'un utilisateur ou None si non trouvé."""
    if not is_allowed_user(user_id):
        return None

    users = get_all_users()
    for user in users:
        if user.get("id") == user_id:
            return user

    return None

def get_user_mode(user_id: str) -> str:
    """Retourne le mode de l'utilisateur (csv/api) ou 'csv' par défaut."""
    user_info = get_user_info(user_id)
    return user_info.get("mode", "csv") if user_info else "csv"

def clear_users_cache() -> None:
    """Vide le cache des utilisateurs (utile pour les tests)."""
    _load_users_config.cache_clear()
    logger.debug("Users config cache cleared")

# Validation stricte pour sécurité
def validate_user_id(user_id: str) -> str:
    """Valide et normalise un user_id, lève une exception si invalide."""
    if not user_id or not isinstance(user_id, str):
        raise ValueError("User ID must be a non-empty string")

    # Normalisation basique
    normalized = user_id.strip().lower()

    # Validation caractères (alphanumériques + underscores seulement)
    if not normalized.replace('_', '').replace('-', '').isalnum():
        raise ValueError("User ID must contain only alphanumeric characters, hyphens and underscores")

    # Vérification longueur
    if len(normalized) > 50:
        raise ValueError("User ID too long (max 50 characters)")

    return normalized