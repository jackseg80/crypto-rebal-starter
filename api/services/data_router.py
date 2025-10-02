"""
Routeur de données centralisé par utilisateur.
Gère CSV, API et configuration selon le mode utilisateur.
"""
from __future__ import annotations
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

from api.services.user_fs import UserScopedFS
from api.config.users import get_user_info
from api.services.config_migrator import ConfigMigrator, get_staleness_state

logger = logging.getLogger(__name__)

class UserDataRouter:
    """
    Routeur centralisé pour les données utilisateur.
    Gère automatiquement CSV vs API selon la configuration user.
    """

    def __init__(self, project_root: str, user_id: str):
        """
        Args:
            project_root: Racine du projet
            user_id: ID utilisateur validé
        """
        self.project_root = project_root
        self.user_id = user_id
        self.user_fs = UserScopedFS(project_root, user_id)
        self.config_migrator = ConfigMigrator(self.user_fs)

        # Charger les settings utilisateur
        self._load_user_settings()

        logger.debug(f"UserDataRouter for '{user_id}' (data_source: {self.data_source})")

    def _load_user_settings(self):
        """Charge les settings utilisateur depuis config.json"""
        try:
            self.settings = self.user_fs.read_json("config.json")
        except (FileNotFoundError, ValueError):
            # Settings par défaut si pas de fichier
            self.settings = {
                "data_source": "csv",
                "csv_glob": "csv/*.csv",
                "api_base_url": "http://localhost:8000",
                "display_currency": "USD",
                "min_usd_threshold": 1.0
            }
            logger.debug(f"Using default settings for user {self.user_id}")

        # Propriétés d'accès rapide
        self.data_source = self.settings.get("data_source", "csv")
        self.csv_glob = self.settings.get("csv_glob", "csv/*.csv")
        # Fichier CSV sélectionné explicitement (nom de fichier)
        self.selected_csv = self.settings.get("csv_selected_file")
        self.api_credentials = {
            "api_key": self.settings.get("cointracking_api_key", ""),
            "api_secret": self.settings.get("cointracking_api_secret", "")
        }

    def get_csv_files(self, file_type: str = "balance") -> List[str]:
        """
        Retourne les fichiers CSV pour un type donné.
        🎯 SOURCES FIRST: Utilise effective_path si disponible

        Args:
            file_type: Type de fichier ('balance', 'coins', 'exchange')

        Returns:
            List[str]: Liste des fichiers CSV trouvés
        """
        # Si get_effective_source() a déjà déterminé un path effectif, l'utiliser
        if hasattr(self, '_effective_read') and hasattr(self, '_effective_path'):
            if self._effective_read in ("snapshot", "imports", "legacy") and self._effective_path:
                logger.debug(f"📂 Using pre-resolved effective path: {self._effective_path}")
                return [self._effective_path]

        # Sinon, résoudre dynamiquement (fallback pour compatibilité)
        from api.services.sources_resolver import resolve_effective_path

        module_mapping = {
            "balance": "cointracking",
            "coins": "cointracking",
            "exchange": "cointracking"
        }

        module = module_mapping.get(file_type, "cointracking")
        mode, effective_path = resolve_effective_path(self.user_fs, module)

        if mode != "empty" and effective_path:
            return [effective_path]

        logger.warning(f"🚫 Sources resolver: No data for user {self.user_id}, type {file_type}")
        return []

    def get_most_recent_csv(self, file_type: str = "balance") -> Optional[str]:
        """Retourne le fichier CSV à utiliser pour un type.

        Si un fichier a été sélectionné explicitement dans le profil
        (self.selected_csv), il est prioritaire s'il existe.
        Sinon, retourne le plus récent.
        """
        files = self.get_csv_files(file_type)
        if not files:
            return None

        # Priorité au fichier explicitement sélectionné (comparaison par nom)
        if self.selected_csv:
            for f in files:
                if Path(f).name == self.selected_csv:
                    return f

        # Sinon, retourner le plus récent
        return files[0]

    def get_api_profile(self) -> Dict[str, Any]:
        """
        Retourne le profil API de l'utilisateur.

        Returns:
            Dict[str, Any]: Configuration API ou dict vide
        """
        if self.data_source == "cointracking_api":
            return {"profile_name": self.user_id}
        else:
            return {}

    def get_api_credentials(self) -> Dict[str, str]:
        """
        Retourne les credentials API pour l'utilisateur.

        Returns:
            Dict[str, str]: Credentials (key, secret, etc.)
        """
        # Utiliser les credentials directement depuis les settings
        return self.api_credentials

    def should_use_api(self) -> bool:
        """Détermine si l'utilisateur doit utiliser l'API ou CSV."""
        return self.data_source == "cointracking_api"

    def should_use_csv(self) -> bool:
        """Détermine si l'utilisateur doit utiliser CSV."""
        return self.data_source == "csv" or self.data_source == "cointracking"

    def get_data_source_info(self) -> Dict[str, Any]:
        """
        Retourne des informations sur la source de données utilisateur.

        Returns:
            Dict[str, Any]: Informations de debug/monitoring
        """
        info = {
            "user_id": self.user_id,
            "data_source": self.data_source,
            "user_root": self.user_fs.get_user_root(),
            "settings": self.settings
        }

        if self.should_use_csv():
            balance_files = self.get_csv_files("balance")
            info.update({
                "csv_files_count": len(balance_files),
                "most_recent_csv": balance_files[0] if balance_files else None
            })

        if self.should_use_api():
            credentials = self.get_api_credentials()
            info.update({
                "api_profile": self.get_api_profile(),
                "has_credentials": bool(credentials.get("api_key") and credentials.get("api_secret"))
            })

        return info

    def get_effective_source(self) -> str:
        """
        🎯 SOURCES FIRST avec respect de la préférence utilisateur
        Retourne la source effective qui sera utilisée.

        Returns:
            str: 'cointracking', 'cointracking_api', ou 'stub'
        """
        from api.services.sources_resolver import resolve_effective_path

        # 🔥 PRIORITÉ UTILISATEUR: Si API explicitement configuré, respecter ce choix
        if self.data_source == "cointracking_api" and self._cointracking_api_ready():
            self._effective_read = "api"
            self._effective_path = None
            logger.info(f"👤 User preference: API explicitly configured for user {self.user_id}")
            return "cointracking_api"

        # --- Sources snapshots et imports (priorité haute) ---
        mode, path = resolve_effective_path(self.user_fs, "cointracking")
        logger.info(f"🔍 Sources resolver returned: mode={mode}, path={path} for user {self.user_id}")

        if mode in ("snapshot", "imports", "user_choice"):
            # Snapshots, imports et choix utilisateur ont priorité absolue sur tout
            self._effective_read = mode
            self._effective_path = path
            logger.info(f"🎯 Sources First: Using {mode} for user {self.user_id} - {path}")
            return "cointracking"

        # --- Legacy seulement si pas de préférence API ---
        if mode == "legacy" and self.data_source != "cointracking_api":
            self._effective_read = mode
            self._effective_path = path
            logger.info(f"🔙 Sources First: Using legacy for user {self.user_id} - {path}")
            return "cointracking"

        # --- Fallback API si credentials valides ---
        if self._cointracking_api_ready():
            self._effective_read = "api"
            self._effective_path = None
            logger.info(f"📡 Sources First: Fallback to API for user {self.user_id}")
            return "cointracking_api"

        # --- Vide propre ---
        self._effective_read = "empty"
        self._effective_path = None
        logger.warning(f"💔 Sources First: No data available for user {self.user_id}")
        return "stub"

    def _cointracking_api_ready(self) -> bool:
        """Vérifie si l'API CoinTracking est prête pour cet utilisateur"""
        from api.services.config_migrator import resolve_secret_ref

        try:
            # Résout key_ref/secret_ref pour l'user courant
            key = resolve_secret_ref("cointracking_api_key", self.user_fs)
            secret = resolve_secret_ref("cointracking_api_secret", self.user_fs)
            return bool(key and secret)
        except Exception as e:
            logger.debug(f"API credentials check failed for user {self.user_id}: {e}")
            return False
