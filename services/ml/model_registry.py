"""
Model Registry - Gestion centralisée des versions de modèles ML
Versioning, chargement, et métadonnées des modèles
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import pickle
import hashlib

logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    """États possibles d'un modèle"""
    TRAINING = "training"
    TRAINED = "trained"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    DEPRECATED = "deprecated"
    FAILED = "failed"


@dataclass
class ModelManifest:
    """Manifest d'un modèle avec métadonnées complètes"""
    name: str
    version: str
    model_type: str  # volatility, sentiment, risk, etc.
    status: ModelStatus

    # Métadonnées techniques
    created_at: datetime
    updated_at: datetime
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None

    # Métadonnées d'entraînement
    training_config: Optional[Dict[str, Any]] = None
    features_used: Optional[List[str]] = None
    training_data_period: Optional[Dict[str, str]] = None  # start_date, end_date
    hyperparameters: Optional[Dict[str, Any]] = None

    # Métriques de performance
    validation_metrics: Optional[Dict[str, float]] = None
    test_metrics: Optional[Dict[str, float]] = None

    # Métadonnées opérationnelles
    target_assets: Optional[List[str]] = None
    prediction_horizon: Optional[str] = None

    # Tags et description
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    author: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertir en dictionnaire pour sérialisation"""
        result = asdict(self)
        # Convertir les dates en ISO format
        for date_field in ['created_at', 'updated_at']:
            if result.get(date_field):
                result[date_field] = result[date_field].isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelManifest':
        """Créer depuis un dictionnaire"""
        # Convertir les dates depuis ISO format
        for date_field in ['created_at', 'updated_at']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(data[date_field])

        return cls(**data)


class ModelRegistry:
    """Registry centralisé pour la gestion des modèles ML"""

    def __init__(self, base_path: str = "models"):
        self.base_path = Path(base_path)
        self.registry_file = self.base_path / "registry.json"
        self._ensure_structure()
        self._load_registry()

    def _ensure_structure(self):
        """Créer la structure de répertoires"""
        self.base_path.mkdir(exist_ok=True)
        for model_type in ["volatility", "sentiment", "risk", "correlation", "blended"]:
            (self.base_path / model_type).mkdir(exist_ok=True)

    def _load_registry(self):
        """Charger le registry depuis le fichier"""
        try:
            if self.registry_file.exists():
                with open(self.registry_file, 'r') as f:
                    registry_data = json.load(f)

                self.models: Dict[str, Dict[str, ModelManifest]] = {}
                for model_name, versions in registry_data.items():
                    self.models[model_name] = {}
                    for version, manifest_data in versions.items():
                        self.models[model_name][version] = ModelManifest.from_dict(manifest_data)
            else:
                self.models = {}
        except Exception as e:
            logger.error(f"Failed to load model registry: {e}")
            self.models = {}

    def _save_registry(self):
        """Sauvegarder le registry dans le fichier"""
        try:
            registry_data = {}
            for model_name, versions in self.models.items():
                registry_data[model_name] = {}
                for version, manifest in versions.items():
                    registry_data[model_name][version] = manifest.to_dict()

            with open(self.registry_file, 'w') as f:
                json.dump(registry_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save model registry: {e}")

    def _compute_file_hash(self, file_path: Path) -> str:
        """Calculer le hash d'un fichier"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def register_model(
        self,
        name: str,
        version: str,
        model_type: str,
        model_object: Any = None,
        file_path: Optional[str] = None,
        **metadata
    ) -> ModelManifest:
        """
        Enregistrer un nouveau modèle

        Args:
            name: Nom du modèle
            version: Version (semver recommandé)
            model_type: Type de modèle
            model_object: Objet modèle à sérialiser (optionnel)
            file_path: Chemin vers fichier existant (optionnel)
            **metadata: Métadonnées supplémentaires
        """
        try:
            # Vérifier si la version existe déjà
            if name in self.models and version in self.models[name]:
                raise ValueError(f"Model {name} version {version} already exists")

            # Déterminer le chemin du fichier
            if file_path:
                final_path = Path(file_path)
            else:
                # Générer un chemin basé sur la structure
                model_dir = self.base_path / model_type / name / version
                model_dir.mkdir(parents=True, exist_ok=True)
                final_path = model_dir / "model.pkl"

                # Sérialiser l'objet modèle si fourni
                if model_object:
                    with open(final_path, 'wb') as f:
                        pickle.dump(model_object, f)

            # Calculer les métadonnées du fichier
            file_size = None
            file_hash = None
            if final_path.exists():
                file_size = final_path.stat().st_size
                file_hash = self._compute_file_hash(final_path)

            # Créer le manifest
            manifest = ModelManifest(
                name=name,
                version=version,
                model_type=model_type,
                status=ModelStatus.TRAINED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                file_path=str(final_path),
                file_size=file_size,
                file_hash=file_hash,
                **metadata
            )

            # Ajouter au registry
            if name not in self.models:
                self.models[name] = {}
            self.models[name][version] = manifest

            # Sauvegarder
            self._save_registry()

            logger.info(f"Registered model {name} version {version}")
            return manifest

        except Exception as e:
            logger.error(f"Failed to register model {name}:{version}: {e}")
            raise

    def load_model(self, name: str, version: Optional[str] = None) -> Any:
        """
        Charger un modèle depuis le registry

        Args:
            name: Nom du modèle
            version: Version spécifique (None = dernière version)
        """
        try:
            if name not in self.models:
                raise ValueError(f"Model {name} not found in registry")

            # Déterminer la version à charger
            if version is None:
                # Prendre la dernière version (tri sémantique simple)
                available_versions = list(self.models[name].keys())
                version = max(available_versions)

            if version not in self.models[name]:
                raise ValueError(f"Version {version} not found for model {name}")

            manifest = self.models[name][version]

            # Vérifier que le fichier existe
            if not manifest.file_path or not Path(manifest.file_path).exists():
                raise FileNotFoundError(f"Model file not found: {manifest.file_path}")

            # Charger le modèle
            with open(manifest.file_path, 'rb') as f:
                model = pickle.load(f)

            logger.info(f"Loaded model {name} version {version}")
            return model

        except Exception as e:
            logger.error(f"Failed to load model {name}:{version}: {e}")
            raise

    def get_manifest(self, name: str, version: Optional[str] = None) -> ModelManifest:
        """Obtenir le manifest d'un modèle"""
        if name not in self.models:
            raise ValueError(f"Model {name} not found")

        if version is None:
            version = max(self.models[name].keys())

        if version not in self.models[name]:
            raise ValueError(f"Version {version} not found for model {name}")

        return self.models[name][version]

    def list_models(self, model_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lister les modèles disponibles"""
        result = []

        for name, versions in self.models.items():
            for version, manifest in versions.items():
                if model_type is None or manifest.model_type == model_type:
                    result.append({
                        "name": name,
                        "version": version,
                        "model_type": manifest.model_type,
                        "status": manifest.status,
                        "created_at": manifest.created_at,
                        "file_size": manifest.file_size
                    })

        return sorted(result, key=lambda x: x['created_at'], reverse=True)

    def update_status(self, name: str, version: str, status: ModelStatus):
        """Mettre à jour le statut d'un modèle"""
        if name not in self.models or version not in self.models[name]:
            raise ValueError(f"Model {name}:{version} not found")

        self.models[name][version].status = status
        self.models[name][version].updated_at = datetime.now()
        self._save_registry()

        logger.info(f"Updated status of {name}:{version} to {status}")

    def update_metrics(
        self,
        name: str,
        version: str,
        validation_metrics: Optional[Dict[str, float]] = None,
        test_metrics: Optional[Dict[str, float]] = None
    ):
        """Mettre à jour les métriques d'un modèle"""
        if name not in self.models or version not in self.models[name]:
            raise ValueError(f"Model {name}:{version} not found")

        manifest = self.models[name][version]

        if validation_metrics:
            manifest.validation_metrics = validation_metrics

        if test_metrics:
            manifest.test_metrics = test_metrics

        manifest.updated_at = datetime.now()
        self._save_registry()

        logger.info(f"Updated metrics for {name}:{version}")

    def get_latest_version(self, name: str) -> Optional[str]:
        """Obtenir la dernière version d'un modèle"""
        if name not in self.models:
            return None

        versions = list(self.models[name].keys())
        return max(versions) if versions else None

    def deprecate_model(self, name: str, version: str, reason: Optional[str] = None):
        """Marquer un modèle comme déprécié"""
        if name not in self.models or version not in self.models[name]:
            raise ValueError(f"Model {name}:{version} not found")

        manifest = self.models[name][version]
        manifest.status = ModelStatus.DEPRECATED
        manifest.updated_at = datetime.now()

        if reason:
            if not manifest.tags:
                manifest.tags = []
            manifest.tags.append(f"deprecated: {reason}")

        self._save_registry()
        logger.info(f"Deprecated model {name}:{version}")


# === INSTANCE GLOBALE ===

_global_model_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Obtenir l'instance globale du model registry"""
    global _global_model_registry
    if _global_model_registry is None:
        _global_model_registry = ModelRegistry()
    return _global_model_registry


def initialize_model_registry(base_path: str = "models") -> ModelRegistry:
    """Initialiser le model registry avec un chemin spécifique"""
    global _global_model_registry
    _global_model_registry = ModelRegistry(base_path)
    return _global_model_registry