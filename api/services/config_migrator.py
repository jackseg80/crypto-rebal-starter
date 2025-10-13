"""
Migration et gestion de configuration sources.json unifiée.
Migre depuis l'ancien config.json vers le nouveau format avec références de credentials.
"""
from __future__ import annotations
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from api.services.user_fs import UserScopedFS

logger = logging.getLogger(__name__)

class ConfigMigrator:
    """
    Gestionnaire de migration et chargement de configuration sources.json.
    """

    def __init__(self, user_fs: UserScopedFS):
        self.user_fs = user_fs

    def load_sources_config(self) -> Dict[str, Any]:
        """
        Charge la configuration sources.json, en la créant si nécessaire
        depuis l'ancien config.json ou par auto-détection.

        Returns:
            Dict[str, Any]: Configuration sources complète
        """
        # Essayer de charger sources.json existant
        if self.user_fs.exists("config/sources.json"):
            try:
                config = self.user_fs.read_json("config/sources.json")
                logger.debug(f"Loaded existing sources.json for user {self.user_fs.user_id}")
                return self._validate_and_complete_config(config)
            except Exception as e:
                logger.warning(f"Failed to load sources.json, will recreate: {e}")

        # Créer sources.json depuis config.json ou par défaut
        return self._create_sources_config()

    def save_sources_config(self, config: Dict[str, Any]) -> None:
        """
        Sauvegarde la configuration sources.json.

        Args:
            config: Configuration à sauvegarder
        """
        validated_config = self._validate_and_complete_config(config)
        self.user_fs.write_json("config/sources.json", validated_config)
        logger.info(f"Saved sources.json for user {self.user_fs.user_id}")

    def _create_sources_config(self) -> Dict[str, Any]:
        """
        Crée une nouvelle configuration sources.json depuis l'ancien config.json
        ou par auto-détection de fichiers.
        """
        logger.info(f"Creating new sources.json for user {self.user_fs.user_id}")

        # Essayer de charger l'ancien config.json
        legacy_config = {}
        try:
            legacy_config = self.user_fs.read_json("config.json")
            logger.debug("Found legacy config.json, migrating...")
        except Exception:
            logger.debug("No legacy config.json found, using defaults")

        # Configuration de base
        config = {
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "modules": {}
        }

        # Migrer/créer module CoinTracking
        config["modules"]["cointracking"] = self._create_cointracking_module(legacy_config)

        # Migrer/créer module Saxo
        config["modules"]["saxobank"] = self._create_saxobank_module(legacy_config)

        # Sauvegarder immédiatement
        self.save_sources_config(config)

        return config

    def _create_cointracking_module(self, legacy_config: Dict[str, Any]) -> Dict[str, Any]:
        """Crée la configuration du module CoinTracking"""
        module = {
            "enabled": True,
            "modes": ["data"],
            "patterns": [
                "cointracking/data/*.csv"
            ],
            "snapshot_ttl_hours": 24,
            "warning_threshold_hours": 12,
            "last_import_at": None,
            "notes": "Module CoinTracking avec support CSV et API"
        }

        # Vérifier si API était configurée dans l'ancien config
        if legacy_config.get("cointracking_api_key") and legacy_config.get("cointracking_api_secret"):
            module["modes"].append("api")
            module["api"] = {
                "key_ref": "cointracking_api_key",
                "secret_ref": "cointracking_api_secret"
            }
            logger.debug("Migrated CoinTracking API configuration")

        # Vérifier si data_source était sur API
        if legacy_config.get("data_source") == "cointracking_api":
            if "api" not in module["modes"]:
                module["modes"].append("api")
            module["preferred_mode"] = "api"

        return module

    def _create_saxobank_module(self, legacy_config: Dict[str, Any]) -> Dict[str, Any]:
        """Crée la configuration du module Saxobank"""
        module = {
            "enabled": True,
            "modes": ["data"],
            "patterns": [
                "saxobank/data/*.csv"
            ],
            "snapshot_ttl_hours": 24,
            "warning_threshold_hours": 12,
            "last_import_at": None,
            "notes": "Module Saxo Bank avec support upload CSV"
        }

        return module

    def _validate_and_complete_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valide et complète une configuration sources.json.

        Args:
            config: Configuration à valider

        Returns:
            Dict[str, Any]: Configuration validée et complétée
        """
        # Vérifier version
        if "version" not in config:
            config["version"] = 1

        # Vérifier modules
        if "modules" not in config:
            config["modules"] = {}

        # S'assurer que chaque module a les champs requis
        for module_name, module_config in config["modules"].items():
            self._validate_module_config(module_name, module_config)

        return config

    def _validate_module_config(self, module_name: str, module_config: Dict[str, Any]) -> None:
        """Valide et complète la configuration d'un module"""
        defaults = {
            "enabled": True,
            "modes": ["data"],
            "patterns": [],
            "snapshot_ttl_hours": 24,
            "warning_threshold_hours": 12,
            "last_import_at": None
        }

        # Appliquer les défauts
        for key, default_value in defaults.items():
            if key not in module_config:
                module_config[key] = default_value

        # Valider modes
        valid_modes = ["data", "api"]
        module_config["modes"] = [m for m in module_config["modes"] if m in valid_modes]

        if not module_config["modes"]:
            module_config["modes"] = ["data"]

    def detect_modules_from_files(self) -> Dict[str, Dict[str, Any]]:
        """
        Auto-détecte les modules présents par scan du filesystem utilisateur.

        Returns:
            Dict[str, Dict[str, Any]]: Modules détectés avec leur config de base
        """
        detected = {}

        # Détecter CoinTracking
        if self.user_fs.glob_files("cointracking/data/*.csv"):
            detected["cointracking"] = {
                "enabled": True,
                "modes": ["data"],
                "detected_reason": "Found files in cointracking/data/"
            }

        # Détecter Saxo
        if self.user_fs.glob_files("saxobank/data/*.csv"):
            detected["saxobank"] = {
                "enabled": True,
                "modes": ["data"],
                "detected_reason": "Found files in saxobank/data/"
            }

        logger.debug(f"Auto-detected modules: {list(detected.keys())}")
        return detected


