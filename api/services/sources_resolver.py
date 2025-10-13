"""
Résolveur centralisé pour Sources - SOT unique pour toute lecture de données.
Système unifié: tous les fichiers dans {module}/data/*.csv
"""
from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Tuple, Optional
from api.services.user_fs import UserScopedFS

logger = logging.getLogger(__name__)

def resolve_effective_path(user_fs: UserScopedFS, module: str) -> Tuple[str, Optional[str]]:
    """
    Résolution unique et centralisée des sources de données (SIMPLIFIÉ).

    Priorité absolue:
    1. Fichier explicite de l'utilisateur (csv_selected_file)
    2. Fichiers dans data/ (le plus récent avec timestamp)
    3. empty

    Args:
        user_fs: FileSystem utilisateur sécurisé
        module: Nom du module ('cointracking', 'saxobank')

    Returns:
        Tuple[mode, path]:
        - mode: 'data' | 'user_choice' | 'empty'
        - path: Chemin absolu du fichier à lire ou None
    """

    # 0) 🎯 PRIORITÉ UTILISATEUR: Fichier explicitement sélectionné
    try:
        user_settings = user_fs.read_json("config.json")
        data_source = user_settings.get("data_source", "")
        csv_selected_file = user_settings.get("csv_selected_file")

        # Ne pas utiliser csv_selected_file si l'utilisateur a explicitement choisi l'API
        if data_source.endswith("_api"):
            logger.debug(f"User has selected API mode ({data_source}), skipping CSV file resolution")
        elif csv_selected_file and module in data_source:
            # Chercher le fichier dans data/ (nouveau système simplifié)
            potential_path = user_fs.get_path(f"{module}/data/{csv_selected_file}")
            if os.path.exists(potential_path):
                logger.info(f"👤 Sources resolver: Using user-selected file for {module} - {potential_path}")
                return "user_choice", potential_path

            logger.warning(f"⚠️ User-selected file not found: {csv_selected_file}, falling back to auto-detection")
    except Exception as e:
        logger.debug(f"Could not read user settings: {e}")

    # 1) 🎯 Fichiers dans data/ (le plus récent)
    data_pattern = f"{module}/data/*.csv"
    data_files = user_fs.glob_files(data_pattern)
    if data_files:
        # Prendre le plus récent par date de modification
        try:
            data_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        except OSError:
            pass
        logger.info(f"📊 Sources resolver: Using data/ for {module} - {data_files[0]}")
        return "data", data_files[0]

    # 2) ❌ VIDE: Aucune source trouvée
    logger.warning(f"💔 Sources resolver: No data found for {module}")
    return "empty", None


def get_effective_source_info(user_fs: UserScopedFS, module: str) -> dict:
    """
    Informations détaillées sur la source effective utilisée.
    Pour debugging et monitoring.
    """
    mode, path = resolve_effective_path(user_fs, module)

    info = {
        "module": module,
        "effective_read": mode,
        "effective_path": str(Path(path).relative_to(user_fs.get_user_root())) if path else None,
        "absolute_path": path
    }

    if path and mode != "empty":
        try:
            stat = os.stat(path)
            info.update({
                "file_size": stat.st_size,
                "modified_at": stat.st_mtime,
                "exists": True
            })
        except OSError:
            info["exists"] = False

    return info