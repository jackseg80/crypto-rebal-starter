"""
Module constants pour centraliser les constantes du projet.
"""

from .exchanges import (
    FAST_SELL_EXCHANGES,
    DEFI_HINTS, 
    COLD_HINTS,
    EXCHANGE_PRIORITIES,
    DEFAULT_EXCHANGE_PRIORITY,
    normalize_exchange_name,
    get_exchange_priority,
    classify_exchange_type,
    is_fast_sell_exchange,
    is_defi_exchange,
    is_cold_storage,
    format_exec_hint,
)

from .app_constants import (
    DEFAULT_API_TIMEOUT,
    DEFAULT_CACHE_TTL,
    MAX_RETRY_ATTEMPTS,
    MIN_TRADE_USD,
    DEFAULT_DRIFT_THRESHOLD,
    MAX_ALLOCATION_DRIFT,
    MIN_ASSET_VALUE_USD,
    CSV_ENCODING,
    RISK_LEVELS,
    ALERT_THRESHOLDS,
    DEFAULT_DATA_DIR,
    DEFAULT_RAW_DATA_DIR,
    DEFAULT_BACKUP_DIR,
    DEBUG_ENABLED,
    DEBUG_LOG_LEVEL,
    API_RATE_LIMIT,
)

__all__ = [
    # Exchange constants
    "FAST_SELL_EXCHANGES",
    "DEFI_HINTS",
    "COLD_HINTS", 
    "EXCHANGE_PRIORITIES",
    "DEFAULT_EXCHANGE_PRIORITY",
    "normalize_exchange_name",
    "get_exchange_priority",
    "classify_exchange_type",
    "is_fast_sell_exchange",
    "is_defi_exchange", 
    "is_cold_storage",
    "format_exec_hint",
    # Application constants
    "DEFAULT_API_TIMEOUT",
    "DEFAULT_CACHE_TTL",
    "MAX_RETRY_ATTEMPTS",
    "MIN_TRADE_USD",
    "DEFAULT_DRIFT_THRESHOLD",
    "MAX_ALLOCATION_DRIFT",
    "MIN_ASSET_VALUE_USD",
    "CSV_ENCODING",
    "RISK_LEVELS",
    "ALERT_THRESHOLDS",
    "DEFAULT_DATA_DIR",
    "DEFAULT_RAW_DATA_DIR",
    "DEFAULT_BACKUP_DIR",
    "DEBUG_ENABLED",
    "DEBUG_LOG_LEVEL",
    "API_RATE_LIMIT",
]
