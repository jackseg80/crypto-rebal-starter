"""
Endpoints pour la gestion des settings utilisateur.
Chaque utilisateur a ses propres settings dans data/users/{user_id}/config.json
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

        # Convertir en dict et sauvegarder
        settings_dict = validated_settings.dict()
        user_fs.write_json("config.json", settings_dict)

        logger.info(f"Settings saved for user {user}: {len(settings_dict)} keys")

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
    Récupère les sources de données disponibles pour l'utilisateur.

    Returns:
        Dict[str, Any]: Sources disponibles (CSV + API conditionnelle)
    """
    try:
        from api.services.data_router import UserDataRouter

        project_root = str(Path(__file__).parent.parent)
        data_router = UserDataRouter(project_root, user)

        sources = []

        # CSV: lister les fichiers CSV disponibles
        csv_files = data_router.get_csv_files("balance")
        if csv_files:
            for i, csv_file in enumerate(csv_files[:5]):  # Limiter à 5 fichiers max
                file_name = Path(csv_file).name
                sources.append({
                    "key": f"csv_{i}",
                    "label": f"📄 {file_name}",
                    "type": "csv",
                    "file_path": csv_file
                })

        # Ajouter une option CSV générique si pas de fichiers spécifiques
        if not csv_files:
            sources.append({
                "key": "csv",
                "label": "📄 Fichiers CSV",
                "type": "csv",
                "file_path": None
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

        return {
            "user": user,
            "sources": sources,
            "current_source": user_settings.get("data_source", "csv"),
            "total_csv_files": len(csv_files) if csv_files else 0
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