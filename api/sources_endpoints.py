"""
Endpoints unifiés pour la gestion des sources de données (CoinTracking, Saxo, etc.).
Point d'entrée unique pour scan/import/refresh des différents modules.
"""
from __future__ import annotations
import os
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field

from api.deps import get_active_user
from api.services.user_fs import UserScopedFS
from api.services.config_migrator import ConfigMigrator, resolve_secret_ref, get_staleness_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sources", tags=["Sources"])

# Modèles Pydantic
class DetectedFile(BaseModel):
    """Fichier détecté"""
    name: str
    relative_path: str
    size_bytes: int
    modified_at: str
    is_legacy: bool = False

class SourceModuleInfo(BaseModel):
    """Informations sur un module de source"""
    name: str
    enabled: bool
    modes: List[str]
    files_detected: int
    detected_files: List[DetectedFile]
    last_import_at: Optional[str] = None
    staleness: Dict[str, Any]
    effective_read: str  # "snapshot" | "imports" | "legacy" | "api"
    effective_path: Optional[str] = None  # Chemin réellement lu
    notes: Optional[str] = None

class SourcesScanResult(BaseModel):
    """Résultat du scan détaillé des sources"""
    module: str
    files_detected: List[str]
    would_move_to: str
    estimated_records: Optional[int] = None
    last_modified: Optional[str] = None
    is_legacy: bool = False

class SourcesListResponse(BaseModel):
    """Réponse de la liste des sources"""
    modules: List[SourceModuleInfo]
    config_version: int
    last_updated: str

class SourcesScanResponse(BaseModel):
    """Réponse du scan des sources"""
    modules: Dict[str, SourcesScanResult]
    scan_timestamp: str

class ImportRequest(BaseModel):
    """Requête d'import d'un module"""
    module: str = Field(..., description="Nom du module (cointracking, saxobank)")
    force: bool = Field(False, description="Forcer l'import même si récent")
    files: Optional[List[str]] = Field(None, description="Fichiers spécifiques à importer (chemins relatifs)")

class ImportResponse(BaseModel):
    """Réponse d'import"""
    success: bool
    module: str
    files_processed: int
    snapshot_created: bool
    message: str
    error: Optional[str] = None

class RefreshApiRequest(BaseModel):
    """Requête de refresh API"""
    module: str = Field(..., description="Nom du module")

class RefreshApiResponse(BaseModel):
    """Réponse refresh API"""
    success: bool
    module: str
    records_fetched: Optional[int] = None
    snapshot_updated: bool
    message: str
    error: Optional[str] = None

def get_user_fs(user: str = Depends(get_active_user)) -> UserScopedFS:
    """Dependency pour obtenir le UserScopedFS de l'utilisateur actuel"""
    project_root = str(Path(__file__).parent.parent)  # api/sources_endpoints.py -> crypto-rebal-starter/
    return UserScopedFS(project_root, user)

def get_config_migrator(user_fs: UserScopedFS = Depends(get_user_fs)) -> ConfigMigrator:
    """Dependency pour obtenir le ConfigMigrator"""
    return ConfigMigrator(user_fs)


