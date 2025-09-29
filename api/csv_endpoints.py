"""
Endpoints pour gestion et téléchargement automatique des fichiers CSV CoinTracking
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import os
import glob
from datetime import datetime
import aiohttp
import asyncio
from pathlib import Path
from api.deps import get_active_user
from api.services.user_fs import UserScopedFS

router = APIRouter()

# Legacy wrapper helpers
def _log_legacy_usage(endpoint: str, user: str):
    """Log l'usage des endpoints legacy pour monitoring de migration"""
    logger.warning(f"[LEGACY] CSV endpoint {endpoint} used by user {user} - consider migrating to /api/sources")

async def _delegate_to_sources(action: str, user: str, **kwargs):
    """Délègue une action vers le nouveau système sources"""
    try:
        if action == "download":
            # Déléguer vers /api/sources/refresh-api pour cointracking
            from api.sources_endpoints import refresh_api, RefreshApiRequest
            from api.services.user_fs import UserScopedFS
            from api.services.config_migrator import ConfigMigrator

            project_root = str(Path(__file__).parent.parent)
            user_fs = UserScopedFS(project_root, user)
            config_migrator = ConfigMigrator(user_fs)

            request = RefreshApiRequest(module="cointracking")
            response = await refresh_api(request, config_migrator, user_fs)

            # Adapter le format de réponse
            if response.success:
                return CSVDownloadResponse(
                    success=True,
                    filename="cointracking_via_sources.csv",
                    size=response.records_fetched or 0,
                    path="cointracking/snapshots/latest.csv"
                )
            else:
                return CSVDownloadResponse(
                    success=False,
                    error=response.error or response.message
                )

        elif action == "status":
            # Déléguer vers /api/sources/list pour cointracking
            from api.sources_endpoints import list_sources
            from api.services.user_fs import UserScopedFS
            from api.services.config_migrator import ConfigMigrator

            project_root = str(Path(__file__).parent.parent)
            user_fs = UserScopedFS(project_root, user)
            config_migrator = ConfigMigrator(user_fs)

            sources_response = await list_sources(config_migrator, user_fs)

            # Adapter pour le format CSV legacy
            files_info = []
            for module in sources_response.modules:
                if module.name == "cointracking" and module.files_detected > 0:
                    files_info.append({
                        'name': f"cointracking_sources_{module.files_detected}_files",
                        'type': 'current_balance',
                        'size': module.files_detected * 1000,  # Estimation
                        'modified': module.last_import_at or sources_response.last_updated
                    })

            return CSVStatusResponse(
                success=True,
                files=files_info
            )

    except Exception as e:
        logger.error(f"Error delegating {action} to sources: {e}")
        return None

class CSVDownloadRequest(BaseModel):
    file_type: str  # 'current_balance', 'balance_by_exchange', 'coins_by_exchange'
    download_path: str = "data/raw/"
    auto_name: bool = True  # Utilise nom avec date automatiquement

class CSVStatusResponse(BaseModel):
    success: bool
    files: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

class CSVDownloadResponse(BaseModel):
    success: bool
    filename: Optional[str] = None
    path: Optional[str] = None
    size: Optional[int] = None
    error: Optional[str] = None


def get_cointracking_credentials_for_user(user: str) -> tuple[str, str]:
    """Récupère les credentials CoinTracking depuis l'environnement"""
    # Utiliser d'abord les clés du profil utilisateur
    try:
        project_root = str(Path(__file__).parent.parent)
        user_fs = UserScopedFS(project_root, user)
        settings = user_fs.read_json("config.json")
        api_key = settings.get("cointracking_api_key")
        api_secret = settings.get("cointracking_api_secret")
    except Exception:
        api_key = None
        api_secret = None

    # Fallback éventuel vers env (dev only)
    if not api_key:
        api_key = os.getenv("CT_API_KEY") or os.getenv("COINTRACKING_API_KEY")
    if not api_secret:
        api_secret = os.getenv("CT_API_SECRET") or os.getenv("COINTRACKING_API_SECRET")

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=400,
            detail="Clés API CoinTracking non configurées pour cet utilisateur"
        )

    return api_key, api_secret


