"""
Service pour la gestion robuste des secrets utilisateur avec fallbacks
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class UserSecretsManager:
    """Gestionnaire de secrets avec fallbacks et mode dev"""

    def __init__(self):
        self.config_dir = Path("config")
        self.data_dir = Path("data/users")
        self._cache = {}

    def get_user_secrets(self, user_id: str = "demo") -> Dict[str, Any]:
        """
        Récupère les secrets d'un utilisateur avec fallbacks:
        1. data/users/{user_id}/secrets.json
        2. config/secrets_example.json avec dev_mode
        3. Secrets vides avec dev_mode activé
        """
        if user_id in self._cache:
            return self._cache[user_id]

        # Chemin principal des secrets utilisateur
        user_secrets_path = self.data_dir / user_id / "secrets.json"

        secrets = None

        # 1. Essayer de charger les secrets utilisateur
        if user_secrets_path.exists():
            try:
                with open(user_secrets_path, 'r', encoding='utf-8') as f:
                    secrets = json.load(f)
                    logger.info(f"Secrets loaded for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to load user secrets for {user_id}: {e}")

        # 2. Fallback sur exemple si disponible
        if secrets is None:
            example_path = self.config_dir / "secrets_example.json"
            if example_path.exists():
                try:
                    with open(example_path, 'r', encoding='utf-8') as f:
                        secrets = json.load(f)
                        secrets["dev_mode"]["enabled"] = True
                        logger.info(f"Using example secrets for user {user_id} (dev mode)")
                except Exception as e:
                    logger.warning(f"Failed to load example secrets: {e}")

        # 3. Fallback ultime - secrets vides avec dev mode
        if secrets is None:
            secrets = {
                "dev_mode": {"enabled": True, "mock_data": True},
                "coingecko": {"api_key": "", "pro": False},
                "cointracking": {"api_key": "", "api_secret": ""},
                "binance": {"api_key": "", "api_secret": "", "testnet": True},
                "kraken": {"api_key": "", "api_secret": ""},
                "exchanges": {"default": "binance"}
            }
            logger.warning(f"Using empty secrets for user {user_id} (dev mode fallback)")

        # Cache et retour
        self._cache[user_id] = secrets
        return secrets

    def get_exchange_config(self, user_id: str = "demo", exchange: str = None) -> Dict[str, Any]:
        """Récupère la config d'un exchange spécifique"""
        secrets = self.get_user_secrets(user_id)

        if exchange is None:
            exchange = secrets.get("exchanges", {}).get("default", "binance")

        return secrets.get(exchange, {})

    def is_dev_mode(self, user_id: str = "demo") -> bool:
        """Vérifie si le mode dev est activé"""
        secrets = self.get_user_secrets(user_id)
        return secrets.get("dev_mode", {}).get("enabled", False)

    def clear_cache(self, user_id: str = None):
        """Vide le cache (tout ou un utilisateur spécifique)"""
        if user_id:
            self._cache.pop(user_id, None)
        else:
            self._cache.clear()

# Instance globale
user_secrets_manager = UserSecretsManager()

# Fonctions helper pour compatibilité
def get_user_secrets(user_id: str = "demo") -> Dict[str, Any]:
    """Helper function pour récupérer les secrets d'un utilisateur"""
    return user_secrets_manager.get_user_secrets(user_id)

def is_dev_mode(user_id: str = "demo") -> bool:
    """Helper function pour vérifier le mode dev"""
    return user_secrets_manager.is_dev_mode(user_id)

def get_coingecko_api_key(user_id: str = None) -> str:
    """
    Récupère la clé API CoinGecko pour un utilisateur.

    Args:
        user_id: ID de l'utilisateur. Si None, utilise fallback .env

    Returns:
        Clé API CoinGecko (peut être vide si non configurée)
    """
    # Fallback sur .env si pas de user_id (rétrocompatibilité)
    if user_id is None:
        return os.getenv("COINGECKO_API_KEY", "")

    # Utiliser UserSecretsManager pour récupérer la clé utilisateur
    secrets = user_secrets_manager.get_user_secrets(user_id)
    return secrets.get("coingecko", {}).get("api_key", "")