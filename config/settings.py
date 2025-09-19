#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration Settings - Centralisation avec Pydantic

Ce module centralise toute la configuration de l'application avec:
- Validation des types avec Pydantic
- Variables d'environnement sécurisées
- Configuration par environnement (dev/prod)
- Validation des contraintes
"""

import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
from pathlib import Path

class DatabaseConfig(BaseSettings):
    """Configuration base de données"""
    redis_url: str = Field(default="redis://localhost:6379", description="URL Redis")
    redis_db: int = Field(default=0, ge=0, le=15, description="Base Redis")
    connection_timeout: int = Field(default=30, ge=1, le=300, description="Timeout connexion")
    
    model_config = {
        'env_prefix': 'DB_'
    }

class APIKeysConfig(BaseSettings):
    """Configuration des clés API"""
    coingecko_api_key: Optional[str] = Field(None, description="Clé CoinGecko")
    fred_api_key: Optional[str] = Field(None, description="Clé FRED")
    cointracking_api_key: Optional[str] = Field(None, description="Clé CoinTracking")
    cointracking_api_secret: Optional[str] = Field(None, description="Secret CoinTracking")
    
    # Exchange API Keys (optionnel)
    binance_api_key: Optional[str] = Field(None, description="Clé Binance")
    binance_api_secret: Optional[str] = Field(None, description="Secret Binance")
    kraken_api_key: Optional[str] = Field(None, description="Clé Kraken")
    kraken_api_secret: Optional[str] = Field(None, description="Secret Kraken")
    
    @field_validator('coingecko_api_key', 'fred_api_key')
    @classmethod
    def validate_api_keys(cls, v):
        if v is not None and len(v) < 10:
            raise ValueError('Clé API trop courte')
        return v
    
    model_config = {
        'env_prefix': 'API_'
    }

class SecurityConfig(BaseSettings):
    """Configuration sécurité"""
    debug_token: str = Field(default="default-debug-token", description="Token debug")
    cors_origins: List[str] = Field(default=["http://localhost:3000"], description="Origins CORS")
    trusted_hosts: List[str] = Field(default=["localhost", "127.0.0.1"], description="Hôtes de confiance")
    max_request_size: int = Field(default=10*1024*1024, description="Taille max requête")
    rate_limit_requests: int = Field(default=0, description="Limite taux par heure (0=disabled)")
    rate_limit_window_sec: int = Field(default=3600, description="Fenêtre de rate limiting (sec)")

    # Content-Security-Policy (CSP) centralisée
    csp_script_src: List[str] = Field(default=["'self'", "https://cdn.jsdelivr.net"], description="Sources autorisées pour scripts")
    csp_style_src: List[str] = Field(default=["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"], description="Sources autorisées pour styles")
    csp_img_src: List[str] = Field(default=["'self'", "data:", "https:"], description="Sources autorisées pour images")
    csp_connect_src: List[str] = Field(
        default=[
            "'self'",
            "https://api.stlouisfed.org",
            "https://api.coingecko.com",
            "https://api.alternative.me",
            "https://crypto-toolbox.vercel.app"
        ],
        description="Sources autorisées pour connexions réseau"
    )
    csp_frame_ancestors: List[str] = Field(default=["'self'"], description="Origines autorisées pour l'embed (frame-ancestors)")
    csp_allow_inline_dev: bool = Field(default=True, description="Autoriser 'unsafe-inline' et 'unsafe-eval' en dev pour /docs/")
    
    @field_validator('debug_token')
    @classmethod
    def validate_debug_token(cls, v):
        if len(v) < 16:
            raise ValueError('Token debug doit faire au moins 16 caractères')
        return v
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    model_config = {
        'env_prefix': 'SECURITY_'
    }

class ExchangeConfig(BaseSettings):
    """Configuration exchanges"""
    default_exchange: str = Field(default="binance", description="Exchange par défaut")
    supported_exchanges: List[str] = Field(
        default=["binance", "kraken", "coinbase"], 
        description="Exchanges supportés"
    )
    max_order_size_usd: float = Field(default=10000.0, description="Taille max ordre USD")
    min_order_size_usd: float = Field(default=10.0, description="Taille min ordre USD")
    default_slippage_pct: float = Field(default=0.5, ge=0.0, le=10.0, description="Slippage défaut %")
    
    model_config = {
        'env_prefix': 'EXCHANGE_'
    }

class PricingConfig(BaseSettings):
    """Configuration pricing"""
    price_source: str = Field(default="auto", description="Source prix (local/market/auto/hybrid)")
    price_hybrid_max_age_min: int = Field(default=30, description="Age max prix hybride (min)")
    price_cache_ttl_sec: int = Field(default=300, description="TTL cache prix (sec)")
    price_update_interval_sec: int = Field(default=60, description="Intervalle MAJ prix (sec)")
    
    @field_validator('price_source')
    @classmethod
    def validate_price_source(cls, v):
        if v not in ['local', 'market', 'auto', 'hybrid']:
            raise ValueError('Source prix doit être: local, market, auto ou hybrid')
        return v
    
    model_config = {
        'env_prefix': 'PRICING_'
    }

class MLConfig(BaseSettings):
    """Configuration Machine Learning"""
    models_path: Path = Field(default=Path("models"), description="Chemin modèles")
    enable_ml_features: bool = Field(default=True, description="Activer ML")
    model_update_interval_hours: int = Field(default=24, description="Intervalle MAJ modèles")
    prediction_confidence_threshold: float = Field(default=0.7, description="Seuil confiance")
    max_model_age_days: int = Field(default=30, description="Age max modèles")
    
    @field_validator('models_path')
    @classmethod
    def validate_models_path(cls, v):
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
        return v
    
    model_config = {
        'env_prefix': 'ML_'
    }

class LoggingConfig(BaseSettings):
    """Configuration logging"""
    log_level: str = Field(default="INFO", description="Niveau log")
    log_format: str = Field(default="json", description="Format log (json/text)")
    log_file_path: Optional[Path] = Field(None, description="Chemin fichier log")
    log_max_size_mb: int = Field(default=100, description="Taille max log MB")
    log_backup_count: int = Field(default=5, description="Nombre backups log")
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level doit être: {", ".join(valid_levels)}')
        return v.upper()
    
    model_config = {
        'env_prefix': 'LOG_'
    }

class Settings(BaseSettings):
    """Configuration principale de l'application"""
    
    # Environnement
    environment: str = Field(default="development", description="Environnement")
    debug: bool = Field(default=False, description="Mode debug")
    
    # Sous-configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api_keys: APIKeysConfig = Field(default_factory=APIKeysConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    exchanges: ExchangeConfig = Field(default_factory=ExchangeConfig)
    pricing: PricingConfig = Field(default_factory=PricingConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    # Configuration serveur
    host: str = Field(default="127.0.0.1", description="Host serveur")
    port: int = Field(default=8000, ge=1, le=65535, description="Port serveur")
    workers: int = Field(default=1, ge=1, le=8, description="Nombre workers")
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v):
        valid_envs = ['development', 'staging', 'production']
        if v not in valid_envs:
            raise ValueError(f'Environment doit être: {", ".join(valid_envs)}')
        return v
    
    @field_validator('debug')
    @classmethod
    def validate_debug_for_prod(cls, v, info):
        # Note: Cette validation sera faite au niveau de l'instance plutôt qu'ici
        # car nous avons besoin d'accéder aux autres champs après initialisation
        return v
    
    def model_post_init(self, __context):
        """Validation post-initialisation"""
        if self.environment == 'production' and self.debug:
            raise ValueError('Debug ne peut pas être activé en production')
    
    def get_cors_origins(self) -> List[str]:
        """Obtenir les origins CORS selon l'environnement"""
        if self.environment == 'production':
            # En production, utiliser seulement les origins configurées
            return self.security.cors_origins
        else:
            # En dev, ajouter localhost par défaut
            origins = self.security.cors_origins.copy()
            dev_origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"]
            for origin in dev_origins:
                if origin not in origins:
                    origins.append(origin)
            return origins
    
    def is_production(self) -> bool:
        """Vérifier si on est en production"""
        return self.environment == 'production'
    
    def is_debug_enabled(self) -> bool:
        """Vérifier si le debug est activé"""
        return self.debug and not self.is_production()
    
    model_config = {
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
        'case_sensitive': False,
        'populate_by_name': True,
        'extra': 'ignore'
    }

# Instance globale des settings
settings = Settings()

# Fonction helper pour obtenir la configuration
def get_settings() -> Settings:
    """Obtenir l'instance de configuration"""
    return settings

# Export des configurations spécifiques
def get_database_config() -> DatabaseConfig:
    return settings.database

def get_api_keys_config() -> APIKeysConfig:
    return settings.api_keys

def get_security_config() -> SecurityConfig:
    return settings.security

def get_exchange_config() -> ExchangeConfig:
    return settings.exchanges

def get_pricing_config() -> PricingConfig:
    return settings.pricing

def get_ml_config() -> MLConfig:
    return settings.ml

def get_logging_config() -> LoggingConfig:
    return settings.logging

# Validation au chargement du module
if __name__ == "__main__":
    # Test de validation
    try:
        config = Settings()
        print("[OK] Configuration validée avec succès")
        print(f"Environment: {config.environment}")
        print(f"Debug: {config.is_debug_enabled()}")
        print(f"CORS Origins: {config.get_cors_origins()}")
        print(f"ML activé: {config.ml.enable_ml_features}")
    except Exception as e:
        print(f"[ERREUR] Configuration: {e}")