def resolve_secret_ref(ref: str, user_fs: UserScopedFS) -> Optional[str]:
    """
    Résout une référence de secret vers sa valeur réelle.

    Recherche d'abord dans config/config.json de l'utilisateur,
    puis dans les variables d'environnement (fallback).

    Args:
        ref: Référence du secret (ex: "cointracking_api_key")
        user_fs: Filesystem utilisateur

    Returns:
        Optional[str]: Valeur du secret ou None si non trouvé
    """
    # 1. Essayer config.json utilisateur
    try:
        config = user_fs.read_json("config.json")
        value = config.get(ref)
        if value:
            logger.debug(f"Resolved secret ref {ref} from user config")
            return str(value)
    except Exception:
        pass

    # 2. Fallback variables d'environnement
    env_value = os.getenv(ref) or os.getenv(ref.upper())
    if env_value:
        logger.debug(f"Resolved secret ref {ref} from environment")
        return env_value

    logger.warning(f"Could not resolve secret reference: {ref}")
    return None


def get_staleness_state(last_update: Optional[str], ttl_hours: int, warning_hours: int) -> Dict[str, Any]:
    """
    Détermine l'état de fraîcheur d'un snapshot/import.

    Args:
        last_update: Timestamp ISO du dernier update ou None
        ttl_hours: TTL en heures avant staleness
        warning_hours: Seuil warning en heures

    Returns:
        Dict avec state ("fresh"|"warning"|"stale"), age_hours, is_stale
    """
    if not last_update:
        return {
            "state": "stale",
            "age_hours": None,
            "is_stale": True,
            "message": "Aucun import détecté"
        }

    try:
        update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=update_time.tzinfo)
        age_hours = (now - update_time).total_seconds() / 3600

        if age_hours >= ttl_hours:
            state = "stale"
            is_stale = True
        elif age_hours >= warning_hours:
            state = "warning"
            is_stale = False
        else:
            state = "fresh"
            is_stale = False

        return {
            "state": state,
            "age_hours": round(age_hours, 1),
            "is_stale": is_stale,
            "message": f"Mis à jour il y a {round(age_hours, 1)}h"
        }

    except Exception as e:
        logger.error(f"Error parsing timestamp {last_update}: {e}")
        return {
            "state": "stale",
            "age_hours": None,
            "is_stale": True,
            "message": "Erreur de timestamp"
        }