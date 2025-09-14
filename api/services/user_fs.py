"""
Système de fichiers scopé par utilisateur avec protection path traversal.
Isole les données de chaque utilisateur dans data/users/{user_id}/
"""
from __future__ import annotations
import os
import glob
from pathlib import Path
from typing import List, Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)

class UserScopedFS:
    """
    Système de fichiers scopé par utilisateur avec sécurité renforcée.
    Empêche le path traversal et isole chaque utilisateur.
    """

    def __init__(self, project_root: str, user_id: str):
        """
        Args:
            project_root: Racine du projet
            user_id: ID utilisateur (déjà validé)
        """
        self.project_root = Path(project_root).resolve()
        self.user_id = user_id
        self.user_root = self.project_root / "data" / "users" / user_id

        # Créer le répertoire utilisateur s'il n'existe pas
        self.user_root.mkdir(parents=True, exist_ok=True)

        logger.debug(f"UserScopedFS initialized for user '{user_id}' at {self.user_root}")

    def _validate_path(self, relative_path: str) -> Path:
        """
        Valide qu'un chemin relatif reste dans le scope utilisateur.

        Args:
            relative_path: Chemin relatif au répertoire utilisateur

        Returns:
            Path: Chemin absolu validé

        Raises:
            ValueError: Si path traversal détecté
        """
        if not relative_path:
            return self.user_root

        # Résolution et vérification anti-traversal
        candidate = (self.user_root / relative_path).resolve()

        try:
            # S'assurer que le chemin reste dans user_root
            candidate.relative_to(self.user_root)
        except ValueError:
            raise ValueError(f"Path traversal detected: {relative_path}")

        return candidate

    def get_path(self, relative_path: str = "") -> str:
        """
        Retourne le chemin absolu sécurisé pour un chemin relatif.

        Args:
            relative_path: Chemin relatif au répertoire utilisateur

        Returns:
            str: Chemin absolu validé
        """
        validated_path = self._validate_path(relative_path)
        return str(validated_path)

    def exists(self, relative_path: str) -> bool:
        """Vérifie si un fichier/dossier existe."""
        try:
            path = self._validate_path(relative_path)
            return path.exists()
        except ValueError:
            return False

    def list_files(self, relative_path: str = "", pattern: str = "*") -> List[str]:
        """
        Liste les fichiers dans un répertoire avec pattern.

        Args:
            relative_path: Répertoire relatif à lister
            pattern: Pattern de fichiers (ex: "*.csv")

        Returns:
            List[str]: Liste des chemins de fichiers trouvés
        """
        try:
            dir_path = self._validate_path(relative_path)
            if not dir_path.is_dir():
                return []

            # Utiliser glob pour le pattern matching
            search_pattern = dir_path / pattern
            files = glob.glob(str(search_pattern))

            # Retourner seulement les fichiers (pas les dossiers)
            return [f for f in files if os.path.isfile(f)]

        except ValueError as e:
            logger.warning(f"Invalid path in list_files: {e}")
            return []

    def glob_files(self, pattern: str) -> List[str]:
        """
        Recherche de fichiers avec pattern glob dans tout le répertoire utilisateur.

        Args:
            pattern: Pattern glob (ex: "**/*.csv", "csv/*.csv")

        Returns:
            List[str]: Liste des fichiers trouvés
        """
        try:
            # Construire le pattern complet
            full_pattern = self.user_root / pattern
            files = glob.glob(str(full_pattern), recursive=True)

            # Valider que tous les fichiers sont dans le scope
            validated_files = []
            for file_path in files:
                try:
                    abs_path = Path(file_path).resolve()
                    abs_path.relative_to(self.user_root)  # Vérification anti-traversal
                    if abs_path.is_file():
                        validated_files.append(str(abs_path))
                except ValueError:
                    logger.warning(f"Path traversal attempt blocked: {file_path}")
                    continue

            return validated_files

        except Exception as e:
            logger.error(f"Error in glob_files: {e}")
            return []

    def read_json(self, relative_path: str) -> Dict[str, Any]:
        """
        Lit un fichier JSON dans le scope utilisateur.

        Args:
            relative_path: Chemin relatif du fichier JSON

        Returns:
            Dict[str, Any]: Contenu JSON parsé

        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            ValueError: Si path traversal ou JSON invalide
        """
        import json

        file_path = self._validate_path(relative_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {relative_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def write_json(self, relative_path: str, data: Dict[str, Any]) -> None:
        """
        Écrit un fichier JSON dans le scope utilisateur.

        Args:
            relative_path: Chemin relatif du fichier JSON
            data: Données à écrire
        """
        import json

        file_path = self._validate_path(relative_path)

        # Créer les répertoires parents si nécessaire
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_most_recent_file(self, pattern: str) -> Optional[str]:
        """
        Trouve le fichier le plus récent correspondant au pattern.

        Args:
            pattern: Pattern de recherche

        Returns:
            Optional[str]: Chemin du fichier le plus récent ou None
        """
        files = self.glob_files(pattern)
        if not files:
            return None

        # Trier par date de modification (plus récent en premier)
        try:
            files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
            return files[0]
        except OSError:
            return files[0] if files else None

    def get_user_root(self) -> str:
        """Retourne le répertoire racine de l'utilisateur."""
        return str(self.user_root)