def get_csv_export_url(file_type: str) -> str:
    """Retourne l'URL d'export CoinTracking selon le type de fichier"""
    base_url = "https://cointracking.info"
    
    urls = {
        'current_balance': f"{base_url}/export_balance.csv",
        'balance_by_exchange': f"{base_url}/export_balance_by_exchange.csv", 
        'coins_by_exchange': f"{base_url}/export_coins_by_exchange.csv"
    }
    
    if file_type not in urls:
        raise HTTPException(status_code=400, detail=f"Type de fichier non supporté: {file_type}")
    
    return urls[file_type]


def generate_csv_filename(file_type: str, auto_name: bool = True) -> str:
    """Génère le nom de fichier CSV selon le type et les conventions"""
    if not auto_name:
        # Noms simples sans date
        names = {
            'current_balance': 'CoinTracking - Current Balance.csv',
            'balance_by_exchange': 'CoinTracking - Balance by Exchange.csv',
            'coins_by_exchange': 'CoinTracking - Coins by Exchange.csv'
        }
        return names.get(file_type, f'cointracking_{file_type}.csv')
    
    # Noms avec date actuelle
    today = datetime.now().strftime('%d.%m.%Y')
    names = {
        'current_balance': f'CoinTracking - Current Balance - {today}.csv',
        'balance_by_exchange': f'CoinTracking - Balance by Exchange - {today}.csv',
        'coins_by_exchange': f'CoinTracking - Coins by Exchange - {today}.csv'
    }
    return names.get(file_type, f'cointracking_{file_type}_{today}.csv')


@router.post("/csv/download")
async def download_csv_file(request: CSVDownloadRequest, user: str = Depends(get_active_user)) -> CSVDownloadResponse:
    """[LEGACY] Télécharge un fichier CSV depuis CoinTracking - délègue vers /api/sources"""
    _log_legacy_usage("download", user)

    # Essayer d'abord la délégation vers sources
    sources_result = await _delegate_to_sources("download", user)
    if sources_result:
        return sources_result

    # Fallback vers l'ancienne logique si nécessaire
    logger.info(f"[LEGACY] Falling back to original CSV download logic for user {user}")
    try:
        api_key, api_secret = get_cointracking_credentials_for_user(user)
        
        # Générer le nom de fichier  
        filename = generate_csv_filename(request.file_type, request.auto_name)
        
        # Créer le dossier de destination si nécessaire
        # Forcer le téléchargement dans le dossier csv du profil utilisateur
        project_root = str(Path(__file__).parent.parent)
        user_fs = UserScopedFS(project_root, user)
        download_dir = Path(user_fs.get_path("csv"))
        download_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = download_dir / filename
        
        # URL d'export CoinTracking
        export_url = get_csv_export_url(request.file_type)
        
        # Paramètres d'authentification CoinTracking
        auth_params = {
            'key': api_key,
            'secret': api_secret,
            'format': 'csv'
        }
        
        # Télécharger le fichier
        async with aiohttp.ClientSession() as session:
            async with session.post(export_url, data=auth_params) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Vérifier si le contenu est un CSV valide (pas une erreur HTML)
                    content_str = content.decode('utf-8-sig', errors='ignore')
                    if content_str.startswith('<!DOCTYPE') or 'error' in content_str.lower():
                        return CSVDownloadResponse(
                            success=False,
                            error="Erreur authentification CoinTracking ou données non disponibles"
                        )
                    
                    # Sauvegarder le fichier
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    # Vérifier la taille du fichier
                    file_size = file_path.stat().st_size
                    
                    if file_size < 100:  # Fichier trop petit, probablement une erreur
                        return CSVDownloadResponse(
                            success=False,
                            error="Fichier téléchargé trop petit - vérifiez vos permissions CoinTracking"
                        )
                    
                    return CSVDownloadResponse(
                        success=True,
                        filename=filename,
                        path=str(file_path),
                        size=file_size
                    )
                else:
                    return CSVDownloadResponse(
                        success=False,
                        error=f"Erreur HTTP {response.status} lors du téléchargement"
                    )
                    
    except HTTPException:
        raise
    except Exception as e:
        return CSVDownloadResponse(
            success=False,
            error=f"Erreur téléchargement: {str(e)}"
        )


