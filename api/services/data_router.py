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
        Priorité : Sources snapshots → Sources imports → Legacy patterns

        Args:
            file_type: Type de fichier ('balance', 'coins', 'exchange')

        Returns:
            List[str]: Liste des fichiers CSV trouvés
        """
        # 🔥 PATCH 4: Prioriser les snapshots Sources
        # 1. Vérifier snapshot CoinTracking récent
        if file_type == "balance":
            snapshot_path = "cointracking/snapshots/latest.csv"
            if self.user_fs.exists(snapshot_path):
                full_path = self.user_fs.get_path(snapshot_path)
                logger.debug(f"Using Sources snapshot for user {self.user_id}: {snapshot_path}")
                return [full_path]

            # 2. Vérifier imports CoinTracking
            import_files = self.user_fs.glob_files("cointracking/imports/*.csv")
            if import_files:
                # Trier par date de modification (plus récent en premier)
                try:
                    import_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
                except OSError:
                    pass
                logger.debug(f"Using Sources imports for user {self.user_id}: {len(import_files)} files")
                return import_files

        # 3. Fallback sur les patterns legacy (pour compatibilité)
        user_pattern = self.csv_glob
        patterns = {
            "balance": [
                f"{user_pattern}/CoinTracking - Current Balance*.csv",
                f"{user_pattern}/Current Balance*.csv",
                f"{user_pattern}/balance*.csv",
                user_pattern,  # Pattern utilisateur brut
                "*.csv"  # Fallback
            ],
            "coins": [
                f"{user_pattern}/CoinTracking - Coins by Exchange*.csv",
                f"{user_pattern}/Coins by Exchange*.csv",
                f"{user_pattern}/coins*.csv"
            ],
            "exchange": [
                f"{user_pattern}/CoinTracking - Balance by Exchange*.csv",
                f"{user_pattern}/Balance by Exchange*.csv",
                f"{user_pattern}/exchange*.csv"
            ]
        }

        file_patterns = patterns.get(file_type, ["*.csv"])

        # Rechercher le premier pattern qui donne des résultats
        for pattern in file_patterns:
            files = self.user_fs.glob_files(pattern)
            if files:
                # Trier par date de modification (plus récent en premier)
                try:
                    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
                except OSError:
                    pass
                logger.warning(f"Using legacy CSV pattern for user {self.user_id}: {pattern} ({len(files)} files)")
                return files

        logger.warning(f"No {file_type} CSV files found for user {self.user_id}")
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
        Retourne la source effective qui sera utilisée.

        Returns:
            str: 'cointracking', 'cointracking_api', ou 'stub'
        """
        if self.should_use_api():
            credentials = self.get_api_credentials()
            if credentials.get("api_key") and credentials.get("api_secret"):
                return "cointracking_api"
            else:
                logger.warning(f"API mode requested for user {self.user_id} but no credentials found")
                return "stub"

        elif self.should_use_csv():
            if self.get_csv_files("balance"):
                return "cointracking"
            else:
                logger.warning(f"CSV mode requested for user {self.user_id} but no CSV files found")
                return "stub"

        return "stub"
