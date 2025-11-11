"""
Endpoints pour la gestion des settings utilisateur.
Chaque utilisateur a ses propres settings dans data/users/{user_id}/config.json
Supports: CoinTracking CSV/API + Saxo CSV sources
"""
from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
import logging

from api.deps import get_active_user
from api.services.user_fs import UserScopedFS
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["User Settings"])

class UserSettings(BaseModel):
    """Modèle pour les settings utilisateur"""
    data_source: str = "csv"
    api_base_url: str = "http://localhost:8000"
    display_currency: str = "USD"
    min_usd_threshold: float = 1.0
    csv_glob: str = "csv/*.csv"
    # Nom du fichier CSV sélectionné explicitement (dans data/users/<user>/csv)
    csv_selected_file: str | None = None
    cointracking_api_key: str = ""
    cointracking_api_secret: str = ""
    coingecko_api_key: str = ""
    fred_api_key: str = ""
    pricing: str = "local"
    refresh_interval: int = 5
    enable_coingecko_classification: bool = True
    enable_portfolio_snapshots: bool = True
    enable_performance_tracking: bool = True
    theme: str = "auto"
    debug_mode: bool = False

@router.get("/settings", response_model=Dict[str, Any])
async def get_user_settings(user: str = Depends(get_active_user)) -> Dict[str, Any]:
    """
    Récupère les settings de l'utilisateur actuel.

    Returns:
        Dict[str, Any]: Settings de l'utilisateur

    Raises:
        HTTPException: 404 si les settings n'existent pas
    """
    try:
        # Utiliser UserScopedFS pour lire les settings
        project_root = str(Path(__file__).parent.parent)
        user_fs = UserScopedFS(project_root, user)

        if not user_fs.exists("config.json"):
            logger.warning(f"No settings found for user {user}, returning defaults")
            # Retourner les settings par défaut
            default_settings = UserSettings()
            return default_settings.dict()

        settings = user_fs.read_json("config.json")
        logger.debug(f"Loaded settings for user {user}: {len(settings)} keys")

        # Fusionner avec les defaults pour assurer la compatibilité
        default_settings = UserSettings()
        merged_settings = default_settings.dict()
        merged_settings.update(settings)

        return merged_settings

    except Exception as e:
        logger.error(f"Error loading settings for user {user}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading user settings: {str(e)}"
        )

@router.put("/settings")
async def save_user_settings(
    settings: Dict[str, Any],
    user: str = Depends(get_active_user)
) -> Dict[str, str]:
    """
    Sauvegarde les settings de l'utilisateur actuel.

    Args:
        settings: Nouveau settings à sauvegarder
        user: ID utilisateur (injecté par dependency)

    Returns:
        Dict[str, str]: Statut de la sauvegarde

    Raises:
        HTTPException: 400 si les settings sont invalides, 500 si erreur serveur
    """
    try:
        # Valider les settings avec le modèle Pydantic
        try:
            validated_settings = UserSettings(**settings)
        except Exception as validation_error:
            logger.warning(f"Settings validation failed for user {user}: {validation_error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid settings: {str(validation_error)}"
            )

        # Utiliser UserScopedFS pour écrire les settings
        project_root = str(Path(__file__).parent.parent)
        user_fs = UserScopedFS(project_root, user)

        # ✅ FIX: Merger avec l'ancien config au lieu d'écraser
        # Charger l'ancien config s'il existe
        old_config = {}
        try:
            old_config = user_fs.read_json("config.json")
            logger.debug(f"Merging with existing config: {len(old_config)} keys")
        except (FileNotFoundError, ValueError):
            logger.debug("No existing config found, creating new one")

        # Convertir les nouveaux settings en dict
        new_settings = validated_settings.dict()

        # Merger (les nouveaux settings écrasent les anciens)
        merged_settings = {**old_config, **new_settings}

        # Sauvegarder
        user_fs.write_json("config.json", merged_settings)

        logger.info(f"✅ Settings saved for user {user}: {len(merged_settings)} keys, csv_selected_file='{merged_settings.get('csv_selected_file')}'")

        return {
            "status": "success",
            "message": f"Settings saved for user {user}",
            "user": user
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving settings for user {user}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving user settings: {str(e)}"
        )

@router.delete("/settings")
async def reset_user_settings(user: str = Depends(get_active_user)) -> Dict[str, str]:
    """
    Remet les settings utilisateur aux valeurs par défaut.

    Args:
        user: ID utilisateur (injecté par dependency)

    Returns:
        Dict[str, str]: Statut de la remise à zéro
    """
    try:
        project_root = str(Path(__file__).parent.parent)
        user_fs = UserScopedFS(project_root, user)

        # Créer les settings par défaut
        default_settings = UserSettings()
        user_fs.write_json("config.json", default_settings.dict())

        logger.info(f"Settings reset to defaults for user {user}")

        return {
            "status": "success",
            "message": f"Settings reset to defaults for user {user}",
            "user": user
        }

    except Exception as e:
        logger.error(f"Error resetting settings for user {user}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resetting user settings: {str(e)}"
        )