@router.get("/csv/status")
async def get_csv_files_status(user: str = Depends(get_active_user)) -> CSVStatusResponse:
    """[LEGACY] Retourne le status des fichiers CSV - délègue vers /api/sources"""
    _log_legacy_usage("status", user)

    # Essayer d'abord la délégation vers sources
    sources_result = await _delegate_to_sources("status", user)
    if sources_result:
        return sources_result

    # Fallback vers l'ancienne logique
    logger.info(f"[LEGACY] Falling back to original CSV status logic for user {user}")
    try:
        project_root = str(Path(__file__).parent.parent)
        user_fs = UserScopedFS(project_root, user)
        data_dir = Path(user_fs.get_path("csv"))
        
        if not data_dir.exists():
            return CSVStatusResponse(success=True, files=[], error="Aucun dossier csv/ pour ce profil")
        
        # Patterns pour trouver les fichiers CSV CoinTracking
        patterns = [
            "CoinTracking - Current Balance*.csv",
            "CoinTracking - Balance by Exchange*.csv", 
            "CoinTracking - Coins by Exchange*.csv"
        ]
        
        files_info = []
        
        for pattern in patterns:
            for file_path in data_dir.glob(pattern):
                if file_path.is_file():
                    stat = file_path.stat()
                    files_info.append({
                        'name': file_path.name,
                        'path': str(file_path),
                        'size': stat.st_size,
                        'modified': stat.st_mtime * 1000,  # Timestamp en ms pour JavaScript
                        'type': detect_file_type(file_path.name)
                    })
        
        # Trier par date de modification (plus récent en premier)
        files_info.sort(key=lambda f: f['modified'], reverse=True)
        
        return CSVStatusResponse(
            success=True,
            files=files_info
        )
        
    except Exception as e:
        return CSVStatusResponse(
            success=False,
            error=f"Erreur vérification fichiers: {str(e)}"
        )


def detect_file_type(filename: str) -> str:
    """Détecte le type de fichier CSV d'après son nom"""
    filename_lower = filename.lower()
    
    if 'balance by exchange' in filename_lower:
        return 'balance_by_exchange'
    elif 'coins by exchange' in filename_lower:
        return 'coins_by_exchange'
    elif 'current balance' in filename_lower:
        return 'current_balance'
    else:
        return 'unknown'


@router.get("/csv/cleanup")
async def cleanup_old_csv_files(keep_days: int = 7):
    """Nettoie les anciens fichiers CSV (garde seulement les X derniers jours)"""
    try:
        data_dir = Path("data/raw/")
        
        if not data_dir.exists():
            return {"success": True, "message": "Dossier data/raw/ n'existe pas", "deleted": 0}
        
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
        deleted_count = 0
        
        # Patterns pour trouver les fichiers CSV CoinTracking  
        patterns = [
            "CoinTracking - Current Balance*.csv",
            "CoinTracking - Balance by Exchange*.csv",
            "CoinTracking - Coins by Exchange*.csv"
        ]
        
        for pattern in patterns:
            for file_path in data_dir.glob(pattern):
                if file_path.is_file():
                    # Garder toujours au moins 1 fichier de chaque type
                    same_type_files = list(data_dir.glob(pattern))
                    if len(same_type_files) <= 1:
                        continue
                    
                    if file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()  # Supprimer le fichier
                        deleted_count += 1
        
        return {
            "success": True, 
            "message": f"Nettoyage terminé - {deleted_count} fichiers supprimés",
            "deleted": deleted_count
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Erreur nettoyage: {str(e)}"
        }