@router.get("/list", response_model=SourcesListResponse)
async def list_sources(
    config_migrator: ConfigMigrator = Depends(get_config_migrator),
    user_fs: UserScopedFS = Depends(get_user_fs)
) -> SourcesListResponse:
    """
    Liste tous les modules de sources configurés avec leur état.
    """
    try:
        # Charger la configuration
        config = config_migrator.load_sources_config()

        modules_info = []

        for module_name, module_config in config["modules"].items():
            # Collecter les fichiers détectés avec détails
            detected_files = []
            import os
            from pathlib import Path
            from api.services.config_migrator import resolve_secret_ref

            # NOUVEAU SYSTÈME SIMPLIFIÉ: Chercher uniquement dans data/
            data_pattern = f"{module_name}/data/*.csv"
            files = user_fs.glob_files(data_pattern)

            for file_path in files:
                try:
                    file_stat = os.stat(file_path)
                    path_obj = Path(file_path)
                    relative_path = str(path_obj.relative_to(user_fs.get_user_root()))

                    detected_file = DetectedFile(
                        name=path_obj.name,
                        relative_path=relative_path,
                        size_bytes=file_stat.st_size,
                        modified_at=datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                        is_legacy=False  # Plus de fichiers legacy dans le nouveau système
                    )
                    detected_files.append(detected_file)
                except (OSError, ValueError) as e:
                    logger.warning(f"Could not get file details for {file_path}: {e}")
                    continue

            # Trier par date de modification (plus récent en premier)
            detected_files.sort(key=lambda f: f.modified_at, reverse=True)
            files_count = len(detected_files)

            # Calculer l'état de staleness
            staleness = get_staleness_state(
                module_config.get("last_import_at"),
                module_config.get("snapshot_ttl_hours", 24),
                module_config.get("warning_threshold_hours", 12)
            )

            # Déterminer effective_read et effective_path (système simplifié)
            effective_read = "none"
            effective_path = None

            # Lecture directe depuis data/ (fichier le plus récent)
            if detected_files:
                effective_read = "data"
                effective_path = detected_files[0].relative_path  # Déjà trié par date (plus récent d'abord)

            # Ajuster modes dynamiquement selon les credentials API
            modes = list(module_config.get("modes", ["data"]))
            # Convertir ancien mode "uploads" vers "data" pour compatibilité
            modes = ["data" if m == "uploads" else m for m in modes]
            if "api" in modes:
                # Vérifier si les credentials API sont résolubles
                api_config = module_config.get("api", {})
                key_ref = api_config.get("key_ref")
                secret_ref = api_config.get("secret_ref")

                if key_ref and secret_ref:
                    key_value = resolve_secret_ref(key_ref, user_fs)
                    secret_value = resolve_secret_ref(secret_ref, user_fs)

                    if not (key_value and secret_value):
                        # Retirer "api" des modes si credentials non résolubles
                        modes = [m for m in modes if m != "api"]
                        logger.debug(f"API mode removed for {module_name} - credentials not resolvable")

            module_info = SourceModuleInfo(
                name=module_name,
                enabled=module_config.get("enabled", True),
                modes=modes,
                files_detected=files_count,
                detected_files=detected_files,
                last_import_at=module_config.get("last_import_at"),
                staleness=staleness,
                effective_read=effective_read,
                effective_path=effective_path,
                notes=module_config.get("notes")
            )

            modules_info.append(module_info)

        return SourcesListResponse(
            modules=modules_info,
            config_version=config.get("version", 1),
            last_updated=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error listing sources: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du chargement des sources: {str(e)}")

@router.get("/scan", response_model=SourcesScanResponse)
async def scan_sources(
    config_migrator: ConfigMigrator = Depends(get_config_migrator),
    user_fs: UserScopedFS = Depends(get_user_fs)
) -> SourcesScanResponse:
    """
    Scan détaillé des fichiers qui seraient importés pour chaque module.
    Dry-run sans actions destructives.
    """
    try:
        config = config_migrator.load_sources_config()
        scan_results = {}

        for module_name, module_config in config["modules"].items():
            if not module_config.get("enabled", True):
                continue

            # NOUVEAU SYSTÈME SIMPLIFIÉ: Chercher uniquement dans data/
            data_pattern = f"{module_name}/data/*.csv"
            all_files = user_fs.glob_files(data_pattern)

            # Supprimer les doublons tout en préservant l'ordre
            seen = set()
            unique_files = []
            for f in all_files:
                if f not in seen:
                    seen.add(f)
                    unique_files.append(f)

            if unique_files:
                # Estimer le nombre d'enregistrements du fichier le plus récent
                estimated_records = None
                last_modified = None

                # Trier par date de modification (plus récent en premier)
                try:
                    unique_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
                    most_recent = unique_files[0]

                    # Timestamp de modification
                    mtime = datetime.fromtimestamp(os.path.getmtime(most_recent))
                    last_modified = mtime.isoformat()

                    # Estimation rapide du nombre de lignes (première MB)
                    estimated_records = _estimate_csv_records(most_recent)

                except Exception as e:
                    logger.warning(f"Could not analyze file {most_recent}: {e}")

                scan_results[module_name] = SourcesScanResult(
                    module=module_name,
                    files_detected=[Path(f).name for f in unique_files],  # Juste les noms
                    would_move_to=f"{module_name}/data/",  # Les fichiers restent dans data/
                    estimated_records=estimated_records,
                    last_modified=last_modified,
                    is_legacy=False  # Plus de fichiers legacy
                )

        return SourcesScanResponse(
            modules=scan_results,
            scan_timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error scanning sources: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du scan: {str(e)}")

@router.post("/refresh-api", response_model=RefreshApiResponse)
async def refresh_api(
    request: RefreshApiRequest,
    config_migrator: ConfigMigrator = Depends(get_config_migrator),
    user_fs: UserScopedFS = Depends(get_user_fs)
) -> RefreshApiResponse:
    """
    Rafraîchit les données depuis l'API pour un module.
    """
    try:
        config = config_migrator.load_sources_config()

        if request.module not in config["modules"]:
            raise HTTPException(status_code=404, detail=f"Module {request.module} non trouvé")

        module_config = config["modules"][request.module]

        if "api" not in module_config.get("modes", []):
            raise HTTPException(status_code=400, detail=f"Module {request.module} n'a pas de mode API")

        # Résoudre les credentials
        api_config = module_config.get("api", {})
        api_key = resolve_secret_ref(api_config.get("key_ref", ""), user_fs)
        api_secret = resolve_secret_ref(api_config.get("secret_ref", ""), user_fs)

        if not api_key or not api_secret:
            return RefreshApiResponse(
                success=False,
                module=request.module,
                snapshot_updated=False,
                message="Credentials API non configurées",
                error="MISSING_CREDENTIALS"
            )

        # Déléguer au module spécifique selon le type
        records_fetched = None

        if request.module == "cointracking":
            records_fetched = await _refresh_cointracking_api(api_key, api_secret, user_fs)
        else:
            return RefreshApiResponse(
                success=False,
                module=request.module,
                snapshot_updated=False,
                message=f"Refresh API non supporté pour {request.module}",
                error="NOT_SUPPORTED"
            )

        if records_fetched is None:
            return RefreshApiResponse(
                success=False,
                module=request.module,
                snapshot_updated=False,
                message="Échec du refresh API",
                error="API_ERROR"
            )

        # Mettre à jour la configuration
        module_config["last_import_at"] = datetime.utcnow().isoformat()
        config_migrator.save_sources_config(config)

        return RefreshApiResponse(
            success=True,
            module=request.module,
            records_fetched=records_fetched,
            snapshot_updated=True,  # Les données sont directement dans data/
            message=f"API rafraîchie, {records_fetched} enregistrements sauvegardés dans data/"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing API for {request.module}: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur refresh API: {str(e)}")

# Fonctions utilitaires

def _estimate_csv_records(file_path: str, sample_bytes: int = 1024*1024) -> Optional[int]:
    """
    Estime le nombre d'enregistrements dans un fichier CSV
    en lisant un échantillon du début du fichier.
    """
    try:
        file_size = os.path.getsize(file_path)

        with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            # Lire un échantillon
            sample = f.read(min(sample_bytes, file_size))

            if not sample.strip():
                return 0

            # Compter les lignes dans l'échantillon
            sample_lines = len(sample.split('\n')) - 1  # -1 pour la ligne vide de fin

            if sample_lines <= 1:  # Juste l'entête
                return 0

            # Estimer le total (en retirant 1 pour l'entête)
            if len(sample) < file_size:
                ratio = file_size / len(sample)
                estimated = int((sample_lines - 1) * ratio)
            else:
                estimated = sample_lines - 1

            return max(0, estimated)

    except Exception as e:
        logger.warning(f"Could not estimate records in {file_path}: {e}")
        return None

async def _refresh_cointracking_api(api_key: str, api_secret: str, user_fs: UserScopedFS) -> Optional[int]:
    """
    Rafraîchit les données CoinTracking via API.
    Sauvegarde directement dans data/ avec versioning automatique.

    Returns:
        Optional[int]: Nombre d'enregistrements récupérés ou None si erreur
    """
    try:
        # Réutiliser la logique existante de csv_endpoints.py
        from api.csv_endpoints import get_csv_export_url
        import aiohttp

        # Créer le répertoire data (nouveau système simplifié)
        data_dir = user_fs.get_path("cointracking/data")
        Path(data_dir).mkdir(parents=True, exist_ok=True)

        # Télécharger le fichier current_balance
        export_url = get_csv_export_url("current_balance")

        auth_params = {
            'key': api_key,
            'secret': api_secret,
            'format': 'csv'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(export_url, data=auth_params) as response:
                if response.status == 200:
                    content = await response.read()

                    # Vérifier que c'est du CSV valide
                    content_str = content.decode('utf-8-sig', errors='ignore')
                    if content_str.startswith('<!DOCTYPE') or 'error' in content_str.lower():
                        raise ValueError("API returned error or HTML instead of CSV")

                    # Sauvegarder directement dans data/ avec timestamp
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    data_file = Path(data_dir) / f"{timestamp}_cointracking_api.csv"

                    with open(data_file, 'wb') as f:
                        f.write(content)

                    # Estimer le nombre d'enregistrements
                    records = _estimate_csv_records(str(data_file))

                    logger.info(f"Downloaded CoinTracking data to data/: {records} records estimated")
                    return records
                else:
                    raise ValueError(f"API returned status {response.status}")

    except Exception as e:
        logger.error(f"Failed to refresh CoinTracking API: {e}")
        return None


class UploadResponse(BaseModel):
    """Réponse d'upload de fichier"""
    success: bool
    message: str
    uploaded_files: List[str] = []
    error: Optional[str] = None


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    module: str = Form(...),
    files: List[UploadFile] = File(...),
    user: str = Depends(get_active_user),
    user_fs: UserScopedFS = Depends(get_user_fs),
    config_migrator: ConfigMigrator = Depends(get_config_migrator)
) -> UploadResponse:
    """
    Upload de fichiers pour un module spécifique.
    Les fichiers sont stockés directement dans {module}/data/ avec versioning automatique.
    """
    try:
        logger.info(f"Uploading {len(files)} files for module '{module}' (user: {user})")

        # Validation du module
        valid_modules = ["cointracking", "saxobank", "banks"]
        if module not in valid_modules:
            return UploadResponse(
                success=False,
                message=f"Module '{module}' non supporté",
                error="INVALID_MODULE"
            )

        # Créer le répertoire data (nouveau système simplifié)
        data_dir = user_fs.get_path(f"{module}/data")
        Path(data_dir).mkdir(parents=True, exist_ok=True)

        uploaded_files = []
        total_size = 0

        for file in files:
            # Validation du fichier
            if not file.filename:
                continue

            # Validation des extensions selon le module
            allowed_extensions = []
            if module == "cointracking":
                allowed_extensions = [".csv"]
            elif module == "saxobank":
                allowed_extensions = [".csv", ".json"]
            elif module == "banks":
                allowed_extensions = [".csv", ".xlsx", ".json"]

            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in allowed_extensions:
                return UploadResponse(
                    success=False,
                    message=f"Extension '{file_extension}' non autorisée pour {module}. Extensions valides: {', '.join(allowed_extensions)}",
                    error="INVALID_EXTENSION"
                )

            # Limitation de taille (10MB par fichier)
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:  # 10MB
                return UploadResponse(
                    success=False,
                    message=f"Fichier '{file.filename}' trop volumineux (max 10MB)",
                    error="FILE_TOO_LARGE"
                )

            total_size += len(content)

            # Générer un nom unique avec timestamp pour versioning
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
            unique_filename = f"{timestamp}_{safe_filename}"

            # Sauvegarder le fichier directement dans data/
            file_path = Path(data_dir) / unique_filename
            with open(file_path, 'wb') as f:
                f.write(content)

            uploaded_files.append(unique_filename)
            logger.info(f"Uploaded to data/: {unique_filename} ({len(content)} bytes)")

        # Limitation de taille totale (50MB par batch)
        if total_size > 50 * 1024 * 1024:  # 50MB
            return UploadResponse(
                success=False,
                message="Taille totale des fichiers trop importante (max 50MB par batch)",
                error="BATCH_TOO_LARGE"
            )

        if not uploaded_files:
            return UploadResponse(
                success=False,
                message="Aucun fichier valide uploadé",
                error="NO_FILES"
            )

        # Mettre à jour le timestamp dans la configuration
        try:
            config = config_migrator.load_sources_config()
            if module in config["modules"]:
                config["modules"][module]["last_import_at"] = datetime.utcnow().isoformat()
                config_migrator.save_sources_config(config)
        except Exception as e:
            logger.warning(f"Could not update config timestamp: {e}")

        return UploadResponse(
            success=True,
            message=f"{len(uploaded_files)} fichier(s) uploadé(s) avec succès dans data/",
            uploaded_files=uploaded_files
        )

    except Exception as e:
        logger.error(f"Upload failed for module '{module}': {e}")
        return UploadResponse(
            success=False,
            message="Erreur lors de l'upload",
            error="UPLOAD_ERROR"
        )