@router.get("/sources")
async def get_user_data_sources(user: str = Depends(get_active_user)) -> Dict[str, Any]:
    """
    Récupère les sources de données disponibles pour l'utilisateur depuis data/ (nouveau système).

    Returns:
        Dict[str, Any]: Sources disponibles (CSV + API conditionnelle)
    """
    try:
        from api.services.data_router import UserDataRouter

        project_root = str(Path(__file__).parent.parent)
        data_router = UserDataRouter(project_root, user)

        sources = []

        # CSV CoinTracking et Saxo: lister les fichiers depuis data/
        csv_files = []

        # Scanner data/ CoinTracking
        ct_data_dir = data_router.user_fs.get_path("cointracking/data")
        if Path(ct_data_dir).exists():
            csv_files.extend([(p, "cointracking") for p in Path(ct_data_dir).glob("*.csv")])

        # Scanner data/ Saxo
        saxo_data_dir = data_router.user_fs.get_path("saxobank/data")
        if Path(saxo_data_dir).exists():
            csv_files.extend([(p, "saxobank") for p in Path(saxo_data_dir).glob("*.csv")])

        # Trier par nom et dédupliquer
        csv_files = sorted(set(csv_files), key=lambda item: item[0].name.lower())

        for i, (csv_path, module) in enumerate(csv_files[:100]):  # Max 100 fichiers (50 cointracking + 50 saxo)
            file_name = csv_path.name
            # Générer une clé unique basée sur le nom du fichier (slug-friendly)
            file_slug = file_name.replace('.csv', '').lower().replace(' ', '_').replace('-', '_')

            # Préfixe selon le module
            key_prefix = "saxo" if module == "saxobank" else "csv"
            icon = "🏦" if module == "saxobank" else "📄"

            sources.append({
                "key": f"{key_prefix}_{file_slug}",
                "label": f"{icon} {file_name}",
                "type": "csv",
                "module": module,
                "file_path": str(csv_path)
            })

        # API CoinTracking: seulement si l'utilisateur a des clés API
        user_settings = data_router.settings
        has_ct_credentials = (
            user_settings.get("cointracking_api_key") and
            user_settings.get("cointracking_api_secret")
        )

        if has_ct_credentials:
            sources.append({
                "key": "cointracking_api",
                "label": "🌐 CoinTracking API",
                "type": "api",
                "file_path": None
            })

        # Compter le nombre de fichiers par module
        cointracking_count = sum(1 for _, m in csv_files if m == "cointracking")
        saxo_count = sum(1 for _, m in csv_files if m == "saxobank")

        return {
            "user": user,
            "sources": sources,
            "current_source": user_settings.get("data_source", "csv"),
            "total_csv_files": len(csv_files) if csv_files else 0,
            "cointracking_files": cointracking_count,
            "saxo_files": saxo_count
        }

    except Exception as e:
        logger.error(f"Error getting data sources for user {user}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user data sources: {str(e)}"
        )

@router.get("/settings/info")
async def get_user_settings_info(user: str = Depends(get_active_user)) -> Dict[str, Any]:
    """
    Récupère des informations de debug sur les settings utilisateur.

    Returns:
        Dict[str, Any]: Informations de debug
    """
    try:
        project_root = str(Path(__file__).parent.parent)
        user_fs = UserScopedFS(project_root, user)

        config_exists = user_fs.exists("config.json")
        user_root = user_fs.get_user_root()

        info = {
            "user": user,
            "user_root": user_root,
            "config_exists": config_exists,
            "config_path": user_fs.get_path("config.json")
        }

        if config_exists:
            settings = user_fs.read_json("config.json")
            info["settings_keys"] = list(settings.keys())
            info["data_source"] = settings.get("data_source", "unknown")

        return info

    except Exception as e:
        logger.error(f"Error getting settings info for user {user}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user settings info: {str(e)}"
        )

@router.get("/sources/debug")
async def debug_user_sources(user: str = Depends(get_active_user)) -> Dict[str, Any]:
    """DEBUG: Vérifie directement les fichiers dans data/ vs imports/"""
    try:
        project_root = str(Path(__file__).parent.parent)
        user_fs = UserScopedFS(project_root, user)

        # Scanner tous les dossiers
        ct_data = list(Path(user_fs.get_path("cointracking/data")).glob("*.csv")) if Path(user_fs.get_path("cointracking/data")).exists() else []
        ct_imports = list(Path(user_fs.get_path("cointracking/imports")).glob("*.csv")) if Path(user_fs.get_path("cointracking/imports")).exists() else []
        saxo_data = list(Path(user_fs.get_path("saxobank/data")).glob("*.csv")) if Path(user_fs.get_path("saxobank/data")).exists() else []
        saxo_imports = list(Path(user_fs.get_path("saxobank/imports")).glob("*.csv")) if Path(user_fs.get_path("saxobank/imports")).exists() else []

        return {
            "cointracking": {
                "data": [str(p.name) for p in ct_data],
                "imports": [str(p.name) for p in ct_imports]
            },
            "saxobank": {
                "data": [str(p.name) for p in saxo_data],
                "imports": [str(p.name) for p in saxo_imports]
            },
            "timestamp": "2025-10-13T18:50:00Z"  # Force reload marker
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

