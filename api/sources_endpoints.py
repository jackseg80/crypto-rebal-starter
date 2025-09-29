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

            for pattern in module_config.get("patterns", []):
                files = user_fs.glob_files(pattern)
                for file_path in files:
                    try:
                        file_stat = os.stat(file_path)
                        path_obj = Path(file_path)
                        relative_path = str(path_obj.relative_to(user_fs.get_user_root()))

                        # Déterminer si c'est un fichier legacy
                        is_legacy = "csv/" in pattern or "/csv/" in relative_path

                        detected_file = DetectedFile(
                            name=path_obj.name,
                            relative_path=relative_path,
                            size_bytes=file_stat.st_size,
                            modified_at=datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                            is_legacy=is_legacy
                        )
                        detected_files.append(detected_file)
                    except (OSError, ValueError) as e:
                        logger.warning(f"Could not get file details for {file_path}: {e}")
                        continue

            # ✨ DÉTECTION ÉLARGIE: Ajouter patterns legacy pour compatibilité
            legacy_patterns = []
            if module_name == "cointracking":
                legacy_patterns = ["csv/CoinTracking*.csv", "csv/Current Balance*.csv", "csv/balance*.csv"]
            elif module_name == "saxobank":
                legacy_patterns = ["csv/saxo*.csv", "csv/positions*.csv", "csv/Portfolio*.csv"]

            for pattern in legacy_patterns:
                files = user_fs.glob_files(pattern)
                for file_path in files:
                    try:
                        file_stat = os.stat(file_path)
                        path_obj = Path(file_path)
                        relative_path = str(path_obj.relative_to(user_fs.get_user_root()))

                        # Éviter doublons si déjà dans detected_files
                        if any(df.relative_path == relative_path for df in detected_files):
                            continue

                        detected_file = DetectedFile(
                            name=path_obj.name,
                            relative_path=relative_path,
                            size_bytes=file_stat.st_size,
                            modified_at=datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                            is_legacy=True  # Marquer explicitement comme legacy
                        )
                        detected_files.append(detected_file)
                    except (OSError, ValueError) as e:
                        logger.warning(f"Could not get legacy file details for {file_path}: {e}")
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

            # Déterminer effective_read et effective_path
            effective_read = "none"
            effective_path = None

            # 1. Vérifier snapshot récent
            snapshot_path = f"{module_name}/snapshots/latest.csv"
            if user_fs.exists(snapshot_path):
                effective_read = "snapshot"
                effective_path = snapshot_path
            # 2. Vérifier imports
            elif user_fs.glob_files(f"{module_name}/imports/*.csv"):
                imports_files = user_fs.glob_files(f"{module_name}/imports/*.csv")
                effective_read = "imports"
                effective_path = str(Path(imports_files[0]).relative_to(user_fs.get_user_root())) if imports_files else None
            # 3. Vérifier legacy - prioriser les vrais legacy puis les autres
            elif detected_files:
                # Prioriser les fichiers explicitement legacy
                legacy_files = [f for f in detected_files if f.is_legacy]
                if legacy_files:
                    effective_read = "legacy"
                    effective_path = legacy_files[0].relative_path
                else:
                    # Fallback sur le premier fichier détecté
                    effective_read = "legacy"
                    effective_path = detected_files[0].relative_path

            # Ajuster modes dynamiquement selon les credentials API
            modes = list(module_config.get("modes", ["uploads"]))
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

            patterns = module_config.get("patterns", [])
            all_files = []
            is_legacy = False

            # Chercher des fichiers pour ce module
            for pattern in patterns:
                files = user_fs.glob_files(pattern)
                all_files.extend(files)

                # Détecter si c'est des fichiers legacy (csv/*)
                if pattern.startswith("csv/") and files:
                    is_legacy = True

            # Supprimer les doublons tout en préservant l'ordre
            seen = set()
            unique_files = []
            for f in all_files:
                if f not in seen:
                    seen.add(f)
                    unique_files.append(f)

            if unique_files:
                # Déterminer où les fichiers iraient
                target_dir = f"{module_name}/imports/"

                # Estimer le nombre d'enregistrements du fichier le plus récent
                estimated_records = None
                last_modified = None

                if unique_files:
                    # Trier par date de modification
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
                    would_move_to=target_dir,
                    estimated_records=estimated_records,
                    last_modified=last_modified,
                    is_legacy=is_legacy
                )

        return SourcesScanResponse(
            modules=scan_results,
            scan_timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error scanning sources: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du scan: {str(e)}")

@router.post("/import", response_model=ImportResponse)
async def import_module(
    request: ImportRequest,
    config_migrator: ConfigMigrator = Depends(get_config_migrator),
    user_fs: UserScopedFS = Depends(get_user_fs)
) -> ImportResponse:
    """
    Importe les fichiers d'un module depuis uploads/ ou legacy vers imports/.
    Parse et crée/met à jour le snapshot.
    """
    try:
        config = config_migrator.load_sources_config()

        if request.module not in config["modules"]:
            raise HTTPException(status_code=404, detail=f"Module {request.module} non trouvé")

        module_config = config["modules"][request.module]

        if not module_config.get("enabled", True):
            raise HTTPException(status_code=400, detail=f"Module {request.module} désactivé")

        # Vérifier si un import récent existe déjà
        if not request.force and module_config.get("last_import_at"):
            staleness = get_staleness_state(
                module_config["last_import_at"],
                module_config.get("snapshot_ttl_hours", 24),
                module_config.get("warning_threshold_hours", 12)
            )

            if staleness["state"] == "fresh":
                return ImportResponse(
                    success=True,
                    module=request.module,
                    files_processed=0,
                    snapshot_created=False,
                    message=f"Import récent déjà disponible ({staleness['age_hours']}h)"
                )

        # Collecter les fichiers à importer
        files_to_import = []

        if request.files:
            # Import de fichiers spécifiques
            user_root = user_fs.get_user_root()
            for file_path in request.files:
                # Convertir le chemin relatif en chemin absolu
                abs_path = user_fs.get_path(file_path)
                if user_fs.exists(file_path) and abs_path.endswith('.csv'):
                    files_to_import.append(abs_path)
                else:
                    logger.warning(f"Fichier spécifié non trouvé ou invalide: {file_path}")
        else:
            # Import de tous les fichiers détectés (comportement par défaut)
            patterns = module_config.get("patterns", [])
            for pattern in patterns:
                files = user_fs.glob_files(pattern)
                files_to_import.extend(files)

        if not files_to_import:
            return ImportResponse(
                success=False,
                module=request.module,
                files_processed=0,
                snapshot_created=False,
                message="Aucun fichier à importer",
                error="NO_FILES"
            )

        # Supprimer doublons et trier par date (plus récent en premier)
        unique_files = list(set(files_to_import))
        unique_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)

        # Créer le répertoire imports
        imports_dir = user_fs.get_path(f"{request.module}/imports")
        Path(imports_dir).mkdir(parents=True, exist_ok=True)

        files_processed = 0

        # Déplacer/copier les fichiers vers imports/
        for src_path in unique_files:
            src_file = Path(src_path)

            # Générer nom de destination avec timestamp si nécessaire
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_name = f"{src_file.stem}_{timestamp}{src_file.suffix}"
            dest_path = Path(imports_dir) / dest_name

            try:
                # Copier (ou déplacer si dans uploads/)
                if "/uploads/" in str(src_path):
                    shutil.move(str(src_path), str(dest_path))
                    logger.info(f"Moved {src_file.name} to imports/")
                else:
                    # Fichier legacy, copier seulement
                    shutil.copy2(str(src_path), str(dest_path))
                    logger.info(f"Copied legacy file {src_file.name} to imports/")

                files_processed += 1

            except Exception as e:
                logger.error(f"Failed to import {src_path}: {e}")
                continue

        # Créer/mettre à jour le snapshot
        snapshot_created = False
        if files_processed > 0:
            snapshot_created = await _create_snapshot(request.module, user_fs, imports_dir)

            # Mettre à jour la configuration
            module_config["last_import_at"] = datetime.utcnow().isoformat()
            config_migrator.save_sources_config(config)

        message = f"Importé {files_processed} fichier(s)"
        if snapshot_created:
            message += ", snapshot créé"

        return ImportResponse(
            success=True,
            module=request.module,
            files_processed=files_processed,
            snapshot_created=snapshot_created,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing module {request.module}: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur import: {str(e)}")

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

        # Créer le snapshot depuis le cache API
        api_cache_dir = user_fs.get_path(f"{request.module}/api_cache")
        snapshot_updated = await _create_snapshot(request.module, user_fs, api_cache_dir)

        # Mettre à jour la configuration
        module_config["last_import_at"] = datetime.utcnow().isoformat()
        config_migrator.save_sources_config(config)

        return RefreshApiResponse(
            success=True,
            module=request.module,
            records_fetched=records_fetched,
            snapshot_updated=snapshot_updated,
            message=f"API rafraîchie, {records_fetched or 0} enregistrements"
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

async def _create_snapshot(module: str, user_fs: UserScopedFS, source_dir: str) -> bool:
    """
    Crée un snapshot consolidé pour un module depuis un répertoire source.
    """
    try:
        # Créer le répertoire snapshots
        snapshots_dir = user_fs.get_path(f"{module}/snapshots")
        Path(snapshots_dir).mkdir(parents=True, exist_ok=True)

        # Pour l'instant, copier simplement le fichier le plus récent
        # TODO: Implémenter la consolidation réelle selon le module

        source_files = list(Path(source_dir).glob("*.csv"))
        if not source_files:
            return False

        # Prendre le plus récent
        latest_file = max(source_files, key=lambda f: f.stat().st_mtime)

        snapshot_name = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        snapshot_path = Path(snapshots_dir) / snapshot_name

        shutil.copy2(str(latest_file), str(snapshot_path))

        # Créer aussi un lien "latest" pour un accès facile
        latest_link = Path(snapshots_dir) / "latest.csv"
        if latest_link.exists():
            latest_link.unlink()

        shutil.copy2(str(snapshot_path), str(latest_link))

        logger.info(f"Created snapshot for {module}: {snapshot_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to create snapshot for {module}: {e}")
        return False

async def _refresh_cointracking_api(api_key: str, api_secret: str, user_fs: UserScopedFS) -> Optional[int]:
    """
    Rafraîchit les données CoinTracking via API.

    Returns:
        Optional[int]: Nombre d'enregistrements récupérés ou None si erreur
    """
    try:
        # Réutiliser la logique existante de csv_endpoints.py
        from api.csv_endpoints import get_csv_export_url
        import aiohttp

        # Créer le répertoire api_cache
        cache_dir = user_fs.get_path("cointracking/api_cache")
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

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

                    # Sauvegarder dans api_cache
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    cache_file = Path(cache_dir) / f"cointracking_balance_{timestamp}.csv"

                    with open(cache_file, 'wb') as f:
                        f.write(content)

                    # Estimer le nombre d'enregistrements
                    records = _estimate_csv_records(str(cache_file))

                    logger.info(f"Downloaded CoinTracking data: {records} records estimated")
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
    user_fs: UserScopedFS = Depends(get_user_fs)
) -> UploadResponse:
    """
    Upload de fichiers pour un module spécifique.
    Les fichiers sont stockés dans {module}/uploads/ pour traitement ultérieur.
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

        # Créer le répertoire uploads
        uploads_dir = user_fs.get_path(f"{module}/uploads")
        Path(uploads_dir).mkdir(parents=True, exist_ok=True)

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

            # Générer un nom unique avec timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
            unique_filename = f"{timestamp}_{safe_filename}"

            # Sauvegarder le fichier
            file_path = Path(uploads_dir) / unique_filename
            with open(file_path, 'wb') as f:
                f.write(content)

            uploaded_files.append(unique_filename)
            logger.info(f"Uploaded: {unique_filename} ({len(content)} bytes)")

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

        return UploadResponse(
            success=True,
            message=f"{len(uploaded_files)} fichier(s) uploadé(s) avec succès",
            uploaded_files=uploaded_files
        )

    except Exception as e:
        logger.error(f"Upload failed for module '{module}': {e}")
        return UploadResponse(
            success=False,
            message="Erreur lors de l'upload",
            error="UPLOAD_ERROR"
        )