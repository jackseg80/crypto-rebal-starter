"""
Résolveur centralisé pour Sources - SOT unique pour toute lecture de données
Remplace définitivement la logique legacy csv_glob/csv_selected_file
"""
from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Tuple, Optional, List
from api.services.user_fs import UserScopedFS

logger = logging.getLogger(__name__)

def resolve_effective_path(user_fs: UserScopedFS, module: str) -> Tuple[str, Optional[str]]:
    """
    Résolution unique et centralisée des sources de données.

    Priorité absolue:
    1. Fichier explicite de l'utilisateur (csv_selected_file)
    2. snapshots → imports → legacy → empty

    Args:
        user_fs: FileSystem utilisateur sécurisé
        module: Nom du module ('cointracking', 'saxobank')

    Returns:
        Tuple[mode, path]:
        - mode: 'snapshot' | 'imports' | 'legacy' | 'user_choice' | 'empty'
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
        elif csv_selected_file and module == "cointracking" and data_source == "cointracking":
            # Chercher le fichier dans uploads/ puis imports/
            for search_dir in ["cointracking/uploads", "cointracking/imports", "cointracking/snapshots"]:
                potential_path = user_fs.get_path(f"{search_dir}/{csv_selected_file}")
                if os.path.exists(potential_path):
                    logger.info(f"👤 Sources resolver: Using user-selected file for {module} - {potential_path}")
                    return "user_choice", potential_path

            logger.warning(f"⚠️ User-selected file not found: {csv_selected_file}, falling back to auto-detection")
    except Exception as e:
        logger.debug(f"Could not read user settings: {e}")

    # 1) 🎯 PRIORITÉ ABSOLUE: Snapshots Sources
    snapshot_pattern = f"{module}/snapshots/latest.*"
    snapshots = user_fs.glob_files(snapshot_pattern)
    if snapshots:
        # Prendre le plus récent si plusieurs
        try:
            snapshots.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        except OSError:
            pass
        logger.info(f"📊 Sources resolver: Using snapshot for {module} - {snapshots[0]}")
        return "snapshot", snapshots[0]

    # 2) 🔄 SECONDAIRE: Imports Sources
    imports_pattern = f"{module}/imports/*.csv"
    imports = user_fs.glob_files(imports_pattern)
    if imports:
        # Prendre le plus récent
        try:
            imports.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        except OSError:
            pass
        logger.info(f"📥 Sources resolver: Using imports for {module} - {imports[0]}")
        return "imports", imports[0]

    # 3) 🔙 FALLBACK: Legacy patterns (backward compatibility)
    legacy_files = _resolve_legacy_patterns(user_fs, module)
    if legacy_files:
        logger.warning(f"⚠️ Sources resolver: Falling back to LEGACY for {module} - {legacy_files[0]}")
        return "legacy", legacy_files[0]

    # 4) ❌ VIDE: Aucune source trouvée
    logger.warning(f"💔 Sources resolver: No data found for {module}")
    return "empty", None

def _resolve_legacy_patterns(user_fs: UserScopedFS, module: str) -> List[str]:
    """
    Patterns legacy pour compatibilité backward.
    ⚠️ Cette fonction sera supprimée quand migration complète.
    """
    legacy_patterns = []

    if module == "cointracking":
        legacy_patterns = [
            "csv/CoinTracking*.csv",
            "csv/Current Balance*.csv",
            "cointracking/uploads/*.csv",  # Sources uploads mais pas snapshot
            "*.csv"  # Dernière chance
        ]
    elif module == "saxobank":
        legacy_patterns = [
            "csv/saxo*.csv",
            "csv/positions*.csv",
            "csv/Positions*.csv",
            "saxobank/uploads/*.csv"  # Sources uploads mais pas snapshot
        ]

    # Chercher dans tous les patterns
    for pattern in legacy_patterns:
        files = user_fs.glob_files(pattern)
        if files:
            # Trier par date de modification (plus récent en premier)
            try:
                files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
            except OSError:
                pass
            return files

    return []

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