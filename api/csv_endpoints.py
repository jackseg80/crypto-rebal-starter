"""
Endpoints pour gestion et téléchargement automatique des fichiers CSV CoinTracking
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import os
import glob
from datetime import datetime
import aiohttp
import asyncio
from pathlib import Path

router = APIRouter()

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


def get_cointracking_credentials():
    """Récupère les credentials CoinTracking depuis l'environnement"""
    api_key = os.getenv("CT_API_KEY") or os.getenv("COINTRACKING_API_KEY")
    api_secret = os.getenv("CT_API_SECRET") or os.getenv("COINTRACKING_API_SECRET")
    
    if not api_key or not api_secret:
        raise HTTPException(
            status_code=400, 
            detail="Clés API CoinTracking non configurées. Vérifiez vos variables d'environnement."
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
async def download_csv_file(request: CSVDownloadRequest) -> CSVDownloadResponse:
    """Télécharge un fichier CSV depuis CoinTracking avec nom automatique"""
    try:
        api_key, api_secret = get_cointracking_credentials()
        
        # Générer le nom de fichier  
        filename = generate_csv_filename(request.file_type, request.auto_name)
        
        # Créer le dossier de destination si nécessaire
        download_dir = Path(request.download_path)
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
async def get_csv_files_status() -> CSVStatusResponse:
    """Retourne le status des fichiers CSV disponibles localement"""
    try:
        data_dir = Path("data/raw/")
        
        if not data_dir.exists():
            return CSVStatusResponse(
                success=True,
                files=[],
                error="Dossier data/raw/ n'existe pas"
            )
        
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